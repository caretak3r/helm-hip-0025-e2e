"""Server-side facts for one test namespace, read from the kube-apiserver audit log.

Every ordering or readiness claim the suite makes comes from here, so all
timestamps share one clock (the apiserver's) at nanosecond resolution:

- applies/deletes: Helm's own create/patch/update/delete requests (userAgent Helm/*)
- readiness:       controller and client writes to the status subresource,
                   logged at RequestResponse level by kind/audit-policy.yaml
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from paths import AUDIT_LOG

# kind -> (apiGroup, resource)
RESOURCES = {
    "ConfigMap": ("", "configmaps"),
    "Secret": ("", "secrets"),
    "Service": ("", "services"),
    "ServiceAccount": ("", "serviceaccounts"),
    "PersistentVolumeClaim": ("", "persistentvolumeclaims"),
    "Pod": ("", "pods"),
    "Deployment": ("apps", "deployments"),
    "StatefulSet": ("apps", "statefulsets"),
    "DaemonSet": ("apps", "daemonsets"),
    "Job": ("batch", "jobs"),
    "Probe": ("readiness.hip0025.example", "probes"),
}
KIND_OF = {resource: kind for kind, (_, resource) in RESOURCES.items()}
# Objects without a status: ready the moment the apiserver accepted them.
STATUSLESS = {"ConfigMap", "Secret", "Service", "ServiceAccount", "PersistentVolumeClaim"}


def parse_ts(value: str) -> datetime:
    """RFC3339Nano -> aware datetime (microseconds; the log carries 6 digits)."""
    value = value.rstrip("Z")
    if "." in value:
        head, frac = value.split(".", 1)
        value = f"{head}.{frac[:6].ljust(6, '0')}"
    else:
        value += ".000000"
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=UTC)


def fmt_ts(ts: datetime | None) -> str:
    return ts.strftime("%H:%M:%S.%f")[:-3] if ts else "—"


@dataclass(frozen=True)
class Event:
    ts: datetime
    verb: str
    kind: str
    name: str
    subresource: str
    user_agent: str
    code: int
    obj: dict | None

    @property
    def by_helm(self) -> bool:
        return self.user_agent.startswith("Helm/")


class AuditLog:
    """Byte-offset view of the shared audit log."""

    def __init__(self, path: str = AUDIT_LOG):
        self.path = path

    def mark(self) -> int:
        try:
            return os.path.getsize(self.path)
        except OSError:
            return 0

    def read(self, offset: int, namespace: str, settle: float = 1.0) -> list[dict]:
        """Raw audit records for `namespace` written after `offset`.

        The apiserver log backend writes synchronously, but the kubelet and
        controllers report status a beat after Helm returns; `settle` lets the
        trailing status writes land before the slice is taken.
        """
        time.sleep(settle)
        records = []
        with open(self.path, "rb") as fh:
            fh.seek(offset)
            for line in fh:
                if namespace.encode() not in line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (rec.get("objectRef") or {}).get("namespace") == namespace:
                    records.append(rec)
        return records


class Timeline:
    def __init__(self, records: list[dict]):
        events = []
        for rec in records:
            if rec.get("stage") != "ResponseComplete":
                continue
            ref = rec.get("objectRef") or {}
            kind = KIND_OF.get(ref.get("resource", ""))
            if not kind:
                continue
            obj = rec.get("responseObject")
            name = ref.get("name") or ((obj or {}).get("metadata") or {}).get("name") or ""
            events.append(Event(
                ts=parse_ts(rec["requestReceivedTimestamp"]),
                verb=rec.get("verb", ""),
                kind=kind,
                name=name,
                subresource=ref.get("subresource") or "",
                user_agent=rec.get("userAgent", ""),
                code=(rec.get("responseStatus") or {}).get("code", 0),
                obj=obj,
            ))
        self.events = sorted(events, key=lambda e: e.ts)

    # ── Helm writes ─────────────────────────────────────────────────────
    def helm_applies(self) -> list[Event]:
        """Helm's create/patch/update of chart objects (release Secrets excluded)."""
        return [
            e for e in self.events
            if e.by_helm and e.verb in ("create", "patch", "update") and not e.subresource
            and e.code < 400 and not _is_release_record(e)
        ]

    def helm_deletes(self) -> list[Event]:
        return [
            e for e in self.events
            if e.by_helm and e.verb == "delete" and not e.subresource
            and e.code < 400 and not _is_release_record(e)
        ]

    def release_writes(self) -> list[Event]:
        """Helm's writes to its release records. The last one of an operation is the
        final status (deployed/failed), written after Helm stopped waiting: the
        server-clock proof of when an install or upgrade finished."""
        return [
            e for e in self.events
            if e.by_helm and _is_release_record(e) and e.verb in ("create", "update", "patch") and e.code < 400
        ]

    def finished(self) -> datetime | None:
        writes = self.release_writes()
        return writes[-1].ts if writes else None

    def applied(self, kind: str, name: str, after: datetime | None = None) -> datetime | None:
        for e in self.helm_applies():
            if e.kind == kind and e.name == name and (after is None or e.ts >= after):
                return e.ts
        return None

    def deleted(self, kind: str, name: str) -> datetime | None:
        for e in self.helm_deletes():
            if e.kind == kind and e.name == name:
                return e.ts
        return None

    # ── Status ──────────────────────────────────────────────────────────
    def status_writes(self, kind: str, name: str) -> list[Event]:
        return [
            e for e in self.events
            if e.kind == kind and e.name == name and e.subresource == "status"
            and e.obj is not None and e.code < 400
        ]

    def ready(self, kind: str, name: str, after: datetime | None = None) -> datetime | None:
        """First moment the apiserver recorded the object as ready (kstatus-equivalent
        for the kinds the fixtures use). Statusless kinds are ready when applied."""
        if kind in STATUSLESS:
            return self.applied(kind, name, after)
        for e in self.status_writes(kind, name):
            if after is not None and e.ts < after:
                continue
            if _ready(kind, e.obj):
                return e.ts
        return None

    def phase_changes(self, kind: str, name: str, field: str = "phase") -> list[tuple[datetime, object]]:
        """(timestamp, .status.<field>) for every status write that changed it."""
        out, last = [], object()
        for e in self.status_writes(kind, name):
            value = (e.obj.get("status") or {}).get(field)
            if value != last:
                out.append((e.ts, value))
                last = value
        return out


def _is_release_record(e: Event) -> bool:
    return e.kind == "Secret" and e.name.startswith("sh.helm.release.")


def _cond(obj: dict, ctype: str) -> str | None:
    for c in (obj.get("status") or {}).get("conditions") or []:
        if c.get("type") == ctype:
            return c.get("status")
    return None


def _ready(kind: str, obj: dict) -> bool:
    status = obj.get("status") or {}
    meta = obj.get("metadata") or {}
    if kind in ("Deployment", "StatefulSet"):
        want = (obj.get("spec") or {}).get("replicas", 1)
        # kstatus "Current": during a rollout the old pod still counts as ready,
        # so also require that no surplus (old) replicas remain.
        return (
            status.get("observedGeneration", 0) >= meta.get("generation", 0)
            and status.get("replicas", 0) == want
            and status.get("updatedReplicas", 0) >= want
            and status.get("readyReplicas", 0) >= want
            and status.get("availableReplicas", 0) >= want
        )
    if kind == "Job":
        return _cond(obj, "Complete") == "True" or status.get("succeeded", 0) >= 1
    if kind == "Pod":
        return _cond(obj, "Ready") == "True"
    return False
