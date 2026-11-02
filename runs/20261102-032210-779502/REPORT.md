# HIP-0025 end-to-end report · 20261102-032210-779502

**Run status: PASS**


| Tier | Expected tests | Selected tests | Executed/recorded tests |
|---|---|---|---|
| PR1 | 49 | 49 | 49 |
| PR2 | 49 | 49 | 49 |
| PR3 | 49 | 49 | 49 |
| Combined | 49 | 49 | 49 |

Each tier is a `helm` binary built from the pull request commits in `tiers.yaml`. The tests install the charts in `charts/` with this binary on the kind cluster `hip0025-e2e` (Kubernetes v1.37.0, node image `kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5`). Every ordering fact and every readiness fact below comes from the kube-apiserver audit log: one clock, microsecond timestamps. The requirement catalog is `requirements.yaml`.

The run keeps the charts that the tests read as a Helm chart repository: see [Charts](#charts).

Upstream Helm cannot install chart-v3 releases yet. For this reason every tier also contains the test-only patches in `wiring/`. The patches connect the `helm` commands to the code of each PR. They do not decide the order or the readiness of resources.

Harness commit `365b51cbcbfe` · started 2026-11-02T03:22:10Z · finished 2026-11-02T03:31:13Z · Go go1.27.3 · darwin/arm64

## Verdict per PR

| Tier | Built from | HIP requirements graded | Result | Go unit tests (the PR's own) |
|---|---|---|---|---|
| **PR1 · subchart sequencing** | `feat/hip-0025-v3-subcharts` @ `588ef3bf8` · wiring base, ordered · tree `043b9268d` · `v4.3+gc1724d7` | 16 (owned by this PR) | 15 met, 1 deviation (documented) | 10/10 packages pass; 1 compile only (no tests) |
| **PR2 · resource-group sequencing (stacked on PR1)** | `feat/hip-0025-v3-resource-groups` @ `d655709ee` · wiring base, ordered, template · tree `33a432001` · `v4.3+g49929e2` | 9 (owned by this PR) | 9 met | 4/4 packages pass; 1 compile only (no tests) |
| **PR3 · custom readiness** | `feat/hip-0025-v3-readiness` @ `82aba7eee` · wiring base, readiness · tree `5f87bd657` · `v4.3+gc7b03d1` | 8 (owned by this PR) | 7 met, 1 met (extension) | 3/3 packages pass |
| **All three PRs merged** | `feat/hip-0025-v3-resource-groups` @ `d655709ee`, `feat/hip-0025-v3-readiness` @ `82aba7eee` · wiring base, ordered, readiness, template · tree `05d84d78e` · `v4.3+g7b8d5f1` | 32 (all) | 30 met, 1 met (extension), 1 deviation (documented) | n/a (merge tier) |

## Requirement matrix

`✓` pass · `✗` fail · `○` not implemented (expected) · `—` not in this tier · **bold** = the owning PR's tier

| Req | HIP-0025 requirement | Owner | Status | PR1 | PR2 | PR3 | Combined |
|---|---|---|---|---|---|---|---|
| [R01](#r01) | --wait=ordered turns sequencing on; default applies everything at once | PR1 | implemented | **✓ PASS** | ✓ PASS | — N/A | ✓ PASS |
| [R02](#r02) | The release records whether sequencing was used | PR1 | implemented | **✓ PASS** | ✓ PASS | — N/A | ✓ PASS |
| [R03](#r03) | Subchart order from dependencies[].depends-on, by name or alias | PR1 | implemented | **✓ PASS** | ✓ PASS | — N/A | ✓ PASS |
| [R04](#r04) | Parent waits for subcharts listed in helm.sh/depends-on/subcharts | PR1 | implemented | **✓ PASS** | ✓ PASS | — N/A | ✓ PASS |
| [R05](#r05) | Subcharts with no dependency between them deploy together | PR1 | implemented | **✓ PASS** | ✓ PASS | — N/A | ✓ PASS |
| [R06](#r06) | A subchart is fully deployed and ready before its dependents begin | PR1 | implemented | **✓ PASS** | ✓ PASS | — N/A | ✓ PASS |
| [R07](#r07) | Circular dependencies are detected and reported | PR1 | implemented | **✓ PASS** | ✓ PASS | — N/A | ✓ PASS |
| [R08](#r08) | A command prints the DAG | PR1 | implemented | **✓ PASS** | ✓ PASS | — N/A | ✓ PASS |
| [R09](#r09) | Upgrades apply in install order | PR1 | implemented | **✓ PASS** | ✓ PASS | — N/A | ✓ PASS |
| [R10](#r10) | Uninstall runs in reverse order | PR1 | implemented | **✓ PASS** | ✓ PASS | — N/A | ✓ PASS |
| [R11](#r11) | Rollback follows the target revision's sequencing; removals go in reverse | PR1 | implemented | **✓ PASS** | ✓ PASS | — N/A | ✓ PASS |
| [R12](#r12) | A readiness failure or timeout fails the install; --rollback-on-failure rolls back | PR1 | implemented | **✓ PASS** | ✓ PASS | — N/A | ✓ PASS |
| [R13](#r13) | Readiness timeout defaults to 1m, is set by --readiness-timeout, and cannot exceed --timeout | PR1 | implemented | **✓ PASS** | ✓ PASS | — N/A | ✓ PASS |
| [R14](#r14) | Hooks are not sequenced; hook-weight still orders them | PR1 | implemented | **✓ PASS** | ✓ PASS | — N/A | ✓ PASS |
| [R15](#r15) | Readiness is checked only for resources something depends on | PR1 | deviation | **✓ PASS** | ✓ PASS | — N/A | ✓ PASS |
| [R16](#r16) | Charts v2 and below behave exactly as before | all | implemented | ✓ PASS | ✓ PASS | ✓ PASS | ✓ PASS |
| [R17](#r17) | A group is applied together and is ready before the next group starts | PR2 | implemented | — N/A | **✓ PASS** | — N/A | ✓ PASS |
| [R18](#r18) | Groups without a mutual dependency deploy in parallel; list order is irrelevant | PR2 | implemented | — N/A | **✓ PASS** | — N/A | ✓ PASS |
| [R19](#r19) | Unsequenced resources deploy last; misconfigured ones warn | PR2 | implemented | — N/A | **✓ PASS** | — N/A | ✓ PASS |
| [R20](#r20) | Group sequencing is sandboxed inside each chart | PR2 | implemented | — N/A | **✓ PASS** | — N/A | ✓ PASS |
| [R21](#r21) | Resource-group cycles are detected and reported | PR2 | implemented | — N/A | **✓ PASS** | — N/A | ✓ PASS |
| [R22](#r22) | Group dependency annotation key helm.sh/depends-on/resource-groups | PR2 | implemented | — N/A | **✓ PASS** | — N/A | ✓ PASS |
| [R23](#r23) | A resource belongs to one resource group only | PR2 | implemented | — N/A | **✓ PASS** | — N/A | ✓ PASS |
| [R24](#r24) | helm template prints deploy order with START/END resource-group delimiters | PR2 | implemented | — N/A | **✓ PASS** | — N/A | ✓ PASS |
| [R25](#r25) | Without annotations, readiness is kstatus | PR3 | implemented | — N/A | — N/A | **✓ PASS** | ✓ PASS |
| [R26](#r26) | helm.sh/readiness-success — any true expression marks the resource ready | PR3 | implemented | — N/A | — N/A | **✓ PASS** | ✓ PASS |
| [R27](#r27) | helm.sh/readiness-failure — any true expression fails it, over success | PR3 | implemented | — N/A | — N/A | **✓ PASS** | ✓ PASS |
| [R28](#r28) | Both annotations are required; one alone falls back to kstatus, warns, and fails lint | PR3 | implemented | — N/A | — N/A | **✓ PASS** | ✓ PASS |
| [R29](#r29) | Expression syntax {jsonpath} op value over .status, ops == != < <= > >= | PR3 | implemented | — N/A | — N/A | **✓ PASS** | ✓ PASS |
| [R30](#r30) | Comparison values are scalars; object comparisons are rejected | PR3 | implemented | — N/A | — N/A | **✓ PASS** | ✓ PASS |
| [R31](#r31) | Custom readiness also applies to a plain --wait | PR3 | extension | — N/A | — N/A | **✓ PASS** | ✓ PASS |
| [R32](#r32) | Custom readiness gates sequencing | Combined | implemented | — N/A | — N/A | — N/A | **✓ PASS** |

## Requirements in detail

### R01
**--wait=ordered turns sequencing on; default applies everything at once** · owner PR1 · status `implemented`

> For Helm CLI, the `--wait=ordered` flag will enable sequencing where resources are applied in groups. [...] By default, resources are all applied at once which is the same behaviour in Chart v2.  
> — HIP-0025, Specification

Note: The HIP also specifies `WaitStrategy=ordered` in the SDK (line 17); the e2e tests reach the SDK field through the CLI flag.

- `test_plain_wait_applies_everything_at_once` — --wait applies all four Deployments together; at least one dependent before dependency ready.  
  PR1 ✓ pass · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_plain_wait_applies_everything_at_once/commands.log">commands</a>, <a href="pr1/test_plain_wait_applies_everything_at_once/audit.jsonl">audit slice</a></summary>

  ```
  apiserver timeline:
    03:27:16.469  apply  Deployment/nginx
    03:27:16.469  apply  Deployment/bar
    03:27:16.469  apply  Deployment/rabbitmq
    03:27:16.469  apply  Deployment/foo
    03:27:19.152  ready  Deployment/nginx
    03:27:19.156  ready  Deployment/rabbitmq
    03:27:19.159  ready  Deployment/bar
    03:27:19.167  ready  Deployment/foo
  apply burst duration (seconds):
    0.000123
  ```
  </details>

### R02
**The release records whether sequencing was used** · owner PR1 · status `implemented`

> Each release will store information of whether sequencing was used or not. This information is used when performing uninstalls and rollbacks.  
> — HIP-0025, Specification

- `test_uninstall_after_plain_install_is_not_sequenced` — A release installed all at once (plain --wait, no stored plan) is uninstalled all at once.  
  PR1 ✓ pass · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_uninstall_after_plain_install_is_not_sequenced/commands.log">commands</a>, <a href="pr1/test_uninstall_after_plain_install_is_not_sequenced/audit.jsonl">audit slice</a></summary>

  ```
  uninstall timeline:
    03:23:33.613  delete Deployment/subchart-a
    03:23:33.613  delete Deployment/parent
    03:23:33.613  delete Deployment/subchart-b
  delete spread:
    0.000s
  ```
  </details>

- `test_release_record_has_plan_when_sequenced` — Ordered install has plan with batches; plain --wait has no plan.  
  PR1 ✓ pass · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_release_record_has_plan_when_sequenced/commands.log">commands</a></summary>

  ```
  plain --wait release plan:
    None
  stored plan batches (chartPath, kind, manifests):
    ('foo/charts/nginx', 'unsequenced', ['foo/charts/nginx/templates/nginx.yaml'])
    ('foo/charts/rabbitmq', 'unsequenced', ['foo/charts/rabbitmq/templates/rabbitmq.yaml'])
    ('foo/charts/bar', 'unsequenced', ['foo/charts/bar/templates/bar.yaml'])
    ('foo', 'unsequenced', ['foo/templates/foo.yaml'])
  ```
  </details>

### R03
**Subchart order from dependencies[].depends-on, by name or alias** · owner PR1 · status `implemented`

> `depends-on`: A new field added to `Chart.yaml` `dependencies` fields that is meant to declare a list of subcharts, by `name` or `alias`, that need to be ready before the subchart in question get installed.  
> — HIP-0025, Additions to Chart.yaml

- `test_subcharts_dag_order_and_gating` — bar waits for nginx+rabbitmq ready; foo waits for bar ready.  
  PR1 ✓ pass · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_subcharts_dag_order_and_gating/commands.log">commands</a>, <a href="pr1/test_subcharts_dag_order_and_gating/audit.jsonl">audit slice</a></summary>

  ```
  apiserver timeline:
    03:27:30.444  apply  Deployment/nginx
    03:27:30.458  apply  Deployment/rabbitmq
    03:27:33.208  ready  Deployment/rabbitmq
    03:27:34.215  ready  Deployment/nginx
    03:27:34.242  apply  Deployment/bar
    03:27:37.225  ready  Deployment/bar
    03:27:37.247  apply  Deployment/foo
    03:27:40.252  ready  Deployment/foo
  ```
  </details>

- `test_subchart_alias_dependency` — zeta with alias z-service; alpha depends on both alias and original name; order respected.  
  PR1 ✓ pass · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_subchart_alias_dependency/commands.log">commands</a>, <a href="pr1/test_subchart_alias_dependency/audit.jsonl">audit slice</a></summary>

  ```
  apiserver timeline:
    03:27:55.677  apply  Deployment/zeta
    03:27:59.339  ready  Deployment/zeta
    03:27:59.374  apply  Deployment/alpha
    03:28:02.394  apply  Deployment/parent
  ```
  </details>

### R04
**Parent waits for subcharts listed in helm.sh/depends-on/subcharts** · owner PR1 · status `implemented`

> `helm.sh/depends-on/subcharts`: An annotation added to `Chart.yaml` to specify chart dependencies—identified by their `name` or `alias`—that must be fully deployed and in a ready state before the current chart resources can be installed.  
> — HIP-0025, Additions to Chart.yaml

- `test_subcharts_dag_order_and_gating` — bar waits for nginx+rabbitmq ready; foo waits for bar ready.  
  PR1 ✓ pass · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_subcharts_dag_order_and_gating/commands.log">commands</a>, <a href="pr1/test_subcharts_dag_order_and_gating/audit.jsonl">audit slice</a></summary>

  ```
  apiserver timeline:
    03:27:30.444  apply  Deployment/nginx
    03:27:30.458  apply  Deployment/rabbitmq
    03:27:33.208  ready  Deployment/rabbitmq
    03:27:34.215  ready  Deployment/nginx
    03:27:34.242  apply  Deployment/bar
    03:27:37.225  ready  Deployment/bar
    03:27:37.247  apply  Deployment/foo
    03:27:40.252  ready  Deployment/foo
  ```
  </details>

### R05
**Subcharts with no dependency between them deploy together** · owner PR1 · status `implemented`

> In this example, Helm will first install and wait for all resources of `nginx` and `rabbitmq` dependencies to be "ready" before attempting to install `bar` resources.  
> — HIP-0025, Chart dependencies example

Note: Read from the example text and diagram (nginx and rabbitmq side by side, installed and then waited on together). The HIP says "at the same time" explicitly only for resource groups (R18). Serializing siblings still satisfies dependency order (R06) but makes an install as slow as the sum of its independent subcharts.

- `test_independent_subcharts_deploy_together` — nginx and rabbitmq (no mutual dependency) applied together before either is ready.  
  PR1 ✓ pass · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_independent_subcharts_deploy_together/commands.log">commands</a>, <a href="pr1/test_independent_subcharts_deploy_together/audit.jsonl">audit slice</a></summary>

  ```
  apiserver timeline:
    03:27:20.481  apply  Deployment/nginx
    03:27:20.496  apply  Deployment/rabbitmq
    03:27:23.163  ready  Deployment/nginx
    03:27:23.167  ready  Deployment/rabbitmq
    03:27:23.210  apply  Deployment/bar
    03:27:26.186  ready  Deployment/bar
    03:27:26.237  apply  Deployment/foo
    03:27:29.197  ready  Deployment/foo
  ```
  </details>

### R06
**A subchart is fully deployed and ready before its dependents begin** · owner PR1 · status `implemented`

> Subcharts are installed in dependency order. Each subchart must be fully deployed and ready before its dependents begin.  
> — HIP-0025, Sequencing Execution Flow

- `test_subcharts_dag_order_and_gating` — bar waits for nginx+rabbitmq ready; foo waits for bar ready.  
  PR1 ✓ pass · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_subcharts_dag_order_and_gating/commands.log">commands</a>, <a href="pr1/test_subcharts_dag_order_and_gating/audit.jsonl">audit slice</a></summary>

  ```
  apiserver timeline:
    03:27:30.444  apply  Deployment/nginx
    03:27:30.458  apply  Deployment/rabbitmq
    03:27:33.208  ready  Deployment/rabbitmq
    03:27:34.215  ready  Deployment/nginx
    03:27:34.242  apply  Deployment/bar
    03:27:37.225  ready  Deployment/bar
    03:27:37.247  apply  Deployment/foo
    03:27:40.252  ready  Deployment/foo
  ```
  </details>

- `test_nested_subcharts_three_levels` — grandchild-a → child-b → parent-z; each level applied after the level below is ready.  
  PR1 ✓ pass · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_nested_subcharts_three_levels/commands.log">commands</a>, <a href="pr1/test_nested_subcharts_three_levels/audit.jsonl">audit slice</a></summary>

  ```
  apiserver timeline:
    03:28:06.739  apply  Deployment/grandchild-a
    03:28:10.390  ready  Deployment/grandchild-a
    03:28:10.423  apply  Deployment/child-b
    03:28:13.400  ready  Deployment/child-b
    03:28:13.422  apply  Deployment/parent-z
  ```
  </details>

### R07
**Circular dependencies are detected and reported** · owner PR1 · status `implemented`

> This approach of building a directed acyclic graph (DAG) is prone to circular dependencies. During the templating phase, Helm will have logic to detect, and report any circular dependencies found in the chart templates.  
> — HIP-0025, Chart dependencies example

- `test_subchart_cycle_detected` — Cycle (a→b, b→a) fails helm install and helm lint; no objects applied.  
  PR1 ✓ pass · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_subchart_cycle_detected/commands.log">commands</a>, <a href="pr1/test_subchart_cycle_detected/audit.jsonl">audit slice</a></summary>

  ```
  install exit code:
    1
  install stderr:
    Error: INSTALLATION FAILED: subchart circular dependency detected in hip-subcharts-cycle: cycle detected among nodes: a, b
  helm apply count:
    0
  lint exit code:
    1
  lint output:
    ==> Linting charts/hip-subcharts-cycle
    [INFO] Chart.yaml: icon is recommended
    [INFO] values.yaml: file does not exist
    [ERROR] /Users/rohit/Documents/helm-hip-0025-e2e/charts/hip-subcharts-cycle: subchart circular dependency detected in hip-subcharts-cycle: cycle detected among nodes: a, b
    
    Error: 1 chart(s) linted, 1 chart(s) failed
  ```
  </details>

### R08
**A command prints the DAG** · owner PR1 · status `implemented`

> Helm will also provide a command to print the DAG for development and troubleshooting purposes.  
> — HIP-0025, Chart dependencies example

- `test_helm_dag_prints_subchart_order` — helm dag prints nginx and rabbitmq before bar.  
  PR1 ✓ pass · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_helm_dag_prints_subchart_order/commands.log">commands</a></summary>

  ```
  helm dag output:
    Chart: foo
      Subchart batches:
        Batch 1: nginx, rabbitmq
        Batch 2: bar
      Unsequenced (deployed last): Deployment/foo
      Chart: foo/charts/nginx
        Subchart batches: (none)
        Unsequenced (deployed last): Deployment/nginx
      Chart: foo/charts/rabbitmq
        Subchart batches: (none)
        Unsequenced (deployed last): Deployment/rabbitmq
      Chart: foo/charts/bar
        Subchart batches: (none)
        Unsequenced (deployed last): Deployment/bar
  subchart batches printed for foo:
    nginx, rabbitmq
    bar
  ```
  </details>

### R09
**Upgrades apply in install order** · owner PR1 · status `implemented`

> A similar process would apply for upgrades. [...] Upgrades would follow the same order as installation.  
> — HIP-0025, Specification

- `test_upgrade_follows_install_order_and_waits_leaf` — Upgrade patches a -> b -> parent, each after the previous is ready again; helm finishes after the leaf is ready.  
  PR1 ✓ pass · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_upgrade_follows_install_order_and_waits_leaf/commands.log">commands</a>, <a href="pr1/test_upgrade_follows_install_order_and_waits_leaf/audit.jsonl">audit slice</a></summary>

  ```
  upgrade timeline:
    03:23:08.478  patch  Deployment/subchart-a
    03:23:11.413  ready  Deployment/subchart-a (new pod)
    03:23:11.466  patch  Deployment/subchart-b
    03:23:14.415  ready  Deployment/subchart-b (new pod)
    03:23:14.454  patch  Deployment/parent
    03:23:17.430  ready  Deployment/parent (new pod)
    03:23:17.524  helm writes release record: deployed
  ```
  </details>

- `test_upgrade_follows_group_order` — Upgrade patches every Deployment; patches follow database/queue -> app, and app's patch comes after both are ready again.  
  PR1 — n/a · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR2): <a href="pr2/test_upgrade_follows_group_order/commands.log">commands</a>, <a href="pr2/test_upgrade_follows_group_order/audit.jsonl">audit slice</a></summary>

  ```
  upgrade timeline:
    03:29:08.713  apply  Deployment/db
    03:29:08.718  apply  Deployment/queue
    03:29:12.611  ready  Deployment/queue
    03:29:12.619  ready  Deployment/db
    03:29:12.747  apply  Deployment/app
    03:29:16.625  ready  Deployment/app
  db patch-marker:
    v2
  queue patch-marker:
    v2
  app patch-marker:
    v2
  db patched:
    03:29:08.713
  queue patched:
    03:29:08.718
  app patched:
    03:29:12.747
  db ready after patch:
    03:29:12.619
  queue ready after patch:
    03:29:12.611
  ```
  </details>

### R10
**Uninstall runs in reverse order** · owner PR1 · status `implemented`

> Uninstalls: Helm would uninstall resources in the reverse order they were installed, as per the sequencing order.  
> — HIP-0025, Sequencing order

- `test_uninstall_reverse_order_for_ordered_install` — Uninstall of a sequenced release deletes in exact reverse: parent -> b -> a, each after the previous is gone.  
  PR1 ✓ pass · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_uninstall_reverse_order_for_ordered_install/commands.log">commands</a>, <a href="pr1/test_uninstall_reverse_order_for_ordered_install/audit.jsonl">audit slice</a></summary>

  ```
  uninstall timeline:
    03:23:28.582  delete Deployment/parent
    03:23:28.693  delete Deployment/subchart-b
    03:23:28.806  delete Deployment/subchart-a
  ```
  </details>

- `test_uninstall_after_plain_install_is_not_sequenced` — A release installed all at once (plain --wait, no stored plan) is uninstalled all at once.  
  PR1 ✓ pass · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_uninstall_after_plain_install_is_not_sequenced/commands.log">commands</a>, <a href="pr1/test_uninstall_after_plain_install_is_not_sequenced/audit.jsonl">audit slice</a></summary>

  ```
  uninstall timeline:
    03:23:33.613  delete Deployment/subchart-a
    03:23:33.613  delete Deployment/parent
    03:23:33.613  delete Deployment/subchart-b
  delete spread:
    0.000s
  ```
  </details>

- `test_uninstall_runs_in_reverse_order` — Uninstall after ordered install deletes app before database and queue (reverse of install order).  
  PR1 — n/a · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR2): <a href="pr2/test_uninstall_runs_in_reverse_order/commands.log">commands</a>, <a href="pr2/test_uninstall_runs_in_reverse_order/audit.jsonl">audit slice</a></summary>

  ```
  uninstall timeline:
    03:29:26.710  delete Deployment/app
    03:29:26.821  delete Deployment/queue
    03:29:26.821  delete Deployment/db
  deletion timestamps:
    app: 03:29:26.710
    queue: 03:29:26.821
    db: 03:29:26.821
  ```
  </details>

### R11
**Rollback follows the target revision's sequencing; removals go in reverse** · owner PR1 · status `implemented`

> Rollbacks: Helm will check from the release object whether the revision being rolled back to, was installed in a sequenced manner. If it was, Helm will respect and enforce this order when installing resources from that revision. When deleting unneeded resources of the revision being rolled back from, the reverse order is followed just like uninstalls.  
> — HIP-0025, Sequencing order

- `test_rollback_follows_target_revision_order` — Rollback to a sequenced revision re-applies it in its order, then removes the extras in reverse (d before c).  
  PR1 ✓ pass · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_rollback_follows_target_revision_order/commands.log">commands</a>, <a href="pr1/test_rollback_follows_target_revision_order/audit.jsonl">audit slice</a></summary>

  ```
  rollback timeline:
    03:24:04.770  patch  Deployment/subchart-a
    03:24:08.578  ready  Deployment/subchart-a
    03:24:08.611  patch  Deployment/subchart-b
    03:24:12.606  ready  Deployment/subchart-b
    03:24:12.658  patch  Deployment/parent
    03:24:16.763  delete Deployment/subchart-d (rev2 only)
    03:24:16.871  delete Deployment/subchart-c (rev2 only)
  plan batches rev1 / rev3:
    rev1: ['hip-lifecycle/charts/a', 'hip-lifecycle/charts/b', 'hip-lifecycle']
    rev3 (rollback): ['hip-lifecycle/charts/a', 'hip-lifecycle/charts/b', 'hip-lifecycle']
  ```
  </details>

### R12
**A readiness failure or timeout fails the install; --rollback-on-failure rolls back** · owner PR1 · status `implemented`

> Installs: [...] If any of the readiness checks fail or timeout, the entire install would fail and the release marked as failed. If `--atomic`, or its SDK equivalent is used, a rollback to the last successful install would take place.  
> — HIP-0025, Sequencing order

Note: Helm v4 renamed --atomic to --rollback-on-failure.

- `test_failure_stops_install_dependent_never_applied` — A dependency that never becomes ready fails the install; its dependent is never applied; the release is failed.  
  PR1 ✓ pass · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_failure_stops_install_dependent_never_applied/commands.log">commands</a>, <a href="pr1/test_failure_stops_install_dependent_never_applied/audit.jsonl">audit slice</a></summary>

  ```
  install:
    exit 1 after 45s: context deadline exceeded
  apiserver timeline:
    03:24:18.339  apply  Deployment/broken
  release status:
    failed
  ```
  </details>

- `test_rollback_on_failure_cleans_up` — --rollback-on-failure: the install fails, then Helm deletes what it applied and leaves no release.  
  PR1 ✓ pass · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_rollback_on_failure_cleans_up/commands.log">commands</a>, <a href="pr1/test_rollback_on_failure_cleans_up/audit.jsonl">audit slice</a></summary>

  ```
  install:
    exit 1: context deadline exceeded
  apiserver timeline:
    03:25:04.653  apply  Deployment/broken
    03:25:49.682  delete Deployment/broken
  releases left in namespace:
    (none)
  ```
  </details>

### R13
**Readiness timeout defaults to 1m, is set by --readiness-timeout, and cannot exceed --timeout** · owner PR1 · status `implemented`

> Helm will wait up to a default of **1 minute** for a resource to either succeed or fail. [...] This timeout can be customized using the `--readiness-timeout` CLI flag [...] However, the specified readiness timeout must not exceed the overall `--timeout` value.  
> — HIP-0025, Readiness

Note: The HIP also specifies the `ReadinessTimeout` field in the SDK (line 208); the e2e tests reach the SDK field through the CLI flag.

- `test_readiness_timeout_per_batch_cap` — --readiness-timeout 10s under --timeout 2m fails the never-ready batch after ~10s, not 1m or 2m.  
  PR1 ✓ pass · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_readiness_timeout_per_batch_cap/commands.log">commands</a></summary>

  ```
  install:
    exit 1 after 10.1s
  error:
    context deadline exceeded
  ```
  </details>

- `test_readiness_timeout_exceeds_timeout_rejected` — --readiness-timeout 3m --timeout 2m: rejected immediately, nothing applied.  
  PR1 ✓ pass · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_readiness_timeout_exceeds_timeout_rejected/commands.log">commands</a>, <a href="pr1/test_readiness_timeout_exceeds_timeout_rejected/audit.jsonl">audit slice</a></summary>

  ```
  error message:
    Error: INSTALLATION FAILED: --readiness-timeout (3m0s) must not exceed --timeout (2m0s)
  applies count:
    0
  ```
  </details>

- `test_default_readiness_timeout_one_minute` — No --readiness-timeout, --timeout 3m: fails after ~60s (default 1m readiness timeout).  
  PR1 ✓ pass · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_default_readiness_timeout_one_minute/commands.log">commands</a></summary>

  ```
  elapsed seconds:
    60.10341
  ```
  </details>

### R14
**Hooks are not sequenced; hook-weight still orders them** · owner PR1 · status `implemented`

> Resources deployed as hooks are not sequenced using changes proposed here. Any sequencing of hooks will still rely on using `"helm.sh/hook-weight"` annotations. Annotations added to resources in hooks will be ignored.  
> — HIP-0025, Abstract

- `test_hooks_not_sequenced_run_by_weight` — Hooks run before chart resources in hook-weight order, outside the plan, despite sequencing annotations.  
  PR1 ✓ pass · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_hooks_not_sequenced_run_by_weight/commands.log">commands</a>, <a href="pr1/test_hooks_not_sequenced_run_by_weight/audit.jsonl">audit slice</a></summary>

  ```
  apiserver timeline:
    03:27:02.996  create Job/hook-weight-minus-5 (pre-install, weight -5)
    03:27:06.190  create Job/hook-weight-5 (pre-install, weight 5)
    03:27:09.225  apply  Deployment/first
    03:27:12.179  apply  Deployment/second
  hook templates:
    hip-lifecycle-hooks/templates/hooks.yaml
  plan manifests:
    hip-lifecycle-hooks/charts/first/templates/deploy.yaml
    hip-lifecycle-hooks/charts/second/templates/deploy.yaml
  hook last_run phases:
    hook-weight-minus-5: Succeeded
    hook-weight-5: Succeeded
  ```
  </details>

### R15
**Readiness is checked only for resources something depends on** · owner PR1 · status `deviation`

> A resources readiness is checked if there is a resource that depends on it as per the sequencing DAG, otherwise the checks are ignored.  
> — HIP-0025, Readiness

Note: Decision D1: the executor also waits on leaf batches, so a successful install means every sequenced resource reached ready. Skipping leaf checks would report success for a release whose last batch never became ready.

- `test_upgrade_follows_install_order_and_waits_leaf` — Upgrade patches a -> b -> parent, each after the previous is ready again; helm finishes after the leaf is ready.  
  PR1 ✓ pass · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_upgrade_follows_install_order_and_waits_leaf/commands.log">commands</a>, <a href="pr1/test_upgrade_follows_install_order_and_waits_leaf/audit.jsonl">audit slice</a></summary>

  ```
  upgrade timeline:
    03:23:08.478  patch  Deployment/subchart-a
    03:23:11.413  ready  Deployment/subchart-a (new pod)
    03:23:11.466  patch  Deployment/subchart-b
    03:23:14.415  ready  Deployment/subchart-b (new pod)
    03:23:14.454  patch  Deployment/parent
    03:23:17.430  ready  Deployment/parent (new pod)
    03:23:17.524  helm writes release record: deployed
  ```
  </details>

### R16
**Charts v2 and below behave exactly as before** · owner all · status `implemented`

> Helm will continue to install/upgrade/uninstall/rollback all resources and dependencies at one go for all charts using `Charts v2` and below.  
> — HIP-0025, Backwards compatibility

- `test_v2_chart_with_plain_wait_applies_in_one_burst` — V2 chart with group annotations: plain --wait applies all at once (max-min < 1s), no sequencing, no plan in release.  
  PR1 ✓ pass · PR2 ✓ pass · PR3 ✓ pass · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_v2_chart_with_plain_wait_applies_in_one_burst/commands.log">commands</a>, <a href="pr1/test_v2_chart_with_plain_wait_applies_in_one_burst/audit.jsonl">audit slice</a></summary>

  ```
  install exit code:
    0
  resource applies:
    ['03:28:19.119', 'ConfigMap/parent-db']
    ['03:28:19.119', 'ConfigMap/r-sub']
    ['03:28:19.122', 'Deployment/parent-app']
  burst duration (seconds):
    0.003025
  release record has plan:
    False
  ```
  </details>

- `test_v2_chart_with_ordered_wait_fails` — V2 chart: --wait=ordered exits non-zero and creates no release.  
  PR1 ✓ pass · PR2 ✓ pass · PR3 ✓ pass · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_v2_chart_with_ordered_wait_fails/commands.log">commands</a></summary>

  ```
  install exit code:
    1
  stderr:
    Error: INSTALLATION FAILED: --wait=ordered requires chart apiVersion v3 (chart "v2-annotated" has apiVersion v2)
  error type:
    v2-rejected
  releases in namespace:
    (none)
  ```
  </details>

- `test_v2_chart_upgrade_rollback_uninstall_succeed` — V2 chart: upgrade, rollback, and uninstall all succeed with plain --wait.  
  PR1 ✓ pass · PR2 ✓ pass · PR3 ✓ pass · Combined ✓ pass
  <details><summary>evidence (PR1): <a href="pr1/test_v2_chart_upgrade_rollback_uninstall_succeed/commands.log">commands</a>, <a href="pr1/test_v2_chart_upgrade_rollback_uninstall_succeed/audit.jsonl">audit slice</a></summary>

  ```
  upgrade revision:
    2
  rollback revision:
    3
  deployments deleted:
    parent-app
  ```
  </details>

### R17
**A group is applied together and is ready before the next group starts** · owner PR2 · status `implemented`

> Resources in each group are deployed together, and Helm waits for all to be ready before continuing to the next group.  
> — HIP-0025, Resource-Group Sequencing

Note: The HIP also states (line 78) that `helm.sh/resource-group` declares the group and any number of resources can belong to a group; the e2e tests reach the annotation through chart manifests.

- `test_groups_follow_the_hip_example` — database and queue deploy together; app starts only after both are ready.  
  PR1 — n/a · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR2): <a href="pr2/test_groups_follow_the_hip_example/commands.log">commands</a>, <a href="pr2/test_groups_follow_the_hip_example/audit.jsonl">audit slice</a></summary>

  ```
  apiserver timeline:
    03:28:19.143  apply  Deployment/queue-processor
    03:28:19.143  apply  Deployment/db-service
    03:28:22.443  ready  Deployment/queue-processor
    03:28:22.448  ready  Deployment/db-service
    03:28:22.573  apply  Deployment/my-app
    03:28:26.460  ready  Deployment/my-app
  ```
  </details>

### R18
**Groups without a mutual dependency deploy in parallel; list order is irrelevant** · owner PR2 · status `implemented`

> Resources in `database` and `queue` resource-groups would be deployed at the same time. They would need to be ready before attempting to deploy `app` resource-group. [...] The order in which they are listed does not affect deployment sequencing.  
> — HIP-0025, Template examples

- `test_groups_follow_the_hip_example` — database and queue deploy together; app starts only after both are ready.  
  PR1 — n/a · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR2): <a href="pr2/test_groups_follow_the_hip_example/commands.log">commands</a>, <a href="pr2/test_groups_follow_the_hip_example/audit.jsonl">audit slice</a></summary>

  ```
  apiserver timeline:
    03:28:19.143  apply  Deployment/queue-processor
    03:28:19.143  apply  Deployment/db-service
    03:28:22.443  ready  Deployment/queue-processor
    03:28:22.448  ready  Deployment/db-service
    03:28:22.573  apply  Deployment/my-app
    03:28:26.460  ready  Deployment/my-app
  ```
  </details>

### R19
**Unsequenced resources deploy last; misconfigured ones warn** · owner PR2 · status `implemented`

> Resources that: lack annotations, depend on non-existent groups, or belong to isolated groups will be deployed after all properly sequenced groups have been processed. If a resource includes sequencing annotations but falls into this unsequenced category due to misconfiguration [...], Helm will emit a warning.  
> — HIP-0025, Unsequenced Resources

- `test_unsequenced_resources_deploy_last_and_warn` — No annotations, a missing dependency, an isolated group: all after app, two warnings.  
  PR1 — n/a · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR2): <a href="pr2/test_unsequenced_resources_deploy_last_and_warn/commands.log">commands</a>, <a href="pr2/test_unsequenced_resources_deploy_last_and_warn/audit.jsonl">audit slice</a></summary>

  ```
  apiserver timeline:
    03:28:31.509  apply  Deployment/my-app
    03:28:34.473  ready  Deployment/my-app
    03:28:34.509  apply  ConfigMap/loose
    03:28:34.509  apply  ConfigMap/orphan
    03:28:34.509  apply  ConfigMap/lonely
  helm warnings:
    level=WARN msg="sequencing: group "orphan" depends-on non-existent group "no-such-group"; moving group to unsequenced batch" chart=hip-groups
    level=WARN msg="sequencing: resource-group "lonely" is isolated (no depends-on edges and no dependents); deploying it in the unsequenced batch after sequenced groups" chart=hip-groups
  ```
  </details>

### R20
**Group sequencing is sandboxed inside each chart** · owner PR2 · status `implemented`

> These annotations are only used for sequencing resources within the same chart. They do not influence or interact with resources across charts or subcharts.  
> — HIP-0025, Sequencing order

- `test_group_sandboxing_parent_and_subchart_use_same_names` — Parent and subchart both define groups 'first' and 'second' with opposite edges; each chart's order holds independently.  
  PR1 — n/a · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR2): <a href="pr2/test_group_sandboxing_parent_and_subchart_use_same_names/commands.log">commands</a>, <a href="pr2/test_group_sandboxing_parent_and_subchart_use_same_names/audit.jsonl">audit slice</a></summary>

  ```
  apiserver timeline:
    03:28:35.743  apply  Deployment/sub-second
    03:28:39.490  ready  Deployment/sub-second
    03:28:39.536  apply  Deployment/sub-first
    03:28:42.499  ready  Deployment/sub-first
    03:28:42.541  apply  Deployment/parent-first
    03:28:45.512  ready  Deployment/parent-first
    03:28:45.547  apply  Deployment/parent-second
    03:28:49.518  ready  Deployment/parent-second
  ```
  </details>

### R21
**Resource-group cycles are detected and reported** · owner PR2 · status `implemented`

> During the templating phase, Helm will have logic to detect, and report any circular dependencies found in the chart templates.  
> — HIP-0025, Chart dependencies example

- `test_group_cycle_detected_and_rejected` — Circular group dependency (a -> b -> c -> a) exits non-zero naming the cycle, nothing applied.  
  PR1 — n/a · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR2): <a href="pr2/test_group_cycle_detected_and_rejected/commands.log">commands</a>, <a href="pr2/test_group_cycle_detected_and_rejected/audit.jsonl">audit slice</a></summary>

  ```
  exit code:
    1
  stderr:
    Error: INSTALLATION FAILED: resource-group circular dependency detected in hip-groups-cycle: cycle detected among nodes: group-a, group-b, group-c
  apiserver applies:
    (none)
  helm lint exit code:
    1
  ```
  </details>

### R22
**Group dependency annotation key helm.sh/depends-on/resource-groups** · owner PR2 · status `implemented`

> `helm.sh/depends-on/resource-groups`: Annotation to declare resource-groups that must exist and in a ready state before this resource can be deployed.  
> — HIP-0025, Additions to templates

Note: The key is used exactly as the HIP spells it. It has two '/' characters, so the API server rejects it; Helm removes it from each object before apply and keeps it in the stored release. A single-slash rename is open for maintainer decision.

- `test_hip_dependency_key_is_removed_before_apply` — The HIP key helm.sh/depends-on/resource-groups orders groups, is kept in the release, and never reaches the API server.  
  PR1 — n/a · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR2): <a href="pr2/test_hip_dependency_key_is_removed_before_apply/commands.log">commands</a>, <a href="pr2/test_hip_dependency_key_is_removed_before_apply/audit.jsonl">audit slice</a></summary>

  ```
  API server on the HIP key:
    The ConfigMap "key-probe" is invalid: metadata.annotations: Invalid value: "helm.sh/depends-on/resource-groups": a valid label key must consist of alphanumeric characters, '-', '_' or '.', and must start and end with an alphanumeric character (e.g. 'MyName',  or 'my.name',  or '123-abc', regex used for validation is '([A-Za-z0-9][-A-Za-z0-9_.]*)?[A-Za-z0-9]') with an optional DNS subdomain prefix and '/' (e.g. 'example.com/MyName')
  my-app annotations on the cluster:
    deployment.kubernetes.io/revision: 1
    helm.sh/resource-group: app
    meta.helm.sh/release-name: r
    meta.helm.sh/release-namespace: e2e-pr2-hip-dependency-key-is-removed-before-apply
  key in the stored release manifest:
    True
  apiserver timeline:
    03:28:52.133  apply  Deployment/queue-processor
    03:28:52.133  apply  Deployment/db-service
    03:28:55.535  ready  Deployment/queue-processor
    03:28:55.538  ready  Deployment/db-service
    03:28:55.574  apply  Deployment/my-app
    03:28:58.545  ready  Deployment/my-app
  ```
  </details>

### R23
**A resource belongs to one resource group only** · owner PR2 · status `implemented`

> A resource can only belong to one group.  
> — HIP-0025, Resource-Group Sequencing

- `test_duplicate_resource_group_assignment_rejected` — Same resource assigned to two groups: install fails with 'assigned to multiple resource groups', nothing applied.  
  PR1 — n/a · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR2): <a href="pr2/test_duplicate_resource_group_assignment_rejected/commands.log">commands</a>, <a href="pr2/test_duplicate_resource_group_assignment_rejected/audit.jsonl">audit slice</a></summary>

  ```
  install exit code:
    1
  error message:
    Error: INSTALLATION FAILED: parsing resource-group annotations for hip-groups-duplicate: resource "apps/v1/Deployment//conflicting-app" assigned to multiple resource groups "group-a" and "group-b"
  ```
  </details>

### R24
**helm template prints deploy order with START/END resource-group delimiters** · owner PR2 · status `implemented`

> `helm template` would print all resources in the order they would be deployed. Groups of resources in a resource-group would be delimited using a `## START resource-group: <chart>/<subchart> <group-name>` comment [...] and `END resource-group: <chart>/<subchart> <group-name>`.  
> — HIP-0025, Sequencing order

Note: The HIP text writes the end marker without `##`, but the example (line 241) uses `## END resource-group: <chart> <group>`. The chart-v3 template path (test wiring patch 0004) reaches the order through sequence.Build and calls the new Plan.TemplateManifest method in pkg/release/v2/sequence; the upstream `helm template` rejects chart v3 with `invalid chart apiVersion`.

- `test_template_prints_delimiters_for_groups` — helm template prints resources in deploy order with ## START/END resource-group delimiters.  
  PR1 — n/a · PR2 ✓ pass · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (PR2): <a href="pr2/test_template_prints_delimiters_for_groups/commands.log">commands</a></summary>

  ```
  helm template output:
    ---
    ## START resource-group: hip-groups database
    # Source: hip-groups/templates/groups.yaml
    # Source: hip-groups/templates/groups.yaml
    # HIP-0025 "Template examples": database and queue have no mutual dependency and
    # deploy together; app waits for both. The dependency list is deliberately in the
    # opposite order to the HIP text ("The order in which they are listed does not
    # affect deployment sequencing").
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: db-service
      annotations:
        helm.sh/resource-group: database
    spec:
      replicas: 1
      selector:
        matchLabels: {app: db-service}
      template:
        metadata:
          labels: {app: db-service}
        spec:
          terminationGracePeriodSeconds: 0
          containers:
            - name: web
              image: nginx:1.27-alpine
              imagePullPolicy: IfNotPresent
              readinessProbe:
                httpGet: {path: /, port: 80}
                initialDelaySeconds: 3
                periodSeconds: 1
    
    
    ## END resource-group: hip-groups database
    ---
    ## START resource-group: hip-groups queue
    # Source: hip-groups/templates/groups.yaml
    # Source: hip-groups/templates/groups.yaml
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: queue-processor
      annotations:
        helm.sh/resource-group: queue
    spec:
      replicas: 1
      selector:
        matchLabels: {app: queue-processor}
      template:
        metadata:
          labels: {app: queue-processor}
        spec:
          terminationGracePeriodSeconds: 0
          containers:
            - name: web
              image: nginx:1.27-alpine
              imagePullPolicy: IfNotPresent
              readinessProbe:
                httpGet: {path: /, port: 80}
                initialDelaySeconds: 3
                periodSeconds: 1
    
    
    ## END resource-group: hip-groups queue
    ---
    ## START resource-group: hip-groups app
    # Source: hip-groups/templates/groups.yaml
    # Source: hip-groups/templates/groups.yaml
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: my-app
      annotations:
        helm.sh/resource-group: app
        helm.sh/depends-on/resource-groups: "[\"queue\",\"database\"]"
    spec:
      replicas: 1
      selector:
        matchLabels: {app: my-app}
      template:
        metadata:
          labels: {app: my-app}
        spec:
          terminationGracePeriodSeconds: 0
          containers:
            - name: web
              image: nginx:1.27-alpine
              imagePullPolicy: IfNotPresent
              readinessProbe:
                httpGet: {path: /, port: 80}
                initialDelaySeconds: 3
                periodSeconds: 1
    
    
    ## END resource-group: hip-groups app
    ---
    # Source: hip-groups/templates/unsequenced.yaml
    # Source: hip-groups/templates/unsequenced.yaml
    # The three "Unsequenced Resources" cases: deployed after every sequenced group.
    apiVersion: v1
    kind: ConfigMap
    metadata:
      name: loose            # lacks annotations
    data: {case: no-annotations}
    
    
    ---
    # Source: hip-groups/templates/unsequenced.yaml
    # Source: hip-groups/templates/unsequenced.yaml
    apiVersion: v1
    kind: ConfigMap
    metadata:
      name: orphan           # depends on a group that does not exist -> warning
      annotations:
        helm.sh/resource-group: orphan
        helm.sh/depends-on/resource-groups: '["no-such-group"]'
    data: {case: missing-dependency}
    
    
    ---
    # Source: hip-groups/templates/unsequenced.yaml
    # Source: hip-groups/templates/unsequenced.yaml
    apiVersion: v1
    kind: ConfigMap
    metadata:
      name: lonely           # isolated group: no edges in or out -> warning
      annotations:
        helm.sh/resource-group: lonely
    data: {case: isolated-group}
  START markers:
    database: 1
    queue: 35
    app: 65
  END markers:
    database: 33
    queue: 63
    app: 94
  ```
  </details>

### R25
**Without annotations, readiness is kstatus** · owner PR3 · status `implemented`

> By default, Helm uses `kstatus` library to assess readiness based on the resource's type and `.status` field.  
> — HIP-0025, Readiness

- `test_deployment_without_annotations_uses_kstatus` — Deployment with no readiness annotations: plain --wait returns after Available.  
  PR1 — n/a · PR2 — n/a · PR3 ✓ pass · Combined ✓ pass
  <details><summary>evidence (PR3): <a href="pr3/test_deployment_without_annotations_uses_kstatus/commands.log">commands</a>, <a href="pr3/test_deployment_without_annotations_uses_kstatus/audit.jsonl">audit slice</a></summary>

  ```
  Deployment ready time:
    03:23:01.379
  install succeeded with kstatus:
    True
  ```
  </details>

### R26
**helm.sh/readiness-success — any true expression marks the resource ready** · owner PR3 · status `implemented`

> `helm.sh/readiness-success`: A list of custom success conditions. If any are true, the resource is marked **ready**.  
> — HIP-0025, Readiness

- `test_success_expressions_mark_ready` — Success list with multiple expressions: install exits only after one becomes true.  
  PR1 — n/a · PR2 — n/a · PR3 ✓ pass · Combined ✓ pass
  <details><summary>evidence (PR3): <a href="pr3/test_success_expressions_mark_ready/commands.log">commands</a>, <a href="pr3/test_success_expressions_mark_ready/audit.jsonl">audit slice</a></summary>

  ```
  Probe count changes:
    ['03:23:06.649', 3]
  apiserver timeline:
    03:23:06.649  status Probe/probe count=3 (test patch)
    03:23:06.653  helm writes release record: deployed
  ```
  </details>

### R27
**helm.sh/readiness-failure — any true expression fails it, over success** · owner PR3 · status `implemented`

> `helm.sh/readiness-failure`: A list of custom failure conditions. If any are true, the resource is marked **failed**, which takes precedence over any success check.  
> — HIP-0025, Readiness

- `test_failure_takes_precedence_over_success` — Success AND failure both true: install fails, error names the Probe.  
  PR1 — n/a · PR2 — n/a · PR3 ✓ pass · Combined ✓ pass
  <details><summary>evidence (PR3): <a href="pr3/test_failure_takes_precedence_over_success/commands.log">commands</a></summary>

  ```
  install exit code:
    1
  error message:
    Error: INSTALLATION FAILED: resource Probe/e2e-pr3-failure-takes-precedence-over-success/probe not ready. status: Failed, message: custom readiness failure condition met
  ```
  </details>

- `test_failure_expression_alone_fails_install` — Only failure expression true: install fails.  
  PR1 — n/a · PR2 — n/a · PR3 ✓ pass · Combined ✓ pass
  <details><summary>evidence (PR3): <a href="pr3/test_failure_expression_alone_fails_install/commands.log">commands</a></summary>

  ```
  install exit code:
    1
  error message snippet:
    Error: INSTALLATION FAILED: resource Probe/e2e-pr3-failure-expression-alone-fails-install/probe not ready. status: Failed, message: custom readiness failure condition met
  ```
  </details>

- `test_failed_probe_plus_pending_waits_for_timeout` — One failed Probe + one pending: helm waits until --timeout, error names both.  
  PR1 — n/a · PR2 — n/a · PR3 ✓ pass · Combined ✓ pass
  <details><summary>evidence (PR3): <a href="pr3/test_failed_probe_plus_pending_waits_for_timeout/commands.log">commands</a></summary>

  ```
  install exit code:
    1
  elapsed seconds:
    30.1
  error message:
    Error: INSTALLATION FAILED: resource Probe/e2e-pr3-failed-probe-plus-pending-waits-for-timeout/probe1 not ready. status: Failed, message: custom readiness failure condition met
    resource Probe/e2e-pr3-failed-probe-plus-pending-waits-for-timeout/probe2 not ready. status: InProgress, message: waiting for custom readiness conditions
    context deadline exceeded
  ```
  </details>

### R28
**Both annotations are required; one alone falls back to kstatus, warns, and fails lint** · owner PR3 · status `implemented`

> Both `helm.sh/readiness-success` and `helm.sh/readiness-failure` must both be provided to override the default readiness logic. If only one is present, Helm will fall back to `kstatus` and emit a warning. Helm will also fail linting when only one of the two is defined.  
> — HIP-0025, Readiness

- `test_only_success_annotation_falls_back_to_kstatus_and_warns` — Only readiness-success annotation: kstatus fallback occurs and helm warns.  
  PR1 — n/a · PR2 — n/a · PR3 ✓ pass · Combined ✓ pass
  <details><summary>evidence (PR3): <a href="pr3/test_only_success_annotation_falls_back_to_kstatus_and_warns/commands.log">commands</a>, <a href="pr3/test_only_success_annotation_falls_back_to_kstatus_and_warns/audit.jsonl">audit slice</a></summary>

  ```
  install:
    exit 0 after 3.1s
  Probe .status.phase changes during install:
    none: never Ready
  helm warnings:
    level=WARN msg="custom readiness annotations must be used together; falling back to default readiness" kind=Probe namespace=e2e-pr3-only-success-annotation-falls-back-to-kstatus-and-warns name=probe successAnnotation=helm.sh/readiness-success failureAnnotation=helm.sh/readiness-failure
  ```
  </details>

- `test_only_success_annotation_fails_helm_lint` — Chart with only readiness-success annotation: helm lint fails.  
  PR1 — n/a · PR2 — n/a · PR3 ✓ pass · Combined ✓ pass
  <details><summary>evidence (PR3): <a href="pr3/test_only_success_annotation_fails_helm_lint/commands.log">commands</a></summary>

  ```
  lint exit code:
    1
  lint output:
    ==> Linting charts/hip-readiness-basic
    [INFO] Chart.yaml: icon is recommended
    [ERROR] hip-readiness-basic/templates/probe.yaml: resource "Probe/probe" has only one of "helm.sh/readiness-success" / "helm.sh/readiness-failure" annotations; both must be present or absent together
    
    Error: 1 chart(s) linted, 1 chart(s) failed
  ```
  </details>

### R29
**Expression syntax {jsonpath} op value over .status, ops == != < <= > >=** · owner PR3 · status `implemented`

> `{<jsonpath_query>} <logical_operator> <value>` [...] `<jsonpath_query>` is a Kubernetes JSONPath query scoped to `.status`. `<logical_operator>` supports: `==`, `!=`, `<`, `<=`, `>`, `>=`. `<value>` is the expected literal for comparison.  
> — HIP-0025, JsonPath syntax

- `test_readiness_operators[==-5-10-10-count-equality number]` — Each operator (==, !=, <, <=, >, >= on numbers; == on strings and booleans) holds the wait until the patch makes it true.  
  PR1 — n/a · PR2 — n/a · PR3 ✓ pass · Combined ✓ pass
  <details><summary>evidence (PR3): <a href="pr3/test_readiness_operators_-5-10-10-count-equality_number_/commands.log">commands</a>, <a href="pr3/test_readiness_operators_-5-10-10-count-equality_number_/audit.jsonl">audit slice</a></summary>

  ```
  equality number operator:
    ==
  count changes:
    ['03:23:49.854', 10]
  install completed:
    True
  apiserver timeline:
    03:23:49.854  status Probe/probe count=10 (test patch)
    03:23:49.857  helm writes release record: deployed
  ```
  </details>

- `test_readiness_operators[!=-5-10-5-count-inequality number]` — Each operator (==, !=, <, <=, >, >= on numbers; == on strings and booleans) holds the wait until the patch makes it true.  
  PR1 — n/a · PR2 — n/a · PR3 ✓ pass · Combined ✓ pass
  <details><summary>evidence (PR3): <a href="pr3/test_readiness_operators_-5-10-5-count-inequality_number_/commands.log">commands</a>, <a href="pr3/test_readiness_operators_-5-10-5-count-inequality_number_/audit.jsonl">audit slice</a></summary>

  ```
  inequality number operator:
    !=
  count changes:
    ['03:23:54.075', 10]
  install completed:
    True
  apiserver timeline:
    03:23:54.075  status Probe/probe count=10 (test patch)
    03:23:54.080  helm writes release record: deployed
  ```
  </details>

- `test_readiness_operators[<-10-4-5-count-less than]` — Each operator (==, !=, <, <=, >, >= on numbers; == on strings and booleans) holds the wait until the patch makes it true.  
  PR1 — n/a · PR2 — n/a · PR3 ✓ pass · Combined ✓ pass
  <details><summary>evidence (PR3): <a href="pr3/test_readiness_operators_-10-4-5-count-less_than_/commands.log">commands</a>, <a href="pr3/test_readiness_operators_-10-4-5-count-less_than_/audit.jsonl">audit slice</a></summary>

  ```
  less than operator:
    <
  count changes:
    ['03:23:58.281', 4]
  install completed:
    True
  apiserver timeline:
    03:23:58.281  status Probe/probe count=4 (test patch)
    03:23:58.284  helm writes release record: deployed
  ```
  </details>

- `test_readiness_operators[<=-10-5-5-count-less or equal]` — Each operator (==, !=, <, <=, >, >= on numbers; == on strings and booleans) holds the wait until the patch makes it true.  
  PR1 — n/a · PR2 — n/a · PR3 ✓ pass · Combined ✓ pass
  <details><summary>evidence (PR3): <a href="pr3/test_readiness_operators_-10-5-5-count-less_or_equal_/commands.log">commands</a>, <a href="pr3/test_readiness_operators_-10-5-5-count-less_or_equal_/audit.jsonl">audit slice</a></summary>

  ```
  less or equal operator:
    <=
  count changes:
    ['03:24:02.468', 5]
  install completed:
    True
  apiserver timeline:
    03:24:02.468  status Probe/probe count=5 (test patch)
    03:24:02.472  helm writes release record: deployed
  ```
  </details>

- `test_readiness_operators[>-5-11-10-count-greater than]` — Each operator (==, !=, <, <=, >, >= on numbers; == on strings and booleans) holds the wait until the patch makes it true.  
  PR1 — n/a · PR2 — n/a · PR3 ✓ pass · Combined ✓ pass
  <details><summary>evidence (PR3): <a href="pr3/test_readiness_operators_-5-11-10-count-greater_than_/commands.log">commands</a>, <a href="pr3/test_readiness_operators_-5-11-10-count-greater_than_/audit.jsonl">audit slice</a></summary>

  ```
  greater than operator:
    >
  count changes:
    ['03:24:06.710', 11]
  install completed:
    True
  apiserver timeline:
    03:24:06.710  status Probe/probe count=11 (test patch)
    03:24:06.716  helm writes release record: deployed
  ```
  </details>

- `test_readiness_operators[>=-5-10-10-count-greater or equal]` — Each operator (==, !=, <, <=, >, >= on numbers; == on strings and booleans) holds the wait until the patch makes it true.  
  PR1 — n/a · PR2 — n/a · PR3 ✓ pass · Combined ✓ pass
  <details><summary>evidence (PR3): <a href="pr3/test_readiness_operators_-5-10-10-count-greater_or_equal_/commands.log">commands</a>, <a href="pr3/test_readiness_operators_-5-10-10-count-greater_or_equal_/audit.jsonl">audit slice</a></summary>

  ```
  greater or equal operator:
    >=
  count changes:
    ['03:24:10.940', 10]
  install completed:
    True
  apiserver timeline:
    03:24:10.940  status Probe/probe count=10 (test patch)
    03:24:10.943  helm writes release record: deployed
  ```
  </details>

- `test_readiness_operators[==-Pending-Ready-Ready-phase-equality string]` — Each operator (==, !=, <, <=, >, >= on numbers; == on strings and booleans) holds the wait until the patch makes it true.  
  PR1 — n/a · PR2 — n/a · PR3 ✓ pass · Combined ✓ pass
  <details><summary>evidence (PR3): <a href="pr3/test_readiness_operators_-Pending-Ready-Ready-phase-equality_string_/commands.log">commands</a>, <a href="pr3/test_readiness_operators_-Pending-Ready-Ready-phase-equality_string_/audit.jsonl">audit slice</a></summary>

  ```
  equality string operator:
    ==
  phase changes:
    ['03:24:15.162', 'Ready']
  install completed:
    True
  apiserver timeline:
    03:24:15.162  status Probe/probe phase=Ready (test patch)
    03:24:15.167  helm writes release record: deployed
  ```
  </details>

- `test_readiness_operators[==-false-true-true-ready-equality boolean]` — Each operator (==, !=, <, <=, >, >= on numbers; == on strings and booleans) holds the wait until the patch makes it true.  
  PR1 — n/a · PR2 — n/a · PR3 ✓ pass · Combined ✓ pass
  <details><summary>evidence (PR3): <a href="pr3/test_readiness_operators_-false-true-true-ready-equality_boolean_/commands.log">commands</a>, <a href="pr3/test_readiness_operators_-false-true-true-ready-equality_boolean_/audit.jsonl">audit slice</a></summary>

  ```
  equality boolean operator:
    ==
  ready changes:
    ['03:24:19.382', True]
  install completed:
    True
  apiserver timeline:
    03:24:19.382  status Probe/probe ready=True (test patch)
    03:24:19.385  helm writes release record: deployed
  ```
  </details>

### R30
**Comparison values are scalars; object comparisons are rejected** · owner PR3 · status `implemented`

> `<value>` is the expected literal for comparison. The value should be a scalor (string, number, boolean). Object comparisons will not be supported.  
> — HIP-0025, JsonPath syntax

- `test_lint_rejects_object_literal_comparison` — helm lint fails when readiness expression compares to an object literal.  
  PR1 — n/a · PR2 — n/a · PR3 ✓ pass · Combined ✓ pass
  <details><summary>evidence (PR3): <a href="pr3/test_lint_rejects_object_literal_comparison/commands.log">commands</a></summary>

  ```
  lint exit code:
    1
  lint output:
    ==> Linting charts/hip-readiness-basic
    [INFO] Chart.yaml: icon is recommended
    [ERROR] hip-readiness-basic/templates/probe.yaml: resource "Probe/probe" has malformed "helm.sh/readiness-success" annotation: expression "{.data} == {\"key\": \"value\"}": object comparisons are not supported
    
    Error: 1 chart(s) linted, 1 chart(s) failed
  ```
  </details>

- `test_install_rejects_object_jsonpath_result` — install --wait fails promptly when JSONPath result is an object, with wrapped error.  
  PR1 — n/a · PR2 — n/a · PR3 ✓ pass · Combined ✓ pass
  <details><summary>evidence (PR3): <a href="pr3/test_install_rejects_object_jsonpath_result/commands.log">commands</a></summary>

  ```
  install exit code:
    1
  elapsed time:
    2.1s
  error message:
    Error: INSTALLATION FAILED: resource Probe/e2e-pr3-install-rejects-object-jsonpath-result/probe not ready. status: Failed, message: custom readiness expression error: evaluating success expression "{.metadata} == {}": JSONPath result is an object or array: object comparisons are not supported
  ```
  </details>

### R31
**Custom readiness also applies to a plain --wait** · owner PR3 · status `extension`

> Not in the HIP.  
> — HIP-0025, (extension)

Note: PR3 ships readiness independently of sequencing, so the annotations are honored by the ordinary watcher wait as well.

- `test_custom_readiness_applies_to_plain_wait` — Probe with custom readiness annotations gates a plain --wait install.  
  PR1 — n/a · PR2 — n/a · PR3 ✓ pass · Combined ✓ pass
  <details><summary>evidence (PR3): <a href="pr3/test_custom_readiness_applies_to_plain_wait/commands.log">commands</a>, <a href="pr3/test_custom_readiness_applies_to_plain_wait/audit.jsonl">audit slice</a></summary>

  ```
  phase changes:
    ['03:24:24.590', 'Ready']
  apiserver timeline:
    03:24:24.590  status Probe/probe phase=Ready (test patch)
    03:24:24.595  helm writes release record: deployed
  ```
  </details>

### R32
**Custom readiness gates sequencing** · owner Combined · status `implemented`

> To enforce sequencing, Helm determines whether resources are "ready" before deploying dependent resources. [...] Chart authors can optionally override this behavior using the following annotations.  
> — HIP-0025, Readiness

- `test_custom_readiness_gates_sequencing` — A Probe gated only by custom readiness holds back the group that depends on it.  
  PR1 — n/a · PR2 — n/a · PR3 — n/a · Combined ✓ pass
  <details><summary>evidence (Combined): <a href="combined/test_custom_readiness_gates_sequencing/commands.log">commands</a>, <a href="combined/test_custom_readiness_gates_sequencing/audit.jsonl">audit slice</a></summary>

  ```
  apiserver timeline:
    03:22:57.844  apply  Probe/gate (group first)
    03:23:02.780  status Probe/gate phase=Ready (test patch)
    03:23:02.796  apply  Deployment/app (group second, depends on first)
  ```
  </details>

## Go unit tests (each PR's own, on the pure PR commit)

**PR1 · subchart sequencing** · `bc232c531..588ef3bf8`

| Package | Scope | Result | Time |
|---|---|---|---|
| `internal/chart/v3` | all tests | [✓ pass](pr1/unit-internal_chart_v3.log) | 1.3s |
| `internal/chart/v3/lint` | all tests | [✓ pass](pr1/unit-internal_chart_v3_lint.log) | 1.3s |
| `internal/chart/v3/lint/rules` | all tests | [✓ pass](pr1/unit-internal_chart_v3_lint_rules.log) | 1.3s |
| `internal/chart/v3/util` | all tests | [✓ pass](pr1/unit-internal_chart_v3_util.log) | 1.3s |
| `internal/release/v2` | all tests | [✓ pass](pr1/unit-internal_release_v2.log) | 1.4s |
| `internal/release/v2/manifest` | all tests (package added by the PR) | [compile only (no tests)](pr1/unit-internal_release_v2_manifest.log) | 0.1s |
| `internal/release/v2/sequence` | all tests (package added by the PR) | [✓ pass](pr1/unit-internal_release_v2_sequence.log) | 1.0s |
| `internal/release/v2/util` | all tests | [✓ pass](pr1/unit-internal_release_v2_util.log) | 1.0s |
| `pkg/action` | all tests | [✓ pass](pr1/unit-pkg_action.log) | 30.9s |
| `pkg/cmd` | 8 test(s) the PR added or changed | [✓ pass](pr1/unit-pkg_cmd.log) | 3.6s |
| `pkg/kube` | all tests | [✓ pass](pr1/unit-pkg_kube.log) | 26.2s |

**PR2 · resource-group sequencing (stacked on PR1)** · `588ef3bf8..d655709ee`

| Package | Scope | Result | Time |
|---|---|---|---|
| `internal/chart/v3/lint/rules` | all tests | [✓ pass](pr2/unit-internal_chart_v3_lint_rules.log) | 1.5s |
| `internal/release/v2/manifest` | all tests | [compile only (no tests)](pr2/unit-internal_release_v2_manifest.log) | 0.1s |
| `internal/release/v2/resourcegroup` | all tests (package added by the PR) | [✓ pass](pr2/unit-internal_release_v2_resourcegroup.log) | 1.2s |
| `internal/release/v2/sequence` | all tests | [✓ pass](pr2/unit-internal_release_v2_sequence.log) | 1.0s |
| `pkg/action` | all tests | [✓ pass](pr2/unit-pkg_action.log) | 31.2s |

**PR3 · custom readiness** · `bc232c531..82aba7eee`

| Package | Scope | Result | Time |
|---|---|---|---|
| `internal/chart/v3/lint` | all tests | [✓ pass](pr3/unit-internal_chart_v3_lint.log) | 2.5s |
| `internal/chart/v3/lint/rules` | all tests | [✓ pass](pr3/unit-internal_chart_v3_lint_rules.log) | 3.3s |
| `pkg/kube` | all tests | [✓ pass](pr3/unit-pkg_kube.log) | 26.6s |

## Charts

[`charts/`](charts/index.yaml) is a Helm chart repository with one archive for each chart directory that the tests read. An archive holds the files that helm loads from the chart directory, byte for byte.

| Chart directory | Chart | Archive | sha256 |
|---|---|---|---|
| `charts/hip-groups` | `hip-groups` 0.1.0, apiVersion v3 | [hip-groups-0.1.0.tgz](charts/hip-groups-0.1.0.tgz) | `bf37c35e80bb2a8c` |
| `charts/hip-groups-cycle` | `hip-groups-cycle` 0.1.0, apiVersion v3 | [hip-groups-cycle-0.1.0.tgz](charts/hip-groups-cycle-0.1.0.tgz) | `df80e6310334f49a` |
| `charts/hip-groups-duplicate` | `hip-groups-duplicate` 0.1.0, apiVersion v3 | [hip-groups-duplicate-0.1.0.tgz](charts/hip-groups-duplicate-0.1.0.tgz) | `e1b3e207300a5d5b` |
| `charts/hip-groups-sandbox` | `hip-groups-sandbox` 0.1.0, apiVersion v3 | [hip-groups-sandbox-0.1.0.tgz](charts/hip-groups-sandbox-0.1.0.tgz) | `55e0f55f660533e4` |
| `charts/hip-groups-upgrade` | `hip-groups-upgrade` 0.1.0, apiVersion v3 | [hip-groups-upgrade-0.1.0.tgz](charts/hip-groups-upgrade-0.1.0.tgz) | `c85ed21623f9786b` |
| `charts/hip-lifecycle` | `hip-lifecycle` 0.1.0, apiVersion v3 | [hip-lifecycle-0.1.0.tgz](charts/hip-lifecycle-0.1.0.tgz) | `a06bfada6ae70d40` |
| `charts/hip-lifecycle-failure` | `hip-lifecycle-failure` 0.1.0, apiVersion v3 | [hip-lifecycle-failure-0.1.0.tgz](charts/hip-lifecycle-failure-0.1.0.tgz) | `81e8152aaa1933a7` |
| `charts/hip-lifecycle-hooks` | `hip-lifecycle-hooks` 0.1.0, apiVersion v3 | [hip-lifecycle-hooks-0.1.0.tgz](charts/hip-lifecycle-hooks-0.1.0.tgz) | `ff795f70d0fc5a7d` |
| `charts/hip-readiness-basic` | `hip-readiness-basic` 0.1.0, apiVersion v3 | [hip-readiness-basic-0.1.0.tgz](charts/hip-readiness-basic-0.1.0.tgz) | `2534a8588e3d9ccf` |
| `charts/hip-readiness-gate` | `hip-readiness-gate` 0.1.0, apiVersion v3 | [hip-readiness-gate-0.1.0.tgz](charts/hip-readiness-gate-0.1.0.tgz) | `2f36f921cbcbf4ea` |
| `charts/hip-subcharts` | `foo` 0.1.0, apiVersion v3 | [foo-0.1.0.tgz](charts/foo-0.1.0.tgz) | `e5cb6705dbea067f` |
| `charts/hip-subcharts-alias` | `hip-subcharts-alias` 0.1.0, apiVersion v3 | [hip-subcharts-alias-0.1.0.tgz](charts/hip-subcharts-alias-0.1.0.tgz) | `2ad3522e71c23a88` |
| `charts/hip-subcharts-cycle` | `hip-subcharts-cycle` 0.1.0, apiVersion v3 | [hip-subcharts-cycle-0.1.0.tgz](charts/hip-subcharts-cycle-0.1.0.tgz) | `3bb3813a3d5898e1` |
| `charts/hip-subcharts-nested` | `parent-z` 0.1.0, apiVersion v3 | [parent-z-0.1.0.tgz](charts/parent-z-0.1.0.tgz) | `81410cb307cfa703` |
| `charts/v2-annotated` | `v2-annotated` 0.1.0, apiVersion v2 | [v2-annotated-0.1.0.tgz](charts/v2-annotated-0.1.0.tgz) | `4c6203de1dff4f32` |

To inspect or install a chart, use a `helm` binary of a tier (`make build TIERS=combined`):

```bash
export HELM_EXPERIMENTAL_CHART_V3=1
helm=.bin/helm-combined
$helm show all runs/20261102-032210-779502/charts/hip-groups-0.1.0.tgz
$helm install r runs/20261102-032210-779502/charts/hip-groups-0.1.0.tgz --wait=ordered -n demo --create-namespace
# or from the published chart repository
$helm repo add hip0025-20261102-032210-779502 https://caretak3r.github.io/helm-hip-0025-e2e/20261102-032210-779502/charts
$helm install r hip0025-20261102-032210-779502/hip-groups --wait=ordered -n demo --create-namespace
```

