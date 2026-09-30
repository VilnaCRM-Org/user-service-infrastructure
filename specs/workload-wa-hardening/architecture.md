---
artifact: architecture
workflow: _bmad/bmm/workflows/3-solutioning/bmad-create-architecture (Create mode, non-interactive)
task: workload-wa-hardening
source_baseline: 66776772979956de9c5abdbee7c45641a1b533fa
date: 2026-09-30
revision: 11 (readiness round-11 findings R11-M1, R11-m1…m4 and R11-n1…n4 addressed on top of revision 10, which answered round 10 (R10-M1, R10-m1, R10-m2 and R10-n1…n6) and applied user decision D-15 on top of revision 9, which answered round 9 (R9-M1, R9-m1, R9-m2 and R9-n1…n4) on top of revision 8, which answered round 8 on top of revision 7 (round-7 findings R7-M1, R7-M2, R7-m1…m9 and R7-n1…n3, plus audit F2, F6 and F8); decisions D-1…D-15 of 2026-09-30 applied)
inputDocuments: [research.md, brief.md, prd.md, decisions.md, specs/poc-workload-runner.md, specs/poc/README.md]
---

# Architecture: Well-Architected hardening of the user-service workload

## 1. Target and engine discovery

| Item | Value |
| --- | --- |
| Target | `pulumi` program at `pulumi/`: project `user-service-infrastructure`, stacks `test` and `prod` |
| Engine | Python Pulumi through `uv` and `pulumi -C pulumi`. Terraform/Terraspace: SKIPPED (not applicable). |
| Backend | `s3://pulumi-user-service-infrastructure-{env}-state` with the `awskms://alias/pulumi-user-service-infrastructure-{env}-secrets` provider. Both are governance-owned and unchanged. |
| Accounts | TEST `891377212104`, PROD `933245420672`, `eu-central-1` |
| Apply path | Saved plan only through the protected service-execution worker (`/pulumi test up`). PROD is gated on TEST. |
| Destructive-diff classifier | `scripts/pulumi_ci_guardrails.py` (`CRITICAL_TYPE_PATTERNS`, `find_destructive_steps`), used by `scripts/run_pulumi_command.py::_validate_safe_preview` |
| Drift check | Two executed paths (R5-M1). **Baseline:** `make test-drift` (`Makefile` lines 229-230) → `scripts/run_pulumi_command.py drift` → `PULUMI_INVOCATIONS["drift"]` (`preview --refresh --expect-no-changes`, `scripts/_pulumi_command_support.py` lines 66-70), run by `.github/workflows/scheduled-drift.yml` (TEST job lines 23-84, PROD job lines 86-147) under the drift role against the baseline program `pulumi/__main__.py` (lines 18-30), with no workload materialization and no receipt check. **Workload:** a new `self-deploy.yml` job `test_workload_drift` (S4.13, R6-M1; the registry job `test_post_apply_drift`, lines 478-568, keeps its registry-only `if`, lines 480-483, and its `needs`, lines 486-489) → `service_execution_host.py` → `service_execution_worker.py` → `poc_workload_runner.execute` → `run_pulumi_command._dispatch_command("plan", …)` (lines 833-839) with a workload drift gate, which is the registry plan-plus-gate pattern of `scripts/poc_registry_runner.py` lines 344 and 364 (R6-m4), under the **preview** role (the same `aws-preview-role-arn` step as the registry job, `self-deploy.yml` line 546). Scheduled workload drift is S4.17 (R6-m11). `scripts/run_pulumi_drift_check.py` is not executed by any workflow or make target (only `tests/pulumi/test_ci_guardrails.py` line 18 and `tests/unit/test_script_entrypoints.py` lines 500-504 reference it), so this plan puts nothing in it. The FR-32 check lives on the workload path (AD-23, S4.13). |
| Profile | `.claude/devops-sdlc.json` is absent. `validate-profile` returned BLOCKED ("Required repository path is missing"). XP-7: run `do-sdlc-setup` before implementation. |

The following argv would be reviewed later. It was not executed in this task:

- `make ci-pr`
- `make test-coverage`
- `make test-guardrails`
- `make test-security`
- `make preview-test`, which is authorized-only.

## 2. Boundaries and ownership

```
bootstrap-infrastructure (governance, CODEOWNERS @Kravalg)
  ├─ IAM: ECS execution + task roles (task role: SQS, SES, KMS, elasticache:Connect);
  │        app-rotation, redeploy, bootstrap-job, restore-operator,
  │        restore-reader and TEST exercise roles (S5.1; restore grants
  │        S5.18a; exercise grants S5.23);
  │        recovery role + grants (test-recovery S5.7, prod-recovery S5.19);
  │        every new role created by an independent CloudFormation stack per
  │        role family (human non-root installer; AD-26 layer 6, R11-M1);
  │        apply-role workload capability; preview + drift read capability
  ├─ KMS (D-4, decided 2026-09-30): runtime CMK (secrets, every workload log
  │        group, flow-log bucket, SNS topic), JWT signing CMK (RSA), 2FA CMK;
  │        key policies name existing roles (roles are created first; AD-15a)
  ├─ Lambda: app-secret rotation + seed (no VPC), redeploy (no VPC),
  │          DocumentDB bootstrap job (VPC-attached after XP-8, USI bootstrap-job SG),
  │          restore-rehearsal reader (package S5.18a; VPC attach after XP-8, S5.18b);
  │          EventBridge RotationSucceeded → redeploy rule; each function in
  │          the independent stack that owns its role (AD-26 layer 6)
  └─ CloudTrail: read management events (for the unauthorized-read alarm)

user-service-infrastructure (this repo; no IAM, no Lambda functions, no SecretVersion)
  ├─ GitHub repository controls (m3; USI's own
  │        scripts/configure_github_repository_controls.py and
  │        scripts/_github_repository_controls.py, admin apply by Kravalg):
  │        environments with Kravalg as sole reviewer: test, prod,
  │        test-recovery, test-exercise, prod-recovery (S5.21);
  │        governance-evidence stays reviewer-less and main-only
  │        (scripts/_github_evidence_environment.py); ruleset check
  │        abandon-manifest-approval with a pinned issuer (S5.22)
  ├─ secrets metadata, SecretPolicy, SecretRotation, seed aws.lambda.Invocation
  ├─ DocumentDB (managed primary password), ElastiCache IAM user + default user + group
  ├─ ECS, autoscaling, alarms, SNS, EventBridge alarm rules
  ├─ VPC: flow logs → S3, default SG, endpoints (pinned policies), egress-tight SGs,
  │        bootstrap-job SG
  ├─ E4: diagnostics, admission resume/abandon/step-2/rollback-zero/policy-update,
  │      recovery command, runtime guard, two-gate phase admission, drift allow-list
  └─ C-runner: step-1 and accepted-workload receipts, mode routing, PROD path

user-service: #501, non-root image, MONGODB-AWS check, Redis IAM token provider,
              KMS signing/encryption, in-container TLS (PROD), multi-arch images
api-gateway-infrastructure: REST API + WAF + VPC link V2 → internal ALB (D-3, decided)
```

### 2.1 Every function and task: APIs called and network path (B-1)

