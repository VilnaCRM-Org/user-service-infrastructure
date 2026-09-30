---
artifact: epics-stories
workflow: _bmad/bmm/workflows/3-solutioning/bmad-create-epics-and-stories (Create mode, non-interactive)
task: workload-wa-hardening
source_baseline: 66776772979956de9c5abdbee7c45641a1b533fa
date: 2026-09-30
revision: 3 (readiness round-3 findings addressed; user decisions of 2026-09-30 applied)
inputDocuments: [prd.md, architecture.md]
---

# Epics and stories: Well-Architected hardening of the user-service workload

## Requirements inventory

- **FRs:** FR-01…FR-34.
- **NFRs:** NFR-01…NFR-11.
- **Decisions:** D-1…D-7 (D-1, D-2, D-3 resolved and D-6 approved on
  2026-09-30; D-4 and D-5 are defaults pending explicit confirmation; D-7 is
  open with no default).
- **External prerequisites:** XP-1…XP-8.
- **Verification items:** V-1…V-20 (method and place in `architecture.md` §5).

All of these are defined in `prd.md` and `architecture.md`.

**Repository keys:**

- USI = VilnaCRM-Org/user-service-infrastructure
- BI = VilnaCRM-Org/bootstrap-infrastructure
- US = VilnaCRM-Org/user-service
- AGI = VilnaCRM-Org/api-gateway-infrastructure

**Story conventions:**

- **Offline tests.** Every story keeps the quality floors (NFR-03).
- **Verification items.** A story's docs or source V-items are its first
  acceptance cases. Its live V-items run only as numbered S4.6 steps.
- **Live items.** "Live (TEST)" items run only in the S4.6 live TEST campaign,
  after gate 1. Each needs explicit user authorization and Kravalg approval
  (NFR-04).
- **Chains.** Stories follow the serialized chains in `architecture.md` §4.

## FR coverage map

| Req | Stories |
| --- | --- |
| FR-01 | S1.2 |
| FR-02 | S1.3, S5.5, S5.10, S5.1 |
| FR-03 | S1.3, S5.1, S3.3 (SES endpoint) |
| FR-04 | S1.4, S5.1, S5.13 |
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
| FR-19 | S3.5-B (TEST), S5.20 + S3.5-A (PROD) |
| FR-20 | S4.1 |
| FR-21 | S4.2, S4.3 |
| FR-22 | S4.3, S5.7, S5.19 |
| FR-23 | S4.4 |
| FR-24 | S4.5, S5.6, S4.6 |
| FR-25 | S5.8, S4.6 |
| FR-26 | S5.9, S3.7 |
| FR-27 | S5.1, S5.2, S5.3, S5.4, S5.7, S5.18, S5.19 |
| FR-28 | S5.16, S4.6 step 17 |
| FR-29 | S1.10 |
| FR-30 | S4.8, S5.18 |
| FR-31 | S4.6, S4.7 |
| FR-32 | S1.11, S4.6 step 14 |
| FR-33 | S5.17, S4.6 step 3 |
| FR-34 | S4.9, S1.3, S4.6 steps 4–7 |

| NFR | Stories |
| --- | --- |
| NFR-01 | S1.1, S1.6, S1.10, S4.1 |
| NFR-02 | S1.1, S1.10, plus the guardrail test in every USI story |
| NFR-03 | all |
| NFR-04 | S4.6, S4.7 |
| NFR-05 | S1.4, S5.13, S1.6, S4.6 steps 9–10 |
| NFR-06 | S5.1–S5.7, S5.17, S5.18, S5.19, S4.6 step 3 |
| NFR-07 | S1.1, S4.2, S4.4, S4.9, S4.6 |
| NFR-08 | S2.4, S4.6 step 11 |
| NFR-09 | S4.3, S4.6 step 13 |
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
| N-11 | FR-27, FR-33 |
| Live TEST acceptance | FR-31, FR-32, FR-34 |

## Epic list

- **E1 Secrets and identity.** No human- or AI-usable long-lived secret.
- **E2 Operations.** Scales with load, pages an owned topic, reviewed cost.
- **E3 Network and TLS.** Least-privilege, observable traffic; the TLS
  posture is decided.
- **E4 Recovery, guard and admission.** Recoverable first deployment, runtime
  guard, two-step and two-gate admission, rollback and restore.
- **E5 Cross-repo prerequisites.** Central identities, grants, application
  changes and front door.

---

## Epic 1: Secrets and identity

### S1.1 (USI): Move secret generation out of Pulumi state and amend the contract

- **Chains:** C-contract and C-runtime head.
- **Scope:**
  - `runtime_secrets.py`: remove the Random and TLS generators and every
    `SecretVersion`; declared purposes `app_secret`, `oauth_encryption_key`
    (plus the interim `non_rotatable` KMS purposes until S1.8);
  - the schema (AD-04), including `admission`, `workload_step` and the
    `central` XP-8 fields;
  - `poc_contract.py`;
  - `poc_secret_observation.py`;
  - `poc_workload_secret_result.py`;
  - `poc_workload_topology.py`;
  - the Random and TLS runtime pins;
  - `test_prd_counts` (recomputes the PRD §1 denominator from the tables);
  - fixtures and tests.
- **V-8** is the first case (provider source).

