# HIP-0025 black-box tests

This repository tests the three pull requests that implement
[HIP-0025](https://github.com/helm/community/blob/main/hips/hip-0025.md), the sequencing of Helm resources.
The tests install charts with real `helm` binaries on a kind cluster. Every result comes from the cluster.

**Dashboard:** <https://caretak3r.github.io/helm-hip-0025-e2e/>

| Tier | Code under test | Pull request |
|---|---|---|
| PR1 | Subchart sequencing and `--wait=ordered` | [caretak3r/helm#4](https://github.com/caretak3r/helm/pull/4) |
| PR2 | Resource-group sequencing (contains PR1) | [caretak3r/helm#5](https://github.com/caretak3r/helm/pull/5) |
| PR3 | Custom readiness | [caretak3r/helm#3](https://github.com/caretak3r/helm/pull/3) |
| Combined | PR2 merged with PR3, so all three pull requests | — |

The three pull requests split the umbrella pull request
[helm/helm#32314](https://github.com/helm/helm/pull/32314), as the maintainers asked.

## How a run works

`make run` does these steps:

1. It fetches the commits that `tiers.yaml` pins from github.com/caretak3r/helm and github.com/helm/helm.
2. It runs the Go unit tests of each pull request on the pull request commit, without other changes.
3. For each tier, it applies the patches in `wiring/` and builds a `helm` binary, `.bin/helm-<tier>`.
4. It creates a kind cluster with kube-apiserver audit logging (`scripts/cluster-up.sh`).
5. It packs each chart in `charts/` into `runs/<stamp>/charts/`, a Helm chart repository.
6. It runs the tests in `e2e/tests/` for all tiers at the same time. Each test uses its own namespace.
7. It writes the evidence to `runs/<stamp>/` and grades the run against the HIP requirements in `requirements.yaml`.

Each test runs the real `helm` command and then reads the result from the cluster. The order of the requests and
the readiness of the objects come from the kube-apiserver audit log. Thus all timestamps in the evidence come from
one clock, the clock of the API server.

A test declares the HIP requirements that it proves and the features that it needs. A tier without these features
reports the test as N/A. The `combined` tier has all features, so it runs every test.

### Why each tier contains wiring patches

Upstream Helm cannot install a chart-v3 release yet. For a chart v3, `helm install` and `helm template` stop with
`invalid chart apiVersion`, and `helm lint` accepts only `v1` and `v2`. HIP-0025 applies only to chart v3. Upstream
tracks chart-v3 support in [helm/helm#31738](https://github.com/helm/helm/issues/31738).

For this reason, each tier contains the test-only patches in [`wiring/`](wiring/README.md). The patches add a plain
chart-v3 lifecycle and connect the `helm` commands to the code of each pull request. They do not decide the order
or the readiness of resources. The patches are not part of a pull request.

## Results

The [dashboard](https://caretak3r.github.io/helm-hip-0025-e2e/) shows each run in `runs/`. For each run, it shows:

- the verdict per pull request,
- a grid of requirements × tiers and a grid of tests × tiers,
- before-and-after pairs (the same operation without and with the feature),
- the commands, observations and audit records of each test,
- the charts that the tests read: one page for each chart with all of its files, and the chart archives as a Helm
  chart repository,
- the commits, patch checksums, source tree IDs and binary checksums of each build,
- the Go unit tests of each pull request.

`runs/<stamp>/REPORT.md` contains the same verdicts as Markdown.

### Run 20261008-084220

This run used the harness commit `768299181667`, a new kind cluster (Kubernetes v1.37.0) and new builds. The builds
are byte-identical to the builds of run 20261005-184055. All tiers are green.
[Dashboard page](https://caretak3r.github.io/helm-hip-0025-e2e/20261008-084220/index.html),
[REPORT.md](runs/20261008-084220/REPORT.md),
[charts](https://caretak3r.github.io/helm-hip-0025-e2e/20261008-084220/charts/index.html).

| Tier | Commit | HIP requirements | Tests | Go unit tests |
|---|---|---|---|---|
| PR1 | `c7c762a4c` | 16 graded: 15 met, 1 deviation (R35) | 21 pass, 25 n/a | 11/11 packages pass |
| PR2 | `453cda84c` | 8 graded: 7 met, 1 not implemented (R26) | 28 pass, 1 xfail (R26), 17 n/a | 5/5 packages pass |
| PR3 | `b57469035` | 7 graded: 6 met, 1 extension (R37) | 19 pass, 27 n/a | 3/3 packages pass |
| Combined | PR2 + PR3 | 30 graded: 27 met, 1 extension, 1 deviation, 1 not implemented | 45 pass, 1 xfail (R26) | — |

### Verdicts

| Verdict | Meaning |
|---|---|
| PASS | The tests for the requirement passed on this tier. |
| FAIL | A test for the requirement failed on this tier. |
| XFAIL | No pull request implements the requirement. The test fails, as expected. |
| XPASS | A test that is marked XFAIL passed. The catalog must change. |
| N/A | The tier does not contain the feature. |

A tier of one pull request is graded on the requirements that this pull request owns. The `combined` tier is graded
on all requirements.

### Differences from the HIP

`requirements.yaml` quotes the HIP for each requirement. These entries are not plain "implemented":

| Req | Status | Description |
|---|---|---|
| R35 | deviation | Helm also waits for resources that nothing depends on. Thus a successful install means that every sequenced resource became ready. |
| R26 | not implemented | `helm template` does not print `## START`/`## END` resource-group delimiters. This is deferred to a follow-up pull request. `helm dag` prints the order. |
| R37 | extension | Custom readiness also applies to a plain `--wait`, not only to `--wait=ordered`. |
| R25 | implemented | The annotation key `helm.sh/depends-on/resource-groups` is used as the HIP spells it. The API server rejects a key with two `/` characters, so Helm removes the key before it applies an object. |

## Run the tests yourself

You need:

- Docker. The published run used Docker Engine 29.8 in Docker Desktop on macOS (arm64), with 24 CPUs and 32 GB of memory.
- [kind](https://kind.sigs.k8s.io/) and `kubectl`
- Go 1.26 or later
- [uv](https://docs.astral.sh/uv/)
- `git`, `make` and `bash`

Do these steps:

```bash
git clone https://github.com/caretak3r/helm-hip-0025-e2e
cd helm-hip-0025-e2e
make run            # about 10 minutes; the result is in runs/<stamp>/
make serve          # the dashboard on http://127.0.0.1:8000
make cluster-down   # delete the kind cluster
```

`make run` creates the kind cluster `hip0025-e2e`. It does not change your current `kubectl` context.

| Command | Result |
|---|---|
| `make run TIERS=pr1,combined` | Test only these tiers |
| `make run ARGS='-k groups'` | Give more arguments to pytest |
| `make build` | Build the binaries only |
| `make report RUN=runs/<stamp>` | Write `REPORT.md` again |
| `make site` | Build the dashboard into `site/` |

The build is reproducible. The same commits and patches give the same source tree ID, the same commit IDs and
the same `helm version` string. Compare the `tree` value in `.bin/helm-<tier>.json` with the value in
`runs/<stamp>/<tier>/build.json`.

### Try the feature by hand

These commands show the difference between `--wait` and `--wait=ordered` without the test suite:

```bash
make build TIERS=combined
make cluster
export HELM_EXPERIMENTAL_CHART_V3=1
helm=.bin/helm-combined
ctx=kind-hip0025-e2e

# Before: --wait applies all four Deployments at the same time.
$helm install plain charts/hip-subcharts --wait --kube-context $ctx -n demo-plain --create-namespace
# After: --wait=ordered applies nginx and rabbitmq, then bar, then foo.
# Each step starts after the step before it is ready.
$helm install ordered charts/hip-subcharts --wait=ordered --kube-context $ctx -n demo-ordered --create-namespace

for ns in demo-plain demo-ordered; do
  kubectl --context $ctx get deployments -n $ns --sort-by=.metadata.creationTimestamp \
    -o custom-columns=NAME:.metadata.name,CREATED:.metadata.creationTimestamp
done

# The order that Helm uses
$helm dag charts/hip-subcharts
```

Each Deployment needs about 3 seconds to become ready. The output looks like this:

```text
NAME       CREATED
bar        2026-10-05T18:36:34Z
foo        2026-10-05T18:36:34Z
nginx      2026-10-05T18:36:34Z
rabbitmq   2026-10-05T18:36:34Z
NAME       CREATED
nginx      2026-10-05T18:36:38Z
rabbitmq   2026-10-05T18:36:38Z
bar        2026-10-05T18:36:41Z
foo        2026-10-05T18:36:44Z
```

`charts/README.md` describes the other charts.

### Inspect or install the charts of a run

Each run keeps the charts that its tests read in `runs/<stamp>/charts/`. This folder is a Helm chart repository:
`index.yaml` and one archive for each chart directory. An archive holds the files that helm loads from the chart
directory, byte for byte. On the dashboard, the run page links to a page for each chart with all of its files and
the tests that read it.

The charts use apiVersion v3, so use a `helm` binary of a tier:

```bash
make build TIERS=combined
make cluster
export HELM_EXPERIMENTAL_CHART_V3=1
helm=.bin/helm-combined
ctx=kind-hip0025-e2e
stamp=$(ls runs | tail -n 1)   # the newest run

# From the dashboard
$helm repo add hip0025-$stamp https://caretak3r.github.io/helm-hip-0025-e2e/$stamp/charts
$helm search repo hip0025-$stamp
$helm show all hip0025-$stamp/hip-groups
$helm install r hip0025-$stamp/hip-groups --wait=ordered --kube-context $ctx -n demo-repo --create-namespace

# Or from the archive in this repository
$helm install r runs/$stamp/charts/hip-groups-0.1.0.tgz --wait=ordered --kube-context $ctx -n demo-archive --create-namespace
```

The run does not use `helm package`. The tier binaries stop with `invalid chart apiVersion` for a chart v3, and for
a chart v2 they write `Chart.yaml` again without the `depends-on` key.

## Repository layout

| Path | Content |
|---|---|
| `tiers.yaml` | The pinned commits, the wiring and the features of each tier |
| `requirements.yaml` | The HIP-0025 requirements, with quotes from the HIP |
| `charts/`, `crds/` | The test charts ([charts/README.md](charts/README.md)) and the `Probe` CRD of the readiness tests |
| `e2e/run.py` | The runner: fetch, unit tests, build, cluster tests, report |
| `e2e/tests/`, `e2e/conftest.py`, `e2e/lib/` | The tests, the pytest fixtures and the audit-log timeline |
| `e2e/grade.py`, `e2e/report.py` | The grading and `REPORT.md` |
| `wiring/` | The test-only patches ([wiring/README.md](wiring/README.md)) |
| `kind/`, `scripts/` | The kind cluster, the audit policy and the helper scripts |
| `testgrid/` | The dashboard generator |
| `runs/` | The evidence of each published run, with the charts of the run in `runs/<stamp>/charts/` |
| `.github/workflows/pages.yml` | Builds the dashboard from `runs/` and publishes it on GitHub Pages |

## License

[Apache License 2.0](LICENSE), the same license as Helm. The patches in `wiring/` change Helm source code.
