---
artifact: epics-stories
workflow: _bmad/bmm/workflows/3-solutioning/bmad-create-epics-and-stories (Create mode, non-interactive)
task: workload-wa-hardening
source_baseline: 66776772979956de9c5abdbee7c45641a1b533fa
date: 2026-09-30
revision: 7 (readiness round-7 findings R7-M1, R7-M2, R7-m1…m9 and R7-n1…n3, plus audit F2, F6 and F8, addressed on top of revision 6; decisions D-1…D-14 of 2026-09-30 applied)
inputDocuments: [prd.md, architecture.md, decisions.md]
---

# Epics and stories: Well-Architected hardening of the user-service workload

## Requirements inventory

- **FRs:** FR-01…FR-35.
- **NFRs:** NFR-01…NFR-11.
- **Decisions:** D-1…D-7 and D-14, all resolved by explicit user decisions
  dated 2026-09-30 (`decisions.md`; D-4 and D-5 as clarified the same day;
  D-6 approved, with `@Kravalg` approval of the README PR still required;
  D-14 sets the recovery targets RPO ≤ 1 hour and RTO ≤ 24 hours), and the
  derived details D-8…D-13, confirmed the same day. The 20% TEST cost
  threshold and the PROD justification rule (NFR-11) are planning
  defaults, not decisions.
- **External prerequisites:** XP-1…XP-16 (XP-15 and XP-16, the PROD counterparts of XP-10 and XP-11, are numbered in revision 8, R8-m6).
- **Verification items:** V-1…V-27 (method and place in `architecture.md` §5).

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
| FR-21 | S4.2, S4.3, S5.7, S5.21 (USI controls) |
| FR-22 | S4.3, S5.7, S5.19, S5.21 (USI controls) |
| FR-23 | S4.4 |
| FR-24 | S4.5, S5.6, S4.6 |
| FR-25 | S5.8, S4.6 |
| FR-26 | S5.9, S3.7, S4.10 (native gate) |
| FR-27 | S5.1, S5.2, S5.3, S5.4, S5.7, S5.17, S5.18a, S5.18b, S5.19, S5.23, S4.16 |
| FR-28 | S5.16, S4.6 step 17 |
| FR-29 | S1.10 |
| FR-30 | S4.8 (point-in-time restore; RPO/RTO per D-14, AD-19), S5.18a, S5.18b, S4.9 (`rollback-zero`) |
| FR-31 | S4.15, S4.6, S4.7, S4.14 (stack → contract mapping), S4.17 (gate 2b) |
| FR-32 | S1.11 (list and program check), S4.10 (checkpoint-field allowance), S4.13 (drift reducer on the executed path), S4.14 (`prod_workload_drift` and the PROD baseline exclusion, R8-n3), S4.17 (scheduled workload drift), S4.6 step 14 |
| FR-33 | S5.17, S5.4 (KMS read), S5.24 (Drift-role reads for S4.17, R7-m9), S4.6 step 3 |
| FR-34 | S4.9, S4.10, S1.3, S4.6 steps 4–7 |
| FR-35 | S4.11, S4.12, S4.13, S4.14, S4.3 (export, clear-pending, import and abandon receipts), S4.6 steps 4, 7, 7b, 13, 14, 20 |

| NFR | Stories |
| --- | --- |
| NFR-01 | S1.1, S1.6, S1.10, S4.1, S4.10, S4.6 steps 4a and 7a |
| NFR-02 | S1.1, S1.10, plus the guardrail test in every USI story |
| NFR-03 | all |
| NFR-04 | S4.6, S4.7, S5.21, S5.22 |
| NFR-05 | S1.4, S5.13, S1.6, S4.6 steps 9–10 |
| NFR-06 | S5.1–S5.7, S5.17, S5.18a, S5.18b, S5.19, S5.21, S5.24 (Drift-role reads, R8-m3), S4.6 step 3 |
| NFR-07 | S1.1, S4.2, S4.4, S4.9, S4.10, S4.11–S4.14, S4.6 |
| NFR-08 | S2.4, S4.6 step 11 |
| NFR-09 | S4.3 (receipt after every checkpoint-writing subcommand), S4.2, S4.6 steps 13, 19 and 20 |
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

- **Chains:** C-contract, C-runtime and C-composition head.
- **Scope:**
  - `runtime_secrets.py`, **hardened branch only** (a projection with
    `workload_step`): it renders no Random or TLS generator and no
    `SecretVersion`; declared purposes `app_secret`, `oauth_encryption_key`
    (plus the interim `non_rotatable` KMS purposes until S1.8). The
    pre-hardening branch keeps its generators unchanged until S4.10 deletes
    that branch (m9; see the transition rule below);
  - `pulumi/app/workload_phase.py`: the `workload_step` branch that selects
    the hardened or the pre-hardening composition (C-composition head, m6);
  - the schema (AD-04), including `admission`, `workload_step`,
    `workload_operation` (`mode`; `phase` for `rollback-zero`; `sequence`;
    `resumes` for `resume`; R6-m7), `documentdb_secret_policy`, `scaling`
    (`starts: [{seq, at}]`, `stops: [{seq, at}]`, `consumed`; R5-M3; and the
    persistent TEST-only flag `scheduled_scaling_suspended`, default
    `false`; R6-m7) and the `central` XP-8 fields;
  - the workload `central` fields of architecture AD-04 (every role, function,
    key and XP-8 field that S1.5, S2.5, S3.3 and admission read), the
    top-level `workload_operation` and `scaling` fields;
  - the receipt **schemas** (`schemas/poc-workload-{step,export,import,abandon,accepted}-receipt-v1.schema.json`)
    and the observation schema `schemas/poc-workload-observation-v1.schema.json`
    (kind `start` or `stop`; R6-m6), so S4.10's rebuild variant and S4.11's
    library read schemas that already exist. A step receipt with
    `outcome: failed` carries `cause` ∈ {`apply`, `result-inspection`}
    (R6-m9). Every receipt carries its `workload_operation`; the export
    receipt has `cause` ∈ {`export`, `clear-pending`} and, for
    `clear-pending`, a required `predecessor` (receipt ID and checkpoint
    sha256) (R5-M2). A step receipt with `outcome: success` also records
    the **projection inputs** of the applied program (R7-M2, R8-m4): the
    `SourceAdmission` facts; the **full image rows** of both images as
    `project_workload_phase` checks them (`uri`, `manifest_media_type`,
    `config_digest`, `config_size`, `platform`;
    `scripts/poc_workload_phase_entrypoint.py` lines 52-93), not only
    the digests; the **certificate observation**
    `{parameter_arn, parameter_version, certificate_arn}` (the closed set
    of `scripts/poc_workload_capabilities.py` line 277), or `null` when the
    contract pins `certificate_arn`; and the **program trees**: the git
    object IDs of `scripts`, `pulumi`, `policy`, `schemas`,
    `pyproject.toml` and `uv.lock` in the installed checkout that ran the
    apply (the applied base). The scheduled path (S4.17) rebuilds the same
    projection from these values without a PR request and compares the
    program trees with its own installed `main`. The observation schema carries the
    bound success receipt's ID, run ID, run attempt and checkpoint sha256
    (R7-m6, audit F6);
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
  `tls:*` or `SecretVersion` types; without one, the pre-hardening graph is
  unchanged (the generators stay there until S4.10).
- **P:** the registry contract digest is unchanged.
- **P:** `test_actual_workload_program_native_first_plan` passes unchanged
  (the pre-hardening projection still renders the installed graph).
- **N:** a fixture re-adding `RandomPassword` or `SecretVersion` fails.
- **N:** a missing central function ARN or CMK gives BLOCKED admission.
- **N:** a Redis secret purpose is rejected by the schema (D-1 = IAM).
- **B:** seed input with any key other than `secret_arn` and `purpose` is
  rejected; a `scaling` entry without `at`, or a `clear-pending` export
  receipt without `predecessor`, fails the schema; a `rollback-zero`
  operation without `phase`, or a `resume` without `resumes`, fails the
  schema (R6-m7); a `success` step receipt without its projection inputs
  fails the schema (R7-M2). The PROD case (a PROD contract with
  `scheduled_scaling_suspended: true` fails) moves to S4.14, which owns the
  PROD contract schema (R7-m4): against the TEST-only schema it would fail
  for the wrong reason (`environment` is `const: test`).

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

- **Chains:** C-data, C-network head, C-compute head; C-composition after
  S1.1 (the step-1/step-2 structure and the XP-8 exports in
  `workload_phase.py`).
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

- **Chains:** C-data, C-network, C-compute; C-composition after S1.3 (the
  ElastiCache user and user-group types in `TAGGABLE_TYPES`).
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

**Acceptance criteria:** the PRD FR-10 rows. **N (fixtures only, m10):** on a
`workload_step` fixture, a DocumentDB audit or profiler log group without
`kms_key_id` fails, and a DocumentDB `master_user_secret_kms_key_id` fails.
The check over every log group of the real program (ECS, Container
Insights, flow logs) is not made here, because S1.8 adds those keys later;
it is S4.10 N3.
**Live (TEST):** S4.6 step 7 (`DescribeSecret` `KmsKeyId`,
`DescribeLogGroups` `kmsKeyId`).

### S1.11 (USI): Drift allow-list contract (FR-32)

- **Chains:** C-contract after S1.8 (R5-M4). S1.8 follows S2.1 in C-compute,
  so the program's `ignore_changes` (ECS `desiredCount`, target
  `minCapacity`/`maxCapacity`) exist when this story checks them. Ordered
  row 20, after S2.1 (row 16) and S1.8 (row 19).
- **Scope:**
  - `drift.out_of_band_fields` in the schema and contract, exactly the AD-23
    table, in two parts (audit): `ignore_fields` (ECS `desiredCount`; target
    `minCapacity`, `maxCapacity`) and `refresh_only_fields` (DocumentDB
    `masterUserSecrets[*].secretStatus`, an output). This story is the only
    writer of the list; S2.1 adds the program's `ignore_changes` and does
    not edit the list;
  - `test_drift_allow_list.py`: the program's `ignore_changes` (a
    `workload_step` projection of the real program, after S2.1) equal
    `ignore_fields` both ways; every `refresh_only_fields` entry names an
    output of a type in the program and has no `ignore_changes`;
  - a doc marker for the list in `docs/poc-workload-admission.md` (NFR-10).
