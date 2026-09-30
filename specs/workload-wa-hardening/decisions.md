# User decisions — workload WA hardening

The user made these decisions explicitly in the Claude Code session on 2026-09-30. Each one counts as "resolved" in the sense of prd.md §6: an explicit, dated user decision.

| ID | Decision | Date | Notes |
|---|---|---|---|
| D-1 | Valkey/Redis authentication uses **IAM auth** (task-role token, TLS, IAM-enabled ElastiCache user). There is no Redis password and no Redis rotation Lambda. | 2026-09-30 | Requires the user-service Redis client stories (S5.13). V-2 and V-5 still apply. |
| D-2 | ALB → task: **recorded risk acceptance in TEST; in-container TLS required in PROD before gate 2.** | 2026-09-30 | S3.5-B for TEST; S5.20 → S3.5-A before S4.7. |
| D-3 | WAF placement: **REST API + WAF, private integration through a VPC link to the internal ALB.** | 2026-09-30 | V-10 decides between ALB-direct (VPC link V2) and an NLB fallback. S3.6 is dropped. |
| D-4 | CMK scope: **one runtime CMK per environment (secrets and logs), plus dedicated JWT-signing and 2FA-encryption CMKs.** The DocumentDB-managed master secret stays on the AWS-managed key because the provider cannot set a CMK on it. | 2026-09-30 | Confirms the plan default. |
| D-5 | Rotation cadence: **90 days for APP_SECRET, OAUTH_PASSPHRASE and OAUTH_ENCRYPTION_KEY; forced re-login at rotation is accepted.** The DocumentDB master password stays on the AWS-managed 7-day rotation. | 2026-09-30 | Confirms the plan default. |
| D-6 | The hard stop is **split into two gates**. Gate 1 admits TEST once hardening lands; gate 2 admits PROD after the TEST evidence exists. | 2026-09-30 | @Kravalg must still approve the specs/poc/README.md source PR (governance). |
| D-7 | Abandoning a failed first apply: **@Kravalg approves a reviewed recovery manifest; a saved-plan destroy removes exactly the listed resources; TEST only.** PROD is never abandoned automatically. | 2026-09-30 | Enables the abandon parts of S4.2 and S4.3 and the AGENTS.md rule-14a amendment, under the constraints in architecture.md (1:1 manifest match, classifier, saved plan). |
