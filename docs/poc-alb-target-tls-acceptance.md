# ALB to task TLS: TEST risk acceptance

**Scope: TEST only.** This document does not cover PROD.

## Decision

D-2 (`specs/workload-wa-hardening/decisions.md`), resolved by the user on
2026-09-30:

- **TEST:** recorded risk acceptance (this document). The ALB target group
  uses HTTP to the task on port 8080.
- **PROD:** in-container TLS on port 8443 with an HTTPS target group and an
  HTTPS health check, required before gate 2 (S5.20 in user-service PR #510,
  and S3.5-A in this repository).

Admission enforces this: a PROD stack with an HTTP target group is refused by admission (FR-19, AD-13).

## Residual risk (A-14)

Assumption A-14 (`specs/workload-wa-hardening/research.md`): an ALB target
group supports HTTPS, the ALB does not validate target certificates, and
in-VPC traffic is authenticated at packet level.

In TEST the ALB does not use it. Traffic between the ALB and the ECS tasks
inside the VPC is plaintext HTTP on port 8080. It is not encrypted on that
hop, so anyone with a network position inside the VPC (a compromised task or
host in the same subnets, or a principal able to mirror or capture ENI
traffic) could read or alter it. Clients still reach the ALB over HTTPS.

## Compensating controls

- Tasks run in private subnets with no public addresses.
- Task security groups admit the ALB security group only.
- VPC flow logs are enabled (S3.1).
- TEST holds no PROD data.

## Owner and review trigger

Owner: `@Kravalg`.

This acceptance ends, and must be reviewed, when either happens:

- TEST moves to an HTTPS target group; or
- any production data enters TEST.
