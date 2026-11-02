"""Isolated evidence regressions; no Helm, Docker or Kubernetes is needed."""

from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
import yaml

from testgrid import collect, render

# collect sets up the same import paths as the dashboard entrypoint.
grade = collect.grade
report = importlib.import_module("report")
runner = importlib.import_module("run")

ROOT = Path(__file__).resolve().parents[2]
# The live catalog has no not-implemented requirement, so the fixture marks this one as
# not-implemented in its own copy. The strict-xfail rules of the grader stay under test.
STRICT_XFAIL = "R24"


def save(path, value):
    path.write_text(json.dumps(value))


def change(path, fn):
    value = json.loads(path.read_text())
    fn(value)
    save(path, value)


def publish_report(run):
    preview = report.render(run, final=False)
    change(run / "run.json", lambda d: d["stages"].update(
        report={"status": "passed", "sha256": runner.sha256(preview)}))
    preview.replace(run / "REPORT.md")


@pytest.fixture
def evidence(tmp_path):
    run = tmp_path / "runs" / "isolated"
    run.mkdir(parents=True)
    for name in ("tiers.yaml", "requirements.yaml"):
        shutil.copy(ROOT / name, run / name)
    cfg = yaml.safe_load((run / "tiers.yaml").read_text())
    catalog = yaml.safe_load((run / "requirements.yaml").read_text())
    for req in catalog["requirements"]:
        if req["id"] == STRICT_XFAIL:
            req["status"] = "not-implemented"
    (run / "requirements.yaml").write_text(yaml.safe_dump(catalog, sort_keys=False))
    reqs = catalog["requirements"]
    suite = [{"nodeid": f"e2e/tests/test_contract.py::test_{r['id']}", "reqs": [r["id"]],
              "needs": cfg["tiers"].get(r["owner"], {}).get("features", []),
              "xfail_strict": r["status"] == "not-implemented"} for r in reqs]
    stages = {s: {"status": "passed"} for s in (
        "collection", "sources", "cluster", "metadata", "charts", "grading", "report",
    )}
    meta = {"evidence_version": 2, "tiers": list(cfg["tiers"]), "suite": suite, "status": "completed",
            "pytest_args": [], "skip_unit": False, "stages": stages, "exit_code": 0}
    for tier, spec in cfg["tiers"].items():
        out = run / tier
        out.mkdir()
        tests = []
        for entry in suite:
            na = bool(set(entry["needs"]) - set(spec["features"]))
            result = "n/a" if na else "xfailed" if entry["xfail_strict"] else "passed"
            tests.append({**entry, "name": entry["nodeid"].split("::")[-1], "doc": "Contract evidence",
                          "outcome": result, "reason": "", "duration": 0, "observations": [], "evidence": "",
                          "phases": {"setup": "skipped" if na else "passed", "teardown": "passed",
                                     **({} if na else {"call": "skipped" if result == "xfailed" else "passed"})}})
        ids = [t["nodeid"] for t in tests]
        save(out / "results.json", {"tests": tests, "coverage": {"expected": suite, "selected": ids,
                                                               "executed": ids}, "exit_code": 0, "errors": []})
        save(out / "build.json", {"tree": "abc", "version": "v4"})
        stages[f"build:{tier}"] = {"status": "passed"}
        stages[f"e2e:{tier}"] = {"status": "passed", "exit_code": 0}
        if "commit" in spec:
            save(out / "unit.json", {"passed": True, "base": "abc", "head": "def",
                                    "selected_packages": ["pkg/example"], "packages": [
                {"package": "pkg/example", "passed": True, "scope": "all tests", "summary": "ok",
                 "seconds": 0, "log": "unit.log", "exit_code": 0,
                 "selected": ["TestExample"], "executed": ["TestExample"], "completed": ["TestExample"],
                 "failed": [], "skipped": []}]})
            stages[f"unit:{tier}"] = {"status": "passed"}
    save(run / "run.json", meta)
    publish_report(run)
    return run


