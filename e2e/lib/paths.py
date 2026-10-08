"""Locations and cluster identity shared by the runner, the fixtures and the dashboard."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHARTS = ROOT / "charts"
CRDS = ROOT / "crds"
RUNS = ROOT / "runs"
WORK = ROOT / ".work"
BIN = ROOT / ".bin"
# Where this repository is published; run.json links the harness commit there.
HARNESS_URL = os.environ.get("HIP0025_HARNESS_URL", "https://github.com/caretak3r/helm-hip-0025-e2e")
# Where the dashboard is published; the commands that use a run's chart repository point there.
SITE_URL = os.environ.get("HIP0025_SITE_URL", "https://caretak3r.github.io/helm-hip-0025-e2e/")

CLUSTER = os.environ.get("HIP0025_CLUSTER", "hip0025-e2e")
CONTEXT = f"kind-{CLUSTER}"
AUDIT_LOG = Path(os.environ.get("HIP0025_AUDIT_LOG", ROOT / ".audit" / "audit.log"))
