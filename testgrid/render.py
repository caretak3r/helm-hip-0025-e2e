"""Write the static site: HTML pages plus verbatim copies of the evidence.

The output only uses relative links inside the site, so it works from any URL
path (for example GitHub Pages under /<repository>/) and from a local folder.
The same runs always give the same bytes.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup, escape

from . import collect

TEMPLATES = Path(__file__).parent / "templates"
RUN_FILES = ("run.json", "REPORT.md", "tiers.yaml", "requirements.yaml")
INLINE_FILES = ("values.yaml", "lint-values.yaml")
TICKS = re.compile(r"`([^`]+)`")


def _lines(value: list) -> str:
    """One observation list as text: one item per line, pairs joined by two spaces."""
    if not value:
        return "(none)"
    return "\n".join("  ".join(map(str, item)) if isinstance(item, list | tuple) else str(item) for item in value)


def _ticks(text: str) -> Markup:
    """Escape the text, then show `quoted` parts (Markdown inline code) as <code>."""
    return Markup(TICKS.sub(r"<code>\1</code>", str(escape(text))))


def _chart_links(text: str, hrefs: dict[str, str]) -> Markup:
    """Escape a commands log, then link each charts/<dir> argument to the chart."""

    def link(m: re.Match) -> str:
        href = hrefs.get(m[2])
        return f'{m[1]}<a href="{escape(href)}">charts/{m[2]}</a>' if href else m[0]

    return Markup(collect.CHART_REF.sub(link, str(escape(text))))


def _env() -> Environment:
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True, trim_blocks=True, lstrip_blocks=True,
                      undefined=StrictUndefined, keep_trailing_newline=True)
    env.filters["seconds"] = lambda value: f"{value:.1f} s"
    env.filters["size"] = lambda n: f"{n / 1024:.1f} KB" if n >= 1024 else f"{n} B"
    env.filters["lines"] = _lines
    env.filters["ticks"] = _ticks
    env.filters["chartlinks"] = _chart_links
    return env


def _write(env: Environment, template: str, dest: Path, **context) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(env.get_template(template).render(**context))


def _copy_files(src: Path, dst: Path) -> int:
    """Copy the files (not the directories) of src into dst."""
    dst.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in sorted(src.iterdir()):
        if f.is_file():
            shutil.copyfile(f, dst / f.name)
            count += 1
    return count


def _evidence(src: Path) -> dict:
    files = []
    for f in sorted(src.iterdir()):
        if f.is_file():
            entry = {"name": f.name, "bytes": f.stat().st_size, "records": None}
            if f.suffix == ".jsonl":
                with f.open() as fh:
                    entry["records"] = sum(1 for line in fh if line.strip())
            files.append(entry)
    log = src / "commands.log"
    return {
        "files": files,
        "inline": {name: (src / name).read_text() for name in INLINE_FILES if (src / name).exists()},
        "log": log.read_text() if log.exists() else "",
    }


def _others(run: dict, tier: dict, test: dict) -> list[dict]:
    """The same test on the other tiers of the run, linked from a test page."""
    out = []
    for tv in run["tiers"]:
        other = tv["by_name"].get(test["name"])
        if tv["id"] == tier["id"] or other is None:
            continue
        link = f"../../{tv['id']}/{collect.test_dir(other)}/index.html" if collect.ran(other) else None
        out.append({"label": tv["label"], "text": collect.grade.outcome_text(other),
                    "css": collect.OUTCOME_CSS.get(other["outcome"], "na"), "link": link})
    return out


def build(runs_dir: Path, out: Path) -> dict:
    runs = collect.collect_runs(runs_dir)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / ".nojekyll").write_text("")  # serve the files as they are; no Jekyll processing
    shutil.copyfile(TEMPLATES / "style.css", out / "style.css")
    env = _env()
    repo = runs[0]["harness"]["url"] if runs else ""
    pages = files = 0
    for run in runs:
        run_out = out / run["stamp"]
        run_out.mkdir()
        for name in RUN_FILES:
            if (run["dir"] / name).exists():
                shutil.copyfile(run["dir"] / name, run_out / name)
                files += 1
        for tv in run["tiers"]:
            files += _copy_files(run["dir"] / tv["id"], run_out / tv["id"])
        _write(env, "run.html.j2", run_out / "index.html", root="../", repo=repo, run=run)
        pages += 1
        charts = run["charts"]
        if charts["archived"]:  # the run's chart repository: index.yaml, the archives, one page per chart
            files += _copy_files(run["dir"] / "charts", run_out / "charts")
            _write(env, "charts.html.j2", run_out / "charts" / "index.html", root="../../", repo=repo, run=run)
            pages += 1
            for chart in charts["all"]:
                if chart["page"]:
                    _write(env, "chart.html.j2", run_out / chart["page"], root="../../../", repo=repo, run=run,
                           chart=chart)
                    pages += 1
        reqs = {row["id"]: row for row in run["req_rows"]}
        for tv, test in run["pages"]:
            src = run["dir"] / tv["id"] / collect.test_dir(test)
            dst = run_out / tv["id"] / collect.test_dir(test)
            files += _copy_files(src, dst)
            used = [charts["by_dir"][name] for name in charts["uses"].get(tv["id"], {}).get(test["name"], [])]
            hrefs = {c["dir"]: f"../../{c['page']}" if c["page"] else c["tree"] for c in used if c["page"] or c["tree"]}
            _write(env, "test.html.j2", dst / "index.html", root="../../../", repo=repo, run=run, tier=tv,
                   test=test, css=collect.OUTCOME_CSS.get(test["outcome"], "na"),
                   outcome=collect.grade.outcome_text(test), evidence=_evidence(src),
                   reqs=[reqs[r] for r in test["reqs"] if r in reqs], others=_others(run, tv, test),
                   charts=used, chart_hrefs=hrefs)
            pages += 1
    _write(env, "index.html.j2", out / "index.html", root="", repo=repo, runs=runs)
    return {"runs": len(runs), "pages": pages + 1, "files": files}
