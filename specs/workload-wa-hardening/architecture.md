---
artifact: architecture
workflow: _bmad/bmm/workflows/3-solutioning/bmad-create-architecture (Create mode, non-interactive)
task: workload-wa-hardening
source_baseline: 66776772979956de9c5abdbee7c45641a1b533fa
date: 2026-09-30
revision: 3 (readiness round-3 findings addressed; user decisions D-1, D-2, D-3, D-6 of 2026-09-30 applied)
inputDocuments: [research.md, brief.md, prd.md]
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
  │        app-rotation, redeploy, bootstrap-job, restore-rehearsal roles;
  │        recovery grants (test-recovery, prod-recovery);
  │        apply-role workload capability; preview + drift read capability
  ├─ KMS: runtime-secrets CMK, JWT signing CMK (RSA), 2FA CMK (per D-4, pending);
  │        key policies name existing roles (roles are created first)
  ├─ Lambda: app-secret rotation + seed (no VPC), redeploy (no VPC),
  │          DocumentDB bootstrap job (VPC-attached after XP-8, USI bootstrap-job SG),
  │          restore-rehearsal reader (VPC-attached, USI bootstrap-job SG);
  │          EventBridge RotationSucceeded → redeploy rule
  └─ CloudTrail: read management events (for the unauthorized-read alarm)

user-service-infrastructure (this repo; no IAM, no Lambda functions, no SecretVersion)
  ├─ secrets metadata, SecretPolicy, SecretRotation, seed aws.lambda.Invocation
  ├─ DocumentDB (managed primary password), ElastiCache IAM user + default user + group
  ├─ ECS, autoscaling, alarms, SNS, EventBridge alarm rules
  ├─ VPC: flow logs → S3, default SG, endpoints (pinned policies), egress-tight SGs,
  │        bootstrap-job SG
  └─ E4: diagnostics, admission resume/abandon/step-2, recovery command,
         runtime guard, two-gate phase admission, drift allow-list

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
| Restore-rehearsal reader (BI, S5.18) | Yes: USI app subnets, USI bootstrap-job SG | `secretsmanager:GetSecretValue` on the temporary cluster's managed secret (tag-conditioned, V-19; else exact ARN by a reviewed ephemeral grant); DocumentDB wire protocol to the temporary cluster, read-only (`count`, sample `find`). | Same as the bootstrap job; the temporary cluster uses the DocumentDB SG. |
| Restore-rehearsal operator (BI role, S5.18, workflow) | No | `rds:RestoreDBClusterFromSnapshot`, `CreateDBInstance`, `ModifyDBCluster` (`ManageMasterUserPassword`), `DescribeDBClusters`, `DeleteDBInstance`, `DeleteDBCluster`, all conditioned on the `<stack>-docdb-restore-rehearsal` names | Public regional endpoint from the GitHub runner. |
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
    (FR-31).
