---
artifact: prd
workflow: _bmad/core/tasks/bmad-create-prd (non-interactive; steps-c 01..12 resolved from task intent)
task: workload-wa-hardening
source_baseline: 66776772979956de9c5abdbee7c45641a1b533fa
date: 2026-09-30
revision: 2 (readiness iteration 1 findings 1-14 addressed)
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

It adds five Well-Architected items outside the hard stop:

- the front-door WAF;
- retirement of the legacy secret path;
- a restore rehearsal;
- a rollback definition;
- the PROD gate.

Each requirement names:

- its owning repository: USI (this repository), BI (bootstrap-infrastructure),
  US (user-service) or AGI (api-gateway-infrastructure);
- its environment (TEST first, then PROD);
- its IAM and state risk;
- its evidence.

**Automation denominator:** 31 FRs and 11 NFRs, 42 requirements in total.

| Category | Count | Requirements |
| --- | --- | --- |
| Offline-testable requirements (unit, integration, policy or doc-marker test proves source behaviour) | 37/42 | All 31 FRs, plus NFR-01, -02, -03, -06, -07 and -10 |
| Evidence-only NFRs (no offline test can prove them; a live measurement or document is the evidence) | 5 | NFR-04, -05, -08, -09, -11 |
| FRs that also require live TEST evidence (Risk column contains L) | 25 | FR-01, 02, 03, 04, 05, 06, 07, 11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 24, 25, 26, 27, 28, 30, 31 |

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

  A label, profile flag or passing test never authorizes.
- **Failure states:**
  - **BLOCKED:** a prerequisite, user decision or reviewer is missing.
  - **FAILED:** an acceptance case fails.
  - A failed live TEST step stops and escalates through the E4 recovery
    command. Before E4 lands, it is stop-and-escalate per
    `docs/poc-workload-recovery.md`.
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
| FR-01 | DocumentDB generates, stores and rotates the primary password in Secrets Manager (`manage_master_user_password=True`). The Pulumi program and state hold no primary password. The app never receives primary credentials. | USI | T→P | ST, CON, L |
| FR-02 | The app authenticates to the DocumentDB 5.0 instance-based cluster with `MONGODB-AWS`, using the ECS task role. `MONGODB_URL` is a non-secret environment value (`authSource=%24external&authMechanism=MONGODB-AWS`, TLS, CA path) with no userinfo. A reviewed, governance-run one-time job creates the `$external` user for the task-role ARN, with `readWrite` on the app database only. | USI + BI + US | T→P | IAM, CON, L |
| FR-03 | SQS and SES are accessed through the task role only. No DSN, env var or secret contains an access key (AD-20). | USI (+BI grants) | T→P | IAM, L |
| FR-04 | Redis authentication follows D-1. **Default:** an RBAC user whose password lives in a Secrets Manager JSON secret, rotated by a reviewed, VPC-attached Lambda with dual-password overlap; `REDIS_URL` and `REDIS_LOCKOUT_URL` resolve from the JSON key `url`; no replication-group `auth_token`. **Alternative:** IAM auth, with `elasticache:Connect` and a user-service token provider. | USI + BI (+US) | T→P | IAM, CON, L |
| FR-05 | A reviewed rotation Lambda rotates `APP_SECRET` and `OAUTH_ENCRYPTION_KEY` on the D-5 schedule. A `RotationSucceeded` event triggers an ECS force-new-deployment of web and worker. (`OAUTH_PASSPHRASE` is `non_rotatable` and is removed by FR-06, not rotated.) | BI + USI | T→P | IAM, L |
| FR-06 | JWT and OAuth signing uses a KMS asymmetric key (RSA, RS256, `kms:Sign`/`GetPublicKey`). 2FA TOTP secret encryption uses KMS `Encrypt`/`Decrypt` with encryption context. The `oauth_private_key`, `oauth_public_key`, `oauth_passphrase` and `two_factor_encryption_key` secret purposes are removed. | US + USI + BI | T→P | IAM, CON, L |
| FR-07 | Every runtime secret has a resource policy. The policy denies `secretsmanager:GetSecretValue` unless `aws:PrincipalArn` is the ECS execution role or that secret's rotation-function role. The DocumentDB-managed secret allows the bootstrap-job role only if V-3 confirms compatibility. `BlockPublicPolicy` is on. The residual risk that admins can replace the policy is recorded; detection is FR-13. | USI (+BI role ARNs) | T→P | IAM, L |
| FR-08 | ECS secret references are the bare secret ARN (AWSCURRENT) or `arn:<json-key>::`, never a version ID. Validators record the observed AWSCURRENT version as evidence only. | USI | T→P | CON |
| FR-09 | Pulumi neither generates nor stores secret material. Specifically: no `pulumi_random` or `pulumi_tls` resource, and **no `aws.secretsmanager.SecretVersion` resource in USI at all**, because the apply and drift roles cannot `GetSecretValue`. Initial values come from a synchronous rotation seed, whose non-secret metadata (e.g. Redis `username`, `user_arn`, host, port, access string) is passed as seed input. The Random and TLS runtime pins are removed. A prior checkpoint containing `random:`, `tls:` or `SecretVersion` URNs fails admission closed. | USI | T→P | ST, CON |
| FR-10 | CMK scope follows D-4. Every `kms_key_arn` and key grant resolves from reviewed central metadata. | BI + USI | T→P | IAM, CON |

