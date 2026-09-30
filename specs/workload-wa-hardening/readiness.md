---
artifact: implementation-readiness
workflow: _bmad/bmm/workflows/3-solutioning/bmad-check-implementation-readiness (Validate mode)
task: workload-wa-hardening
source_baseline: 66776772979956de9c5abdbee7c45641a1b533fa
date: 2026-09-30
revision: 3
author: the planning agent that wrote revision 3 (NOT an independent reviewer)
independent_reviewer: none yet for revision 3; round 4 is requested
status: PENDING independent round-4 review
---

# Implementation readiness

## Verdict

**PENDING. Not PASS.** This file is written by the author of revision 3. It
records what was changed and why; it does not grade itself.

- Only an independent reviewer's PASS satisfies the planning gate.
- Revision 3 answers readiness round 3 (FAIL) and records the user decisions of
  2026-09-30.
- Round 4 has not run. Until it reports PASS, the stage is BLOCKED.

## Review history

| Round | Reviewer | Result | Handled in |
| --- | --- | --- | --- |
| 1 | independent `devops-sdlc:fr-nfr-reviewer` | FAIL: 3 blocking, 10 major, minors | revision 2 |
| 2 | independent reviewer | Result not stored in this bundle. The revision-2 `readiness.md` was written before it arrived and wrongly listed the reviewer as its author; this revision corrects that. | — |
| 3 | independent reviewer (findings relayed by the coordinator) | FAIL: B-1, B-2, M-1…M-13, m-1…m-12 | revision 3 (this file) |
| 4 | independent reviewer | requested, not run | — |

The round-3 minor findings arrived as one combined list. They are numbered
m-1…m-12 below in the order the coordinator relayed them.

## User decisions recorded 2026-09-30 (from the user in chat)

| ID | Decision | Where recorded |
| --- | --- | --- |
| D-1 | IAM auth for Valkey/Redis. The RBAC password and its rotation Lambda are removed; a `default` user with access string `off` stays. | `prd.md:285`, `architecture.md:101` |
| D-2 | Recorded risk acceptance for ALB→task HTTP in TEST; in-container TLS in PROD before gate 2. | `prd.md` §6 D-2 row, `prd.md:157` (FR-19) |
| D-3 | REST API + WAF. VPC link V2 directly to the ALB (V-10), NLB only as a reviewed fallback. | `prd.md` §6 D-3 row, `prd.md:176` (FR-28), `architecture.md:537` |
| D-6 | Two gates approved by the user; `@Kravalg` approval of the README source PR is still required. | `prd.md` §6 D-6 row, `prd.md:293` (§6.1) |
| D-4, D-5 | Defaults kept, marked "pending explicit user confirmation". Not decided. | `prd.md` §6 |
| D-7 | No default. An explicit decision is required before any abandon implementation. | `prd.md:291` |

## Round-3 finding → resolution map

Line numbers refer to revision 3 of each file.

