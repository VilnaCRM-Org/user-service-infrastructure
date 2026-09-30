---
artifact: prd
workflow: _bmad/core/tasks/bmad-create-prd (non-interactive; steps-c 01..12 resolved from task intent)
task: workload-wa-hardening
source_baseline: 66776772979956de9c5abdbee7c45641a1b533fa
date: 2026-09-30
revision: 3 (readiness round-3 findings B-1, B-2, M-1..M-13, m-1..m-12 addressed; user decisions of 2026-09-30 recorded)
inputDocuments: [research.md, brief.md, specs/poc/README.md]
---

# PRD: Well-Architected hardening of the user-service workload

## 1. Executive summary

This PRD turns every "Workload phase hard stop" precondition into measurable
requirements with acceptance cases:

- F-01, F-02, F-03, F-04, F-08, F-09, F-14 and F-15;
- #501 and the non-root image;
- N-11, N-04 and N-06;
- #57;
- live TEST acceptance.

It adds Well-Architected items outside the hard stop:

- the front-door WAF (FR-28);
- retirement of the legacy secret path (FR-29);
- a restore rehearsal and a rollback definition (FR-30);
- the PROD gate (FR-31);
- the drift allow-list (FR-32), preview and drift read capability (FR-33) and
  the two-step first-workload admission (FR-34).

Each requirement names:

- its owning repository: USI (this repository), BI (bootstrap-infrastructure),
  US (user-service) or AGI (api-gateway-infrastructure);
- its environment (TEST first, then PROD);
- its IAM and state risk;
- its evidence.

**Automation denominator:** 34 FRs and 11 NFRs, 45 requirements in total.

| Category | Count | Requirements |
| --- | --- | --- |
| Offline-testable requirements (unit, integration, policy or doc-marker test proves source behaviour) | 40/45 | All 34 FRs, plus NFR-01, -02, -03, -06, -07 and -10 |
| Evidence-only NFRs (no offline test can prove them; a live measurement or document is the evidence) | 5 | NFR-04, -05, -08, -09, -11 |
| FRs that also require live TEST evidence (Risk column contains L; equals every FR whose §5.1 live-evidence cell is not "—") | 33 | FR-01 … FR-28 and FR-30 … FR-34 (every FR except FR-29) |
| Offline-testable NFRs that also carry live evidence | 2 | NFR-01 (TEST state metadata scan), NFR-06 (live `iam:SimulatePrincipalPolicy` run, S4.6 step 3) |

A test (`test_prd_counts`, S1.1) recomputes these counts from the tables below
so the denominator cannot drift from the rows again.

## 2. Authorized actions and failure states

- **Authorized by this plan:** nothing live. Implementation stories may change
  source and tests in their owning repository.
- **Actions that need separate, explicit, per-action authorization from the
  user in chat, then the Kravalg protected-environment gate:**
  - every live action (`pulumi preview/up`, `aws`);
  - every BI governance apply;
  - the DocumentDB `$external` bootstrap job;
  - forced rotation;
  - the recovery command;
  - the phase admission gates;
  - the restore rehearsal.

  A label, profile flag, passing test or recorded user decision never
  authorizes a live action.
- **Failure states:**
  - **BLOCKED:** a prerequisite, user decision or reviewer is missing.
  - **FAILED:** an acceptance case fails.
  - A failed live TEST step stops and escalates through the E4 recovery
    command. Before E4 lands, it is stop-and-escalate per
    `docs/poc-workload-recovery.md`. Each S4.6 step names its own STOP and
    fallback (`epics-stories.md` S4.6).
- **Quality floors, never lowered:**
  - 100% branch coverage;
  - unit, integration and policy suites each at 100% line coverage;
  - `make ci-pr` green;
  - the policy pack aligned;
  - no suppression, baseline or threshold edit.

## 3. Functional requirements

Legend:

- **Env:** T = TEST, P = PROD. PROD always follows accepted TEST.
- **Risk:**
  - IAM = changes central IAM or KMS;
  - ST = changes Pulumi state or checkpoint topology;
  - CON = changes the workload contract, schema or validators;
  - L = live evidence is required.

### E1 Secrets and identity (F-01, F-02, F-14)

