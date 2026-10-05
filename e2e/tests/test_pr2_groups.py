"""PR2 · resource-group sequencing (HIP-0025 "Resource-Group Sequencing")."""

import pytest

from paths import CONTEXT

CHART = "hip-groups"
SEQUENCED = ["db-service", "queue-processor", "my-app"]
UNSEQUENCED = ["loose", "orphan", "lonely"]


def _timeline_rows(tl, deployments, configmaps=()):
    rows = []
    for name in deployments:
        rows += [(tl.applied("Deployment", name), f"apply  Deployment/{name}"),
                 (tl.ready("Deployment", name), f"ready  Deployment/{name}")]
    for name in configmaps:
        rows.append((tl.applied("ConfigMap", name), f"apply  ConfigMap/{name}"))
    return rows


@pytest.mark.req("R20", "R21")
@pytest.mark.needs("ordered", "groups")
def test_groups_follow_the_hip_example(e2e, order):
    """database and queue deploy together; app starts only after both are ready."""
    e2e.install(CHART, "--wait=ordered", "--timeout", "3m")
    tl = e2e.timeline()
    e2e.observe_timeline("apiserver timeline", _timeline_rows(tl, SEQUENCED))

    db_apply, q_apply = tl.applied("Deployment", "db-service"), tl.applied("Deployment", "queue-processor")
    db_ready, q_ready = tl.ready("Deployment", "db-service"), tl.ready("Deployment", "queue-processor")
    app_apply = tl.applied("Deployment", "my-app")

    # R21: same batch — both siblings were sent before either became ready.
    order.before("last sibling applied", max(db_apply, q_apply), "first sibling ready", min(db_ready, q_ready))
    # R20: the dependent group waits for every group it depends on to be ready.
    order.before("db-service ready", db_ready, "my-app applied", app_apply)
    order.before("queue-processor ready", q_ready, "my-app applied", app_apply)


@pytest.mark.req("R22")
@pytest.mark.needs("ordered", "groups")
def test_unsequenced_resources_deploy_last_and_warn(e2e, order):
    """No annotations, a missing dependency, an isolated group: all after app, two warnings."""
    run = e2e.install(CHART, "--wait=ordered", "--timeout", "3m")
    tl = e2e.timeline()
    e2e.observe_timeline("apiserver timeline", _timeline_rows(tl, ["my-app"], UNSEQUENCED))

    app_ready = tl.ready("Deployment", "my-app")
    for name in UNSEQUENCED:
        order.before("my-app ready", app_ready, f"ConfigMap/{name} applied", tl.applied("ConfigMap", name))

    # slog's text handler escapes quotes (\"orphan\"); compare on the unescaped text.
    warnings = [line.replace('\\"', '"') for line in run.err.splitlines() if "level=WARN" in line]
    e2e.observe("helm warnings", warnings)
    assert any('"orphan" depends-on non-existent group' in w for w in warnings), "no warning for the missing dependency"
    assert any('"lonely" is isolated' in w for w in warnings), "no warning for the isolated group"
    assert not any("loose" in w for w in warnings), "an unannotated resource must not warn"


@pytest.mark.req("R23")
@pytest.mark.needs("ordered", "subcharts", "groups")
def test_group_sandboxing_parent_and_subchart_use_same_names(e2e, order):
    """Parent and subchart both define groups 'first' and 'second' with opposite edges; each chart's order holds independently."""
    e2e.install("hip-groups-sandbox", "--wait=ordered", "--timeout", "3m")
    tl = e2e.timeline()

    parent_deployments = ["parent-first", "parent-second"]
    sub_deployments = ["sub-second", "sub-first"]
    e2e.observe_timeline("apiserver timeline", _timeline_rows(tl, parent_deployments + sub_deployments))

    # Parent chart: first -> second
    p_first_ready = tl.ready("Deployment", "parent-first")
    p_second_apply = tl.applied("Deployment", "parent-second")
    order.before("parent-first ready", p_first_ready, "parent-second applied", p_second_apply)

    # Subchart: second -> first (opposite!)
    s_second_ready = tl.ready("Deployment", "sub-second")
    s_first_apply = tl.applied("Deployment", "sub-first")
    order.before("sub-second ready", s_second_ready, "sub-first applied", s_first_apply)


