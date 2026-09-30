---
artifact: implementation-readiness
workflow: _bmad/bmm/workflows/3-solutioning/bmad-check-implementation-readiness (Validate mode)
task: workload-wa-hardening
source_baseline: 66776772979956de9c5abdbee7c45641a1b533fa (workload source); bundle parent 57f38aa
date: 2026-09-30
revision: 5
author: the planning agent that wrote revision 5 (NOT an independent reviewer)
independent_reviewer: none yet for revision 5
status: PENDING independent review of revision 5
---

# Implementation readiness

## Verdict

**PENDING. Not PASS.** The author of revision 5 wrote this file. It records
what changed and the repository source each fix was checked against. It does
not grade itself.

- Only an independent reviewer's PASS satisfies the planning gate.
- Revision 5 answers independent readiness round 5 (FAIL: 5 major, 18
  minor). Round 5 confirmed every round-4 finding resolved; that map is in
  revision 4 (commit `57f38aa`) and is not repeated here.
- Before commit, a fresh-context author-side audit (`claude-router:audit`,
  read-only) checked these fixes against the source and returned REFUTED.
  It found 7 major and 7 minor items, all fixed in the same commit:
  - receipt copy-out in `service_execution_host.py`;
  - two more rejection sites (topology `_validate_workload_step` and the
    registry capture path);
  - drift/observation jobs racing receipt publication;
  - a scheduled-drift exit code;
  - the `ignore_fields`/`refresh_only_fields` split;
  - step 13 after a cancellation;
  - the step-2 start entry naming and its own PR;
  - `test-preview` approval and the concurrency group;
  - a citation;
  - the FR-11 wording;
  - the PROD cost case;
  - the hardened-branch-only S2.1;
  - the hashes;
  - the registry-phase observation.

  The fixes were not re-audited. That audit is not an independent review.
- Round 5 was recorded as the last allowed review round. Whether another
  independent round runs is for the coordinator and the user to decide.
  Until an independent reviewer reports PASS, the stage stays BLOCKED.

## Review history

| Round | Reviewer | Result | Handled in |
| --- | --- | --- | --- |
| 1 | independent `devops-sdlc:fr-nfr-reviewer` | FAIL: 3 blocking, 10 major, minors | revision 2 |
| 2 | independent reviewer | Result not stored in this bundle | — |
| 3 | independent reviewer (relayed by the coordinator) | FAIL: B-1, B-2, M-1…M-13, m-1…m-12 | revision 3 |
| 4 | independent reviewer (relayed by the coordinator) | FAIL: R4-B1…B3, R4-M1…M10, m1…m12 | revision 4 |
| 5 | independent reviewer (relayed by the coordinator) | FAIL: R5-M1…M5, m1…m18; every round-4 finding confirmed resolved | revision 5 (this file) |

## User decisions (all explicit, dated 2026-09-30)

`decisions.md` is the source and is unchanged in revision 5. Every decision
is resolved, and none is a default: D-1…D-7, and the derived details
D-8…D-13 that the user confirmed the same day. XP-14 (the PROD registry) is
still an open ownership item that blocks gate 2.

Revision 5 adds three **planning targets**, not user decisions. Each is a
STOP for a user decision if a measurement misses it, and the user may change
it: the DocumentDB RPO ≤ 5 min and RTO ≤ 4 h (m16), and the 20% cost
forecast threshold (m17).

## Round-5 finding → resolution map

Line numbers refer to revision 5. "Source" is the repository file and lines
each fix was checked against, at `57f38aa` (the workload source is
unchanged from the baseline).

