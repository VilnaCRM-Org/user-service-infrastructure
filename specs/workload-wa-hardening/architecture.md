---
artifact: architecture
workflow: _bmad/bmm/workflows/3-solutioning/bmad-create-architecture (Create mode, non-interactive)
task: workload-wa-hardening
source_baseline: 66776772979956de9c5abdbee7c45641a1b533fa
date: 2026-09-30
revision: 2 (readiness iteration 1 findings addressed)
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
  ├─ IAM: ECS execution + task roles; app-rotation, redis-rotation, redeploy,
  │        bootstrap-job roles; recovery grants; apply-role workload capability
  ├─ KMS: runtime-secrets CMK, JWT signing CMK (RSA), 2FA CMK (per D-4); key
  │        policies incl. cloudwatch/events principals for the SNS topic key
  ├─ Lambda: app-secret rotation (no VPC), redis-rbac rotation (VPC-attached to
  │          USI subnets + USI rotation-fn SG, XP-8), redeploy (no VPC),
  │          DocumentDB bootstrap job (VPC-attached, USI bootstrap-job SG);
  │          EventBridge RotationSucceeded → redeploy rule
  └─ CloudTrail: read management events (for the unauthorized-read alarm)

user-service-infrastructure (this repo; no IAM, no Lambda functions, no SecretVersion)
  ├─ secrets metadata, SecretPolicy, SecretRotation, seed aws.lambda.Invocation
  ├─ DocumentDB (managed primary password), ElastiCache RBAC users/group
  ├─ ECS, autoscaling, alarms, SNS, EventBridge alarm rules
  ├─ VPC: flow logs → S3, default SG, endpoints, egress-tight SGs,
  │        bootstrap-job SG, rotation-fn SG
  └─ E4: diagnostics, admission resume/abandon, recovery command, runtime guard,
         two-gate phase admission

user-service: #501, non-root image, MONGODB-AWS check, KMS signing/encryption,
              Redis support per D-1, multi-arch images
