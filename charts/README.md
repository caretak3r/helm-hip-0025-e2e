# Test charts

All charts except `v2-annotated` use `apiVersion: v3`, because HIP-0025 applies only to chart v3. Most charts copy
an example from the HIP. The workloads use `nginx:1.27-alpine` with a readiness probe that passes after a delay
(`readyDelay`, 3 seconds by default). Thus a test can see that Helm waited: if a resource becomes ready
immediately, the order of the requests does not show a wait.

| Chart | Content | Requirements | Tests |
|---|---|---|---|
| `hip-subcharts` | The "Chart dependencies" example of the HIP: `nginx` and `rabbitmq` → `bar` → `foo` (the parent). The parent also has `helm.sh/depends-on/subcharts`. | R01–R05, R07, R15 | `test_plain_wait_applies_everything_at_once`, `test_independent_subcharts_deploy_together`, `test_subcharts_dag_order_and_gating`, `test_release_record_has_plan_when_sequenced`, `test_helm_dag_prints_subchart_order` |
| `hip-subcharts-alias` | `alpha` depends on `zeta` by its alias `z-service` and by its name | R03 | `test_subchart_alias_dependency` |
| `hip-subcharts-nested` | Three levels: `grandchild-a` → `child-b` → the parent | R05 | `test_nested_subcharts_three_levels` |
| `hip-subcharts-cycle` | `a` depends on `b`, and `b` depends on `a` | R06 | `test_subchart_cycle_detected` |
| `hip-lifecycle` | `a` → `b` → the parent. `c` and `d` (`c.enabled`) are added and removed between revisions. | R02, R08–R10, R35 | `test_upgrade_follows_install_order_and_waits_leaf`, `test_uninstall_reverse_order_for_ordered_install`, `test_uninstall_after_plain_install_is_not_sequenced`, `test_rollback_follows_target_revision_order` |
| `hip-lifecycle-failure` | `broken` never becomes ready. `dependent` depends on it. | R11, R12 | `test_failure_stops_install_dependent_never_applied`, `test_rollback_on_failure_cleans_up`, `test_readiness_timeout_per_batch_cap`, `test_readiness_timeout_exceeds_timeout_rejected`, `test_default_readiness_timeout_one_minute` |
| `hip-lifecycle-hooks` | Hooks with `helm.sh/hook-weight`, and sequenced subcharts `first` → `second` | R13 | `test_hooks_not_sequenced_run_by_weight` |
| `hip-groups` | The "Template examples" of the HIP: `database` and `queue` → `app`. Also a resource without annotations, a resource with a missing dependency, and an isolated group. | R20–R22, R25, R26 | `test_groups_follow_the_hip_example`, `test_unsequenced_resources_deploy_last_and_warn`, `test_hip_dependency_key_is_removed_before_apply`, `test_template_prints_delimiters_for_groups` |
| `hip-groups-cycle` | Groups `a` → `b` → `c` → `a` | R24 | `test_group_cycle_detected_and_rejected` |
| `hip-groups-sandbox` | The parent and its subchart both define the groups `first` and `second`, with opposite edges | R23 | `test_group_sandboxing_parent_and_subchart_use_same_names` |
| `hip-groups-upgrade` | Groups for upgrade and uninstall order | R08, R09 | `test_upgrade_follows_group_order`, `test_uninstall_runs_in_reverse_order` |
| `hip-readiness-basic` | A `Probe` (see `crds/probe.yaml`) with `helm.sh/readiness-success` and `helm.sh/readiness-failure` expressions from values, and a Deployment without annotations | R30–R34, R37 | `test_deployment_without_annotations_uses_kstatus`, `test_success_expressions_mark_ready`, `test_failure_takes_precedence_over_success`, `test_failure_expression_alone_fails_install`, `test_failed_probe_plus_pending_waits_for_timeout`, `test_only_success_annotation_falls_back_to_kstatus_and_warns`, `test_only_success_annotation_fails_helm_lint`, `test_readiness_operators`, `test_custom_readiness_applies_to_plain_wait` |
| `hip-readiness-gate` | A `Probe` in group `first` gates a Deployment in group `second` | R36 | `test_custom_readiness_gates_sequencing` |
| `v2-annotated` | A chart v2 with resource-group annotations and a `depends-on` field | R14 | `test_v2_chart_with_plain_wait_applies_in_one_burst`, `test_v2_chart_with_ordered_wait_fails`, `test_v2_chart_upgrade_rollback_uninstall_succeed` |

## The `Probe` resource

`crds/probe.yaml` defines `Probe` (`probes.readiness.hip0025.example`), a custom resource that does nothing. The
readiness tests write its `.status` with `kubectl patch --subresource=status` at known moments. Thus the tests
control exactly when a custom readiness expression becomes true or false. `scripts/cluster-up.sh` installs the CRD.

## Use a chart by hand

Use a `helm` binary that this repository builds (see "Try the feature by hand" in the main README), and set
`HELM_EXPERIMENTAL_CHART_V3=1`:

```bash
export HELM_EXPERIMENTAL_CHART_V3=1
.bin/helm-combined dag charts/hip-groups
.bin/helm-combined install demo charts/hip-groups --wait=ordered --kube-context kind-hip0025-e2e -n demo --create-namespace
```
