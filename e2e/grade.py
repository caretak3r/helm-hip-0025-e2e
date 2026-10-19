"""Grade a run against the HIP-0025 requirement catalog.

REPORT.md (report.py) and the dashboard (testgrid/) both take their verdicts from
this module, so the two views cannot disagree. A run directory carries copies of
tiers.yaml and requirements.yaml from the moment it ran; grading uses those copies,
so a later change to the catalog does not change an old run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

# Cell verdicts, worst first.
FAIL, BUILD, XPASS, UNTESTED, PASS, XFAIL, NA = "FAIL", "BUILD FAILED", "XPASS", "UNTESTED", "PASS", "XFAIL", "N/A"
GLYPH = {PASS: "✓", FAIL: "✗", XFAIL: "○", XPASS: "!", NA: "—", UNTESTED: "?", BUILD: "✗"}
# What a cell verdict means for a requirement, in report order.
MEANINGS = ["MET", "MET (extension)", "DEVIATION (documented)", "NOT IMPLEMENTED", "FAILING", "UNTESTED",
            "NOW PASSING — update requirements.yaml", "BUILD FAILED", "n/a"]
OUTCOME_TEXT = {"passed": "✓ pass", "failed": "✗ FAIL", "error": "✗ ERROR", "xfailed": "○ xfail",
                "xpassed": "! XPASS", "n/a": "— n/a", "skipped": "skip"}


def _yaml(run: Path, name: str) -> dict:
    snapshot = run / name
    return yaml.safe_load((snapshot if snapshot.exists() else ROOT / name).read_text())


def load(run: Path) -> dict:
    cfg = _yaml(run, "tiers.yaml")
    tiers = list(cfg["tiers"])
    data = {"run": run, "cfg": cfg, "reqs": _yaml(run, "requirements.yaml")["requirements"], "tiers": tiers,
            "results": {}, "builds": {}, "units": {}, "load_errors": []}
    for tier in tiers:
        for key, name in (("results", "results.json"), ("builds", "build.json"), ("units", "unit.json")):
            f = run / tier / name
            if f.exists():
                try:
                    data[key][tier] = json.loads(f.read_text())
                except (ValueError, OSError) as exc:
                    data["load_errors"].append(f"{tier}/{name}: {exc}")
    meta = run / "run.json"
    try:
        data["meta"] = json.loads(meta.read_text()) if meta.exists() else {}
    except (ValueError, OSError) as exc:
        data["meta"] = {}
        data["load_errors"].append(f"run.json: {exc}")
    return data


def label(data: dict, tier: str) -> str:
    return data["cfg"]["tiers"].get(tier, {}).get("label", tier)


def is_merge(data: dict, tier: str) -> bool:
    return "merge" in data["cfg"]["tiers"].get(tier, {})


def tests_for(data: dict, tier: str, rid: str) -> list[dict]:
    return [t for t in data["results"].get(tier, {}).get("tests", []) if rid in t.get("reqs", [])]


def cell(data: dict, tier: str, rid: str) -> str:
    if tier not in data["results"]:
        return BUILD
    tests = tests_for(data, tier, rid)
    if not tests:
        return UNTESTED
    outcomes = {test_outcome(data, tier, t) for t in tests}
    if outcomes & {"failed", "error"}:
        return FAIL
    if "xpassed" in outcomes:
        return XPASS
    if outcomes & {"skipped", "unknown"}:
        return UNTESTED
    if "passed" in outcomes:
        return PASS
    if "xfailed" in outcomes:
        return XFAIL
    return NA


def owned(data: dict, req: dict, tier: str) -> bool:
    """A PR tier is graded on the requirements it owns; a merge tier on all of them."""
    return is_merge(data, tier) or req["owner"] in ("all", tier)


def meaning(req: dict, verdict: str) -> str:
    if verdict == PASS:
        return {"deviation": "DEVIATION (documented)", "extension": "MET (extension)"}.get(req["status"], "MET")
    if verdict == XFAIL:
        return "NOT IMPLEMENTED"
    if verdict == XPASS:
        return "NOW PASSING — update requirements.yaml"
    return {FAIL: "FAILING", UNTESTED: "UNTESTED", BUILD: "BUILD FAILED", NA: "n/a"}[verdict]


def pr_summary(data: dict, tier: str) -> dict:
    counts: dict[str, int] = {}
    for req in data["reqs"]:
        if owned(data, req, tier):
            m = meaning(req, cell(data, tier, req["id"]))
            counts[m] = counts.get(m, 0) + 1
    unit = data["units"].get(tier)
    if unit is None:
        unit_text = "n/a (merge tier)" if is_merge(data, tier) else "not run"
    elif "error" in unit:
        unit_text = "ERROR"
    else:
        packages = unit.get("packages", [])
        tested = [p for p in packages if not p.get("compile_only")]
        ok = sum(p.get("passed") is True for p in tested)
        unit_text = f"{ok}/{len(tested)} packages pass"
        if len(tested) != len(packages):
            unit_text += f"; {len(packages) - len(tested)} compile only (no tests)"
    return {"counts": counts, "unit": unit_text}


def test_outcome(data: dict, tier: str, test: dict) -> str:
    """N/A is a feature mismatch; only the catalog's strict expected failures count."""
    outcome = test.get("outcome", "unknown")
    if "failed" in test.get("phases", {}).values():
        return "error"
    manifest = {t["nodeid"]: t for t in data["meta"].get("suite", [])}
    spec = manifest.get(test.get("nodeid"), test)
    missing = set(spec.get("needs", [])) - set(data["cfg"]["tiers"][tier]["features"])
    if outcome == "n/a" and not missing:
        return "error"
    if missing and outcome != "n/a":
        return "error"
    if outcome == "xfailed":
        reqs = {r["id"]: r for r in data["reqs"]}
        ids = spec.get("reqs", [])
        allowed = bool(ids) and all(reqs.get(r, {}).get("status") == "not-implemented" for r in ids)
        if not allowed or (data["meta"].get("evidence_version") == 2
                           and not (spec.get("xfail_strict") and test.get("xfail_strict"))):
            return "error"
    if outcome == "passed" and spec.get("xfail_strict"):
        return "xpassed"
    return outcome


