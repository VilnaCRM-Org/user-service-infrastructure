# PoC generated secret lifecycle

Desired workload source declares each secret's name, encryption-key ARN and
service ownership. The key ARN must resolve from reviewed platform metadata
before workload admission. Secret values, generated ARN suffixes and version IDs
are not desired inputs: first creation cannot know those AWS-generated values.

`poc_secret_observation.validate_secret_observation` checks metadata supplied by
the trusted result observer. Every purpose must have an exact matching name,
account, region, key and owner. Extra fields, including secret values, fail.
After the first accepted workload, updates and rollback of a generated
(pre-hardening) shape must preserve the exact ARN and version from its
authenticated prior receipt; a hardened shape compares the ARN and name only
(see "ECS references resolve `AWSCURRENT`" below). Desired secret names and
keys remain immutable across workload transitions. Rotation needs a separate
reviewed protocol.

Hard stop: the pre-hardening shape pins secret versions and has no rotation. The
`workload` phase must not be enabled (`specs/poc/poc-test.json` stays
`"registry"`) until secret rotation (F-01) and `AWSCURRENT` references instead of
version pinning (F-02) land in the stacked hardening PR, together with the other
preconditions listed in `README.md` ("Workload phase hard stop").

This is source validation only. The helper neither queries AWS nor authenticates
a receipt. The observer must resolve the actual `AWSCURRENT` version from AWS,
never a caller-selected historical version. The trusted controller must supply the native current observation and
require the authenticated previous observation whenever an accepted workload
exists. Missing evidence must not select first-creation mode. This binding must
be wired before workload deployment; passing these tests does not prove live
secret generation or persistence. Registry-only execution cannot emit a secret
observation.

## Hardened (seeded) declarations

A contract that carries `workload_step` uses the hardened shape of
`poc-test-v1` (AD-04). Its `secret_lifecycle.generation` is `rotation-seed`,
it has no `provider_refresh_actions`, and each reference adds `rotation`
(`{function_ref, schedule_days: 90}` or, for the interim KMS-bound purposes,
`non_rotatable`) and `value_kind`. Only `app_secret` and `oauth_encryption_key`
are rotated; no Redis or DocumentDB purpose may be declared (D-1). The
DocumentDB-managed secret is observed only, through
`central.documentdb_managed_secret_arn`, and keeps its service-managed
rotation. Every `function_ref` must name a key of
`central.rotation_function_arns`, and a missing central function or CMK makes
the contract invalid, so admission is refused before any read (NFR-07).

Every declared secret is encrypted by the runtime CMK: its `kms_key_arn` must
equal `central.cmk.runtime.arn`, and the runtime, JWT and 2FA CMK ARNs must be
pairwise distinct (D-4). The JWT or 2FA key, the `aws/secretsmanager` key or
any other key in the account is refused. `rotation.schedule_days` must be the
exact integer `90`.

For such a projection the program declares only `Secret` resources: no Random
or TLS generator and no `SecretVersion` (FR-09, NFR-01). Before its first
resource, `WorkloadPhaseStack` registers one guard for the whole stack, twice:
`pulumi.runtime.register_stack_transformation` reaches every resource the
program builds, whatever its parent (the workload owner, the registry and mail
resources, and root resources with no parent), and
`pulumi.runtime.register_resource_transform` lets the engine also reach the
children of a packaged component. The component-level transformation on the
secret, network and messaging planes stays as a second layer. The guard fails
the program on any Random, TLS or `SecretVersion` type and on any type outside
the closed allowlist of the hardened graph. `HARDENED_TYPES` is exactly the set
the hardened graph renders. S1.1 rendered nine tagged types (VPC, subnet, route
table, internet gateway, EIP, NAT gateway, security group, Secrets Manager
secret and SQS queue), four untagged or self-tagged types (route-table
association, ECR repository, Route 53 record and SES identity) and six
component tokens. S1.3 adds the data and compute planes: twelve tagged types
(log group, DocumentDB cluster, instance, cluster parameter group and subnet
group, ECS cluster, service and task definition, load balancer, listener,
target group and the ALB log bucket), seven untagged types (the ECR lifecycle
policy and the six ALB log bucket settings) and three component tokens (data
plane, compute plane and ALB access logs). ElastiCache stays outside it until
S1.4. `TAGGABLE_TYPES` only selects what the planes tag; it admits no type.
Widening the allowlist is a reviewed change.