| ID | Requirement | Owner | Env | Risk |
| --- | --- | --- | --- | --- |
| FR-01 | DocumentDB generates, stores and rotates the primary password in Secrets Manager (`manage_master_user_password=True`); the rotation is AWS-managed and runs no Lambda in the workload VPC. The Pulumi program and state hold no primary password. The app never receives primary credentials. | USI | T→P | ST, CON, L |
| FR-02 | The app authenticates to the DocumentDB **5.0 instance-based** cluster with `MONGODB-AWS`, using the ECS task role. Any other engine version or an elastic cluster raises at program build time (IAM auth exists only on 5.0 instance-based clusters, A-01). `MONGODB_URL` is a non-secret environment value (`authSource=%24external&authMechanism=MONGODB-AWS`, TLS, CA path) with no userinfo. A reviewed, governance-run one-time job creates the `$external` user for the task-role ARN, with `readWrite` on the app database only. | USI + BI + US | T→P | IAM, CON, L |
| FR-03 | SQS and SES are accessed through the task role only. No DSN, env var or secret contains an access key (AD-20). SES API traffic uses the SES API interface endpoint if V-12 confirms it, else NAT (FR-18). | USI (+BI grants) | T→P | IAM, L |
| FR-04 | **Redis/Valkey IAM authentication (D-1, decided 2026-09-30).** ElastiCache Redis OSS ≥7.0 or Valkey ≥7.2 with in-transit encryption **required**. An IAM-enabled ElastiCache user (`authentication_mode.type=iam`, `user_name == user_id`) with a reviewed access string, and a `default` user with access string `off` (V-5), both in one user group bound by `user_group_ids`. No `auth_token`, no Redis password, no Redis secret and no Redis rotation function exist. The task role has `elasticache:Connect` on the exact replication-group ARN and the exact IAM-user ARN. `REDIS_URL` and `REDIS_LOCKOUT_URL` are plain `rediss://<primary-endpoint>:<port>` values with no userinfo; `REDIS_IAM_USER_ID`, `REDIS_REPLICATION_GROUP_ID` (lower-case) and `AWS_REGION` are plain env values. The user-service Redis client (S5.13) signs a fresh IAM token for every new connection and re-authenticates (`AUTH`/`HELLO` with a fresh token) or reconnects before the 12 h connection limit; token lifetime is the shorter of 15 min and the task credentials' expiry (V-9). | USI + BI + US | T→P | IAM, CON, L |
| FR-05 | A reviewed rotation Lambda rotates `APP_SECRET` and `OAUTH_ENCRYPTION_KEY` on the D-5 schedule. A `RotationSucceeded` event triggers an ECS force-new-deployment of web and worker. The initial value comes from an **idempotent** synchronous seed: when the secret already has an `AWSCURRENT` version the seed returns `status=noop` and writes nothing. Seed inputs are immutable (`{secret_arn, purpose}`), and the destructive-diff classifier treats replace or delete of an `aws:lambda/invocation:Invocation` as critical. (`OAUTH_PASSPHRASE` is `non_rotatable` and is removed by FR-06, not rotated.) | BI + USI | T→P | IAM, ST, L |
| FR-06 | JWT and OAuth signing uses a KMS asymmetric key (RSA, RS256, `kms:Sign`/`GetPublicKey`). 2FA TOTP secret encryption uses KMS `Encrypt`/`Decrypt` with encryption context. The `oauth_private_key`, `oauth_public_key`, `oauth_passphrase` and `two_factor_encryption_key` secret purposes are removed. | US + USI + BI | T→P | IAM, CON, L |
| FR-07 | Every USI-declared runtime secret (`app_secret`, `oauth_encryption_key`) has a resource policy with `BlockPublicPolicy` on. It denies `secretsmanager:GetSecretValue` unless `aws:PrincipalArn` is the ECS execution role or the app-rotation role, and denies `secretsmanager:PutSecretValue` and `secretsmanager:UpdateSecretVersionStage` unless `aws:PrincipalArn` is the app-rotation role. The DocumentDB-managed secret gets a policy allowing only the bootstrap-job role (and, for reads, no other principal) only if V-3 confirms the managed rotation still works; otherwise identity policy plus the FR-13 alarm, recorded. The residual risk that admins can replace a policy is recorded; detection is FR-13. | USI (+BI role ARNs) | T→P | IAM, L |
| FR-08 | ECS secret references are the bare secret ARN (AWSCURRENT) or `arn:<json-key>::`, never a version ID. Validators record the observed AWSCURRENT version as evidence only. | USI | T→P | CON, L |
| FR-09 | Pulumi neither generates nor stores secret material. Specifically: no `pulumi_random` or `pulumi_tls` resource, and **no `aws.secretsmanager.SecretVersion` resource in USI at all**, because the apply and drift roles cannot `GetSecretValue`. Initial values come from the FR-05 seed, whose only input is `{secret_arn, purpose}`. The Random and TLS runtime pins are removed. A prior checkpoint containing `random:`, `tls:` or `SecretVersion` URNs fails admission closed. | USI | T→P | ST, CON, L |
| FR-10 | CMK scope follows D-4 (default pending explicit user confirmation). Every `kms_key_arn` and key grant resolves from reviewed central metadata. | BI + USI | T→P | IAM, CON, L |

### E2 Operations (F-03, F-04, F-15)

| ID | Requirement | Owner | Env | Risk |
| --- | --- | --- | --- | --- |
| FR-11 | The web service autoscales with target tracking on `ALBRequestCountPerTarget` and `ECSServiceAverageCPUUtilization`, within per-environment min and max. Pulumi ignores `desiredCount` (FR-32). | USI (+BI) | T→P | IAM, L |
| FR-12 | The worker autoscales on SQS backlog per task: metric math over the three work queues' `ApproximateNumberOfMessagesVisible` divided by `RunningTaskCount`. | USI | T→P | L |
| FR-13 | A service-owned, KMS-encrypted SNS topic receives every §3.1 alarm and all security and rotation events. The topic policy allows only `cloudwatch.amazonaws.com` and `events.amazonaws.com` with `aws:SourceAccount`. Every alarm has a runbook entry in `docs/sre-operations.md`. The subscription endpoint is XP-6. | USI | T→P | L |
| FR-14 | Cost and sustainability (F-15): (a) Fargate ARM64 once multi-arch images exist; (b) VPC endpoints with the NAT, endpoint and CloudTrail read-event cost trade-off recorded; (c) TEST-only scheduled scale-down; (d) a cost document with before and after figures. | USI + US | T (c), T→P | L |

#### 3.1 Alarm catalogue (FR-13)

| Alarm | Metric / event | Threshold (initial, tunable) |
| --- | --- | --- |
| DLQ depth | `ApproximateNumberOfMessagesVisible` on the three failed-* queues | ≥1 for 5 min |
| ALB 5xx | `HTTPCode_Target_5XX_Count` and `HTTPCode_ELB_5XX_Count` | >5/min for 3 of 5 min |
| Unhealthy targets | `UnHealthyHostCount` | ≥1 for 3 min |
| ECS running < desired | Container Insights `RunningTaskCount` < `DesiredTaskCount` (metric math) | 10 min; suppressed when desired = 0 |
| DocumentDB CPU / memory | `CPUUtilization` >80%; `FreeableMemory` below 10% of the class | 15 min |
| Redis memory / evictions | `DatabaseMemoryUsagePercentage` >80%; `Evictions` >0 | 5–15 min |
| Redis auth failures | ElastiCache `AuthenticationFailures` (and the IAM-auth metrics named by V-9, if published) | >0 for 5 min |
| Rotation failure | EventBridge `RotationFailed` or `RotationAbandoned` on the workload secrets | any |
| Unauthorized secret read | EventBridge `GetSecretValue` on the workload secrets (§3.2) where the caller is not allow-listed | any |
| Secret policy or value change | EventBridge `PutResourcePolicy`, `DeleteResourcePolicy`, `DeleteSecret`, `PutSecretValue` or `UpdateSecretVersionStage` on the workload secrets by a non-allow-listed caller | any |
| DocumentDB IAM auth pressure | `StsGetCallerIdentityCalls` (V-11) | informational |

