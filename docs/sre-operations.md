# SRE Operations Guide

This guide covers the day-2 operating model for the template: validating local
prerequisites, previewing changes safely, and handling common infrastructure
maintenance flows.

## Preflight

Run the basic workstation check before blaming Docker, Pulumi, or CI:

```bash
make doctor
```

The command verifies that Docker and Docker Compose are available, reports the
effective env file, and prints the service and Pulumi directory that the
Makefile will target. It does not print secrets.

## Daily Workflow

For the normal edit-test loop:

```bash
make test
```

Before pushing a branch that changes infrastructure logic, Docker wiring, or CI
contracts, use the same non-mutation battery that GitHub runs in
`pulumi-local.yml`:

```bash
make ci-pr
```

When you also want the dedicated mutation suite locally:

```bash
make ci
```

Use `make ci-pr` to catch the same structural, policy, quality, unit,
integration, CLI, security-scan, and preview guardrails that GitHub runs before
merge. Use `make ci` when you also want the mutation suite before the branch
reaches GitHub Actions.

## Preview and Apply

Use previews as the default gate for real infrastructure changes:

```bash
make pulumi-preview
```

The preview target syncs the shared `uv` environment if necessary and enables
the repository policy pack automatically, so guardrail drift is caught before
the Pulumi plan is shown.

When you want to reproduce the credential-free PR preview flow locally, use:

```bash
make test-guardrails
```

That target generates the preview artifact and blocks destructive changes to
critical resources without requiring live AWS credentials. Keep
`make test-iam-validation` for the separate Access Analyzer check when you
intentionally have AWS credentials configured.

Apply only after the preview is understood and reviewed:

```bash
make pulumi-up
pulumi -C pulumi stack output
```

`make pulumi-up` uses the same policy-pack enforcement path as preview.

For drift reconciliation without applying a fresh plan:

```bash
make pulumi-refresh
```

For teardown:

```bash
make pulumi-destroy
```

Treat destroy as irreversible unless you have a tested restore path.

Managed DocumentDB clusters and instances are Pulumi-protected in every
environment, and each cluster keeps deletion protection plus a named final
snapshot (`<stack>-docdb-final`). A destroy therefore stops at DocumentDB until a
separately reviewed change removes that protection; do not unprotect state or
disable deletion protection out of band.

A failed, interrupted or partial first workload apply is not recoverable with
shipped tooling: stop and escalate to governance, following the
[PoC workload recovery runbook](poc-workload-recovery.md).

## Stack Strategy

Recommended stack patterns:

- `dev` for shared baseline development
- `pr-<number>` for short-lived validation environments
- `smoke` for manual release verification

Avoid mixing unrelated validation work into one long-lived shared stack. It
makes previews noisy and rollback decisions ambiguous.

## Incident and Drift Triage

When something looks wrong:

1. run `make doctor`
2. run `make test` to separate local code issues from cloud drift
3. run `make pulumi-refresh` if the concern is live-state drift
4. inspect `pulumi -C pulumi stack output` for the non-secret state you expect
5. use an ephemeral stack for risky experiments instead of debugging directly in
   a shared environment
6. if a change is intentionally destructive, document the reason and add the
   `allow-destructive-infra-change` label instead of bypassing the workflow

## Alarm Runbooks

Every CloudWatch metric alarm of the PRD §3.1 catalogue (FR-13) is declared in
`pulumi/app/observability.py`. Each alarm is named
`<stack tag>-<suffix>`, for example `user-service-infrastructure-test-dlq-failed-send-email`,
and sends its alarm action and its OK action only to the service-owned SNS
topic `<stack tag>-alarms` on the runtime CMK (S2.3); no alarm has an
insufficient-data action. The hardened guard refuses any other action list.
The topic subscription endpoint is XP-6. Each heading below is the alarm
suffix; `tests/unit/test_alarm_runbooks.py` fails when a declared alarm has no
entry, when an entry lacks a severity, first responder, escalation,
containment, missing-data or evidence line, or when the missing-data line
differs from the declared alarm.

Rules for every entry:

- The first responder is the service owner on call.
- Any §3.2a secret, IAM or KMS event escalates to Kravalg.
- A containment that stops PROD (the `rollback-zero` stop plan) records the
  incident reason in the stop PR (AD-10).
- A containment names only actions that admission accepts. A `policy-update`
  plan changes only the managed-secret `SecretPolicy` or a `VpcEndpoint`
  policy, with `policy` as the only changed input (FR-07). A security-group,
  role or IAM change goes through a reviewed PR, a BI role change or a Kravalg
  escalation, never a `policy-update` plan.