def assert_consumers(run, expected):
    data = collect.load_run(run)
    assert data["assessment"]["status"] == expected
    assert data["green"] is (expected == "PASS")
    text = report.render(run).read_text()
    assert f"**Run status: {expected}**" in text
    out = run.parent.parent / "site"
    render.build(run.parent, out)
    assert expected in (out / run.name / "index.html").read_text()
    assert expected in (out / "index.html").read_text()
    if expected != "PASS":
        assert data["assessment"]["issues"]
    return data


def test_complete_run_with_na_and_strict_xfail(evidence):
    data = assert_consumers(evidence, "PASS")["data"]
    assert grade.cell(data, "pr1", STRICT_XFAIL) == grade.NA
    assert grade.cell(data, "combined", STRICT_XFAIL) == grade.XFAIL


@pytest.mark.parametrize("mutation, status", [
    ("empty", "INCOMPLETE"), ("missing_test", "INCOMPLETE"), ("missing_unit", "INCOMPLETE"),
    ("error_unit", "FAILED"), ("lying_unit", "FAILED"), ("zero_go", "INCOMPLETE"),
    ("go_no_match", "INCOMPLETE"), ("missing_tier", "INCOMPLETE"), ("zero_tiers", "INCOMPLETE"),
    ("pytest_exit", "FAILED"), ("collection", "FAILED"), ("teardown", "FAILED"),
    ("setup", "FAILED"), ("skip", "INCOMPLETE"), ("xfail", "FAILED"), ("xpass", "FAILED"),
    ("fake_na", "FAILED"), ("missing_phases", "INCOMPLETE"), ("worker", "FAILED"),
    ("loose_xfail", "FAILED"),
])
def test_incomplete_and_failed_evidence(evidence, mutation, status):
    result = evidence / "combined" / "results.json"
    unit = evidence / "pr1" / "unit.json"
    if mutation == "empty":
        change(result, lambda d: d.update(tests=[]))
    elif mutation == "missing_test":
        change(result, lambda d: d["tests"].pop())
    elif mutation == "missing_unit":
        unit.unlink()
    elif mutation == "error_unit":
        save(unit, {"error": "unit worker exploded"})
    elif mutation == "lying_unit":
        change(unit, lambda d: d["packages"][0].update(passed=False))
    elif mutation == "zero_go":
        change(unit, lambda d: d.update(packages=[]))
    elif mutation == "go_no_match":
        change(unit, lambda d: d["packages"][0].update(executed=[]))
    elif mutation in ("missing_tier", "zero_tiers"):
        for tier in (["pr1"] if mutation == "missing_tier" else ["pr1", "pr2", "pr3", "combined"]):
            shutil.rmtree(evidence / tier)
    elif mutation == "pytest_exit":
        change(result, lambda d: d.update(exit_code=2))
    elif mutation == "collection":
        change(result, lambda d: d.update(errors=[{"phase": "collection", "error": "import failed"}]))
    elif mutation in ("setup", "teardown"):
        change(result, lambda d: d["tests"][0]["phases"].update({mutation: "failed"}))
    elif mutation == "missing_phases":
        change(result, lambda d: d["tests"][0].pop("phases"))
    elif mutation == "loose_xfail":
        change(result, lambda d: next(t for t in d["tests"] if STRICT_XFAIL in t["reqs"]).update(xfail_strict=False))
    elif mutation == "worker":
        change(evidence / "run.json", lambda d: d["stages"]["e2e:pr1"].update(
            status="failed", error="pytest worker exploded"))
    else:
        outcome = {"skip": "skipped", "xfail": "xfailed", "xpass": "xpassed", "fake_na": "n/a"}[mutation]
        change(result, lambda d: d["tests"][0].update(outcome=outcome))
    assert_consumers(evidence, status)