The guard is type-level plus the listed property checks
(`HARDENED_PROPERTY_CHECKS`). The SES identity's `dkimSigningAttributes` may
hold only `nextSigningKeyLength`; a BYODKIM `domainSigningPrivateKey` or
selector fails before registration. The check reads both key casings:
snake_case on the SDK transformation path and camelCase on the engine path.
An opaque value, such as an input type or an `Output`, fails closed.

`WorkloadPhaseStack` also registers a deny-all engine invoke transform through
`pulumi.runtime.register_invoke_transform`. Its allowlist is empty: no hardened
module calls a provider function, and any call fails the program before the
provider runs it. A story that needs an invoke adds a reviewed allowlist.

S1.3 added property checks with the data and compute planes. A DocumentDB
`Cluster` must have `manageMasterUserPassword` literally true, no
`masterPassword` or `masterPasswordWo`, engine `docdb` and engine version
`5.0.0`. A `TaskDefinition`'s container definitions must hold only the
exact-case keys `ComputePlane` emits (`name`, `image`, `essential`, `command`,
`environment`, `secrets`, `portMappings`, `readonlyRootFilesystem`,
`mountPoints`, `linuxParameters`, `healthCheck`, `logConfiguration`). ECS
matches JSON keys case-insensitively, so a PascalCase key or two keys that
differ only in case fail. Environment rows are exactly `{name, value}` and
secret rows exactly `{name, valueFrom}`; environment names must not overlap
secret names. Every key and string leaf except `secrets[].valueFrom` must be
credential-free (no AWS access key, URL userinfo or credential query
parameter), so `command`, `image`, `healthCheck.command` and
`logConfiguration.options` are scanned too, and every `valueFrom` must be a
bare secret ARN. `ComputePlane` applies the same check when it serializes
(`require_plain_containers`), so both layers agree. The pre-hardening shape
keeps its version-pinned `valueFrom` (AD-25).

The task definition check inspects a JSON string and defers only a value it
cannot inspect yet. An SDK `Output` on the SDK transformation path is
deferred: it reaches the engine transform once the SDK serializes it. On the
engine path an unknown preview value is deferred, whether it arrives as a
preview `Unknown` or as an unknown, non-secret output value: a preview never
writes the definition, and the `up` that writes it sends the resolved string,
which the engine transform inspects. A known output value is inspected as its
string. Anything else fails as an unreviewed property: a secret-marked input
(`Output.secret(...)`, which reaches the engine as a secret map or a secret
output value), a map, a list or any other object. The task
volumes may only name ephemeral storage, so an FSx `credentialsParameter` or
Docker `driverOpts` fails. A `Listener` default action must not carry
`authenticate_oidc` in any casing, since its `clientSecret` is a secret
input, and an opaque action (an `Output`, a secret map, an `Unknown` or an
unreviewed input type) fails closed. A Secrets Manager `Secret` must not carry
an inline `policy` at any step: a resource policy joins only as the step-2
`SecretPolicy` (FR-34 B, AD-08). An ECS `Service` must not carry
`serviceConnectConfiguration`, whose log configuration has `secretOptions`.
An elastic DocumentDB cluster (`aws:docdb/elasticCluster:ElasticCluster`)
fails at every step (V-17). Redis joins in S1.4 with its own check:
ElastiCache carries no `authToken`.