- The missing-data line records the alarm's `treatMissingData` mode and why:
  `notBreaching` where a quiet metric is no failure, `breaching` where an
  always-published metric bound to the data plane is absent only when the
  dimension is wrong or the instance is gone, and `missing` where the alarm
  keeps its state (no insufficient-data action pages anyone).
- Never copy secret values, tokens or decrypted outputs into the evidence.

Severities: **SEV-1** is customer-facing loss of service, **SEV-2** is loss of
work or degraded capacity, **SEV-3** is a risk that needs action within one
working day, and **informational** needs no immediate action.

Docs-verified cases recorded with these runbooks:

- **V-11:** DocumentDB publishes `StsGetCallerIdentityCalls` for IAM
  (`MONGODB-AWS`) authentication (`iam-identity-auth.html`, verified
  2026-09-30). The live TEST check must confirm data at the alarm's own
  `DBClusterIdentifier` dimension (the data plane's cluster identifier, for
  example `user-service-infrastructure-test-docdb`), not only at some other
  dimension. The fallback, if it shows no data there, is to drop the
  informational `docdb-sts-calls` alarm by a reviewed PR and record it.
- **V-25:** the ECS `awslogs` driver writes to the runtime-CMK log groups
  without a KMS statement for the execution role (A-28). If a live check shows
  `AccessDeniedException` on `PutLogEvents`, the fallback is the reviewed
  AD-15a execution-role row (`kms:GenerateDataKey` with
  `kms:ViaService=logs.<region>.amazonaws.com`) with both of its parts
  (R14-n1): (1) an ECS runtime stack amendment (AD-26 layer 6) with `Modify`
  rows on the execution role's policy and on its `-Boundary` and `-Guard`
  policies (the guard's `NotResource` deny and the boundary allow), run by the
  XP-17 installer; and (2) S5.4's runtime-CMK key-policy statement naming the
  execution role (no root `kms:*`). Both parts run in the one conditional
  row-43 serialization slot (R13-n5), after step 7's STOP and before step 18;
  then step 7 is re-run.

### `dlq-failed-send-email`

- **Alarm:** `ApproximateNumberOfMessagesVisible` ≥ 1 on `failed-send-email` for 5 min.
- **Severity:** SEV-2 (outbound mail was lost after its retries).
- **First responder:** the service owner on call.
- **Escalation:** the service owner lead; Kravalg if the cause is a §3.2a secret, IAM or KMS event (for example an SES or KMS `AccessDenied`).
- **Containment:** stop the redrive, fix the cause by a reviewed PR (a `policy-update` plan only when the permission is in a `VpcEndpoint` policy), then redrive the queue to `send-email`.
- **Missing data:** `notBreaching`: SQS stops publishing the metric for a queue idle for six hours, and an idle DLQ is the healthy state.
- **Evidence to keep:** the message count and age, one sample message ID with its attributes, the worker log lines for that ID, and the fix PR.

### `dlq-failed-domain-events`

- **Alarm:** `ApproximateNumberOfMessagesVisible` ≥ 1 on `failed-domain-events` for 5 min.
- **Severity:** SEV-2 (domain events were not processed).
- **First responder:** the service owner on call.
- **Escalation:** the service owner lead; Kravalg if the cause is a §3.2a secret, IAM or KMS event.
- **Containment:** pause the redrive, fix the consumer or permission by a reviewed PR, then redrive to `domain-events`.
- **Missing data:** `notBreaching`: SQS stops publishing the metric for a queue idle for six hours, and an idle DLQ is the healthy state.
- **Evidence to keep:** the message count and age, sample message IDs, the worker log lines, and the fix PR.

### `dlq-failed-insert-user-batch`

- **Alarm:** `ApproximateNumberOfMessagesVisible` ≥ 1 on `failed-insert-user-batch` for 5 min.
- **Severity:** SEV-2 (user batch inserts were not written).
- **First responder:** the service owner on call.
- **Escalation:** the service owner lead; Kravalg if the cause is a §3.2a secret, IAM or KMS event (for example a DocumentDB IAM authentication failure).
- **Containment:** fix the cause by a reviewed PR, confirm DocumentDB health, then redrive to `insert-user-batch`.
- **Missing data:** `notBreaching`: SQS stops publishing the metric for a queue idle for six hours, and an idle DLQ is the healthy state.
- **Evidence to keep:** the message count and age, sample message IDs, the worker and DocumentDB log lines, and the fix PR.

### `alb-target-5xx`

- **Alarm:** `HTTPCode_Target_5XX_Count` > 5 per minute for 3 of 5 min.
- **Severity:** SEV-1 (API requests fail).
- **First responder:** the service owner on call.
- **Escalation:** the service owner lead; Kravalg if the errors come from a §3.2a secret, IAM or KMS event.
- **Containment:** roll back to the last good image by a reviewed PR; in PROD, if errors persist, apply the `rollback-zero` stop plan and record the incident reason (AD-10).
- **Missing data:** `notBreaching`: the ALB publishes no 5xx count while no request fails.
- **Evidence to keep:** the ALB access-log objects for the window, the web task log lines, the deployed image tag, and the rollback PR.

### `alb-elb-5xx`

- **Alarm:** `HTTPCode_ELB_5XX_Count` > 5 per minute for 3 of 5 min.
- **Severity:** SEV-1 (the load balancer cannot reach a healthy target).
- **First responder:** the service owner on call.
- **Escalation:** the service owner lead; Kravalg if a listener certificate, IAM or KMS change caused it.
- **Containment:** restore healthy targets (roll back the image or the task definition by a reviewed PR); in PROD, a `rollback-zero` stop records the incident reason (AD-10).
- **Missing data:** `notBreaching`: the ALB publishes no 5xx count while no request fails.
- **Evidence to keep:** the ALB access-log objects with the `elb_status_code`, the target health history, and the ECS service events.

### `alb-unhealthy-targets`

- **Alarm:** `UnHealthyHostCount` ≥ 1 for 3 min.
- **Severity:** SEV-2 (capacity is degraded; SEV-1 when no target is healthy).
- **First responder:** the service owner on call.
- **Escalation:** the service owner lead; Kravalg if the health check fails on a §3.2a secret, IAM or KMS event.
- **Containment:** let ECS replace the task; if the new tasks fail too, roll back the image by a reviewed PR.
- **Missing data:** `notBreaching`: with no registered target (services at 0 tasks) nothing is unhealthy.
- **Evidence to keep:** the target health reason codes, the stopped-task reasons, and the web task log lines.

### `ecs-web-below-desired`

- **Alarm:** Container Insights `RunningTaskCount` < `DesiredTaskCount` for the web service for 10 min (`IF(desired > 0, desired - FILL(running, 0), 0)`: a missing `RunningTaskCount` counts as 0 running tasks); suppressed while the desired count is 0 (TEST night or weekend stop, PROD `rollback-zero` stop).
- **Severity:** SEV-2 (web capacity is below its target).
- **First responder:** the service owner on call.
- **Escalation:** the service owner lead; Kravalg if tasks stop on a secret, IAM or KMS error (for example `ResourceInitializationError` on a secret).
- **Containment:** fix the task start failure by a reviewed PR; in PROD, a `rollback-zero` stop plan records the incident reason (AD-10).
- **Missing data:** `notBreaching`: `FILL` already turns a missing running count into 0; with no desired count the service is stopped.
- **Evidence to keep:** the ECS service events, the stopped-task reasons, and the web task log lines.

### `ecs-worker-below-desired`

- **Alarm:** Container Insights `RunningTaskCount` < `DesiredTaskCount` for the worker service for 10 min (`IF(desired > 0, desired - FILL(running, 0), 0)`: a missing `RunningTaskCount` counts as 0 running tasks); suppressed while the desired count is 0.
- **Severity:** SEV-2 (queue processing is below its target).
- **First responder:** the service owner on call.
- **Escalation:** the service owner lead; Kravalg if tasks stop on a secret, IAM or KMS error.
- **Containment:** fix the task start failure by a reviewed PR and watch the DLQ alarms; in PROD, a `rollback-zero` stop plan records the incident reason (AD-10).
- **Missing data:** `notBreaching`: `FILL` already turns a missing running count into 0; with no desired count the service is stopped.
- **Evidence to keep:** the ECS service events, the stopped-task reasons, the worker task log lines, and the queue depths.

### `docdb-cpu`

- **Alarm:** DocumentDB `CPUUtilization` > 80% for 15 min on the busiest instance: `MAX` over the per-`DBInstanceIdentifier` averages of the data plane's instances, so a hot writer alarms even when a quiet reader keeps the cluster average low.
- **Severity:** SEV-3 (SEV-2 when API latency or errors rise with it).
- **First responder:** the service owner on call.
- **Escalation:** the service owner lead.
- **Containment:** find the slow queries in the profiler log group, reduce the load (scale the worker down by a reviewed PR), and plan an index or instance-class change by a reviewed PR.
- **Missing data:** `breaching`: every instance publishes CPU each period and the alarm names the data plane's instance outputs, so no data means a wrong dimension or a lost instance.
- **Evidence to keep:** the profiler log entries, the Performance Insights top queries, and the change PR.

### `docdb-freeable-memory`

- **Alarm:** DocumentDB `FreeableMemory` below 10% of the instance class memory for 15 min.
- **Severity:** SEV-3 (SEV-2 when swap or latency rises with it).
- **First responder:** the service owner on call.
- **Escalation:** the service owner lead.
- **Containment:** reduce the working set or connections, then plan an instance-class change by a reviewed PR.
- **Missing data:** `breaching`: the cluster publishes memory each period and the alarm names the data plane's cluster output, so no data means a wrong dimension.
- **Evidence to keep:** the memory and connection metrics, the profiler log entries, and the change PR.

### `redis-memory`

- **Alarm:** Redis `DatabaseMemoryUsagePercentage` > 80% on any member for 15 min.
- **Severity:** SEV-3.
- **First responder:** the service owner on call.
- **Escalation:** the service owner lead.
- **Containment:** check the key TTLs and the largest keys, then plan a node-type change by a reviewed PR.
- **Missing data:** `missing`: the member IDs are derived names, not outputs, so the alarm can exist before the group; it keeps its state, and the console shows `INSUFFICIENT_DATA` if a dimension is wrong.
- **Evidence to keep:** the memory and key-count metrics per member, and the change PR.

### `redis-evictions`

- **Alarm:** Redis `Evictions` > 0 across the group in 5 min.
- **Severity:** SEV-3 (SEV-2 when lockout or session keys are evicted).
- **First responder:** the service owner on call.
- **Escalation:** the service owner lead.
- **Containment:** follow `redis-memory`; reduce the cached data or raise the node type by a reviewed PR.
- **Missing data:** `notBreaching`: no eviction is the healthy state.
- **Evidence to keep:** the eviction and memory metrics per member, and the change PR.

### `redis-auth-failures`

- **Alarm:** ElastiCache `AuthenticationFailures` > 0 across the group in 5 min. The IAM-auth metrics named by V-9 join this alarm only if a live check shows they are published.
- **Severity:** SEV-2 (a client fails Redis IAM authentication; it can be an attack).
- **First responder:** the service owner on call.
- **Escalation:** Kravalg (a §3.2a IAM event).
- **Containment:** confirm the caller from the task logs; a broken app role is fixed by a BI role change in a reviewed PR; for an unknown caller, escalate to Kravalg at once and remove its network or IAM path by a reviewed PR (a BI role or IAM change, or a security-group change); in PROD, if the failures continue, apply the `rollback-zero` stop plan and record the incident reason (AD-10).
- **Missing data:** `notBreaching`: no failed authentication is the healthy state.
- **Evidence to keep:** the failure count per member, the task log lines with the IAM user ID, the CloudTrail events for the role, and the fix PR.

### `docdb-sts-calls`

- **Alarm:** DocumentDB `StsGetCallerIdentityCalls` above its anomaly-detection band (2 deviations) for 15 min (V-11).
- **Severity:** informational (IAM authentication pressure, for example a reconnect storm).
- **First responder:** the service owner on call.
- **Escalation:** Kravalg when the calls come with authentication failures (a §3.2a IAM event).
- **Containment:** none by default; check the client connection pooling, and open a reviewed PR if a client reconnects in a loop.
- **Missing data:** `missing`: the metric is published only while clients authenticate with IAM, and the alarm is informational.
- **Evidence to keep:** the call metric, the DocumentDB audit entries for `MONGODB-AWS`, and the client connection counts.

## Network Hardening

### Managed default security group (S3.2, FR-16)

The hardened workload program declares one `aws:ec2/defaultSecurityGroup:DefaultSecurityGroup`
(`user-service-default-sg`) on the workload VPC with empty `ingress` and empty `egress`. Nothing in the
workload may use the default group, so it holds zero rules (Security Hub EC2.2).

- **Adoption:** AWS creates the default group with the VPC, and the group cannot be deleted. Pulumi does
  not create a new group: on the first apply it adopts the existing default group and removes every
  ingress and egress rule it finds. No import step is needed.
- **Drift:** a rule added outside Pulumi shows as drift and the next apply removes it. A rule added in
  code fails the hardened guard (`Hardened workload graph holds an unreviewed property`) before any
  preview.
- **Destroy:** deleting the resource, or destroying the stack, only stops Pulumi managing the group.
  The group stays in the VPC with the rules it had, which is zero rules, until AWS deletes the VPC.
- **Pre-hardening graph:** the bridge graph does not manage the default group (AD-25).

### VPC flow logs (S3.1, FR-15)

The hardened workload program declares one `aws:ec2/flowLog:FlowLog` (`user-service-vpc-flow-log`) on the
workload VPC with `traffic_type` `ALL`, destination type `s3` and no IAM role argument. Delivery to S3 runs as
the `delivery.logs.amazonaws.com` service, so no role exists.

- **Bucket:** `<stack tag>-<account>-flow-logs`, owned by the `flow-logs` component. SSE-KMS with the runtime CMK
  (`central.cmk.runtime.arn`, D-4) and the bucket key on; public access blocked; object ownership
  `BucketOwnerEnforced`; `force_destroy=false` and Pulumi `protect`; records expire after 30 days in TEST and
  90 days in PROD.
- **Bucket policy:** denies every request without TLS (`aws:SecureTransport` `false`). It allows only
  `delivery.logs.amazonaws.com` `s3:PutObject` on `AWSLogs/<acct>/*` and `s3:GetBucketAcl` on the bucket, each
  with `aws:SourceAccount` = the account and `aws:SourceArn` like `arn:aws:logs:<region>:<acct>:*`.
- **Guards:** a flow log with an IAM role argument and any hardened bucket with `force_destroy=true` fail the
  hardened guard. The component refuses SSE-S3, SSE-KMS with any key other than the runtime CMK, a bucket policy
  without the TLS deny or a delivery statement without `aws:SourceArn`, before any registration.
- **V-16 (first case, docs):** the runtime key policy is governance-owned. It must allow
  `delivery.logs.amazonaws.com` `kms:GenerateDataKey*` and `kms:Decrypt` with `aws:SourceAccount` and
  `aws:SourceArn` (AD-15a). The apply role holds `ec2:CreateFlowLogs` and `logs:CreateLogDelivery` (S5.2); the
  matching deletes belong to the TEST recovery role (S5.7). If delivery fails with SSE-KMS, STOP and fix the key
  or bucket policy by a reviewed PR. SSE-S3 is not a fallback: D-4 decided SSE-KMS, and changing it needs a new
  user decision.
- **Import and abandon:** no N-06 import list or abandon manifest exists yet. When S4.3 and S4.10 add them, the
  bucket family joins the import list and is always `retain` in an abandon manifest (AD-16, D-11).

## CI Troubleshooting

Map failures back to their local commands:

- `Structural` -> `make test-pulumi`
- `Policy` -> `make test-policy`
- `Ruff` -> `make test-ruff`
- `Ty` -> `make test-ty`
- `Maintainability` -> `make test-maintainability`
- `Architecture` -> `make test-architecture`
- `Dependency Hygiene` -> `make test-dependency-hygiene`
- `Coverage` -> `make test-unit && make test-integration && make test-policy && make test-coverage`
- `Unit` -> `make test-unit`
- `Integration` -> `make test-integration`
- `Mutation` -> `make test-mutation`
- `Run Bats Tests` -> `make test-cli`
- `Local Battery` -> `make ci-pr`
- `Preview` -> `make test-preview`
- `Destructive Diff Gate` -> `make test-destructive-diff`
- `IAM Validation` -> `make test-iam-validation`
- `Secrets Scan` -> `make test-secrets`
- `Dependency Audit` -> `make test-deps-security`
- `Bandit` -> `make test-bandit`
- `Actionlint` -> `make test-actionlint`
- `Yamllint` -> `make test-yaml`
- `Hadolint` -> `make test-dockerfile`
- `CodeQL`, `Dependency Review`, `Infracost`, and `CodeRabbit` -> GitHub-native only

That mapping is intentional. If a failure cannot be reproduced locally with the
matching target, the problem is probably workflow-specific and should be treated
as a CI contract issue.

## Release Hygiene

Release automation should stay boring:

- keep changelog generation deterministic
- use the documented token fallback contract
- avoid mixing release logic with deployment logic
- prefer one-purpose workflows over single giant pipelines

## Cleanup

When local state gets messy:

```bash
make clean
```

This removes Compose state and Python build artifacts without touching cloud
resources.
