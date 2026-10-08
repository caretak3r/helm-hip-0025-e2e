"""Turn run directories into the data that the pages show.

Every verdict comes from e2e/grade.py. This module only arranges the verdicts
and the evidence for the templates; it never decides a result.
"""

from __future__ import annotations

import re
import sys
import tarfile
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "e2e"))
sys.path.insert(0, str(ROOT / "e2e" / "lib"))
import grade  # noqa: E402
from paths import SITE_URL  # noqa: E402

PAIRS = Path(__file__).parent / "before_after.yaml"

# Test modules in display order, with their headings.
MODULES = {
    "test_pr1_subcharts": "PR1 · subchart sequencing",
    "test_pr1_lifecycle": "PR1 · upgrade, rollback, uninstall, failure, hooks",
    "test_pr2_groups": "PR2 · resource-group sequencing",
    "test_pr3_readiness": "PR3 · custom readiness",
    "test_combined": "All three PRs together",
    "test_v2_compat": "Chart v2 does not change",
}
OUTCOME_ORDER = ["failed", "error", "xpassed", "passed", "xfailed", "n/a", "skipped"]
OUTCOME_CSS = {"passed": "pass", "failed": "fail", "error": "fail", "xfailed": "xfail", "xpassed": "xpass",
               "n/a": "na", "skipped": "na"}
VERDICT_CSS = {grade.PASS: "pass", grade.FAIL: "fail", grade.BUILD: "fail", grade.XPASS: "xpass",
               grade.XFAIL: "xfail", grade.UNTESTED: "untested", grade.NA: "na"}
MEANING_CSS = {"MET": "pass", "MET (extension)": "pass", "DEVIATION (documented)": "deviation",
               "NOT IMPLEMENTED": "xfail", "FAILING": "fail", "UNTESTED": "untested",
               "NOW PASSING — update requirements.yaml": "xpass", "BUILD FAILED": "fail", "n/a": "na"}
COMMAND = re.compile(r"^(\d\d:\d\d:\d\d\.\d{3}) \$ (.*)$")
EXIT = re.compile(r"^\[exit (-?\d+), ([\d.]+)s\]$")
SHA = re.compile(r"[0-9a-f]{40}")
# A chart directory in a helm command: the tests pass charts/<dir>, relative to the repository root.
CHART_REF = re.compile(r"(^|\s)charts/([\w.-]+)(?=\s|$)")


def web(url: str) -> str:
    return url.removesuffix(".git")


def test_dir(test: dict) -> str:
    return test["evidence"].rsplit("/", 1)[-1] if test.get("evidence") else ""


def ran(test: dict | None) -> bool:
    return bool(test) and test["outcome"] not in ("n/a", "skipped") and bool(test_dir(test))


def page(tier: str, test: dict) -> str:
    """Link from the run page to the page of one test on one tier."""
    return f"{tier}/{test_dir(test)}/index.html"


def commands(log: Path, only_helm: bool = False) -> list[dict]:
    """The commands in a commands.log, each with its exit code and duration."""
    if not log.exists():
        return []
    out: list[dict] = []
    for line in log.read_text().splitlines():
        if m := COMMAND.match(line):
            out.append({"time": m[1], "cmd": m[2], "exit": None, "seconds": None})
        elif (m := EXIT.match(line)) and out and out[-1]["exit"] is None:
            out[-1]["exit"], out[-1]["seconds"] = int(m[1]), float(m[2])
    if only_helm:  # the binary under test: .bin/helm-<tier>
        out = [c for c in out if Path(c["cmd"].split(" ", 1)[0]).name.startswith("helm")]
    return out


def chart_refs(log: Path) -> list[str]:
    """The chart directories that the helm commands in a commands.log read, in order."""
    refs: dict[str, None] = {}
    for c in commands(log, only_helm=True):
        refs.update((m[2], None) for m in CHART_REF.finditer(c["cmd"]))
    return list(refs)


def timeline(test: dict) -> dict | None:
    """The first observation that is a list: the server-clock timeline of the test."""
    for obs in test.get("observations", []):
        if isinstance(obs["value"], list):
            return obs
    return None


def _harness(meta: dict) -> dict:
    harness = meta.get("harness", {})
    url, commit = harness.get("url", ""), harness.get("commit", "")
    sha = bool(SHA.fullmatch(commit))
    return {
        "url": url,
        "commit": commit,
        "short": commit[:12] if sha else (commit or "unknown"),
        "dirty": harness.get("dirty", False),
        "commit_url": f"{url}/commit/{commit}" if url and sha else None,
        "blob": f"{url}/blob/{commit}" if url and sha else None,
        "tree": f"{url}/tree/{commit}" if url and sha else None,
    }