**Acceptance criteria:**

- **P:** the graph has no `random:*`, `tls:*` or `SecretVersion` types.
- **P:** the registry contract digest is unchanged.
- **N:** a fixture re-adding `RandomPassword` or `SecretVersion` fails.
- **N:** a missing central function ARN or CMK gives BLOCKED admission.
- **N:** a Redis secret purpose is rejected by the schema (D-1 = IAM).
- **B:** seed input with any key other than `secret_arn` and `purpose` is
  rejected.

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
- **B:** the prior-receipt comparison uses ARN and name only.
- Doc markers are updated (NFR-10).
- **Live (TEST):** S4.6 step 7 (task definition has no version IDs).

### S1.2 (USI): DocumentDB-managed primary password

- **Chains:** C-data head.

**Acceptance criteria:**

- **P:** `manage_master_user_password=True` and no `master_password`.
- **N:** a password config key raises.
- **B:** no `master_user_secret_kms_key_id` is passed; the A-05 exception is
  recorded.
- **Live (TEST):** S4.6 step 4 (`MasterUserSecret` active, rotation enabled,
  metadata only).

### S1.3 (USI): DocumentDB IAM wiring, bootstrap-job SG, step-1 shape, DSN tests

- **Chains:** C-data, C-network head, C-compute head.
- **Scope:**
  - plain-env `MONGODB_URL`;
  - engine `5.0.0`, instance-based; anything else raises (V-17, docs);
  - remove `document_db_url`;
  - the `bootstrap-job` SG plus the DocumentDB ingress from it;
  - `initial_service_scale=0` and the step-1 resource set (FR-34), expressed
    as program structure only; the step-2 **admission** lives in S4.9
    (C-contract);
  - the FR-03 DSN regression tests (AD-20);
  - export the subnet IDs, the bootstrap-job SG ID and the DocumentDB-managed
    secret ARN (XP-8).

**Acceptance criteria:**

- The PRD FR-02 and FR-03 rows.
- **N:** engine version `4.0.0` raises; an elastic cluster raises.
- **B:** the step-1 graph contains no seed, rotation, secret policy or
  autoscaling target.
- **Live (TEST):** S4.6 steps 4 and 7.

### S1.4 (USI): Redis IAM authentication (D-1, decided)

- **Chains:** C-data, C-network, C-compute.
- **Scope:**
  - `transit_encryption_enabled=True`, `transit_encryption_mode="required"`,
    no `auth_token`;
  - the IAM app user (`type=iam`, `user_name == user_id`), the `default` user
    with access string `off`, a `UserGroup`, `user_group_ids` (AD-02);
  - plain env `REDIS_URL`, `REDIS_LOCKOUT_URL`, `REDIS_IAM_USER_ID`,
    `REDIS_REPLICATION_GROUP_ID` (lower case), `AWS_REGION`;
  - the Redis SG ingress from the service SG only;
  - no Redis secret, no rotation SG, no seed.
- **V-5** (docs + provider source) and **V-9** (docs) are the first cases.

**Acceptance criteria:**

- The PRD FR-04 rows.
- **N:** `auth_token` set, a Redis secret declared, TLS disabled or
  `preferred`, or `user_name ≠ user_id` raises.
- **B:** a mixed-case replication-group id is lower-cased in the env value.
- **Live (TEST):** S4.6 steps 4, 7 and 10 (13 h soak, NFR-05).

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
- **Depends on:** the S5.4 central metadata values and D-4 (default pending
  confirmation; the story may be written against the default but gate 1
  requires D-4 resolved).

**Acceptance criteria:** the PRD FR-10 rows. **Live (TEST):** S4.6 step 7
(`DescribeSecret` `KmsKeyId`).

### S1.11 (USI): Drift allow-list contract (FR-32)

- **Chains:** C-contract after S1.9.
- **Scope:**
  - `drift.out_of_band_fields` in the schema and contract, exactly the AD-23
    table;
  - `test_drift_allow_list.py`: every `ignore_changes` in the program is on
    the list;
  - `scripts/run_pulumi_drift_check.py`: after a refresh, any state change on
    an unlisted field fails the check, with the field named in the sanitized
    summary.
- **V-13** (docs + provider source) is the first case.

**Acceptance criteria:**

- **P:** program `ignore_changes` equals the list.
- **N1:** an extra `ignore_changes` field fails.
- **N2:** a refresh fixture changing `aws:elasticache/user:User.accessString`
  fails the drift check.
- **N3:** a list entry for a type not in the program fails (closed list).
- **B:** a refresh fixture changing only ECS `desiredCount` passes.
- **Live (TEST):** S4.6 step 14.

### S1.6 (USI): Rotation wiring and idempotent synchronous seed

- **Chains:** C-runtime after S1.7; C-guard head.
- **Depends on:** the S5.3 function names and ARNs, which are deterministic
  (`arn:aws:lambda:<region>:<acct>:function:<name>`), and D-5 (default
  pending confirmation).
- **V-6** (docs), **V-7** and **V-18** (provider source) are the first cases.
- **Scope:**
  - a seed `aws.lambda.Invocation` per rotated secret, input exactly
    `{secret_arn, purpose}`;
  - `SecretRotation(rotate_immediately=False)` `depends_on` the seed
    (AD-06 step-2 order);
  - an output-schema test;
  - `aws:lambda/invocation:Invocation` added to `CRITICAL_TYPE_PATTERNS` in
    `scripts/pulumi_ci_guardrails.py`.

