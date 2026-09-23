# First-workload topology prerequisite

`poc_workload_topology.py` checks the exact current two-AZ workload owner graph:
the unchanged eleven-resource registry/prerequisite baseline, pinned AWS/Random/TLS providers,
generated secret resources, network/data/queue planes, ECS Fargate web and worker,
public HTTPS ALB, and service-owned ALB log storage. No AWS apply is enabled.

The prior graph must be the complete registry graph. Its goals retain the existing
strict registry validator. Every additional owner must have the exact name, type,
parent, protection and provider link, and must only be created. Missing/extra
owners, imported resources, changed baseline resources and foreign references
reject. New preview inputs must match the reconstructed saved-plan inputs, with
secret redaction only in the preview. Only exact pinned SDK type aliases are
permitted; arbitrary aliases remain forbidden.

The native CLI can omit unchanged component outputs from `newState`. This module
restores only an absent projection from the validated prior; the saved goal still
must have no output changes. An explicitly different output map rejects. This
handling does not modify the existing registry runner or validator.

A first preview can serialize an unresolved generated SecretVersion value as the
exact Pulumi unknown sentinel. The topology check permits that sentinel only in
the new resource with mandatory `secretString` secret-output marking. Known values
require Pulumi secret wrappers. The no-change/prior-state validator is unchanged.

## Execution remains closed

`admit_first_workload_plan` always rejects after a successful topology check with
`workload-native-capability-and-input-admission-required`. There is no capability
boolean, caller assertion or synthetic receipt that bypasses this stop. The
existing worker stops also remain unchanged.

The worker now runs bounded native role/boundary, execution-role ECR simulation
and certificate prerequisites described in [workload admission](poc-workload-admission.md).
They do not satisfy the complete capability/input or saved-plan replay gate here.

Topology does not establish all workload input semantics, generated unknown
values, installed runtime/deployer IAM intersection, current native resources,
artifact provenance, authenticated prior/result receipts or cloud health. Those
gates and same-run source/checkpoint replay binding must be implemented and
independently verified before replacing this stop. No successful check here is a
deployment or workload acceptance receipt.

Tests run the actual installed registry/workload composition and Pulumi v3.223.0
engine against a local backend and three test-only loopback provider transports.
Only the synthetic registry baseline is applied; the workload is previewed into a
native saved plan. The stub providers never contact AWS and do not implement AWS
provider semantics or IAM. These tests establish native engine/SDK wire and full
composition topology compatibility, separately from the still-missing AWS proof.
