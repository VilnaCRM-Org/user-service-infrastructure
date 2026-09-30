---
artifact: implementation-readiness
workflow: _bmad/bmm/workflows/3-solutioning/bmad-check-implementation-readiness (Validate mode)
task: workload-wa-hardening
source_baseline: 66776772979956de9c5abdbee7c45641a1b533fa (workload source); bundle parent 1ebbd09
date: 2026-09-30
revision: 4
author: the planning agent that wrote revision 4 (NOT an independent reviewer)
independent_reviewer: none yet for revision 4; round 5 (the last) is requested
status: PENDING independent round-5 review
---

# Implementation readiness

## Verdict

**PENDING. Not PASS.** The author of revision 4 wrote this file. It records
what changed and the repository source each fix was checked against. It does
not grade itself.

- Only an independent reviewer's PASS satisfies the planning gate.
- Revision 4 answers readiness round 4 (FAIL) and records the user's D-4 and
  D-5 clarifications of 2026-09-30.
- Before this file was written, a fresh-context author-side audit
  (`claude-router:audit`, read-only) found 33 more defects. All of them are
  fixed below. A re-check of those fixes was requested but had not returned
  when the bundle was committed. It is not a review.
- Round 5 is the last allowed review. Until it reports PASS, the stage is
  BLOCKED.

## Review history

| Round | Reviewer | Result | Handled in |
| --- | --- | --- | --- |
| 1 | independent `devops-sdlc:fr-nfr-reviewer` | FAIL: 3 blocking, 10 major, minors | revision 2 |
| 2 | independent reviewer | Result not stored in this bundle | — |
| 3 | independent reviewer (relayed by the coordinator) | FAIL: B-1, B-2, M-1…M-13, m-1…m-12 | revision 3 |
| 4 | independent reviewer (relayed by the coordinator) | FAIL: R4-B1…B3, R4-M1…M10, m1…m12 | revision 4 (this file) |
| 5 | independent reviewer | requested, not run (last round) | — |

## User decisions (all explicit, dated 2026-09-30)

`decisions.md` is the source. Every decision is resolved, and none is a
default.

| ID | Decision | Where recorded |
| --- | --- | --- |
| D-1 | IAM auth for Valkey/Redis | `decisions.md:7`; `prd.md:319`; `architecture.md` AD-02 |
| D-2 | TEST risk acceptance; in-container TLS in PROD before gate 2 | `decisions.md:8`; `prd.md:320`, `:189` (FR-19) |
| D-3 | REST API + WAF, VPC link V2 → ALB | `decisions.md:9`; `prd.md:321`, `:208` (FR-28) |
| D-4 | Runtime CMK for secrets, every workload log group and the flow-log bucket (SSE-KMS); logs and delivery principals; separate JWT and 2FA CMKs; the DocumentDB master secret on the AWS key | `decisions.md:10`; `prd.md:322`, `:109` (FR-10), `:185` (FR-15); `architecture.md:413` (AD-15a) |
| D-5 | 90 days for `APP_SECRET` and `OAUTH_ENCRYPTION_KEY`, with forced re-login; `OAUTH_PASSPHRASE` retired by S1.8, not rotated; DocumentDB 7-day managed rotation | `decisions.md:11`; `prd.md:323`, `:104` (FR-05); `epics-stories.md:1254` (S5.15 dropped) |
| D-6 | Two gates; `@Kravalg` approval of the README PR still required | `prd.md:324` |
| D-7 | TEST abandon via a Kravalg-approved manifest and a saved-plan destroy | `decisions.md:13`; `prd.md:325`, `:196` (FR-21), `:197` (FR-22) |

## Round-4 finding → resolution map

Line numbers refer to revision 4. "Source" is the repository file and lines
each fix was checked against, at `1ebbd09`.

