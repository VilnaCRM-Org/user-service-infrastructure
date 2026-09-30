---
artifact: epics-stories
workflow: _bmad/bmm/workflows/3-solutioning/bmad-create-epics-and-stories (Create mode, non-interactive)
task: workload-wa-hardening
source_baseline: 66776772979956de9c5abdbee7c45641a1b533fa
date: 2026-09-30
revision: 2 (readiness iteration 1 findings addressed)
inputDocuments: [prd.md, architecture.md]
---

# Epics and stories: Well-Architected hardening of the user-service workload

## Requirements inventory

- **FRs:** FR-01…FR-31.
- **NFRs:** NFR-01…NFR-11.
- **Decisions:** D-1…D-7.
- **External prerequisites:** XP-1…XP-8.
- **Verification items:** V-1…V-8.

All of these are defined in `prd.md` and `architecture.md`.

**Repository keys:**

- USI = VilnaCRM-Org/user-service-infrastructure
- BI = VilnaCRM-Org/bootstrap-infrastructure
- US = VilnaCRM-Org/user-service
- AGI = VilnaCRM-Org/api-gateway-infrastructure

**Story conventions:**

- **Offline tests.** Every story keeps the quality floors (NFR-03).
- **Live items.** "Live (TEST)" items run only in the S4.6 live TEST campaign,
  after gate 1. Each needs explicit user authorization and Kravalg approval
  (NFR-04). This removes the circularity between the phase gate and live
  evidence.
- **Chains.** Stories follow the serialized chains in `architecture.md` §4.

## FR coverage map

| Req | Stories |
| --- | --- |
| FR-01 | S1.2 |
| FR-02 | S1.3, S5.5, S5.10, S5.1 |
| FR-03 | S1.3, S5.1 |
| FR-04 | S1.4, S5.3, S5.13 |
| FR-05 | S1.6, S5.3 |
| FR-06 | S5.11, S5.12, S1.8, S5.4 |
| FR-07 | S1.5, S5.1 |
| FR-08 | S1.7 |
| FR-09 | S1.1, S1.6, S4.2 (admission fail-closed) |
| FR-10 | S1.9, S5.4 |
| FR-11 | S2.1, S5.2 |
| FR-12 | S2.2 |
| FR-13 | S2.3, S2.4, S2.5, S5.4 |
| FR-14 | S2.6, S5.14, S3.3 |
| FR-15 | S3.1, S5.2 |
| FR-16 | S3.2 |
| FR-17 | S3.3 |
| FR-18 | S3.4, S1.3, S1.4 |
| FR-19 | S3.5 |
| FR-20 | S4.1 |
| FR-21 | S4.2, S4.3 |
| FR-22 | S4.3, S5.7 |
| FR-23 | S4.4 |
| FR-24 | S4.5, S5.6, S4.6 |
| FR-25 | S5.8, S4.6 |
| FR-26 | S5.9, S3.7 |
| FR-27 | S5.1, S5.2, S5.3, S5.4, S5.7 |
| FR-28 | S5.16, S3.6 (only if D-3=b) |
| FR-29 | S1.10 |
| FR-30 | S4.8 |
| FR-31 | S4.6, S4.7 |

| NFR | Stories |
| --- | --- |
| NFR-01 | S1.1, S1.6, S1.10, S4.1 |
| NFR-02 | S1.1, S1.10, plus the guardrail test in every USI story |
| NFR-03 | all |
| NFR-04 | S4.6, S4.7 |
| NFR-05 | S1.4, S1.6, S4.6 |
| NFR-06 | S5.1–S5.7 |
| NFR-07 | S1.1, S4.2, S4.4, S4.6 |
| NFR-08 | S2.4, S4.6 |
| NFR-09 | S4.3, S4.6 |
| NFR-10 | S1.7, S4.3, S4.6 |
| NFR-11 | S2.6 |

Every hard-stop precondition has an FR:

| Precondition | FRs |
| --- | --- |
| F-01, F-02, F-14 | FR-01…FR-10 |
| F-03, F-04, F-15 | FR-11…FR-14 |
| F-08, F-09 | FR-15…FR-19 |
| N-06 | FR-20…FR-22 |
| #57 | FR-23 |
| N-04 | FR-24 |
| #501 | FR-25 |
| Non-root | FR-26 |
| N-11 | FR-27 |
| Live TEST acceptance | FR-31 |

