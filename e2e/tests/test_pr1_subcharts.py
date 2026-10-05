"""PR1 · subchart sequencing (HIP-0025 "Chart dependencies example")."""

import pytest

CHART = "hip-subcharts"
SUBCHARTS = ["nginx", "rabbitmq", "bar", "foo"]


def _timeline_rows(tl, deployments):
    rows = []
    for name in deployments:
        rows += [(tl.applied("Deployment", name), f"apply  Deployment/{name}"),
                 (tl.ready("Deployment", name), f"ready  Deployment/{name}")]
    return rows


@pytest.mark.req("R01")
@pytest.mark.needs("ordered", "subcharts")
def test_plain_wait_applies_everything_at_once(e2e, order):
    """--wait applies all four Deployments together; at least one dependent before dependency ready."""
    e2e.install(CHART, "--wait", "--timeout", "3m")
    tl = e2e.timeline()
    e2e.observe_timeline("apiserver timeline", _timeline_rows(tl, SUBCHARTS))

    applies = [tl.applied("Deployment", name) for name in SUBCHARTS]

    burst_max = max(applies)
    burst_min = min(applies)
    burst_duration = (burst_max - burst_min).total_seconds()
    e2e.observe("apply burst duration (seconds)", burst_duration)

    # R01: everything applied within one burst (< 1s)
    assert burst_duration < 1.0, f"expected one burst, got {burst_duration}s spread"

    # At least one dependent applied before its dependency was ready (proves no gating)
    bar_apply = tl.applied("Deployment", "bar")
    nginx_ready = tl.ready("Deployment", "nginx")
    rabbitmq_ready = tl.ready("Deployment", "rabbitmq")

    # bar depends on nginx and rabbitmq, so with plain --wait it should apply before they're ready
    assert bar_apply < min(nginx_ready, rabbitmq_ready), \
        "plain --wait should not gate: bar applied before nginx/rabbitmq ready"


@pytest.mark.req("R15")
@pytest.mark.needs("ordered", "subcharts")
def test_independent_subcharts_deploy_together(e2e, order):
    """nginx and rabbitmq (no mutual dependency) applied together before either is ready."""
    e2e.install(CHART, "--wait=ordered", "--timeout", "3m")
    tl = e2e.timeline()
    e2e.observe_timeline("apiserver timeline", _timeline_rows(tl, SUBCHARTS))

    nginx_apply, nginx_ready = tl.applied("Deployment", "nginx"), tl.ready("Deployment", "nginx")
    rabbitmq_apply, rabbitmq_ready = tl.applied("Deployment", "rabbitmq"), tl.ready("Deployment", "rabbitmq")

    # R15: nginx and rabbitmq have no dependency between them, so both should be
    # applied before either is ready (parallel deployment)
    order.before("last sibling applied", max(nginx_apply, rabbitmq_apply),
                 "first sibling ready", min(nginx_ready, rabbitmq_ready))


@pytest.mark.req("R05", "R04", "R03")
@pytest.mark.needs("ordered", "subcharts")
def test_subcharts_dag_order_and_gating(e2e, order):
    """bar waits for nginx+rabbitmq ready; foo waits for bar ready."""
    e2e.install(CHART, "--wait=ordered", "--timeout", "3m")
    tl = e2e.timeline()
    e2e.observe_timeline("apiserver timeline", _timeline_rows(tl, SUBCHARTS))

    nginx_ready = tl.ready("Deployment", "nginx")
    rabbitmq_ready = tl.ready("Deployment", "rabbitmq")
    bar_apply, bar_ready = tl.applied("Deployment", "bar"), tl.ready("Deployment", "bar")
    foo_apply = tl.applied("Deployment", "foo")

    # R03/R05: bar applied after BOTH nginx and rabbitmq are ready
    order.before("nginx ready", nginx_ready, "bar applied", bar_apply)
    order.before("rabbitmq ready", rabbitmq_ready, "bar applied", bar_apply)

    # R04: foo (parent) applied after bar is ready
    order.before("bar ready", bar_ready, "foo applied", foo_apply)


@pytest.mark.req("R02")
@pytest.mark.needs("ordered", "subcharts")
def test_release_record_has_plan_when_sequenced(e2e):
    """Ordered install has plan with batches; plain --wait has no plan."""
    # First test plain --wait (no plan)
    e2e.install(CHART, "--wait", "--timeout", "3m", release="plain")
    plain_rec = e2e.release_record(release="plain")
    e2e.observe("plain --wait release plan", plain_rec.get("plan"))
    assert plain_rec.get("plan") is None, "plain --wait should not store a plan"
    e2e.uninstall(release="plain")

    # Now test --wait=ordered (has plan)
    e2e.install(CHART, "--wait=ordered", "--timeout", "3m", release="ordered")
    plan = e2e.release_record(release="ordered").get("plan")
    assert plan is not None, "ordered install should store a plan"
    batches = [(b["chartPath"], b["kind"], [m["path"] for m in b["manifests"]]) for b in plan["batches"]]
    e2e.observe("stored plan batches (chartPath, kind, manifests)", [str(b) for b in batches])

    # The stored plan must encode the DAG: nginx and rabbitmq before bar, bar before foo.
    position = {path: i for i, (path, _, _) in enumerate(batches)}
    for chart in ("foo/charts/nginx", "foo/charts/rabbitmq", "foo/charts/bar", "foo"):
        assert chart in position, f"plan has no batch for {chart}: {list(position)}"
    assert max(position["foo/charts/nginx"], position["foo/charts/rabbitmq"]) < position["foo/charts/bar"], \
        "bar's batch must come after nginx's and rabbitmq's"
    assert position["foo/charts/bar"] < position["foo"], "foo's own resources must come after bar"


