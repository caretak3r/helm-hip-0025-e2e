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


@pytest.mark.req("R17", "R18")
@pytest.mark.needs("ordered", "groups")
def test_groups_follow_the_hip_example(e2e, order):
    """database and queue deploy together; app starts only after both are ready."""
    e2e.install(CHART, "--wait=ordered", "--timeout", "3m")
    tl = e2e.timeline()
    e2e.observe_timeline("apiserver timeline", _timeline_rows(tl, SEQUENCED))

    db_apply, q_apply = tl.applied("Deployment", "db-service"), tl.applied("Deployment", "queue-processor")
    db_ready, q_ready = tl.ready("Deployment", "db-service"), tl.ready("Deployment", "queue-processor")
    app_apply = tl.applied("Deployment", "my-app")

    # R18: same batch — both siblings were sent before either became ready.
    order.before("last sibling applied", max(db_apply, q_apply), "first sibling ready", min(db_ready, q_ready))
    # R17: the dependent group waits for every group it depends on to be ready.
    order.before("db-service ready", db_ready, "my-app applied", app_apply)
    order.before("queue-processor ready", q_ready, "my-app applied", app_apply)


@pytest.mark.req("R19")
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


@pytest.mark.req("R20")
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


@pytest.mark.req("R21")
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


@pytest.mark.req("R22")
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




@pytest.mark.req("R23")
@pytest.mark.needs("ordered", "groups")
def test_duplicate_resource_group_assignment_rejected(e2e):
    """Same resource assigned to two groups: install fails with 'assigned to multiple resource groups', nothing applied."""
    run = e2e.helm("install", "r", e2e.chart("hip-groups-duplicate"),
                   "--namespace", e2e.ns, "--wait=ordered", "--timeout", "1m",
                   check=False)

    e2e.observe("install exit code", run.code)
    e2e.observe("error message", run.err[:600])

    assert run.code != 0, "install must fail when same resource is in multiple groups"
    assert "assigned to multiple resource groups" in run.err, \
        "error must contain 'assigned to multiple resource groups'"

    # Verify nothing was applied
    tl = e2e.timeline()
    assert not tl.applied("Deployment", "conflicting-app"), \
        "conflicting resource must not have been applied"
@pytest.mark.req("R24")
@pytest.mark.needs("groups")
def test_template_prints_delimiters_for_groups(e2e):
    """helm template prints resources in deploy order with ## START/END resource-group delimiters."""
    run = e2e.helm("template", "test-release", e2e.chart("hip-groups"))
    e2e.observe("helm template output", run.out)

    # HIP requirement: delimiters like "## START resource-group: <chart> <group>"
    assert "## START resource-group:" in run.out, "template output must contain START resource-group delimiter"
    assert "## END resource-group:" in run.out, "template output must contain END resource-group delimiter"

    # Parse START and END markers
    lines = run.out.splitlines()
    start_markers = {}  # group name -> (line index, chart_group label)
    end_markers = {}    # group name -> (line index, chart_group label)

    for i, line in enumerate(lines):
        if "## START resource-group:" in line:
            # Format: "## START resource-group: <chart> <group>"
            parts = line.split()
            if len(parts) >= 4:
                chart_group = " ".join(parts[3:])  # e.g. "hip-groups database"
                group = parts[-1]  # last token is the group name
                start_markers[group] = (i, chart_group)
        elif "## END resource-group:" in line:
            parts = line.split()
            if len(parts) >= 4:
                chart_group = " ".join(parts[3:])
                group = parts[-1]
                end_markers[group] = (i, chart_group)

    e2e.observe("START markers", {k: v[0] for k, v in start_markers.items()})
    e2e.observe("END markers", {k: v[0] for k, v in end_markers.items()})

    # Every START must have a matching END with the same chart and group
    assert start_markers.keys() == end_markers.keys(), \
        f"START and END groups must match: START={set(start_markers.keys())}, END={set(end_markers.keys())}"

    for group in start_markers:
        start_idx, start_label = start_markers[group]
        end_idx, end_label = end_markers[group]
        assert start_label == end_label, \
            f"START and END labels must match for {group}: START={start_label}, END={end_label}"
        assert end_idx > start_idx, \
            f"END must come after START for {group}: START={start_idx}, END={end_idx}"

    # Groups should appear in dependency order: database and queue before app
    assert "database" in start_markers, "database group must appear"
    assert "queue" in start_markers, "queue group must appear"
    assert "app" in start_markers, "app group must appear"

    db_start = start_markers["database"][0]
    queue_start = start_markers["queue"][0]
    app_start = start_markers["app"][0]

    assert app_start > db_start, "app must come after database"
    assert app_start > queue_start, "app must come after queue"

@pytest.mark.req("R09")
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


@pytest.mark.req("R10")
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