#### 3.2 Unauthorized-read event matching (FR-13, m-3)

- The secret match covers every form a caller may send in
  `requestParameters.secretId`: the secret name, the full ARN and the partial
  ARN. The rule uses `prefix` matches on `<name>` and on
  `arn:aws:secretsmanager:<region>:<acct>:secret:<name>`.
- The caller match is: `userIdentity.type` is `AssumedRole` and
  `userIdentity.sessionContext.sessionIssuer.arn` is `anything-but` the
  allow-list, **or** `userIdentity.type` is anything other than `AssumedRole`
  and `AWSService`, **or** `userIdentity.type` is `AWSService` and
  `userIdentity.invokedBy` is `anything-but` the allow-listed services
  (`secretsmanager.amazonaws.com`, `rds.amazonaws.com`).
- Denied calls (`errorCode` present, e.g. `AccessDenied`) match too: an
  attempted read is an incident even when the policy stopped it.

### E3 Network and TLS (F-08, F-09)

| ID | Requirement | Owner | Env | Risk |
| --- | --- | --- | --- | --- |
| FR-15 | VPC flow logs (`traffic_type=ALL`) go to a dedicated, service-owned S3 bucket. Bucket controls: SSE-S3 (AES256) unless D-4 is confirmed with a CMK for logs, in which case SSE-KMS whose key policy allows `delivery.logs.amazonaws.com` `kms:GenerateDataKey*` and `kms:Decrypt` with `aws:SourceAccount` and `aws:SourceArn` (V-16); TLS-only; public access blocked; object ownership `BucketOwnerEnforced`; lifecycle 30 d in TEST and 90 d in PROD. The bucket policy allows `delivery.logs.amazonaws.com` `s3:PutObject` on `AWSLogs/<acct>/*` and `s3:GetBucketAcl`, each with `aws:SourceAccount` and `aws:SourceArn` = `arn:aws:logs:<region>:<acct>:*`. No IAM role is used. The apply role holds `ec2:CreateFlowLogs`, `ec2:DeleteFlowLogs`, `logs:CreateLogDelivery` and `logs:DeleteLogDelivery` (S5.2). | USI (+BI) | T→P | IAM, L |
| FR-16 | The VPC default security group is managed and has zero ingress and zero egress rules. | USI | T→P | L |
| FR-17 | The VPC has an S3 gateway endpoint and interface endpoints for `ecr.api`, `ecr.dkr`, `logs`, `secretsmanager`, `sqs`, `kms`, `sts` and, if V-12 confirms it, the SES API endpoint, with private DNS on. The endpoint SG accepts 443 only from the service and bootstrap-job SGs. Each endpoint policy is an **exact pinned document** (architecture AD-12a): the S3 gateway policy allows only `s3:GetObject` on the ECR layer bucket `arn:aws:s3:::prod-<region>-starport-layer-bucket/*` (V-14); interface policies allow only the named service actions for principals of this account on this account's (or the reviewed ECR registry account's) resources. Each document passes the policy pack unmodified or through a reviewed pin (S3.3). | USI | T→P | L |
| FR-18 | Egress is tightened: <ul><li>**Service SG:** 443 to the endpoint SG; the DocumentDB port to the DocumentDB SG; the Redis port to the Redis SG; 443 to `0.0.0.0/0` **only** if V-12 fails (SES API via NAT, recorded); no all-protocol rule.</li><li>**ALB SG:** only the container port to the service SG.</li><li>**DocumentDB SG:** ingress from the service and bootstrap-job SGs only; no egress.</li><li>**Redis SG:** ingress from the service SG only; no egress.</li><li>**Bootstrap-job SG:** the DocumentDB port to the DocumentDB SG and 443 to the endpoint SG only.</li></ul> | USI | T→P | L |
| FR-19 | ALB→task TLS per D-2 (decided 2026-09-30). **TEST:** a recorded risk acceptance citing A-14 (`docs/poc-alb-target-tls-acceptance.md`), checked by a doc test. **PROD:** an HTTPS target group and HTTPS health check on 8443 with in-container TLS (S5.20, S3.5-A), required before gate 2; a PROD stack with an HTTP target group is refused by admission. | USI (+US) | T→P | L |

### E4 Recovery and guard (N-06, #57, N-04)