Typed-input audit (S1.3, F-02): the args classes of every allowlisted type in
pulumi-aws 7.23.0, nested input types included, were searched for `secret`,
`password`, `token`, `private_key`, `client_secret` and `credential`. The
sensitive inputs found are the DocumentDB `masterPassword` and
`masterPasswordWo`, the task definition FSx `credentialsParameter`, the
listener OIDC `clientSecret`, the Service Connect `secretOptions` and the SES
`domainSigningPrivateKey`; each has a check above. The other hits carry no
secret material: OIDC `tokenEndpoint` is a URL, the SES DKIM `tokens` are
public DNS values, ECR `kmsKey` is a key ARN, the Secrets Manager
`forceOverwriteReplicaSecret` is a flag, and the S3, SQS and ECR `policy`
inputs are resource policies left to source review.

The guard is bound to the contract's `workload_step` (FR-34, AD-18). Step 1
refuses every step-2 type: the seed `Invocation`, `SecretRotation`,
`SecretPolicy`, autoscaling targets and policies, and `ScheduledAction`. Step 2
still refuses each one until its own story adds it to the allowlist; the
create-only step-2 admission is S4.9.

Residuals the guard does not inspect: free-form inputs of allowed types (for
example a secret description, a tag value, a queue policy or a DNS record
value), values passed to `pulumi.export` or `register_outputs`, which are not
resource inputs, and default-provider config. Review of the program source and
of the stack config remains the control for these. The listener OIDC
`clientSecret` and the container fields other than `environment` (`command`,
`image`, `healthCheck`, `logConfiguration` and the rest) are no longer
residuals: the checks above inspect them.

The stack that renders no hardened contract registers no such guard.

A seeded secret has no version until the seed runs. After that its identity is
preserved and a secret that had a current version keeps one; the version may
change, and that change is evidence only. The seed input is exactly
`{secret_arn, purpose}` for a rotated purpose
(`poc_secret_observation.validate_seed_input`); the ARN must fully match the
declared TEST name, account, region and partition. A contract without
`workload_step` keeps the pre-hardening shape and graph unchanged until the
topology story removes that branch (AD-25). Switching a workload contract
between the two shapes is refused; it would need a reviewed state migration.

Receipt schemas (`schemas/poc-workload-*-v1.schema.json`) are local shape only.
A Secrets Manager `VersionId` is the caller's `ClientRequestToken`: 32 to 64
characters of `[A-Za-z0-9-]`. AWS only recommends a UUID, so the schemas and
`validate_secret_observation` keep that charset and refuse the hex-256 value
shape it would otherwise admit. `secret_metadata` keys are the six declared
purposes plus `documentdb_primary`. A TEST receipt names only account
`891377212104` resources and the one gateway certificate parameter; the abandon
receipt is TEST-only (`urn:pulumi:test::`, mode `recovery-abandon`) and the
import receipt's mode is `recovery-import`. A schema cannot compare two values,
so the S4.11 receipt library must enforce that a retained secret's `import_id`
equals its `secret.arn`, and that no URN appears in both `deleted` and `retain`
of one abandon receipt. A PROD step receipt names only account `933245420672`
secret, KMS, image and certificate ARNs. JSON Schema `pattern` runs as
`re.search`, where `$` also matches before a trailing newline. A hardened
contract is therefore validated a second time with every schema pattern applied
by `re.fullmatch` (all `poc-test-v1` patterns are anchored), so no hardened
string field accepts a trailing newline. In the receipt schemas, fixed-length
fields pin their length, and the S4.11 library must re-check every
variable-length field with `re.fullmatch`.

V-8 (provider source): pulumi-aws 7.23.0 builds on terraform-provider-aws
v6.36.0 with no Secrets Manager patch. Reading `Secret` calls only
`DescribeSecret` and `GetResourcePolicy`, `SecretRotation` only
`DescribeSecret`, and `SecretPolicy` only `GetResourcePolicy`. Only
`SecretVersion` calls `GetSecretValue`, so it is never declared.

### ECS references resolve `AWSCURRENT` (F-02, FR-08)