| Finding | Resolution | Location |
| --- | --- | --- |
| B-1 Redis rotation Lambda network path; APIs of every VPC Lambda | Resolved by D-1: no Redis secret, rotation Lambda or rotation SG. New table lists every function and task, the APIs it calls and its network path (DocumentDB-managed rotation is AWS-managed; app rotation, seed and redeploy run outside the VPC; the bootstrap job needs only the `secretsmanager` endpoint and the DocumentDB port, no STS or docdb API). | `architecture.md:64`; `prd.md:101` (FR-04); `prd.md:156` (FR-18) |
| B-2 Preview and drift roles cannot read workload types | New FR-33 and BI story S5.17 in C-BI; S4.6 preconditions and step 3 depend on it; simulator-matrix regression for both roles. | `prd.md:181`; `epics-stories.md:710`; `architecture.md:439`; `epics-stories.md:600`, `:619` |
| M-1 No closed list of out-of-band fields | FR-32, AD-23 per-type list (ECS `desiredCount`; TEST autoscaling min/max; DocumentDB `masterUserSecrets[*].secretStatus`; none for ElastiCache users), C-contract story S1.11 with N1–N3 tests; V-13 on `--refresh --expect-no-changes`. | `prd.md:180`; `architecture.md:415`; `epics-stories.md:255`; `architecture.md:540` |
| M-2 Managed-secret ARN and bootstrap-job SG missing from XP-8; wrong claims | XP-8 now carries subnet IDs, bootstrap-job SG ID and the DocumentDB-managed secret ARN; exact-ARN (plus V-19 tag) grant after step 1; the "patterns need no apply output" claim is corrected. | `prd.md:332`; `architecture.md:221`; `epics-stories.md:715` (S5.5) |
| M-3 C-BI order: keys before roles | S5.1 creates every role with no KMS statements; S5.4 creates keys naming only existing roles, then the KMS identity statements; S5.3 functions reuse S5.1 roles. | `architecture.md:439`; `epics-stories.md:708`, `:711` |
| M-4 V-items lack method and live placement | V table with method, offline story, live S4.6 step and STOP/fallback for V-1…V-20; S4.6 steps name their V-items and STOP rules. | `architecture.md:521`; `epics-stories.md:597` |
| M-5 Recovery abandon/import outside saved plans | Import and abandon run as saved plans through the classifier; the removal plan's destructive steps must equal the manifest 1:1; the AGENTS.md rule-14a text, runbook and grants are explicit and happen only if D-7 decides so. | `architecture.md:307`, `:319`, `:328`; `prd.md:164` (FR-21), `:165` (FR-22) |
| M-6 No per-secret recovery decision | `secret_recovery_decision` per secret (`retain` or `schedule-deletion` 7–30 d; `force-delete` refused), recovery-role grant with condition keys (V-15), P/N/B cases. | `architecture.md:323`; `epics-stories.md:521`; `epics-stories.md:713` (S5.7); `prd.md` §5.1 FR-21 row |
| M-7 Endpoint policies not pinned; ECR layer bucket missing | AD-12a exact documents per endpoint, including the S3 gateway statement for `prod-<region>-starport-layer-bucket`; pack passes unmodified or through `reviewed_iam_documents` pins extended to `VpcEndpoint`; S3.3 P/N/B tests. | `architecture.md:268`; `prd.md:155` (FR-17); `epics-stories.md:427` |
| M-8 Seed not idempotent; Invocation replacement not critical | Seed returns `noop` when AWSCURRENT exists; input fixed to `{secret_arn, purpose}`; `aws:lambda/invocation:Invocation` added to `CRITICAL_TYPE_PATTERNS`; V-18. | `architecture.md:165`; `prd.md:102` (FR-05); `epics-stories.md:278` |
| M-9 No BI identity for PROD recovery and restore rehearsal | S5.18 restore-rehearsal identity, reader Lambda, network and grants; S5.19 `prod-recovery`; both in C-BI and in the ordered list. | `epics-stories.md:714`, `:717`; `architecture.md:64` (reader rows) |
| M-10 Defaults counted as resolutions; D-6 scope | "Resolved" defined as an explicit dated user decision; no default for D-6 or D-7; FR-31 gate 1 lists the applicable decisions; §6.1 lists what D-6 relaxes and keeps. | `prd.md:276`, `:291`, `:293`; `prd.md:179` (FR-31) |
| M-11 Gate 2 lacks gate-1 checks and a receipt schema | Gate 2 re-checks every gate-1 condition and requires a schema-validated sanitized receipt (run IDs, SHA, approver ≠ requester, hashes); N test for placeholder links. | `prd.md:179`, `:184`; `architecture.md:398`; `epics-stories.md:686` |
| M-12 Step-2 admission undefined; admission in non-contract stories | FR-34 and AD-18 define the create-only `step2` mode and its preconditions; new C-contract story S4.9 holds the step-2 and multi-arch admission moved out of S1.3 and S2.6. | `prd.md:182`; `architecture.md:364`; `epics-stories.md:550`; `epics-stories.md:184`, `:391` |
| M-13 Live-evidence counts wrong; NFR-06 simulate offline only | Recounted from the tables: 45 requirements, 40 offline-testable, 5 evidence-only NFRs, 33 FRs with live evidence (all but FR-29); NFR-06 is offline + live; `test_prd_counts` guards the numbers. | `prd.md:41`; `prd.md:209` (NFR-06) |
| m-1 Missing boundary and negative cells | Every §5.1 and §5.2 row now has P, N and B cells. | `prd.md` §5 (from line 216), `:260` (§5.2) |
| m-2 NFR-05 measure undefined | Measure defined: 13 h soak with zero IAM-path auth failures; single-key window W with the 5xx alarm and counted failures. | `prd.md:208` |
| m-3 Alarm fixtures for `AWSService`, denied calls, name vs ARN | PRD §3.2 matching rules; FR-13 N/B fixtures; S2.5 P1–P4, N1–N2, B1–B2. | `prd.md:134`; `prd.md:237`; `epics-stories.md:374` |
| m-4 FR-24 margins | 300 s margin: process ≤ 3000 s, window ≤ 3300 s; boundary 3000/3001. | `prd.md:167`; `prd.md:248` |
| m-5 Flow-log bucket encryption, delivery principal, `DeleteLogDelivery` | FR-15 names SSE-S3 default, SSE-KMS key-policy terms, the delivery bucket policy and `logs:DeleteLogDelivery`; V-16. | `prd.md:153`; `epics-stories.md:413` |
| m-6 FR-02 N case for unsupported engine | FR-02 raises for non-5.0 or elastic; §5.1 N cell; V-17. | `prd.md:99`, `:226` |
| m-7 AD-06 vs AD-18 ordering; step-2 health observation | AD-06 step-2 order; task definitions unchanged in step 2; AD-18 item 4 health observation; S4.6 step 7. | `architecture.md:165`, `:381`; `epics-stories.md:634` |
| m-8 S5.2 details | SLR creation with `iam:AWSServiceName`, attachment quota and policy size, `RotationLambdaARN`, and write denies for non-rotation principals (FR-07 resource policy plus the S5.2 denies). | `epics-stories.md:709`; `architecture.md:507`; `prd.md:104` (FR-07) |
| m-9 FR-28 live evidence unscheduled | S4.6 step 17; gate 2 requires it if PROD is public. | `epics-stories.md:660`; `prd.md:176` |
| m-10 `readiness.md` authorship and staleness; run-summary checklist | This file states its author and PENDING status; `run-summary.md` has an acceptance checklist. | this file (front matter); `run-summary.md` |
| m-11 Brief success metric 2 incoherent | Rewritten: rotation window, 5xx alarm does not fire, forced re-login per D-5. | `brief.md:67` |
| m-12 "every offline story above" | Replaced by an explicit gate-1 story, BI, decision and prerequisite list. | `epics-stories.md:600` |
| Added V-items (A-16, `StsGetCallerIdentityCalls`, A-20) | V-10 (REST VPC link V2 → ALB, docs and provider source verified 2026-09-30), V-11, V-12 (SES API endpoint now exists; A-20 corrected). | `architecture.md:537`–`:539` (V-10…V-12); `research.md:266`, `:270`, `:274` |

