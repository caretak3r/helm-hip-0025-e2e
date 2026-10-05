"""PR1 · lifecycle operations (upgrade, uninstall, rollback, failure handling, hooks)."""

import pytest

CHART = "hip-lifecycle"
CHART_FAILURE = "hip-lifecycle-failure"
CHART_HOOKS = "hip-lifecycle-hooks"


def _timeline_rows(tl, names):
    """Helper to collect apply/ready pairs for deployments."""
    rows = []
    for name in names:
        applied = tl.applied("Deployment", name)
        ready = tl.ready("Deployment", name)
        rows += [(applied, f"apply  Deployment/{name}"),
                 (ready, f"ready  Deployment/{name}")]
    return rows


@pytest.mark.req("R08", "R35")
@pytest.mark.needs("ordered", "subcharts")
def test_upgrade_follows_install_order_and_waits_leaf(e2e, order):
    """Upgrade patches a -> b -> parent, each after the previous is ready again; helm finishes after the leaf is ready."""
    e2e.install(CHART, "--wait=ordered", "--timeout", "3m", values={"global.rev": "1"})
    mark = e2e.mark()
    e2e.upgrade(CHART, "--wait=ordered", "--timeout", "3m", values={"global.rev": "2"})
    tl = e2e.timeline(since=mark)

    a_patch = tl.applied("Deployment", "subchart-a")
    a_ready = tl.ready("Deployment", "subchart-a", after=a_patch)
    b_patch = tl.applied("Deployment", "subchart-b")
    b_ready = tl.ready("Deployment", "subchart-b", after=b_patch)
    p_patch = tl.applied("Deployment", "parent")
    p_ready = tl.ready("Deployment", "parent", after=p_patch)
    finished = tl.finished()
    e2e.observe_timeline("upgrade timeline", [
        (a_patch, "patch  Deployment/subchart-a"), (a_ready, "ready  Deployment/subchart-a (new pod)"),
        (b_patch, "patch  Deployment/subchart-b"), (b_ready, "ready  Deployment/subchart-b (new pod)"),
        (p_patch, "patch  Deployment/parent"), (p_ready, "ready  Deployment/parent (new pod)"),
        (finished, "helm writes release record: deployed"),
    ])

    # R08: the upgrade applies in install order, gated on readiness.
    order.before("subchart-a ready", a_ready, "subchart-b patched", b_patch)
    order.before("subchart-b ready", b_ready, "parent patched", p_patch)
    # R35 (deviation): the leaf (parent, nothing depends on it) is still waited on.
    order.before("parent ready", p_ready, "helm finished", finished)


@pytest.mark.req("R09")
@pytest.mark.needs("ordered", "subcharts")
def test_uninstall_reverse_order_for_ordered_install(e2e, order):
    """Uninstall of a sequenced release deletes in exact reverse: parent -> b -> a, each after the previous is gone."""
    e2e.install(CHART, "--wait=ordered", "--timeout", "3m")
    mark = e2e.mark()
    e2e.uninstall()
    tl = e2e.timeline(since=mark)

    p_del, b_del, a_del = (tl.deleted("Deployment", n) for n in ("parent", "subchart-b", "subchart-a"))
    e2e.observe_timeline("uninstall timeline", [(p_del, "delete Deployment/parent"),
                                                (b_del, "delete Deployment/subchart-b"),
                                                (a_del, "delete Deployment/subchart-a")])
    order.before("parent deleted", p_del, "subchart-b deleted", b_del)
    order.before("subchart-b deleted", b_del, "subchart-a deleted", a_del)


@pytest.mark.req("R09", "R02")
@pytest.mark.needs("ordered", "subcharts")
def test_uninstall_after_plain_install_is_not_sequenced(e2e):
    """A release installed all at once (plain --wait, no stored plan) is uninstalled all at once."""
    e2e.install(CHART, "--wait", "--timeout", "3m")
    assert e2e.release_record().get("plan") is None, "plain install must not store a plan"
    mark = e2e.mark()
    e2e.uninstall()
    tl = e2e.timeline(since=mark)

    deletes = [(tl.deleted("Deployment", name), f"delete Deployment/{name}")
               for name in ("parent", "subchart-b", "subchart-a")]
    e2e.observe_timeline("uninstall timeline", deletes)
    stamps = [ts for ts, _ in deletes]
    assert all(stamps), f"missing delete records: {deletes}"
    spread = (max(stamps) - min(stamps)).total_seconds()
    e2e.observe("delete spread", f"{spread:.3f}s")
    # Sequenced teardown waits for each deletion to finish (seconds per pod); one burst proves it did not.
    assert spread < 1.0, f"deletes spread over {spread:.1f}s: uninstall was sequenced although the install was not"


