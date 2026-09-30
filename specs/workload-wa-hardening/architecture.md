---
artifact: architecture
workflow: _bmad/bmm/workflows/3-solutioning/bmad-create-architecture (Create mode, non-interactive)
task: workload-wa-hardening
source_baseline: 66776772979956de9c5abdbee7c45641a1b533fa
date: 2026-09-30
revision: 4 (readiness round-4 findings addressed; decisions D-1…D-7 of 2026-09-30 applied, including the D-4 and D-5 clarifications)
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
| Drift check | `scripts/run_pulumi_drift_check.py` runs `pulumi preview --refresh --expect-no-changes` under the drift role |
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
  ├─ GitHub environments with Kravalg as sole reviewer: test, prod,
  │        test-recovery, test-exercise (S5.21), prod-recovery (S5.19);
  │        governance-evidence stays reviewer-less and main-only (BI
  │        _github_evidence_environment.py); ruleset check
  │        abandon-manifest-approval (S5.22)
  ├─ KMS (D-4, decided 2026-09-30): runtime CMK (secrets, every workload log
  │        group, flow-log bucket, SNS topic), JWT signing CMK (RSA), 2FA CMK;
  │        key policies name existing roles (roles are created first; AD-15a)
  ├─ Lambda: app-secret rotation + seed (no VPC), redeploy (no VPC),
  │          DocumentDB bootstrap job (VPC-attached after XP-8, USI bootstrap-job SG),
  │          restore-rehearsal reader (package S5.18a; VPC attach after XP-8, S5.18b);
  │          EventBridge RotationSucceeded → redeploy rule
  └─ CloudTrail: read management events (for the unauthorized-read alarm)