**Acceptance criteria:**

- The PRD FR-05 and FR-09 rows.
- **N1:** an output key outside `{secret_arn, version_id, status}` fails.
- **N2:** a preview fixture that replaces or deletes a seed Invocation is
  classified critical and refused.
- **B1:** the schedule equals the D-5 minimum and is accepted; one day less
  is refused.
- **B2:** a seed fixture on a secret with AWSCURRENT returns `noop`.
- **Live (TEST):** S4.6 step 9 (forced rotation, `RotationSucceeded`, new
  deployment, NFR-05).

### S1.5 (USI): Secret resource policies

- **Chains:** C-runtime after S1.6.
- **Depends on:** the S5.1 and S5.3 role ARNs.
- **V-3** (docs) is the first case.

**Acceptance criteria:**

- The PRD FR-07 rows.
- **N1:** a `*` or empty allow-list fails.
- **N2:** a write-deny allow-list that includes the execution role fails.
- **B:** the managed-secret policy is emitted only when the V-3 flag in the
  contract is `confirmed`.
- **Live (TEST):** S4.6 steps 8 and 11.

### S1.8 (USI): Consume the KMS JWT and 2FA keys; drop the PEM purposes

- **Chains:** C-contract, C-runtime and C-compute (after S2.1).
- **Depends on:** S5.11, S5.12 and S5.4.

**Acceptance criteria:**

- The PRD FR-06 rows.
- **P:** the bootstrap command writes no PEM.
- **N:** re-adding a PEM purpose fails the schema.
- **B:** gate 1 is refused while any `non_rotatable` purpose exists.
- **Live (TEST):** S4.6 step 7 (login, JWT verification, 2FA).

## Epic 2: Operations

### S2.1 (USI): Web autoscaling

- **Chains:** new `autoscaling.py`, plus `compute.py` (`ignore_changes`) in
  C-compute after S1.10. The autoscaling targets belong to the step-2 set.

**Acceptance criteria:**

- The PRD FR-11 rows.
- **Live (TEST):** S4.6 step 12 (load test).

### S2.2 (USI): Worker backlog autoscaling

- **Scope:** `autoscaling.py`, after S2.1.

**Acceptance criteria:**

- The PRD FR-12 rows.
- **Live (TEST):** S4.6 step 12 (backlog scale-out).

### S2.3 (USI): Owned SNS topic

- **Scope:** new `observability.py`.
- The KMS key comes from S5.4. The subscription endpoint is XP-6.

**Acceptance criteria:** the PRD FR-13 topic rows.

### S2.4 (USI): Alarm catalogue and runbooks

- **Scope:** `observability.py`; the runbook section per alarm in
  `docs/sre-operations.md`.
- **V-11** (docs) is the first case.

**Acceptance criteria:**

- The PRD §3.1 and FR-13 rows.
- **B:** desired=0 does not alarm.
- **Live (TEST):** S4.6 step 11 (delivery within 5 min, NFR-08).

### S2.5 (USI): Security and rotation EventBridge rules

- **Scope:** `observability.py`, implementing the PRD §3.2 matching.
- **Depends on:** S1.5.

**Acceptance criteria:**

- **P1:** an assumed-role read from a non-allow-listed role matches.
- **P2:** an `AWSService` read invoked by an unlisted service matches.
- **P3:** a denied (`AccessDenied`) read matches.
- **P4:** a `PutSecretValue` by a non-rotation role matches.
- **N1:** an execution-role session read does not match.
- **N2:** a rotation-role `PutSecretValue` does not match.
- **B1:** name, full-ARN and partial-ARN `secretId` fixtures all match.
- **B2:** the rule state is `ENABLED_WITH_ALL_CLOUDTRAIL_MANAGEMENT_EVENTS`.
- **Live (TEST):** S4.6 step 11.

### S2.6 (USI + US): Cost and sustainability

- **Chains:** C-compute after S3.7.
- **Depends on:** S5.14 and S3.3.
- **Scope:**
  - TEST scheduled actions (their min/max fields are on the AD-23 list);
  - ARM64 in the program when the contract marks the image multi-arch; the
    **admission** check that refuses ARM64 without an arm64 manifest lives in
    S4.9 (C-contract);
  - `docs/poc-cost-review.md`, which includes the endpoint, NAT and
    CloudTrail read-event costs.

**Acceptance criteria:** the PRD FR-14 rows; NFR-11.

## Epic 3: Network and TLS

### S3.2 (USI): Managed default SG

- **Chains:** C-network after S1.4.

**Acceptance criteria:** the PRD FR-16 rows. **Live (TEST):** S4.6 step 12.

### S3.1 (USI): VPC flow logs to S3

- **Chains:** C-network.
- **Scope:** new `flow_logs.py`; the bucket and its policy per FR-15; the
  bucket joins the N-06 import list.
- **V-16** (docs) is the first case.

**Acceptance criteria:**

- The PRD FR-15 rows.
- **N:** a delivery statement without `aws:SourceArn` fails; SSE-KMS without
  the delivery principal in the key policy fails.
