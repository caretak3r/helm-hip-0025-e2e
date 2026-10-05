# Wiring patches (test only)

Upstream Helm cannot install a chart-v3 release yet. At the commit that the three pull requests start from
(`d31cd6992`), and on `main` today:

- `helm install` and `helm upgrade` stop with `invalid chart apiVersion` for a chart that is not v2
  (`pkg/action/install.go`, `pkg/action/upgrade.go`).
- `helm rollback` and `helm uninstall` read only release/v1 records.
- `helm lint` accepts only `apiVersion` `v1` and `v2`, and `helm template` stops with `invalid chart apiVersion`.

HIP-0025 applies only to chart v3, so the pull requests put their code in the chart-v3 packages
(`internal/chart/v3`, `internal/release/v2`, `pkg/kube`). Upstream tracks chart-v3 support in the actions in
[helm/helm#31738](https://github.com/helm/helm/issues/31738).

The patches in this directory connect the `helm` commands to that code, so that a black-box test can run
`helm install` with a chart v3. They are not part of a pull request, and they are not proposed for Helm.

## The patches

| Patch | Applied to | Content |
|---|---|---|
| `0001-base-chart-v3-lifecycle.patch` | every tier | A plain chart-v3 lifecycle: release/v2 storage in `action.Configuration`; install, upgrade, rollback and uninstall for chart v3 that apply everything at once and wait like a chart v2; hooks; `--rollback-on-failure`; `template`, `lint`, `get` and `status` for chart v3. `pkg/action/wire_v3.go` defines the seams that the next two patches use. |
| `0002-ordered-overlay.patch` | PR1, PR2, combined | `pkg/action/wire_ordered_v3.go` (212 lines). It sends `--wait=ordered` installs and upgrades to the sequencing code of PR1 and stores the plan on the release. It makes rollback follow the plan of the target revision, and uninstall delete in reverse order when the release was installed sequenced. |
| `0003-readiness-overlay.patch` | PR3, combined | `pkg/action/wire_readiness_v3.go` (46 lines). It gives the `helm.sh/readiness-*` annotations of the resources to each chart-v3 wait, for a plain `--wait` and for each batch of `--wait=ordered`. |

Each patch is the output of `git format-patch` for one commit on top of the upstream commit `d31cd6992`. `make run`
and `make build` apply them with `git am -3`.

## What the patches do not do

The patches do not decide the order of resources or the readiness of a resource:

- The order comes from `sequence.Build` and `sequence.RecoverPlan` (PR1), and the resource groups of PR2 in it.
  `wire_ordered_v3.go` calls these functions and gives the plan to the executor of PR1 (`sequencedDeployment`).
- The readiness comes from `kube.CustomReadinessEligibleResources` and `kube.WithCustomReadiness` (PR3).
  `wire_readiness_v3.go` calls these two functions only.
- Without an overlay, a chart-v3 operation applies everything at once and waits like a chart v2.

To examine this, read `wire_ordered_v3.go` in `0002-ordered-overlay.patch` and `wire_readiness_v3.go` in
`0003-readiness-overlay.patch`. Each file is short.

## The combined tier

The combined tier merges PR3 into PR2 (PR2 contains PR1). Two overlaps need a mechanical fix, which
`scripts/resolve-combined.sh` does:

1. `internal/chart/v3/lint/lint.go`: each pull request registers one lint rule. The fix keeps both.
2. PR1 and PR3 each define the same unexported function `isHookManifest` in `internal/chart/v3/lint/rules`. The fix
   keeps the copy of PR1. The pull request that merges second must make the same change.

Any other conflict stops the build.
