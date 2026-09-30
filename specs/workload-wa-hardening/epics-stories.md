---
artifact: epics-stories
workflow: _bmad/bmm/workflows/3-solutioning/bmad-create-epics-and-stories (Create mode, non-interactive)
task: workload-wa-hardening
source_baseline: 66776772979956de9c5abdbee7c45641a1b533fa
date: 2026-09-30
revision: 4 (readiness round-4 findings addressed; decisions D-1…D-7 of 2026-09-30 applied)
inputDocuments: [prd.md, architecture.md, decisions.md]
---

# Epics and stories: Well-Architected hardening of the user-service workload

## Requirements inventory

- **FRs:** FR-01…FR-35.
- **NFRs:** NFR-01…NFR-11.
- **Decisions:** D-1…D-7, all resolved by explicit user decisions dated
  2026-09-30 (`decisions.md`; D-4 and D-5 as clarified the same day; D-6
  approved, with `@Kravalg` approval of the README PR still required).
- **External prerequisites:** XP-1…XP-14.
- **Verification items:** V-1…V-26 (method and place in `architecture.md` §5).

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
| FR-01 | S1.2, S4.10 |
| FR-02 | S1.3, S5.5, S5.10, S5.1 |
| FR-03 | S1.3, S5.1, S3.3 (SES endpoint) |
| FR-04 | S1.4, S5.1, S5.13 |
| FR-05 | S1.6, S5.3 |
| FR-06 | S5.11, S5.12, S1.8, S5.4 |
| FR-07 | S1.5, S5.1, S4.9 (`policy-update`) |
| FR-08 | S1.7 |
| FR-09 | S1.1, S1.6, S4.2 (admission fail-closed), S4.10 (graph) |
| FR-10 | S1.9, S5.4, S3.1, S2.3, S2.4 |
| FR-11 | S2.1, S5.2, S4.9 (`rollback-zero`) |
| FR-12 | S2.2 |
| FR-13 | S2.3, S2.4, S2.5, S5.4 |
| FR-14 | S2.6, S5.14, S3.3 |
| FR-15 | S3.1, S5.2, S5.4 |
| FR-16 | S3.2 |
| FR-17 | S3.3 |
| FR-18 | S3.4, S1.3, S1.4 |
| FR-19 | S3.5-B (TEST), S5.20 + S3.5-A (PROD), S4.7 P-1 |
| FR-20 | S4.1 |
| FR-21 | S4.2, S4.3, S5.7, S5.21 |
| FR-22 | S4.3, S5.7, S5.19, S5.21 |
| FR-23 | S4.4 |
| FR-24 | S4.5, S5.6, S4.6 |
| FR-25 | S5.8, S4.6 |
| FR-26 | S5.9, S3.7, S4.10 (native gate) |
| FR-27 | S5.1, S5.2, S5.3, S5.4, S5.7, S5.17, S5.18a, S5.18b, S5.19, S5.23, S4.16 |
| FR-28 | S5.16, S4.6 step 17 |
| FR-29 | S1.10 |
| FR-30 | S4.8, S5.18a, S5.18b, S4.9 (`rollback-zero`) |
| FR-31 | S4.15, S4.6, S4.7 |
| FR-32 | S1.11, S4.6 step 14 |
| FR-33 | S5.17, S5.4 (KMS read), S4.6 step 3 |
| FR-34 | S4.9, S4.10, S1.3, S4.6 steps 4–7 |
| FR-35 | S4.11, S4.12, S4.13, S4.14, S4.3 (export and abandon receipts), S4.6 steps 4, 7, 7b, 13, 14, 20 |

| NFR | Stories |
| --- | --- |
| NFR-01 | S1.1, S1.6, S1.10, S4.1, S4.10, S4.6 steps 4a and 7a |
| NFR-02 | S1.1, S1.10, plus the guardrail test in every USI story |
| NFR-03 | all |
| NFR-04 | S4.6, S4.7, S5.21, S5.22 |
| NFR-05 | S1.4, S5.13, S1.6, S4.6 steps 9–10 |
| NFR-06 | S5.1–S5.7, S5.17, S5.18a, S5.18b, S5.19, S5.21, S4.6 step 3 |
| NFR-07 | S1.1, S4.2, S4.4, S4.9, S4.10, S4.11–S4.14, S4.6 |
| NFR-08 | S2.4, S4.6 step 11 |
| NFR-09 | S4.3, S4.6 steps 13, 19 and 20 |
| NFR-10 | S1.7, S4.3, S4.10, S4.13, S4.6 |
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
| Live TEST acceptance | FR-31, FR-32, FR-34, FR-35 |

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
  - the schema (AD-04), including `admission`, `workload_step`,
    `documentdb_secret_policy`, `start_at` and the `central` XP-8 fields;
  - the workload `central` fields of architecture AD-04 (every role, function,
    key and XP-8 field that S1.5, S2.5, S3.3 and admission read), the
    top-level `workload_operation` and `scaling` fields;
  - `poc_contract.py`;
  - `poc_secret_observation.py`;
  - the **transition rule** (architecture AD-25): the hardened shape renders
    only for a projection with `workload_step`. The Random and TLS
    generators and their runtime pins (`pyproject.toml` lines 16-17,
    `scripts/poc_provider_runtime.py` lines 56 and 62) stay in the
    pre-hardening branch, because the native test starts those providers.
    `poc_workload_topology.py`, `poc_workload_secret_result.py`, the native
    integration test and the pins are **not** edited here; S4.10 owns them;
  - `test_prd_counts` (recomputes the PRD §1 denominator from the tables);
  - fixtures and tests.
- **V-8** is the first case (provider source).

**Acceptance criteria:**

- **P:** with a `workload_step` projection, the graph has no `random:*`,
  `tls:*` or `SecretVersion` types.
- **P:** the registry contract digest is unchanged.
- **P:** `test_actual_workload_program_native_first_plan` passes unchanged
  (the pre-hardening projection still renders the installed graph).
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
- **Grant dependency:** the apply-role managed-password grants (S5.2, V-21)
  must be applied before step 1.
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

- **Chains:** C-contract after S1.7; C-data after S1.10.
- **Depends on:** the S5.4 central metadata values and D-4 (decided
  2026-09-30).
- **Scope:** `cmk` central metadata (runtime, JWT and 2FA key ARNs and
  aliases); the declared secrets' `kms_key_id` = runtime CMK; `kms_key_id` =
  runtime CMK on the DocumentDB audit and profiler log groups (`data.py`);
  no `master_user_secret_kms_key_id`. The ECS web and worker log groups
  (`compute.py`) get the runtime CMK in S1.8 (C-compute); the SNS topic in
  S2.3; the flow-log bucket in S3.1.

**Acceptance criteria:** the PRD FR-10 rows. **N:** a log group without
`kms_key_id` fails; a DocumentDB `master_user_secret_kms_key_id` fails.
**Live (TEST):** S4.6 step 7 (`DescribeSecret` `KmsKeyId`,
`DescribeLogGroups` `kmsKeyId`).

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
  (`arn:aws:lambda:<region>:<acct>:function:<name>`), and D-5 (decided
  2026-09-30: 90 days for `APP_SECRET` and `OAUTH_ENCRYPTION_KEY`;
  `OAUTH_PASSPHRASE` not rotated).
- **V-6** (docs), **V-7** and **V-18** (provider source) are the first cases.
- **Scope:**
  - a seed `aws.lambda.Invocation` per rotated secret, input exactly
    `{secret_arn, purpose}`;
  - `SecretRotation(rotate_immediately=False)` `depends_on` the seed
    (AD-06 step-2 order);
  - an output-schema test;
  - `aws:lambda/invocation:Invocation` added to `CRITICAL_TYPE_PATTERNS` in
    `scripts/pulumi_ci_guardrails.py` (lines 17-30). The same edit adds the
    two gaps found in round 4: `aws:docdb/` (the list has `aws:rds/` only)
    and `aws:s3/bucketV2:` (the list has `aws:s3/bucket:Bucket` only, and the
    access-log bucket is a `BucketV2`).

**Acceptance criteria:**

- The PRD FR-05 and FR-09 rows.
- **N1:** an output key outside `{secret_arn, version_id, status}` fails.
- **N2:** a preview fixture that replaces or deletes a seed Invocation is
  classified critical and refused.
- **N3:** a replace of `aws:docdb/cluster:Cluster` or
  `aws:s3/bucketV2:BucketV2` is classified critical.
- **N4:** a rotation entry for `oauth_passphrase` is refused (D-5).
- **B1:** a 90-day schedule is accepted; 89 and 91 are refused.
- **B2:** a seed fixture on a secret with AWSCURRENT returns `noop`.
- **Live (TEST):** S4.6 step 9 (forced rotation, `RotationSucceeded`, new
  deployment, NFR-05).

### S1.5 (USI): Secret resource policies

- **Chains:** C-runtime after S1.6.
- **Depends on:** the S5.1 and S5.3 role ARNs.
- **V-3** (docs) is the first case.
- **Scope:** the declared-secret policies; the managed-secret `SecretPolicy`
  (step-2 set, never deleted) rendering the document of the contract state
  `documentdb_secret_policy` ∈ {`deny-other-readers`, `allow-rotation`,
  `tls-only`} (architecture AD-08). The initial state is
  `deny-other-readers`.

**Acceptance criteria:**

- The PRD FR-07 rows.
- **N1:** a `*` or empty allow-list fails.
- **N2:** a write-deny allow-list that includes the execution role fails.
- **N3:** an unknown `documentdb_secret_policy` state fails the schema.
- **B:** each state renders exactly its fixture document; switching state
  changes only the `policy` input of the same URN.
- **Live (TEST):** S4.6 steps 8 and 11.