## Epic list

- **E1 Secrets and identity.** No human- or AI-usable long-lived secret.
- **E2 Operations.** Scales with load, pages an owned topic, reviewed cost.
- **E3 Network and TLS.** Least-privilege, observable traffic; the TLS
  posture is decided.
- **E4 Recovery, guard and admission.** Recoverable first deployment, runtime
  guard, two-gate admission, rollback and restore.
- **E5 Cross-repo prerequisites.** Central identities, grants, application
  changes and front door.

---

## Epic 1: Secrets and identity

### S1.1 (USI): Move secret generation out of Pulumi state and amend the contract

- **Chains:** C-contract and C-runtime head.
- **Scope:**
  - `runtime_secrets.py`: remove the Random and TLS generators and every
    `SecretVersion`;
  - the schema (AD-04);
  - `poc_contract.py`;
  - `poc_secret_observation.py`;
  - `poc_workload_secret_result.py`;
  - `poc_workload_topology.py`;
  - the Random and TLS runtime pins;
  - fixtures and tests.
- **V-8** is the first case.

**Acceptance criteria:**

- **P:** the graph has no `random:*`, `tls:*` or `SecretVersion` types.
- **P:** the registry contract digest is unchanged.
- **N:** a fixture re-adding `RandomPassword` or `SecretVersion` fails.
- **N:** a missing central function ARN or CMK gives BLOCKED admission.
- **B:** seed input with a `password` key is rejected.

**Risk:** ST (guarded by AD-09), CON.

### S1.7 (USI): ECS secret references by ARN (AWSCURRENT)

- **Chains:** after S1.1 in C-contract and C-runtime.
- **Scope:**
  - `ecs_secrets()` uses the ARN or `arn:key::`;
  - the validators record the observed AWSCURRENT as evidence only;
  - `secret-lifecycle.md`.

**Acceptance criteria:**

- **P:** `valueFrom` is the ARN or `arn:key::`.
- **N:** a version suffix fails.
- **B:** the lockout reference equals the Redis reference; the prior-receipt
  comparison uses ARN and name only.
- Doc markers are updated (NFR-10).

### S1.2 (USI): DocumentDB-managed primary password

- **Chains:** C-data head.

**Acceptance criteria:**

- **P:** `manage_master_user_password=True` and no `master_password`.
- **N:** a password config key raises.
- **B:** no `master_user_secret_kms_key_id` is passed; the A-05 exception is
  recorded.
- **Live (TEST):** `MasterUserSecret` is active and rotation is enabled
  (metadata).

### S1.3 (USI): DocumentDB IAM wiring, bootstrap-job SG, AD-18 step split, DSN tests

- **Chains:** C-data, C-network head, C-compute head.
- **Scope:**
  - plain-env `MONGODB_URL`;
  - remove `document_db_url`;
  - the `bootstrap-job` SG plus the DocumentDB ingress;
  - `initial_service_scale=0`;
  - step-2 admission requires the S5.5 evidence and the XP-8 metadata;
  - the FR-03 DSN regression tests (AD-20);
  - export the subnet and SG IDs.

**Acceptance criteria:**

- The PRD FR-02 and FR-03 rows.
- **N:** step 2 without evidence is refused.
- **Live (TEST):** the S4.6 campaign runs step 1 and step 2.

### S1.4 (USI): Redis authentication per D-1

- **Chains:** C-data, C-runtime, C-network.
- **Scope (RBAC default):**
  - disabled `default` and app users, a `UserGroup`, `user_group_ids`, no
    `auth_token`;
  - the `redis_user` secret with no version;
  - the `rotation-fn` SG (Redis port and endpoint 443) and the Redis SG
    ingress;
  - the seed input schema.
- **Scope (IAM):** the IAM user plus the `Connect` requirement.
- **V-5** is the first case.

**Acceptance criteria:**

- The PRD FR-04 rows for the chosen mode.
- The FR-18 rotation-fn SG rules.
- **Live (TEST):** two forced rotations with no Redis auth errors (NFR-05).

### S1.10 (USI): Legacy managed path fails closed

- **Chains:** C-data, C-compute, C-stack.
- **Scope:**
  - `stack.py` `UserServiceStack` managed mode raises for test and prod;
  - remove or guard `compute.py::_create_runtime_secrets` and the
    `data.py::_persist_url` fallback;
  - AD-22.