| Finding | Resolution | Location | Source checked |
| --- | --- | --- | --- |
| R4-B1 D-4/D-5/D-7 not carried; abandon conditional | Every artifact records dated resolutions, and no "pending", "default" or "only if D-7" remains. TEST abandon is unconditional in FR-21, FR-22, NFR-09, AD-16, S4.2, S4.3, S5.7 and the ordered list. S5.15 is dropped. `decisions.md` is hashed in `run-summary.md`. | `prd.md:104,109,196,197,245,322-325`; `architecture.md:47,445,565`; `epics-stories.md:17,298,258,741,826,1236,1238,1254,1284`; `brief.md:142`; `research.md` §4 | `decisions.md` |
| R4-B2 runner admits only the first apply | FR-35 and AD-24 cover the runner, admission observation, worker, workflow and docs. There is a receipt after every admitted apply (success or failed), plus the export and abandon receipts. The mode → anchor table covers `first`, `resume` (failed or export receipt), `step2`, `rollback-zero`, `policy-update`, recovery and `drift`. The mode comes from the reviewed contract field `workload_operation`. The C-runner chain is S4.4 → S4.5 → S4.11 → S4.12 → S4.13 → S4.14, before S4.6. The reviewed amendment covers README line 127, runner spec lines 37-40, log-health line 57, and test lines 175 and 185. Regression tests are listed. | `prd.md:215`; `architecture.md:720,769,911`; `epics-stories.md:705,879,901,940` | `scripts/poc_workload_runner.py:44-47,53,61,154,170-176`; `scripts/poc_workload_admission.py:150-166,464-475`; `scripts/service_execution_worker.py:5,25-30,90-94,99`; `.github/workflows/self-deploy.yml`; `specs/poc-workload-runner.md:37-40`; `specs/poc/README.md:95,127`; `docs/poc-workload-log-health.md:57`; `tests/unit/test_workload_apply_docs_consistency.py:175,185`; `tests/unit/test_service_execution_worker.py:166` |
| R4-B3 `secretsmanager` endpoint policy cycle | Two deterministic statements: declared names `-??????`, and `secret:rds!cluster-*` with `aws:PrincipalArn` limited to the bootstrap-job and restore-reader roles (both created in S5.1, row 8) plus `aws:PrincipalAccount`. There is no XP-8 value, so the pin is offline. S3.3 tests: reader allowed; execution role, task role and foreign account denied. | `architecture.md:364,932`; `prd.md:187`; `epics-stories.md:510,1233` | `policy/guardrails.py:487-511` |
| R4-M1 no topology owner | AD-25 and S4.10 make one C-topology writer for the topology (both stacks), the secret-history checker, the native integration test, the pins and `recovery/delete-actions.json`. The transition rule keeps S1.1's generators and pins in the pre-hardening branch. | `architecture.md:834,884,910`; `epics-stories.md:645,126` | `scripts/poc_workload_topology.py:21-50,61,142-300,859,1058,1099-1170`; `scripts/poc_workload_secret_result.py:121-135`; `specs/poc-workload-runner.md:79-82,89-98`; `tests/integration/test_poc_first_topology_native.py:101,105`; `pyproject.toml:16-17`; `scripts/poc_provider_runtime.py:56,62` |
| R4-M2/M3 D-4/D-5 scope | FR-10 and FR-15 (SSE-KMS, no SSE-S3 fallback); V-16 STOP; the AD-15a principals; `kms_key_id` on every log group, including the pre-created Container Insights group; the topology | `prd.md:109,185`; `architecture.md:413,1046`; `epics-stories.md:353,258,493,1236` | `pulumi/app/compute.py:213-217` |
| R4-M4 abandon | Only `delete`/`same` ops are allowed, and every `delete` of every type matches the manifest 1:1 (not `find_destructive_steps`). The identity is `GitHubCiRecovery-user-service-infrastructure-test`, with lock-prefix-only object delete, `rds:ModifyDBCluster` on `user-service-infrastructure-test-docdb`, and provider-derived delete sets (V-26). The log buckets are always `retain`. Kravalg approval is enforced by the sole-reviewer environment (S5.21), the in-run approvals API check and the required check (S5.22). The rehearsal runs at steps 18–20, after 14–17, with BI ENI detach and a rebuild variant. | `prd.md:196,197`; `architecture.md:445,464,482,493,546,574,582,592`; `epics-stories.md:741,826,1149,1156,1166,1238,1242,1243` | `scripts/pulumi_ci_guardrails.py:16-30,115-125`; `scripts/poc_registry_plan.py:21,57`; `.github/CODEOWNERS`; `AGENTS.md:157-159`; BI @debd88b `scripts/_github_repository_controls.py:308-319`, `scripts/_github_environment_controls.py:36-49` |
| R4-M5 0-task start and stop | V-23; a create-only one-time start action (A-26); `rollback-zero` = stop or start action plus only the target's `suspendedState` update; the `start_at` window; TEST schedules in the step-2 set; the consumed-action fallback | `prd.md:115,214`; `architecture.md:287,316,701,1053`; `epics-stories.md:375,784` | `research.md:276` (AWS docs, 2026-09-30) |
| R4-M6 V-3 fallback | Three `documentdb_secret_policy` states; update-only `policy-update`; never deleted by an apply mode | `prd.md:106`; `architecture.md:235,1033`; `epics-stories.md:332,784` | — |
| R4-M7 S5.18 split | S5.18a (grants, no VPC) at row 42; S5.18b after XP-8 (step 5; detach at step 18, re-attach at step 20) | `epics-stories.md:1239,1240`; `architecture.md:908`; `prd.md:367` | — |
| R4-M8 per-key table | AD-15a: the execution role has `kms:Decrypt` with `kms:ViaService` secretsmanager and a `SecretARN` context. The logs part is checked live by V-25, with a reviewed fallback row. There is an exercise-role S3 row. | `architecture.md:413,1055`; `epics-stories.md:1236` | `research.md:278` |
| R4-M9 managed-password and restore grants | A-27 (aws-knowledge docs, 2026-09-30: RDS and Aurora document `CreateSecret`, `TagResource` and `kms:DescribeKey`; the DocumentDB page is silent) is checked by V-21 and V-22. The grants are in S5.2, S5.5 and S5.18a. | `architecture.md:80,81,994,1051,1052`; `epics-stories.md:1234,1239` | `research.md:277` |
| R4-M10 runner prerequisites | XP-9…XP-13 are gate-1 checks; XP-14 (PROD registry) is a gate-2 check | `prd.md:211,391,409`; `architecture.md:671`; `epics-stories.md:1023` | `specs/poc/README.md:107-128`; `scripts/poc_workload_runner.py:170-176`; `specs/poc-workload-runner.md:110-113` |
| m1 PROD-shaped preview | S3.5-A is at row 25; P-1 is the PROD `plan` under gate 2a | `epics-stories.md:584,1214`; `prd.md:189` | — |
| m2 state scan; FR-14 | Steps 4a and 7a; FR-14 live evidence is the observed scheduled scale-down | `epics-stories.md:1063`; `prd.md:237` | — |
| m3 allow-lists per event type | PRD §3.2a (`PutResourcePolicy`, `RotateSecret`, `DeleteResourcePolicy`, `DeleteSecret`, `RestoreSecret`, managed secrets); S2.5 has P/N cases per row | `prd.md:155`; `architecture.md:258`; `epics-stories.md:432` | — |
| m4 first-deployment rollback | `rollback-zero` until an accepted release exists | `prd.md:210`; `architecture.md:649` | — |
| m5 V-15 in S5.7 | Cited | `epics-stories.md:1238`; `architecture.md:1045` | — |
| m6 simulator identity | The preview role, with an S5.17 grant on the exact role ARNs; other live actions use the S5.23 exercise role | `prd.md:207`; `epics-stories.md:1045,1235,1244` | — |
| m7 KMS read timing | The preview and drift KMS read is in S5.4 on the exact key ARNs | `prd.md:213`; `epics-stories.md:1235,1236` | — |
| m8 XP-8 dependents | Exactly three BI dependents, plus the USI contract PR (step 5b) | `prd.md:367`; `epics-stories.md:1073` | — |
| m9 VpcEndpoint pin identity | `aws:ec2/vpcEndpoint:VpcEndpoint|<serviceName>|<tags.Name>`, fail-closed, with one digest per endpoint per environment | `architecture.md:376`; `epics-stories.md:523` | `policy/reviewed_iam.py:29-42,108-132`; `policy/vilnacrm_guardrails.yaml` |
| m10 run-summary | Parent `1ebbd09` and the `decisions.md` hash are recorded | `run-summary.md` | — |
| m11 Kravalg-only approvals | S5.21 (sole reviewer, `prevent_self_review`, no bypass); read-only check at step 1 | `epics-stories.md:1242,1035` | BI `scripts/_github_repository_controls.py:308-319`; `AGENTS.md:157-159` |
| m12 egress inventory | `docs/poc-egress-inventory.md` comes first in S3.4; STOP at step 12 | `prd.md:188`; `epics-stories.md:552,1117` | — |

