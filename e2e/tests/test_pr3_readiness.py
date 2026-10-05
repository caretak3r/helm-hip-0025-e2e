"""PR3 · custom readiness annotations (HIP-0025 "Readiness")."""

import pytest
import yaml

from timeline import fmt_ts

CHART = "hip-readiness-basic"


@pytest.mark.req("R30")
@pytest.mark.needs("readiness")
def test_deployment_without_annotations_uses_kstatus(e2e):
    """Deployment with no readiness annotations: plain --wait returns after Available."""
    e2e.install(CHART, "--wait", "--timeout", "2m", values={"deployment.enabled": "true"})
    tl = e2e.timeline()

    app_ready = tl.ready("Deployment", "app")

    e2e.observe("Deployment ready time", fmt_ts(app_ready))
    e2e.observe("install succeeded with kstatus", True)
    assert app_ready is not None, "Deployment never became ready"


@pytest.mark.req("R31")
@pytest.mark.needs("readiness")
def test_success_expressions_mark_ready(e2e, order):
    """Success list with multiple expressions: install exits only after one becomes true."""
    values_content = {
        "probe": {
            "successExpressions": ['{.phase} == Ready', '{.count} >= 3'],
            "failureExpressions": ['{.phase} == Failed']
        }
    }
    values_file = e2e.dir / "values.yaml"
    values_file.write_text(yaml.dump(values_content))

    # Patch count=3 at t+4s while phase stays Pending (or absent)
    e2e.later(4.0, e2e.patch_status, "Probe", "probe", {"count": 3})

    e2e.helm("install", "r", e2e.chart(CHART), "-f", str(values_file),
             "--namespace", e2e.ns, "--wait", "--timeout", "2m")
    tl = e2e.timeline()

    changes = tl.phase_changes("Probe", "probe", field="count")
    e2e.observe("Probe count changes", [(fmt_ts(ts), val) for ts, val in changes])

    assert len(changes) > 0, "count never changed"
    patch_time = changes[0][0]  # first time count changed

    # Helm's final release-record write (server clock) comes after the patch.
    finished = tl.finished()
    e2e.observe_timeline("apiserver timeline", [(patch_time, "status Probe/probe count=3 (test patch)"),
                                                (finished, "helm writes release record: deployed")])
    assert finished is not None and finished > patch_time, \
        f"install finished at {fmt_ts(finished)}, before the count patch at {fmt_ts(patch_time)}"


@pytest.mark.req("R32")
@pytest.mark.needs("readiness")
def test_failure_takes_precedence_over_success(e2e):
    """Success AND failure both true: install fails, error names the Probe."""
    values_content = {
        "probe": {
            "successExpressions": ['{.phase} == Ready'],
            "failureExpressions": ['{.phase} == Ready']
        }
    }
    values_file = e2e.dir / "values.yaml"
    values_file.write_text(yaml.dump(values_content))

    # Patch to make both true
    e2e.later(2.0, e2e.patch_status, "Probe", "probe", {"phase": "Ready"})

    run = e2e.helm("install", "r", e2e.chart(CHART), "-f", str(values_file),
                   "--namespace", e2e.ns, "--wait", "--timeout", "1m",
                   check=False)

    e2e.observe("install exit code", run.code)
    e2e.observe("error message", run.err[:600])

    assert run.code != 0, "install should have failed"
    assert "probe" in run.err.lower(), "error should name the Probe"
    assert "readiness" in run.err.lower() or "failed" in run.err.lower(), \
        "error should mention readiness or failure"


@pytest.mark.req("R32")
@pytest.mark.needs("readiness")
def test_failure_expression_alone_fails_install(e2e):
    """Only failure expression true: install fails."""
    values_content = {
        "probe": {
            "successExpressions": ['{.phase} == Ready'],
            "failureExpressions": ['{.phase} == Failed']
        }
    }
    values_file = e2e.dir / "values.yaml"
    values_file.write_text(yaml.dump(values_content))

    # Patch to failed
    e2e.later(2.0, e2e.patch_status, "Probe", "probe", {"phase": "Failed"})

    run = e2e.helm("install", "r", e2e.chart(CHART), "-f", str(values_file),
                   "--namespace", e2e.ns, "--wait", "--timeout", "1m",
                   check=False)

    e2e.observe("install exit code", run.code)
    e2e.observe("error message snippet", run.err[:500])

    assert run.code != 0, "install should have failed"
    assert "probe" in run.err.lower()