@pytest.mark.parametrize("selection", ["tiers", "tests", "skip_unit", "manual"])
def test_diagnostic_runs_are_partial(evidence, selection):
    if selection == "tiers":
        change(evidence / "run.json", lambda d: d.update(tiers=["pr1"]))
        for tier in ("pr2", "pr3", "combined"):
            shutil.rmtree(evidence / tier)
    elif selection == "skip_unit":
        change(evidence / "run.json", lambda d: d.update(skip_unit=True))
        for tier in ("pr1", "pr2", "pr3"):
            (evidence / tier / "unit.json").unlink()
            change(evidence / "run.json", lambda d, t=tier: d["stages"][f"unit:{t}"].update(status="skipped"))
    elif selection == "tests":
        change(evidence / "run.json", lambda d: d.update(pytest_args=["-k", "R01"]))
        for tier in ("pr1", "pr2", "pr3", "combined"):
            def select(d):
                d["tests"] = d["tests"][:1]
                d["coverage"]["selected"] = d["coverage"]["selected"][:1]
                d["coverage"]["executed"] = d["coverage"]["executed"][:1]
            change(evidence / tier / "results.json", select)
    else:
        (evidence / "run.json").unlink()
        for tier in ("pr2", "pr3", "combined"):
            shutil.rmtree(evidence / tier)
        (evidence / "pr1" / "build.json").unlink()
        (evidence / "pr1" / "unit.json").unlink()
    if (evidence / "run.json").exists():
        change(evidence / "run.json", lambda d: d.update(exit_code=1))
    assert_consumers(evidence, "PARTIAL")


def test_legacy_is_not_relabelled_failed(evidence):
    change(evidence / "run.json", lambda d: [d.pop(k) for k in ("evidence_version", "suite", "stages", "status")])
    assert_consumers(evidence, "LEGACY")


def test_early_failure_without_environment_metadata(evidence):
    for tier in ("pr1", "pr2", "pr3", "combined"):
        shutil.rmtree(evidence / tier)
    save(evidence / "run.json", {"evidence_version": 2, "status": "failed", "stages": {
        "sources": {"status": "failed", "error": "fetch unavailable"}}})
    data = assert_consumers(evidence, "FAILED")
    assert any("fetch unavailable" in issue for issue in data["assessment"]["issues"])


@pytest.mark.parametrize("stage", ["early_failure", "partial_artifacts"])
def test_dashboard_links_only_to_recorded_evidence(evidence, stage):
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.hrefs = []

        def handle_starttag(self, tag, attrs):
            if tag == "a":
                self.hrefs.extend(value for name, value in attrs if name == "href" and value)

    if stage == "early_failure":
        for tier in ("pr1", "pr2", "pr3", "combined"):
            shutil.rmtree(evidence / tier)
        change(evidence / "run.json", lambda d: d.update(status="failed", exit_code=1))
    else:
        for path in ("run.json", "REPORT.md", "pr1/results.json"):
            (evidence / path).unlink()

    out = evidence.parent.parent / "site"
    render.build(evidence.parent, out)
    page = out / evidence.name / "index.html"
    links = Links()
    links.feed(page.read_text())
    local_paths = [u.path for href in links.hrefs
                   if not (u := urlsplit(href)).scheme and not u.netloc and u.path]
    assert {"requirements.yaml", "tiers.yaml"}.issubset(local_paths)
    if stage == "partial_artifacts":
        assert "pr3/build.json" in local_paths
    for path in local_paths:
        assert (page.parent / path).is_file(), f"Link has no recorded artifact: {path}"


