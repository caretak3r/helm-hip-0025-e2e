#!/usr/bin/env python3
"""Build one helm binary for each HIP-0025 pull request, test it on kind, keep the evidence.

    make run                       # sources + unit + build + e2e + REPORT.md, all tiers
    make run TIERS=pr1,combined    # a subset of the tiers
    make run ARGS='-k subchart'    # extra pytest arguments

Stages (tiers run in parallel where they are independent):
  sources  fetch the commits pinned in tiers.yaml from GitHub into .work/helm
  unit     each PR's own Go tests on the pure PR commit (no wiring), like CI on the PR
  build    PR commit + wiring patches -> .bin/helm-<tier> (skipped when the inputs did not change)
  e2e      pytest per tier against the kind cluster; evidence in runs/<stamp>/<tier>/
  report   runs/<stamp>/REPORT.md, graded against requirements.yaml
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from paths import BIN, CLUSTER, CONTEXT, HARNESS_URL, ROOT, RUNS, WORK  # noqa: E402

CFG = yaml.safe_load((ROOT / "tiers.yaml").read_text())
TIERS = CFG["tiers"]
SRC = WORK / "helm"  # one git repository holds every pinned commit; each tier is a worktree of it
HARNESS_ID = {
    "GIT_AUTHOR_NAME": "hip0025 e2e", "GIT_AUTHOR_EMAIL": "e2e@hip0025.invalid",
    "GIT_COMMITTER_NAME": "hip0025 e2e", "GIT_COMMITTER_EMAIL": "e2e@hip0025.invalid",
}
# Packages whose full suites need the network or the macOS keychain; only the
# tests that the PR adds or changes run there.
NOISY_PACKAGES = {"pkg/cmd", "pkg/downloader", "pkg/registry", "pkg/repo/v1"}


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def sh(*cmd: str, cwd=None, env=None, check=True) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, cwd=cwd, env={**os.environ, **(env or {})}, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} (in {cwd}) failed:\n{proc.stdout}{proc.stderr}")
    return proc


def git(*args: str, cwd=SRC, env=None, check=True) -> str:
    return sh("git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args,
              cwd=cwd, env={**HARNESS_ID, **(env or {})}, check=check).stdout.strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


# ── sources ───────────────────────────────────────────────────────────────


def has_commit(sha: str) -> bool:
    return sh("git", "cat-file", "-e", f"{sha}^{{commit}}", cwd=SRC, check=False).returncode == 0


def fetch_sources() -> None:
    if not (SRC / ".git").exists():
        SRC.mkdir(parents=True, exist_ok=True)
        git("init", "-q")
    pins = [(CFG["upstream"]["url"], CFG["upstream"]["branch"], CFG["upstream"]["base"])]
    pins += [(CFG["fork"]["url"], s["branch"], s["commit"]) for s in TIERS.values() if "commit" in s]
    for url, branch, sha in pins:
        if has_commit(sha):
            continue
        log(f"fetch   {url} {branch}")
        git("fetch", "-q", "--no-tags", url, f"refs/heads/{branch}", check=False)
        if not has_commit(sha):  # the branch moved on; ask for the pinned commit itself
            git("fetch", "-q", "--no-tags", url, sha, check=False)
        if not has_commit(sha):
            raise RuntimeError(f"{url} has no commit {sha} (branch {branch}); update tiers.yaml")
        git("update-ref", f"refs/pins/{sha}", sha)  # keep the pinned commit after `git gc`


def members(tier: str) -> list[str]:
    return TIERS[tier].get("merge", [tier])


def tier_inputs(tier: str) -> dict:
    spec = TIERS[tier]
    inputs = {
        "commits": {TIERS[m]["branch"]: TIERS[m]["commit"] for m in members(tier)},
        "wiring": [{"name": n, "file": CFG["wiring"][n], "sha256": sha256(ROOT / CFG["wiring"][n])}
                   for n in spec["wiring"]],
    }
    if "resolve" in spec:
        inputs["resolve"] = {"file": spec["resolve"], "sha256": sha256(ROOT / spec["resolve"])}
    return inputs


# ── build ─────────────────────────────────────────────────────────────────


def worktree(name: str, start: str) -> Path:
    path = WORK / "trees" / name
    if not (path / ".git").exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        git("worktree", "prune")
        git("worktree", "add", "-q", "--detach", str(path), start)
    else:
        for op in ("merge", "am", "cherry-pick"):
            git(op, "--abort", cwd=path, check=False)
        git("reset", "-q", "--hard", cwd=path)
        git("clean", "-qfdx", cwd=path)
        git("checkout", "-q", "--detach", start, cwd=path)
    return path


def conflicts(path: Path) -> list[str]:
    return git("diff", "--name-only", "--diff-filter=U", cwd=path, check=False).splitlines()


def assemble(tier: str) -> Path:
    """PR commit(s) + wiring patches. Commit dates are fixed, so the same inputs always
    give the same commit IDs and the same `helm version` string."""
    spec = TIERS[tier]
    heads = [TIERS[m]["commit"] for m in members(tier)]
    date = max(git("show", "-s", "--format=%cI", sha) for sha in heads)
    fixed = {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
    path = worktree(tier, heads[0])
    for member, sha in zip(members(tier)[1:], heads[1:], strict=True):
        git("merge", "-q", "--no-ff", "-m", f"e2e: merge {member}", sha, cwd=path, env=fixed, check=False)
        if "resolve" in spec:
            res = sh("bash", str(ROOT / spec["resolve"]), cwd=path, check=False)
            if res.returncode != 0:
                raise RuntimeError(f"{tier}: {spec['resolve']} failed: {(res.stdout + res.stderr).strip()}")
        if conflicts(path):
            raise RuntimeError(f"{tier}: merging {member} needs a human: {conflicts(path)}")
        if git("rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=path, check=False):
            git("commit", "-q", "--no-edit", cwd=path, env=fixed)
        elif git("diff", "--cached", "--name-only", cwd=path):
            git("commit", "-q", "-m", f"e2e: {spec['resolve']} fixups", cwd=path, env=fixed)
    for name in spec["wiring"]:
        patch = ROOT / CFG["wiring"][name]
        res = sh("git", "-c", "commit.gpgsign=false", "am", "-q", "-3", "--committer-date-is-author-date",
                 str(patch), cwd=path, env=HARNESS_ID, check=False)
        if res.returncode != 0:
            git("am", "--abort", cwd=path, check=False)
            raise RuntimeError(f"{tier}: wiring {name} does not apply: {(res.stdout + res.stderr).strip()}")
    return path


def build(tier: str, force: bool = False) -> dict:
    BIN.mkdir(parents=True, exist_ok=True)
    binary = BIN / f"helm-{tier}"
    stamp_file = BIN / f"helm-{tier}.json"
    inputs = tier_inputs(tier)
    go = sh("go", "env", "GOVERSION").stdout.strip()
    if not force and binary.exists() and stamp_file.exists():
        cached = json.loads(stamp_file.read_text())
        if cached.get("inputs") == inputs and cached.get("go") == go and cached.get("binary_sha256") == sha256(binary):
            return {**cached, "rebuilt": False}
    path = assemble(tier)
    head = git("rev-parse", "HEAD", cwd=path)
    started = time.time()
    sh("go", "build", "-trimpath", "-ldflags",
       f"-X helm.sh/helm/v4/internal/version.gitCommit={head} -X helm.sh/helm/v4/internal/version.gitTreeState=clean",
       "-o", str(binary), "./cmd/helm", cwd=path)
    info = {
        "tier": tier, "inputs": inputs, **inputs, "base": CFG["upstream"]["base"],
        "tree_head": head, "tree": git("rev-parse", "HEAD^{tree}", cwd=path),
        "version": sh(str(binary), "version", "--short").stdout.strip(),
        "binary": rel(binary), "binary_sha256": sha256(binary),
        "go": go, "goos": sh("go", "env", "GOOS").stdout.strip(), "goarch": sh("go", "env", "GOARCH").stdout.strip(),
        "build_seconds": round(time.time() - started, 1),
    }
    stamp_file.write_text(json.dumps(info, indent=2))
    return {**info, "rebuilt": True}


# ── unit ──────────────────────────────────────────────────────────────────


def unit(tier: str, out: Path) -> dict:
    """The PR's own Go tests on the pure PR commit (what a CI run on the PR sees)."""
    spec = TIERS[tier]
    head = spec["commit"]
    base = TIERS[spec["stacked_on"]]["commit"] if "stacked_on" in spec else CFG["upstream"]["base"]
    path = worktree(f"unit-{tier}", head)
    # Hermetic like CI: never read the developer's helm repositories, cache or plugins.
    home = WORK / f"unit-home-{tier}"
    shutil.rmtree(home, ignore_errors=True)
    env = {f"HELM_{kind}_HOME": str(home / kind.lower()) for kind in ("CACHE", "CONFIG", "DATA")}
    changed = git("diff", "--name-only", base, head, "--", "*.go").splitlines()
    packages = sorted({str(Path(f).parent) for f in changed})
    results = []
    for pkg in packages:
        pkg_dir = path / pkg
        if not pkg_dir.is_dir() or not any(f.suffix == ".go" for f in pkg_dir.iterdir()):
            continue  # package deleted by the PR
        new_pkg = not git("ls-tree", "-d", "--name-only", base, "--", pkg)
        names = sorted(set(re.findall(
            r"^(?:\+func |@@ [^@]* @@ func )(Test\w+)\(",
            git("diff", base, head, "--", f"{pkg}/*_test.go"), re.M)))
        if not new_pkg and pkg in NOISY_PACKAGES and not names:
            continue
        args = ["go", "test", "-count=1", f"./{pkg}/"]
        scope = "all tests (package added by the PR)" if new_pkg else "all tests"
        if pkg in NOISY_PACKAGES and not new_pkg:
            args += ["-run", f"^({'|'.join(names)})$"]
            scope = f"{len(names)} test(s) the PR added or changed"
        started = time.time()
        proc = sh(*args, cwd=path, env=env, check=False)
        log_file = out / f"unit-{pkg.replace('/', '_')}.log"
        log_file.write_text(f"$ {' '.join(args)}\n" + proc.stdout + proc.stderr)
        results.append({"package": pkg, "scope": scope, "passed": proc.returncode == 0,
                        "seconds": round(time.time() - started, 1), "log": log_file.name,
                        "summary": _go_summary(proc.stdout + proc.stderr)})
    info = {"tier": tier, "base": base, "head": head, "packages": results,
            "passed": all(r["passed"] for r in results)}
    (out / "unit.json").write_text(json.dumps(info, indent=2))
    return info


