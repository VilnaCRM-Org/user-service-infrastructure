---
artifact: implementation-readiness
workflow: _bmad/bmm/workflows/3-solutioning/bmad-check-implementation-readiness (Validate mode)
task: workload-wa-hardening
source_baseline: 66776772979956de9c5abdbee7c45641a1b533fa (workload source); bundle parent 68584e1
date: 2026-09-30
revision: 6
author: the planning agent that wrote revision 6 (NOT an independent reviewer)
independent_reviewer: none yet for revision 6
status: PENDING independent review of revision 6
---

# Implementation readiness

## Verdict

**PENDING. Not PASS.** The author of revision 6 wrote this file. It records
what changed and the repository source each fix was checked against. It does
not grade itself.

- Only an independent reviewer's PASS satisfies the planning gate.
- Revision 6 answers independent readiness round 6 (FAIL: 2 major,
  R6-M1 and R6-M2; 13 minor, R6-m1 and R6-m3…m14; no R6-m2 was relayed).
- No fresh-context author-side audit ran on revision 6 before the commit.
  The fixes were checked against the cited source by the author only.
- Round 5 was recorded as the last allowed review round, and round 6 ran
  after it. Whether another independent round runs is for the coordinator
  and the user to decide. Until an independent reviewer reports PASS, the
  stage stays BLOCKED.

## Review history

| Round | Reviewer | Result | Handled in |
| --- | --- | --- | --- |
| 1 | independent `devops-sdlc:fr-nfr-reviewer` | FAIL: 3 blocking, 10 major, minors | revision 2 |
| 2 | independent reviewer | Result not stored in this bundle | — |
| 3 | independent reviewer (relayed by the coordinator) | FAIL: B-1, B-2, M-1…M-13, m-1…m-12 | revision 3 |
| 4 | independent reviewer (relayed by the coordinator) | FAIL: R4-B1…B3, R4-M1…M10, m1…m12 | revision 4 |
| 5 | independent reviewer (relayed by the coordinator) | FAIL: R5-M1…M5, m1…m18; every round-4 finding confirmed resolved | revision 5 |
| 6 | independent reviewer (relayed by the coordinator) | FAIL: R6-M1, R6-M2, R6-m1, R6-m3…m14 | revision 6 (this file) |

## User decisions (all explicit, dated 2026-09-30)

`decisions.md` is the source. Commit `68584e1` added D-14 after revision
5; revision 6 changes only the label of the D-14 row. Every decision is
resolved, and none is a default: D-1…D-7 and D-14, and the derived details
D-8…D-13 that the user confirmed the same day. XP-14 (the PROD registry) is
still an open ownership item that blocks gate 2.

- **D-14 is a user decision (R6-m1):** DocumentDB RPO ≤ 1 hour and RTO ≤ 24
  hours for TEST and PROD. A measured miss is a STOP at gate 2a for a new
  user decision; no default relaxes D-14.
- **Planning defaults, not user decisions:** only the 20% TEST cost forecast
  threshold and the rule that every PROD increase is justified (NFR-11,
  m17). The user may change them.

## Round-6 finding → resolution map

Line numbers refer to revision 6. "Source" is the repository file and lines
each fix was checked against, at `68584e1` (the workload source is unchanged
from the baseline). Every rewrite of a pinned workflow-shape test is a
guardrail change that needs an `APPROVED` review by `@Kravalg`
specifically, recorded with the PR number in the acceptance receipt, as the
round-5 m14 hard-stop amendment is.