@pytest.mark.parametrize("stage_name, exit_code", [
    *[(s, None) for s in ("collection", "sources", "cluster", "metadata", "charts",
                         "build:pr1", "e2e:pr1", "unit:pr1")],
    ("e2e:pr1", 5), ("publication", None), (None, None),
])
def test_runner_persists_worker_and_early_failures(evidence, monkeypatch, stage_name, exit_code):
    meta = json.loads((evidence / "run.json").read_text())
    monkeypatch.setattr(runner, "RUNS", evidence.parent)
    monkeypatch.setattr(runner, "ROOT", evidence)  # snapshot the fixture's catalog, not the live one
    monkeypatch.setattr(runner, "rel", str)
    monkeypatch.setattr(runner, "collect_suite", lambda out: meta["suite"])
    monkeypatch.setattr(runner, "fetch_sources", lambda: None)
    monkeypatch.setattr(runner, "ensure_cluster", lambda: None)
    monkeypatch.setattr(runner, "run_meta", lambda *args: {})
    monkeypatch.setattr(runner.chartrepo, "publish", lambda *args, **kw: [])
    monkeypatch.setattr(runner, "build", lambda *args: {"binary": "unused", "version": "v4", "tree": "abc"})

    def unit(tier, out):
        record = json.loads((evidence / tier / "unit.json").read_text())
        save(out / "unit.json", record)
        return record

    def e2e(tier, binary, out, args):
        shutil.copy(evidence / tier / "results.json", out / "results.json")
        return 0

    monkeypatch.setattr(runner, "unit", unit)
    monkeypatch.setattr(runner, "e2e", e2e)
    if stage_name == "publication":
        replace = Path.replace

        def fail_publication(path, target):
            if path.name == "REPORT.md.tmp":
                raise OSError("injected publication exception")
            return replace(path, target)

        monkeypatch.setattr(Path, "replace", fail_publication)
    elif stage_name:
        target = {"collection": "collect_suite", "sources": "fetch_sources", "cluster": "ensure_cluster",
                  "metadata": "run_meta", "charts": "publish"}.get(stage_name, stage_name.split(":")[0])

        def fail(*args, **kwargs):
            if exit_code is not None:
                return exit_code
            raise RuntimeError(f"injected {stage_name} exception")

        monkeypatch.setattr(runner.chartrepo if stage_name == "charts" else runner, target, fail)
    out = runner.run(list(runner.TIERS), SimpleNamespace(pytest=[], skip_unit=False, rebuild=False))
    saved = json.loads((out / "run.json").read_text())
    if stage_name:
        assert saved["exit_code"] != 0
        stage = saved["stages"]["report" if stage_name == "publication" else stage_name]
        assert stage["status"] == "failed"
        if exit_code is None:
            assert f"injected {stage_name} exception" in stage["error"]
        else:
            assert stage["exit_code"] == exit_code
    else:
        assert saved["exit_code"] == 0
    assert_consumers(out, "FAILED" if stage_name else "PASS")


def test_zero_selected_go_tests_are_not_passes(evidence):
    result = runner.go_coverage([], ["TestMissing"], 0)
    assert not result["passed"]
    change(evidence / "pr1" / "unit.json", lambda d: d["packages"][0].update(result))
    assert_consumers(evidence, "FAILED")


def test_compile_only_package_is_not_a_test_pass(evidence):
    result = runner.go_coverage([], [], 0, compile_only=True)
    change(evidence / "pr1" / "unit.json", lambda d: d["packages"].append({
        **d["packages"][0], **result, "package": "pkg/no_tests",
    }))
    change(evidence / "pr1" / "unit.json", lambda d: d["selected_packages"].append("pkg/no_tests"))
    publish_report(evidence)
    data = assert_consumers(evidence, "PASS")
    assert data["tiers"][0]["unit_text"].startswith("1/1")
    change(evidence / "pr1" / "unit.json", lambda d: d.update(
        packages=d["packages"][1:], selected_packages=["pkg/no_tests"]))
    assert_consumers(evidence, "INCOMPLETE")


