---
artifact: implementation-readiness
workflow: _bmad/bmm/workflows/3-solutioning/bmad-check-implementation-readiness (Validate mode)
task: workload-wa-hardening
source_baseline: 66776772979956de9c5abdbee7c45641a1b533fa (workload source); bundle parent 5cc069c (revision 6)
date: 2026-09-30
revision: 7
author: the planning agent that wrote revision 7 (NOT an independent reviewer)
independent_reviewer: none yet for revision 7
status: PENDING independent review of revision 7
---

# Implementation readiness

## Verdict

**PENDING. Not PASS.** The author of revision 7 wrote this file. It records
what changed and the repository source each fix was checked against. It does
not grade itself.

- Only an independent reviewer's PASS satisfies the planning gate.
- Revision 7 answers independent readiness round 7 (FAIL: 2 major, R7-M1
  and R7-M2; 9 minor, R7-m1…m9; 3 nits, R7-n1…n3) and three further
  findings of a fresh-context audit of revision 6 (F2, F6 and F8; its F1,
  F3, F4, F5 and F7 duplicate R7-m5, R7-m3, R7-M1 plus R7-m7, R7-m6 and
  R7-n2).
- A fresh-context, read-only audit of the revision-7 changes ran before the
  commit; its result and what was folded in are recorded in "Pre-commit
  audit of revision 7" below. It is an author-side check, not the
  independent review.
- Rounds 5, 6 and 7 ran after round 5 was recorded as the last allowed
  round. Whether another independent round runs is for the coordinator and
  the user to decide. Until an independent reviewer reports PASS, the stage
  stays BLOCKED.

## Review history

| Round | Reviewer | Result | Handled in |
| --- | --- | --- | --- |
| 1 | independent `devops-sdlc:fr-nfr-reviewer` | FAIL: 3 blocking, 10 major, minors | revision 2 |
| 2 | independent reviewer | Result not stored in this bundle | — |
| 3 | independent reviewer (relayed by the coordinator) | FAIL: B-1, B-2, M-1…M-13, m-1…m-12 | revision 3 |
| 4 | independent reviewer (relayed by the coordinator) | FAIL: R4-B1…B3, R4-M1…M10, m1…m12 | revision 4 |
| 5 | independent reviewer (relayed by the coordinator) | FAIL: R5-M1…M5, m1…m18; every round-4 finding confirmed resolved | revision 5 |
| 6 | independent reviewer (relayed by the coordinator) | FAIL: R6-M1, R6-M2, R6-m1, R6-m3…m14 | revision 6 |
| 7 | independent reviewer (relayed by the coordinator), plus a fresh-context audit of revision 6 | FAIL: R7-M1, R7-M2, R7-m1…m9, R7-n1…n3; audit F1…F8 (F2, F6, F8 new) | revision 7 (this file) |

## User decisions (all explicit, dated 2026-09-30)

`decisions.md` is the source. Commit `68584e1` added D-14 after revision
5; revision 6 changed only the label of the D-14 row; revision 7 does not
change `decisions.md`, and no round-7 finding needed a new user decision. Every decision is
resolved, and none is a default: D-1…D-7 and D-14, and the derived details
D-8…D-13 that the user confirmed the same day. XP-14 (the PROD registry) is
still an open ownership item that blocks gate 2.

- **D-14 is a user decision (R6-m1):** DocumentDB RPO ≤ 1 hour and RTO ≤ 24
  hours for TEST and PROD. A measured miss is a STOP at gate 2a for a new
  user decision; no default relaxes D-14.
- **Planning defaults, not user decisions:** only the 20% TEST cost forecast
  threshold and the rule that every PROD increase is justified (NFR-11,
  m17). The user may change them.

## Round-7 finding → resolution map

Line numbers refer to revision 7. "Source" is the repository file and lines
each fix was checked against, in the current tree at `5cc069c` (the
workload source is unchanged from the baseline). Every rewrite of a pinned
workflow-shape test still needs an `APPROVED` review by `@Kravalg`
specifically, recorded with the PR number in the acceptance receipt, like
the round-5 m14 amendment. The fresh-context audit of revision 6 is cited
as "audit F<n>"; the pre-commit audit of revision 7 as "pre-commit audit".