| Finding | Resolution | Location | Source checked |
| --- | --- | --- | --- |
| R6-M1 pinned CI-shape tests have no owner; registry-phase regression | Every pinned test is assigned, with its new closed set and the negatives kept. **S4.11:** `test_ci_guardrails.py` 262-273 and `test_trusted_test_controller_workflow.py` 16-26 gain `test_apply_receipt`; `test_poc_source_workflow.py` 214-223 gain it (no `always(`; its `if` is `!cancelled()` plus source success plus `test_apply` success or failure); the credential set is unchanged. **S4.13:** a **separate** `test_workload_drift` job (option 1): `test_post_apply_drift` keeps its `if` and `needs`, so the registry chain is untouched and `test_poc_registry_workflow.py` 128-132 and `test_poc_source_workflow.py` 223 need no relaxation. `test_ci_guardrails.py` 262-273 (three new jobs), 280-306 (exact `if`s; 293-297 byte-equal), 314-319 (`test_workload_drift`, `test_workload_observation`), 347-353 (`test_workload_drift`); `test_trusted_test_controller_workflow.py` 9 and 16-26; `test_poc_registry_completion_workflow.py` 148-151 (the closed `test_workload*` set); `test_poc_source_workflow.py` 196-201 and 214-223; `test_poc_phase_source_adapter.py` 414-416. **S4.14:** the seven `prod_*` jobs in `test_ci_guardrails.py` 98-101, 262-273, 280-306, 314-319 and 347-353; `test_trusted_test_controller_workflow.py` 9 and 16-26; `test_service_execution_workflow.py` 55 and 58; `test_service_initializer.py` 330-336; `test_service_execution_host.py` 173-175; `test_poc_source_workflow.py` 40-50, 196-201 and 214-223; PROD only behind `admission.prod`. **S4.17:** `test_poc_scheduled_registry_workflow.py` 19, `test_ci_guardrails.py` 177 and 347-353. `test_workload_observation` and `test_workload_acceptance` require `needs.test_apply.result == 'success'`. Regression case S4.13 B2: on a registry run with `test_apply_receipt` skipped, the registry chain still runs. The C-runner list names the tests and `scripts/poc_phase_source_adapter.py`. No gate is weakened. | `architecture.md:23,974-986,1088-1096,1132-1140,1196-1239,1376`; `prd.md:213`; `epics-stories.md:846-951,1219-1447,1449-1551,1867-1931,1766-1773` | `tests/pulumi/test_ci_guardrails.py:98-101,177,262-273,280-306,314-319,347-353`; `tests/unit/test_trusted_test_controller_workflow.py:9,16-26`; `tests/unit/test_service_execution_workflow.py:55,58`; `tests/unit/test_poc_registry_completion_workflow.py:16-23,148-152`; `tests/unit/test_poc_registry_workflow.py:128-132`; `tests/unit/test_poc_source_workflow.py:40-50,196-201,214-223`; `tests/unit/test_poc_phase_source_adapter.py:414-416`; `tests/unit/test_service_initializer.py:330-336`; `tests/unit/test_service_execution_host.py:173-175`; `tests/unit/test_poc_scheduled_registry_workflow.py:19`; `.github/workflows/self-deploy.yml:480-483,486-489,572-581,661-667,723-730`; `scripts/poc_phase_source_adapter.py:291` |
| R6-M2 S4.2 uses S4.9 rules before S4.9 | C-contract is S4.10 → S4.11 → S4.9 → S4.2 → S4.3. S4.9 moves before S4.2 in the text and the ordered list (rows 30 and 31); S4.9 follows S4.11, S4.2 follows S4.9, S4.3 follows S4.2. The no-forward-dependency claim is re-verified over all 51 rows (S4.17 added as row 49). | `architecture.md:1374`; `epics-stories.md:716-722,956-958,1036-1038,1104-1106,2052-2054,2075-2083` | — |
| R6-m1 D-14 labels | RPO ≤ 1 hour and RTO ≤ 24 hours are labelled user decision D-14 in AD-19, FR-30, S4.8, this file and `run-summary.md`; the "unchanged in revision 5" wording is corrected; D-14 is in the PRD §6 table, the front-matter decision ranges (PRD, architecture, epics, brief), the epics inventory and ordered row 0. Only the 20% threshold and the PROD justification rule stay planning defaults (NFR-11). | `architecture.md:7,856-875`; `prd.md:7,211,248,327`; `epics-stories.md:7,17-23,1850-1854,2023`; `brief.md:7`; `decisions.md:14`; this file; `run-summary.md` | `decisions.md` (commit `68584e1`) |
| R6-m3 acceptance job has no AWS credentials | `test_workload_observation` captures the checkpoint through the trusted observer (preview role) and writes it into its artifact; `test_workload_acceptance` verifies that artifact, like the registry proof. The observation job "runs no Pulumi command and holds no state lock". | `architecture.md:794-835`; `epics-stories.md:1230-1270,1408,1430` | `.github/workflows/self-deploy.yml:570-657,659-690`; `scripts/poc_backend_observer.py:419-470` |
| R6-m4 drift dispatch not implementable | The registry plan-plus-gate pattern is reused: `drift` captures with operation `plan` (the only other accepted one is `up-plan`) and dispatches `_dispatch_command("plan")`, whose `_run_plan_command` supplies the plan path and the JSON preview; the gate runs `validate_drift` on every completed plan, and since `plan` has no `--expect-no-changes`, the drifted field is always named. No `workload-drift` invocation is added. V-13 is restated for the `plan` invocation. | `architecture.md:23,940-966,1063-1066,1513`; `prd.md:213,290`; `epics-stories.md:329,1223-1226,1271-1297,1417-1420,1766-1773` | `scripts/run_pulumi_command.py:592-639,816-839`; `scripts/_pulumi_command_support.py:50-72,159-162,180-190`; `scripts/poc_backend_observer.py:181-185`; `scripts/poc_registry_runner.py:344,364`; `scripts/service_execution_host.py:27-31`; `scripts/service_execution_worker.py:128-132` |
| R6-m5 TEST-only pins | S4.14 has a pin table: host 142, `self-deploy.yml` 62 and 79-86, worker 74 and 93, runner 53, 82, 164 and 202, reconciliation 15, 92 and 104 each with a PROD fixture; the observer's 183 (with constants 37-43), 363 and 389 are assigned to XP-14 (PRD §7); line 184 is not a TEST pin. | `epics-stories.md:1483-1499,1541`; `architecture.md:1007,1240-1256`; `prd.md:416-422` | the cited lines of each file |
| R6-m6 runner waits for scale-in | The sentence is deleted. The observation job also covers stop plans (running = desired = 0), and hold admission requires the authenticated stop observation. FR-11 keeps "the window never lengthens the apply". | `architecture.md:354-381,794-835,1165-1167`; `prd.md:116,269`; `epics-stories.md:153,981-990,1027,1230-1270,1444,1774-1780` | — |
| R6-m7 hold flag and phase | S1.1 adds `workload_operation.phase` (and `resumes` for `resume`) and the persistent TEST-only `scaling.scheduled_scaling_suspended`. Only hold sets and only start clears it (S4.9); a `policy-update` during a hold renders every target `same`. AD-04, AD-10, S2.1, S4.12 and the mode → anchor table are aligned. | `architecture.md:163-175,369-387,1162-1167,1188-1190`; `prd.md:116,269`; `epics-stories.md:141-160,183-189,437-446,470-474,975-990,1027-1034,1193-1216` | — |
| R6-m8 export after a cancellation | S4.3's `export` uses a private, hash-only reader under the recovery role that tolerates pending operations, a lock and `delete`/`pendingReplacement` rows; admission never uses it. P3 has a non-empty `pending_operations` fixture; N6 keeps the observer's refusal. | `architecture.md:735-750`; `epics-stories.md:1123-1132,1180-1187,1753-1756` | `scripts/poc_backend_observer.py:40-43,366,391,452-470` |
| R6-m9 failed result inspection leaves no receipt | The runner writes an `outcome: failed` receipt (`cause: result-inspection`) when `_inspect_first_result` or the S4.10 checker raises; the worker copies it in a `finally` block. S4.11 P3 is the positive case. | `architecture.md:1112-1140,1176-1187`; `prd.md:216`; `epics-stories.md:153-156,859-872,933-937` | `scripts/poc_workload_runner.py:123-147,200-204`; `scripts/service_execution_worker.py:106-132` |
| R6-m10 restore rehearsal | R-1 is a point-in-time restore (`RestoreDBClusterToPointInTime`, `UseLatestRestorableTime`); S5.18a grants it; the achieved recovery point (the source `LatestRestorableTime` used) is the RPO evidence. No user decision was needed: this is stronger than the metadata-only evidence. | `architecture.md:85,852-872,1522`; `prd.md:211`; `epics-stories.md:1839-1864,1973` | `pulumi/app/environment.py:677-681` |
| R6-m11 PROD scheduled drift | Gate 2b requires S4.17 (scheduled workload drift for both workload stacks, schedule-only provenance, Drift role); FR-31, AD-21, S4.15 and S4.7 encode it. The PROD stack → contract mapping is defined (`poc-prod.json`, `admission` only in `poc-test.json`). No risk acceptance is recorded. | `architecture.md:175-186,893-903,996-999,1257-1273`; `prd.md:212-213,289,416-422`; `epics-stories.md:1381-1383,1553-1565,1867-1931,1941-1960,2072-2073` | `scripts/poc_phase_admission.py:24`; `scripts/poc_scheduled_registry_drift.py:1-40`; `.github/workflows/scheduled-drift.yml`; `scripts/poc_backend_observer.py:428-437` |
| R6-m12 `importID` after a recovery import | New V-27 (engine source first, like V-24) in S4.10 and S4.3; if `importID` persists, it is accepted only for URNs listed in the import receipt; the registry `_state` stays unchanged. | `architecture.md:1029-1040,1344-1348,1527`; `epics-stories.md:25,807-816,832-834,1139-1141` | `scripts/poc_workload_reconciliation.py:31-49,95`; `scripts/poc_registry_plan.py:312` |
| R6-m13 `poc_registry_plan.py` ownership | Each statement is scoped: S4.11 does not change the file; S4.3's post-abandon baseline acceptance is its only change. The file is in the C-contract list, and the R5-M5 row below is amended. | `architecture.md:716-719,1053-1056,1374`; `epics-stories.md:896-898,1133-1135,2001-2006`; this file | `scripts/poc_registry_plan.py:297-324,365-376` |
| R6-m14 empty-stack citation | Corrected to lines 850-856. | `architecture.md:996`; `epics-stories.md:1379`; the R5-M1 row below | `scripts/run_pulumi_command.py:850-856` |