### S1.8 (USI): Consume the KMS JWT and 2FA keys; drop the PEM purposes

- **Chains:** C-contract, C-runtime and C-compute (after S2.1).
- **Depends on:** S5.11, S5.12 and S5.4.
- **Scope:** the JWT and 2FA key env values; the PEM, passphrase and 2FA
  purposes removed (D-5: `OAUTH_PASSPHRASE` is retired here, never
  rotated); `kms_key_id` = runtime CMK on the ECS web and worker log groups
  and on a pre-created `/aws/ecs/containerinsights/<cluster>/performance`
  group with retention, created before the cluster that enables
  `containerInsights` `enhanced` (`pulumi/app/compute.py` lines 213-217),
  so ECS never auto-creates it without the CMK (D-4).

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
- **Scope:** targets with `min = max(contract min, 1)` and
  `ignore_changes=["minCapacity","maxCapacity"]`; target-tracking policies;
  the one-time start action `<svc>-start-<seq>` (`at(<start_at>)`,
  `depends_on` the target and policies) and the `rollback-zero` stop action
  `<svc>-stop-<seq>` (`min = max = 0`) with the target's
  `suspendedState.scheduledScalingSuspended` set while stopped. Both are
  rendered from the contract `scaling` lists, so each start or stop is a new
  URN, and a name in `scaling.consumed` is not rendered (architecture
  AD-10). The TEST target value is set so that a load below the front
  door's WAF per-IP rate limit triggers scale-out; both values are recorded
  in the contract.
- **V-23** (docs, A-26) is the first case.

**Acceptance criteria:**

- The PRD FR-11 rows.
- **N:** a start action with `min < 1`, or a stop action in a plan that also
  changes the target, fails.
- **B:** adding `start` sequence 2 after `stop` sequence 1 renders exactly
  one new URN.
- **Live (TEST):** S4.6 step 7 (start observed, V-23), step 15 (stop and
  restart), step 17 (load test through the front door).

### S2.2 (USI): Worker backlog autoscaling

- **Scope:** `autoscaling.py`, after S2.1.

**Acceptance criteria:**

- The PRD FR-12 rows.
- **Live (TEST):** S4.6 step 12 (backlog scale-out).

### S2.3 (USI): Owned SNS topic

- **Scope:** new `observability.py`.
- The KMS key is the runtime CMK from S5.4 (D-4; CloudWatch alarms cannot
  publish to an `alias/aws/sns` topic). The subscription endpoint is XP-6.

**Acceptance criteria:** the PRD FR-13 topic rows; **N:** a topic without
the runtime CMK fails.

### S2.4 (USI): Alarm catalogue and runbooks

- **Scope:** `observability.py`; the runbook section per alarm in
  `docs/sre-operations.md`.
- **V-11** and **V-25** (docs) are the first cases.

**Acceptance criteria:**

- The PRD §3.1 and FR-13 rows.
- **B:** desired=0 does not alarm.
- **Live (TEST):** S4.6 step 11 (delivery within 5 min, NFR-08).

### S2.5 (USI): Security and rotation EventBridge rules

- **Scope:** `observability.py`, implementing the PRD §3.2 matching and
  the per-event-type allow-lists of PRD §3.2a, reading the role ARNs from
  the S1.1 `central` fields.
- **Depends on:** S1.5.

**Acceptance criteria (one P and one N per PRD §3.2a row, plus the §3.2
matching):**

- **P1:** an assumed-role read from a non-allow-listed role matches.
- **P2:** an `AWSService` read invoked by an unlisted service matches.
- **P3:** a denied (`AccessDenied`) read matches.
- **P4:** a `PutSecretValue` by a non-rotation role matches.
- **P5:** `DeleteSecret` or `RestoreSecret` by the TEST recovery role in
  PROD matches; `DeleteResourcePolicy` by any role other than the TEST
  recovery role matches.
- **P6:** `PutResourcePolicy` by any role other than the apply role
  matches; `RotateSecret` by an unlisted role matches.
- **P7:** a managed-secret `GetSecretValue` by a role other than the
  bootstrap-job and restore-reader roles matches; a managed-secret
  `DeleteSecret` by any caller other than `rds.amazonaws.com` matches.
- **N1:** an execution-role session read of a declared secret does not
  match.
- **N2:** a rotation-role `PutSecretValue` does not match.
- **N3:** `PutResourcePolicy` by the apply role does not match.
- **N4:** `DeleteSecret`, `RestoreSecret` and `DeleteResourcePolicy` by the
  TEST recovery role in TEST do not match.
- **N5:** a managed-secret `GetSecretValue` by the bootstrap-job or
  restore-reader role does not match; a managed-secret `DeleteSecret` by
  `rds.amazonaws.com` does not match.
- **N6:** `RotateSecret` by the apply, app-rotation or TEST exercise role
  does not match.
- **B1:** name, full-ARN and partial-ARN `secretId` fixtures all match, and
  an `rds!cluster-` managed-secret name matches the prefix.
- **B2:** the rule state is `ENABLED_WITH_ALL_CLOUDTRAIL_MANAGEMENT_EVENTS`.
- **Live (TEST):** S4.6 step 11.

### S2.6 (USI + US): Cost and sustainability

- **Chains:** C-compute after S3.7.
- **Depends on:** S5.14 and S3.3.
- **Scope:**
  - TEST night and weekend scheduled actions, created in **step 2** (they
    are in the FR-34 step-2 set; their min/max effect is on the AD-23 list);
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
- **Scope:** new `flow_logs.py`; the bucket and its policy per FR-15, with
  SSE-KMS on the runtime CMK (D-4, decided 2026-09-30), a bucket key and
  `force_destroy=false`; the bucket family joins the N-06 import list and
  is always `retain` in an abandon manifest (AD-16).
- **V-16** (docs) is the first case.

**Acceptance criteria:**

- The PRD FR-15 rows.
- **N:** a delivery statement without `aws:SourceArn` fails; SSE-S3 fails;
  SSE-KMS without the delivery principal in the runtime key-policy metadata
  fails; `force_destroy=true` fails.
- **Live (TEST):** S4.6 step 12 (object delivered).

### S3.3 (USI): VPC endpoints with pinned policies

- **Chains:** C-network; C-guard after S1.6.
- **Scope:**
  - the endpoint set of FR-17; the SES API endpoint only if V-12 (docs)
    confirms the service;
  - the endpoint SG admits the service and bootstrap-job SGs;
  - the AD-12a documents as `tests/fixtures/endpoint-policies/*.json` and
    `test_endpoint_policies.py` (byte-equal after rendering). The
    `secretsmanager` document has the deterministic `rds!cluster-*`
    statement limited by `aws:PrincipalArn` to the bootstrap-job and
    restore-reader role ARNs plus `aws:PrincipalAccount` (R4-B3). It never
    names an XP-8 value, so it renders offline and stays acyclic;
  - the pin identity (m9): `policy/reviewed_iam.py::_policy_identity` gains
    `aws:ec2/vpcEndpoint:VpcEndpoint|<serviceName>|<tags.Name>` (literal
    parts only; an unknown value returns no identity and fails closed;
    `vpcId` is not part of the key). `policy/vilnacrm_guardrails.yaml`
    `reviewed_iam_documents` gets one key per endpoint per environment, each
    with exactly one sha256 of the canonical rendered document for that
    environment. A governance-reviewed change (CODEOWNERS plus Kravalg).
- **V-12**, **V-14** and **V-20** (docs) are the first cases.

**Acceptance criteria:**

- **P:** every rendered policy equals its fixture and passes the pack.
- **P2:** a small offline evaluator over the rendered `secretsmanager`
  document allows `GetSecretValue` on `rds!cluster-abc` for the
  bootstrap-job and restore-reader role ARNs.
- **N1:** an extra action or statement fails the equality test and the pack.
- **N2:** a pin whose hash does not match fails; a TEST digest under a PROD
  key fails.
- **N3:** an S3 gateway policy without the ECR layer bucket fails.
- **N4:** the evaluator denies `GetSecretValue` on `rds!cluster-abc` for the
  ECS execution role, the task role and a principal of another account.
- **N5:** a `VpcEndpoint` with an unknown `tags.Name` has no pin identity
  and fails the pack.
- **B:** the TEST and PROD renderings differ only in account, region and
  role ARNs; each has its own pinned digest.
- **Live (TEST):** S4.6 steps 3 and 7 (endpoint service lookup, image
  pull) and step 6 (the bootstrap job reads the managed secret through the
  endpoint).

### S3.4 (USI): Egress tightening

- **Chains:** C-network tail.
- **Scope (m12):** first, `docs/poc-egress-inventory.md`, the outbound
  inventory. It lists every destination of the web and worker containers
  from the user-service configuration at the image digest (DocumentDB,
  Redis, each AWS API through its endpoint, SES, any OAuth, webhook or
  telemetry host), with port, protocol and path (endpoint, NAT or none), and
  a doc-marker test pins it. Then the SG rule sets of FR-18 remove
  `0.0.0.0/0` everywhere except the recorded V-12 fallback.

**Acceptance criteria:**

- The PRD FR-18 rows.
- **N:** a `0.0.0.0/0` 443 rule without the V-12 fallback record fails; an
  inventory row without a path fails; a destination in the user-service
  configuration that is missing from the inventory fails review (STOP before
  merge).
- **Live (TEST):** S4.6 step 12. STOP rule: a flow-log `REJECT` from the
  service SG to a destination missing from the inventory, or a failed
  health or feature check caused by egress, stops the campaign until a
  reviewed inventory and SG change lands.

### S3.5-B (USI): TEST ALB→task TLS risk acceptance (D-2, decided)

- Independent: `docs/poc-alb-target-tls-acceptance.md` and a doc test. The
  document records the user's 2026-09-30 decision and states that it covers
  TEST only.