For a hardened projection, `RuntimeSecrets.ecs_secrets()` sets each container
secret's `valueFrom` to the bare secret ARN: hardened declarations select no JSON
key. The validator also accepts `arn:<json-key>::`. ECS then resolves the `AWSCURRENT` version at task start, so a
rotated value needs only new tasks. `require_unversioned_reference` refuses any
reference with a version ID or staging label (`arn:::<id>`, `arn::AWSCURRENT:`)
and checks shape only. The exact-identity check is made by `ecs_secrets()`
(through `_current_references`): it fullmatches each reference against
`secret_arn_regex(...)` for the exact declared name in the deployment's own
account and region, with the six-character random suffix and ASCII digits only,
so a foreign, partial or look-alike ARN fails. A missing declaration fails the
inventory check. The pre-hardening
projection keeps its version-pinned references until S4.10 removes that branch.

The observed `AWSCURRENT` version is evidence only. For a seeded secret the
prior-receipt comparison uses the ARN and the name bound by that ARN: a rotation
may change `version_id`, a different ARN is a replacement and fails, and a secret
that had a current version cannot lose it. The generated (pre-hardening) shape
still requires the exact prior observation.

`_validate_secret_arn` in `poc_secret_observation.py` pins TEST through the
module constants `REGION` and `ACCOUNT_ID`, not the contract. S4.14's pin
inventory must include that use site.

This validator does not prove rotation provenance. AD-25 requires
`LastRotatedDate` later than the receipt, with rotation enabled by the reviewed
function; S4.10's result checker must prove that.

### DocumentDB primary password is DocumentDB-managed (S1.2, FR-01, A-05)

On the hardened path the DocumentDB cluster is declared with
`manage_master_user_password=True` and no `master_password`, so DocumentDB owns
and rotates the primary password in its own managed secret. Pulumi never holds
or generates it. A `documentDbPassword` (or `documentDbMasterPassword`) config
key is refused instead of being ignored. Since S1.3 the hardened
`WorkloadPhaseStack` composes the data plane under its stack-wide guard and
refuses that key itself, before any resource registers; `DataPlane` refuses it
again before its own registration. A native preview of the hardened workload
with a secret `documentDbPassword` fails without echoing its value. The
pre-hardening shape keeps its generated password until S4.10 removes that
branch (AD-25).

The application authenticates as the ECS task role with `MONGODB-AWS` (S1.3,
FR-02). `MONGODB_URL` is a plain environment value with no userinfo:
`mongodb://<endpoint>:<port>/<db>?tls=true&tlsCAFile=<ca>&replicaSet=rs0&readPreference=secondaryPreferred&retryWrites=false&authSource=%24external&authMechanism=MONGODB-AWS`,
with the database and CA path URL-encoded. No `document_db_url` secret exists
on the hardened path. IAM authentication exists only on instance-based
DocumentDB 5.0 clusters (V-17, from the AWS DocumentDB IAM identity
authentication guide, A-01), so `WorkloadPhaseStack` refuses any other engine
version beside the password refusal, before any resource registers, and the
data plane repeats that check. An elastic cluster fails the guard. The live
check is S4.6 step 4.

After step 1 the stack exports the XP-8 values in the contract's shape:
`lambda_network` (`subnet_ids`, the app subnets, and
`bootstrap_job_security_group_id`) and `documentdb_managed_secret_arn`. The
bootstrap-job security group has no ingress and egresses only inside the VPC,
to the DocumentDB port and to 443 for the Secrets Manager interface endpoint;
the DocumentDB security group admits it beside the service group. S3.3 and S3.4
narrow those egress rules to the endpoint and DocumentDB groups (FR-18). The
two CIDR egress rules are an interim: S3.4 replaces both with security-group
references and must update
`test_the_bootstrap_job_sg_reaches_documentdb_and_stays_in_the_vpc`.

Exception A-05 (D-4): pulumi-aws 7.23.0 exposes `manage_master_user_password`
and `master_user_secrets` but no `master_user_secret_kms_key_id`. The managed
secret therefore stays on the AWS-managed key `aws/secretsmanager`, not the
runtime CMK that encrypts the USI-declared secrets, and no
`master_user_secret_kms_key_id` is ever passed. The managed-password grants of
the apply role (S5.2, V-21) must be applied before step 1. The live check is
S4.6 step 4: `MasterUserSecret` active, rotation enabled, metadata only.
