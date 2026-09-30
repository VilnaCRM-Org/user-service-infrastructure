# User decisions — workload WA hardening

The user made these decisions explicitly in the Claude Code session on 2026-09-30. Each one counts as "resolved" in the sense of prd.md §6: an explicit, dated user decision. The user gave the D-4 and D-5 clarifications in a second chat message on the same date (2026-09-30); they replace the earlier D-4 and D-5 wording.

| ID | Decision | Date | Notes |
|---|---|---|---|
| D-1 | Valkey/Redis authentication uses **IAM auth** (task-role token, TLS, IAM-enabled ElastiCache user). There is no Redis password and no Redis rotation Lambda. | 2026-09-30 | Requires the user-service Redis client stories (S5.13). V-2 and V-5 still apply. |
| D-2 | ALB → task: **recorded risk acceptance in TEST; in-container TLS required in PROD before gate 2.** | 2026-09-30 | S3.5-B for TEST. For PROD, S3.5-A (the PROD HTTPS shape) merges before S4.10, and S5.20 (in-container TLS) is merged and published before gate 2. The PROD-shaped preview evidence runs after S3.5-A, as S4.7 precondition P-1. |
| D-3 | WAF placement: **REST API + WAF, private integration through a VPC link to the internal ALB.** | 2026-09-30 | V-10 decides between ALB-direct (VPC link V2) and an NLB fallback. S3.6 is dropped. |
| D-4 | CMK scope (clarified 2026-09-30): **one runtime CMK per environment encrypts (a) the USI-declared secrets, (b) every CloudWatch log group of the workload (ECS web and worker, DocumentDB audit and profiler, the BI function log groups, and any other log group this plan adds) and (c) the VPC flow-log S3 bucket (SSE-KMS).** The runtime key policy allows `logs.<region>.amazonaws.com` (with a `kms:EncryptionContext:aws:logs:arn` condition) and `delivery.logs.amazonaws.com`. **Separate CMKs** exist for JWT signing (RSA) and 2FA encryption. The **DocumentDB-managed master secret stays on the AWS-managed key.** | 2026-09-30 | Recorded in prd.md FR-10, FR-15, §6; per-key table in architecture.md AD-15a. |
| D-5 | Rotation (clarified 2026-09-30): **`APP_SECRET` and `OAUTH_ENCRYPTION_KEY` rotate every 90 days; forced re-login at rotation is accepted. `OAUTH_PASSPHRASE` is not rotated: the KMS JWT move (S1.8) retires it.** The DocumentDB master password stays on the AWS-managed 7-day rotation. | 2026-09-30 | No previous-key tolerance is built: S5.15 is dropped. |
| D-6 | The hard stop is **split into two gates**. Gate 1 admits TEST once hardening lands; gate 2 admits PROD after the TEST evidence exists. | 2026-09-30 | @Kravalg must still approve the specs/poc/README.md source PR (governance). |
| D-7 | Abandoning a failed first apply: **@Kravalg approves a reviewed recovery manifest; a saved-plan destroy removes exactly the listed resources; TEST only.** PROD is never abandoned automatically. | 2026-09-30 | Makes the abandon parts of FR-21, FR-22, S4.2, S4.3 and S5.7 and the AGENTS.md rule-14a amendment unconditional, under the constraints in architecture.md AD-16: every delete step matches the manifest 1:1, the classifier runs, the plan is saved, and the approver is @Kravalg (environment protection with Kravalg as sole reviewer plus the in-run approver check). A CODEOWNERS approval alone does not count. |

## Consequences the plan derives (not new decisions)

- The SNS alarm topic uses the runtime CMK. CloudWatch alarms cannot publish to a topic encrypted with the AWS-managed `alias/aws/sns` key, and the runtime CMK is the only CMK D-4 provides for runtime data.
- The ALB access-log bucket stays on SSE-S3, because ALB access logging supports only SSE-S3. DocumentDB storage, ElastiCache and SQS stay on their current AWS-managed encryption. D-4 does not name them, and this plan does not change them.
- Log groups outside this workload are outside D-4 (for example an AGI stage log group). The AGI owner decides them.

## Confirmed derived details (explicit user confirmation, 2026-09-30)

| ID | Decision |
|---|---|
| D-8 | The SNS alarm topic uses the runtime CMK, because CloudWatch alarms cannot publish to a topic on the AWS-managed SNS key. |
| D-9 | The ALB access-log bucket stays SSE-S3, the only server-side encryption ALB access logging supports. |
| D-10 | DocumentDB storage, ElastiCache and SQS keep their current AWS-managed encryption. |
| D-11 | A TEST abandon always retains both log buckets (the ALB access-log bucket and the flow-log bucket). |
| D-12 | The abandon rehearsal runs at the end of the TEST campaign (S4.6 steps 18–20) and is followed by a rebuild. |
| D-13 | A new TEST exercise role and a `test-exercise` environment run the live checks (S5.23, S4.16). |

Open ownership item: XP-14 (the PROD registry phase) is outside this plan and blocks gate 2 until someone owns it.
