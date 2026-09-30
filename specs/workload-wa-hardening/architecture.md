---
artifact: architecture
workflow: _bmad/bmm/workflows/3-solutioning/bmad-create-architecture (Create mode, non-interactive)
task: workload-wa-hardening
source_baseline: 66776772979956de9c5abdbee7c45641a1b533fa
date: 2026-09-30
revision: 7 (readiness round-7 findings R7-M1, R7-M2, R7-m1…m9 and R7-n1…n3, plus audit F2, F6 and F8, addressed on top of revision 6; decisions D-1…D-14 of 2026-09-30 applied)
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
  │        apply-role workload capability; preview + drift read capability
  ├─ KMS (D-4, decided 2026-09-30): runtime CMK (secrets, every workload log
  │        group, flow-log bucket, SNS topic), JWT signing CMK (RSA), 2FA CMK;
  │        key policies name existing roles (roles are created first; AD-15a)
  ├─ Lambda: app-secret rotation + seed (no VPC), redeploy (no VPC),
  │          DocumentDB bootstrap job (VPC-attached after XP-8, USI bootstrap-job SG),
  │          restore-rehearsal reader (package S5.18a; VPC attach after XP-8, S5.18b);
  │          EventBridge RotationSucceeded → redeploy rule
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
    `lambda:GetFunction`, and USI may not create IAM).
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
  - The Application Auto Scaling SLR is created by BI or granted narrowly
    (S5.2).
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
  statement (S5.4), because the BI permission boundaries also evaluate
  identity policies. `<r>` = `eu-central-1`, `<a>` = the account.

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
  | runtime (TEST only) | TEST exercise role `GitHubCiExercise-user-service-infrastructure-test` (S5.23) | `kms:Decrypt` | `kms:ViaService=s3.<r>.amazonaws.com`; `kms:EncryptionContext:aws:s3:arn` like `arn:aws:s3:::<flow-log bucket>/*` (reading flow-log objects, S4.6 step 12) |

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
    managed-secret ARN → S5.5 re-run → step 2 → accepted receipt → clean
    drift). The receipt (step 21) is assembled from the rebuilt stack. So
    the abandon never removes the stack before steps 14–17 run.
  - **BI ENIs before a removal plan.** The bootstrap-job and restore-reader
    Lambdas are attached to the USI subnets and bootstrap-job SG (S5.5,
    S5.18b), and their ENIs block the SG and subnet deletes. Before the
    removal plan, a reviewed BI PR detaches both functions (empty
    `vpc_config`), and a read-only `DescribeNetworkInterfaces` check shows no
    ENI in those subnets owned by another service. STOP if an ENI remains.
    The rebuild re-attaches both through the refreshed XP-8 metadata.
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
      present, and every applicable decision marked `resolved` with a date in
      `prd.md` §6 and `decisions.md` (defaults do not count); or
    - gate 2a: every gate-1 condition, plus `admission.prod: "preview"`,
      plus the campaign-complete TEST acceptance receipt (PRD §3.3), plus
      the restore item (S4.8, measured against D-14), XP-14, XP-15 and XP-16 (R8-m6). It admits only the PROD `plan`
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
      `status: before-acceptance` or `checked` from a scheduled run after
      the gate-2a PR that first set `poc-prod.json` `phase: workload`
      (R8-m1; the S4.17 jobs are data-driven, and a `registry-phase`
      record never counts). PROD is never admitted without scheduled
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
    certificate parameter (lines 170-176).
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
  certificate_arn}` of `scripts/poc_workload_capabilities.py` line 277;
  runner lines 177-184) and the program trees (the git object IDs of
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
     accepts `prod` with the PROD certificate parameter (XP-15, the PROD
     counterpart of XP-10; its TEST-analogous name is pinned as an
     assumption the gateway owner confirms in the S4.14 PR, R8-m6), the PROD
     topology (S4.10), the PROD registry anchor (XP-14) and `prod-recovery`.
     `abandon` is never admitted for PROD. S4.14 also owns the PROD
     contract schema (AD-04, R7-m4), the PROD baseline-drift exclusion
     (AD-23, R7-m2), and PROD fixtures for the further TEST pins that
     round 7 found (R7-m3): the workload gate's use of the registry
     `_binding` (`scripts/poc_registry_runner.py` lines 266-283, called at
     runner line 58), `scripts/poc_workload_capabilities.py` (lines 22-23,
     30, 32, 92, 111, 130-133 and 286, reached through
     `poc_workload_admission.py` line 470), `scripts/poc_workload_images.py`
     (lines 44, 68, 126, 282 and 349), `scripts/poc_workload_phase_entrypoint.py`
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
     image rows and the certificate observation. Fresh Drift-role reads
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
     needs a TEST `checked` record and a PROD `before-acceptance` or
     `checked` record from a run after the flip (AD-21). A receipt-lineage
     lookup error, including an incomplete pagination, exits non-zero.
     **Reads (R7-m9, R8-m3):** the capability, image and certificate
     checks read IAM, ECR (including `GetDownloadUrlForLayer`), SSM and
     ACM, and the refresh and the capture's registry-row checks read the
     ECR repositories, the SES identity and the Route53 DKIM records. The
     BI story S5.24 (unconditional) inventories and adds them after
     XP-14, XP-15 and XP-16 and before S4.17, with
     `iam:SimulatePrincipalPolicy` on the execution role only, citing the
     existing TEST registry-read grants of BI `origin/main` and narrowing
     the Drift role's explicit deny of `ssm:GetParameter` and
     `ecr:GetAuthorizationToken`. The PROD job needs the PROD observer
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
    `workload-source-binding`, `workload-certificate-parameter-required`,
    `workload-isolated-transport-required`, `workload-plan-bytes-changed`)
    keep passing for the modes they cover today.
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

## 4. IAM and state boundary; single-writer sequencing

**Serialized chains.** One writer per chain. A story may join a chain only
after its predecessor merges.

| Chain | Order |
| --- | --- |
| C-BI (IAM/KMS/Lambda, governance apply) | S5.1 (every central role: execution, task, app-rotation, redeploy, bootstrap-job, restore-operator, restore-reader, exercise; no KMS statements) → S5.2 (apply capability, including the managed-password and log-group KMS describe grants) → S5.17 (preview/drift read without KMS; `iam:SimulatePrincipalPolicy` for the preview role) → S5.4 (CMKs whose key policies name only existing roles, per AD-15a; then the matching identity statements, including the preview/drift KMS read) → S5.3 (functions that use the S5.1 roles; KMS-encrypted function log groups; rules) → S5.23 (TEST exercise role) → S5.7 (test-recovery role and grants, derived from the S4.10 graph) → S5.18a (grants on the S5.1 restore-operator and restore-reader roles, reader package, no VPC) → [live, after USI step 1] S5.5 (XP-8 metadata, exact-ARN grant, bootstrap-job VPC attach, job run) → S5.18b (restore-reader VPC attach, after XP-8) → S5.6 (conditional) → S5.19 (prod-recovery role and grants) → [after XP-14, XP-15 and XP-16] S5.24 (Drift-role registry-row, refresh, IAM, ECR, SSM and ACM read inventory and grants for S4.17, with `SimulatePrincipalPolicy` on the execution role only and the Drift-role deny narrowed; R7-m9, R8-m3) |
| C-controls (USI GitHub repository controls, m3: `scripts/configure_github_repository_controls.py`, `scripts/_github_repository_controls.py`, `scripts/_github_environment_controls.py`, `tests/unit/test_configure_repository_controls.py`; admin apply by Kravalg) | S5.21 (Kravalg-only environments `test`, `prod`, `test-recovery`, `test-exercise`, `prod-recovery`; `governance-evidence` checked unchanged) → S5.22 (ruleset: `abandon-manifest-approval` required with a pinned issuer, after S4.3) |
| C-contract (`schemas/` (including the S4.14 PROD contract schema `poc-prod-v1.schema.json` and the S4.15 `poc-workload-scheduled-drift-result-v1.schema.json`; R7-m4, R7-m1), `scripts/poc_contract.py`, `scripts/poc_phase_admission.py` (the stack → contract mapping, S4.14), secret validators, admission, drift allow-list, receipt schemas, `scripts/poc_workload_reconciliation.py` and `docs/poc-workload-reconciliation.md` (R5-M1, R5-M5), `scripts/poc_registry_plan.py` (only S4.3's post-abandon baseline acceptance, R6-m13), acceptance-receipt validator) | S1.1 → S1.7 → S1.9 → S1.8 → S1.11 → S4.10 → S4.11 → S4.9 → S4.2 → S4.3 → S4.12 → S4.13 → S4.14 → S4.15 → S4.6 → S4.7. S1.11 follows S1.8, which follows S2.1 in C-compute, so the program's `ignore_changes` exist when S1.11 checks them (R5-M4). S4.9 precedes S4.2 (R6-M2): S4.2's `resume` applies S4.9's per-mode admission rules and `start_at` window, while S4.9 depends only on S4.10, S4.11 and S2.6. |
| C-topology (`scripts/poc_workload_topology.py`, `scripts/poc_workload_secret_result.py`, the native integration test, the Random/TLS pins, `recovery/delete-actions.json`, the runner-spec topology text) | S4.10 only (AD-25) |
| C-runner (`scripts/poc_workload_runner.py`, `scripts/service_execution_worker.py`, `scripts/service_execution_host.py` (receipt copy-out; PROD `JOBS`, lines 27-31; the S4.17 scheduled entries with scheduled-main provenance, R7-M2), the worker diagnostics, `.github/workflows/self-deploy.yml`, `.github/workflows/scheduled-drift.yml`, `scripts/run_pulumi_command.py` (the scheduled exclusion), `scripts/poc_phase_source_adapter.py` (the `workload_route` and `workload_observation` outputs, R6-M1), `scripts/poc_workload_observation.py`, `scripts/poc_scheduled_workload_drift.py` (S4.17), the admission observation functions, receipt modules, `specs/poc-workload-runner.md` lifecycle text, the README line-127 sentence, `docs/poc-workload-log-health.md`, `test_workload_apply_docs_consistency.py`, `tests/unit/test_service_execution_worker.py`, and the workflow-shape tests that pin the CI graph (R6-M1): `tests/pulumi/test_ci_guardrails.py`, `tests/unit/test_trusted_test_controller_workflow.py`, `tests/unit/test_service_execution_workflow.py`, `tests/unit/test_poc_registry_completion_workflow.py`, `tests/unit/test_poc_registry_workflow.py`, `tests/unit/test_poc_source_workflow.py`, `tests/unit/test_poc_phase_source_adapter.py`, `tests/unit/test_service_initializer.py`, `tests/unit/test_service_execution_host.py`, `tests/unit/test_poc_scheduled_registry_workflow.py`, `tests/unit/test_service_reviewed_credentials.py` (R7-m7)) | S4.1 → S4.4 → S4.5 → S4.11 → S4.12 → S4.13 → S4.14 → S4.17 → S4.7 (R8-m7: S4.7's unstubbed PROD host seam test edits `tests/unit/test_service_execution_host.py`). S4.1 heads it because its FR-20 test is `tests/unit/test_service_execution_worker.py` (m5). S4.11–S4.14 also hold the C-contract slot at their position in that chain, because they edit `poc_workload_admission.py`. S4.17 follows XP-14, XP-15, XP-16 and S5.24 and is a gate-2b precondition only. Every rewrite of a workflow-shape test is a guardrail change that needs an `APPROVED` review by `@Kravalg` specifically, recorded like the round-5 m14 hard-stop amendment (`epics-stories.md` S4.11, S4.13, S4.14, S4.17, S4.7). |
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
  - `iam:CreateServiceLinkedRole` only with `iam:AWSServiceName` in
    {`ecs.amazonaws.com`, `ecs.application-autoscaling.amazonaws.com`,
    `elasticache.amazonaws.com`, `rds.amazonaws.com`,
    `elasticloadbalancing.amazonaws.com`}, unless BI pre-creates the SLRs.

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