@pytest.mark.req("R32")
@pytest.mark.needs("readiness")
def test_failed_probe_plus_pending_waits_for_timeout(e2e):
    """One failed Probe + one pending: helm waits until --timeout, error names both."""
    import time

    # Use the multi-probe support
    values_content = {
        "probes": [
            {
                "name": "probe1",
                "successExpressions": ['{.phase} == Ready'],
                "failureExpressions": ['{.phase} == Failed']
            },
            {
                "name": "probe2",
                "successExpressions": ['{.phase} == Ready'],
                "failureExpressions": ['{.phase} == Failed']
            }
        ]
    }
    values_file = e2e.dir / "values.yaml"
    values_file.write_text(yaml.dump(values_content))

    # Make probe1 fail at t+2s; probe2 stays pending (no status update)
    e2e.later(2.0, e2e.patch_status, "Probe", "probe1", {"phase": "Failed"})

    start = time.time()

    run = e2e.helm("install", "r", e2e.chart(CHART), "-f", str(values_file),
                   "--namespace", e2e.ns, "--wait", "--timeout", "30s",
                   check=False)

    elapsed = time.time() - start

    e2e.observe("install exit code", run.code)
    e2e.observe("elapsed seconds", round(elapsed, 1))
    e2e.observe("error message", run.err[:800])

    assert run.code != 0, "install should have failed"

    # Should wait close to the timeout (30s), not fail fast
    assert elapsed >= 28, f"should wait ~30s for timeout, but finished in {elapsed:.1f}s"

    # Error should name both probes
    err_lower = run.err.lower()
    assert "probe1" in err_lower, "error should mention probe1"
    assert "probe2" in err_lower, "error should mention probe2"


@pytest.mark.req("R33")
@pytest.mark.needs("readiness")
def test_only_success_annotation_falls_back_to_kstatus_and_warns(e2e):
    """Only readiness-success annotation: kstatus fallback occurs and helm warns."""
    values_content = {
        "probe": {
            "successExpressions": ['{.phase} == Ready']
        },
        "deployment": {
            "enabled": True
        }
    }
    values_file = e2e.dir / "values.yaml"
    values_file.write_text(yaml.dump(values_content))

    # Also add a Deployment to make the fallback observable
    run = e2e.helm("install", "r", e2e.chart(CHART), "-f", str(values_file),
                   "--namespace", e2e.ns, "--wait", "--timeout", "1m",
                   check=False)

    tl = e2e.timeline()
    phases = tl.phase_changes("Probe", "probe")
    warnings = [line for line in run.err.splitlines() if "level=WARN" in line]
    e2e.observe("install", f"exit {run.code} after {run.seconds:.1f}s")
    e2e.observe("Probe .status.phase changes during install", [str(p) for p in phases] or ["none: never Ready"])
    e2e.observe("helm warnings", warnings)

    # Fallback: the lone success expression ({.phase} == Ready) is never true, yet the
    # install succeeds on kstatus alone instead of blocking until --timeout.
    assert run.code == 0, f"install must succeed on kstatus fallback: {run.err}"
    assert not any(value == "Ready" for _, value in phases), "the Probe was made Ready, so fallback is not proven"
    assert run.seconds < 50, f"install took {run.seconds:.0f}s: it waited on the custom expression"
    assert any("falling back to default readiness" in w and "name=probe" in w for w in warnings), \
        f"expected a fallback warning naming the Probe, got {warnings}"


@pytest.mark.req("R33")
@pytest.mark.needs("readiness")
def test_only_success_annotation_fails_helm_lint(e2e):
    """Chart with only readiness-success annotation: helm lint fails."""
    # Create a values file with only success annotation
    values_content = {
        "probe": {
            "successExpressions": ['{.phase} == Ready']
        }
    }
    values_file = e2e.dir / "lint-values.yaml"
    values_file.write_text(yaml.dump(values_content))

    # Use helm lint on the chart
    lint_run = e2e.helm("lint", e2e.chart(CHART), "-f", str(values_file), check=False)

    e2e.observe("lint exit code", lint_run.code)
    e2e.observe("lint output", lint_run.out + lint_run.err)

    assert lint_run.code != 0, "helm lint should fail when only one readiness annotation is present"
    output = (lint_run.out + lint_run.err).lower()
    assert "readiness" in output or "annotation" in output, \
        "lint error should mention readiness or annotations"

