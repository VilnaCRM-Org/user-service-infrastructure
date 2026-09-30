---
artifact: product-brief
workflow: _bmad/bmm/workflows/1-analysis/bmad-create-product-brief (Create mode, non-interactive)
task: workload-wa-hardening
source_baseline: 66776772979956de9c5abdbee7c45641a1b533fa
date: 2026-09-30
inputDocuments: [specs/poc/README.md, specs/poc/secret-lifecycle.md, docs/poc-workload-recovery.md, research.md]
---

# Product brief: Well-Architected hardening of the user-service workload

## Vision

The user-service ECS workload runs first in TEST and then in PROD. Its end state:

- No human-usable or AI-usable long-lived secret exists anywhere.
- Every credential is either an IAM role session or a managed secret that
  rotates automatically without downtime.
- The workload scales with load and alarms to an owned topic.
- It sits in a least-privilege network.
- A failed first deployment can be recovered through a reviewed, evidenced
  command instead of stop-and-escalate.

Delivering this satisfies every precondition of the "Workload phase hard stop"
in `specs/poc/README.md`. Admission then happens in two gates (D-6):

1. **Gate 1** admits TEST only and runs the live TEST campaign.
2. **Gate 2** admits PROD after the live evidence exists.

## Problem

The workload source (PR #56, `6677677`) is complete, but by design it is not
safe to deploy. The main problems:

- **Secrets and identity.**
  - Secrets are generated inside Pulumi state and never rotate.
  - ECS pins secret versions.
  - The app logs into DocumentDB as the primary user and into Redis with a
    static AUTH token.
- **Operations.** There is no autoscaling, no alarm and no notification.
- **Network.**
  - Egress is open.
  - There are no flow logs.
  - The default SG is unmanaged.
  - ALB→task traffic is plain HTTP with no recorded acceptance.
- **Recovery.** A failed first apply is unrecoverable with shipped tooling
  (N-06).
- **Guarding.** The phase gate exists only at PR-head review (#57).
- **Timing.** The apply timing budget is unmeasured (N-04).

## Users and stakeholders

| Actor | Need |
| --- | --- |
| Service owner (user-service team) | A deployable, observable, self-scaling service with no manual secret handling. |
| Governance owner (`@Kravalg`, bootstrap CODEOWNERS) | IAM, state and recovery changes that stay reviewable, central and least-privilege. |
| Operator on call | Actionable alarms, sanitized failure diagnostics and a reviewed recovery command. |
| AI implementation agents | Unambiguous, file-scoped stories with offline tests. No access to secret values. |
| End users | No outage or forced logout beyond the recorded rotation impact. |

## Success metrics

1. **Zero static credentials in Pulumi state.** A state export (metadata scan)
   of the TEST workload shows no `random:*`, `tls:*` or `SecretVersion`
   resource. USI owns no `SecretVersion` at all.
2. **Rotation works with no downtime.**
   - Every remaining app secret has rotation enabled.
   - A forced rotation in TEST completes (`RotationSucceeded`) and produces a
     new ECS deployment.
   - The target group sees 0 HTTP 5xx during that window, beyond the 5xx
     alarm threshold.
3. **Credential-free app connections.** The app connects to DocumentDB via
   `MONGODB-AWS`, and to SQS and SES via the task role, with no credential
   anywhere in env or secrets.
4. **Scaling.** Web scales out under a synthetic load test. The worker scales
   on backlog.
5. **Alarm routing.** Every alarm in the catalogue routes to the owned SNS topic
   and fires in a controlled TEST exercise.
6. **Network hardening.** Flow logs are delivered. The default SG has no rules.
   Security groups have no `0.0.0.0/0` all-protocol egress.
7. **Recovery rehearsal.** In TEST, a deliberately interrupted first apply is
   recovered or abandoned through the reviewed command, with before and after
   evidence.
8. **Timing.** A measured first create finishes ≤ 3300 s process time and
   ≤ 3600 s from OIDC issuance to observation, or the bootstrap
   `MaxSessionDuration` increase has landed.

## Scope

**In scope:** epics E1–E5 (see `prd.md`). The repositories involved:

- this repository (`user-service-infrastructure`);
- `bootstrap-infrastructure` (IAM, CMK, rotation functions, CloudTrail,
  recovery grants);
- `user-service` (non-root image, #501, MONGODB-AWS check, KMS signing and
  encryption, optional Redis IAM, multi-arch images);
- `api-gateway-infrastructure` (the API front door).

**Out of scope:**

- Implementing any code in this planning task.
- Running any `aws` or `pulumi` command against an account.
- PROD deployment before TEST acceptance.
- DocumentDB global clusters.
- FQDN egress filtering (Network Firewall or DNS Firewall), which is deferred
  and recorded.

## Constraints

- **Governance rules** (AGENTS.md):
  - no IAM roles, policies or OIDC trust in this repository;
  - OIDC-only credentials;
  - saved-plan apply;
  - TEST before PROD;
  - Kravalg-gated protected environments;
  - 100% branch coverage;
  - no destructive-diff overrides.
- **Secret-handling rules.** Never read, print or copy secret material. This
  applies to agents and to CI output.
- **Apply role deny.** `GetSecretValue` and `lambda:GetFunction` are denied to
  the apply role (research R-16).

## Assumptions

Each assumption is recorded and none changes scope.

- **AS-1.** The workload has never been applied in TEST or PROD (R-02), so
  E1's state changes are source-only.
- **AS-2.** The engine stays Redis OSS 7.1. A later Valkey move is compatible
  with both D-1 options.
- **AS-3.** The service stays on the private gateway topology: internal ALB
  behind an API Gateway VPC link.
- **AS-4.** User-owned decisions D-1…D-7 use the defaults in `prd.md` §6 until
  the user decides. A default never authorizes a live action.