| Finding | Resolution | Location | Source checked |
| --- | --- | --- | --- |
| R7-M1 S4.14 misses pins it breaks (with audit F4, first half) | S4.14 lists each with its exact new assertion, keeping the TEST negatives: `prod_destructive_diff` exists, holds no credentials, `needs` exactly `[preflight, poc_prepare_source, prod_preview]`, `if` with `repository_dispatch`, `admission_prod` and `target_environment == 'prod'` (TEST job lines 250-255 byte-equal); the `poc_prepare_source` guard becomes `test \|\| prod`; the trusted-controller concurrency group and `target_environment` check become per-environment; the ancestry loop's TEST check becomes per-environment (`prod_*` also `admission_prod`); host test line 141 uses `root` for every `_preview` job (the host copies to `ROOT`); the host and seam tests follow the job's environment, every fault is environment-dependent (`-prod` on TEST and `-test` on PROD both fail); `_target_coordinates`/`_target` (host line 164; XP-14-owned) are stubbed with PROD coordinates, and S4.7 adds the unstubbed PROD seam case after XP-14 (pre-commit audit); host test lines 173-178 keep both `prepare` refusals on an unknown job, since `prepare` checks only job membership (pre-commit audit); the worker test's request follows `worker.JOBS[job]`. N4. | `epics-stories.md:1734-1735,1746-1840,1806-1816,1878-1881,2495-2501`; `architecture.md:1332-1352` | `tests/pulumi/test_ci_guardrails.py:249-255,281-284`; `tests/unit/test_trusted_test_controller_workflow.py:9,72-75,101-104`; `tests/unit/test_poc_source_workflow.py:214-224`; `tests/unit/test_service_execution_host.py:78-144,141,173-178,233-322`; `tests/unit/test_service_execution_worker.py:81-131,101`; `scripts/service_execution_host.py:130-134,164,214-219`; `scripts/poc_backend_observer.py:183,188-210` |
| R7-M2 S4.17 not implementable | S4.17 adds an isolated scheduled launch: host and worker entries `scheduled_{test,prod}_workload_drift` with host operation `scheduled-drift` (observer line 175) and scheduled-main provenance (the `poc_scheduled_registry_drift.py` `_context`/`verify_provenance` pattern), never a PR request; the jobs use `setup-service-execution`, a host `recheck` before each credential step and one host `execute`, with exact permissions (`contents`, `actions`, `deployments` read; `id-token: write`) and `GH_TOKEN` (pre-commit audit). The projection comes from the projection inputs recorded in the latest success receipt (S1.1 field, S4.11 writer) and from the contract that receipt applied, read at its `head_sha`/`blob_sha` as the adapter does, so the entrypoint's digest binding holds and a merged but unapplied operation PR does not change the check (pre-commit audit). It has its own gate modelled on `poc_scheduled_registry_drift._gate`, because the runner's gate and `execute` are PR-bound (`_review`, `observe_workload`, `revalidate_requester`, `capture_backend`, `_trusted_root`) (pre-commit audit). Negatives: outside the container fails with `workload-materializer-worker`/`-readonly`; no scheduled path calls any PR-bound function; contract-binding mismatch fails. The scheduled-registry workflow test (lines 1, 19, sibling test) and `CASES` are rewritten with Kravalg's approval. `_worker()` is never bypassed. | `epics-stories.md:160-165,875-878,2245-2472`; `architecture.md:1166-1169,1353-1415,1519` | `scripts/poc_workload_materializer.py:137-143`; `scripts/poc_workload_runner.py:51-75,155-157,158-184`; `scripts/service_execution_host.py:137-151,158,161`; `scripts/service_execution_worker.py:34-53,82-103`; `scripts/poc_backend_observer.py:175,183,428-435`; `scripts/poc_scheduled_registry_drift.py:49-101,136`; `scripts/poc_source_artifact.py:66`; `scripts/poc_workload_phase_entrypoint.py:104`; `scripts/poc_phase_source_adapter.py:239-245`; `scripts/poc_phase_admission.py:34-43`; `tests/unit/test_poc_scheduled_registry_workflow.py:1,19,22-46`; `tests/pulumi/test_ci_guardrails.py:177,185-186,341-353`; `.github/actions/setup-service-execution/action.yml` |
| R7-m1 S4.17 pre-acceptance exit 0 | Every verdict writes a `poc-workload-scheduled-drift-result-v1` record (`checked` or `before-acceptance`) bound to the captured checkpoint sha256 and the latest success receipt; before acceptance the same drift check runs against the latest success receipt and fails on drift, and a clean run exits 0 with a warning annotation (pre-commit audit); any lineage lookup error, including incomplete pagination, exits non-zero. S4.15 owns the schema, and its `complete` level (and gate 2b) accepts only `checked`. Negative tests: S4.17 N5 and B, S4.15 N2, S4.7 N3. | `epics-stories.md:1909-1920,1943-1945,2375-2399,2458-2459,2465-2471,2529-2530`; `architecture.md:940-943,1391-1404`; `prd.md:212-213` | — |
| R7-m2 baseline exclusion per stack | S4.13 excludes only stack `test`, when `poc-test.json` has `phase: workload`; S4.14 excludes `prod` only when `poc-prod.json` exists with `phase: workload`; a missing file keeps the baseline for `prod`. The PR that first sets `phase: workload` in `poc-prod.json` also enables the S4.17 PROD job, and S4.17 checks drift against the latest success receipt before acceptance, so no night leaves the `prod` workload uncovered; before any workload success receipt the checkpoint holds only registry resources, the registry owner's recorded case (pre-commit audit). S4.13 N5, S4.14 B2. | `epics-stories.md:1534-1542,1595-1600,1697-1702,1889-1893,2375-2383,2483-2494`; `architecture.md:1039-1046,1398-1404`; `prd.md:213` | `scripts/poc_phase_admission.py:24`; `.github/workflows/scheduled-drift.yml:23-84` |
| R7-m3 S4.14 pin table incomplete (audit F3) | New rows with PROD fixtures or an XP-14 assignment: the workload gate's use of `poc_registry_runner._binding` (266-283, called at runner line 58); `poc_workload_capabilities.py` (22-23, 30, 32, 92, 111, 130-133, 286; via admission line 470); `poc_workload_images.py` (44, 68, 126, 282, 349); and, from the pre-commit audit, the capture's registry-row check (`poc_registry_runner._capture` 254-263, `_ecr_inventory` 240-245), runner lines 194-195, `poc_workload_phase_entrypoint.py` 109-116, `poc_workload_materializer.py` 89 and host line 164. Observer 199-201 and `poc_registry_plan.py` (21, 26-27, 36, 60-65, 69-71) go to XP-14, with the statement that an XP-14 change to that file is outside the R6-m13 rule; the PROD counterparts of XP-10 and XP-11 are named in PRD §7 and the S4.7 preconditions. | `epics-stories.md:1709-1736,2505-2509,2578-2580`; `architecture.md:1332-1352`; `prd.md:412-433` | `scripts/poc_registry_runner.py:240-245,254-263,266-283`; `scripts/poc_workload_runner.py:40-48,58,90,179,194-195`; `scripts/poc_workload_capabilities.py:22-23,30,32,92,111,130-133,286`; `scripts/poc_workload_admission.py:468,470`; `scripts/poc_workload_images.py:44,68,126,282,349`; `scripts/poc_workload_phase_entrypoint.py:109-116`; `scripts/poc_workload_materializer.py:89`; `scripts/poc_registry_plan.py:21,26-27,36,60-65,69-71`; `scripts/poc_backend_observer.py:188-210,199-201` |
| R7-m4 nobody owns the PROD contract schema | S4.14 owns `schemas/poc-prod-v1.schema.json` (PROD `environment`, account and backend; no `admission`; `scheduled_scaling_suspended` `const: false`; accepts `phase: registry` and `workload`) and the stack dispatch in `poc_contract.py`; `poc-test-v1` is not widened, so the observer's `account_id` `const` read stays. S1.1's PROD B-case moves to S4.14 (N5). S4.7 owns the PROD workload contract PRs (N4). The S4.15 hard-stop test covers `poc-prod.json` (N3, B). | `epics-stories.md:195-201,1677-1696,1882-1885,1921-1929,1945-1948,2483-2494,2531-2533`; `architecture.md:173-190`; `prd.md:212,216,426-427` | `schemas/poc-test-v1.schema.json:162-209`; `scripts/poc_contract.py:17`; `scripts/poc_backend_observer.py:199-201` |
| R7-m5 `post-acceptance` from contract bytes (audit F1) | `workload_route` is derived from the authenticated receipt lineage (S4.11 lookup, complete pagination): `post-acceptance` only with an accepted receipt and no later abandon; the first-deployment `rollback-zero` and the step-7 STOP `policy-update` route `pre-acceptance`. `poc_prepare_source` gains exactly `deployments: read` (test lines 57-62 rewritten). A lookup error fails `poc_prepare_source`. S4.13 B4 and N8; AD-19 and S4.6 step 7 say so. | `epics-stories.md:1428-1446,1494-1496,1611-1615,1641-1645,2073-2078`; `architecture.md:876-880,1279-1292`; `prd.md:216` | `tests/unit/test_poc_source_workflow.py:57-62`; `scripts/poc_phase_source_adapter.py:291` |
| R7-m6 observation records not authenticated (audit F5) | The S4.11 library writes, publishes, authenticates and looks up `poc-workload-observation-v1` records bound to a success receipt (P4, N5); S4.9's duplicate "health-observation evidence schema" item becomes the ownership note (schema S1.1, library S4.11, job S4.13); N8 fixtures come from the S4.11 library. | `epics-stories.md:863-871,989-996,1057-1062,1080-1084`; `architecture.md:1241-1244` | — |
| R7-m7 observation pre-credential steps; credential lists (audit F4, second half) | S4.13 defines the observation job's ten steps modelled on `test_registry_observation` (admit, credential-free wait, admit, `load-aws-ci-env`, admit, `configure-aws-credentials`, observe, upload) and the behaviour when the PR is merged or closed, or its head or base moves, during the wait (the post-wait `admit` fails before credentials; `verify_reviewed_source` requires `OPEN` and the same head and base); a sibling test pins it with the change matrix. `test_ci_guardrails.py` 389-396, `CLOUD_JOBS` and `CASES` gain `test_workload_drift` (S4.13) and `prod_preview`, `prod_apply`, `prod_workload_drift` (S4.14, with a committed contract fixture for the real host `recheck`); the observation jobs are pinned by the sibling test, because those three lists require a host `recheck` and exactly one host `execute`, which the observation job must not have. | `epics-stories.md:1312-1340,1501-1519,1616-1620,1820-1836`; `architecture.md:823-842` | `.github/workflows/self-deploy.yml:601-641`; `scripts/poc_registry_completion.py:103-112,162-166`; `scripts/reviewed_source_admission.py:126-133`; `tests/pulumi/test_ci_guardrails.py:389-409,465`; `tests/unit/test_service_reviewed_credentials.py:18-22,42`; `tests/unit/test_service_execution_workflow.py:9-13,37-40` |
| R7-m8 observation capture vs the drift lock | The capture lists the lock prefix first and retries every 30 s while a lock exists, within the 30-min window, never removing a lock; timeout is `workload-observation-lock-timeout`, a STOP at S4.6 step 7. S4.13 N10, B5. | `epics-stories.md:1341-1353,1621-1623,1646-1647,2073-2082`; `architecture.md:844-851` | `scripts/poc_backend_observer.py:452,470` |
| R7-m9 Drift-role reads for S4.17 | New BI row S5.24 at ordered row 49, after XP-14 and before S4.17, as requested. It holds the read inventory, derived from the existing observer, images and capabilities modules, and grants IAM `GetRole`/`SimulatePrincipalPolicy`, ECR `GetAuthorizationToken`/`BatchGetImage`/`BatchCheckLayerAvailability`/`GetDownloadUrlForLayer` (the last one added from the pre-commit audit), SSM `GetParameter` and ACM `DescribeCertificate`. Deviation from the request: it is unconditional. S5.17 grants none of these reads, so the condition is always true, and a trigger in S4.17 (row 50) would be a forward dependency (pre-commit audit). S4.17's first case checks that the inventory covers every call. | `epics-stories.md:82,2261-2272,2554,2653,2657-2680`; `architecture.md:1405-1409,1515`; `prd.md:214` | `scripts/poc_workload_images.py:77-87,126,206-209`; `scripts/poc_workload_capabilities.py:25-29,37-48,92-94`; S5.17 row (no IAM, ECR, SSM or ACM read) |
| R7-n1 AS-4 lacks D-14 | AS-4 lists D-14 (the STOP on a miss is labelled as the plan's rule, AD-19) and names D-8…D-13. | `brief.md:7,160-165` | `decisions.md` |
| R7-n2 `_inspect_first_result` lines; drift-job rationale (audit F7) | Lines 124-148; the rationale cites the byte-equal pins `test_ci_guardrails.py` 293-297 and `test_poc_registry_workflow.py` 128-132 (line 223 only rejects `always(`). | `epics-stories.md:879,1454-1463`; `architecture.md:1178,1302-1310` | `scripts/poc_workload_runner.py:124-148`; `tests/pulumi/test_ci_guardrails.py:293-297`; `tests/unit/test_poc_registry_workflow.py:128-132`; `tests/unit/test_poc_source_workflow.py:223` |
| R7-n3 `comment_result`; reconciliation docstring | `comment_result` `needs` gain `test_apply_receipt` (S4.11), the three `test_workload_*` jobs (S4.13) and the seven `prod_*` jobs (S4.14), pinned next to `test_poc_registry_completion_workflow.py` 153-156; the `poc_workload_reconciliation.py` docstring (lines 1-7) is in S4.13's doc scope. | `epics-stories.md:948-951,1520-1524,1559-1563,1837-1839` | `.github/workflows/self-deploy.yml:783-797`; `tests/unit/test_poc_registry_completion_workflow.py:153-156`; `scripts/poc_workload_reconciliation.py:1-7` |
| Audit F2 receipt upload fails registry runs | The `test_apply` upload step is guarded by `always() && needs.poc_prepare_source.outputs.phase == 'workload'` and keeps `if-no-files-found: error` like every other upload; the worker and host copies are no-ops without a file; S4.11 B2 and S4.13 B2 assert that the upload is inert on a registry run. | `epics-stories.md:896-911,951-953,998-1002,1635-1637`; `architecture.md:1188-1195` | `.github/workflows/self-deploy.yml:135,274,284,655`; `tests/unit/test_service_execution_worker.py:130`; `tests/unit/test_poc_registry_workflow.py:115` |
| Audit F6 acceptance binds to "latest" | The acceptance job requires the artifact checkpoint to equal the same-run `test_apply_receipt` receipt (run ID and attempt), and that receipt to still be the latest; otherwise STOP and nothing is published. Its `if` also names the TEST workload-phase `up`, so the ancestry test's line 221 holds (pre-commit audit). P2, N7. | `epics-stories.md:1305-1311,1354-1377,1578-1582,1606-1610,2078-2079`; `architecture.md:817-822,862-872` | `.github/workflows/self-deploy.yml:659-697`; `tests/unit/test_poc_source_workflow.py:221` |
| Audit F8 "the gate always runs" | Softened, not reordered: `_validate_safe_preview` (lines 611-613) runs before the gate (614-617), so a protected replace or delete fails closed with the safe-preview message and no field named. Reason: the check is the protected-destruction guard shared by every plan path, and reordering it would change that guard only to improve a message; detection and failure are unchanged. S4.13 N4 gains the case. The round-6 R6-m4 row below is amended. | `epics-stories.md:1398-1413,1589-1594`; `architecture.md:995-1010`; `prd.md:213`; this file (R6-m4 row) | `scripts/run_pulumi_command.py:483-510,592-639` |

**Ordered list (re-verified in revision 7).** 52 rows (0-51): S5.24 is new
at row 49, S4.17 moves to row 50 and S4.7 to row 51. No story depends on a
higher-numbered row, including the test- and ownership-level dependencies
of R7-m4 (the PROD schema is S4.14's, row 39, before S4.15, XP-14 and S4.7)
and R7-m6 (S4.9, row 30, reads observation records through the S4.11
library, row 29, and its N8 fixtures are S4.11-written, so it needs nothing
from S4.13, row 38). S4.14's PROD host tests stub the XP-14 observer
coordinates, and the unstubbed PROD seam case is S4.7's, after XP-14. The
scheduled-drift result schema is S4.15's (row 40), before S4.17 (row 50)
emits it; the projection inputs are in the S1.1 schema (row 2) and the
S4.11 writer (row 29); S5.24 (row 49) holds its own inventory. See
`epics-stories.md:2657-2685`.

**Residual, recorded (not a new risk acceptance).** The TEST workload stack
leaves the baseline scheduled drift at the gate-1 flip, and S4.17 (row 50)
merges after the TEST campaign (row 43), as round 6 decided (S4.17 is a
gate-2b precondition). During the campaign, workload drift is checked by
`test_workload_drift` after every post-acceptance apply (S4.6 step 14), not
nightly. The registry resources of a stack are outside the baseline program
either way (the registry owner's recorded case, S4.13).

## Pre-commit audit of revision 7

A read-only `claude-router:audit` subagent, with fresh context, audited
the uncommitted revision-7 diff against `5cc069c` before the commit. It
could not edit files and ran no make, pulumi or aws command.

- **Result: REFUTED.** It spot-checked more than 40 newly cited source
  lines and found them accurate. It rated R7-m1, m4…m8, R7-n1…n3 and
  F2, F6 and F8 resolved, and R7-M1, R7-M2, R7-m2, R7-m3 and R7-m9
  incomplete.
- **Findings and what revision 7 did:**
  1. (major) The S4.14 PROD host tests would have needed the XP-14 observer
     coordinates (host line 164, observer lines 183 and 188-210). Fixed:
     the PROD cases stub them, every fault depends on the environment, and
     S4.7 owns the unstubbed case after XP-14.
  2. Host test lines 173-178 were missing. Fixed.
  3. The pin table was incomplete. Fixed: new rows for the capture's
     registry check, runner lines 194-195, entrypoint lines 109-116,
     materializer line 89 and host line 164; the `poc_registry_plan.py`
     row is relabelled.
  4. `ecr:GetDownloadUrlForLayer` was missing from S5.24. Fixed.
  5. S5.24 was conditional on a later row. Fixed: S5.24 is now
     unconditional, stays at row 49 and holds the read inventory.
  6. The S4.17 permissions and `GH_TOKEN` were missing. Fixed; the job is
     also in `CASES`.
  7. S4.17 reused PR-bound functions and did not address the contract
     binding. Fixed: S4.17 has its own gate and uses the contract the
     receipt applied (`head_sha` and `blob_sha`).
  8. PROD had a gap in drift detection. Fixed: the PROD job is enabled by
     the PR that first sets `phase: workload`, and the drift check also
     runs before acceptance. The TEST campaign residual is recorded
     above.
  9. The PROD XP-10 and XP-11 counterparts were claimed but not encoded.
     Fixed: they are now in PRD §7 and the S4.7 preconditions.
  10. The Location ranges were wrong. Recomputed.
  11. Nits (the step count, the `repository_dispatch` guard, the
      acceptance `if`, the contract fixture for the PROD recheck, the
      architecture wording and the D-14 wording). All fixed.
- No invented user decision was found.
- **Not yet confirmed:** a recheck of these fixes by the same auditor was
  requested but had not returned when this revision was committed. The
  fixes are therefore unconfirmed by the auditor, and the next
  independent reviewer should check them.

## Round-6 finding → resolution map

Line numbers refer to revision 6. Revision 7 supersedes parts of these rows
(the round-7 map above is authoritative where they differ): R6-M1 (more
pins, R7-M1; the drift-job rationale, R7-n2), R6-m3 (same-run binding,
audit F6; pre-credential steps, R7-m7; lock retry, R7-m8), R6-m4 (the
"always named" claim, audit F8), R6-m5 (more pins, R7-m3), R6-m6 (the
observation record's authentication, R7-m6), R6-m9 (the line citation,
R7-n2) and R6-m11 (the isolated scheduled launch and result record, R7-M2,
R7-m1, R7-m9; the per-stack exclusion, R7-m2; the PROD schema, R7-m4).
"Source" is the repository file and lines each fix was checked against, at
`68584e1` (the workload source is unchanged from the baseline). Every rewrite of a pinned workflow-shape test is a
guardrail change that needs an `APPROVED` review by `@Kravalg`
specifically, recorded with the PR number in the acceptance receipt, as the
round-5 m14 hard-stop amendment is.

| Finding | Resolution | Location | Source checked |
| --- | --- | --- | --- |
| R6-M1 pinned CI-shape tests have no owner; registry-phase regression | Every pinned test is assigned, with its new closed set and the negatives kept. **S4.11:** `test_ci_guardrails.py` 262-273 and `test_trusted_test_controller_workflow.py` 16-26 gain `test_apply_receipt`; `test_poc_source_workflow.py` 214-223 gain it (no `always(`; its `if` is `!cancelled()` plus source success plus `test_apply` success or failure); the credential set is unchanged. **S4.13:** a **separate** `test_workload_drift` job (option 1): `test_post_apply_drift` keeps its `if` and `needs`, so the registry chain is untouched and `test_poc_registry_workflow.py` 128-132 and `test_poc_source_workflow.py` 223 need no relaxation. `test_ci_guardrails.py` 262-273 (three new jobs), 280-306 (exact `if`s; 293-297 byte-equal), 314-319 (`test_workload_drift`, `test_workload_observation`), 347-353 (`test_workload_drift`); `test_trusted_test_controller_workflow.py` 9 and 16-26; `test_poc_registry_completion_workflow.py` 148-151 (the closed `test_workload*` set); `test_poc_source_workflow.py` 196-201 and 214-223; `test_poc_phase_source_adapter.py` 414-416. **S4.14:** the seven `prod_*` jobs in `test_ci_guardrails.py` 98-101, 262-273, 280-306, 314-319 and 347-353; `test_trusted_test_controller_workflow.py` 9 and 16-26; `test_service_execution_workflow.py` 55 and 58; `test_service_initializer.py` 330-336; `test_service_execution_host.py` 173-175; `test_poc_source_workflow.py` 40-50, 196-201 and 214-223; PROD only behind `admission.prod`. **S4.17:** `test_poc_scheduled_registry_workflow.py` 19, `test_ci_guardrails.py` 177 and 347-353. `test_workload_observation` and `test_workload_acceptance` require `needs.test_apply.result == 'success'`. Regression case S4.13 B2: on a registry run with `test_apply_receipt` skipped, the registry chain still runs. The C-runner list names the tests and `scripts/poc_phase_source_adapter.py`. No gate is weakened. | `architecture.md:23,974-986,1088-1096,1132-1140,1196-1239,1376`; `prd.md:213`; `epics-stories.md:846-951,1219-1447,1449-1551,1867-1931,1766-1773` | `tests/pulumi/test_ci_guardrails.py:98-101,177,262-273,280-306,314-319,347-353`; `tests/unit/test_trusted_test_controller_workflow.py:9,16-26`; `tests/unit/test_service_execution_workflow.py:55,58`; `tests/unit/test_poc_registry_completion_workflow.py:16-23,148-152`; `tests/unit/test_poc_registry_workflow.py:128-132`; `tests/unit/test_poc_source_workflow.py:40-50,196-201,214-223`; `tests/unit/test_poc_phase_source_adapter.py:414-416`; `tests/unit/test_service_initializer.py:330-336`; `tests/unit/test_service_execution_host.py:173-175`; `tests/unit/test_poc_scheduled_registry_workflow.py:19`; `.github/workflows/self-deploy.yml:480-483,486-489,572-581,661-667,723-730`; `scripts/poc_phase_source_adapter.py:291` |
| R6-M2 S4.2 uses S4.9 rules before S4.9 | C-contract is S4.10 → S4.11 → S4.9 → S4.2 → S4.3. S4.9 moves before S4.2 in the text and the ordered list (rows 30 and 31); S4.9 follows S4.11, S4.2 follows S4.9, S4.3 follows S4.2. The no-forward-dependency claim is re-verified over all 51 rows (S4.17 added as row 49). | `architecture.md:1374`; `epics-stories.md:716-722,956-958,1036-1038,1104-1106,2052-2054,2075-2083` | — |
| R6-m1 D-14 labels | RPO ≤ 1 hour and RTO ≤ 24 hours are labelled user decision D-14 in AD-19, FR-30, S4.8, this file and `run-summary.md`; the "unchanged in revision 5" wording is corrected; D-14 is in the PRD §6 table, the front-matter decision ranges (PRD, architecture, epics, brief), the epics inventory and ordered row 0. Only the 20% threshold and the PROD justification rule stay planning defaults (NFR-11). | `architecture.md:7,856-875`; `prd.md:7,211,248,327`; `epics-stories.md:7,17-23,1850-1854,2023`; `brief.md:7`; `decisions.md:14`; this file; `run-summary.md` | `decisions.md` (commit `68584e1`) |
| R6-m3 acceptance job has no AWS credentials | `test_workload_observation` captures the checkpoint through the trusted observer (preview role) and writes it into its artifact; `test_workload_acceptance` verifies that artifact, like the registry proof. The observation job "runs no Pulumi command and holds no state lock". | `architecture.md:794-835`; `epics-stories.md:1230-1270,1408,1430` | `.github/workflows/self-deploy.yml:570-657,659-690`; `scripts/poc_backend_observer.py:419-470` |
| R6-m4 drift dispatch not implementable | The registry plan-plus-gate pattern is reused: `drift` captures with operation `plan` (the only other accepted one is `up-plan`) and dispatches `_dispatch_command("plan")`, whose `_run_plan_command` supplies the plan path and the JSON preview; the gate runs `validate_drift` on every completed plan, and since `plan` has no `--expect-no-changes`, the drifted field is named (amended in revision 7, audit F8: a protected replace or delete fails closed earlier with the safe-preview message, without the field). No `workload-drift` invocation is added. V-13 is restated for the `plan` invocation. | `architecture.md:23,940-966,1063-1066,1513`; `prd.md:213,290`; `epics-stories.md:329,1223-1226,1271-1297,1417-1420,1766-1773` | `scripts/run_pulumi_command.py:592-639,816-839`; `scripts/_pulumi_command_support.py:50-72,159-162,180-190`; `scripts/poc_backend_observer.py:181-185`; `scripts/poc_registry_runner.py:344,364`; `scripts/service_execution_host.py:27-31`; `scripts/service_execution_worker.py:128-132` |
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
  owns the trusted observer's PROD coordinates (including the schema read
  at lines 199-201), the TEST registry constants of
  `scripts/poc_registry_plan.py`, and the committed
  `specs/poc/poc-prod.json`, which must validate against the S4.14 PROD
  schema (R6-m5, R6-m11, R7-m3, R7-m4).
- **PROD counterparts of XP-10 and XP-11 (R7-m3).** The PROD gateway
  certificate parameter and the PROD permissions-boundary path are recorded
  with their owners and pinned in S4.14; gate 2a refuses PROD without
  them.

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
  S4.13 `test_workload_drift`, routed by the authenticated receipt lineage;
  the per-stack scheduled-drift exclusion; S4.17 scheduled workload drift
  in the isolated worker container before gate 2b, with a `checked` result
  record)
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