@pytest.fixture
def pytest_project(tmp_path):
    root = tmp_path / "pytest-project"
    (root / "e2e" / "tests").mkdir(parents=True)
    shutil.copy(ROOT / "tiers.yaml", root / "tiers.yaml")
    shutil.copy(ROOT / "e2e" / "conftest.py", root / "e2e" / "conftest.py")
    shutil.copytree(ROOT / "e2e" / "lib", root / "e2e" / "lib", ignore=shutil.ignore_patterns("__pycache__"))
    return root


@pytest.mark.parametrize("case, body, expected", [
    ("pass", "def test_probe():\n    assert True\n", "PASS"),
    ("setup", "@pytest.fixture\ndef broken():\n    assert False\n"
     "def test_probe(broken):\n    pass\n", "FAILED"),
    ("teardown", "@pytest.fixture\ndef broken():\n    yield\n    assert False\n"
     "def test_probe(broken):\n    pass\n", "FAILED"),
    ("collection", "raise RuntimeError('collection broken')\n", "FAILED"),
    ("skip", "def test_probe():\n    pytest.skip('N/A: arbitrary skip is not feature gating')\n", "INCOMPLETE"),
    ("xfail", "@pytest.mark.xfail(strict=True)\ndef test_probe():\n    assert False\n", "FAILED"),
    ("xpass", "@pytest.mark.xfail(strict=True)\ndef test_probe():\n    assert True\n", "FAILED"),
])
def test_real_pytest_phase_evidence_reaches_consumers(evidence, pytest_project, case, body, expected):
    source = pytest_project / "e2e" / "tests" / "test_probe.py"
    source.write_text("import pytest\npytestmark = pytest.mark.req('R01')\n" + body)
    out = pytest_project / "output"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "e2e/tests", "--tier", "pr1", "--helm", "missing-binary",
         "--out", str(out), "-q", "-o", "addopts="],
        cwd=pytest_project, env={**os.environ, "PYTEST_ADDOPTS": ""}, capture_output=True, text=True,
    )
    result = json.loads((out / "results.json").read_text())
    assert result["exit_code"] == proc.returncode
    if case in ("setup", "teardown"):
        assert result["tests"][0]["phases"][case] == "failed"
    if case == "collection":
        assert result["errors"]
    reqs = yaml.safe_load((evidence / "requirements.yaml").read_text())
    reqs["requirements"] = [r for r in reqs["requirements"] if r["id"] == "R01"]
    (evidence / "requirements.yaml").write_text(yaml.safe_dump(reqs))
    change(evidence / "run.json", lambda d: d.update(suite=result["coverage"]["expected"]))
    for tier in ("pr1", "pr2", "pr3", "combined"):
        save(evidence / tier / "results.json", result)
    if expected == "PASS":
        publish_report(evidence)
    assert_consumers(evidence, expected)


@pytest.mark.parametrize("selection_source", ["environment", "configuration"])
def test_unfiltered_collection_ignores_selection(evidence, pytest_project, monkeypatch, selection_source):
    source = pytest_project / "e2e" / "tests" / "test_probe.py"
    source.write_text("import pytest\npytestmark = pytest.mark.req('R01')\n"
                      "def test_keep():\n    pass\n\ndef test_drop():\n    pass\n")
    monkeypatch.setattr(runner, "ROOT", pytest_project)
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k keep" if selection_source == "environment" else "")
    if selection_source == "configuration":
        (pytest_project / "pyproject.toml").write_text('[tool.pytest.ini_options]\naddopts = "-k keep"\n')
    out = pytest_project / "output"
    out.mkdir()
    suite = runner.collect_suite(out)
    assert {s["nodeid"].split("::")[-1] for s in suite} == {"test_keep", "test_drop"}
    selected = pytest_project / "selected"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "e2e/tests", "--tier", "pr1", "--helm", "missing-binary",
         "--out", str(selected), "-q"],
        cwd=pytest_project, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads((selected / "results.json").read_text())
    assert len(result["coverage"]["expected"]) == 2
    assert len(result["coverage"]["selected"]) == len(result["coverage"]["executed"]) == 1
    reqs = yaml.safe_load((evidence / "requirements.yaml").read_text())
    reqs["requirements"] = [r for r in reqs["requirements"] if r["id"] == "R01"]
    (evidence / "requirements.yaml").write_text(yaml.safe_dump(reqs))
    change(evidence / "run.json", lambda d: d.update(suite=suite))
    for tier in ("pr1", "pr2", "pr3", "combined"):
        save(evidence / tier / "results.json", result)
    change(evidence / "run.json", lambda d: d.update(exit_code=1))
    assert_consumers(evidence, "PARTIAL")


