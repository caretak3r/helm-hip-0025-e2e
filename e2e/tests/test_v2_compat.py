"""R14 · Charts v2 backwards compatibility."""

import pytest

from timeline import fmt_ts


@pytest.mark.req("R14")
def test_v2_chart_with_plain_wait_applies_in_one_burst(e2e):
    """V2 chart with group annotations: plain --wait applies all at once (max-min < 1s), no sequencing, no plan in release."""
    run = e2e.install("v2-annotated", "--wait", "--timeout", "3m")
    e2e.observe("install exit code", run.code)
    assert run.code == 0, f"plain --wait install must succeed: {run.err}"

    tl = e2e.timeline()
    applies = tl.helm_applies()

    # Filter to just our resources (exclude subchart and release secrets)
    resource_applies = [a for a in applies if a.kind in ["Deployment", "ConfigMap"] and not a.name.startswith("sh.helm.release")]
    e2e.observe("resource applies", [(fmt_ts(a.ts), f"{a.kind}/{a.name}") for a in resource_applies])

    if len(resource_applies) >= 2:
        timestamps = [a.ts for a in resource_applies]
        min_ts = min(timestamps)
        max_ts = max(timestamps)
        burst_duration = (max_ts - min_ts).total_seconds()
        e2e.observe("burst duration (seconds)", burst_duration)

        # All applied in one burst (max-min < 1s)
        assert burst_duration < 1.0, f"resources must be applied in one burst, got {burst_duration}s spread"


    # Release record must not have a plan (no sequencing)
    rec = e2e.release_record()
    e2e.observe("release record has plan", "plan" in rec)
    assert "plan" not in rec, "v2 chart with plain --wait must not create a sequencing plan"


@pytest.mark.req("R14")
def test_v2_chart_with_ordered_wait_fails(e2e):
    """V2 chart: --wait=ordered exits non-zero and creates no release."""
    run = e2e.install("v2-annotated", "--wait=ordered", "--timeout", "3m", check=False)
    e2e.observe("install exit code", run.code)
    e2e.observe("stderr", run.err)

    assert run.code != 0, "--wait=ordered on v2 chart must fail"

    # On pr3, --wait=ordered itself is invalid; on pr1/pr2, it's rejected for v2 charts.
    # Accept either error message.
    is_flag_error = "unknown flag" in run.err.lower() or "invalid" in run.err.lower()
    is_v2_error = "v2" in run.err.lower() or "chart version" in run.err.lower() or "apiversion" in run.err.lower()

    e2e.observe("error type", "flag-invalid" if is_flag_error else "v2-rejected" if is_v2_error else "other")
    assert is_flag_error or is_v2_error, f"expected flag or v2 error, got: {run.err}"

    # No release should be created
    list_run = e2e.helm("list", "-o", "json")
    import json
    releases = json.loads(list_run.out) if list_run.out.strip() else []
    e2e.observe("releases in namespace", [r.get("name") for r in releases])
    assert len(releases) == 0, "no release should be created when install fails"


@pytest.mark.req("R14")
def test_v2_chart_upgrade_rollback_uninstall_succeed(e2e):
    """V2 chart: upgrade, rollback, and uninstall all succeed with plain --wait."""
    # Initial install
    e2e.install("v2-annotated", "--wait", "--timeout", "3m")

    # Upgrade
    e2e.upgrade("v2-annotated", "--wait", "--timeout", "3m")
    rec_after_upgrade = e2e.release_record(revision=2)
    e2e.observe("upgrade revision", rec_after_upgrade["version"])
    assert rec_after_upgrade["version"] == 2, "upgrade must create revision 2"

    # Rollback
    e2e.rollback(1, "--wait", "--timeout", "3m")
    rec_after_rollback = e2e.release_record()
    e2e.observe("rollback revision", rec_after_rollback["version"])
    assert rec_after_rollback["version"] == 3, "rollback must create revision 3"

    # Uninstall
    e2e.uninstall("--wait", "--timeout", "3m")

    # Verify nothing remains
    tl = e2e.timeline()
    deletes = tl.helm_deletes()
    deployment_deletes = [d for d in deletes if d.kind == "Deployment"]
    e2e.observe("deployments deleted", [d.name for d in deployment_deletes])
    assert len(deployment_deletes) >= 1, "at least parent-app should be deleted"