api-gateway-infrastructure: REST API + WAF + VPC link V2 → internal ALB (D-3 default)
```

## 3. Architecture decisions

- **AD-01 DocumentDB identity (FR-01, FR-02).**
  - **Cluster:** `aws.docdb.Cluster(manage_master_user_password=True)`, with
    no `master_password`.
  - **App connection:** `MONGODB_URL` is a plain environment value:

    ```
    mongodb://<endpoint>:<port>/<db>?tls=true&tlsCAFile=<ca>&replicaSet=rs0&readPreference=secondaryPreferred&retryWrites=false&authSource=%24external&authMechanism=MONGODB-AWS
    ```

  - **`$external` user (S5.5):** a BI VPC-attached Lambda creates it. The
    Lambda runs in the USI app subnets with the USI bootstrap-job SG.
    - It reads the DocumentDB-managed secret under the bootstrap-job role.
    - It runs `createUser` or `updateUser` to set
      `arn:aws:iam::<acct>:role/<task-role>` with `readWrite` on the app
      database only.
    - Its evidence is the run ID, the approver and a user-list hash. The
      password is never printed.
  - **Failure mode (V-1 fails):** an app DB user with a rotated password is
    needed. That is a new user decision, not a silent fallback.
- **AD-02 Redis identity (FR-04, D-1).**
  - **RBAC design:**
    - a `default` user, disabled (`off`), with no password;
    - an app user created disabled (`off ~* -@all`, `no-password-required`),
      with `ignore_changes=[access_string, authentication_mode, passwords, no_password_required]`;
    - a `UserGroup` containing both users (V-5);
    - `ReplicationGroup(user_group_ids=[…])`, with no `auth_token`.
  - **Secret:** USI creates the `redis_user` secret **without any
    `SecretVersion`**.
  - **Redis rotation function (BI):**
    - It is VPC-attached (USI rotation-fn SG; Redis port and endpoint 443).
    - `seed` (AD-06) receives this non-secret input from the USI Invocation:
      `{secret_arn, username, user_arn, host, port, access_string}`.
    - `createSecret` generates the password with `GetRandomPassword`.
    - `setSecret` calls `ModifyUser`: `passwords=[current, pending]` on
      rotation (overlap), or `[pending]` plus the reviewed access string on
      seed.
    - `testSecret` runs AUTH over TLS.
    - `finishSecret` writes the JSON
      `{username, password, user_arn, host, port, url}`.
  - **ECS references:** `REDIS_URL` and `REDIS_LOCKOUT_URL` use
    `valueFrom=arn:…:url::`.
  - **Residual risk:** the access string is enforced by reviewed Lambda code
    plus a post-apply metadata observer (`DescribeUsers.AccessString`), not
    by the Pulumi diff.
  - **IAM alternative:** `authentication_mode={type:"iam"}`, username equal to
    the user id, and `elasticache:Connect` on the task role. Needs the US token
    provider. No secret and no rotation-fn SG.
- **AD-03 Secret inventory (FR-06, FR-09).**
  - **Declared purposes** go from ten to three: `app_secret`,
    `oauth_encryption_key` and `redis_user` (absent if D-1=IAM).
  - **Observed purpose:** `documentdb_primary`, managed by DocumentDB.
  - **Removed:**
    - `document_db_password`, `document_db_url`;
    - `redis_auth_token`, `redis_url`;
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
  - The top level gains `admission: {test: bool, prod: bool}` (AD-21).
  - `central` gains `rotation_function_arns`, `redeploy_function_arn`,
    `bootstrap_job_role_arn`, `cmk` and `lambda_network`.
  - One serialized writer changes `poc_contract`, `poc_secret_observation`,
    `poc_workload_secret_result` and `poc_workload_topology`.
  - A test proves the registry contract digest is unchanged.
- **AD-05 Function ownership.**
  - All Lambda functions live in BI (R-16: the apply role is denied
    `lambda:GetFunction`, and USI may not create IAM).
  - USI references the function ARNs from reviewed central metadata. It
    creates only `SecretRotation` and the seed `aws.lambda.Invocation`.
  - The BI functions act only on an allow-listed set of secret ARN patterns
    (NFR-06).
- **AD-06 Synchronous seed (FR-05, FR-09).**
  - One `aws.lambda.Invocation` per rotated secret calls the BI `seed`, which
    runs the four steps synchronously.
  - The output schema is exactly `{secret_arn, version_id, status}`. Input may
    contain only the non-secret keys listed in AD-02. A `password` or
    `secret` key is rejected by a USI test and by the BI function.
  - Dependency order: `SecretRotation(rotate_immediately=False)`
    `depends_on` the seed, because rotation configuration runs a test rotation
    (`testSecret`) that needs AWSCURRENT. The ECS task definitions and services
    `depends_on` both.
  - V-7: TF `aws_lambda_invocation` must need only `lambda:InvokeFunction`,
    not `GetFunction`.
  - V-8: reading `Secret` and `SecretRotation` must use
    `DescribeSecret`/`GetResourcePolicy` only, not `GetSecretValue`.
- **AD-07 Redeploy on rotation (FR-05).**
  - BI owns the rule `source=aws.secretsmanager`, `eventName=RotationSucceeded`,
    restricted to the workload secret ARN patterns.
  - The redeploy Lambda calls `ecs:UpdateService(forceNewDeployment)` on the
    deterministic service ARNs:

    ```
    arn:aws:ecs:<region>:<acct>:service/<stack_tag>-ecs/<stack_tag>-web|worker
    ```

    These are fixed by `build_resource_name`. They are known before any USI
    apply, so there is no forward dependency.
  - V-4: `RotationSucceeded` delivery must be verified.
- **AD-08 Secret access control (FR-07).**
  - Each secret gets a `SecretPolicy(block_public_policy=True)`:
    `Deny GetSecretValue`, `Principal "*"`,
    `StringNotEquals aws:PrincipalArn [allow-list]`. The allow-list is exact
    role ARNs, not session ARNs; `aws:PrincipalArn` resolves an assumed role to
    its role ARN.
  - **Allow-lists:**
    - `app_secret` and `oauth_encryption_key`: the execution role and the
      app-rotation role;
    - `redis_user`: the execution role and the redis-rotation role;
    - `documentdb_primary`: the bootstrap-job role, only if V-3 confirms the
      managed rotation keeps working. Otherwise identity policy plus the
      alarm, recorded.
  - **Detection:** EventBridge rules with
    `ENABLED_WITH_ALL_CLOUDTRAIL_MANAGEMENT_EVENTS` match
    `userIdentity.sessionContext.sessionIssuer.arn` with `anything-but` the
    allow-list. Test fixtures cover assumed-role events. Rules also cover
    policy-change and rotation-failure events.
  - The BI CloudTrail read events are XP-3.
  - BI grants secret ARNs using `arn:…:secret:<name>-??????` patterns, so no
    USI apply output is needed.
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
  - `appautoscaling.Target` per service.
  - Web: target tracking on `ALBRequestCountPerTarget` (resource label) and
    CPU.
  - Worker: metric math (A-17) with a zero-task guard.
  - The ECS services use `ignore_changes=["desiredCount"]`.
  - TEST only: `ScheduledAction`s at night and on weekends.
  - The Application Auto Scaling SLR is created by BI or granted narrowly
    (N-11).
- **AD-11 Observability.**
  - A new `observability.py` owns the SNS topic (CMK per D-4, key policy in
    BI), the topic policy, the alarms and the EventBridge rules.
  - The runbooks live in `docs/sre-operations.md`.
- **AD-12 Network.**
  - Components:
    - `FlowLogs` (S3, following the `access_logs.py` pattern);
    - `DefaultSecurityGroup` with no rules;
    - `VpcEndpoints` plus an endpoint SG;
    - egress rules;
    - the `bootstrap-job` SG;
    - the `rotation-fn` SG (only when D-1=RBAC).
  - USI exports the app subnet IDs and the job and function SG IDs for XP-8.
  - The new fixed-name resources join the N-06 import list.
- **AD-13 ALB→task TLS (D-2).**
  - (B) `docs/poc-alb-target-tls-acceptance.md` with a doc-marker test.
  - (A) Caddy internal TLS on :8443, with an HTTPS target group and health
    check.
- **AD-14 Non-root.** US runs as UID ≥1000 on :8080 (or :8443 under A), with
  the supervisor socket in `/srv/app/var/run`. USI drops `ALL` capabilities
  and sets the port.
- **AD-15 KMS app keys.** BI provides:
  - a JWT key (`RSA_4096`, `SIGN_VERIFY`);
  - a 2FA key (symmetric, encryption-context `user_id`);
  - the task-role grants.

  USI passes the key ARNs as plain environment values.
- **AD-16 Recovery and admission modes.**
  - **Diagnostics:** parse the Pulumi event log into an allow-listed summary.
  - **Admission:** `mode ∈ {first, resume, abandon}`.
    - `abandon` is accepted only from the recovery workflow. It needs a
      reviewed `abandon-manifest.json` with explicit unprotects, a DocumentDB
      deletion-protection change, a final-snapshot decision with a collision
      check (`docs/poc-workload-recovery.md` §4) and a `data_loss_decision`.
    - It follows D-7.
    - It never uses the normal PR apply route, so AGENTS rule 14 is preserved
      for normal applies. The destructive diff is authorized only through the
      governance recovery environment and its reviewed manifest.
  - **Registry capture:** `scripts/poc_registry_plan.py` accepts the registry
    baseline after a verified abandon receipt.
  - **Recovery command:** `.github/workflows/recovery.yml` (main-only,
    `workflow_dispatch`, environment `test-recovery`) runs
    `scripts/poc_workload_recovery.py`, which has these subcommands:
    - `export`;
    - `release-lock`;
    - `clear-pending`;
    - `import` (from `import-list.json`);
    - `abandon`.

    Every subcommand produces evidence JSON.
  - CODEOWNERS entries for these USI files are added in USI (S4.3). BI
    provides the role grants and the environment (S5.7).
  - **Runtime guard:** the runner resolves `admission.<env>` from the
    installed `main` contract at the trusted controller checkout.
    Mismatch, missing or unreadable means refuse.
- **AD-17 Timing.** The runner records the OIDC issuance time and the
  observation end time in the evidence. The budget test compares them with
  strict bounds.
- **AD-18 Two-step first workload.**
  1. **Step 1 (saved plan):** network (including the job and function SGs),
     data (DocumentDB-managed password, Redis users disabled), secret
     metadata, ECS services with `initial_service_scale=0`, no seed and no
     rotation. The time is measured (FR-24).
  2. **BI gate:** a BI metadata PR supplies the subnet and SG IDs (XP-8).
     BI applies the VPC attachment of the redis-rotation and bootstrap-job
     Lambdas. S5.5 creates the `$external` user.
  3. **Step 2 (saved plan):** seed Invocations, `SecretRotation`s,
     `SecretPolicy`s, and the autoscaling minimums. Admission refuses step 2
     without the S5.5 evidence and the XP-8 metadata.
- **AD-19 Rollback (FR-30).**
  - Rollback means a saved-plan re-apply of the previous accepted release:
    image digests, task-definition inputs and the original registry anchor
    (existing contract rule).
  - The ECS deployment circuit breaker handles in-deploy rollback.
  - A rollback to an unaccepted release is refused.
  - Restore: a TEST DocumentDB snapshot is restored to a temporary cluster
    (reviewed operator task, evidence, deletion), as a gate for PROD.
- **AD-20 SQS and SES (FR-03).** Keep the credential-free DSNs (R-19). Add a
  regression test that rejects userinfo and keys. The BI task-role grants
  scope the seven queues and the SES identity.
- **AD-21 Two-gate admission (FR-31, D-6).**
  - The contract carries `admission: {test, prod}`.
  - The hard-stop test becomes:
    - `phase == "registry"`; or
    - (`phase == "workload"` and `admission.test` and every offline marker is
      satisfied) — gate 1; or
    - (`admission.prod` and every live-evidence marker is linked) — gate 2.
  - The README "Workload phase hard stop" is rewritten accordingly. This
    governance-reviewed change needs D-6.
- **AD-22 Legacy path (FR-29).** `UserServiceStack` managed mode (the
  non-`RuntimeSecrets` path) raises for `test` and `prod`. The
  `_create_runtime_secrets` and `_persist_url` fallbacks are removed or made
  unreachable for shared stacks. Dev and preview placeholders are unchanged.

## 4. IAM and state boundary; single-writer sequencing

**Serialized chains.** One writer per chain. A story may join a chain only
after its predecessor merges.

| Chain | Order |
| --- | --- |
| C-BI (IAM/KMS/Lambda, governance apply) | S5.1 → S5.2 → S5.4 → S5.3 → S5.7 → [live] S5.5 → S5.6 (conditional) |
| C-contract (`schemas/`, `scripts/poc_contract.py`, secret validators, topology, admission) | S1.1 → S1.7 → S1.9 → S1.8 → S4.2 → S4.3 → S4.6 → S4.7 |
| C-runtime (`runtime_secrets.py`) | S1.1 → S1.7 → S1.4 → S1.6 → S1.5 → S1.8 |
| C-data (`data.py`) | S1.2 → S1.3 → S1.4 → S1.10 |
| C-network (`network.py`) | S1.3 → S1.4 → S3.2 → S3.1 → S3.3 → S3.4 |
| C-compute (`compute.py`) | S1.3 → S1.10 → S2.1 → S1.8 → S3.5(A) → S3.7 → S2.6 |
| C-stack (`stack.py`) | S1.10 |

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

1. BI S5.1–S5.4 and S5.3 (non-VPC parts) use deterministic ARNs and patterns.
2. USI step 1.
3. The XP-8 metadata.
4. The BI VPC attachments and S5.5.
5. USI step 2.

**State risk summary:**

- No live state migrates under R-02; AD-09 fails closed.
- The new fixed-name resources join the import list.
- Protected-resource changes pass the destructive-diff gate. The only
  exception is the D-7 abandon, which runs through the recovery environment.

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
  | FR-13 | AD-11 |
  | FR-15 to FR-18 | AD-12 |
  | FR-19 | AD-13 |
  | FR-20 to FR-23 | AD-16 |
  | FR-24 | AD-17, AD-18 |
  | FR-25, FR-26 | AD-14 |
  | FR-27 | AD-05, AD-08 |
  | FR-28 | §2 (AGI) |
  | FR-29 | AD-22 |
  | FR-30 | AD-19 |
  | FR-31 | AD-21 |

- No AD creates IAM, Lambda or `SecretVersion` in USI (NFR-02, FR-09).
- **Apply-role actions needed (N-11):**
  - `secretsmanager:CreateSecret`, `PutResourcePolicy`, `RotateSecret` and
    `TagResource`;
  - `lambda:InvokeFunction` on the BI function ARNs.

  `GetSecretValue` and `GetFunction` stay denied.
- **Open verification items.** Each is the first acceptance case of its story.

  | Item | Question | Story |
  | --- | --- | --- |
  | V-1 | ext-mongodb container credentials | S5.10 |
  | V-2 | phpredis ACL user in the URL | S5.13 |
  | V-3 | Resource-policy compatibility of the DocumentDB-managed secret | S1.5 |
  | V-4 | `RotationSucceeded` delivery | S5.3 |
  | V-5 | `default` user in the user group | S1.4 |
  | V-6 | `RotateSecret` caller permissions for a BI-owned function | S1.6 |
  | V-7 | `aws_lambda_invocation` needs no `GetFunction` | S1.6 |
  | V-8 | `Secret` and `SecretRotation` reads need no `GetSecretValue` | S1.1 |