- **Live (TEST):** S4.6 step 12 (object delivered).

### S3.3 (USI): VPC endpoints with pinned policies

- **Chains:** C-network; C-guard after S1.6.
- **Scope:**
  - the endpoint set of FR-17; the SES API endpoint only if V-12 (docs)
    confirms the service;
  - the endpoint SG admits the service and bootstrap-job SGs;
  - the AD-12a documents as `tests/fixtures/endpoint-policies/*.json` and
    `test_endpoint_policies.py` (byte-equal after rendering);
  - the policy-pack path: each document passes
    `wildcard_iam_violations` unmodified, or S3.3 extends
    `reviewed_iam_documents` to `aws:ec2/vpcEndpoint:VpcEndpoint|<name>` with
    exact sha256 pins (governance review).
- **V-12**, **V-14** and **V-20** (docs) are the first cases.

**Acceptance criteria:**

- **P:** every rendered policy equals its fixture and passes the pack.
- **N1:** an extra action or statement fails the equality test and the pack.
- **N2:** a pin whose hash does not match fails.
- **N3:** an S3 gateway policy without the ECR layer bucket fails.
- **B:** the TEST and PROD renderings differ only in account and region.
- **Live (TEST):** S4.6 steps 3 and 7 (endpoint service lookup, image pull).

### S3.4 (USI): Egress tightening

- **Chains:** C-network tail.

**Acceptance criteria:**

- The PRD FR-18 rows.
- **N:** a `0.0.0.0/0` 443 rule without the V-12 fallback record fails.
- **Live (TEST):** S4.6 step 12 (no rejected required flows).

### S3.5-B (USI): TEST ALB→task TLS risk acceptance (D-2, decided)

- Independent: `docs/poc-alb-target-tls-acceptance.md` and a doc test. The
  document records the user's 2026-09-30 decision and states that it covers
  TEST only.

**Acceptance criteria:** the PRD FR-19 TEST rows; **N:** the doc without the
"TEST only" marker fails.

### S3.5-A (USI): PROD HTTPS target group on 8443 (D-2, decided)

- **Chains:** C-compute tail, after S2.6.
- **Depends on:** S5.20 (US in-container TLS) and S5.9.
- **Scope:** HTTPS target group and health check on 8443 for PROD; admission
  refuses a PROD stack with an HTTP target group.

**Acceptance criteria:** the PRD FR-19 PROD rows. **Live (TEST):** a
PROD-shaped preview in TEST (S4.6 step 16).

### S3.6: dropped

D-3 = REST API + WAF (decided 2026-09-30). WAF on the internal ALB is not
built.

### S3.7 (USI): Non-root capability drops and port

- **Chains:** C-compute after S1.8.
- **Depends on:** S5.9.

**Acceptance criteria:** the PRD FR-26 rows. **Live (TEST):** S4.6 step 16.

## Epic 4: Recovery, guard and admission

### S4.1 (USI): Sanitized operator diagnostics

- Independent.

**Acceptance criteria:** the PRD FR-20 and NFR-01 rows. **Live (TEST):** S4.6
step 13 (induced failure).

### S4.4 (USI): Runtime admission guard (#57)

- Independent.
- The runner reads `admission.<env>` from the installed `main` contract.

**Acceptance criteria:** the PRD FR-23 rows. **Live (TEST):** S4.6 step 2
(refusal observed for `prod` while `admission.prod` is false).

### S4.5 (USI): Measured N-04 timing

- **Scope:** runner timestamps plus a budget test over the recorded evidence,
  with the FR-24 margin bounds.
- **Depends on:** S4.4.

**Acceptance criteria:**

- The PRD FR-24 rows.
- **Live (TEST):** measured in S4.6 steps 4 and 7. If over the bound, S5.6
  is required before S4.7.

### S4.2 (USI): Resume/abandon admission and fail-closed prior-checkpoint check

- **Chains:** C-contract after S1.8.
- **Scope, always:**
  - `poc_workload_admission.py`, `poc_workload_topology.py`: `resume`;
  - the AD-09 forbidden-URN check.
- **Scope, only if D-7 = governed abandon:**
  - `abandon` admission;
  - `scripts/poc_registry_plan.py`: accepts the baseline after an abandon
    receipt;
  - the abandon-manifest schema: unprotects, deletion-protection change,
    snapshot decision with a collision check, `data_loss_decision`, one
    `secret_recovery_decision` per workload secret;
  - the 1:1 comparison of the removal plan's destructive steps with the
    manifest.
- **Depends on:** D-7 for the abandon scope (open, no default). The resume
  scope does not wait for D-7.

**Acceptance criteria:**

- The PRD FR-21 rows.
- **N1:** a prior checkpoint with `random:` is refused (FR-09 and AD-09).
- **N2 (abandon):** a manifest missing a `secret_recovery_decision` for one
  secret is refused; `force-delete` is refused.
- **N3 (abandon):** a removal plan with one extra or one missing destructive
  step is refused.
- **B (abandon):** `recovery_window_days` 7 and 30 accepted; 6 and 31
  refused.

### S4.9 (USI): Step-2 admission mode and multi-arch admission (FR-34)