**Acceptance criteria:**

- **P:** managed test/prod without `RuntimeSecrets` raises.
- **N:** a graph containing any `SecretVersion` fails.
- **B:** dev and preview placeholder mode is unaffected.
- The social-login secrets future path is documented (FR-29).

### S1.9 (USI): CMK binding per D-4

- **Chains:** C-contract after S1.7.
- **Depends on:** the S5.4 central metadata values and D-4.

**Acceptance criteria:** the PRD FR-10 rows.

### S1.6 (USI): Rotation wiring and synchronous seed

- **Chains:** C-runtime after S1.4.
- **Depends on:** the S5.3 function names and ARNs, which are deterministic
  (`arn:aws:lambda:<region>:<acct>:function:<name>`), and D-5.
- **V-6 and V-7** are the first cases.
- **Scope:**
  - a seed `aws.lambda.Invocation` per rotated secret;
  - `SecretRotation(rotate_immediately=False)` `depends_on` the seed;
  - ECS `depends_on` both;
  - an output-schema test.

**Acceptance criteria:**

- The PRD FR-05 and FR-09 rows.
- **N:** an output key outside `{secret_arn, version_id, status}` fails.
- **B:** the schedule is at least the D-5 minimum.
- **Live (TEST):** a forced rotation, `RotationSucceeded`, a new deployment,
  and the impact measured per NFR-05.

### S1.5 (USI): Secret resource policies

- **Chains:** C-runtime after S1.6.
- **Depends on:** the S5.1 role ARNs.
- **V-3** is the first case.

**Acceptance criteria:**

- The PRD FR-07 rows.
- **N:** a `*` or empty allow-list fails.
- **Live (TEST):** a denied read by a test principal, and the S2.5 alarm
  fires.

### S1.8 (USI): Consume the KMS JWT and 2FA keys; drop the PEM purposes

- **Chains:** C-contract, C-runtime and C-compute (after S2.1).
- **Depends on:** S5.11, S5.12 and S5.4.

**Acceptance criteria:**

- The PRD FR-06 rows.
- **P:** the bootstrap command writes no PEM.
- **N:** re-adding a PEM purpose fails the schema.
- **B:** gate 1 is refused while any `non_rotatable` purpose exists.

## Epic 2: Operations

### S2.1 (USI): Web autoscaling

- **Chains:** new `autoscaling.py`, plus `compute.py` (`ignore_changes`) in
  C-compute after S1.10.

**Acceptance criteria:**

- The PRD FR-11 rows.
- **Live (TEST):** a load test.

### S2.2 (USI): Worker backlog autoscaling

- **Scope:** `autoscaling.py`, after S2.1.

**Acceptance criteria:**

- The PRD FR-12 rows.
- **Live (TEST):** a backlog scale-out.

### S2.3 (USI): Owned SNS topic

- **Scope:** new `observability.py`.
- The KMS key comes from S5.4. The subscription endpoint is XP-6.

**Acceptance criteria:** the PRD FR-13 topic rows.

### S2.4 (USI): Alarm catalogue and runbooks

- **Scope:** `observability.py`; the runbook section per alarm in
  `docs/sre-operations.md`.

**Acceptance criteria:**

- The PRD §3.1 and FR-13 rows.
- **B:** desired=0 does not alarm.
- **Live (TEST):** delivery within 5 min (NFR-08).

### S2.5 (USI): Security and rotation EventBridge rules

- **Scope:** `observability.py`. The pattern uses
  `userIdentity.sessionContext.sessionIssuer.arn` with `anything-but`.
- **Depends on:** S1.5.

**Acceptance criteria:**

- **P:** a fixture of an assumed-role event from a non-allow-listed role
  matches.
- **N:** an execution-role session event does not match.
- **B:** the rule state is `ENABLED_WITH_ALL_CLOUDTRAIL_MANAGEMENT_EVENTS`.

### S2.6 (USI + US): Cost and sustainability

- **Chains:** C-compute tail.
- **Depends on:** S5.14 and S3.3.
- **Scope:**
  - TEST scheduled actions;
  - ARM64 with a multi-arch admission check;
  - `docs/poc-cost-review.md`, which includes the endpoint, NAT and
    CloudTrail read-event costs.

**Acceptance criteria:** the PRD FR-14 rows; NFR-11.

## Epic 3: Network and TLS