| Caller | VPC | APIs it calls | Network path it needs |
| --- | --- | --- | --- |
| DocumentDB-managed primary rotation | AWS-managed by the service | None from the workload VPC | None. No Lambda runs in the workload VPC for it (FR-01). |
| App-secret rotation and seed Lambda (BI) | No | `secretsmanager:DescribeSecret`, `GetSecretValue`, `PutSecretValue`, `UpdateSecretVersionStage`, `GetRandomPassword`. KMS use happens inside Secrets Manager (`kms:GenerateDataKey`/`Decrypt` with `kms:ViaService=secretsmanager.<region>.amazonaws.com`). | Lambda service network to the public regional endpoint. No VPC endpoint is needed. If BI policy ever requires VPC attachment, a new story must add the function SG to the `secretsmanager` endpoint SG ingress first. |
| Redeploy Lambda (BI) | No | `ecs:UpdateService` (`forceNewDeployment`) and `ecs:DescribeServices` on the two deterministic service ARNs | Public regional endpoint. |
| DocumentDB `$external` bootstrap job (BI) | Yes: USI app subnets, USI bootstrap-job SG (XP-8) | `secretsmanager:GetSecretValue` on the exact DocumentDB-managed secret ARN (AWS-managed key, decrypted inside Secrets Manager); the DocumentDB wire protocol over TLS to the cluster port (CA bundled in the package). It makes **no** STS call (credentials come from the Lambda environment), **no** `docdb`/`rds` API call (the cluster endpoint is a non-secret input), and **no** CloudWatch Logs call (the Lambda service ships logs). | `secretsmanager` interface endpoint (private DNS) and the DocumentDB port to the DocumentDB SG. Both are in FR-17/FR-18. |
| Restore-rehearsal reader (BI; role and package S5.18a, VPC attachment S5.18b after XP-8) | Yes: USI app subnets, USI bootstrap-job SG | `secretsmanager:GetSecretValue` on the temporary cluster's managed secret (tag-conditioned, V-19; else exact ARN by a reviewed ephemeral grant); DocumentDB wire protocol to the temporary cluster, read-only (`count`, sample `find`). | Same as the bootstrap job; the temporary cluster uses the DocumentDB SG. |
| Restore-rehearsal operator (BI role, S5.18a, workflow) | No | `rds:RestoreDBClusterToPointInTime` with `UseLatestRestorableTime` (R6-m10; on the source `cluster:user-service-infrastructure-test-docdb`, the target `cluster:<stack>-docdb-restore-rehearsal`, the existing `subgrp:` DocumentDB subnet group and the cluster parameter group), `CreateDBInstance`, `ModifyDBCluster` with `ManageMasterUserPassword` (`rds:ManageMasterUserPassword` = true), `DescribeDBClusters` (including the source cluster's `LatestRestorableTime`), `DeleteDBInstance`, `DeleteDBCluster` (`SkipFinalSnapshot`), `AddTagsToResource`, all conditioned on the rehearsal names. For the managed password: `secretsmanager:CreateSecret` and `secretsmanager:TagResource` on `secret:rds!cluster-*`, and `kms:DescribeKey` on `alias/aws/secretsmanager` (docs A-27; V-22). For the encrypted source cluster storage: `kms:CreateGrant`, `kms:Decrypt`, `kms:DescribeKey` on the DocumentDB storage key with `kms:ViaService=rds.<region>.amazonaws.com` (V-22). | Public regional endpoint from the GitHub runner. |
| USI apply role, step 1 (`CreateDBCluster` with `ManageMasterUserPassword`) | No (GitHub runner) | `rds:CreateDBCluster` (with `rds:ManageMasterUserPassword` = true); DocumentDB creates the managed secret with the caller's permissions: `secretsmanager:CreateSecret` and `secretsmanager:TagResource` on `secret:rds!cluster-*`, and `kms:DescribeKey` on `alias/aws/secretsmanager` (the RDS and Aurora pages document this; the DocumentDB page is silent, so V-21 confirms it). `CreateLogGroup` with `kmsKeyId` needs `kms:DescribeKey` on the runtime CMK with `kms:ViaService=logs.<region>.amazonaws.com` (A-28). | Public regional endpoints. |
| ECS tasks (web, worker) | Yes | `ecr.api`, `ecr.dkr`, S3 (ECR layers), `logs`, `secretsmanager` (execution role), `sqs`, `kms` (`Sign`, `GetPublicKey`, `Encrypt`, `Decrypt`), SES API. **MONGODB-AWS:** the client signs an `sts:GetCallerIdentity` request that the DocumentDB instance itself sends to STS, so the task makes no STS call. **Redis IAM:** the token is a local SigV4 signature; no API call. Credentials come from `169.254.170.2`. | The interface and gateway endpoints of FR-17; SES API per V-12 (else NAT 443, recorded); the DocumentDB and Redis ports. The `sts` endpoint is kept for SDK default-chain calls. |

## 3. Architecture decisions

- **AD-01 DocumentDB identity (FR-01, FR-02).**
  - **Cluster:** `aws.docdb.Cluster(manage_master_user_password=True)`, with
    no `master_password`, engine version `5.0.0`, instance-based. Any other
    version or an elastic cluster raises (V-17).
  - **App connection:** `MONGODB_URL` is a plain environment value:

    ```
    mongodb://<endpoint>:<port>/<db>?tls=true&tlsCAFile=<ca>&replicaSet=rs0&readPreference=secondaryPreferred&retryWrites=false&authSource=%24external&authMechanism=MONGODB-AWS
    ```

  - **`$external` user (S5.5):** the BI VPC-attached bootstrap job creates it,
    running in the USI app subnets with the USI bootstrap-job SG.
    - It reads the DocumentDB-managed secret under the bootstrap-job role. The
      grant is on the **exact** secret ARN delivered by XP-8, not a pattern,
      because the managed secret's name (`rds!cluster-<uuid>`) is not
      deterministic.
    - It runs `createUser` or `updateUser` to set
      `arn:aws:iam::<acct>:role/<task-role>` with `readWrite` on the app
      database only.
    - Its evidence is the run ID, the approver and a user-list hash. The
      password is never printed.
  - **Failure mode (V-1 fails):** an app DB user with a rotated password is
    needed. That is a new user decision, not a silent fallback.
- **AD-02 Redis identity (FR-04, D-1 = IAM, decided 2026-09-30).**
  - **Engine:** Redis OSS 7.1 (AS-2) or Valkey ≥7.2, with
    `transit_encryption_enabled=True` and `transit_encryption_mode="required"`.
  - **Users:**
    - `default` user: `user_name="default"`, a stack-scoped `user_id`,
      access string `off -@all`, `authentication_mode={type:"no-password-required"}`
      (V-5 confirms the group rule and the accepted mode);
    - app user: `authentication_mode={type:"iam"}`, `user_name == user_id`
      (`<stack>-app`), reviewed access string `on ~* +@all -@dangerous`.
  - **Group:** a `UserGroup` containing both; `ReplicationGroup(user_group_ids=[…])`,
    no `auth_token`.
  - **No secret, no rotation function, no rotation SG.** The access string is
    managed by Pulumi and never changed out of band (AD-23 lists no
    ElastiCache fields).
  - **Task-role grant (S5.1):** `elasticache:Connect` on
    `arn:aws:elasticache:<region>:<acct>:replicationgroup:<rg-id>` and
    `arn:aws:elasticache:<region>:<acct>:user:<stack>-app`. Both ARNs are
    deterministic (`build_resource_name`), so no apply output is needed.
    Only `aws:SourceIp` and `aws:ResourceTag/*` are usable as conditions for
    replication groups (V-9).
  - **Env values:** `REDIS_URL=REDIS_LOCKOUT_URL=rediss://<primary-endpoint>:<port>`,
    `REDIS_IAM_USER_ID`, `REDIS_REPLICATION_GROUP_ID` (lower case), `AWS_REGION`.
  - **Client (S5.13):** a token per new connection (SigV4 presign of
    `Action=connect&User=<user-id>` for service `elasticache`, host = the
    replication-group id), a connection lifetime cap of 11 h (re-`AUTH` or
    reconnect), no re-auth inside `MULTI`/`EXEC` or Lua. The token lifetime is
    the shorter of 15 min and the task credentials' expiry; tokens are needed
    only at `AUTH` time.
- **AD-03 Secret inventory (FR-06, FR-09).**
  - **Declared purposes** go from ten to two: `app_secret` and
    `oauth_encryption_key`.
  - **Observed purpose:** `documentdb_primary`, managed by DocumentDB.
  - **Removed:**
    - `document_db_password`, `document_db_url`;
    - `redis_auth_token`, `redis_url` (D-1: no Redis secret at all);
    - `oauth_private_key`, `oauth_public_key`, `oauth_passphrase`;
    - `two_factor_encryption_key`.
  - **Interim:** the four KMS-bound purposes stay declared as
    `non_rotatable` until S1.8. Admission rejects `non_rotatable` at gate 1
    (FR-31). D-5 (decided 2026-09-30) confirms that `oauth_passphrase` is
    retired by S1.8 and is never rotated.
- **AD-04 Contract evolution.**
  - `poc-test-v1` is amended in place (status `proposed-not-installed`, no
    committed workload section).
  - `secret_lifecycle` changes:
    - `generation` becomes `"rotation-seed"`;
    - `provider_refresh_actions` is removed;
    - each reference gains `rotation` (`{function_ref, schedule_days}` or
      `"service-managed"`) and `value_kind`.
  - The top level gains `admission: {test: bool, prod: false | "preview" | true}`
    (AD-21), `workload_step: 1 | 2` (AD-18), `workload_operation: {mode,
    phase, sequence, resumes}` (AD-24; `phase` ∈ {`stop`, `hold`, `start`}
    is required for `rollback-zero` and absent otherwise; `resumes`, the
    `{mode, phase}` of the operation being finished, is required for
    `resume` and absent otherwise; R6-m7), `documentdb_secret_policy`
    (AD-08), `scaling: {starts: [{seq, at}…], stops: [{seq, at}…],
    consumed: [name…], scheduled_scaling_suspended: bool}` (AD-10; one `at`
    time per action, R5-M3; `scheduled_scaling_suspended` is a persistent
    TEST-only flag, default `false`, and a PROD contract with `true` fails
    the PROD schema of S4.14, R6-m7, R7-m4) and `drift.out_of_band_fields` (AD-23, added by
    S1.11).
  - **Stack → contract mapping (R6-m11).** Stack `test` reads
    `specs/poc/poc-test.json` (today's `CONTRACT_PATH`,
    `scripts/poc_phase_admission.py` line 24). Stack `prod` reads a new
    `specs/poc/poc-prod.json`, validated by a separate PROD schema
    `schemas/poc-prod-v1.schema.json` that S4.14 owns (R7-m4):
    `poc-test-v1.schema.json` pins `environment: test`, the TEST account and
    the TEST backend (lines 179-209), so no PROD contract validates against
    it, and it is not widened, because the trusted observer reads its
    `account_id` `const` (`scripts/poc_backend_observer.py` lines 199-201).
    The PROD schema has `environment` `const: prod`, the PROD account and
    backend, no `admission` object and
    `scaling.scheduled_scaling_suspended` `const: false`, and accepts
    `phase: registry` (XP-14) and `phase: workload` (the S4.7 PRs). It carries its own `phase`,
    `workload_step`, `workload_operation`, `scaling` (no
    `scheduled_scaling_suspended: true`, no night or weekend schedule),
    `documentdb_secret_policy`, `drift.out_of_band_fields`, PROD `central`
    fields and the PROD registry anchor (XP-14). S4.14 adds the mapping and
    an offline `poc-prod.json` fixture; the committed file lands with
    XP-14. `admission` stays in `poc-test.json` only: it is the single gate
    record for both stacks, and the runner reads `admission.prod` from the
    installed `main` `poc-test.json` before it reads `poc-prod.json`.
  - The workload `central` object (`schemas/poc-test-v1.schema.json`, today
    `additionalProperties: false` with only `execution_role_arn` and
    `task_role_arn` beyond the publisher fields) gains:
    `app_rotation_role_arn`, `redeploy_role_arn`, `bootstrap_job_role_arn`,
    `restore_operator_role_arn`, `restore_reader_role_arn` (S5.1);
    `apply_role_arn`, `recovery_role_arn`, `exercise_role_arn` (the §3.2a
    allow-lists); `rotation_function_arns`, `redeploy_function_arn` (S5.3);
    `cmk` (runtime, JWT, 2FA ARNs and aliases; S5.4); `lambda_network`
    (XP-8: subnet IDs, bootstrap-job SG ID) and
    `documentdb_managed_secret_arn` (XP-8). S1.1 adds all of them to the
    schema; each consumer story (S1.5, S2.5, S3.3) only reads them.
  - One serialized writer (C-contract) changes `poc_contract`,
    `poc_secret_observation` and `poc_workload_admission`.
    `poc_workload_topology` and `poc_workload_secret_result` change only in
    S4.10, which is part of C-contract (AD-25).
  - A test proves the registry contract digest is unchanged.
- **AD-05 Function ownership.**
  - All Lambda functions live in BI (R-16: the apply role is denied
    `lambda:GetFunction`, and USI may not create IAM). Each function lives
    in the BI independent CloudFormation stack that owns its role,
    because no CI applier may pass those roles (AD-26 layer 6, R11-M1);
    BI CI owns the log groups, permissions and rules.
  - USI references the function ARNs from reviewed central metadata. It
    creates only `SecretRotation` and the seed `aws.lambda.Invocation`.
  - The BI functions act only on an allow-listed set of secret ARN patterns
    (NFR-06).
- **AD-06 Idempotent synchronous seed (FR-05, FR-09; M-8).**
  - One `aws.lambda.Invocation` per rotated secret calls the BI `seed` entry.
  - **Input is immutable and non-secret:** exactly `{secret_arn, purpose}`,
    both fixed per stack. Any other key is rejected by a USI test and by the
    BI function.
  - **Idempotent:** if the secret already has an `AWSCURRENT` version the seed
    returns `{status:"noop", version_id:<current>}` and writes nothing;
    otherwise it runs `createSecret`, `setSecret`, `testSecret` and
    `finishSecret` synchronously and returns `{status:"seeded", …}`. The
    output schema is exactly `{secret_arn, version_id, status}`.
  - **Replacement is critical:** `aws:lambda/invocation:Invocation` joins
    `CRITICAL_TYPE_PATTERNS`, so any replace or delete of a seed Invocation
    is rejected by the classifier. V-18 confirms which input changes cause
    replacement.
  - **Ordering inside step 2 (AD-18, m-7):** the seed Invocation →
    `SecretRotation(rotate_immediately=False)` (`depends_on` the seed, because
    rotation configuration runs `testSecret`, which needs AWSCURRENT) →
    `SecretPolicy` → autoscaling targets and policies (`depends_on` both) →
    the TEST night and weekend `ScheduledAction`s → the one-time start
    `ScheduledAction` of the single unconsumed `scaling.starts` entry
    (`<svc>-start-1` on an on-time first build; `depends_on` the target and
    every policy). The ECS task definitions and services exist from step 1 at 0
    tasks and are **not** changed in step 2. Tasks start only when the
    one-time start action fires (AD-10, V-23), after the seed and rotation
    exist.
  - V-7: `aws.lambda.Invocation` must need only `lambda:InvokeFunction`, not
    `GetFunction`.
  - V-8: reading `Secret`, `SecretRotation` and `SecretPolicy` must use
    `DescribeSecret`/`GetResourcePolicy` only, not `GetSecretValue`.
- **AD-07 Redeploy on rotation (FR-05).**
  - BI owns the rule `source=aws.secretsmanager`, `eventName=RotationSucceeded`,
    restricted to the workload secret ARN patterns.
  - The redeploy Lambda calls `ecs:UpdateService(forceNewDeployment)` on the
    deterministic service ARNs:

    ```
    arn:aws:ecs:<region>:<acct>:service/<stack_tag>-ecs/<stack_tag>-web|worker
    ```

    These are fixed by `build_resource_name`, so there is no forward
    dependency.
  - V-4: `RotationSucceeded` delivery must be verified.
- **AD-08 Secret access control (FR-07).**
  - Each USI-declared secret gets a `SecretPolicy(block_public_policy=True)`
    with two deny statements (`Principal "*"`,
    `StringNotEquals aws:PrincipalArn [allow-list]`, exact role ARNs):
    - `Deny secretsmanager:GetSecretValue` unless the execution role or the
      app-rotation role;
    - `Deny secretsmanager:PutSecretValue` and
      `secretsmanager:UpdateSecretVersionStage` unless the app-rotation role.
  - `documentdb_primary`: a `SecretPolicy` created in step 2 and never
    deleted by an apply mode (only the TEST abandon removes it, together with
    its cluster). The contract field `documentdb_secret_policy` selects its
    document:
    - `deny-other-readers` (initial): `Deny GetSecretValue` unless
      `aws:PrincipalArn` is the bootstrap-job role;
    - `allow-rotation`: the same deny, plus the rotation principal or
      condition that V-3 identifies (for example `aws:PrincipalIsAWSService`
      or `aws:CalledVia` `rds.amazonaws.com`);
    - `tls-only`: one `Deny GetSecretValue` when `aws:SecureTransport` is
      `false`, which no legitimate caller triggers.

    The V-3 live check (S4.6 step 8) runs with `deny-other-readers` in
    place. A fallback is a reviewed contract PR that moves the state one step,
    applied by an update-only saved plan (admission mode `policy-update`:
    exactly one `update` step, on that `SecretPolicy` URN; any `delete`,
    `create` or second step is refused). The residual risk of each state is
    recorded. The restore-rehearsal secret belongs to a temporary cluster
    outside Pulumi and gets no policy; the exact-ARN or tag grant (S5.18a)
    limits it.
  - **Detection:** EventBridge rules with
    `ENABLED_WITH_ALL_CLOUDTRAIL_MANAGEMENT_EVENTS` implement the PRD §3.2
    matching (name, full-ARN and partial-ARN `secretId`; assumed-role,
    non-role and `AWSService` callers; denied calls). Rules also cover
    policy-change, value-change and rotation-failure events. Each event type
    has its own closed allow-list (PRD §3.2a): `PutResourcePolicy` by the apply
    role (step 2, `policy-update`); `DeleteSecret` and `DeleteResourcePolicy`
    by the TEST recovery role (abandon) and `RestoreSecret` by it (rebuild);
    `DeleteSecret`
    of a managed secret by `rds.amazonaws.com` (cluster deletion). Every other
    caller alarms. The managed-secret match uses the `rds!cluster-` prefix,
    so the rules need no XP-8 value.
  - The BI CloudTrail read events are XP-3.
  - **Grant scoping (corrected, M-2):** BI grants the USI-declared secrets with
    `arn:…:secret:<name>-??????` patterns, which need no USI apply output.
    The DocumentDB-managed secret is the exception: its ARN is known only
    after step 1 and reaches BI through XP-8, and BI grants it by exact ARN
    (plus a tag condition if V-19 confirms the tag).
- **AD-09 State-migration guard, fail-closed and offline (FR-09, NFR-07).**
  - Workload admission rejects any prior checkpoint containing these URN
    types. The check is a function in `scripts/poc_workload_admission.py`
    (S4.2, C-contract), called by `observe_workload` for every mode; it is
    not added to `scripts/poc_workload_topology.py`, whose only writer stays
    S4.10 (m15):
    - `random:*`;
    - `tls:*`;
    - `aws:secretsmanager/secretVersion:SecretVersion`;
    - the removed legacy secret URNs.
  - A one-time metadata observation by the existing trusted backend observer
    confirms R-02 before gate 1 (S4.6), and again before the first workload
    preview. The observation checks for the 11 registry resources and no
    workload URN.
  - E1 stories stay offline and need no preview.
  - If R-02 is false: STOP. A state-migration plan (state removal of the
    forbidden URNs, keeping the protected `Secret`s) is reviewed by the
    `state-migration-reviewer` and executed only through the FR-22 recovery
    command.
- **AD-10 Autoscaling and create-only start/stop (R4-M5, m4, R5-M3).**
  - `appautoscaling.Target` per service, created in **step 2** (AD-18), with
    `min = max(contract min, 1)` and `max = contract max`.
  - Web: target tracking on `ALBRequestCountPerTarget` (resource label) and
    CPU.
  - Worker: metric math (A-17) with a zero-task guard.
  - The ECS services use `ignore_changes=["desiredCount"]` (AD-23).
  - **Per-action times (R5-M3).** The contract lists every one-time action
    with its own time: `scaling.starts: [{seq, at}]` and
    `scaling.stops: [{seq, at}]`. The program renders `<svc>-start-<seq>` and
    `<svc>-stop-<seq>` with `schedule = at(<that entry's at>)`. An entry is
    **immutable once its URN is in the checkpoint**: a contract PR may only
    append a new entry (the next `seq`) or move an entry to
    `scaling.consumed` (below). So a new operation never changes the
    rendered inputs of an earlier action, and admission sees `same` for
    every earlier action (FR-11: no change to an earlier action). The
    `start_at` window below applies only to the new entry. An entry whose URN
    is **not** in the checkpoint (for example an action whose apply failed
    before it was created) may be moved to `scaling.consumed` and replaced by
    a new entry; that renders nothing to delete (m11).
  - **Start (step 2):** the service stays at `desiredCount=0` from step 1, and
    target tracking cannot scale from 0 tasks (no CPU or request data), so
    step 2 creates one one-time `ScheduledAction` per service for the
    **single unconsumed `scaling.starts` entry** (audit): `<svc>-start-<seq>`,
    `schedule = at(<entry at>)`,
    `scalable_target_action = {min_capacity: min, max_capacity: max}`. AWS
    documents that it scales out to `MinCapacity` when current capacity is
    below it (A-26). The step-2 set (FR-34, S4.9, S4.10) names that entry by
    its `seq`, not by a fixed `start-1`. The entry is set in its own small
    contract PR after the S5.5 job (S4.6 step 6b), right before the step-7
    request, so the window has the least slack to lose. If the window is
    missed, a new PR moves the uncreated entry to `scaling.consumed` and
    appends the next `seq`; the step-2 set follows it. The health
    observation (AD-18 item 4) waits for it in its own job. The action is
    `create`, so step 2 stays create-only.
  - **Stop (`rollback-zero`, first deployment), two plans.** Suspending
    scheduled scaling also blocks one-time actions, so the stop and the
    suspension cannot share a plan.
    1. **Stop plan** (`workload_operation.mode: rollback-zero`,
       `phase: stop`): create-only; it creates `<svc>-stop-<seq>` for the new
       `scaling.stops` entry with `min = max = 0` (A-26: scale in to
       `MaxCapacity`). The apply job does not wait for the scale-in
       (R6-m6). The separate `test_workload_observation` job of the same
       run (AD-18 item 4) waits until the stop entry's `at()` time and
       records every service with running = desired = 0 and each target at
       `min = max = 0`; `test_workload_acceptance` publishes that result as
       an authenticated **stop observation** bound to the stop plan's
       success receipt.
    2. **Hold plan** (`phase: hold`, TEST only, because only TEST has
       recurring actions): admitted only when the latest receipt is the
       stop plan's success receipt **and** its authenticated stop
       observation exists (R6-m6). Its contract PR sets the persistent flag
       `scaling.scheduled_scaling_suspended: true` (R6-m7), from which the
       program renders `suspendedState.scheduledScalingSuspended`. The plan
       is exactly one `update` per target, changing only that field to
       true, so the TEST morning action cannot restart a stopped service.
       With `max = 0`, dynamic scaling cannot scale out either. Only a hold
       plan sets the flag and only a start plan clears it (S4.9). A
       `policy-update` during a hold leaves the flag `true`, so every target
       is `same` and the plan renders no extra `Target` update. **Provider-source first case
       (m1, V-23 e):** S2.1 and S4.9 first read the pinned `pulumi-aws`
       provider's update path for `aws:appautoscaling/target:Target` and
       record whether `RegisterScalableTarget` re-sends `MinCapacity` and
       `MaxCapacity` on an update, and, under
       `ignore_changes=["minCapacity","maxCapacity"]` with `up --refresh`,
       whether it sends the refreshed live values (0 and 0 after the stop)
       or older program values. If it can send values other than the live
       ones, the hold plan could restart a stopped service, and S4.9 does
       not merge until the hold design is changed in a reviewed PR. V-23(d)
       stays the live STOP at step 15.

    A **restart plan** (`phase: start`) comes from a contract PR that sets
    `scaling.scheduled_scaling_suspended: false` (TEST) and appends a new
    `scaling.starts` entry; the plan updates the flag back to false and
    creates `<svc>-start-<seq>` in the same plan. That works because the un-suspension is applied at apply time
    and the start action fires at least 10 min later. The mode admits
    nothing else: no other `update`, no `delete`, no change to the service
    or to an earlier action. V-23(d) checks live that a suspension blocks
    one-time actions and that the restart plan fires after the
    un-suspension. In PROD a stop needs gate 2b, the `prod` environment
    approval and a recorded incident reason.
  - **`start_at` window (m13).** Replay admission (the `_gate` check that
    runs immediately before `up --plan`) checks only the new entry's `at()`
    time:
    - lower bound: admission time + 10 min for a `rollback-zero` plan (it
      creates only the action, plus the hold-flag update), and admission
      time + 60 min for a `step2` plan (seeds, rotations and policies come
      first; 60 min is above the 3300 s apply process timeout, so the action
      exists before it fires, or the apply has failed);
    - upper bound: admission time + 120 min for every mode.

    The window never lengthens the apply: the apply job keeps its 3300 s
    process timeout and 70-min job budget (`self-deploy.yml` `test_apply`,
    `tests/unit/test_apply_timeout_budget.py`; FR-24). The health
    observation that waits for the action runs in a separate job whose
    credentials are requested only after the wait (AD-18 item 4). After an
    approval delay, a new time means a new reviewed contract PR (a new
    entry) and a new saved plan.
  - **V-23 (live, S4.6 step 7)** checks: (a) whether registering the target
    with `min` above the current `desiredCount` of 0 already scales out (if
    so, the start action is redundant but harmless); (b) whether the
    one-time start action scales out from 0 at its time; (c) whether a fired
    one-time action stays listed. With per-action times, a fired action that
    stays listed renders the same `at()` it was created with, so its
    preview is `same`. If (c) shows that AWS removes fired one-time actions,
    the next apply's refresh (`up-plan` runs with `--refresh`) drops them
    from state, and a program that still renders them would propose
    `create`. **STOP before the next apply of any mode** (m12), not only
    before step 14. The reviewed fix has two parts: (1) a contract PR moves
    the fired actions to `scaling.consumed`, and the program stops rendering
    them; (2) the AD-23 entry lets the drift check accept a refresh-time
    removal of exactly those names. After both, the preview is `same`. No
    delete step is ever needed.
  - **Abandon and rebuild (D-12).** The abandon removal plan deletes every
    start and stop action with the rest of the workload. In the rebuild
    (S4.6 step 20), the 5b contract PR moves every earlier entry to
    `scaling.consumed` (none of their URNs is in the new checkpoint, so
    nothing is deleted), and the 6b PR appends one new `scaling.starts`
    entry, which the rebuild's step 2 creates as its single unconsumed
    entry.
  - TEST only: recurring `ScheduledAction`s at night and on weekends,
    created in step 2. They change the target's min and max, so those two
    fields are on the allow-list (AD-23). The start and stop actions change
    them in PROD too, so the allow-list entry covers both environments.
  - The Application Auto Scaling SLR must exist before step 1; no CI role
    may create it, and a missing one comes from S5.1's service-linked-role
    stack (§5, AD-26 layer 6; R11-m2).
- **AD-11 Observability.**
  - A new `observability.py` owns the SNS topic (runtime CMK per D-4, key
    policy in BI; CloudWatch alarms cannot publish to an `alias/aws/sns`
    topic), the topic policy, the alarms and the EventBridge rules.
  - Every workload log group carries `kms_key_id` = the runtime CMK (D-4):
    ECS web and worker, the pre-created Container Insights performance group
    (S1.8), DocumentDB audit and profiler (USI), and the BI function log
    groups (S5.3).
  - The runbooks live in `docs/sre-operations.md`.
- **AD-12 Network.**
  - Components:
    - `FlowLogs` (S3, following the `access_logs.py` pattern, FR-15);
    - `DefaultSecurityGroup` with no rules;
    - `VpcEndpoints` plus an endpoint SG, with pinned policies (AD-12a);
    - egress rules;
    - the `bootstrap-job` SG.
  - There is no rotation-function SG (D-1 = IAM).
  - USI exports the app subnet IDs, the bootstrap-job SG ID and the
    DocumentDB-managed secret ARN for XP-8.
  - The new fixed-name resources join the N-06 import list.
- **AD-12a Pinned endpoint policies (FR-17, M-7).** Each document is committed
  as `tests/fixtures/endpoint-policies/<service>.json` with only `${account}`,
  `${region}` and metadata placeholders; the program renders it and a test
  asserts byte-equal JSON after rendering.

  | Endpoint | Statement(s) |
  | --- | --- |
  | S3 gateway | `Allow`, `Principal "*"`, `s3:GetObject`, `arn:aws:s3:::prod-${region}-starport-layer-bucket/*` (V-14). No other statement. |
  | `ecr.api` | `Allow` `ecr:GetAuthorizationToken` (resource `*`, the API has no resource ARN), condition `aws:PrincipalAccount=${account}`; `Allow` `ecr:BatchGetImage`, `ecr:GetDownloadUrlForLayer`, `ecr:BatchCheckLayerAvailability` on `arn:aws:ecr:${region}:${registry_account}:repository/<reviewed repos>` (V-20). |
  | `ecr.dkr` | Same image actions and resources as `ecr.api`, with `aws:PrincipalAccount=${account}`. |
  | `logs` | `logs:CreateLogStream`, `logs:PutLogEvents` on `arn:aws:logs:${region}:${account}:log-group:<stack log groups>:*`. |
  | `secretsmanager` | Two statements, both deterministic (R4-B3). (1) `Allow` `secretsmanager:GetSecretValue`, `DescribeSecret` on `arn:aws:secretsmanager:${region}:${account}:secret:<declared names>-??????`, with `aws:PrincipalAccount=${account}`. (2) `Allow` `secretsmanager:GetSecretValue` on `arn:aws:secretsmanager:${region}:${account}:secret:rds!cluster-*`, with `aws:PrincipalAccount=${account}` and `ArnEquals aws:PrincipalArn` = [`${bootstrap_job_role_arn}`, `${restore_reader_role_arn}`]. Both role ARNs are deterministic, created in S5.1 (row 8 of the ordered list, before S3.3) and published in central metadata. The document never contains an XP-8 value, so the endpoint, which step 1 creates, depends on no step-1 output, and the pin is computed offline. The identity-side exact-ARN grant (S5.5) still narrows the bootstrap job to the one real secret. |
  | `sqs` | `sqs:SendMessage`, `ReceiveMessage`, `DeleteMessage`, `ChangeMessageVisibility`, `GetQueueAttributes`, `GetQueueUrl` on the seven deterministic queue ARNs. |
  | `kms` | `kms:Sign`, `GetPublicKey`, `Encrypt`, `Decrypt`, `GenerateDataKey` on the D-4 key ARNs from central metadata, with `aws:PrincipalAccount=${account}`. |
  | `sts` | Only `sts:GetCallerIdentity`, with `aws:PrincipalAccount=${account}`. Every other STS action is denied by omission. |
  | SES API (if V-12) | `ses:SendEmail`, `ses:SendRawEmail` on the SES identity ARN from the contract, with `aws:PrincipalAccount=${account}`. |

  Policy-pack path: `policy/guardrails.py::wildcard_iam_violations` (line
  487) inspects the endpoint `policy` field and must pass each rendered
  document unmodified. Where a wildcard is unavoidable
  (`ecr:GetAuthorizationToken` resource `*`, `-??????` suffixes,
  `rds!cluster-*`), S3.3 extends the pin mechanism of `policy/reviewed_iam.py`
  (m9):
  - **Identity key.** Today `_policy_identity` (lines 29-42) returns an
    identity only for `aws:iam/policy:Policy` (`type|name`) and
    `aws:iam/rolePolicy:RolePolicy` (`type|name|role`). S3.3 adds
    `aws:ec2/vpcEndpoint:VpcEndpoint` with the identity
    `aws:ec2/vpcEndpoint:VpcEndpoint|<serviceName>|<tags.Name>`. `serviceName`
    is a literal (for example `com.amazonaws.eu-central-1.secretsmanager`).
    `tags.Name` is the deterministic `build_resource_name` value, which
    contains the stack tag (`user-service-infrastructure-test-…` or
    `user-service-infrastructure-prod-…`; `scripts/poc_registry_plan.py`
    line 21 `PROJECT`). Each
    part must pass `_physical_name`-style literal checks, and an unknown
    value (the Pulumi unknown sentinel) returns no identity, so the pack fails
    closed. `vpcId` is unknown on first create and is not part of the key.
  - **Digests.** `policy/vilnacrm_guardrails.yaml` `reviewed_iam_documents`
    gets one key per endpoint per environment. Each key pins exactly one
    sha256 of `_canonical_document(policy)` for that environment's
    rendering, because account and region are rendered in. So TEST and PROD
    have different keys and different digests. `_ADDITIONAL_DOCUMENT_FIELDS`
    does not apply to endpoints.
  - **Governance.** The change is a reviewed governance change (CODEOWNERS
    plus Kravalg review), never a rule relaxation. A rendered document whose
    digest is not pinned fails the pack.
- **AD-13 ALB→task TLS (D-2, decided).**
  - TEST: `docs/poc-alb-target-tls-acceptance.md` (risk acceptance citing
    A-14) with a doc-marker test.
  - PROD, before gate 2: Caddy internal TLS on :8443 (S5.20), an HTTPS target
    group and an HTTPS health check (S3.5-A). Admission refuses a PROD stack
    whose target group protocol is HTTP.
- **AD-14 Non-root.** US runs as UID ≥1000 on :8080 (and :8443 in PROD), with
  the supervisor socket in `/srv/app/var/run`. USI drops `ALL` capabilities
  and sets the port.
- **AD-15 KMS app keys.** BI provides:
  - a JWT key (`RSA_4096`, `SIGN_VERIFY`);
  - a 2FA key (symmetric, encryption-context `user_id`);
  - the task-role grants.

  USI passes the key ARNs as plain environment values.
- **AD-15a Per-key grant table (D-4, R4-M8, m7).** No key policy has an
  `arn:aws:iam::<acct>:root` `kms:*` statement. Every principal is named. Each
  row is both a key-policy statement and, for IAM roles, a matching identity
  statement (S5.4; on a role S5.1 created, a reviewed amendment of its
  stack, AD-26 layer 6, R11-M1), because the BI permission boundaries also
  evaluate identity policies. `<r>` = `eu-central-1`, `<a>` = the account.

  | Key | Principal | Actions | Conditions |
  | --- | --- | --- | --- |
  | all three | BI apply role (key administrator) | `kms:Create*`, `Describe*`, `Enable*`, `List*`, `Put*`, `Update*`, `Revoke*`, `Disable*`, `Get*`, `TagResource`, `UntagResource`, `ScheduleKeyDeletion`, `CancelKeyDeletion` (no cryptographic action) | `aws:PrincipalAccount` = `<a>` |
  | all three | preview and drift roles `GitHubCi{Preview,Drift}-user-service-infrastructure-{env}` | `kms:DescribeKey`, `GetKeyPolicy`, `GetKeyRotationStatus`, `ListResourceTags` | none beyond the exact key ARN (m7: granted here, after the keys exist, not in S5.17) |
  | runtime | USI apply role | `kms:DescribeKey` | `kms:ViaService` ∈ {`logs.<r>.amazonaws.com`, `secretsmanager.<r>.amazonaws.com`, `sns.<r>.amazonaws.com`, `s3.<r>.amazonaws.com`} (A-28) |
  | runtime | ECS execution role | `kms:Decrypt` | `kms:ViaService=secretsmanager.<r>.amazonaws.com`; `kms:EncryptionContext:SecretARN` like `arn:aws:secretsmanager:<r>:<a>:secret:<declared names>-??????` |
  | runtime | app-rotation role (rotation and seed) | `kms:Decrypt`, `kms:GenerateDataKey` | `kms:ViaService=secretsmanager.<r>.amazonaws.com`; `kms:EncryptionContext:SecretARN` like the declared names |
  | runtime | `logs.<r>.amazonaws.com` (service) | `kms:Encrypt*`, `Decrypt*`, `ReEncrypt*`, `GenerateDataKey*`, `Describe*` | `ArnLike kms:EncryptionContext:aws:logs:arn` = `arn:aws:logs:<r>:<a>:log-group:<workload log group names>` (ECS web and worker, `/aws/ecs/containerinsights/<cluster>/performance`, `/aws/docdb/<cluster>/audit`, `/aws/docdb/<cluster>/profiler`, `/aws/lambda/<BI function names>`); `aws:SourceAccount` = `<a>` |
  | runtime | `delivery.logs.amazonaws.com` (service) | `kms:GenerateDataKey*`, `kms:Decrypt` | `aws:SourceAccount` = `<a>`; `aws:SourceArn` like `arn:aws:logs:<r>:<a>:*` (V-16) |
  | runtime | `cloudwatch.amazonaws.com`, `events.amazonaws.com` (services, SNS publish) | `kms:GenerateDataKey*`, `kms:Decrypt` | `aws:SourceAccount` = `<a>` |
  | JWT (RSA_4096, SIGN_VERIFY) | ECS task role | `kms:Sign`, `kms:GetPublicKey` | `kms:SigningAlgorithm=RSASSA_PKCS1_V1_5_SHA_256` on `Sign` |
  | 2FA (symmetric) | ECS task role | `kms:Encrypt`, `kms:Decrypt` | `ForAllValues:StringEquals kms:EncryptionContextKeys` = [`user_id`] and `Null kms:EncryptionContextKeys` = false |
  | runtime (TEST only) | TEST exercise role `GitHubCiExercise-user-service-infrastructure-test` (created by S5.1; this row's key-policy and identity statements are S5.4's, the role's other grants S5.23's) | `kms:Decrypt` | `kms:ViaService=s3.<r>.amazonaws.com`; `kms:EncryptionContext:aws:s3:arn` like `arn:aws:s3:::<flow-log bucket>/*` (reading flow-log objects, S4.6 step 12) |

  No row exists for the bootstrap-job, restore-reader, restore-operator,
  redeploy or recovery roles. The Container Insights performance log group,
  which ECS would otherwise auto-create without the CMK
  (`pulumi/app/compute.py` lines 213-217 enable `containerInsights`
  `enhanced`), is pre-created by USI (S1.8) with `kms_key_id` and retention,
  so D-4 holds for it too. The DocumentDB-managed secret uses the AWS key
  (A-05), and deleting a CMK-encrypted secret needs no KMS permission. The
  ECS execution role has no logs row: CloudWatch Logs encrypts with its own
  service principal, and the docs name no KMS permission for `PutLogEvents`
  (A-28). V-25 checks this live; the fallback is a reviewed row
  `kms:GenerateDataKey` with `kms:ViaService=logs.<r>.amazonaws.com` for the
  execution role.
- **AD-16 Recovery and admission modes (M-5, M-6, R4-M4; D-7 decided 2026-09-30).**
  - **Diagnostics:** parse the Pulumi event log into an allow-listed summary.
  - **Admission modes:** `first`, `rebuild-first`, `step2`, `resume`, `rollback-zero`
    (`stop`, `hold`, `start` phases), `policy-update`, `recovery-import`,
    `recovery-abandon`. S4.2, S4.9 and S4.3 own the admission functions; the
    runner routes to them (AD-24).
  - **Every recovery mutation is a saved plan through the classifier.**
    - `import`: the program runs with `import_` options for the listed
      fixed-name or retained resources. `preview --save-plan` must contain
      only `import` and `same` steps, and the imported URNs must equal
      `import-list.json` 1:1. Then `up --plan`.
    - `abandon` (TEST only): two saved plans.
      1. **Unprotect plan:** the program with `protect=False` on every
         manifest URN, `retain_on_delete=True` on every `retain` entry,
         DocumentDB `deletion_protection=False`, the manifest's final-snapshot
         setting, and each secret's `recovery_window_in_days` from its
         `secret_recovery_decision`. Its steps must be `update` or `same`
         only. The only AWS call it makes is `rds:ModifyDBCluster`
         (deletion protection); the other changes are state-only (V-24).
      2. **Removal plan:** the program in abandon mode renders only the
         registry graph. The comparison **does not use
         `find_destructive_steps`**, which returns only critical types
         (`scripts/pulumi_ci_guardrails.py` lines 115-125). Instead, every
         step's op must be `delete` or `same`. Any other op is refused:
         `update`, `replace`, `create-replacement`, `delete-replaced`,
         `discard`, `discard-replaced`, `remove-pending-replace`,
         `read-replacement`, `import-replacement`. The set of `delete` URNs,
         of every resource type, must equal the manifest's `delete` and
         `retain` entries 1:1, and the `same` URNs must equal the eleven
         registry resources. The classifier still runs, and its critical
         steps must be a subset of the manifest. Only then does `up --plan`
         run in `test-recovery`.
    - **Secrets:** each workload secret has one `secret_recovery_decision`:
      `retain` (the secret, its `SecretPolicy` and its `SecretRotation`
      stay; the rebuild imports them), or `schedule-deletion` with
      `recovery_window_days` 7–30. `force-delete` is refused. A re-created
      secret with a pending-deletion name must be restored (`RestoreSecret`)
      and imported, never force-deleted.
    - **Log buckets (non-empty):** the ALB access-log bucket and the flow-log
      bucket keep `force_destroy=false`. The manifest must mark each of
      them, and each sub-resource (ownership controls, public-access block,
      encryption, versioning, lifecycle, policy), `retain`. `delete` is
      refused, no object is deleted, and no empty-bucket step exists. Log
      data is never destroyed by abandon, and the public-access block and
      encryption are never removed from a retained bucket.
    - **DocumentDB:** `delete`, with the final snapshot
      `<stack>-docdb-final` (collision check: an existing snapshot of that
      name refuses the manifest) and a `data_loss_decision`. The managed
      secret goes with the cluster (A-27).
  - **Executing identity (R4-M4).** The BI role
    `GitHubCiRecovery-user-service-infrastructure-test` is assumable only by
    OIDC `sub` = `repo:VilnaCRM-Org/user-service-infrastructure:environment:test-recovery`
    on `main`. S5.7 grants it:
    - state: read and write of the TEST state bucket prefix, including
      `s3:DeleteObject` on the lock prefix (`.pulumi/locks/*`) only, and
      `kms:Decrypt`/`GenerateDataKey` on the existing state secrets-provider
      key (governance-owned);
    - update: `rds:ModifyDBCluster` on
      `cluster:user-service-infrastructure-test-docdb` only (the identifier of
      `scripts/poc_workload_topology.py` line 61);
    - delete: the complete API set that the pinned provider's delete path
      calls for each resource type of the hardened step-1 and step-2 graph
      (AD-25), except retained types. S4.10 derives the set
      (`recovery/delete-actions.json`) from the pinned `pulumi-aws` provider
      source per type, including drain and detach calls
      before the delete (for example `ecs:UpdateService` to desired 0 before
      `ecs:DeleteService`, `ec2:DeleteRoute`, `sns:SetTopicAttributes` for
      a topic policy). Each action is scoped to the deterministic name/ARN
      pattern of the TEST stack or, where the API supports it,
      `aws:ResourceTag/Environment=test` and
      `aws:ResourceTag/Project=user-service-infrastructure`
      (`scripts/poc_registry_plan.py` lines 21 and 57). V-26 checks the set
      live. Examples: `ecs:DeleteService`, `ecs:DeregisterTaskDefinition`,
      `ecs:DeleteCluster`; `elasticloadbalancing:DeleteLoadBalancer`,
      `DeleteTargetGroup`, `DeleteListener`; `ec2:DeleteSecurityGroup`,
      `RevokeSecurityGroup*`, `DeleteVpcEndpoints`, `DeleteFlowLogs`,
      `DeleteSubnet`, `DeleteRouteTable`, `DisassociateRouteTable`,
      `DeleteNatGateway`, `ReleaseAddress`, `DetachInternetGateway`,
      `DeleteInternetGateway`, `DeleteVpc`; `rds:DeleteDBCluster`
      (+ `CreateDBClusterSnapshot` for the final snapshot),
      `DeleteDBInstance`, `DeleteDBSubnetGroup`,
      `DeleteDBClusterParameterGroup`; `elasticache:DeleteReplicationGroup`,
      `DeleteUser`, `DeleteUserGroup`, `DeleteCacheSubnetGroup`;
      `sqs:DeleteQueue`; `sns:DeleteTopic`; `events:RemoveTargets`,
      `DeleteRule`; `cloudwatch:DeleteAlarms`; `logs:DeleteLogGroup`,
      `logs:DeleteLogDelivery`; `application-autoscaling:DeregisterScalableTarget`,
      `DeleteScalingPolicy`, `DeleteScheduledAction`;
      `ecr:DeleteLifecyclePolicy`; `secretsmanager:DeleteSecret` (with
      `secretsmanager:RecoveryWindowInDays` ≥ 7 and
      `secretsmanager:ForceDeleteWithoutRecovery` = false, V-15),
      `RestoreSecret`, `DescribeSecret`, `CancelRotateSecret`,
      `DeleteResourcePolicy` on the declared-name patterns and on
      `secret:rds!cluster-*` (the managed-secret policy is deleted before its
      cluster); the Invocation delete makes no call (V-18);
    - read: the S5.17 read set, for the export and the import.
    - No `s3:DeleteBucket`, no `s3:DeleteObject*` outside the state lock
      prefix, no `s3:PutBucketPublicAccessBlock` or `s3:DeleteBucketPolicy`
      on the log buckets, and no `kms:*` key-management action (the log
      buckets are always retained).
    An offline test compares the per-type action map (from the provider
    source) with the AD-25 graph and with the S5.7 simulator matrix. A graph
    type without a mapped action set fails.
  - **Approval: @Kravalg specifically (R4-M4, m11).**
    - The `test-recovery` and `prod-recovery` environments use USI's own
      `scripts/_github_repository_controls.py::protected_reviewer_environment_payload`
      (line 185; the same payload as BI @debd88b lines 308-319): reviewers =
      [Kravalg's user ID] only, `prevent_self_review: true`,
      `can_admins_bypass: false`, main-only branch policy. USI's
      `scripts/configure_github_repository_controls.py` applies them (both
      by S5.21, m3). This matches the AGENTS.md contract "sole environment
      reviewer Kravalg" (AGENTS.md lines 157-159).
    - In the run, `scripts/poc_workload_recovery.py abandon` refuses unless
      `GET /repos/{owner}/{repo}/actions/runs/{run_id}/approvals` shows an
      `approved` state for environment `test-recovery` by Kravalg's user ID,
      and the requester (`github.triggering_actor`) is someone else.
    - The manifest PR must be approved by Kravalg: the status check
      `abandon-manifest-approval` (created in S4.3) reads the PR reviews on
      the head SHA and needs an `APPROVED` review by Kravalg's user ID.
      S5.22 (after S4.3) makes it a required check in USI's own ruleset
      (m3). The ruleset's required checks are branch-wide (the `main`
      ruleset has only a `ref_name` condition; USI
      `scripts/_github_repository_controls.py` lines 46-60 and the ruleset
      payload), so the check reports success without further review on a PR
      that does not change `recovery/abandon-manifest.json`. **Issuer pin
      (m2):** today `_harden_status_check` (USI lines 64-78) and
      `required_status_checks_rule` (lines 46-60) pin only the `Governance
      Promotion` context to an App; every other context, including a new
      one, is issuer-less, so any integration could post it. S5.22 adds its
      own pinning code: the `abandon-manifest-approval` context is emitted
      with `integration_id` = the GitHub Actions App ID, `_harden_status_check`
      sets it and refuses an existing entry with another issuer, and
      `ruleset_verification_blockers` (lines 385-409) reports a missing or
      different issuer. A spoofing test (an entry without `integration_id`,
      or with another App's ID) fails the verification.
      CODEOWNERS (`* @Kravalg @dmytrocraft`, USI `.github/CODEOWNERS`) is not
      enough on its own, because either owner can approve.
  - **Rule changes (D-7, decided 2026-09-30; unconditional):**
    - AGENTS.md rule 14 gains: "14a. The only exception is the TEST-only
      `abandon` of the governance recovery command
      (`.github/workflows/recovery.yml`, environment `test-recovery`, sole
      reviewer Kravalg), whose saved removal plan contains only `delete` and
      `same` steps and whose `delete` URNs equal the Kravalg-approved
      `abandon-manifest.json` 1:1. Labels still never authorize."
    - `docs/poc-workload-recovery.md` gains the abandon and rebuild runbook
      section.
  - **Rehearsal placement.** The abandon rehearsal runs at the **end** of
    the S4.6 campaign (step 19), after every other live item (steps 1–17)
    has its evidence. Step 18 prepares it: the Kravalg-approved manifest and
    the BI ENI detach. Then step 20 rebuilds the stack (recovery import of
    retained resources (import receipt) → `rebuild-first` → XP-8 refresh for the new
    subnet IDs, SG ID and managed-secret ARN (items 1-4; R12-m3) → the
    S5.5 and S5.18b re-attaches → S5.5 re-run → step 2 → accepted receipt → clean
    drift). The receipt (step 21) is assembled from the rebuilt stack. So
    the abandon never removes the stack before steps 14–17 run.
  - **BI ENIs before a removal plan.** The bootstrap-job and restore-reader
    Lambdas are attached to the USI subnets and bootstrap-job SG (S5.5,
    S5.18b), and their ENIs block the SG and subnet deletes. Before the
    removal plan, two reviewed BI stack amendments, one at a time, detach
    them: S5.5's function-role stack amendment the bootstrap job, then
    S5.18b's restore stack amendment the reader (R12-m3; empty `VpcConfig`
    only; the execution roles keep the network-interface grant, because
    Lambda deletes its ENIs with those roles, AD-26 layer 6),
    and a read-only `DescribeNetworkInterfaces` check, polled for up to 45
    minutes, shows no Lambda ENI and no ENI owned by another service in
    those subnets. STOP if an ENI remains. The rebuild re-attaches both
    (S5.5, then S5.18b) through the refreshed XP-8 metadata, whose subnet
    and SG IDs are new because the abandon deleted them.
  - **Registry capture:** `scripts/poc_registry_plan.py` accepts the registry
    baseline after a verified abandon receipt. S4.3 issues the receipt and
    makes this change, which is the only change to that file in this plan
    (R6-m13); S4.11 and every other story leave the file unchanged.
  - **Rebuild variant (after an abandon).** `recovery-import` renders the
    registry graph plus exactly the abandon receipt's `retain` set with
    `import_` IDs; its plan has only `import` and `same` steps. The step-1
    checker then accepts a retained declared secret with one `AWSCURRENT`
    and rotation enabled (as recorded in the abandon receipt) instead of
    zero versions. The step-2 admission's created set is the step-2 set minus
    the imported URNs (a retained secret's `SecretPolicy` and
    `SecretRotation`); its seed Invocation is created again and returns
    `noop` (AD-06). A `schedule-deletion` secret must be restored
    (`RestoreSecret`, by the recovery role) and imported the same way; it is
    never force-deleted.
  - **Recovery command:** `.github/workflows/recovery.yml` (main-only,
    `workflow_dispatch`, environment `test-recovery`; `prod-recovery` for
    PROD without `abandon`) runs `scripts/poc_workload_recovery.py`, which has
    these subcommands:
    - `export` (writes an export receipt, `cause: export`). It reads the
      checkpoint with a **private, hash-only reader** under the recovery
      role (R6-m8), in `scripts/poc_workload_recovery.py`: S3 `HeadObject`
      and `GetObject` of the checkpoint key plus the lock listing. It
      records only `{version, etag, sha256}`, the pending-operation count
      and whether a lock exists. It tolerates a non-empty
      `pending_operations`, a present lock and rows marked `delete` or
      `pendingReplacement`, which a cancelled apply leaves behind and which
      the trusted observer refuses (`scripts/poc_backend_observer.py` lines
      366 and 391, and its empty lock-listing check). It never emits
      resource inputs or outputs. `clear-pending` uses the same reader for
      its before-hash. Admission never uses it: `resume` still captures
      through the trusted observer after `release-lock` and
      `clear-pending`;
    - `release-lock` (deletes only the lock object; the checkpoint sha256
      before and after must be equal, else it refuses and writes nothing);
    - `clear-pending` (rewrites the checkpoint without its pending
      operations, then writes an **export receipt** for the new checkpoint
      with `cause: clear-pending` and `predecessor` = the prior failed or
      export receipt's ID and checkpoint sha256; R5-M2);
    - `import` (from `import-list.json`; writes an import receipt);
    - `abandon` (TEST only; refused in `prod-recovery`; writes the abandon
      receipt).

    Every subcommand produces evidence JSON. **Every subcommand that writes
    the checkpoint also writes a receipt bound to the new checkpoint**
    (AD-24), so the resume anchor never goes stale after a recovery step: a
    `clear-pending` without its receipt leaves the live checkpoint unequal to
    every receipt, and `resume` is refused.
  - CODEOWNERS entries for these USI files are added in USI (S4.3). BI
    provides the role grants (S5.7, S5.19); USI's repository controls provide
    the environments (S5.21).
  - **Runtime guard:** the runner resolves `admission.<env>` from the
    installed `main` contract at the trusted controller checkout.
    Mismatch, missing or unreadable means refuse.
- **AD-17 Timing.** The runner records the OIDC issuance time and the
  observation end time in the evidence. The budget test compares them with
  the FR-24 margin bounds (process ≤ 3000 s, window ≤ 3300 s).
- **AD-18 Two-step first workload (FR-34, M-12).**
  1. **Step 1 (saved plan, `workload_step: 1`, runner mode `first`):**
     network (including the bootstrap-job SG, endpoints and flow logs), data
     (DocumentDB-managed password, Redis IAM and `default` users), secret
     metadata, KMS-encrypted log groups, observability, ECS task definitions
     and services at `initial_service_scale=0`. No seed, rotation, secret
     policy, autoscaling target or scheduled action. The time is measured
     (FR-24). The runner's result inspection (S4.10 checker) passes, and the
     runner issues the authenticated **step-1 result receipt** (AD-24).
  2. **BI gate (XP-8, S5.5):** a BI metadata PR supplies the subnet IDs, the
     bootstrap-job SG ID and the DocumentDB-managed secret ARN. BI applies the
     exact-ARN grant and the VPC attachment. S5.5 creates the `$external`
     user and emits its evidence receipt.
  3. **Step 2 (saved plan, `workload_step: 2`, runner mode `step2`):** seed
     Invocations → `SecretRotation`s → `SecretPolicy`s → autoscaling targets
     and policies → TEST `ScheduledAction`s → one-time start actions (AD-06
     order, AD-10). Admission is **create-only**: every plan step is `create`
     or `same`; the created URNs equal the step-2 set; no `update`, `replace`
     or `delete` of any step-1 URN. Admission refuses step 2 without the
     step-1 receipt (its checkpoint is the anchor), the S5.5 receipt and the
     XP-8 metadata in the installed `main` central metadata.
  4. **Step-2 health observation (m13, R6-m3, R6-m6):** a separate
     read-only job, not the apply job. `self-deploy.yml` gains
     `test_workload_observation` (S4.13): environment `test-preview`;
     `needs: [preflight, poc_prepare_source, test_apply,
     test_apply_receipt]`, so the success receipt it binds to is published
     first; its `if` requires `needs.test_apply.result == 'success'`,
     `needs.test_apply_receipt.result == 'success'` and a TEST
     workload-phase `up` whose operation creates a start or stop action
     (the `poc_prepare_source` output `workload_observation`). It waits
     until the new action's `at()` time, only then requests preview-role
     credentials, and records, for a start action, every service
     `steadyState` with running = desired ≥ 1, all targets `healthy`, and
     the app health endpoint green for DocumentDB (MONGODB-AWS) and Redis
     (IAM); for a stop action, every service with running = desired = 0
     and each target at `min = max = 0`. The conditions must hold within 30
     min after the later of the `at()` time and the job's start. At the end
     it captures the checkpoint through the trusted backend observer
     (`backend.capture_backend(source, operation="plan")`, preview role)
     and writes its `{version, etag, sha256}`, with the same-run
     `test_apply_receipt` receipt ID, run ID and run attempt, into the
     observation artifact, as `test_registry_observation` does for the
     registry (`self-deploy.yml` lines 570-657). **Pre-credential
     admission (R7-m7):** like that job (lines 601-641), it checks out
     `.trusted`, installs the trusted runtime, runs
     `poc_workload_observation.py admit` (job name, same-run source
     artifact, `up` request for the job's environment, `base_sha`, current
     review; the pattern of `poc_registry_completion.admit`), waits with no
     credential, runs `admit` again before `load-aws-ci-env` and again
     immediately before `configure-aws-credentials`, then observes and
     uploads. `verify_reviewed_source` requires the pull request to be
     `OPEN` (`scripts/reviewed_source_admission.py` line 128), so a merge or
     close during the wait fails the post-wait `admit` before any
     credential; the job fails and nothing is published (a STOP at S4.6
     step 7; the next admitted start plan repeats the observation). A
     sibling workflow test pins the sequence with the change matrix of
     `tests/pulumi/test_ci_guardrails.py` lines 397-409. `test-preview` is a Kravalg-reviewed
     environment, so a late approval only delays the observation; the
     health states are current states, not events. Its `timeout-minutes`
     covers the 120-min upper bound of the `start_at` window plus the
     30-min observation, below GitHub's 360-min job limit. It runs no
     Pulumi command and holds no state lock, so it uses its own concurrency
     group `workload-observation-${{ github.repository }}-test` and does not
     hold `pulumi-state-…-test-test` while it waits. The observer requires
     an empty lock listing at the start and the end of a capture
     (`scripts/poc_backend_observer.py` lines 452 and 470), and
     `test_workload_drift` or a scheduled drift job may hold the lock, so
     the capture lists the lock prefix first and retries every 30 s while a
     lock exists, inside the 30-min observation window; it never removes a
     lock. A lock that outlasts the window fails the job with
     `workload-observation-lock-timeout`, a STOP at S4.6 step 7 (R7-m8). The apply job's 3300 s
     process timeout and 70-min budget and the FR-24 bounds are unchanged.
     A failure is STOP (S4.6 step 7). On success, the `governance-evidence`
     job `test_workload_acceptance` (`needs: [preflight,
     poc_prepare_source, test_apply, test_apply_receipt,
     test_workload_observation]`; its `if` requires
     `needs.test_apply.result == 'success'`,
     `needs.test_workload_observation.result == 'success'` and a TEST
     workload-phase `up`) holds no AWS
     credentials. It verifies the same-run observation artifact (upload
     digest and file sha256, as `test_registry_proof` verifies the registry
     observation) and, **bound to the same run (audit F6)**, that the
     artifact's checkpoint equals the checkpoint of the receipt this run's
     `test_apply_receipt` published (same run ID and attempt) and that this
     receipt is still the stack's latest receipt; otherwise it fails and
     publishes nothing (STOP). It then publishes, through the S4.11 receipt
     library (R7-m6), the **accepted-workload receipt** (AD-24) for the
     first passing start observation of a lineage, and otherwise an
     authenticated `poc-workload-observation-v1` record (kind `start` or
     `stop`) bound to that success receipt.
- **AD-19 Rollback (FR-30, m4).**
  - **First deployment** (no accepted-workload receipt yet, or the first
    accepted release is the only one): there is no prior release to return
    to. Rollback means stop serving: the create-only `rollback-zero` mode
    (AD-10) scales both services to 0. The stack stays for `resume`, recovery
    import or TEST `abandon`. The step-2 STOP rule uses this mode. Before
    the first accepted receipt this `rollback-zero` routes
    `pre-acceptance`, because the route comes from the authenticated
    receipt lineage (AD-24, R7-m5), so it runs no drift job and does not
    go red for a missing accepted receipt.
  - **Later releases** (after an accepted-workload receipt with a clean-drift
    result): a saved-plan re-apply of the previous accepted release (image
    digests, task-definition inputs and the original registry anchor;
    existing contract rule). The release/rollback secret checker accepts
    rotation-caused version changes (AD-25).
  - The ECS deployment circuit breaker handles in-deploy rollback in both
    cases.
  - A rollback to an unaccepted release is refused. A release rollback
    before any accepted-workload receipt is refused.
  - Restore (R6-m10): a **point-in-time restore** of the TEST cluster
    (`RestoreDBClusterToPointInTime` with `UseLatestRestorableTime: true`,
    source `user-service-infrastructure-test-docdb`) to
    `<stack>-docdb-restore-rehearsal` under the S5.18a operator role,
    switched to a managed primary password (`ModifyDBCluster`), read by the
    S5.18b reader, then deleted; a gate for PROD.
  - **Recovery targets: user decision D-14 (dated 2026-09-30,
    `decisions.md`), not planning defaults (R6-m1).** DocumentDB, the only
    stateful store that needs a restore:
    - **RPO ≤ 1 hour** (D-14) inside the backup retention window
      (`documentDbBackupRetentionDays`, default 7 days,
      `pulumi/app/environment.py` lines 677-681). Evidence: the S4.8 R-1
      point-in-time restore itself. The source cluster's
      `LatestRestorableTime` is read (`DescribeDBClusters`) immediately
      before the request, and the CloudTrail
      `RestoreDBClusterToPointInTime` event (metadata only) shows
      `useLatestRestorableTime: true`, so that time is the achieved
      recovery point. The recorded RPO is the request time minus the
      achieved recovery point (≤ 3600 s).
    - **RTO ≤ 24 hours** (D-14): from the restore request to the reader's
      document-count sample on the restored cluster (S4.8 R-1 measures
      it).
    - Redis holds cache and lockout state only; it is rebuilt, not
      restored, so no RPO applies. Its snapshots stay as configured.
    - A measured value above a target is a STOP at gate 2a: the user
      decides to accept it or to change the design; a default never
      accepts it.
- **AD-20 SQS and SES (FR-03).** Keep the credential-free DSNs (R-19). Add a
  regression test that rejects userinfo and keys. The BI task-role grants
  scope the seven queues and the SES identity.
- **AD-21 Two-gate admission (FR-31, D-6).**
  - The contract carries `admission: {test, prod}`.
  - The hard-stop test becomes:
    - `phase == "registry"`; or
    - gate 1: `phase == "workload"`, `admission.test`, every gate-1 story
      marker present, the BI prerequisite markers present, the R-02
      observation receipt present, the XP-9 … XP-13 prerequisite markers
      present (XP-9 including the packaged TEST capability `enabled` in
      BI, R9-m1; XP-10 as the gateway-supplied certificate ARN pinned in
      the TEST contract, user decision D-15; XP-11 including the TEST
      Preview and Apply workload-observation reads, their seed boundary
      amendment and the approving BI and seed PRs, with no deny and no
      seed guard narrowed; AD-26, R9-M1, R10-M1), the XP-18 marker (BI's
      reviewed retirement of `Issue215CutoverSessions` on the TEST Apply
      role, with the read-back showing it absent; R12-M1),
      and every applicable decision marked `resolved` with a date in
      `prd.md` §6 and `decisions.md` (defaults do not count); or
    - gate 2a: every gate-1 condition, plus `admission.prod: "preview"`,
      plus the campaign-complete TEST acceptance receipt (PRD §3.3), plus
      the restore item (S4.8, measured against D-14), XP-14, XP-15 and XP-16 (R8-m6; since revision 12 XP-16 is S5.1's PROD ECS boundaries, verified live by S4.7, R12-M2), XP-18's PROD Apply read-back still showing no deny-all hold (R12-M1), and S5.24a's PROD Preview and Apply workload-observation reads (AD-26, R9-M1). It admits only the PROD `plan`
      (`prod_preview` job), which produces the P-1 PROD-shaped preview
      evidence (FR-19); or
    - gate 2b: every gate-2a condition, plus `admission.prod: true`, plus the
      P-1 item in the receipt, which is then complete and schema-valid with
      no placeholder, plus **scheduled workload drift detection for the
      `prod` workload stack** (R6-m11): S4.17 merged, and two uploaded
      `poc-workload-scheduled-drift-result-v1` records linked in the
      receipt, each with its run link, `artifact_id` and
      `artifact_sha256` (R8-M1): a clean scheduled run on the TEST
      workload stack with `status: checked` (R7-m1; a `before-acceptance`
      record never counts as the TEST item), and a PROD record with
      `status: before-acceptance` and `null` receipt fields from a
      scheduled run after the gate-2a PR that first set `poc-prod.json`
      `phase: workload` (R8-m1; the S4.17 jobs are data-driven, and a
      `registry-phase` record never counts). PROD cannot apply before gate
      2b, so no PROD success receipt exists and a PROD `checked` record
      cannot occur (R9-n1). Because that record runs no PROD image,
      capability or certificate comparison, gate 2b also links the
      S5.24b PROD Drift simulator evidence (AD-26). PROD is never admitted without scheduled
      drift detection, and no risk acceptance replaces this condition.
  - S4.15 owns the offline part: the acceptance-receipt schema and validator
    (`schemas/poc-test-acceptance-receipt-v1.schema.json`,
    `test_poc_acceptance_receipt.py`, with `campaign` and `complete`
    validation levels) and the two-gate rewrite of
    `test_workload_phase_hard_stop.py`. The README text and the phase flip
    are the S4.6 step-1 PR.
  - The README "Workload phase hard stop" is rewritten accordingly, listing
    what D-6 relaxes and keeps (PRD §6.1). The change is governance-reviewed
    and needs `@Kravalg` approval of the source PR.
- **AD-22 Legacy path (FR-29).** `UserServiceStack` managed mode (the
  non-`RuntimeSecrets` path) raises for `test` and `prod`. The
  `_create_runtime_secrets` and `_persist_url` fallbacks are removed or made
  unreachable for shared stacks. Dev and preview placeholders are unchanged.
- **AD-23 Drift allow-list (FR-32, M-1).** A closed list in the contract
  (`drift.out_of_band_fields`), keyed by Pulumi resource type. Nothing else may
  change outside Pulumi. The list has two parts (audit):
  - `ignore_fields`: the input fields the program ignores. S1.11 compares
    this part both ways with the program's `ignore_changes` (ECS
    `desiredCount`; target `minCapacity`, `maxCapacity`).
  - `refresh_only_fields`: output fields that refresh may change with no
    program diff (DocumentDB `masterUserSecrets[*].secretStatus`). Only the
    drift reducer reads this part, together with the `scaling.consumed`
    removal rule for one-time actions. The program has no `ignore_changes`
    for it.

  | Resource type | Fields allowed to change outside Pulumi | Why | Program handling |
  | --- | --- | --- | --- |
  | `aws:ecs/service:Service` | `desiredCount` | Application Auto Scaling owns it (FR-11, FR-12). | `ignore_changes=["desiredCount"]` |
  | `aws:appautoscaling/target:Target` | `minCapacity`, `maxCapacity` | The TEST night and weekend actions (FR-14c) and the one-time start and stop actions (AD-10, both environments) change them. `suspendedState` is managed by Pulumi (`rollback-zero`). | `ignore_changes=["minCapacity","maxCapacity"]` |
  | `aws:appautoscaling/scheduledAction:ScheduledAction` named `*-start-*` or `*-stop-*` | none by default. If V-23(c) shows that AWS removes a fired one-time action, a reviewed contract PR lists it in `scaling.consumed`, the program stops rendering it, and the drift check accepts a refresh-time removal of exactly the listed names (AD-10). | V-23 | not rendered once consumed |
  | `aws:docdb/cluster:Cluster` | `masterUserSecrets[*].secretStatus` (`refresh_only_fields`) | Managed rotation changes the status. These are outputs, not inputs, so refresh may change state without a diff. | none (output) |
  | `aws:elasticache/user:User`, `aws:elasticache/userGroup:UserGroup` | none | IAM auth removed the rotation Lambda that used to change passwords and access strings. | none |
  | `aws:secretsmanager/secret:Secret`, `SecretRotation`, `SecretPolicy` | none (version stages are not Pulumi state) | Rotation changes versions, not these resources. | none |
  | `aws:cloudwatch/logGroup:LogGroup` | none | `kms_key_id` is managed by Pulumi (D-4). | none |

  **Where the FR-32 check runs (R5-M1).** On the executed workload drift
  path only, never in the unexecuted `scripts/run_pulumi_drift_check.py`:
  - **Dispatch (R6-m4).** Today the runner's drift call would reach
    `run_pulumi_command._dispatch_command("drift", …)` (runner line 202).
    Its `_run_regular_command` path (lines 816-830) passes no plan path
    (`_required_plan_path`, `scripts/_pulumi_command_support.py` lines
    159-162, raises for any invocation with a plan flag) and captures no
    JSON, and the runner's capture would ask the trusted observer for
    operation `drift`, which `_target` refuses
    (`scripts/poc_backend_observer.py` lines 181-185 accept only `plan` and
    `up-plan`). S4.13 therefore reuses the registry plan-plus-gate pattern
    (`scripts/poc_registry_runner.py` line 344 maps `drift` to operation
    `plan`; line 364 dispatches that operation). For a workload `drift`
    request the runner captures with operation `plan` (preview role) and
    calls `_dispatch_command("plan", …)`. That branch (`_run_plan_command`,
    lines 592-639) supplies the private plan path, writes the `--json`
    preview of `PULUMI_INVOCATIONS["plan"]` (`preview --json --refresh
    --save-plan`, support lines 52-57, plus `--show-sames` because a gate
    is set, lines 180-181) and calls the runner's gate on every completed
    plan that passes the shared safe-preview check. The workload drift gate runs `validate_drift` and raises with the
    drifted field named. The `plan` invocation has no
    `--expect-no-changes`, so a drifted plan still exits 0 and reaches the
    gate, which names the field; a gate failure fails the command. **Kept
    exception (audit F8):** `_run_plan_command` calls the shared
    `_validate_safe_preview` (lines 611-613; defined at 483-510) before the
    gate (lines 614-617), so a drift whose refresh plans a replace or
    delete of a protected resource fails closed with the safe-preview
    message, without the field named. The order stays: the safe-preview
    check is the protected-destruction guard of every plan path (registry
    drift and `test_preview` included), and moving a workload gate in front
    of it would change that shared guard only to improve a message; the
    drift is still detected and the command still fails.
    No new `PULUMI_INVOCATIONS` entry and no new `_dispatch_command` branch
    are needed, and the baseline `drift` entry is unchanged. The drift plan
    stays in the worker's private area: the worker copies artifacts to
    `/public` only for `plan` jobs (worker lines 128-132).
  - **Reducer.** `scripts/poc_workload_reconciliation.py` (the existing
    no-change reducer, lines 224-245 `validate_no_change`) gains
    `validate_drift(preview, *, saved_plan, prior_resources, allowed)`: the
    same checks, except that a step's refreshed `oldState`/`newState` may
    differ from the authenticated prior checkpoint row (the checkpoint of the
    latest success receipt, AD-24) **only** at the AD-23 field paths of that
    row's type (inputs and outputs), plus a refresh-time removal of exactly
    the `scaling.consumed` action URNs. Any other difference fails with the
    field named in the sanitized summary (FR-20 allow-list).
  - **Role and job (R6-M1).** The **preview** role produces the gate-2
    clean-drift evidence: the new `self-deploy.yml` job
    `test_workload_drift` (S4.13) assumes `aws-preview-role-arn`, as the
    registry job does at line 546
    (`GitHubCiPreview-user-service-infrastructure-test`, read set S5.17
    plus the S5.4 key read), and S4.14's `prod_workload_drift` assumes the
    PROD preview role. The registry job `test_post_apply_drift` is not
    changed, so the registry chain `test_post_apply_drift` →
    `test_registry_observation` → `test_registry_proof` →
    `test_registry_dispatch` (`needs` at lines 578-581, 664-667 and
    726-730) never depends on a workload job. The drift role stays on the
    scheduled paths (the baseline one and S4.17).
  - **Scheduled drift (S4.13).** `scheduled-drift.yml` runs the baseline
    program, which renders no workload, so for a workload checkpoint it
    would propose deleting every workload resource and has no receipt to
    check. The baseline therefore excludes a workload-phase stack from
    `make test-drift`, **per stack (R7-m2)**: S4.13 excludes stack `test`
    only, when the installed `main` `poc-test.json` has `phase: workload`;
    S4.14 excludes stack `prod` only when the installed `main`
    `poc-prod.json` exists and has `phase: workload`, so a missing file
    (before XP-14) or `phase: registry` keeps the baseline running for
    `prod`. The exclusion sits in the
    `drift` branch of `run_pulumi_command.py` only (not in
    `_configured_stack_names`, line 84, which `preview`, `plan` and `up-plan`
    share). It prints the recorded reason `workload-drift-routed-to-runner`
    as a notice. When every configured stack is excluded, the command
    exits 0 with that notice; today an empty stack list returns 1 (lines
    850-856), which would fail the nightly job. `specs/poc-workload-runner.md`
    records the exclusion. Workload drift runs through the worker with an
    accepted receipt (AD-24) and, for scheduled detection, through S4.17
    (R6-m11), a gate-2b precondition. **Observation, not changed here:** the
    baseline program also renders none of the eleven registry resources, so
    the same reasoning applies to a `phase: registry` TEST stack. The
    registry owner decides that case, and this plan records it.
  - **Owner.** `scripts/poc_workload_reconciliation.py` is a C-contract file
    (§4): S4.10 makes the M5 allowances below, then S4.13 adds
    `validate_drift`, and S4.14 replaces its TEST-only `PREFIX` and `ROOT`
    imports from `poc_registry_plan` (line 15, used at lines 92 and 104)
    with the stack's own prefix (R6-m5).

  **Checkpoint fields that Pulumi stores (R5-M5).** Pulumi records
  `ignoreChanges` on checkpoint rows and plan goals, and, after an unprotect
  plan, `retainOnDelete` on checkpoint rows (`scripts/poc_registry_plan.py`
  lists `ignoreChanges` in `GOAL_FIELDS`, lines 74-78, and both fields in
  `STATE_FIELDS`, lines 79-86). Today
  `scripts/poc_workload_reconciliation.py` rejects any state row with either
  field (`UNSAFE_STATE`, lines 39 and 45, checked at line 95), which
  `scripts/poc_workload_secret_result.py` (lines 71 and 212) and
  `scripts/poc_gateway_backend.py` (line 40) reuse through `_inventory`, and
  `scripts/poc_workload_topology.py` rejects `ignoreChanges` on a create goal
  (lines 321-326) and any `UNSAFE_STATE` field on a create step's
  `newState` (`_validate_workload_step`, lines 1114-1115). S4.10 changes both
  files, as a recorded, deliberate narrow change: a row or goal may carry `ignoreChanges` only
  when it equals the AD-23 list for its type (`["desiredCount"]` on
  `aws:ecs/service:Service`, `["minCapacity","maxCapacity"]` on
  `aws:appautoscaling/target:Target`); `retainOnDelete: true` is accepted
  only on the abandon path (`_inventory(…, abandon_retain=<manifest retain
  URNs>)`, called by S4.2/S4.3) and only for manifest `retain` URNs. Every
  other occurrence still fails.

  **`importID` after a recovery import (R6-m12, V-27).** The rebuild imports
  retained resources with the `import_` option (AD-16), and Pulumi may
  persist `importID` on those checkpoint rows. `UNSAFE_STATE` rejects it
  (reconciliation line 37, checked at line 95), and so does the registry
  `_state` (`scripts/poc_registry_plan.py` line 312). V-27 reads the pinned
  engine source first (S4.10, like V-24). If `importID` persists, S4.10
  accepts it only on rows whose URN the authenticated import receipt lists
  (`_inventory(…, imported=<import receipt URNs>)`, used by the
  workload-aware capture); every other occurrence still fails. The registry
  `_state` rule stays unchanged, because the import list never contains a
  registry resource. If `importID` does not persist, nothing changes.

  **Workload-aware capture (audit).** A third rejection site sits on every
  capture: `scripts/poc_registry_plan.py::_state` (lines 297-324) rejects both
  fields, and `_prior` (lines 365-376) requires every URN to be a registry
  URN. It runs through `poc_registry_runner._capture` (lines 254-258), which
  `poc_workload_runner._capture` (line 41) and
  `poc_workload_admission.inspect_registry` (line 150) call. So any
  checkpoint that holds workload resources fails before the mode → anchor
  table is consulted. S4.11 (C-runner and C-contract; it already edits both
  callers) adds a workload-aware capture: it reads the checkpoint through
  `backend.capture_backend`, checks the registry rows with the registry
  `_state` rules and the workload rows with the S4.10 `_inventory`
  allowance, and binds the result to the mode's anchor. `first` keeps
  today's registry-only capture. S4.11 does not change
  `poc_registry_plan.py`, because the registry phase still needs its closed
  rules; the only change to that file in this plan is S4.3's post-abandon
  baseline acceptance (AD-16, R6-m13).

  Tests: every `ignore_changes` in the program is on the list (N: an extra
  field fails; S1.11); the drift reducer fails when a refresh changes an
  unlisted field and passes when only listed fields changed (S4.13); the
  reconciliation and topology checks accept exactly the AD-23
  `ignoreChanges` and the abandon-path `retainOnDelete`, and refuse any
  other value (S4.10). V-13 confirms that the `plan` invocation
  (`preview --json --refresh --save-plan --show-sames`) emits the refreshed
  per-step states the reducer reads, and that a refresh which changes only
  listed fields yields only `same` steps (R6-m4).

- **AD-24 Runner lifecycle (FR-35, R4-B2).** The installed path at `1ebbd09`
  admits only a first TEST apply, in four places:
  - **Runner** (`scripts/poc_workload_runner.py`): `_capture` requires the
    checkpoint to equal `observation.anchor.checkpoint` (lines 44-47,
    `workload-checkpoint-binding`); `_gate` calls only
    `topology.admit_first_workload_plan` (line 61) for stack `test` only
    (line 53); `execute` refuses `drift` (line 154,
    `workload-accepted-state-receipt-required`) and requires the gateway
    certificate parameter (lines 170-176; S4.14 replaces this rule with
    `workload-certificate-arn-required`, user decision D-15, AD-26).
  - **Admission observation** (`scripts/poc_workload_admission.py`):
    `inspect_registry` (lines 150-166), called by `observe_workload` (lines
    464-475) for every command, requires the live checkpoint to hold exactly
    the registry resources (`workload-completed-registry-required`) and to
    equal the registry receipt checkpoint
    (`workload-registry-checkpoint-changed`).
  - **Worker** (`scripts/service_execution_worker.py`): `JOBS` and `ACCOUNTS`
    (lines 25-30) are TEST-only; the source binding requires
    `target_environment == "test"` (lines 90-94); a workload contract admits
    only `plan` and `up-plan` (line 99, `workload-drift-not-enabled`; test
    `tests/unit/test_service_execution_worker.py:166`; docstring line 5).
  - **Workflow** (`.github/workflows/self-deploy.yml`): only TEST jobs exist
    (`test_preview`, `test_destructive_diff`, `test_apply`,
    `test_post_apply_drift` and the three `test_registry_*` jobs), and the
    source route refuses every target except `test` (lines 62 and 79-86).
  - **Docs and tests pin it:** `specs/poc-workload-runner.md` lines 37-40,
    `specs/poc/README.md` line 127, `docs/poc-workload-log-health.md` line 57,
    `tests/unit/test_workload_apply_docs_consistency.py` lines 175 and 185;
    the workflow-shape tests pin the job graph (R6-M1; S4.11, S4.13, S4.14
    and S4.17 own their rewrites).

  **Operation source.** The mode is never a request flag. Each operation is a
  reviewed contract PR on `main` that sets
  `workload_operation: {mode, sequence}` (AD-04). The runner reads it from
  the installed `main` contract (as the runtime guard does) and refuses a
  mode whose anchor does not match. Recovery modes come only from
  `recovery.yml` in a recovery environment.

  **Receipts (one per admitted apply).** Every admitted `up-plan`, successful
  or failed, ends with the runner capturing the final checkpoint through the
  trusted backend and writing `poc-workload-step-receipt-v1`: stack, mode,
  operation sequence, `outcome` (`success` or `failed`), checkpoint
  `{version, etag, sha256}`, `run_id`, `run_attempt`, `source_sha`,
  contract digest, projection digest, generated-files digest and the
  secret-metadata observation; a `success` receipt also records the
  projection inputs (the `SourceAdmission` facts, the full image rows
  `uri`, `manifest_media_type`, `config_digest`, `config_size` and
  `platform` of `scripts/poc_workload_phase_entrypoint.py` lines 52-93,
  and the certificate observation `{parameter_arn, parameter_version,
  certificate_arn}` of `scripts/poc_workload_capabilities.py` line 277,
  or `null`, which S4.14 makes the only value under user decision D-15
  because the contract then carries the ARN; runner lines 177-184) and the program trees (the git object IDs of
  `scripts`, `pulumi`, `policy`, `schemas`, `pyproject.toml` and
  `uv.lock` in the installed checkout), which the scheduled path uses
  instead of a PR request (R7-M2, R8-m4). **Failure path (m4, audit).** Two processes
  fail the job on a non-zero status. The worker raises at
  `scripts/service_execution_worker.py` line 127
  (`require(result == 0, "worker-execution")`). The host,
  `scripts/service_execution_host.py`, runs the worker container with
  `check=True` (`_run`, lines 76-83), mounts `/public` from a random
  `mkdtemp` under `RUNNER_TEMP` (lines 166-167), and copies out only for
  `_preview` jobs (lines 213-218). So: the runner writes the receipt file
  before it returns the status or raises. **Result-inspection failure
  (R6-m9):** when the apply succeeds but `_inspect_first_result` (runner
  lines 124-148) or the S4.10 checker raises, the runner captures the final
  checkpoint through the trusted backend, writes an `outcome: failed`
  receipt with `cause: result-inspection`, and re-raises; only if that
  capture also fails is no receipt written, and the recovery `export`
  covers it. The worker copies the receipt to `/public` in a `finally`
  block around `_test` and the line-127 check (today it copies only `plan`
  artifacts, lines 128-132), so a raise still copies it; the host runs the
  `test_apply` container without raising first, copies
  `/public/workload-receipt` to the fixed path
  `.trusted/.artifacts/workload-receipt` in a `finally` path, and only then
  raises on a non-zero status. Both copies are no-ops when no receipt
  file exists, as on every registry-phase run (audit F2). `test_apply`
  uploads that path in a step guarded by
  `always() && needs.poc_prepare_source.outputs.phase == 'workload'`, with
  `if-no-files-found: error` like every other upload in the file (lines
  135, 274, 284 and 655), so a registry-phase run skips the step and
  `test_apply` does not fail for a missing receipt; and a new
  `self-deploy.yml` job
  **`test_apply_receipt`** (environment `governance-evidence`, no AWS
  credentials, `needs: [preflight, poc_prepare_source, test_apply]`)
  publishes and authenticates it on both the success and the failure path.
  Its `if` has no `always()` (R6-M1): `!cancelled() &&
  needs.poc_prepare_source.result == 'success' &&
  (needs.test_apply.result == 'success' || needs.test_apply.result ==
  'failure')`, plus a TEST workload-phase `up`. A
  cancelled job kills the host too, so a cancellation leaves no receipt;
  the recovery `export` covers that case. If the
  job dies before it can write a receipt (for example a credential-window
  timeout), the recovery `export` (S4.3, `test-recovery`) writes
  `poc-workload-export-receipt-v1` with the same checkpoint fields. **Every
  recovery subcommand that writes the checkpoint writes a receipt for the
  new checkpoint** (AD-16, R5-M2): `clear-pending` an export receipt with
  `cause: clear-pending` and `predecessor` (the prior receipt's ID and
  checkpoint sha256), `import` an import receipt and `abandon` an abandon
  receipt; `release-lock` must leave the checkpoint unchanged. Every
  receipt carries the `workload_operation` it belongs to, so `resume` knows
  which operation to finish. Every receipt is published and authenticated
  like the registry proof: an immutable artifact, the protected
  `governance-evidence` environment, and App deployment and status readback
  (README items 2-3; XP-9). The **latest receipt** of a stack is the one
  whose checkpoint equals the live checkpoint; any other receipt is stale and
  refused.

  **Mode → anchor table.** Admission observation replaces the two registry
  checks with this table. The registry receipt stays the release identity
  (README line 95: updates keep the original registry anchor).

  | Mode | Anchor that must equal the live checkpoint | Extra condition |
  | --- | --- | --- |
  | `first` | registry receipt checkpoint (today's rule) | the checkpoint holds only registry resources |
  | `resume` | latest receipt with `outcome: failed`, or an export receipt (`cause: export` or `clear-pending`; a `clear-pending` receipt's `predecessor` must be a failed or export receipt of the same lineage) | the operation to finish is the anchor's `workload_operation` (m11), and the installed contract's `workload_operation.resumes` equals its mode and phase (R6-m7). The checkpoint holds the URNs of the last `success` receipt before it (the registry resources for an interrupted step 1) plus a subset of the URNs that operation creates or updates. The resumed plan may only `create` or `update` URNs of that operation, under that operation's own admission rule (for example the `step2` created set, the `rollback-zero` phase rule, or the one `policy-update` step), plus `same`. A new action's `at()` time must be inside the window (AD-10); an action URN not yet in state may be replaced by a new `scaling` entry. |
  | `step2` | latest receipt: `success` of step 1 (`first` or `resume`) | S5.5 receipt; XP-8 values in the installed contract |
  | `rollback-zero`, `policy-update` | latest receipt: `success` of any mode after step 2 | `hold`: the latest receipt is the `stop` plan's success receipt and its authenticated stop observation exists (R6-m6). Only `hold` may set and only `start` may clear `scaling.scheduled_scaling_suspended`; any other mode that would change it renders a `Target` update and is refused (R6-m7) |
  | `recovery-import` | latest receipt or export receipt (after an abandon: the abandon receipt) | import list = the abandon receipt's `retain` set, or the reviewed import list; writes an **import receipt** |
  | `rebuild-first` | latest receipt is an import receipt whose predecessor is an abandon receipt | the checkpoint holds exactly the registry resources plus the abandon receipt's `retain` set; creates the rest of the step-1 graph (retained step-2 URNs stay `same`); the step-1 checker runs in its rebuild variant |
  | `recovery-abandon` | latest receipt or export receipt | the Kravalg-approved manifest lists exactly its resources |
  | `drift` | latest `success` receipt, and an accepted-workload receipt in the same lineage (no abandon in between) | read-only |
  | release, release rollback | as `drift`, plus a clean-drift result bound to the latest receipt | — |

  The C-runner chain changes this path in four stories, all before S4.6,
  and a fifth, S4.17, before gate 2b (R6-m11):
  1. **S4.11 step, export and abandon receipts; anchor rebinding.** The
     receipt library `scripts/poc_workload_receipts.py` over the S1.1
     schemas, including the `poc-workload-observation-v1` records (write,
     publish, authenticate and look up by bound success receipt; R7-m6),
     with complete pagination on every lookup; issuance in the runner after every admitted apply (success and
     failure paths, including a failed result inspection, R6-m9), the
     worker copy in a `finally` block, the host copy-out in a `finally`
     path, the `test_apply` upload and the `test_apply_receipt`
     publication job; the workload-aware capture (AD-25) and the table above
     in `inspect_registry`/`observe_workload` and in `_capture`. It also removes
     the stale "issues no receipt" wording: the runner docstring (lines 1-7)
     and `specs/poc-workload-runner.md` lines 38-40, 50-52 and 97-98 (lines
     37-38 and 121-122 change in S4.13). S4.3 issues the export,
     clear-pending, import and abandon receipts with the same library.
  2. **S4.12 mode routing.** `execute` and `_gate` dispatch by
     `workload_operation.mode` (and, for `rollback-zero`, by
     `workload_operation.phase`; R6-m7): `first` → `admit_first_workload_plan`;
     `step2`, `rollback-zero`, `policy-update` → S4.9; `resume` and
     `rebuild-first` → S4.2;
     `recovery-import` and `recovery-abandon` → S4.3, only from
     `recovery.yml`. An unknown mode, a mode not allowed for the command, or
     a stale or missing anchor is refused.
  3. **S4.13 accepted-workload receipt; drift and releases.** Every admitted
     apply that creates a start or stop action runs the AD-18 observation in
     the separate `test_workload_observation` job (m13, R6-m6). The first
     passing start observation after step 2 writes
     `poc-workload-accepted-receipt-v1` through `test_workload_acceptance`
     (for example after a step-7 STOP, the next successful `rollback-zero`
     start plan). `drift` and releases then follow the table. Scope: runner
     line 154 and the drift plan-plus-gate dispatch with the FR-32 reducer
     (AD-23, R6-m4); worker line 99 (drift routed only with the accepted
     receipt), worker docstring line 5 and
     `tests/unit/test_service_execution_worker.py:166`; the new
     `self-deploy.yml` job **`test_workload_drift`** (R6-M1): environment
     `test-preview`, the `pulumi-state-…-test-test` concurrency group,
     `needs: [preflight, poc_prepare_source, test_apply,
     test_apply_receipt]`, and an `if` that requires
     `needs.test_apply.result == 'success'`,
     `needs.test_apply_receipt.result == 'success'` and a TEST
     workload-phase `up` whose `poc_prepare_source` output `workload_route`
     is `post-acceptance`. **That output comes from the authenticated
     receipt lineage, not from the contract bytes (R7-m5, audit F1):** the
     adapter reads the stack's receipts through the S4.11 library
     (`poc_prepare_source` gains `deployments: read`) and writes
     `post-acceptance` only when the lineage holds an accepted-workload
     receipt with no later abandon; otherwise `pre-acceptance`. So the
     first-deployment `rollback-zero` (AD-19) and the step-7 STOP
     `policy-update` for V-14 or V-20, which run before 7b, run no drift
     job and do not go red; a lookup error or incomplete pagination fails
     `poc_prepare_source`. The success receipt the drift job binds to is
     published first, and no drift job runs before an accepted receipt
     exists. Also in scope: the worker and host
     `JOBS` entries for it; the `poc_prepare_source` outputs
     `workload_route` and `workload_observation`, written by
     `scripts/poc_phase_source_adapter.py` (today it writes only `phase=`,
     line 291); the scheduled-drift exclusion (AD-23); and
     `specs/poc-workload-runner.md` lines 121-122. **Registry chain
     unchanged (R6-M1):** `test_post_apply_drift` keeps its `if` (lines
     480-483) and `needs` (lines 486-489), and no registry job needs a
     workload job. So a registry-phase run, where `test_apply_receipt` is
     skipped, still runs `test_post_apply_drift`,
     `test_registry_observation`, `test_registry_proof` and
     `test_registry_dispatch`. A separate job was chosen over widening
     `test_post_apply_drift`: a `needs: test_apply_receipt` on the registry
     job would make GitHub skip it, and the three registry jobs after it,
     on every registry-phase run, and avoiding that would need a status
     function in its `if`, which is pinned byte-equal by
     `tests/pulumi/test_ci_guardrails.py` lines 293-297 and
     `tests/unit/test_poc_registry_workflow.py` lines 128-132 (R7-n2;
     `tests/unit/test_poc_source_workflow.py` line 223 only rejects
     `always(`). A **reviewed amendment** (Kravalg-approved
     governance PR) changes README line 127, runner spec lines 37-40 and
     `docs/poc-workload-log-health.md` line 57 to "Workload drift is admitted
     only with an authenticated accepted-workload receipt and is rejected
     without one." `test_workload_apply_docs_consistency.py` changes with
     them: line 175 gets the new sentence, and line 185 becomes two
     assertions (drift not routed without the receipt, routed with it).
  4. **S4.14 PROD path.** Worker `JOBS`/`ACCOUNTS` and host `JOBS`
     (`scripts/service_execution_host.py` lines 27-31) gain the PROD entries
     (`prod_preview`, `prod_apply`, `prod_workload_drift`; account
     `933245420672`), and `self-deploy.yml` gains exactly the PROD jobs
     `prod_preview`, `prod_destructive_diff`, `prod_apply`,
     `prod_apply_receipt`, `prod_workload_drift`,
     `prod_workload_observation` and `prod_workload_acceptance`, in the
     `prod-preview`, `prod` and `governance-evidence` environments, each
     behind `admission.prod`. S4.14 lists every TEST-only pin on this path
     with its PROD fixture, or assigns it to XP-14 (R6-m5; the table is in
     `epics-stories.md` S4.14). The source binding accepts
     `prod` only when the installed `main` contract has `admission.prod` =
     `"preview"` (PROD `plan` only, gate 2a) or `true` (gate 2b). The runner
     accepts `prod` with the PROD certificate ARN pinned in
     `poc-prod.json` (XP-15, the PROD counterpart of XP-10; no SSM
     parameter, user decision D-15), the PROD
     topology (S4.10), the PROD registry anchor (XP-14) and `prod-recovery`.
     `abandon` is never admitted for PROD. S4.14 also owns the PROD
     contract schema (AD-04, R7-m4), the PROD baseline-drift exclusion
     (AD-23, R7-m2), and PROD fixtures for the further TEST pins that
     round 7 found (R7-m3): the workload gate's use of the registry
     `_binding` (`scripts/poc_registry_runner.py` lines 266-283, called at
     runner line 58), `scripts/poc_workload_capabilities.py` (lines 22-23,
     30, 32, 92, 111, 130-133 and 286, reached through
     `poc_workload_admission.py` line 470), `scripts/poc_workload_images.py`
     (lines 44, 68, 126, 282 and 349; line 126, the ECR token, is removed
     by the token-free config read rather than made stack-aware, AD-26,
     R9-M1), `scripts/poc_workload_phase_entrypoint.py`
     (lines 109-116, role prefix), `scripts/poc_workload_materializer.py`
     (line 89), runner lines 194-195 and the registry-row check of every
     capture (`poc_registry_runner._capture`, lines 254-263). Because the
     host's `_target_coordinates` (host line 164; observer lines 188-210)
     is XP-14-owned, S4.14's PROD host and seam tests stub it, and S4.7
     adds the unstubbed PROD seam case after XP-14. XP-14 owns the
     observer's schema read (lines 199-201) and the TEST registry constants
     of `scripts/poc_registry_plan.py` (lines 21, 26-27, 36, 60-65 and
     69-71); an
     XP-14 change to that file is outside this plan and outside the R6-m13
     rule. It rewrites every workflow-shape pin the PROD jobs break
     (R7-M1; the list is in `epics-stories.md` S4.14). **Revision 8
     (R8-m2):** S4.14's first case is a grep-derived inventory of every
     TEST literal and TEST-constant use in `scripts/` (87, 38 and 41 hits at
     `72873f9`), each with an owner or an exclusion reason, re-checked by
     a test. New S4.14 rows: the materializer's `Pulumi.test.yaml`
     (lines 24 and 126), `poc_contract.py` `_registry_semantics` (lines
     116-126, run for every contract including XP-14's `poc-prod.json`)
     and `_mail_semantics` (lines 102-113; the PROD domain is XP-14's, and
     the map ships without it, fail closed), `poc_secret_observation.py`
     `SECRET_PREFIX` (line 11) and every `CONTRACT_PATH` consumer. New
     XP-14 rows: the observer's `_caller`, `_key` and `LOCKS`,
     `_REGISTRIES`, the registry completion and the mail prerequisite.
     The PROD host-test stand-ins check the PROD coordinates and raise the
     observer's own error on a mismatch (R8-A1).
  5. **S4.17 scheduled workload drift (R6-m11, R7-M2).** One schedule-only
     job per workload stack in `.github/workflows/scheduled-drift.yml`
     (`scheduled_test_workload_drift`, `scheduled_prod_workload_drift`;
     environments `test-drift` and `prod-drift`; the Drift role with
     `role-session-name` `gha-scheduled-test-drift-${{ github.run_id }}`
     or `gha-scheduled-prod-drift-${{ github.run_id }}`, the names the
     observer's `_caller` checks at lines 219-223, R8-n1; the stack's
     `pulumi-state-…` concurrency group). **Isolated launch:** the
     materializer's `_worker()` (`scripts/poc_workload_materializer.py`
     lines 137-143) requires euid 0, pid 1 and a read-only `/` and
     `/trusted` with no local bypass, and the runner requires
     `ServiceTransport` (runner lines 155-157), so the script runs only in
     the service-execution container. Today that launch is PR-bound (host
     `recheck`, `scripts/service_execution_host.py` lines 137-151; worker
     `admit`, `scripts/service_execution_worker.py` lines 34-53). S4.17
     adds host and worker entries for the two jobs with host operation
     `scheduled-drift` (the observer's Drift identity,
     `scripts/poc_backend_observer.py` line 175) and scheduled-main
     provenance (the `_context`/`verify_provenance` pattern of
     `scripts/poc_scheduled_registry_drift.py`, lines 49-101) in place of
     the PR request; no scheduled path reads a PR request, review or source
     artifact. The jobs use `setup-service-execution`, a host `recheck`
     before each credential step and one host `execute`, with exactly
     `contents`, `actions` and `deployments` read plus `id-token: write`,
     and `GH_TOKEN` (host line 158). **Result publication (R8-M1):** the
     worker copies to `/public` only for `plan` today (lines 129-132) and
     the host copies out only for `_preview` jobs (lines 214-219); for the
     two scheduled jobs the worker's scheduled route copies the result
     record to `/public/workload-drift-result/record.json` after a
     zero status, the host copies it to
     `.trusted/.artifacts/workload-drift-result/record.json` (a no-op when
     absent), and one pinned `actions/upload-artifact` step directly after
     `execute` uploads it as
     `poc-workload-scheduled-drift-<env>-${{ github.run_id }}-${{ github.run_attempt }}`
     with `if-no-files-found: error`, `overwrite: false` and
     `retention-days: 7`; the sibling test pins "execute, followed only by
     that upload". **Data-driven enablement (R8-m1):** both jobs run
     nightly from S4.17's merge. Each reads its stack's installed `main`
     contract; on `phase: registry` it writes a `registry-phase` record,
     emits a notice and exits 0 (the baseline still covers that stack), and
     on `phase: workload` it checks drift. So the PROD job starts checking
     after the gate-2a PR that first sets `poc-prod.json`
     `phase: workload`, the same PR that removes `prod` from the baseline
     (R7-m2), with no enabling PR. **Projection (R7-M2, R8-m4):**
     `scripts/poc_scheduled_workload_drift.py` builds the projection only
     from the authenticated latest success receipt: its `SourceAdmission`
     facts, the contract that receipt applied (read at its recorded
     `head_sha` and `blob_sha`, as the source adapter does at lines
     239-245, so a merged but unapplied operation PR does not change the
     check; the digest binding of
     `scripts/poc_workload_phase_entrypoint.py` line 104 holds), the full
     image rows and the certificate observation (`null` under D-15; the
     ARN is in that contract). Fresh Drift-role reads
     are comparisons, never inputs: the image, capability and certificate
     reads, the captured checkpoint and the registry-row checks must equal
     the receipt. Because the program is imported from installed `main`
     (entrypoint lines 194-208) and the old contract is validated against
     the installed schema (line 101), the script first compares the
     receipt's program trees with its installed checkout and fails with
     the distinct reason `workload-drift-installed-program-changed` on any
     difference; it then compares the projection digest and the
     generated-files digest with the receipt's. Whenever code changed
     after the last TEST apply, a TEST release (a no-op re-apply through
     the normal PR path, AD-24 release row) runs before the gate-2b clean
     `checked` run. **Gate:** its own, modelled on
     `poc_scheduled_registry_drift._gate` (line 136 on), because the
     runner's gate and `execute` are PR-bound (`registry._review`,
     `observe_workload`, `revalidate_requester`, `capture_backend` and
     `_trusted_root`, which requires `repository_dispatch`): it captures
     the checkpoint with `capture_scheduled_backend` (observer lines
     428-435), binds the provider identity with S4.14's stack-aware
     binding (the registry `_binding`, `scripts/poc_registry_runner.py`
     lines 266-283, is TEST-only; R8-A4), and runs `validate_drift`
     through the plan-plus-gate dispatch. The plan is discarded and
     nothing is applied. Any change outside AD-23 fails the scheduled job
     with the field named, as a failed baseline scheduled drift does
     today. **Result record (R7-m1):** each run that exits 0 writes one
     `poc-workload-scheduled-drift-result-v1` record (schema owned by
     S4.15): `checked`; `before-acceptance` while the lineage has no
     accepted receipt, bound to the captured checkpoint sha256 and the
     latest success receipt; or `registry-phase`. Before acceptance the
     same drift check still runs against the latest success receipt (a
     read-only diagnostic, distinct from the PR `drift` command of the
     table above) and fails on drift; a clean run exits 0 with a warning
     annotation. With no workload success receipt yet no check runs (the
     registry resources are the registry owner's recorded case). Gate 2b
     needs a TEST `checked` record and a PROD `before-acceptance` record
     with `null` receipt fields from a run after the flip (AD-21; PROD
     cannot apply before gate 2b, so `checked` cannot occur, R9-n1). A receipt-lineage
     lookup error, including an incomplete pagination, exits non-zero.
     **Reads (R7-m9, R8-m3, R9-m1, R9-m2):** the capability and image
     checks read IAM, ECR (including `GetDownloadUrlForLayer`) and ACM;
     every capture reads `s3:GetBucketVersioning` on the stack's state
     bucket (`scripts/poc_backend_observer.py` lines 443 and 476); and
     the refresh and the capture's registry-row checks read the ECR
     repositories, the SES identity and the Route53 DKIM records. The BI
     story S5.24 (unconditional) inventories and adds them after XP-14
     and XP-15 (and XP-16, which S5.1 satisfies at row 8, R12-M2) and
     before S4.17, with
     `iam:SimulatePrincipalPolicy` on the execution role only, citing the
     existing TEST grants of BI `origin/main` (active only while the
     packaged TEST capability is `enabled`). It narrows neither the
     Drift role's deny nor its seed guard (AD-26): the certificate ARN
     comes from the contract the receipt applied (user decision D-15; the
     receipt's certificate observation is `null`), so no role reads an
     SSM parameter, and S4.14's token-free config read needs no
     `ecr:GetAuthorizationToken`. Its boundary additions go through a
     seed catalog amendment (R10-M1). The PROD job needs the PROD observer
     coordinates of XP-14. S4.17 is a gate-2b precondition (AD-21), and it
     rewrites the scheduled workflow pins and the host and worker
     copy-out pins with Kravalg's approval
     (`tests/unit/test_poc_scheduled_registry_workflow.py` lines 1, 19 and
     a sibling test; `tests/pulumi/test_ci_guardrails.py` lines 177 and
     347-353; `tests/unit/test_service_execution_worker.py` lines 128-130;
     `tests/unit/test_service_execution_host.py` lines 109-112 and
     140-144).
  - **Regression tests (all four stories):** `step2` without a step-1
    receipt refused, admitted with one; `resume` without a failed or export
    receipt refused; a failed receipt → `clear-pending` (with its export
    receipt) → `resume` admitted, and the same without the clear-pending
    receipt refused as stale; `drift` without an accepted receipt refused
    (`workload-accepted-state-receipt-required` and, in the worker,
    `workload-drift-not-enabled`), admitted with one; release refused without
    a clean-drift result; a stale receipt refused. The existing negatives
    (`workload-checkpoint-binding` for `first`,
    `workload-completed-registry-required`,
    `workload-registry-checkpoint-changed`, `workload-stack`,
    `workload-first-command`, `workload-request-binding`,
    `workload-source-binding`, `workload-isolated-transport-required`,
    `workload-plan-bytes-changed`) keep passing for the modes they cover
    today; `workload-certificate-parameter-required` is replaced by
    `workload-certificate-arn-required` (user decision D-15, S4.14).
- **AD-25 Topology, native gates and secret history owned by one story (R4-M1).**
  `scripts/poc_workload_topology.py::expected_graph` (line 142) is the closed
  installed composition. Today it contains the Random and TLS providers and
  resources, ten `Secret` + `SecretVersion` pairs (lines 173-220), five SGs
  and no endpoints, flow logs, ElastiCache users, KMS log groups, alarms or
  autoscaling. The native gates pin the web container's kept capabilities
  (`NET_BIND_SERVICE`, `SETUID`, `SETGID`; `specs/poc-workload-runner.md`
  lines 79-82) and the secret env names (`CONTAINER_SECRET_NAMES`, lines
  40-50). `scripts/poc_workload_secret_result.py` requires a "sole current
  version" and `RotationEnabled` absent or `false` (lines 121-135; spec lines
  89-98). **S4.10 (C-contract) is the only story that edits these files.**
  It changes them in one PR:
  - **both stacks:** the graphs, names and accounts are parameterized by
    stack (`test`, `prod`) through `build_resource_name` and the contract
    account, replacing the hard-coded `-test-` names (topology lines 61,
    859, 955 and 1058) and the TEST URN prefix and root imported at lines
    149-151 (R8-m2), with the service and provider URNs derived from the
    stack's prefix and the registry nodes from a stack-selected registry
    set whose PROD entry is XP-14's, stubbed in S4.10's PROD fixtures (so
    S4.10 needs nothing from XP-14); the PROD graph adds the S3.5-A HTTPS
    target group on 8443;
  - the **step-1 graph**: removes Random/TLS, `SecretVersion`s and the eight
    removed purposes (FR-09, S1.1), and deletes the pre-hardening program
    branch together with the Random and TLS runtime pins (`pyproject.toml`
    lines 16-17, `scripts/poc_provider_runtime.py` lines 56 and 62). It adds the S1.2 managed password (no
    password input), S1.3 bootstrap-job SG and plain `MONGODB_URL`, S1.4
    ElastiCache users, user group and TLS-required group, S1.10 (no legacy
    path), S2.3/S2.4/S2.5 topic, topic policy, alarms and EventBridge rules
    and targets, S3.1 flow log and bucket family, S3.2 default SG, S3.3
    endpoint SG and endpoints, S3.4 egress rules, and `kms_key_id` on every
    log group, including the pre-created Container Insights group (D-4);
  - the **step-2 graph**: seed Invocations, `SecretRotation`s, `SecretPolicy`s
    (declared and managed), targets, policies, TEST `ScheduledAction`s and
    start actions (S1.5, S1.6, S2.1, S2.2, S2.6); plus the `rollback-zero`
    and `policy-update` URN rules;
  - the **native gates**: web and worker drop `ALL` capabilities with no
    add-back (S3.7, FR-26), use unprivileged port 8080 (PROD HTTPS 8443,
    S3.5-A), run a non-root `User`, and the secret env names are exactly
    `APP_SECRET` and `OAUTH_ENCRYPTION_KEY`, while the Redis, DocumentDB and
    KMS values are plain env;
  - the **secret-history checker**: after step 1, each declared secret
    exists with **zero** versions (no seed yet) and rotation absent; the
    DocumentDB-managed secret is observed with `RotationEnabled` true
    (managed, AWS key) and one `AWSCURRENT`. After step 2, each declared
    secret has exactly one `AWSCURRENT`, `RotationEnabled` true,
    `RotationLambdaARN` = the BI function and `RotationRules` = 90 days
    (D-5). The release/rollback checker accepts a changed current version
    only when `LastRotatedDate` is later than the receipt observation and
    rotation is enabled with the reviewed function. It still never calls
    `GetSecretValue`. A rebuild variant (AD-16) accepts the retained secrets
    listed in the authenticated abandon receipt;
  - `recovery/delete-actions.json`: per graph type, the API set of the pinned
    provider's delete path (V-26), which S5.7 grants and S4.3 checks;
  - **the checkpoint-field allowance (R5-M5, AD-23):**
    `scripts/poc_workload_reconciliation.py` (`UNSAFE_STATE` lines 31-49,
    check at line 95) and `scripts/poc_workload_topology.py` (create-goal
    check at lines 321-326 and create-step `newState` check at lines
    1114-1115) accept `ignoreChanges` equal to the AD-23 `ignore_fields`
    for the row's type, `retainOnDelete` only on the abandon path for
    manifest `retain` URNs and, if V-27 shows that `importID` persists
    after a recovery import, `importID` only on rows whose URN the
    authenticated import receipt lists (R6-m12), as a recorded deliberate
    narrow change;
  - the matching `specs/poc-workload-runner.md` text and doc-marker tests.

  **Transition rule (keeps CI green without a second topology writer).**
  Until S4.10 merges, the program emits the hardened shape only when the
  projection carries `workload_step` (AD-04). The existing projection
  fixtures have no `workload_step`, so they keep rendering the installed
  graph, and `tests/integration/test_poc_first_topology_native.py::test_actual_workload_program_native_first_plan`
  stays green. Each program story (S1.x, S2.x, S3.x) tests its hardened
  resources with a `workload_step` fixture in its own unit tests and does
  not edit the topology files. S1.1 keeps the Random and TLS generators and
  runtime pins inside the pre-hardening branch, because that native test
  still starts the `random` 4.19.2 and `tls` 5.3.1 providers
  (`tests/integration/test_poc_first_topology_native.py` line 105). S4.10
  then switches the native integration test to the step-1 and step-2
  projections, makes `workload_step` required, and deletes the
  pre-hardening branch and those pins. No workload can be
  applied in between, because `phase` stays `registry` until gate 1 and
  gate 1 lists S4.10.

- **AD-26 Workload observation reads under the explicit secret-read denies and the seed-owned IAM layers, and the creation of every new IAM principal (R9-M1, R9-m1, R9-m2; revision 10: user decision D-15, R10-M1, R10-m1, R10-m2, R10-n3; revision 11: R11-M1, R11-m1, R11-m2, R11-n1, R11-n2, R11-n4; revision 12: R12-M1, R12-M2, R12-m1, R12-m2, R12-m3, R12-m4, R12-n3).**
  **Problem.** Every workload `plan` and `up-plan` observes its
  prerequisites: `scripts/poc_workload_runner.py` line 178 and the gate at
  line 55 call `poc_workload_admission.observe_workload`
  (`scripts/poc_workload_admission.py` lines 464-475). It reads the images
  (`scripts/poc_workload_images.py`: `ecr get-authorization-token` at line
  126, then the config blob over the registry HTTP API, lines 206-231) and
  the capabilities (`scripts/poc_workload_capabilities.py`:
  `ssm get-parameter` at line 299). `plan` runs as the Preview role and
  `up-plan` as the Apply role (`scripts/poc_backend_observer.py` lines
  173-174). In BI (`origin/main` `bea5252`) the Preview role's read-only
  policy ends with `DenySecretLeakingReads`, Resource `*`
  (`pulumi/infra/governance.py` lines 266-271). That document is attached
  to every non-apply purpose, Preview and Drift alike (lines 448-456).
  The Apply role carries `DenySecretLeakingReadsApply`, whose
  `NotResource` exempts only the `/{project}/ci/*` secrets
  (`pulumi/infra/ci_bootstrap.py` lines 634-663). Both action lists
  (`ci_bootstrap.py` lines 132-145 and 153-166) include `ssm:GetParameter`
  and `ecr:GetAuthorizationToken`. The seed-owned guards deny the same
  two actions again (fourth layer below). An explicit Deny overrides
  every Allow. Unchanged, the first TEST workload `plan` (from the S4.6
  gate-1 PR on) and `prod_preview` (gate 2a) fail with `AccessDenied`,
  and so would every `up-plan`.

  **Non-weakening design, adopted for both reads** (least privilege: AWS
  Well-Architected Security Pillar SEC03, best practice SEC03-BP02 "Grant
  least privilege access"). Revision 10 narrows no deny and no guard.
  1. **The ECR token: removed (S4.14).** The token has one use:
     it downloads the image config blob (`_authorization`, lines 123-143;
     `_download_config`, lines 206-231, with the `Authorization: Basic`
     header at line 219; called from `_config`, lines 244-245), so the
     platform can be read from the config (`os`, `architecture`). The
     manifest and layer checks already use the IAM-authorized,
     repository-scoped `ecr:BatchGetImage` and
     `ecr:BatchCheckLayerAvailability` (`_native`, lines 51-74).
     `ecr:DescribeImages` gives no platform for a single-image manifest, so
     it cannot replace the config check. S4.14 replaces the token path with
     `ecr get-download-url-for-layer` on the config digest. That API is
     repository-scoped (`ecr:GetDownloadUrlForLayer`) and returns a
     pre-signed URL. The reader then makes one GET of that URL on the fixed
     regional layer-bucket host that is already allow-listed (`LAYER_HOST`,
     lines 46-48; `_blob_target`, lines 153-169), with no `Authorization`
     header and the size, digest and platform checks unchanged.
     `ecr:GetDownloadUrlForLayer` is in no deny list and no guard
     statement, so the `ecr:GetAuthorizationToken` deny is narrowed for
     no role. **Open point V-28, fail closed.** The AWS API reference
     documents `GetDownloadUrlForLayer` for image layers referenced in an
     image. It does not state that the config blob is accepted, and the
     offline tests cannot prove it (`docs/poc-workload-admission.md` line
     69 says the same of today's path). The first live call is the first
     TEST workload `plan` (S4.6 step 1, the gate-1 PR's `plan`), which is
     read-only. A refused config digest, or a URL outside `LAYER_HOST`,
     fails that plan with `image-config-observation-failed` before any
     apply. That is a STOP. The fallback keeps the token path and removes
     `ecr:GetAuthorizationToken` from the Preview, Apply and Drift denies
     **and** from the seed guards (the `ae950d73…` statement of the
     Preview and Drift guards and the `9f269660…`/`ce12c400…` statements
     of the Apply guards, below), which changes the guard template
     hashes and the catalog hashes through a seed amendment. That weakens
     denies on Resource `*`, which the NFR-06 rule (narrow only to one
     exact ARN) does not allow. It therefore needs a user decision that
     amends NFR-06, as well as the BI security review and the seed review
     approved by `@Kravalg`. This plan does not take it.
  2. **The certificate parameter: removed by user decision D-15
     (2026-09-30).** The gateway owner supplies the certificate ARN, and a
     reviewed USI contract PR pins it in the workload contract
     (`workload.external.domain.certificate_arn`; XP-10 for TEST, XP-15
     for PROD). The capabilities reader already skips SSM when the
     contract carries `certificate_arn` (`_certificate_input`, lines
     295-298; `certificate_projection`, lines 269-272), and ACM
     `DescribeCertificate` then binds the certificate alone
     (`_certificate`, lines 243-266: issued, currently valid, the FQDN in
     the SANs, TLS server-auth usage). S4.14 makes this the only path: the
     TEST schema requires `certificate_arn` and drops the
     `certificate_parameter_name` alternative
     (`schemas/poc-test-v1.schema.json` lines 508-527), the PROD schema
     has only `certificate_arn`, the runner's
     `workload-certificate-parameter-required` rule
     (`scripts/poc_workload_runner.py` lines 170-176) becomes
     `workload-certificate-arn-required`, and the SSM read path
     (`_certificate_input`'s `ssm get-parameter`, line 299, and the
     `("ssm", "get-parameter")` entry of `_native`, lines 37-47) is
     removed. **No CI role (Preview, Apply or Drift; TEST or PROD) gets
     any `ssm:GetParameter` read, and no identity deny, seed guard, seed
     boundary or catalog hash is loosened for SSM** (D-15). ACM managed
     renewal keeps the same ARN, so a USI contract PR is needed only when
     the certificate is replaced. **Operating residual (R10-n4), not a
     risk acceptance (PRD §7 XP-10 has the exact order and windows):** a
     replacement needs the exact-ARN `acm:DescribeCertificate` grant
     update (which revision 9 needed as well, plus a seed amendment if
     the boundary holds the exact ARN) and the USI contract PR, then an
     apply. PR plans fail closed on the ACM check between the contract
     PR and the grant update; S4.17 checks the applied contract's ARN
     until the new ARN is applied; and once the old certificate is no
     longer issued or valid, both fail closed until then. The gap
     between this and D-15's rationale ("only a USI PR") is surfaced to
     the user in `readiness.md`, not decided here. Deriving the ARN from ACM alone (for example by
     listing certificates for the FQDN) would drop the gateway owner's
     binding and stays rejected.
  3. **Scheduled drift: no SSM and no token (S4.14, S4.17; R9-m2).**
     S4.17 builds the projection from the latest success receipt and the
     contract that receipt applied. Under D-15 that contract carries the
     certificate ARN, and the receipt's certificate observation is
     `null` (S1.1 schema), so S4.17 calls
     `capabilities.inspect_capabilities(contract)` on the applied
     contract: role reads, the execution-role pull simulation and ACM
     `DescribeCertificate` on the pinned ARN, and no parameter read,
     because none exists. Revision 9's `certificate=` reader parameter is
     no longer needed and is not added. With point 1 the image comparison
     needs no token either, so **the Drift role's deny and guard are not
     narrowed at all.** Revision 9's lost signal (a gateway re-pointing of
     the parameter between applies) no longer exists: the ARN changes
     only through a reviewed contract PR.

  **Required grants per stack** (TEST Preview and Apply: XP-11; PROD
  Preview and Apply: S5.24a, R9-M1 (c); Drift, both stacks: S5.24b).
  Only allows that no deny and no guard statement blocks (D-15):

  | Role | Allow (exact resources) | Deny and guard change |
  | --- | --- | --- |
  | `GitHubCiPreview-user-service-infrastructure-{env}` | `iam:GetRole` on the stack's ECS execution and task roles; `iam:SimulatePrincipalPolicy` on the execution role (TEST: S5.17 already grants it on the S4.6 step-3 role list, which stays unchanged; PROD: S5.24a grants it on the PROD execution role only); `ecr:BatchGetImage`, `ecr:BatchCheckLayerAvailability` and `ecr:GetDownloadUrlForLayer` on the stack's two workload repositories; `acm:DescribeCertificate` on the certificate ARN the stack's contract pins (metadata only; TEST XP-10, PROD XP-15); `s3:GetBucketVersioning` on the stack's state bucket (TEST: the `PocBackendVersioning` statement of the enabled TEST capability; PROD: XP-14) | none: `DenySecretLeakingReads` and the seed guard stay as they are |
  | `GitHubCiApply-user-service-infrastructure-{env}` | the same reads, with `iam:SimulatePrincipalPolicy` on the execution role only | none: `DenySecretLeakingReadsApply` and the seed guard stay as they are |
  | `GitHubCiDrift-user-service-infrastructure-{env}` | the same reads, with `iam:SimulatePrincipalPolicy` on the execution role only (S5.24b; `s3:GetBucketVersioning` for TEST from `PocBackendVersioning`, for PROD from S5.24b) | none |

  No role gets `ssm:GetParameter`, `ssm:GetParameters`,
  `ssm:GetParametersByPath` or `ecr:GetAuthorizationToken`. The
  `iam:SimulatePrincipalPolicy` calls simulate the execution role's own
  ECR pull, including `ecr:GetAuthorizationToken` for that role (`_pull`,
  lines 193-232). They do not call it, so the caller's token deny does
  not affect them.

  **Reachable privilege of the Drift role after S5.24b (R9-m2):**

  | Principal | Action | Resource | Reachable privilege |
  | --- | --- | --- | --- |
  | Drift `{env}` | `ecr:BatchGetImage`, `ecr:BatchCheckLayerAvailability`, `ecr:GetDownloadUrlForLayer` | the stack's two workload repositories | manifests, layer availability and pre-signed blob URLs of those two repositories, plus whatever a repository policy grants (below) |
  | Drift `{env}` | `ecr:GetAuthorizationToken` | `*` | none: still explicitly denied (identity deny and seed guard), so no registry HTTP access |
  | Drift `{env}` | `ssm:GetParameter`, `ssm:GetParameters`, `ssm:GetParametersByPath` | `*` | none: still explicitly denied (identity deny and seed guard); the certificate ARN comes from the applied contract (D-15) |
  | Drift `{env}` | `acm:DescribeCertificate` | the certificate ARN the stack's contract pins | certificate metadata; no private key (`acm:ExportCertificate` is not granted) |
  | Drift `{env}` | `iam:GetRole` | the stack's ECS execution and task roles | role metadata and trust policies |
  | Drift `{env}` | `iam:SimulatePrincipalPolicy` | the execution role only | simulation decisions for that role's policies |
  | Drift `{env}` | `s3:GetBucketVersioning` | the stack's state bucket | the versioning status |
  | Drift `{env}` | the registry-row and refresh reads (S5.24b) | the stack's registry resources | metadata |

  **Repository policies (R9-m2).** Within one account, a repository-policy
  statement that allows `*` gives every principal of the account those
  actions without an identity grant. So the removed-token argument of
  revision 8 ("the token grants nothing without the repository-scoped
  pull grants") held only if no such policy exists. Neither USI
  (`pulumi/`, `scripts/`) nor BI (#219 `pulumi/`) code defines an ECR
  repository policy (grep for `RepositoryPolicy`). The XP-11 and S5.24
  reviews each read every workload repository's policy read-only (BI
  owner) and record it. A statement that allows a pull action to `*` is a
  STOP for that review. A statement that names the account principal is
  recorded; for same-account callers it defers to identity policies.

  **The six IAM layers (R10-M1; pre-commit audit 1; R11-M1, R11-n4).**
  Layers 1-5 apply to each USI CI role: identity allows, identity
  denies, the permissions boundary, the seed guard and the seed's
  attachment constraint. Layer 6 is principal creation: the seed guards
  deny role creation to every CI and operator principal, so they decide
  who may **not** create a role; the identity that does create the new
  roles, the reviewed human non-root installer (PRD §7 XP-17), is not in
  the seed catalog and is not governed by it (corrected in revision 12,
  R12-m1). An allow is
  effective only if an identity policy allows it, the permissions
  boundary allows it, and no explicit identity deny or seed guard denies
  it. Checked
  read-only against BI `origin/main` `bea5252` (the `wt-boot-urllib3`
  worktree, whose `pulumi/` tree equals `origin/main`):
  1. **Identity allows: new, scoped to the USI identity (R10-n3).** The
     grants above. `_governance_policy_documents` (`pulumi/infra/
     governance.py` lines 414-475) renders every enrolled repository, so
     the new statements are keyed to repository
     `user-service-infrastructure` and its stack; every other enrolled
     repository's rendered documents stay byte-identical.
  2. **Identity denies: unchanged by this plan.** `DenySecretLeakingReads` and
     `DenySecretLeakingReadsApply` keep their action lists and resources.
     With D-15 the deny documents do not change at all: neither
     `_governance_read_only_policy_document` (`governance.py` line 212
     on, the deny at lines 266-271) nor `_apply_secret_deny_document`
     (`ci_bootstrap.py` lines 634-663), which also renders the platform
     apply role's `secret-read-deny` document (line 700), so the platform
     roles' documents stay byte-identical as well.
     **The TEST Apply role also carries an inline deny-all hold (R12-M1).**
     BI keeps `Issue215CutoverSessions` on
     `GitHubCiApply-user-service-infrastructure-test`: an unconditional
     deny-all inline policy, whose retirement is "a separate reviewed
     activation" and "a prerequisite to any downstream service apply"
     (BI `docs/governance-stack.md` lines 478-480 at `origin/main`
     through `wt-boot-urllib3`; #284 `wt-boot-pr280`
     `specs/test-poc-prerequisite-capability/post-seed-activation.md`
     lines 80-84, 257-259 and 368-370, and `review.md` line 15;
     `specs/service-test-preview-trust-cutover/runbook.md` lines 34-35 on
     `origin/main`).
     No seed catalog models it (neither `test.json` nor `prod.json` names
     it), and no BI source names an equivalent hold on the PROD Apply
     role; the catalogs cannot show its absence, because they do not
     model the TEST one either. While it is attached, an explicit Deny
     overrides every TEST Apply allow of this plan: every TEST Apply allow
     row of the S5.2 (row 9) and XP-11 (row 42) matrices fails, S4.6 step
     3 fails, and the step-4 apply fails with `AccessDenied`. It also
     blocks XP-9's TEST registry-phase apply, which #284 runs under the
     same role (`specs/test-poc-prerequisite-capability/requirements.md`
     FR2: the fixed ECR repositories and the SES identity), so XP-9 and
     XP-13 depend on it as well. This plan
     does not remove, narrow or bypass it. Its retirement is BI's own
     reviewed activation and a named external precondition, **XP-18**
     (PRD §7), before row 9's first TEST Apply allow row; XP-18 also
     reads back the PROD Apply role's inline policies before row 9's PROD
     part. Gate 1 checks it, S4.6 step 3 reads it back, and step 4's
     STOP routes an explicit-deny `AccessDenied` to it rather than to an
     S4.3 `resume`.
  3. **Permissions boundary: seed-owned, amended by a seed catalog
     amendment.** The Preview, Apply and Drift roles carry
     `GovernanceBoundary-user-service-infrastructure-{env}`
     (`pulumi/infra/governance.py` lines 486-497, with
     `permissions_boundary` at line 492; the ARN is built at lines
     98-109). The same boundary also bounds the ConfigRead roles
     `GitHubCiConfigRead-user-service-infrastructure-{env}` and
     `…-test-pr` (TEST) or `…-prod-preview` (PROD) (the catalog
     `principals`; pre-commit audit 4). BI renders its content in
     `pulumi/infra/governance_automation.py` `service_boundary_policy`
     (lines 422-455): `sts:GetCallerIdentity`, the state-bucket S3
     actions, the Pulumi KMS alias, the repository's CI secret reads, and
     the TEST PoC statements while the capability is rendered. The
     installed policy is seed-owned: an `existing_capability_boundary`
     with ownership `existing_operator_policy_transfer_to_seed` in the
     seed catalog (TEST `test.json` lines 307-319, template `4a170a1c…`;
     PROD `prod.json` lines 307-319, template `b331c0c6…`), whose catalog
     hashes are pinned in `pulumi/seed/policy_registry.py` lines 18-21
     (`CATALOG_HASHES`). #219 needed a dedicated seed amendment for its
     boundary change (`pulumi/seed/test_poc_prerequisite_amendment.py`
     lines 1-5 (no AWS calls; a live CloudFormation owner and the
     observed policy versions must be authenticated before a change set
     runs), 20-40 (the target policies, the result catalog hash and the
     baseline policy hashes) and 58-72 (the statement replacement and the
     6144-character check); prepared on `origin/main` by #274, commit
     `1ed394d`; identical in `wt-boot-219`). So **every boundary addition
     goes through a seed catalog amendment** with a new catalog hash pin
     in `policy_registry.py`, a named seed owner, CloudFormation
     change-set evidence and `@Kravalg`'s approval, in addition to the BI
     security review of the identity change. This applies to XP-11,
     S5.24a, S5.24b, the XP-14 PROD `s3:GetBucketVersioning` addition,
     and every other BI grant story that gives these roles a new allow
     (S5.2, whose amendment also covers S5.5's later exact-ARN
     `secretsmanager:PutResourcePolicy` and `GetResourcePolicy` through
     the `secret:rds!cluster-*` pattern, S5.17, the S5.4 identity
     statements; `epics-stories.md` Epic 5). A boundary addition changes
     no ConfigRead role's effective permissions, because their identity
     policies do not change; the matrices assert that (ConfigRead rows).
  4. **Seed guard: unchanged relative to the story's baseline catalog
     (R11-M1).** No story of this plan narrows a guard's Resource-`*`
     deny or an SSM or token deny. The catalog guard entries still change
     where a story adds statements or exact ARNs: S5.2's PassRole
     fragments add deny statements to the USI Preview, Drift and Apply
     guards of both environments (layer 6), and a new managed policy
     joins the governance guard's lists (layer 5). So each
     matrix's guard-layer rows compare a guard with the story's
     **baseline catalog** (the result catalog of its predecessor in the
     one-open serialization below), not with `origin/main`. The
     statement and template hashes below are the `origin/main` values.
     Each USI CI role has an attached,
     hash-pinned `immutable_managed_guard` in the seed catalog. TEST
     (`pulumi/seed/catalogs/test.json`): Preview and Drift, lines
     712-761, both with statement `ae950d73…` (lines 3273-3299; Deny,
     Resource `*`); Apply, lines 649-663, with statement `9f269660…`
     (lines 3102-3118; Deny, `NotResource` the `/{project}/ci/*`
     secrets). PROD (`pulumi/seed/catalogs/prod.json`): Apply lines
     649-663 with statement `ce12c400…` (lines 3711-3727); Drift lines
     712-725 and Preview lines 747-760, both with `ae950d73…` (lines
     3277-3303). These statements deny `ssm:GetParameter*` and
     `ecr:GetAuthorizationToken`. With D-15 and the token-free image read
     no guard narrowing is needed: these statements do not change, and
     the observation reads change no guard template hash or catalog guard
     entry. The new allows are blocked by
     no guard statement; the only other guard statement whose actions
     match them (`d413d73a…` TEST, `aec83856…` PROD, `Action: *`) is
     limited to the seed's own bucket, KMS key and secrets. The token
     fallback of point 1 would also have to narrow these guards, which
     stays a user decision amending NFR-06.
  5. **Seed attachment constraint: where the Apply allows live
     (pre-commit audit 1).** The seed's `verify_active_enrollment`
     (`pulumi/seed/policy_registry.py` lines 554-591, with `_verify_mutable_role` at 554-567) lets the USI Apply
     role hold only its guard plus the managed policies that
     `_mutable_attachment_sets` names (lines 532-551: `-pulumi-backend`
     and `-secret-read-deny`; #219 adds the TEST `-poc-prerequisites` in
     `wt-boot-219` lines 542-546). Every other enrolled role keeps its
     exact attachment set. BI attaches every Apply document as its own
     customer-managed policy (`pulumi/infra/ci_bootstrap.py` lines
     770-773 and 814-842), and the governance apply role may write only
     the policy names of `_managed_policy_resources`
     (`pulumi/infra/governance_automation.py` lines 480-489). Preview and
     Drift documents are inline role policies, which the seed does not
     pin for these roles, so **new Preview and Drift allows go into their
     existing inline documents**. **Inline size check (pre-commit recheck N1):** IAM
     limits the aggregate size of a role's inline policies to 10,240
     characters (whitespace is not counted), and the Preview and Drift
     roles already carry inline documents. S5.17, S5.4 (the Preview and
     Drift KMS read), XP-11, S5.24a and S5.24b therefore each record, in
     their PR, the aggregate rendered inline size of every role they
     touch (the current documents plus the new allows) and fail an offline
     check above 10,240 characters. For the Apply role: the TEST XP-11
     allows go into the TEST `-poc-prerequisites` managed policy that
     #219 admits, within 6144 characters.
     For the PROD Apply role, S5.24a's reads go **fit-first** (R12-m4)
     into one of S5.2's PROD Apply managed policies (row 9, already in
     `_managed_policy_resources`, the governance ceilings' read lists and
     `G-GitHubGovernanceApply`'s two `NotResource` lists), within 6144
     characters; only if no S5.2 PROD Apply policy has room does S5.24a
     create a new one. So the NFR-06 condition "only because the size
     limits leave no other design" holds for every new policy.
     **A new managed policy for a USI CI role (R11-m1).** Any new Apply
     managed policy (S5.2's workload capability, which does not fit the
     existing `-pulumi-backend`, `-secret-read-deny` or TEST
     `-poc-prerequisites` documents; S5.24a's PROD reads only if no S5.2
     PROD Apply policy has room; or XP-11 if it does not fit) and any new
     Preview or Drift managed policy (the inline-overflow fallback above)
     must be writable by the
     governance apply role, `GitHubGovernanceApply`, and readable by its
     Preview and Drift runs. #219's amendment shows the full set for one
     policy (`pulumi/seed/test_poc_prerequisite_amendment.py` lines
     114-145, identical in `wt-boot-219`). Each such policy therefore
     needs these changes in one seed review and one serialization slot:
     1. the governance Preview ceiling
        `issue215-seed/{env}/ceiling/C-GitHubGovernancePreview`
        (`test.json` lines 435-454): its policy-read statement (the
        second, `339af045…` on `origin/main`, `f16f9131…` after #284,
        PROD `6227eeae…`; `iam:GetPolicy`,
        `GetPolicyVersion`, `ListEntitiesForPolicy`, `ListPolicyTags`,
        `ListPolicyVersions`) gains the policy ARN in `Resource`
        (amendment lines 114-130);
     2. the governance Drift ceiling
        `issue215-seed/{env}/ceiling/C-GitHubGovernanceDrift`
        (`test.json` lines 415-434), the same statement, the same change
        (after #284 the TEST ceiling templates are `b97d4596…` Preview
        and `02517ab5…` Drift);
     3. the governance apply guard
        `issue215-seed/{env}/guard/G-GitHubGovernanceApply` (`test.json`
        lines 599-614): its `iam:*` statement (`8c068aaa…` on
        `origin/main`, lines 2915-2931; PROD `9fb811f6…`) gains the
        policy ARN in `NotResource` (amendment lines 132-135);
     4. the same guard's policy-write statement (`5366ec11…` on
        `origin/main`, lines 2493-2508; PROD `06267ab9…`), which denies
        `iam:CreatePolicy`, `CreatePolicyVersion`, `DeletePolicy`,
        `DeletePolicyVersion`, `SetDefaultPolicyVersion`, `TagPolicy`
        and `UntagPolicy` outside its `NotResource` list, gains the
        policy ARN (amendment lines 136-144). #284 already rewrites these
        two statements of the TEST guard (template `b6d1a587…`,
        statements `21195ff8…` and `bb116727…`), so a TEST story edits
        the post-#284 statements;
     5. the governance write scope, `_managed_policy_resources`
        (`pulumi/infra/governance_automation.py` lines 480-489), which
        today resolves only the Apply role's `pulumi-backend`,
        `secret-read-deny` and, for TEST, `poc-prerequisites` names and
        gains the new name (a Preview or Drift policy needs its own
        resolution there).

     Plus the seed attachment rule: `_mutable_attachment_sets` for an
     Apply policy, or the role's catalog `attachment_arns` and its
     attachment rule in `policy_registry.py` for a Preview or Drift
     policy. The USI Apply guard itself
     (`issue215-seed/{env}/guard/GitHubCiApply-user-service-infrastructure`,
     `test.json` lines 649-663) has no policy-write statement, so it does
     not change for a new policy. Each matrix has a
     `verify_active_enrollment` row (the Apply role's attachment set is
     inside the permitted set, every other role's is exact) and
     exact-ARN rows for the governance apply role (layer 6).
  6. **Principal creation: independent CloudFormation owners
     (R11-M1).** This plan creates new roles: the TEST and PROD ECS
     execution and task roles, the app-rotation, redeploy and
     bootstrap-job function roles, the TEST restore-operator,
     restore-reader and exercise roles, and the TEST and PROD recovery
     roles. It also grants on them (S5.4, S5.23, S5.18a, S5.5, S5.18b)
     and passes them (S5.2 to ECS; the function roles to Lambda). No CI
     or operator principal may create a role, and none may grant on a
     role that its guard does not name (BI `origin/main`,
     `pulumi/seed/catalogs/test.json`; PROD `prod.json` has the
     same guard entries, with account-specific statement hashes and
     different statement lines where noted: PROD `a9609b86…` is
     at `prod.json:3208` (TEST `94cec98a…`, 3000), `06267ab9…` at 1767 (TEST
     2493) and `9fb811f6…` at 3061 (TEST 2915)):
     - the platform apply guard
       `GitHubCiApply-bootstrap-infrastructure` (lines 629-648) and the
       `PulumiAutomation-bootstrap-infrastructure` and
       `PulumiDeploy-bootstrap-infrastructure` guards (lines 978-1015)
       carry `8f75c4a5…` (lines 2944-2975): Deny `iam:CreateRole`,
       `iam:CreatePolicy*` and `iam:PutRolePermissionsBoundary`, among
       others, on Resource `*`. The platform apply guard also carries
       `94cec98a…` (lines 3000-3020, PROD `a9609b86…`: Deny `iam:Put*`,
       `iam:Attach*`, `iam:Update*`, `iam:TagRole` and others outside
       `s3-backup-role-ac43c65`) and `4fae8daf…` (lines 2483-2492, PROD
       `473c8904…`: Deny `iam:PassRole` outside four named roles);
     - the governance apply guard `G-GitHubGovernanceApply` (lines
       599-614) carries `dc27f076…` (lines 3815-3829: Deny
       `iam:CreateRole` on `*`) and `8c068aaa…` (lines 2915-2931: Deny
       `iam:*` outside the GitHub OIDC provider, the six USI CI roles,
       the two USI boundaries and the two USI Apply policies);
     - the USI Apply guard (lines 649-663) carries `dc27f076…` too, and
       the USI Preview and Drift guards (lines 712-761) carry
       `ae950d73…`, whose actions include `iam:CreateRole` on `*`;
     - the operator Apply guards: `GitHubOperatorApply-closed-actions`
       (lines 801-809) is `01dcac0c…` (lines 1671-1701), a Deny on every
       action outside its `NotAction` list, which lacks `iam:CreateRole`;
       and `GitHubOperatorApply-iam-write` (lines 843-852) carries
       `455fe8d0…` (lines 2411-2439), which denies `iam:PutRolePolicy`,
       `iam:AttachRolePolicy` and the other role writes outside its named
       roles.

     **Route: an independent CloudFormation owner per role family**, as
     BI itself set it for the #219 publisher in #285 (`wt-boot-219`
     `54e9e2f`): a publisher-only stack with its own reviewed template
     (`pulumi/seed/poc_runtime_fence_stack.py`: `DeletionPolicy` and
     `UpdateReplacePolicy` `Retain`, lines 98-99 and 113-114; a
     permanent stack policy that denies `Update:*`, lines 165-166), a
     separately authenticated installer that verifies absent names and
     complete change-set provenance
     (`specs/219-test-workload-capability/runtime-enrollment.md` lines
     26-30), a post-create verifier
     (`pulumi/seed/poc_publisher_stack_verification.py`
     `verify_publisher_stack`, line 197) and a reviewed amendment path
     (`runtime-enrollment.md` lines 247-302: a review-only UPDATE change
     set, `update-stack` with a narrow
     `--stack-policy-during-update-body`, the permanent policy read back
     unchanged, `verify_amended_publisher_stack`). Each stack of this
     plan has:
     - a reviewed template in BI and its SHA-256, recorded in the PR;
     - a human, non-root installer outside GitHub CI, named and reviewed
       in the PR (the coordinator's direction; #285 requires the
       separately authenticated installer above and a named, reviewed
       holder for its break-glass path, `runtime-enrollment.md` lines
       236-239). **The installer identity is the external precondition
       XP-17 (R12-m1; PRD §7), before row 8:** a reviewed non-root
       installer role of the same class as #284's
       `--installer-role-arn` (`wt-boot-pr280`
       `specs/test-poc-prerequisite-capability/post-seed-activation.md`
       lines 200-236: an already-issued non-root installer session,
       authenticated by STS identity and immutable RoleId), with the
       minimum permissions XP-17 lists and per-install evidence (caller
       ARN, RoleId, MFA present, non-root). The seed catalog holds
       exactly 24 principals and no installer (`test.json` lines
       1143-1568; `pulumi/seed/README.md` lines 14-24 and 167-170), and
       BI records that no authenticated live installer exists yet
       (`wt-boot-219` `specs/219-test-workload-capability/installability-stop.md`
       lines 5-10). So **the seed does not guard this identity** (a
       recorded residual): its bounds are its own reviewed policies,
       the per-install evidence and the stack policies;
     - a CREATE change set whose rows are exactly the reviewed `Add` rows,
       with the `DescribeChangeSet` output kept as evidence, and a
       preflight that the stack, role and policy names are absent;
     - a post-create verifier modelled on `verify_publisher_stack`
       (`CREATE_COMPLETE`, canonical template, termination protection,
       the permanent deny-update stack policy, the exact resources, each
       role's trust, boundary, attachments, inline policies and tags,
       and each function's role, package digest and `VpcConfig`);
     - `@Kravalg`'s approval.

     Each role holds its grants as inline `Policies` of its
     `AWS::IAM::Role` resource, so adding or removing a grant is a
     `Modify` row on that role (`Replacement: False`), never a `Remove`
     row of a retained policy resource, which would leave the grant in
     IAM. A later grant, function or function setting of a family is a
     **reviewed stack amendment** by the same kind of installer: a
     reviewed amended template and its hash, a review-only UPDATE change
     set whose rows are exactly the reviewed `Add` and `Modify` rows (no
     `Replacement: True`, no `Remove`), `update-stack` with a
     during-update policy that allows only those logical IDs, the
     permanent policy read back unchanged, a post-update verifier on
     `UPDATE_COMPLETE`, and `@Kravalg`'s approval.

     | Stack (per family) | Created by | Holds at creation | Later reviewed amendments |
     | --- | --- | --- | --- |
     | ECS runtime, TEST and PROD (one stack each) | S5.1 (row 8) | the execution and task roles (path `/`) with their ECS trust, one retained `-Boundary` and one retained workload-shaped `-Guard` managed policy per role at `/issue219/{env}/{boundary,guard}/` (R12-M2, below), and every S5.1 grant: for the execution role the secret reads, `logs:CreateLogStream`/`logs:PutLogEvents` on the stack's two ECS log groups and, for TEST, #219's `execution_policy()` ECR pull grant; for the task role SQS, SES and `elasticache:Connect` | S5.4 (row 11: the AD-15a identity rows as `Modify` rows on the roles **and** `Modify` rows on the boundary and guard policies, which gain the same KMS actions); PROD only, S5.24a (row 50, after XP-14): the PROD execution role's ECR pull grant and the matching boundary and guard rows on XP-14's repositories |
     | function roles, TEST and PROD | S5.1 (row 8) | the app-rotation, redeploy and bootstrap-job roles with their S5.1 grants | S5.4 (the app-rotation AD-15a row, row 11); S5.3 (row 13: the app-rotation and seed, redeploy and bootstrap-job functions, as `Add` rows); S5.5 (inside row 43: in S4.6 steps 5-6 the bootstrap-job exact-ARN secret read, its scoped Lambda network-interface grant (R12-m2, below; kept for the life of the function) with the source-function deny, and the function's `VpcConfig`; in step 18 the `VpcConfig`-only detach; in step 20 the re-attach with the rebuilt XP-8 subnet and SG IDs, the grant re-scoped to them and the new secret ARN; R12-m3) |
     | restore, TEST | S5.1 (row 8) | the restore-operator and restore-reader roles, trust only | S5.18a (row 42: the grants and the reader function without `VpcConfig`); S5.18b (inside row 43: the reader's scoped network-interface grant (kept for the life of the function) and `VpcConfig` in step 5, the `VpcConfig`-only detach in step 18, the re-attach in step 20 with the rebuilt subnet and SG IDs and the grant re-scoped to them); S4.8 (row 45, only if V-19 selects the ephemeral exact-ARN reader grant: its add and its removal) |
     | exercise, TEST | S5.1 (row 8) | the exercise role, trust only (S5.4's runtime key policy names it, AD-15a) | S5.4 (its AD-15a row, row 11); S5.23 (its other grants, row 33) |
     | recovery, TEST | S5.7 (row 34) | the recovery role with every S5.7 grant | none planned |
     | recovery, PROD | S5.19 (row 47) | the recovery role with every S5.19 grant | none planned |
     | service-linked roles, per account, only if a read finds one missing | S5.1 (row 8) | `AWS::IAM::ServiceLinkedRole` for each missing one of the five (R11-m2) | none |

     The exercise and restore roles are created in S5.1, trust only,
     because S5.4's key policy names the exercise role (KMS rejects a key
     policy whose principal does not exist) and the S3.3 endpoint policy
     binds the restore-reader ARN (AD-12a); their grants arrive with the
     stories that own them (S5.23, S5.18a). **The Lambda
     network-interface grant, scoped (R11-M1 audit and recheck N1;
     re-scoped in revision 12, R12-m2):** a function with a `VpcConfig`
     needs, on its execution role, the documented set
     `ec2:CreateNetworkInterface`, `ec2:DescribeNetworkInterfaces`,
     `ec2:DescribeSubnets`, `ec2:DeleteNetworkInterface`,
     `ec2:AssignPrivateIpAddresses` and `ec2:UnassignPrivateIpAddresses`.
     The AWS Lambda guide lists them and says to allow them on
     `"Resource": "*"` ("Giving Lambda functions access to resources in
     an Amazon VPC",
     <https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc.html>,
     section "Required IAM permissions"), but it does not say that they
     lack resource-level support. The Service Authorization Reference
     for Amazon EC2 ("Actions, resources, and condition keys for Amazon
     EC2",
     <https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonec2.html>,
     read 2026-10-01 in its published machine-readable form,
     <https://servicereference.us-east-1.amazonaws.com/v1/ec2/ec2.json>,
     version v1.4) lists these resource types:
     `CreateNetworkInterface`: `network-interface`, `security-group` and
     `subnet` (condition keys include `ec2:SubnetID`,
     `ec2:SecurityGroupID` and `ec2:Vpc` on the subnet and security
     group); `DeleteNetworkInterface`, `AssignPrivateIpAddresses` and
     `UnassignPrivateIpAddresses`: `network-interface`, with the
     resource condition keys `ec2:Subnet` and `ec2:Vpc` (type ARN);
     `DescribeNetworkInterfaces` and `DescribeSubnets`: no resource type.
     So the grant is:
     - `ec2:CreateNetworkInterface` on the XP-8 subnet ARNs
       (`arn:aws:ec2:eu-central-1:<account>:subnet/<id>`), the XP-8
       bootstrap-job SG ARN (`…:security-group/<id>`) and
       `arn:aws:ec2:eu-central-1:<account>:network-interface/*` (the new
       ENI's ID is not known in advance);
     - `ec2:DeleteNetworkInterface`, `ec2:AssignPrivateIpAddresses` and
       `ec2:UnassignPrivateIpAddresses` on
       `arn:aws:ec2:eu-central-1:<account>:network-interface/*` with
       `ArnEquals ec2:Subnet` = the XP-8 subnet ARNs;
     - `ec2:DescribeNetworkInterfaces` and `ec2:DescribeSubnets` on
       `"*"`, the only part without a resource scope, because the EC2
       reference lists no resource type for them (the NFR-06 rule for
       such actions).

     No EC2 condition narrows the Describe pair, and the Lambda page's
     condition keys `lambda:VpcIds`, `lambda:SubnetIds` and
     `lambda:SecurityGroupIds` apply to the caller of `CreateFunction`
     and `UpdateFunctionConfiguration` (the Lambda service reference,
     <https://servicereference.us-east-1.amazonaws.com/v1/lambda/lambda.json>,
     lists them on those two actions), not to the execution role. **Open
     point V-29 (live, fail closed):** the Lambda guide documents only
     the `*` form, so whether the service accepts the scoped grant is
     proven live by the first attach amendment (S4.6 step 5): its
     post-update verifier requires the function `State` `Active`,
     `LastUpdateStatus` `Successful` and a `lambda` ENI in the XP-8
     subnets, and the step-18 check requires that ENI deleted within 45
     minutes. The reader attaches to the same subnets and SG, and Lambda
     shares a Hyperplane ENI between functions with the same subnet and
     SG combination (the same page), so the reader may create no ENI of
     its own; its grant is proven only where CloudTrail shows a
     `CreateNetworkInterface` or `DeleteNetworkInterface` call under the
     reader role, and otherwise the bootstrap job's first attach is the
     Create evidence. A refusal or a failed update is a STOP; the
     fallback, each step a reviewed stack amendment and each re-proven by
     V-29, is: (1) drop the `ec2:Subnet` condition; (2) widen the four
     mutating actions to the resource-type wildcards in the region and
     account (`…:subnet/*`, `…:security-group/*`,
     `…:network-interface/*`); (3) widen them to
     `arn:aws:ec2:eu-central-1:<account>:*`. If the service still refuses,
     the fallback is exhausted: STOP, then a **user decision** to amend
     NFR-06 to the documented `"Resource": "*"` form (with the
     `lambda:SourceFunctionArn` deny); this plan does not take it.
     The grant is bounded three more ways. (1) It sits only on the
     bootstrap-job and restore-reader execution roles, and is created
     only by the human stack amendment that also adds the `VpcConfig`
     (the function depends on the role). (2) Each of those roles carries
     the deny the same page recommends: `Deny` of the six actions plus
     `ec2:DetachNetworkInterface` on `*` with `ArnEquals
     lambda:SourceFunctionArn` = the function's own ARN, so the
     function's code cannot call EC2 while the Lambda service still can.
     (3) Every other principal is unchanged. **Who can re-point or
     re-code the functions (R12-m2; audit of revision 12):** stack
     policies restrict only CloudFormation updates, not direct Lambda
     calls, and `lambda:UpdateFunctionCode` would run any code as the
     bootstrap-job role (the DocumentDB secret read) or the reader role.
     So every stack amendment that adds a function or changes its code or
     `VpcConfig` (S5.3 at row 13 for the three function-role functions,
     S5.18a at row 42 for the reader, then S5.5 and S5.18b in row 43)
     carries simulator rows that `lambda:UpdateFunctionConfiguration` and
     `lambda:UpdateFunctionCode` on every function of that stack are
     denied to every CI and operator principal that exists at that row
     (the TEST recovery role from row 34 on): the USI Preview, Apply,
     Drift, recovery and exercise roles (simulated by the TEST Preview
     role, whose S5.17 grant from row 10 covers them; every PROD USI role
     by the BI owner, because S5.24 gives the PROD Preview role
     `iam:SimulatePrincipalPolicy` on the PROD execution role only and
     this plan does not widen it) and `GitHubGovernanceApply`,
     `GitHubCiApply-bootstrap-infrastructure`,
     `PulumiAutomation-bootstrap-infrastructure`,
     `PulumiDeploy-bootstrap-infrastructure` and the operator Apply role
     (run by the BI owner with a BI identity, "Who runs which rows"). An
     allowed row is a STOP for that amendment and then a **user
     decision**: the remedy (for example the documented
     `lambda:VpcIds`/`lambda:SubnetIds` caller conditions, or a deny of
     the update actions on these functions, added to that principal's
     guard) is a seed-guard change outside NFR-06's closed list of guard
     changes, so it amends NFR-06; this plan takes no such decision. Only
     the XP-17 installer may update the functions. **Lifecycle decision
     (recheck N1): the grant lives as long as the function, and only the
     `VpcConfig` is removed by the detach amendment.** The Lambda VPC guide
     (<https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc.html>)
     says only that "Lambda relies on permissions in the function
     execution role" to manage the ENIs, so the plan keeps the grant on
     both roles, and Lambda deletes an unused Hyperplane ENI only after
     no other function or published version uses it; the page says this takes up to 20 minutes (older
     guidance said up to 45, so the plan uses 45), and that deleting the
     role first leaves the ENI for a manual delete. Removing the grant in
     the detach amendment would therefore strand the ENI, which blocks the
     SG and subnet deletes. Keeping the grant needs no second removal
     amendment and no wait between two human steps, and the extra
     exposure is nil because of the source-function deny. **Rebuild
     (R12-m3):** the step-19 abandon deletes the USI subnets and the
     bootstrap-job SG (the manifest retains only the log-bucket families
     and the retained secrets), so the rebuild has new subnet and SG IDs
     and XP-8 items 1-4 all repeat (item 4, the Apply-role secret-policy
     re-grant, is a governance change, not a seed operation). The step-20 re-attach (S5.5
     for the bootstrap job, S5.18b for the reader) therefore `Modify`s
     the grant's subnet and SG ARNs and the `ec2:Subnet` condition to
     the rebuilt ones together with the `VpcConfig` (the old ENIs are
     already gone, by the step-18 check), and S5.5 also moves the secret
     read to the new managed-secret ARN. The grant leaves with the
     function (a later stack amendment that removes the function and the
     role's grant together, after the ENI check below shows no Lambda ENI
     in the XP-8 subnets). The ENI check is read-only
     `ec2:DescribeNetworkInterfaces` filtered on the XP-8 `subnet-id`
     values and `interface-type` = `lambda`, polled for up to 45 minutes
     after the detach.

     **Functions that run as S5.1 roles live in the owning stack (not
     by guard narrowing).** A Lambda function with one of these roles
     needs `iam:PassRole` on it. The platform apply guards deny
     `iam:PassRole` outside four named roles (`4fae8daf…`, in the platform
     apply, `PulumiAutomation`, `PulumiDeploy`,
     `GitHubCiPreview-bootstrap-infrastructure` and
     `G-GitHubCiDrift-bootstrap-infrastructure` guards; PROD
     `473c8904…`). Adding the function roles to that list would narrow a
     guard deny where a non-weakening design exists, which NFR-06 does
     not allow. So the function itself belongs to the stack that owns
     its role: S5.3 adds the three functions to the function-role stacks
     and S5.18a the reader to the restore stack, each with its reviewed
     package digest; the human installer passes the role. BI CI keeps
     the rest of S5.3 (the log groups with the runtime CMK, created
     before the functions; the Lambda permissions; the
     `RotationSucceeded` rule, which follow the amendment because they name
     the functions), none of which passes a role. The cost: every
     function code or `VpcConfig` change (S5.3, S5.5, S5.18a, S5.18b,
     including the S4.6 step-18 `VpcConfig` detach and step-20 re-attach)
     is a human stack amendment.

     **The TEST ECS roles have one owner: S5.1.** #219 already proposes
     the same names (`user-service-infrastructure-test-EcsExecution` and
     `-EcsTask`; BI `origin/main` `pulumi/seed/poc_pass_role.py` lines
     16-19, and `PocRuntimeRoles` in `pulumi/infra/poc_runtime_enrollment.py`
     line 112, which registers them in the governance project). S5.1
     adopts #219's runtime-role and PassRole fragments as its template
     input: the names, the ECS trust (`ecs-tasks.amazonaws.com` with
     `aws:SourceAccount` and `aws:SourceArn`, `runtime-enrollment.md`
     lines 106-107), and `propose_pass_role` (`poc_pass_role.py` lines
     42-94), which S5.2 applies. S5.1 does not defer to #219's later
     "reviewed runtime amendment" (`runtime-enrollment.md` lines 12-16,
     55, 315-322 and 360-363), because that amendment would amend the
     governor's identity, boundary and immutable guards for the two
     roles (lines 360-363), which is the governor-guard route this plan
     does not choose, and no story of this plan owns or schedules it.
     #219's reason for leaving the ECS fences out of its publisher stack
     (lines 12-16: a deny-update stack would freeze them before the
     workload's log, secret, KMS, SQS and SES grants exist) does not
     apply to S5.1's stack, which holds the complete S5.1 grant set at
     creation; the later KMS rows are reviewed amendments. S5.1's
     preflight requires both names absent (`iam:GetRole` returns
     `NoSuchEntity`) and `PocRuntimeRoles` still unregistered (no module
     under BI `pulumi/` or `scripts/` imports `poc_runtime_enrollment`,
     by grep); either failing is a STOP, and the BI review records that
     S5.1's stack replaces #219's later runtime amendment for these two
     roles. **S5.2 applies all of `propose_pass_role` on S5.1's two
     ARNs** (and the same shape on the PROD ARNs): for Apply, the
     identity allow `PassOnlyTestEcsRuntimeRoles` (the two ARNs, only
     to `ecs-tasks.amazonaws.com`), the same allow in the boundary
     through S5.2's seed amendment, and the guard statements
     `DenyPassingOtherRoles` and `DenyPassingRolesOutsideEcsTasks`; for
     Preview and Drift, the identity and guard statement
     `DenyReadRolePassRole`, which keeps the read roles from using the
     shared boundary allow. So the Preview, Drift and Apply guard
     template hashes of both environments change in S5.2 (layer 4). The
     ConfigRead roles share the boundary but not the identity allow, so
     their `iam:PassRole` stays denied (ConfigRead rows).

     **The ECS roles' boundaries, guards and execution-role grants: S5.1
     creates them (R12-M2; audit of revision 12).** USI admission requires
     each ECS role to have path `/` and the permissions boundary
     `arn:aws:iam::<account>:policy/issue219/{env}/boundary/{name}-Boundary`
     (`scripts/poc_workload_capabilities.py` `_role`, lines 89-117, the
     boundary check at lines 106-116; S4.14 makes `test` the request's
     stack), and `_pull` (lines 193-232, called at line 338 with the
     execution role) simulates `ecr:GetAuthorizationToken` on `*` and
     `ecr:BatchCheckLayerAvailability`, `ecr:BatchGetImage` and
     `ecr:GetDownloadUrlForLayer` on each registry ARN, with
     `aws:RequestedRegion`, and requires every row `allowed` **and**
     `AllowedByPermissionsBoundary` (`_decision`, lines 160-191). The
     task definitions use the `awslogs` driver (`pulumi/app/compute.py`
     lines 727-734) on the log groups `/aws/ecs/<stack_tag>/web` and
     `/worker` (lines 223-233), which the execution role writes. #219
     proposes all of this only as unwired source: the boundary and guard
     ARNs (`wt-boot-219` `pulumi/seed/poc_runtime.py` `policy_arn`, lines
     66-73), the execution role's `execution_policy()` (lines 166-168,
     rendered by `_ecr_policy`, lines 191-210: `sts:GetCallerIdentity`
     and `ecr:GetAuthorizationToken` on `*` and the three pull actions on
     the two TEST repositories `REPOSITORY_ARNS`, each ECR allow with
     `aws:RequestedRegion`), its guard `_ecr_guard` (lines 213-235), the
     role registration with `permissions_boundary`
     (`pulumi/infra/poc_runtime_enrollment.py` lines 127-147), and the
     explicit exclusion of the four ECS fences from its stack
     (`runtime-enrollment.md` lines 12-16 and 95-104). This plan does not
     adopt #219's later runtime amendment (above), so **S5.1's ECS
     runtime stack of each environment creates, per role:**
     - the `{name}-Boundary` managed policy at path
       `/issue219/{env}/boundary/` (`AWS::IAM::ManagedPolicy`,
       `DeletionPolicy` and `UpdateReplacePolicy` `Retain`), set as the
       role's `PermissionsBoundary`. Its content covers every grant of
       that role and nothing else, and it changes only by `Modify` rows
       (a `PolicyDocument` update is "No interruption" for
       `AWS::IAM::ManagedPolicy`, while a name or path change is
       "Replacement": CloudFormation template reference
       <https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-iam-managedpolicy.html>,
       read 2026-10-01): for the execution role `sts:GetCallerIdentity`,
       the secret reads, the two log-stream writes, the `_pull` set (TEST
       at creation; PROD later, below) and (S5.4) `kms:Decrypt` on the
       runtime CMK via Secrets Manager; for the task role SQS, SES,
       `elasticache:Connect` and (S5.4) the JWT and 2FA key actions;
     - a workload-shaped `{name}-Guard` managed policy at
       `/issue219/{env}/guard/` (`Retain`), attached to the role. #219's
       own guard documents are not adopted as they are: the execution
       guard denies every action outside ECR pull and
       `sts:GetCallerIdentity` (`_ecr_guard`) and the task guard and
       boundary are deny-all (`poc_runtime.py` line 276), so they would
       block the secret, log, KMS, SQS and SES grants. But the guard's
       purpose stays (`runtime-enrollment.md` lines 88-92): a permissions
       boundary does not limit a same-account resource-based policy that
       names the role session, so an explicit deny is still needed. S5.1's
       guard therefore follows #219's shape over the workload set: a
       `Deny` with `NotAction` equal to the role's action set; one
       `Deny Action=<group> NotResource=<exact ARNs or patterns>` per
       action group of the role, with the NotResource equal to that
       group's resources in the `-Boundary` (the ECR pull actions on the
       stack's two repositories; the secret reads on the exact secret
       patterns; the two log-stream writes on the `log-stream` ARNs; for
       the task role the SQS, SES and `elasticache:Connect` actions on
       their exact ARNs), so a same-account resource policy naming the
       role session cannot reach any other resource of a service the role
       uses; and a `Deny` of the ECR actions when `aws:RequestedRegion` is
       not `eu-central-1`. S5.4's amendment adds the KMS actions to the
       `NotAction` list and a `Deny Action=kms:Decrypt` (and, for the task
       role, the JWT and 2FA key actions) with `NotResource` the runtime
       CMK (or the JWT and 2FA key ARNs) by `Modify` rows; S5.24a adds the
       PROD ECR group's `NotResource` deny the same way;
     - the execution role's inline pull grant, #219's `execution_policy()`
       shape with the environment's account and repositories (for TEST
       exactly #219's document on `user-service-test-web` and
       `-worker`);
     - the execution role's `logs:CreateLogStream` and
       `logs:PutLogEvents` on
       `arn:aws:logs:eu-central-1:<account>:log-group:/aws/ecs/<stack_tag>/{web,worker}:log-stream:*`
       (the Logs service reference lists `log-stream` as their resource
       type).

     **The PROD ECR part waits for XP-14 (audit of revision 12,
     finding 1).** The PROD repository names belong to XP-14 (row 48;
     PRD §7), so S5.1's PROD stack at row 8 creates the PROD roles,
     boundaries and guards **without** the ECR pull grant and without the
     `_pull` rows in the boundary and guard. **S5.24a (row 50) owns the
     PROD ECS runtime stack amendment** that adds them on XP-14's two PROD
     repositories (`Modify` rows on the role and on both policies), before
     its catalog amendment. No PROD `_pull` runs before gate 2a (S4.7, row
     52), so nothing uses the grant earlier. Each boundary and guard is
     one managed policy of at most 6144 characters; S5.1, S5.4 and
     S5.24a record the rendered sizes and fail an offline check above
     that. **ARNs taken over from #219 (for the BI review):** these four
     TEST policy ARNs are the ones #219's later runtime amendment
     reserves, and the obsolete staged change sets on the
     `REVIEW_IN_PROGRESS` stack `issue219-runtime-fences-test`
     (`runtime-enrollment.md` lines 32-49) contain fences with the same
     names. S5.1's preflight requires them absent (a collision is a
     STOP), and the BI review records that S5.1 takes these names over
     and that #219's runtime amendment is withdrawn or renamed.

     The post-create verifier checks each role's `PermissionsBoundary`
     ARN, its single guard attachment, each policy's default version
     document (equal to the reviewed one) and the `Retain` policies in
     the template; S5.4's and S5.24a's post-update verifiers check the
     amended documents. **Offline regression:** S5.1's PR renders the
     template and asserts, for each ECS role, the `_role` expectations
     (path `/`, the exact boundary ARN) and, for TEST, that the identity
     and boundary documents each carry an `Allow` statement covering every
     `_pull` (action, resource) pair with `aws:RequestedRegion`. It also asserts that each guard's per-group `NotResource` list equals the boundary's resources for that group. USI S4.14
     (row 39) adds `_role`/`_pull` fixtures from S5.1's reviewed TEST
     template as amended by S5.4 (the row-11 template; its hash
     recorded): `get-role` fixtures from the template pass `_role`; a
     structural helper in the test asserts the pull coverage above and
     then feeds stubbed `simulate-principal-policy` rows (`allowed`,
     `AllowedByPermissionsBoundary`) to `_pull`. Negative fixtures: a
     template variant with a wrong boundary path fails with
     `workload-native-role-boundary`; one with a role path other than
     `/` fails with `workload-native-role-identity`; one whose boundary
     lacks `ecr:GetDownloadUrlForLayer` fails the structural helper; a
     stubbed row whose `PermissionsBoundaryDecisionDetail` is not
     `AllowedByPermissionsBoundary` fails with
     `workload-execution-pull-decision`. USI has no offline IAM
     evaluator, so the live proof of the boundary decision is the
     simulator row (S5.1 at row 8 for TEST, S4.6 step 3, S4.7). The PROD
     fixtures use stand-ins for XP-14's repository names, like S4.14's
     other XP-14 rows.
     **XP-16 folded into S5.1:** the PROD boundary path that XP-16 left
     to the bootstrap owner is created by S5.1's PROD ECS runtime stack
     at row 8, so XP-16 needs no row-49 deliverable: S4.14 (row 39) pins
     the name from S5.1's reviewed PROD template and S4.7 verifies it
     live (PRD §7).

     **Not chosen: the governor-guard route.** Narrowing `8f75c4a5…` or
     `dc27f076…`, adding the new roles to the `8c068aaa…` `NotResource`
     list (which widens that statement's exemption, so the governance
     apply role's `iam:*` reaches them; corrected in revision 12,
     R12-n3), or adding `iam:CreateRole` to the `01dcac0c…` `NotAction`
     list would let a CI or operator principal create or write roles.
     Each narrows a Resource-`*` deny, which NFR-06 does not allow, so that
     route would need a user decision amending NFR-06. This plan does not
     take it; NFR-06 stays as it is.

     **Evidence (R11-M1).** Every stack PR and every seed amendment
     carries simulator rows:
     - `iam:CreateRole` is denied, on each new role ARN and on `*`, to
       every CI applier: the USI Preview, Apply and Drift roles, the
       governance apply role, the platform apply role,
       `PulumiAutomation-bootstrap-infrastructure-{env}`,
       `PulumiDeploy-bootstrap-infrastructure` and the operator Apply
       role; the matched statement maps to `8f75c4a5…`, `dc27f076…`,
       `ae950d73…` or `01dcac0c…` through the guard's catalog
       `statement_ids` order;
     - each applier stays limited to exact role and policy ARNs: the USI
       Apply role's `iam:PassRole` is allowed only on the two ECS roles of
       its stack and only to `ecs-tasks.amazonaws.com`, and denied on
       every other role and to every other service, and the Preview and
       Drift roles' `iam:PassRole` is denied everywhere; the platform
       apply, `PulumiAutomation` and `PulumiDeploy` roles'
       `iam:PassRole` on every new role is denied (their four existing
       roles are unchanged); the governance apply role's policy writes
       are allowed only on the policy ARNs of its lists and denied on
       every other policy; `iam:PutRolePolicy` and `iam:AttachRolePolicy`
       on a new role are denied to the USI roles, the governance apply
       role, the three platform appliers and the operator Apply role;
     - for each stack amendment that adds a function or changes its code
       or `VpcConfig` (S5.3, S5.18a, S5.5, S5.18b; R12-m2):
       `lambda:UpdateFunctionConfiguration` and `lambda:UpdateFunctionCode`
       on every function of that stack denied to every CI and operator
       principal (the list in the network-interface paragraph above);
     - for S5.1's ECS runtime stacks (R12-M2): one verifier row per
       boundary and guard policy (the role's `PermissionsBoundary` ARN
       equals `…:policy/issue219/{env}/boundary/{name}-Boundary`, the
       role's only managed attachment is its `-Guard`, and each default
       version document equals the reviewed one), and the TEST execution
       role's `_pull` set simulated `allowed` with
       `AllowedByPermissionsBoundary` (run by the BI owner at row 8,
       because no USI role's simulate grant exists before S5.17; S4.6
       step 3 repeats it live under the Preview role); the PROD rows run
       at S5.24a's PROD ECS amendment (row 50) and live in S4.7;
     - the stack's post-create or post-update verifier output, and the
       XP-17 per-install evidence (caller ARN, RoleId, MFA, non-root).

     **Who runs which rows.** The rows for the TEST USI Preview, Apply
     and Drift roles are simulated by the TEST Preview role, whose S5.17
     simulate grant covers them, and S4.6 step 3 repeats them live. The
     BI owner runs **every PROD USI-role row** with a BI identity in the
     stack or amendment PR, including S5.24a's own PROD ECS `_pull`
     verifier rows, because S5.24's PROD Preview grant covers the PROD
     execution role only (S5.24a's catalog amendment comes after its
     stack amendment, so no wider grant exists when those rows run; this
     plan does not widen it), and S4.7 attaches that output for PROD and
     repeats the execution-role rows live. The rows for the governance,
     platform and operator roles are outside that grant too: the BI owner
     runs them with a BI identity, and S4.6 step 3 and S4.7 attach that
     output rather than simulate it.

  **Boundary size and fallback form (R10-m1).** The boundary is one
  managed policy of at most 6144 characters (`governance_automation.py`
  lines 185-194; the amendment's check at
  `test_poc_prerequisite_amendment.py` lines 69-72), shared by Preview,
  Apply, Drift and the ConfigRead roles. On `origin/main` it renders to
  about 1.2 thousand characters (TEST 1235, PROD 1240, measured over the
  catalog statements). **S5.2's TEST baseline is the post-#284 boundary
  (R11-n2):** #284 replaces the TEST catalog entry with 11 statements,
  template `805998b5…`, which renders to 2894 characters (about 2.9
  thousand; `wt-boot-pr280` `e85534c`, measured the same way). The PROD
  entry is unchanged (template `b331c0c6…`). Amendments cite catalog
  entries by template and statement hash, not by line, because each
  amendment moves the lines. Copying
  every allow of S5.2, S5.17, S5.4, XP-11 and S5.24 into it exactly will
  not fit. So each story that adds boundary content records the rendered
  boundary size in its seed amendment and fails its size check above
  6144. The fallback form, approved in the seed review, is a service or
  resource-family ceiling in the boundary (for example `ecr:BatchGetImage`,
  `ecr:BatchCheckLayerAvailability` and `ecr:GetDownloadUrlForLayer` on
  `arn:aws:ecr:eu-central-1:<account>:repository/user-service-*`), as
  BI's `platform_control_boundary` already caps service and resource
  families while the identity policies keep the exact verb grants
  (`pulumi/infra/platform_iam.py` lines 642-645). The exact allows stay
  in the identity policies, so the effective permission of the Preview,
  Apply and Drift roles is unchanged. A ceiling also raises the
  ConfigRead roles' ceiling; their identity policies do not change, so
  their effective permission does not either, and the ConfigRead rows
  of each matrix prove it (pre-commit audit 4). S5.2 already anticipates several managed policies for the Apply role's
  identity capability (`epics-stories.md` S5.2 attachment quota); the
  boundary itself stays one policy. No boundary addition and no ceiling
  adds an action outside the allows' services, and no deny is widened or
  narrowed by it.

  **Seed operation serialization (R10-m2; R11-M1, R11-n1).** Every seed
  catalog amendment pins its baseline policy hashes and its result
  catalog hash (`test_poc_prerequisite_amendment.py` lines 32-40), and
  every one edits `pulumi/seed/policy_registry.py`: `CATALOG_HASHES`
  (TEST line 19, PROD line 20, adjacent, so a TEST and a PROD amendment
  conflict in one hunk) and, for an Apply attachment change,
  `_mutable_attachment_sets` (lines 532-551). Every independent stack
  install or amendment (layer 6) is checked against the catalog guards
  its verifier and simulator rows read. So **only one seed operation is
  open at a time**, across both catalogs and every stack: a catalog
  amendment, a stack install or a stack amendment. Each rebases on its
  merged and applied predecessor and takes that predecessor's result
  catalog as its baseline (catalog hash, boundary and guard hashes).
  **Facts about #219's bootstrap PRs (R11-n1, verified read-only):**
  #284 (`wt-boot-pr280`, `e85534c`) carries the only #219 catalog
  change, the TEST prerequisite activation: the TEST pin becomes
  `ff2eaf29…` (`policy_registry.py` lines 18-21), the TEST boundary
  becomes 11 statements with template `805998b5…`, the governance
  Preview and Drift ceilings and `G-GitHubGovernanceApply` admit
  `-poc-prerequisites`, `_mutable_attachment_sets` admits
  `GitHubCiApply-user-service-infrastructure-test-poc-prerequisites`
  (lines 542-546), and the packaged TEST capability is
  `"state": "enabled"` (`pulumi/infra/test-poc-identity.json` line 11).
  PROD is unchanged (`d4b56073…`). #285 (`wt-boot-219`, `54e9e2f`,
  which contains #284) changes no catalog hash, no catalog file and no
  `policy_registry.py` line relative to #284; it adds the independent
  publisher stack. Order, with each operation's ordered row:
  1. external precondition, no row: #284 merged and applied before the
     first operation of row 8; its result `ff2eaf29…` is the TEST
     baseline of every later TEST amendment. #285's publisher stack is
     not open while any operation below is open. **Also before row 8
     (R12-m1): XP-17**, the reviewed non-root installer role with its
     minimum permissions (PRD §7); without it no stack install or
     amendment starts (STOP). **Before row 9's first TEST Apply allow
     row (R12-M1): XP-18**, BI's reviewed retirement of
     `Issue215CutoverSessions` on the TEST Apply role, read back absent,
     and the PROD Apply role's inline policies read back with no
     deny-all hold, before row 9's PROD part (STOP otherwise). If BI's
     retirement activation changes a catalog or a stack, it takes the
     one-open slot before row 9, like #284;
  2. row 8, S5.1: the service-linked-role stack of each account, only if
     the preflight read finds one of the five missing (R11-m2); then the
     TEST ECS runtime stack, the PROD ECS runtime stack (each with the
     retained boundary and guard policies; PROD without its ECR part,
     R12-M2), the TEST and PROD
     function-role stacks, the TEST restore stack and the TEST exercise
     stack, one at a time;
  3. row 9, S5.2: the TEST catalog amendment, then the PROD one
     (boundary allows including the PassRole fragment, the USI Apply
     guard's PassRole fragment, and the new Apply managed policies with
     the layer-5 changes);
  4. row 10, S5.17: TEST, then PROD;
  5. row 11, S5.4: TEST, then PROD (the Preview, Drift and Apply KMS
     reads); then the AD-15a identity rows as stack amendments of the
     TEST and PROD ECS runtime stacks (with `Modify` rows on their
     boundary and guard policies, R12-M2), the TEST and PROD function-role stacks
     and the TEST exercise stack;
  6. row 13, S5.3, in this order: BI CI creates the function log
     groups, then the TEST (then PROD) function-role stack amendment adds
     the three functions (no catalog change), then BI CI creates the
     Lambda permissions and the `RotationSucceeded` rule;
  7. row 33, S5.23: the TEST exercise stack amendment;
  8. row 34, S5.7: the TEST recovery stack install;
  9. row 42, S5.18a then XP-11: the TEST restore stack amendment, then
     XP-11's TEST catalog amendment (after S5.18a, before S4.6);
  10. row 43, S4.6, one amendment at a time in this order (R12-m3):
      step 5, S5.5's TEST function-role stack amendment (the
      bootstrap-job exact XP-8 secret read, its scoped network-interface
      grant and `VpcConfig`), then S5.18b's TEST restore stack amendment
      (the reader's scoped grant and `VpcConfig`); step 18, S5.5's
      `VpcConfig`-only detach of the bootstrap job, then S5.18b's
      `VpcConfig`-only detach of the reader (the ENI check follows both);
      step 20, S5.5's re-attach (the rebuilt XP-8 subnet and SG IDs, the
      grant re-scoped to them, the new managed-secret ARN), then
      S5.18b's re-attach (the same subnet and SG IDs, its grant
      re-scoped); and, inside step 20 before step 2, the XP-8 item-4
      re-grant of the USI Apply role's exact-ARN secret-policy read and
      write on the new managed-secret ARN, which is S5.5's governance
      identity change and not a seed operation, so it is not a seed
      installer row and lands before step 2 needs it;
  11. row 45, S4.8, only if V-19 selects the ephemeral exact-ARN reader
      grant: its add and its removal, as TEST restore stack amendments;
  12. row 47, S5.19: the PROD recovery stack install;
  13. row 48, XP-14: the PROD `s3:GetBucketVersioning` catalog amendment;
  14. row 50: S5.24a's PROD ECS runtime stack amendment (the PROD
      execution role's ECR pull grant and the boundary and guard rows on
      XP-14's repositories, R12-M2), then S5.24a's catalog amendment (its
      PROD Apply reads fit-first into an S5.2 PROD Apply policy, R12-m4),
      then S5.24b's.

  An Apply or Preview/Drift managed-policy change (layer 5) rides in its
  story's catalog amendment in this order. S5.5's Apply-role
  `secretsmanager:PutResourcePolicy` and `GetResourcePolicy` grant needs
  no catalog amendment of its own: S5.2's covers it (layer 3; audit 3).
  No operation's baseline comes from a higher row.

  **Governance, failure and evidence (R9-M1 (d), (f)).** Each grant goes
  through the BI owner's security review and `@Kravalg`'s approval, and
  its boundary addition through the seed review, as S5.24 already
  required. XP-11 covers the TEST Preview and Apply roles. S5.24 ships as
  two separately reviewed and approved BI PRs: **S5.24a**, the PROD
  Preview and Apply reads (needed for gate 2a), and **S5.24b**, the Drift
  reads for TEST and PROD (needed for S4.17 and gate 2b). The split
  separates the two reviews and their records; a rejected Drift part
  still stops gate 2a, through S4.17, C-runner and the S4.7 live PROD
  matrix (recheck N1). The approving PR numbers (identity and seed) are
  recorded in the acceptance receipt. It fails closed. A rejected review
  is a STOP: at gate 1 for XP-11, at gate 2a for S5.24a, and at S4.17 and
  so gate 2a for S5.24b. What follows a rejection is a user decision,
  and this plan takes none. If only the Apply-role reads are rejected,
  adopting the fallback design (`up-plan` reuses the Preview-role
  observation instead of re-reading under the Apply role) needs that
  user decision.

  **Regression evidence.** A BI simulator matrix per owner.
  `iam:SimulatePrincipalPolicy` evaluates the permissions boundary, so
  each allow row also proves the boundary addition. Each matrix has
  seven kinds of rows:
  - **allow rows:** each listed read allowed for its role on its exact
    resource and denied on any other (other roles, repositories,
    certificates);
  - **SSM and token rows (D-15):** `ssm:GetParameter` denied for every
    role on every parameter, the former certificate parameter
    `/vilnacrm/{env}/user-service/gateway-certificate-arn` included;
    `ssm:GetParameters` and `ssm:GetParametersByPath` denied on any
    parameter; `ecr:GetAuthorizationToken` denied;
  - **guard-layer rows (R10-M1; R11-M1):** each role's seed guard is
    attached with its catalog template hash equal to the story's
    baseline catalog, the result of its predecessor in the one-open
    serialization (on `origin/main`: TEST Preview and Drift
    `3a5ec954…`, Apply `326bd0c9…`; PROD Preview and Drift `9d60b32c…`,
    Apply `cfc893b4…`; S5.2's PassRole fragments replace the Preview,
    Drift and Apply hashes of both environments, so every later story
    pins the post-S5.2 values), its
    `ae950d73…`, `9f269660…` or `ce12c400…`
    statement still lists `ssm:GetParameter`, `ssm:GetParameters`,
    `ssm:GetParametersByPath` and `ecr:GetAuthorizationToken`, and each
    simulated SSM and token denial lists the guard among its
    `MatchedStatements` next to the identity deny. The simulator reports
    a matched statement by its `SourcePolicyId` (the guard policy) and
    its position in that policy's document, and the matrix maps the
    position to the catalog statement hash through the guard's
    `statement_ids` order in the catalog (pre-commit audit 11);
  - **renderer-scope rows (R10-n3):** the rendered governance documents
    of every other enrolled repository, and the platform roles'
    documents (including the platform apply role's `secret-read-deny`
    from `_apply_secret_deny_document`, `ci_bootstrap.py` line 700), are
    byte-identical before and after the change; the USI
    `DenySecretLeakingReads` and `DenySecretLeakingReadsApply` documents
    are byte-identical too;
  - **ConfigRead rows (pre-commit audit 4):** each boundary-sharing
    ConfigRead role's simulated decision for every new allow is
    unchanged (still denied), because its identity policies do not
    change;
  - **attachment rows (layer 5):** `verify_active_enrollment` over the
    amended catalog passes: the Apply role's managed attachments stay
    inside `_mutable_attachment_sets`, and every other role's set is
    exact.
  - **principal-creation and exact-ARN rows (layer 6, R11-M1):**
    `iam:CreateRole` denied to every CI applier on the new role ARNs and
    on `*`; the USI Apply role's `iam:PassRole` limited to the two ECS
    roles of its stack and to `ecs-tasks.amazonaws.com`, and denied to
    Preview and Drift; the governance apply role's policy writes limited
    to the policy ARNs of its lists; the rows for BI roles come from the
    BI PR evidence (layer 6, "Who runs which rows").

  The matrices:
  - **XP-11 (TEST, before gate 1):** the allow rows for Preview and Apply
    (the three ECR reads on the two TEST repositories, `iam:GetRole` on
    both ECS roles, `acm:DescribeCertificate` on the XP-10 ARN;
    `iam:SimulatePrincipalPolicy` for Apply on the execution role only,
    Preview keeping S5.17's unchanged step-3 list), and the SSM, token,
    guard-layer, renderer-scope and principal-creation rows for Preview,
    Apply and Drift.
    Only Drift *denies* are asserted, because the TEST Drift allows are
    S5.24b's (row 50, after gate 1). **Hold rows (R12-M1):** a read-back
    by the BI owner (`iam:ListRolePolicies` on the TEST Apply role, then
    `iam:GetRolePolicy` of each name) shows no `Issue215CutoverSessions`
    and no inline document that denies `*`; and every simulated TEST
    Apply allow row is `allowed` with no entry of its
    `MatchedStatements` whose `SourcePolicyId` is
    `Issue215CutoverSessions`. S5.2's TEST matrix (row 9) carries the
    same two rows, and its PROD matrix the PROD Apply read-back.
  - **S5.24a (PROD Preview and Apply):** the PROD ECS rows of its stack
    amendment (the PROD execution role's `_pull` set `allowed` with
    `AllowedByPermissionsBoundary`; the boundary and guard documents),
    the XP-18 PROD read-back, and the same rows (principal-creation
    rows included) on the PROD roles,
    repositories and XP-15 certificate ARN, plus an allow row for the
    PROD Preview role's `iam:SimulatePrincipalPolicy` on the PROD
    execution role, which S5.24a grants because S5.17's step-3 list names
    only TEST roles (pre-commit audit 12).
  - **S5.24b (Drift, TEST and PROD):** its allows (the ECR, IAM, ACM,
    registry-row, refresh and versioning reads; `iam:SimulatePrincipalPolicy`
    on the execution role only), and the SSM, token, guard-layer and
    renderer-scope rows for the Drift roles.
  - The existing matrices stay unchanged.

  Live repeats: the S4.6 step-3 simulator run (TEST, the XP-11 matrix)
  and the S4.7 PROD simulator run before gate 2a (the S5.24a matrix and
  the PROD part of the S5.24b matrix).

## 4. IAM and state boundary; single-writer sequencing

**Serialized chains.** One writer per chain. A story may join a chain only
after its predecessor merges.

| Chain | Order |
| --- | --- |
| C-BI (IAM/KMS/Lambda, governance apply) | [external, before S5.1: #284 and XP-17, the reviewed installer role, R12-m1] S5.1 (every central role except the two recovery roles, each role family created by its own independent CloudFormation stack through the XP-17 human non-root installer (AD-26 layer 6, R11-M1): ECS runtime per environment (execution and task, each with its retained `-Boundary` and workload-shaped `-Guard` policies, and the execution role's log-stream grants and, for TEST, its ECR pull grant (PROD's at S5.24a, after XP-14), R12-M2; the TEST stack adopts #219's names and PassRole fragments), function roles per environment (app-rotation, redeploy, bootstrap-job), TEST restore (operator, reader; trust only) and TEST exercise (trust only), plus a service-linked-role stack for any of the five that a read finds missing (R11-m2); no KMS statements) → [external, before S5.2: XP-18, `Issue215CutoverSessions` retired, R12-M1] S5.2 (apply capability, including the managed-password and log-group KMS describe grants) → S5.17 (preview/drift read without KMS; `iam:SimulatePrincipalPolicy` for the preview role) → S5.4 (CMKs whose key policies name only existing roles, per AD-15a; then the matching identity statements, including the preview/drift KMS read) → S5.3 (functions that use the S5.1 roles, added to the function-role stacks by reviewed stack amendments because no CI applier may pass those roles (AD-26 layer 6); KMS-encrypted function log groups and rules by BI CI) → S5.23 (TEST exercise role grants, an amendment of its S5.1 stack) → S5.7 (test-recovery role and grants in their own stack, derived from the S4.10 graph) → S5.18a (grants on the S5.1 restore-operator and restore-reader roles and the reader function without VPC, as a restore-stack amendment) → XP-11 (the TEST Preview and Apply workload-observation reads and their seed boundary amendment: an external gate-1 prerequisite whose BI and seed changes take this C-BI slot, after S5.18a (row 42) and before S4.6 (row 43); R10-m2) → [live, after USI step 1] S5.5 (XP-8 metadata, the bootstrap-job exact-ARN grant as a function-stack amendment, bootstrap-job scoped network-interface grant and VPC attach, job run; the bootstrap-job `VpcConfig` detach in step 18 and the re-attach with the rebuilt subnet and SG IDs in step 20, R12-m3) → S5.18b (restore-reader scoped network-interface grant and VPC attach, after XP-8, as restore-stack amendments; detach and re-attach in steps 18 and 20) → S5.6 (conditional) → S5.19 (prod-recovery role and grants in their own stack) → [after XP-14, XP-15 and XP-16] S5.24 (Drift-role registry-row, refresh, `s3:GetBucketVersioning`, IAM, ECR and ACM read inventory and grants for S4.17, with `SimulatePrincipalPolicy` on the execution role only and the Drift-role deny unchanged; plus the PROD Preview and Apply workload-observation reads (no SSM read and no deny or guard narrowed, user decision D-15), before gate 2a; two separately approved PRs, S5.24a (PROD Preview/Apply) and S5.24b (Drift); each adds the matching boundary statements through a seed catalog amendment; R7-m9, R8-m3, R9-M1, R9-m1, R9-m2, R10-M1, AD-26). The TEST Preview and Apply counterparts are XP-11, in the slot after S5.18a. Every C-BI grant to the preview, apply or drift service role also widens the seed-owned `GovernanceBoundary-user-service-infrastructure-<env>` through a seed catalog amendment, by exactly that grant or by the seed-approved service or resource-family ceiling, with a size check against the 6144-character limit (AD-26, R10-M1, R10-m1). **Seed operation order (R10-m2, R11-M1):** one seed operation (catalog amendment, stack install or stack amendment) is open at a time across both catalogs and every stack (AD-26 serialization), in this order: #284 (external precondition) → row 8 S5.1 stack installs (SLR stacks if needed, TEST ECS, PROD ECS, TEST and PROD function roles, TEST restore, TEST exercise) → row 9 S5.2 → row 10 S5.17 → row 11 S5.4 (catalog, then the stack amendments) → row 13 S5.3 (function-role stack amendments) → row 33 S5.23 (stack amendment) → row 34 S5.7 (stack install) → row 42 S5.18a (stack amendment), then XP-11 → row 43 S5.5 and S5.18b (stack amendments, steps 5-6, 18 and 20) → row 45 S4.8 (only if V-19 selects the ephemeral reader grant) → row 47 S5.19 (stack install) → row 48 XP-14's PROD `s3:GetBucketVersioning` addition → row 50 S5.24a → S5.24b; each takes its predecessor's result catalog as its baseline |
| C-controls (USI GitHub repository controls, m3: `scripts/configure_github_repository_controls.py`, `scripts/_github_repository_controls.py`, `scripts/_github_environment_controls.py`, `tests/unit/test_configure_repository_controls.py`; admin apply by Kravalg) | S5.21 (Kravalg-only environments `test`, `prod`, `test-recovery`, `test-exercise`, `prod-recovery`; `governance-evidence` checked unchanged) → S5.22 (ruleset: `abandon-manifest-approval` required with a pinned issuer, after S4.3) |
| C-contract (`schemas/` (including the S4.14 PROD contract schema `poc-prod-v1.schema.json` and the S4.15 `poc-workload-scheduled-drift-result-v1.schema.json`; R7-m4, R7-m1), `scripts/poc_contract.py`, `scripts/poc_phase_admission.py` (the stack → contract mapping, S4.14), secret validators, admission, drift allow-list, receipt schemas, `scripts/poc_workload_reconciliation.py` and `docs/poc-workload-reconciliation.md` (R5-M1, R5-M5), `scripts/poc_registry_plan.py` (only S4.3's post-abandon baseline acceptance, R6-m13), `scripts/poc_registry_phase_entrypoint.py` (only S4.10's stack-keyed registry-set selector next to `_REGISTRIES`; the `prod` entry is XP-14's, outside this plan; R9-n4), acceptance-receipt validator) | S1.1 → S1.7 → S1.9 → S1.8 → S1.11 → S4.10 → S4.11 → S4.9 → S4.2 → S4.3 → S4.12 → S4.13 → S4.14 → S4.15 → S4.6 → S4.7. S1.11 follows S1.8, which follows S2.1 in C-compute, so the program's `ignore_changes` exist when S1.11 checks them (R5-M4). S4.9 precedes S4.2 (R6-M2): S4.2's `resume` applies S4.9's per-mode admission rules and `start_at` window, while S4.9 depends only on S4.10, S4.11 and S2.6. |
| C-topology (`scripts/poc_workload_topology.py`, `scripts/poc_workload_secret_result.py`, the native integration test, the Random/TLS pins, `recovery/delete-actions.json`, the runner-spec topology text) | S4.10 only (AD-25) |
| C-runner (`scripts/poc_workload_runner.py`, `scripts/service_execution_worker.py`, `scripts/service_execution_host.py` (receipt copy-out; PROD `JOBS`, lines 27-31; the S4.17 scheduled entries with scheduled-main provenance, R7-M2), the worker diagnostics, `.github/workflows/self-deploy.yml`, `.github/workflows/scheduled-drift.yml`, `scripts/run_pulumi_command.py` (the scheduled exclusion), `scripts/poc_phase_source_adapter.py` (the `workload_route` and `workload_observation` outputs, R6-M1), `scripts/poc_workload_observation.py`, `scripts/poc_scheduled_workload_drift.py` (S4.17), the admission observation functions (including `scripts/poc_workload_images.py` and `scripts/poc_workload_capabilities.py`, which only S4.14 edits in this plan: the token-free config read, the D-15 certificate change and the release-platform pin at capabilities lines 327-330; S4.9's multi-arch check lives in `scripts/poc_workload_admission.py`, C-contract, and edits neither module; S4.17 calls them; R9-M1, R10-n6, AD-26), receipt modules, `specs/poc-workload-runner.md` lifecycle text, the README line-127 sentence, `docs/poc-workload-log-health.md`, `test_workload_apply_docs_consistency.py`, `tests/unit/test_service_execution_worker.py`, and the workflow-shape tests that pin the CI graph (R6-M1): `tests/pulumi/test_ci_guardrails.py`, `tests/unit/test_trusted_test_controller_workflow.py`, `tests/unit/test_service_execution_workflow.py`, `tests/unit/test_poc_registry_completion_workflow.py`, `tests/unit/test_poc_registry_workflow.py`, `tests/unit/test_poc_source_workflow.py`, `tests/unit/test_poc_phase_source_adapter.py`, `tests/unit/test_service_initializer.py`, `tests/unit/test_service_execution_host.py`, `tests/unit/test_poc_scheduled_registry_workflow.py`, `tests/unit/test_service_reviewed_credentials.py` (R7-m7)) | S4.1 → S4.4 → S4.5 → S4.11 → S4.12 → S4.13 → S4.14 → S4.17 → S4.7 (R8-m7: S4.7's unstubbed PROD host seam test edits `tests/unit/test_service_execution_host.py`). S4.1 heads it because its FR-20 test is `tests/unit/test_service_execution_worker.py` (m5). S4.11–S4.14 also hold the C-contract slot at their position in that chain, because they edit `poc_workload_admission.py`. S4.17 follows XP-14, XP-15, XP-16 (S5.1's since revision 12) and S5.24 and is a gate-2b precondition; because S4.7 (gate 2a) follows it in C-runner, a stop of S4.17 (for example a rejected S5.24b) also stops gate 2a (recheck N1, R10-n1). Every rewrite of a workflow-shape test is a guardrail change that needs an `APPROVED` review by `@Kravalg` specifically, recorded like the round-5 m14 hard-stop amendment (`epics-stories.md` S4.11, S4.13, S4.14, S4.17, S4.7). |
| C-composition (`pulumi/app/workload_phase.py`: the plane imports and wiring at lines 13-29 and in `WorkloadPhaseStack.__init__`, `TAGGABLE_TYPES`, `_validate_target`) (m6) | S1.1 (`workload_step` branch) → S1.3 (step-1/step-2 structure, XP-8 exports) → S1.4 (ElastiCache user and group types) → S2.1 (autoscaling plane) → S2.3 (observability plane, with every taggable type S2.4 and S2.5 add) → S3.2 (default SG) → S3.1 (flow-log plane and bucket family) → S3.3 (endpoints and endpoint SG) → S3.5-A (`_validate_target` parameterized by stack so the program renders `prod`; today it pins `test` and the TEST registries, lines 125-160; before S4.10, whose PROD native plan needs it) |
| C-autoscaling (`pulumi/app/autoscaling.py`) | S2.1 → S2.2 → S2.6 (TEST schedules) |
| C-observability (`pulumi/app/observability.py`) | S2.3 → S2.4 → S2.5 |
| C-runtime (`runtime_secrets.py`) | S1.1 → S1.7 → S1.6 → S1.5 → S1.8 |
| C-data (`data.py`) | S1.2 → S1.3 → S1.4 → S1.10 → S1.9 |
| C-network (`network.py`) | S1.3 → S1.4 → S3.2 → S3.1 → S3.3 → S3.4 |
| C-compute (`compute.py`) | S1.3 → S1.4 → S1.10 → S2.1 → S1.8 → S3.7 → S2.6 → S3.5-A |
| C-stack (`stack.py`) | S1.10 |
| C-guard (`scripts/pulumi_ci_guardrails.py`, `policy/`) | S1.6 (Invocation, `aws:docdb/` and `aws:s3/bucketV2:` critical) → S3.3 (VpcEndpoint pin identity and digests) → S4.3 (recovery classifier use) |

**Independent file scopes.** These can run in parallel with at most three
agents, after the chain heads they read from:

- the TLS doc (S3.5-B);
- the TEST exercise workflow (S4.16, after S5.23);
- US stories;
- the AGI story.

The runner diagnostics, guard and timing (S4.1, S4.4, S4.5) are not
independent: they edit C-runner files, so they head C-runner (m5).
`observability.py` and `autoscaling.py` are serialized chains, not
independent scopes, because their stories also wire `workload_phase.py`
(C-composition).

**Cross-repo gates are acyclic in time:**

1. BI S5.1 → S5.2 → S5.17 → S5.4 → S5.3 → S5.23 → S5.7 → S5.18a use
   deterministic ARNs and patterns only; the USI repository controls S5.21
   and S5.22 use no apply output. The `secretsmanager` endpoint
   policy uses deterministic role ARNs and `rds!cluster-*` (R4-B3), so it is
   acyclic.
2. USI step 1, then the authenticated step-1 receipt.
3. XP-8 metadata (subnet IDs, bootstrap-job SG ID, DocumentDB-managed secret
   ARN), the exact-ARN grant and the bootstrap-job VPC attachment, then S5.5.
   S5.18b (reader VPC attach) follows XP-8 before S4.8.
4. USI step 2 (anchored on the step-1 receipt), then the accepted-workload
   receipt, which opens drift.

**State risk summary:**

- No live state migrates under R-02; AD-09 fails closed.
- The new fixed-name resources join the import list.
- Protected-resource changes pass the destructive-diff gate. The only
  exception is the TEST abandon (D-7, decided 2026-09-30). It runs through
  the Kravalg-approved recovery environment, as a saved removal plan whose
  `delete` URNs, of every type, equal the manifest 1:1 (AD-16).
- A seed Invocation replace or delete is critical (AD-06).

## 5. Validation

- Every FR maps to an AD:

  | FR | AD |
  | --- | --- |
  | FR-01, FR-02 | AD-01 |
  | FR-03 | AD-20 |
  | FR-04 | AD-02 |
  | FR-05 | AD-06, AD-07 |
  | FR-06 | AD-03, AD-15 |
  | FR-07 | AD-08 |
  | FR-08, FR-09 | AD-03, AD-06, AD-09 |
  | FR-10 | AD-04, AD-15a |
  | FR-11, FR-12, FR-14 | AD-10 |
  | FR-13 | AD-11, AD-08 |
  | FR-15 to FR-18 | AD-12, AD-12a, §2.1 |
  | FR-19 | AD-13 |
  | FR-20 to FR-23 | AD-16 |
  | FR-24 | AD-17, AD-18 |
  | FR-25, FR-26 | AD-14 |
  | FR-27, FR-33 | AD-05, AD-08, §4 C-BI |
  | FR-28 | §2 (AGI), V-10 |
  | FR-29 | AD-22 |
  | FR-30 | AD-19, §2.1 |
  | FR-31 | AD-21 |
  | FR-32 | AD-23 |
  | FR-34 | AD-18, AD-10 |
  | FR-35 | AD-24, AD-25 |

- No AD creates IAM, Lambda or `SecretVersion` in USI (NFR-02, FR-09).
- **Apply-role actions needed (N-11, S5.2):**
  - `secretsmanager:CreateSecret`, `PutResourcePolicy`, `GetResourcePolicy`,
    `RotateSecret` (with `secretsmanager:RotationLambdaARN` limited to the BI
    function ARNs, V-15), `TagResource`, `DescribeSecret` on the
    declared-name patterns. No delete action (`DeleteResourcePolicy`,
    `CancelRotateSecret`, `DeleteSecret`, `DeleteScheduledAction`): no
    admitted apply mode deletes (NFR-06); deletes belong to the TEST recovery
    role (AD-16);
  - for the DocumentDB-managed password (R4-M9, A-27, V-21): `rds:CreateDBCluster`
    with `rds:ManageMasterUserPassword` = true; `secretsmanager:CreateSecret`
    and `secretsmanager:TagResource` on
    `arn:aws:secretsmanager:<r>:<a>:secret:rds!cluster-*`; `kms:DescribeKey`
    on the AWS-managed `alias/aws/secretsmanager` key (resource
    `arn:aws:kms:<r>:<a>:key/*` with `kms:ResourceAliases` =
    `alias/aws/secretsmanager`); `secretsmanager:DescribeSecret` on
    `secret:rds!cluster-*` (metadata, for the step-1 result observation).
    `PutResourcePolicy` and `GetResourcePolicy` on the managed secret are
    granted on the **exact** XP-8 ARN in S5.5, because step 2 and
    `policy-update` run after XP-8;
  - `kms:DescribeKey` on the runtime CMK with the `kms:ViaService` set of
    AD-15a (log groups with `kms_key_id`, secrets, SNS, the flow-log bucket);
  - `application-autoscaling:RegisterScalableTarget` (including
    `SuspendedState`), `PutScalingPolicy` and `PutScheduledAction` on the two
    service resource IDs (targets, start, stop and TEST schedules);
  - `lambda:InvokeFunction` on the BI function ARNs;
  - `ec2:CreateFlowLogs`, `logs:CreateLogDelivery` (the matching deletes
    belong to the TEST recovery role);
  - **no `iam:CreateServiceLinkedRole` (R11-m2).** The seed statement
    `05f77e26…` (BI `origin/main` `pulumi/seed/catalogs/test.json` lines
    1767-1780; the same hash in `prod.json`) denies it on `*` unless
    `iam:AWSServiceName` is `budgets`, `guardduty` or `securityhub`, and
    it is in the USI Apply guard (`test.json` line 658) and in every BI
    applier guard. So the five service-linked roles the workload needs,
    for `ecs.amazonaws.com`, `ecs.application-autoscaling.amazonaws.com`,
    `elasticache.amazonaws.com`, `rds.amazonaws.com` and
    `elasticloadbalancing.amazonaws.com`, must already exist. Their
    existence is a read-only `iam:GetRole` precondition of S4.6 step 1
    (on the roles under `/aws-service-role/`). A missing one is created
    only by the independent-owner route (AD-26 layer 6): an
    `AWS::IAM::ServiceLinkedRole` resource in a seed stack of that
    account, installed by the human non-root installer in S5.1's slot of
    the serialization, never by a CI role.

  `GetSecretValue`, `PutSecretValue`, `UpdateSecretVersionStage` and
  `GetFunction` stay denied.
- **Open verification items (M-4).** Each item has a method and a place.
  "Docs" and "source" items are closed offline, as the first acceptance case
  of their story. "Live" items run as numbered S4.6 steps (V-22 also as S4.8
  step R-1) with a STOP rule and a fallback. No live item is closed by an
  offline story. A policy fix during the campaign is applied only by the
  update-only `policy-update` mode (S4.9): exactly one `update` step, on a
  URN from the closed set {managed-secret `SecretPolicy`, each
  `VpcEndpoint`}, with `policy` as the only changed input.

  | Item | Question | Method | Offline story | Live step (S4.6) | STOP / fallback |
  | --- | --- | --- | --- | --- | --- |
  | V-1 | ext-mongodb 2.4.1 (libmongoc) obtains ECS container credentials for `MONGODB-AWS` | source (libmongoc) + live | S5.10 | 7 | STOP: step-2 health fails → `rollback-zero` saved plan (AD-10, AD-19); new user decision (app DB user with rotated password). |
  | V-2 | phpredis 6.3 `AUTH [user, token]`, re-`AUTH` on an open connection, and a Symfony `RedisAdapter` custom connection factory | source + US integration test against a local ACL-enabled Valkey 7.2 + live | S5.13 | 7, 10 | STOP: US fix before step 2 is retried. |
  | V-3 | A resource policy on the DocumentDB-managed secret keeps the managed rotation working, and which principal or condition the managed rotation uses | docs + live (forced rotation with the `deny-other-readers` policy present) | S1.5 | 8 | Fallback (non-destructive, R4-M6): a reviewed contract PR moves `documentdb_secret_policy` to `allow-rotation`, then to `tls-only` if that also fails; each is an update-only `policy-update` saved plan (exactly one `update` of the managed-secret `SecretPolicy`); the policy is never deleted; the residual risk is recorded. |
  | V-4 | `RotationSucceeded` reaches the default bus | docs (A-11) + live | S5.3 | 9 | STOP: no redeploy observed → escalate; no manual force deployment outside review. |
  | V-5 | The user group rule for `default`, and acceptance of `no-password-required` with `off` for the engine | docs + provider source + live | S1.4 | 4 | STOP: if a password is required, user decision (a Pulumi-generated password is not allowed). |
  | V-6 | `RotateSecret` caller needs `lambda:InvokeFunction` on the BI function | docs + live simulate | S1.6 | 3 | STOP: simulator denies → BI grant fix. |
  | V-7 | `aws.lambda.Invocation` needs only `lambda:InvokeFunction` | provider source | S1.6 | — | STOP: redesign the seed trigger (BI-side), escalate. |
  | V-8 | `Secret`, `SecretRotation`, `SecretPolicy` reads use no `GetSecretValue` | provider source | S1.1 | — | STOP: redesign. |
  | V-9 | IAM auth limits: TLS required; token 15 min or credential expiry; 12 h disconnect unless re-`AUTH`/`HELLO`; `user_name == user_id`; no re-auth in `MULTI`/Lua; lower-case replication-group id; only `aws:SourceIp`/`aws:ResourceTag` conditions | docs, verified 2026-09-30 (ElastiCache `auth-iam.html`) + live | S1.4, S5.13 | 10 | STOP: soak failure → US fix. |
  | V-10 | REST API private integration over VPC link V2 **directly to the ALB** in `eu-central-1` | docs, verified 2026-09-30 (REST API whitepaper: VPC link V2 supports ALB and NLB; What's New 2025-11 lists Europe (Frankfurt)); provider source, verified: `pulumi_aws` 7.23.0 `apigateway.Integration.integration_target` + live | S5.16 | 17 | Fallback: NLB (TCP 443) with an ALB-type target group, recorded and reviewed; never silent. |
  | V-11 | DocumentDB `StsGetCallerIdentityCalls` is published | docs, verified 2026-09-30 (`iam-identity-auth.html`) + live | S2.4 | 12 | Fallback: drop the informational alarm, recorded. |
  | V-12 | SES API interface endpoint (What's New 2025-12) service name and private DNS for the SES v2 host used by async-aws | docs + live read-only `DescribeVpcEndpointServices` | S3.3 | 3, 11 | Fallback: no SES endpoint; service SG keeps 443 to `0.0.0.0/0` via NAT for SES only, recorded (FR-18). |
  | V-13 | The `plan` invocation that the workload drift gate reads (`preview --json --refresh --save-plan --show-sames`, R6-m4) emits the refreshed per-step states that the FR-32 reducer reads, and a refresh that changes only AD-23 fields yields only `same` steps | docs + engine/provider source + live | S4.13 (first case; S1.11 cites it for the list semantics) | 14 | STOP: investigate; the list is never widened without review. If the invocation does not emit the refreshed states, S4.13 does not merge until the reducer input is redesigned in a reviewed PR. |
  | V-14 | ECR layer bucket name `prod-eu-central-1-starport-layer-bucket` | docs + live pull | S3.3 | 7 | STOP: pull fails → tasks never start (health fails) → `rollback-zero`; the pinned policy is fixed in a reviewed PR and applied as a `policy-update` plan. |
  | V-15 | Condition keys `secretsmanager:RotationLambdaARN`, `RecoveryWindowInDays`, `ForceDeleteWithoutRecovery` | docs (service authorization reference) | S5.2, S5.7 | 3, 19 | STOP: key absent → redesign the grant. |
  | V-16 | Flow logs to S3 with SSE-KMS (runtime CMK, D-4) need `delivery.logs.amazonaws.com` in the key policy; creator needs `logs:CreateLogDelivery`/`DeleteLogDelivery` | docs | S3.1 | 12 | STOP: delivery fails → fix the key or bucket policy by a reviewed PR. SSE-S3 is not a fallback, because D-4 decided SSE-KMS; changing it needs a new user decision. |
  | V-17 | IAM auth needs DocumentDB 5.0 instance-based | docs (A-01) + live | S1.3 | 4 | STOP: cluster version mismatch → fix before step 2. |
  | V-18 | Which `aws.lambda.Invocation` input changes replace it; lifecycle scope (a delete makes no call under the default `CREATE_ONLY` scope) | provider source + live | S1.6 | 19 | STOP: redesign. |
  | V-19 | The DocumentDB-managed secret carries a cluster tag usable as `secretsmanager:ResourceTag` | docs + live read-only `DescribeSecret` (metadata) | S5.5, S5.18a | 5 | Fallback: exact ARN only. |
  | V-20 | `aws:PrincipalAccount` semantics for `ecr:GetAuthorizationToken`; the reviewed ECR registry account | docs + live pull | S3.3 | 7 | STOP: as V-14 (`rollback-zero`, reviewed pin fix, `policy-update` plan). |
  | V-21 | `CreateDBCluster` with `ManageMasterUserPassword` needs, under the caller (USI apply role), `secretsmanager:CreateSecret` and `TagResource` on `rds!cluster-*` and `kms:DescribeKey` on `alias/aws/secretsmanager` (documented for RDS and Aurora, A-27; not stated for DocumentDB) | docs + live simulate + live apply (CloudTrail `CreateSecret` event for the managed secret, metadata only) | S5.2 | 3, 4 | STOP: step 1 fails with `AccessDenied` → the BI grant is fixed by a reviewed PR, then S4.3 `resume`. An unneeded grant found by the CloudTrail check is removed in a reviewed PR before gate 2. |
  | V-22 | The restore operator needs `secretsmanager:CreateSecret`/`TagResource` and `kms:DescribeKey` for `ModifyDBCluster(ManageMasterUserPassword)`; `kms:CreateGrant`/`Decrypt`/`DescribeKey` on the DocumentDB storage key for the point-in-time restore (R6-m10); and the source-cluster, target-cluster and subnet-group resource permissions of `RestoreDBClusterToPointInTime` (A-27) | docs + live simulate + live restore | S5.18a | 3 (simulate); S4.8 step R-1 | STOP: restore or modify denied → BI grant fix, rehearsal re-run; the temporary cluster is deleted first. |
  | V-23 | ECS service autoscaling at 0 tasks: (a) whether `RegisterScalableTarget` with `min` above `desiredCount=0` scales out by itself; (b) whether the one-time `at()` start action scales 0 → `min` (A-26 documents it); (c) whether a fired one-time action stays listed; (d) whether `scheduledScalingSuspended` blocks one-time actions, and whether a restart plan that un-suspends and creates a start action fires it; (e) (m1) whether the pinned provider's `Target` update re-sends `MinCapacity`/`MaxCapacity`, and which values it sends under `ignore_changes` with `up --refresh` (the hold plan must not change the live 0/0) | docs (A-26, verified 2026-09-30) + provider source (e) + live | S2.1 and S4.9 ((e) is the first case of both) | 7, 7b, 15 | STOP: (b) fails → the services stay at 0 tasks, so nothing needs rolling back; the start mechanism is redesigned in a reviewed PR. (c) shows removal → STOP before the next apply of any mode (m12); the two-part fix of AD-10 (`scaling.consumed` contract PR, so the program stops rendering the fired actions, plus the AD-23 entry). (d) differs from AD-10 → STOP at step 15; the stop and hold sequence is redesigned in a reviewed PR. (e) shows that a hold update can send non-live min/max → S4.9 does not merge until the hold design changes in a reviewed PR. |
  | V-24 | Setting `retain_on_delete` (and `protect=False`, `recovery_window_in_days`, `final_snapshot_identifier`) changes only state in the unprotect plan (`update` steps, no cloud call except `rds:ModifyDBCluster`), and a later `delete` of a retained resource makes no cloud call | engine and provider source + live | S4.2 | 19 | STOP: any cloud delete observed on a retained resource → stop the abandon; recover by S4.3 import. |
  | V-25 | The ECS awslogs driver writes to a log group encrypted with the runtime CMK with no KMS statement for the execution role (A-28) | docs + live | S2.4 | 7 | Fallback: a reviewed AD-15a row for the execution role (`kms:GenerateDataKey` with `kms:ViaService=logs.<r>.amazonaws.com`), then step 7 is re-run. |
  | V-26 | The per-type delete action sets derived from the pinned provider's delete paths are complete (drain and detach calls included) for the recovery role | provider source + live (CloudTrail of the abandon run, no `AccessDenied`) | S4.10, S5.7 | 19 | STOP: an `AccessDenied` stops the removal plan mid-way → S4.3 `export`, reviewed S5.7 grant fix, then `recovery-abandon` again from the export receipt. |
  | V-27 | Whether a resource imported with the `import_` option (the rebuild's recovery import, AD-16) keeps `importID` on its checkpoint row after the import apply (R6-m12) | engine source (first case) + live | S4.10 (first case), S4.3 | 20 | If it persists, S4.10's allowance accepts `importID` only on rows whose URN the authenticated import receipt lists, and every other `importID` still fails. A live `importID` on an unlisted row → STOP before `rebuild-first`; S4.3 `export`, then a reviewed fix. |
  | V-28 | `ecr:GetDownloadUrlForLayer` accepts an image's **config** digest (not only a layer digest) and returns a pre-signed URL on exactly `LAYER_HOST` (R9-M1, R10-n5; AD-26 point 1) | docs (the API reference documents image layers and is silent on the config blob) + live | S4.14 (P4, N7; the offline fakes assume acceptance) | 1 (the gate-1 PR's TEST workload `plan`, read-only), confirmed again by the step-4 `up-plan` | STOP: the `plan` fails with `image-config-observation-failed` before any apply. No automatic fallback: the token path needs a user decision that amends NFR-06 and narrows the identity denies and the seed guards (AD-26), plus the BI security and seed reviews approved by `@Kravalg`. |
  | V-29 | The Lambda service accepts the resource-scoped network-interface grant of AD-26 layer 6 (R12-m2: `ec2:CreateNetworkInterface` on the XP-8 subnet and SG ARNs and `network-interface/*`; `ec2:DeleteNetworkInterface`, `AssignPrivateIpAddresses` and `UnassignPrivateIpAddresses` on `network-interface/*` with `ec2:Subnet`; only the two Describe actions on `*`), creates the ENI and deletes it after the detach | docs (the Lambda guide shows only the `*` form; the EC2 Service Authorization Reference lists the resource types) + live | S5.5, S5.18b | 5 (attach: function `State` `Active`, `LastUpdateStatus` `Successful`, a `lambda` ENI in the XP-8 subnets), 18 (the ENI deleted within 45 minutes) and 20 (re-attach) | STOP: the update fails or the ENI is not created or not deleted. Fallback, each a reviewed stack amendment re-proven here: drop the `ec2:Subnet` condition; then the resource-type wildcards `…:subnet/*`, `…:security-group/*`, `…:network-interface/*` in the region and account; then `arn:aws:ec2:eu-central-1:<account>:*`. If still refused: STOP, then a user decision to amend NFR-06 to the documented `*` form. The reader may share the bootstrap job's ENI, so its grant is proven only where CloudTrail shows a call under the reader role. |