## Round-5 finding → resolution map (revision 5, amended)

Line numbers refer to revision 5. Revision 6 supersedes parts of these rows:
R5-M1 (drift job and dispatch: R6-M1, R6-m4; citation: R6-m14), R5-M5
(file scope: R6-m13), m13 (observation job: R6-m3, R6-m6) and m16 (restore
method and labels: R6-m1, R6-m10). Where they differ, the round-6 map is
authoritative.

| Finding | Resolution | Location | Source checked |
| --- | --- | --- | --- |
| R5-M1 FR-32 check in an unexecuted script | The FR-32 check moves to the executed workload path. A `workload-drift` invocation (`preview --refresh --expect-no-changes --json --save-plan`) is registered in `run_pulumi_command.py`, and the runner dispatches it. `validate_drift` in `scripts/poc_workload_reconciliation.py` accepts refreshed changes only on AD-23 fields. The list has two parts: `ignore_fields`, compared both ways with the program, and `refresh_only_fields`, read only by the reducer. The reconciliation file is a C-contract file (S4.10, then S4.13). The **preview** role produces the gate-2 clean-drift evidence (`test_post_apply_drift`; PROD `prod_post_apply_drift`). Its `if` admits workload operations after acceptance, and its workload branch `needs: test_apply_receipt`. `scheduled-drift.yml` excludes workload-phase stacks in the `drift` branch only, with the recorded reason `workload-drift-routed-to-runner`; if every stack is excluded, the job exits 0. The same baseline limit for a `phase: registry` stack is recorded, not changed. Architecture line 23 and the FR-32 test names are fixed. Step 14 is the `test_post_apply_drift` job of the step-13 `resume` run. `run_pulumi_drift_check.py` carries nothing. | `architecture.md:23,837-847,859-902,939-946,1193,1330`; `prd.md:213,290`; `epics-stories.md:297-334,1117-1233,1466-1473` | `Makefile:229-230`; `scripts/run_pulumi_command.py:54-70,84,850-856` (citation corrected in revision 6, R6-m14); `scripts/_pulumi_command_support.py:66-70`; `.github/workflows/scheduled-drift.yml:23-84,86-147`; `pulumi/__main__.py:18-30`; `.github/workflows/self-deploy.yml:478-568` (`if` 480-483, `needs` 486-489, role 546); `scripts/service_execution_host.py:27-31`; `scripts/service_execution_worker.py:28,99`; `scripts/poc_workload_runner.py:154,202`; `scripts/poc_workload_reconciliation.py:224-245`; `docs/poc-workload-reconciliation.md`; `tests/pulumi/test_ci_guardrails.py:18`; `tests/unit/test_script_entrypoints.py:500-504` |
| R5-M2 `clear-pending` leaves the resume anchor stale | Every recovery subcommand that writes the checkpoint writes a receipt for the new checkpoint. `clear-pending` writes an export receipt with `cause: clear-pending` and a `predecessor` link to the prior failed or export receipt. `release-lock` must leave the checkpoint unchanged. The S1.1 schema carries `cause`, `predecessor` and `workload_operation`. Offline tests cover two chains, each admitting `resume`: failed receipt → `clear-pending` → `resume` (P2), and cancelled run → `export` → `release-lock` → `clear-pending` → `resume` (P3). The same chain without the clear-pending receipt is refused. FR-35 B, the FR-35 live column, NFR-09 and step 13 are updated. A cancellation kills the host, so step 13 runs `export` first. | `architecture.md:697-718,987-1022,1030`; `prd.md:216,246,293,307`; `epics-stories.md:126-179,888-921,1022-1092,1452-1465` | `scripts/poc_workload_runner.py:44-47`; `scripts/poc_workload_admission.py:150-166,464-475`; `scripts/service_execution_host.py:76-83` |
| R5-M3 one `start_at` for many actions | The contract lists each action with its own time: `scaling.starts: [{seq, at}]` and `scaling.stops: [{seq, at}]`. An entry is immutable once its URN is in the checkpoint, and the window applies only to the new entry. Step 2 creates the single unconsumed start entry, named by `seq`. That entry comes from its own PR (step 6b); a missed window moves the uncreated entry to `consumed`. The S2.1 B1 test requires earlier inputs to be byte-equal, and S4.9 N7 refuses an update of an earlier action. V-23(c) is reconciled (a fired action that stays listed is `same`). D-12 and abandon are covered: the rebuild's 5b PR moves earlier entries to `consumed`, and its 6b PR appends a new entry. | `architecture.md:165-168,306-334,398-404`; `prd.md:116,215,269`; `epics-stories.md:413-458,956-1021,1387-1400,1505-1515` | `research.md:276` (A-26) |
| R5-M4 S1.11 forward dependency | S1.11 moves to C-contract after S1.8 (S1.1 → S1.7 → S1.9 → S1.8 → S1.11 → S4.10), at ordered row 20, after S2.1 (row 16). S2.1 adds the `ignore_changes` values, only in the hardened branch, and does not edit the list. | `architecture.md:1191`; `epics-stories.md:297-334,413-436,1660,1691-1696` | `pulumi/` has no `ignore_changes` today (grep); `tests/integration/test_poc_first_topology_native.py:247-248` |
| R5-M5 checks reject `ignoreChanges`/`retainOnDelete` | S4.10 owns a recorded, deliberate narrow change. `ignoreChanges` is allowed only when it equals the AD-23 `ignore_fields`; `retainOnDelete` only on the abandon path, for manifest `retain` URNs. The change covers four places: reconciliation `UNSAFE_STATE`, and the topology create-goal, create-step `newState` and `_validate_workload_step` checks. It has P2 and N4 tests and is recorded in `docs/poc-workload-reconciliation.md`. The registry capture path (`poc_registry_plan._state`/`_prior`), which both callers use, gets a workload-aware capture in S4.11 for every mode except `first`. S4.11 does not change `poc_registry_plan.py`; S4.3's post-abandon baseline acceptance is the file's only change in this plan (scoped in revision 6, R6-m13). | `architecture.md:904-938,1156-1162`; `epics-stories.md:733-815,846-854` | `scripts/poc_workload_reconciliation.py:31-49,95`; `scripts/poc_registry_plan.py:74-86,297-324,365-376`; `scripts/poc_registry_runner.py:254-258`; `scripts/poc_workload_runner.py:36-44`; `scripts/poc_workload_admission.py:150-152`; `scripts/poc_workload_secret_result.py:71,212`; `scripts/poc_gateway_backend.py:40`; `scripts/poc_workload_topology.py:321-326,1111-1115` |
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
| m16 RPO/RTO | RPO ≤ 1 hour (point-in-time restore, `LatestRestorableTime` lag, D-14) and RTO ≤ 24 hours (D-14), measured in S4.8 and validated by S4.15. A miss is a STOP at gate 2a. | `architecture.md:788-803`; `prd.md:211`; `epics-stories.md:1532-1557` | `pulumi/app/environment.py:677-681`; `pulumi/app/data.py:204-211` |
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
- **XP-14.** The PROD registry phase (outside this plan; gate 2). It also
  owns the trusted observer's PROD coordinates and the committed
  `specs/poc/poc-prod.json` (R6-m5, R6-m11).