### S3.2 (USI): Managed default SG

- **Chains:** C-network after S1.4.

**Acceptance criteria:** the PRD FR-16 rows.

### S3.1 (USI): VPC flow logs to S3

- **Chains:** C-network.
- **Scope:** new `flow_logs.py`; the bucket joins the N-06 import list.

**Acceptance criteria:** the PRD FR-15 rows.

### S3.3 (USI): VPC endpoints

- **Chains:** C-network.
- The endpoint SG admits the service, bootstrap-job and rotation-fn SGs.

**Acceptance criteria:** the PRD FR-17 rows.

### S3.4 (USI): Egress tightening

- **Chains:** C-network tail.

**Acceptance criteria:**

- The PRD FR-18 rows.
- **Live (TEST):** no rejected required flows.

### S3.5 (USI, plus US if A): ALB→task TLS decision

- (B) the doc plus a doc test.
- (A) an HTTPS target group on 8443, in C-compute after S1.8, depending on
  S5.9 and the US Caddy change.

**Acceptance criteria:** the PRD FR-19 rows.

### S3.6 (USI, only if D-3=b): WAF on the internal ALB

- **Scope:** WebACL with `forwarded_ip_config` (X-Forwarded-For with a
  fallback) and a spoofing analysis document.

**Acceptance criteria:**

- **P:** the association exists.
- **N:** an IP-based rule without a forwarded-IP config fails.
- **B:** TEST count mode for one week, with review.

### S3.7 (USI): Non-root capability drops and port

- **Chains:** C-compute after S3.5(A) or S1.8.
- **Depends on:** S5.9.

**Acceptance criteria:** the PRD FR-26 rows.

## Epic 4: Recovery, guard and admission

### S4.1 (USI): Sanitized operator diagnostics

- Independent.

**Acceptance criteria:** the PRD FR-20 and NFR-01 rows.

### S4.4 (USI): Runtime admission guard (#57)

- Independent.
- The runner reads `admission.<env>` from the installed `main` contract.

**Acceptance criteria:** the PRD FR-23 rows.

### S4.5 (USI): Measured N-04 timing

- **Scope:** runner timestamps plus a budget test over the recorded evidence.
- **Depends on:** S4.4.

**Acceptance criteria:**

- The PRD FR-24 rows.
- **Live (TEST):** measured during the S4.6 steps. If over the bound, S5.6 is
  required before S4.7.

### S4.2 (USI): Resume/abandon admission and fail-closed prior-checkpoint check

- **Chains:** C-contract after S1.8.
- **Scope:**
  - `poc_workload_admission.py`, `poc_workload_topology.py`;
  - `scripts/poc_registry_plan.py`: accepts the baseline after an abandon
    receipt;
  - the abandon-manifest schema: unprotects, deletion-protection change,
    snapshot decision with a collision check, `data_loss_decision`;
  - the AD-09 forbidden-URN check.
- **Depends on:** D-7.

**Acceptance criteria:**

- The PRD FR-21 rows.
- **N:** a prior checkpoint with `random:` is refused (FR-09 and AD-09).

### S4.3 (USI + BI): Reviewed CI recovery command

- **Chains:** C-contract.
- **Scope:**
  - `.github/workflows/recovery.yml`;
  - `scripts/poc_workload_recovery.py` (`export`, `release-lock`,
    `clear-pending`, `import`, `abandon`);
  - `import-list.json` covering every fixed-name resource, including the new
    E1–E3 ones;
  - the evidence schema;
  - USI `.github/CODEOWNERS` entries (`@Kravalg`) for these files;
  - `docs/poc-workload-recovery.md` made executable.
- **Depends on:** S4.2 and S5.7.

**Acceptance criteria:**

- The PRD FR-22 rows.
- **Live (TEST):** a rehearsal in S4.6 (NFR-09).

### S4.6 (USI): Gate 1 (TEST-only admission) and the live TEST campaign

- **Chains:** C-contract.
- **Depends on:** every offline story above, C-BI up to S5.7, D-1…D-7, and
  the one-time R-02 metadata observation.