def _cfg_commits(cfg: dict, tier: str) -> dict:
    spec = cfg["tiers"][tier]
    return {cfg["tiers"][m]["branch"]: cfg["tiers"][m]["commit"] for m in spec.get("merge", [tier])}


def _tier(data: dict, tier: str, fork: str, harness: dict) -> dict:
    spec = data["cfg"]["tiers"][tier]
    build = data["builds"].get(tier, {})
    results = data["results"].get(tier)
    tests = results["tests"] if results else []
    counts = Counter(t["outcome"] for t in tests)
    summary = grade.pr_summary(data, tier)
    commits = build.get("commits") or _cfg_commits(data["cfg"], tier)

    def file_link(item: dict) -> dict:
        return {**item, "url": f"{harness['blob']}/{item['file']}" if harness["blob"] else None}

    return {
        "id": tier,
        "label": spec.get("label", tier),
        "title": spec.get("title", tier),
        "pr": spec.get("pr"),
        "merge": [data["cfg"]["tiers"][m].get("label", m) for m in spec.get("merge", [])],
        "commits": [{"branch": b, "sha": s, "url": f"{fork}/commit/{s}"} for b, s in commits.items()],
        "build": build,
        "error": build.get("error"),
        "wiring": [file_link(w) for w in build.get("wiring", [])],
        "resolve": file_link(build["resolve"]) if build.get("resolve") else None,
        "results": results,
        "by_name": {t["name"]: t for t in tests},
        "outcomes": [{"outcome": o, "count": counts[o], "css": OUTCOME_CSS[o],
                      "text": grade.OUTCOME_TEXT.get(o, o)} for o in OUTCOME_ORDER if counts.get(o)],
        "graded": sum(summary["counts"].values()),
        "scope": "all requirements" if grade.is_merge(data, tier) else "the requirements this PR owns",
        "meanings": [{"meaning": m, "count": summary["counts"][m], "css": MEANING_CSS[m]}
                     for m in grade.MEANINGS if summary["counts"].get(m)],
        "unit_text": summary["unit"],
        "unit": data["units"].get(tier),
    }


def _req_rows(data: dict, tiers: list[dict]) -> list[dict]:
    rows = []
    for req in data["reqs"]:
        cells = []
        for tv in tiers:
            verdict = grade.cell(data, tv["id"], req["id"])
            shown = next((t for t in grade.tests_for(data, tv["id"], req["id"]) if ran(t)), None)
            cells.append({"verdict": verdict, "glyph": grade.GLYPH[verdict], "css": VERDICT_CSS[verdict],
                          "owner": tv["id"] == req["owner"], "link": page(tv["id"], shown) if shown else None})
        rows.append({
            "id": req["id"], "title": req["title"], "section": req.get("section", ""), "status": req["status"],
            "owner": grade.label(data, req["owner"]), "hip": " ".join(req["hip"].split()),
            "note": " ".join(req.get("note", "").split()), "cells": cells,
        })
    return rows


def _test_groups(tiers: list[dict]) -> list[dict]:
    order: dict[str, list[str]] = {}
    first: dict[str, dict] = {}
    for tv in tiers:
        for t in (tv["results"] or {}).get("tests", []):
            module = t["nodeid"].split("::")[0].rsplit("/", 1)[-1].removesuffix(".py")
            names = order.setdefault(module, [])
            if t["name"] not in names:
                names.append(t["name"])
                first[t["name"]] = t
    modules = [m for m in MODULES if m in order] + sorted(m for m in order if m not in MODULES)
    groups = []
    for module in modules:
        rows = []
        for name in order[module]:
            cells = []
            for tv in tiers:
                t = tv["by_name"].get(name)
                cells.append(None if t is None else {
                    "text": grade.outcome_text(t), "css": OUTCOME_CSS.get(t["outcome"], "na"),
                    "seconds": t["duration"] if ran(t) else None, "link": page(tv["id"], t) if ran(t) else None,
                })
            rows.append({"name": name, "doc": first[name]["doc"], "reqs": first[name]["reqs"], "cells": cells})
        groups.append({"module": module, "title": MODULES.get(module, module), "rows": rows})
    return groups