def test_fully_skipped_go_package_is_accounted_for(evidence):
    result = runner.go_coverage([
        {"Action": "run", "Test": "TestEnvironment"},
        {"Action": "skip", "Test": "TestEnvironment"},
    ], ["TestEnvironment"], 0)
    assert result["passed"]
    unit = evidence / "pr1" / "unit.json"
    change(unit, lambda d: d["packages"].append({
        **d["packages"][0], **result, "package": "pkg/skipped",
    }))
    change(unit, lambda d: d["selected_packages"].append("pkg/skipped"))
    publish_report(evidence)
    assert_consumers(evidence, "PASS")
    change(unit, lambda d: d.update(packages=d["packages"][1:], selected_packages=["pkg/skipped"]))
    assert_consumers(evidence, "INCOMPLETE")


@pytest.mark.parametrize("mutation", ["missing", "duplicate_record", "duplicate_selection", "missing_manifest"])
def test_selected_go_package_manifest_is_required(evidence, mutation):
    unit = evidence / "pr1" / "unit.json"
    change(unit, lambda d: d["packages"].append({**d["packages"][0], "package": "pkg/second"}))
    change(unit, lambda d: d["selected_packages"].append("pkg/second"))
    publish_report(evidence)
    assert_consumers(evidence, "PASS")
    if mutation == "missing":
        change(unit, lambda d: d["packages"].pop())
    elif mutation == "duplicate_record":
        change(unit, lambda d: d["packages"].append(d["packages"][0]))
    elif mutation == "duplicate_selection":
        change(unit, lambda d: d["selected_packages"].append("pkg/example"))
    else:
        change(unit, lambda d: d.pop("selected_packages"))
    assert_consumers(evidence, "INCOMPLETE")


@pytest.mark.parametrize("stage", ["grading", "report"])
@pytest.mark.parametrize("state", ["absent", "running"])
@pytest.mark.parametrize("runner_status", ["finalizing", "completed"])
def test_interrupted_finalization_cannot_pass(evidence, stage, state, runner_status):
    change(evidence / "run.json", lambda d: d.update(status=runner_status))
    if state == "absent":
        change(evidence / "run.json", lambda d: d["stages"].pop(stage))
    else:
        change(evidence / "run.json", lambda d: d["stages"][stage].update(status=state))
    assert_consumers(evidence, "INCOMPLETE")


def test_nonzero_terminal_exit_contradicts_pass(evidence):
    change(evidence / "run.json", lambda d: d.update(exit_code=1))
    assert_consumers(evidence, "FAILED")


def test_zero_terminal_exit_cannot_claim_partial_as_success(evidence):
    change(evidence / "run.json", lambda d: d.update(tiers=["pr1"]))
    assert_consumers(evidence, "FAILED")


def test_unpublished_report_stays_incomplete_after_report_command(evidence):
    (evidence / "REPORT.md").replace(evidence / "REPORT.md.tmp")
    assert_consumers(evidence, "INCOMPLETE")
    site = evidence.parent.parent / "site" / evidence.name
    assert not (site / "REPORT.md.tmp").exists()
    proc = subprocess.run(
        [sys.executable, str(ROOT / "e2e" / "run.py"), "report", "--run", str(evidence)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not grade.all_green(evidence)
    assert_consumers(evidence, "INCOMPLETE")
