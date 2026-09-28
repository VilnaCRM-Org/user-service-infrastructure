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

The installed worker sends `test_preview` and first-create `test_apply` to the
protected workload runner. The exact first-workload topology is checked again
against the saved plan before replay. A successful apply must produce a new,
stable complete checkpoint with the fixed graph, unchanged registry resources
and native secret metadata read twice. The backend and requester are rechecked
before the job reports success. Workload drift and later releases remain closed
until an authenticated accepted-workload receipt exists. This first-apply result
is not a success receipt or gateway descriptor; live application acceptance is
still required.

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
their fixed visibility timeout. It pins their physical names to the TEST PoC
defaults, including `health-check-queue`, and binds each application transport DSN
to its fixed queue name, TEST account, region and `auto_setup=false`. These checks
operate on the saved native plan and preview together; live resource identifiers
and effective cloud behavior still require the accepted-result observer and manual
TEST acceptance.
The generated configuration also fixes the application's JWT issuer/audience and
metrics namespace to its TEST runtime contract. The protected config overlay and
native task-definition gate reject changes to those three public values.

The source includes a metadata-only first-create secret-history checker. It
compares the protected checkpoint graph with the registry baseline and reads
Secrets Manager `DescribeSecret` twice for every declared runtime secret. It
requires the same ARN, name, KMS key and sole current version in checkpoint and
native metadata, with no pending rotation or deletion. It never calls
`GetSecretValue`. On its own this checker does not authenticate the checkpoint or
AWS session. The installed runner composes it with authenticated private
checkpoint reads after the first saved-plan apply; it still issues no receipt.

Live prerequisites remain external: installed central runtime/deployment IAM and
the exact SSM read grant in bootstrap #219; completed registry proof; authenticated
immutable image publication; gateway-owned issued ACM certificate and its SSM
publication; verified SES prerequisites. Gateway route deployment follows the
[authenticated backend descriptor contract](poc-api-gateway-backend.md).

The metadata-only release/rollback secret checker accepts two complete workload
checkpoints and a prior secret observation supplied by a future authenticated
receipt. It requires every secret and secret-version state row to remain unchanged
apart from observation timestamps, then reads native secret descriptions twice
and requires the current version, ARN and KMS key to match that prior observation.
It never reads secret values. Neither this checker nor its caller yet authenticates
an accepted workload receipt or enables a release/rollback apply.