@pytest.mark.req("R10")
@pytest.mark.needs("ordered", "subcharts")
def test_rollback_follows_target_revision_order(e2e, order):
    """Rollback to a sequenced revision re-applies it in its order, then removes the extras in reverse (d before c)."""
    e2e.install(CHART, "--wait=ordered", "--timeout", "3m", values={"global.rev": "1", "c.enabled": "false"})
    e2e.upgrade(CHART, "--wait=ordered", "--timeout", "3m", values={"global.rev": "2", "c.enabled": "true"})
    mark = e2e.mark()
    # Plain --wait on purpose: the HIP says rollback takes the order from the target revision's record.
    e2e.rollback(1, "--wait", "--timeout", "3m")
    tl = e2e.timeline(since=mark)

    a_patch = tl.applied("Deployment", "subchart-a")
    a_ready = tl.ready("Deployment", "subchart-a", after=a_patch)
    b_patch = tl.applied("Deployment", "subchart-b")
    b_ready = tl.ready("Deployment", "subchart-b", after=b_patch)
    p_patch = tl.applied("Deployment", "parent")
    d_del, c_del = tl.deleted("Deployment", "subchart-d"), tl.deleted("Deployment", "subchart-c")
    e2e.observe_timeline("rollback timeline", [
        (a_patch, "patch  Deployment/subchart-a"), (a_ready, "ready  Deployment/subchart-a"),
        (b_patch, "patch  Deployment/subchart-b"), (b_ready, "ready  Deployment/subchart-b"),
        (p_patch, "patch  Deployment/parent"),
        (d_del, "delete Deployment/subchart-d (rev2 only)"), (c_del, "delete Deployment/subchart-c (rev2 only)"),
    ])

    order.before("subchart-a ready", a_ready, "subchart-b patched", b_patch)
    order.before("subchart-b ready", b_ready, "parent patched", p_patch)
    order.before("parent patched (target applied)", p_patch, "first removal", d_del)
    order.before("subchart-d deleted", d_del, "subchart-c deleted", c_del)

    rev1, rev3 = e2e.release_record(revision=1), e2e.release_record(revision=3)
    rev1_batches = [b["chartPath"] for b in rev1["plan"]["batches"]]
    rev3_batches = [b["chartPath"] for b in (rev3.get("plan") or {}).get("batches", [])]
    e2e.observe("plan batches rev1 / rev3", {"rev1": rev1_batches, "rev3 (rollback)": rev3_batches})
    assert rev3["info"]["status"] == "deployed", f"rev3 status {rev3['info']['status']}"
    assert rev3_batches == rev1_batches, "the rollback revision must carry the target revision's plan"


@pytest.mark.req("R11")
@pytest.mark.needs("ordered", "subcharts")
def test_failure_stops_install_dependent_never_applied(e2e):
    """A dependency that never becomes ready fails the install; its dependent is never applied; the release is failed."""
    run = e2e.install(CHART_FAILURE, "--wait=ordered", "--timeout", "45s", check=False)
    tl = e2e.timeline()
    status = e2e.helm("status", "r", "--namespace", e2e.ns)
    record = e2e.release_record()
    e2e.observe("install", f"exit {run.code} after {run.seconds:.0f}s: {run.err.strip().splitlines()[-1] if run.err.strip() else ''}")
    e2e.observe_timeline("apiserver timeline", [(tl.applied("Deployment", "broken"), "apply  Deployment/broken"),
                                                (tl.applied("Deployment", "dependent"), "apply  Deployment/dependent")])
    e2e.observe("release status", record["info"]["status"])

    assert run.code != 0, "install must fail"
    assert tl.applied("Deployment", "broken") is not None, "broken must be applied"
    assert tl.applied("Deployment", "dependent") is None, "dependent must never be applied"
    assert record["info"]["status"] == "failed", f"release status is {record['info']['status']}"
    assert "STATUS: failed" in status.out


@pytest.mark.req("R11")
@pytest.mark.needs("ordered", "subcharts")
def test_rollback_on_failure_cleans_up(e2e):
    """--rollback-on-failure: the install fails, then Helm deletes what it applied and leaves no release."""
    run = e2e.install(CHART_FAILURE, "--wait=ordered", "--timeout", "45s", "--rollback-on-failure", check=False)
    tl = e2e.timeline()
    statuses = ("--deployed", "--failed", "--pending", "--superseded", "--uninstalled")
    releases = e2e.helm("list", *statuses, "--short", "--namespace", e2e.ns).out.split()
    e2e.observe("install", f"exit {run.code}: {run.err.strip().splitlines()[-1] if run.err.strip() else ''}")
    e2e.observe_timeline("apiserver timeline", [(tl.applied("Deployment", "broken"), "apply  Deployment/broken"),
                                                (tl.deleted("Deployment", "broken"), "delete Deployment/broken")])
    e2e.observe("releases left in namespace", releases)

    assert run.code != 0, "install must fail"
    assert "rollback-on-failure" in run.err, "the error must say the release was rolled back"
    assert tl.deleted("Deployment", "broken") is not None, "Helm must delete what it applied"
    assert not e2e.exists("Deployment", "broken") and not e2e.exists("Deployment", "dependent")
    assert releases == [] and e2e.release_record() is None, "no release record may remain"