- **Chains:** C-contract after S4.2.
- **Depends on:** S1.3 (step-1 shape), S1.6, S1.5, S2.1 (step-2 URN set),
  S2.6 (ARM64 flag).
- **Scope:**
  - admission mode `step2`: saved-plan steps only `create` or `same`; created
    URNs equal the step-2 set; no `update`, `replace` or `delete` of any
    step-1 URN;
  - step-2 preconditions: the S5.5 receipt and the XP-8 metadata in the
    installed `main` central metadata;
  - the step-2 health-observation evidence schema (AD-18 item 4);
  - the multi-arch admission check (moved from S2.6).

**Acceptance criteria:**

- The PRD FR-34 rows.
- **N1:** a step-2 plan updating the ECS service is refused.
- **N2:** step 2 without the S5.5 receipt or the XP-8 metadata is refused.
- **N3:** ARM64 without an arm64 manifest is refused.
- **B:** an all-`same` step-2 plan is admitted and changes nothing.

### S4.3 (USI + BI): Reviewed CI recovery command

- **Chains:** C-contract after S4.9; C-guard after S3.3.
- **Scope:**
  - `.github/workflows/recovery.yml` (`test-recovery`; `prod-recovery`
    without `abandon`);
  - `scripts/poc_workload_recovery.py` (`export`, `release-lock`,
    `clear-pending`, `import`, and `abandon` only if D-7 allows), with every
    mutation as a saved plan through the classifier (AD-16);
  - `import-list.json` covering every fixed-name resource, including the new
    E1–E3 ones;
  - the evidence schema;
  - USI `.github/CODEOWNERS` entries (`@Kravalg`) for these files;
  - `docs/poc-workload-recovery.md` made executable;
  - only if D-7 = governed abandon: the AGENTS.md rule-14a amendment and the
    abandon runbook section (AD-16).
- **Depends on:** S4.2 and S5.7.

**Acceptance criteria:**

- The PRD FR-22 rows.
- **N1:** an import plan containing a `create` or `update` step is refused.
- **N2:** `abandon` in `prod-recovery` is refused.
- **Live (TEST):** S4.6 step 13 (rehearsal, NFR-09).

### S4.6 (USI + BI live): Gate 1 (TEST-only admission) and the live TEST campaign

- **Chains:** C-contract after S4.3.
- **Preconditions (explicit gate-1 list, replaces "every offline story"):**
  - USI merged: S1.1, S1.7, S1.2, S1.3, S1.4, S1.10, S1.9, S1.11, S1.6, S1.5,
    S1.8, S2.1, S2.2, S2.3, S2.4, S2.5, S2.6, S3.2, S3.1, S3.3, S3.4, S3.5-B,
    S3.7, S4.1, S4.4, S4.5, S4.2, S4.9, S4.3;
  - US merged and published: S5.8, S5.9, S5.10, S5.11, S5.12, S5.13, S5.14;
  - BI applied: S5.1, S5.2, S5.17, S5.4, S5.3, S5.7;
  - decisions resolved (explicit, dated, PRD §6): D-1, D-2 (TEST), D-4, D-5,
    D-6, D-7;
  - XP-6 (subscription endpoint) and XP-7 (profile) present;
  - the R-02 metadata observation receipt.
- **Steps, in order.** Every step needs separate authorization. Each names
  its V-items and its STOP rule. A STOP ends the campaign until the named fix
  lands; the stack is recovered through S4.3.
  1. **Gate-1 PR:** `phase: workload`, `admission: {test: true, prod: false}`,
     and the README hard stop plus its test rewritten into two gates (AD-21,
     PRD §6.1). Needs `@Kravalg` approval (D-6 governance). STOP: not
     approved.
  2. **R-02 re-observation** (read-only) and runtime-guard refusal for `prod`
     observed (FR-23). STOP: any workload URN present → AD-09.
  3. **Read-only live checks:** live `iam:SimulatePrincipalPolicy` for the
     apply, preview, drift, task, execution, rotation, redeploy, bootstrap-job
     and recovery roles (FR-27, FR-33, NFR-06, V-6, V-15);
     `DescribeVpcEndpointServices` for V-12. STOP: any required action
     denied or any forbidden action allowed. Fallback for V-12: FR-18 NAT
     variant, recorded, before step 4.
  4. **Step-1 saved-plan apply** with timing (FR-24, FR-34). Checks: V-5
     (users and group accepted), V-17 (engine), `MasterUserSecret` active
     (FR-01), services at 0. STOP: V-5 fails → user decision; any failure →
     S4.3 resume.
  5. **XP-8 BI metadata PR** (subnet IDs, bootstrap-job SG ID,
     DocumentDB-managed secret ARN); V-19 via read-only `DescribeSecret`
     metadata; the exact-ARN grant and VPC attachment applied (S5.5).
     Fallback for V-19: exact ARN only.
  6. **S5.5 bootstrap job** run. STOP: user not created → escalate.
  7. **Step-2 saved-plan apply** (S4.9 create-only admission) and the step-2
     health observation (AD-18 item 4): V-1 (MONGODB-AWS), V-2 (Redis IAM
     client), V-14 and V-20 (image pull through endpoints), FR-08 and FR-10
     metadata, FR-06 login/JWT/2FA, timing (FR-24). STOP: health fails →
     roll back to 0 tasks by saved plan; V-1 failure → user decision; V-2
     failure → US fix.
  8. **V-3 check:** forced rotation of the DocumentDB-managed secret with its
     policy in place; the app stays healthy. Fallback: delete that
     `SecretPolicy` by saved plan; residual recorded.
  9. **App-secret rotation exercise:** forced rotation of both purposes; V-4
     (`RotationSucceeded`), redeploy observed, NFR-05 single-key window
     measured. STOP: no redeploy → escalate.
  10. **Redis IAM soak, 13 h** (V-9, V-2, NFR-05 IAM paths). STOP: any auth
      failure → US fix.
  11. **Alarms:** NFR-08 delivery; denied `GetSecretValue` and
      `PutSecretValue` by a test principal (FR-07) with the S2.5 alarms;
      SES mail sent (FR-03, V-12).
  12. **Scaling and network:** FR-11 load test, FR-12 backlog scale-out,
      FR-15 object delivered (V-16), FR-16 describe, FR-18 flow-log review,
      V-11 metric observed. Fallback for V-11: drop the informational alarm.
  13. **Recovery rehearsal** (S4.3, NFR-09) with an induced failure (FR-20).
  14. **Clean drift** under the drift role (FR-32, V-13) after step 12 moved
      `desiredCount`. STOP: unlisted drift → investigate, no list widening.
  15. **Rollback** (AD-19).
  16. **FR-25 worker healthcheck, FR-26 non-root**, and a PROD-shaped preview
      in TEST for S3.5-A (FR-19), if S3.5-A has merged.
  17. **Front door (FR-28, V-10):** AGI TEST route through VPC link V2 → ALB
      and WAF sampled requests. Fallback: reviewed NLB variant. Required
      before any public exposure and before gate 2 if PROD is public.
  18. **Receipt:** assemble the PRD §3.3 receipt and validate it.

