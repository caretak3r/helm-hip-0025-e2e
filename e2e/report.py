"""Write runs/<stamp>/REPORT.md: the run graded against the HIP-0025 requirement catalog.

The dashboard (testgrid/) shows the same verdicts as HTML; both come from grade.py.
"""

from __future__ import annotations

from pathlib import Path

from grade import (
    FAIL,
    GLYPH,
    MEANINGS,
    XPASS,
    cell,
    evidence_tier,
    label,
    load,
    outcome_text,
    pr_summary,
    tests_for,
)
from paths import SITE_URL


def _built_from(data: dict, tier: str) -> str:
    b = data["builds"].get(tier, {})
    if "error" in b:
        return f"build failed: {b['error'].splitlines()[0]}"
    commits = ", ".join(f"`{branch}` @ `{sha[:9]}`" for branch, sha in b.get("commits", {}).items())
    wiring = ", ".join(w["name"] for w in b.get("wiring", []))
    return f"{commits} · wiring {wiring} · tree `{b.get('tree', '?')[:9]}` · `{b.get('version', '?')}`"


def render(run: Path) -> Path:
    data = load(run)
    tiers = data["tiers"]
    meta = data["meta"]
    cluster = meta.get("cluster", {})
    lines: list[str] = []
    w = lines.append
    w(f"# HIP-0025 end-to-end report · {run.name}")
    w("")
    w("Each tier is a `helm` binary built from the pull request commits in `tiers.yaml`. The tests install the "
      f"charts in `charts/` with this binary on the kind cluster `{cluster.get('name', '?')}` "
      f"(Kubernetes {cluster.get('server_version', '?')}, node image `{cluster.get('node_image', '?')}`). "
      "Every ordering fact and every readiness fact below comes from the kube-apiserver audit log: one clock, "
      "microsecond timestamps. The requirement catalog is `requirements.yaml`.")
    w("")
    if meta.get("charts"):
        w("The run keeps the charts that the tests read as a Helm chart repository: see [Charts](#charts).")
        w("")
    w("Upstream Helm cannot install chart-v3 releases yet. For this reason every tier also contains the test-only "
      "patches in `wiring/`. The patches connect the `helm` commands to the code of each PR. They do not decide "
      "the order or the readiness of resources.")
    w("")
    harness = meta.get("harness", {})
    w(f"Harness commit `{harness.get('commit', '?')[:12]}`{' (with local changes)' if harness.get('dirty') else ''} · "
      f"started {meta.get('started_utc', '?')} · finished {meta.get('finished_utc', '?')} · "
      f"Go {meta.get('tools', {}).get('go', '?')} · {meta.get('host', {}).get('os', '?')}/"
      f"{meta.get('host', {}).get('arch', '?')}")
    w("")

    w("## Verdict per PR")
    w("")
    w("| Tier | Built from | HIP requirements graded | Result | Go unit tests (the PR's own) |")
    w("|---|---|---|---|---|")
    for tier in tiers:
        s = pr_summary(data, tier)
        graded = sum(s["counts"].values())
        result = ", ".join(f"{s['counts'][k]} {k.lower()}" for k in MEANINGS if s["counts"].get(k))
        scope = "all" if "merge" in data["cfg"]["tiers"][tier] else "owned by this PR"
        title = data["cfg"]["tiers"][tier]["title"]
        w(f"| **{title}** | {_built_from(data, tier)} | {graded} ({scope}) | {result} | {s['unit']} |")
    w("")

    w("## Requirement matrix")
    w("")
    w("`✓` pass · `✗` fail · `○` not implemented (expected) · `—` not in this tier · **bold** = the owning PR's tier")
    w("")
    w("| Req | HIP-0025 requirement | Owner | Status | " + " | ".join(label(data, t) for t in tiers) + " |")
    w("|---|---|---|---|" + "---|" * len(tiers))
    for req in data["reqs"]:
        cells = []
        for tier in tiers:
            v = cell(data, tier, req["id"])
            text = f"{GLYPH[v]} {v}"
            cells.append(f"**{text}**" if tier == req["owner"] else text)
        w(f"| [{req['id']}](#{req['id'].lower()}) | {req['title']} | {label(data, req['owner'])} "
          f"| {req['status']} | " + " | ".join(cells) + " |")
    w("")

    failing = [(r, t) for r in data["reqs"] for t in tiers if cell(data, t, r["id"]) in (FAIL, XPASS)]
    if failing:
        w("## Needs attention")
        w("")
        for req, tier in failing:
            for test in tests_for(data, tier, req["id"]):
                if test["outcome"] in ("failed", "error", "xpassed"):
                    w(f"- **{req['id']} on {label(data, tier)}** — `{test['name']}`: {test['doc']}  ")
                    w(f"  `{_one_line(test['reason'])}`")
        w("")

    w("## Requirements in detail")
    for req in data["reqs"]:
        w("")
        w(f"### {req['id']}")
        w(f"**{req['title']}** · owner {label(data, req['owner'])} · status `{req['status']}`")
        w("")
        w("> " + " ".join(req["hip"].split()) + f"  \n> — HIP-0025, {req['section']}")
        if req.get("note"):
            w("")
            w(f"Note: {' '.join(req['note'].split())}")
        names: dict[str, dict] = {}
        for tier in tiers:
            for test in tests_for(data, tier, req["id"]):
                names.setdefault(test["name"], {"doc": test["doc"], "tiers": {}})["tiers"][tier] = test
        if not names:
            w("")
            w("**No test covers this requirement.**")
            continue
        for name, info in names.items():
            w("")
            verdicts = " · ".join(f"{label(data, t)} {outcome_text(info['tiers'][t])}" for t in tiers
                                  if t in info["tiers"])
            w(f"- `{name}` — {info['doc']}  ")
            w(f"  {verdicts}")
            shown = evidence_tier(info["tiers"], req["owner"], tiers)
            if shown:
                test = info["tiers"][shown]
                links = [f"<a href=\"{test['evidence']}/commands.log\">commands</a>"]
                if (run / test["evidence"] / "audit.jsonl").exists():
                    links.append(f"<a href=\"{test['evidence']}/audit.jsonl\">audit slice</a>")
                w(f"  <details><summary>evidence ({label(data, shown)}): {', '.join(links)}</summary>")
                w("")
                w("  ```")
                for obs in test["observations"]:
                    w(f"  {obs['label']}:")
                    for line in _obs_lines(obs["value"]):
                        w(f"    {line}")
                w("  ```")
                w("  </details>")
            for tier, test in info["tiers"].items():
                if test["outcome"] in ("failed", "error"):
                    w(f"  - failure on {label(data, tier)}: `{_one_line(test['reason'])}`")

    w("")
    w("## Go unit tests (each PR's own, on the pure PR commit)")
    for tier in tiers:
        unit = data["units"].get(tier)
        if not unit or "error" in unit:
            continue
        w("")
        w(f"**{data['cfg']['tiers'][tier]['title']}** · `{unit['base'][:9]}..{unit['head'][:9]}`")
        w("")
        w("| Package | Scope | Result | Time |")
        w("|---|---|---|---|")
        for pkg in unit["packages"]:
            res = "✓ pass" if pkg["passed"] else f"✗ {pkg['summary']}"
            w(f"| `{pkg['package']}` | {pkg['scope']} | [{res}]({tier}/{pkg['log']}) | {pkg['seconds']}s |")
    w("")
    _charts(lines, run, meta.get("charts", []))
    md = run / "REPORT.md"
    md.write_text("\n".join(lines) + "\n")
    return md