def assess(data: dict, *, final: bool = True) -> dict:
    """One run verdict for the CLI, Markdown report and dashboard.

    Legacy records retain their outcomes, but cannot prove a full collection or
    successful teardown. Missing new metadata is not a historical test failure.
    """
    meta = data["meta"]
    modern = meta.get("evidence_version") == 2
    failed = list(data["load_errors"])
    incomplete, partial = [], []
    tiers = data["tiers"]
    selected = meta.get("tiers", tiers)
    if not meta:
        partial.append("Manual evidence: no runner metadata or full-run contract.")
    if set(selected) != set(tiers):
        partial.append("Selected tiers differ from the full tier catalog.")
    if meta.get("skip_unit"):
        partial.append("Go unit tests were explicitly skipped.")
    if not modern and meta.get("pytest_args"):
        partial.append("Legacy pytest arguments: full-suite selection cannot be established.")
    if meta.get("exit_code", 0) != 0 and not modern:
        failed.append(f"Runner exit code: {meta['exit_code']}.")
    if meta.get("status") == "failed":
        failed.append("Runner failed.")
    stages = meta.get("stages", {})
    for name, stage in stages.items():
        if stage.get("status") == "failed" or stage.get("error") or stage.get("exit_code", 0) != 0:
            failed.append(f"{name}: {stage.get('error') or 'stage failed'} (exit {stage.get('exit_code', '?')}).")
    suite = meta.get("suite", [])
    expected = {t["nodeid"] for t in suite}
    coverage = []
    if modern:
        if not expected:
            incomplete.append("Missing unfiltered suite collection.")
        if final and meta.get("status") not in ("completed", "failed"):
            incomplete.append("Runner has not completed.")
        required = ["collection", "sources", "cluster", "metadata", "charts"]
        if final:
            required += ["grading", "report"]
            if meta.get("exit_code") is None:
                incomplete.append("Runner exit code is missing.")
            if not (data["run"] / "REPORT.md").is_file():
                incomplete.append("Final report has not been published.")
        required += [f"{s}:{t}" for t in selected if t in tiers for s in ("build", "e2e")]
        required += [f"unit:{t}" for t in selected if t in tiers and not is_merge(data, t)
                     and not meta.get("skip_unit")]
        for name in required:
            if stages.get(name, {}).get("status") not in ("passed", "failed"):
                incomplete.append(f"{name}: stage did not complete.")
    # For old runs, peer evidence can disprove completeness, never prove it.
    peer_ids = {t["nodeid"] for r in data["results"].values() for t in r.get("tests", [])}
    for tier in tiers:
        if tier not in selected:
            continue
        build = data["builds"].get(tier)
        if not build:
            incomplete.append(f"{tier}: missing build record.")
        elif build.get("error"):
            failed.append(f"{tier}: build: {build['error']}")
        result = data["results"].get(tier, {})
        tests = result.get("tests", [])
        ids = {t["nodeid"] for t in tests}
        cov = result.get("coverage", {})
        chosen = set(cov.get("selected", []))
        executed = set(cov.get("executed", []))
        coverage.append({"tier": tier, "expected": len(expected) if modern else None,
                         "selected": len(chosen) if cov else None, "executed": len(ids)})
        if result.get("exit_code", 0) != 0 or result.get("errors"):
            failed.append(f"{tier}: pytest exit {result.get('exit_code', '?')}; errors: {result.get('errors', [])}")
        if not tests:
            incomplete.append(f"{tier}: no test results.")
        if len(ids) != len(tests):
            incomplete.append(f"{tier}: duplicate test records.")
        if modern:
            if result.get("exit_code") is None or not cov:
                incomplete.append(f"{tier}: missing pytest exit or coverage evidence.")
            collected = {t["nodeid"] for t in cov.get("expected", [])}
            if collected != expected:
                partial.append(f"{tier}: collection differs from the unfiltered suite.")
            if chosen != expected:
                partial.append(f"{tier}: selected {len(chosen)}/{len(expected)} tests.")
            if not chosen or not chosen <= expected:
                incomplete.append(f"{tier}: empty or unknown test selection.")
            if ids != chosen or executed != ids:
                incomplete.append(f"{tier}: selected, executed and recorded test IDs disagree.")
        elif ids != peer_ids:
            incomplete.append(f"{tier}: test records differ from other tiers.")
        for test in tests:
            outcome = test_outcome(data, tier, test)
            if outcome in ("failed", "error", "xpassed"):
                failed.append(f"{tier}: {test['nodeid']}: {outcome}.")
            elif outcome not in ("passed", "xfailed", "n/a"):
                incomplete.append(f"{tier}: {test['nodeid']}: {outcome} is not required coverage.")
            if modern:
                phases = test.get("phases", {})
                required_phases = {"setup": "skipped", "teardown": "passed"} if outcome == "n/a" else {
                    "setup": "passed", "call": "skipped" if outcome == "xfailed" else "passed",
                    "teardown": "passed",
                }
                if any(phases.get(k) != v for k, v in required_phases.items()):
                    incomplete.append(f"{tier}: {test['nodeid']}: incomplete test phase evidence.")
        if not modern or chosen == expected:
            for req in data["reqs"]:
                if cell(data, tier, req["id"]) == UNTESTED:
                    incomplete.append(f"{tier}: {req['id']} has no complete coverage.")
        unit = data["units"].get(tier)
        if unit is None:
            if not is_merge(data, tier) and not meta.get("skip_unit"):
                incomplete.append(f"{tier}: missing required Go unit record.")
            continue
        if unit.get("error"):
            failed.append(f"{tier}: unit: {unit['error']}")
            continue
        packages = unit.get("packages", [])
        if modern:
            selected_packages = unit.get("selected_packages", [])
            recorded_packages = [p.get("package") for p in packages]
            if (not selected_packages or len(set(selected_packages)) != len(selected_packages)
                    or len(set(recorded_packages)) != len(recorded_packages)
                    or set(selected_packages) != set(recorded_packages)):
                incomplete.append(f"{tier}: selected Go packages and package records disagree.")
        if not packages:
            incomplete.append(f"{tier}: no Go packages tested.")
        if unit.get("passed") is not True:
            failed.append(f"{tier}: Go unit stage did not pass.")
        for pkg in packages:
            if pkg.get("passed") is not True or pkg.get("exit_code", 0) != 0 or pkg.get("failed"):
                failed.append(f"{tier}: {pkg.get('package', '?')}: Go tests failed.")
            if modern:
                selected_go, executed_go = set(pkg.get("selected", [])), set(pkg.get("executed", []))
                completed_go, skipped_go = set(pkg.get("completed", [])), set(pkg.get("skipped", []))
                compile_only = pkg.get("compile_only") and not (
                    selected_go or executed_go or completed_go or skipped_go
                )
                if (not compile_only and (not selected_go or selected_go != executed_go
                                          or executed_go != completed_go | skipped_go)
                        or pkg.get("exit_code") is None):
                    incomplete.append(f"{tier}: {pkg.get('package', '?')}: incomplete Go test execution.")
        if modern and not any(p.get("completed") for p in packages):
            incomplete.append(f"{tier}: no Go tests completed successfully.")
    issues = failed + incomplete + partial
    status = "FAILED" if failed else "INCOMPLETE" if incomplete else "PARTIAL" if partial else "PASS"
    if not meta and not failed:
        status = "PARTIAL"  # direct pytest evidence has no runner completeness contract
    if status == "PASS" and not modern:
        status = "LEGACY"
        issues.append("Historical outcomes retained; full-suite collection, exits and phases were not recorded.")
    if modern and final:
        if ((status == "PASS" and meta.get("exit_code") != 0)
                or (status == "PARTIAL" and meta.get("exit_code") != 1)):
            status = "FAILED"
            issues.append(f"Runner exit {meta.get('exit_code')} contradicts the evidence verdict.")
        if status == "PASS":
            try:
                digest = hashlib.sha256((data["run"] / "REPORT.md").read_bytes()).hexdigest()
            except OSError:
                digest = None
            if not digest or digest != stages.get("report", {}).get("sha256"):
                status = "INCOMPLETE"
                issues.append("Published report does not match the finalized report evidence.")
    return {"status": status, "issues": issues, "coverage": coverage}


def all_green(run: Path) -> bool:
    return assess(load(run))["status"] == "PASS"


def outcome_text(test: dict) -> str:
    return OUTCOME_TEXT.get(test["outcome"], test["outcome"])


def evidence_tier(by_tier: dict, owner: str, order: list[str]) -> str | None:
    """The tier whose evidence best shows a test: the owning PR's tier if it ran there."""
    ran = [t for t in order if t in by_tier and by_tier[t]["outcome"] not in ("n/a", "skipped")]
    if owner in ran:
        return owner
    return ran[0] if ran else None