- **AD-04 Contract evolution.**
  - `poc-test-v1` is amended in place (status `proposed-not-installed`, no
    committed workload section).
  - `secret_lifecycle` changes:
    - `generation` becomes `"rotation-seed"`;
    - `provider_refresh_actions` is removed;
    - each reference gains `rotation` (`{function_ref, schedule_days}` or
      `"service-managed"`) and `value_kind`.
  - The top level gains `admission: {test: bool, prod: bool}` (AD-21),
    `workload_step: 1 | 2` (AD-18) and `drift.out_of_band_fields` (AD-23).
  - `central` gains `rotation_function_arns`, `redeploy_function_arn`,
    `bootstrap_job_role_arn`, `cmk`, `lambda_network` (XP-8: subnet IDs,
    bootstrap-job SG ID) and `documentdb_managed_secret_arn` (XP-8).
  - One serialized writer (C-contract) changes `poc_contract`,
    `poc_secret_observation`, `poc_workload_secret_result`,
    `poc_workload_topology` and `poc_workload_admission`.
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
    `SecretPolicy` → autoscaling targets (`depends_on` both). The ECS task
    definitions and services exist from step 1 at 0 tasks and are **not**
    changed in step 2; tasks start only when the step-2 autoscaling target
    raises the desired count after the seed and rotation exist.
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
  - `documentdb_primary`: a policy allowing reads only by the bootstrap-job
    role (and not denying the service's own rotation) only if V-3 confirms the
    managed rotation keeps working. Otherwise identity policy plus the alarm,
    recorded.
  - **Detection:** EventBridge rules with
    `ENABLED_WITH_ALL_CLOUDTRAIL_MANAGEMENT_EVENTS` implement the PRD §3.2
    matching (name, full-ARN and partial-ARN `secretId`; assumed-role,
    non-role and `AWSService` callers; denied calls). Rules also cover
    policy-change, value-change and rotation-failure events.
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
- **AD-10 Autoscaling.**
  - `appautoscaling.Target` per service, created in **step 2** (AD-18).
  - Web: target tracking on `ALBRequestCountPerTarget` (resource label) and
    CPU.
  - Worker: metric math (A-17) with a zero-task guard.
  - The ECS services use `ignore_changes=["desiredCount"]` (AD-23).
  - TEST only: `ScheduledAction`s at night and on weekends. They change the
    target's min and max, so those two fields are on the TEST allow-list
    (AD-23).
  - The Application Auto Scaling SLR is created by BI or granted narrowly
    (S5.2).
- **AD-11 Observability.**
  - A new `observability.py` owns the SNS topic (CMK per D-4, key policy in
    BI), the topic policy, the alarms and the EventBridge rules.
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
  | `secretsmanager` | `secretsmanager:GetSecretValue`, `DescribeSecret` on `arn:aws:secretsmanager:${region}:${account}:secret:<declared names>-??????` and the exact XP-8 managed-secret ARN, with `aws:PrincipalAccount=${account}`. |
  | `sqs` | `sqs:SendMessage`, `ReceiveMessage`, `DeleteMessage`, `ChangeMessageVisibility`, `GetQueueAttributes`, `GetQueueUrl` on the seven deterministic queue ARNs. |
  | `kms` | `kms:Sign`, `GetPublicKey`, `Encrypt`, `Decrypt`, `GenerateDataKey` on the D-4 key ARNs from central metadata, with `aws:PrincipalAccount=${account}`. |
  | `sts` | Only `sts:GetCallerIdentity`, with `aws:PrincipalAccount=${account}`. Every other STS action is denied by omission. |
  | SES API (if V-12) | `ses:SendEmail`, `ses:SendRawEmail` on the SES identity ARN from the contract, with `aws:PrincipalAccount=${account}`. |

  Policy-pack path: `policy/guardrails.py::wildcard_iam_violations` must pass
  each rendered document unmodified. Where a wildcard is unavoidable
  (`ecr:GetAuthorizationToken` resource `*`, `-??????` suffixes), S3.3
  extends the existing `reviewed_iam_documents` pin mechanism in
  `policy/vilnacrm_guardrails.yaml` to the identity
  `aws:ec2/vpcEndpoint:VpcEndpoint|<name>` with exact sha256 pins. That is a
  reviewed governance change (CODEOWNERS), never a rule relaxation.
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
- **AD-16 Recovery and admission modes (M-5, M-6).**
  - **Diagnostics:** parse the Pulumi event log into an allow-listed summary.
  - **Admission:** `mode ∈ {first, resume, step2, abandon}`.
  - **Every recovery mutation is a saved plan through the classifier.**
    - `import`: the program runs with `import_` options for the listed
      fixed-name resources; `preview --save-plan` must contain only `import`
      and `same` steps, and the imported URNs must equal `import-list.json`
      1:1. Then `up --plan`.
    - `abandon` (only if D-7 = governed abandon, TEST only): two saved plans.
      1. **Unprotect plan:** the program with `protect=False` on the manifest
         URNs, DocumentDB `deletion_protection=False` and the manifest's
         final-snapshot setting. Its steps must be `update` or `same` only.
      2. **Removal plan:** the program in abandon mode renders the registry
         graph. `find_destructive_steps` lists the destructive steps; the set
         of `(urn, op)` must equal the manifest entries 1:1 (no extra, no
         missing). Only then does `up --plan` run in `test-recovery`.
    - The manifest carries one `secret_recovery_decision` per workload secret:
      `retain` (the secret stays, protected; the next first apply imports it)
      or `schedule-deletion` with `recovery_window_days` 7–30. `force-delete`
      is refused. A re-created secret with a pending-deletion name must be
      restored (`RestoreSecret`) and imported, never force-deleted.
  - **Rule changes, explicit (only if D-7 = governed abandon):**
    - AGENTS.md rule 14 gains: "14a. The only exception is the TEST-only
      `abandon` of the governance recovery command
      (`.github/workflows/recovery.yml`, environment `test-recovery`), whose
      saved plan's destructive steps equal the reviewed
      `abandon-manifest.json` 1:1. Labels still never authorize."
    - `docs/poc-workload-recovery.md` gains the abandon runbook section.
    - The recovery role gains `secretsmanager:DeleteSecret` (with
      `secretsmanager:RecoveryWindowInDays` ≥ 7 and
      `secretsmanager:ForceDeleteWithoutRecovery=false`, V-15),
      `RestoreSecret` and `DescribeSecret` on the workload name patterns,
      TEST only (S5.7).
    - If D-7 = no abandon, none of these changes happen; S4.3 ships no
      `abandon` subcommand and an unrecoverable TEST stack is
      stop-and-escalate.
  - **Registry capture:** `scripts/poc_registry_plan.py` accepts the registry
    baseline after a verified abandon receipt.
  - **Recovery command:** `.github/workflows/recovery.yml` (main-only,
    `workflow_dispatch`, environment `test-recovery`; `prod-recovery` for
    PROD without `abandon`) runs `scripts/poc_workload_recovery.py`, which has
    these subcommands:
    - `export`;
    - `release-lock`;
    - `clear-pending`;
    - `import` (from `import-list.json`);
    - `abandon` (only if D-7 allows; refused in `prod-recovery`).

    Every subcommand produces evidence JSON.
  - CODEOWNERS entries for these USI files are added in USI (S4.3). BI
    provides the role grants and the environments (S5.7, S5.19).
  - **Runtime guard:** the runner resolves `admission.<env>` from the
    installed `main` contract at the trusted controller checkout.
    Mismatch, missing or unreadable means refuse.
- **AD-17 Timing.** The runner records the OIDC issuance time and the
  observation end time in the evidence. The budget test compares them with
  the FR-24 margin bounds (process ≤ 3000 s, window ≤ 3300 s).
- **AD-18 Two-step first workload (FR-34, M-12).**
  1. **Step 1 (saved plan, `workload_step: 1`):** network (including the
     bootstrap-job SG), data (DocumentDB-managed password, Redis IAM and
     `default` users), secret metadata, ECS task definitions and services at
     `initial_service_scale=0`; no seed, rotation, secret policy or
     autoscaling target. The time is measured (FR-24).
  2. **BI gate (XP-8, S5.5):** a BI metadata PR supplies the subnet IDs, the
     bootstrap-job SG ID and the DocumentDB-managed secret ARN. BI applies the
     exact-ARN grant and the VPC attachment. S5.5 creates the `$external`
     user and emits its evidence receipt.
  3. **Step 2 (saved plan, `workload_step: 2`, admission mode `step2`):** seed
     Invocations → `SecretRotation`s → `SecretPolicy`s → autoscaling targets
     and policies (AD-06 order). Admission is **create-only**: every plan
     step is `create` or `same`; the created URNs equal the step-2 set; no
     `update`, `replace` or `delete` of any step-1 URN. Admission refuses
     step 2 without the S5.5 receipt and the XP-8 metadata in the installed
     `main` central metadata.
  4. **Step-2 health observation:** the trusted observer records, within a
     bounded wait, every service `steadyState` with running = desired ≥ 1,
     all targets `healthy`, and the app health endpoint green for DocumentDB
     (MONGODB-AWS) and Redis (IAM). A failure is STOP (S4.6 step 7).
- **AD-19 Rollback (FR-30).**
  - Rollback means a saved-plan re-apply of the previous accepted release:
    image digests, task-definition inputs and the original registry anchor
    (existing contract rule).
  - The ECS deployment circuit breaker handles in-deploy rollback.
  - A rollback to an unaccepted release is refused.
  - Restore: a TEST DocumentDB snapshot is restored to
    `<stack>-docdb-restore-rehearsal` under the S5.18 identity, switched to a
    managed primary password (`ModifyDBCluster`), read by the S5.18 reader,
    then deleted; a gate for PROD.
- **AD-20 SQS and SES (FR-03).** Keep the credential-free DSNs (R-19). Add a
  regression test that rejects userinfo and keys. The BI task-role grants
  scope the seven queues and the SES identity.
- **AD-21 Two-gate admission (FR-31, D-6).**
  - The contract carries `admission: {test, prod}`.
  - The hard-stop test becomes:
    - `phase == "registry"`; or
    - gate 1: `phase == "workload"`, `admission.test`, every gate-1 story
      marker present, the BI prerequisite markers present, the R-02
      observation receipt present, and every applicable decision marked
      `resolved` with a date in `prd.md` §6 (defaults do not count); or
    - gate 2: every gate-1 condition, plus `admission.prod`, plus a
      schema-valid TEST acceptance receipt (PRD §3.3) with no placeholder.
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
  | `aws:appautoscaling/target:Target` (TEST only) | `minCapacity`, `maxCapacity` | The TEST scheduled actions change them (FR-14c). | `ignore_changes` in TEST only |
  | `aws:docdb/cluster:Cluster` | `masterUserSecrets[*].secretStatus` | Managed rotation changes the status. These are outputs, not inputs, so refresh may change state without a diff. | none (output) |
  | `aws:elasticache/user:User`, `aws:elasticache/userGroup:UserGroup` | none | IAM auth removed the rotation Lambda that used to change passwords and access strings. | none |
  | `aws:secretsmanager/secret:Secret`, `SecretRotation`, `SecretPolicy` | none (version stages are not Pulumi state) | Rotation changes versions, not these resources. | none |

  Tests: every `ignore_changes` in the program is on the list (N: an extra
  field fails); the drift check fails when a refresh changes an unlisted
  field. V-13 confirms that `--refresh --expect-no-changes` exits 0 when only
  listed fields changed.

## 4. IAM and state boundary; single-writer sequencing

**Serialized chains.** One writer per chain. A story may join a chain only
after its predecessor merges.

| Chain | Order |
| --- | --- |
| C-BI (IAM/KMS/Lambda, governance apply) | S5.1 (every central role: execution, task, app-rotation, redeploy, bootstrap-job; no KMS statements) → S5.2 (apply capability) → S5.17 (preview/drift read) → S5.4 (CMKs whose key policies name only the existing S5.1 roles, then the KMS identity statements that reference the new key ARNs) → S5.3 (functions that use the S5.1 roles; rules) → S5.7 (test-recovery) → S5.18 (restore-rehearsal identity) → [live, after USI step 1] S5.5 (XP-8 metadata, exact-ARN grant, VPC attach, job run) → S5.6 (conditional) → S5.19 (prod-recovery) |
| C-contract (`schemas/`, `scripts/poc_contract.py`, secret validators, topology, admission, drift allow-list, receipt schema) | S1.1 → S1.7 → S1.9 → S1.11 → S1.8 → S4.2 → S4.9 → S4.3 → S4.6 → S4.7 |
| C-runtime (`runtime_secrets.py`) | S1.1 → S1.7 → S1.6 → S1.5 → S1.8 |
| C-data (`data.py`) | S1.2 → S1.3 → S1.4 → S1.10 |
| C-network (`network.py`) | S1.3 → S1.4 → S3.2 → S3.1 → S3.3 → S3.4 |
| C-compute (`compute.py`) | S1.3 → S1.4 → S1.10 → S2.1 → S1.8 → S3.7 → S2.6 → S3.5-A |
| C-stack (`stack.py`) | S1.10 |
| C-guard (`scripts/pulumi_ci_guardrails.py`, `policy/`) | S1.6 (Invocation critical) → S3.3 (endpoint pins) → S4.3 (recovery classifier use) |

**Independent file scopes.** These can run in parallel with at most three
agents, after the chain heads they read from:

- `observability.py` (S2.3 → S2.4 → S2.5);
- `autoscaling.py` (S2.2 after S2.1);
- the worker diagnostics (S4.1);
- the runner guard (S4.4, then S4.5);
- the TLS doc (S3.5-B);
- US stories;
- the AGI story.

**Cross-repo gates are acyclic in time:**

1. BI S5.1 → S5.2 → S5.17 → S5.4 → S5.3 → S5.7 → S5.18 use deterministic
   ARNs and patterns only.
2. USI step 1.
3. XP-8 metadata (subnet IDs, bootstrap-job SG ID, DocumentDB-managed secret
   ARN), the exact-ARN grant and the VPC attachment, then S5.5.
4. USI step 2.

**State risk summary:**

- No live state migrates under R-02; AD-09 fails closed.
- The new fixed-name resources join the import list.
- Protected-resource changes pass the destructive-diff gate. The only
  exception is the D-7 abandon (if decided), which runs through the recovery
  environment with a manifest-matched saved plan.
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
  | FR-10 | AD-04 |
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
  | FR-34 | AD-18 |

- No AD creates IAM, Lambda or `SecretVersion` in USI (NFR-02, FR-09).
- **Apply-role actions needed (N-11, S5.2):**
  - `secretsmanager:CreateSecret`, `PutResourcePolicy`, `DeleteResourcePolicy`,
    `RotateSecret` (with `secretsmanager:RotationLambdaARN` limited to the BI
    function ARNs, V-15), `CancelRotateSecret`, `TagResource`, `DescribeSecret`;
  - `lambda:InvokeFunction` on the BI function ARNs;
  - `ec2:CreateFlowLogs`, `DeleteFlowLogs`, `logs:CreateLogDelivery`,
    `logs:DeleteLogDelivery`;
  - `iam:CreateServiceLinkedRole` only with `iam:AWSServiceName` in
    {`ecs.amazonaws.com`, `ecs.application-autoscaling.amazonaws.com`,
    `elasticache.amazonaws.com`, `rds.amazonaws.com`,
    `elasticloadbalancing.amazonaws.com`}, unless BI pre-creates the SLRs.

  `GetSecretValue`, `PutSecretValue`, `UpdateSecretVersionStage` and
  `GetFunction` stay denied.
- **Open verification items (M-4).** Each item has a method and a place.
  "Docs" and "source" items are closed offline, as the first acceptance case
  of their story. "Live" items run as numbered S4.6 steps with a STOP rule
  and a fallback. No live item is closed by an offline story.

  | Item | Question | Method | Offline story | Live step (S4.6) | STOP / fallback |
  | --- | --- | --- | --- | --- | --- |
  | V-1 | ext-mongodb 2.4.1 (libmongoc) obtains ECS container credentials for `MONGODB-AWS` | source (libmongoc) + live | S5.10 | 7 | STOP: step-2 health fails → roll back to 0 tasks by saved plan; new user decision (app DB user with rotated password). |
  | V-2 | phpredis 6.3 `AUTH [user, token]`, re-`AUTH` on an open connection, and a Symfony `RedisAdapter` custom connection factory | source + US integration test against a local ACL-enabled Valkey 7.2 + live | S5.13 | 7, 10 | STOP: US fix before step 2 is retried. |
  | V-3 | A resource policy on the DocumentDB-managed secret keeps the managed rotation working | docs + live | S1.5 | 8 | Fallback: delete that `SecretPolicy` by saved plan; identity policy plus alarm; residual recorded. |
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
  | V-14 | ECR layer bucket name `prod-eu-central-1-starport-layer-bucket` | docs + live pull | S3.3 | 7 | STOP: pull fails → revert policy by saved plan, fix. |
  | V-15 | Condition keys `secretsmanager:RotationLambdaARN`, `RecoveryWindowInDays`, `ForceDeleteWithoutRecovery` | docs (service authorization reference) | S5.2, S5.7 | 3 | STOP: key absent → redesign the grant. |
  | V-16 | Flow logs to S3 with SSE-KMS need `delivery.logs.amazonaws.com` in the key policy; creator needs `logs:CreateLogDelivery`/`DeleteLogDelivery` | docs | S3.1 | 12 | Fallback: SSE-S3 (the default). |
  | V-17 | IAM auth needs DocumentDB 5.0 instance-based | docs (A-01) + live | S1.3 | 4 | STOP: cluster version mismatch → fix before step 2. |
  | V-18 | Which `aws.lambda.Invocation` input changes replace it; lifecycle scope | provider source | S1.6 | — | STOP: redesign. |
  | V-19 | The DocumentDB-managed secret carries a cluster tag usable as `secretsmanager:ResourceTag` | docs + live read-only `DescribeSecret` (metadata) | S5.5, S5.18 | 5 | Fallback: exact ARN only. |
  | V-20 | `aws:PrincipalAccount` semantics for `ecr:GetAuthorizationToken`; the reviewed ECR registry account | docs + live pull | S3.3 | 7 | STOP: revert policy by saved plan, fix. |
