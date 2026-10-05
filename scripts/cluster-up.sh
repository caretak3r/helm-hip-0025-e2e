#!/usr/bin/env bash
# Create the kind cluster for the tests, with kube-apiserver audit logging.
#
# The tests read every ordering fact and every readiness fact from the audit
# log. A cluster without a working audit log cannot run the tests. The script is
# safe to run again: it keeps an existing cluster when its audit log works.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLUSTER="${HIP0025_CLUSTER:-hip0025-e2e}"
CONTEXT="kind-${CLUSTER}"
NODE_IMAGE="${HIP0025_NODE_IMAGE:-kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5}"
AUDIT_LOG="$ROOT/.audit/audit.log"
CONFIG="$ROOT/.work/kind-cluster.yaml"

for tool in docker kind kubectl; do
  command -v "$tool" >/dev/null || { echo "cluster-up: $tool is not installed" >&2; exit 1; }
done

# The audit log must grow when the apiserver handles a request that the policy logs.
audit_works() {
  local before after
  before=$(wc -c <"$AUDIT_LOG" 2>/dev/null || echo 0)
  kubectl --context "$CONTEXT" -n default create configmap "audit-check-$$" >/dev/null
  kubectl --context "$CONTEXT" -n default delete configmap "audit-check-$$" >/dev/null
  sleep 1
  after=$(wc -c <"$AUDIT_LOG" 2>/dev/null || echo 0)
  [ "$after" -gt "$before" ]
}

# The images that the charts in charts/ use, and the Probe CRD of the readiness
# tests. The tiers run in parallel, so the cluster gets both before the tests
# start: no test waits for an image download or races to create the CRD.
IMAGES=(nginx:1.27-alpine busybox:1.36)
prepare() {
  for image in "${IMAGES[@]}"; do
    docker exec "${CLUSTER}-control-plane" crictl pull "$image" >/dev/null
  done
  kubectl --context "$CONTEXT" apply -f "$ROOT/crds/probe.yaml" >/dev/null
  kubectl --context "$CONTEXT" wait --for=condition=Established crd/probes.readiness.hip0025.example \
    --timeout=60s >/dev/null
}

if kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
  if kubectl --context "$CONTEXT" get --raw /readyz >/dev/null 2>&1 && audit_works; then
    prepare
    echo "cluster-up: $CONTEXT is ready; audit log ${AUDIT_LOG#"$ROOT"/}"
    exit 0
  fi
  echo "cluster-up: $CLUSTER is not ready or its audit log does not work; creating it again"
  kind delete cluster --name "$CLUSTER"
fi

mkdir -p "$(dirname "$AUDIT_LOG")" "$(dirname "$CONFIG")"
rm -f "$(dirname "$AUDIT_LOG")"/audit*.log
sed "s|@ROOT@|$ROOT|g" "$ROOT/kind/cluster.yaml" >"$CONFIG"
# kind makes the new cluster the current kubectl context. The tests always give
# --context, so keep the context that the user had.
previous_context=$(kubectl config current-context 2>/dev/null || true)
kind create cluster --name "$CLUSTER" --image "$NODE_IMAGE" --config "$CONFIG" --wait 180s
if [ -n "$previous_context" ]; then
  kubectl config use-context "$previous_context" >/dev/null
fi
kubectl --context "$CONTEXT" wait --for=condition=Ready nodes --all --timeout=180s >/dev/null
until kubectl --context "$CONTEXT" -n default get serviceaccount default >/dev/null 2>&1; do sleep 1; done

if ! audit_works; then
  echo "cluster-up: the audit log ${AUDIT_LOG#"$ROOT"/} does not grow; check kind/cluster.yaml" >&2
  exit 1
fi
prepare
echo "cluster-up: $CONTEXT is ready; audit log ${AUDIT_LOG#"$ROOT"/}"