**Acceptance criteria:**

- **P:** a schema-valid TEST acceptance receipt with every step's evidence.
- **N1:** gate 1 with any listed story unmerged or any listed decision only
  defaulted is refused.
- **N2:** a receipt with a placeholder link is refused.
- **B:** a PROD run is refused while `admission.prod` is false.

**Risk:** ST, IAM, L.

### S4.8 (USI + BI live): Restore rehearsal and rollback evidence

- **Scope:**
  - the restore runbook;
  - a TEST snapshot restore to `<stack>-docdb-restore-rehearsal` under the
    S5.18 identity, `ModifyDBCluster` to a managed password, the S5.18 reader
    records the document-count sample, then the temporary cluster is deleted.
- **Depends on:** S4.6 and S5.18.

**Acceptance criteria:** the PRD FR-30 rows.

### S4.7 (USI): Gate 2 (PROD admission) and the PROD plan

- **Scope:** `admission.prod: true`, and the PROD promotion plan: recovery
  environment `prod-recovery`, PROD live acceptance.
- **Depends on:** S4.6, S4.8, S5.6 (if triggered), S5.19, S5.20 + S3.5-A
  (D-2 PROD), D-3 resolved, S5.16 with S4.6 step 17 evidence if PROD is
  publicly exposed, and a PROD live simulator run.

**Acceptance criteria:**

- **P:** gate 2 is accepted with every gate-1 check passing and the
  schema-valid receipt.
- **N1:** any gate-1 check failing is refused.
- **N2:** any missing receipt item or placeholder link is refused.
- **N3:** a PROD stack with an HTTP target group is refused.
- **B:** PROD recovery grants must exist before the PROD apply.

## Epic 5: Cross-repo prerequisites