## Remaining user decisions

None are open for planning. Some decisions arise only if a live check or
measurement fails:

| ID | Trigger | State |
| --- | --- | --- |
| Conditional: V-1 fails | step-2 health (step 7) | a new decision would be needed (an app DB user with a rotated password) |
| Conditional: V-5 requires a `default` password | step 1 | a new decision would be needed (no Pulumi-generated password allowed) |
| Conditional: V-16 fails with SSE-KMS | step 12 | SSE-S3 would contradict D-4, so a new decision would be needed |
| Conditional: a D-14 RPO or RTO target missed | S4.8, before gate 2a | a new user decision: accept the measured value or change the design |

## Skill applicability (devops-sdlc 14)

**Applicable and addressed:**

- security-iam (AD-15a, S5.x, S5.21/S5.22 repository controls)
- state-migration (AD-16, AD-25, the R5-M5 checkpoint-field allowance, the
  V-27 `importID` case and the private export reader)
- observability (§3.2a)
- cost-optimization (NFR-11 with source labels and the planning-default
  threshold)
- backup-recovery (S4.8 point-in-time restore measured against user
  decision D-14, AD-19; S5.18a/b)
- delivery-and-rollback (AD-19, AD-24)
- drift-management (FR-32 on the executed workload path: S1.11, S4.10,
  S4.13 `test_workload_drift`; the scheduled-drift exclusion; S4.17
  scheduled workload drift before gate 2b)
- python-pulumi
- infrastructure-quality
- evidence-and-coverage
- environment-lifecycle (gate 2a/2b, S4.14, the stack → contract mapping)
- incident-response (m18): each S2.4 runbook entry names a severity, a first
  responder, an escalation path (Kravalg for secret, IAM or KMS events), a
  containment action and the evidence to keep. A PROD `rollback-zero` stop
  needs a recorded incident reason (AD-10). Every S4.6 STOP rule escalates
  through S4.3.
- bmad-autonomous-planning

**SKIPPED:** terraform-terraspace, because the engine is Pulumi.