**Acceptance criteria:** the PRD FR-19 TEST rows; **N:** the doc without the
"TEST only" marker fails.

### S3.5-A (USI): PROD HTTPS target group on 8443 (D-2, decided)

- **Chains:** C-compute tail, after S2.6; before S4.10, so the hardened
  topology (S4.10) and the PROD path (S4.14) include the PROD HTTPS shape
  (m1: S3.5-A moved earlier).
- **Depends on:** S5.9 (port layout). The S5.20 image (US in-container TLS)
  must be merged and published before gate 2 (S4.7), not before this story
  merges: only PROD renders the HTTPS target group, and only gate 2 admits
  PROD.
- **Scope:** HTTPS target group and health check on 8443 for PROD; admission
  refuses a PROD stack with an HTTP target group; TEST keeps HTTP (D-2).

**Acceptance criteria:** the PRD FR-19 PROD rows. **Live (TEST):** a
PROD-shaped preview in TEST, run after this story merges as S4.7
precondition P-1 (m1); it is not an S4.6 step.

### S3.6: dropped

D-3 = REST API + WAF (decided 2026-09-30). WAF on the internal ALB is not
built.

### S3.7 (USI): Non-root capability drops and port

- **Chains:** C-compute after S1.8.
- **Depends on:** S5.9.

**Acceptance criteria:** the PRD FR-26 rows. **Live (TEST):** S4.6 step 16.

## Epic 4: Recovery, guard and admission

Stories appear in chain order: S4.1; C-runner head S4.4 → S4.5; then the
C-contract tail S4.10 → S4.11 → S4.2 → S4.9 → S4.3 → S4.12 → S4.13 → S4.14 →
S4.15; S4.16; then the live stories S4.6 → S4.8 → S4.7.

### S4.1 (USI): Sanitized operator diagnostics

- Independent.

**Acceptance criteria:** the PRD FR-20 and NFR-01 rows. **Live (TEST):** S4.6
step 13 (induced failure).

### S4.4 (USI): Runtime admission guard (#57)

- **Chains:** C-runner head (it edits `scripts/poc_workload_runner.py`).
- The runner reads `admission.<env>` from the installed `main` contract.

**Acceptance criteria:** the PRD FR-23 rows. **Live (TEST):** S4.6 step 2
(refusal observed for `prod` while `admission.prod` is false).

### S4.5 (USI): Measured N-04 timing

- **Chains:** C-runner after S4.4.
- **Scope:** runner timestamps plus a budget test over the recorded evidence,
  with the FR-24 margin bounds.

**Acceptance criteria:**

- The PRD FR-24 rows.
- **Live (TEST):** measured in S4.6 steps 4 and 7. If over the bound, S5.6
  is required before S4.7.

### S4.10 (USI): Hardened first-workload topology, native gates and secret history (R4-M1)

- **Chains:** C-contract after S1.8; the only C-topology story (architecture
  AD-25).
- **Depends on (merged):** S1.1, S1.2, S1.3, S1.4, S1.5, S1.6, S1.7, S1.8,
  S1.9, S1.10, S2.1, S2.2, S2.3, S2.4, S2.5, S2.6, S3.1, S3.2, S3.3, S3.4,
  S3.5-A, S3.7.
- **Scope (the only story that edits these files):**
  - `scripts/poc_workload_topology.py`: `expected_graph` split into the
    step-1 and step-2 graphs, parameterized by stack (`test`, `prod`;
    replacing the hard-coded `-test-` names at lines 61, 859 and 1058), for
    every resource those stories add or remove (AD-25 list), including
    `kms_key_id` on every log group and the pre-created Container Insights
    group; the PROD HTTPS target group (S3.5-A); the named URN sets that S4.9
    admits (step-2 set, `rollback-zero` set, `policy-update` set); the
    native input gates;
  - the native capability gate (`specs/poc-workload-runner.md` lines
    79-82; `CONTAINER_DROPPED_CAPABILITIES`): web and worker drop `ALL`
    with no add-back, unprivileged port 8080, non-root `User`;
    `CONTAINER_SECRET_NAMES` (lines 40-50) is reduced to `APP_SECRET` and
    `OAUTH_ENCRYPTION_KEY`; Redis, DocumentDB and KMS values are plain env;
  - `scripts/poc_workload_secret_result.py` (spec lines 89-98; code lines
    121-135): after step 1, each declared secret has zero versions and no
    rotation, and the DocumentDB-managed secret is accepted with
    `RotationEnabled` true (managed) and one `AWSCURRENT`; after step 2,
    each declared secret has exactly one `AWSCURRENT`, `RotationEnabled`
    true, the BI `RotationLambdaARN` and 90-day rules; the release checker
    accepts a changed current version only after a later
    `LastRotatedDate` with the reviewed function; a rebuild variant accepts
    the retained secrets listed in an authenticated abandon receipt
    (architecture AD-16);
  - `tests/integration/test_poc_first_topology_native.py`: switched to the
    step-1 and step-2 projections for both stacks; `workload_step` made
    required; the pre-hardening program branch deleted with the Random and
    TLS generators and runtime pins (`pyproject.toml` lines 16-17,
    `scripts/poc_provider_runtime.py` lines 56 and 62);
  - `recovery/delete-actions.json`: for each resource type of the step-1 and
    step-2 graphs, the complete API set that the pinned `pulumi-aws`
    provider's delete path calls (drain and detach calls included, for
    example `ecs:UpdateService` before `ecs:DeleteService`,
    `ec2:DeleteRoute`, `sns:SetTopicAttributes`; V-26), with a test that
    every graph type has an entry. S5.7 grants it; S4.3 uses it;
  - `specs/poc-workload-runner.md` topology and checker text, with
    doc-marker tests.

**Acceptance criteria:**

- **P:** the actual program's native step-1 and step-2 plans are admitted
  by the new graphs, for `test` and for `prod`.
- **N1:** a step-1 plan containing any `random:`, `tls:` or `SecretVersion`
  type, or a web container keeping `NET_BIND_SERVICE`, is refused.
- **N2:** a step-1 result where a declared secret has a version (outside
  the rebuild variant), or a step-2 result where a declared secret has
  `RotationEnabled` false, is refused.
- **N3:** a log group without `kms_key_id` is refused; a `prod` graph with an
  HTTP target group is refused.
- **B:** the managed secret with `RotationEnabled` true and a single
  `AWSCURRENT` is accepted after step 1; a rotated version with a later
  `LastRotatedDate` is accepted by the release checker.

### S4.11 (USI): Receipts after every apply; anchor rebinding (FR-35 part 1)

- **Chains:** C-runner after S4.5; C-contract after S4.10 (it edits
  `poc_workload_admission.py`).
- **Scope:**
  - `schemas/poc-workload-step-receipt-v1.schema.json`,
    `poc-workload-export-receipt-v1` and `poc-workload-abandon-receipt-v1`,
    and `scripts/poc_workload_receipts.py` (write, publish, authenticate,
    latest-receipt lookup; architecture AD-24);
  - `scripts/poc_workload_runner.py`: a step receipt after every admitted
    `up-plan`, on the success path (after the S4.10 result checks) and on
    the failure path (final checkpoint through the trusted backend,
    `outcome: failed`); `_capture` (lines 44-47) binds to the mode's anchor;
  - `scripts/poc_workload_admission.py`: `inspect_registry` (lines 150-166)
    and `observe_workload` (lines 464-475) apply the mode → anchor table of
    AD-24 instead of the registry-only count and equality, for every mode
    except `first`, which keeps today's rule; the registry receipt stays the
    release identity.

**Acceptance criteria:**

- **P:** a successful step-1 fixture yields a schema-valid receipt bound to
  the new checkpoint; a failed apply fixture yields an `outcome: failed`
  receipt.
- **N1:** a receipt with a changed checkpoint sha256, run ID or contract
  digest is refused.
- **N2:** an unauthenticated receipt (no matching deployment status) is
  refused.
- **N3:** every existing negative still fails the same way for `first`
  (`workload-checkpoint-binding`, `workload-completed-registry-required`,
  `workload-registry-checkpoint-changed`, `workload-stack`,
  `workload-first-command`).
- **B:** a receipt for an older checkpoint of the same stack (stale) is
  refused.
- **Live (TEST):** S4.6 step 4.

### S4.2 (USI): Resume and abandon admission; fail-closed prior-checkpoint check

- **Chains:** C-contract after S4.11.
- **Decision:** D-7, decided 2026-09-30. The abandon scope is unconditional
  and TEST-only.
