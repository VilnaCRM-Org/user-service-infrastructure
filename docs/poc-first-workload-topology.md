# First-workload topology prerequisite

`poc_workload_topology.py` checks the exact current two-AZ workload owner graph:
the unchanged eleven-resource registry/prerequisite baseline, pinned AWS/Random/TLS providers,
generated secret resources, network/data/queue planes, ECS Fargate web and worker,
internal HTTPS ALB for the API Gateway private integration, and service-owned ALB
log storage. No AWS apply is enabled.

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

The native saved-plan gate also binds the fixed TLS policy, sole HTTPS forward
action, HTTP/IP target-group health settings, web service target and container
port, absence of a worker load balancer, and the target-group VPC dependency.
First-create target and listener ARNs may still be unknown; these checks do not
prove resolved physical relationships or authorize execution.

A first preview can serialize an unresolved generated SecretVersion value as the
exact Pulumi unknown sentinel. The topology check permits that sentinel only in
the new resource with mandatory `secretString` secret-output marking. Known values
require Pulumi secret wrappers. The no-change/prior-state validator is unchanged.

## Preview-only admission

`admit_first_workload_plan` accepts the exact validated TEST first-create preview.
The installed worker routes only `test_preview` to the workload runner. It rejects
workload `up-plan` and drift before invoking the runner; the runner independently
requires a result observer before apply. Preview admission is not apply authority.

The preview observation path implements bounded native role/boundary,
execution-role ECR simulation and certificate prerequisites described in
[workload admission](poc-workload-admission.md). Apply stops before this path.
They do not satisfy the complete apply capability/input or accepted-result gate.

Topology does not establish all workload input semantics, generated unknown
values, installed runtime/deployer IAM intersection, current native resources,
artifact provenance, authenticated prior/result receipts or cloud health. Those
gates and same-run source/checkpoint replay binding must be implemented and
independently verified before enabling apply. No successful check here is a
deployment or workload acceptance receipt.

Tests run the actual installed registry/workload composition and Pulumi v3.223.0
engine against a local backend and three test-only loopback provider transports.
Only the synthetic registry baseline is applied; the workload is previewed into a
native saved plan. The stub providers never contact AWS and do not implement AWS
provider semantics or IAM. These tests establish native engine/SDK wire and full
composition topology compatibility, separately from the still-missing AWS proof.