| Finding | Resolution | Location | Source checked |
| --- | --- | --- | --- |
| R5-M1 FR-32 check in an unexecuted script | The FR-32 check moves to the executed workload path. A `workload-drift` invocation (`preview --refresh --expect-no-changes --json --save-plan`) is registered in `run_pulumi_command.py`, and the runner dispatches it. `validate_drift` in `scripts/poc_workload_reconciliation.py` accepts refreshed changes only on AD-23 fields. The list has two parts: `ignore_fields`, compared both ways with the program, and `refresh_only_fields`, read only by the reducer. The reconciliation file is a C-contract file (S4.10, then S4.13). The **preview** role produces the gate-2 clean-drift evidence (`test_post_apply_drift`; PROD `prod_post_apply_drift`). Its `if` admits workload operations after acceptance, and its workload branch `needs: test_apply_receipt`. `scheduled-drift.yml` excludes workload-phase stacks in the `drift` branch only, with the recorded reason `workload-drift-routed-to-runner`; if every stack is excluded, the job exits 0. The same baseline limit for a `phase: registry` stack is recorded, not changed. Architecture line 23 and the FR-32 test names are fixed. Step 14 is the `test_post_apply_drift` job of the step-13 `resume` run. `run_pulumi_drift_check.py` carries nothing. | `architecture.md:23,837-847,859-902,939-946,1193,1330`; `prd.md:213,290`; `epics-stories.md:297-334,1117-1233,1466-1473` | `Makefile:229-230`; `scripts/run_pulumi_command.py:54-70,84,846-852`; `scripts/_pulumi_command_support.py:66-70`; `.github/workflows/scheduled-drift.yml:23-84,86-147`; `pulumi/__main__.py:18-30`; `.github/workflows/self-deploy.yml:478-568` (`if` 480-483, `needs` 486-489, role 546); `scripts/service_execution_host.py:27-31`; `scripts/service_execution_worker.py:28,99`; `scripts/poc_workload_runner.py:154,202`; `scripts/poc_workload_reconciliation.py:224-245`; `docs/poc-workload-reconciliation.md`; `tests/pulumi/test_ci_guardrails.py:18`; `tests/unit/test_script_entrypoints.py:500-504` |
| R5-M2 `clear-pending` leaves the resume anchor stale | Every recovery subcommand that writes the checkpoint writes a receipt for the new checkpoint. `clear-pending` writes an export receipt with `cause: clear-pending` and a `predecessor` link to the prior failed or export receipt. `release-lock` must leave the checkpoint unchanged. The S1.1 schema carries `cause`, `predecessor` and `workload_operation`. Offline tests cover two chains, each admitting `resume`: failed receipt → `clear-pending` → `resume` (P2), and cancelled run → `export` → `release-lock` → `clear-pending` → `resume` (P3). The same chain without the clear-pending receipt is refused. FR-35 B, the FR-35 live column, NFR-09 and step 13 are updated. A cancellation kills the host, so step 13 runs `export` first. | `architecture.md:697-718,987-1022,1030`; `prd.md:216,246,293,307`; `epics-stories.md:126-179,888-921,1022-1092,1452-1465` | `scripts/poc_workload_runner.py:44-47`; `scripts/poc_workload_admission.py:150-166,464-475`; `scripts/service_execution_host.py:76-83` |
| R5-M3 one `start_at` for many actions | The contract lists each action with its own time: `scaling.starts: [{seq, at}]` and `scaling.stops: [{seq, at}]`. An entry is immutable once its URN is in the checkpoint, and the window applies only to the new entry. Step 2 creates the single unconsumed start entry, named by `seq`. That entry comes from its own PR (step 6b); a missed window moves the uncreated entry to `consumed`. The S2.1 B1 test requires earlier inputs to be byte-equal, and S4.9 N7 refuses an update of an earlier action. V-23(c) is reconciled (a fired action that stays listed is `same`). D-12 and abandon are covered: the rebuild's 5b PR moves earlier entries to `consumed`, and its 6b PR appends a new entry. | `architecture.md:165-168,306-334,398-404`; `prd.md:116,215,269`; `epics-stories.md:413-458,956-1021,1387-1400,1505-1515` | `research.md:276` (A-26) |
| R5-M4 S1.11 forward dependency | S1.11 moves to C-contract after S1.8 (S1.1 → S1.7 → S1.9 → S1.8 → S1.11 → S4.10), at ordered row 20, after S2.1 (row 16). S2.1 adds the `ignore_changes` values, only in the hardened branch, and does not edit the list. | `architecture.md:1191`; `epics-stories.md:297-334,413-436,1660,1691-1696` | `pulumi/` has no `ignore_changes` today (grep); `tests/integration/test_poc_first_topology_native.py:247-248` |
| R5-M5 checks reject `ignoreChanges`/`retainOnDelete` | S4.10 owns a recorded, deliberate narrow change. `ignoreChanges` is allowed only when it equals the AD-23 `ignore_fields`; `retainOnDelete` only on the abandon path, for manifest `retain` URNs. The change covers four places: reconciliation `UNSAFE_STATE`, and the topology create-goal, create-step `newState` and `_validate_workload_step` checks. It has P2 and N4 tests and is recorded in `docs/poc-workload-reconciliation.md`. The registry capture path (`poc_registry_plan._state`/`_prior`), which both callers use, gets a workload-aware capture in S4.11 for every mode except `first`; `poc_registry_plan.py` is not changed. | `architecture.md:904-938,1156-1162`; `epics-stories.md:733-815,846-854` | `scripts/poc_workload_reconciliation.py:31-49,95`; `scripts/poc_registry_plan.py:74-86,297-324,365-376`; `scripts/poc_registry_runner.py:254-258`; `scripts/poc_workload_runner.py:36-44`; `scripts/poc_workload_admission.py:150-152`; `scripts/poc_workload_secret_result.py:71,212`; `scripts/poc_gateway_backend.py:40`; `scripts/poc_workload_topology.py:321-326,1111-1115` |
| m1 hold plan re-sending min/max | V-23(e): the provider source is read as the first case of S2.1 and S4.9. S4.9 does not merge if a hold update can send values other than the live ones. V-23(d) stays the live STOP. | `architecture.md:345-357,1340`; `epics-stories.md:436-443,980-986` | — |
| m2 S5.22 issuer pinning | S5.22 adds its own pinned-context code and a spoofing test. | `architecture.md:638-656`; `epics-stories.md:1597` | `scripts/_github_repository_controls.py:13,46-60,64-78,385-409` (USI) |
| m3 which repo applies USI controls | USI applies its own environments and ruleset with its own scripts (new chain C-controls). S5.21 extends `ADDITIONAL_PROTECTED_ENVIRONMENTS` and `SERVICE_PROTECTED_ENVIRONMENTS` and the verification. `prod-recovery` moves from S5.19 to S5.21. | `architecture.md:54-61,626-633,1190`; `epics-stories.md:1596-1597,1600`; `prd.md:62,357` | `scripts/configure_github_repository_controls.py:79-85,256-311,527-538`; `scripts/_github_repository_controls.py:185`; `scripts/_github_environment_controls.py:22,36`; `scripts/_github_evidence_environment.py` |
| m4 stale "issues no receipt"; failure-path publication | S4.11 updates the runner docstring (lines 1-7) and spec lines 38-40, 50-52 and 97-98; S4.13 updates lines 37-38 and 121-122. The receipt reaches publication in four steps: the worker copies it before line 127; the host copies it out in a `finally` path, because today it raises first and copies only `_preview` jobs; `test_apply` uploads it with `if: always()`; and the new `test_apply_receipt` job (`governance-evidence`) publishes it. The host is added to C-runner. | `architecture.md:987-1007,1041-1051,1193`; `epics-stories.md:829-866` | `scripts/poc_workload_runner.py:1-7`; `specs/poc-workload-runner.md:36-40,50-52,97-98,121-122`; `scripts/service_execution_worker.py:127-132`; `scripts/service_execution_host.py:76-83,166-167,213-218`; `.github/workflows/self-deploy.yml:659-700` |
| m5 S4.1 not independent | S4.1 heads C-runner: S4.1 → S4.4 → S4.5. | `architecture.md:1193,1204-1216`; `epics-stories.md:704-712,1613-1635,1667` | `tests/unit/test_service_execution_worker.py` |
| m6 `workload_phase.py` wiring owner | New chain C-composition: S1.1 → S1.3 → S1.4 → S2.1 → S2.3 → S3.2 → S3.1 → S3.3 → S3.5-A. S3.5-A carries the `_validate_target` PROD parameterization, before S4.10. There are also new C-autoscaling and C-observability chains. S2.3 wires observability and adds the S2.4 and S2.5 types. | `architecture.md:1194-1196`; `epics-stories.md:468-474,663-685` | `pulumi/app/workload_phase.py:13-29,31-57,125-160` |
| m7 brief metric 4 | Aligned: `SetAlarmState` is the scale-out exercise, and the load test is optional after S5.16. | `brief.md:81-85` | — |
| m8 S3.5-A vs P-1 | S3.5-A has no TEST live item. P-1 is the PROD `plan` under gate 2a (`prod_preview`). | `epics-stories.md:663-685` | — |
| m9 S1.1 generators | Only the hardened branch drops them; the pre-hardening branch keeps them until S4.10. | `epics-stories.md:126-179` | `tests/integration/test_poc_first_topology_native.py:105` |
| m10 S1.9 negative test | Scoped to `workload_step` fixtures; the all-log-groups check is S4.10 N3. | `epics-stories.md:276-296` | `pulumi/app/compute.py:213-217` |
| m11 resume after step 2 | Resume finishes the anchor's `workload_operation` under that mode's rule. The checkpoint must hold the URNs of the last success receipt plus a subset of that operation's URNs. An uncreated action may be replaced by a new entry. | `architecture.md:1030`; `epics-stories.md:897-909,1452-1465` | — |
| m12 V-23(c) STOP timing | STOP before the next apply of any mode. | `architecture.md:383-397,1340`; `epics-stories.md:1413-1418` | `scripts/_pulumi_command_support.py:59-64` (`up-plan` has `--refresh`) |
| m13 window vs apply budget | The window runs from + 10 min (`rollback-zero`) or + 60 min (`step2`) to + 120 min. The observation runs in the separate `test_workload_observation` job. It gets credentials only after the wait, has its own concurrency group and `needs: test_apply_receipt`. A late `test-preview` approval only delays it. The 3300 s process timeout, 70-min job budget and FR-24 bounds are unchanged. | `architecture.md:366-382,747-768`; `epics-stories.md:993-999,1125-1145`; `prd.md:116` | `.github/workflows/self-deploy.yml:164,319-345,361,507,598`; `scripts/configure_github_repository_controls.py:79-85`; `tests/unit/test_apply_timeout_budget.py` |
| m14 hard-stop test rewrite | S4.15 needs Kravalg's approval specifically, or the rewrite moves into the step-1 PR. | `epics-stories.md:1272-1280` | `.github/CODEOWNERS` (`* @Kravalg @dmytrocraft`) |
| m15 AD-09 file | A function in `scripts/poc_workload_admission.py` (S4.2), not the topology. | `architecture.md:280-285`; `epics-stories.md:910-913` | — |
| m16 RPO/RTO | RPO ≤ 5 min (point-in-time restore, `LatestRestorableTime` lag) and RTO ≤ 4 h, measured in S4.8 and validated by S4.15. A miss is a STOP at gate 2a. | `architecture.md:788-803`; `prd.md:211`; `epics-stories.md:1532-1557` | `pulumi/app/environment.py:677-681`; `pulumi/app/data.py:204-211` |
| m17 cost threshold and source label | NFR-11 requires a data-source label on every figure and a 20% forecast threshold, and every PROD increase is justified. S2.6 has the doc test. | `prd.md:248,309`; `epics-stories.md:539-560` | — |
| m18 run-summary checklist; incident-response applicability | The run-summary line now names the three `rollback-zero` phases. The incident-response entry below names its content (the S2.4 runbook fields). | `run-summary.md` checklist; `epics-stories.md:481-500`; this file | — |