@pytest.mark.req("R03")
@pytest.mark.needs("ordered", "subcharts")
def test_subchart_alias_dependency(e2e, order):
    """zeta with alias z-service; alpha depends on both alias and original name; order respected."""
    e2e.install("hip-subcharts-alias", "--wait=ordered", "--timeout", "3m")
    tl = e2e.timeline()

    zeta_apply, zeta_ready = tl.applied("Deployment", "zeta"), tl.ready("Deployment", "zeta")
    alpha_apply = tl.applied("Deployment", "alpha")
    parent_apply = tl.applied("Deployment", "parent")

    e2e.observe_timeline("apiserver timeline", [
        (zeta_apply, "apply  Deployment/zeta"),
        (zeta_ready, "ready  Deployment/zeta"),
        (alpha_apply, "apply  Deployment/alpha"),
        (parent_apply, "apply  Deployment/parent"),
    ])

    # alpha depends on zeta (by both alias and name), so alpha applies after zeta ready
    order.before("zeta ready", zeta_ready, "alpha applied", alpha_apply)

    # parent applies after alpha ready (no explicit dependency, but alpha is a subchart)
    alpha_ready = tl.ready("Deployment", "alpha")
    order.before("alpha ready", alpha_ready, "parent applied", parent_apply)


@pytest.mark.req("R05")
@pytest.mark.needs("ordered", "subcharts")
def test_nested_subcharts_three_levels(e2e, order):
    """grandchild-a → child-b → parent-z; each level applied after the level below is ready."""
    e2e.install("hip-subcharts-nested", "--wait=ordered", "--timeout", "3m")
    tl = e2e.timeline()

    grandchild_apply, grandchild_ready = tl.applied("Deployment", "grandchild-a"), tl.ready("Deployment", "grandchild-a")
    child_apply, child_ready = tl.applied("Deployment", "child-b"), tl.ready("Deployment", "child-b")
    parent_apply = tl.applied("Deployment", "parent-z")

    e2e.observe_timeline("apiserver timeline", [
        (grandchild_apply, "apply  Deployment/grandchild-a"),
        (grandchild_ready, "ready  Deployment/grandchild-a"),
        (child_apply, "apply  Deployment/child-b"),
        (child_ready, "ready  Deployment/child-b"),
        (parent_apply, "apply  Deployment/parent-z"),
    ])

    # child-b applied after grandchild-a ready
    order.before("grandchild-a ready", grandchild_ready, "child-b applied", child_apply)

    # parent-z applied after child-b ready
    order.before("child-b ready", child_ready, "parent-z applied", parent_apply)


@pytest.mark.req("R06")
@pytest.mark.needs("ordered", "subcharts")
def test_subchart_cycle_detected(e2e):
    """Cycle (a→b, b→a) fails helm install and helm lint; no objects applied."""
    chart_path = e2e.chart("hip-subcharts-cycle")

    # helm install --wait=ordered should fail with cycle error
    run = e2e.helm("install", "cycle-test", chart_path, "--wait=ordered", "--timeout", "2m", check=False)
    e2e.observe("install exit code", run.code)
    e2e.observe("install stderr", run.err)

    assert run.code != 0, "install with cycle should fail"
    # Check that error message mentions the cycle
    assert "cycle" in run.err.lower() or "circular" in run.err.lower(), \
        f"error should mention cycle/circular dependency: {run.err}"

    # Verify no Helm objects were applied to the cluster
    tl = e2e.timeline()
    helm_applies = tl.helm_applies()
    e2e.observe("helm apply count", len(helm_applies))
    assert len(helm_applies) == 0, f"expected no applies with cycle, got {len(helm_applies)}"

    # helm lint should also fail
    lint_run = e2e.helm("lint", chart_path, check=False)
    e2e.observe("lint exit code", lint_run.code)
    e2e.observe("lint output", lint_run.out + lint_run.err)

    assert lint_run.code != 0, "lint should fail for chart with cycle"
    lint_output = lint_run.out + lint_run.err
    assert "cycle" in lint_output.lower() or "circular" in lint_output.lower(), \
        f"lint should mention cycle: {lint_output}"


@pytest.mark.req("R07")
@pytest.mark.needs("ordered", "subcharts")
def test_helm_dag_prints_subchart_order(e2e):
    """helm dag prints nginx and rabbitmq before bar."""
    chart_path = e2e.chart(CHART)
    run = e2e.helm("dag", chart_path)
    e2e.observe("helm dag output", run.out)

    # The parent chart's block lists its subchart batches: "Batch N: a, b".
    parent_block = run.out.split("  Chart: foo/charts/")[0]
    batches = [
        [name.strip() for name in line.split(":", 1)[1].split(",")]
        for line in parent_block.splitlines() if line.strip().startswith("Batch ")
    ]
    e2e.observe("subchart batches printed for foo", [", ".join(b) for b in batches])
    assert len(batches) >= 2 and sorted(batches[0]) == ["nginx", "rabbitmq"] and batches[1] == ["bar"], \
        f"expected Batch 1: nginx, rabbitmq then Batch 2: bar, got {batches}"
