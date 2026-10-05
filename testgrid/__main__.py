"""Build the dashboard from the committed runs.

    uv run python -m testgrid build [--runs runs] [--out site]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import render

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m testgrid", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="render every run under --runs into --out")
    build.add_argument("--runs", type=Path, default=ROOT / "runs", help="directory with one folder per run")
    build.add_argument("--out", type=Path, default=ROOT / "site", help="output directory (replaced)")
    args = parser.parse_args()
    stats = render.build(args.runs, args.out)
    print(f"testgrid: {stats['runs']} run(s), {stats['pages']} pages, {stats['files']} evidence files -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