user-service-infrastructure (this repo; no IAM, no Lambda functions, no SecretVersion)
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
| Restore-rehearsal operator (BI role, S5.18a, workflow) | No | `rds:RestoreDBClusterFromSnapshot` (on the source `cluster-snapshot:` ARN, the target `cluster:<stack>-docdb-restore-rehearsal`, the existing `subgrp:` DocumentDB subnet group and the cluster parameter group), `CreateDBInstance`, `ModifyDBCluster` with `ManageMasterUserPassword` (`rds:ManageMasterUserPassword` = true), `DescribeDBClusters`, `DescribeDBClusterSnapshots`, `DeleteDBInstance`, `DeleteDBCluster` (`SkipFinalSnapshot`), `AddTagsToResource`, all conditioned on the rehearsal names. For the managed password: `secretsmanager:CreateSecret` and `secretsmanager:TagResource` on `secret:rds!cluster-*`, and `kms:DescribeKey` on `alias/aws/secretsmanager` (docs A-27; V-22). For the encrypted snapshot: `kms:CreateGrant`, `kms:Decrypt`, `kms:DescribeKey` on the DocumentDB storage key with `kms:ViaService=rds.<region>.amazonaws.com` (V-22). | Public regional endpoint from the GitHub runner. |
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
    sequence}` (AD-24), `documentdb_secret_policy` (AD-08), `scaling:
    {start_at, starts: [seq…], stops: [seq…], consumed: [name…]}` (AD-10) and
    `drift.out_of_band_fields` (AD-23).
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
    the TEST night and weekend `ScheduledAction`s → the one-time
    `<svc>-start-1` `ScheduledAction` (`depends_on` the target and every
    policy). The ECS task definitions and services exist from step 1 at 0
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
  - Workload admission (`poc_workload_admission`/`poc_workload_topology`)
    rejects any prior checkpoint containing these URN types:
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
- **AD-10 Autoscaling and create-only start/stop (R4-M5, m4).**
  - `appautoscaling.Target` per service, created in **step 2** (AD-18), with
    `min = max(contract min, 1)` and `max = contract max`.
  - Web: target tracking on `ALBRequestCountPerTarget` (resource label) and
    CPU.
  - Worker: metric math (A-17) with a zero-task guard.
  - The ECS services use `ignore_changes=["desiredCount"]` (AD-23).
  - **Start (step 2):** the service stays at `desiredCount=0` from step 1, and
    target tracking cannot scale from 0 tasks (no CPU or request data), so
    step 2 creates one one-time `ScheduledAction` per service:
    `<svc>-start-<seq>`, `schedule = at(<contract start_at>)`,
    `scalable_target_action = {min_capacity: min, max_capacity: max}`. AWS
    documents that it scales out to `MinCapacity` when current capacity is
    below it (A-26). `start_at` is a contract value set in the step-2 PR, no
    earlier than the expected apply end, and the health observation waits
    for it. The action is `create`, so step 2 stays create-only.
  - **Stop (`rollback-zero`, first deployment), two plans.** Suspending
    scheduled scaling also blocks one-time actions, so the stop and the
    suspension cannot share a plan.
    1. **Stop plan** (`workload_operation.mode: rollback-zero`,
       `phase: stop`): create-only; it creates `<svc>-stop-<seq>` with
       `min = max = 0` (A-26: scale in to `MaxCapacity`). The runner waits
       for the observed scale-in to 0 tasks.
    2. **Hold plan** (`phase: hold`, TEST only, because only TEST has
       recurring actions): exactly one `update` per target, changing only
       `suspendedState.scheduledScalingSuspended` to true, so the TEST
       morning action cannot restart a stopped service. With `max = 0`,
       dynamic scaling cannot scale out either.

    A **restart plan** (`phase: start`) updates the flag back to false (TEST)
    and creates `<svc>-start-<seq>` in the same plan. That works because the
    un-suspension is applied at apply time and the start action fires at
    least 10 min later. The mode admits nothing else: no other `update`, no
    `delete`, no change to the service or to an earlier action. V-23(d)
    checks live that a suspension blocks one-time actions and that the
    restart plan fires after the un-suspension. In PROD a stop needs gate
    2b, the `prod` environment approval and a recorded incident reason.
  - **`start_at` window.** Replay admission (the `_gate` check that runs
    immediately before `up --plan`) refuses a plan whose new start or stop
    action has an `at()` time earlier than the admission time + 10 min or
    later than the admission time + 24 h. After an approval delay, a new
    `start_at` means a new reviewed contract PR and a new saved plan.
  - **V-23 (live, S4.6 step 7)** checks three things: (a) whether registering
    the target with `min` above the current `desiredCount` of 0 already
    scales out (if so, the start action is redundant but harmless); (b)
    whether the one-time start action scales out from 0 at its time; (c)
    whether a fired one-time action stays listed. If (c) shows that AWS
    removes fired one-time actions, a refresh drops them from state, and a
    program that still renders them would propose `create`. STOP before step
    14. The reviewed fix has two parts: (1) a contract PR lists the fired
    actions in `scaling.consumed`, and the program stops rendering them; (2)
    the AD-23 entry lets the drift check accept a refresh-time removal of
    exactly those names. After both, the preview is `same`. No delete step
    is ever needed.
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
    - The `test-recovery` and `prod-recovery` environments use BI
      `scripts/_github_repository_controls.py::protected_reviewer_environment_payload`
      (bootstrap-infrastructure @debd88b, lines 308-319): reviewers =
      [Kravalg's user ID] only, `prevent_self_review: true`,
      `can_admins_bypass: false`, main-only branch policy (`test-recovery`
      by S5.21, `prod-recovery` by S5.19). This matches the AGENTS.md contract "sole environment reviewer
      Kravalg" (AGENTS.md lines 157-159).
    - In the run, `scripts/poc_workload_recovery.py abandon` refuses unless
      `GET /repos/{owner}/{repo}/actions/runs/{run_id}/approvals` shows an
      `approved` state for environment `test-recovery` by Kravalg's user ID,
      and the requester (`github.triggering_actor`) is someone else.
    - The manifest PR must be approved by Kravalg: the status check
      `abandon-manifest-approval` (created in S4.3) reads the PR reviews on
      the head SHA and needs an `APPROVED` review by Kravalg's user ID.
      S5.22 (after S4.3) makes it a required check in the ruleset. BI
      required checks are branch-wide (no path condition;
      `scripts/_github_repository_controls.py` lines 78-98 and 257 @debd88b),
      so the check reports success without further review on a PR that does
      not change `recovery/abandon-manifest.json`, and it is pinned to its
      issuing GitHub Actions integration like the other required checks
      (`_harden_status_check`).
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
    baseline after a verified abandon receipt (S4.3 issues the receipt and
    makes this change).
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
    - `export`;
    - `release-lock`;
    - `clear-pending`;
    - `import` (from `import-list.json`);
    - `abandon` (TEST only; refused in `prod-recovery`).

    Every subcommand produces evidence JSON.
  - CODEOWNERS entries for these USI files are added in USI (S4.3). BI
    provides the role grants and the environments (S5.7, S5.19, S5.21).
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
  4. **Step-2 health observation:** the trusted observer records, within a
     bounded wait after `start_at`, every service `steadyState` with
     running = desired ≥ 1, all targets `healthy`, and the app health
     endpoint green for DocumentDB (MONGODB-AWS) and Redis (IAM). A failure
     is STOP (S4.6 step 7). On success the runner issues the
     **accepted-workload receipt** (AD-24).
- **AD-19 Rollback (FR-30, m4).**
  - **First deployment** (no accepted-workload receipt yet, or the first
    accepted release is the only one): there is no prior release to return
    to. Rollback means stop serving: the create-only `rollback-zero` mode
    (AD-10) scales both services to 0. The stack stays for `resume`, recovery
    import or TEST `abandon`. The step-2 STOP rule uses this mode.
  - **Later releases** (after an accepted-workload receipt with a clean-drift
    result): a saved-plan re-apply of the previous accepted release (image
    digests, task-definition inputs and the original registry anchor;
    existing contract rule). The release/rollback secret checker accepts
    rotation-caused version changes (AD-25).
  - The ECS deployment circuit breaker handles in-deploy rollback in both
    cases.
  - A rollback to an unaccepted release is refused. A release rollback
    before any accepted-workload receipt is refused.
  - Restore: a TEST DocumentDB snapshot is restored to
    `<stack>-docdb-restore-rehearsal` under the S5.18a operator role,
    switched to a managed primary password (`ModifyDBCluster`), read by the
    S5.18b reader, then deleted; a gate for PROD.
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
      the restore item (S4.8) and XP-14. It admits only the PROD `plan`
      (`prod_preview` job), which produces the P-1 PROD-shaped preview
      evidence (FR-19); or
    - gate 2b: every gate-2a condition, plus `admission.prod: true`, plus the
      P-1 item in the receipt, which is then complete and schema-valid with
      no placeholder.
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
  change outside Pulumi.

  | Resource type | Fields allowed to change outside Pulumi | Why | Program handling |
  | --- | --- | --- | --- |
  | `aws:ecs/service:Service` | `desiredCount` | Application Auto Scaling owns it (FR-11, FR-12). | `ignore_changes=["desiredCount"]` |
  | `aws:appautoscaling/target:Target` | `minCapacity`, `maxCapacity` | The TEST night and weekend actions (FR-14c) and the one-time start and stop actions (AD-10, both environments) change them. `suspendedState` is managed by Pulumi (`rollback-zero`). | `ignore_changes=["minCapacity","maxCapacity"]` |
  | `aws:appautoscaling/scheduledAction:ScheduledAction` named `*-start-*` or `*-stop-*` | none by default. If V-23(c) shows that AWS removes a fired one-time action, a reviewed contract PR lists it in `scaling.consumed`, the program stops rendering it, and the drift check accepts a refresh-time removal of exactly the listed names (AD-10). | V-23 | not rendered once consumed |
  | `aws:docdb/cluster:Cluster` | `masterUserSecrets[*].secretStatus` | Managed rotation changes the status. These are outputs, not inputs, so refresh may change state without a diff. | none (output) |
  | `aws:elasticache/user:User`, `aws:elasticache/userGroup:UserGroup` | none | IAM auth removed the rotation Lambda that used to change passwords and access strings. | none |
  | `aws:secretsmanager/secret:Secret`, `SecretRotation`, `SecretPolicy` | none (version stages are not Pulumi state) | Rotation changes versions, not these resources. | none |
  | `aws:cloudwatch/logGroup:LogGroup` | none | `kms_key_id` is managed by Pulumi (D-4). | none |

  Tests: every `ignore_changes` in the program is on the list (N: an extra
  field fails); the drift check fails when a refresh changes an unlisted
  field. V-13 confirms that `--refresh --expect-no-changes` exits 0 when only
  listed fields changed.

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
  - **Workflow** (`.github/workflows/self-deploy.yml`): only `test_preview`,
    `test_apply` and `test_post_apply_drift` jobs exist.
  - **Docs and tests pin it:** `specs/poc-workload-runner.md` lines 37-40,
    `specs/poc/README.md` line 127, `docs/poc-workload-log-health.md` line 57,
    `tests/unit/test_workload_apply_docs_consistency.py` lines 175 and 185.

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
  secret-metadata observation. If the job dies before it can write a receipt
  (for example a credential-window timeout), the recovery `export`
  (S4.3, `test-recovery`) writes `poc-workload-export-receipt-v1` with the
  same checkpoint fields. Every receipt is published and authenticated like
  the registry proof: an immutable artifact, the protected
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
  | `resume` | latest receipt with `outcome: failed`, or an export receipt | the checkpoint holds registry resources plus a subset of the current step's graph |
  | `step2` | latest receipt: `success` of step 1 (`first` or `resume`) | S5.5 receipt; XP-8 values in the installed contract |
  | `rollback-zero`, `policy-update` | latest receipt: `success` of any mode after step 2 | — |
  | `recovery-import` | latest receipt or export receipt (after an abandon: the abandon receipt) | import list = the abandon receipt's `retain` set, or the reviewed import list; writes an **import receipt** |
  | `rebuild-first` | latest receipt is an import receipt whose predecessor is an abandon receipt | the checkpoint holds exactly the registry resources plus the abandon receipt's `retain` set; creates the rest of the step-1 graph (retained step-2 URNs stay `same`); the step-1 checker runs in its rebuild variant |
  | `recovery-abandon` | latest receipt or export receipt | the Kravalg-approved manifest lists exactly its resources |
  | `drift` | latest `success` receipt, and an accepted-workload receipt in the same lineage (no abandon in between) | read-only |
  | release, release rollback | as `drift`, plus a clean-drift result bound to the latest receipt | — |

  The C-runner chain changes this path in four stories, all before S4.6:
  1. **S4.11 step, export and abandon receipts; anchor rebinding.** The
     receipt schemas and `scripts/poc_workload_receipts.py`; issuance in the
     runner after every admitted apply (success and failure paths); the
     table above in `inspect_registry`/`observe_workload` and in `_capture`.
     S4.3 issues the export and abandon receipts with the same library.
  2. **S4.12 mode routing.** `execute` and `_gate` dispatch by
     `workload_operation.mode`: `first` → `admit_first_workload_plan`;
     `step2`, `rollback-zero`, `policy-update` → S4.9; `resume` and
     `rebuild-first` → S4.2;
     `recovery-import` and `recovery-abandon` → S4.3, only from
     `recovery.yml`. An unknown mode, a mode not allowed for the command, or
     a stale or missing anchor is refused.
  3. **S4.13 accepted-workload receipt; drift and releases.** Every admitted
     apply that leaves `desiredCount ≥ 1` (after `start_at`) runs the AD-18
     health observation. The first passing observation after step 2 writes
     `poc-workload-accepted-receipt-v1` (for example after a step-7 STOP,
     the next successful `rollback-zero` start plan). `drift` and releases
     then follow the table. Scope: runner line 154; worker line 99 (drift
     routed only with the accepted receipt), worker docstring line 5 and
     `tests/unit/test_service_execution_worker.py:166`; `self-deploy.yml`
     `test_post_apply_drift`. A **reviewed amendment** (Kravalg-approved
     governance PR) changes README line 127, runner spec lines 37-40 and
     `docs/poc-workload-log-health.md` line 57 to "Workload drift is admitted
     only with an authenticated accepted-workload receipt and is rejected
     without one." `test_workload_apply_docs_consistency.py` changes with
     them: line 175 gets the new sentence, and line 185 becomes two
     assertions (drift not routed without the receipt, routed with it).
  4. **S4.14 PROD path.** Worker `JOBS`/`ACCOUNTS` gain the PROD entries
     (`prod_preview`, `prod_apply`, `prod_post_apply_drift`; account
     `933245420672`), and `self-deploy.yml` gains the matching jobs in the
     `prod-preview` and `prod` environments. The source binding accepts
     `prod` only when the installed `main` contract has `admission.prod` =
     `"preview"` (PROD `plan` only, gate 2a) or `true` (gate 2b). The runner
     accepts `prod` with the PROD certificate parameter (the PROD counterpart
     of XP-10, SSM name recorded with the gateway owner and pinned), the PROD
     topology (S4.10), the PROD registry anchor (XP-14) and `prod-recovery`.
     `abandon` is never admitted for PROD.
  - **Regression tests (all four stories):** `step2` without a step-1
    receipt refused, admitted with one; `resume` without a failed or export
    receipt refused; `drift` without an accepted receipt refused
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
    account, replacing the hard-coded `-test-` names (topology lines 61, 859
    and 1058); the PROD graph adds the S3.5-A HTTPS target group on 8443;
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
| C-BI (IAM/KMS/Lambda/GitHub environments, governance apply) | S5.1 (every central role: execution, task, app-rotation, redeploy, bootstrap-job, restore-operator, restore-reader, exercise; no KMS statements) → S5.2 (apply capability, including the managed-password and log-group KMS describe grants) → S5.17 (preview/drift read without KMS; `iam:SimulatePrincipalPolicy` for the preview role) → S5.4 (CMKs whose key policies name only existing roles, per AD-15a; then the matching identity statements, including the preview/drift KMS read) → S5.3 (functions that use the S5.1 roles; KMS-encrypted function log groups; rules) → S5.21 (Kravalg-only environments `test`, `prod`, `test-recovery`, `test-exercise`; `governance-evidence` checked unchanged) → S5.23 (TEST exercise role) → S5.7 (test-recovery role and grants, derived from the S4.10 graph) → S5.22 (ruleset: `abandon-manifest-approval` required, after S4.3) → S5.18a (grants on the S5.1 restore-operator and restore-reader roles, reader package, no VPC) → [live, after USI step 1] S5.5 (XP-8 metadata, exact-ARN grant, bootstrap-job VPC attach, job run) → S5.18b (restore-reader VPC attach, after XP-8) → S5.6 (conditional) → S5.19 (prod-recovery) |
| C-contract (`schemas/`, `scripts/poc_contract.py`, secret validators, admission, drift allow-list, receipt schemas, acceptance-receipt validator) | S1.1 → S1.7 → S1.9 → S1.11 → S1.8 → S4.10 → S4.11 → S4.2 → S4.9 → S4.3 → S4.12 → S4.13 → S4.14 → S4.15 → S4.6 → S4.7 |
| C-topology (`scripts/poc_workload_topology.py`, `scripts/poc_workload_secret_result.py`, the native integration test, the Random/TLS pins, `recovery/delete-actions.json`, the runner-spec topology text) | S4.10 only (AD-25) |
| C-runner (`scripts/poc_workload_runner.py`, `scripts/service_execution_worker.py`, `.github/workflows/self-deploy.yml`, the admission observation functions, receipt modules, `specs/poc-workload-runner.md` lifecycle text, the README line-127 sentence, `docs/poc-workload-log-health.md`, `test_workload_apply_docs_consistency.py`, `test_service_execution_worker.py`) | S4.4 → S4.5 → S4.11 → S4.12 → S4.13 → S4.14. S4.11–S4.14 also hold the C-contract slot at their position in that chain, because they edit `poc_workload_admission.py`. |
| C-runtime (`runtime_secrets.py`) | S1.1 → S1.7 → S1.6 → S1.5 → S1.8 |
| C-data (`data.py`) | S1.2 → S1.3 → S1.4 → S1.10 → S1.9 |
| C-network (`network.py`) | S1.3 → S1.4 → S3.2 → S3.1 → S3.3 → S3.4 |
| C-compute (`compute.py`) | S1.3 → S1.4 → S1.10 → S2.1 → S1.8 → S3.7 → S2.6 → S3.5-A |
| C-stack (`stack.py`) | S1.10 |
| C-guard (`scripts/pulumi_ci_guardrails.py`, `policy/`) | S1.6 (Invocation, `aws:docdb/` and `aws:s3/bucketV2:` critical) → S3.3 (VpcEndpoint pin identity and digests) → S4.3 (recovery classifier use) |

**Independent file scopes.** These can run in parallel with at most three
agents, after the chain heads they read from:

- `observability.py` (S2.3 → S2.4 → S2.5);
- `autoscaling.py` (S2.2 after S2.1);
- the worker diagnostics (S4.1);
- the TLS doc (S3.5-B);
- US stories;
- the AGI story.

The runner guard and timing (S4.4, S4.5) are no longer independent: they
edit `scripts/poc_workload_runner.py`, so they head C-runner.

**Cross-repo gates are acyclic in time:**

1. BI S5.1 → S5.2 → S5.17 → S5.4 → S5.3 → S5.21 → S5.23 → S5.7 → S5.22 → S5.18a use
   deterministic ARNs and patterns only. The `secretsmanager` endpoint
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
  | V-13 | `preview --refresh --expect-no-changes` exits 0 when only AD-23 fields changed | docs + provider source + live | S1.11 | 14 | STOP: investigate; the list is never widened without review. |
  | V-14 | ECR layer bucket name `prod-eu-central-1-starport-layer-bucket` | docs + live pull | S3.3 | 7 | STOP: pull fails → tasks never start (health fails) → `rollback-zero`; the pinned policy is fixed in a reviewed PR and applied as a `policy-update` plan. |
  | V-15 | Condition keys `secretsmanager:RotationLambdaARN`, `RecoveryWindowInDays`, `ForceDeleteWithoutRecovery` | docs (service authorization reference) | S5.2, S5.7 | 3, 19 | STOP: key absent → redesign the grant. |
  | V-16 | Flow logs to S3 with SSE-KMS (runtime CMK, D-4) need `delivery.logs.amazonaws.com` in the key policy; creator needs `logs:CreateLogDelivery`/`DeleteLogDelivery` | docs | S3.1 | 12 | STOP: delivery fails → fix the key or bucket policy by a reviewed PR. SSE-S3 is not a fallback, because D-4 decided SSE-KMS; changing it needs a new user decision. |
  | V-17 | IAM auth needs DocumentDB 5.0 instance-based | docs (A-01) + live | S1.3 | 4 | STOP: cluster version mismatch → fix before step 2. |
  | V-18 | Which `aws.lambda.Invocation` input changes replace it; lifecycle scope (a delete makes no call under the default `CREATE_ONLY` scope) | provider source + live | S1.6 | 19 | STOP: redesign. |
  | V-19 | The DocumentDB-managed secret carries a cluster tag usable as `secretsmanager:ResourceTag` | docs + live read-only `DescribeSecret` (metadata) | S5.5, S5.18a | 5 | Fallback: exact ARN only. |
  | V-20 | `aws:PrincipalAccount` semantics for `ecr:GetAuthorizationToken`; the reviewed ECR registry account | docs + live pull | S3.3 | 7 | STOP: as V-14 (`rollback-zero`, reviewed pin fix, `policy-update` plan). |
  | V-21 | `CreateDBCluster` with `ManageMasterUserPassword` needs, under the caller (USI apply role), `secretsmanager:CreateSecret` and `TagResource` on `rds!cluster-*` and `kms:DescribeKey` on `alias/aws/secretsmanager` (documented for RDS and Aurora, A-27; not stated for DocumentDB) | docs + live simulate + live apply (CloudTrail `CreateSecret` event for the managed secret, metadata only) | S5.2 | 3, 4 | STOP: step 1 fails with `AccessDenied` → the BI grant is fixed by a reviewed PR, then S4.3 `resume`. An unneeded grant found by the CloudTrail check is removed in a reviewed PR before gate 2. |
  | V-22 | The restore operator needs `secretsmanager:CreateSecret`/`TagResource` and `kms:DescribeKey` for `ModifyDBCluster(ManageMasterUserPassword)`; `kms:CreateGrant`/`Decrypt`/`DescribeKey` on the DocumentDB storage key for the snapshot restore; and the snapshot and subnet-group resource permissions (A-27) | docs + live simulate + live restore | S5.18a | 3 (simulate); S4.8 step R-1 | STOP: restore or modify denied → BI grant fix, rehearsal re-run; the temporary cluster is deleted first. |
  | V-23 | ECS service autoscaling at 0 tasks: (a) whether `RegisterScalableTarget` with `min` above `desiredCount=0` scales out by itself; (b) whether the one-time `at()` start action scales 0 → `min` (A-26 documents it); (c) whether a fired one-time action stays listed; (d) whether `scheduledScalingSuspended` blocks one-time actions, and whether a restart plan that un-suspends and creates a start action fires it | docs (A-26, verified 2026-09-30) + live | S2.1 | 7, 7b, 15 | STOP: (b) fails → the services stay at 0 tasks, so nothing needs rolling back; the start mechanism is redesigned in a reviewed PR. (c) shows removal → STOP before step 14; the two-part fix of AD-10 (`scaling.consumed` contract PR, so the program stops rendering the fired actions, plus the AD-23 entry). (d) differs from AD-10 → STOP at step 15; the stop and hold sequence is redesigned in a reviewed PR. |
  | V-24 | Setting `retain_on_delete` (and `protect=False`, `recovery_window_in_days`, `final_snapshot_identifier`) changes only state in the unprotect plan (`update` steps, no cloud call except `rds:ModifyDBCluster`), and a later `delete` of a retained resource makes no cloud call | engine and provider source + live | S4.2 | 19 | STOP: any cloud delete observed on a retained resource → stop the abandon; recover by S4.3 import. |
  | V-25 | The ECS awslogs driver writes to a log group encrypted with the runtime CMK with no KMS statement for the execution role (A-28) | docs + live | S2.4 | 7 | Fallback: a reviewed AD-15a row for the execution role (`kms:GenerateDataKey` with `kms:ViaService=logs.<r>.amazonaws.com`), then step 7 is re-run. |
  | V-26 | The per-type delete action sets derived from the pinned provider's delete paths are complete (drain and detach calls included) for the recovery role | provider source + live (CloudTrail of the abandon run, no `AccessDenied`) | S4.10, S5.7 | 19 | STOP: an `AccessDenied` stops the removal plan mid-way → S4.3 `export`, reviewed S5.7 grant fix, then `recovery-abandon` again from the export receipt. |