**Classifier gap found while checking source.** `CRITICAL_TYPE_PATTERNS`
(`scripts/pulumi_ci_guardrails.py:17-30`) has no `aws:docdb/` and no
`aws:s3/bucketV2:` pattern. S1.6 adds both (`epics-stories.md:314`;
`research.md:326`).

**Author-side audit additions (33 defects, all fixed).**

- The admission, worker and workflow scope of the runner lifecycle.
- Resume from a failed step 1, and per-apply anchors.
- The rebuild variant with retained secrets.
- The S1.1 pins kept until S4.10.
- The ordered-list forward dependencies, removed by the new C-contract
  order S4.10 → S4.11 → S4.2 → S4.9 → S4.3 → S4.12 … S4.15.
- The PROD topology (S4.10) and the PROD registry (XP-14).
- The AD-04 `central` fields.
- The lock-prefix delete and the real resource names.
- The provider-derived delete sets (V-26).
- The TEST schedule vs `rollback-zero` conflict (`suspendedState`).
- Named identities for every live action (S5.23, S4.16).
- A STOP rule on every S4.6 step.
- The receipt validator and the two-gate test (S4.15), with gate 2a/2b and
  P-1.
- The V-23(c) consumed-action handling.
- A single owner for `prod-recovery` (S5.19).
- The Container Insights log group.
- The `policy-update` scope.
- The apply-role delete grants removed.
- The §3.2a and S2.5 coverage.
- The research wording, the soak window, the `start_at` window and the step
  5b contract PR.