def _charts(lines: list[str], run: Path, charts: list[dict]) -> None:
    if not charts:  # a run from before the chart archives
        return
    w = lines.append
    example = next((c for c in charts if c["apiVersion"] == "v3"), charts[0])
    w("## Charts")
    w("")
    w("[`charts/`](charts/index.yaml) is a Helm chart repository with one archive for each chart directory that the "
      "tests read. An archive holds the files that helm loads from the chart directory, byte for byte.")
    w("")
    w("| Chart directory | Chart | Archive | sha256 |")
    w("|---|---|---|---|")
    for c in charts:
        w(f"| `{c['source']}` | `{c['name']}` {c['version']}, apiVersion {c['apiVersion']} "
          f"| [{c['archive']}](charts/{c['archive']}) | `{c['sha256'][:16]}` |")
    w("")
    w("To inspect or install a chart, use a `helm` binary of a tier (`make build TIERS=combined`):")
    w("")
    w("```bash")
    w("export HELM_EXPERIMENTAL_CHART_V3=1")
    w("helm=.bin/helm-combined")
    w(f"$helm show all runs/{run.name}/charts/{example['archive']}")
    w(f"$helm install r runs/{run.name}/charts/{example['archive']} --wait=ordered -n demo --create-namespace")
    w("# or from the published chart repository")
    w(f"$helm repo add hip0025-{run.name} {SITE_URL}{run.name}/charts")
    w(f"$helm install r hip0025-{run.name}/{example['name']} --wait=ordered -n demo --create-namespace")
    w("```")
    w("")


def _obs_lines(value) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value] or ["(none)"]
    if isinstance(value, dict):
        return [f"{k}: {v}" for k, v in value.items()]
    return str(value).splitlines() or [""]


def _one_line(text: str) -> str:
    return " ".join(str(text).split())[:400]
