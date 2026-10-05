"""Combined tier · custom readiness gates sequencing (HIP-0025 R36)."""

import pytest

CHART = "hip-readiness-gate"


@pytest.mark.req("R36")
@pytest.mark.needs("ordered", "groups", "readiness")
def test_custom_readiness_gates_sequencing(e2e, order):
    """A Probe gated only by custom readiness holds back the group that depends on it."""
    # The Probe has no status, so kstatus alone would call it ready at once; only the
    # custom expression ({.phase} == Ready), satisfied by this patch at t+5s, can gate.
    e2e.later(5.0, e2e.patch_status, "Probe", "gate", {"phase": "Ready"})
    e2e.install(CHART, "--wait=ordered", "--timeout", "3m")
    tl = e2e.timeline()

    gate_apply = tl.applied("Probe", "gate")
    ready = next((ts for ts, phase in tl.phase_changes("Probe", "gate") if phase == "Ready"), None)
    app_apply = tl.applied("Deployment", "app")
    e2e.observe_timeline("apiserver timeline", [
        (gate_apply, "apply  Probe/gate (group first)"),
        (ready, "status Probe/gate phase=Ready (test patch)"),
        (app_apply, "apply  Deployment/app (group second, depends on first)"),
    ])

    order.before("Probe applied", gate_apply, "Probe ready", ready)
    order.before("Probe ready", ready, "Deployment applied", app_apply)