- **Scope, in order.** Every live step needs separate authorization.
  1. A PR sets `phase: workload` and `admission: {test: true, prod: false}`,
     and rewrites the README hard stop plus its test into two gates
     (AD-21, D-6).
  2. Step-1 apply, with timing (S4.5).
  3. The XP-8 BI metadata and VPC attachment.
  4. S5.5.
  5. Step-2 apply.
  6. The live items of every story: rotation, alarms, scaling, network,
     denied read.
  7. The recovery rehearsal (S4.3).
  8. Clean drift.
  9. Rollback (AD-19).
  10. The FR-25 worker health check.

**Acceptance criteria:**

- **P:** a TEST acceptance receipt with all the evidence links.
- **N:** gate 1 with a missing offline marker or decision is refused.
- **B:** a PROD run is refused while `admission.prod` is false.

**Risk:** ST, L.

### S4.8 (USI): Restore rehearsal and rollback evidence

- **Scope:**
  - the restore runbook;
  - a TEST snapshot restore to a temporary cluster: a reviewed operator task
    with evidence, then the temporary cluster is deleted.
- **Depends on:** S4.6.

**Acceptance criteria:** the PRD FR-30 rows.

### S4.7 (USI): Gate 2 (PROD admission) and the PROD plan

- **Scope:** `admission.prod: true`, and the PROD promotion plan: recovery
  environment `prod-recovery`, PROD live acceptance, and D-2 resolved for
  PROD.
- **Depends on:** S4.6, S4.8, S5.6 (if triggered) and XP-5 for any public
  exposure.

**Acceptance criteria:**

- **P:** gate 2 is accepted with all the live evidence.
- **N:** any missing live item is refused.
- **B:** PROD recovery grants must exist before the PROD apply.

## Epic 5: Cross-repo prerequisites

| Story | Repo | Deliverable | Key acceptance (P / N / B) |
| --- | --- | --- | --- |
| S5.8 | US | Merge #501 | Merged; the image command equals the USI contract command (FR-25). |
| S5.1 | BI | Central ECS execution and task roles (secret patterns `name-??????`, deterministic ARNs; task role SQS, SES, KMS; `elasticache:Connect` only if D-1=IAM). XP-1: recover or re-author `d41c019`. | Simulator allows / out-of-scope denied / `iam:PassedToService` present |
| S5.2 | BI | Apply-role workload capability (N-11): ecs, ec2 (including flow logs and endpoints), elasticache (including users), docdb/rds, logs (`CreateLogDelivery`), cloudwatch, application-autoscaling plus SLR, elbv2, s3, secretsmanager (Create, PutResourcePolicy, RotateSecret, tagging), `lambda:InvokeFunction` on BI functions, events, sns, wafv2 (D-3=b), `PassRole` limited to the ECS roles. `GetSecretValue` and `GetFunction` denies stay. | Matrix allows / denies stay / conditions |
| S5.4 | BI | CMKs per D-4 (key policies including the cloudwatch and events principals for the SNS key); CloudTrail read management events | Grants only the listed principals / no broad `kms:*` / JWT key-change procedure |
| S5.3 | BI | App rotation (no VPC), redis-rbac rotation (VPC-ready, with the attachment applied after XP-8), redeploy (deterministic service ARNs), `seed` entries, Lambda permissions (`aws:SourceAccount`), `RotationSucceeded` rule, allow-listed secret patterns (NFR-06). V-4. | Step unit tests with overlap / `testSecret` failure means no stage move / second rotation drops the oldest; seed output has no material |
| S5.7 | BI | `test-recovery` environment, lock-prefix delete, state read and write, import read grants for the recovery role | Exactly the recovery set / PR-head assumption denied |
| S5.5 | BI (live) | `$external` bootstrap job (VPC Lambda, USI bootstrap-job SG), idempotent, with evidence | User exists with `readWrite` on the app database only / unapproved run refused / re-run makes no change |
| S5.6 | BI (conditional) | `MaxSessionDuration` plus `role-duration-seconds` | Covers the measured time plus margin |
| S5.9 | US | Non-root images (UID ≥1000, :8080 or :8443, supervisor socket under `/srv/app/var/run`) | Non-root `User` / bind to :80 fails / healthchecks pass |
| S5.10 | US | MONGODB-AWS check (V-1) | TEST connect / wrong role fails / survives credential refresh |
| S5.11 | US | KMS JWT signing (league and lexik), JWKS from `GetPublicKey` | Verifies / tampered rejected / dual-key window |
| S5.12 | US | KMS 2FA encryption with context `user_id` | Enrol and verify / wrong context fails / size bound |
| S5.13 | US | Redis per D-1 (V-2: RBAC URL parse test, or IAM token provider) | PRD FR-04 rows |
| S5.14 | US | Multi-arch publishing (amd64 and arm64, immutable `sha-` tags) | Both architectures / missing architecture refused by USI admission |
| S5.15 | US (optional, D-5) | Previous-key tolerance for `APP_SECRET` and `OAUTH_ENCRYPTION_KEY` | Not scheduled by default |
| S5.16 | AGI | REST API + WAF + VPC link V2 → internal ALB, custom domain, pipeline (D-3=a default) | Route reaches the service / direct ALB access from outside the VPC fails / 60-day inactivity documented |