@pytest.mark.req("R24")
@pytest.mark.needs("ordered", "groups")
def test_group_cycle_detected_and_rejected(e2e):
    """Circular group dependency (a -> b -> c -> a) exits non-zero naming the cycle, nothing applied."""
    run = e2e.install("hip-groups-cycle", "--wait=ordered", check=False)
    e2e.observe("exit code", run.code)
    e2e.observe("stderr", run.err)

    assert run.code != 0, "install with group cycle must fail"
    assert "cycle" in run.err.lower() or "circular" in run.err.lower(), f"error must mention cycle: {run.err}"

    # Nothing should be applied
    tl = e2e.timeline()
    applies = tl.helm_applies()
    e2e.observe("apiserver applies", [(a.ts, f"{a.kind}/{a.name}") for a in applies])
    assert len(applies) == 0, f"expected no applies but got {len(applies)}"

    # helm lint should also fail
    lint_run = e2e.helm("lint", e2e.chart("hip-groups-cycle"), check=False)
    e2e.observe("helm lint exit code", lint_run.code)
    assert lint_run.code != 0, "helm lint must fail on cycle"


@pytest.mark.req("R25")
@pytest.mark.needs("ordered", "groups")
def test_hip_dependency_key_is_removed_before_apply(e2e, order):
    """The HIP key helm.sh/depends-on/resource-groups orders groups, is kept in the release, and never reaches the API server."""
    key = "helm.sh/depends-on/resource-groups"
    # The API server rejects the key (two '/'), which is why Helm must remove it.
    kubectl = f"kubectl --context {CONTEXT}"
    rejected = e2e.run(["sh", "-c", (
        f"{kubectl} create configmap key-probe -n {e2e.ns} --dry-run=client -o yaml"
        f" | {kubectl} annotate -f - '{key}=[]' --local -o yaml"
        f" | {kubectl} apply --dry-run=server -f -")], check=False)
    e2e.observe("API server on the HIP key", rejected.err.strip() or f"exit {rejected.code}")
    assert rejected.code != 0 and key in rejected.err, "expected the API server to reject the HIP key"

    e2e.install(CHART, "--wait=ordered", "--timeout", "3m")
    tl = e2e.timeline()
    live = e2e.get("Deployment", "my-app")["metadata"].get("annotations", {})
    stored = e2e.release_record()["manifest"]
    e2e.observe("my-app annotations on the cluster", live)
    e2e.observe("key in the stored release manifest", key in stored)
    e2e.observe_timeline("apiserver timeline", _timeline_rows(tl, SEQUENCED))

    assert key not in live, "the HIP key must be removed before apply"
    assert live.get("helm.sh/resource-group") == "app", "helm.sh/resource-group must be kept"
    assert key in stored, "the stored release keeps the key so the plan can be rebuilt"
    order.before("db-service ready", tl.ready("Deployment", "db-service"), "my-app applied", tl.applied("Deployment", "my-app"))
    order.before("queue-processor ready", tl.ready("Deployment", "queue-processor"),
                 "my-app applied", tl.applied("Deployment", "my-app"))


@pytest.mark.req("R26")
@pytest.mark.needs("groups")
@pytest.mark.xfail(strict=True, reason="R26 not implemented: helm template does not print START/END resource-group delimiters")
def test_template_prints_delimiters_for_groups(e2e):
    """helm template prints resources in deploy order with ## START/END resource-group delimiters."""
    run = e2e.helm("template", "test-release", e2e.chart("hip-groups"))
    e2e.observe("helm template output", run.out)

    # HIP requirement: delimiters like "## START resource-group: <chart>/<subchart> <group-name>"
    assert "## START resource-group:" in run.out, "template output must contain START resource-group delimiter"
    assert "## END resource-group:" in run.out, "template output must contain END resource-group delimiter"

    # Groups should appear in dependency order
    lines = run.out.splitlines()
    start_indices = {}
    for i, line in enumerate(lines):
        if "## START resource-group:" in line:
            # Extract group name from delimiter
            parts = line.split()
            if len(parts) >= 4:
                group = parts[-1]
                start_indices[group] = i

    e2e.observe("group start indices", start_indices)
    # database and queue should come before app
    assert "database" in start_indices, "database group must appear"
    assert "queue" in start_indices, "queue group must appear"
    assert "app" in start_indices, "app group must appear"
    assert start_indices["app"] > start_indices["database"], "app must come after database"
    assert start_indices["app"] > start_indices["queue"], "app must come after queue"


