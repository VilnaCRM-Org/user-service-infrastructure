---
artifact: implementation-readiness
workflow: _bmad/bmm/workflows/3-solutioning/bmad-check-implementation-readiness (Validate mode)
task: workload-wa-hardening
source_baseline: 66776772979956de9c5abdbee7c45641a1b533fa
date: 2026-09-30
reviewer: independent agent devops-sdlc:fr-nfr-reviewer (read-only; not the author)
---

# Implementation readiness

## Verdict

**BLOCKED.** This is not PASS.

- Independent review iteration 1 returned **FAIL**, with 3 blocking, 10 major
  and several minor findings.
- All findings were addressed in revision 2 of `prd.md`, `architecture.md` and
  `epics-stories.md`. `research.md` and `brief.md` were synced to match.
- The same reviewer was asked to re-review revision 2 (iteration 2). Its
  result had not arrived when this file was written.
- Per the procedure, only an independent PASS satisfies the gate. The planning
  gate therefore stays open until iteration 2 reports PASS.

Iterations used: 2 of 5. Iteration 2 is still pending.

## Iteration 1 findings and their resolution in revision 2

| # | Severity | Finding | Resolution |
| --- | --- | --- | --- |
| 1 | blocking | The phase switch was circular: the guard needs `phase=workload` on main, but that switch needed live evidence. | Two-gate admission: FR-31, AD-21, D-6, S4.6 (gate 1 plus the live TEST campaign) and S4.7 (gate 2). |
| 2 | blocking | The Redis rotation Lambda had no network path, and its ordering formed a cross-repo loop. | Added the rotation-fn SG (FR-17, FR-18, S1.4) and the XP-8 metadata step. AD-18 now uses the order step 1 → VPC attach → S5.5 → step 2. |
| 3 | blocking | A `SecretVersion` cannot be read under the `GetSecretValue` deny. | USI now owns no `SecretVersion` (FR-09, AD-02, AD-06). Metadata goes through the seed input. V-8 added. |
| 4 | major | #501, non-root and N-11 had no FR. | Added FR-25 to FR-28. |
| 5 | major | The automation counts were inflated. | Recounted: 37/42 offline-testable, 5 evidence-only NFRs, 25 live FRs. Added the §5.2 NFR P/N/B table. |
| 6 | major | The legacy secret path was ignored. | Added FR-29, S1.10 and AD-22 (fail closed). |
| 7 | major | The dependency orders disagreed, and some ARNs were needed before they existed. | Chains aligned. Deterministic ARNs and `name-??????` patterns used. |
| 8 | major | File-scope collisions. | Per-file chains C-* defined in `architecture.md` §4. |
| 9 | major | NFR-05 conflicted with D-5, and FR-05 conflicted with AD-03. | NFR-05 scoped. The passphrase was removed from FR-05. |
| 10 | major | The abandon path was unresolved. | Abandon runs only through the recovery environment with a reviewed manifest. Added a snapshot decision, `poc_registry_plan.py` in S4.2, and D-7. |
| 11 | major | WAF on an ALB behind an HTTP API does not see client IPs. | D-3 default changed to REST API + WAF. S3.6 is conditional and uses `forwarded_ip_config`. |
| 12 | major | The alarm pattern matched the wrong identity field. | Now matches `sessionContext.sessionIssuer.arn` with `anything-but`, with assumed-role fixtures. |
| 13 | major | The AD-09 live preview conflicted with offline stories. | Replaced with a fail-closed offline admission check plus a one-time observation. |
| 14 | minor | Several small gaps. | Added the PROD gate (S4.7) and restore (S4.8/FR-30), V-7, the NFR-06 seed allow-list, the S5.4 key principals, AD-20, CODEOWNERS in USI and the BI VPC bootstrap job. Seed now runs before `SecretRotation`. |

## Unresolved external prerequisites

These are recorded gates, not planning defects.

- **XP-1.** Central ECS roles: the source (`d41c019`) is not in the local
  bootstrap clone.
- **XP-2.** N-11 apply-role capability.
- **XP-3.** CMKs, the rotation, redeploy and bootstrap functions, and
  CloudTrail read events.
- **XP-4.** user-service work: #501 (still OPEN), the non-root image,
  MONGODB-AWS (V-1), KMS signing and 2FA, and multi-arch images.
- **XP-5.** The AGI front door. The repository is still a scaffold.
- **XP-6.** The SNS subscription endpoint.
- **XP-7.** `.claude/devops-sdlc.json` is absent, so `validate-profile`
  returned BLOCKED. `do-sdlc-setup` must run before implementation.
- **XP-8.** Post-step-1 subnet and SG metadata for BI.

## User-owned decisions

| ID | Decision | Default |
| --- | --- | --- |
| D-1 | Valkey/Redis auth | Rotated RBAC password; the IAM alternative needs a US change. |
| D-2 | ALB→task TLS vs recorded acceptance | Acceptance for TEST; PROD needs an explicit choice. |
| D-3 | WAF placement | REST API + WAF + VPC link V2. |
| D-4 | CMK scope | Runtime CMK per environment plus JWT and 2FA CMKs; the DocumentDB-managed secret stays on the AWS key (A-05). |
| D-5 | Rotation cadence and impact | 90 d; forced re-login accepted. |
| D-6 | Two-gate hard-stop amendment | — |
| D-7 | Abandon authority | — |

## Skill applicability (devops-sdlc 14)

**Applicable and addressed:**

- security-iam
- state-migration
- observability
- cost-optimization
- backup-recovery (S4.8)
- delivery-and-rollback (AD-19)
- drift-management
- python-pulumi
- infrastructure-quality
- evidence-and-coverage
- environment-lifecycle (PROD gate)
- incident-response (runbooks in S2.4)
- bmad-autonomous-planning

**SKIPPED:** terraform-terraspace, because the engine is Pulumi.