---

## Independent vs shared changes

- **Shared or serialized:** the chains C-BI, C-contract, C-runtime, C-data,
  C-network, C-compute and C-stack in `architecture.md` §4. There is one
  writer per chain.
- **Independent:** these can run in parallel with at most three agents, after
  their chain heads:
  - S2.2;
  - S2.3 → S2.4 → S2.5;
  - S4.1;
  - S4.4 → S4.5 (offline part);
  - S3.5-B;
  - S5.8–S5.15 (US);
  - S5.16 (AGI).

## Ordered story list

| # | Story | Repo | Kind |
| --- | --- | --- | --- |
| 0 | Resolve D-1…D-7 | user | decision gate |
| 1 | S5.8 #501 | US | independent |
| 2 | S1.1 generation out of state + contract | USI | C-contract, C-runtime |
| 3 | S1.7 AWSCURRENT refs | USI | C-contract, C-runtime |
| 4 | S1.2 DocumentDB-managed password | USI | C-data |
| 5 | S1.3 DocumentDB IAM + bootstrap-job SG + step split + DSN tests | USI | C-data, C-network, C-compute |
| 6 | S1.4 Redis auth (D-1) + rotation-fn SG | USI | C-data, C-runtime, C-network |
| 7 | S1.10 legacy path fail-closed | USI | C-data, C-compute, C-stack |
| 8 | S5.1 central ECS roles | BI | C-BI |
| 9 | S5.2 apply-role capability (N-11) | BI | C-BI |
| 10 | S5.4 CMKs + CloudTrail read events | BI | C-BI |
| 11 | S1.9 CMK binding | USI | C-contract |
| 12 | S5.3 rotation, redeploy and seed functions | BI | C-BI |
| 13 | S1.6 rotation wiring + seed | USI | C-runtime |
| 14 | S1.5 secret policies | USI | C-runtime |
| 15 | S2.1 → S2.2 autoscaling | USI | C-compute, then independent |
| 16 | S2.3 → S2.4 → S2.5 topic, alarms, security rules | USI | independent |
| 17 | S5.10, S5.13, S5.11, S5.12 | US | independent (may start any time) |
| 18 | S1.8 KMS keys; drop PEM purposes | USI | C-contract, C-runtime, C-compute |
| 19 | S3.2 → S3.1 → S3.3 → S3.4 network | USI | C-network |
| 20 | S3.5-B TLS acceptance doc (default D-2) | USI | independent |
| 21 | S5.9 non-root → S3.5-A (only if D-2=A) → S3.7 | US → USI | C-compute |
| 22 | S5.14 multi-arch → S2.6 cost/Graviton | US → USI | C-compute tail |
| 23 | S5.16 front door (+S3.6 only if D-3=b) | AGI (USI) | independent |
| 24 | S4.1 diagnostics; S4.4 → S4.5 guard and timing | USI | independent |
| 25 | S4.2 resume/abandon + fail-closed prior check | USI | C-contract |
| 26 | S5.7 recovery grants | BI | C-BI |
| 27 | S4.3 recovery command | USI | C-contract |
| 28 | S4.6 gate 1 + live TEST campaign (step 1 → XP-8 → S5.5 → step 2 → live items → rehearsal → drift → rollback) | USI (+BI live) | final TEST, live |
| 29 | S5.6 if the timing is over the bound | BI | conditional |
| 30 | S4.8 restore rehearsal | USI | live TEST |
| 31 | S4.7 gate 2 + PROD plan | USI | PROD gate |

**No forward dependencies.** Every story depends only on lower-numbered rows.
BI inputs to USI are deterministic names, ARNs or patterns. The only
apply-derived values (subnet and SG IDs) flow through XP-8 inside step 28.