### E2 Operations (F-03, F-04, F-15)

| ID | Requirement | Owner | Env | Risk |
| --- | --- | --- | --- | --- |
| FR-11 | The web service autoscales with target tracking on `ALBRequestCountPerTarget` and `ECSServiceAverageCPUUtilization`, within per-environment min and max. Pulumi ignores `desiredCount`. | USI (+BI) | T→P | IAM, L |
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
| Rotation failure | EventBridge `RotationFailed` or `RotationAbandoned` on the workload secrets | any |
| Unauthorized secret read | EventBridge `GetSecretValue` on the workload secret ARNs where `userIdentity.sessionContext.sessionIssuer.arn` is `anything-but` the allow-listed role ARNs, or `userIdentity.type` ≠ `AssumedRole` | any |
| Secret policy change | EventBridge `PutResourcePolicy`, `DeleteResourcePolicy` or `DeleteSecret` on the workload secrets | any |
| DocumentDB IAM auth pressure | `StsGetCallerIdentityCalls` | informational |

### E3 Network and TLS (F-08, F-09)

| ID | Requirement | Owner | Env | Risk |
| --- | --- | --- | --- | --- |
| FR-15 | VPC flow logs (`traffic_type=ALL`) go to a dedicated, service-owned S3 bucket. Bucket controls: SSE per D-4; TLS-only; public access blocked; lifecycle 30 d in TEST and 90 d in PROD; `delivery.logs.amazonaws.com` allowed with `aws:SourceAccount` and `aws:SourceArn`. No IAM role is used. | USI (+BI `logs:CreateLogDelivery`) | T→P | IAM, L |
| FR-16 | The VPC default security group is managed and has zero ingress and zero egress rules. | USI | T→P | L |
| FR-17 | The VPC has an S3 gateway endpoint and interface endpoints for `ecr.api`, `ecr.dkr`, `logs`, `secretsmanager`, `sqs`, `kms` and `sts`, with private DNS on. The endpoint SG accepts 443 only from the service, bootstrap-job and rotation-function SGs. Endpoint policies are restricted to the account. | USI | T→P | L |
| FR-18 | Egress is tightened: <ul><li>**Service SG:** 443 to `0.0.0.0/0` (SES API, STS fallback) and to the endpoint SG; the DocumentDB port to the DocumentDB SG; the Redis port to the Redis SG; no all-protocol rule.</li><li>**ALB SG:** only the container port to the service SG.</li><li>**DocumentDB and Redis SGs:** no egress. The DocumentDB SG allows ingress from the bootstrap-job SG; the Redis SG allows ingress from the rotation-function SG.</li><li>**Bootstrap-job SG:** the DocumentDB port and endpoint 443 only.</li><li>**Rotation-function SG:** the Redis port and endpoint 443 only.</li></ul> | USI | T→P | L |
| FR-19 | ALB→task TLS follows D-2. **Default (B):** a recorded acceptance citing A-14, checked by a test. **Option (A):** an HTTPS target group and health check on 8443 with in-container TLS. | USI (+US) | T→P | L |