@pytest.mark.req("R34")
@pytest.mark.needs("readiness")
@pytest.mark.parametrize("operator,initial,target,threshold,field,description", [
    ("==", 5, 10, 10, "count", "equality number"),
    ("!=", 5, 10, 5, "count", "inequality number"),  # expr: != 5, start at 5, patch to 10
    ("<", 10, 4, 5, "count", "less than"),  # expr: < 5, start at 10, patch to 4
    ("<=", 10, 5, 5, "count", "less or equal"),
    (">", 5, 11, 10, "count", "greater than"),  # expr: > 10, start at 5, patch to 11
    (">=", 5, 10, 10, "count", "greater or equal"),
    ("==", "Pending", "Ready", "Ready", "phase", "equality string"),
    ("==", "false", "true", "true", "ready", "equality boolean"),
])
def test_readiness_operators(e2e, operator, initial, target, threshold, field, description):
    """Each operator (==, !=, <, <=, >, >= on numbers; == on strings and booleans) holds the wait until the patch makes it true."""

    # Build the success expression using threshold (the comparison value)
    success_expr = f'{{.{field}}} {operator} {threshold}'
    failure_expr = '{.phase} == Failed'  # dummy failure to satisfy pair requirement

    # Patch to target value at t+3s
    patch_val = target
    # For boolean field, convert string to actual bool for status
    if field == "ready":
        if isinstance(initial, str):
            initial = initial.lower() == "true"
        if isinstance(target, str):
            patch_val = target.lower() == "true"

    e2e.later(3.0, e2e.patch_status, "Probe", "probe", {field: patch_val})

    values_content = {
        "probe": {
            "successExpressions": [success_expr],
            "failureExpressions": [failure_expr]
        }
    }
    values_file = e2e.dir / "values.yaml"
    values_file.write_text(yaml.dump(values_content))

    run = e2e.helm("install", "r", e2e.chart(CHART), "-f", str(values_file),
                   "--namespace", e2e.ns, "--wait", "--timeout", "2m")

    tl = e2e.timeline()
    changes = tl.phase_changes("Probe", "probe", field=field)

    e2e.observe(f"{description} operator", operator)
    e2e.observe(f"{field} changes", [(fmt_ts(ts), val) for ts, val in changes])
    e2e.observe("install completed", run.code == 0)

    # Find when the field changed to target
    target_time = None
    for ts, val in changes:
        if val == patch_val:
            target_time = ts
            break

    assert target_time is not None, f"{field} never changed to {target}"
    finished = tl.finished()
    e2e.observe_timeline("apiserver timeline", [(target_time, f"status Probe/probe {field}={patch_val} (test patch)"),
                                                (finished, "helm writes release record: deployed")])
    assert finished is not None and finished > target_time, \
        f"install finished at {fmt_ts(finished)}, before {field} reached {target} at {fmt_ts(target_time)}"


@pytest.mark.req("R37")
@pytest.mark.needs("readiness")
def test_custom_readiness_applies_to_plain_wait(e2e):
    """Probe with custom readiness annotations gates a plain --wait install."""
    values_content = {
        "probe": {
            "successExpressions": ['{.phase} == Ready'],
            "failureExpressions": ['{.phase} == Failed']
        }
    }
    values_file = e2e.dir / "values.yaml"
    values_file.write_text(yaml.dump(values_content))

    # Patch to Ready at t+4s
    e2e.later(4.0, e2e.patch_status, "Probe", "probe", {"phase": "Ready"})

    e2e.helm("install", "r", e2e.chart(CHART), "-f", str(values_file),
             "--namespace", e2e.ns, "--wait", "--timeout", "2m")

    tl = e2e.timeline()
    changes = tl.phase_changes("Probe", "probe", field="phase")

    e2e.observe("phase changes", [(fmt_ts(ts), val) for ts, val in changes])

    # Verify that Ready was reached
    ready_time = None
    for ts, val in changes:
        if val == "Ready":
            ready_time = ts
            break

    assert ready_time is not None, "Probe never reached Ready phase"
    finished = tl.finished()
    e2e.observe_timeline("apiserver timeline", [(ready_time, "status Probe/probe phase=Ready (test patch)"),
                                                (finished, "helm writes release record: deployed")])
    assert finished is not None and finished > ready_time, "plain --wait returned before the custom expression held"
