---
artifact: research
workflow: _bmad/bmm/workflows/1-analysis/research/bmad-technical-research (bmalph 2.11.0)
task: workload-wa-hardening
repository: VilnaCRM-Org/user-service-infrastructure
branch: feat/workload-wa-hardening
source_baseline: 66776772979956de9c5abdbee7c45641a1b533fa (PR #56 head)
date: 2026-09-30
status: planning-only
revision: 3 (A-16 and A-20 re-verified 2026-09-30; A-23..A-25 added; D-1, D-2, D-3 decided by the user)
---

# Technical research: Well-Architected hardening of the user-service ECS workload

## 1. Scope and method

This research covers the preconditions listed in `specs/poc/README.md`,
"Workload phase hard stop", which gate the switch of `specs/poc/poc-test.json`
`phase` from `registry` to `workload`.

The findings come from four kinds of evidence:

- **Source.** Pinned repository source at `6677677`.
- **Sibling repositories.** Read-only reads of sibling repositories:
  - the local `bootstrap-infrastructure` clone at `debd88b`;
  - the local `api-gateway-infrastructure` clone;
  - `VilnaCRM-Org/user-service` at `main` through `gh api`.
- **AWS documentation.** AWS documentation retrieved with the aws-knowledge MCP
  tools.
- **Provider schema.** The installed Pulumi AWS provider Python SDK 7.23.0 in
  `~/.venvs/user-service-infrastructure`.

Constraints on the evidence:

- No AWS or Pulumi command ran against any account.
- No secret value was read.
- Each claim carries one of these tags:
  - `[SRC]` repository source read;
  - `[AWS]` AWS documentation;
  - `[SDK]` Pulumi provider schema;
  - `[UNVERIFIED]` needs confirmation during implementation.

## 2. Current state (baseline `6677677`)

### 2.1 Phase and live state

- **R-01 `[SRC]`.** `specs/poc/poc-test.json` has `phase: "registry"` and
  status `proposed-not-installed`. `tests/unit/test_workload_phase_hard_stop.py`
  fails any phase change and requires every hard-stop marker to appear in
  `specs/poc/README.md`.
- **R-02 `[SRC]`.** No workload resource has been applied in TEST or PROD.
  - The recorded TEST checkpoint is the 11-resource registry graph: seven
    registry resources, the SES identity and three DKIM records.
  - The workload path (`WorkloadPhaseStack`) has never produced a checkpoint.
  - **Consequence:** moving secret generation out of Pulumi state is a
    source-only change. No live `pulumi_random` or `pulumi_tls` state exists
    that would need `state rm` or import.
  - This holds only while R-02 stays true. Any workload apply before these
    stories land turns them into a state migration (see architecture AD-09).

### 2.2 Secrets (F-01, F-02)

- **R-03 `[SRC]`.** `pulumi/app/runtime_secrets.py` generates material inside
  Pulumi state and writes it into Secrets Manager. `RandomPassword` and
  `RandomBytes` come from `pulumi_random` 4.19.2; `tls.PrivateKey` RSA-4096
  comes from `pulumi_tls` 5.3.1.

  | Material | Generator | Written to |
  | --- | --- | --- |
  | `document_db_password` | `RandomPassword` | `SecretVersion` (protected) |
  | `redis_auth_token` | `RandomPassword` | `SecretVersion` (protected) |
  | `app_secret` | `RandomBytes` | `SecretVersion` (protected) |
  | `oauth_encryption_key` | `RandomBytes` | `SecretVersion` (protected) |
  | `oauth_passphrase` | `RandomBytes` | `SecretVersion` (protected) |
  | `two_factor_encryption_key` | `RandomBytes` | `SecretVersion` (protected) |
  | `oauth_private_key` / `oauth_public_key` | `tls.PrivateKey` | `SecretVersion` (protected) |

  The state is KMS-encrypted, but the values are recoverable by anyone who can
  decrypt the state: the operator or the apply role path. That is the
  "human/AI-usable long-lived secret" problem.
- **R-04 `[SRC]`.** `pulumi/app/data.py` has three problems:
  - It feeds the generated password into `aws.docdb.Cluster.master_password`,
    and the app uses the primary user through `MONGODB_URL`
    (`authSource=admin`).
  - It feeds the generated token into `aws.elasticache.ReplicationGroup.auth_token`
    with `auth_token_update_strategy="ROTATE"`.
  - It composes `document_db_url` and `redis_url` secrets that embed those
    credentials.
- **R-05 `[SRC]`.** `RuntimeSecrets.ecs_secrets()` injects eight secrets through
  nine environment names, pinned as `<arn>:::<version_id>`. `REDIS_LOCKOUT_URL`
  reuses the `REDIS_URL` reference. This is F-02.
- **R-06 `[SRC]`.** Other code encodes the ten-purpose inventory and its
  version-preservation rule, so it must change together with the runtime:
  - `specs/poc/secret-lifecycle.md`;
  - `scripts/poc_secret_observation.py`;
  - `scripts/poc_workload_secret_result.py`;
  - `scripts/poc_workload_topology.py`;
  - `scripts/poc_contract.py`;
  - `schemas/poc-test-v1.schema.json`: `workload.secret_lifecycle` requires
    owner, namespace, generation, guard_amendment, provider_refresh_actions,
    review and references, and each reference is exactly
    `{name, kms_key_arn, owner}`;
  - the fixtures and tests.
- **R-07 `[SRC]`.** The trusted runtime installs Random 4.19.2 and TLS 5.3.1
  before credentials, with SHA-256 pins. Removing the generators allows
  removing those pins.

### 2.3 Operations (F-03, F-04, F-15)

- **R-08 `[SRC]`.** Current ECS settings:
  - `web_desired_count` and `worker_desired_count` default to 2;
  - there is no Application Auto Scaling;
  - there are no CloudWatch alarms and no SNS topic;
  - the ECS cluster has `containerInsights=enhanced`, so `RunningTaskCount` is
    available for metric math;
  - Fargate `runtime_platform` is `X86_64`;
  - DocumentDB uses `db.t4g.medium` × 2 and Redis uses `cache.t4g.small` with
    one replica, both Graviton;
  - there is one NAT gateway per AZ.

### 2.4 Network and TLS (F-08, F-09)

- **R-09 `[SRC]`.** `pulumi/app/network.py` has these gaps:
  - no VPC flow logs;
  - the VPC default security group is unmanaged;
  - the service SG egress is all protocols to `0.0.0.0/0`;
  - the ALB SG egress is all traffic to `0.0.0.0/0`;
  - the DocumentDB and Redis SGs allow all egress to the VPC CIDR;
  - there are no VPC endpoints.

  For the private-gateway workload the ALB is internal. Its SG admits 443 only
  from the VPC-link SG.
- **R-10 `[SRC]`.** The target group and its health check use `HTTP` on
  container port 80. The HTTPS listener uses `ELBSecurityPolicy-TLS13-1-2-Res-2021-06`
  and requires an admitted `certificateArn`.

### 2.5 Recovery and guard (N-04, N-06, #57)

- **R-11 `[SRC]`.** `docs/poc-workload-recovery.md` states N-06 is NOT met:
  - there is no resume or abandon admission for a non-registry checkpoint;
  - there is no import path for fixed-name resources;
  - Pulumi output stays in `private.log` (`scripts/service_execution_worker.py:141-153`,
    mode 0600, "private logs never reach Actions");
  - there is no command that exports state, releases the lock or clears
    pending operations.
- **R-12 `[SRC]`.** N-04 timing budget:
  - `.github/workflows/self-deploy.yml:344` `test_apply` `timeout-minutes: 70`;
  - the service-transport `pulumi up` has a 3300 s process timeout;
  - no `role-duration-seconds` is set, so the STS session is 3600 s;
  - `MARGIN_SECONDS=300` is an assumption and has not been measured.
- **R-13 `[SRC]`.** The phase gate is PR-head only. Issue #57 tracks a runtime
  guard that is independent of the PR head.

### 2.6 Cross-repository facts

- **R-14 `[SRC]` bootstrap-infrastructure `debd88b`:**
  - The ECS execution and task roles consumed by the workload are not defined
    on `main`. `pulumi/infra/iam/task_roles.py` is a 7-line stub.
  - `specs/poc/README.md` cites a proposed inventory
    (`pulumi/seed/catalogs/poc-runtime-test.json`, local source commit
    `d41c019`). That commit is not present in the local clone, so the central
    roles are proposed and not installed.
- **R-15 `[SRC]`** The apply role `GitHubCiApply-user-service-infrastructure-<env>`
  is backend-scoped:
  - its automation policy families are s3, kms, ce, backup, sqs, cloudtrail, ecr,
    config, sns, secretsmanager, events, budgets, securityhub, guardduty and
    limited iam;
  - it has no ecs, ec2, elasticache, docdb/rds, logs, cloudwatch,
    application-autoscaling, lambda or wafv2 actions;
  - `docs/governance-stack.md:188-192` says workload resource deployment needs a
    reviewed bootstrap boundary change (N-11).
- **R-16 `[SRC]`.** `DenySecretLeakingReadsApply` (`ci_bootstrap.py:153-166,626-655`)
  denies these actions to the apply role:
  - `secretsmanager:GetSecretValue`, except `/<project>/ci/*`;
  - `ssm:GetParameter*`;
  - `lambda:GetFunction`;
  - `ecr:GetAuthorizationToken`.

  **Consequence:**
  - Pulumi cannot read any `aws.lambda.Function` in this repo, because refresh
    calls `GetFunction`.
  - Rotation and redeploy functions must therefore be owned by
    bootstrap-infrastructure (AD-05).
  - The apply role never reads secret values, which matches the design.
- **R-17 `[SRC]`.** No `MaxSessionDuration` is set on the CI roles, so the
  default is 3600 s. No runtime-secret CMK exists centrally. The only KMS key is
  the Pulumi secrets alias.
- **R-18 `[SRC]` user-service `main`, database:**
  - `ext-mongodb` 2.4.1, `mongodb/mongodb` 2.4.1, `doctrine/mongodb-odm` 2.16.1;
  - `doctrine_mongodb.yaml` passes `MONGODB_URL` with empty `options`, so the
    auth mechanism must be expressed in the URI;
  - the Dockerfile bundles the DocumentDB CA bundle.
  - `[UNVERIFIED]` whether the libmongoc bundled in ext-mongodb 2.4.1 obtains
    ECS container credentials (`AWS_CONTAINER_CREDENTIALS_RELATIVE_URI`) for
    `MONGODB-AWS`. This needs a TEST integration check (story S5.10).
- **R-19 `[SRC]` user-service, messaging and mail:**
  - `symfony/amazon-sqs-messenger` v7.4.6 on `async-aws/core` 1.28.1. With no
    key in the DSN, `accessKeyId` is null and the async-aws default chain
    includes `ContainerProvider`.
  - `symfony/amazon-mailer` v8.1.5 (`ses+api://default?region=…`) likewise
    passes a null user.
  - The health-check `Aws\Sqs\SqsClient` uses the SDK default chain.

  **Consequence:** SQS and SES already work with task-role credentials and no
  static keys. The current DSNs (`compute.py::_queue_dsn`, `mailer_dsn`)
  contain no credentials.
- **R-20 `[SRC]` user-service, Redis:**
  - Redis is consumed through phpredis 6.3.0 via
    `RedisAdapter::createConnection(REDIS_URL|REDIS_LOCKOUT_URL)`.
  - There is no ElastiCache IAM token support; IAM auth needs an app change.
    D-1 = IAM auth (user decision, 2026-09-30), so this change is story S5.13.
  - `[UNVERIFIED]` whether phpredis 6.3 accepts `AUTH [user, token]` and
    re-`AUTH` on an open connection through a custom `RedisAdapter` factory
    (V-2).
- **R-21 `[SRC]` user-service, key material and what rotation breaks:**
  - `APP_SECRET` is the kernel secret. Rotation invalidates Symfony-signed
    artefacts.
  - `league/oauth2-server` 9.3.0 and `lexik/jwt-authentication-bundle` 3.2.0
    read the OAuth and JWT keys as file paths, with `OAUTH_PASSPHRASE`.
    Rotating the keypair invalidates issued access tokens.
  - `OAUTH_ENCRYPTION_KEY` (type `plain`) encrypts refresh tokens and auth
    codes. Rotation invalidates outstanding ones.
  - `TWO_FACTOR_ENCRYPTION_KEY` is AES-256-GCM. Rotation makes stored TOTP
    secrets undecryptable. Previous-key support is only a "Growth" spec item.
  - There is no KMS integration.
- **R-22 `[SRC]` user-service, container runtime:**
  - No `USER` directive: web (FrankenPHP) and worker (supervisord) run as root.
  - The supervisor socket `/run/supervisor.sock` is `chmod=0700`.
  - PR #501 (worker healthcheck) is OPEN and not merged.
- **R-23 `[SRC]`.** api-gateway-infrastructure is an untouched scaffold with a
  single example S3 bucket. It has no API, VPC link, domain, WAF or pipeline.

- **R-24 `[SRC]` legacy path.** The legacy managed path writes config-supplied
  secret material into `SecretVersion`s. It runs without `RuntimeSecrets`
  (`pulumi/app/stack.py` `UserServiceStack`). Two places do the writing:
  - `compute.py::_create_runtime_secrets` covers the mailer DSN, the app keys,
    the OAuth PEMs and the GitHub, Google, Facebook and Twitter client
    secrets;
  - the `data.py::_persist_url` fallback covers the connection URLs.

  It must fail closed for shared stacks (FR-29).
- **R-25 `[SRC]` Pulumi reads.** Pulumi reads `aws.secretsmanager.SecretVersion`
  with `GetSecretValue`. That call is denied to the apply and drift roles
  (R-16). Therefore USI must not own any `SecretVersion`. This was found by
  the readiness review; confirm it as V-8 for `Secret` and `SecretRotation`.

## 3. AWS capability verification

| ID | Claim | Tag / source |
| --- | --- | --- |
| A-01 | IAM auth is available only on DocumentDB instance-based cluster version 5.0. The primary user cannot use IAM and stays password-based. | [AWS] documentdb/latest/devguide/iam-identity-auth.html |
| A-02 | IAM users and roles are created in `$external` by the primary user: `db.createUser({user:"arn:aws:iam::<acct>:role/<role>", mechanisms:["MONGODB-AWS"], roles:[…]})`. Authorization stays at DB level. | [AWS] same page |
| A-03 | The connection string uses `authSource=%24external&authMechanism=MONGODB-AWS`. Drivers pick up ECS task-role credentials from the environment. Connections do not drop when the temporary credentials expire. The dependency on STS carries throttling risk. The `StsGetCallerIdentityCalls` metric exists. | [AWS] same page; repost documentdb-iam-authentication-issues |
| A-04 | DocumentDB can manage the primary password in Secrets Manager at create or modify time. The default rotation is every 7 days and is modifiable. The secret is deleted with the cluster. A CMK may be specified. Global clusters and cross-Region replicas are not supported. | [AWS] documentdb/latest/devguide/docdb-secrets-manager.html |
| A-05 | Pulumi AWS 7.23.0 `aws.docdb.Cluster` exposes `manage_master_user_password` and `master_user_secrets`, but no `master_user_secret_kms_key_id`. The KMS key of the DocumentDB-managed secret therefore cannot be set from this provider version. | [SDK] pulumi_aws/docdb/cluster.py |
| A-06 | ElastiCache IAM auth works on Redis OSS ≥7.0 or Valkey ≥7.2 and needs TLS. Username must equal user ID. A token is valid 15 min. Connections drop after 12 h unless re-authenticated. `elasticache:Connect` is required. Current engine: redis 7.1 with TLS required, so it is eligible. | [AWS] AmazonElastiCache/latest/dg/auth-iam.html |
| A-07 | ElastiCache RBAC passwords can be rotated by a Secrets Manager rotation Lambda through `ModifyUser`. The secret JSON holds `{username,password,user_arn}`. The Lambda needs `elasticache:DescribeUsers` and `ModifyUser` plus the Secrets Manager rotation actions. For Valkey the initial user needs a temporary password with access string `off`.  Historical: not used after D-1 = IAM auth. | [AWS] AmazonElastiCache/latest/dg/User-Secrets-Manager.html |
| A-08 | A user may hold up to two passwords, which gives the dual-password overlap.  Historical: not used after D-1 = IAM auth. | [AWS] CDK PasswordUserProps; ModifyUser `passwords`; [SDK] `aws.elasticache.User` supports `authentication_mode.type ∈ {password,no-password-required,iam}` |
| A-09 | Migration from AUTH to RBAC uses `modify-replication-group --auth-token-update-strategy DELETE --user-group-ids-to-add`. Not needed here, because the cluster has never been created (R-02). | [AWS] Clusters.RBAC.html |
| A-10 | ECS injects secrets only at container start. A rotated value needs new tasks or a force new deployment. `valueFrom` = the bare secret ARN resolves AWSCURRENT, and `arn:…:<json-key>::` selects a JSON key (Fargate PV ≥1.4.0). | [AWS] AmazonECS/latest/developerguide/secrets-envvar-secrets-manager.html; containers blog |
| A-11 | Secrets Manager emits `RotationStarted`, `RotationSucceeded`, `RotationFailed` and `RotationAbandoned` as `AWS Service Event via CloudTrail`. | [AWS] secretsmanager/latest/userguide/cloudtrail_log_entries.html |
| A-12 | EventBridge receives read-only management events such as `GetSecretValue` only when the rule state is `ENABLED_WITH_ALL_CLOUDTRAIL_MANAGEMENT_EVENTS` and a CloudTrail trail logs read management events. | [AWS] eventbridge/latest/userguide/eb-service-event-cloudtrail-management.html; compute blog |
| A-13 | Secret resource policies are evaluated with identity policies, and an explicit deny wins. A deny on `GetSecretValue` conditioned on principal is a documented pattern. | [AWS] determine-acccess_examine-iam-policies.html; storage blog |
| A-14 | An ALB target group supports HTTPS. The ALB does not validate target certificates, so self-signed ones work. In-VPC traffic is authenticated at packet level. | [AWS] elasticloadbalancing/latest/application/load-balancer-target-groups.html |
| A-15 | HTTP APIs have no AWS WAF integration; choose REST APIs for WAF. WAF associates with ALB (including internal), REST API stages, AppSync and CloudFront. | [AWS] apigateway/latest/developerguide/http-api-vs-rest.html; WAFV2 AssociateWebACL |
| A-16 | REST APIs support private integration with an ALB directly through VPC link V2 (V1 supports NLB only). VPC link V2 subnets and SGs are immutable. Links go INACTIVE after 60 days of inactivity. The load balancer, link and API must be in the same account. Re-verified 2026-09-30: the What's New entry of 2025-11 lists Europe (Frankfurt); `pulumi_aws` 7.23.0 `apigateway.Integration` exposes `integration_target` (ALB or NLB ARN for VPC link V2). Live check: V-10. | [AWS] whitepaper best-practices-api-gateway-private-apis-integration/rest-api.html; whats-new/2025/11/api-gateway-rest-apis-integration-load-balancer; [SDK] pulumi_aws/apigateway/integration.py |
| A-17 | ECS worker scaling can use SQS backlog per task: metric math `ApproximateNumberOfMessagesVisible / RunningTaskCount`. `RunningTaskCount` needs Container Insights. | [AWS] AmazonECS/latest/developerguide/service-autoscaling-queue.html |
| A-18 | Flow logs to CloudWatch Logs need an IAM role trusted by `vpc-flow-logs.amazonaws.com`, which this repository may not create. Flow logs to S3 need only creator permissions plus the bucket policy. | [AWS] vpc flow-logs-iam-role.html; flow-logs-s3-create-flow-log.html |
| A-19 | Security Hub EC2.2 requires VPC default security groups with no inbound or outbound rules. | [AWS] securityhub ec2-controls.html |
| A-20 | Fargate tasks in private subnets use ECR (api, dkr and S3 for layers), Secrets Manager and CloudWatch Logs interface endpoints when present. **Corrected 2026-09-30:** SES now supports VPC endpoints for its API (What's New 2025-12, all SES Regions), not only SMTP. The endpoint service name and private DNS for the SES v2 host used by async-aws are V-12; if V-12 fails, SES API egress stays via NAT. | [AWS] AmazonECS/latest/developerguide/vpc-endpoints.html; whats-new/2025/12/amazon-ses-vpc-api-endpoints; ses send-email-set-up-vpc-endpoints.html |
| A-21 | KMS RSA keys support `RSASSA_PKCS1_V1_5_SHA_256` (RS256) sign and verify. `GetPublicKey` exports the public key. | [AWS] kms symm-asymm-choose-key-spec.html |
| A-22 | The Pulumi 7.23.0 SDK exposes the building blocks the plan needs: `aws.secretsmanager.SecretRotation(rotate_immediately, rotation_lambda_arn)`, `SecretPolicy(block_public_policy)`, `aws.ec2.DefaultSecurityGroup`, `aws.appautoscaling.{Target,Policy,ScheduledAction}` and `aws.elasticache.{User,UserGroup}`. | [SDK] |
| A-23 | ElastiCache IAM auth limits (re-verified 2026-09-30): TLS required; token valid 15 min (and not beyond the signing credentials' expiry); connection disconnected after 12 h unless `AUTH`/`HELLO` with a new token; no re-auth inside `MULTI`/`EXEC` or Lua; username = user id; for replication groups only `aws:SourceIp` and `aws:ResourceTag/*` conditions; cache names are lower case. Revoking `elasticache:Connect` does not drop open sessions; removing the user from the group does. | [AWS] AmazonElastiCache/latest/dg/auth-iam.html; connecting-public-endpoint.html |
| A-24 | DocumentDB publishes `StsGetCallerIdentityCalls` (calls the instance makes to regional STS for `MONGODB-AWS`), and the audit log records `mechanism = MONGODB-AWS`. | [AWS] documentdb/latest/devguide/iam-identity-auth.html |
| A-25 | With `manage_master_user_password`, DocumentDB rotates the primary secret itself (default 7 days); no customer Lambda is deployed. | [AWS] secretsmanager integrating_how-services-use-secrets_DocDB; CDK docdb README |

## 4. Options analysis

| Topic | Options | Recommendation (default until the user decides) |
| --- | --- | --- |
| DocumentDB auth | (a) primary user via secret (today); (b) DocumentDB-managed primary + app user password rotated by Lambda; (c) DocumentDB-managed primary + IAM (`MONGODB-AWS`) app user | (c). No app password exists at all. It needs a reviewed one-time `$external` bootstrap job and a TEST check of ext-mongodb 2.4.1 container credentials. |
| Redis auth (**D-1**) | (a) IAM auth: phpredis token provider needed (user-service change), 12 h re-auth; (b) RBAC user, password rotated by a reviewed Lambda with dual passwords, URL delivered through a JSON key; (c) keep AUTH token rotation (`ROTATE`/`SET`) | **Decided by the user 2026-09-30: (a) IAM auth.** It removes the Redis secret, the VPC rotation Lambda and its network path. |
| App secrets | Reviewed rotation Lambda plus a `RotationSucceeded` → ECS force-new-deployment hook | Adopted. The rotation impact on sessions and tokens is recorded (D-5). |
| JWT keys, 2FA key | Stay in Secrets Manager (not rotatable without breakage), or KMS asymmetric sign and KMS encrypt | KMS. This needs user-service stories. |
| Function ownership | This repo, or bootstrap-infrastructure | bootstrap-infrastructure, because of R-16 and the no-IAM rule. |
| ALB→task TLS (**D-2**) | (a) HTTPS target group with in-container TLS (Caddy internal cert, port 8443); (b) recorded acceptance citing A-14 | **Decided by the user 2026-09-30:** (b) for TEST; (a) required in PROD before gate 2. |
| WAF (**D-3**) | (a) REST API + WAF + VPC link V2 → ALB; (b) HTTP API, with WAF on the internal ALB; (c) CloudFront + WAF → HTTP API | **Decided by the user 2026-09-30: (a)**, with VPC link V2 directly to the ALB (A-16), no NLB. Under (b) the ALB sees the VPC-link ENI IPs, so IP reputation and rate rules need `forwarded_ip_config` and a spoofing analysis. (c) is rejected, because origin lock-down needs a long-lived shared header secret. |
| CMK scope (**D-4**) | (a) AWS-managed keys; (b) one bootstrap-owned symmetric CMK per environment for runtime secrets, plus an asymmetric JWT CMK and a symmetric 2FA CMK; (c) per-purpose CMKs | (b), a default pending explicit user confirmation. The DocumentDB-managed secret stays on `aws/secretsmanager` until the provider supports `master_user_secret_kms_key_id` (A-05). |
| Flow logs | S3 or CloudWatch Logs | S3, because no IAM role is needed (A-18). |
| Egress | SG-only tightening; Network Firewall or DNS Firewall | SG tightening plus VPC endpoints, including the SES API endpoint if V-12 passes, which removes the last `0.0.0.0/0` rule. FQDN filtering is deferred for cost reasons and recorded. |

## 5. Risks discovered

1. **State-migration window (AD-09).** If anyone applies the workload phase
   before E1 lands, the generators and protected `SecretVersion`s enter state.
   Removal would then need the reviewed recovery command, which does not exist
   today.
2. **Central roles.** The central ECS roles are proposed and not installed, and
   their source is unavailable locally (R-14). Every live acceptance blocks on
   bootstrap.
3. **Apply-role deny.** The apply role's `lambda:GetFunction` deny (R-16) rules
   out Lambdas owned by this repo.
4. **DocumentDB-managed secret key.** The provider gap (A-05) prevents a CMK on
   the DocumentDB-managed secret.
5. **Unauthorized-read detection.** Detection depends on central CloudTrail
   read-event logging (A-12), which is not verified.
6. **Asynchronous rotation seeding.** A seeded secret may have no AWSCURRENT
   when ECS starts. This needs a synchronous seed invocation (AD-06).
7. **Session breakage.** Rotation of `APP_SECRET` or `OAUTH_ENCRYPTION_KEY`
   logs users out or invalidates tokens (D-5).
8. **Preview and drift roles.** No reviewed BI grant is known to give the
   preview and drift roles read access to the workload resource types
   (readiness round 3, finding B-2; the same gap as R-15 for the apply role).
   Until FR-33 lands, no workload preview or drift check can be relied on.
9. **Managed-secret ARN.** The DocumentDB-managed secret name is not
   deterministic, so the bootstrap-job grant must wait for XP-8.
10. **Non-root image.** Moving to non-root needs the port moved to ≥1024 and the
   supervisor socket re-owned. This is a coordinated change across
   user-service and this repository.
