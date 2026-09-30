---
artifact: prd
workflow: _bmad/core/tasks/bmad-create-prd (non-interactive; steps-c 01..12 resolved from task intent)
task: workload-wa-hardening
source_baseline: 66776772979956de9c5abdbee7c45641a1b533fa
date: 2026-09-30
revision: 7 (readiness round-7 findings R7-M1, R7-M2, R7-m1..m9 and R7-n1..n3, plus audit F2, F6 and F8, addressed on top of revision 6; decisions D-1..D-14 of 2026-09-30 recorded: D-1..D-7 and D-14 as user decisions, D-8..D-13 as confirmed details)
inputDocuments: [research.md, brief.md, decisions.md, specs/poc/README.md, specs/poc-workload-runner.md]
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
- the drift allow-list (FR-32), preview and drift read capability (FR-33),
  the two-step first-workload admission (FR-34) and the runner lifecycle
  (authenticated step and accepted-workload receipts, mode routing, PROD
  path; FR-35).

Each requirement names:

- its owning repository: USI (this repository), BI (bootstrap-infrastructure),
  US (user-service) or AGI (api-gateway-infrastructure);
- its environment (TEST first, then PROD);
- its IAM and state risk;
- its evidence.

**Automation denominator:** 35 FRs and 11 NFRs, 46 requirements in total.

| Category | Count | Requirements |
| --- | --- | --- |
| Offline-testable requirements (unit, integration, policy or doc-marker test proves source behaviour) | 41/46 | All 35 FRs, plus NFR-01, -02, -03, -06, -07 and -10 |
| Evidence-only NFRs (only live or document evidence meets them; their offline fixtures check the evidence format, never the requirement itself) | 5 | NFR-04, -05, -08, -09, -11 |
| FRs that also require live TEST evidence (Risk column contains L; equals every FR whose §5.1 live-evidence cell is not "—") | 34 | FR-01 … FR-28 and FR-30 … FR-35 (every FR except FR-29) |
| Offline-testable NFRs that also carry live evidence | 2 | NFR-01 (TEST state metadata scan, S4.6 steps 4a and 7a), NFR-06 (live `iam:SimulatePrincipalPolicy` run, S4.6 step 3) |

A test (`test_prd_counts`, S1.1) recomputes these counts from the tables below
so the denominator cannot drift from the rows again.

## 2. Authorized actions and failure states

- **Authorized by this plan:** nothing live. Implementation stories may change
  source and tests in their owning repository.
- **Actions that need separate, explicit, per-action authorization from the
  user in chat, then the Kravalg protected-environment gate:**
  - every live action (`pulumi preview/up`, `aws`);
  - every BI governance apply and every USI repository-controls apply
    (S5.21, S5.22);
  - the DocumentDB `$external` bootstrap job;
  - forced rotation;
  - the recovery command, including the TEST abandon and rebuild rehearsal;
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
| FR-05 | A reviewed rotation Lambda rotates `APP_SECRET` and `OAUTH_ENCRYPTION_KEY` every **90 days** (D-5, decided 2026-09-30; forced re-login at rotation is accepted). A `RotationSucceeded` event triggers an ECS force-new-deployment of web and worker. The initial value comes from an **idempotent** synchronous seed: when the secret already has an `AWSCURRENT` version the seed returns `status=noop` and writes nothing. Seed inputs are immutable (`{secret_arn, purpose}`), and the destructive-diff classifier treats replace or delete of an `aws:lambda/invocation:Invocation` as critical. `OAUTH_PASSPHRASE` is **not rotated** (D-5): it stays `non_rotatable` until the KMS JWT move (FR-06, S1.8) retires it. The DocumentDB master password keeps the AWS-managed 7-day rotation (FR-01). | BI + USI | T→P | IAM, ST, L |
| FR-06 | JWT and OAuth signing uses a KMS asymmetric key (RSA, RS256, `kms:Sign`/`GetPublicKey`). 2FA TOTP secret encryption uses KMS `Encrypt`/`Decrypt` with encryption context. The `oauth_private_key`, `oauth_public_key`, `oauth_passphrase` and `two_factor_encryption_key` secret purposes are removed. | US + USI + BI | T→P | IAM, CON, L |
| FR-07 | Every USI-declared runtime secret (`app_secret`, `oauth_encryption_key`) has a resource policy with `BlockPublicPolicy` on. It denies `secretsmanager:GetSecretValue` unless `aws:PrincipalArn` is the ECS execution role or the app-rotation role, and denies `secretsmanager:PutSecretValue` and `secretsmanager:UpdateSecretVersionStage` unless `aws:PrincipalArn` is the app-rotation role. The DocumentDB-managed secret gets a `SecretPolicy` created in step 2 and never deleted by an apply mode (only the TEST abandon, FR-21, removes it with its cluster). Its document is selected by the contract field `documentdb_secret_policy`, which has three states: `deny-other-readers` (reads denied unless the bootstrap-job role; the initial state, so the V-3 live check runs with the policy present), `allow-rotation` (the same read deny, plus the rotation principal or condition that V-3 identifies), and `tls-only` (a single `Deny` of `GetSecretValue` when `aws:SecureTransport` is `false`; no legitimate caller is affected). A transition is an update-only saved plan: admission mode `policy-update` admits exactly one `update` step, on a URN from the closed set {managed-secret `SecretPolicy`, each `VpcEndpoint`}, with `policy` as the only changed input. The residual risk that admins can replace a policy is recorded; detection is FR-13. | USI (+BI role ARNs) | T→P | IAM, L |
| FR-08 | ECS secret references are the bare secret ARN (AWSCURRENT) or `arn:<json-key>::`, never a version ID. Validators record the observed AWSCURRENT version as evidence only. | USI | T→P | CON, L |
| FR-09 | Pulumi neither generates nor stores secret material. Specifically: no `pulumi_random` or `pulumi_tls` resource, and **no `aws.secretsmanager.SecretVersion` resource in USI at all**, because the apply and drift roles cannot `GetSecretValue`. Initial values come from the FR-05 seed, whose only input is `{secret_arn, purpose}`. The Random and TLS runtime pins are removed (by S4.10, when the pre-hardening program branch is deleted). A prior checkpoint containing `random:`, `tls:` or `SecretVersion` URNs fails admission closed. | USI | T→P | ST, CON, L |
| FR-10 | CMK scope follows D-4 (decided 2026-09-30). One runtime CMK per environment encrypts the USI-declared secrets, every workload CloudWatch log group (`kms_key_id` on the ECS web and worker, the pre-created Container Insights performance group, DocumentDB audit and profiler, and BI function log groups), the VPC flow-log bucket (SSE-KMS) and the alarm SNS topic. Separate CMKs exist for JWT signing (RSA) and 2FA encryption. The DocumentDB-managed master secret stays on the AWS-managed key (A-05). Every `kms_key_arn` and key grant resolves from reviewed central metadata. The per-key principal, action and condition table is architecture AD-15a. | BI + USI | T→P | IAM, CON, L |

### E2 Operations (F-03, F-04, F-15)