| ID | Requirement | Owner | Env | Risk |
| --- | --- | --- | --- | --- |
| FR-20 | Sanitized operator diagnostics: the job summary shows the failing URN, resource type, operation and the AWS error code and message, from an allow-list of fields. Everything else, including secret-like values, is dropped. `private.log` stays private. | USI | T | L |
| FR-21 | A non-registry TEST checkpoint admission path. <ul><li>**`resume`** admits only create or update of unfinished resources and rejects replace or delete of protected URNs.</li><li>**`abandon`** (TEST only, **only if D-7 = governed abandon**) runs through the governance recovery command (FR-22), never the normal apply route. It requires a reviewed `abandon-manifest.json` naming each unprotect, the DocumentDB deletion-protection change, the final-snapshot decision with a collision check (`<stack>-docdb-final`), a `data_loss_decision`, and one `secret_recovery_decision` per workload secret (`retain` or `schedule-deletion` with `recovery_window_days` 7–30; `force-delete` is refused). Abandon executes as saved plans through the shared destructive-diff classifier; the plan's destructive steps must equal the manifest's entries 1:1 (no extra, no missing).</li></ul> After a successful abandon, registry capture (`scripts/poc_registry_plan.py`) accepts the registry baseline again. | USI | T | ST, L |
| FR-22 | A reviewed, governance-owned CI recovery command. CODEOWNERS `@Kravalg` covers the workflow and script in USI. It runs in the protected environment `test-recovery` (and `prod-recovery` for PROD, without `abandon`). Operations: stack export (private, hashed), lock release, pending-operation clear, imports of fixed-name resources from an explicit import list, and TEST abandon (FR-21, only if D-7 allows). Imports run as saved plans whose steps are only `import` or `same`, with URNs equal to the import list 1:1. It emits evidence: before and after state hashes, lock and pending listings, the import list, the saved-plan hash, run IDs and the approver. | USI + BI | T (P without abandon) | ST, IAM, L |
| FR-23 | Runtime guard (#57): the protected worker refuses workload `plan` and `up-plan` unless the installed `main` contract, not the PR head, admits the target environment (FR-31 admission field). | USI | T→P | L |
| FR-24 | Measured timing (N-04): record "OIDC issuance to result observation" and "job start to end" for each first-create step. Margin: 300 s. Gate 2 requires process time ≤ 3000 s (3300 − 300) and credential window ≤ 3300 s (3600 − 300) for every measured step; otherwise the BI `MaxSessionDuration` increase and `role-duration-seconds` (S5.6) must land first. | USI (+BI conditional) | T | IAM, L |

### E5 Cross-repo and cross-cutting

| ID | Requirement | Owner | Env | Risk |
| --- | --- | --- | --- | --- |
| FR-25 | The worker healthcheck matches the running supervisor config (user-service #501). The USI `worker_health_command` in the contract equals the published image's command. | US + USI | T→P | CON, L |
| FR-26 | The web and worker images run as non-root (UID ≥1000). USI drops all Linux capabilities for both containers and uses an unprivileged container port. | US + USI | T→P | L |
| FR-27 | BI N-11 grants: the apply-role workload capability, the central ECS roles, the app-rotation, redeploy and bootstrap-job roles, and the recovery and restore-rehearsal grants are installed as reviewed IAM documents. `scripts/poc_workload_capabilities.py` proves the simulator matrix offline (every required action allowed, every denied action denied, condition keys present), and a live `iam:SimulatePrincipalPolicy` run in S4.6 step 3 repeats it. | BI + USI | T→P | IAM, L |
| FR-28 | Front-door security per D-3 (decided 2026-09-30), outside the hard stop and required before any public exposure: a REST API regional endpoint with AWS WAF (managed common, known-bad-inputs and IP-reputation groups plus a rate rule), a private integration over **VPC link V2 directly to the internal ALB** (`integration_target` = ALB ARN; no NLB; V-10), a custom domain and a deploy pipeline. Live TEST evidence is S4.6 step 17; PROD public exposure requires it before gate 2. | AGI (+USI outputs) | T→P | L |
| FR-29 | The legacy managed path (`pulumi/app/stack.py` `UserServiceStack`, `compute.py::_create_runtime_secrets`, `data.py::_persist_url` fallback) fails closed for `test` and `prod`, or is removed. It currently writes config-supplied secret material, including the social-login client secrets, into `SecretVersion`s. Social-login secrets, if ever enabled, are written outside Pulumi by a governance secret-write path. That is future work, recorded here. | USI | T→P | ST, CON |
| FR-30 | Backup and rollback. **Restore:** a TEST DocumentDB snapshot is restored to a temporary cluster `<stack>-docdb-restore-rehearsal` under the BI restore-rehearsal identity (S5.18), the cluster is switched to a managed primary password, a VPC-attached BI reader (bootstrap-job SG) records restore time and a document-count sample, then the temporary cluster is deleted; this is a PROD gate. **Rollback:** re-apply the prior accepted release (image digests, task-definition inputs, registry anchor) as a saved plan, plus the ECS circuit breaker (AD-19). | USI + BI | T (gate for P) | IAM, L |
| FR-31 | Two-gate phase admission (D-6). **Gate 1 (TEST-only admission):** `poc-test.json` `phase: "workload"` with `admission: {"test": true, "prod": false}`, allowed only when (a) every story in the explicit gate-1 list (`epics-stories.md` S4.6 preconditions) is merged, (b) the BI prerequisites S5.1, S5.2, S5.17, S5.4, S5.3 and S5.7 are applied, (c) the one-time metadata observation confirms R-02, and (d) every decision applicable to gate 1 (D-1, D-2 TEST part, D-4, D-5, D-6, D-7) is **resolved**. **Gate 2 (PROD admission):** `admission.prod: true`, allowed only when every gate-1 check still passes **and** a schema-validated, sanitized TEST acceptance receipt (§3.3) links live evidence for: step 1 and step 2 (FR-34), clean drift (FR-32), rollback, recovery rehearsal, timing (FR-24), restore (FR-30), the FR-28 front door if PROD is publicly exposed, and D-2 PROD (FR-19 HTTPS) and D-3 resolved. The hard-stop test and the README change encode both gates. | USI | T, then P | ST, L |
| FR-32 | Drift allow-list (M-1). The contract carries a closed, per-resource-type list of fields allowed to change outside Pulumi (architecture AD-23). Every `ignore_changes` in the program must appear on that list and nothing else. "Clean drift" means the drift role's `pulumi preview --refresh --expect-no-changes` exits 0, and any refresh-time state change is on the list (V-13). | USI | T→P | CON, L |
| FR-33 | Preview and drift read capability (B-2). BI grants the `GitHubCiPreview-user-service-infrastructure-{env}` and `GitHubCiDrift-user-service-infrastructure-{env}` roles read-only (`Describe*`/`List*`/`Get*` except secret values and function code) access to every workload resource type: ec2 (VPC, subnets, SGs, endpoints, flow logs), ecs, docdb/rds describe, elasticache (including users and user groups), logs, cloudwatch, application-autoscaling, elbv2, wafv2, apigateway, events, sns, s3 (bucket configuration), secretsmanager `DescribeSecret`/`GetResourcePolicy`/`ListSecretVersionIds`, and kms `DescribeKey`/`GetKeyPolicy`/`GetKeyRotationStatus`/`ListResourceTags`. `GetSecretValue`, `lambda:GetFunction` and `kms:Decrypt` on runtime keys stay denied. The simulator matrix regression covers both roles. | BI + USI | T→P | IAM, L |
| FR-34 | Two-step first-workload admission (M-12). The contract names the step (`workload_step: 1 \| 2`). **Step 1** creates the network, data, secret metadata and ECS services at 0 tasks, with no seed, rotation, secret policy or autoscaling target. **Step 2** is admitted only in a **create-only** mode: every step in the saved plan is `create` or `same`; its created URNs are exactly the step-2 set (seed Invocations, `SecretRotation`s, `SecretPolicy`s, autoscaling targets and policies); no `update`, `replace` or `delete` of any step-1 URN. Step 2 also requires the S5.5 evidence receipt and the XP-8 metadata in the installed `main` central metadata. After step 2 a health observation must show every service steady with running = desired ≥ 1 and healthy targets. | USI | T→P | ST, CON, L |

#### 3.3 TEST acceptance receipt (FR-31 gate 2, M-11)

`schemas/poc-test-acceptance-receipt-v1.schema.json` validates the receipt.
Each evidence item has:

- `item` (one of the gate-2 items), `stack`, `source_sha` (the `main` commit),
  `contract_digest`;
- `run_id` and `run_attempt` (numeric), and a run URL under
  `https://github.com/VilnaCRM-Org/<repo>/actions/runs/<run_id>`;
- `artifact_sha256` (64 hex) for every evidence artifact;
- `requester` and `approver`, which must differ;
- no secret-like values (the FR-20 redaction runs over the receipt).

The validator refuses placeholder links (`TBD`, `TODO`, `example`, `<…>`,
all-zero IDs or hashes) and any item without every field.

## 4. Non-functional requirements

| ID | Requirement | Measure | Kind |
| --- | --- | --- | --- |
| NFR-01 | No secret material in Pulumi state, program outputs, logs, CI output, PR comments or artifacts. | A static graph test (no `random:`, `tls:` or `SecretVersion` types), redaction tests, and a TEST state metadata scan. | offline + live |
| NFR-02 | Governance: no `aws.iam.*`, OIDC trust or `aws.lambda.Function` in USI. OIDC-only credentials. Saved-plan apply only. No `AdministratorAccess`. | Policy pack and guardrail tests, plus new type-deny tests. | offline |
| NFR-03 | The quality floors (§2) are unchanged and green. | `make ci-pr`, `make test-coverage`. | offline |
| NFR-04 | TEST before PROD. Each live step is approved by Kravalg, with a requester different from the approver. | Workflow run evidence; receipt field check (§3.3). | evidence-only |
| NFR-05 | Credential changes cause no outage. **IAM paths (Redis IAM, DocumentDB IAM):** zero authentication failures. **Single-key rotations (`APP_SECRET`, `OAUTH_ENCRYPTION_KEY`):** impact stays within D-5. | **IAM paths:** during a 13 h soak that crosses the 12 h Redis connection limit and at least two task-credential refreshes, the app `auth_failure{backend=redis\|documentdb}` log metric and the ElastiCache `AuthenticationFailures` metric are both 0. **Single-key:** window W = `RotationSucceeded` time → ECS deployment `COMPLETED` + 5 min; in W the ALB 5xx alarm does not fire, and the counts of failed refresh-token and failed decrypt log events are recorded; the result passes if every failure is a forced re-login accepted by D-5. | evidence-only |
| NFR-06 | Least privilege. Every new grant is scoped to named ARNs, name patterns (`<name>-??????`), deterministic ARNs or exact XP-8 ARNs, with conditions. The BI seed and rotation functions act only on allow-listed secret ARNs. | Reviewed IAM document hashes plus the offline capability simulator, and a live `iam:SimulatePrincipalPolicy` run (S4.6 step 3). | offline + live |
| NFR-07 | Fail closed: a missing central role, CMK, decision or evidence, or a forbidden prior-checkpoint URN, gives BLOCKED admission. | Negative admission and capability tests. | offline |
| NFR-08 | An alarm reaches SNS within 5 min. | TEST alarm exercise: time from the induced condition to the SNS delivery record. | evidence-only |
| NFR-09 | An interrupted TEST first apply is resumed (or abandoned, if D-7 allows) through FR-22 within one working day, with complete evidence. | TEST rehearsal. | evidence-only |
| NFR-10 | Docs stay in sync (`specs/poc/README.md`, `secret-lifecycle.md`, `docs/poc-workload-recovery.md`, `security-baseline.md`, `sre-operations.md`, `poc-workload-admission.md`). | Doc-marker tests. | offline |
| NFR-11 | Cost: the TEST monthly estimate is recorded before and after, and each PROD increase is justified. | Cost document. | evidence-only |

## 5. Traceability: acceptance cases

P = positive, N = negative, B = boundary. Every cell is filled; no row uses
"—" for N or B.

### 5.1 Functional requirements

| Req | P | N | B | Offline test | Live evidence |
| --- | --- | --- | --- | --- | --- |
| FR-01 | The cluster args contain `manage_master_user_password=True` and no `master_password`. | A password config key raises. | The managed secret ARN is observed as metadata only. The A-05 key exception is recorded. | `test_data_plane.py` | TEST `MasterUserSecret` active, rotation enabled (metadata). |
| FR-02 | The URL contains the mechanism, source, TLS and CA. | Userinfo raises. Engine version `4.0.0` or an elastic cluster raises (V-17). | The database name is URL-encoded. The connection survives credential refresh. | `test_data_plane.py`, `test_compute_env.py` | TEST job evidence; health green; audit log shows `MONGODB-AWS`. |
| FR-03 | Queue and mailer DSNs carry no userinfo. | A key or userinfo in a DSN raises. | Region is present. `auto_setup=false`. | `test_compute_env.py` | TEST mail sent and queues consumed. CloudTrail shows the task-role session. |
| FR-04 | IAM user (`type=iam`, `user_name == user_id`), `default` user `off`, group, `user_group_ids`, `transit_encryption_mode=required`, plain `rediss://` URL, no Redis secret. | `auth_token` set, a Redis secret declared, `transit_encryption_enabled=false`, `user_name ≠ user_id`, or userinfo in `REDIS_URL` raises. A task role without `elasticache:Connect` fails the simulator. | Upper-case replication-group id is lower-cased in the env value. US: a connection older than 11 h re-authenticates; a token is regenerated per connection. | `test_data_plane.py`, `test_compute_env.py`; BI simulator; US S5.13 tests | TEST 13 h soak: no Redis auth failures (NFR-05). |
| FR-05 | Rotation plus seed per rotated purpose; `RotationSucceeded` rule to redeploy. | A secret without rotation fails the validator. A function ARN outside the BI metadata fails. A plan that replaces an Invocation is classified critical. | Seed on a secret with AWSCURRENT returns `noop` and writes nothing. Seed before `SecretRotation`. Schedule = D-5 minimum is accepted; one day less is refused. | `test_runtime_secrets.py`; `test_pulumi_ci_guardrails.py`; BI tests | TEST forced rotation → new deployment; impact per NFR-05. |
| FR-06 | No PEM or 2FA purposes; KMS key env values. | Re-adding a PEM purpose fails the schema. | Manual asymmetric key change with a dual-key window. | USI + US tests | TEST login, JWT verification, 2FA; CloudTrail `kms:Sign`. |
| FR-07 | The read deny has a `PrincipalArn` allow-list; the write deny names only the rotation role. | Missing, empty or wildcard allow-list fails. A write-deny allow-list containing the execution role fails. | Apply role still denied; admin residual risk recorded. | `test_secret_policy.py` | TEST denied read and denied `PutSecretValue` by a test principal, plus the alarm fired (no value printed). |
| FR-08 | `valueFrom` is the ARN or `arn:key::`. | A version suffix fails. | The lockout URL equals the Redis URL. | `test_runtime_secrets.py`, `test_poc_secret_observation.py` | TEST task definition has no version IDs. |
| FR-09 | No Random, TLS or `SecretVersion` types; seed input is `{secret_arn, purpose}`. | A generator or `SecretVersion` fails. A prior checkpoint with a forbidden URN is refused. | Seed input with any extra key is rejected. | runtime and topology/admission tests | TEST state metadata scan. |
| FR-10 | Key ARNs match the D-4 metadata. | Unknown key or wrong alias fails. | A-05 exception recorded. | `test_poc_contract.py` | TEST `DescribeSecret` `KmsKeyId`. |
| FR-11 | Target and policies match. | min > max, or PROD min < 1, raises; missing `ignore_changes` fails. | TEST 0 only via schedule. | `test_autoscaling.py` | TEST load test. |
| FR-12 | Metric math over three queues. | A DLQ in the math fails. | Zero tasks does not divide by zero. | `test_autoscaling.py` | TEST backlog scale-out. |
| FR-13 | Topic with KMS; every alarm actions to the topic; runbook entry exists. | Topic policy without `SourceAccount` fails. Fixtures: an execution-role session read does not match; a non-allow-listed assumed-role read matches; an `AWSService` event invoked by an unlisted service matches; a denied (`AccessDenied`) read matches. | Name, full-ARN and partial-ARN `secretId` fixtures all match. Missing-data mode per alarm. | `test_observability.py`, doc test | TEST alarm exercise. |
| FR-14 | TEST night schedule; ARM64 when multi-arch. | PROD scale-to-0 fails. | Weekend edges. | `test_autoscaling.py` | Cost document. |
| FR-15 | Flow log ALL to S3; bucket controls and delivery policy. | IAM role argument present fails. Non-TLS-only bucket fails. A delivery statement without `aws:SourceArn` fails. SSE-KMS without the delivery principal in the key policy fails. | Lifecycle 30 d TEST / 90 d PROD. | `test_flow_logs.py` | TEST object delivered. |
| FR-16 | Default SG has no rules. | Any rule fails. | Adoption and destroy semantics documented. | `test_network.py` | TEST describe shows no rules. |
| FR-17 | Endpoint set, DNS, SG; each policy equals its pinned document. | Missing endpoint fails. An extra action, extra statement or missing account condition fails the equality test and the pack. A pin whose hash does not match fails. | TEST single-AZ only with a cost record. Region placeholder renders per environment. | `test_network.py`, `test_endpoint_policies.py`, policy tests | TEST image pull via endpoints (V-14). |
| FR-18 | SG rule sets equal the expected sets, including the bootstrap-job SG. | `-1` egress to `0.0.0.0/0` fails. A `0.0.0.0/0` 443 rule without the V-12 fallback record fails. | DNS unaffected. | `test_network.py` | TEST flow logs show no rejected required flows. |
| FR-19 | TEST: doc markers present. PROD: HTTPS target group and health check. | A PROD HTTP target group is refused. | TEST doc test passes with an HTTP target group. | `test_compute.py`, doc test | TEST healthy targets; PROD-shape preview in TEST (S3.5-A). |
| FR-20 | Summary has the allow-listed fields. | Secret-like values dropped; `private.log` never uploaded. | Truncation marker. | `test_service_execution_worker.py` | TEST induced failure. |
| FR-21 | Resume admits create or update subsets. | Protected replace or delete refused. Abandon without manifest, snapshot decision, secret decisions or D-7 refused. An abandon plan with one extra or one missing destructive step is refused. `force-delete` refused. | `recovery_window_days` 7 and 30 accepted; 6 and 31 refused. Post-abandon registry capture accepts the baseline. | admission, topology, `test_poc_registry_plan.py`, `test_poc_workload_recovery.py` | TEST rehearsal. |
| FR-22 | Protected environment, main only, CODEOWNERS; import as saved plan. | PR head, non-protected environment, import mismatch or an import plan with a non-import step refused. `abandon` in `prod-recovery` refused. | Idempotent lock release. | workflow and script tests | TEST rehearsal. |
| FR-23 | Main admits the environment ⇒ allowed. | PR head admits but main does not ⇒ refused. | Missing contract ⇒ refused. | `test_poc_workload_runner.py` | TEST refusal observed. |
| FR-24 | Measured times within the margin bounds. | 3001 s process time blocks gate 2. | Exactly 3000 s process and 3300 s window pass. | `test_apply_timeout_budget.py` | TEST timing evidence. |
| FR-25 | Contract command equals the image command. | Mismatch refused. | Healthcheck grace period. | `test_poc_contract.py` | TEST worker healthy. |
| FR-26 | Capabilities drop `ALL`; unprivileged port. | An add-back fails. | Health-check port follows. | `test_compute.py`; US image test | TEST tasks healthy, `User` non-root. |
| FR-27 | Simulator: required actions allowed. | `GetSecretValue`, `GetFunction` and out-of-scope actions denied. | Conditions present. | BI tests; `test_poc_workload_capabilities.py` | TEST live simulator run. |
| FR-28 | REST stage has WAF; route reaches the service through VPC link V2 → ALB. | Direct ALB access from outside the VPC fails. An integration with an NLB target without a recorded V-10 fallback fails the AGI test. | VPC link 60-day inactivity documented. | AGI tests | TEST route and WAF sampled requests (S4.6 step 17). |
| FR-29 | Managed test/prod without `RuntimeSecrets` raises. | Any `SecretVersion` in the graph fails. | Dev/preview mode unaffected. | `test_stack.py` | — |
| FR-30 | Restore runbook and rollback procedure exist. | Rollback to an unaccepted release refused. A restore target name other than `<stack>-docdb-restore-rehearsal` refused. | The restore target is deleted after the check. | doc and admission tests | TEST restore and rollback evidence. |
| FR-31 | Gate 1 admits TEST only; gate 2 admits PROD. | Gate 1 with a missing listed story or an unresolved decision (a default is not a resolution) is refused. PROD with `admission.prod` false is refused. A receipt with a placeholder link is refused. | Gate 2 with any gate-1 check failing, or any live item missing, is refused. | `test_workload_phase_hard_stop.py`, `test_poc_acceptance_receipt.py`, runner tests | TEST acceptance receipt. |
| FR-32 | Program `ignore_changes` equals the allow-list. | An `ignore_changes` field not on the list fails. A refresh diff on an unlisted field fails the drift check. | ECS `desiredCount` change by autoscaling gives a clean drift result. | `test_drift_allow_list.py`, `test_run_pulumi_drift_check.py` | TEST clean drift after scaling (S4.6 step 14). |
| FR-33 | Simulator: every workload read allowed for both roles. | `GetSecretValue`, `GetFunction`, `kms:Decrypt` and any write denied. | Condition-less `Describe*` on types whose API has no resource ARN is recorded. | BI tests; `test_poc_workload_capabilities.py` | TEST live simulator run; a TEST preview completes. |
| FR-34 | Step 1 and step 2 URN sets; step 2 admitted in create-only mode. | A step-2 plan with any update, replace or delete of a step-1 URN is refused. Step 2 without S5.5 evidence or XP-8 metadata is refused. | An empty step-2 plan (all `same`) is admitted and changes nothing. | `test_poc_workload_admission.py`, topology tests | TEST step 1, step 2 and the step-2 health observation. |

### 5.2 Non-functional requirements

| NFR | P | N | B | Evidence |
| --- | --- | --- | --- | --- |
| NFR-01 | Graph has no secret types; redacted summary. | A seeded fake secret in a log is not in the summary. | Truncated output is still redacted. | Tests plus TEST scan |
| NFR-02 | Guardrail tests pass. | An `aws.iam.Role` or `aws.lambda.Function` added in a fixture fails. | Resource policies (`SecretPolicy`, `TopicPolicy`, bucket policy) are allowed. | Policy pack |
| NFR-03 | CI green. | A threshold edit fails `test_quality_thresholds` and review. | Coverage at exactly 100% passes; 99.99% fails. | CI run |
| NFR-04 | Approver ≠ requester. | Self-approval blocked. | PROD only after the TEST receipt. | Run evidence |
| NFR-05 | Zero IAM-path auth failures in the soak. | An injected expired token (TEST only, negative control) shows one counted failure and the alarm. | Single-key window impact within D-5; a connection at 11 h re-authenticates. | TEST exercise |
| NFR-06 | Simulator allows the scoped actions. | Wildcard resource rejected in review. | `name-??????` patterns match only the intended secrets. | IAM hashes, live simulator |
| NFR-07 | Complete inputs are admitted. | Each missing input is BLOCKED. | Unreadable metadata is BLOCKED. | Tests |
| NFR-08 | Delivery within 5 min. | Disabled alarm action detected by test. | Delivery at exactly 300 s passes; 301 s fails. | TEST exercise |
| NFR-09 | Resume succeeds. | Abandon without D-7 refused. | Lock already released. | Rehearsal |
| NFR-10 | Markers present. | Stale marker fails. | A marker present in one doc but missing in its pair fails. | Doc tests |
| NFR-11 | Estimate recorded. | A PROD increase without a justification line fails the doc test. | TEST vs PROD split. | Cost document |

## 6. User-owned decisions

**"Resolved" means an explicit user decision recorded here with its date.** A
default is not a resolution. A default applies only to source planning and
never authorizes a live action. Gate 1 and gate 2 check resolution, not
defaults (FR-31).

| ID | Decision | Options | Status | Blocks |
| --- | --- | --- | --- | --- |
| D-1 | Redis/Valkey auth mode | IAM auth (US change) or rotated RBAC password (infra-only) | **RESOLVED 2026-09-30 by the user: IAM auth.** The RBAC password, the Redis secret and the Redis rotation Lambda are removed from the plan; a `default` user with access string `off` is kept. | S1.4, S5.1, S5.13, gate 1 |
| D-2 | ALB→task TLS | (A) in-container TLS or (B) recorded acceptance | **RESOLVED 2026-09-30 by the user:** (B) recorded risk acceptance for TEST; (A) in-container TLS required in PROD before gate 2. | S3.5-B (TEST), S5.20 + S3.5-A (PROD), gate 2 |
| D-3 | WAF placement | (a) REST API + WAF + VPC link V2; (b) HTTP API with WAF on the internal ALB; (c) CloudFront + WAF | **RESOLVED 2026-09-30 by the user: (a) REST API + WAF.** Integration: VPC link V2 directly to the ALB (V-10, docs-verified 2026-09-30); NLB→ALB only as a reviewed fallback if the live check fails. S3.6 is dropped. | S5.16, gate 2 (public exposure) |
| D-4 | CMK scope | AWS-managed; one runtime CMK per environment plus JWT and 2FA CMKs; per-purpose CMKs | **DEFAULT PENDING EXPLICIT USER CONFIRMATION:** runtime CMK per environment plus JWT and 2FA CMKs; the DocumentDB-managed secret stays on the AWS key (A-05); flow logs use SSE-S3. Not decided. | S1.9, S5.4, gate 1 |
| D-5 | App-secret rotation cadence and accepted impact | 30, 90 or 180 days; optional US previous-key tolerance (S5.15) | **DEFAULT PENDING EXPLICIT USER CONFIRMATION:** 90 days, forced re-login accepted, S5.15 not scheduled. Not decided. | S1.6, gate 1 |
| D-6 | Amend the hard stop into two gates (FR-31) | Two-gate admission, or keep the single gate | **APPROVED 2026-09-30 by the user: two gates.** Governance still requires `@Kravalg` approval of the source PR that amends `specs/poc/README.md` and its test (S4.6 step 1). What D-6 relaxes is listed in §6.1. | S4.6, S4.7 |
| D-7 | Abandon authority | (a) governance recovery command with a reviewed manifest, TEST only, which amends AGENTS.md rule 14 as in architecture AD-16; (b) no abandon (resume and import only; an unrecoverable TEST stack is stop-and-escalate) | **OPEN — no default.** An explicit user decision is required before any abandon implementation (the S4.2 abandon scope, the S4.3 `abandon` subcommand, the AGENTS.md rule-14 amendment and the runbook section). | S4.2 (abandon part), S4.3 (abandon part), gate 1 |

### 6.1 What D-6 relaxes, and what it keeps

**Relaxed** (moved from "before the `workload` phase" to "before PROD
admission"):

- "Live TEST acceptance of the first workload apply, clean drift and
  rollback" (README hard stop, last bullet);
- the N-04 rule "no `workload` phase until the first create is measured
  within these bounds or that increase is landed". Under two gates, the TEST
  first create is the measurement; the bound applies at gate 2 (FR-24).

**Kept** (still required at gate 1):

- every other hard-stop precondition (F-01 … F-15, #501, non-root, N-11);
- the N-06 sub-preconditions (admission path, diagnostics, import path,
  recovery command), so a failed TEST first apply is recoverable;
- the runtime guard (#57);
- "TEST before PROD", saved-plan apply and the Kravalg environment gates.

**Accepted risk under gate 1:** a TEST first create may exceed the 3600 s
credential window and leave a state lock; FR-22 recovers it. PROD is never
admitted by gate 1.

## 7. External prerequisites (not satisfiable by USI)

- **XP-1.** BI installs the central ECS execution and task roles. They are
  proposed only; `d41c019` is unavailable locally (R-14).
- **XP-2.** BI provides the apply-role workload capability and boundary (N-11),
  and the preview and drift read capability (FR-33).
- **XP-3.** BI provides the CMKs, key policies, the app-rotation, redeploy and
  bootstrap-job functions and roles, the restore-rehearsal identity, and
  CloudTrail read events.
- **XP-4.** US provides #501, the non-root image, the MONGODB-AWS check, the
  Redis IAM token provider, KMS signing and encryption, in-container TLS for
  PROD and multi-arch images.
- **XP-5.** AGI provides the front door per D-3.
- **XP-6.** The user supplies the SNS subscription endpoint.
- **XP-7.** The devops-sdlc profile `.claude/devops-sdlc.json` must exist
  (created by `do-sdlc-setup`) before implementation.
- **XP-8.** After the step-1 apply, a reviewed BI metadata PR supplies the
  values that are not deterministic: the USI app subnet IDs, the
  **bootstrap-job SG ID** and the **DocumentDB-managed secret ARN**
  (`rds!cluster-…`). BI then grants the bootstrap-job role
  `secretsmanager:GetSecretValue` on that exact ARN (plus the
  `secretsmanager:ResourceTag` cluster condition if V-19 confirms the tag), and
  attaches the bootstrap-job Lambda to those subnets and that SG. No other BI
  grant depends on an apply output.