- The FR-32 drift **reducer** is not here: it runs on the executed workload
  drift path (`scripts/poc_workload_reconciliation.py::validate_drift`,
  called by the drift gate of the runner's plan-plus-gate dispatch, R6-m4)
  and is S4.13. Nothing
  goes into `scripts/run_pulumi_drift_check.py`, which no workflow or make
  target runs (architecture §1 and AD-23).
- **V-13** (docs) is cited for the list semantics; its first case, with the
  engine source, is in S4.13.

**Acceptance criteria:**

- **P:** program `ignore_changes` equals `ignore_fields`.
- **N1:** an extra `ignore_changes` field fails.
- **N2:** a list entry for a type not in the program fails (closed list).
- **N3:** a `refresh_only_fields` entry that names an input, or that the
  program also ignores, fails.
- **B:** an `ignore_fields` entry that the program does not ignore fails
  (equal both ways); the DocumentDB `refresh_only_fields` entry passes with
  no `ignore_changes` on the cluster.
- **Live (TEST):** S4.6 step 14 (with S4.13).

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
  (step-2 set, never deleted by an apply mode; only the TEST abandon
  removes it with its cluster) rendering the document of the contract state
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

- **Chains:** new `autoscaling.py` (C-autoscaling head), `compute.py`
  (`ignore_changes`) in C-compute after S1.10, and the autoscaling-plane
  wiring and taggable types in `pulumi/app/workload_phase.py`
  (C-composition, m6). The autoscaling targets belong to the step-2 set.
- **Scope:** targets with `min = max(contract min, 1)` and
  `ignore_changes=["minCapacity","maxCapacity"]`; ECS services with
  `ignore_changes=["desiredCount"]`; target-tracking policies; one one-time
  start action `<svc>-start-<seq>` per `scaling.starts` entry and one stop
  action `<svc>-stop-<seq>` (`min = max = 0`) per `scaling.stops` entry, each
  with `schedule = at(<that entry's at>)` (per-action times, R5-M3), the
  start actions `depends_on` the target and policies, and the target's
  `suspendedState.scheduledScalingSuspended` rendered from the persistent
  TEST-only contract flag `scaling.scheduled_scaling_suspended` (S1.1,
  R6-m7), so an operation that leaves the flag unchanged renders the target
  `same`. A name in
  `scaling.consumed` is not rendered (architecture AD-10). The
  target-tracking values are contract values. The TEST scale-out is
  exercised by setting the policy's high alarm (`SetAlarmState`), so this
  story has no front-door dependency. This story does not edit
  `drift.out_of_band_fields` (S1.11 owns it, R5-M4). Every resource and
  every `ignore_changes` of this story renders only for a `workload_step`
  projection (AD-25 transition rule, audit), so
  `test_actual_workload_program_native_first_plan` stays green until
  S4.10.
- **First cases:** **V-23(e)** (provider source, m1): the pinned
  `pulumi-aws` provider's update path for `aws:appautoscaling/target:Target`,
  recording whether `RegisterScalableTarget` re-sends `MinCapacity` and
  `MaxCapacity` and which values it sends under `ignore_changes` with
  `up --refresh`; then **V-23** (docs, A-26). V-23(d) stays a live STOP at
  step 15.

**Acceptance criteria:**

- The PRD FR-11 rows.
- **N:** a start action with `min < 1`, or a stop action in a plan that also
  changes the target, fails.
- **B1:** appending the stop entry `seq: 1` after the start entry `seq: 1`, then the start entry `seq: 2`, renders
  exactly one new URN each time, and every earlier action's rendered inputs
  (`schedule`, `scalable_target_action`) are byte-equal to the previous
  rendering (FR-11: no change to an earlier action).
- **B2:** a fixture that changes an earlier entry's `at` changes that URN's
  `schedule` input, which S4.9 admission refuses (the entry is immutable
  once in state); moving an entry to `scaling.consumed` removes it from the
  rendering and changes no other URN.
- **B3 (R6-m7):** with the flag `true`, a `policy-update` projection renders
  every target byte-equal to the hold rendering (no `Target` update).
- **Live (TEST):** S4.6 step 7 (start observed, V-23), step 12 (scale-out
  by the alarm exercise), step 15 (stop, hold and restart; V-23 d).

### S2.2 (USI): Worker backlog autoscaling

- **Scope:** `autoscaling.py` (C-autoscaling), after S2.1.

**Acceptance criteria:**

- The PRD FR-12 rows.
- **Live (TEST):** S4.6 step 12 (backlog scale-out).

### S2.3 (USI): Owned SNS topic

- **Scope:** new `observability.py` (C-observability head), and its wiring
  into `WorkloadPhaseStack` (`pulumi/app/workload_phase.py`, C-composition,
  m6: the import next to lines 13-29, the plane in the step-1 set, and every
  taggable type that S2.3, S2.4 and S2.5 add in `TAGGABLE_TYPES`: topic,
  alarm, EventBridge rule). S2.4 and S2.5 edit only `observability.py`.
- The KMS key is the runtime CMK from S5.4 (D-4; CloudWatch alarms cannot
  publish to an `alias/aws/sns` topic). The subscription endpoint is XP-6.

**Acceptance criteria:** the PRD FR-13 topic rows; **N:** a topic without
the runtime CMK fails.

### S2.4 (USI): Alarm catalogue and runbooks

- **Scope:** `observability.py` (C-observability, after S2.3); the runbook
  section per alarm in `docs/sre-operations.md`. **Incident response
  (m18):** each runbook entry names the severity, the first responder (the
  service owner on call), the escalation (Kravalg for any §3.2a secret,
  IAM or KMS event), the containment action (for example the
  `rollback-zero` stop plan, a `policy-update` plan, or a BI key or role
  change by a reviewed PR) and the evidence to keep; a PROD stop records the
  incident reason (AD-10).
- **V-11** and **V-25** (docs) are the first cases.

**Acceptance criteria:**

- The PRD §3.1 and FR-13 rows.
- **N:** a runbook entry without severity, escalation or containment fails
  the doc test.
- **B:** desired=0 does not alarm.
- **Live (TEST):** S4.6 step 11 (delivery within 5 min, NFR-08).

### S2.5 (USI): Security and rotation EventBridge rules

- **Scope:** `observability.py` (C-observability, after S2.4), implementing the PRD §3.2 matching and
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

- **Chains:** C-compute after S3.7; C-autoscaling after S2.2.
- **Depends on:** S5.14 and S3.3.
- **Scope:**
  - TEST night and weekend scheduled actions, created in **step 2** (they
    are in the FR-34 step-2 set; their min/max effect is on the AD-23 list);
  - ARM64 in the program when the contract marks the image multi-arch; the
    **admission** check that refuses ARM64 without an arm64 manifest lives in
    S4.9 (C-contract);
  - `docs/poc-cost-review.md`, which includes the endpoint, NAT and
    CloudTrail read-event costs. Every figure carries a data-source label
    (AWS Pricing Calculator export or AWS Price List API query for
    `eu-central-1` with its retrieval date, or Cost Explorer actuals with
    the billing period), and the NFR-11 forecast threshold applies (m17).

**Acceptance criteria:** the PRD FR-14 rows; NFR-11. **N:** a figure without
a source label, an after-estimate more than 20% above its before-estimate
without a justification line, or any PROD increase without a justification
line (audit), fails the doc test. **B:** a TEST increase of exactly 20% needs
no justification.

## Epic 3: Network and TLS

### S3.2 (USI): Managed default SG

- **Chains:** C-network after S1.4; C-composition after S2.3 (its taggable
  type).

**Acceptance criteria:** the PRD FR-16 rows. **Live (TEST):** S4.6 step 12.

### S3.1 (USI): VPC flow logs to S3

- **Chains:** C-network; C-composition after S3.2 (the flow-log plane
  wiring and the bucket-family taggable types in `workload_phase.py`).
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

- **Chains:** C-network; C-guard after S1.6; C-composition after S3.1 (the
  endpoint and endpoint-SG taggable types).
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
  refuses a PROD stack with an HTTP target group; TEST keeps HTTP (D-2);
  `pulumi/app/workload_phase.py::_validate_target` (lines 125-160, today
  pinned to `test` and the TEST registries) parameterized by stack, so the
  program can render `prod` (C-composition tail, m6), which S4.10's PROD
  native plan needs.

**Acceptance criteria:** the PRD FR-19 PROD rows. **P:** a `prod` fixture
renders the HTTPS target group; **N:** a `prod` fixture with TEST registry
names raises. **Live:** none in TEST (TEST keeps HTTP, so no TEST run can
show the PROD shape). The PROD evidence is **P-1**: the PROD `plan` under
gate 2a (`admission.prod: "preview"`), run by the S4.14 `prod_preview` job
in the PROD account as an S4.7 precondition (m8). It is not an S4.6 step.

### S3.6: dropped

D-3 = REST API + WAF (decided 2026-09-30). WAF on the internal ALB is not
built.

### S3.7 (USI): Non-root capability drops and port

- **Chains:** C-compute after S1.8.
- **Depends on:** S5.9.

**Acceptance criteria:** the PRD FR-26 rows. **Live (TEST):** S4.6 step 16.

## Epic 4: Recovery, guard and admission

Stories appear in chain order: the C-runner head S4.1 → S4.4 → S4.5 (m5);
then the C-contract tail S4.10 → S4.11 → S4.9 → S4.2 → S4.3 → S4.12 → S4.13
→ S4.14 → S4.15 (R6-M2: S4.9 precedes S4.2); S4.16; then the live stories
S4.6 → S4.8; then S4.17 (after XP-14; a gate-2b precondition, R6-m11) and
S4.7.

### S4.1 (USI): Sanitized operator diagnostics

- **Chains:** C-runner head (m5). Its code is the worker diagnostics and its
  FR-20 test is `tests/unit/test_service_execution_worker.py`, both C-runner
  files, so it is not independent.

**Acceptance criteria:** the PRD FR-20 and NFR-01 rows. **Live (TEST):** S4.6
step 13 (induced failure).

### S4.4 (USI): Runtime admission guard (#57)

- **Chains:** C-runner after S4.1 (it edits `scripts/poc_workload_runner.py`).
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

- **Chains:** C-contract after S1.11; the only C-topology story (architecture
  AD-25).
- **Depends on (merged):** S1.1, S1.2, S1.3, S1.4, S1.5, S1.6, S1.7, S1.8,
  S1.9, S1.10, S1.11, S2.1, S2.2, S2.3, S2.4, S2.5, S2.6, S3.1, S3.2, S3.3, S3.4,
  S3.5-A, S3.7.
- **Scope (the only story that edits these files):**
  - `scripts/poc_workload_topology.py`: `expected_graph` split into the
    step-1 and step-2 graphs, parameterized by stack (`test`, `prod`;
    replacing the hard-coded `-test-` names at lines 61, 859, 955 (the
    `awslogs-group` name; R8-m2) and 1058, and the TEST URN prefix and
    root that lines 149-151 import from `poc_registry_plan` with the
    stack's own, derived deterministically as in the S4.14 reconciliation
    row, as are the service and provider URNs of lines 159, 175, 349 and
    393; the registry nodes of lines 144, 372 and 388, and of
    `scripts/poc_workload_secret_result.py` line 68, come from a
    stack-selected registry set, whose PROD entry is XP-14's and is
    stubbed in this story's PROD fixtures; the selector is a stack-keyed
    function that this story adds in `scripts/poc_registry_phase_entrypoint.py`
    next to `_REGISTRIES` (not a C-topology file), returning today's set
    for `test` and failing closed for `prod` until XP-14 adds the `prod`
    entry, an edit outside this plan like its `_mail_semantics` entry;
    see the S4.10 registry-set note in S4.14), for
    every resource those stories add or remove (AD-25 list), including
    `kms_key_id` on every log group and the pre-created Container Insights
    group; the PROD HTTPS target group (S3.5-A); the named URN sets that S4.9 admits (step-2 set,
    whose start action is named by the single unconsumed `scaling.starts` entry's `seq`; `rollback-zero` set; `policy-update` set); the
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
  - **the checkpoint-field allowance (R5-M5; a recorded, deliberate narrow
    change, architecture AD-23):** `scripts/poc_workload_reconciliation.py`
    (`UNSAFE_STATE` lines 31-49 rejects `ignoreChanges` at line 39 and
    `retainOnDelete` at line 45, checked at line 95; reused by
    `scripts/poc_workload_secret_result.py` lines 71 and 212 and
    `scripts/poc_gateway_backend.py` line 40) and
    `scripts/poc_workload_topology.py` (create goals with `ignoreChanges`
    rejected at lines 321-326, and a create step's `newState` with any
    `UNSAFE_STATE` field rejected in `_validate_workload_step`, lines
    1114-1115). Both accept `ignoreChanges` only when it equals the AD-23
    `ignore_fields` for the row's type, and `retainOnDelete: true`
    only on the abandon path for manifest `retain` URNs
    (`_inventory(…, abandon_retain=…)`). **`importID` (R6-m12, V-27):** if
    the engine source shows that `importID` persists on a checkpoint row
    after an `import_` apply, both accept it only on rows whose URN the
    authenticated import receipt lists (`_inventory(…, imported=…)`);
    `scripts/poc_registry_plan.py` line 312 stays unchanged, because no
    registry resource is ever imported. `docs/poc-workload-reconciliation.md`
    records the change;
  - `specs/poc-workload-runner.md` topology and checker text, with
    doc-marker tests.
- **V-27** (engine source, R6-m12) is a first case, like V-24: whether
  `importID` persists on a checkpoint row after an `import_` apply, read
  from the pinned Pulumi engine.

**Acceptance criteria:**

- **P:** the actual program's native step-1 and step-2 plans are admitted
  by the new graphs, for `test` and for `prod`.
- **P2 (R5-M5):** a checkpoint whose ECS service row has
  `ignoreChanges: ["desiredCount"]` and whose target row has
  `["minCapacity","maxCapacity"]` passes `_inventory`, the secret-result
  checker and the gateway projection; a create goal and a create step's
  `newState` with the AD-23 list pass the topology check; an abandon-path row with `retainOnDelete: true`
  for a manifest `retain` URN passes; if V-27 shows that `importID`
  persists, a row with `importID` that the import receipt lists passes.
- **N4 (R5-M5):** `ignoreChanges` on any other type, an extra field on a
  listed type, `retainOnDelete` outside the abandon path, or on a URN that
  is not a manifest `retain` entry, is refused; so is an `importID` on a
  row that the authenticated import receipt does not list (R6-m12).
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
  - `scripts/poc_workload_receipts.py` (write, publish, authenticate,
    latest-receipt lookup, lineage; architecture AD-24) over the S1.1 receipt
    schemas (step, export, import, abandon, accepted) **and the S1.1
    `poc-workload-observation-v1` records** (R7-m6): write, publish,
    authenticate and look up an observation record bound to one success
    receipt (receipt ID, run ID, run attempt and checkpoint sha256). S4.9's
    `hold` admission (N8) and S4.13's acceptance job use this function; no
    later story adds an authentication path. Every lookup reads the
    complete deployment and status pages; an API error or an incomplete
    pagination is an error, never an empty result (R7-m1, R7-m5);
  - `scripts/poc_workload_runner.py`: a step receipt after every admitted
    `up-plan`, on the success path (after the S4.10 result checks) and on
    the failure path (final checkpoint through the trusted backend,
    `outcome: failed`), written before `execute` returns the status;
    `_capture` (lines 44-47) binds to the mode's anchor; a success receipt
    records the projection inputs that S4.17 rebuilds the projection from
    (R7-M2, R8-m4): the `SourceAdmission` facts, the full image rows
    (`initial.images`) and the certificate observation
    (`initial.certificate`) exactly as runner lines 177-184 pass them to
    `project_workload_phase`, next to the projection digest and the
    generated-files digest the receipt already carries (AD-24), and the
    program trees of the installed checkout (the S1.1 field);
  - **result-inspection failure (R6-m9):** when the apply succeeds but
    `_inspect_first_result` (runner lines 124-148) or the S4.10 checker
    raises, the runner captures the final checkpoint through the trusted
    backend, writes an `outcome: failed` receipt with
    `cause: result-inspection`, and re-raises; only a failed capture leaves
    no receipt, which the recovery `export` covers;
  - **failure-path publication (m4, audit):** the worker fails the job on a
    non-zero status (`scripts/service_execution_worker.py` line 127,
    `require(result == 0, "worker-execution")`) or on a raise from the
    runner, so the worker copies the receipt file to `/public` in a
    `finally` block around `_test` and that check (R6-m9; today it copies
    only `plan` artifacts, lines 128-132). The host
    (`scripts/service_execution_host.py`) runs the container with
    `check=True` (`_run`, lines 76-83), mounts `/public` from a random
    `mkdtemp` (lines 166-167) and copies out only for `_preview` jobs (lines
    213-218); for `test_apply` it now runs the container without raising
    first, copies `/public/workload-receipt` to
    `.trusted/.artifacts/workload-receipt` in a `finally` path, and then
    raises on a non-zero status. **Both copies are no-ops when no receipt
    file exists (audit F2):** a registry-phase run writes none, so the
    worker's `finally` copy and the host's copy-out do nothing, and the
    worker test's plan-copy count
    (`tests/unit/test_service_execution_worker.py` line 130, a registry
    fixture) stays as it is; a sibling workload fixture checks the receipt
    copy. `test_apply` uploads that path in a step guarded by exactly
    `if: ${{ always() && needs.poc_prepare_source.outputs.phase == 'workload' }}`
    with `if-no-files-found: error`, like every other `self-deploy.yml`
    upload (lines 135, 274, 284 and 655): on a registry-phase run the step
    is skipped, so `test_apply` does not fail for a missing receipt and the
    registry chain still runs; on a workload-phase run a missing receipt
    fails the step, and the recovery `export` covers it. The new job
    **`test_apply_receipt`** in
    `.github/workflows/self-deploy.yml` (environment `governance-evidence`,
    no AWS credentials, `needs: [preflight, poc_prepare_source,
    test_apply]`) publishes and authenticates it on the success and the
    failure path. Its `if` has no `always()` (R6-M1): `!cancelled() &&
    needs.poc_prepare_source.result == 'success' &&
    (needs.test_apply.result == 'success' || needs.test_apply.result ==
    'failure')`, plus `command == 'up'`, `target_environment == 'test'`
    and `phase == 'workload'`. A cancelled job leaves no receipt; the
    recovery `export` covers it;
  - **workload-aware capture (audit):** `poc_workload_runner._capture` (line
    41) and `poc_workload_admission.inspect_registry` (line 150) call
    `poc_registry_runner._capture` (lines 254-258), whose
    `poc_registry_plan._prior`/`_state` (lines 365-376, 297-324) accept only
    registry URNs and reject `ignoreChanges`/`retainOnDelete`. For every
    mode except `first`, this story reads the checkpoint through
    `backend.capture_backend`, checks the registry rows with the registry
    rules and the workload rows with the S4.10 `_inventory` allowance, and
    binds it to the mode's anchor. This story does not change
    `poc_registry_plan.py`; the file's only change in this plan is S4.3's
    post-abandon baseline acceptance (R6-m13);
  - **stale wording (m4):** the runner module docstring (lines 1-7, "it
    issues no cross-run receipt") and `specs/poc-workload-runner.md` lines
    38-40 ("not a success receipt"), 50-52 ("before issuing any workload
    receipt") and 97-98 ("it still issues no receipt") describe the new
    receipts; lines 37-38 and 121-122 change in S4.13;
  - `scripts/poc_workload_admission.py`: `inspect_registry` (lines 150-166)
    and `observe_workload` (lines 464-475) apply the mode → anchor table of
    AD-24 instead of the registry-only count and equality, for every mode
    except `first`, which keeps today's rule; the registry receipt stays the
    release identity;
  - **workflow-shape tests (R6-M1; guardrail change):**
    `tests/pulumi/test_ci_guardrails.py` lines 262-273 and
    `tests/unit/test_trusted_test_controller_workflow.py` lines 16-26 (the
    closed `self-deploy.yml` job set) gain exactly `test_apply_receipt`;
    `tests/unit/test_poc_source_workflow.py` lines 214-223 extend the
    ancestry loop to `test_apply_receipt`, which must have
    `poc_prepare_source` as an ancestor, `!cancelled()` and
    `needs.poc_prepare_source.result == 'success'` in its `if`, and no
    `always(`. `comment_result` (`self-deploy.yml` lines 783-797) gains
    `test_apply_receipt` in its `needs` (R7-n3), and a new assertion next
    to `tests/unit/test_poc_registry_completion_workflow.py` lines 153-156
    pins it. A new assertion pins the `test_apply` receipt-upload step:
    its exact `if` above, `if-no-files-found: error` and the path
    `.trusted/.artifacts/workload-receipt` (audit F2). The negatives stay:
    no other new job, and
    `test_apply_receipt` has no `id-token: write` and no AWS credential
    step, so the credential-job set (`test_ci_guardrails.py` lines
    314-319) is unchanged. The PR needs an `APPROVED` review by `@Kravalg`
    specifically (a `@dmytrocraft` CODEOWNERS approval alone does not
    count), recorded with the PR number in the acceptance receipt, as the
    round-5 m14 hard-stop amendment is; without it the story does not
    merge.

**Acceptance criteria:**

- **P:** a successful step-1 fixture yields a schema-valid receipt bound to
  the new checkpoint; a failed apply fixture yields an `outcome: failed`
  receipt, which the worker copies before it raises `worker-execution` and
  the `test_apply_receipt` job publishes (workflow and host contract test:
  the worker exits 1 and the receipt still reaches the upload path).
- **P3 (R6-m9):** an apply fixture that succeeds but whose
  `_inspect_first_result` or S4.10 checker raises still yields an
  `outcome: failed` receipt with `cause: result-inspection`; the worker's
  `finally` copies it, the host copies it out, the job fails, and
  `test_apply_receipt` publishes it.
- **P2 (audit):** a checkpoint with the step-1 workload rows (ECS services
  with `ignoreChanges: ["desiredCount"]`) is captured and bound for
  `step2`; `first` still refuses it (`workload-completed-registry-required`).
- **N1:** a receipt with a changed checkpoint sha256, run ID or contract
  digest is refused.
- **N2:** an unauthenticated receipt (no matching deployment status) is
  refused.
- **N3:** every existing negative still fails the same way for `first`
  (`workload-checkpoint-binding`, `workload-completed-registry-required`,
  `workload-registry-checkpoint-changed`, `workload-stack`,
  `workload-first-command`).
- **N4 (R6-M1):** a workflow fixture with any other new job, a
  `test_apply_receipt` that holds AWS credentials, or a job-level `if`
  containing `always(` fails the workflow-shape tests.
- **P4 (R7-m6):** an observation record written by the library for a
  success receipt authenticates and is found by the lookup for that
  receipt. **N5 (R7-m6):** an observation record bound to another receipt,
  with a changed checkpoint sha256 or run attempt, or without a matching
  deployment status, is refused. **N6 (R7-m1, R7-m5):** a lookup whose API
  call fails, or whose deployment or status listing is incomplete (a
  missing or failed next page), raises instead of returning "no receipt".
- **B:** a receipt for an older checkpoint of the same stack (stale) is
  refused; the old "issues no receipt" sentences fail the doc test.
- **B2 (audit F2):** on a registry-phase workflow fixture the `test_apply`
  receipt-upload step is skipped by its phase guard; with no receipt file
  the worker's `finally` copy and the host's copy-out are no-ops, and the
  host and worker tests pass unchanged for the registry fixtures; on a
  workload-phase fixture a missing receipt fails the upload step.
- **Live (TEST):** S4.6 step 4.

### S4.9 (USI): Step-2, rollback-zero and policy-update admission; multi-arch admission (FR-34)

- **Chains:** C-contract after S4.11 (R6-M2). It precedes S4.2, whose
  `resume` applies its per-mode rules, its `start_at` window and the
  `rollback-zero` resume boundary.
- **Depends on:** S4.10 (URN sets), S4.11 (anchors), S2.6 (ARM64 flag).
- **Scope:**
  - admission mode `step2`: saved-plan steps only `create` or `same`;
    created URNs equal the S4.10 step-2 set (seed Invocations, rotations,
    secret policies including the managed-secret policy, targets, policies,
    TEST `ScheduledAction`s, the start action of the single unconsumed
    `scaling.starts` entry (`<svc>-start-1` on an on-time first build; the
    set names the entry by its `seq`)), or, in the
    rebuild variant,
    that set minus the URNs imported from the abandon receipt's `retain`
    set; no `update`, `replace` or `delete` of any step-1 URN;
  - step-2 preconditions: the latest receipt is a step-1 success (S4.11);
    the S5.5 receipt; the XP-8 metadata in the installed `main` contract
    (S4.6 step 5b);
  - admission mode `rollback-zero` in three phases (architecture AD-10):
    `stop` (only `create` of the `<svc>-stop-<seq>` of the new
    `scaling.stops` entry, plus `same`; every earlier action `same`);
    `hold` (TEST only; admitted only when the latest receipt is the `stop`
    plan's success receipt and its authenticated stop observation
    (`poc-workload-observation-v1`, kind `stop`, running = desired = 0)
    exists, R6-m6; the contract flag `scaling.scheduled_scaling_suspended`
    is `true`; exactly one `update` per target whose only changed input is
    `suspendedState.scheduledScalingSuspended` → true, plus `same`);
    `start` (the contract flag is `false`; that field → false, where set,
    plus `create` of the `<svc>-start-<seq>` of the new `scaling.starts`
    entry, plus `same`). **Flag rule (R6-m7):** only `hold` may set and only
    `start` may clear the flag; in every other mode, including a
    `policy-update` during a hold, every target must be `same`;
  - **first case (m1, V-23 e, provider source):** before the hold rule is
    implemented, the pinned provider's `Target` update path is read and the
    values it sends for the ignored `minCapacity`/`maxCapacity` under
    `up --refresh` are recorded; if an update can send values other than
    the live ones (0 and 0 after a stop), this story does not merge until
    the hold design changes in a reviewed PR. V-23(d) stays the live STOP
    at step 15;
  - **per-action immutability (R5-M3):** in every mode, an action URN that
    is already in the checkpoint must be `same`; an `update` or `replace`
    of an earlier action (for example a changed `at`) is refused;
  - admission mode `policy-update`: exactly one `update` step, whose URN is
    in the closed set {managed-secret `SecretPolicy`, each `VpcEndpoint`}
    and whose only changed input is `policy`;
  - the `start_at` window (m13), checked only for the new entry's `at()`
    against the replay admission time (the `_gate` check immediately before
    `up --plan`): at least + 10 min for `rollback-zero` and + 60 min for
    `step2` (above the 3300 s apply process timeout), at most + 120 min, so
    the separate observation job (S4.13) stays within its timeout and the
    apply job's FR-24 bounds are unchanged;
  - **observation record (R7-m6):** S4.9 adds no schema. The observation
    schema `poc-workload-observation-v1` is S1.1's, the authentication and
    lookup are the S4.11 library's, and the job that writes the record is
    S4.13's. `hold` admission calls the S4.11 lookup for the stop
    observation bound to the latest success receipt (the `stop` plan's);
  - the multi-arch admission check (moved from S2.6).

**Acceptance criteria:**

- The PRD FR-34 rows.
- **N1:** a step-2 plan updating the ECS service is refused.
- **N2:** step 2 without a step-1 success receipt, the S5.5 receipt or the
  XP-8 metadata is refused.
- **N3:** ARM64 without an arm64 manifest is refused.
- **N4:** a `rollback-zero` plan updating the target in any field other than
  `suspendedState`, deleting anything, or combining `stop` with the
  suspension is refused.
- **N5:** a `policy-update` plan with a `delete`, a second step, or a
  changed input other than `policy` is refused.
- **N6:** a `rollback-zero` entry 9 min after the replay admission time, a
  `step2` entry 59 min after it, or any entry 121 min after it, is refused.
- **N7 (R5-M3):** a plan that updates an earlier start or stop action (a
  changed `at` in the contract) is refused.
- **N8 (R6-m6, R6-m7, R7-m6):** a `hold` plan without the authenticated
  stop observation, or with one bound to another receipt, or with a `start`
  observation, is refused; a `policy-update` or `stop` plan that changes
  the flag (a `Target` update) is refused. The fixtures are records written
  by the S4.11 library (row 29), so the test needs no S4.13 code.
- **B:** an all-`same` step-2 plan is admitted and changes nothing; entries
  at exactly + 10 min (`rollback-zero`), + 60 min (`step2`) and + 120 min
  are admitted; a `policy-update` during a hold (flag `true`, every target
  `same`) is admitted.

### S4.2 (USI): Resume and abandon admission; fail-closed prior-checkpoint check

- **Chains:** C-contract after S4.9 (R6-M2), which follows S4.11.
- **Decision:** D-7, decided 2026-09-30. The abandon scope is unconditional
  and TEST-only.
- **Scope:**
  - `poc_workload_admission.py`: `resume`, anchored on the latest failed or
    export receipt (S4.11; an export receipt from `export` or from
    `clear-pending`, whose `predecessor` must be a failed or export receipt
    of the same lineage, R5-M2). **Resume condition (m11), also after step
    2:** the operation to finish is the anchor's `workload_operation`; the
    checkpoint holds the URNs of the last success receipt before the anchor
    (the registry resources for an interrupted step 1) plus a subset of the
    URNs that operation creates or updates; the plan may only `create` or
    `update` URNs of that operation under that operation's own admission
    rule (S4.9 for `step2`, `rollback-zero`, `policy-update`), plus `same`;
    a new action's `at()` must be inside the AD-10 window, and an action URN
    not yet in state may be replaced by a new `scaling` entry;
    `rebuild-first` (after an abandon: anchored on the
    import receipt that follows the abandon receipt; the checkpoint holds
    exactly the registry plus the abandon receipt's `retain` set; only
    `create` of the remaining step-1 URNs and `same`);
  - the AD-09 forbidden-URN check, as a function in
    `scripts/poc_workload_admission.py` called by `observe_workload` for
    every mode (m15). It does not touch `scripts/poc_workload_topology.py`,
    whose only writer is S4.10;
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
- **N6:** `resume` without a failed or export receipt is refused; a
  `resume` after step 2 whose plan touches a URN outside the anchor's
  operation, or a `clear-pending` export receipt whose `predecessor` is a
  success receipt, is refused;
  `rebuild-first` without an import receipt that follows an abandon receipt
  is refused, and so is a `rebuild-first` checkpoint holding a URN outside
  the `retain` set.
- **B:** `recovery_window_days` 7 and 30 accepted; 6 and 31 refused; a
  `resume` of an interrupted `rollback-zero` start plan (step 13 shape)
  whose checkpoint holds the step-2 URNs plus nothing of the start action
  is admitted.

### S4.3 (USI + BI): Reviewed CI recovery command

- **Chains:** C-contract after S4.2 (R6-M2); C-guard after S3.3.
- **Decision:** D-7, decided 2026-09-30. `abandon` is unconditional
  (TEST only).
- **Scope:**
  - `.github/workflows/recovery.yml` (`test-recovery`; `prod-recovery`
    without `abandon`), assuming `GitHubCiRecovery-user-service-infrastructure-{env}`
    (S5.7, S5.19);
  - `scripts/poc_workload_recovery.py` (`export`, `release-lock`,
    `clear-pending`, `import`, `abandon`), with every mutation as a saved
    plan through the classifier (AD-16). **Every subcommand that writes the
    checkpoint writes a receipt for the new checkpoint (R5-M2):** `export`
    an export receipt (`cause: export`); `clear-pending` an export receipt
    with `cause: clear-pending` and `predecessor` = the prior failed or
    export receipt's ID and checkpoint sha256; `abandon` the abandon receipt;
    `import` the import receipt (S4.11 library). `release-lock` writes no
    checkpoint: it refuses and writes nothing if the checkpoint sha256
    before and after differs;
  - **private, hash-only checkpoint reader (R6-m8):** `export`, and the
    before-hash of `clear-pending`, read the checkpoint under the recovery
    role with S3 `HeadObject`/`GetObject` and the lock listing, and record
    only `{version, etag, sha256}`, the pending-operation count and lock
    presence. The reader tolerates a non-empty `pending_operations`, a
    present lock and rows marked `delete` or `pendingReplacement`, which a
    cancelled apply leaves behind and which the trusted observer refuses
    (`scripts/poc_backend_observer.py` lines 366 and 391 and its empty
    lock-listing check). It never emits resource values, and admission
    never uses it;
  - `scripts/poc_registry_plan.py`: accepts the registry baseline after a
    verified abandon receipt; this is the file's only change in this plan
    (R6-m13; S4.11 leaves it unchanged);
  - the rebuild variant of `import` (registry graph plus the abandon
    receipt's `retain` set; `RestoreSecret` for a `schedule-deletion`
    secret before import); the import receipt lists every imported URN,
    which the S4.10 `importID` allowance reads (V-27, R6-m12);
  - the use of the S4.10 delete-action map (`recovery/delete-actions.json`)
    in the abandon preflight: every `delete` step's type must have an entry,
    and the S5.7 simulator matrix must allow exactly those actions;
  - the in-run Kravalg approval check: the run's environment approval
    (`GET /repos/{owner}/{repo}/actions/runs/{run_id}/approvals`) must be
    `approved` for the environment by Kravalg's user ID, with a different
    requester; otherwise refuse;
  - the status check `abandon-manifest-approval` (needs an `APPROVED` review
    by Kravalg's user ID on the PR head for any change to
    `recovery/abandon-manifest.json`; it reports success on every PR that
    does not change that file, because the USI ruleset's required checks
    are branch-wide); S5.22 (USI repository controls) makes it required and
    pins its issuer;
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
- **P2 (R5-M2, offline):** failed receipt → `release-lock` → `clear-pending`
  (writes the linked export receipt) → `resume` admitted by the S4.2
  admission; without the clear-pending receipt the same `resume` is refused
  as stale; `release-lock` on a fixture whose checkpoint changes is
  refused.
- **P3 (audit, offline; R6-m8):** a cancelled run with no receipt, whose
  checkpoint fixture has a non-empty `pending_operations` and a present
  lock → `export` through the private hash-only reader (export receipt
  carrying the installed `workload_operation`) →
  `release-lock` → `clear-pending` (predecessor = that export receipt) →
  `resume` admitted.
- **N6 (R6-m8):** the trusted observer still refuses the P3 fixture, and no
  admission path accepts a hash from the private reader.
- **Live (TEST):** S4.6 step 13 (resume rehearsal) and steps 18–20 (abandon
  and rebuild, NFR-09).

### S4.12 (USI): Runner mode routing (FR-35 part 2)

- **Chains:** C-runner after S4.11; C-contract after S4.3.
- **Scope:** `execute` and `_gate` dispatch by the installed contract's
  `workload_operation.mode` (and `workload_operation.phase` for
  `rollback-zero`; R6-m7): `first`, `rebuild-first`, `step2`, `resume`
  (whose `resumes` must equal the anchor's operation),
  `rollback-zero` (`stop`, `hold`, `start`), `policy-update` (to the S4.2
  and S4.9 admission functions), and
  `recovery-import` and `recovery-abandon` (to S4.3, only when invoked from
  `recovery.yml` in `test-recovery` or `prod-recovery`), each with the
  anchor of the AD-24 table.

**Acceptance criteria:**

- **P:** `step2` with a valid step-1 success receipt is admitted.
- **N1:** `step2` without it is refused.
- **N2:** an unknown mode, a mode that `workload_operation` does not name, or
  `recovery-abandon` outside `test-recovery` is refused; so is a
  `rollback-zero` without `phase`, or a `resume` whose `resumes` differs
  from the anchor's operation (R6-m7).
- **N3:** `first` against a checkpoint that already contains workload URNs
  is refused (`resume` is the only path).
- **B:** `resume` after an interrupted step 2 binds to that apply's failed
  receipt; `resume` after `clear-pending` binds to the clear-pending export
  receipt and finishes the operation it names.
- **Live (TEST):** S4.6 steps 7, 13 and 15.

### S4.13 (USI): Accepted-workload receipt; drift and releases open (FR-35 part 3; FR-32 drift check)

- **Chains:** C-runner after S4.12; C-contract after S4.12 (it also edits
  `scripts/poc_workload_reconciliation.py` after S4.10).
- **V-13** (docs + engine source) is the first case: the `plan` invocation
  (`preview --json --refresh --save-plan --show-sames`) emits the
  refreshed per-step states the reducer reads, and a refresh that changes
  only AD-23 fields yields only `same` steps (R6-m4).
- **Scope:**
  - `schemas/poc-workload-accepted-receipt-v1.schema.json` and
    `schemas/poc-workload-observation-v1.schema.json` (from S1.1);
  - **observation in its own job (m13, R6-m3, R6-m6):** new
    `scripts/poc_workload_observation.py` and the `self-deploy.yml` job
    `test_workload_observation`: environment `test-preview`;
    `needs: [preflight, poc_prepare_source, test_apply,
    test_apply_receipt]`; an `if` that requires
    `needs.test_apply.result == 'success'`,
    `needs.test_apply_receipt.result == 'success'`, `command == 'up'`,
    `target_environment == 'test'`, `phase == 'workload'` and a
    `poc_prepare_source` output `workload_observation` of `start` or
    `stop`; and its own concurrency group
    `workload-observation-${{ github.repository }}-test`, because it runs
    no Pulumi command and holds no state lock, so it must not hold
    `pulumi-state-…-test-test` while it waits. It waits until the new
    entry's `at()` time, only then requests preview-role credentials, and
    runs the AD-18 item-4 observation: for a start action every service
    healthy with running = desired ≥ 1; for a stop action every service
    with running = desired = 0 and each target at `min = max = 0`. It must
    pass within 30 min after the later of the `at()` time and the job's
    start (`test-preview` needs Kravalg's approval, so a late approval only
    delays the observation). At the end it captures the checkpoint through
    the trusted backend observer (`backend.capture_backend(source,
    operation="plan")`, preview role) and writes `{version, etag, sha256}`,
    together with the same-run `test_apply_receipt` receipt ID, run ID and
    run attempt, into the uploaded observation artifact, as
    `test_registry_observation` does. Its `timeout-minutes` covers the
    120-min window bound plus the observation, under GitHub's 360-min job
    limit. The apply job's 3300 s process timeout, 70-min budget and the
    FR-24 bounds (`tests/unit/test_apply_timeout_budget.py`) are unchanged;
  - **pre-credential admission (R7-m7),** modelled on
    `test_registry_observation` (`self-deploy.yml` lines 601-641): the
    steps are, in this order, (1) check out `.trusted` at `github.sha`
    without persisted credentials; (2) install the trusted runtime
    (`setup-poc-runtime`); (3) `poc_workload_observation.py admit`, which
    requires `GITHUB_JOB == "test_workload_observation"` (S4.14 adds
    `prod_workload_observation`), the same-run source artifact, a
    `command == 'up'` request for the job's environment, `base_sha ==
    GITHUB_SHA` and the current review through `poc_registry_runner._review`
    (as `poc_registry_completion.admit`, lines 103-112 and 162-166, does);
    (4) `poc_workload_observation.py wait`, which holds no credential and
    sleeps until the entry's `at()` time; (5) `admit` again; (6)
    `load-aws-ci-env` (preview keys only; like lines 611-627); (7) `admit`
    again; (8) `configure-aws-credentials` with the preview role (like
    lines 629-640); (9) `observe`; (10) the upload with
    `if-no-files-found: error`. Each credential step (6 and 8) directly
    follows an `admit` step, and neither that `admit` nor the credential
    step has an `if` or `continue-on-error`. **PR merged or
    closed during the wait:** `_review` calls `verify_reviewed_source`,
    which requires the pull request to be `OPEN`
    (`scripts/reviewed_source_admission.py` line 128), so the post-wait
    `admit` fails before any credential is issued, the job fails, no
    observation record or accepted receipt is published, and the
    acceptance job is skipped. The same check also requires the head and
    base to be unchanged (lines 130-131), so a new commit on the PR or
    another merge to `main` during the wait fails the same way. That is the S4.6 step-7 STOP: the step PR
    stays open until `test_workload_acceptance` finishes, and a lost
    observation is recovered by the next admitted start plan (AD-24: the
    first passing start observation writes the accepted receipt);
  - **lock-tolerant capture (R7-m8):** the observer requires an empty lock
    listing at the start and the end of a capture
    (`scripts/poc_backend_observer.py` lines 452 and 470), and
    `test_workload_drift` or a scheduled drift job of the same run window
    may hold the Pulumi lock. `observe` therefore lists the lock prefix
    through the observer's own read before each capture attempt and
    retries every 30 s while a lock exists (a capture that fails while a
    lock is listed is retried the same way; any other capture failure fails
    at once). It never deletes or breaks a lock. The retries stay inside the
    30-min observation window; if a lock is still present when the window
    ends, the job fails with `workload-observation-lock-timeout`, which is
    a STOP (S4.6 step 7): no record is published, and the next admitted
    start or stop plan repeats the observation;
  - **publication without AWS credentials (R6-m3):** the
    `governance-evidence` job `test_workload_acceptance`
    (`needs: [preflight, poc_prepare_source, test_apply,
    test_apply_receipt, test_workload_observation]`; an `if` that requires
    `needs.test_apply.result == 'success'`,
    `needs.test_workload_observation.result == 'success'`,
    `needs.preflight.outputs.command == 'up'`,
    `needs.preflight.outputs.target_environment == 'test'` and
    `needs.poc_prepare_source.outputs.phase == 'workload'`, so the ancestry
    test's TEST check, line 221, holds) has no
    `id-token: write` and no AWS step. It verifies the same-run observation
    artifact (upload digest and file sha256, as `test_registry_proof`
    verifies the registry observation). **Same-run binding (audit F6):**
    it requires that the artifact's checkpoint equals the checkpoint of the
    receipt that this run's `test_apply_receipt` published (same run ID and
    run attempt), and that this receipt is still the stack's latest receipt
    (S4.11 lookup, complete pagination). If another receipt has become the
    latest, or the checkpoints differ, the job fails and nothing is
    published: STOP (S4.6 step 7). It then publishes the accepted-workload
    receipt for the first passing start observation of a lineage, and
    otherwise a `poc-workload-observation-v1` record (kind `start` or
    `stop`) bound to that success receipt, both through the S4.11 library
    (R7-m6). The `stop` record is what S4.9 `hold` admission requires;
  - **FR-32 drift check on the executed path (R5-M1, R6-m4):** the runner
    (`scripts/poc_workload_runner.py` line 154 today refuses `drift`)
    admits `drift` only with an authenticated accepted receipt in the
    stack's lineage and a latest success receipt. It then follows the
    registry plan-plus-gate pattern (`scripts/poc_registry_runner.py` line
    344 maps `drift` to operation `plan`; line 364 dispatches it). It
    captures with operation `plan`, because the trusted observer's
    `_target` accepts only `plan` and `up-plan`
    (`scripts/poc_backend_observer.py` lines 181-185), and calls
    `run_pulumi_command._dispatch_command("plan", …)` (lines 833-839),
    whose `_run_plan_command` (lines 592-639) supplies the private plan
    path and captures the `--json` preview. `_run_regular_command` (lines
    816-830) is not used: it passes no plan path (`_required_plan_path`,
    `scripts/_pulumi_command_support.py` lines 159-162, raises for any
    invocation with a plan flag) and captures no JSON. The runner's gate
    passes the preview, the saved plan and the checkpoint of the latest
    success receipt to the new
    `scripts/poc_workload_reconciliation.py::validate_drift` (next to
    `validate_no_change`, lines 224-245). It accepts a refreshed state
    change only on the AD-23 fields of the row's type and a refresh-time
    removal of exactly the `scaling.consumed` actions, and names any other
    field in the sanitized summary. The `plan` invocation has no
    `--expect-no-changes`, so a drifted plan exits 0 and reaches the gate,
    which names the field; the gate's failure fails the command. **One
    exception is kept (audit F8):** `_run_plan_command` runs the shared
    `_validate_safe_preview` (`scripts/run_pulumi_command.py` lines
    611-613, defined at 483-510) before the gate (lines 614-617). A drift
    whose refresh makes Pulumi plan a replace or delete of a protected
    resource therefore fails closed with the safe-preview message
    ("…contains protected resource destruction; overrides are disabled.",
    lines 504-508), without the field named. The order is not changed:
    `_validate_safe_preview` is the protected-destruction guard shared by
    every plan path (the registry drift and `test_preview` included), and
    putting a workload gate in front of it would change that shared guard
    for a diagnostic gain only; the drift is still detected and the job
    still fails, which S4.6 step 14 treats as unlisted drift. No
    `PULUMI_INVOCATIONS` entry is added. `docs/poc-workload-reconciliation.md`
    (which today says the reducer is "not wired into the worker") describes
    the wiring. Nothing goes into `scripts/run_pulumi_drift_check.py`;
  - **gate-2 clean-drift job (R6-M1):** the new `self-deploy.yml` job
    **`test_workload_drift`**, launched through the host and the worker
    (both `JOBS` maps gain it; the host operation is `plan`, so the preview
    role), with environment `test-preview`, the
    `pulumi-state-${{ github.repository }}-test-test` concurrency group,
    `needs: [preflight, poc_prepare_source, test_apply,
    test_apply_receipt]`, and exactly this `if`:
    `needs.test_apply.result == 'success' && needs.test_apply_receipt.result == 'success' && needs.preflight.outputs.command == 'up' && needs.preflight.outputs.target_environment == 'test' && needs.poc_prepare_source.outputs.phase == 'workload' && needs.poc_prepare_source.outputs.workload_route == 'post-acceptance'`.
    So no drift job runs after step 1 or step 2, before an accepted
    receipt exists, and the latest success receipt is published before
    drift binds to it;
  - **routing outputs:** `scripts/poc_phase_source_adapter.py` (today it
    writes only `phase=`, line 291) also writes `workload_route`
    (`registry`, `pre-acceptance` or `post-acceptance`) and
    `workload_observation` (`none`, `start` or `stop`: `start` for
    `step2`, a `rollback-zero` start or a `resume` of either; `stop` for a
    `rollback-zero` stop or its `resume`). `workload_observation` comes
    from the same reviewed contract bytes as `phase`. **`workload_route` is
    derived from the authenticated receipt lineage, not from the contract
    bytes (R7-m5, audit F1):** for a `phase: workload` contract the adapter
    reads the stack's receipts through the S4.11 library (deployment and
    status readback with complete pagination) and writes `post-acceptance`
    only when the lineage holds an authenticated accepted-workload receipt
    with no abandon receipt after it; otherwise `pre-acceptance`, whatever
    the mode. So the first-deployment `rollback-zero` (AD-19) and the
    step-7 STOP `policy-update` for V-14 or V-20, which run before step 7b,
    route `pre-acceptance`; `test_workload_drift` is skipped and does not
    fail with `workload-accepted-state-receipt-required`. A lookup error or
    an incomplete pagination fails `poc_prepare_source`, so no cloud job
    runs. `poc_prepare_source` gains exactly `deployments: read` for this
    read (no write, no `id-token`). Both outputs are routing hints only:
    the worker, the runner and admission re-check the mode and the
    anchor;
  - **registry chain unchanged (R6-M1):** `test_post_apply_drift` keeps its
    `if` (`self-deploy.yml` lines 480-483) and `needs` (lines 486-489), and
    `test_registry_observation`, `test_registry_proof` and
    `test_registry_dispatch` keep their `needs` (lines 578-581, 664-667,
    726-730). No registry job needs a workload job, so a registry-phase
    run, on which `test_apply_receipt` is skipped, still runs the registry
    chain. A separate drift job was chosen instead of adding
    `needs: test_apply_receipt` to `test_post_apply_drift`: that `needs`
    would make GitHub skip the registry drift job, and the three registry
    jobs after it, on every registry-phase run. Avoiding that would need a
    status function in that job's `if`, and its `if` is pinned byte-equal
    by `tests/pulumi/test_ci_guardrails.py` lines 293-297 and
    `tests/unit/test_poc_registry_workflow.py` lines 128-132, so both
    registry pins would have to be rewritten (R7-n2;
    `tests/unit/test_poc_source_workflow.py` line 223 only rejects
    `always(`);
  - **workflow-shape tests (R6-M1; guardrail change).** This story rewrites
    each closed set it changes and keeps every negative:
    - `tests/pulumi/test_ci_guardrails.py` lines 262-273: the closed
      `self-deploy.yml` job set gains exactly `test_workload_drift`,
      `test_workload_observation` and `test_workload_acceptance`. Lines
      280-306: the `guards` map gains the exact `if` of each new job, and
      each still needs `preflight`; the `test_post_apply_drift` guard
      (lines 293-297) stays byte-equal. Lines 314-319: the credential-job
      set gains exactly `test_workload_drift` and
      `test_workload_observation` (`test_apply_receipt` and
      `test_workload_acceptance` hold no credentials). Lines 347-353: the
      state-job set gains exactly `test_workload_drift`; a new assertion
      checks that `test_workload_observation` runs no `make` target and no
      host `execute` and uses `workload-observation-${{ github.repository }}-test`;
    - `tests/unit/test_trusted_test_controller_workflow.py`: line 9
      (`JOBS`, the worker-launched jobs that recheck before each OIDC
      stage) gains `test_workload_drift`, and lines 16-26 (the closed set)
      gain the three new jobs;
    - `tests/unit/test_poc_registry_completion_workflow.py` lines 148-151:
      "no `test_workload*` job" becomes "the `test_workload*` jobs are
      exactly `test_workload_drift`, `test_workload_observation` and
      `test_workload_acceptance`"; `test_workload_apply` stays absent, and
      line 152 (no job text names `poc_workload_admission.py`) stays;
    - `tests/unit/test_poc_registry_workflow.py` lines 128-132 (the
      registry-only drift `if`) stay byte-equal, and a sibling test pins
      `test_workload_drift` the same way (preview role, `test-preview`);
    - `tests/unit/test_poc_source_workflow.py`: lines 214-223, the
      ancestry loop gains the three new jobs, with no `always(` in any of
      them; lines 196-201, the `poc_prepare_source` outputs gain
      `workload_route` and `workload_observation`; lines 57-62, the
      `poc_prepare_source` permissions gain exactly `deployments: read`
      (R7-m5; still no write and no `id-token`);
    - `tests/unit/test_poc_phase_source_adapter.py` lines 414-416: the
      exact output becomes
      `phase=registry\nworkload_route=registry\nworkload_observation=none\n`;
      new cases pin the lineage-derived route (B4, N8 below);
    - **credentialed-job lists (R7-m7):**
      `tests/pulumi/test_ci_guardrails.py` lines 389-396 (the jobs whose
      credential steps follow the host `recheck`, run against the real
      host with the change matrix of lines 397-409),
      `tests/unit/test_service_reviewed_credentials.py` lines 18-22
      (`CLOUD_JOBS`) and `tests/unit/test_service_execution_workflow.py`
      lines 9-13 (`CASES`) each gain exactly `test_workload_drift`. The
      observation job is not added to these three lists, because each of
      them requires the host `recheck` guard and exactly one host `execute`
      launch, which `test_workload_observation` must not have; a sibling
      parametrized test pins its own sequence instead: the ten steps of
      the pre-credential admission above in that order, an `admit` step
      immediately before `load-aws-ci-env` and before
      `configure-aws-credentials` with no `if` and no
      `continue-on-error`, no credential step before the `wait` step, and
      the same change matrix (`none` accepted; `retarget`, `base_moved`,
      `base_missing`, `head_moved`, `closed`, `merged` and
      `checkout_moved` refused) run against the real
      `poc_workload_observation.py admit`;
    - **`comment_result` (R7-n3):** `self-deploy.yml` lines 783-797 gain
      `test_workload_drift`, `test_workload_observation` and
      `test_workload_acceptance` in `needs`; the assertion next to
      `tests/unit/test_poc_registry_completion_workflow.py` lines 153-156
      pins them.

    The PR needs an `APPROVED` review by `@Kravalg` specifically (a
    `@dmytrocraft` CODEOWNERS approval alone does not count), recorded with
    the PR number in the acceptance receipt, as the round-5 m14 hard-stop
    amendment is; without it the story does not merge;
  - **scheduled drift (R5-M1):** `.github/workflows/scheduled-drift.yml`
    (TEST job lines 23-84, PROD job lines 86-147) runs `make test-drift` →
    `scripts/run_pulumi_command.py drift` under the drift role against the
    baseline program `pulumi/__main__.py` (lines 18-30), which renders no
    workload and checks no receipt. **Per stack (R7-m2):** S4.13 excludes
    only stack `test`, and only when the installed `main`
    `specs/poc/poc-test.json` (today's `CONTRACT_PATH`,
    `scripts/poc_phase_admission.py` line 24) has `phase: workload`; it
    never excludes `prod`, because the `prod` stack reads its own contract
    (S4.14 adds that rule). The drift path of `run_pulumi_command.py` (not
    `_configured_stack_names`, line 84, which `preview`, `plan` and
    `up-plan` share) excludes the stack and prints the recorded reason
    `workload-drift-routed-to-runner`. When every stack is
    excluded, the command exits 0 with the notice (today an empty list
    returns 1, lines 850-856). The exclusion and its reason are recorded in
    `specs/poc-workload-runner.md`. Scheduled workload drift is S4.17
    (R6-m11), a gate-2b precondition with its own schedule-only
    provenance. The same baseline-program limit already applies to a
    `phase: registry` TEST stack; that is recorded for the registry owner
    and not changed here;
  - `scripts/service_execution_worker.py` line 99: `drift` admitted only
    with the accepted receipt; releases and release rollback also need a
    clean-drift result bound to the latest receipt, and use
    `inspect_retained_secret_history` with the receipt observation;
  - the worker docstring (line 5) and
    `tests/unit/test_service_execution_worker.py` (line 166: drift refused
    without the receipt, routed with it);
  - `specs/poc-workload-runner.md` lines 121-122 (the release checker's
    caller now authenticates the accepted receipt);
  - the `scripts/poc_workload_reconciliation.py` module docstring (lines
    1-7: "The worker intentionally does not call it until those
    independent gates and result observation are implemented") describes
    the `validate_drift` wiring, together with
    `docs/poc-workload-reconciliation.md` (R7-n3);
  - the **reviewed amendment** (Kravalg-approved governance PR): the README
    sentence (`specs/poc/README.md` line 127), the runner spec (lines
    37-40) and `docs/poc-workload-log-health.md` line 57 become "The PR
    `drift` command is admitted only with an authenticated
    accepted-workload receipt and is rejected without one." (R8-m5: the
    sentence names the PR `drift` command, because the S4.17 scheduled
    diagnostic also runs before acceptance and is not this command);
    `tests/unit/test_workload_apply_docs_consistency.py`
    line 175 carries the new sentence, and line 185 becomes two assertions
    (drift not routed without a receipt; routed with one).

**Acceptance criteria:**

- **P:** `drift` with a valid accepted receipt is routed through
  `test_workload_drift` (preview role) to the runner's plan-plus-gate
  dispatch, and a refresh fixture that changes only ECS `desiredCount` and
  target `minCapacity`/`maxCapacity` passes `validate_drift`.
- **P2 (R6-m3, audit F6):** `test_workload_acceptance`, with no AWS
  credential, issues the accepted receipt from a same-run observation
  artifact whose checkpoint equals the checkpoint of this run's
  `test_apply_receipt` receipt (same run ID and attempt), which is still
  the latest receipt.
- **N1:** `drift` without it is refused with
  `workload-accepted-state-receipt-required` (runner) and
  `workload-drift-not-enabled` (worker).
- **N2:** a release with an accepted receipt but no clean-drift result is
  refused.
- **N3:** the old README sentence without the new one fails the doc test.
- **N4 (FR-32, R6-m4):** a refresh fixture changing
  `aws:elasticache/user:User.accessString`, or any field not on the AD-23
  list, fails `validate_drift` with that field named, and the command
  exits non-zero although the preview itself exited 0. A refresh fixture
  whose plan replaces or deletes a protected resource exits non-zero with
  the safe-preview message and never reaches the gate (audit F8).
- **N5 (R7-m2):** the scheduled drift with a `phase: workload`
  `poc-test.json` runs no baseline preview for stack `test`, prints
  `workload-drift-routed-to-runner` and exits 0 when no stack is left;
  stack `prod` is still previewed by the baseline in the same fixture
  (S4.13 never excludes `prod`); `preview`, `plan` and `up-plan` stack
  selection is unchanged.
- **N6 (m13, R6-M1):** a workflow fixture whose observation job requests
  credentials before the wait, whose `timeout-minutes` is below the window
  bound plus 30 min, or whose drift, observation or acceptance job lacks
  `test_apply_receipt` in `needs` or `needs.test_apply.result == 'success'`
  in its `if`, fails the workflow contract test.
- **N7 (R6-m3, audit F6):** an observation artifact whose checkpoint
  differs from this run's `test_apply_receipt` receipt, whose run ID or
  attempt differs, whose receipt is no longer the latest, or whose digest
  does not match the upload, is refused by `test_workload_acceptance`, and
  nothing is published.
- **N8 (R7-m5):** an adapter fixture whose receipt lookup fails, or whose
  deployment or status listing is incomplete, fails `poc_prepare_source`
  (no route output is written); a contract whose mode is `rollback-zero`
  but whose lineage holds no accepted receipt never routes
  `post-acceptance`.
- **N9 (R7-m7):** an observation fixture whose pull request is merged or
  closed during the wait fails at the post-wait `admit` before any
  credential step; a workflow fixture with a credential step before the
  `wait` step, or without an `admit` immediately before each credential
  step, fails the sibling workflow test.
- **N10 (R7-m8):** an observation fixture with a lock listed for the whole
  30-min window fails with `workload-observation-lock-timeout` and
  publishes nothing; no fixture path deletes a lock.
- **B:** an accepted receipt from before an abandon is refused after the
  abandon (lineage broken); a refresh-time removal of exactly the
  `scaling.consumed` actions passes, and of any other action fails.
- **B2 (registry regression, R6-M1):** on a registry-phase workflow fixture,
  where `test_apply_receipt` is skipped, the `needs` and `if` of
  `test_post_apply_drift`, `test_registry_observation`,
  `test_registry_proof` and `test_registry_dispatch` name no workload job
  and are byte-equal to today's, so the registry chain still runs; the
  unchanged `tests/unit/test_poc_registry_completion_workflow.py` lines
  16-23 (the observation needs exactly `preflight`, `poc_prepare_source`
  and `test_post_apply_drift`) still pass.
  The same fixture also skips the `test_apply` receipt-upload step (its
  phase guard) and `test_apply` succeeds without a receipt (audit F2; S4.11
  B2).
- **B3 (R6-m6):** a stop-plan fixture routes to `test_workload_observation`
  with the stop expectation (running = desired = 0), and its published
  record is kind `stop`.
- **B4 (R7-m5, audit F1):** a first-deployment `rollback-zero` stop and a
  step-7 STOP `policy-update`, each before any accepted receipt, route
  `pre-acceptance`; `test_workload_drift` is skipped and the run does not go
  red; the same `rollback-zero` after an accepted receipt routes
  `post-acceptance`, and after an abandon routes `pre-acceptance` again.
- **B5 (R7-m8):** an observation fixture with a lock listed for 5 min,
  then released, captures the checkpoint and passes inside the window.
- **Live (TEST):** S4.6 steps 7b, 14 and 15 (and again in step 20).

### S4.14 (USI): PROD path (FR-35 part 4)

- **Chains:** C-runner after S4.13; C-contract after S4.13.
- **First case: grep-derived TEST-pin inventory (R8-m2).** The pin table
  below is complete by construction: the story first runs, read-only,
  over `scripts/`,

  ```
  grep -rnE --include='*.py' '891377212104|-test|"test"|Pulumi\.test\.yaml|CONTRACT_PATH' scripts/
  grep -rnE --include='*.py' '/test/|(backend|registry)\.(ACCOUNT|BUCKET|PROVIDER|PREFIX|ROOT|STACK|ENVIRONMENT)\b|SECRET_PREFIX|mail\.(DOMAIN|ZONE|ARN)\b|^(DOMAIN|ZONE) = ' scripts/
  grep -rnE --include='*.py' '\b(registry|graph)\.(REGISTRIES|DEFAULT_TAGS|[A-Z_]+_URN|_graph)\b|from poc_registry_plan import|urn:pulumi:test::|/test\.json|vilnacrmtest' scripts/
  ```

  The first command is the requested literal inventory (the TEST account
  ID, `-test`, `"test"`, `Pulumi.test.yaml` and `CONTRACT_PATH`); the
  second and third catch the indirect uses of the TEST constants that the
  first misses (for example `backend.ACCOUNT`, the `/test/` path
  segments, the TEST registry set and tags, the TEST URNs, the checkpoint
  key and the TEST mail domain; the third was added from the pre-commit
  audit). At `72873f9` (the workload source is unchanged from the
  baseline) they return 87, 38 and 41 lines. Every hit has an owner or an
  exclusion reason below. The story adds a test that re-runs the three
  commands and fails on any hit outside this table, keyed on the file and
  the matched text, not on line numbers (which this story's own edits
  shift), so a new TEST pin cannot land unowned.

  | File | Lines hit (grep 1; grep 2; grep 3) | Owner | Row or exclusion reason |
  | --- | --- | --- | --- |
  | `scripts/service_execution_worker.py` | 26, 27, 28, 30, 74, 93 | S4.14 (26-30 also S4.17) | `JOBS`/`ACCOUNTS` gain the PROD jobs and account (scope below) and the two scheduled jobs (S4.17); 74 and 93: pin-table rows |
  | `scripts/service_execution_host.py` | 142 | S4.14 | pin-table row |
  | `scripts/poc_workload_runner.py` | 53, 82, 164, 202; 190, 191, 194, 195; 42 | S4.14 | pin-table rows (53, 82, 164, 202, 194-195; 42: the capture row). 190-191 excluded: `registry.ROOT` there is `poc_registry_runner.ROOT`, the installed repository path (`scripts/poc_registry_runner.py` line 35), not a stack coordinate |
  | `scripts/poc_workload_materializer.py` | 24, 89, 126 | S4.14 | pin-table rows |
  | `scripts/poc_workload_capabilities.py` | 22, 23; 30, 32, 92, 111, 130, 133, 286 | S4.14 (with XP-15 and XP-16) | pin-table row |
  | `scripts/poc_workload_images.py` | —; 44, 68, 126, 282, 349; 53, 239, 346 | S4.14 (the PROD registry set: XP-14) | pin-table row |
  | `scripts/poc_workload_phase_entrypoint.py` | 18, 41, 111 | S4.14 | 18 and 41: the `CONTRACT_PATH` row; 111: the role-prefix row (109-116) |
  | `scripts/poc_workload_admission.py` | 110; —; 148, 154 | S4.14 (the PROD registry set: XP-14) | 110: the `CONTRACT_PATH` row; 148 and 154: the `inspect_registry` row |
  | `scripts/poc_phase_admission.py` | 24, 119, 216, 219 | S4.14 | 24: the stack → contract mapping (scope below); 119, 216, 219: the `CONTRACT_PATH` row |
  | `scripts/poc_source_artifact.py` | 256, 314 | S4.14 | the `CONTRACT_PATH` row |
  | `scripts/poc_phase_source_adapter.py` | 119, 181, 213, 241 | S4.14 | the `CONTRACT_PATH` row |
  | `scripts/poc_contract.py` | 17, 99, 109, 122, 125; —; 112 | S4.14 (the PROD mail domain: XP-14) | 17: the schema dispatch (scope below); 99, 109, 112, 122, 125: the `poc_contract.py` rows |
  | `scripts/poc_secret_observation.py` | 11; 11, 19 | S4.14 | the `SECRET_PREFIX` row |
  | `scripts/poc_workload_topology.py` | 61, 859, 955, 1058; 149, 151, 1160; 144, 159, 175, 349, 372, 388, 393 | S4.10 (the PROD registry set: XP-14, stubbed) | 61, 149-151, 859, 955, 1058: parameterized by stack in S4.10 (the only C-topology writer); 144, 372 and 388 (`registry.REGISTRIES`, `registry._graph`) and 159, 175, 349 and 393 (`SERVICE_URN`, `PROVIDER_URN`): the S4.10 registry-set note below. 1160 excluded: `registry.STACK` and `registry.ENVIRONMENT` are Pulumi type tokens (`scripts/poc_registry_plan.py` lines 22 and 25), not stack coordinates |
  | `scripts/poc_backend_observer.py` | 37, 40, 41, 183, 194, 206, 220, 222, 225, 325; 43; 42, 345, 363 | XP-14 | the observer rows (constants including `CHECKPOINT` at 42, `_target`, `_target_coordinates`, `_caller`, `_key`, `LOCKS`, the provider URN at 345 and the URN prefix at 363) |
  | `scripts/poc_registry_runner.py` | 175, 176, 272, 305, 338, 364; 130, 131, 194, 240, 242, 245, 269, 270, 358, 359; 187, 232, 258, 262, 347, 367 | XP-14 | 269-272: the `_binding` row; 187, 194, 232, 240-245, 258 and 262: the capture row. 130-131 (`_runtime_environment`), 175-176 (`_project`), 305 (`_gate`), 338, 347, 358-359, 364 and 367 (`execute`) excluded from S4.14: registry-phase code that the workload path never calls (it calls only `_capture`, `_review`, `_binding`, `_read_plan`, `_trusted_root` and the module handles) |
  | `scripts/poc_registry_plan.py` | 21, 27, 36, 55, 61, 63, 69, 71; —; 26 | XP-14 | the `poc_registry_plan.py` row |
  | `scripts/poc_registry_phase_entrypoint.py` | 16, 20 | XP-14 | the `_REGISTRIES` row |
  | `scripts/poc_registry_completion.py` | 30, 32, 33, 105, 257, 367; 118; 116, 150, 153, 159, 173, 198, 200, 280, 282 | XP-14 | the registry-completion row |
  | `scripts/poc_mail_prerequisite.py` | —; 13, 14, 15; 13, 27, 394 | XP-14 | the capture row (the SES and DKIM inventory) and the `_mail_semantics` row |
  | `scripts/poc_scheduled_registry_drift.py` | 24, 106, 138, 184; 177, 178; 125, 126, 128 | XP-14 | excluded from S4.14 and S4.17: the TEST registry scheduled diagnostic, connected to no workflow (`specs/poc/README.md` lines 52-57); S4.17 models its gate and does not call it |
  | `scripts/poc_publisher_dispatch.py` | 89 | XP-14 (with the PROD counterpart of XP-12) | excluded from S4.14: the TEST image publisher environment `poc-test-images`, used by the TEST registry dispatch job (`self-deploy.yml` lines 762 and 780); PROD image publication is outside this plan |
  | `scripts/poc_workload_reconciliation.py` | —; —; 15 | S4.14 | the reconciliation row (`PREFIX`/`ROOT` imports) |
  | `scripts/poc_workload_secret_result.py` | —; —; 68 | S4.10 (the PROD registry set: XP-14, stubbed) | the S4.10 registry-set note below |
  | `scripts/configure_github_repository_controls.py` | 80, 85 | — | excluded: environment-name lists that already include `prod` and `prod-preview` (S5.21 edits the file for other reasons) |
  | `scripts/governance_promotion.py` | 160, 265 | — | excluded: loops over both `test` and `prod` |
  | `scripts/initialize_service_stack.py` | 33 | — | excluded: accepts both `test` and `prod` |
  | `scripts/pulumi_command_preflight.py` | 304 | — | excluded: the environment list already adds `prod-preview` and `prod` for a `prod` request |
  | `scripts/pulumi_pr_comment.py` | 11, 36 | — | excluded: `/pulumi <action>` defaults to `test`, and `/pulumi prod <action>` is already parsed |
  | `scripts/run_mutation_tests.py` | 64, 66 | — | excluded: false positives (`--tests-dir`, `--test-time-multiplier`) |

  **S4.10 registry-set note (pre-commit audit).** The expected graphs of
  `scripts/poc_workload_topology.py` (lines 144, 372, 388) and
  `scripts/poc_workload_secret_result.py` (line 68) start from the TEST
  registry graph (`registry._graph(RegistryPhaseProjection(registry.REGISTRIES))`)
  and hang workload nodes under `registry.SERVICE_URN` and
  `registry.PROVIDER_URN` (topology lines 159, 175, 349, 393). S4.10
  derives the stack's service and provider URNs from the stack's own
  prefix, which is deterministic (`scripts/poc_registry_plan.py` lines
  26-30 build them from `PREFIX`), and takes the registry nodes (names,
  tags, outputs) from a stack-selected registry set. For `test` that set
  is today's; for `prod` it is XP-14's (the `_REGISTRIES` and
  `poc_registry_plan.py` rows), so S4.10's PROD fixtures stub it, as
  S4.14's do, and S4.10 reads nothing from row 48. No PROD registry name
  is assumed.

- **Scope:**
  - `scripts/service_execution_worker.py` `JOBS`/`ACCOUNTS` (lines 25-30)
    and `scripts/service_execution_host.py` `JOBS` (lines 27-31, with the
    `prod_apply` receipt copy-out of S4.11) gain `prod_preview`,
    `prod_apply`, `prod_workload_drift` and account `933245420672`; the
    source binding accepts `prod` only per `admission.prod` (`"preview"` →
    `plan` only; `true` → apply);
  - `.github/workflows/self-deploy.yml` gains exactly seven PROD jobs,
    mirroring the TEST jobs: `prod_preview` (`prod-preview`),
    `prod_destructive_diff` (no credentials), `prod_apply` (`prod`),
    `prod_apply_receipt` (`governance-evidence`), `prod_workload_drift`
    (`prod-preview`, preview role), `prod_workload_observation`
    (`prod-preview`) and `prod_workload_acceptance`
    (`governance-evidence`). Each is guarded by
    `target_environment == 'prod'` and by the new `poc_prepare_source`
    output `admission_prod` (written by
    `scripts/poc_phase_source_adapter.py` from the installed `main`
    `poc-test.json`): `preview` or `true` for `prod_preview` and
    `prod_destructive_diff`, `true` for the other five. No other PROD job
    exists;
  - the **stack → contract mapping** (R6-m11, architecture AD-04):
    `scripts/poc_phase_admission.py` `CONTRACT_PATH` (line 24) becomes
    stack-aware, and an offline `specs/poc/poc-prod.json` fixture drives
    the tests; the committed file comes with XP-14;
  - **the PROD contract schema (R7-m4):** today
    `schemas/poc-test-v1.schema.json` pins `environment: test` (lines
    179-181), the TEST account (lines 182-184) and the TEST backend
    (lines 188-209), so no PROD contract can validate. S4.14 adds
    `schemas/poc-prod-v1.schema.json` (`environment` `const: prod`,
    `account_id` `const: "933245420672"`, the PROD backend
    `s3://pulumi-user-service-infrastructure-prod-state` and
    `awskms://alias/pulumi-user-service-infrastructure-prod-secrets?region=eu-central-1`,
    the same pattern as the worker's `_coordinates`,
    `scripts/service_execution_worker.py` lines 57-65) and the stack
    dispatch in `scripts/poc_contract.py` (`SCHEMA_PATH`, line 17, stays
    the TEST schema). The PROD schema carries the TEST-only constraints:
    no `admission` object (it lives only in `poc-test.json`),
    `scaling.scheduled_scaling_suspended` `const: false`, and no night or
    weekend schedule (AD-04). It accepts `phase: registry` (the file XP-14 commits) and
    `phase: workload` (the S4.7 PRs). `poc-test-v1.schema.json` is not
    widened, so its `account_id` `const` stays readable by the trusted
    observer (`scripts/poc_backend_observer.py` lines 199-201). The S1.1
    B-case "a PROD contract with `scheduled_scaling_suspended: true` fails
    the schema" moves here, against the PROD schema;
  - **baseline scheduled drift for `prod` (R7-m2):** the S4.13 exclusion in
    the `drift` branch of `run_pulumi_command.py` gains stack `prod`, only
    when the installed `main` `specs/poc/poc-prod.json` exists and has
    `phase: workload`. A missing `poc-prod.json` (before XP-14) or
    `phase: registry` keeps the baseline drift for `prod` running;
  - the runner accepts `prod` with the PROD certificate parameter (XP-15,
    the PROD counterpart of XP-10; the TEST-analogous name is pinned as an
    assumption that the gateway owner confirms in this PR before it merges,
    R8-m6), the PROD topology (S4.10), the PROD registry anchor (XP-14)
    and `prod-recovery`; `abandon` is never admitted for PROD.
    `prod_workload_drift` runs the S4.13 drift path under the PROD preview
    role, and the PROD observation and acceptance jobs mirror
    `test_workload_observation` and `test_workload_acceptance`;
  - **every TEST-only pin on the path (R6-m5)**, each with its PROD fixture
    or its owner:

    | Pin | Today | S4.14 change and PROD fixture |
    | --- | --- | --- |
    | `scripts/service_execution_host.py` line 142 | `recheck` requires `target_environment == "test"` | accepts `prod` for the `prod_*` jobs only, and only when the installed `main` `poc-test.json` has `admission.prod` other than `false`. Fixture: a `prod_preview` recheck under `"preview"` passes; a `prod_apply` recheck under `"preview"` fails. |
    | `.github/workflows/self-deploy.yml` line 62 | `poc_prepare_source` runs for `test` only | runs for `test` and `prod`. Fixture: a `prod` request prepares source facts and routes only to `prod_*` jobs. |
    | `.github/workflows/self-deploy.yml` lines 79-86 | the source route refuses every target except `test` ("PROD promotion is unavailable") | refuses every target except `test` and `prod`. Fixture: `prod` exits 0; `""` and `dev` still exit 1. |
    | `scripts/service_execution_worker.py` line 74 | `_replay_inputs` requires account `test` | accepts `prod` for `prod_apply`. Fixture: PROD replay inputs are copied. |
    | `scripts/service_execution_worker.py` line 93 | the source binding requires `target_environment == "test"` | accepts `prod` per `admission.prod`. Fixture: a PROD `plan` under `"preview"` passes; a PROD `up-plan` under `"preview"` fails. |
    | `scripts/poc_workload_runner.py` line 53 | the gate requires `stack == "test"` | requires the request's stack. Fixture: a `prod` gate with the PROD topology passes; a `test` plan under a `prod` request fails. |
    | `scripts/poc_workload_runner.py` line 82 | the prepared configuration is for stack `test` | the request's stack. Fixture: the PROD configuration is materialized. |
    | `scripts/poc_workload_runner.py` line 164 | the request binding requires `test` | the request's stack per `admission.prod`. Fixture: as for worker line 93. |
    | `scripts/poc_workload_runner.py` line 202 | dispatch to stacks `["test"]` | `[<stack>]`. Fixture: PROD dispatch. |
    | `scripts/poc_workload_reconciliation.py` lines 15, 92 and 104 | TEST `PREFIX` and `ROOT` imported from `poc_registry_plan` | the stack's own prefix and root. Fixture: PROD checkpoint rows pass `_inventory`; TEST rows under a `prod` stack fail. |
    | `scripts/poc_backend_observer.py` line 183 (with the constants at lines 37-43), line 363 and line 389 | TEST account, bucket, provider, URN prefix and stack name | **assigned to XP-14**: the PROD registry phase owns the observer's PROD coordinates, because the PROD registry capture needs the same ones (PRD §7). S4.14's PROD fixtures stub `backend.capture_backend` with PROD coordinates, and gate 2a refuses PROD without XP-14. Line 184 (operations `plan` and `up-plan` only) is not a TEST pin and does not change; the drift capture maps to `plan` (S4.13). |
    | `scripts/poc_backend_observer.py` lines 199-201 (R7-m3) | the target check reads `poc_contract.SCHEMA_PATH` and requires its `account_id` `const` to equal the TEST `ACCOUNT` | **assigned to XP-14** with the other observer coordinates. S4.14 keeps this read working: the PROD schema is a separate file and `poc-test-v1.schema.json`'s `account_id` stays a `const` (R7-m4). |
    | `scripts/poc_registry_runner.py` lines 266-283 (`_binding`), called by the workload gate at `scripts/poc_workload_runner.py` line 58 (R7-m3) | the provider identity must carry `backend.ACCOUNT`, `s3://{backend.BUCKET}` and `stack: "test"` | the workload gate binds with the request's stack and that stack's observer coordinates through a stack-aware binding in `poc_workload_runner.py`; the registry `_binding` itself is unchanged (the registry path stays TEST until XP-14). Fixture: a `prod` provider identity (PROD account, PROD bucket, `stack: "prod"`) passes; a TEST identity under a `prod` request fails; the TEST binding is unchanged. |
    | `scripts/poc_workload_capabilities.py` lines 22-23 (`ROLE_NAMES` `-test-EcsExecution`, `-test-EcsTask`), 30 (`CERTIFICATE_PARAMETER_NAME` `/vilnacrm/test/user-service/gateway-certificate-arn`), 32 (SSM parameter ARN), 92 (role ARN), 111 (`policy/issue219/test/boundary/`), 130-133 (trust `aws:SourceAccount`/`aws:SourceArn`) and 286 (ACM certificate ARN pattern); reached through `scripts/poc_workload_admission.py` line 470 (R7-m3) | TEST role names, certificate parameter, account and boundary path | parameterized by the request's stack: `-{stack}-EcsExecution`/`-{stack}-EcsTask`, the PROD certificate parameter (XP-15, the PROD counterpart of XP-10), the PROD account in every ARN, and the PROD boundary path (XP-16, the PROD counterpart of XP-11). **Assumption, not a decision (R8-m6):** S4.14 pins the deterministic, TEST-analogous names `/vilnacrm/prod/user-service/gateway-certificate-arn` and `arn:aws:iam::933245420672:policy/issue219/prod/boundary/`; the gateway owner (XP-15) and the bootstrap owner (XP-16) confirm the names in this PR before it merges (a naming statement recorded here, not the row-49 deliverable, which is the parameter and path existing live), and S4.7 verifies them live. `iam:SimulatePrincipalPolicy` runs only for the execution role (`_pull`, lines 193-232, called at line 338 with `roles["execution"]`); `iam:GetRole` reads both roles (lines 333 and 341). Fixture: PROD role, certificate and boundary reads pass for a `prod` request; a TEST role name or the TEST certificate parameter under a `prod` request fails; the TEST fixtures are unchanged. |
    | `scripts/poc_workload_images.py` lines 44 (`REGISTRY_HOST`), 68 (`--registry-id`), 126 (`get-authorization-token --registry-ids`), 282 (`registryId` check) and 349 (image URI) (R7-m3), and the TEST registry set at lines 53, 239 and 346 (`graph.REGISTRIES`; R8-m2, pre-commit audit) | the TEST account's ECR registry | the request's stack account and the stack's registry set (the PROD registry names are XP-14's and stubbed). Fixture: PROD image digests from `933245420672.dkr.ecr.eu-central-1.amazonaws.com` pass for a `prod` request; a TEST registry ID under a `prod` request fails. |
    | `scripts/poc_registry_plan.py` lines 21 (TEST `ACCOUNT`), 26-27 (`PREFIX` `urn:pulumi:test::…`, `ROOT`), 36 (`user-service-test-{kind}` registry names), 51-59 (`DEFAULT_TAGS`, `Environment: test` at line 55; R8-m2), 60-65 (`ENVIRONMENT_OUTPUTS`, `environment: test`, `stackTag` at line 63) and 69-71 (`ROOT_OUTPUTS` TEST backend URL and secrets provider) (R7-m3) | the TEST registry graph, URN prefix and root outputs | **assigned to XP-14**: the PROD registry graph is registry-phase work. The R6-m13 rule ("`poc_registry_plan.py` changes only in S4.3") scopes this plan's stories only; any XP-14 change to this file is outside that rule and outside this plan. For `prod`, S4.14 reads the PROD counterparts that XP-14 provides (the registry graph, `_ecr_inventory` coordinates and tags used by the capture, row below) and its fixtures stub them; the reconciliation row above replaces the `PREFIX`/`ROOT` imports with the stack's own. |
    | `scripts/poc_workload_runner.py` lines 40-48 (`_capture`) → `scripts/poc_registry_runner.py` lines 254-263 (`_capture`: TEST registry graph, `_ecr_inventory` at lines 240-245 with `backend.ACCOUNT`, `graph.DEFAULT_TAGS`; `ecr_read`, lines 185-199, with `--registry-id` `backend.ACCOUNT` at line 194; and `graph.mail.inspect_inventory`, with the TEST domain, zone and identity ARN of `scripts/poc_mail_prerequisite.py` lines 13-15 and the TEST zone name at lines 27 and 394; R8-m2) (audit) | the registry rows of every capture are checked against the TEST registry graph and TEST ECR | the S4.11 workload-aware capture checks the registry rows against the request stack's registry graph, ECR coordinates and tags (TEST today; PROD from XP-14). Fixture: a PROD checkpoint with PROD registry rows passes for a `prod` request with the XP-14 counterparts stubbed; TEST registry rows under a `prod` request fail. |
    | `scripts/poc_workload_runner.py` lines 194-195 (`backend_url`, `secrets_provider` from `registry.backend.BUCKET`/`PROVIDER`) (audit) | TEST backend | the request stack's observer coordinates (XP-14 for PROD). Fixture: the PROD context carries the PROD bucket and provider. |
    | `scripts/poc_workload_phase_entrypoint.py` lines 109-116 (role prefix `…-test`, `workload-role-binding`), reached from runner line 179 (audit) | the central ECS role ARNs must be the TEST ones | the prefix uses the contract's stack (`…-{stack}`). Fixture: PROD central role ARNs pass for a PROD contract; TEST role ARNs in a PROD contract fail. |
    | `scripts/poc_workload_materializer.py` line 89 (`"environment": "test"` in the expected baseline configuration), reached from runner line 90 (audit) | TEST stack configuration | the request's stack. Fixture: the PROD baseline configuration materializes; a TEST configuration under a `prod` request fails. |
    | `scripts/poc_workload_materializer.py` lines 24 (`FILES` names `Pulumi.test.yaml`) and 126 (the generated `Pulumi.test.yaml` document) (R8-m2) | the generated stack configuration file is named for stack `test` | `Pulumi.<stack>.yaml` from the projection's `backend.stack`, in `FILES` and in `_documents`. Fixture: a PROD projection materializes exactly `Pulumi.yaml`, `Pulumi.prod.yaml`, `__main__.py` and `python`; a `Pulumi.test.yaml` under a `prod` request fails. |
    | `scripts/poc_contract.py` lines 116-126 (`_registry_semantics`: ECR ARN and URI with the TEST account), run by `_semantics` (line 185) inside `_validate_document` (line 190) for **every** contract, including XP-14's `phase: registry` `poc-prod.json` (R8-m2) | a PROD contract's registries fail "registry ARN/name mismatch" | **owned by S4.14 in the C-contract chain:** the account comes from the contract's own `account_id`, which each stack's schema pins as a `const` (TEST `891377212104`, PROD `933245420672`). Fixture: a PROD `phase: registry` contract with PROD ECR ARNs and URIs validates; a PROD contract with TEST ECR identifiers fails; the TEST fixtures are unchanged. |
    | `scripts/poc_contract.py` lines 102-113 (`_mail_semantics`: the TEST SES identity ARN at line 109 and the owned domain `user.vilnacrmtest.com`), run through `_workload_semantics` (line 153) for every `phase: workload` contract, so for the S4.7 PROD workload PRs (R8-m2) | a PROD workload contract fails "SES identity/sender must match the TEST owned domain" | **S4.14 owns the code; XP-14 owns the PROD domain (explicit note).** The identity ARN's account comes from the contract's `account_id`, and the owned domain comes from a per-stack map whose `test` entry is today's value. The PROD sending identity is a PROD registry-phase resource (XP-14; `scripts/poc_mail_prerequisite.py` lines 13-15 hold the TEST domain, zone and ARN), and this plan does not decide its domain, so S4.14 ships the map with no `prod` entry: every PROD workload contract fails `_mail_semantics` until XP-14 adds the entry, and gate 2a refuses PROD without XP-14. XP-14's edit to this map is outside this plan, like its `poc_registry_plan.py` constants. Fixture: with the `prod` entry stubbed, a PROD workload contract validates; a PROD contract with the TEST identity fails; with no entry it fails closed. |
    | `scripts/poc_contract.py` line 99 (the error text names `poc-test-v1`) (R8-m2) | names the TEST schema | names the schema of the contract's stack. Fixture: a PROD shape failure reports `poc-prod-v1`. |
    | `scripts/poc_secret_observation.py` line 11 (`SECRET_PREFIX`, the TEST secret ARN prefix), used at line 19 and reached through `validate_secret_observation` from `scripts/poc_workload_secret_result.py` (imported at line 17; called at lines 206, 254 and 272) (R8-m2) | every observed secret ARN must be in the TEST account | **owned by S4.14** (C-contract; S1.1 also edits this file): the prefix is built from the `account_id` of the contract that `validate_secret_observation(contract, …)` already receives, so `scripts/poc_workload_secret_result.py` (C-topology, S4.10 only) is not edited. Fixture: PROD secret ARNs pass for a PROD contract; TEST ARNs under a PROD contract fail; the TEST fixtures are unchanged. |
    | `CONTRACT_PATH` consumers (R8-m2): `scripts/poc_phase_admission.py` lines 119 (metadata `path`), 216 and 219 (`main`: the contract read and the `schemas/poc-test-v1.schema.json` read); `scripts/poc_source_artifact.py` lines 256 and 314; `scripts/poc_phase_source_adapter.py` lines 119, 181, 213 and 241; `scripts/poc_workload_phase_entrypoint.py` lines 18 and 41 (`_source` requires `source.path == CONTRACT_PATH`); `scripts/poc_workload_admission.py` line 110 (the registry contract read at the registry receipt's head) | every source path, contents read and path check is `specs/poc/poc-test.json` | each uses the contract path (and, at line 219, the schema path) of the request's stack from the stack → contract mapping; `poc-test.json` stays the only `admission` record and is still read for `admission.prod`. Fixture: a `prod` request's source metadata, contents reads and entrypoint `_source` check use `specs/poc/poc-prod.json` and `schemas/poc-prod-v1.schema.json`; `poc-test.json` as the contract of a `prod` request fails `workload-source-path`; a `test` request never reads `poc-prod.json` (B). |
    | `scripts/service_execution_host.py` line 164 (`backend._target_coordinates`) and the observer target check (lines 183 and 188-210) (audit) | TEST coordinates before the container starts | **assigned to XP-14** (observer coordinates); S4.14's host fixtures stub them with checking PROD stand-ins (R8-A1, host-test item below), and S4.7 adds the unstubbed PROD case after XP-14. |
    | `scripts/poc_backend_observer.py` lines 42 (`CHECKPOINT`, `.pulumi/stacks/…/test.json`), 345 (the TEST provider URN) and 213-228 (`_caller`: the session names `gha-scheduled-test-drift-{run_id}` and `gha-pr-test-{purpose}-{run_id}` at lines 219-223 and the `-test` assumed-role ARN at line 225), line 325 (`_key`: the KMS alias `alias/pulumi-…-test-secrets`) and line 43 (`LOCKS`, the TEST lock prefix) (R8-m2) | TEST caller identity, secrets key and lock prefix | **assigned to XP-14** with the other observer coordinates. The PROD analogues are the session names the workflows use (`gha-scheduled-prod-drift-${{ github.run_id }}`, already at `scheduled-drift.yml` line 139; `gha-pr-prod-{purpose}-${{ github.run_id }}` for the S4.14 jobs), the `-prod` role and alias, and the `…/prod/` lock prefix; S4.14's fixtures stub them. |
    | `scripts/poc_registry_phase_entrypoint.py` lines 13-22 (`_REGISTRIES`: `user-service-test-web`, `user-service-test-worker`), checked by `_stable_registries` (lines 38-52), which the workload path calls at `scripts/poc_workload_phase_entrypoint.py` lines 107 and 314 and `scripts/poc_workload_capabilities.py` line 326 (R8-m2) | a PROD contract's registries fail "Registry ownership differs" | **assigned to XP-14**: the PROD registry names are PROD registry-phase data. S4.14's workload callers select the request stack's registry set, and its fixtures stub the PROD set. Fixture: a PROD contract with the stubbed PROD names passes; TEST names in a PROD contract fail. |
    | `scripts/poc_workload_admission.py` lines 147-155 (`inspect_registry`: the anchor capture uses `registry.graph.REGISTRIES` and `registry.graph._graph`, the TEST registry set and graph) (R8-m2, pre-commit audit) | the first-workload anchor check counts the TEST registry graph | the stack's registry set and graph (TEST today; PROD from XP-14, stubbed). Fixture: a PROD checkpoint with exactly the stubbed PROD registry resources passes for a `prod` request; the TEST set under a `prod` request fails. |
    | `scripts/poc_registry_completion.py` lines 30, 32-33 (TEST environment `poc-test-registry` and the record kinds), 105, 257 and 367 (TEST request and contract path) and 118 (TEST ECR ARN), reached from `scripts/poc_workload_admission.py` line 134 (`completion.verify_completion`, the registry anchor of the first workload) (R8-m2) | the registry anchor is verified only as a TEST registry completion | **assigned to XP-14**: the PROD registry completion receipt is XP-14's. S4.14's PROD admission fixtures stub it; gate 2a refuses PROD without XP-14. |

  - **docs (NFR-10, R8-m5):** `specs/poc/README.md` lines 52-57 ("The
    scheduled TEST and PROD jobs retain the installed main-only
    `make test-drift` route … the TEST-only launcher does not accept
    scheduled jobs") state the per-stack baseline exclusion (`test` from
    S4.13, `prod` from this story) and that the PR launcher now accepts
    the PROD jobs behind `admission.prod`; this is a README governance
    change and needs the same `@Kravalg` approval as the rest of this
    PR; `docs/poc-workload-admission.md` line 10 ("PROD remains absent;
    scheduled drift retains the installed-main path") names the seven
    PROD jobs behind `admission.prod` and the per-stack exclusion;
    `docs/ci-guardrails.md` line 147 (the `Scheduled Test Drift` and
    `Scheduled Prod Drift` row) and lines 170-181 ("Scheduled drift and
    PR commands") state that the baseline jobs skip a workload-phase
    stack with `workload-drift-routed-to-runner`. S4.17 amends the same
    three places for the scheduled workload jobs;
  - **workflow-shape tests (R6-M1; guardrail change):**
    - `tests/pulumi/test_ci_guardrails.py`: lines 262-273, the closed job
      set gains exactly the seven `prod_*` jobs; lines 280-306, their exact
      `if`s; lines 314-319, the credential-job set gains exactly
      `prod_preview`, `prod_apply`, `prod_workload_drift` and
      `prod_workload_observation`; lines 347-353, the state-job set gains
      exactly `prod_preview`, `prod_apply` and `prod_workload_drift`, each
      on `pulumi-state-${{ github.repository }}-prod-prod`; lines 98-101,
      "no `prod_` job" becomes "the `prod_` jobs are exactly the seven,
      each behind `admission_prod`";
    - **further pins that S4.14 breaks (R7-M1)**, each with its exact new
      assertion; the TEST assertions next to them stay unchanged:
      - `tests/pulumi/test_ci_guardrails.py` line 249,
        `assert "prod_destructive_diff" not in jobs`, becomes: the job
        exists; it has no `id-token` permission and no
        `configure-aws-credentials` or `load-aws-ci-env` step; its `needs`
        is exactly `["preflight", "poc_prepare_source", "prod_preview"]`;
        its `if` is pinned exactly (`job["if"] == …`, not a substring
        check; R8-A3), with the `||` parenthesized as the
        `poc_prepare_source` guard below does, because `&&` binds tighter
        than `||` in a GitHub Actions expression:
        `github.event_name == 'repository_dispatch' && needs.preflight.outputs.target_environment == 'prod' && (needs.poc_prepare_source.outputs.admission_prod == 'preview' || needs.poc_prepare_source.outputs.admission_prod == 'true')`
        (the dispatch clause, as its TEST twin, keeps scheduled execution
        excluded); an unparenthesized form fails the test; its last step
        runs `destructive-gate`. Lines 250-255 (the TEST job) stay
        byte-equal;
      - `tests/pulumi/test_ci_guardrails.py` lines 281-284, the
        `poc_prepare_source` guard, becomes exactly
        `${{ needs.preflight.result == 'success' && (needs.preflight.outputs.target_environment == 'test' || needs.preflight.outputs.target_environment == 'prod') }}`
        (with `self-deploy.yml` line 62);
      - `tests/unit/test_trusted_test_controller_workflow.py` lines 72-75
        (one `…-test-test` group for every `JOBS` member) become a
        per-environment group: for a job named `<env>_…`,
        `pulumi-state-${{ github.repository }}-<env>-<env>`, so
        `prod_preview`, `prod_apply` and `prod_workload_drift` use
        `…-prod-prod` and the TEST jobs keep `…-test-test`; lines 101-104
        (`target_environment == 'test'` in each `JOBS` job's `if`) become a
        per-environment check: each `JOBS` job's `if` contains
        `needs.preflight.outputs.target_environment == '<env>'` for its
        own `<env>` and never the other one, the `prod_*` jobs also
        contain `admission_prod`, and `poc_prepare_source` contains both
        values (the guard above);
      - `tests/unit/test_poc_source_workflow.py` line 221 (TEST in every
        ancestry-loop job) becomes per-environment: each `test_*` job's
        `if` contains `target_environment == 'test'`, each `prod_*` job's
        `if` contains `target_environment == 'prod'` and `admission_prod`;
        lines 219, 222-224 (ancestry, no `false &&`, no `always(`, no
        `continue-on-error`) stay for every job;
      - `tests/unit/test_service_execution_host.py` lines 78-144, which
        run over every `host.JOBS` member: the fixture sets the role
        metadata for the job's environment (`-test` or `-prod` role ARN,
        TEST or PROD account). `host.execute` reaches
        `backend._target_coordinates` (host line 164; observer lines
        188-210, TEST account, `-test` role, TEST bucket and provider) and,
        in the seam test, `backend._target` (observer line 183), both
        XP-14-owned; so for a `prod_*` job S4.14's fixtures replace
        `_target_coordinates`, `_target` and `capture_backend` with
        **checking PROD stand-ins (R8-A1)**, not pass-through stubs: each
        compares `AWS_ACCOUNT_ID` with `933245420672`, the job's role key
        with `arn:aws:iam::933245420672:role/GitHubCi<Kind>-user-service-infrastructure-prod`,
        `PULUMI_BACKEND_URL` with
        `s3://pulumi-user-service-infrastructure-prod-state` and
        `PULUMI_SECRETS_PROVIDER` with the PROD alias URL, and `_target`
        also requires the request's `target_environment == "prod"`. On a
        mismatch the stand-in raises the observer's own error through
        `backend._require` (`ValueError("Backend observation precondition
        failed")`, observer lines 76-79); on a match `capture_backend`
        calls the patched `aws_read` boundary
        (`("sts", "get-caller-identity", {})`). So the `None`,
        `"missing"`, `"role"`, `"account"`, cross-environment and
        `"worker"` faults of lines 233-322 keep their meaning for PROD
        jobs: `calls` is `["docker", "native-sts"]` on success, `[]` for a
        host-side fault and `["docker"]` for the worker fault, as today.
        The unstubbed real-seam PROD case is S4.7's, after XP-14
        (below). Line 141,
        `destination = root if job == "test_preview" else workspace`,
        becomes `destination = root` for every `_preview` job, matching
        the host's copy to `ROOT` for every `_preview` job
        (`scripts/service_execution_host.py` lines 214-219), so
        `prod_preview`'s artifacts are checked under `root`; lines 233-271:
        the request at line 244 uses the job's environment
        (`target_environment` `test` for `test_*`, `prod` for `prod_*`);
        every fault depends on the job's environment: `"account"` (line
        268) replaces the job's own account with `000000000000`; `"prod"`
        (line 269) becomes a cross-environment fault that swaps the job's
        role suffix for the other environment's, so a `-prod` role on a
        TEST job still fails and a `-test` role on a PROD job is added;
        `"worker"` (line 311) swaps the suffix the same way inside the
        worker;
      - `tests/unit/test_service_execution_host.py` lines 173-178 (R7-M1,
        audit): today both `host.prepare` refusals (a valid and a foreign
        `Pulumi.yaml`) pass only because `prod_preview` is not in
        `host.JOBS`; `prepare` (host lines 130-134) checks job membership
        and reads no project file. The new form: `prod_preview` passes
        `host.prepare`, and both refusals are kept on an unknown job
        (`prod_destroy`), so they keep failing for today's reason. No
        project-runtime check is added;
      - `tests/unit/test_service_execution_worker.py` lines 81-131: the
        loaded source's `request.target_environment` (line 101) is the
        job's account from `worker.JOBS[job]`, and the fixture's
        `coordinates(monkeypatch, account)` (line 84) already follows it;
        a `test` request under a `prod_*` job and a `prod` request under a
        `test_*` job fail with `workload-source-binding`;
      - **credentialed-job lists (R7-m7):**
        `tests/pulumi/test_ci_guardrails.py` lines 389-396 gain
        `prod_preview`, `prod_apply` and `prod_workload_drift`, and the
        fixture environment at line 465 (`REQUEST_TARGET_ENVIRONMENT`)
        uses the job's environment. Because the real host `recheck` now
        reads `admission.prod` from the installed `poc-test.json` (host
        line 142 row above), the temporary repository of that test commits
        a `specs/poc/poc-test.json` fixture with `admission.prod` `"preview"`
        for `prod_preview` and `true` for `prod_apply` and
        `prod_workload_drift`;
        `tests/unit/test_service_reviewed_credentials.py` lines 18-22
        (`CLOUD_JOBS`) and `tests/unit/test_service_execution_workflow.py`
        lines 9-13 (`CASES`) gain the same three jobs; the S4.13 sibling
        observation test gains `prod_workload_observation`, and
        `poc_workload_observation.py admit` accepts that job for a `prod`
        request;
      - `comment_result` (`self-deploy.yml` lines 783-797) gains the
        seven `prod_*` jobs in `needs`, pinned by the S4.13 assertion
        (R7-n3);
    - `tests/unit/test_trusted_test_controller_workflow.py`: line 9
      (`JOBS`) gains `prod_preview`, `prod_apply` and
      `prod_workload_drift`, and lines 16-26 gain the seven jobs;
    - `tests/unit/test_service_execution_workflow.py`: line 58 ("no
      `prod_*` job") becomes the same closed PROD set, and line 55
      ("PROD promotion is unavailable") becomes the new source-route
      message;
    - `tests/unit/test_service_initializer.py` lines 330-336: the PROD
      peers `prod_preview`, `prod_apply` and `prod_workload_drift` share
      the PROD state group;
    - `tests/unit/test_service_execution_host.py` lines 173-178: see the
      R7-M1 list below;
    - `tests/unit/test_poc_source_workflow.py`: lines 40-50 (`prod` is no
      longer rejected by the source route; `""` and `dev` still are), lines
      196-201 (the new `admission_prod` output) and lines 214-223 (the
      ancestry loop gains the `prod_*` jobs, with no `always(`);
    - `tests/unit/test_poc_phase_source_adapter.py` lines 414-416: the
      exact output gains `admission_prod=false`.

    Negatives kept: no other job and no other credentialed job; PROD is
    reachable only through these seven jobs, behind `admission.prod`;
    `abandon` is never reachable for PROD. The PR needs an `APPROVED`
    review by `@Kravalg` specifically, recorded with the PR number in the
    acceptance receipt like the round-5 m14 amendment; without it the story
    does not merge.

**Acceptance criteria:**

- **P:** a PROD fixture with `admission.prod: true` and every PROD input is
  admitted offline; a PROD `plan` fixture under `"preview"` is admitted.
- **P2 (R6-m5, R7-m3):** every row of the pin table passes its PROD
  fixture, with the observer and the XP-14 registry counterparts stubbed
  for the XP-14 rows.
- **P3 (R8-m2):** the inventory test re-runs the three grep commands of
  the first case, and every hit maps to a row or an exclusion of the
  inventory table.
- **N1:** PROD with `admission.prod: false` is refused; a PROD `up-plan`
  under `"preview"` is refused.
- **N2:** PROD `recovery-abandon` is refused; PROD without XP-14 is refused.
- **N3 (R6-M1):** a workflow fixture with a PROD job outside the seven, or a
  PROD job without the `admission_prod` guard, fails the workflow-shape
  tests.
- **N4 (R7-M1):** a `-prod` role on a TEST job and a `-test` role on a PROD
  job both fail the host seam test; a `prod_destructive_diff` with
  credentials, without `prod_preview` in `needs`, without the
  `admission_prod` guard, or with the `||` not parenthesized (R8-A3)
  fails; a PROD state job on `…-test-test` fails; a PROD stand-in given a
  TEST account, role, bucket or provider raises the observer's error
  (R8-A1).
- **N6 (R8-m2):** a new TEST literal in `scripts/` that neither grep row
  nor exclusion covers fails the inventory test; a PROD contract with TEST
  ECR identifiers fails `_registry_semantics`; a PROD workload contract
  fails `_mail_semantics` while the `prod` domain entry is absent.
- **N5 (R7-m4):** a PROD contract with `scheduled_scaling_suspended: true`,
  with an `admission` object, with `environment: test`, or with the TEST
  account or backend fails `poc-prod-v1.schema.json`; a TEST contract with
  `environment: prod` still fails `poc-test-v1.schema.json`.
- **B:** the TEST path is unchanged (every TEST test passes); a `test`
  request never reads `poc-prod.json`; the observer's
  `schema["account_id"]["const"]` read (lines 199-201) still passes.
- **B2 (R7-m2):** the baseline scheduled drift keeps previewing `prod`
  when `poc-prod.json` is missing or has `phase: registry`, and excludes
  `prod` with `workload-drift-routed-to-runner` only when it has
  `phase: workload`; the `test` exclusion follows `poc-test.json` alone.
- **Live (TEST):** S4.6 step 2 (PROD refused). PROD live use is S4.7.

### S4.15 (USI): TEST acceptance receipt validator and two-gate hard-stop test

- **Chains:** C-contract after S4.14.
- **Scope:** `schemas/poc-test-acceptance-receipt-v1.schema.json` (PRD
  §3.3), `scripts/poc_acceptance_receipt.py` with two validation levels
  (`campaign`: every S4.6 item, where step 17 (front door) is required only
  when the contract records `public_exposure: true`; `complete`: plus the
  S4.8 restore item with its measured RPO and RTO against D-14, the S4.7
  P-1 item and the S4.17 scheduled-drift items (a clean scheduled TEST run
  and a PROD record after the flip; R6-m11, R8-m1)),
  `tests/unit/test_poc_acceptance_receipt.py`, and the
  offline two-gate rewrite of `tests/unit/test_workload_phase_hard_stop.py`
  (gate 1, 2a, 2b; AD-21; gate 2b also checks the S4.17 story marker, which
  defines a check and adds no code dependency on S4.17). The README text and the phase flip stay in the
  S4.6 step-1 PR.
- **Scheduled-drift result record (R7-m1, R8-m1).** This story also owns
  `schemas/poc-workload-scheduled-drift-result-v1.schema.json`, the record
  that S4.17 emits: `stack`, `status` ∈ {`checked`, `before-acceptance`,
  `registry-phase`}, the captured checkpoint sha256 (`null` for
  `registry-phase`, whose run captures no checkpoint; pre-commit audit),
  the latest success receipt's ID and checkpoint sha256 (`null` only for
  `before-acceptance` when the stack has no success receipt yet, and
  always for `registry-phase`), the accepted receipt's ID (required for `checked`,
  absent otherwise), the scheduled run ID and attempt and the installed
  `main` SHA. `registry-phase` is the record of a run whose installed
  `main` contract for the stack has `phase: registry`: no drift check ran
  (R8-m1). The acceptance receipt's S4.17 items (PRD §3.3) carry the
  uploaded artifact's numeric `artifact_id` and its `artifact_sha256`
  (the sha256 of the uploaded `record.json`), next to the run link
  (R8-M1). The `complete` level (and gate 2b) requires **two** S4.17
  items: (1) the TEST item with `status: checked`, a checkpoint sha256
  equal to the bound success receipt's, and a run link; and (2) a PROD
  item from a scheduled run after the S4.7 PR that first set
  `poc-prod.json` `phase: workload`, with `status: before-acceptance` or
  `checked` (either status exists only when the installed `poc-prod.json`
  had `phase: workload`, so the record itself proves the run followed the
  flip; R8-m1). `registry-phase`, any other status, a missing
  `artifact_id` or `artifact_sha256`, or a PROD item with `stack: test`
  is refused. S4.15 owns the schema so that the validator and the
  emitter share one definition without a forward dependency on S4.17.
- **Hard stop for `poc-prod.json` (R7-m4).** The rewritten hard-stop test
  also reads `specs/poc/poc-prod.json` when it exists, validated by the
  S4.14 PROD schema: `phase: registry` (or no file) always passes;
  `phase: workload` passes only when the installed `poc-test.json`
  satisfies gate 2a (`admission.prod: "preview"`) or gate 2b
  (`admission.prod: true`) with all their conditions. Offline fixtures
  cover each case; the test does not need the committed file (XP-14).
- **Governance (m14):** the hard-stop test pins the README hard stop, so its
  rewrite is a governance change. The S4.15 PR needs an `APPROVED` review by
  `@Kravalg` specifically (a `@dmytrocraft` CODEOWNERS approval alone does
  not count), recorded with the PR number in the acceptance receipt, and
  the rewritten test must still pass with the installed `phase: registry`
  contract (the registry branch is unchanged). Without that approval, the
  rewrite moves into the Kravalg-approved S4.6 step-1 PR instead.

**Acceptance criteria:**

- The PRD FR-31 rows and §3.3.
- **N1:** a placeholder link, an all-zero hash or an equal requester and
  approver is refused.
- **N2:** a `complete` validation without the restore, P-1 or S4.17
  scheduled-drift item is refused; so is one whose TEST S4.17 item has
  `status: before-acceptance`, a checkpoint sha256 different from its
  bound success receipt, or no accepted receipt ID (R7-m1); one without
  the PROD S4.17 item, or whose PROD item has `status: registry-phase`;
  and one whose S4.17 item lacks `artifact_id` or `artifact_sha256`
  (R8-M1, R8-m1).
- **N3 (R7-m4):** a `poc-prod.json` fixture with `phase: workload` while
  `admission.prod` is `false` fails the hard-stop test; with
  `admission.prod: "preview"` and a missing gate-2a condition it fails
  too.
- **B:** a `campaign`-valid receipt is accepted at gate 2a only with the
  restore item; the rewritten hard-stop test passes on the installed
  `phase: registry` contract, with no `poc-prod.json` and with a
  `phase: registry` `poc-prod.json` fixture.
- **B2 (R8-m1, pre-commit audit):** a `registry-phase` record with a
  `null` captured checkpoint and `null` receipt fields validates against
  the result schema and is refused as either gate-2b item; a
  `registry-phase` record with a non-null captured checkpoint, or a
  `checked` or `before-acceptance` record with a `null` one, fails the
  schema.

### S4.16 (USI): TEST exercise workflow

- **Chains:** independent new files.
- **Depends on:** S5.23.
- **Scope:** `.github/workflows/test-exercise.yml` (main only, environment
  `test-exercise`, role `GitHubCiExercise-user-service-infrastructure-test`)
  and `scripts/poc_test_exercise.py` with sanitized subcommands: `rotate`
  (`RotateSecret` on a named workload secret), `denied-read` (attempts
  `GetSecretValue` and `PutSecretValue` and expects `AccessDenied`; never
  prints a value; the resource-policy proof itself is the preview role's
  `SimulateCustomPolicy` run, because the exercise role has no identity
  allow), `alarm` (`sqs:SendMessage` of an inert marker to one DLQ only,
  which no worker consumes; `cloudwatch:SetAlarmState` on one workload
  alarm or on a scaling policy's alarm to exercise FR-11 and FR-12), `flow-log-review`
  (reads flow-log objects and reports REJECT counts by destination, never
  raw records), `cloudtrail` (`LookupEvents` metadata for V-21 and the
  §3.2a evidence), `log-counts` (Logs Insights counts for NFR-05) and the
  optional `load` (drives requests through the AGI TEST route at the
  recorded rate, only when S5.16 exists).

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
    S4.10, S4.11, S4.9, S4.2, S4.3, S4.12, S4.13, S4.14, S4.15, S4.16;
  - US merged and published: S5.8, S5.9, S5.10, S5.11, S5.12, S5.13, S5.14;
  - BI applied: S5.1, S5.2, S5.17, S5.4, S5.3, S5.23, S5.7, S5.18a;
  - USI repository controls applied (admin): S5.21, S5.22;
  - decisions resolved (explicit, dated 2026-09-30, `decisions.md` and PRD
    §6): D-1, D-2 (TEST), D-4, D-5, D-6, D-7 — all resolved;
  - XP-6 (subscription endpoint) and XP-7 (profile) present;
  - XP-9 (completed registry proof and receipt), XP-10 (gateway ACM
    certificate and SSM publication), XP-11 (bootstrap #219 grants), XP-12
    (authenticated image publication), XP-13 (SES prerequisites) present
    (R4-M10);
  - the R-02 metadata observation receipt.
- **No scheduled workload drift during the campaign (R8-n2).** This is a
  consequence of D-6's two-gate order, recorded here and not a new risk
  acceptance: the gate-1 flip makes the baseline scheduled drift skip
  stack `test` (S4.13), and S4.17 (ordered after this campaign; a gate-2b
  precondition, as revision 6 ordered) is not merged yet. From the flip
  until S4.17 merges, the TEST workload stack gets drift checks only from
  `test_workload_drift` after each post-acceptance apply (step 14), not
  nightly. The registry resources of the stack are outside the baseline
  program either way (the registry owner's recorded case, S4.13). No
  PROD workload exists in this window, and PROD is never admitted without
  S4.17 (AD-21).
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
     `test-exercise` and `prod-recovery` each list reviewers = [Kravalg]
     only, `prevent_self_review` true, no admin bypass (S5.21, verified by
     USI `configure_github_repository_controls.py` verify mode);
     `governance-evidence` equals the evidence payload (reviewer-less,
     main-only; USI `scripts/_github_evidence_environment.py`); the ruleset
     requires `abandon-manifest-approval` with its pinned issuer (S5.22).
     STOP: not approved, or any environment or the ruleset differs.
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
       central metadata, `workload_step: 2`,
       `workload_operation: {mode: step2}`; Kravalg-approved. STOP: not
       approved.
  6. **S5.5 bootstrap job** run; it reads the managed secret through the
     `secretsmanager` endpoint's `rds!cluster-*` statement (FR-17). STOP:
     user not created → escalate.
     - **6b. Start-entry PR (audit):** a small Kravalg-approved contract PR
       appends the single `scaling.starts` entry `{seq: 1, at}`, with `at`
       planned for + 60 to + 120 min after the step-7 replay admission,
       right before the step-7 request. If the window is missed, a new PR
       moves the uncreated entry to `scaling.consumed` and appends the next
       `seq` (AD-10). STOP: not approved.
  7. **Step-2 saved-plan apply** (mode `step2`, anchored on the step-1
     success receipt; S4.9 create-only admission). The start actions fire at
     the `at` time of the `seq: 1` start entry (V-23 a and b). Then the step-2 health
     observation in the separate `test_workload_observation` job (AD-18
     item 4, m13): V-1 (MONGODB-AWS), V-2 (Redis IAM client), V-14 and V-20
     (image pull through endpoints), V-25 (logs delivered to the
     CMK-encrypted groups), FR-08 and FR-10 metadata, FR-06
     login/JWT/2FA, timing (FR-24). STOP: health fails → `rollback-zero`
     saved plan; V-1 failure → user decision; V-2 failure → US fix; V-14,
     V-20 → reviewed pin fix via `policy-update`; V-25 → AD-15a fallback
     row. These STOP plans run before 7b, so their `workload_route` is
     `pre-acceptance` (derived from the receipt lineage, R7-m5): no
     `test_workload_drift` job runs for them and the run does not go red
     for a missing accepted receipt. The step PR stays open until
     `test_workload_acceptance` finishes: a merge or close during the
     observation wait fails the post-wait `admit` before credentials
     (R7-m7), and a Pulumi lock held for the whole observation window
     fails with `workload-observation-lock-timeout` (R7-m8); both are a
     STOP at this step, and the next admitted start plan repeats the
     observation (AD-24). An acceptance refused because another receipt
     became the latest (audit F6) is the same STOP.
     - **7a. TEST state metadata scan** again after step 2 (NFR-01). STOP
       as in 4a.
     - **7b. Accepted-workload receipt** written and authenticated by the
       first passing health observation (FR-35, S4.13), published by
       `test_workload_acceptance` from the observation artifact and its
       checkpoint (R6-m3); V-23 (c) recorded
       (fired actions listed or not). STOP: no passing observation → stays
       at 7; AWS removed a fired action → STOP **before the next apply of
       any mode** (m12), until the `scaling.consumed` contract PR and the
       AD-23 entry land.
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
      (`denied-read`, FR-07) with the S2.5 alarms, and the preview role's
      `SimulateCustomPolicy` run proving the live `SecretPolicy` denies a
      caller that has an identity allow; one event per PRD §3.2a
      row (the allow-listed caller does not alarm, a different caller does);
      SES mail sent (FR-03, V-12). STOP: a delivery over 300 s, a missing
      alarm, or an alarm from an allow-listed caller → S2.4/S2.5 fix.
  12. **Scaling and network:** FR-11 web scale-out and FR-12 worker
      scale-out, each exercised by setting its scaling policy's alarm
      (`alarm` exercise; no marker message reaches a consumed queue),
      FR-14c scheduled scale-down and restore
      observed, FR-15 object delivered with the runtime CMK (V-16), FR-16
      describe, FR-18 `flow-log-review` against
      `docs/poc-egress-inventory.md`, V-11 metric observed. STOP (m12): a
      `REJECT` to a destination missing from the inventory, or a check
      failing because of egress → reviewed inventory and SG change; V-16
      delivery failure → key or bucket policy fix. Fallback for V-11: drop
      the informational alarm.
  13. **Resume rehearsal** (S4.3, FR-21 resume, NFR-09) with an induced
      failure (FR-20): the run of an admitted `rollback-zero` start plan
      (the `<svc>-start-2` entry, no capacity change) is cancelled after the
      apply starts. A cancellation kills the host too, so no failed receipt
      is expected (audit). Then `export` through the private hash-only
      reader (R6-m8; the checkpoint still holds pending operations and the
      lock), which writes the export receipt carrying the installed
      `workload_operation`, unless a failed receipt was published;
      `release-lock` (checkpoint unchanged), `clear-pending` (writes the
      export receipt with `cause: clear-pending` linked to the failed or
      export receipt, R5-M2) and `resume` from that receipt, finishing the
      start-plan operation (m11); the resume PR's contract names
      `resumes: {mode: rollback-zero, phase: start}` (R6-m7).
      If the new start action's `at()` is outside the window by then, a
      contract PR moves the uncreated `start-2` entry to `scaling.consumed`
      and appends `start-3` (AD-10). STOP: resume refused or failed →
      escalate; no further step until the stack is clean.
  14. **Clean drift** (FR-32, V-13): the `test_workload_drift` job (R6-M1)
      of the step-13 `resume` run, which follows step 12's scaling (moved
      `desiredCount`) and the schedules (moved min/max). It runs the S4.13
      path (worker → runner → plan-plus-gate dispatch → `validate_drift`;
      R6-m4) under the **preview** role, admitted by the accepted receipt
      and the latest success receipt (FR-35). This is the
      gate-2 clean-drift evidence; each later admitted post-acceptance apply
      repeats it. STOP: unlisted drift → investigate, no list widening.
  15. **Rollback (first deployment, AD-19):** `rollback-zero` stop plan →
      its `test_workload_observation` job records running = desired = 0 and
      `test_workload_acceptance` publishes the stop observation (R6-m6) →
      hold plan (contract flag `scaling.scheduled_scaling_suspended: true`,
      admitted only with that stop observation; R6-m7) → the next morning
      action does not restart them (V-23 d) → start plan (flag `false`, a
      new start entry) → healthy again; a release-rollback request is refused because no prior accepted
      release exists (FR-30 N). STOP: the restart is unhealthy → escalate
      with the services at 0.
  16. **FR-25 worker healthcheck, FR-26 non-root** observed. STOP: a root
      `User` or an unhealthy worker → US or S3.7 fix.
  17. **Front door (FR-28, V-10):** AGI TEST route through VPC link V2 → ALB
      and WAF sampled requests; optionally the `load` exercise through the
      route. Runs only when S5.16 has merged. Fallback: reviewed NLB
      variant. STOP: no route → AGI fix. Required before any public exposure
      and before gate 2 if PROD is public; otherwise the receipt records it
      as not applicable (S4.15).
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
      variant; `RestoreSecret` where needed; import receipt) →
      `rebuild-first` (S4.2) creates the rest of step 1 → step-1 receipt → XP-8 refresh (the new managed-secret ARN; BI re-attaches
      both Lambdas and re-grants the exact ARNs) and the 5b contract PR
      (every earlier `scaling` entry moved to `scaling.consumed`, because
      the abandon deleted those actions; AD-10 D-12) →
      S5.5 re-run → the 6b start-entry PR (one new `starts` entry) → step 2 (`step2`, rebuild variant) → health observation →
      accepted receipt → clean drift (the post-apply drift of the next
      post-acceptance apply, a `rollback-zero` start plan with a new entry and
      no capacity change, as in step 13).
      STOP rules as in steps 4–7 and 14.
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
  - **R-1 (R6-m10):** a point-in-time restore of the rebuilt TEST cluster
    `user-service-infrastructure-test-docdb`
    (`RestoreDBClusterToPointInTime` with `UseLatestRestorableTime: true`)
    to `<stack>-docdb-restore-rehearsal` under the S5.18a operator role,
    with `ModifyDBCluster` to a managed password (V-22). The source
    cluster's `LatestRestorableTime` is read (`DescribeDBClusters`)
    immediately before the request, and the CloudTrail
    `RestoreDBClusterToPointInTime` event (metadata only) confirms
    `useLatestRestorableTime: true`; that time is the achieved recovery
    point. The S5.18b reader (VPC-attached after XP-8) records the
    document-count sample. Then the temporary cluster is deleted;
  - **recovery targets (user decision D-14, dated 2026-09-30; architecture
    AD-19; R6-m1):** RPO ≤ 1 hour, recorded as the request time minus the
    achieved recovery point (≤ 3600 s), and RTO ≤ 24 hours, from the
    restore request to the reader's document-count sample;
  - the restore item, with the measured RPO and RTO, is appended to the
    acceptance receipt.
- **Depends on:** S4.6, S5.18a and S5.18b.

**Acceptance criteria:** the PRD FR-30 rows. **N:** a restore item without
the measured RPO and RTO, or without the point-in-time restore evidence
(`UseLatestRestorableTime` and the achieved recovery point), is refused by
the S4.15 validator. **B:** an RTO of exactly 24 hours and an RPO of exactly
3600 s pass; 3601 s fails. **STOP:** V-22 denial → BI grant fix; the
temporary cluster is deleted before a re-run. A measured RPO or RTO above
its D-14 target → STOP at gate 2a for a new user decision (accept the
measured value or change the design); a default never relaxes D-14.

### S4.17 (USI): Scheduled workload drift for the workload stacks (gate-2b precondition)

- **Why (R6-m11):** S4.13 excludes workload-phase stacks from the baseline
  scheduled drift (`workload-drift-routed-to-runner`). Without this story a
  PROD workload stack would have no scheduled drift detection. The user
  has not accepted that risk, so no risk acceptance is recorded, and gate
  2b requires this story (PRD FR-31, architecture AD-21).
- **Chains:** C-runner after S4.14; ordered after XP-14 (row 48), XP-15
  and XP-16 (row 49) and the BI amendment S5.24 (row 50); this story is
  row 51, and S4.7 (row 52) follows it in C-runner (R8-m7).
- **Depends on:** S4.11 (the receipt library, including the projection
  inputs of a success receipt), S4.13 (the drift gate and
  `validate_drift`), S4.14 (the stack → contract mapping, the PROD schema,
  the PROD path and its stack-aware provider-identity binding), S4.15
  (the scheduled-drift result schema and the gate-2b rule), S5.17 and
  S5.24 (the Drift-role read set), XP-14 (the observer's PROD coordinates
  and the committed `specs/poc/poc-prod.json`), and XP-15 and XP-16 (the
  PROD certificate parameter and boundary path that the PROD capability
  reads use).
- **First case (R7-m9, R8-m3):** the story checks that the S5.24 read
  inventory (row 50) covers every AWS call the scheduled path makes,
  derived from the code, not from a summary: the state bucket, KMS key
  and checkpoint (observer); the program refresh reads, including the
  eleven registry resources (ECR repositories, the SES identity and the
  Route53 DKIM records) that the refresh also reads; the registry-row
  checks of the capture (`ecr:DescribeRepositories` through
  `scripts/poc_registry_runner.py` `ecr_read`, lines 185-199;
  `sesv2 get-email-identity`, `route53 get-hosted-zone` and
  `route53 list-resource-record-sets` through
  `scripts/poc_mail_prerequisite.py`, lines 301-310 and 389-424, as
  `scripts/poc_scheduled_registry_drift.py` lines 122-129 already does
  under the Drift identity); and the image, capability and certificate
  checks. S5.24 is unconditional because the Drift role holds none of the
  IAM, ECR image, SSM or ACM reads (the round-7 request for a conditional
  row "like S5.6" is kept in position, before this story, but its
  condition is always true, and an inventory that lived here would be a
  forward trigger from row 51 to row 50). A call missing from the
  inventory stops this story until a reviewed S5.24 amendment lands. The
  receipts are read from GitHub deployments and statuses, not AWS.
- **Isolated launch (R7-M2).** The scheduled path uses the same isolated
  container as the PR jobs and never bypasses it: the materializer's
  `_worker()` (`scripts/poc_workload_materializer.py` lines 137-143)
  requires euid 0, pid 1 and a read-only `/` and `/trusted`, with no local
  bypass, and the runner requires `ServiceTransport`
  (`scripts/poc_workload_runner.py` lines 155-157,
  `workload-isolated-transport-required`). Today the only isolated launch
  is PR-bound: host `recheck` (`scripts/service_execution_host.py` lines
  137-151) reads the PR request and its review, and worker `admit`
  (`scripts/service_execution_worker.py` lines 34-53) does the same. This
  story adds a scheduled launch:
  - **host:** `JOBS` gains `scheduled_test_workload_drift` and
    `scheduled_prod_workload_drift` with host operation `scheduled-drift`,
    which the observer already maps to the Drift role
    (`scripts/poc_backend_observer.py` line 175, `AWS_DRIFT_ROLE_ARN`).
    For these two jobs, `recheck` and `execute` verify scheduled-main
    provenance instead of a PR request, with the pattern of
    `scripts/poc_scheduled_registry_drift.py` `_context` and
    `verify_provenance` (lines 49-101: event `schedule`, `refs/heads/main`,
    run attempt 1, the `scheduled-drift.yml` workflow ref,
    `GITHUB_SHA == GITHUB_WORKFLOW_SHA`, and the run and `main` ref read
    back), and never call `preflight.read_request`,
    `revalidate_requester` or `verify_reviewed_source`. The container gets
    no `REQUEST_*`, `EXPECTED_BASE_SHA` or `POC_SOURCE_*` variable for
    them. Every PR job keeps today's `recheck`. **Result copy-out
    (R8-M1):** today the host copies out only for `_preview` jobs (lines
    214-219). For the two scheduled jobs, after the worker container
    exits 0, `execute` copies `/public/workload-drift-result/record.json`
    to the fixed path `.trusted/.artifacts/workload-drift-result/record.json`
    (it requires the target not to exist, as the `_preview` copy does);
    the copy is a no-op when the file is absent, and a non-zero container
    status raises before any copy, as today;
  - **worker:** `JOBS` gains the two jobs as (`test`, `scheduled-drift`)
    and (`prod`, `scheduled-drift`). `admit` verifies the same
    scheduled-main provenance for them, with no PR request; `execute`
    routes them to `scripts/poc_scheduled_workload_drift.py` and never to
    `_test` (lines 82-103), which reads the PR source artifact. The
    `before_program` recheck repeats the provenance check. **Result
    publication (R8-M1):** today the worker copies to `/public` only for
    `plan` (lines 129-132). The scheduled route copies the script's
    result record to `/public/workload-drift-result/record.json` after the
    script returns 0 and the final provenance recheck passes; a non-zero
    status copies nothing;
  - **workflow:** `.github/workflows/scheduled-drift.yml` gains
    `scheduled_test_workload_drift` and `scheduled_prod_workload_drift`
    (schedule and `main` only; environments `test-drift` and `prod-drift`;
    the Drift role; the stack's
    `pulumi-state-${{ github.repository }}-<env>-<env>` concurrency group;
    no `needs`; job permissions exactly `contents: read`,
    `actions: read` (the provenance check reads
    `GET /actions/runs/{id}`, `scripts/poc_scheduled_registry_drift.py`
    line 78), `deployments: read` (the S4.11 receipt lookups) and
    `id-token: write`; job env `GH_TOKEN: ${{ github.token }}`, because
    `host.execute` requires it, `scripts/service_execution_host.py`
    line 158). Their steps, in order: check out `.trusted` at
    `github.sha` without persisted credentials;
    `./.trusted/.github/actions/setup-service-execution` (which runs host
    `prepare` and `build` from installed `main`); host `recheck`;
    `load-aws-ci-env` (Drift keys only); host `recheck`;
    `configure-aws-credentials` with the Drift role and
    `role-session-name: gha-scheduled-test-drift-${{ github.run_id }}`
    (TEST) or `gha-scheduled-prod-drift-${{ github.run_id }}` (PROD)
    (R8-n1; the names the observer's `_caller` checks,
    `scripts/poc_backend_observer.py` lines 219-223, and that the
    baseline jobs already use, `scheduled-drift.yml` lines 76 and 139;
    the observer accepts the PROD name once XP-14 makes `_caller`
    stack-aware); host `execute`; and **exactly one upload step directly
    after it (R8-M1):**
    `actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02`
    (the SHA every upload in `self-deploy.yml` pins, lines 131, 268, 278
    and 651) with `name: poc-workload-scheduled-drift-<env>-${{ github.run_id }}-${{ github.run_attempt }}`,
    `path: .trusted/.artifacts/workload-drift-result/record.json`,
    `if-no-files-found: error`, `overwrite: false` and
    `retention-days: 7` (the retention of every upload in `self-deploy.yml`,
    `self-deploy.yml` lines 137, 275, 285 and 657; so a record is linked
    into the acceptance receipt within seven days, or a later nightly run
    is linked instead). The upload has no `if`, so it runs only after a
    successful `execute`; a successful run that left no record fails the
    job at the upload. The baseline jobs keep excluding workload-phase
    stacks (S4.13, S4.14).
  - **enablement is data-driven (R8-m1).** Both jobs exist and run
    nightly from this story's merge; no later PR enables or disables a
    job. Each run reads the installed `main` contract of its stack (the
    AD-04 mapping, `git show <GITHUB_SHA>:<path>` in the trusted
    checkout, as `scripts/poc_scheduled_registry_drift.py` lines 104-113
    does). On `phase: registry` it takes no Drift-role read beyond the
    provenance and contract reads, writes a `status: registry-phase`
    record (S4.15 schema), emits `::notice::workload-drift-registry-phase`
    and exits 0: the baseline scheduled drift still covers that stack
    (S4.14 B2), and gate 2b never counts this record. On
    `phase: workload` it runs the checks below. A missing contract file
    exits non-zero (`workload-drift-contract-missing`); XP-14 commits
    `poc-prod.json` before this story (row 48). So the PROD job starts
    checking on the first night after the gate-2a PR (S4.7) that first
    sets `poc-prod.json` `phase: workload`, the same PR that removes
    `prod` from the baseline, and no night leaves the `prod` stack
    uncovered.
- **Scope:**
  - `scripts/poc_scheduled_workload_drift.py`, running only inside the
    worker container (it calls `materializer._worker()` before any
    materialization). It looks up, through the S4.11 library, the
    authenticated latest success receipt and the accepted receipt of the
    stack's lineage;
  - **installed program must equal the applied base (R8-m4):** the
    program that renders the projection is imported from installed
    `main` (`scripts/poc_workload_phase_entrypoint.py` lines 194-208:
    `/trusted/scripts` and `/trusted/pulumi`), and the old contract is
    validated against the installed schema
    (`poc_contract._validate_document`, entrypoint line 101). So before
    any projection the script compares the program trees that the latest
    success receipt records (the git object IDs of `scripts`, `pulumi`,
    `policy`, `schemas`, `pyproject.toml` and `uv.lock`; S1.1, S4.11)
    with the same object IDs of its installed checkout; any difference
    fails with the distinct reason
    `workload-drift-installed-program-changed`, writes no record and exits
    non-zero, so a code change is never reported as infrastructure drift
    and never passes silently. After building the projection and the
    generated files, it compares their digests with the receipt's
    projection digest and generated-files digest (AD-24); a projection
    difference fails with `workload-drift-projection-binding`, a
    generated-files difference with
    `workload-drift-installed-program-changed`;
  - **applied contract, not the current file (audit):**
    `project_workload_phase` requires the contract digest to equal
    `SourceAdmission.contract_sha256`
    (`scripts/poc_workload_phase_entrypoint.py` line 104). The script
    therefore reads the contract that the latest success receipt applied,
    as the source adapter does for a PR run
    (`scripts/poc_phase_source_adapter.py` lines 239-245: the stack's
    contract file (AD-04 mapping) at the recorded `head_sha`, whose blob
    must equal the recorded `blob_sha`). It requires that blob to equal the
    receipt's `SourceAdmission.blob_sha` and its digest to equal the
    receipt's contract digest; otherwise it fails with
    `workload-drift-contract-binding`. The current file on `main` is used
    only for the phase decision above, never for the projection, so an
    operation PR that is merged but not yet applied does not change the
    check;
  - **where each projection field comes from (R7-M2, R8-m4):** the
    projection is built only from the latest success receipt: the
    `SourceAdmission` facts, the applied contract (read and bound as
    above), the full image rows (`uri`, `manifest_media_type`,
    `config_digest`, `config_size`, `platform`; entrypoint lines 52-93)
    and the certificate observation
    `{parameter_arn, parameter_version, certificate_arn}` (capabilities
    line 277), or `null`. Fresh Drift-role reads are **comparisons, never
    projection inputs**: `images.inspect_images(contract)` must return rows
    equal to the receipt's rows; `capabilities.inspect_capabilities(contract)`
    (role reads, the execution-role pull simulation and the certificate
    parameter and certificate reads) must return a certificate
    observation equal to the receipt's; the checkpoint captured with
    `capture_scheduled_backend` must equal the latest success receipt's;
    and the refresh plan is the drift observation itself. A difference in
    an image row, the certificate observation or the checkpoint fails
    with the item named;
  - **scheduled gate with no PR call (audit, R8-A4):** the runner's path
    is PR-bound: `_gate` (runner lines 51-75) calls `registry._review`,
    `admission.observe_workload(source, …)` and
    `revalidate_requester(source["request"])` (line 72); `_capture`
    reaches `capture_backend` and `_target`, which reads
    `source["request"]` (observer line 183); and `execute` calls
    `registry._trusted_root()`, which requires
    `GITHUB_EVENT_NAME == "repository_dispatch"`
    (`scripts/poc_source_artifact.py` line 66). So the script has its own
    gate, modelled on `poc_scheduled_registry_drift._gate` (line 136 on):
    it re-verifies the scheduled provenance, captures with
    `backend.capture_scheduled_backend` (observer lines 428-435, Drift
    identity), requires the checkpoint to equal the latest success
    receipt's, runs the registry-row checks of the S4.11 workload-aware
    capture for the job's stack (the registry graph, ECR and SES/DKIM
    inventory; S4.14 capture row), checks the plan bytes, binds the
    provider identity with **S4.14's stack-aware binding** in
    `poc_workload_runner.py` (the registry `_binding`,
    `scripts/poc_registry_runner.py` lines 266-283, stays TEST-only and is
    never called here), requires the job's stack (not the registry
    gate's `stack == "test"`, line 138), and runs `validate_drift` against
    that receipt's checkpoint. It calls `images.inspect_images(contract)`
    and `capabilities.inspect_capabilities(contract)` directly (each takes
    only the contract) and none of `_review`, `observe_workload`,
    `revalidate_requester`, `capture_backend` or `_trusted_root`. It
    reuses the materializer, `run_pulumi_command._dispatch_command("plan", …)`
    and `validate_drift` unchanged. The saved plan stays in the worker's
    private area and is discarded; nothing is applied. It exits non-zero,
    with the drifted field named, on any change outside AD-23 (a protected
    replace or delete fails closed with the safe-preview message, as in
    S4.13);
  - **before acceptance (R7-m1, audit):** when the lineage has a success
    receipt but no accepted receipt, the script runs the same drift check
    against the latest success receipt and fails on drift. This is a
    read-only diagnostic; AD-24's `drift` row governs the PR `drift`
    command, which opens releases, not this check. When a `phase: workload`
    stack has no workload success receipt yet (only the registry
    resources, or only failed or export receipts), no drift check runs:
    the registry resources are the registry owner's recorded case
    (S4.13), which the baseline program does not cover either (the
    failed-or-export case is a recorded residual, `readiness.md`, R8-n4);
  - **result record (R7-m1, R8-M1):** every run that exits 0 writes
    exactly one `poc-workload-scheduled-drift-result-v1` record (schema
    owned by S4.15), which the worker and the host copy out and the
    upload step publishes: `status: checked` after a passing drift check
    with an accepted receipt, bound to the captured checkpoint sha256,
    the latest success receipt and the accepted receipt; `status:
    before-acceptance` when the lineage has no accepted receipt yet, bound
    to the captured checkpoint sha256 and the latest success receipt (its
    ID is `null` only when the stack has no success receipt); or `status:
    registry-phase` (above). A `before-acceptance` run exits 0 only when
    its drift check passed or no success receipt exists, and it emits a
    GitHub warning annotation (`::warning::workload-drift-before-acceptance`),
    so it is visible in the run and never counts as a clean TEST run: the
    S4.15 `complete` level accepts a TEST item only with `checked`, and a
    PROD item with `before-acceptance` or `checked` from a run after the
    flip. Any run that fails (drift, a binding or program difference, a
    denied read, a lineage lookup error including an incomplete
    pagination) exits non-zero and publishes no record; after the first
    accepted receipt, a missing or stale latest receipt fails;
  - **docs (NFR-10, R8-m5):** `specs/poc/README.md` lines 52-57 (the
    candidate `poc_scheduled_registry_drift.py` is not connected; "the
    TEST-only launcher does not accept scheduled jobs") state that the
    launcher accepts exactly the two scheduled workload jobs, with
    scheduled-main provenance and no PR input, that the registry
    diagnostic stays unconnected, and that a result record cannot
    authorize a transition; this README change needs the story's
    `@Kravalg` approval; `docs/poc-workload-admission.md` line 10 names
    the scheduled workload drift for workload-phase stacks;
    `docs/ci-guardrails.md` line 147 gains the two workload jobs in the
    nightly table, and lines 170-181 state that the scheduled file now
    also runs the isolated service-execution container for the two
    workload jobs, still with read-only drift roles and no apply or
    promotion job;
  - **workflow-shape tests (guardrail change):**
    `tests/unit/test_poc_scheduled_registry_workflow.py`: line 1 (the
    module docstring "Schedule retains installed drift until an isolated
    diagnostic is admitted") says that the isolated workload diagnostic is
    now admitted for the two workload jobs only; line 19 and
    `tests/pulumi/test_ci_guardrails.py` line 177 (the closed scheduled job
    set) gain exactly the two new jobs; lines 22-46 (the baseline jobs,
    including the negatives at lines 40-46: no `service_execution_host`,
    no `setup-service-execution`, no `poc_scheduled_registry_drift`, no
    `client_payload`, no `head_sha`) stay for the two baseline jobs; a
    sibling test pins the two workload jobs: the schedule and `main`
    `if`, the environment, the concurrency group, the exact permissions
    and `GH_TOKEN` env above, `setup-service-execution`
    before any credential step, a host `recheck` immediately before each
    credential step with no `if` and no `continue-on-error`, the exact
    `role-session-name` of each job (R8-n1), exactly one host `execute`
    **followed only by the one upload step above** (its pinned action SHA,
    exact `name`, `path`, `if-no-files-found: error`, `overwrite: false`,
    `retention-days: 7`, and no `if` or `continue-on-error`; R8-M1), the
    Drift role only (no preview or apply key), no `make`, no `needs`, no
    `client_payload` and no `head_sha`. `tests/pulumi/test_ci_guardrails.py`
    lines 185-186 (no `needs.preflight` and no `client_payload` in the
    workflow) and the baseline loop at lines 191-243 stay; lines 347-353
    (the state-job set) gain the two jobs, and the predicate (lines
    341-345) needs no change because it already recognises the host
    `execute` launch. `tests/unit/test_service_execution_workflow.py`
    lines 9-13 (`CASES`) gain (`scheduled-drift`,
    `scheduled_test_workload_drift`) and (`scheduled-drift`,
    `scheduled_prod_workload_drift`);
  - **pinned host and worker assertions this story changes (R8-M1),**
    each with its new form; every PR-job assertion stays:
    - `tests/unit/test_service_execution_worker.py` lines 128-130, run
      over every `worker.JOBS` member: line 128
      (`calls[-3:] == ["execute", "admit", "admit"]`) stays for the PR
      jobs, and for the two scheduled jobs becomes
      `calls[-3:] == ["scheduled", "admit", "admit"]` (the scheduled script
      call, its `before_program` recheck and the final recheck, where
      `admit` is the scheduled-provenance check for these jobs), with no
      `execute` (the PR route, `registry.execute`) and no
      `load_verified_contract` call; line 129
      (`replay` only for `up-plan`) stays; line 130
      (`len(copied) == (2 if command == "plan" else 0)`) becomes
      `len(copied) == {"plan": 2, "scheduled-drift": 1}.get(command, 0)`,
      the scheduled copy targeting `/public/workload-drift-result`, so
      line 131 (every target's parent is `/public`) stays; a scheduled
      fixture whose script exits non-zero copies nothing;
    - `tests/unit/test_service_execution_host.py` lines 109-112 (the fake
      worker writes `/public` files only for `_preview` jobs) also write
      `workload-drift-result/record.json` for the two scheduled jobs, and
      lines 140-144 (the copy-out check) assert that record under
      `root / ".artifacts/workload-drift-result"` for them, next to
      S4.14's `destination = root` for every `_preview` job; a scheduled
      fixture with no record copies nothing and does not raise. Lines
      78-144 and 233-322 run the scheduled jobs with Drift-role
      fixtures, no request and scheduled provenance;
    The PR needs an `APPROVED` review by `@Kravalg` specifically, recorded
    like the round-5 m14 amendment.

**Acceptance criteria:**

- **P:** a scheduled fixture on a workload stack with an accepted receipt
  and a refresh that changes only AD-23 fields passes and writes a
  `checked` record bound to the captured checkpoint and both receipts;
  the host copies it to `.trusted/.artifacts/workload-drift-result/record.json`
  and the workflow fixture uploads it.
- **P2 (R7-M2):** the scheduled job launches through host `execute` into
  the worker container, and `_worker()` passes there.
- **N1:** a refresh fixture that changes an unlisted field fails with that
  field named.
- **N2:** a workload-phase stack whose lineage has an accepted receipt but
  whose latest receipt is missing or stale fails; it is never skipped
  silently.
- **N3:** a dispatch or PR trigger, or any PR input, is refused. **No
  scheduled path reads a PR request (R7-M2):** a fixture in which host
  `recheck`, worker `admit` or the script calls `preflight.read_request`,
  `revalidate_requester`, `verify_reviewed_source`, `registry._review`,
  `admission.observe_workload`, `backend.capture_backend`,
  `registry._binding` or `registry._trusted_root` for a scheduled job
  fails the test.
- **N8 (audit):** a contract read at the receipt's `head_sha` whose blob
  differs from the recorded `blob_sha`, or whose digest differs from the
  receipt's contract digest, fails with `workload-drift-contract-binding`;
  an installed `main` contract that differs because an operation PR is
  merged but not yet applied does not change the verdict.
- **N4 (R7-M2):** running the script outside the container (euid not 0,
  pid not 1, or a writable `/` or `/trusted`) fails with
  `workload-materializer-worker` or `workload-materializer-readonly`;
  there is no bypass flag or environment variable.
- **N5 (R7-m1):** a receipt lookup that fails, or whose deployment or
  status listing is incomplete, exits non-zero and writes no record.
- **N6 (R7-M2, R8-m4):** an image row, capability or certificate
  observation that differs from the latest success receipt's fails with
  the item named; a projection digest that differs from the receipt's
  fails with `workload-drift-projection-binding`.
- **N7 (R7-m9):** a denied Drift-role read fails the job; no read is
  skipped.
- **N9 (R8-M1):** a workflow fixture whose workload job lacks the upload,
  has a step after it, has an `if` or `continue-on-error` on it, uses
  another action SHA, or sets `if-no-files-found` to anything but
  `error` fails the sibling test; a job with another `role-session-name`
  fails it too (R8-n1).
- **B:** a stack with a success receipt but no accepted receipt runs the
  drift check, writes a `before-acceptance` record bound to the captured
  checkpoint sha256 and the latest success receipt, emits the warning
  annotation, exits 0 on a clean refresh and non-zero on an unlisted
  change; a `phase: workload` stack with no workload success receipt
  writes a `before-acceptance` record with a `null` receipt and exits 0
  with the warning; the S4.15 `complete` level refuses both as the TEST
  item.
- **B2 (R8-m1):** on a stack whose installed `main` contract has
  `phase: registry`, the job takes no Drift-role read beyond provenance
  and the contract, writes a `registry-phase` record, emits the notice
  and exits 0, and the upload publishes that record; S4.15 refuses it as
  either gate-2b item; the baseline scheduled jobs keep previewing that
  stack (S4.14 B2). A missing contract file exits non-zero.
- **B3 (R8-m4):** installed program trees or a generated-files digest
  that differ from the latest success receipt's (for example after a
  merged code change and before the next apply) fail with
  `workload-drift-installed-program-changed`, write no record and exit
  non-zero, before any projection or refresh; with equal trees the run
  proceeds.
- **Live:** a clean scheduled TEST run (`status: checked`), appended to
  the acceptance receipt before gate 2b. **Sequencing (R8-m4):** when any
  file in the program trees changed on `main` after the TEST workload
  stack's latest success receipt, a TEST release that re-applies the
  current accepted image digests (a no-op re-apply through the normal PR
  path, AD-24 release row) runs first, so the clean `checked` run is bound
  to the installed code. Both jobs exist from this story's merge; the
  PROD job starts checking on the first night after the gate-2a PR (S4.7)
  that first sets `poc-prod.json` `phase: workload`, and gate 2b requires
  a linked PROD `before-acceptance` or `checked` record from a scheduled
  run after that flip (S4.15, S4.7 N3; R8-m1).

### S4.7 (USI): Gate 2 (PROD admission) and the PROD plan

- **Chains:** C-runner after S4.17 (R8-m7: its host-test change below
  edits a C-runner file); C-contract after S4.6.
- **Scope:** gate 2a (`admission.prod: "preview"`), then gate 2b
  (`admission.prod: true`), and the PROD promotion plan: recovery
  environment `prod-recovery`, the S4.14 PROD path, PROD live acceptance.
- **PROD workload contract PRs (R7-m4).** This story owns every PROD
  workload contract PR: the `specs/poc/poc-prod.json` change from the
  XP-14 `phase: registry` file to `phase: workload`, its `workload_step`,
  `workload_operation`, `scaling`, `documentdb_secret_policy`,
  `drift.out_of_band_fields` and PROD `central` fields, each validated by
  the S4.14 PROD schema and each Kravalg-approved. The S4.15 hard-stop test
  refuses a `phase: workload` `poc-prod.json` unless `poc-test.json`
  satisfies gate 2a or 2b. The `admission.prod` PRs stay in
  `poc-test.json`. The S4.17 jobs are data-driven (R8-m1): the PROD job
  exists from S4.17's merge and writes `registry-phase` records until the
  gate-2a PR that first sets `phase: workload` in `poc-prod.json`; from
  the next night it checks the `prod` stack. That PR also removes `prod`
  from the baseline (S4.14), so there is no night on which neither the
  baseline nor S4.17 covers the `prod` stack.
- **Real-seam PROD test (R7-M1, audit).** Once XP-14's observer
  coordinates exist, this story adds the unstubbed PROD parametrization of
  `tests/unit/test_service_execution_host.py` lines 233-322 (host →
  worker → backend coordinates → native STS boundary), with the
  environment-dependent faults of S4.14; S4.14's PROD cases use checking
  stand-ins for the observer because XP-14 comes later (row 48). This is
  a rewrite of a pinned C-runner test, so the PR that adds it needs an
  `APPROVED` review by `@Kravalg` specifically, recorded with the PR
  number in the acceptance receipt like the round-5 m14 amendment (R8-m7).
- **Preconditions:**
  - S4.6, S4.8, S4.14, S5.6 (if triggered), S5.19, S5.20 merged and
    published (with S3.5-A already merged; D-2 PROD), D-3 resolved, S5.16
    with S4.6 step 17 evidence if PROD is publicly exposed, XP-14 (PROD
    registry), XP-15 (the PROD gateway certificate parameter, the PROD
    counterpart of XP-10) and XP-16 (the PROD permissions-boundary path,
    the PROD counterpart of XP-11, which
    `scripts/poc_workload_capabilities.py` line 111 pins for TEST), both
    gate-2a prerequisites (ordered row 49; R8-m6); S4.14 pins their
    TEST-analogous names as an assumption the owners confirm in the S4.14
    PR, row 49 makes them exist live under those names, and this story
    verifies them live (the PROD capability
    reads of `prod_preview` pass with the pinned names; a difference is a
    STOP before gate 2a); and a PROD live simulator run;
  - **S4.17 (R6-m11), before gate 2b:** merged, with two linked result
    records in the receipt, each with its run link, `artifact_id` and
    `artifact_sha256` (R8-M1): a clean scheduled TEST workload drift run
    (`status: checked`, R7-m1), and a PROD record with
    `status: before-acceptance` or `checked` from a scheduled run after the
    gate-2a PR that first set `poc-prod.json` `phase: workload` (R8-m1). If
    any file in the program trees (S1.1) changed on `main` after the TEST
    workload stack's latest success receipt, a TEST release that re-applies
    the current accepted image digests (a no-op re-apply through the
    normal PR path, AD-24 release row) runs before that clean TEST run, so
    it does not fail with `workload-drift-installed-program-changed`
    (R8-m4). No risk acceptance replaces this;
  - **P-1 (m1), under gate 2a:** the PROD `plan` (`prod_preview` job, S4.14)
    shows the HTTPS target group and health check on 8443 (FR-19); its
    evidence is appended to the receipt. STOP: an HTTP target group or any
    admission refusal → fix before gate 2b.

**Acceptance criteria:**

- **P:** gate 2b is accepted with every gate-1 check passing and a
  `complete`-valid receipt, including P-1 and both S4.17 scheduled-drift
  items (TEST `checked`; PROD after the flip).
- **N1:** any gate-1 check failing is refused.
- **N2:** any missing receipt item or placeholder link is refused.
- **N3:** a PROD stack with an HTTP target group is refused; gate 2b
  without the TEST S4.17 item, or with a TEST item whose status is
  `before-acceptance`, is refused (R7-m1); gate 2b without a PROD S4.17
  record (`before-acceptance` or `checked`) from a scheduled run after the
  flip, or with only a `registry-phase` PROD record, is refused; an S4.17
  item without `artifact_id` or `artifact_sha256` is refused (R8-m1,
  R8-M1).
- **N4 (R7-m4):** a PROD workload contract PR that fails the S4.14 PROD
  schema, or a `phase: workload` `poc-prod.json` while `admission.prod`
  is `false`, is refused.
- **B:** PROD recovery grants must exist before the PROD apply.

## Epic 5: Cross-repo prerequisites

| Story | Repo | Deliverable | Key acceptance (P / N / B) |
| --- | --- | --- | --- |
| S5.8 | US | Merge #501 | Merged / the image command differs from the USI contract command → refused (FR-25) / healthcheck grace period covers supervisor start |
| S5.1 | BI | **Every central role, created first (M-3):** ECS execution and task roles, app-rotation, redeploy and bootstrap-job roles, the restore-operator and restore-reader roles (trust policy only; their grants land in S5.18a), and the TEST exercise role (trust only; grants in S5.23). Their ARNs are published in central metadata, which the S3.3 endpoint policy reads. Secret patterns `name-??????`, deterministic ARNs; task role SQS, SES, `elasticache:Connect` on the exact replication-group and user ARNs (D-1). **No KMS statements** (they land in S5.4 after the keys exist) and no bootstrap-job grant on the DocumentDB-managed secret (it lands in S5.5 after XP-8). XP-1: recover or re-author `d41c019`. | Simulator allows / out-of-scope and `GetSecretValue` on the task role denied / `iam:PassedToService` present |
| S5.2 | BI | Apply-role workload capability (N-11): ecs, ec2 (including `CreateFlowLogs` and endpoints; no `DeleteFlowLogs`), elasticache (including users and groups), docdb/rds, logs (`CreateLogDelivery`; `DeleteLogDelivery` belongs to the TEST recovery role), cloudwatch, application-autoscaling (`RegisterScalableTarget` including `SuspendedState`, `PutScalingPolicy`, `PutScheduledAction` on the two service resource IDs; no `DeleteScheduledAction`), elbv2, s3, secretsmanager (`CreateSecret`, `PutResourcePolicy`, `GetResourcePolicy`, `RotateSecret` with `secretsmanager:RotationLambdaARN` limited to the BI functions, tagging; **no delete action** — `DeleteResourcePolicy`, `CancelRotateSecret`, `DeleteSecret` stay with the TEST recovery role, because no admitted apply mode deletes), `lambda:InvokeFunction` on BI functions, events, sns. **Managed password (R4-M9, V-21, A-27):** `rds:CreateDBCluster` with `rds:ManageMasterUserPassword` = true; `secretsmanager:CreateSecret` and `TagResource` on `secret:rds!cluster-*`; `kms:DescribeKey` on `alias/aws/secretsmanager` (`kms:ResourceAliases`); `secretsmanager:DescribeSecret` on `secret:rds!cluster-*` (metadata only). The managed-secret `PutResourcePolicy`/`GetResourcePolicy` is granted on the exact XP-8 ARN in S5.5. **Runtime-CMK describe:** `kms:DescribeKey` with the AD-15a `kms:ViaService` set (added in S5.4 once the key ARN exists). **SLRs:** `iam:CreateServiceLinkedRole` only with `iam:AWSServiceName` ∈ {ecs, ecs.application-autoscaling, elasticache, rds, elasticloadbalancing}, or BI pre-creates them. **Attachment quota:** the capability fits within the role's managed-policy attachment quota and the 6144-character managed-policy size; the story records the count and sizes. `PassRole` limited to the ECS roles. `GetSecretValue`, `PutSecretValue`, `UpdateSecretVersionStage` and `GetFunction` denies stay. V-15, V-21 (docs). | Matrix allows / denies stay; `RotateSecret` with another function ARN denied; `CreateDBCluster` with `ManageMasterUserPassword` false denied; `CreateSecret` on a declared-name pattern other than the listed names denied / attachment count and sizes within quota |
| S5.17 | BI | **Preview and drift read capability (FR-33, B-2):** read-only grants for `GitHubCiPreview-…-{env}` and `GitHubCiDrift-…-{env}` on every workload resource type (ec2, ecs, docdb/rds describe, elasticache, logs, cloudwatch, application-autoscaling including scheduled actions, elbv2, wafv2, apigateway, events, sns, s3 configuration, secretsmanager metadata). **No KMS statement here** (m7): the KMS read lands in S5.4 on the exact key ARNs. **Simulation grant (m6):** the preview role gets `iam:SimulatePrincipalPolicy` and `iam:GetContextKeysForPrincipalPolicy` on the exact ARNs of the S4.6 step-3 role list only, and `iam:SimulateCustomPolicy` (read-only, no resource scope) for the step-11 resource-policy proof. Simulator-matrix regression for both roles. | Every workload read allowed / `GetSecretValue`, `GetFunction`, `kms:Decrypt`, every write, and `SimulatePrincipalPolicy` on a role outside the list denied / the existing registry-phase matrix is unchanged |
| S5.4 | BI | CMKs per D-4 (decided 2026-09-30): the runtime CMK (secrets, every workload log group, flow-log bucket, SNS topic), the JWT signing CMK (RSA_4096) and the 2FA CMK. Key policies follow the **per-key table architecture AD-15a** (principal, action, condition): no `root` `kms:*` statement; `logs.<region>.amazonaws.com` with `kms:EncryptionContext:aws:logs:arn`; `delivery.logs.amazonaws.com` with `aws:SourceAccount`/`aws:SourceArn`; cloudwatch and events for SNS; the ECS execution role `kms:Decrypt` with `kms:ViaService=secretsmanager.<region>.amazonaws.com`; the app-rotation role; the task role on the JWT and 2FA keys; the preview and drift roles' read (m7); the apply role's `DescribeKey` via logs, secretsmanager, sns and s3. Every named role already exists (S5.1, or the pre-existing preview, drift and apply roles). Then, in the same story and after the keys exist, the matching identity statements. CloudTrail read management events. | Grants only the AD-15a rows / no broad `kms:*`; a key policy naming a role absent from the role inventory fails the offline check; an execution-role `Decrypt` without `kms:ViaService` fails / JWT key-change procedure |
| S5.3 | BI | Functions using the S5.1 roles: app rotation + idempotent seed (no VPC), redeploy (no VPC, deterministic service ARNs), bootstrap-job function package (VPC attachment deferred to S5.5), their log groups created explicitly with `kms_key_id` = the runtime CMK (D-4), Lambda permissions (`aws:SourceAccount`), `RotationSucceeded` rule, allow-listed secret patterns (NFR-06). V-4 (docs). | Step unit tests / `testSecret` failure means no stage move; a function log group without the runtime CMK fails / seed on a secret with AWSCURRENT returns `noop`; seed output has no material |
| S5.7 | BI | **TEST recovery (D-7, decided 2026-09-30; unconditional):** the role `GitHubCiRecovery-user-service-infrastructure-test`, trusted only for OIDC `sub` `repo:VilnaCRM-Org/user-service-infrastructure:environment:test-recovery` on `main` (the `test-recovery` environment itself is configured by the USI repository controls, S5.21: Kravalg sole reviewer). Grants per architecture AD-16: state read and write, `s3:DeleteObject` on the state lock prefix (`.pulumi/locks/*`) only, state secrets-provider key use; `rds:ModifyDBCluster` on `cluster:user-service-infrastructure-test-docdb`; the per-type delete-action map `recovery/delete-actions.json` from S4.10 (pinned provider delete paths, drain and detach calls included; V-26), scoped to the TEST name patterns or `aws:ResourceTag/Project=user-service-infrastructure` + `Environment=test`; no S3 bucket delete, no object delete outside the lock prefix, no KMS key management; `secretsmanager:DeleteSecret` (`secretsmanager:RecoveryWindowInDays` ≥ 7, `secretsmanager:ForceDeleteWithoutRecovery` = false — **V-15**), `RestoreSecret`, `DescribeSecret`, `CancelRotateSecret`, `DeleteResourcePolicy` on the workload patterns and `rds!cluster-*`; the import read set (S5.17). TEST only. | Exactly the recovery set; each graph type's delete allowed on the TEST pattern / PR-head assumption denied; force delete denied; `s3:DeleteBucket` and a log-bucket `s3:DeleteObject` denied; the PROD account denied / recovery window 7 allowed, 6 denied |
| S5.18a | BI | **Restore-rehearsal grants (FR-30, M-9), before step 1:** on the S5.1 operator role, the architecture §2.1 grants (`RestoreDBClusterToPointInTime` with `UseLatestRestorableTime` on the source `cluster:user-service-infrastructure-test-docdb` and the rehearsal target, with the subnet-group and parameter-group resources, R6-m10; the achieved recovery point is the RPO evidence; `CreateDBInstance`; `ModifyDBCluster` with `rds:ManageMasterUserPassword`; `secretsmanager:CreateSecret`/`TagResource` on `rds!cluster-*`; `kms:DescribeKey` on `alias/aws/secretsmanager`; `kms:CreateGrant`/`Decrypt`/`DescribeKey` on the DocumentDB storage key via `rds.<region>.amazonaws.com`; describe and delete on `<stack>-docdb-restore-rehearsal` only; V-22 docs); on the S5.1 reader role, `GetSecretValue` on the temporary cluster's managed secret by tag condition (V-19) or a reviewed ephemeral exact-ARN grant; the reader package **without** VPC attachment. | Restore and read allowed for the rehearsal name / restore to any other name, a point-in-time restore from any other source cluster, delete of the real cluster, and the reader on the real cluster's secret denied / `ManageMasterUserPassword` false denied |
| S5.18b | BI (live) | **Restore-reader VPC attachment (R4-M7), after XP-8 (S4.6 step 5):** attach the S5.18a reader to the USI app subnets and bootstrap-job SG from the XP-8 metadata; detach before an abandon (S4.6 step 18), re-attach in the rebuild (step 20). | Reader reaches the temporary cluster port and the `secretsmanager` endpoint / attach refused without XP-8 metadata / detach leaves no ENI |
| S5.5 | BI (live) | XP-8 metadata PR; exact-ARN `GetSecretValue` grant for the bootstrap-job role (plus tag condition if V-19); exact-ARN `secretsmanager:PutResourcePolicy` and `GetResourcePolicy` for the USI apply role (step-2 managed-secret policy and `policy-update`); bootstrap-job VPC attachment; `$external` bootstrap job run, idempotent, with evidence. The `secretsmanager` endpoint needs no XP-8 change (`rds!cluster-*` statement, S3.3). Runs as S4.6 steps 5–6 and again in step 20. | User exists with `readWrite` on the app database only / unapproved run refused / re-run makes no change |
| S5.21 | USI (repository controls; admin apply by Kravalg) | **Kravalg-only environment approvals (m11, R4-M4, m3):** USI applies its own environments with its own scripts, not BI's: `scripts/configure_github_repository_controls.py` (lines 79-85 `ADDITIONAL_PROTECTED_ENVIRONMENTS` and `SERVICE_PROTECTED_ENVIRONMENTS`; apply loop lines 527-538) and `scripts/_github_repository_controls.py::protected_reviewer_environment_payload` (line 185; the same payload as BI debd88b lines 308-319): reviewers = [Kravalg's user ID] only, `prevent_self_review: true`, `can_admins_bypass: false`, main-only branch policy. `test-recovery`, `test-exercise` and `prod-recovery` join `ADDITIONAL_PROTECTED_ENVIRONMENTS` (so the apply, the main-branch policy loop and `_verify_applied_controls`, lines 256-311, cover them) and `SERVICE_PROTECTED_ENVIRONMENTS` (so the drift-only preservation check covers them); `test` and `prod` keep their current payloads. `governance-evidence` is not changed: it stays reviewer-less and main-only by design (USI `scripts/_github_evidence_environment.py`), so receipt publication stays unattended. Offline tests (`tests/unit/test_configure_repository_controls.py`) reuse `environment_prevents_self_review` and `environment_is_main_only` (`scripts/_github_environment_controls.py` lines 22 and 36). | Each payload equals the expected one, and the verification set lists all five / a second reviewer, `prevent_self_review` false, admin bypass, or one of the three new environments missing from the verification set fails / a non-main branch policy fails |
| S5.22 | USI (repository controls; admin apply by Kravalg) | **Required manifest approval check (R4-M4, m2, m3), after S4.3:** USI's own ruleset requires the status check `abandon-manifest-approval` (created by S4.3): it joins `REQUIRED_STATUS_CHECKS` (USI `scripts/_github_repository_controls.py` line 13). The ruleset's checks are branch-wide (only a `ref_name` condition), so the check succeeds on PRs that do not change `recovery/abandon-manifest.json` and enforces Kravalg's approval on PRs that do. **Own issuer-pinning code (m2):** today `required_status_checks_rule` (lines 46-60) and `_harden_status_check` (lines 64-78) pin only `Governance Promotion`; this story adds a pinned-context map so `abandon-manifest-approval` is emitted with `integration_id` = the GitHub Actions App ID, `_harden_status_check` sets it and refuses an existing entry with another issuer, and `ruleset_verification_blockers` (line 385) reports a missing or different issuer. | Required check present with the pinned issuer / a ruleset without it, or an entry without `integration_id` or with another App's ID (spoofing test), fails verification / other contexts and paths unaffected; the `Governance Promotion` pin is unchanged |
| S5.23 | BI | **TEST exercise role (R4 audit, live-action identities):** grants on the S5.1 role `GitHubCiExercise-user-service-infrastructure-test`, trusted only for OIDC `sub` `repo:VilnaCRM-Org/user-service-infrastructure:environment:test-exercise` on `main`: `secretsmanager:RotateSecret` on the declared patterns and `rds!cluster-*` (TEST), with `lambda:InvokeFunction` on the BI rotation function ARNs (V-6); `sqs:SendMessage` on the three DLQs only; `cloudwatch:SetAlarmState` on the workload alarms and the Application Auto Scaling policy alarms of the two services; `s3:GetObject`/`ListBucket` on the flow-log bucket plus the AD-15a runtime-key row (`kms:Decrypt` via S3); `cloudtrail:LookupEvents`; `logs:StartQuery`/`GetQueryResults` on the workload log groups. No `GetSecretValue`, `PutSecretValue` or write outside this list, so `denied-read` is refused. TEST account only. | Matrix allows exactly the list / `GetSecretValue`, `PutSecretValue` and PROD denied / PR-head assumption denied |
| S5.6 | BI (conditional) | `MaxSessionDuration` plus `role-duration-seconds` | Covers the measured time plus the 300 s margin / below-margin value refused / exactly at the margin accepted |
| S5.24 | BI (R7-m9, R8-m3; after XP-14, XP-15 and XP-16, before S4.17) | **Drift-role read inventory and grants for scheduled workload drift.** The story derives, from the existing modules that the S4.17 path calls (the observer, `poc_registry_runner.py` `ecr_read`, `poc_mail_prerequisite.py`, `poc_workload_images.py`, `poc_workload_capabilities.py` and the program refresh), every AWS call the Drift role `GitHubCiDrift-user-service-infrastructure-{env}` makes beyond the S5.17 set, and grants exactly those reads. **Registry rows and refresh (R8-m3):** the refresh also reads the eleven registry resources, and S4.17 runs the capture's registry-row checks: `ecr:DescribeRepositories` (`scripts/poc_registry_runner.py` lines 185-199), `ses:GetEmailIdentity`, `route53:GetHostedZone` and `route53:ListResourceRecordSets` (`scripts/poc_mail_prerequisite.py` lines 301-310 and 389-424; the calls `scripts/poc_scheduled_registry_drift.py` lines 122-129 already makes under the Drift identity), plus the refresh reads of those three resource types from the pinned `pulumi-aws` provider source (derived as S4.10 derives delete paths). Checked read-only against BI: the local bootstrap-infrastructure clone's fetched `origin/main` (`bea5252`) grants the TEST Drift role `ecr:DescribeRepositories`/`ecr:ListTagsForResource` on `user-service-test-{web,worker}`, `ses:GetEmailIdentity`/`ses:ListTagsForResource` on `user.vilnacrmtest.com` and `route53:GetHostedZone`/`route53:ListResourceRecordSets` on the TEST zone (`pulumi/infra/governance.py` `_test_poc_capability_statements`, line 289 on, statements `PocRegistryMetadata`, `PocMailIdentityMetadata` and `PocDkimZoneMetadata` at lines 347, 356 and 364, attached to every purpose at lines 457-461 while the packaged TEST PoC identity is enabled, line 329; not present at the clone's checked-out `debd88b`); the story cites those grants for TEST, adds any refresh read they miss, and adds the PROD equivalents on XP-14's PROD repositories, identity and zone, which no BI grant covers. **Workload reads:** `iam:GetRole` on the stack's ECS execution and task roles (`_role`, `scripts/poc_workload_capabilities.py` line 89 on, with the native read set at lines 37-48; called at lines 333 and 341); `iam:SimulatePrincipalPolicy` on the stack's **execution role only** (`_pull`, lines 193-232, called at line 338 with the execution role; R8-m3); `ecr:GetAuthorizationToken` (account-wide by AWS design) and `ecr:BatchGetImage`, `ecr:BatchCheckLayerAvailability` and `ecr:GetDownloadUrlForLayer` on the stack's two workload repositories (`scripts/poc_workload_images.py` lines 77-87, 126 and 206-209; the same pull set as `PULL_ACTIONS`, capabilities lines 25-29); `ssm:GetParameter` on the stack's gateway certificate parameter (TEST XP-10, PROD XP-15); `acm:DescribeCertificate` on that certificate. **Explicit deny (R8-m3, found while checking BI):** the read-only policy of the service preview and drift roles carries the `DenySecretLeakingReads` statement (`pulumi/infra/governance.py` line 267, at both `debd88b` and `bea5252`) over `_READ_ONLY_SECRET_DENY_ACTIONS` (`pulumi/infra/ci_bootstrap.py` lines 132-145), which include `ssm:GetParameter` and `ecr:GetAuthorizationToken`; an explicit deny overrides any allow, so the story must narrow that deny for the Drift role only (for `ssm:GetParameter`, a `NotResource` carve-out of the exact certificate parameter ARN, as the apply role's `DenySecretLeakingReadsApply` already carves out its own CI secrets, `pulumi/infra/ci_bootstrap.py` `_apply_secret_deny_document`; for `ecr:GetAuthorizationToken`, removal from the Drift role's deny, because the token grants nothing without the repository-scoped pull grants above). The exact form is the BI owner's security review, approved by Kravalg; without it the story does not merge. It is unconditional, because the Drift role holds none of the IAM, ECR image, SSM or ACM reads; the round-7 request for a conditional row is kept in position (row 50, like S5.6) but its condition is always true. | Each listed read allowed for the Drift role, including through the narrowed deny / any write, `GetSecretValue`, `kms:Decrypt`, `ssm:GetParameter` on any other parameter, `iam:SimulatePrincipalPolicy` on the task role or any other role, and the same reads on other roles, repositories, identities, zones or parameters denied / the existing registry and baseline drift matrices, and the deny for the preview role, are unchanged |
| S5.19 | BI | **PROD recovery (M-9):** the role `GitHubCiRecovery-user-service-infrastructure-prod`, trusted only for the USI `prod-recovery` environment on `main` (the environment itself is USI S5.21), with grants mirroring S5.7 **without** any delete, abandon or `DeleteSecret` grant. | Exactly the recovery set / delete actions denied / PR-head assumption denied |
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

- **Shared or serialized:** the chains C-BI, C-controls, C-contract,
  C-topology, C-runner, C-composition, C-autoscaling, C-observability,
  C-runtime, C-data, C-network, C-compute, C-stack and C-guard in
  `architecture.md` §4. There is one writer per chain. S4.10 is the only
  writer of `scripts/poc_workload_topology.py`,
  `scripts/poc_workload_secret_result.py` and the native topology
  integration test. `scripts/poc_workload_reconciliation.py` is C-contract
  (S4.10, then S4.13, then S4.14). `scripts/poc_registry_plan.py` changes
  only in S4.3 among this plan's stories (R6-m13); its TEST registry
  constants are XP-14's, outside this plan and outside that rule (R7-m3).
  The PROD contract schema `schemas/poc-prod-v1.schema.json` is S4.14's and
  the scheduled-drift result schema is S4.15's (C-contract; R7-m4, R7-m1).
  The workflow-shape tests (including
  `tests/unit/test_service_reviewed_credentials.py`, R7-m7) and
  `scripts/poc_phase_source_adapter.py` are C-runner (S4.11, S4.13, S4.14,
  S4.17, then S4.7 for the unstubbed PROD host seam test; R6-M1, R8-m7);
  S4.17 also adds the scheduled host and worker entries and the result
  copy-out (R7-M2, R8-M1). S4.14 makes `poc_contract.py`'s registry and
  mail semantics and `poc_secret_observation.py`'s ARN prefix
  stack-aware in its C-contract slot (R8-m2). `pulumi/app/workload_phase.py` is C-composition
  (S1.1 → S1.3 → S1.4 → S2.1 → S2.3 → S3.2 → S3.1 → S3.3 → S3.5-A).
- **Independent:** these can run in parallel with at most three agents, after
  their chain heads:
  - S4.16 (after S5.23);
  - S3.5-B;
  - S5.8–S5.14 and S5.20 (US);
  - S5.16 (AGI).

  S4.1, S4.4 and S4.5 edit C-runner files (the worker diagnostics and
  `tests/unit/test_service_execution_worker.py`, the runner), so they head
  C-runner (m5). S2.2 and S2.4–S2.5 are serialized in C-autoscaling and
  C-observability, because S2.1 and S2.3 also wire `workload_phase.py`.

## Ordered story list

| # | Story | Repo | Kind |
| --- | --- | --- | --- |
| 0 | D-1 … D-7 and D-14 (recovery targets RPO ≤ 1 hour, RTO ≤ 24 hours) recorded as explicit user decisions dated 2026-09-30 (`decisions.md`; D-4, D-5 clarified the same day), and the derived details D-8 … D-13 confirmed the same day | user | done; `@Kravalg` approval of the README PR is still S4.6 step 1 |
| 1 | S5.8 #501 | US | independent |
| 2 | S1.1 generation out of state (hardened branch) + contract (per-action `scaling`, receipt schemas) + central fields (+ transition rule) | USI | C-contract, C-runtime, C-composition head |
| 3 | S1.7 AWSCURRENT refs | USI | C-contract, C-runtime |
| 4 | S1.2 DocumentDB-managed password | USI | C-data |
| 5 | S1.3 DocumentDB IAM + bootstrap-job SG + step-1 shape + DSN tests | USI | C-data, C-network, C-compute, C-composition |
| 6 | S1.4 Redis IAM auth (D-1) | USI | C-data, C-network, C-compute, C-composition |
| 7 | S1.10 legacy path fail-closed | USI | C-data, C-compute, C-stack |
| 8 | S5.1 every central role, incl. restore and exercise roles (no KMS statements) | BI | C-BI |
| 9 | S5.2 apply-role capability (N-11, managed-password grants, no deletes) | BI | C-BI |
| 10 | S5.17 preview and drift read (no KMS) + simulation grant | BI | C-BI |
| 11 | S5.4 CMKs per AD-15a, then identity statements (incl. preview/drift KMS read); CloudTrail read events | BI | C-BI |
| 12 | S1.9 CMK binding (secrets, DocumentDB log groups) | USI | C-contract, C-data |
| 13 | S5.3 rotation, seed, redeploy and bootstrap-job functions; KMS log groups | BI | C-BI |
| 14 | S1.6 rotation wiring + idempotent seed + critical patterns (Invocation, docdb, bucketV2) | USI | C-runtime, C-guard |
| 15 | S1.5 secret policies (three managed-secret states) | USI | C-runtime |
| 16 | S2.1 → S2.2 autoscaling, per-action start/stop times (S2.1 adds `ignore_changes`, not the list) | USI | C-compute, C-autoscaling, C-composition |
| 17 | S2.3 → S2.4 → S2.5 topic (plane wiring), alarms and runbooks, security rules and allow-lists | USI | C-observability, C-composition |
| 18 | S5.10, S5.13, S5.11, S5.12 | US | independent (may start any time) |
| 19 | S1.8 KMS keys; drop PEM and passphrase purposes; ECS and Container Insights log-group CMK | USI | C-contract, C-runtime, C-compute |
| 20 | S1.11 drift allow-list contract (after S2.1 and S1.8, R5-M4) | USI | C-contract |
| 21 | S3.2 → S3.1 → S3.3 → S3.4 network (egress inventory first in S3.4) | USI | C-network, C-guard, C-composition |
| 22 | S3.5-B TEST TLS risk acceptance | USI | independent |
| 23 | S5.9 non-root → S3.7 | US → USI | C-compute |
| 24 | S5.14 multi-arch → S2.6 cost/Graviton + TEST schedules (cost figures with source labels) | US → USI | C-compute, C-autoscaling |
| 25 | S3.5-A PROD HTTPS target group (PROD shape); `_validate_target` by stack | USI | C-compute tail, C-composition tail |
| 26 | S5.16 front door | AGI | independent |
| 27 | S4.1 → S4.4 → S4.5 diagnostics, guard and timing | USI | C-runner head (m5) |
| 28 | S4.10 hardened topology (both stacks), native gates, secret history, checkpoint-field allowance; pins removed | USI | C-contract, C-topology |
| 29 | S4.11 receipts after every apply, including a failed result inspection (failure-path publication job; phase-guarded upload), projection inputs in the success receipt; observation-record authentication; anchor rebinding | USI | C-runner, C-contract |
| 30 | S4.9 step-2, rollback-zero (hold needs the stop observation, authenticated by the S4.11 library; the suspension flag), policy-update + multi-arch admission; per-action window | USI | C-contract |
| 31 | S4.2 resume (any operation, under S4.9's rules) + abandon admission + fail-closed prior check | USI | C-contract |
| 32 | S5.21 Kravalg-only environments (`test`, `prod`, `test-recovery`, `test-exercise`, `prod-recovery`; `governance-evidence` unchanged) | USI (repository controls) | C-controls |
| 33 | S5.23 TEST exercise role grants | BI | C-BI |
| 34 | S5.7 test-recovery role and grants (delete map from the S4.10 graph) | BI | C-BI |
| 35 | S4.3 recovery command (import, abandon, a receipt from every checkpoint-writing subcommand, private hash-only export reader, approvals check, delete-action map) | USI | C-contract, C-guard |
| 36 | S5.22 ruleset: `abandon-manifest-approval` required with a pinned issuer | USI (repository controls) | C-controls |
| 37 | S4.12 runner mode routing | USI | C-runner, C-contract |
| 38 | S4.13 accepted-workload receipt (observation job with pre-credential admission, lock-tolerant checkpoint capture, start and stop; same-run receipt binding); separate `test_workload_drift` job with the FR-32 plan-plus-gate reducer; lineage-derived `workload_route`; TEST scheduled-drift exclusion; releases (reviewed README/spec/log-health/test amendment); workflow-shape test rewrites | USI | C-runner, C-contract |
| 39 | S4.14 PROD path (worker, workflow, gate 2a/2b; every TEST-only pin with a PROD fixture or XP-14; stack → contract mapping; PROD contract schema; PROD scheduled-drift exclusion) | USI | C-runner, C-contract |
| 40 | S4.15 acceptance-receipt validator (+ scheduled-drift result schema, `checked` only) + two-gate hard-stop test (both contracts) | USI | C-contract |
| 41 | S4.16 TEST exercise workflow | USI | independent |
| 42 | S5.18a restore-rehearsal grants (no VPC) | BI | C-BI |
| 43 | S4.6 gate 1 + live TEST campaign (steps 1–21, including S5.5 and S5.18b) | USI (+BI live) | final TEST, live |
| 44 | S5.6 if the timing is over the bound | BI | conditional |
| 45 | S4.8 point-in-time restore rehearsal (D-14 targets) | USI (+BI live) | live TEST |
| 46 | S5.20 in-container TLS merged and published | US | before gate 2 |
| 47 | S5.19 prod-recovery role and grants (environment from S5.21) | BI | C-BI |
| 48 | XP-14 PROD registry proof (registry-phase work outside this plan; includes the observer's PROD coordinates, `_caller`, `_key` and `LOCKS`; the TEST registry constants of `poc_registry_plan.py` and `_REGISTRIES`; the PROD registry completion; the PROD mail domain for `_mail_semantics`; and the committed `poc-prod.json` under the S4.14 PROD schema) | USI registry | prerequisite |
| 49 | XP-15 PROD gateway certificate parameter (gateway owner) and XP-16 PROD permissions-boundary path (bootstrap owner), each existing live under the TEST-analogous name its owner confirmed in the S4.14 PR (R8-m6) | gateway, BI | gate-2a prerequisite |
| 50 | S5.24 Drift-role read inventory and grants (registry rows and refresh reads; IAM `GetRole`, `SimulatePrincipalPolicy` on the execution role only; ECR incl. `GetDownloadUrlForLayer`; SSM; ACM; the Drift-role deny narrowed) for the S4.17 path (R7-m9, R8-m3) | BI | C-BI; before S4.17 |
| 51 | S4.17 scheduled workload drift for the TEST and PROD workload stacks (isolated scheduled launch through the host and worker; data-driven per stack; result record copied out and uploaded) | USI | C-runner; gate-2b precondition |
| 52 | S4.7 gate 2a (P-1 PROD preview), then gate 2b + PROD plan; PROD workload contract PRs (the first one starts the S4.17 PROD checks and removes `prod` from the baseline); the unstubbed PROD host seam test after XP-14 (Kravalg-approved) | USI | C-runner tail; PROD gate |

**No forward dependencies (re-verified over all 53 rows, rows 0-52, in
revision 8, including test-level and ownership-level dependencies; R6-M2,
R7-m4, R7-m6, R8-m6).** Every story depends only on lower-numbered rows. S4.9
(row 30) depends only on S4.10 (row 28), S4.11 (row 29) and S2.6 (row 24);
its `hold` rule reads the observation record through the S4.11 library,
and its N8 fixtures are S4.11-written records, so neither the code nor the
tests need S4.13 (row 38), which later writes the live records. The
observation schema is S1.1's (row 2). S4.2 (row 31) uses S4.9's per-mode
admission rules, its `start_at` window and the `rollback-zero` resume
boundary, and S4.3 (row 35) follows S4.2. S4.10 (row 28) derives the
stack's URN prefix, root, provider and service URNs deterministically and
stubs the PROD registry set in its PROD fixtures (the S4.10 registry-set
note in S4.14), so it reads nothing from XP-14 (row 48). S4.13 (row 38) derives `workload_route` with the S4.11
lookup (row 29). S4.14 (row 39) owns the PROD contract schema, which S4.15
(row 40) uses for the `poc-prod.json` hard-stop cases (offline fixtures),
XP-14 (row 48) uses for its committed `phase: registry` file, and S4.7
(row 52) uses for the PROD workload contract PRs. S4.14's XP-14 rows
(including the PROD mail domain, which its code leaves absent so a PROD
workload contract fails closed) use stubs and checking stand-ins, never
row-48 data. S4.14 pins the TEST-analogous XP-15 and XP-16 names as an
assumption that the owners confirm in the S4.14 PR before it merges: a
naming statement recorded in row 39 itself, not the row-49 deliverable
(pre-commit audit). XP-15 and XP-16 (row 49) are the parameter and the
boundary path existing live under those names; S5.24 (row 50) grants
`ssm:GetParameter` on the XP-15 parameter, and S4.7 (row 52) verifies
both live. S4.15 (row 40)
owns the scheduled-drift result schema, including `registry-phase`, and
defines the two-item gate-2b check that names S4.17 and the S4.7 flip;
S4.17 (row 51) only emits records of that schema, so the check is a
definition, not a code dependency. S4.17 (row 51) follows S1.1 (row 2,
projection inputs, full image rows, certificate observation and program
trees in the success-receipt schema), S4.11 (row 29, the writer), S4.13
(row 38), S4.14 (row 39, the PROD schema and the stack-aware binding),
S4.15 (row 40), XP-14 (row 48), XP-15 and XP-16 (row 49) and S5.24 (row
50), and S4.7 (row 52) follows it in C-runner and needs it. S5.24 (row
50) holds its own read inventory, derived from modules and BI code that
exist today (the observer, `poc_registry_runner.py`,
`poc_mail_prerequisite.py`, the images and capabilities modules, and the
BI governance policy), so nothing in row 50 waits for row 51.
S1.11 (row 20) checks the program's `ignore_changes`, which S2.1 (row 16)
adds; S1.8 (row 19) is its C-contract predecessor (R5-M4). The C-composition
writers (rows 2, 5, 6, 16, 17, 21, 25) run in row order, and S3.5-A (row 25)
makes the program render `prod` before S4.10 (row 28) needs it.
BI inputs to USI are deterministic names, ARNs or patterns (the
`secretsmanager` endpoint policy included: `rds!cluster-*` plus the
deterministic S5.1 role ARNs). The only apply-derived values (subnet IDs,
bootstrap-job SG ID, DocumentDB-managed secret ARN) flow through XP-8 inside
row 43 (S4.6 steps 5 and 5b, again in step 20), and they feed only S5.5,
S5.18b and the USI contract. S5.15 is dropped (D-5).
