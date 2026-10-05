#!/usr/bin/env bash
# Combined tier = PR2 (which contains PR1) merged with PR3. Two known, mechanical
# overlaps; anything else is a new conflict for a human.
#   1. internal/chart/v3/lint/lint.go: each PR registers one rule -> keep both.
#   2. internal/chart/v3/lint/rules: PR1 and PR3 each define the identical
#      unexported isHookManifest -> keep PR1's, drop PR3's (whichever PR merges
#      upstream second has to make the same edit).
set -euo pipefail

for f in $(git diff --name-only --diff-filter=U); do
  case "$f" in
    internal/chart/v3/lint/lint.go)
      git show ":2:$f" > "$f.ours"; git show ":1:$f" > "$f.base"; git show ":3:$f" > "$f.theirs"
      git merge-file --union "$f.ours" "$f.base" "$f.theirs"
      mv "$f.ours" "$f"; rm -f "$f.base" "$f.theirs"
      git add "$f" ;;
    *) echo "resolve-combined: unexpected conflict in $f" >&2; exit 3 ;;
  esac
done

rules=internal/chart/v3/lint/rules
if grep -q '^func isHookManifest' "$rules/sequencing.go" 2>/dev/null &&
   grep -q '^func isHookManifest' "$rules/readiness.go" 2>/dev/null; then
  python3 - "$rules/readiness.go" <<'PY'
import re, sys
path = sys.argv[1]
src = open(path).read()
src = re.sub(r"\nfunc isHookManifest\(manifest releaseutil\.Manifest\) bool \{\n.*?\n\}\n", "\n", src, flags=re.S)
body = src.split(")\n", 1)[1] if src.startswith("/*") or "import (" in src else src
if "release." not in body.replace('release "helm.sh/helm/v4/internal/release/v2"', ""):
    src = src.replace('\trelease "helm.sh/helm/v4/internal/release/v2"\n', "")
open(path, "w").write(src)
PY
  gofmt -w "$rules/readiness.go"
  git add "$rules/readiness.go"
fi
