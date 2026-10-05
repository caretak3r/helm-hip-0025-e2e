"""Grade a run against the HIP-0025 requirement catalog.

REPORT.md (report.py) and the dashboard (testgrid/) both take their verdicts from
this module, so the two views cannot disagree. A run directory carries copies of
tiers.yaml and requirements.yaml from the moment it ran; grading uses those copies,
so a later change to the catalog does not change an old run.
"""

from __future__ import annotations

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
    tiers = [t for t in cfg["tiers"] if (run / t).is_dir()]
    data = {"run": run, "cfg": cfg, "reqs": _yaml(run, "requirements.yaml")["requirements"], "tiers": tiers,
            "results": {}, "builds": {}, "units": {}}
    for tier in tiers:
        for key, name in (("results", "results.json"), ("builds", "build.json"), ("units", "unit.json")):
            f = run / tier / name
            if f.exists():
                data[key][tier] = json.loads(f.read_text())
    meta = run / "run.json"
    data["meta"] = json.loads(meta.read_text()) if meta.exists() else {}
    return data


def label(data: dict, tier: str) -> str:
    return data["cfg"]["tiers"].get(tier, {}).get("label", tier)


def is_merge(data: dict, tier: str) -> bool:
    return "merge" in data["cfg"]["tiers"].get(tier, {})


def tests_for(data: dict, tier: str, rid: str) -> list[dict]:
    return [t for t in data["results"].get(tier, {}).get("tests", []) if rid in t["reqs"]]


def cell(data: dict, tier: str, rid: str) -> str:
    if tier not in data["results"]:
        return BUILD
    tests = tests_for(data, tier, rid)
    if not tests:
        return UNTESTED
    outcomes = {t["outcome"] for t in tests}
    if outcomes & {"failed", "error"}:
        return FAIL
    if "xpassed" in outcomes:
        return XPASS
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
        ok = sum(p["passed"] for p in unit["packages"])
        unit_text = f"{ok}/{len(unit['packages'])} packages pass"
    return {"counts": counts, "unit": unit_text}


def all_green(run: Path) -> bool:
    data = load(run)
    for tier in data["tiers"]:
        if "error" in data["builds"].get(tier, {}) or not data["units"].get(tier, {}).get("passed", True):
            return False
        for req in data["reqs"]:
            if cell(data, tier, req["id"]) in (FAIL, XPASS, BUILD):
                return False
    return True


def outcome_text(test: dict) -> str:
    return OUTCOME_TEXT.get(test["outcome"], test["outcome"])


def evidence_tier(by_tier: dict, owner: str, order: list[str]) -> str | None:
    """The tier whose evidence best shows a test: the owning PR's tier if it ran there."""
    ran = [t for t in order if t in by_tier and by_tier[t]["outcome"] not in ("n/a", "skipped")]
    if owner in ran:
        return owner
    return ran[0] if ran else None
