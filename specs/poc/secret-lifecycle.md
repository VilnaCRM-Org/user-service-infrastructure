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
the hardened graph renders: nine tagged types (VPC, subnet, route table,
internet gateway, EIP, NAT gateway, security group, Secrets Manager secret and
SQS queue), four untagged or self-tagged types (route-table association, ECR
repository, Route 53 record and SES identity) and the six component tokens.
`TAGGABLE_TYPES` only selects what the planes tag; it admits no type. Widening
the allowlist is a reviewed change.

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

When the data and compute planes rejoin the hardened graph (S1.3, S4.10), that
story widens the allowlist with property checks of its own: DocumentDB
`manageMasterUserPassword` must be true with no `masterPassword` or
`masterPasswordWo`; ElastiCache carries no `authToken`; and TaskDefinition
environment names must not overlap the declared secret names.

Residuals the guard does not inspect: free-form inputs of allowed types (for
example a secret description, a tag value, a queue policy or a DNS record
value), values passed to `pulumi.export` or `register_outputs`, which are not
resource inputs, and default-provider config. Review of the program source and
of the stack config remains the control for these.

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
key raises on that path instead of being ignored. The pre-hardening shape keeps
its generated password until S4.10 removes that branch (AD-25).

Exception A-05 (D-4): pulumi-aws 7.23.0 exposes `manage_master_user_password`
and `master_user_secrets` but no `master_user_secret_kms_key_id`. The managed
secret therefore stays on the AWS-managed key `aws/secretsmanager`, not the
runtime CMK that encrypts the USI-declared secrets, and no
`master_user_secret_kms_key_id` is ever passed. The managed-password grants of
the apply role (S5.2, V-21) must be applied before step 1. The live check is
S4.6 step 4: `MasterUserSecret` active, rotation enabled, metadata only.