@pytest.mark.req("R12")
@pytest.mark.needs("ordered", "subcharts")
def test_readiness_timeout_per_batch_cap(e2e):
    """--readiness-timeout 10s under --timeout 2m fails the never-ready batch after ~10s, not 1m or 2m."""
    run = e2e.install(CHART_FAILURE, "--wait=ordered", "--readiness-timeout", "10s", "--timeout", "2m", check=False)
    e2e.observe("install", f"exit {run.code} after {run.seconds:.1f}s")
    e2e.observe("error", run.err.strip().splitlines()[-1] if run.err.strip() else "")
    assert run.code != 0, "install must fail"
    assert 9 <= run.seconds <= 30, f"failed after {run.seconds:.1f}s; the 10s per-batch cap was not applied"
    assert "broken" in run.err, "the error must name the resource that was not ready"


@pytest.mark.req("R12")
@pytest.mark.needs("ordered", "subcharts")
def test_readiness_timeout_exceeds_timeout_rejected(e2e):
    """--readiness-timeout 3m --timeout 2m: rejected immediately, nothing applied."""
    run = e2e.install(CHART_FAILURE, "--wait=ordered", "--readiness-timeout", "3m", "--timeout", "2m", check=False)

    assert run.code != 0, "should fail validation"
    e2e.observe("error message", run.err)
    assert "must not exceed" in run.err or "cannot exceed" in run.err.lower(), "error should mention timeout constraint"

    # Nothing should be applied
    tl = e2e.timeline()
    applies = tl.helm_applies()
    e2e.observe("applies count", len(applies))
    assert len(applies) == 0, "nothing should be applied when validation fails"


@pytest.mark.req("R12")
@pytest.mark.needs("ordered", "subcharts")
def test_default_readiness_timeout_one_minute(e2e):
    """No --readiness-timeout, --timeout 3m: fails after ~60s (default 1m readiness timeout)."""
    run = e2e.install(CHART_FAILURE, "--wait=ordered", "--timeout", "3m", check=False)

    assert run.code != 0, "install should fail"
    elapsed = run.seconds
    e2e.observe("elapsed seconds", elapsed)

    # Default is 1 minute; allow some margin
    assert 55 <= elapsed <= 100, f"should fail around 60s with default readiness timeout, got {elapsed}s"


@pytest.mark.req("R13")
@pytest.mark.needs("ordered", "subcharts")
def test_hooks_not_sequenced_run_by_weight(e2e, order):
    """Hooks run before chart resources in hook-weight order, outside the plan, despite sequencing annotations."""
    e2e.install(CHART_HOOKS, "--wait=ordered", "--timeout", "3m")
    tl = e2e.timeline()
    low, high = tl.applied("Job", "hook-weight-minus-5"), tl.applied("Job", "hook-weight-5")
    first, second = tl.applied("Deployment", "first"), tl.applied("Deployment", "second")
    e2e.observe_timeline("apiserver timeline", [
        (low, "create Job/hook-weight-minus-5 (pre-install, weight -5)"),
        (high, "create Job/hook-weight-5 (pre-install, weight 5)"),
        (first, "apply  Deployment/first"), (second, "apply  Deployment/second"),
    ])
    order.before("hook weight -5", low, "hook weight 5", high)
    order.before("hook weight 5", high, "first chart resource", min(first, second))

    rec = e2e.release_record()
    plan_paths = {m["path"] for b in rec["plan"]["batches"] for m in b["manifests"]}
    hook_paths = {h["path"] for h in rec["hooks"]}
    e2e.observe("hook templates", sorted(hook_paths))
    e2e.observe("plan manifests", sorted(plan_paths))
    e2e.observe("hook last_run phases", {h["name"]: h["last_run"]["phase"] for h in rec["hooks"]})
    assert len(rec["hooks"]) == 2, "both hooks must be recorded"
    assert not hook_paths & plan_paths, f"hooks leaked into the plan: {hook_paths & plan_paths}"
    assert all(h["last_run"]["phase"] == "Succeeded" for h in rec["hooks"])