## Unresolved external prerequisites

These are recorded gates, not planning defects.

- **XP-1.** Central roles: the source (`d41c019`) is not in the local
  bootstrap clone.
- **XP-2 / XP-3.** The BI capability, KMS, function, restore, recovery,
  exercise and environment stories.
- **XP-4.** user-service work.
- **XP-5.** The AGI front door.
- **XP-6.** The SNS subscription endpoint.
- **XP-7.** `.claude/devops-sdlc.json` is absent, so `validate-profile`
  returned BLOCKED.
- **XP-8.** The post-step-1 metadata.
- **XP-9 … XP-13.** The existing runner prerequisites.
- **XP-14.** The PROD registry phase (outside this plan; gate 2).

## Remaining user decisions

None are open for planning. Three conditional decisions arise only if a live
check fails:

| ID | Trigger | State |
| --- | --- | --- |
| Conditional: V-1 fails | step-2 health (step 7) | a new decision would be needed (an app DB user with a rotated password) |
| Conditional: V-5 requires a `default` password | step 1 | a new decision would be needed (no Pulumi-generated password allowed) |
| Conditional: V-16 fails with SSE-KMS | step 12 | SSE-S3 would contradict D-4, so a new decision would be needed |

## Skill applicability (devops-sdlc 14)

**Applicable and addressed:**

- security-iam (AD-15a, S5.x)
- state-migration (AD-16, AD-25)
- observability (§3.2a)
- cost-optimization
- backup-recovery (S4.8, S5.18a/b)
- delivery-and-rollback (AD-19, AD-24)
- drift-management (FR-32, S1.11, S4.13)
- python-pulumi
- infrastructure-quality
- evidence-and-coverage
- environment-lifecycle (gate 2a/2b, S4.14)
- incident-response (runbooks in S2.4)
- bmad-autonomous-planning

**SKIPPED:** terraform-terraspace, because the engine is Pulumi.