@pytest.mark.req("R08")
@pytest.mark.needs("ordered", "groups")
def test_upgrade_follows_group_order(e2e, order):
    """Upgrade patches every Deployment; patches follow database/queue -> app, and app's patch comes after both are ready again."""
    # Initial install
    e2e.install("hip-groups-upgrade", "--wait=ordered", "--timeout", "3m", values={"patchValue": "v1"})

    # Upgrade with a new value that patches all Deployments
    mark = e2e.mark()
    e2e.upgrade("hip-groups-upgrade", "--wait=ordered", "--timeout", "3m", values={"patchValue": "v2"})

    tl_upgrade = e2e.timeline(since=mark)
    e2e.observe_timeline("upgrade timeline", _timeline_rows(tl_upgrade, ["db", "queue", "app"]))

    # Verify all deployments were patched
    for name in ["db", "queue", "app"]:
        obj = e2e.get("Deployment", name)
        patch_val = obj["metadata"]["annotations"]["patch-marker"]
        e2e.observe(f"{name} patch-marker", patch_val)
        assert patch_val == "v2", f"{name} must be patched to v2"

    # Get apply timestamps from the upgrade timeline
    from timeline import fmt_ts
    db_apply = tl_upgrade.applied("Deployment", "db")
    queue_apply = tl_upgrade.applied("Deployment", "queue")
    app_apply = tl_upgrade.applied("Deployment", "app")

    # Get ready timestamps from the full timeline (they may have stayed ready)
    tl_full = e2e.timeline()
    db_ready = tl_full.ready("Deployment", "db", after=db_apply)
    queue_ready = tl_full.ready("Deployment", "queue", after=queue_apply)

    e2e.observe("db patched", fmt_ts(db_apply) if db_apply else None)
    e2e.observe("queue patched", fmt_ts(queue_apply) if queue_apply else None)
    e2e.observe("app patched", fmt_ts(app_apply) if app_apply else None)
    e2e.observe("db ready after patch", fmt_ts(db_ready) if db_ready else None)
    e2e.observe("queue ready after patch", fmt_ts(queue_ready) if queue_ready else None)
    # Verify patches followed group order: db and queue before app, and app after both are ready
    order.before("db patched", db_apply, "app patched", app_apply)
    order.before("queue patched", queue_apply, "app patched", app_apply)

    # Gating: app is patched only after the new db and queue pods are ready.
    order.before("db ready after patch", db_ready, "app patched", app_apply)
    order.before("queue ready after patch", queue_ready, "app patched", app_apply)


@pytest.mark.req("R09")
@pytest.mark.needs("ordered", "groups")
def test_uninstall_runs_in_reverse_order(e2e, order):
    """Uninstall after ordered install deletes app before database and queue (reverse of install order)."""
    e2e.install("hip-groups-upgrade", "--wait=ordered", "--timeout", "3m")

    mark = e2e.mark()
    e2e.uninstall("--wait=ordered", "--timeout", "3m")

    tl = e2e.timeline(since=mark)
    deletes = tl.helm_deletes()
    e2e.observe_timeline("uninstall timeline", [(d.ts, f"delete {d.kind}/{d.name}") for d in deletes])

    # Find deletion timestamps
    from timeline import fmt_ts
    deletions = {d.name: d.ts for d in deletes if d.kind == "Deployment"}
    e2e.observe("deletion timestamps", {k: fmt_ts(v) for k, v in deletions.items()})

    assert "app" in deletions, "app must be deleted"
    assert "db" in deletions, "db must be deleted"
    assert "queue" in deletions, "queue must be deleted"

    # app should be deleted before db and queue (reverse order)
    order.before("app deleted", deletions["app"], "db deleted", deletions["db"])
    order.before("app deleted", deletions["app"], "queue deleted", deletions["queue"])