### E4 Recovery and guard (N-06, #57, N-04)

| ID | Requirement | Owner | Env | Risk |
| --- | --- | --- | --- | --- |
| FR-20 | Sanitized operator diagnostics: the job summary shows the failing URN, resource type, operation and the AWS error code and message, from an allow-list of fields. Everything else, including secret-like values, is dropped. `private.log` stays private. | USI | T | — |
| FR-21 | A non-registry TEST checkpoint admission path. <ul><li>**`resume`** admits only create or update of unfinished resources and rejects replace or delete of protected URNs.</li><li>**`abandon`** (TEST only) runs through the governance recovery command (FR-22), not the normal apply route. It requires a reviewed `abandon-manifest.json` naming each unprotect, the DocumentDB deletion-protection change, the final-snapshot decision with a collision check (`<stack>-docdb-final`), and a `data_loss_decision`. It requires D-7 authority.</li></ul> After a successful abandon, registry capture (`scripts/poc_registry_plan.py`) accepts the registry baseline again. | USI | T | ST, L |
| FR-22 | A reviewed, governance-owned CI recovery command. CODEOWNERS `@Kravalg` covers the workflow and script in USI. It runs in the protected environment `test-recovery`. Operations: stack export (private, hashed), lock release, pending-operation clear, imports of fixed-name resources from an explicit import list, and TEST abandon (FR-21). It emits evidence: before and after state hashes, lock and pending listings, the import list, run IDs and the approver. | USI + BI | T | ST, IAM, L |
| FR-23 | Runtime guard (#57): the protected worker refuses workload `plan` and `up-plan` unless the installed `main` contract, not the PR head, admits the target environment (FR-31 admission field). | USI | T→P | — |
| FR-24 | Measured timing (N-04): record "OIDC issuance to result observation" and "job start to end" for each first-create step. If the process time is ≥3300 s or the credential window is ≥3600 s, the BI `MaxSessionDuration` increase and `role-duration-seconds` must land before gate 2 (FR-31). | USI (+BI conditional) | T | IAM, L |

### E5 Cross-repo and cross-cutting

| ID | Requirement | Owner | Env | Risk |
| --- | --- | --- | --- | --- |
| FR-25 | The worker healthcheck matches the running supervisor config (user-service #501). The USI `worker_health_command` in the contract equals the published image's command. | US + USI | T→P | CON, L |
| FR-26 | The web and worker images run as non-root (UID ≥1000). USI drops all Linux capabilities for both containers and uses an unprivileged container port. | US + USI | T→P | L |
| FR-27 | BI N-11 grants: the apply-role workload capability, the central ECS roles, the rotation, redeploy and bootstrap-job roles and the recovery grants are installed as reviewed IAM documents. `scripts/poc_workload_capabilities.py` proves the simulator matrix (every required action allowed, every denied action denied, condition keys present). | BI + USI | T→P | IAM, L |
| FR-28 | Front-door security per D-3, outside the hard stop and required before any public exposure. **Default:** a REST API regional endpoint with AWS WAF (managed common, known-bad-inputs and IP-reputation groups plus a rate rule), a VPC link V2 to the internal ALB, a custom domain and a deploy pipeline. | AGI (+USI outputs) | T→P | L |
| FR-29 | The legacy managed path (`pulumi/app/stack.py` `UserServiceStack`, `compute.py::_create_runtime_secrets`, `data.py::_persist_url` fallback) fails closed for `test` and `prod`, or is removed. It currently writes config-supplied secret material, including the social-login client secrets, into `SecretVersion`s. Social-login secrets, if ever enabled, are written outside Pulumi by a governance secret-write path. That is future work, recorded here. | USI | T→P | ST, CON |
| FR-30 | Backup and rollback. **Restore:** a TEST DocumentDB snapshot is restored to a temporary cluster with evidence (restore time, document count sample), then the temporary cluster is deleted; this is a PROD gate. **Rollback:** re-apply the prior accepted release (image digests, task-definition inputs, registry anchor) as a saved plan, plus the ECS circuit breaker (AD-19). | USI | T (gate for P) | L |
| FR-31 | Two-gate phase admission (D-6). **Gate 1 (TEST-only admission):** `poc-test.json` `phase: "workload"` with `admission: {"test": true, "prod": false}`, allowed only after every offline story and the BI prerequisites land, the one-time metadata observation confirms R-02, and D-1..D-5 are resolved. **Gate 2 (PROD admission):** `admission.prod: true`, allowed only after live TEST evidence for the first apply (AD-18 two-step), clean drift, rollback, recovery rehearsal, timing and restore, and after D-2 is resolved for PROD. The hard-stop test and the README change to encode both gates. | USI | T, then P | ST, L |

## 4. Non-functional requirements

| ID | Requirement | Measure | Kind |
| --- | --- | --- | --- |
| NFR-01 | No secret material in Pulumi state, program outputs, logs, CI output, PR comments or artifacts. | A static graph test (no `random:`, `tls:` or `SecretVersion` types), redaction tests, and a TEST state metadata scan. | offline + live |
| NFR-02 | Governance: no `aws.iam.*`, OIDC trust or `aws.lambda.Function` in USI. OIDC-only credentials. Saved-plan apply only. No `AdministratorAccess`. | Policy pack and guardrail tests, plus new type-deny tests. | offline |
| NFR-03 | The quality floors (§2) are unchanged and green. | `make ci-pr`, `make test-coverage`. | offline |
| NFR-04 | TEST before PROD. Each live step is approved by Kravalg, with a requester different from the approver. | Workflow run evidence. | evidence-only |
| NFR-05 | **Dual-credential paths** (Redis RBAC or IAM, DocumentDB IAM): zero failed authentications caused by rotation. **Single-key rotations** (`APP_SECRET`, `OAUTH_ENCRYPTION_KEY`): the impact is measured and stays within D-5 (failed refresh or decrypt count bounded to the rollout window; forced re-login accepted). | TEST forced-rotation exercise: 5xx count, auth-error log metric, deployment timeline. | evidence-only |
| NFR-06 | Least privilege. Every new grant is scoped to named ARNs, name patterns (`<name>-??????`) or deterministic ARNs, with conditions. The BI seed and rotation functions act only on allow-listed secret ARNs. | Reviewed IAM document hashes plus the capability simulator. | offline |
| NFR-07 | Fail closed: a missing central role, CMK, decision or evidence, or a forbidden prior-checkpoint URN, gives BLOCKED admission. | Negative admission and capability tests. | offline |
| NFR-08 | An alarm reaches SNS within 5 min. | TEST alarm exercise. | evidence-only |
| NFR-09 | An interrupted TEST first apply is resumed or abandoned through FR-22 within one working day, with complete evidence. | TEST rehearsal. | evidence-only |
| NFR-10 | Docs stay in sync (`specs/poc/README.md`, `secret-lifecycle.md`, `docs/poc-workload-recovery.md`, `security-baseline.md`, `sre-operations.md`, `poc-workload-admission.md`). | Doc-marker tests. | offline |
| NFR-11 | Cost: the TEST monthly estimate is recorded before and after, and each PROD increase is justified. | Cost document. | evidence-only |

## 5. Traceability: acceptance cases

P = positive, N = negative, B = boundary.

### 5.1 Functional requirements

| Req | P | N | B | Offline test | Live evidence |
| --- | --- | --- | --- | --- | --- |
| FR-01 | The cluster args contain `manage_master_user_password=True` and no `master_password`. | A password config key raises. | The managed secret ARN is observed as metadata only. The A-05 key exception is recorded. | `test_data_plane.py` | TEST `MasterUserSecret` active, rotation enabled (metadata). |
| FR-02 | The URL contains the mechanism, source, TLS and CA. | Userinfo raises. Step-2 admission without bootstrap-job evidence is refused. | The database name is URL-encoded. The connection survives credential refresh. | `test_data_plane.py`, `test_compute_env.py`, admission tests | TEST job evidence; health green; audit log shows `MONGODB-AWS`. |
| FR-03 | Queue and mailer DSNs carry no userinfo. | A key or userinfo in a DSN raises. | Region is present. `auto_setup=false`. | `test_compute_env.py` | TEST mail sent and queues consumed. CloudTrail shows the task-role session. |
| FR-04 (RBAC) | A `default` disabled user, the app user, a group and `user_group_ids`; no `auth_token`; `url` JSON key reference. | `auth_token` set raises. An initially active or no-password app user fails. | Both passwords are valid during the overlap. The second rotation removes the oldest. | `test_data_plane.py`, `test_runtime_secrets.py`; BI rotation tests | TEST two forced rotations; no Redis auth errors; ≤2 passwords. |
| FR-04 (IAM) | `type=iam`, username = user id, `elasticache:Connect`. | A missing grant fails the simulator. | 12 h re-auth. | Same | TEST 13 h soak. |
| FR-05 | Rotation plus seed per rotated purpose; `RotationSucceeded` rule to redeploy. | A secret without rotation fails the validator. A function ARN outside the BI metadata fails. | Seed before `SecretRotation` (so `testSecret` succeeds); schedule ≥ D-5. | `test_runtime_secrets.py`; BI tests | TEST forced rotation → new deployment; impact per NFR-05. |
| FR-06 | No PEM or 2FA purposes; KMS key env values. | Re-adding a PEM purpose fails the schema. | Manual asymmetric key change with a dual-key window. | USI + US tests | TEST login, JWT verification, 2FA; CloudTrail `kms:Sign`. |
| FR-07 | The deny has a `PrincipalArn` allow-list. | Missing, empty or wildcard allow-list fails. | Apply role still denied; admin residual risk recorded. | `test_secret_policy.py` | TEST denied read by a test principal plus alarm fired (no value printed). |
| FR-08 | `valueFrom` is the ARN or `arn:key::`. | A version suffix fails. | The lockout reference equals the Redis reference. | `test_runtime_secrets.py`, `test_poc_secret_observation.py` | TEST task definition has no version IDs. |
| FR-09 | No Random, TLS or `SecretVersion` types; seed input is non-secret. | A generator or `SecretVersion` fails. A prior checkpoint with a forbidden URN is refused. | Seed input containing a `password` key is rejected. | runtime and topology/admission tests | TEST state metadata scan. |
| FR-10 | Key ARNs match the D-4 metadata. | Unknown key or wrong alias fails. | A-05 exception recorded. | `test_poc_contract.py` | TEST `DescribeSecret` `KmsKeyId`. |
| FR-11 | Target and policies match. | min > max, or PROD min < 1, raises; missing `ignore_changes` fails. | TEST 0 only via schedule. | `test_autoscaling.py` | TEST load test. |
| FR-12 | Metric math over three queues. | A DLQ in the math fails. | Zero tasks does not divide by zero. | `test_autoscaling.py` | TEST backlog scale-out. |
| FR-13 | Topic with KMS; every alarm actions to the topic; runbook entry exists. | Topic policy without `SourceAccount` fails. | Missing-data mode per alarm. | `test_observability.py`, doc test | TEST alarm exercise. |
| FR-14 | TEST night schedule; ARM64 when multi-arch. | PROD scale-to-0 fails. ARM64 without an arm64 manifest refused. | Weekend edges. | `test_autoscaling.py` | Cost document. |
| FR-15 | Flow log ALL to S3; bucket controls. | IAM role argument present fails. Non-TLS-only bucket fails. | Lifecycle per environment. | `test_flow_logs.py` | TEST object delivered. |
| FR-16 | Default SG has no rules. | Any rule fails. | Adoption and destroy semantics documented. | `test_network.py` | TEST describe shows no rules. |
| FR-17 | Endpoint set, DNS, SG. | Missing endpoint fails. | TEST single-AZ only with a cost record. | `test_network.py` | TEST pull via endpoint. |
| FR-18 | SG rule sets equal the expected sets, including the two job SGs. | `-1` egress to `0.0.0.0/0` fails. | DNS unaffected. | `test_network.py` | TEST flow logs show no rejected required flows. |
| FR-19 | (B) doc markers present; (A) HTTPS target group. | (A) HTTP target group fails. | Health check over HTTPS. | `test_compute.py`, doc test | TEST healthy targets. |
| FR-20 | Summary has the allow-listed fields. | Secret-like values dropped; `private.log` never uploaded. | Truncation marker. | `test_service_execution_worker.py` | TEST induced failure. |
| FR-21 | Resume admits create or update subsets. | Protected replace or delete refused. Abandon without manifest, snapshot decision or D-7 refused. | Post-abandon registry capture accepts the baseline. Empty diff means complete. | admission, topology, `test_poc_registry_plan.py` | TEST rehearsal. |
| FR-22 | Protected environment, main only, CODEOWNERS. | PR head, non-protected environment or import mismatch refused. | Idempotent lock release. | workflow and script tests | TEST rehearsal. |
| FR-23 | Main admits the environment ⇒ allowed. | PR head admits but main does not ⇒ refused. | Missing contract ⇒ refused. | `test_poc_workload_runner.py` | TEST refusal observed. |
| FR-24 | Measured times below the bounds. | Over the bound blocks gate 2. | Exactly 3300 s counts as over. | `test_apply_timeout_budget.py` | TEST timing evidence. |
| FR-25 | Contract command equals the image command. | Mismatch refused. | Healthcheck grace period. | `test_poc_contract.py` | TEST worker healthy. |
| FR-26 | Capabilities drop `ALL`; unprivileged port. | An add-back fails. | Health-check port follows. | `test_compute.py`; US image test | TEST tasks healthy, `User` non-root. |
| FR-27 | Simulator: required actions allowed. | `GetSecretValue`, `GetFunction` and out-of-scope actions denied. | Conditions present. | BI tests; `test_poc_workload_capabilities.py` | TEST simulator run. |
| FR-28 | REST stage has WAF; route reaches the service. | Direct ALB access from outside the VPC fails. | VPC link 60-day inactivity documented. | AGI tests | TEST route and WAF sampled requests. |
| FR-29 | Managed test/prod without `RuntimeSecrets` raises. | Any `SecretVersion` in the graph fails. | Dev/preview mode unaffected. | `test_stack.py` | — |
| FR-30 | Restore runbook and rollback procedure exist. | Rollback to an unaccepted release refused. | The snapshot restore target is deleted after the check. | doc and admission tests | TEST restore and rollback evidence. |
| FR-31 | Gate 1 admits TEST only; gate 2 admits PROD. | Gate 1 with a missing offline story or decision is refused. PROD with `admission.prod` false is refused. | Gate 2 with any live item missing is refused. | `test_workload_phase_hard_stop.py`, runner tests | TEST acceptance receipt. |

### 5.2 Non-functional requirements

| NFR | P | N | B | Evidence |
| --- | --- | --- | --- | --- |
| NFR-01 | Graph has no secret types; redacted summary. | A seeded fake secret in a log is not in the summary. | Truncated output is still redacted. | Tests plus TEST scan |
| NFR-02 | Guardrail tests pass. | An `aws.iam.Role` or `aws.lambda.Function` added in a fixture fails. | Resource policies (`SecretPolicy`, `TopicPolicy`, bucket policy) are allowed. | Policy pack |
| NFR-03 | CI green. | Threshold edit rejected by review. | — | CI run |
| NFR-04 | Approver ≠ requester. | Self-approval blocked. | PROD only after the TEST receipt. | Run evidence |
| NFR-05 | Zero Redis or DocumentDB auth failures during rotation. | An injected overlap removal shows failures (negative control, TEST only). | Rollout-window impact for single-key rotations within D-5. | TEST exercise |
| NFR-06 | Simulator allows the scoped actions. | Wildcard resource rejected in review. | `name-??????` patterns match only the intended secrets. | IAM hashes |
| NFR-07 | Complete inputs are admitted. | Each missing input is BLOCKED. | Unreadable metadata is BLOCKED. | Tests |
| NFR-08 | Delivery within 5 min. | Disabled action detected by test. | — | TEST exercise |
| NFR-09 | Resume succeeds. | Abandon without D-7 refused. | Lock already released. | Rehearsal |
| NFR-10 | Markers present. | Stale marker fails. | — | Doc tests |
| NFR-11 | Estimate recorded. | — | TEST vs PROD split. | Cost document |

## 6. User-owned decisions

A default applies only to source planning and never authorizes a live action.

| ID | Decision | Options | Default | Blocks |
| --- | --- | --- | --- | --- |
| D-1 | Redis/Valkey auth mode | IAM auth (US change) or rotated RBAC password (infra-only) | Rotated RBAC password. A pending doc comment asks the user. | S1.4, S5.13, gate 1 |
| D-2 | ALB→task TLS | (A) in-container TLS or (B) recorded acceptance | (B) for TEST. PROD needs an explicit choice. | S3.5, gate 2 |
| D-3 | WAF placement | (a) REST API + WAF + VPC link V2; (b) HTTP API with WAF on the internal ALB (needs a `forwarded_ip_config` spoofing analysis, because the ALB sees VPC-link ENI IPs); (c) CloudFront + WAF | (a) | S5.16 |
| D-4 | CMK scope | AWS-managed; one runtime CMK per environment plus JWT and 2FA CMKs; per-purpose CMKs | Runtime CMK per environment plus JWT and 2FA CMKs. The DocumentDB-managed secret stays on the AWS key (A-05). | S1.9, S5.4 |
| D-5 | App-secret rotation cadence and accepted impact | 30, 90 or 180 days; optional US previous-key tolerance (S5.15) | 90 days, forced re-login accepted, S5.15 not scheduled | S1.6 |
| D-6 | Approval to amend the hard stop into two gates (FR-31) | Two-gate admission, or keep the single gate (circular: cannot produce live evidence) | Two-gate. A governance-reviewed README and test change. | S4.6, S4.7 |
| D-7 | Abandon authority | Governance recovery command with a reviewed manifest, or no abandon (resume only) | Recovery command with manifest, TEST only | S4.2, S4.3 |

## 7. External prerequisites (not satisfiable by USI)

- **XP-1.** BI installs the central ECS execution and task roles. They are
  proposed only; `d41c019` is unavailable locally (R-14).
- **XP-2.** BI provides the apply-role workload capability and boundary (N-11).
- **XP-3.** BI provides the CMKs, key policies, rotation, redeploy and
  bootstrap-job functions and roles, and CloudTrail read events.
- **XP-4.** US provides #501, the non-root image, the MONGODB-AWS check, KMS
  signing and encryption, and multi-arch images.
- **XP-5.** AGI provides the front door per D-3.
- **XP-6.** The user supplies the SNS subscription endpoint.
- **XP-7.** The devops-sdlc profile `.claude/devops-sdlc.json` must exist
  (created by `do-sdlc-setup`) before implementation.
- **XP-8.** BI reviews a metadata update after the step-1 apply, supplying the
  USI subnet IDs and the rotation-function SG ID for the Redis rotation
  Lambda's VPC attachment. These values are not deterministic.
