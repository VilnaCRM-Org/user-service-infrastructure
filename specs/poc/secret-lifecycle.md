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

Hard stop: the current source pins secret versions and has no rotation. The
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

For such a projection the program declares only `Secret` resources: no Random
or TLS generator and no `SecretVersion`, and a transformation fails the program
if either is added (FR-09, NFR-01). A seeded secret has no version until the
seed runs; after that its identity and first version are preserved. The seed
input is exactly `{secret_arn, purpose}` for a rotated purpose
(`poc_secret_observation.validate_seed_input`). A contract without
`workload_step` keeps the pre-hardening shape and graph unchanged until the
topology story removes that branch (AD-25). Switching a workload contract
between the two shapes is refused; it would need a reviewed state migration.

### ECS references resolve `AWSCURRENT` (F-02, FR-08)

For a hardened projection, `RuntimeSecrets.ecs_secrets()` sets each container
secret's `valueFrom` to the bare secret ARN, or to `arn:<json-key>::` when a JSON
key is selected. ECS then resolves the `AWSCURRENT` version at task start, so a
rotated value needs only new tasks. `require_unversioned_reference` refuses any
reference with a version ID or staging label (`arn:::<id>`, `arn::AWSCURRENT:`),
and a missing declaration fails the inventory check. The pre-hardening
projection keeps its version-pinned references until S4.10 removes that branch.

The observed `AWSCURRENT` version is evidence only. For a seeded secret the
prior-receipt comparison uses the ARN and the name bound by that ARN: a rotation
may change `version_id`, a different ARN is a replacement and fails, and a secret
that had a current version cannot lose it. The generated (pre-hardening) shape
still requires the exact prior observation.

V-8 (provider source): pulumi-aws 7.23.0 builds on terraform-provider-aws
v6.36.0 with no Secrets Manager patch. Reading `Secret` calls only
`DescribeSecret` and `GetResourcePolicy`, `SecretRotation` only
`DescribeSecret`, and `SecretPolicy` only `GetResourcePolicy`. Only
`SecretVersion` calls `GetSecretValue`, so it is never declared.

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
