# ALB to task TLS: TEST risk acceptance

**Scope: TEST only.** This document does not cover PROD.

## Decision

D-2 (`specs/workload-wa-hardening/decisions.md`), resolved by the user on
2026-09-30:

- **TEST:** recorded risk acceptance (this document). The ALB target group
  uses HTTP to the task on the container port (80 at this base; 8080 once the
  non-root image contract of user-service S5.9 and AD-14 lands here).
- **PROD:** in-container TLS on port 8443 with an HTTPS target group and an
  HTTPS health check, required before gate 2 (S5.20 in user-service PR #510,
  and S3.5-A in this repository).

Admission enforces this: a PROD stack with an HTTP target group is refused by admission (FR-19, AD-13).
At this base that holds because admission accepts only the TEST stack; the
explicit protocol check for PROD arrives with S3.5-A.

## Residual risk (A-14)

Assumption A-14 (`specs/workload-wa-hardening/research.md`): an ALB target
group supports HTTPS, the ALB does not validate target certificates, and
in-VPC traffic is authenticated at packet level.

In TEST the ALB does not use it. Traffic between the ALB and the ECS tasks
inside the VPC is plaintext HTTP on the container port. A-14 treats in-VPC traffic as
authenticated at packet level, so this is not exposure to arbitrary sniffing.
The exposure is a compromised task or ENI in the same VPC that could read or
alter this hop. Clients still reach the ALB over HTTPS.

## Compensating controls

In place at the base commit 0721d93:

- Tasks run in the private app subnets with `assign_public_ip=False`
  (`pulumi/app/network.py`, `pulumi/app/compute.py`).
- The service security group admits the container port from the ALB security
  group only (`pulumi/app/network.py`).

Planned, not in place at this base:

- VPC flow logs to S3 (planned, S3.1).

## Acceptance conditions (attested by the owner)

- TEST holds no PROD data. This is an assumption the owner attests, not a
  technical control.

## Owner and review trigger

Owner: `@Kravalg`.

This acceptance ends, and must be reviewed, when either happens:

- TEST moves to an HTTPS target group; or
- any production data enters TEST.