def _go_summary(text: str) -> str:
    fails = re.findall(r"^--- FAIL: (\S+)", text, re.M)
    if fails:
        return "FAIL: " + ", ".join(fails[:8])
    tail = [line for line in text.splitlines() if line.startswith(("ok ", "FAIL", "---"))]
    return tail[-1] if tail else text.strip().splitlines()[-1] if text.strip() else ""


# ── cluster + e2e ─────────────────────────────────────────────────────────


def ensure_cluster() -> None:
    sh("bash", str(ROOT / "scripts" / "cluster-up.sh"))


def first_line(*cmd: str) -> str:
    proc = sh(*cmd, check=False)
    return (proc.stdout or proc.stderr).strip().splitlines()[0] if proc.returncode == 0 else "unavailable"


def run_meta(stamp: str, started: str, tiers: list[str], args) -> dict:
    server = json.loads(sh("kubectl", "--context", CONTEXT, "version", "-o", "json").stdout)["serverVersion"]
    node = sh("docker", "inspect", f"{CLUSTER}-control-plane", "--format", "{{.Config.Image}}", check=False)
    status = sh("git", "status", "--porcelain", "--", ".", ":!runs", cwd=ROOT, check=False)
    return {
        "stamp": stamp,
        "started_utc": started,
        "harness": {
            "url": HARNESS_URL,
            "commit": first_line("git", "-C", str(ROOT), "rev-parse", "HEAD"),
            "dirty": bool(status.stdout.strip()) or status.returncode != 0,
        },
        "host": {"os": platform.system().lower(), "arch": platform.machine()},
        "tools": {
            "go": sh("go", "env", "GOVERSION").stdout.strip(),
            "kind": first_line("kind", "version"),
            "kubectl": json.loads(sh("kubectl", "version", "--client", "-o", "json").stdout)["clientVersion"][
                "gitVersion"],
            "docker": first_line("docker", "version", "--format", "{{.Server.Version}}"),
            "python": platform.python_version(),
        },
        "cluster": {"name": CLUSTER, "context": CONTEXT, "node_image": node.stdout.strip() or "unknown",
                    "server_version": server["gitVersion"]},
        "sources": {"upstream": {"url": CFG["upstream"]["url"], "base": CFG["upstream"]["base"]},
                    "fork": {"url": CFG["fork"]["url"]}},
        "tiers": tiers,
        "pytest_args": args.pytest,
    }


