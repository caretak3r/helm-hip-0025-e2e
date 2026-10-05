"""HIP-0025 end-to-end suite: real `helm` binaries against the kind cluster.

Run through `make run` (see README.md). One pytest process per tier, from the
repository root:

    uv run pytest e2e/tests --tier pr1 --helm .bin/helm-pr1 --out runs/<stamp>/pr1

Markers
    @pytest.mark.req("R05", ...)      HIP-0025 requirement(s) the test proves
    @pytest.mark.needs("subcharts")   features the tier must ship (tiers.yaml);
                                      otherwise the test is reported N/A
"""

from __future__ import annotations

import base64
import gzip
import json
import os
import re
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

E2E = Path(__file__).resolve().parent
sys.path.insert(0, str(E2E / "lib"))
from paths import CHARTS, CONTEXT, ROOT  # noqa: E402
from timeline import AuditLog, Timeline, fmt_ts  # noqa: E402


def pytest_addoption(parser):
    parser.addoption("--tier", required=True, help="tier from tiers.yaml (pr1, pr2, pr3, combined)")
    parser.addoption("--helm", required=True, help="helm binary under test")
    parser.addoption("--out", required=True, help="evidence directory for this tier")


def pytest_configure(config):
    config.addinivalue_line("markers", "req(*ids): HIP-0025 requirement ids")
    config.addinivalue_line("markers", "needs(*features): tier features the test requires")
    tiers = yaml.safe_load((ROOT / "tiers.yaml").read_text())["tiers"]
    tier = config.getoption("--tier")
    if tier not in tiers:
        raise pytest.UsageError(f"unknown tier {tier!r}; known: {', '.join(tiers)}")
    config._hip_tier = tier
    config._hip_features = set(tiers[tier]["features"])
    config._hip_results = []
    Path(config.getoption("--out")).mkdir(parents=True, exist_ok=True)


def pytest_collection_modifyitems(config, items):
    have = config._hip_features
    for item in items:
        marker = item.get_closest_marker("needs")
        need = set(marker.args) if marker else set()
        missing = sorted(need - have)
        if missing:
            item.add_marker(pytest.mark.skip(reason=f"N/A: tier has no {', '.join(missing)}"))


# ── Results plugin ─────────────────────────────────────────────────────────


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call" or (rep.when == "setup" and rep.outcome != "passed"):
        req = item.get_closest_marker("req")
        needs = item.get_closest_marker("needs")
        status = rep.outcome
        if hasattr(rep, "wasxfail"):
            status = "xfailed" if rep.skipped else "xpassed"
        reason = ""
        if rep.skipped and not hasattr(rep, "wasxfail"):
            reason = rep.longrepr[2] if isinstance(rep.longrepr, tuple) else str(rep.longrepr)
            reason = reason.replace("Skipped: ", "")
            if reason.startswith("N/A"):
                status = "n/a"
        elif rep.failed:
            reason = _short_failure(rep)
        elif hasattr(rep, "wasxfail"):
            reason = rep.wasxfail
        ctx = getattr(item, "_hip_ctx", None)
        item.config._hip_results.append({
            "nodeid": item.nodeid,
            "name": item.name,
            "doc": (item.function.__doc__ or "").strip(),
            "reqs": list(req.args) if req else [],
            "needs": list(needs.args) if needs else [],
            "outcome": status,
            "reason": reason,
            "duration": round(rep.duration, 2),
            "observations": ctx.observations if ctx else [],
            "evidence": str(ctx.dir.relative_to(Path(item.config.getoption("--out")).parent)) if ctx else "",
        })


def _short_failure(rep) -> str:
    """The assertion's own message; pytest's introspection lines follow it on "assert ..."."""
    crash = getattr(rep.longrepr, "reprcrash", None)
    text = (crash.message if crash else str(rep.longrepr)).strip()
    message = text.split("\nassert ")[0].split("\n  assert ")[0]
    return message[:1200]


