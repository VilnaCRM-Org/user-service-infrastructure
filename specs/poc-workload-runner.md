# Sealed TEST workload runner source boundary

`scripts/poc_workload_runner.py` connects the existing authenticated source,
registry receipt/checkpoint, publisher, image and native prerequisite readers to
the protected workload materializer and shared saved-plan dispatcher. It accepts
only the root PID 1, read-only installed worker and its `ServiceTransport`; there
is no local execution fallback or arbitrary program path.

The runner requires the production domain declaration to use
`certificate_parameter_name: /vilnacrm/test/user-service/gateway-certificate-arn`.
The schema retains an explicit `certificate_arn` alternative for internal/test
projections, but the production runner rejects that alternative. Both fields
together, neither field, and any other parameter name reject. The trusted reader
requires the exact SSM Name/ARN, String/text type, positive integer version and
same-account regional ACM certificate ARN. It applies existing issued-certificate,
SAN, TLS usage and validity checks, then repeats SSM/ACM observation. No decrypted
parameter or application secret is fetched or logged.

The source contract remains immutable. The closed `poc-workload-child-v2`
projection carries separate public certificate observation fields:
`parameter_arn`, `parameter_version`, and `certificate_arn`. Its canonical digest,
the prepared configuration digest and all generated file digests enter the
saved-plan `executionIdentity`. Replay rejects missing or changed execution
identity, including replay through an ordinary registry context. Existing source,
age, plan/preview byte hashes and provider/checkpoint checks remain in force.

Before every child preview/apply, the original source/requester admission runs and
the protected generated files are read back with exact content, mode, ownership,
single-link and path checks. The child uses the generated isolated Python wrapper.
Neither GitHub authority nor PR-controlled Python is passed to that child.

This is not an enabled deployment route. The installed worker's workload stop
remains intact, the first-workload semantic gate still rejects every plan, replay
additionally requires a workload result observer, and drift rejects without an
authenticated accepted-workload receipt. No success receipt or gateway descriptor
can be issued by this adapter. Complete the remaining resource-input validation,
result/secret observation and phase-aware workflow/drift routes before enabling it.

The workload source uses an internal ALB in its application subnets and only an
HTTPS listener. A service-owned VPC-link security group is its exclusive ingress
source. The generated application trusted-proxy CIDRs match these ALB subnets.
The legacy template path remains separate from this fixed workload projection.
The first-workload native plan gate now checks the private ALB flag, single
security-group HTTPS ingress, VPC-link egress limited to the admitted application
subnet CIDRs, issued-certificate listener input, and private noninteractive
Fargate service settings with circuit-breaker rollback. First-create physical
IDs are unresolved in the plan; the accepted-result observer must still bind
their actual subnet, listener and security-group relationships before issuing
any workload receipt or gateway descriptor.
The native gate also requires the fixed ALB/subnet/security-group, HTTPS listener,
and ECS task/service dependency edges. These edges are an early rejection check,
not proof of the resolved physical relationships.
The first-plan gate binds both private application subnet CIDRs to the admitted
trusted-proxy networks, rejects public IP assignment on application/data subnets,
requires encrypted DocumentDB and Redis with retained backups/snapshots, and
requires all six SQS queues to keep AWS-managed KMS encryption, long polling and
their fixed visibility timeout. These checks operate on the saved native plan and
preview together; live resource identifiers and effective cloud behavior still
require the accepted-result observer and manual TEST acceptance.

Live prerequisites remain external: installed central runtime/deployment IAM and
the exact SSM read grant in bootstrap #219; completed registry proof; authenticated
immutable image publication; gateway-owned issued ACM certificate and its SSM
publication; verified SES prerequisites. Gateway route deployment follows the
[authenticated backend descriptor contract](poc-api-gateway-backend.md).