def e2e(tier: str, binary: str, out: Path, pytest_args: list[str]) -> int:
    # Paths stay relative to the repository root, so the evidence shows the exact
    # commands that ran and does not contain the paths of this machine.
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "e2e/tests", "--tier", tier, "--helm", binary, "--out", rel(out), "-q",
         *pytest_args],
        cwd=ROOT, capture_output=True, text=True,
    )
    (out / "pytest.log").write_text(proc.stdout + proc.stderr)
    return proc.returncode


# ── orchestration ─────────────────────────────────────────────────────────


def run(tiers: list[str], args) -> Path:
    started = utc_now()
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    log(f"HIP-0025 e2e run {stamp}: tiers {', '.join(tiers)}")
    fetch_sources()
    ensure_cluster()
    out = RUNS / stamp
    for tier in tiers:
        (out / tier).mkdir(parents=True, exist_ok=True)
    for name in ("tiers.yaml", "requirements.yaml"):  # grade the run against the catalog it ran with
        shutil.copy(ROOT / name, out / name)
    meta = run_meta(stamp, started, tiers, args)

    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        unit_jobs = {pool.submit(unit, t, out / t): t for t in tiers if "commit" in TIERS[t] and not args.skip_unit}
        builds = {}
        for tier, fut in {t: pool.submit(build, t, args.rebuild) for t in tiers}.items():
            try:
                builds[tier] = fut.result()
                b = builds[tier]
                log(f"build {tier:<9} {b['version']:<18} {'rebuilt' if b['rebuilt'] else 'cached '} "
                    f"tree {b['tree'][:9]}")
            except Exception as exc:  # a broken tier must not hide the others
                builds[tier] = {"tier": tier, "error": str(exc)}
                log(f"build {tier:<9} FAILED: {str(exc).splitlines()[0]}")
        for tier, b in builds.items():
            record = {k: v for k, v in b.items() if k != "inputs"}
            (out / tier / "build.json").write_text(json.dumps(record, indent=2))

        runnable = [t for t in tiers if "error" not in builds[t]]
        e2e_jobs = {pool.submit(e2e, t, builds[t]["binary"], out / t, args.pytest): t for t in runnable}
        for fut in cf.as_completed(e2e_jobs):
            tier = e2e_jobs[fut]
            res_file = out / tier / "results.json"
            counts: dict[str, int] = {}
            if res_file.exists():
                for test in json.loads(res_file.read_text())["tests"]:
                    counts[test["outcome"]] = counts.get(test["outcome"], 0) + 1
            log(f"e2e   {tier:<9} " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "no results"))
        for fut in cf.as_completed(unit_jobs):
            tier = unit_jobs[fut]
            try:
                u = fut.result()
                log(f"unit  {tier:<9} {'pass' if u['passed'] else 'FAIL'} ({len(u['packages'])} package(s))")
            except Exception as exc:
                (out / tier / "unit.json").write_text(json.dumps({"tier": tier, "error": str(exc)}))
                log(f"unit  {tier:<9} ERROR: {str(exc).splitlines()[0]}")

    import grade  # noqa: PLC0415
    import report  # noqa: PLC0415

    meta["finished_utc"] = utc_now()
    meta["exit_code"] = 0 if grade.all_green(out) else 1
    (out / "run.json").write_text(json.dumps(meta, indent=2) + "\n")
    log(f"report  {rel(report.render(out))}")
    return out


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", nargs="?", default="run", choices=["run", "build", "report"])
    parser.add_argument("--tiers", default=",".join(TIERS), help="comma-separated subset of " + ",".join(TIERS))
    parser.add_argument("--rebuild", action="store_true", help="rebuild binaries even if the inputs did not change")
    parser.add_argument("--skip-unit", action="store_true", help="skip the PRs' Go unit tests")
    parser.add_argument("--run", default=None, help="report: run directory (default: the newest under runs/)")
    argv = sys.argv[1:]
    extra = argv[argv.index("--") + 1:] if "--" in argv else []
    args = parser.parse_args(argv[: argv.index("--")] if "--" in argv else argv)
    args.pytest = extra  # everything after `--` goes to pytest, e.g. `-- -k subchart`
    tiers = [t.strip() for t in args.tiers.split(",") if t.strip()]
    unknown = [t for t in tiers if t not in TIERS]
    if unknown:
        parser.error(f"unknown tier(s): {', '.join(unknown)}")

    if args.command == "build":
        fetch_sources()
        for tier in tiers:
            b = build(tier, args.rebuild)
            log(f"build {tier:<9} {b['version']} {'rebuilt' if b['rebuilt'] else 'cached'} tree {b['tree'][:9]} "
                f"-> {b['binary']}")
        return 0
    if args.command == "report":
        import report  # noqa: PLC0415
        run_dir = Path(args.run) if args.run else max(p for p in RUNS.iterdir() if (p / "run.json").exists())
        log(f"report  {report.render(run_dir)}")
        return 0
    out = run(tiers, args)
    return json.loads((out / "run.json").read_text())["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