## Unresolved external prerequisites

These are recorded gates, not planning defects.

- **XP-1.** Central roles: the source (`d41c019`) is not in the local
  bootstrap clone.
- **XP-2 / XP-3.** The BI capability, KMS, function, restore, recovery and
  exercise stories.
- **XP-4.** user-service work.
- **XP-5.** The AGI front door.
- **XP-6.** The SNS subscription endpoint.
- **XP-7.** `.claude/devops-sdlc.json` is absent, so `validate-profile`
  returned BLOCKED.
- **XP-8.** The post-step-1 metadata.
- **XP-9 … XP-13.** The existing runner prerequisites.
- **XP-14.** The PROD registry phase (outside this plan; gate 2).

## Remaining user decisions

None are open for planning. Some decisions arise only if a live check or
measurement fails:

| ID | Trigger | State |
| --- | --- | --- |
| Conditional: V-1 fails | step-2 health (step 7) | a new decision would be needed (an app DB user with a rotated password) |
| Conditional: V-5 requires a `default` password | step 1 | a new decision would be needed (no Pulumi-generated password allowed) |
| Conditional: V-16 fails with SSE-KMS | step 12 | SSE-S3 would contradict D-4, so a new decision would be needed |
| Conditional: RPO or RTO target missed | S4.8, before gate 2a | the user accepts the measured value or asks for a design change |

## Skill applicability (devops-sdlc 14)

**Applicable and addressed:**

- security-iam (AD-15a, S5.x, S5.21/S5.22 repository controls)
- state-migration (AD-16, AD-25, the R5-M5 checkpoint-field allowance)
- observability (§3.2a)
- cost-optimization (NFR-11 with source labels and threshold)
- backup-recovery (S4.8 with the AD-19 RPO/RTO targets, S5.18a/b)
- delivery-and-rollback (AD-19, AD-24)
- drift-management (FR-32 on the executed workload path: S1.11, S4.10,
  S4.13; the scheduled-drift exclusion)
- python-pulumi
- infrastructure-quality
- evidence-and-coverage
- environment-lifecycle (gate 2a/2b, S4.14)
- incident-response (m18): each S2.4 runbook entry names a severity, a first
  responder, an escalation path (Kravalg for secret, IAM or KMS events), a
  containment action and the evidence to keep. A PROD `rollback-zero` stop
  needs a recorded incident reason (AD-10). Every S4.6 STOP rule escalates
  through S4.3.
- bmad-autonomous-planning

**SKIPPED:** terraform-terraspace, because the engine is Pulumi.