def _before_after(run_dir: Path, tiers: list[dict]) -> list[dict]:
    by_id = {tv["id"]: tv for tv in tiers}
    out = []
    for pair in yaml.safe_load(PAIRS.read_text())["pairs"]:
        tv = by_id.get(pair.get("tier", "combined"))
        sides = []
        for key in ("before", "after"):
            side = dict(pair[key])
            t = tv["by_name"].get(side["test"]) if tv else None
            if ran(t):
                side.update({
                    "found": True, "text": grade.outcome_text(t), "css": OUTCOME_CSS.get(t["outcome"], "na"),
                    "commands": commands(run_dir / tv["id"] / test_dir(t) / "commands.log", only_helm=True),
                    "timeline": timeline(t), "link": page(tv["id"], t),
                })
            else:
                side["found"] = False
            sides.append(side)
        out.append({**pair, "tier_label": tv["label"] if tv else pair.get("tier", "combined"), "sides": sides})
    return out


def _archive_files(archive: Path) -> list[dict]:
    """The files in a chart archive, in archive order, as text where they are UTF-8."""
    files = []
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            if member.isfile():
                data = tar.extractfile(member).read()
                try:
                    text = data.decode()
                except UnicodeDecodeError:
                    text = None
                files.append({"path": member.name, "bytes": member.size, "text": text})
    return files


def _charts(run_dir: Path, meta: dict, harness: dict, tiers: list[dict]) -> dict:
    """The charts that the tests of a run read, and the tests that read each chart.

    A run keeps its charts as archives in runs/<stamp>/charts/ (run.json maps them). A run
    from before the archives links to the chart directories in its harness commit."""
    charts: dict[str, dict] = {}
    for rec in meta.get("charts", []):
        name = Path(rec["source"]).name
        archive = run_dir / "charts" / rec["archive"]
        files = _archive_files(archive)
        chart_yaml = next(f["text"] for f in files if f["path"] == f"{rec['name']}/Chart.yaml")
        charts[name] = {**rec, "page": f"charts/{name}/index.html", "bytes": archive.stat().st_size,
                        "description": yaml.safe_load(chart_yaml).get("description", ""), "files": files}
    archived = bool(charts)
    uses: dict[str, dict[str, list[str]]] = {}
    for tv in tiers:
        for test in (tv["results"] or {}).get("tests", []):
            if not test_dir(test):
                continue
            names = chart_refs(run_dir / tv["id"] / test_dir(test) / "commands.log")
            uses.setdefault(tv["id"], {})[test["name"]] = names
            for name in names:
                chart = charts.setdefault(name, {"source": f"charts/{name}", "page": None})
                chart.setdefault("used_by", []).append({"tier": tv["label"], "test": test["name"],
                                                        "link": page(tv["id"], test)})
    for name, chart in charts.items():
        chart.setdefault("used_by", [])
        chart["dir"] = name
        chart["tree"] = f"{harness['tree']}/{chart['source']}" if harness["tree"] else None
    return {
        "archived": archived,
        "all": [charts[name] for name in sorted(charts)],  # not "items": Jinja would find dict.items
        "by_dir": charts,
        "uses": uses,
        "repo_name": f"hip0025-{run_dir.name}",
        "repo_url": f"{SITE_URL}{run_dir.name}/charts" if archived else None,
    }


def load_run(run_dir: Path) -> dict:
    data = grade.load(run_dir)
    harness = _harness(data["meta"])
    fork = web(data["cfg"]["fork"]["url"])
    tiers = [_tier(data, t, fork, harness) for t in data["tiers"]]
    return {
        "stamp": run_dir.name,
        "dir": run_dir,
        "meta": data["meta"],
        "data": data,
        "harness": harness,
        "fork": fork,
        "upstream": web(data["cfg"]["upstream"]["url"]),
        "base": data["cfg"]["upstream"]["base"],
        "tiers": tiers,
        "green": grade.all_green(run_dir),
        "req_rows": _req_rows(data, tiers),
        "test_groups": _test_groups(tiers),
        "before_after": _before_after(run_dir, tiers),
        "charts": _charts(run_dir, data["meta"], harness, tiers),
        "pages": [(tv, t) for tv in tiers for t in (tv["results"] or {}).get("tests", []) if test_dir(t)],
    }


def collect_runs(runs_dir: Path) -> list[dict]:
    """Every run under runs_dir that has a run.json, newest first."""
    dirs = sorted(d for d in runs_dir.iterdir() if (d / "run.json").is_file()) if runs_dir.is_dir() else []
    runs = [load_run(d) for d in dirs]
    runs.sort(key=lambda r: (r["meta"].get("started_utc", ""), r["stamp"]), reverse=True)
    return runs