def pytest_sessionfinish(session):
    config = session.config
    out = Path(config.getoption("--out"))
    helm = config.getoption("--helm")
    version = subprocess.run([helm, "version", "--short"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (out / "results.json").write_text(json.dumps({
        "tier": config._hip_tier,
        "features": sorted(config._hip_features),
        "helm": helm,
        "helm_version": version,
        "finished": datetime.now(UTC).isoformat(),
        "tests": config._hip_results,
    }, indent=2))


# ── Fixtures ──────────────────────────────────────────────────────────────


_LOG_LOCK = threading.Lock()


@dataclass
class Run:
    cmd: list[str]
    code: int
    out: str
    err: str
    started: datetime
    finished: datetime

    @property
    def seconds(self) -> float:
        return (self.finished - self.started).total_seconds()

    def __str__(self) -> str:
        return f"$ {' '.join(self.cmd)}\n[exit {self.code}, {self.seconds:.1f}s]\n{self.out}{self.err}"


@dataclass
class Ctx:
    """One test's handle on the cluster: a fresh namespace, the tier's helm binary,
    and an evidence directory the report links to."""

    tier: str
    helm_bin: str
    ns: str
    dir: Path
    env: dict
    audit: AuditLog = field(default_factory=AuditLog)
    observations: list = field(default_factory=list)
    start: int = 0
    _timers: list = field(default_factory=list)

    # commands --------------------------------------------------------------
    def run(self, cmd: list[str], check: bool | None = True, timeout: int = 600) -> Run:
        started = datetime.now(UTC)
        # Every command runs in the repository root, so the logged paths are the real, relative ones.
        proc = subprocess.run(cmd, capture_output=True, text=True, env=self.env, timeout=timeout, cwd=ROOT)
        run = Run(cmd, proc.returncode, proc.stdout, proc.stderr, started, datetime.now(UTC))
        with _LOG_LOCK, open(self.dir / "commands.log", "a") as fh:
            fh.write(f"{started.strftime('%H:%M:%S.%f')[:-3]} {run}\n\n")
        if check and run.code != 0:
            raise AssertionError(f"command failed:\n{run}")
        return run

    def helm(self, *args: str, check: bool | None = True, timeout: int = 600) -> Run:
        return self.run([self.helm_bin, *args, "--kube-context", CONTEXT], check=check, timeout=timeout)

    def kubectl(self, *args: str, check: bool | None = True) -> Run:
        return self.run(["kubectl", "--context", CONTEXT, *args], check=check)

    def chart(self, name: str) -> str:
        """The fixture chart, as a path relative to the repository root."""
        if not (CHARTS / name / "Chart.yaml").exists():
            raise FileNotFoundError(f"no fixture chart named {name!r} in {CHARTS.relative_to(ROOT)}/")
        return str((CHARTS / name).relative_to(ROOT))

    def _release_cmd(self, verb: str, release: str, chart: str | None, flags, values: dict | None, check):
        args = [verb, release] + ([self.chart(chart)] if chart else [])
        args += ["--namespace", self.ns]
        for key, value in (values or {}).items():
            args += ["--set", f"{key}={value}"]
        return self.helm(*args, *flags, check=check)

    def install(self, chart: str, *flags: str, release: str = "r", values: dict | None = None, check=True) -> Run:
        return self._release_cmd("install", release, chart, flags, values, check)

    def upgrade(self, chart: str, *flags: str, release: str = "r", values: dict | None = None, check=True) -> Run:
        return self._release_cmd("upgrade", release, chart, flags, values, check)

    def rollback(self, revision: int, *flags: str, release: str = "r", check=True) -> Run:
        return self.helm("rollback", release, str(revision), "--namespace", self.ns, *flags, check=check)

    def uninstall(self, *flags: str, release: str = "r", check=True) -> Run:
        return self.helm("uninstall", release, "--namespace", self.ns, *flags, check=check)

    # cluster state ---------------------------------------------------------
    def mark(self) -> int:
        return self.audit.mark()

    def timeline(self, since: int | None = None) -> Timeline:
        records = self.audit.read(self.start if since is None else since, self.ns)
        with open(self.dir / "audit.jsonl", "w") as fh:
            for rec in records:
                fh.write(json.dumps(rec) + "\n")
        return Timeline(records)

    def get(self, kind: str, name: str) -> dict:
        return json.loads(self.kubectl("get", kind, name, "-n", self.ns, "-o", "json").out)

    def exists(self, kind: str, name: str) -> bool:
        return self.kubectl("get", kind, name, "-n", self.ns, check=False).code == 0

    def release_record(self, release: str = "r", revision: int | None = None) -> dict | None:
        """Decoded release/v2 JSON from the storage Secret (None if absent)."""
        selector = f"owner=helm,name={release}" + (f",version={revision}" if revision else "")
        res = self.kubectl("get", "secret", "-n", self.ns, "-l", selector, "-o", "json")
        items = json.loads(res.out)["items"]
        if not items:
            return None
        items.sort(key=lambda s: int(s["metadata"]["labels"].get("version", "0")))
        raw = base64.b64decode(base64.b64decode(items[-1]["data"]["release"]))
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass
        return json.loads(raw)

    def later(self, seconds: float, fn, *args):
        """Run fn(*args) on a timer thread while a blocking helm command is in flight
        (e.g. flip a Probe's status mid-install). Joined when the test ends."""
        timer = threading.Timer(seconds, fn, args)
        timer.start()
        self._timers.append(timer)
        return timer

    def patch_status(self, kind: str, name: str, status: dict) -> Run:
        return self.kubectl("patch", kind, name, "-n", self.ns, "--subresource=status",
                            "--type=merge", "-p", json.dumps({"status": status}))

    # report ----------------------------------------------------------------
    def observe(self, label: str, value) -> None:
        """Record a fact the test asserted on; it is printed in the report."""
        self.observations.append({"label": label, "value": value})

    def observe_timeline(self, label: str, rows: list[tuple]) -> None:
        """rows: (timestamp, what) pairs, rendered as a sorted server-clock table."""
        rows = sorted(((ts, what) for ts, what in rows if ts is not None), key=lambda r: r[0])
        self.observe(label, [f"{fmt_ts(ts)}  {what}" for ts, what in rows])


@pytest.fixture(scope="session")
def tier(request) -> str:
    return request.config._hip_tier


@pytest.fixture(scope="session")
def session_env(request, tmp_path_factory) -> dict:
    home = tmp_path_factory.mktemp("helm-home")
    env = dict(os.environ)
    env.update({
        "HELM_EXPERIMENTAL_CHART_V3": "1",
        "HELM_CACHE_HOME": str(home / "cache"),
        "HELM_CONFIG_HOME": str(home / "config"),
        "HELM_DATA_HOME": str(home / "data"),
    })
    # scripts/cluster-up.sh installs the Probe CRD once. The tiers run in parallel,
    # so they must not race to create it.
    crd = subprocess.run(["kubectl", "--context", CONTEXT, "wait", "--for=condition=Established",
                          "crd/probes.readiness.hip0025.example", "--timeout=60s"], capture_output=True, text=True)
    if crd.returncode != 0:
        pytest.exit(f"the Probe CRD is not on {CONTEXT}; run scripts/cluster-up.sh first\n{crd.stderr}", returncode=3)
    return env


@pytest.fixture
def e2e(request, tier, session_env) -> Ctx:
    slug = re.sub(r"[^a-z0-9]+", "-", request.node.name.lower().removeprefix("test_")).strip("-")
    ns = f"e2e-{tier}-{slug}"[:63].rstrip("-")
    out = Path(request.config.getoption("--out")) / re.sub(r"[^\w.-]+", "_", request.node.name)
    out.mkdir(parents=True, exist_ok=True)
    (out / "commands.log").write_text("")
    ctx = Ctx(tier=tier, helm_bin=request.config.getoption("--helm"), ns=ns, dir=out, env=session_env)
    ctx.kubectl("delete", "namespace", ns, "--ignore-not-found", "--wait=true", "--timeout=120s", check=False)
    ctx.kubectl("create", "namespace", ns)
    ctx.start = ctx.mark()
    request.node._hip_ctx = ctx
    yield ctx
    for timer in ctx._timers:
        timer.join()
    (out / "observations.json").write_text(json.dumps(ctx.observations, indent=2, default=str))
    ctx.kubectl("delete", "namespace", ns, "--wait=false", check=False)


@pytest.fixture
def order():
    """Assert helpers that explain themselves in the failure message."""
    return Order()


class Order:
    @staticmethod
    def before(first_label: str, first_ts, second_label: str, second_ts):
        assert first_ts is not None, f"no audit record for {first_label}"
        assert second_ts is not None, f"no audit record for {second_label}"
        assert first_ts < second_ts, (
            f"{first_label} at {fmt_ts(first_ts)} is not before {second_label} at {fmt_ts(second_ts)}"
        )