| Story | Repo | Deliverable | Key acceptance (P / N / B) |
| --- | --- | --- | --- |
| S5.8 | US | Merge #501 | Merged / the image command differs from the USI contract command → refused (FR-25) / healthcheck grace period covers supervisor start |
| S5.1 | BI | **Every central role, created first (M-3):** ECS execution and task roles, app-rotation, redeploy and bootstrap-job roles. Secret patterns `name-??????`, deterministic ARNs; task role SQS, SES, `elasticache:Connect` on the exact replication-group and user ARNs (D-1). **No KMS statements** (they land in S5.4 after the keys exist) and no bootstrap-job grant on the DocumentDB-managed secret (it lands in S5.5 after XP-8). XP-1: recover or re-author `d41c019`. | Simulator allows / out-of-scope and `GetSecretValue` on the task role denied / `iam:PassedToService` present |
| S5.2 | BI | Apply-role workload capability (N-11): ecs, ec2 (including flow logs and endpoints), elasticache (including users and groups), docdb/rds, logs (`CreateLogDelivery`, `DeleteLogDelivery`), cloudwatch, application-autoscaling, elbv2, s3, secretsmanager (Create, Put/DeleteResourcePolicy, `RotateSecret` with `secretsmanager:RotationLambdaARN` limited to the BI functions, tagging), `lambda:InvokeFunction` on BI functions, events, sns. **SLRs:** `iam:CreateServiceLinkedRole` only with `iam:AWSServiceName` ∈ {ecs, ecs.application-autoscaling, elasticache, rds, elasticloadbalancing}, or BI pre-creates them. **Attachment quota:** the capability fits within the role's managed-policy attachment quota and the 6144-character managed-policy size; the story records the count and sizes. `PassRole` limited to the ECS roles. `GetSecretValue`, `PutSecretValue`, `UpdateSecretVersionStage` and `GetFunction` denies stay. V-15. | Matrix allows / denies stay; `RotateSecret` with another function ARN denied / attachment count and sizes within quota |
| S5.17 | BI | **Preview and drift read capability (FR-33, B-2):** read-only grants for `GitHubCiPreview-…-{env}` and `GitHubCiDrift-…-{env}` on every workload resource type (ec2, ecs, docdb/rds describe, elasticache, logs, cloudwatch, application-autoscaling, elbv2, wafv2, apigateway, events, sns, s3 configuration, secretsmanager metadata, kms describe). Simulator-matrix regression for both roles. | Every workload read allowed / `GetSecretValue`, `GetFunction`, `kms:Decrypt` and every write denied / the existing registry-phase matrix is unchanged |
| S5.4 | BI | CMKs per D-4 (pending confirmation). Key policies name only roles that already exist (all created in S5.1), plus the cloudwatch and events principals for the SNS key. Then, in the same story and after the keys exist, the task-role and app-rotation-role KMS identity statements that reference the new key ARNs. CloudTrail read management events. | Grants only the listed principals / no broad `kms:*`; a key policy naming a role absent from the S5.1 inventory fails the offline check / JWT key-change procedure |
| S5.3 | BI | Functions using the S5.1 roles: app rotation + idempotent seed (no VPC), redeploy (no VPC, deterministic service ARNs), bootstrap-job function package (VPC attachment deferred to S5.5), Lambda permissions (`aws:SourceAccount`), `RotationSucceeded` rule, allow-listed secret patterns (NFR-06). V-4 (docs). | Step unit tests / `testSecret` failure means no stage move / seed on a secret with AWSCURRENT returns `noop`; seed output has no material |
| S5.7 | BI | `test-recovery` environment, lock-prefix delete, state read and write, import read grants for the recovery role; **only if D-7 = governed abandon:** `secretsmanager:DeleteSecret` (`RecoveryWindowInDays` ≥ 7, `ForceDeleteWithoutRecovery=false`), `RestoreSecret`, `DescribeSecret` on the workload patterns, TEST only. | Exactly the recovery set / PR-head assumption denied; force delete denied / recovery window 7 allowed, 6 denied |
| S5.18 | BI | **Restore-rehearsal identity (FR-30, M-9):** an operator role for `rds:RestoreDBClusterFromSnapshot`, `CreateDBInstance`, `ModifyDBCluster`, `Describe*`, `DeleteDBInstance`, `DeleteDBCluster` conditioned on `<stack>-docdb-restore-rehearsal`; a VPC-attached reader Lambda (USI subnets, bootstrap-job SG) with `GetSecretValue` on the temporary cluster's managed secret by tag condition (V-19) or a reviewed ephemeral exact-ARN grant; network uses the existing DocumentDB SG and subnet group. | Restore and read allowed for the rehearsal name / restore to any other name and delete of the real cluster denied / reader cannot read the real cluster's secret |
| S5.5 | BI (live) | XP-8 metadata PR; exact-ARN `GetSecretValue` grant (plus tag condition if V-19); VPC attachment; `$external` bootstrap job run, idempotent, with evidence. Runs as S4.6 steps 5–6. | User exists with `readWrite` on the app database only / unapproved run refused / re-run makes no change |
| S5.6 | BI (conditional) | `MaxSessionDuration` plus `role-duration-seconds` | Covers the measured time plus the 300 s margin / below-margin value refused / exactly at the margin accepted |
| S5.19 | BI | **PROD recovery (M-9):** `prod-recovery` environment and recovery-role grants mirroring S5.7 without any abandon or delete grant. | Exactly the recovery set / delete actions denied / PR-head assumption denied |
| S5.9 | US | Non-root images (UID ≥1000, :8080, supervisor socket under `/srv/app/var/run`) | Non-root `User` / bind to :80 fails / healthchecks pass |
| S5.20 | US | **In-container TLS for PROD (D-2):** Caddy internal certificate on :8443, HTTPS health endpoint | HTTPS responds on 8443 / plain HTTP on 8443 refused / certificate renewal before expiry |
| S5.10 | US | MONGODB-AWS check (V-1 source) | TEST connect / wrong role fails / survives credential refresh |
| S5.11 | US | KMS JWT signing (league and lexik), JWKS from `GetPublicKey` | Verifies / tampered rejected / dual-key window |
| S5.12 | US | KMS 2FA encryption with context `user_id` | Enrol and verify / wrong context fails / size bound |
| S5.13 | US | **Redis IAM token provider (D-1):** SigV4 token per new connection from the task-role credentials (lower-case replication-group id, user id), `AUTH [user, token]` over TLS, re-`AUTH` or reconnect before 11 h, no re-auth inside `MULTI`/Lua, a Symfony `RedisAdapter` connection factory for `REDIS_URL` and `REDIS_LOCKOUT_URL`, `auth_failure{backend=redis}` log metric. V-2 and V-9 (source and docs). | Integration test against a local ACL Valkey 7.2 authenticates / an expired or wrong-user token fails with a counted `auth_failure` / a connection aged 11 h re-authenticates; token regenerated when credentials rotate |
| S5.14 | US | Multi-arch publishing (amd64 and arm64, immutable `sha-` tags) | Both architectures / missing architecture refused by USI admission (S4.9) / manifest digest pinned |
| S5.15 | US (optional, D-5) | Previous-key tolerance for `APP_SECRET` and `OAUTH_ENCRYPTION_KEY` | Not scheduled unless D-5 is decided with it |
| S5.16 | AGI | REST API + WAF + VPC link V2 **directly to the internal ALB** (`integration_target`), custom domain, pipeline (D-3, decided). V-10 (docs and provider source). | Route reaches the service / direct ALB access from outside the VPC fails; an NLB target without a recorded fallback fails / 60-day inactivity documented |

