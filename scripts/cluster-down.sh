#!/usr/bin/env bash
# Delete the kind cluster that scripts/cluster-up.sh created.
set -euo pipefail

CLUSTER="${HIP0025_CLUSTER:-hip0025-e2e}"
kind delete cluster --name "$CLUSTER"