| ID | Requirement | Owner | Env | Risk |
| --- | --- | --- | --- | --- |
| FR-11 | The web service autoscales with target tracking on `ALBRequestCountPerTarget` and `ECSServiceAverageCPUUtilization`, within per-environment min and max. Pulumi ignores `desiredCount` (FR-32). **Create-only start and stop (m4, R4-M5):** the services exist at 0 tasks after step 1. Step 2 creates, per service, the scalable target, its policies and a one-time `ScheduledAction` `<svc>-start-<seq>` for the single unconsumed `scaling.starts` entry (`schedule = at(<that entry's at>)`, `min = max(contract min, 1)`, `max = contract max`). **Per-action times (R5-M3):** the contract lists each action with its own time (`scaling.starts: [{seq, at}]`, `scaling.stops: [{seq, at}]`); an entry is immutable once its URN is in the checkpoint, and a new operation only appends an entry, so the rendered inputs of earlier actions never change. AWS documents that a one-time action scales out to `MinCapacity` when current capacity is below it (A-26). A rollback to 0 tasks uses admission mode `rollback-zero` in two plans, because a scheduled-scaling suspension also blocks one-time actions: a create-only **stop** plan creates `<svc>-stop-<seq>` with `min = max = 0`, and the run's separate observation job records running = desired = 0 (R6-m6). A TEST-only **hold** plan is admitted only with that authenticated stop observation; its only change is the target's `suspendedState.scheduledScalingSuspended` = true, rendered from the persistent TEST-only contract flag `scaling.scheduled_scaling_suspended` (R6-m7), so the morning schedule cannot restart a stopped service. A **start** plan clears the flag and creates `<svc>-start-<seq>` for a new `scaling.starts` entry. Only a hold plan sets the flag and only a start plan clears it; a `policy-update` during a hold keeps it and renders no `Target` update. No plan changes the service, deletes anything or changes an earlier action. Only the new entry's `at()` time is checked, against the replay admission time: at least + 10 min for a `rollback-zero` plan and + 60 min for a `step2` plan, at most + 120 min (architecture AD-10); the health observation runs in its own job, so the apply's FR-24 bounds are unchanged. V-23 confirms the behaviour live, and its provider-source part (e) is checked before S4.9 merges. | USI (+BI) | T→P | IAM, L |
| FR-12 | The worker autoscales on SQS backlog per task: metric math over the three work queues' `ApproximateNumberOfMessagesVisible` divided by `RunningTaskCount`. | USI | T→P | L |
| FR-13 | A service-owned SNS topic, encrypted with the runtime CMK (D-4; CloudWatch alarms cannot publish to an `alias/aws/sns` topic), receives every §3.1 alarm and all security and rotation events. The topic policy allows only `cloudwatch.amazonaws.com` and `events.amazonaws.com` with `aws:SourceAccount`. Every alarm has a runbook entry in `docs/sre-operations.md`. The subscription endpoint is XP-6. | USI | T→P | L |
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
  `arn:aws:secretsmanager:<region>:<acct>:secret:<name>`. For the
  DocumentDB-managed secret, whose name is not deterministic, the prefix is
  `rds!cluster-`. That prefix covers every DocumentDB- or RDS-managed secret
  in the account, so it can only alarm too often, never too little, and it
  needs no XP-8 value.
- The caller match is: `userIdentity.type` is `AssumedRole` and
  `userIdentity.sessionContext.sessionIssuer.arn` is `anything-but` the
  allow-list, **or** `userIdentity.type` is anything other than `AssumedRole`
  and `AWSService`, **or** `userIdentity.type` is `AWSService` and
  `userIdentity.invokedBy` is `anything-but` the allow-listed services
  (`secretsmanager.amazonaws.com`, `rds.amazonaws.com`).
- Denied calls (`errorCode` present, e.g. `AccessDenied`) match too: an
  attempted read is an incident even when the policy stopped it.

#### 3.2a Allow-list per alarm event type (m3)

Each EventBridge rule has its own closed allow-list. A caller that the table
does not allow for an event type always matches (alarms). An allow-list entry
is an exact role ARN (`sessionIssuer.arn`) or an `invokedBy` service.

| Event type | Allow-listed callers (no alarm) | Scope |
| --- | --- | --- |
| `GetSecretValue` (declared secrets) | ECS execution role; app-rotation role | TEST and PROD |
| `GetSecretValue` (DocumentDB-managed secrets, `rds!cluster-` prefix) | bootstrap-job role; restore-reader role (TEST, restore rehearsal); `rds.amazonaws.com`, `secretsmanager.amazonaws.com` (managed rotation) | TEST and PROD |
| `PutSecretValue`, `UpdateSecretVersionStage` | app-rotation role; `secretsmanager.amazonaws.com` (rotation); for the managed secret also `rds.amazonaws.com` | TEST and PROD |
| `PutResourcePolicy` | USI apply role (`GitHubCiApply-user-service-infrastructure-{env}`), only while a step-2 or `policy-update` saved plan runs. Every other `PutResourcePolicy` alarms. | TEST and PROD |
| `RotateSecret` | USI apply role (step 2 `SecretRotation`); app-rotation role; `secretsmanager.amazonaws.com`, `rds.amazonaws.com` (scheduled and managed rotation); TEST exercise role (forced rotation, S4.6 steps 8 and 9). Every other caller alarms. | exercise role TEST only |
| `DeleteResourcePolicy` | TEST recovery role (`GitHubCiRecovery-user-service-infrastructure-test`), abandon only. Every other call alarms, including every PROD call. | TEST only |
| `DeleteSecret`, `RestoreSecret` (declared secrets) | TEST recovery role: `DeleteSecret` in an abandon run, `RestoreSecret` in the rebuild. Every other call alarms, including every PROD call. | TEST only |
| `DeleteSecret` (DocumentDB-managed secrets) | `rds.amazonaws.com` (`AWSService`; the cluster deletion of an abandon or of the restore rehearsal deletes its secret, A-27). Every other caller alarms. | TEST and PROD |
| `RotationFailed`, `RotationAbandoned` | none | TEST and PROD |

An allow-listed caller does not alarm for that event type only. An
EventBridge pattern cannot express "only while … runs", so the identity
enforces it: only the protected saved-plan worker can assume the apply role,
and only the `test-recovery` environment can assume the recovery role. The
acceptance receipt (S4.6 step 21) lists every allow-listed event of the
campaign with the run ID that caused it. An allow-listed event without a
matching run is a finding. S2.5 tests every row (P, N, B).

### E3 Network and TLS (F-08, F-09)

| ID | Requirement | Owner | Env | Risk |
| --- | --- | --- | --- | --- |
| FR-15 | VPC flow logs (`traffic_type=ALL`) go to a dedicated, service-owned S3 bucket. Bucket controls: **SSE-KMS with the runtime CMK** (D-4, decided 2026-09-30); the runtime key policy allows `delivery.logs.amazonaws.com` `kms:GenerateDataKey*` and `kms:Decrypt` with `aws:SourceAccount` and `aws:SourceArn` (V-16); bucket key on; TLS-only; public access blocked; object ownership `BucketOwnerEnforced`; `force_destroy=false`; lifecycle 30 d in TEST and 90 d in PROD. The bucket policy allows `delivery.logs.amazonaws.com` `s3:PutObject` on `AWSLogs/<acct>/*` and `s3:GetBucketAcl`, each with `aws:SourceAccount` and `aws:SourceArn` = `arn:aws:logs:<region>:<acct>:*`. No IAM role is used. The apply role holds `ec2:CreateFlowLogs` and `logs:CreateLogDelivery` (S5.2); the matching deletes belong to the TEST recovery role (S5.7), because no apply mode deletes. SSE-S3 is not a fallback: if SSE-KMS delivery fails, the step STOPs until the key policy is fixed. | USI (+BI) | T→P | IAM, L |
| FR-16 | The VPC default security group is managed and has zero ingress and zero egress rules. | USI | T→P | L |
| FR-17 | The VPC has an S3 gateway endpoint and interface endpoints for `ecr.api`, `ecr.dkr`, `logs`, `secretsmanager`, `sqs`, `kms`, `sts` and, if V-12 confirms it, the SES API endpoint, with private DNS on. The endpoint SG accepts 443 only from the service and bootstrap-job SGs. Each endpoint policy is an **exact pinned document** (architecture AD-12a) that uses deterministic values only, so it needs no apply output. The S3 gateway policy allows only `s3:GetObject` on the ECR layer bucket `arn:aws:s3:::prod-<region>-starport-layer-bucket/*` (V-14). Interface policies allow only the named service actions for principals of this account on this account's (or the reviewed ECR registry account's) resources. The `secretsmanager` policy reaches DocumentDB-managed secrets through `secret:rds!cluster-*`, limited by `aws:PrincipalArn` to the bootstrap-job and restore-reader roles plus `aws:PrincipalAccount`; it never names the XP-8 ARN. Each document passes the policy pack unmodified or through a reviewed pin (S3.3). | USI | T→P | L |
| FR-18 | Egress is tightened, after a reviewed **outbound-traffic inventory** (`docs/poc-egress-inventory.md`, S3.4) lists every destination, port and path the web and worker containers use (the user-service configuration, HTTP clients, SDK endpoints, SES, OAuth providers if enabled). A destination missing from the inventory blocks S3.4. <ul><li>**Service SG:** 443 to the endpoint SG; the DocumentDB port to the DocumentDB SG; the Redis port to the Redis SG; 443 to `0.0.0.0/0` **only** if V-12 fails (SES API via NAT, recorded); no all-protocol rule.</li><li>**ALB SG:** only the container port to the service SG.</li><li>**DocumentDB SG:** ingress from the service and bootstrap-job SGs only; no egress.</li><li>**Redis SG:** ingress from the service SG only; no egress.</li><li>**Bootstrap-job SG:** the DocumentDB port to the DocumentDB SG and 443 to the endpoint SG only.</li></ul> | USI | T→P | L |
| FR-19 | ALB→task TLS per D-2 (decided 2026-09-30). **TEST:** a recorded risk acceptance citing A-14 (`docs/poc-alb-target-tls-acceptance.md`), checked by a doc test. **PROD:** an HTTPS target group and HTTPS health check on 8443 with in-container TLS (S5.20, S3.5-A), required before gate 2; a PROD stack with an HTTP target group is refused by admission. The PROD-shaped preview evidence (P-1) is the PROD `plan` admitted by gate 2a (`admission.prod: "preview"`, S4.14 `prod_preview` job). It runs after S3.5-A, never inside S4.6 (m1). | USI (+US) | T→P | L |

