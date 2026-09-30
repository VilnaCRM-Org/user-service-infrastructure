---
artifact: implementation-readiness
workflow: _bmad/bmm/workflows/3-solutioning/bmad-check-implementation-readiness (Validate mode)
task: workload-wa-hardening
source_baseline: 66776772979956de9c5abdbee7c45641a1b533fa (workload source); bundle parent 9b17199 (revision 10)
date: 2026-09-30
revision: 11
author: the planning agent that wrote revision 11 (NOT an independent reviewer)
independent_reviewer: none yet for revision 11
status: PENDING independent review of revision 11
---

# Implementation readiness

## Verdict

**PENDING. Not PASS.** The author of revision 11 wrote this file. It records
what changed and the repository source each fix was checked against. It does
not grade itself.

- Only an independent reviewer's PASS satisfies the planning gate.
- Revision 11 answers independent readiness round 11 against `9b17199`
  (FAIL: 1 major, R11-M1; 4 minor, R11-m1…m4; 4 nits, R11-n1…n4). It
  adds no user decision. The route for R11-M1 (independent
  CloudFormation owners for every new IAM principal) is a design choice
  within the existing decisions, given as the coordinator's direction
  and recorded below with its rationale.
- A fresh-context, read-only audit of the revision-11 changes ran before
  the commit, and a recheck by the same auditor after its findings were
  folded in; both are recorded in "Pre-commit audit of revision 11"
  below. They are author-side checks, not the independent review.
- Revision 10 answered independent readiness round 10 (FAIL: 1 major,
  R10-M1; 2 minor, R10-m1 and R10-m2; 6 nits, R10-n1…n6) and applied the
  new user decision D-15 (2026-09-30: the gateway certificate ARN is
  pinned in the reviewed USI contract; no CI role reads SSM).
- A fresh-context, read-only audit of the revision-10 changes ran before
  the commit, and a recheck by the same auditor after its findings were
  folded in; both are recorded in "Pre-commit audit of revision 10"
  below. They are author-side checks, not the independent review.
- Rounds 5 to 11 ran after round 5 was recorded as the last allowed
  round. Whether another independent round runs is for the coordinator
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
| 6 | independent reviewer (relayed by the coordinator) | FAIL: R6-M1, R6-M2, R6-m1, R6-m3…m14 | revision 6 |
| 7 | independent reviewer (relayed by the coordinator), plus a fresh-context audit of revision 6 | FAIL: R7-M1, R7-M2, R7-m1…m9, R7-n1…n3; audit F1…F8 (F2, F6, F8 new) | revision 7 |
| 8 | independent reviewer (relayed by the coordinator), plus the recheck of the revision-7 pre-commit audit | FAIL: R8-M1, R8-m1…m7, R8-n1…n4; recheck residuals A1…A4 | revision 8 |
| 9 | independent reviewer (relayed by the coordinator) | FAIL: R9-M1, R9-m1, R9-m2, R9-n1…n4 | revision 9 |
| 10 | independent reviewer (relayed by the coordinator), against `8e097aa` | FAIL: R10-M1, R10-m1, R10-m2, R10-n1…n6; the coordinator relayed user decision D-15 with it | revision 10 |
| 11 | independent reviewer (relayed by the coordinator), against `9b17199` | FAIL: R11-M1, R11-m1…m4, R11-n1…n4; the coordinator gave the design direction for R11-M1 (independent CloudFormation owners) | revision 11 (this file) |

## User decisions (all explicit, dated 2026-09-30)

`decisions.md` is the source. Commit `68584e1` added D-14 after revision
5; revision 6 changed only the label of the D-14 row; revisions 7, 8 and 9
did not change `decisions.md`. **Revision 10 adds D-15**, a user decision
the user gave in chat on 2026-09-30, answering the coordinator's
question: the gateway certificate ARN is pinned in the reviewed USI
workload contract and checked only with `acm:DescribeCertificate`; no CI
role (Preview, Apply or Drift; TEST or PROD) gets any `ssm:GetParameter`
read, and no identity deny, seed guard, seed boundary or catalog hash is
loosened for SSM. The rationale the user accepted: ACM managed renewal
keeps the same ARN, so a reviewed USI PR is needed only if the
certificate is replaced. Every decision is resolved, and none is a
default: D-1…D-7, D-14 and D-15, and the derived details D-8…D-13 that
the user confirmed the same day. XP-14 (the PROD registry) is still an
open ownership item that blocks gate 2, and XP-15 and XP-16 (the PROD
counterparts of XP-10 and XP-11) block gate 2a.

- **D-14 is a user decision (R6-m1):** DocumentDB RPO ≤ 1 hour and RTO ≤ 24
  hours for TEST and PROD. A measured miss is a STOP at gate 2a for a new
  user decision; no default relaxes D-14.
- **D-15 is a user decision (revision 10):** recorded in `decisions.md`
  row D-15, PRD §6, the front matter of the PRD, architecture, epics and
  brief (D-1…D-15), brief AS-4, the epics inventory and ordered row 0.
- **Revision 11 adds no user decision.** `decisions.md` changes only in
  D-15's note text (R11-n3: option (a)'s seed amendment applies "if the
  boundary holds the exact ARN"); the user's wording is unchanged.
- **The R11-M1 route is a design choice, not a user decision.** The
  coordinator directed the independent-CloudFormation-owner route, the
  precedent bootstrap-infrastructure itself set in #285 (a
  publisher-only seed stack with its own reviewed template, `Retain`
  resources, a permanent deny-update stack policy, a post-create verifier
  and a reviewed amendment path). It stays within NFR-06 and D-15: no
  guard's Resource-`*` deny is narrowed, no CI role gets `iam:CreateRole`
  or `iam:CreateServiceLinkedRole`, and every new principal still needs a
  reviewed template, a human non-root installer, change-set evidence, a
  post-create verifier and `@Kravalg`'s approval. The alternative, the
  governor-guard route (narrowing `8f75c4a5…` or `dc27f076…`, widening
  `8c068aaa…`, or adding `iam:CreateRole` to `01dcac0c…`), narrows
  Resource-`*` denies; it would need a user decision amending NFR-06 and
  is not chosen (architecture AD-26 layer 6).
- **Planning defaults, not user decisions:** only the 20% TEST cost forecast
  threshold and the rule that every PROD increase is justified (NFR-11,
  m17). The user may change them.

## Round-11 finding → resolution map

Line numbers refer to revision 11 as committed. "Source" is the
repository file and lines each fix was checked against: USI at
`9b17199` (the workload source is unchanged from the baseline); BI
`origin/main` through the worktree `wt-boot-urllib3` (`862b4bf`, whose
`pulumi/` tree equals `origin/main`); #284 through `wt-boot-pr280`
(`e85534c`); and #285 through `wt-boot-219` (`54e9e2f`). All reads were
`sed`, `grep`, `git log`, `git diff --stat`, `git merge-base` and
read-only Python evaluations of the catalogs; nothing was fetched,
checked out or executed. TEST catalog lines are `test.json`; PROD has the
same entries at the same lines in `prod.json` (statement hashes that
embed an account differ and are named where cited).