- **Scope:**
  - `poc_workload_admission.py`: `resume` (create or update of unfinished
    resources of the current step only), anchored on the latest failed or
    export receipt (S4.11);
  - the AD-09 forbidden-URN check;
  - `abandon` admission (architecture AD-16):
    - the unprotect-plan check (only `update` and `same`; the only
      non-state change is DocumentDB `deletion_protection`);
    - the removal-plan check: every op is `delete` or `same`; any other op
      is refused; the `delete` URNs, **of every resource type**, equal the
      manifest's `delete` and `retain` entries 1:1; the `same` URNs equal
      the registry baseline. `find_destructive_steps` is not the
      comparator, because it returns only critical types;
    - the `abandon-manifest.json` schema: one entry per checkpoint resource
      except the registry baseline (`delete` or `retain`); the log-bucket
      families always `retain` (a `delete` is refused); DocumentDB
      deletion-protection change; final-snapshot decision with a collision
      check (`<stack>-docdb-final`); `data_loss_decision`; one
      `secret_recovery_decision` per workload secret; the approver field
      (Kravalg's user ID).
- **V-24** (engine and provider source) is the first case.

**Acceptance criteria:**

- The PRD FR-21 rows.
- **N1:** a prior checkpoint with `random:` is refused (FR-09 and AD-09).
- **N2:** a manifest missing a `secret_recovery_decision` for one secret is
  refused; `force-delete` is refused.
- **N3:** a removal plan with one extra or one missing `delete` step is
  refused, including a non-critical type (fixture:
  `aws:ecs/service:Service`, `aws:cloudwatch/metricAlarm:MetricAlarm`).
- **N4:** a removal plan containing `replace`, `delete-replaced`, `discard`
  or `update` is refused.
- **N5:** a manifest with `delete` on the flow-log bucket, the ALB
  access-log bucket or any of their sub-resources is refused.
- **N6:** `resume` without a failed or export receipt is refused.
- **B:** `recovery_window_days` 7 and 30 accepted; 6 and 31 refused.

### S4.9 (USI): Step-2, rollback-zero and policy-update admission; multi-arch admission (FR-34)

- **Chains:** C-contract after S4.2.
- **Depends on:** S4.10 (URN sets), S4.11 (anchors), S2.6 (ARM64 flag).
- **Scope:**
  - admission mode `step2`: saved-plan steps only `create` or `same`;
    created URNs equal the S4.10 step-2 set (seed Invocations, rotations,
    secret policies including the managed-secret policy, targets, policies,
    TEST `ScheduledAction`s, `<svc>-start-1`), or, in the rebuild variant,
    that set minus the URNs imported from the abandon receipt's `retain`
    set; no `update`, `replace` or `delete` of any step-1 URN;
  - step-2 preconditions: the latest receipt is a step-1 success (S4.11);
    the S5.5 receipt; the XP-8 metadata in the installed `main` contract
    (S4.6 step 5b);
  - admission mode `rollback-zero`: only `create` of the next
    `<svc>-stop-<seq>` or `<svc>-start-<seq>` URNs, plus at most one
    `update` per target whose only changed input is
    `suspendedState.scheduledScalingSuspended`, plus `same`
    (architecture AD-10);
  - admission mode `policy-update`: exactly one `update` step, whose URN is
    in the closed set {managed-secret `SecretPolicy`, each `VpcEndpoint`}
    and whose only changed input is `policy`;
  - the `start_at` window: a new start or stop action's `at()` time between
    apply start + 10 min and + 24 h;
  - the step-2 health-observation evidence schema (AD-18 item 4);
  - the multi-arch admission check (moved from S2.6).

**Acceptance criteria:**

- The PRD FR-34 rows.
- **N1:** a step-2 plan updating the ECS service is refused.
- **N2:** step 2 without a step-1 success receipt, the S5.5 receipt or the
  XP-8 metadata is refused.
- **N3:** ARM64 without an arm64 manifest is refused.
- **N4:** a `rollback-zero` plan updating the target in any field other than
  `suspendedState`, or deleting anything, is refused.
- **N5:** a `policy-update` plan with a `delete`, a second step, or a
  changed input other than `policy` is refused.
- **N6:** an `at()` time 9 minutes after the apply start, or 25 hours after
  it, is refused.
- **B:** an all-`same` step-2 plan is admitted and changes nothing.

### S4.3 (USI + BI): Reviewed CI recovery command

- **Chains:** C-contract after S4.9; C-guard after S3.3.
- **Decision:** D-7, decided 2026-09-30. `abandon` is unconditional
  (TEST only).
- **Scope:**
  - `.github/workflows/recovery.yml` (`test-recovery`; `prod-recovery`
    without `abandon`), assuming `GitHubCiRecovery-user-service-infrastructure-{env}`
    (S5.7, S5.19);
  - `scripts/poc_workload_recovery.py` (`export`, `release-lock`,
    `clear-pending`, `import`, `abandon`), with every mutation as a saved
    plan through the classifier (AD-16); `export` writes the export receipt
    and `abandon` the abandon receipt (S4.11 library);
  - `scripts/poc_registry_plan.py`: accepts the registry baseline after a
    verified abandon receipt;
  - the rebuild variant of `import` (registry graph plus the abandon
    receipt's `retain` set; `RestoreSecret` for a `schedule-deletion`
    secret before import);
  - the use of the S4.10 delete-action map (`recovery/delete-actions.json`)
    in the abandon preflight: every `delete` step's type must have an entry,
    and the S5.7 simulator matrix must allow exactly those actions;
  - the in-run Kravalg approval check: the run's environment approval
    (`GET /repos/{owner}/{repo}/actions/runs/{run_id}/approvals`) must be
    `approved` for the environment by Kravalg's user ID, with a different
    requester; otherwise refuse;
  - the status check `abandon-manifest-approval` (needs an `APPROVED` review
    by Kravalg's user ID on the PR head for any change to
    `recovery/abandon-manifest.json`); S5.22 makes it required;
  - `import-list.json` covering every fixed-name resource and every
    `retain` family (the log buckets, retained secrets), including the new
    E1–E3 ones;
  - the evidence schema;
  - USI `.github/CODEOWNERS` entries (`@Kravalg`) for these files;
  - `docs/poc-workload-recovery.md` made executable, including the abandon
    and rebuild runbook and the BI ENI detach step (AD-16);
  - the AGENTS.md rule-14a amendment (AD-16).
- **Depends on:** S4.2, S4.9, S4.10, S4.11, S5.7 and S5.21.

**Acceptance criteria:**

- The PRD FR-22 rows.
- **N1:** an import plan containing a `create` or `update` step is refused.
- **N2:** `abandon` in `prod-recovery` is refused.
- **N3:** an approvals fixture approved by `dmytrocraft`, by the requester,
  or with no approval is refused; approved by Kravalg with another
  requester is accepted.
- **N4:** a manifest PR fixture with only a `dmytrocraft` approval fails
  `abandon-manifest-approval`.
- **N5:** a removal plan with a type missing from `recovery/delete-actions.json`
  is refused.
- **Live (TEST):** S4.6 step 13 (resume rehearsal) and steps 18–20 (abandon
  and rebuild, NFR-09).

### S4.12 (USI): Runner mode routing (FR-35 part 2)

- **Chains:** C-runner after S4.11; C-contract after S4.3.
- **Scope:** `execute` and `_gate` dispatch by the installed contract's
  `workload_operation.mode`: `first`, `step2`, `resume`, `rollback-zero`,
  `policy-update` (to the S4.2 and S4.9 admission functions), and
  `recovery-import` and `recovery-abandon` (to S4.3, only when invoked from
  `recovery.yml` in `test-recovery` or `prod-recovery`), each with the
  anchor of the AD-24 table.

**Acceptance criteria:**

- **P:** `step2` with a valid step-1 success receipt is admitted.
- **N1:** `step2` without it is refused.
- **N2:** an unknown mode, a mode that `workload_operation` does not name, or
  `recovery-abandon` outside `test-recovery` is refused.
- **N3:** `first` against a checkpoint that already contains workload URNs
  is refused (`resume` is the only path).
- **B:** `resume` after an interrupted step 2 binds to that apply's failed
  receipt.
- **Live (TEST):** S4.6 steps 7, 13 and 15.

### S4.13 (USI): Accepted-workload receipt; drift and releases open (FR-35 part 3)

- **Chains:** C-runner after S4.12; C-contract after S4.12.
- **Scope:**
  - `schemas/poc-workload-accepted-receipt-v1.schema.json`; the runner runs
    the AD-18 health observation after every admitted apply that leaves
    `desiredCount ≥ 1`, and the first passing observation after step 2
    writes and authenticates the accepted receipt;
  - `scripts/poc_workload_runner.py` line 154 and
    `scripts/service_execution_worker.py` line 99: `drift` admitted only
    with an authenticated accepted receipt in the stack's lineage and a
    latest success receipt; release and release rollback also need a
    clean-drift result bound to the latest receipt, and use
    `inspect_retained_secret_history` with the receipt observation;
  - the worker docstring (line 5) and
    `tests/unit/test_service_execution_worker.py` (line 166: drift refused
    without the receipt, routed with it); the `self-deploy.yml`
    `test_post_apply_drift` job passes the receipt reference;
  - the **reviewed amendment** (Kravalg-approved governance PR): the README
    sentence (`specs/poc/README.md` line 127), the runner spec (lines
    37-40) and `docs/poc-workload-log-health.md` line 57 become "Workload
    drift is admitted only with an authenticated accepted-workload receipt
    and is rejected without one."; `tests/unit/test_workload_apply_docs_consistency.py`
    line 175 carries the new sentence, and line 185 becomes two assertions
    (drift not routed without a receipt; routed with one).

**Acceptance criteria:**

- **P:** `drift` with a valid accepted receipt is routed to the drift role.
- **N1:** `drift` without it is refused with
  `workload-accepted-state-receipt-required` (runner) and
  `workload-drift-not-enabled` (worker).
- **N2:** a release with an accepted receipt but no clean-drift result is
  refused.
- **N3:** the old README sentence without the new one fails the doc test.
- **B:** an accepted receipt from before an abandon is refused after the
  abandon (lineage broken).
- **Live (TEST):** S4.6 steps 7b and 14 (and again in step 20).

### S4.14 (USI): PROD path (FR-35 part 4)

- **Chains:** C-runner after S4.13; C-contract after S4.13.
- **Scope:** `scripts/service_execution_worker.py` `JOBS`/`ACCOUNTS` (lines
  25-30) gain `prod_preview`, `prod_apply`, `prod_post_apply_drift` and
  account `933245420672`, and the source binding (lines 90-94) accepts
  `prod` only per `admission.prod` (`"preview"` → `plan` only; `true` →
  apply); `.github/workflows/self-deploy.yml` gains the matching PROD jobs in
  the `prod-preview` and `prod` environments; the runner accepts `prod` with
  the PROD certificate parameter (the PROD counterpart of XP-10, SSM name
  recorded with the gateway owner and pinned), the PROD topology (S4.10),
  the PROD registry anchor (XP-14) and `prod-recovery`; `abandon` is never
  admitted for PROD.

**Acceptance criteria:**

- **P:** a PROD fixture with `admission.prod: true` and every PROD input is
  admitted offline; a PROD `plan` fixture under `"preview"` is admitted.
- **N1:** PROD with `admission.prod: false` is refused; a PROD `up-plan`
  under `"preview"` is refused.
- **N2:** PROD `recovery-abandon` is refused; PROD without XP-14 is refused.
- **B:** the TEST path is unchanged (every TEST test passes).
- **Live (TEST):** S4.6 step 2 (PROD refused). PROD live use is S4.7.

### S4.15 (USI): TEST acceptance receipt validator and two-gate hard-stop test

- **Chains:** C-contract after S4.14.
- **Scope:** `schemas/poc-test-acceptance-receipt-v1.schema.json` (PRD
  §3.3), `scripts/poc_acceptance_receipt.py` with two validation levels
  (`campaign`: every S4.6 item; `complete`: plus the S4.8 restore and the
  S4.7 P-1 items), `tests/unit/test_poc_acceptance_receipt.py`, and the
  offline two-gate rewrite of `tests/unit/test_workload_phase_hard_stop.py`
  (gate 1, 2a, 2b; AD-21). The README text and the phase flip stay in the
  S4.6 step-1 PR.

**Acceptance criteria:**

- The PRD FR-31 rows and §3.3.
- **N1:** a placeholder link, an all-zero hash or an equal requester and
  approver is refused.
- **N2:** a `complete` validation without the restore or P-1 item is
  refused.
- **B:** a `campaign`-valid receipt is accepted at gate 2a only with the
  restore item.

### S4.16 (USI): TEST exercise workflow

- **Chains:** independent new files.
- **Depends on:** S5.23.
- **Scope:** `.github/workflows/test-exercise.yml` (main only, environment
  `test-exercise`, role `GitHubCiExercise-user-service-infrastructure-test`)
  and `scripts/poc_test_exercise.py` with sanitized subcommands: `rotate`
  (`RotateSecret` on a named workload secret), `denied-read` (attempts
  `GetSecretValue` and `PutSecretValue` and expects `AccessDenied`; never
  prints a value), `alarm` (`sqs:SendMessage` of a marker to one DLQ;
  `cloudwatch:SetAlarmState` on one workload alarm), `flow-log-review`
  (reads flow-log objects and reports REJECT counts by destination, never
  raw records), `cloudtrail` (`LookupEvents` metadata for V-21 and the
  §3.2a evidence), `log-counts` (Logs Insights counts for NFR-05) and
  `load` (drives requests through the AGI TEST route at the recorded rate).

**Acceptance criteria:**

- **P:** each subcommand's evidence JSON is schema-valid and redacted
  (FR-20).
- **N:** `denied-read` that unexpectedly succeeds exits non-zero without
  printing the value; a subcommand in PROD is refused.
- **B:** `load` stops at the recorded rate ceiling.

### S4.6 (USI + BI live): Gate 1 (TEST-only admission) and the live TEST campaign

- **Chains:** C-contract after S4.15.
- **Preconditions (explicit gate-1 list):**
  - USI merged: S1.1, S1.7, S1.2, S1.3, S1.4, S1.10, S1.9, S1.11, S1.6, S1.5,
    S1.8, S2.1, S2.2, S2.3, S2.4, S2.5, S2.6, S3.2, S3.1, S3.3, S3.4, S3.5-B,
    S3.5-A (PROD shape only; TEST keeps HTTP), S3.7, S4.1, S4.4, S4.5,
    S4.10, S4.11, S4.2, S4.9, S4.3, S4.12, S4.13, S4.14, S4.15, S4.16;
  - US merged and published: S5.8, S5.9, S5.10, S5.11, S5.12, S5.13, S5.14;
  - BI applied: S5.1, S5.2, S5.17, S5.4, S5.3, S5.21, S5.23, S5.7, S5.22,
    S5.18a;
  - decisions resolved (explicit, dated 2026-09-30, `decisions.md` and PRD
    §6): D-1, D-2 (TEST), D-4, D-5, D-6, D-7 — all resolved;
  - XP-6 (subscription endpoint) and XP-7 (profile) present;
  - XP-9 (completed registry proof and receipt), XP-10 (gateway ACM
    certificate and SSM publication), XP-11 (bootstrap #219 grants), XP-12
    (authenticated image publication), XP-13 (SES prerequisites) present
    (R4-M10);
  - the R-02 metadata observation receipt.
- **Operation PRs.** Every apply below is preceded by a reviewed contract PR
  that sets `workload_operation` (and, where needed, `workload_step`,
  `scaling` or `documentdb_secret_policy`), approved by Kravalg. The runner
  reads it from the installed `main` contract (AD-24).
- **Steps, in order.** Every step needs separate authorization. Each names
  its V-items and its STOP rule. A STOP ends the campaign until the named fix
  lands; the stack is recovered through S4.3.
  1. **Gate-1 PR:** `phase: workload`, `admission: {test: true, prod: false}`,
     and the README hard stop rewritten into two gates (AD-21, PRD §6.1;
     the test is S4.15). Needs `@Kravalg` approval (D-6 governance).
     Read-only environment check (m11): `test`, `prod`, `test-recovery`,
     `test-exercise` and `governance-evidence` each list reviewers =
     [Kravalg] only, `prevent_self_review` true, no admin bypass (S5.21).
     STOP: not approved, or any environment differs.
  2. **R-02 re-observation** (read-only), runtime-guard refusal for `prod`
     observed (FR-23), and the S4.14 PROD path refused (FR-35). STOP: any
     workload URN present → AD-09; PROD not refused → fix before step 3.
  3. **Read-only live checks (m6):** live `iam:SimulatePrincipalPolicy`,
     called by `GitHubCiPreview-user-service-infrastructure-test` (S5.17
     grant, exact role ARNs only), for the apply, preview, drift, task,
     execution, app-rotation, redeploy, bootstrap-job, recovery,
     restore-operator, restore-reader and exercise roles, with the key and
     secret resource policies as `ResourcePolicy` inputs (FR-27, FR-33,
     NFR-06, V-6, V-15, V-21 and V-22 simulate parts);
     `DescribeVpcEndpointServices` for V-12. STOP: any required action
     denied or any forbidden action allowed. Fallback for V-12: FR-18 NAT
     variant, recorded, before step 4.
  4. **Step-1 saved-plan apply** (mode `first`) with timing (FR-24, FR-34).
     Checks: V-5 (users and group accepted), V-17 (engine), V-21 (the
     managed secret is created under the apply role; `cloudtrail`
     exercise), `MasterUserSecret` active (FR-01), services at 0; the
     **step-1 success receipt** is issued and authenticated (FR-35, S4.11).
     STOP: V-5 fails → user decision; V-21 `AccessDenied` → BI grant fix,
     then `resume` from the failed receipt; any other failure → S4.3
     `resume` (or `export` first if no receipt was written).
     - **4a. TEST state metadata scan** (NFR-01, FR-09): the trusted
       observer reads the checkpoint and records type counts only. STOP: any
       `random:`, `tls:` or `SecretVersion` type, or a secret-like output.
  5. **XP-8 BI metadata PR** (subnet IDs, bootstrap-job SG ID,
     DocumentDB-managed secret ARN); V-19 via read-only `DescribeSecret`
     metadata; the exact-ARN grants (bootstrap-job read; apply-role
     `PutResourcePolicy`/`GetResourcePolicy`) and the bootstrap-job VPC
     attachment applied (S5.5); S5.18b (restore-reader VPC attachment) may
     apply now. Fallback for V-19: exact ARN only. STOP: the BI apply fails
     or the attachment shows no ENI in the USI subnets.
     - **5b. USI contract PR:** the XP-8 values in the installed `main`
       central metadata, `workload_step: 2`, `scaling.start_at`,
       `workload_operation: {mode: step2}`; Kravalg-approved. STOP: not
       approved.
  6. **S5.5 bootstrap job** run; it reads the managed secret through the
     `secretsmanager` endpoint's `rds!cluster-*` statement (FR-17). STOP:
     user not created → escalate.
  7. **Step-2 saved-plan apply** (mode `step2`, anchored on the step-1
     success receipt; S4.9 create-only admission). The start actions fire at
     `start_at` (V-23 a and b). Then the step-2 health observation (AD-18
     item 4): V-1 (MONGODB-AWS), V-2 (Redis IAM client), V-14 and V-20
     (image pull through endpoints), V-25 (logs delivered to the
     CMK-encrypted groups), FR-08 and FR-10 metadata, FR-06
     login/JWT/2FA, timing (FR-24). STOP: health fails → `rollback-zero`
     saved plan; V-1 failure → user decision; V-2 failure → US fix; V-14,
     V-20 → reviewed pin fix via `policy-update`; V-25 → AD-15a fallback
     row.
     - **7a. TEST state metadata scan** again after step 2 (NFR-01). STOP
       as in 4a.
     - **7b. Accepted-workload receipt** written and authenticated by the
       first passing health observation (FR-35, S4.13); V-23 (c) recorded
       (fired actions listed or not). STOP: no passing observation → stays
       at 7; AWS removed a fired action → `scaling.consumed` contract PR and
       the AD-23 entry before step 14.
  8. **V-3 check:** forced rotation (`rotate` exercise) of the
     DocumentDB-managed secret with its `deny-other-readers` policy in place;
     the app stays healthy. Fallback (non-destructive): reviewed contract PR
     to `allow-rotation`, then `tls-only` if needed, each as a
     `policy-update` plan; the policy is never deleted; residual recorded.
     STOP: the app becomes unhealthy → `rollback-zero`, then the fallback.
  9. **App-secret rotation exercise:** forced rotation (`rotate`) of both
     purposes; V-4 (`RotationSucceeded`), redeploy observed, NFR-05
     single-key window measured (`log-counts`). STOP: no redeploy →
     escalate; a failure outside D-5 → escalate.
  10. **Redis IAM soak, 13 h** (V-9, V-2, NFR-05 IAM paths), starting at the
      TEST morning restore and ending before the night action (the contract
      night window is at most 11 h, which leaves at least 13 h of day).
      STOP: any auth failure → US fix.
  11. **Alarms:** NFR-08 delivery (`alarm` exercise; ≤ 300 s); denied
      `GetSecretValue` and `PutSecretValue` by the exercise role
      (`denied-read`, FR-07) with the S2.5 alarms; one event per PRD §3.2a
      row (the allow-listed caller does not alarm, a different caller does);
      SES mail sent (FR-03, V-12). STOP: a delivery over 300 s, a missing
      alarm, or an alarm from an allow-listed caller → S2.4/S2.5 fix.
  12. **Scaling and network:** FR-12 backlog scale-out (`alarm` marker
      messages to the work queue), FR-14c scheduled scale-down and restore
      observed, FR-15 object delivered with the runtime CMK (V-16), FR-16
      describe, FR-18 `flow-log-review` against
      `docs/poc-egress-inventory.md`, V-11 metric observed. STOP (m12): a
      `REJECT` to a destination missing from the inventory, or a check
      failing because of egress → reviewed inventory and SG change; V-16
      delivery failure → key or bucket policy fix. Fallback for V-11: drop
      the informational alarm.
  13. **Resume rehearsal** (S4.3, FR-21 resume, NFR-09) with an induced
      failure (FR-20): the run of an admitted `rollback-zero` start plan
      (`<svc>-start-2`, no capacity change) is cancelled after the apply
      starts; then `release-lock`, `clear-pending` and `resume` from the
      failed (or export) receipt. STOP: resume refused or failed → escalate;
      no further step until the stack is clean.
  14. **Clean drift** under the drift role (FR-32, V-13), admitted by the
      accepted receipt and the latest success receipt (FR-35), after step 12
      moved `desiredCount` and the schedules moved min/max. STOP: unlisted
      drift → investigate, no list widening.
  15. **Rollback (first deployment, AD-19):** `rollback-zero` stop plan →
      services at 0, scheduled scaling suspended → start plan → healthy
      again; a release-rollback request is refused because no prior accepted
      release exists (FR-30 N). STOP: the restart is unhealthy → escalate
      with the services at 0.
  16. **FR-25 worker healthcheck, FR-26 non-root** observed. STOP: a root
      `User` or an unhealthy worker → US or S3.7 fix.
  17. **Front door (FR-28, V-10):** AGI TEST route through VPC link V2 → ALB
      and WAF sampled requests; then the FR-11 load test through the route
      (`load` exercise, below the recorded WAF per-IP limit) with web
      scale-out observed. Fallback: reviewed NLB variant. STOP: no route or
      no scale-out → AGI or S2.1 fix. Required before any public exposure
      and before gate 2 if PROD is public.
  18. **Abandon preparation:** the `abandon-manifest.json` PR listing every
      workload resource (`delete`, or `retain` for the log-bucket families
      and each retained secret), approved by Kravalg (required check
      `abandon-manifest-approval`); a reviewed BI PR detaches the
      bootstrap-job and restore-reader Lambdas from the USI subnets and SG;
      read-only `DescribeNetworkInterfaces` shows no foreign ENI. STOP: an
      ENI remains, or the approval is not Kravalg's.
  19. **Abandon rehearsal** (D-7; FR-21, NFR-09) in `test-recovery`,
      approved by Kravalg (in-run approvals check): unprotect plan (V-24),
      removal plan compared 1:1 with the manifest (all types), `up --plan`
      (V-26), the abandon receipt, then registry capture accepts the
      baseline. Alarms: `DeleteSecret` and `DeleteResourcePolicy` by the
      recovery role, and the managed `DeleteSecret` by `rds.amazonaws.com`,
      are allow-listed (PRD §3.2a); anything else alarms. V-15 and V-18
      observed. STOP: any cloud delete of a retained resource (V-24), an
      `AccessDenied` (V-26), or any mismatch → stop; `export`, then recover
      by S4.3 `import` or a new `recovery-abandon`.
  20. **Rebuild:** recovery `import` of the retained resources (rebuild
      variant; `RestoreSecret` where needed) → `resume` of step 1 → step-1
      receipt → XP-8 refresh (the new managed-secret ARN; BI re-attaches
      both Lambdas and re-grants the exact ARNs) and the 5b contract PR →
      S5.5 re-run → step 2 (`step2`, rebuild variant) → health observation →
      accepted receipt → clean drift. STOP rules as in steps 4–7 and 14.
  21. **Receipt:** assemble the PRD §3.3 receipt from steps 1–20 (including
      every PRD §3.2a allow-listed event with its run ID) and validate it at
      the `campaign` level (S4.15). STOP: invalid → fix the evidence, never
      the validator.

**Acceptance criteria:**

- **P:** a `campaign`-valid TEST acceptance receipt with every step's
  evidence.
- **N1:** gate 1 with any listed story unmerged, any XP-9 … XP-13 missing,
  or any listed decision only defaulted is refused.
- **N2:** a receipt with a placeholder link is refused.
- **B:** a PROD run is refused while `admission.prod` is false.

**Risk:** ST, IAM, L.

### S4.8 (USI + BI live): Restore rehearsal and rollback evidence

- **Scope:**
  - the restore runbook;
  - **R-1:** a TEST snapshot (the step-19 final snapshot
    `<stack>-docdb-final`, or a fresh manual snapshot of the rebuilt
    cluster) is restored to `<stack>-docdb-restore-rehearsal` under the
    S5.18a operator role, with `ModifyDBCluster` to a managed password (V-22).
    The S5.18b reader (VPC-attached after XP-8) records the document-count
    sample. Then the temporary cluster is deleted;
  - the restore item is appended to the acceptance receipt.
- **Depends on:** S4.6, S5.18a and S5.18b.

**Acceptance criteria:** the PRD FR-30 rows. **STOP:** V-22 denial → BI
grant fix; the temporary cluster is deleted before a re-run.

### S4.7 (USI): Gate 2 (PROD admission) and the PROD plan

- **Scope:** gate 2a (`admission.prod: "preview"`), then gate 2b
  (`admission.prod: true`), and the PROD promotion plan: recovery
  environment `prod-recovery`, the S4.14 PROD path, PROD live acceptance.
- **Preconditions:**
  - S4.6, S4.8, S4.14, S5.6 (if triggered), S5.19, S5.20 merged and
    published (with S3.5-A already merged; D-2 PROD), D-3 resolved, S5.16
    with S4.6 step 17 evidence if PROD is publicly exposed, XP-14 (PROD
    registry), and a PROD live simulator run;
  - **P-1 (m1), under gate 2a:** the PROD `plan` (`prod_preview` job, S4.14)
    shows the HTTPS target group and health check on 8443 (FR-19); its
    evidence is appended to the receipt. STOP: an HTTP target group or any
    admission refusal → fix before gate 2b.

**Acceptance criteria:**

- **P:** gate 2b is accepted with every gate-1 check passing and a
  `complete`-valid receipt, including P-1.
- **N1:** any gate-1 check failing is refused.
- **N2:** any missing receipt item or placeholder link is refused.
- **N3:** a PROD stack with an HTTP target group is refused.
- **B:** PROD recovery grants must exist before the PROD apply.

## Epic 5: Cross-repo prerequisites

| Story | Repo | Deliverable | Key acceptance (P / N / B) |
| --- | --- | --- | --- |
| S5.8 | US | Merge #501 | Merged / the image command differs from the USI contract command → refused (FR-25) / healthcheck grace period covers supervisor start |
| S5.1 | BI | **Every central role, created first (M-3):** ECS execution and task roles, app-rotation, redeploy and bootstrap-job roles, the restore-operator and restore-reader roles (trust policy only; their grants land in S5.18a), and the TEST exercise role (trust only; grants in S5.23). Their ARNs are published in central metadata, which the S3.3 endpoint policy reads. Secret patterns `name-??????`, deterministic ARNs; task role SQS, SES, `elasticache:Connect` on the exact replication-group and user ARNs (D-1). **No KMS statements** (they land in S5.4 after the keys exist) and no bootstrap-job grant on the DocumentDB-managed secret (it lands in S5.5 after XP-8). XP-1: recover or re-author `d41c019`. | Simulator allows / out-of-scope and `GetSecretValue` on the task role denied / `iam:PassedToService` present |
| S5.2 | BI | Apply-role workload capability (N-11): ecs, ec2 (including flow logs and endpoints), elasticache (including users and groups), docdb/rds, logs (`CreateLogDelivery`, `DeleteLogDelivery`), cloudwatch, application-autoscaling (`RegisterScalableTarget` including `SuspendedState`, `PutScalingPolicy`, `PutScheduledAction` on the two service resource IDs; no `DeleteScheduledAction`), elbv2, s3, secretsmanager (`CreateSecret`, `PutResourcePolicy`, `GetResourcePolicy`, `RotateSecret` with `secretsmanager:RotationLambdaARN` limited to the BI functions, tagging; **no delete action** — `DeleteResourcePolicy`, `CancelRotateSecret`, `DeleteSecret` stay with the TEST recovery role, because no admitted apply mode deletes), `lambda:InvokeFunction` on BI functions, events, sns. **Managed password (R4-M9, V-21, A-27):** `rds:CreateDBCluster` with `rds:ManageMasterUserPassword` = true; `secretsmanager:CreateSecret` and `TagResource` on `secret:rds!cluster-*`; `kms:DescribeKey` on `alias/aws/secretsmanager` (`kms:ResourceAliases`); `secretsmanager:DescribeSecret` on `secret:rds!cluster-*` (metadata only). The managed-secret `PutResourcePolicy`/`GetResourcePolicy` is granted on the exact XP-8 ARN in S5.5. **Runtime-CMK describe:** `kms:DescribeKey` with the AD-15a `kms:ViaService` set (added in S5.4 once the key ARN exists). **SLRs:** `iam:CreateServiceLinkedRole` only with `iam:AWSServiceName` ∈ {ecs, ecs.application-autoscaling, elasticache, rds, elasticloadbalancing}, or BI pre-creates them. **Attachment quota:** the capability fits within the role's managed-policy attachment quota and the 6144-character managed-policy size; the story records the count and sizes. `PassRole` limited to the ECS roles. `GetSecretValue`, `PutSecretValue`, `UpdateSecretVersionStage` and `GetFunction` denies stay. V-15, V-21 (docs). | Matrix allows / denies stay; `RotateSecret` with another function ARN denied; `CreateDBCluster` with `ManageMasterUserPassword` false denied; `CreateSecret` on a declared-name pattern other than the listed names denied / attachment count and sizes within quota |
| S5.17 | BI | **Preview and drift read capability (FR-33, B-2):** read-only grants for `GitHubCiPreview-…-{env}` and `GitHubCiDrift-…-{env}` on every workload resource type (ec2, ecs, docdb/rds describe, elasticache, logs, cloudwatch, application-autoscaling including scheduled actions, elbv2, wafv2, apigateway, events, sns, s3 configuration, secretsmanager metadata). **No KMS statement here** (m7): the KMS read lands in S5.4 on the exact key ARNs. **Simulation grant (m6):** the preview role gets `iam:SimulatePrincipalPolicy` and `iam:GetContextKeysForPrincipalPolicy` on the exact ARNs of the S4.6 step-3 role list only. Simulator-matrix regression for both roles. | Every workload read allowed / `GetSecretValue`, `GetFunction`, `kms:Decrypt`, every write, and `SimulatePrincipalPolicy` on a role outside the list denied / the existing registry-phase matrix is unchanged |
| S5.4 | BI | CMKs per D-4 (decided 2026-09-30): the runtime CMK (secrets, every workload log group, flow-log bucket, SNS topic), the JWT signing CMK (RSA_4096) and the 2FA CMK. Key policies follow the **per-key table architecture AD-15a** (principal, action, condition): no `root` `kms:*` statement; `logs.<region>.amazonaws.com` with `kms:EncryptionContext:aws:logs:arn`; `delivery.logs.amazonaws.com` with `aws:SourceAccount`/`aws:SourceArn`; cloudwatch and events for SNS; the ECS execution role `kms:Decrypt` with `kms:ViaService=secretsmanager.<region>.amazonaws.com`; the app-rotation role; the task role on the JWT and 2FA keys; the preview and drift roles' read (m7); the apply role's `DescribeKey` via logs, secretsmanager, sns and s3. Every named role already exists (S5.1, or the pre-existing preview, drift and apply roles). Then, in the same story and after the keys exist, the matching identity statements. CloudTrail read management events. | Grants only the AD-15a rows / no broad `kms:*`; a key policy naming a role absent from the role inventory fails the offline check; an execution-role `Decrypt` without `kms:ViaService` fails / JWT key-change procedure |
| S5.3 | BI | Functions using the S5.1 roles: app rotation + idempotent seed (no VPC), redeploy (no VPC, deterministic service ARNs), bootstrap-job function package (VPC attachment deferred to S5.5), their log groups created explicitly with `kms_key_id` = the runtime CMK (D-4), Lambda permissions (`aws:SourceAccount`), `RotationSucceeded` rule, allow-listed secret patterns (NFR-06). V-4 (docs). | Step unit tests / `testSecret` failure means no stage move; a function log group without the runtime CMK fails / seed on a secret with AWSCURRENT returns `noop`; seed output has no material |
| S5.7 | BI | **TEST recovery (D-7, decided 2026-09-30; unconditional):** the role `GitHubCiRecovery-user-service-infrastructure-test`, trusted only for OIDC `sub` `repo:VilnaCRM-Org/user-service-infrastructure:environment:test-recovery` on `main` (the `test-recovery` environment itself is configured by S5.21: Kravalg sole reviewer). Grants per architecture AD-16: state read and write, `s3:DeleteObject` on the state lock prefix (`.pulumi/locks/*`) only, state secrets-provider key use; `rds:ModifyDBCluster` on `cluster:user-service-infrastructure-test-docdb`; the per-type delete-action map `recovery/delete-actions.json` from S4.10 (pinned provider delete paths, drain and detach calls included; V-26), scoped to the TEST name patterns or `aws:ResourceTag/Project=user-service-infrastructure` + `Environment=test`; no S3 bucket delete, no object delete outside the lock prefix, no KMS key management; `secretsmanager:DeleteSecret` (`secretsmanager:RecoveryWindowInDays` ≥ 7, `secretsmanager:ForceDeleteWithoutRecovery` = false — **V-15**), `RestoreSecret`, `DescribeSecret`, `CancelRotateSecret`, `DeleteResourcePolicy` on the workload patterns and `rds!cluster-*`; the import read set (S5.17). TEST only. | Exactly the recovery set; each graph type's delete allowed on the TEST pattern / PR-head assumption denied; force delete denied; `s3:DeleteBucket` and a log-bucket `s3:DeleteObject` denied; the PROD account denied / recovery window 7 allowed, 6 denied |
| S5.18a | BI | **Restore-rehearsal grants (FR-30, M-9), before step 1:** on the S5.1 operator role, the architecture §2.1 grants (`RestoreDBClusterFromSnapshot` with the snapshot, subnet-group and parameter-group resources; `CreateDBInstance`; `ModifyDBCluster` with `rds:ManageMasterUserPassword`; `secretsmanager:CreateSecret`/`TagResource` on `rds!cluster-*`; `kms:DescribeKey` on `alias/aws/secretsmanager`; `kms:CreateGrant`/`Decrypt`/`DescribeKey` on the DocumentDB storage key via `rds.<region>.amazonaws.com`; describe and delete on `<stack>-docdb-restore-rehearsal` only; V-22 docs); on the S5.1 reader role, `GetSecretValue` on the temporary cluster's managed secret by tag condition (V-19) or a reviewed ephemeral exact-ARN grant; the reader package **without** VPC attachment. | Restore and read allowed for the rehearsal name / restore to any other name, delete of the real cluster, and the reader on the real cluster's secret denied / `ManageMasterUserPassword` false denied |
| S5.18b | BI (live) | **Restore-reader VPC attachment (R4-M7), after XP-8 (S4.6 step 5):** attach the S5.18a reader to the USI app subnets and bootstrap-job SG from the XP-8 metadata; detach before an abandon (S4.6 step 18), re-attach in the rebuild (step 20). | Reader reaches the temporary cluster port and the `secretsmanager` endpoint / attach refused without XP-8 metadata / detach leaves no ENI |
| S5.5 | BI (live) | XP-8 metadata PR; exact-ARN `GetSecretValue` grant for the bootstrap-job role (plus tag condition if V-19); exact-ARN `secretsmanager:PutResourcePolicy` and `GetResourcePolicy` for the USI apply role (step-2 managed-secret policy and `policy-update`); bootstrap-job VPC attachment; `$external` bootstrap job run, idempotent, with evidence. The `secretsmanager` endpoint needs no XP-8 change (`rds!cluster-*` statement, S3.3). Runs as S4.6 steps 5–6 and again in step 20. | User exists with `readWrite` on the app database only / unapproved run refused / re-run makes no change |
| S5.21 | BI | **Kravalg-only environment approvals (m11, R4-M4):** the USI environments `test`, `prod`, `test-recovery`, `test-exercise` and `governance-evidence` are configured through BI `scripts/_github_repository_controls.py::protected_reviewer_environment_payload` (debd88b lines 308-319): reviewers = [Kravalg's user ID] only, `prevent_self_review: true`, `can_admins_bypass: false`, main-only branch policy. `prod-recovery` is created later by S5.19 with the same payload. Offline tests reuse `environment_prevents_self_review` and `environment_is_main_only` (`scripts/_github_environment_controls.py`). | Each payload equals the expected one / a second reviewer, `prevent_self_review` false or admin bypass fails / a non-main branch policy fails |
| S5.22 | BI | **Required manifest approval check (R4-M4), after S4.3:** the USI ruleset (`ruleset_payload` in `scripts/_github_repository_controls.py`) requires the status check `abandon-manifest-approval` (created by S4.3) for PRs that change `recovery/abandon-manifest.json`. | Required check present / a ruleset without it fails the BI test / other paths unaffected |
| S5.23 | BI | **TEST exercise role (R4 audit, live-action identities):** grants on the S5.1 role `GitHubCiExercise-user-service-infrastructure-test`, trusted only for OIDC `sub` `repo:VilnaCRM-Org/user-service-infrastructure:environment:test-exercise` on `main`: `secretsmanager:RotateSecret` on the declared patterns and `rds!cluster-*` (TEST); `sqs:SendMessage` on the work queues and DLQs; `cloudwatch:SetAlarmState` on the workload alarms; `s3:GetObject`/`ListBucket` on the flow-log bucket plus the AD-15a runtime-key row (`kms:Decrypt` via S3); `cloudtrail:LookupEvents`; `logs:StartQuery`/`GetQueryResults` on the workload log groups. No `GetSecretValue`, `PutSecretValue` or write outside this list, so `denied-read` is refused. TEST account only. | Matrix allows exactly the list / `GetSecretValue`, `PutSecretValue` and PROD denied / PR-head assumption denied |
| S5.6 | BI (conditional) | `MaxSessionDuration` plus `role-duration-seconds` | Covers the measured time plus the 300 s margin / below-margin value refused / exactly at the margin accepted |
| S5.19 | BI | **PROD recovery (M-9):** the role `GitHubCiRecovery-user-service-infrastructure-prod` and the `prod-recovery` environment (Kravalg sole reviewer, `protected_reviewer_environment_payload`), with grants mirroring S5.7 **without** any delete, abandon or `DeleteSecret` grant. | Exactly the recovery set / delete actions denied / PR-head assumption denied |
| S5.9 | US | Non-root images (UID ≥1000, :8080, supervisor socket under `/srv/app/var/run`) | Non-root `User` / bind to :80 fails / healthchecks pass |
| S5.20 | US | **In-container TLS for PROD (D-2):** Caddy internal certificate on :8443, HTTPS health endpoint | HTTPS responds on 8443 / plain HTTP on 8443 refused / certificate renewal before expiry |
| S5.10 | US | MONGODB-AWS check (V-1 source) | TEST connect / wrong role fails / survives credential refresh |
| S5.11 | US | KMS JWT signing (league and lexik), JWKS from `GetPublicKey` | Verifies / tampered rejected / dual-key window |
| S5.12 | US | KMS 2FA encryption with context `user_id` | Enrol and verify / wrong context fails / size bound |
| S5.13 | US | **Redis IAM token provider (D-1):** SigV4 token per new connection from the task-role credentials (lower-case replication-group id, user id), `AUTH [user, token]` over TLS, re-`AUTH` or reconnect before 11 h, no re-auth inside `MULTI`/Lua, a Symfony `RedisAdapter` connection factory for `REDIS_URL` and `REDIS_LOCKOUT_URL`, `auth_failure{backend=redis}` log metric. V-2 and V-9 (source and docs). | Integration test against a local ACL Valkey 7.2 authenticates / an expired or wrong-user token fails with a counted `auth_failure` / a connection aged 11 h re-authenticates; token regenerated when credentials rotate |
| S5.14 | US | Multi-arch publishing (amd64 and arm64, immutable `sha-` tags) | Both architectures / missing architecture refused by USI admission (S4.9) / manifest digest pinned |
| S5.15 | — | **Dropped** (D-5, decided 2026-09-30: forced re-login is accepted, no previous-key tolerance is built). | — |
| S5.16 | AGI | REST API + WAF + VPC link V2 **directly to the internal ALB** (`integration_target`), custom domain, pipeline (D-3, decided). V-10 (docs and provider source). | Route reaches the service / direct ALB access from outside the VPC fails; an NLB target without a recorded fallback fails / 60-day inactivity documented |

---

## Independent vs shared changes

- **Shared or serialized:** the chains C-BI, C-contract, C-topology,
  C-runner, C-runtime, C-data, C-network, C-compute, C-stack and C-guard in
  `architecture.md` §4. There is one writer per chain. S4.10 is the only
  writer of `scripts/poc_workload_topology.py`,
  `scripts/poc_workload_secret_result.py` and the native topology
  integration test.
- **Independent:** these can run in parallel with at most three agents, after
  their chain heads:
  - S2.2;
  - S2.3 → S2.4 → S2.5;
  - S4.1;
  - S4.16 (after S5.23);
  - S3.5-B;
  - S5.8–S5.14 and S5.20 (US);
  - S5.16 (AGI).

  S4.4 and S4.5 edit the runner, so they are not independent: they head
  C-runner.

## Ordered story list

| # | Story | Repo | Kind |
| --- | --- | --- | --- |
| 0 | D-1 … D-7 recorded as explicit user decisions dated 2026-09-30 (`decisions.md`; D-4, D-5 clarified the same day) | user | done; `@Kravalg` approval of the README PR is still S4.6 step 1 |
| 1 | S5.8 #501 | US | independent |
| 2 | S1.1 generation out of state + contract + central fields (+ transition rule) | USI | C-contract, C-runtime |
| 3 | S1.7 AWSCURRENT refs | USI | C-contract, C-runtime |
| 4 | S1.2 DocumentDB-managed password | USI | C-data |
| 5 | S1.3 DocumentDB IAM + bootstrap-job SG + step-1 shape + DSN tests | USI | C-data, C-network, C-compute |
| 6 | S1.4 Redis IAM auth (D-1) | USI | C-data, C-network, C-compute |
| 7 | S1.10 legacy path fail-closed | USI | C-data, C-compute, C-stack |
| 8 | S5.1 every central role, incl. restore and exercise roles (no KMS statements) | BI | C-BI |
| 9 | S5.2 apply-role capability (N-11, managed-password grants, no deletes) | BI | C-BI |
| 10 | S5.17 preview and drift read (no KMS) + simulation grant | BI | C-BI |
| 11 | S5.4 CMKs per AD-15a, then identity statements (incl. preview/drift KMS read); CloudTrail read events | BI | C-BI |
| 12 | S1.9 CMK binding (secrets, DocumentDB log groups) | USI | C-contract, C-data |
| 13 | S1.11 drift allow-list contract | USI | C-contract |
| 14 | S5.3 rotation, seed, redeploy and bootstrap-job functions; KMS log groups | BI | C-BI |
| 15 | S1.6 rotation wiring + idempotent seed + critical patterns (Invocation, docdb, bucketV2) | USI | C-runtime, C-guard |
| 16 | S1.5 secret policies (three managed-secret states) | USI | C-runtime |
| 17 | S2.1 → S2.2 autoscaling, start/stop actions | USI | C-compute, then independent |
| 18 | S2.3 → S2.4 → S2.5 topic, alarms, security rules and allow-lists | USI | independent |
| 19 | S5.10, S5.13, S5.11, S5.12 | US | independent (may start any time) |
| 20 | S1.8 KMS keys; drop PEM and passphrase purposes; ECS and Container Insights log-group CMK | USI | C-contract, C-runtime, C-compute |
| 21 | S3.2 → S3.1 → S3.3 → S3.4 network (egress inventory first in S3.4) | USI | C-network, C-guard |
| 22 | S3.5-B TEST TLS risk acceptance | USI | independent |
| 23 | S5.9 non-root → S3.7 | US → USI | C-compute |
| 24 | S5.14 multi-arch → S2.6 cost/Graviton + TEST schedules | US → USI | C-compute |
| 25 | S3.5-A PROD HTTPS target group (PROD shape) | USI | C-compute tail |
| 26 | S5.16 front door | AGI | independent |
| 27 | S4.1 diagnostics; S4.4 → S4.5 guard and timing | USI | independent; C-runner head |
| 28 | S4.10 hardened topology (both stacks), native gates, secret history; pins removed | USI | C-contract, C-topology |
| 29 | S4.11 receipts after every apply; anchor rebinding | USI | C-runner, C-contract |
| 30 | S4.2 resume + abandon admission + fail-closed prior check | USI | C-contract |
| 31 | S4.9 step-2, rollback-zero, policy-update + multi-arch admission | USI | C-contract |
| 32 | S5.21 Kravalg-only environments (`test`, `prod`, `test-recovery`, `test-exercise`, `governance-evidence`) | BI | C-BI |
| 33 | S5.23 TEST exercise role grants | BI | C-BI |
| 34 | S5.7 test-recovery role and grants (delete map from the S4.10 graph) | BI | C-BI |
| 35 | S4.3 recovery command (import, abandon, receipts, approvals check, delete-action map) | USI | C-contract, C-guard |
| 36 | S5.22 ruleset: `abandon-manifest-approval` required | BI | C-BI |
| 37 | S4.12 runner mode routing | USI | C-runner, C-contract |
| 38 | S4.13 accepted-workload receipt; drift and releases (reviewed README/spec/log-health/test amendment) | USI | C-runner, C-contract |
| 39 | S4.14 PROD path (worker, workflow, gate 2a/2b) | USI | C-runner, C-contract |
| 40 | S4.15 acceptance-receipt validator + two-gate hard-stop test | USI | C-contract |
| 41 | S4.16 TEST exercise workflow | USI | independent |
| 42 | S5.18a restore-rehearsal grants (no VPC) | BI | C-BI |
| 43 | S4.6 gate 1 + live TEST campaign (steps 1–21, including S5.5 and S5.18b) | USI (+BI live) | final TEST, live |
| 44 | S5.6 if the timing is over the bound | BI | conditional |
| 45 | S4.8 restore rehearsal | USI (+BI live) | live TEST |
| 46 | S5.20 in-container TLS merged and published | US | before gate 2 |
| 47 | S5.19 prod-recovery role and environment | BI | C-BI |
| 48 | XP-14 PROD registry proof (registry-phase work outside this plan) | USI registry | prerequisite |
| 49 | S4.7 gate 2a (P-1 PROD preview), then gate 2b + PROD plan | USI | PROD gate |

**No forward dependencies.** Every story depends only on lower-numbered rows.
BI inputs to USI are deterministic names, ARNs or patterns (the
`secretsmanager` endpoint policy included: `rds!cluster-*` plus the
deterministic S5.1 role ARNs). The only apply-derived values (subnet IDs,
bootstrap-job SG ID, DocumentDB-managed secret ARN) flow through XP-8 inside
row 43 (S4.6 steps 5 and 5b, again in step 20), and they feed only S5.5,
S5.18b and the USI contract. S5.15 is dropped (D-5).