### E4 Recovery and guard (N-06, #57, N-04)

| ID | Requirement | Owner | Env | Risk |
| --- | --- | --- | --- | --- |
| FR-20 | Sanitized operator diagnostics: the job summary shows the failing URN, resource type, operation and the AWS error code and message, from an allow-list of fields. Everything else, including secret-like values, is dropped. `private.log` stays private. | USI | T | L |
| FR-21 | A non-registry TEST checkpoint admission path. <ul><li>**`resume`** admits only `create` or `update` of unfinished resources and rejects replace or delete of protected URNs.</li><li>**`abandon`** (TEST only; D-7, decided 2026-09-30) runs only through the governance recovery command (FR-22), never the normal apply route. It needs a reviewed `abandon-manifest.json` that lists every resource of the checkpoint (except the eleven registry resources) with one decision each: `delete` or `retain`. It also names the DocumentDB deletion-protection change, the final-snapshot decision with a collision check (`<stack>-docdb-final`) and a `data_loss_decision`. Each workload secret has one `secret_recovery_decision`: `retain`, or `schedule-deletion` with `recovery_window_days` 7–30; `force-delete` is refused. **Log buckets:** the ALB access-log bucket and the flow-log bucket, with every bucket sub-resource (ownership, public-access block, encryption, versioning, lifecycle, policy), are always `retain`. `force_destroy` stays `false`, no object is deleted, and a manifest that sets `delete` on any of them is refused. A `retain` entry becomes `retain_on_delete=True` in the unprotect plan, so its later `delete` step removes it from state only, and the rebuild imports it (FR-22). **Comparison (R4-M4):** the removal plan may contain only `delete` and `same` steps. Every other op is refused (`update`, `replace`, `create-replacement`, `delete-replaced`, `discard`, `discard-replaced`, `remove-pending-replace`, `read-replacement`, `import-replacement`). The set of `delete` URNs, of every resource type (not only `find_destructive_steps` critical types), must equal the manifest's `delete` and `retain` entries 1:1, and the `same` URNs must equal the registry baseline.</li><li>**Approval:** the manifest PR and the run are approved by **@Kravalg specifically**. The `test-recovery` environment has Kravalg as its sole required reviewer with `prevent_self_review` and no admin bypass (USI repository controls, S5.21; role S5.7), and the recovery script refuses unless the run's environment approval (`GET /repos/{owner}/{repo}/actions/runs/{run_id}/approvals`) names Kravalg's user ID and the requester is someone else. A CODEOWNERS approval (`* @Kravalg @dmytrocraft`) does not satisfy this.</li></ul> After a successful abandon, registry capture (`scripts/poc_registry_plan.py`) accepts the registry baseline again. | USI | T | ST, L |
| FR-22 | A reviewed, governance-owned CI recovery command. CODEOWNERS `@Kravalg` covers the workflow and script in USI. It runs in the protected environment `test-recovery` (and `prod-recovery` for PROD, without `abandon`). Both environments have Kravalg as their sole required reviewer (AGENTS.md "sole environment reviewer Kravalg"). The executing identity is the BI recovery role `GitHubCiRecovery-user-service-infrastructure-{env}`, assumable only from that environment on `main`; S5.7 and S5.19 list its grants. Operations: stack export (private, hashed), lock release, pending-operation clear, imports of fixed-name or retained resources from an explicit import list, and TEST `abandon` (FR-21; D-7, decided 2026-09-30). Imports run as saved plans whose steps are only `import` or `same`, with URNs equal to the import list 1:1. It emits evidence: before and after state hashes, lock and pending listings, the import list, the saved-plan hash, run IDs and the approver. | USI + BI | T (P without abandon) | ST, IAM, L |
| FR-23 | Runtime guard (#57): the protected worker refuses workload `plan` and `up-plan` unless the installed `main` contract, not the PR head, admits the target environment (FR-31 admission field). | USI | T→P | L |
| FR-24 | Measured timing (N-04): record "OIDC issuance to result observation" and "job start to end" for each first-create step. Margin: 300 s. Gate 2 requires process time ≤ 3000 s (3300 − 300) and credential window ≤ 3300 s (3600 − 300) for every measured step; otherwise the BI `MaxSessionDuration` increase and `role-duration-seconds` (S5.6) must land first. | USI (+BI conditional) | T | IAM, L |

### E5 Cross-repo and cross-cutting

| ID | Requirement | Owner | Env | Risk |
| --- | --- | --- | --- | --- |
| FR-25 | The worker healthcheck matches the running supervisor config (user-service #501). The USI `worker_health_command` in the contract equals the published image's command. | US + USI | T→P | CON, L |
| FR-26 | The web and worker images run as non-root (UID ≥1000). USI drops all Linux capabilities for both containers and uses an unprivileged container port. | US + USI | T→P | L |
| FR-27 | BI N-11 grants: the apply-role workload capability, the central ECS roles, the app-rotation, redeploy and bootstrap-job roles, and the recovery and restore-rehearsal (operator and reader) grants are installed as reviewed IAM documents. `scripts/poc_workload_capabilities.py` proves the simulator matrix offline (every required action allowed, every denied action denied, condition keys present). A live `iam:SimulatePrincipalPolicy` run in S4.6 step 3 repeats it. Other live exercises (forced rotation, denied reads, alarm and scaling-alarm induction, flow-log and CloudTrail reads, log counts, optional load) use the TEST exercise role `GitHubCiExercise-user-service-infrastructure-test` in the `test-exercise` environment (S5.23, S4.16). The simulator run uses the `GitHubCiPreview-user-service-infrastructure-{env}` role, which S5.17 grants `iam:SimulatePrincipalPolicy` and `iam:GetContextKeysForPrincipalPolicy` on the exact role ARNs of the matrix only, plus `iam:SimulateCustomPolicy` (no resource scope exists for it; read-only) (m6). Key and secret resource policies are passed as `ResourcePolicy` inputs. | BI + USI | T→P | IAM, L |
| FR-28 | Front-door security per D-3 (decided 2026-09-30), outside the hard stop and required before any public exposure: a REST API regional endpoint with AWS WAF (managed common, known-bad-inputs and IP-reputation groups plus a rate rule), a private integration over **VPC link V2 directly to the internal ALB** (`integration_target` = ALB ARN; no NLB; V-10), a custom domain and a deploy pipeline. Live TEST evidence is S4.6 step 17; PROD public exposure requires it before gate 2. | AGI (+USI outputs) | T→P | L |
| FR-29 | The legacy managed path (`pulumi/app/stack.py` `UserServiceStack`, `compute.py::_create_runtime_secrets`, `data.py::_persist_url` fallback) fails closed for `test` and `prod`, or is removed. It currently writes config-supplied secret material, including the social-login client secrets, into `SecretVersion`s. Social-login secrets, if ever enabled, are written outside Pulumi by a governance secret-write path. That is future work, recorded here. | USI | T→P | ST, CON |
| FR-30 | Backup and rollback. **Restore:** a point-in-time restore of the TEST cluster (`RestoreDBClusterToPointInTime` with `UseLatestRestorableTime`, R6-m10) to a temporary cluster `<stack>-docdb-restore-rehearsal` under the BI restore-operator role (S5.18a). The cluster is switched to a managed primary password. A VPC-attached BI reader (bootstrap-job SG, attached in S5.18b after XP-8) records the restore time and a document-count sample. Then the temporary cluster is deleted. This is a PROD gate. **Recovery targets (user decision D-14, dated 2026-09-30; architecture AD-19; R6-m1):** DocumentDB RPO ≤ 1 hour inside the backup retention window, recorded as the restore request time minus the achieved recovery point of the point-in-time restore (the source `LatestRestorableTime` it used), and RTO ≤ 24 hours from the restore request to the reader's document-count sample; a measured value above a target is a STOP at gate 2a for a new user decision. Redis is rebuilt, not restored. **Rollback (m4):** (a) *first deployment*, before any accepted-workload receipt exists: there is no prior release, so rollback means stop serving. A create-only `rollback-zero` plan (FR-11) scales both services to 0, and the stack stays in place for `resume`, recovery or `abandon`. (b) *later releases*, after an accepted-workload receipt (FR-35): re-apply the prior accepted release (image digests, task-definition inputs, original registry anchor) as a saved plan. The ECS circuit breaker (AD-19) covers in-deploy failures in both cases. | USI + BI | T (gate for P) | IAM, L |
| FR-31 | Two-gate phase admission (D-6). **Gate 1 (TEST-only admission):** `poc-test.json` `phase: "workload"` with `admission: {"test": true, "prod": false}`, allowed only when all of these hold: (a) every story in the explicit gate-1 list (`epics-stories.md` S4.6 preconditions) is merged; (b) the BI prerequisites S5.1, S5.2, S5.17, S5.4, S5.3, S5.23, S5.7 and S5.18a are applied, and the USI repository controls S5.21 and S5.22 are applied; (c) the one-time metadata observation confirms R-02; (d) every decision applicable to gate 1 (D-1, D-2 TEST part, D-4, D-5, D-6, D-7) is **resolved**, as all are since 2026-09-30; (e) the existing runner prerequisites XP-9 … XP-13 (§7) hold. **Gate 2 (PROD admission), in two parts.** **2a:** `admission.prod: "preview"` admits only the PROD `plan`. It is allowed when every gate-1 check still passes, the TEST acceptance receipt (§3.3) is campaign-complete, the restore item (FR-30, S4.8, measured against D-14) is present, and XP-14, XP-15 and XP-16 hold (R8-m6). **2b:** `admission.prod: true`, allowed when every 2a condition holds and the receipt is complete and schema-valid. Gate 2b also requires **scheduled workload drift detection for the `prod` workload stack** (S4.17, R6-m11): merged, and two uploaded result records linked in the receipt, each with its run link, artifact ID and artifact sha256 (R8-M1): a clean scheduled TEST run with `status: checked` (R7-m1; a `before-acceptance` record never counts as the TEST item), and a PROD record with `status: before-acceptance` or `checked` from a scheduled run after the gate-2a PR that first set `poc-prod.json` `phase: workload` (R8-m1; the S4.17 jobs are data-driven, and a `registry-phase` record never counts); no risk acceptance replaces it. It must link live evidence for: step 1 and step 2 with their receipts (FR-34, FR-35), clean drift (FR-32), rollback, the resume, abandon and rebuild rehearsals, timing (FR-24), restore (FR-30), the FR-28 front door if PROD is publicly exposed, the P-1 PROD preview (FR-19), D-2 PROD (FR-19 HTTPS, S5.20 published) and D-3 resolved. **Stack → contract mapping (R6-m11):** stack `test` reads `specs/poc/poc-test.json`; stack `prod` reads a new `specs/poc/poc-prod.json`, validated by a separate PROD schema `schemas/poc-prod-v1.schema.json` that S4.14 owns (R7-m4; architecture AD-04), committed with XP-14 as `phase: registry` and moved to `phase: workload` only by the S4.7 PRs; `admission` lives only in `poc-test.json`, the single gate record for both stacks. The hard-stop test and the README change encode both gates. | USI | T, then P | ST, L |
| FR-32 | Drift allow-list (M-1). The contract carries a closed, per-resource-type list of fields allowed to change outside Pulumi (architecture AD-23). Every `ignore_changes` in the program must appear on that list and nothing else. "Clean drift" means the executed workload drift path (R5-M1, R6-M1, R6-m4: the new `self-deploy.yml` job `test_workload_drift` → worker → runner → `run_pulumi_command._dispatch_command("plan", …)`, that is the `plan` invocation `preview --json --refresh --save-plan` with a drift gate, as the registry runner handles drift) exits 0 **and** the FR-32 reducer in `scripts/poc_workload_reconciliation.py`, run by that gate, accepts every refresh-time state change against the checkpoint of the latest success receipt only on listed fields (V-13). The gate-2 clean-drift evidence comes from that job under the **preview** role (the same role step as the registry drift job, `self-deploy.yml` line 546; PROD: `prod_workload_drift`). The registry job `test_post_apply_drift` stays registry-only and unchanged. `scripts/run_pulumi_drift_check.py` is not executed by anything and carries no FR-32 logic. A drift whose refresh plans a replace or delete of a protected resource fails closed earlier, with the shared safe-preview message and no field named (audit F8). The baseline scheduled drift (`scheduled-drift.yml`, drift role, baseline program) excludes a workload-phase stack with the recorded reason `workload-drift-routed-to-runner`, per stack: `test` when `poc-test.json` has `phase: workload` (S4.13), `prod` only when `poc-prod.json` exists with `phase: workload` (S4.14; R7-m2). Scheduled workload drift for both workload stacks is S4.17 (R6-m11, R7-M2), launched in the isolated worker container with scheduled-main provenance and no PR request, and required before gate 2b; each run that exits 0 writes one uploaded result record (`checked`, `before-acceptance`, or `registry-phase` for a stack whose installed contract has `phase: registry`; R7-m1, R8-m1, R8-M1), and a run whose installed program differs from the applied base fails with its own reason (R8-m4). | USI | T→P | CON, L |
| FR-33 | Preview and drift read capability (B-2). BI grants the `GitHubCiPreview-user-service-infrastructure-{env}` and `GitHubCiDrift-user-service-infrastructure-{env}` roles read-only access (`Describe*`/`List*`/`Get*`, except secret values and function code) to every workload resource type: ec2 (VPC, subnets, SGs, endpoints, flow logs), ecs, docdb/rds describe, elasticache (including users and user groups), logs, cloudwatch, application-autoscaling (including scheduled actions), elbv2, wafv2, apigateway, events, sns, s3 (bucket configuration), and secretsmanager `DescribeSecret`/`GetResourcePolicy`/`ListSecretVersionIds` (S5.17). The kms `DescribeKey`/`GetKeyPolicy`/`GetKeyRotationStatus`/`ListResourceTags` read for both roles is granted in **S5.4** on the exact new key ARNs, through the key policies and identity statements, because the key ARNs exist only after S5.4 (m7). `GetSecretValue`, `lambda:GetFunction` and `kms:Decrypt` stay denied. The simulator matrix regression covers both roles. The scheduled workload drift (S4.17) also reads IAM, ECR, SSM and ACM for its capability, image and certificate checks, and the registry rows (ECR repositories, the SES identity and the Route53 DKIM records) for its refresh and capture checks; those reads, including `ecr:GetDownloadUrlForLayer`, with `iam:SimulatePrincipalPolicy` on the execution role only, come through the BI story S5.24 after XP-14, XP-15 and XP-16 and before S4.17, which also narrows the Drift role's explicit secret-read deny for the certificate parameter and the ECR token (R7-m9, R8-m3). | BI + USI | T→P | IAM, L |
| FR-34 | Two-step first-workload admission (M-12). The contract names the step (`workload_step: 1 \| 2`). **Step 1** creates the network, data, secret metadata and ECS services at 0 tasks, with no seed, rotation, secret policy, autoscaling target or scheduled action. **Step 2** is admitted only in a **create-only** mode. Every step in the saved plan is `create` or `same`. Its created URNs are exactly the step-2 set: seed Invocations, `SecretRotation`s, `SecretPolicy`s (including the DocumentDB-managed secret policy in state `deny-other-readers`), autoscaling targets and policies, the one-time start scheduled actions of the single unconsumed `scaling.starts` entry (`<svc>-start-1` on an on-time first build; a missed window moves that uncreated entry to `scaling.consumed` and appends the next `seq`) and, in TEST only, the night and weekend `ScheduledAction`s (FR-14c). There is no `update`, `replace` or `delete` of any step-1 URN. Step 2 also requires the authenticated step-1 result receipt (FR-35), the S5.5 evidence receipt and the XP-8 metadata in the installed `main` central metadata. After step 2, a health observation must show every service steady with running = desired ≥ 1 and healthy targets. | USI | T→P | ST, CON, L |
| FR-35 | Runner lifecycle (R4-B2). The installed path admits only a first TEST apply: the runner binds the checkpoint to the registry anchor (`scripts/poc_workload_runner.py` lines 44-47), calls only `admit_first_workload_plan` (line 61), is TEST-only (line 53) and refuses `drift` (line 154). Admission `inspect_registry` (`scripts/poc_workload_admission.py` lines 150-166) requires a registry-only checkpoint equal to the registry receipt. The worker (`scripts/service_execution_worker.py` lines 25-30, 90-94, 99) and `self-deploy.yml` are TEST-only and refuse workload drift. The C-runner chain changes this, in order: **(1)** authenticated **receipts after every admitted apply**, successful or failed (`poc-workload-step-receipt-v1`: checkpoint, run, attempt, mode, outcome, digests, secret metadata), plus a receipt from every recovery subcommand that writes the checkpoint: **export** (also written by `clear-pending`, with `cause: clear-pending` and a link to the prior receipt, R5-M2), **import** and **abandon**. The failure-path receipt (also written when the post-apply result inspection fails, R6-m9) is published by the `test_apply_receipt` job, because the worker fails the apply job on a non-zero status (`scripts/service_execution_worker.py` line 127). They are published through the same governance-evidence path as the registry proof. Admission and the runner bind each mode to its anchor by the mode → anchor table (architecture AD-24): `first` → registry receipt; `resume` → the latest failed or export receipt (so an interrupted step 1 is resumable, and so is a failed operation after `clear-pending`), finishing the operation that receipt names; `step2` → the latest step-1 success; `rollback-zero` and `policy-update` → the latest success after step 2; the recovery modes → the latest receipt or export. A stale receipt is refused. The release identity keeps the original registry anchor. **(2)** Mode routing from the reviewed contract field `workload_operation` (never a request flag), including `rebuild-first` after an abandon (anchor: the recovery import receipt that follows the abandon receipt). **(3)** An authenticated **accepted-workload receipt**, written by the first passing health observation after step 2. It opens `drift` in the runner and the worker. Releases also need a clean-drift result. The pinned README, runner-spec and log-health sentences and their tests change through a reviewed amendment. **(4)** A **PROD path**: worker jobs and account, `self-deploy.yml` PROD jobs, gate 2a (`plan` only) and gate 2b (apply), the PROD contract schema (R7-m4), the PROD certificate parameter, the PROD topology and the PROD registry anchor (XP-14). The post-acceptance route that opens the drift job comes from the authenticated receipt lineage, never from the contract bytes, so a `rollback-zero` or `policy-update` before the first accepted receipt runs no drift job (R7-m5). The existing binding negatives keep passing. | USI | T→P | ST, CON, L |

#### 3.3 TEST acceptance receipt (FR-31 gate 2, M-11)

`schemas/poc-test-acceptance-receipt-v1.schema.json` validates the receipt.
Each evidence item has:

- `item` (one of the gate-2 items), `stack`, `source_sha` (the `main` commit),
  `contract_digest`;
- `run_id` and `run_attempt` (numeric), and a run URL under
  `https://github.com/VilnaCRM-Org/<repo>/actions/runs/<run_id>`;
- `artifact_sha256` (64 hex) for every evidence artifact; the S4.17
  scheduled-drift items also carry the uploaded artifact's numeric
  `artifact_id` (R8-M1);
- `requester` and `approver`, which must differ;
- no secret-like values (the FR-20 redaction runs over the receipt).

The validator refuses placeholder links (`TBD`, `TODO`, `example`, `<…>`,
all-zero IDs or hashes) and any item without every field.

## 4. Non-functional requirements

| ID | Requirement | Measure | Kind |
| --- | --- | --- | --- |
| NFR-01 | No secret material in Pulumi state, program outputs, logs, CI output, PR comments or artifacts. | A static graph test (no `random:`, `tls:` or `SecretVersion` types), redaction tests, and a TEST state metadata scan after step 1 and after step 2 (S4.6 steps 4a and 7a). The scan reads the checkpoint through the trusted observer and records only type counts and a pass or fail result. | offline + live |
| NFR-02 | Governance: no `aws.iam.*`, OIDC trust or `aws.lambda.Function` in USI. OIDC-only credentials. Saved-plan apply only. No `AdministratorAccess`. | Policy pack and guardrail tests, plus new type-deny tests. | offline |
| NFR-03 | The quality floors (§2) are unchanged and green. | `make ci-pr`, `make test-coverage`. | offline |
| NFR-04 | TEST before PROD. Each live step is approved by Kravalg, with a requester different from the approver. | Workflow run evidence; receipt field check (§3.3). | evidence-only |
| NFR-05 | Credential changes cause no outage. **IAM paths (Redis IAM, DocumentDB IAM):** zero authentication failures. **Single-key rotations (`APP_SECRET`, `OAUTH_ENCRYPTION_KEY`):** impact stays within D-5. | **IAM paths:** during a 13 h soak that crosses the 12 h Redis connection limit and at least two task-credential refreshes, the app `auth_failure{backend=redis\|documentdb}` log metric and the ElastiCache `AuthenticationFailures` metric are both 0. **Single-key:** window W = `RotationSucceeded` time → ECS deployment `COMPLETED` + 5 min; in W the ALB 5xx alarm does not fire, and the counts of failed refresh-token and failed decrypt log events are recorded; the result passes if every failure is a forced re-login accepted by D-5. | evidence-only |
| NFR-06 | Least privilege. Every new grant is scoped to named ARNs, name patterns (`<name>-??????`), deterministic ARNs or exact XP-8 ARNs, with conditions. The BI seed and rotation functions act only on allow-listed secret ARNs. | Reviewed IAM document hashes plus the offline capability simulator, and a live `iam:SimulatePrincipalPolicy` run (S4.6 step 3). | offline + live |
| NFR-07 | Fail closed: a missing central role, CMK, decision or evidence, or a forbidden prior-checkpoint URN, gives BLOCKED admission. | Negative admission and capability tests. | offline |
| NFR-08 | An alarm reaches SNS within 5 min. | TEST alarm exercise: time from the induced condition to the SNS delivery record. | evidence-only |
| NFR-09 | An interrupted TEST apply is resumed, or abandoned (D-7, decided 2026-09-30; TEST only, Kravalg-approved manifest), through FR-22 within one working day, with complete evidence. Every recovery subcommand that writes the checkpoint (`clear-pending`, `import`, `abandon`) leaves a receipt bound to the new checkpoint, so the resume anchor never goes stale (R5-M2). | TEST rehearsals: resume after `release-lock` and `clear-pending` (S4.6 step 13) and abandon plus rebuild (S4.6 steps 19–20). | evidence-only |
| NFR-10 | Docs stay in sync (`specs/poc/README.md`, `secret-lifecycle.md`, `docs/poc-workload-recovery.md`, `security-baseline.md`, `sre-operations.md`, `poc-workload-admission.md`, `docs/ci-guardrails.md`; R8-m5). | Doc-marker tests. | offline |
| NFR-11 | Cost (m17): the TEST and PROD monthly estimates are recorded before and after. Every figure carries a data-source label: an AWS Pricing Calculator export or an AWS Price List API query for `eu-central-1` with its retrieval date, or Cost Explorer actuals with the billing period. Forecast threshold: an after-estimate more than 20% above its before-estimate needs a justification line naming the driver (endpoints, NAT, CloudTrail read events, CMK requests, flow-log storage, Container Insights); each PROD increase is justified. The threshold and the PROD justification rule are planning defaults, not user decisions (D-14 does not cover them); the user may change them. | Cost document (`docs/poc-cost-review.md`, S2.6) and its doc test. | evidence-only |

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
| FR-07 | The read deny has a `PrincipalArn` allow-list; the write deny names only the rotation role; the managed-secret policy renders the document of its `documentdb_secret_policy` state. | Missing, empty or wildcard allow-list fails. A write-deny allow-list containing the execution role fails. A `policy-update` plan with a `delete` of the managed-secret `SecretPolicy` or with a second step is refused. An unknown policy state fails the schema. | Apply role still denied; admin residual risk recorded. Each state transition (`deny-other-readers` → `allow-rotation` → `tls-only`) is exactly one `update` step. | `test_secret_policy.py`, `test_poc_workload_admission.py` | TEST denied read and denied `PutSecretValue` by a TEST exercise role (`denied-read`), plus the alarm fired (no value printed), and an `iam:SimulateCustomPolicy` run (preview role) with an identity allow for `GetSecretValue`/`PutSecretValue`, the exercise-role caller ARN and the live `SecretPolicy` as `ResourcePolicy`, which shows the resource policy alone denies; V-3 check with the policy present (S4.6 step 8). |
| FR-08 | `valueFrom` is the ARN or `arn:key::`. | A version suffix fails. | The lockout URL equals the Redis URL. | `test_runtime_secrets.py`, `test_poc_secret_observation.py` | TEST task definition has no version IDs. |
| FR-09 | No Random, TLS or `SecretVersion` types; seed input is `{secret_arn, purpose}`. | A generator or `SecretVersion` fails. A prior checkpoint with a forbidden URN is refused. | Seed input with any extra key is rejected. | runtime and topology/admission tests | TEST state metadata scan. |
| FR-10 | Key ARNs match the D-4 metadata: secrets and log groups on the runtime CMK; the flow-log bucket SSE-KMS on the runtime CMK; the JWT and 2FA keys separate. | Unknown key or wrong alias fails. A workload log group without `kms_key_id` fails. A `master_user_secret_kms_key_id` on DocumentDB fails (the AWS key stays). | A-05 exception recorded. | `test_poc_contract.py`, `test_observability.py`, `test_flow_logs.py` | TEST `DescribeSecret` `KmsKeyId`; `DescribeLogGroups` `kmsKeyId`; flow-log object `SSEKMSKeyId`. |
| FR-11 | Target and policies match; step 2 creates the start action of the single unconsumed `scaling.starts` entry (`<svc>-start-1` on an on-time first build) with `min = max(contract min, 1)`. | min > max, or PROD min < 1, raises; missing `ignore_changes` fails. A `rollback-zero` plan that updates the service, deletes anything, or updates the target in any field other than `suspendedState` is refused. A new entry's `at()` time before the replay admission time + 10 min (`rollback-zero`) or + 60 min (`step2`), or after + 120 min, is refused. A plan that changes an earlier action's inputs is refused. A stop plan that also suspends scheduled scaling is refused. A hold plan without the authenticated stop observation is refused, and so is any change of `scaling.scheduled_scaling_suspended` outside a hold or start plan. | TEST 0 only via schedule or `rollback-zero`. A start action at exactly `min = 1` is admitted. Appending a new `scaling.stops` entry renders exactly one new URN and leaves every earlier action's inputs unchanged. A `policy-update` during a hold renders every target `same`. | `test_autoscaling.py`, `test_poc_workload_admission.py` | TEST start observed (V-23, S4.6 step 7); web scale-out by the target-tracking alarm exercise (`SetAlarmState`, step 12); stop, hold and restart (step 15, V-23 d); a load test through the front door only if S5.16 exists (step 17). |
| FR-12 | Metric math over three queues. | A DLQ in the math fails. | Zero tasks does not divide by zero. | `test_autoscaling.py` | TEST backlog scale-out. |
| FR-13 | Topic with KMS; every alarm actions to the topic; runbook entry exists. | Topic policy without `SourceAccount` fails. Fixtures: an execution-role session read does not match; a non-allow-listed assumed-role read matches; an `AWSService` event invoked by an unlisted service matches; a denied (`AccessDenied`) read matches. | Name, full-ARN and partial-ARN `secretId` fixtures all match. Missing-data mode per alarm. | `test_observability.py`, doc test | TEST alarm exercise. |
| FR-14 | TEST night and weekend schedule; ARM64 when multi-arch. | A PROD night or weekend scale-to-0 schedule fails. | Weekend edges. | `test_autoscaling.py`, cost doc test | TEST scheduled scale-down observed: the night action sets desired to 0 and the morning action restores min (S4.6 step 12); the cost document records the before and after estimate. |
| FR-15 | Flow log ALL to S3; bucket controls, SSE-KMS with the runtime CMK, delivery policy. | IAM role argument present fails. Non-TLS-only bucket fails. A delivery statement without `aws:SourceArn` fails. SSE-S3, or SSE-KMS without the delivery principal in the runtime key policy, fails. `force_destroy=true` fails. | Lifecycle 30 d TEST / 90 d PROD. | `test_flow_logs.py` | TEST object delivered with the runtime CMK (V-16). |
| FR-16 | Default SG has no rules. | Any rule fails. | Adoption and destroy semantics documented. | `test_network.py` | TEST describe shows no rules. |
| FR-17 | Endpoint set, DNS, SG; each policy equals its pinned document. | Missing endpoint fails. An extra action, extra statement or missing account condition fails the equality test and the pack. A pin whose hash does not match fails. In the `secretsmanager` policy, a `rds!cluster-*` statement without the `aws:PrincipalArn` limit fails, and the evaluator denies the execution role on `rds!cluster-*`. | TEST single-AZ only with a cost record. Region placeholder renders per environment. The bootstrap-job and restore-reader roles are allowed on `rds!cluster-*`. | `test_network.py`, `test_endpoint_policies.py`, policy tests | TEST image pull via endpoints (V-14); bootstrap job reads the managed secret through the endpoint (S4.6 step 6). |
| FR-18 | SG rule sets equal the expected sets, including the bootstrap-job SG. | `-1` egress to `0.0.0.0/0` fails. A `0.0.0.0/0` 443 rule without the V-12 fallback record fails. | DNS unaffected. | `test_network.py` | TEST flow logs show no rejected required flows. |
| FR-19 | TEST: doc markers present. PROD: HTTPS target group and health check. | A PROD HTTP target group is refused. | TEST doc test passes with an HTTP target group. | `test_compute.py`, doc test, PROD topology test (S4.10) | TEST healthy targets; P-1 PROD preview under gate 2a (S4.7). |
| FR-20 | Summary has the allow-listed fields. | Secret-like values dropped; `private.log` never uploaded. | Truncation marker. | `test_service_execution_worker.py` | TEST induced failure. |
| FR-21 | Resume admits create or update subsets. Abandon admits a removal plan whose `delete` URNs, of every type, equal the manifest 1:1. | Protected replace or delete refused. Abandon without manifest, snapshot decision or secret decisions refused. An abandon plan with one extra or one missing `delete` (of any type, for example an `aws:ecs/service:Service` that the critical-type classifier ignores), or with any op other than `delete` and `same`, is refused. `delete` on a log bucket or bucket sub-resource refused. `force-delete` refused. A run approved by anyone other than Kravalg is refused. | `recovery_window_days` 7 and 30 accepted; 6 and 31 refused. Post-abandon registry capture accepts the baseline. A `retain` entry appears as a `delete` step after its unprotect plan set `retain_on_delete` (V-24). | admission, topology, `test_poc_registry_plan.py`, `test_poc_workload_recovery.py` | TEST resume rehearsal (S4.6 step 13); abandon plus rebuild rehearsal (steps 19–20). |
| FR-22 | Protected environment, main only, sole reviewer Kravalg, recovery role; import as saved plan. | PR head, non-protected environment, import mismatch or an import plan with a non-import step refused. `abandon` in `prod-recovery` refused. An environment whose reviewers are not exactly [Kravalg], or which allows self-review or admin bypass, fails the BI check. | Idempotent lock release. | workflow and script tests; BI environment tests | TEST rehearsal. |
| FR-23 | Main admits the environment ⇒ allowed. | PR head admits but main does not ⇒ refused. | Missing contract ⇒ refused. | `test_poc_workload_runner.py` | TEST refusal observed. |
| FR-24 | Measured times within the margin bounds. | 3001 s process time blocks gate 2. | Exactly 3000 s process and 3300 s window pass. | `test_apply_timeout_budget.py` | TEST timing evidence. |
| FR-25 | Contract command equals the image command. | Mismatch refused. | Healthcheck grace period. | `test_poc_contract.py` | TEST worker healthy. |
| FR-26 | Capabilities drop `ALL`; unprivileged port. | An add-back fails. | Health-check port follows. | `test_compute.py`; US image test | TEST tasks healthy, `User` non-root. |
| FR-27 | Simulator: required actions allowed. | `GetSecretValue`, `GetFunction` and out-of-scope actions denied. | Conditions present. | BI tests; `test_poc_workload_capabilities.py` | TEST live simulator run. |
| FR-28 | REST stage has WAF; route reaches the service through VPC link V2 → ALB. | Direct ALB access from outside the VPC fails. An integration with an NLB target without a recorded V-10 fallback fails the AGI test. | VPC link 60-day inactivity documented. | AGI tests | TEST route and WAF sampled requests (S4.6 step 17). |
| FR-29 | Managed test/prod without `RuntimeSecrets` raises. | Any `SecretVersion` in the graph fails. | Dev/preview mode unaffected. | `test_stack.py` | — |
| FR-30 | Restore runbook and rollback procedure exist; first-deployment rollback is `rollback-zero`. | Rollback to an unaccepted release refused. A release rollback before an accepted-workload receipt exists is refused. A restore target name other than `<stack>-docdb-restore-rehearsal` refused. | The restore target is deleted after the check. | doc and admission tests | TEST restore (S4.8) and rollback evidence (S4.6 step 15). |
| FR-31 | Gate 1 admits TEST only; gate 2a admits the PROD `plan`; gate 2b admits the PROD apply. | Gate 1 with a missing listed story, a missing XP-9 … XP-13 prerequisite or an unresolved decision (a default is not a resolution) is refused. PROD with `admission.prod` false is refused; a PROD apply under `"preview"` is refused. A receipt with a placeholder link is refused. | Gate 2a without XP-14, XP-15, XP-16 or the restore item is refused; gate 2b with any gate-1 check failing, or any live item missing (including P-1 and the two S4.17 scheduled-drift items, R6-m11, R8-m1), or with only a `registry-phase` PROD record, is refused. | `test_workload_phase_hard_stop.py`, `test_poc_acceptance_receipt.py` (S4.15), runner tests | TEST acceptance receipt. |
| FR-32 | Program `ignore_changes` equals the allow-list. | An `ignore_changes` field not on the list fails. A refresh-time change on an unlisted field fails the drift reducer. | ECS `desiredCount` change by autoscaling gives a clean drift result. | `test_drift_allow_list.py` (S1.11); `tests/unit/test_poc_workload_reconciliation.py` (`validate_drift`) and `tests/unit/test_poc_workload_runner.py` (the drift plan-plus-gate dispatch) (S4.13); `tests/unit/test_poc_scheduled_workload_drift.py` (S4.17) | TEST clean drift after scaling, from `test_workload_drift` under the preview role (S4.6 step 14); a clean scheduled TEST run (S4.17) before gate 2b. |
| FR-33 | Simulator: every workload read allowed for both roles. | `GetSecretValue`, `GetFunction`, `kms:Decrypt` and any write denied. | Condition-less `Describe*` on types whose API has no resource ARN is recorded. | BI tests; `test_poc_workload_capabilities.py` | TEST live simulator run; a TEST preview completes. |
| FR-34 | Step 1 and step 2 URN sets; step 2 admitted in create-only mode. | A step-2 plan with any update, replace or delete of a step-1 URN is refused. Step 2 without the step-1 receipt, S5.5 evidence or XP-8 metadata is refused. A step-2 plan missing a TEST `ScheduledAction` is refused. | An empty step-2 plan (all `same`) is admitted and changes nothing. | `test_poc_workload_admission.py`, topology tests | TEST step 1, step 2 and the step-2 health observation. |
| FR-35 | Receipts are issued after every admitted apply (success and failure); each mode is admitted only with its anchor from the AD-24 table; the accepted-workload receipt opens `drift`. | `step2` without a step-1 success receipt, `resume` without a failed or export receipt, or `drift` without an accepted receipt is refused (`workload-accepted-state-receipt-required` in the runner, `workload-drift-not-enabled` in the worker). A receipt with a changed checkpoint sha256, run ID or contract digest, or a stale receipt, is refused. An unknown mode, or a mode not named by `workload_operation`, is refused. The existing negatives keep passing (`workload-checkpoint-binding` for `first`, `workload-completed-registry-required`, `workload-registry-checkpoint-changed`, `workload-stack`, `workload-first-command`, `workload-request-binding`, `workload-source-binding`, `workload-certificate-parameter-required`). A PROD run with `admission.prod` false is refused; a PROD apply with `"preview"` is refused. | A step 1 interrupted before any receipt is resumable from the recovery export receipt. A failed receipt followed by `clear-pending`, which writes an export receipt (`cause: clear-pending`) linked to the failed one, admits `resume`; a `clear-pending` without that receipt leaves every receipt stale and `resume` is refused (R5-M2). `drift` with an accepted receipt but no clean-drift result admits drift and refuses a release. | `test_poc_workload_runner.py`, `test_poc_workload_admission.py`, `test_poc_workload_receipts.py`, `test_poc_workload_recovery.py`, `test_service_execution_worker.py`, `test_workload_apply_docs_consistency.py` | TEST step-1 receipt (S4.6 step 4), step 2 admitted with it (step 7), accepted receipt and drift (steps 7b and 14), resume from the export and clear-pending receipts after a cancelled run (step 13), rebuild (step 20). |

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
| NFR-09 | Resume succeeds, including after `clear-pending`; abandon plus rebuild succeeds. | Abandon without a Kravalg-approved manifest refused. `resume` after a `clear-pending` that wrote no receipt refused. | Lock already released. | Rehearsal |
| NFR-10 | Markers present. | Stale marker fails. | A marker present in one doc but missing in its pair fails. | Doc tests |
| NFR-11 | Estimates recorded with data-source labels. | A figure without a source label, or an increase above 20% (or any PROD increase) without a justification line, fails the doc test. | An increase of exactly 20% needs no justification; 20.1% does. TEST vs PROD split. | Cost document |

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
| D-4 | CMK scope | AWS-managed; one runtime CMK per environment plus JWT and 2FA CMKs; per-purpose CMKs | **RESOLVED 2026-09-30 by the user (clarified the same day):** one runtime CMK per environment encrypts the USI-declared secrets, every workload CloudWatch log group (ECS, DocumentDB audit and profiler, BI function log groups, others this plan adds) and the VPC flow-log S3 bucket (SSE-KMS). The key policy allows `logs.<region>.amazonaws.com` with a `kms:EncryptionContext:aws:logs:arn` condition, and `delivery.logs.amazonaws.com`. JWT-signing and 2FA CMKs are separate. The DocumentDB-managed master secret stays on the AWS-managed key (A-05). Derived, not a new decision: the SNS alarm topic uses the runtime CMK (`decisions.md`). | S1.9, S3.1, S2.3, S5.4, gate 1 |
| D-5 | App-secret rotation cadence and accepted impact | 30, 90 or 180 days; optional US previous-key tolerance (S5.15) | **RESOLVED 2026-09-30 by the user (clarified the same day):** `APP_SECRET` and `OAUTH_ENCRYPTION_KEY` rotate every 90 days, and forced re-login at rotation is accepted. `OAUTH_PASSPHRASE` is **not** rotated: the KMS JWT move (S1.8) retires it. The DocumentDB master password keeps the AWS-managed 7-day rotation. S5.15 is dropped. | S1.6, S1.8, gate 1 |
| D-6 | Amend the hard stop into two gates (FR-31) | Two-gate admission, or keep the single gate | **APPROVED 2026-09-30 by the user: two gates.** Governance still requires `@Kravalg` approval of the source PR that amends `specs/poc/README.md` and its test (S4.6 step 1). What D-6 relaxes is listed in §6.1. | S4.6, S4.7 |
| D-7 | Abandon authority | (a) governance recovery command with a reviewed manifest, TEST only, which amends AGENTS.md rule 14 as in architecture AD-16; (b) no abandon | **RESOLVED 2026-09-30 by the user: (a).** @Kravalg approves a reviewed recovery manifest, and a saved-plan destroy removes exactly the listed resources, in TEST only. PROD is never abandoned automatically. The abandon scope of FR-21, FR-22, S4.2, S4.3 and S5.7, the AGENTS.md rule-14a amendment and the runbook section are unconditional. Kravalg-specific approval is enforced by environment protection and the in-run approver check (FR-21), not by CODEOWNERS alone. | S4.2, S4.3, S5.7, S5.21, gate 1 |
| D-14 | Recovery targets (FR-30) | RPO and RTO values for DocumentDB | **RESOLVED 2026-09-30 by the user: RPO ≤ 1 hour, RTO ≤ 24 hours** for TEST and PROD (replacing the proposed RPO ≤ 5 min / RTO ≤ 4 h). S4.8 measures against them; a miss is a STOP at gate 2a for a new user decision. The 20% TEST cost threshold and the PROD justification rule (NFR-11) are not covered: they stay planning defaults. | S4.8, S4.15, gate 2a |

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
  bootstrap-job functions and roles, the restore-rehearsal identities, the
  recovery and TEST exercise roles and CloudTrail read events. (The
  Kravalg-only environments and the manifest-approval ruleset check are USI
  repository controls, S5.21 and S5.22, applied by a repository admin.)
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
  (`rds!cluster-…`). These BI items depend on it, and only these (m8):
  1. the bootstrap-job role's `secretsmanager:GetSecretValue` on that exact ARN
     (plus the `secretsmanager:ResourceTag` cluster condition if V-19
     confirms the tag; S5.5);
  2. the bootstrap-job Lambda's VPC attachment to those subnets and that SG
     (S5.5);
  3. the restore-reader Lambda's VPC attachment to the same subnets and SG
     (S5.18b).

  The XP-8 values also reach the USI installed `main` contract through a
  reviewed USI contract PR (S4.6 step 5b), which step-2 admission reads.
  The `secretsmanager` endpoint policy does **not** depend on XP-8. It uses
  the deterministic `secret:rds!cluster-*` statement (FR-17). After an abandon
  and rebuild, a new cluster has a new managed-secret ARN, and XP-8 item 1
  repeats (S4.6 step 20).

The existing runner already requires the prerequisites below
(`specs/poc-workload-runner.md` lines 110-113; `specs/poc/README.md` lines
107-128; `scripts/poc_workload_runner.py` lines 170-176). Gate 1 checks each
one (FR-31 e):

- **XP-9.** A completed, authenticated registry proof and receipt: the
  trusted registry observer, the TEST-only proof publication and the
  authenticated deployment chain that builds `RegistryReleaseBinding`
  (README items 1–3).
- **XP-10.** The gateway-owned, issued ACM certificate, published in SSM as
  `/vilnacrm/test/user-service/gateway-certificate-arn` (String, positive
  version, same-account regional ACM ARN). The runner refuses without it
  (`workload-certificate-parameter-required`).
- **XP-11.** The bootstrap #219 grants: installed central runtime and
  deployment IAM, and the exact SSM read grant.
- **XP-12.** Authenticated immutable image publication: the application
  manifest and both ECR images (`sha-` tags, multi-arch per S5.14),
  authenticated by the runner.
- **XP-13.** Verified SES prerequisites: the sending identity and its
  verification, and the account's sending status, recorded as metadata.

Gate 2 also needs prerequisites that this plan does not build:

- **XP-14.** A completed, authenticated **PROD registry** phase: the PROD
  registry apply, observation, proof and receipt that anchor the PROD
  workload. The registry runner is TEST-only today
  (`scripts/poc_registry_plan.py` line 21 pins the TEST account). This is
  registry-phase work outside this plan. Gate 2a and the S4.14 PROD path
  refuse PROD without it. XP-14 also owns the PROD coordinates of the
  trusted backend observer (`scripts/poc_backend_observer.py`: constants
  lines 37-43, the environment check at line 183, the URN prefix at line
  363 and the stack name at line 389; and the schema read at lines
  199-201, R7-m3), which the PROD registry capture and the S4.14 and S4.17
  PROD workload paths all use, the TEST registry constants of
  `scripts/poc_registry_plan.py` (lines 21, 26-27, 36, 60-65 and 69-71; R7-m3;
  any XP-14 change to that file is outside this plan and outside the
  R6-m13 rule that limits this plan's changes to S4.3), and the committed
  `specs/poc/poc-prod.json`, which must validate against the S4.14 PROD
  schema (R6-m5, R6-m11, R7-m4). From the revision-8 grep inventory
  (R8-m2; `epics-stories.md` S4.14 first case) it also owns the
  observer's `_caller` session names and assumed-role ARN (lines
  213-228), `_key` alias (line 325) and `LOCKS` prefix (line 43); the
  PROD registry names of `scripts/poc_registry_phase_entrypoint.py`
  `_REGISTRIES` (lines 13-22); the PROD registry completion
  (`scripts/poc_registry_completion.py`); the PROD SES domain, zone and
  identity (`scripts/poc_mail_prerequisite.py` lines 13-15), including
  the `prod` entry of the `_mail_semantics` domain map that S4.14 leaves
  absent (fail closed); and the PROD counterpart of the TEST image
  publisher environment (`scripts/poc_publisher_dispatch.py` line 89).
- **XP-15. PROD counterpart of XP-10 (R7-m3, R8-m6).** The PROD gateway
  certificate SSM parameter, owned by the gateway owner as XP-10.
- **XP-16. PROD counterpart of XP-11 (R7-m3, R8-m6).** The PROD
  permissions-boundary path that `scripts/poc_workload_capabilities.py`
  line 111 pins for TEST, owned by the bootstrap owner as XP-11.
- **Assumption for XP-15 and XP-16, not a decision (R8-m6).** S4.14 pins
  the deterministic, TEST-analogous names
  `/vilnacrm/prod/user-service/gateway-certificate-arn` and
  `arn:aws:iam::933245420672:policy/issue219/prod/boundary/` in its PROD
  fixtures. Each owner confirms the name in the S4.14 PR before it
  merges; that naming statement is recorded in S4.14 and is not the XP
  deliverable. XP-15 and XP-16 are the parameter and the boundary path
  existing live under those names, gate-2a prerequisites (ordered row
  49); S4.7 verifies both live, and gate 2a and the S4.7 preconditions
  refuse PROD without them.