| Finding | Resolution | Location | Source checked |
| --- | --- | --- | --- |
| R11-M1 no plan to create the new IAM principals | **AD-26 layer 6** names every guard that stops it: `8f75c4a5…` (Deny `iam:CreateRole`, `iam:CreatePolicy*`, `iam:PutRolePermissionsBoundary` on `*`) in the platform apply, `PulumiAutomation` and `PulumiDeploy` guards; `94cec98a…` and `4fae8daf…` in the platform apply guard; `dc27f076…` (Deny `iam:CreateRole`) and `8c068aaa…` (`iam:*` outside the USI CI set) in `G-GitHubGovernanceApply`, `dc27f076…` also in the USI Apply guard; and `01dcac0c…`, whose `NotAction` list lacks `iam:CreateRole`. **Route (coordinator direction; design choice, not a user decision):** an independent CloudFormation stack per role family, as #285 did for the publisher: a reviewed template and hash, `Retain` resources, a permanent deny-update stack policy, a human non-root installer named in the PR, a CREATE change set with exactly the reviewed `Add` rows as evidence, a post-create verifier like `verify_publisher_stack`, and `@Kravalg`'s approval; every later grant is a reviewed stack amendment with a post-update verifier. Stacks: ECS runtime (TEST, PROD), function roles (TEST, PROD), restore and exercise (TEST, trust only, because S5.4's key policy names the exercise role and S3.3's endpoint policy binds the reader) by S5.1; recovery by S5.7 and S5.19; S5.4, S5.23, S5.18a and S5.5 are amendments. **TEST ECS single owner: S5.1**, adopting #219's names and `propose_pass_role` fragments; it does not defer to #219's later runtime amendment, because that amendment amends the governor's identity, boundary and guards (the route not chosen) and no story owns it; the preflight requires both names absent and `PocRuntimeRoles` unregistered. S5.2 applies all of `propose_pass_role` on S5.1's ARNs (the Apply allow and deny statements, and the Preview and Drift `DenyReadRolePassRole`), so the Preview, Drift and Apply guard hashes change and guard rows pin the baseline catalog. **Functions live in the stack that owns their role** (S5.3 adds the three functions to the function-role stacks, S5.18a the reader to the restore stack; S5.5 and S5.18b add the Lambda network-interface grant and `VpcConfig` by amendment), because the platform appliers' `4fae8daf…` denies `iam:PassRole` on those roles and NFR-06 does not allow narrowing it while this non-weakening design exists. **The governor-guard route is not chosen and would need a user decision amending NFR-06.** Guard-layer rows compare with the story's baseline catalog. Evidence rows: `iam:CreateRole` denied to every CI applier; each applier limited to exact role and policy ARNs; the USI-role rows are simulated by the Preview role (S4.6 step 3, S4.7), and the BI-role rows come from BI PR evidence run with a BI identity, because they are outside the Preview role's simulate grant. **#284 and #285 facts corrected** (R11-n1 row). **Serialization:** one seed operation (catalog amendment, stack install or stack amendment) open at a time, each with its row. NFR-06 and FR-27 name the route. | `architecture.md:43-44,52-53,216-220,456-458,538-541,558,1613,1769-1776,1831-1843,1938-2145,2179-2246,2278-2317,2318-2339,2351,2462-2476`; `prd.md:208,245,357-361,472-487,517-534,589-610`; `epics-stories.md:2491-2493,2500-2501,2515-2520,2640-2654,3381-3391,3530-3557,3558-3609,3614-3628,3688-3727,3734-3755,3788-3805` | BI `origin/main` `pulumi/seed/catalogs/test.json:575-598,599-614,629-648,649-663,801-809,978-1015,1671-1701,2483-2492,2493-2508,2915-2931,2944-2975,3000-3020,3815-3829` (PROD `prod.json` entries at the same lines; `9fb811f6…` line 3061, `06267ab9…` line 1767, `473c8904…` line 2264); `pulumi/seed/poc_pass_role.py:1-5,16-19,42-94`; `pulumi/infra/poc_runtime_enrollment.py:112-135`; `test.json:712-761,843-852,2411-2439,3273-3299` (the Preview and Drift guards with `ae950d73…`, the operator `iam-write` guard with `455fe8d0…`); `prod.json:3208` (`a9609b86…`), `prod.json:2487` (`6227eeae…`); the guard sets that hold `4fae8daf…`; a grep of BI `pulumi/` and `scripts/` for `poc_runtime_enrollment` (no importer); `wt-boot-219`: `specs/219-test-workload-capability/runtime-enrollment.md:12-16,26-30,51-65,95-113,125-139,196-302,315-322,358-363`, `pulumi/seed/poc_runtime_fence_stack.py:98-99,113-114,165-166`, `pulumi/seed/poc_publisher_stack_verification.py:197` |
| R11-m1 the five changes for a new managed policy | Listed in full, as #219's amendment makes them: (1) the governance Preview ceiling's and (2) the governance Drift ceiling's policy-read statement (`339af045…` on `origin/main`); (3) `G-GitHubGovernanceApply`'s `iam:*` statement (`8c068aaa…`; `21195ff8…` after #284; PROD `9fb811f6…`); (4) its policy-write statement (`5366ec11…`; `bb116727…` after #284; PROD `06267ab9…`); (5) `_managed_policy_resources`. Plus the seed attachment rule. The guard is named `G-GitHubGovernanceApply` everywhere; the USI Apply guard has no policy-write statement. The Preview/Drift inline-overflow fallback (a new managed policy) now needs the same five changes, a write-scope resolution of its own and the role's `attachment_arns`. | `architecture.md:1885-1937`; `prd.md:561-588`; `epics-stories.md:2536-2542,3503-3529` | `wt-boot-urllib3` `pulumi/seed/test_poc_prerequisite_amendment.py:17-40,114-145` (identical in `wt-boot-219`); `pulumi/infra/governance_automation.py:480-489`; `test.json:415-434,435-454,599-614,649-663,2251`; `wt-boot-pr280` `test.json` (`G-GitHubGovernanceApply` template `b6d1a587…`) |
| R11-m2 service-linked roles | S5.2's `iam:CreateServiceLinkedRole` branch is removed: `05f77e26…` denies it outside budgets, guardduty and securityhub in the USI Apply guard (line 658) and every BI applier guard. The five SLRs' existence is a read-only `iam:GetRole` precondition of S4.6 step 1 (a missing one is a STOP). The creator of a missing one is the independent-owner route: an `AWS::IAM::ServiceLinkedRole` in a seed stack of that account, installed by the human non-root installer first in row 8 (S5.1). | `architecture.md:456-458,2462-2476` and the layer-6 stack table (2023-2031); `epics-stories.md:2586-2596,2603,3614,3615`; `prd.md:245` | `test.json:649-663,1767-1780` (and the guards' `statement_ids`; `prod.json:1753`) |
| R11-m3 test-level forward dependency | S4.10 now unit-tests `_task_execution_inputs` (a directly built projection; ARM64 accepted for `linux/arm64`, `X86_64` rejected, and the reverse) and asserts that the end-to-end ARM64 path fails closed at the entrypoint's line-59 pin (`validate_first_workload_topology` → `_checked` → `project_workload_phase` → `_images`). The positive end-to-end ARM64 fixture moves to S4.14, which widens that pin and replaces S4.10's fail-closed assertion. The ordered-list note and this file's R10-n6 row and ARM64 residual are corrected. | `epics-stories.md:853-873,2009-2025,3719,3734-3755` (S4.10, S4.14, row 39 and the note); this file (R10-n6 row, "ARM64 before S4.14" residual) | `scripts/poc_workload_topology.py:18,365-371,814-839`; `scripts/poc_workload_phase_entrypoint.py:52-59,96-123,126-133`; `tests/unit/test_poc_workload_topology.py:166-170,275-280` |
| R11-m4 ARM64 publisher platform source | Both revision-10 branches are withdrawn with their reasons (the release block is unreachable at dispatch; a "reviewed dispatch input" has no carrier). The source is a committed, schema-validated optional contract field `publish_platform` (S4.14, TEST schema; absent means `linux/amd64`; in a workload contract it must equal `release.platform`), changed only by a reviewed USI contract PR, never `client_payload`. `poc_prepare_source` exports it, the dispatch job's job-level `env` (lines 739-748) carries it to both the `prepare` (760-762) and `dispatch` (774-781) steps, and `prepare()` checks it against the authenticated contract. Tests: arm64 and absent values, an out-of-enum value, an environment/contract mismatch, the `prepare` and `dispatch` requests equal, no `client_payload` read. Cross-repo precondition: the user-service publisher accepts arm64 (S5.14, row 24). | `epics-stories.md:2036-2089,3719` (row 39) | `.github/workflows/self-deploy.yml:1-8,40-53,60-80,721-781`; `schemas/poc-test-v1.schema.json:440-455,815-840` (top-level keys, `additionalProperties: false`); `scripts/poc_publisher_dispatch.py:143-175,211-217,261-271`; `tests/unit/test_poc_publisher_dispatch.py:128` |
| R11-n1 #284/#285 facts | "Not verified locally" is replaced by the verified facts: #284 carries the only #219 catalog change (TEST pin `ff2eaf29…`; TEST boundary 11 statements, template `805998b5…`; `-poc-prerequisites` in `policy_registry.py` lines 542-546; capability `"state": "enabled"`); #285 contains #284 and changes no catalog file, catalog hash or `policy_registry.py` line; PROD is unchanged (`d4b56073…`). #284 is the external precondition of row 8. | `architecture.md:2179-2246`; `prd.md:589-610`; `epics-stories.md:3558-3609,3788-3805`; this file's R10-m2 row | `wt-boot-pr280` and `wt-boot-219` `pulumi/seed/policy_registry.py:18-21,540-548`, `pulumi/infra/test-poc-identity.json:11`, `pulumi/seed/catalogs/test.json:307-322`; `git merge-base --is-ancestor e85534c 54e9e2f`; `git diff --stat e85534c 54e9e2f` over the catalogs, `policy_registry.py` and the identity file (empty); `git diff --stat 862b4bf e85534c` (three files) |
| R11-n2 S5.2's TEST baseline | The post-#284 TEST boundary (11 statements, template `805998b5…`, 2894 characters, measured like the `origin/main` 1235) is S5.2's TEST baseline; catalog entries are cited by template and statement hash. | `architecture.md:2146-2178`; `prd.md:542-545`; `epics-stories.md:3558-3576,3615` | `wt-boot-pr280` `pulumi/seed/catalogs/test.json:307-322` |
| R11-n3 D-15 option (a) | "if the boundary holds the exact ARN" added to option (a) (note text only; the user's wording is unchanged). | `decisions.md:15`; `prd.md:459-471`; this file (pre-commit audit 10 finding 6, its recheck item 2, and "Surfaced for the user") | — |
| R11-n4 layer count | "Four layers" becomes six: identity allows, identity denies, the boundary, the seed guard, the seed attachment constraint, and the new seed principal-creation authority. | `architecture.md:1769-1776`; `prd.md:485-487`; `epics-stories.md:2500-2501`; this file (skill applicability); `run-summary.md` checklist | — |

**Ordered list (re-verified in revision 11).** Still 53 rows (0-52); no
row is added or moved. Rows 8-11, 13, 33, 34, 42, 43, 45 and 47 name
their seed operations, and row 39 names the `publish_platform` field and
the end-to-end ARM64 fixture. Every new role is created in row 8 (or in
its own row: S5.7 row 34, S5.19 row 47) before any row passes it or
grants on it (rows 9, 11, 13, 33, 42, 43, 45); every seed operation's
baseline comes from a lower row; #284 is the external precondition of
row 8's first operation. Test level (R11-m3): S4.10 (row 28) no longer
needs S4.14 (row 39) for a passing fixture. S4.14 depends on S5.14 (row
24) for the publisher's arm64 support. No story depends on a
higher-numbered row. See `epics-stories.md:3676-3838`.

**Residuals recorded in revision 11 (not new risk acceptances).**

- **Stack amendments in the live campaign (R11-M1).** S5.5's
  bootstrap-job grant, network-interface grant and `VpcConfig` are a
  function-stack amendment by the human installer in S4.6 steps 5-6 and
  again after the step-20 rebuild (only the secret ARN changes then);
  S5.18b's reader attach (step 5), `VpcConfig`-only detach (step 18) and
  `VpcConfig` re-attach (step 20) are restore-stack amendments. The
  network-interface grant stays for the life of the function (recheck N1);
  if V-19 selects the ephemeral reader grant, S4.8 adds and removes it
  the same way. Each is a human step with its own evidence; none is a CI
  path.
- **Functions in the stacks (R11-M1).** Every function that runs as an
  S5.1 role lives in that role's stack, so no platform applier's
  `iam:PassRole` guard changes. The cost: every function code or
  `VpcConfig` change (S5.3, S5.5, S5.18a, S5.18b, including the S4.6
  step-18 `VpcConfig` detach and step-20 re-attach) is a human stack
  amendment with its own evidence. A second cost of the same route: the
  exercise and restore roles are created trust-only in S5.1, and their
  grants arrive by later amendments.

## Pre-commit audit of revision 11

A read-only `claude-router:audit` subagent, with fresh context, audited
the uncommitted revision-11 diff against `9b17199` before the commit, then
rechecked the fixes. It could not edit files and ran no make, pulumi or aws
command.

**First pass: REFUTED (2 major, 3 minor, 3 nits).** Findings (all eight
were fixed in revision 11):

1. (major) Live principal-creation rows outside the Preview simulate grant.
2. (major) S5.3 narrowing `4fae8daf`.
3. (minor) The shared `4fae8daf` scope.
4. (minor) S5.2 omitting #219's read-role PassRole denies.
5. (minor) Lambda network-interface grants missing (the recheck, N1 below,
   then corrected their scope and lifecycle).
6. (nit) The exercise KMS row with two owners.
7. (nit) Citation errors (`ae950d73`, `455fe8d0`, `PocRuntimeRoles`, the
   human installer credit).
8. (nit) The Remove rows, the PROD hash counterparts, the row 10 marking
   and XP-1.

**Recheck: REFUTED.** All eight first-pass items were confirmed fixed; it
found three new items, now folded in:

- **N1 (major): the Lambda network-interface grant was under-scoped,
  incomplete and removed too early.** The AWS Lambda guide ("Giving Lambda
  functions access to resources in an Amazon VPC",
  <https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc.html>,
  read through the aws-knowledge MCP) lists six actions on
  `"Resource": "*"`: `ec2:CreateNetworkInterface`,
  `DescribeNetworkInterfaces`, `DescribeSubnets`, `DeleteNetworkInterface`,
  `AssignPrivateIpAddresses`, `UnassignPrivateIpAddresses`. The plan had
  five, scoped to subnet ARNs, and dropped `DescribeSubnets`. The page
  names no EC2 condition key that narrows them (its `lambda:VpcIds`,
  `lambda:SubnetIds` and `lambda:SecurityGroupIds` constrain the caller of
  `CreateFunction` and `UpdateFunctionConfiguration`), so no condition was
  adopted. Fixed: the documented set on `*` is an explicit NFR-06
  exception ("no resource scope exists for these actions", like
  `iam:SimulateCustomPolicy` and the `acm` read), recorded in PRD NFR-06
  and AD-26; it is bounded by the `lambda:SourceFunctionArn` deny the same
  page recommends. **Lifecycle choice: the grant stays for the life of the
  function and the detach removes only `VpcConfig`,** because Lambda
  deletes an unused ENI with the creating function's execution role (up to
  20 minutes per the page; the plan polls up to 45). S5.18b's detach
  acceptance, S5.5, the S4.6 ordered row 43 text and the step-18 STOP
  (an ENI remains after 45 minutes, or the grant was removed before the
  read-only `DescribeNetworkInterfaces` check on the XP-8 subnets passed)
  are consistent with this.
- **N2 (nit):** architecture.md said PROD `prod.json` has the same entries
  at the same lines. Fixed: the guard entries are the same, but the
  statement lines differ (PROD `a9609b86` 3208 against TEST `94cec98a`
  3000; `06267ab9` 1767 against 2493; `9fb811f6` 3061 against 2915).
- **N3 (nit):** S5.3 and row 13 did not state the full order. Fixed: BI CI
  log groups, then the stack amendment that creates the functions, then BI
  CI Lambda permissions and the `RotationSucceeded` rule.

**Coordinator design choice, not a user decision.** The independent
CloudFormation-owner route for new IAM principals and for the functions
that run as them (AD-26 layer 6) is the coordinator's design choice made to
avoid narrowing any seed guard. No user decision is taken or needed, and
none is recorded in `decisions.md`.

**Trade-offs recorded.** (1) Every Lambda function and `VpcConfig` change
becomes a human stack amendment. (2) The exercise and restore roles are
created trust-only in S5.1, because S5.4's key policy and the S3.3 endpoint
policy name them, and their grants arrive by later amendments. The ordered
list is unchanged (53 rows) and no story depends on a higher-numbered row.

## Round-10 finding → resolution map

Line numbers refer to revision 10 as committed. "Source" is the
repository file and lines each fix was checked against: USI at
`8e097aa` (the workload source is unchanged from the baseline), and BI
`origin/main` `bea5252` read in the worktree `wt-boot-urllib3` (branch
`fix/urllib3-2.8.0-cves`, `862b4bf`, whose only change against
`origin/main` is `uv.lock`, so its `pulumi/` tree equals `origin/main`),
plus the unmerged #219 worktree `wt-boot-219` at `54e9e2f` for
comparison. Nothing was fetched, checked out or executed. Findings of
the pre-commit audit are cited as "audit <n>".

| Finding | Resolution | Location | Source checked |
| --- | --- | --- | --- |
| D-15 (user decision, 2026-09-30) | Recorded with the user's wording, date and accepted rationale in `decisions.md` and PRD §6, and in every decision range (D-1…D-15) and list. **Code owner: S4.14** (the one editor of the capabilities module, holding the C-runner and C-contract slots at row 39): the TEST schema requires `certificate_arn` and drops `certificate_parameter_name`; the PROD schema has only `certificate_arn`; the runner rule becomes `workload-certificate-arn-required`; the SSM read path and the `("ssm", "get-parameter")` operation are removed; the receipt's certificate observation is narrowed to `null`; the pinned runner, contract, capabilities and entrypoint tests and `specs/poc-workload-runner.md` (8-17, 110-113), `specs/poc-api-gateway-backend.md` (30, 41-60) and `docs/poc-workload-admission.md` (104-111) are updated. Revision 9's `certificate=` reader parameter is withdrawn. **XP-10 and XP-15 rewritten:** the gateway owner supplies the ARN, a reviewed USI contract PR pins it (TEST: the gate-1 PR, S4.6 step 1; PROD: S4.7's contract PR), a replacement needs a new contract PR, and until it merges PR plans and scheduled drift fail closed on the ACM check (operating residual). **AD-26, XP-11 and S5.24a/S5.24b rewritten:** every `ssm:GetParameter` carve-out is removed; the only allows are `iam:GetRole`, `iam:SimulatePrincipalPolicy` (execution role only for Apply and Drift), the three ECR pull reads and `acm:DescribeCertificate`, which no deny or guard blocks; `DenySecretLeakingReads`, `DenySecretLeakingReadsApply` and every seed guard statement are unchanged; negative matrix rows prove `ssm:GetParameter` denied for every role. **S4.17** takes the ARN from the contract its success receipt applied. From the pre-commit audit: S4.14's test and doc list is completed (audit 5); the replacement residual is corrected (the grant update, a possible seed amendment, S4.17's applied-contract window, ACM's in-use rule), and its gap with D-15's rationale is surfaced to the user (audit 6); D-15 joins the gate-1 decision lists (audit 10). | `decisions.md:15`; `prd.md:7,212,214,245,295,330,412-468,469-585,630-659`; `architecture.md:7,928-932,1145,1187,1352,1443,1492,1521-1524,1605-2007`; `epics-stories.md:7,17-23,27,83,85,96,171,1844,1908-1994,2056,2271-2282,2437-2498,2527-2539,2549-2573,2802-2811,2998-3017,3042-3048,3190-3201,3256-3262,3281-3304,3446-3447,3458,3511,3550,3560`; `brief.md:7,163-168` | `scripts/poc_workload_runner.py:170-178`; `scripts/poc_workload_capabilities.py:30-34,37-47,243-266,269-292,295-319,322-346`; `scripts/poc_workload_admission.py:455-475`; `scripts/poc_workload_phase_entrypoint.py:96-123,226-231`; `schemas/poc-test-v1.schema.json:508-527`; `specs/poc-workload-runner.md:8-21,110-113`; `specs/poc-api-gateway-backend.md:30,41-60`; `docs/poc-workload-admission.md:104-111`; `tests/unit/test_poc_workload_runner.py:18-25,52-56,224-242,316-321`; `tests/unit/test_poc_contract.py:325-333`; `tests/unit/test_poc_workload_capabilities.py:320,333,371-459`; `tests/unit/test_poc_workload_phase_entrypoint.py:40-107` |
| R10-M1 seed-owned IAM layers | **AD-26 now names four layers** for each USI CI role: identity allows (new, USI-scoped), identity denies (unchanged), **seed guard: unchanged**, and the **seed-owned permissions boundary**. The guards (TEST Preview and Drift statement `ae950d73…`, Apply `9f269660…`; PROD Preview and Drift `ae950d73…`, Apply `ce12c400…`) deny `ssm:GetParameter*` and `ecr:GetAuthorizationToken`; with D-15 and the token-free image read no guard narrowing is needed, and a computed check over the catalogs shows that no guard statement matches the remaining allows except the seed-resource-only `d413d73a…`/`aec83856…`. The token fallback would also have to narrow the guards, which stays a user decision amending NFR-06. Guard-layer rows are in the XP-11, S5.24a and S5.24b matrices (and S4.6 step 3, S4.7). The boundary is an `existing_capability_boundary` in the seed catalog, with hashes pinned in `policy_registry.py`, so **every boundary addition goes through a seed catalog amendment** with a new catalog hash pin, a named seed owner, CloudFormation change-set evidence and `@Kravalg`'s approval. The Epic 5 boundary rule and AD-26 no longer locate the boundary only in `governance_automation.py`. From the pre-commit audit: the boundary also bounds the ConfigRead roles, with ConfigRead rows in the matrices (audit 4); the seed's attachment constraint on the Apply role is AD-26 layer 5, with the Preview and Drift allows in the existing inline documents, the TEST Apply allows in `-poc-prerequisites`, the seed code, write-scope and guard changes for any new Apply managed policy, and `verify_active_enrollment` rows (audit 1); S5.2's amendment covers S5.5's later grant (audit 3). | `architecture.md:1632-1667,1761-1875,1944-2003`; `prd.md:469-585,628`; `epics-stories.md:2437-2498,2549-2573,3281-3304,3350-3441,3446,3458` | BI `origin/main`: `pulumi/seed/catalogs/test.json:307-319,649-663,712-761,3102-3118,3273-3299,3667`; `pulumi/seed/catalogs/prod.json:307-319,649-663,712-725,747-760,3277-3303,3325,3711-3727`; `pulumi/seed/policy_registry.py:18-21`; `pulumi/seed/test_poc_prerequisite_amendment.py:1-5,20-40,58-72` (prepared by #274, `1ed394d`; identical in `wt-boot-219`); `pulumi/infra/governance.py:98-109,212,266-271,414-475,486-497`; `pulumi/infra/governance_automation.py:422-455,480-489`; `pulumi/infra/ci_bootstrap.py:132-145,153-166,634-663,770-773,814-842`; `pulumi/seed/policy_registry.py:532-551,554-591`; `pulumi/seed/test_poc_prerequisite_amendment.py:135-144`; `wt-boot-219` `pulumi/seed/policy_registry.py:542-546`; the catalog `principals` bound by each boundary |
| R10-m1 boundary size | The boundary is one policy of at most 6144 characters, shared by Preview, Apply, Drift and the ConfigRead roles (audit 4; today about 1.2 thousand: TEST 1235, PROD 1240, computed over the catalog statements), so "copy every allow exactly" will not fit. Each story that adds boundary content records the rendered size in its seed amendment (S5.2, S5.17, S5.4, XP-11, XP-14's addition, S5.24a, S5.24b). The fallback form is a service or resource-family ceiling in the boundary, approved in the seed review, with the exact allows kept in the identity policies, as BI's `platform_control_boundary` does. S5.2's several managed policies are noted. | `architecture.md:1876-1901`; `prd.md:520-543`; `epics-stories.md:3350-3441,3446-3447,3458` | `pulumi/infra/governance_automation.py:185-194`; `pulumi/seed/test_poc_prerequisite_amendment.py:69-72`; `pulumi/infra/platform_iam.py:642-645` |
| R10-m2 seed amendment conflicts | Every amendment pins baseline and result hashes, so they are serialized in C-BI order, one open across both catalogs (recheck N2): #219's own amendment (revision 11, R11-n1, verified read-only: #284 carries the only #219 catalog change, the TEST prerequisite activation, and #285 changes no catalog hash) → S5.2 → S5.17 → S5.4 (rows 9-11) → XP-11 → XP-14's PROD addition → S5.24a → S5.24b. XP-11's BI identity change and seed amendment take the C-BI slot in **row 42, after S5.18a and before S4.6 (row 43)**; no row is added. No forward dependency: XP-11 reads only the catalog left by rows 9-11, and its matrix asserts only Drift denies. | `architecture.md:1902-1925,2015`; `prd.md:563-572`; `epics-stories.md:3350-3441,3553,3559,3561,3565-3643` | `pulumi/seed/test_poc_prerequisite_amendment.py:32-40` |
| R10-n1 gate effect of a rejected S5.24b | The R9-M1 (d) and R9-m2 rows below, the "Remaining user decisions" table and the architecture C-runner row now say that a rejected S5.24b stops S4.17 and therefore gate 2a (recheck N1), not "gate 2b", "gate-2b precondition only" or "gate 2a unaffected" (audit 7). | this file (R9-M1 (d) and R9-m2 rows; "Remaining user decisions"); `architecture.md:2019` | `epics-stories.md:3458` (S5.24 row, rejected-S5.24b sentence) |
| R10-n2 FR coverage | FR-31 lists XP-11 (gate 1) and S5.24a (gate 2a); FR-33 lists XP-11, S5.24a and S5.24b. | `epics-stories.md:83,85` | — |
| R10-n3 renderer scope | The new identity statements render for the USI identity only (`_governance_policy_documents` renders every enrolled repository). With D-15 the deny documents do not change at all, including `_apply_secret_deny_document`, which also renders the platform apply role's document. Renderer-scope rows prove that other repositories' and the platform roles' documents stay byte-identical. | `architecture.md:1767-1780,1968-1974`; `prd.md:479-507`; `epics-stories.md:2448-2461,3458` | `pulumi/infra/governance.py:414-475`; `pulumi/infra/ci_bootstrap.py:634-663,690-705` (the platform apply role's `secret-read-deny` at line 700) |
| R10-n4 certificate re-pointing | Answered by the D-15 operating residual: a replacement needs a USI contract PR. PR plans keep checking the old ARN until that PR merges, then fail closed on the ACM read until the grant update (and any seed amendment) is applied; scheduled drift keeps checking the applied contract's ARN until an apply of the new-ARN contract writes a new success receipt. The ARN never changes silently. | `prd.md:430-468`; `architecture.md:1668-1703`; `epics-stories.md:2998-3017` | `scripts/poc_workload_capabilities.py:243-266` |
| R10-n5 V-28 and test names | The config-blob open point is **V-28** in the V-table, with S4.14 as its offline story and **S4.6 step 1** (the gate-1 PR's `plan`) as its live step. S4.14's tests name the two `authorize=` tests and keep the "pre-signed URL never exposed" assertion. | `architecture.md:2171`; `epics-stories.md:28,1881-1907,2249-2253,2527-2539` | `tests/unit/test_poc_workload_image_config.py:303-334`; `scripts/poc_workload_images.py:235-259` |
| R10-n6 "only S4.14 edits" | S4.9's multi-arch check lives in `scripts/poc_workload_admission.py` (C-contract) and edits neither the images nor the capabilities module, so the architecture claim holds and is scoped in the C-runner row. The AMD64 pins further down have owners (audit 2): S4.10 derives the topology `cpuArchitecture` from the release platform, and S4.14 widens the capabilities and projection platform checks to the schema enum; the FR-14 coverage row lists S4.9, S4.10 and S4.14. **Recheck of audit 2:** the image-publisher request's `"platform": "linux/amd64"` (`scripts/poc_publisher_dispatch.py` line 170) is S4.14's too (pin-table row; `docs/poc-workload-admission.md` line 111 joins its doc list), so FR-14 (a) is admissible from gate 1 only through S4.10 (row 28) and S4.14 (row 39), both before row 43; an ARM64 publication (XP-12, external) runs after row 39, so there is no forward dependency. Until S4.14 merges an ARM64 contract fails closed. **Corrected in revision 11:** S4.10's end-to-end ARM64 fixture could not pass before S4.14 (the entrypoint's line-59 pin), so S4.10 unit-tests `_task_execution_inputs` and asserts the fail-closed path, and the positive fixture is S4.14's (R11-m3); the publisher's platform comes from the committed `publish_platform` field, not a release block or a dispatch input (R11-m4). | `epics-stories.md:66,853-862,1101-1122,1995-2037`; `architecture.md:2019` | `scripts/poc_workload_capabilities.py:327-330`; `scripts/poc_workload_phase_entrypoint.py:59`; `scripts/poc_workload_topology.py:828`; `scripts/poc_workload_admission.py:355,370-377,448,464-475`; `scripts/poc_publisher_dispatch.py:170`; `docs/poc-workload-admission.md:111`; `tests/unit/test_poc_publisher_dispatch.py:128` |

**Ordered list (re-verified in revision 10).** Still 53 rows (0-52); no
row is added or moved. Row 0 lists D-15. Row 39 (S4.14) adds the D-15
code change and the publisher request's release platform (FR-14 (a)). Row 42 now carries XP-11's BI identity change and TEST seed
amendment after S5.18a, before S4.6 (row 43), which checks it. Row 48's
XP-14 PROD versioning addition is a PROD seed amendment before S5.24a's
(row 50). Row 49 is the issued PROD certificate with its supplied ARN
and the XP-16 path. The TEST ARN is pinned by the gate-1 PR (row 43)
after S4.14 (row 39) makes the schemas require it; the PROD ARN by S4.7's
contract PR (row 52) after XP-15 (row 49). No story depends on a
higher-numbered row, and no seed amendment's baseline hash comes from a
higher row. Two external preconditions without a row are stated (audit
8): #219's own TEST seed amendment before row 9's, and XP-10 before rows
42 and 43. See `epics-stories.md:3507-3643`.

**Residuals recorded in revision 10 (not new risk acceptances).**

- **Certificate replacement window (D-15, R10-n4; audit 6).** ACM
  managed renewal keeps the ARN and needs no PR. A replacement needs the
  exact-ARN `acm:DescribeCertificate` grant update (which revision 9
  needed too; plus a seed amendment if the boundary holds the exact
  ARN), the USI contract PR and an apply. PR plans keep checking the old
  ARN until the contract PR merges, then fail closed on the ACM read
  until the grant update is applied; S4.17 checks the
  applied contract's ARN until the new ARN is applied; and once the old
  certificate is no longer issued or valid, both fail closed until then
  (ACM does not delete a certificate a listener still uses). No apply
  runs while a check fails. Exact order and windows: PRD §7 XP-10.
- **ARM64 before S4.14 (R10-n6, audit 2 and its recheck).** Until S4.14
  (row 39) widens the capabilities (lines 327-330) and projection
  (entrypoint line 59) platform pins and replaces the publisher
  request's `"platform": "linux/amd64"` literal
  (`scripts/poc_publisher_dispatch.py` line 170), and S4.10 (row 28)
  derives the topology `cpuArchitecture` (line 828), an ARM64 contract
  fails closed (`inspect_release` compares the build-provenance platform
  with the contract `release.platform`:
  `scripts/poc_workload_admission.py` `_evidence_values`, line 355 and
  lines 370-377, called from `inspect_release`, line 448). FR-14 (a) is
  admissible from gate 1 only through S4.10 (row 28) and S4.14 (row 39),
  both on the gate-1 list and before S4.6 (row 43); an ARM64 image
  publication (XP-12, external, no row) runs after row 39. No forward
  dependency; no user decision is needed. **Revision 11 (R11-m3,
  R11-m4):** S4.10's own tests assert the fail-closed end-to-end ARM64
  path and unit-test `_task_execution_inputs`; the passing end-to-end
  ARM64 fixture is S4.14's. The publisher's platform comes from the
  committed `publish_platform` contract field at job level, never from
  `client_payload`.

## Pre-commit audit of revision 10

A read-only `claude-router:audit` subagent (agent `ad4bf7989881acda3`),
with fresh context, audited the uncommitted revision-10 diff against
`8e097aa` before the commit. It could not edit files and ran no make,
pulumi or aws command.

- **Result: REFUTED (2 major, 6 minor, 4 nits).** It confirmed as
  accurate: the `wt-boot-urllib3` `pulumi/` tree equals `bea5252`; every
  cited seed catalog line and hash (TEST 307-319, 649-663, 712-761,
  3102-3118, 3273-3299, 3667; PROD 307-319, 649-663, 712-725, 747-760,
  3277-3303, 3325, 3711-3727; guard templates `3a5ec954`, `326bd0c9`,
  `9d60b32c`, `cfc893b4`; boundaries `4a170a1c`, `b331c0c6`); the
  computed guard check; the boundary sizes 1235 and 1240; the amendment
  module lines; the BI and USI code, test and doc lines; the D-15
  propagation; V-28; 53 ordered rows; the FR-31 and FR-33 coverage; no
  live text granting `ssm:GetParameter`; and no invented user decision.
- **Findings and what revision 10 did:**
  1. (major) A fifth seed constraint was missing: `verify_active_enrollment`
     lets the Apply role hold only the managed policies of
     `_mutable_attachment_sets`, and every other role keeps its exact
     attachment set. Fixed: AD-26 layer 5, PRD XP-11, Epic 5, S5.2,
     S5.24a and S4.6 name where the allows live and the seed code,
     write-scope and guard changes a new Apply managed policy needs,
     with `verify_active_enrollment` rows.
  2. (major) FR-14 (a) ARM64 was dropped without a user decision. Fixed:
     S4.10 owns the topology `cpuArchitecture`, S4.14 the capabilities
     and projection platform pins; the FR-14 row lists them.
  3. (minor) S5.5's Apply grant was outside the boundary rule. Fixed:
     S5.2's amendment covers the `secret:rds!cluster-*` pattern.
  4. (minor) The boundary also bounds the ConfigRead roles. Fixed in the
     text, with ConfigRead matrix rows.
  5. (minor) S4.14's test and doc list was incomplete (runner `driver`
     and `certificate` mutation, capabilities parameter fixtures and
     tests, entrypoint projection tests, runner spec 19-21, line 286).
     Fixed.
  6. (minor) The replacement residual was inaccurate and went beyond
     D-15's rationale. Fixed in PRD XP-10, AD-26, S4.17, D-15's note and
     this file; the gap is surfaced to the user in "Remaining user
     decisions" with three options; the plan's default is (a), exact-ARN grants with a BI
     grant update and seed amendment on replacement if the boundary holds the exact ARN, and the user may
     choose (b) or (c).
  7. (minor) R10-n1 was only partly fixed. Fixed: the R9-m2 row and the
     architecture C-runner row.
  8. (minor) #219's amendment and XP-10 had no ordered row. Fixed: both
     are stated as external preconditions of rows 9 and 42 (and 43).
  9. (nit) `architecture.md` still listed
     `workload-certificate-parameter-required` as a kept negative.
     Fixed.
  10. (nit) The gate-1 decision lists omitted D-15. Fixed (FR-31 (d),
      S4.6).
  11. (nit) `MatchedStatements` reports a policy ID and a position, not a
      catalog hash. Fixed: the matrices map the position through the
      guard's catalog `statement_ids` order.
  12. (nit, pre-existing) The PROD Preview role's simulate grant relied
      on S5.17's TEST list. Fixed: S5.24a grants it on the PROD
      execution role, with an allow row.
- **Recheck (same auditor): REFUTED; 9 of 12 findings fixed and 3
  partly fixed; new findings N1-N3. All folded in by the revision-10
  pass that followed.** The recheck did not itemize the third partly
  fixed finding to this pass, so only the two it named with a residual
  are listed as partial (findings 2 and 6). Items and fixes:
  1. **Finding 2 (major residual, ARM64 admission).** The image-publisher
     request sent `"platform": "linux/amd64"` (`scripts/poc_publisher_dispatch.py`
     line 170), and `inspect_release` (line 408) → `_evidence_values`
     (line 335, platform at 355, equality at 370-377) requires the
     build-provenance platform to equal the contract `release.platform`,
     so an ARM64 contract still failed. Fixed: S4.14 owns line 170 (pin
     table row; release-platform pins bullet; files
     `self-deploy.yml` lines 776-781 and
     `tests/unit/test_poc_publisher_dispatch.py` line 128; ARM64 fixtures),
     `docs/poc-workload-admission.md` line 111 joins S4.14's doc list, and
     the claim "FR-14 (a) is admissible from gate 1" now names the
     dependency on S4.10 (row 28) and S4.14 (row 39). No forward
     dependency: both precede S4.6 (row 43), and the external XP-12
     publication of an ARM64 image runs after row 39. The publisher's
     platform is a reviewed value checked against the schema enum, from
     the contract's `release.platform` when a release block exists and
     otherwise from a reviewed dispatch input, because the committed
     `specs/poc/poc-test.json` has no release block at dispatch time;
     admission's existing equality check refuses a mismatch. Locations:
     `epics-stories.md` S4.9 bullet (1101-1122), S4.14 release-platform
     pins (1995-2037) and pin-table row; this file's R10-n6 row and
     "ARM64 before S4.14" residual; `run-summary.md` checklist.
  2. **Finding 6 (nits, wording).** The R10-n4 row and D-15's note said PR
     plans and scheduled drift fail closed until the USI contract PR
     merges. Fixed to the PRD XP-10 behavior: PR plans keep checking the
     old ARN until that PR merges, then fail closed on the ACM read until
     the grant update (and any seed amendment) is applied; scheduled drift
     keeps checking the applied contract's ARN until an apply of the
     new-ARN contract writes a new success receipt (this file's R10-n4
     row and residual, `decisions.md` D-15 note text only, and the same
     sentence in the PRD §6 D-15 row). D-15's replacement-path options now
     carry one wording everywhere: the plan's default is (a), exact-ARN
     grants with a BI grant update and seed amendment on replacement if the boundary holds the exact ARN; the
     user may choose (b) or (c) (PRD XP-10, "Surfaced for the user",
     `decisions.md`, finding 6 above).
  3. **N1 (minor, inline policy size).** IAM limits a role's aggregate
     inline policy size to 10,240 characters, and Layer 5 puts every new
     Preview and Drift allow into inline documents. Fixed: an aggregate
     inline-size check in S5.17, S5.4, XP-11, S5.24a and S5.24b, with the
     fallback of a new managed policy (seed catalog `attachment_arns`
     amendment plus a seed code change, same seed review). Locations:
     `architecture.md` layer 5, `prd.md` XP-11 seed attachment bullet,
     `epics-stories.md` the XP-11 attachment bullet, the Epic 5
     attachment paragraph and the S5.17, S5.4 and S5.24 rows.
  4. **N2 (minor, TEST and PROD amendments).** "A TEST amendment and a
     PROD amendment do not conflict" was wrong: every amendment edits
     `pulumi/seed/policy_registry.py` (`CATALOG_HASHES`, TEST line 19 and
     PROD line 20, adjacent; some also `_mutable_attachment_sets`).
     Fixed: one amendment is open at a time across both catalogs, in the
     existing C-BI order (no row added or moved), each rebasing on its
     predecessor. Locations: `architecture.md` serialization paragraph and
     the C-BI row, `prd.md` XP-11 serialization bullet, `epics-stories.md`
     Epic 5 serialization paragraph, the ordered-list note and the S5.24
     row, and this file's R10-m2 row.
  5. **N3 (nit, ranges).** The R10-n6 row ended `853-860` (the V-27 item
     ends at 862) and `1101-1114` (the S4.9 bullet ends at 1118). Fixed,
     and every other `epics-stories.md`, `prd.md` and `architecture.md`
     range of the round-10 map, the residuals and the ordered-list note
     was re-derived against the final files. The R10-n1 row also cited
     `epics-stories.md:3332`, which is not the S5.24 sentence; it now
     cites the S5.24 row.

## Round-9 finding → resolution map

Line numbers refer to revision 9 as committed. "Source" is the
repository file and lines each fix was checked against, in the tree at
`c61d8d6` (the workload source is unchanged from the baseline). BI
citations come from the read-only local clone `bootstrap-infrastructure`:
its fetched `origin/main` `bea5252`, read with `git show`, and the
unmerged #219 worktree `wt-boot-219` at `54e9e2f` (branch
`feat/publisher-seed-219`). Nothing was fetched or checked out. Findings
of the pre-commit audit are cited as "audit <n>".

| Finding | Resolution | Location | Source checked |
| --- | --- | --- | --- |
| R9-M1 (a) non-weakening design first | **Evaluated in AD-26, security-first (SEC03, SEC03-BP02).** (1) **ECR token: feasible, adopted.** The token only downloads the config blob over registry HTTP, for the platform check. S4.14 replaces that with `ecr get-download-url-for-layer` on the config digest (repository-scoped `ecr:GetDownloadUrlForLayer`, in neither deny list) plus one unauthenticated GET on the already allow-listed `LAYER_HOST`. Owner, files and tests: S4.14; `scripts/poc_workload_images.py`, `tests/unit/test_poc_workload_image_config.py`, `tests/unit/test_poc_workload_images.py`, `docs/poc-workload-admission.md` 54-72; P4 and N7. `ecr:DescribeImages` cannot replace it, because it gives no platform for a single-image manifest. The open point is recorded fail-closed: AWS documents the API for image layers, not explicitly for the config blob. A refusal fails the read-only first TEST `plan` before any apply, which is a STOP. The token fallback narrows a Resource-`*` deny, so it needs a user decision amending NFR-06 as well as the owner review (audit 5). (2) **Certificate parameter on the PR paths: not feasible without a user decision.** The reader skips SSM for a contract `certificate_arn`, but the runner refuses such a contract, and XP-10 has the gateway owner publish the ARN in SSM. It is recorded as a user alternative; the narrowest carve-out stays. (3) **Scheduled drift: feasible, adopted (with R9-m2).** S4.14 adds a `certificate=` reader parameter that takes the receipt's observation (no SSM read), and S4.17 passes it (audit 4). With no token either, the Drift deny is not narrowed. | `architecture.md:1597-1687`; `epics-stories.md:1819-1877,2085-2127,2781-2798,2824-2836,2985-2990` | `scripts/poc_workload_images.py:46-48,51-74,77-120,123-143,153-169,179-203,206-231,235-259`; `scripts/poc_workload_capabilities.py:243-266,269-292,295-319,322-346`; `scripts/poc_workload_runner.py:170-176`; `specs/poc-workload-runner.md:110-113`; `docs/poc-workload-admission.md:54-72`; `tests/unit/test_poc_workload_image_config.py:124-130,184-210,345,391-459`; `tests/unit/test_poc_workload_images.py:312,345,386`; AWS API reference `GetDownloadUrlForLayer` (aws-knowledge MCP, 2026-09-30) |
| R9-M1 (b) the remaining narrowing, TEST | XP-11 now names the TEST Preview and Apply items. **Allows:** `iam:GetRole` on both ECS roles; `iam:SimulatePrincipalPolicy` on the execution role only for Apply (Preview keeps S5.17's step-3 list, audit 2); the three ECR reads on the two repositories; `acm:DescribeCertificate`; `ssm:GetParameter` on the exact XP-10 ARN. **Boundary:** each allow also goes into the `GovernanceBoundary-<project>-test` permissions boundary (audit 1). **The one narrowed deny:** `ssm:GetParameter` leaves `DenySecretLeakingReads` (Preview only; the shared read-only document becomes purpose-aware) and `DenySecretLeakingReadsApply`, into a Deny whose `NotResource` is that ARN. `GetParameters`, `GetParametersByPath` and `ecr:GetAuthorizationToken` stay denied. FR-31(e), the AD-21 gate-1 marker and the S4.6 precondition name it. S5.2 and S5.17 point to XP-11 and S5.24a. Epic 5 states the boundary rule for every C-BI grant to the three service roles (S5.2, S5.17, S5.4 and S5.24 included). | `prd.md:212,245,415-467`; `architecture.md:924-937,1689-1704,1731-1757,1814`; `epics-stories.md:24,93,2275-2309,3132-3151,3157-3158` | `scripts/poc_workload_runner.py:55,178`; `scripts/poc_workload_admission.py:464-475`; `scripts/poc_backend_observer.py:173-174`; `scripts/poc_workload_capabilities.py:30-34,299,307`; BI `origin/main` `pulumi/infra/governance.py:98-109,266-271,441-456,486-497`, `pulumi/infra/governance_automation.py:422-455`, `pulumi/infra/ci_bootstrap.py:132-145,153-166,634-663`; `wt-boot-219` `pulumi/infra/governance.py:279-283` |
| R9-M1 (c) PROD owner before gate 2a | **S5.24 is widened** to the PROD Preview and Apply reads and their narrowed `ssm:GetParameter` denies, at row 50 (≤ 50), before S4.7 (row 52). It ships as two separately approved PRs, S5.24a (PROD Preview/Apply, gate 2a) and S5.24b (Drift, gate 2b), so each part has its own review record (audit 3); a Drift rejection still stops gate 2a through S4.17, C-runner and the S4.7 live matrix (recheck N1). Why S5.24: it already follows XP-14/15/16, whose PROD repositories, parameter and boundary it names, and it has the same BI review. Extending XP-16 (a path outside the plan) or adding XP-17 would split one IAM review and renumber the list. XP-16 says so, and gate 2a (FR-31, AD-21, S4.7) requires S5.24a. | `epics-stories.md:3169,3272,3075-3084,3122,3299-3311`; `prd.md:212,291,513-521`; `architecture.md:933-937,1814` | as (b); `scripts/poc_workload_capabilities.py:30-34` |
| R9-M1 (d) governance, fail closed | Every narrowing needs the BI owner's security review plus `@Kravalg` approval, with the PR number in the acceptance receipt. A rejection is a STOP: gate 1 (XP-11), gate 2a (S5.24a), or S4.17 and therefore gate 2a (S5.24b; recheck N1, corrected in revision 10, R10-n1). If only the Apply-role narrowing is rejected, adopting the fallback design (`up-plan` reuses the Preview-role observation) needs a **user decision**. The contract-carried certificate ARN was another; the user later decided it (D-15, revision 10). The "is that decision" wording is removed (audit 9). | `architecture.md:1759-1773`; `prd.md:457-463`; `epics-stories.md:2303-2309,3169` | — |
| R9-M1 (e) residual replaced | The revision-8 "Preview-role deny" residual is replaced by the XP-11 and S5.24a requirements (see "Residuals recorded in revision 8" below). | this file | — |
| R9-M1 (f) regression evidence | One BI simulator matrix per owner; the simulator evaluates the permissions boundary. **XP-11:** TEST Preview and Apply allows and denies, and **only denies** for TEST Drift, whose allows are S5.24b's (row 50) and so cannot be asserted at gate 1 (audit 2). **S5.24a:** PROD Preview and Apply. **S5.24b:** TEST and PROD Drift. The exact parameter is allowed for Preview and Apply only. Any other parameter, `GetParameters` and `GetParametersByPath` are denied, and so is the token (not needed). The ECR reads are allowed only on the two repositories. Apply and Drift may simulate only the execution role. Repeated live in S4.6 step 3 (XP-11) and the S4.7 PROD simulator run before gate 2a (S5.24a and the PROD part of S5.24b). | `architecture.md:1775-1805`; `epics-stories.md:2343-2364,3075-3084,3169`; `prd.md:463-467` | — |
| R9-m1 S5.24 inventory | S5.24b and the S4.17 first case name `s3:GetBucketVersioning` on each stack's state bucket (two calls per capture). The TEST grants S5.24b cites are inactive at BI `origin/main` (`"enabled": false`) and need the capability `enabled`. PRD XP-9 now says so, and AD-21's gate-1 marker checks it (audit 8). A `withdrawn` state (tombstones Deny every purpose and override S5.24's Allows) or `disabled` while a workload stack exists is a STOP. XP-14 names the PROD Preview and Apply `GetBucketVersioning`, with its boundary addition (Apply added because `up-plan` runs the same capture); S5.24b names the PROD Drift one. "Only grant" is scoped to grants reaching the service CI roles (audit 10). | `epics-stories.md:2612-2643,3169`; `prd.md:214,396-410,502-510`; `architecture.md:924-932,1477-1491` | `scripts/poc_backend_observer.py:438-476` (calls at 443, 476); BI `origin/main` `pulumi/infra/governance.py:156-164,289,329,347,356,364,369-374,457-461`, `pulumi/infra/test-poc-identity.json:11`; `wt-boot-219` `54e9e2f` `pulumi/infra/governance.py:279-290,391-396,436-457,503-510`, `pulumi/infra/test-poc-identity.json:11` |
| R9-m2 Drift-role narrowing record | **No Drift narrowing remains.** The non-weakening alternative is adopted: no fresh SSM read (the receipt's certificate ARN, with an ACM read, through S4.14's parameter) and no token (S4.14). What is lost is recorded: a gateway re-pointing between applies is seen by the next PR `plan`. The unproven revision-8 rationale is withdrawn: a repository policy allowing `*` would let any token holder pull. The principal → action → reachable-privilege table is in AD-26. The XP-11 and S5.24 reviews read and record the repository policies, and a `*` pull grant is a STOP (no code defines a repository policy today). A rejected S5.24b review is a STOP of S4.17, and therefore of gate 2a, needing a user decision (corrected in revision 10, R10-n1; revision 9 said gate 2b). The approval PR numbers go in the acceptance receipt. | `architecture.md:1673-1687,1706-1729`; `epics-stories.md:1862-1877,2781-2798,2824-2836,2978-2990,3169`; `prd.md:214` | `scripts/poc_workload_capabilities.py:193-232,243-266,269-292,295-299,336,339`; `grep -rn RepositoryPolicy` over USI `pulumi/` and `scripts/` and `wt-boot-219` `pulumi/` (no hit; `pulumi/app/compute.py:434` is a lifecycle policy) |
| R9-n1 PROD gate-2b record | The PROD item is `before-acceptance` with `null` success-receipt fields; `checked` cannot occur, because PROD cannot apply before gate 2b. A PROD `checked` or non-null record is refused fail-closed. Gate 2b links the S5.24a/S5.24b PROD simulator evidence and S4.7's live PROD simulator run. The row-40 label is fixed (audit 10). | `prd.md:212,291`; `architecture.md:938-955,1472-1475`; `epics-stories.md:2169-2184,2206-2213,2868-2870,3024-3031,3085-3095,3109-3123,3262` | `scripts/poc_workload_runner.py:53,164` (TEST-only today; S4.14's `admission.prod` rule) |
| R9-n2 concurrency residual | Added to the R8-n4 residual: within one scheduled run, a stack's baseline job and its S4.17 workload job share `pulumi-state-…-<env>-<env>`, so one of them waits pending. A PR job that holds the group can then cause that pending job to be cancelled. | this file, "Residuals recorded in revision 8" | `.github/workflows/scheduled-drift.yml:35-37,98-100` |
| R9-n3 grep base | S4.14 re-runs the three greps at its own base and records the counts in its PR. The `_REGISTRIES` rows (inventory and pin table) include S4.10's selector, which adds a grep-1 hit, and P3 covers hits that exist only at that base. | `epics-stories.md:1704-1712,1733,1911,2085-2088` | `scripts/poc_registry_phase_entrypoint.py:13-22` |
| R9-n4 front matter, NFR-10, §4 | `revision: 9` in the PRD, architecture and epics front matter. The NFR-10 row adds S4.14 and S4.17. The C-contract chain lists `scripts/poc_registry_phase_entrypoint.py` (S4.10's selector), and C-runner names the images and capabilities modules, which only S4.14 edits. | `prd.md:7`; `architecture.md:7,1816,1818`; `epics-stories.md:7,97` | — |

**Ordered list (re-verified in revision 9).** Still 53 rows (0-52); no row
is added or moved. S5.24 at row 50 ships as two PRs:
- S5.24a (PROD Preview and Apply) precedes its first use in
  `prod_preview` (S4.7, row 52);
- S5.24b (Drift) precedes S4.17 (row 51).

The TEST owner is XP-11, a gate-1 prerequisite that S4.6 (row 43) checks
before the gate-1 PR. The XP-11 matrix asserts only Drift denies, so it
does not need S5.24b (audit 2). S4.14 (row 39) removes the ECR token and
adds the `certificate=` reader parameter. It does both before every row
that relies on them: S4.6 (43), S5.24 (50) and S4.17 (51). S5.24b's
no-SSM Drift inventory therefore rests on row 39, not on row 51 (audit
4), and S4.17 edits neither module. S4.15 (row 40) defines the PROD-item
rule as a check, with no code dependency on rows 50-52. No story depends
on a higher-numbered row. See `epics-stories.md:3218-3334`.

## Pre-commit audit of revision 9

A read-only `claude-router:audit` subagent, with fresh context, audited
the uncommitted revision-9 diff against `c61d8d6` before the commit. It
could not edit files and ran no make, pulumi or aws command.

- **Result: REFUTED (2 major, 6 minor, 2 nits).** It confirmed as
  accurate the cited USI lines (runner, admission, images, capabilities,
  observer), the docs, workflow and test lines, BI `origin/main`
  `governance.py` 156-164, 266-271, 329-374 and 448-461, `ci_bootstrap.py`
  132-145 and 153-166, `test-poc-identity.json:11`, and `wt-boot-219`
  279-290, 391-396, 436-457 and 503-510. It rated the ECR design sound,
  the open point fail-closed, and the SSM narrowing exact. It found no
  stale "Drift narrowing" text and 53 rows with the PROD owner at row 50.
  The only surviving "`before-acceptance` or `checked`" is in the
  historical round-8 row.
- **Findings and what revision 9 did:**
  1. (major) The plan never mentioned the service roles' permissions
     boundary `GovernanceBoundary-<project>-<env>` (BI `governance.py`
     486-497; `governance_automation.py` `service_boundary_policy`
     422-455), which caps every new allow. Fixed: AD-26 "Third layer",
     XP-11 and S5.24 add each allow to the boundary in the same review.
     The Epic 5 rule covers S5.2, S5.17, S5.4 and S5.24 (a gap that
     predates revision 9), and the simulator proves it.
  2. (major) The step-3 matrix could not pass. It said simulate "on the
     execution role only" for Preview, although S5.17 grants Preview the
     step-3 list, and it asserted TEST Drift allows that only S5.24b (row
     50) grants. Fixed: execution-role-only applies to Apply and Drift;
     the XP-11 matrix asserts only Drift denies; the Drift allows are in
     the S5.24b matrix.
  3. (minor) One S5.24 approval could not give two different STOP
     points. Fixed: two separately approved PRs, S5.24a and S5.24b.
  4. (minor) Forward dependency: S5.24's no-SSM Drift inventory depended
     on S4.17 (row 51) adding the `certificate=` parameter. Fixed: S4.14
     (row 39) adds it (P5, N8); S4.17 only passes it.
  5. (minor) The token fallback contradicts the new NFR-06 rule (narrow
     only to one exact ARN). Fixed: the fallback needs a user decision
     that amends NFR-06.
  6. (minor) This section was missing. Fixed: this section.
  7. (minor) The "revision 9" hash block held revision-8 hashes. Fixed:
     recomputed at commit time and checked with `sha256sum -c`.
  8. (minor) XP-9 did not state the capability dependency. Fixed: PRD
     XP-9 and the AD-21 gate-1 marker.
  9. (nit) "the fallback … is that decision" read as a made decision.
     Fixed: "adopting the fallback needs that user decision".
  10. (nit) Citations fixed: the PRD revision line is 7; the
      `DenySecretLeakingReadsApply` function is 634-663; "only
      `GetBucketVersioning` grant" is scoped to the service CI roles; the
      ordered-list reference is 3218-3334; and the row-40 label now
      carries the PROD `before-acceptance` rule.
- No invented user decision was found.
- **Recheck (same auditor): REFUTED, one new minor and one nit; both
  fixed before the commit by the coordinator.** Findings 1-6 and 8-10 are
  fixed and finding 7 was deferred to commit time, as intended. About 25
  recomputed Location ranges were checked and hold; 53 rows, no other new
  forward dependency.
  - N1 (minor): the claim "a rejected S5.24b does not block gate 2a" was
    wrong. S4.7 (gate 2a) follows S4.17 in C-runner, and its live PROD
    simulator run repeats the PROD part of the S5.24b matrix, so a
    rejected S5.24b stops S4.17 and therefore gate 2a. Fixed: the claim
    is removed and replaced by the correct effect in S5.24 (the row and
    its STOP sentence), the ordered-list dependency paragraph, AD-26 in
    `architecture.md`, and the R9-M1 (c) row above. The split still
    keeps the two reviews and their records separate.
  - N2 (nit): the dependency paragraph said S5.24's inventory rests on
    code "that exist today". Fixed: "that exist at row 50, after S4.14
    (row 39)".

## Round-8 finding → resolution map

Line numbers refer to revision 8. "Source" is the repository file and lines
each fix was checked against, in the current tree at `72873f9` (the
workload source is unchanged from the baseline: `git diff --stat
66776772 72873f9 -- scripts schemas tests .github docs specs/poc` is
empty). BI citations are from the read-only local clone
`bootstrap-infrastructure` (checked-out `debd88b`; its fetched
`origin/main` is `bea5252`). Every rewrite of a pinned workflow-shape or
C-runner test still needs an `APPROVED` review by `@Kravalg`
specifically, recorded with the PR number in the acceptance receipt. The
revision-7 audit recheck residuals are cited as "A<n>". Where this map
differs from the round-7 map below (R7-m2's "the PROD job is enabled by
the PR", the R7-m3 pin table, the R7-m9 inventory), this map is
authoritative.

| Finding | Resolution | Location | Source checked |
| --- | --- | --- | --- |
| R8-M1 S4.17 cannot publish its result record | The worker's scheduled route copies the script's record to `/public/workload-drift-result/record.json` after a zero status (today it copies only for `plan`); the host copies it to `.trusted/.artifacts/workload-drift-result/record.json` for the two scheduled jobs, a no-op when absent (today only `_preview` jobs); one pinned upload step directly after `execute`: `actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02`, name `poc-workload-scheduled-drift-<env>-${{ github.run_id }}-${{ github.run_attempt }}`, `if-no-files-found: error`, `overwrite: false`, `retention-days: 7` (the pin and retention of every upload in `self-deploy.yml`), no `if`. The sibling test pins "execute, followed only by that upload" (N9). Changed pinned assertions: worker test 128 (`calls[-3:]` stays for PR jobs; for the scheduled jobs `["scheduled", "admit", "admit"]`, with no PR `execute`), 130 (`len(copied) == {"plan": 2, "scheduled-drift": 1}.get(command, 0)`), 131 stays; host test 109-112 (the fake worker writes the record for the scheduled jobs) and 140-144 (the record under `root`). The S4.15 items, FR-31, AD-21 and PRD §3.3 carry `artifact_id` and `artifact_sha256`. | `epics-stories.md:2481-2549,2665-2683,2698-2755,2758-2762,2794-2798,2062-2086,2107-2113,2122-2128`; `architecture.md:937-947,1402-1413,1453-1465,1478-1483`; `prd.md:212,227-229` | `scripts/service_execution_worker.py:129-132`; `scripts/service_execution_host.py:214-219`; `.github/workflows/self-deploy.yml:131-137,268-285,651-657`; `tests/unit/test_service_execution_worker.py:128-131`; `tests/unit/test_service_execution_host.py:109-112,140-144` |
| R8-m1 (with A2) S4.17 PROD enablement | (a) Live now says the PROD job starts checking after the gate-2a PR (S4.7) that first sets `phase: workload`. (b) Enablement is data-driven: both jobs run from S4.17's merge; each reads its stack's installed `main` contract; on `phase: registry` it writes a distinct `registry-phase` record (S4.15 schema), emits a notice and exits 0; a missing contract exits non-zero. The self-contradiction ("enabled by the PR" vs. "a `phase: registry` stack is not handled here") is removed in S4.17, S4.7, AD-21, the architecture S4.17 item and FR-31; B2 is the new B case. (c) Gate 2b (S4.15 `complete`, S4.7 precondition and N3, FR-31, AD-21) requires a linked PROD `before-acceptance` or `checked` record from a scheduled run after the flip; `registry-phase` never counts. | `epics-stories.md:2550-2566,2807-2812,2819-2829,2062-2086,2838-2851,2875-2886,2899-2905`; `architecture.md:937-947,1414-1420`; `prd.md:212-213,291` | `scripts/poc_scheduled_registry_drift.py:104-119`; `.github/workflows/scheduled-drift.yml:23-147` |
| R8-m2 S4.14 pin table incomplete | S4.14's first case is a grep-derived inventory over `scripts/` (three commands: the requested literals, 87 hits; indirect TEST-constant uses, 38 hits; and, from the pre-commit audit, the TEST registry set, tags, URNs, checkpoint key and mail domain, 41 hits; the check is keyed on file and matched text), with every hit owned or excluded, and a test that re-runs both (P3, N6). New S4.14 rows: materializer 24 and 126; `poc_contract.py` 99, 102-113 (`_mail_semantics`; S4.14 owns the code, XP-14 the PROD domain, map shipped without it so PROD fails closed) and 116-126 (`_registry_semantics`, account from the contract; runs for every contract, including XP-14's `poc-prod.json`); `poc_secret_observation.py` 11 (prefix from the contract account, so the S4.10-only `poc_workload_secret_result.py` is not edited); every `CONTRACT_PATH` consumer (`poc_phase_admission.py` 119, 216, 219; `poc_source_artifact.py` 256, 314; `poc_phase_source_adapter.py` 119, 181, 213, 241; entrypoint 18, 41; `poc_workload_admission.py` 110). New XP-14 rows: observer `_caller` 213-228, `_key` 325, `LOCKS` 43; `_REGISTRIES` 13-22; registry completion; the capture row gains `ecr_read` and the mail inventory; `poc_registry_plan.py` gains 51-59 and 63. S4.10 gains topology 955 and 149-151, and the S4.10 registry-set note (service and provider URNs derived from the stack's prefix; the PROD registry set is XP-14's and stubbed, so S4.10 needs nothing from row 48). New S4.14 row: `poc_workload_admission.py` `inspect_registry` (147-155); the images row gains the registry set (53, 239, 346); the observer row gains 42 and 345. Exclusions are listed with reasons. | `epics-stories.md:1679-1749,1810-1842,2014-2016,2030-2033,782-796`; `architecture.md:1364-1377,1514-1519`; `prd.md:429-439` | the three grep commands (87, 38 and 41 lines); `scripts/poc_workload_materializer.py:24,89,126`; `scripts/poc_contract.py:99,102-113,116-126,153,185,190`; `scripts/poc_secret_observation.py:11,19,52-73`; `scripts/poc_workload_secret_result.py:17,206,254,272`; `scripts/poc_phase_admission.py:24,119,216,219`; `scripts/poc_source_artifact.py:256,314`; `scripts/poc_phase_source_adapter.py:119,181,213,241`; `scripts/poc_workload_phase_entrypoint.py:18,41,107,111,314`; `scripts/poc_workload_admission.py:110,134`; `scripts/poc_backend_observer.py:43,213-228,325`; `scripts/poc_registry_phase_entrypoint.py:13-22,38-52`; `scripts/poc_registry_completion.py:30-33,105,118,257,367`; `scripts/poc_registry_runner.py:35,130-131,175-176,185-199,305,338,358-364`; `scripts/poc_mail_prerequisite.py:13-15`; `scripts/poc_workload_topology.py:61,149-151,859,955,1058,1160` |
| R8-m3 S5.24 inventory | S5.24 adds the registry-row and refresh reads: `ecr:DescribeRepositories`, `ses:GetEmailIdentity`, `route53:GetHostedZone`, `route53:ListResourceRecordSets` and the provider refresh reads of those types; S4.17's gate runs the capture's registry-row checks. BI checked read-only: `origin/main` `bea5252` already grants those registry reads to the TEST Drift role (`_test_poc_capability_statements`, statements at 347, 356, 364, attached to every purpose at 457-461 while the TEST PoC identity is enabled, 329); `debd88b` does not; no BI grant covers PROD, so S5.24 adds the PROD equivalents. **Found while checking:** the read-only policy's explicit `DenySecretLeakingReads` (governance line 267) denies `ssm:GetParameter` and `ecr:GetAuthorizationToken` (ci_bootstrap 132-145), so S5.24 must narrow it for the Drift role; the exact form is the BI owner's security review with Kravalg's approval. `iam:SimulatePrincipalPolicy` is restricted to the execution role; `iam:GetRole` covers both roles. NFR-06 lists S5.24. | `epics-stories.md:2929,2450-2469,93`; `architecture.md:1466-1483,1588`; `prd.md:214` | `scripts/poc_scheduled_registry_drift.py:122-129`; `scripts/poc_registry_runner.py:185-199,254-263`; `scripts/poc_mail_prerequisite.py:301-310,389-424`; `scripts/poc_workload_capabilities.py:25-29,37-48,89,193-232,333,338,341`; BI `origin/main` `pulumi/infra/governance.py:267,289,329,347,356,364,457-461`, `pulumi/infra/ci_bootstrap.py:132-145` |
| R8-m4 S4.17 projection and program semantics | The projection comes only from the latest success receipt (`SourceAdmission` facts, the applied contract, the full image rows, the certificate observation); fresh Drift-role reads (images, capabilities and certificate, checkpoint, registry rows) are comparisons, never inputs. The success receipt records the full image rows, the certificate observation `{parameter_arn, parameter_version, certificate_arn}` and the program trees (S1.1 schema, S4.11 writer, AD-24). S4.17 compares the program trees first (distinct reason `workload-drift-installed-program-changed`, B3), then the projection digest (`workload-drift-projection-binding`) and the generated-files digest. A TEST release (a no-op re-apply through the normal PR path, AD-24 release row) runs before the gate-2b clean `checked` run whenever code changed after the last apply (S4.17 Live, S4.7 precondition). | `epics-stories.md:160-175,894-900,2573-2591,2607-2623,2788-2793,2813-2829,2875-2886`; `architecture.md:1171-1178,1421-1440`; `prd.md:213` | `scripts/poc_workload_phase_entrypoint.py:52-93,101,104,194-208`; `scripts/poc_workload_capabilities.py:269-292`; `scripts/poc_workload_runner.py:177-184`; `scripts/poc_registry_runner.py:37` (`TRUSTED_PATHS`) |
| R8-m5 docs drift | S4.14 and S4.17 amend `specs/poc/README.md` lines 52-57 (with the story's Kravalg approval), `docs/poc-workload-admission.md` line 10 and `docs/ci-guardrails.md` lines 147 and 170-181; NFR-10 lists `docs/ci-guardrails.md`. S4.13's amended sentence names the PR `drift` command. | `epics-stories.md:1844-1858,2684-2697,1589-1597`; `prd.md:249` | `specs/poc/README.md:52-57`; `docs/poc-workload-admission.md:10`; `docs/ci-guardrails.md:147,170-181`; `tests/unit/test_workload_apply_docs_consistency.py:175` (no test pins the three doc passages: grep of `tests/`) |
| R8-m6 PROD counterparts of XP-10 and XP-11 | Numbered XP-15 and XP-16 in PRD §7, with the assumption that S4.14 pins the TEST-analogous names `/vilnacrm/prod/user-service/gateway-certificate-arn` and `arn:aws:iam::933245420672:policy/issue219/prod/boundary/`, which the owners confirm in the S4.14 PR before it merges (a naming statement recorded in row 39, so no forward dependency; pre-commit audit) and S4.7 verifies live. The parameter and the path existing live are a gate-2a prerequisite row (row 49) in the ordered list, and gate 2a (FR-31, AD-21) names them. | `prd.md:212,291,440-452`; `epics-stories.md:24,1799-1803,1825,2865-2874,3031`; `architecture.md:931,1340-1342` | `scripts/poc_workload_capabilities.py:30,111` |
| R8-m7 S4.7 chain and approval | C-runner is S4.1 → … → S4.14 → S4.17 → S4.7; S4.7's unstubbed host seam test needs the `@Kravalg`-specific approval. | `architecture.md:1592`; `epics-stories.md:2833-2834,2852-2860,2960-2964` | `tests/unit/test_service_execution_host.py:233-322` |
| R8-n1 role-session-name | The S4.17 steps and sibling test pin `gha-scheduled-test-drift-${{ github.run_id }}` and `gha-scheduled-prod-drift-${{ github.run_id }}`; the observer accepts the TEST name today and the PROD name once XP-14 makes `_caller` stack-aware (inventory row). | `epics-stories.md:2526-2535,2698-2726,2794-2798`; `architecture.md:1378-1384` (the session names at 1382-1383) | `scripts/poc_backend_observer.py:219-223`; `.github/workflows/scheduled-drift.yml:76,139` |
| R8-n2 TEST campaign window | Recorded in S4.6 as a consequence of D-6's gate order, not a new risk acceptance. | `epics-stories.md:2176-2186` | — |
| R8-n3 FR-32 coverage | The FR-32 row lists S4.14. | `epics-stories.md:81` | — |
| R8-n4 residuals | Recorded below: a PROD stack with only failed or export receipts gets no drift check; a queued scheduled job can be cancelled by the concurrency group. | this file, "Residuals recorded in revision 8" | GitHub Actions concurrency: one running and at most one pending job per group; a newer pending job cancels the older pending one |
| A1 PROD seam stand-ins | S4.14's PROD fixtures replace `_target_coordinates`, `_target` and `capture_backend` with checking stand-ins: PROD account, role, bucket and provider (and `target_environment == "prod"` for `_target`); a mismatch raises the observer's own `ValueError("Backend observation precondition failed")`, a match calls the patched `aws_read` boundary, so every fault keeps its meaning. | `epics-stories.md:1914-1933,2023-2029` | `tests/unit/test_service_execution_host.py:233-322`; `scripts/poc_backend_observer.py:76-79,181-210` |
| A3 `prod_destructive_diff` `if` | Pinned exactly, with the `\|\|` parenthesized; an unparenthesized form fails (N4). | `epics-stories.md:1876-1884,2023-2029` | `tests/pulumi/test_ci_guardrails.py:246-255,281-284` |
| A4 gate line, binding, wording | (1) Checked, not changed: `def _gate` of `scripts/poc_scheduled_registry_drift.py` is at line 136 in the tree (`cat -n`; line 134 is blank, `_recheck` is 132-133), so the plan keeps "line 136 on". (2) The S4.17 gate uses S4.14's stack-aware binding and never the TEST-only registry `_binding`; N3 lists `registry._binding`. (3) "as round 6 decided" now reads "as revision 6 ordered". | `epics-stories.md:2624-2654,2770-2776`; `architecture.md:1441-1452`; this file (round-7 residual) | `scripts/poc_scheduled_registry_drift.py:132-138`; `scripts/poc_registry_runner.py:266-283` |

**Ordered list (re-verified in revision 8).** 53 rows (0-52): XP-15 and
XP-16 are new at row 49 (gate-2a prerequisites), S5.24 moves to row 50,
S4.17 to row 51 and S4.7 to row 52. No story depends on a higher-numbered
row. The checks added in revision 8: S4.14 (row 39) pins the XP-15 and
XP-16 names as an assumption the owners confirm in the S4.14 PR itself
(row 49 is the live parameter and path, not the confirmation) and uses
stubs or checking
stand-ins for every XP-14 row, including the absent PROD mail domain, so it
reads nothing from rows 48-49; S4.10 (row 28) derives the stack's URN
prefix, root, provider and service URNs without XP-14 and stubs the PROD
registry set; S5.24 (row 50) grants on the XP-15
parameter (row 49) and holds its own inventory from existing modules and
BI code; S4.17 (row 51) follows S1.1 (row 2, the new receipt fields),
S4.11 (row 29), S4.14 (row 39, the stack-aware binding), S4.15 (row 40,
the `registry-phase` status and the two-item gate-2b rule), XP-14, XP-15,
XP-16 and S5.24; S4.7 (row 52) follows S4.17 in C-runner. See
`epics-stories.md:3036-3073`.

**Residuals recorded in revision 8 (not new risk acceptances).**

- **TEST campaign window (R8-n2).** Now recorded in S4.6: from the gate-1
  flip until S4.17 merges, the TEST workload stack gets drift checks only
  from `test_workload_drift` after each post-acceptance apply.
- **PROD stack with only failed or export receipts (R8-n4).** A
  `phase: workload` stack whose lineage has no workload success receipt
  (for example after a failed first PROD apply) gets no scheduled drift
  check: S4.17 writes a `before-acceptance` record with a `null` receipt
  and exits 0 with the warning, and the baseline no longer covers the
  stack. The recovery path (S4.3 `export`, then `resume`) is the control,
  and the warning is visible every night.
- **Queued scheduled job cancelled by the concurrency group (R8-n4,
  R9-n2).** The S4.17 jobs share `pulumi-state-…-<env>-<env>` with the
  PR jobs of the stack, and, within one scheduled run, with that stack's
  baseline job (`.github/workflows/scheduled-drift.yml` lines 35-37 and
  98-100, `cancel-in-progress: false`). The baseline job and the
  workload job of a stack therefore never run at once: one of them waits
  pending. GitHub Actions keeps at most one pending job per group, so a
  queued scheduled job is cancelled if a newer job for the same group
  queues behind a running one. A PR job that holds the group while the
  two scheduled jobs of the stack queue can cause one of them to be
  cancelled. That night then has no check of that kind for the stack; the
  run shows as cancelled, not green, and the next night runs again.
- **Code changes after the last apply (R8-m4).** Any merge that changes
  a program tree makes the next scheduled run of each workload stack fail
  with `workload-drift-installed-program-changed` until a release
  re-applies that stack. This is visible, never silent; for PROD after
  gate 2b it is an operating rule (re-apply after code changes), recorded
  here.
- **Preview-role deny: replaced by a requirement in revision 9 (R9-M1
  (e)).** This was a residual in revision 8. It is now a requirement.
  XP-11 names the TEST Preview and Apply workload-observation reads and
  the one narrowed deny (`ssm:GetParameter` on the exact XP-10 parameter
  ARN), and S5.24a names the PROD ones (row 50, before gate 2a). Each
  allow is also added to the service permissions boundary. Both go
  through the BI security review approved by `@Kravalg`, and both fail
  closed. The ECR token is no longer needed (S4.14), and the Drift role's
  deny is not narrowed (S4.17, R9-m2). See architecture AD-26. Revision
  10 (user decision D-15) removes the `ssm:GetParameter` narrowing too:
  no deny and no seed guard is narrowed for any role.

## Pre-commit audit of revision 8

A read-only `claude-router:audit` subagent, with fresh context, audited
the uncommitted revision-8 diff against `72873f9` before the commit. It
could not edit files and ran no make, pulumi or aws command.

- **Result: REFUTED.** It spot-checked more than 60 newly cited source
  lines (including the bootstrap-infrastructure citations) and found them
  accurate. It reproduced both grep counts (87 and 38) with every hit in
  the table, and confirmed A4's point 1: `def _gate` is at line 136. It
  rated R8-M1, R8-m1, R8-m3, R8-m4, R8-m5, R8-m7, n1-n4, A1 and A3
  addressed, found no invented user decision, and found the row numbers
  consistent.
- **Findings and what revision 8 did:**
  1. (minor, close to major) The inventory was not complete by
     construction: neither grep matched `registry.REGISTRIES`,
     `graph._graph`, `*_URN`, `DEFAULT_TAGS`, `from poc_registry_plan
     import`, `urn:pulumi:test::`, `/test.json` or `vilnacrmtest`, and
     S4.10's PROD graph silently depended on XP-14's registry names.
     Fixed: a third grep (41 hits) with every hit owned or excluded; new
     rows (`inspect_registry`, the images registry set, observer 42 and
     345); the S4.10 registry-set note (service and provider URNs derived
     from the stack's prefix, the PROD registry set stubbed, no PROD
     registry name assumed); the inventory test keys on file and matched
     text.
  2. (minor) Forward dependency: S4.14 (row 39) waited on a confirmation
     placed at row 49. Fixed: the owners confirm the names in the S4.14 PR
     (a naming statement in row 39); row 49 is the parameter and path
     existing live.
  3. (minor) The result schema required a captured checkpoint for
     `registry-phase`, which captures none. Fixed: `null` for
     `registry-phase`, with S4.15 B2 cases.
  4. (nit) Location and Source lines off by about 3, and
     `TRUSTED_PATHS` at line 37. Fixed: every round-8 Location range was
     recomputed from the final text.
  5. (nit) "the repository's retention for every upload" overstated.
     Fixed: "every upload in `self-deploy.yml`".
  6. (nit) The FR-31 boundary cell omitted XP-15 and XP-16. Fixed.
  7. (nit) The inventory test keyed on line numbers. Fixed with item 1.
- No invented user decision was found.
- **Recheck: CONFIRMED.** The same auditor rechecked all seven fixes
  read-only after the first commit of revision 8 (`ead0f03`): the three
  greps return 87, 38 and 41 lines with every hit in the table, the
  XP-15/XP-16 wording has no forward dependency, the `registry-phase`
  checkpoint is null with validator cases, 45 recomputed Location ranges
  start and end on the cited text, and the retention and FR-31 wording is
  fixed. Its one optional nit (S4.10 did not name the file of the
  stack-selected registry set or its behaviour before XP-14) is folded
  in: a stack-keyed selector in `scripts/poc_registry_phase_entrypoint.py`,
  outside C-topology, that fails closed for `prod` until XP-14 adds the
  entry, an edit outside this plan.

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
merges after the TEST campaign (row 43), as revision 6 ordered (S4.17 is a
gate-2b precondition; wording corrected in revision 8, R8-A4). During the campaign, workload drift is checked by
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
- **XP-9 … XP-13.** The existing runner prerequisites. Revision 9 makes
  XP-11 explicit (R9-M1). Revision 10 (D-15, R10-M1, R10-m2): XP-10 is
  the gateway-supplied certificate ARN pinned in the TEST contract, with
  no SSM publication; XP-11 is the TEST Preview and Apply
  workload-observation reads (no SSM), with the denies and seed guards
  unchanged, and their seed boundary amendment in the C-BI slot after
  S5.18a (revision 11: the #219 part is #284's catalog amendment; the
  TEST ECS roles are S5.1's, R11-M1), under the BI security review and the seed review approved by
  `@Kravalg` (PRD §7, AD-26). XP-9 also keeps
  the packaged TEST capability `enabled`. Its `PocBackendVersioning` and
  registry reads serve every TEST capture, and `withdrawn` while a
  workload stack exists is a STOP (R9-m1).
- **XP-14.** The PROD registry phase (outside this plan; gate 2). It also
  owns the trusted observer's PROD coordinates (including the schema read
  at lines 199-201), the TEST registry constants of
  `scripts/poc_registry_plan.py`, and the committed
  `specs/poc/poc-prod.json`, which must validate against the S4.14 PROD
  schema (R6-m5, R6-m11, R7-m3, R7-m4). Revision 8 adds, from the grep
  inventory (R8-m2): the observer's `_caller`, `_key` and `LOCKS`,
  `_REGISTRIES`, the PROD registry completion, the PROD SES domain, zone
  and identity (including the `prod` entry of the `_mail_semantics`
  domain map, absent until then so PROD fails closed) and the PROD
  counterpart of the TEST image publisher environment. Revision 9 adds
  `s3:GetBucketVersioning` on the PROD state bucket for the PROD Preview
  and Apply roles (R9-m1).
- **XP-15 and XP-16 (R7-m3, R8-m6; XP-15 rewritten by D-15).** The
  issued PROD gateway certificate, whose ARN the gateway owner supplies
  for S4.7's contract PR (no SSM parameter), and the PROD
  permissions-boundary path (bootstrap owner), numbered in PRD §7 and
  ordered as row 49, a gate-2a prerequisite. S4.14 pins the
  TEST-analogous boundary path as an assumption the bootstrap owner
  confirms in the S4.14 PR (a naming statement recorded there, not the
  row-49 deliverable); S4.7 verifies both live.

## Remaining user decisions

None are open for planning. D-15 (revision 10) settled the certificate
source that revision 9 left to the user. These confirmations are owner
or review items, not user decisions:
- the XP-16 boundary path name (the bootstrap owner confirms the
  TEST-analogous path in the S4.14 PR); XP-15 has no name to confirm
  under D-15, only the ARN the gateway owner supplies;
- the PROD mail domain (XP-14);
- the exact form of each boundary addition (exact allows or a
  seed-approved service or resource-family ceiling, R10-m1), the named
  seed owner and the CloudFormation change-set evidence of each seed
  amendment, and the order of the open amendments after #219's
  (R10-m2). These are the BI owner's security review and the seed review,
  approved by `@Kravalg`;
- the repository-policy record (XP-11 for TEST, S5.24a and S5.24b for
  PROD and Drift).
- for every independent stack (R11-M1): the reviewed template and its
  hash, the named human non-root installer, the CREATE or UPDATE
  change-set evidence and the verifier output; the BI review's record
  that S5.1's TEST ECS stack replaces #219's later runtime amendment for
  the two ECS roles. These are the BI owner's and the seed reviews,
  approved by `@Kravalg`.

**Surfaced for the user, not decided here (pre-commit audit 6):** D-15's
accepted rationale says a certificate replacement needs only a reviewed
USI PR. Under NFR-06's exact-ARN rule the plan also needs the BI
`acm:DescribeCertificate` grant update on replacement, plus a seed
amendment if the boundary holds the exact ARN. The plan's default is
(a), exact-ARN grants with a BI grant update and seed amendment on
replacement if the boundary holds the exact ARN; the user may choose (b) or (c). The options (PRD §7
XP-10): (a) accept the extra BI and seed PRs; (b) an ACM certificate-family
ceiling in the boundary (seed review), which removes the seed amendment
only; (c) `acm:DescribeCertificate` on the account's regional
`certificate/*` in the identity policies (metadata only), which removes
both but amends NFR-06 and so needs a user decision.

Revision 9 removed the Drift-role narrowing, and revision 10 (D-15)
removes every `ssm:GetParameter` narrowing (AD-26). Some decisions arise
only if a live check, a measurement or an owner review fails:

| ID | Trigger | State |
| --- | --- | --- |
| Conditional: V-1 fails | step-2 health (step 7) | a new decision would be needed (an app DB user with a rotated password) |
| Conditional: V-5 requires a `default` password | step 1 | a new decision would be needed (no Pulumi-generated password allowed) |
| Conditional: V-16 fails with SSE-KMS | step 12 | SSE-S3 would contradict D-4, so a new decision would be needed |
| Conditional: a D-14 RPO or RTO target missed | S4.8, before gate 2a | a new user decision: accept the measured value or change the design |
| Conditional: the BI security review or the seed review rejects XP-11's or S5.24a's Preview and Apply reads or their boundary amendment (R9-M1 (d), R10-M1) | XP-11 before gate 1; S5.24a before gate 2a | a STOP, then a user decision. If only the Apply-role reads are rejected, one option is the recorded fallback design, in which `up-plan` reuses the Preview-role observation. This plan does not choose it. |
| Conditional: a stack or stack-amendment review is rejected, a preflight finds a role name present (for example #219's `PocRuntimeRoles` registered first), or a post-create or post-update verifier fails (R11-M1) | the row of that seed operation (8, 11, 13, 33, 34, 42, 43, 45 or 47) | a STOP for that story, then an owner decision. The governor-guard route (narrowing a Resource-`*` deny so a CI role can create roles) is not a fallback: it needs a user decision amending NFR-06, which this plan does not take |
| Conditional: the BI or seed review rejects S5.24b's Drift grants | S5.24b, before S4.17, and therefore before gate 2a (recheck N1; corrected in revision 10, R10-n1) | a STOP, then a user decision |
| Conditional: a boundary amendment exceeds 6144 characters and the seed review rejects the service-family ceiling (R10-m1) | the amendment of S5.2, S5.17, S5.4, XP-11, XP-14, S5.24a or S5.24b | a STOP for that story, then an owner or user decision (for example a second boundary design, which this plan does not choose) |
| Conditional: `GetDownloadUrlForLayer` refuses the config digest, or its URL is outside `LAYER_HOST` (V-28, R9-M1 (a), R10-n5) | S4.6 step 1, the first TEST workload `plan` (read-only, before any apply) | a STOP. The token fallback removes `ecr:GetAuthorizationToken` from the Preview, Apply and Drift identity denies and from their seed guards (guard template and catalog hashes change through a seed amendment). That narrows Resource-`*` denies, so it needs a user decision that amends NFR-06, as well as the BI security review and the seed review approved by `@Kravalg` |

## Skill applicability (devops-sdlc 14)

**Applicable and addressed:**

- security-iam (AD-15a, AD-26 with its six IAM layers: identity allows, unchanged denies, the seed-owned boundary, seed guards unchanged relative to each story's baseline catalog, the seed attachment constraint, and principal creation only by independent CloudFormation stacks (R11-M1, R11-n4); S5.x, S5.21/S5.22 repository controls)
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
  in the isolated worker container before gate 2b, data-driven per stack,
  with an uploaded result record (`checked`, `before-acceptance` or
  `registry-phase`), a projection bound only to the receipt, and a
  distinct failure when the installed program differs from the applied
  base)
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