## Unresolved external prerequisites

These are recorded gates, not planning defects.

- **XP-1.** Central roles: the source (`d41c019`) is not in the local
  bootstrap clone.
- **XP-2.** N-11 apply-role capability; preview and drift read (S5.17).
- **XP-3.** CMKs, functions, restore-rehearsal identity, CloudTrail read
  events.
- **XP-4.** user-service work: #501 (still OPEN), non-root, MONGODB-AWS (V-1),
  the Redis IAM token provider (V-2), KMS signing and 2FA, in-container TLS
  for PROD, multi-arch images.
- **XP-5.** The AGI front door. The repository is still a scaffold.
- **XP-6.** The SNS subscription endpoint.
- **XP-7.** `.claude/devops-sdlc.json` is absent, so `validate-profile`
  returned BLOCKED. `do-sdlc-setup` must run before implementation.
- **XP-8.** Post-step-1 subnet IDs, bootstrap-job SG ID and DocumentDB-managed
  secret ARN for BI.

## Remaining user decisions

| ID | Needed before | State |
| --- | --- | --- |
| D-4 CMK scope | gate 1 (S1.9, S5.4) | default pending explicit confirmation |
| D-5 rotation cadence and impact | gate 1 (S1.6) | default pending explicit confirmation |
| D-7 abandon authority | any abandon implementation; gate 1 | open, no default |
| D-6 governance | S4.6 step 1 | user-approved; needs `@Kravalg` approval of the README PR |
| Conditional: V-1 fails | step 2 retry | would need a new decision (app DB user with a rotated password) |
| Conditional: V-5 requires a `default` password | step 1 retry | would need a new decision (no Pulumi-generated password allowed) |

## Skill applicability (devops-sdlc 14)

**Applicable and addressed:**

- security-iam
- state-migration
- observability
- cost-optimization
- backup-recovery (S4.8, S5.18)
- delivery-and-rollback (AD-19)
- drift-management (FR-32, S1.11, S5.17)
- python-pulumi
- infrastructure-quality
- evidence-and-coverage
- environment-lifecycle (PROD gate)
- incident-response (runbooks in S2.4)
- bmad-autonomous-planning

**SKIPPED:** terraform-terraspace, because the engine is Pulumi.