---

## Independent vs shared changes

- **Shared or serialized:** the chains C-BI, C-contract, C-runtime, C-data,
  C-network, C-compute, C-stack and C-guard in `architecture.md` §4. There is
  one writer per chain.
- **Independent:** these can run in parallel with at most three agents, after
  their chain heads:
  - S2.2;
  - S2.3 → S2.4 → S2.5;
  - S4.1;
  - S4.4 → S4.5 (offline part);
  - S3.5-B;
  - S5.8–S5.15 and S5.20 (US);
  - S5.16 (AGI).

## Ordered story list

| # | Story | Repo | Kind |
| --- | --- | --- | --- |
| 0 | Record D-1, D-2, D-3, D-6 (done 2026-09-30); obtain explicit D-4 and D-5 confirmation and the D-7 decision | user | decision gate (gate 1 needs all) |
| 1 | S5.8 #501 | US | independent |
| 2 | S1.1 generation out of state + contract | USI | C-contract, C-runtime |
| 3 | S1.7 AWSCURRENT refs | USI | C-contract, C-runtime |
| 4 | S1.2 DocumentDB-managed password | USI | C-data |
| 5 | S1.3 DocumentDB IAM + bootstrap-job SG + step-1 shape + DSN tests | USI | C-data, C-network, C-compute |
| 6 | S1.4 Redis IAM auth (D-1) | USI | C-data, C-network, C-compute |
| 7 | S1.10 legacy path fail-closed | USI | C-data, C-compute, C-stack |
| 8 | S5.1 every central role (no KMS statements) | BI | C-BI |
| 9 | S5.2 apply-role capability (N-11) | BI | C-BI |
| 10 | S5.17 preview and drift read capability | BI | C-BI |
| 11 | S5.4 CMKs, then KMS identity statements; CloudTrail read events | BI | C-BI |
| 12 | S1.9 CMK binding | USI | C-contract |
| 13 | S1.11 drift allow-list contract | USI | C-contract |
| 14 | S5.3 rotation, seed, redeploy and bootstrap-job functions (roles from S5.1) | BI | C-BI |
| 15 | S1.6 rotation wiring + idempotent seed + Invocation critical | USI | C-runtime, C-guard |
| 16 | S1.5 secret policies | USI | C-runtime |
| 17 | S2.1 → S2.2 autoscaling | USI | C-compute, then independent |
| 18 | S2.3 → S2.4 → S2.5 topic, alarms, security rules | USI | independent |
| 19 | S5.10, S5.13, S5.11, S5.12 | US | independent (may start any time) |
| 20 | S1.8 KMS keys; drop PEM purposes | USI | C-contract, C-runtime, C-compute |
| 21 | S3.2 → S3.1 → S3.3 → S3.4 network | USI | C-network, C-guard |
| 22 | S3.5-B TEST TLS risk acceptance | USI | independent |
| 23 | S5.9 non-root → S3.7 | US → USI | C-compute |
| 24 | S5.14 multi-arch → S2.6 cost/Graviton | US → USI | C-compute |
| 25 | S5.16 front door | AGI | independent |
| 26 | S4.1 diagnostics; S4.4 → S4.5 guard and timing | USI | independent |
| 27 | S4.2 resume (+ abandon only if D-7 allows) + fail-closed prior check | USI | C-contract |
| 28 | S4.9 step-2 admission + multi-arch admission | USI | C-contract |
| 29 | S5.7 test-recovery grants | BI | C-BI |
| 30 | S4.3 recovery command | USI | C-contract, C-guard |
| 31 | S5.18 restore-rehearsal identity | BI | C-BI |
| 32 | S4.6 gate 1 + live TEST campaign (steps 1–18, including S5.5) | USI (+BI live) | final TEST, live |
| 33 | S5.6 if the timing is over the bound | BI | conditional |
| 34 | S4.8 restore rehearsal | USI (+BI live) | live TEST |
| 35 | S5.20 in-container TLS → S3.5-A PROD HTTPS target group | US → USI | C-compute tail |
| 36 | S5.19 prod-recovery | BI | C-BI |
| 37 | S4.7 gate 2 + PROD plan | USI | PROD gate |

**No forward dependencies.** Every story depends only on lower-numbered rows.
BI inputs to USI are deterministic names, ARNs or patterns. The only
apply-derived values (subnet IDs, bootstrap-job SG ID, DocumentDB-managed
secret ARN) flow through XP-8 inside row 32 (S4.6 step 5).
