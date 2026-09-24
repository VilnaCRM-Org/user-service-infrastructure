# TEST PoC desired contract

`poc-test.json` is the fixed desired-source path for the TEST registry phase.
It declares the two service-owned ECR repositories using the logical names in
`RegistryPlane`. It does not request ECS, networking, secrets or application
deployment.

The central references identify proposed source, not completed installation:

- `inventory_sha256` is the canonical hash of bootstrap's proposed
  `pulumi/seed/catalogs/poc-runtime-test.json` (local source commit `d41c019`).
- `seed_enrollment_revision` pins the proposed TEST policy catalog in bootstrap
  source commit `4a0bd14`, including the bounded ECR capability and bucket
  versioning read for preview, apply and scheduled drift. It is not evidence that
  those policies have been installed.
- The publisher role, workflow and environment are declared by that inventory.
  Registry creation does not establish their existence or activate image publishing.

The document remains `proposed-not-installed`. Its prerequisite strings are
descriptive and cannot authorize deployment. The trusted controller must verify
current review, account/backend identity, actual prior ownership and capability,
then validate and bind the saved plan before execution. Hashes and schema
validation alone do not admit an initial deployment.

After installation, runtime evidence must identify the actual policy revision
and role ownership. A later reviewed workload contract must reference its real
release and external inputs. Never substitute synthetic fixture values for
unresolved runtime evidence.

## Registry execution

The TEST self-deploy workflow authenticates the requested source in a separate
job, then passes its same-run artifact coordinates to the installed-main
`poc_registry_runner.py`. Runtime dependencies are installed before assuming AWS
credentials; execution disables dependency synchronization. The child program
uses the fixed registry implementation and authenticated contract data.

The initial migration preserves the existing stack exports, EnvironmentSettings
component and provider identity. Only the recorded three-resource TEST checkpoint
can use the legacy provider-hardening transition. The resulting eleven-resource
graph contains the original seven registry resources plus the SES identity and
three Easy DKIM DNS records, with no workload or service-owned IAM resources.
Unknown prior state or inaccessible repositories
fail admission.

Apply rechecks requester authorization, reviewed source, backend version and the
complete saved plan immediately before replay. Its postcondition requires the
complete graph. Post-apply drift uses the preview identity and requires every
resource operation to be unchanged. These source controls still require trusted
installation and live acceptance; this document does not claim either is complete.

The scheduled TEST and PROD jobs retain the installed main-only `make test-drift`
route. The candidate `poc_scheduled_registry_drift.py` diagnostic helper is not
connected to that workflow. Integrating it requires separate validation against
the installed controller; the TEST-only launcher does not accept scheduled jobs.
Diagnostic results cannot authorize initialization, a workload transition or
promotion.

Managed workload settings require explicit `executionRoleArn` and `taskRoleArn`
matching the protected account, project and environment. Compute consumes those
central identities and does not create ECS roles or policies. Their existence,
trust, effective permissions and PassRole authorization must still be verified
through the controller before enabling the workload phase.

The internal workload composition generates stable Random/TLS resources and
persists the ten declared secret purposes under their exact names and KMS keys.
Database and Redis connection strings use the same generated credentials as the
services. ECS receives eight distinct consumed secret references through nine
environment names, pinned to their versions. `REDIS_LOCKOUT_URL` explicitly uses
the same ARN and version as `REDIS_URL`; compiled application defaults do not
recompute that alias. SES uses task-role credentials; social OAuth is disabled.
This source path still needs authenticated secret-history checks and workload
dispatch admission before it can establish first-deployment or rollback acceptance.

The trusted runtime installs AWS 7.23.0, Random 4.19.2 and TLS 5.3.1 before AWS
credentials, using fixed archive and executable SHA-256 pins. Execution rechecks
those binaries and SDK versions, uses a private plugin home, and disables automatic
and ambient plugin acquisition. Installing these binaries does not add provider
resources to the registry graph.

## Release binding prerequisite

Every proposed workload release now declares three registry bindings:

- `registry_phase_receipt_id`: positive GitHub deployment ID, not an artifact ID.
- `registry_contract_digest`: SHA-256 of the complete canonical registry contract.
- `registry_checkpoint_version`: original opaque, non-null S3 checkpoint VersionId.

The existing contract transition validator compares the declared digest with the
supplied previous registry document. `validate_registry_release_binding` also
compares all three fields with a typed `RegistryReleaseBinding` supplied by a
trusted caller. This pure comparison authenticates neither the caller nor the
deployment, checkpoint, application publisher, image digest or secret history.
Updates and rollback retain the release's original registry anchor; it must not
be replaced with the current workload checkpoint version. Synthetic fixtures
remain offline examples and cannot establish deployment readiness.

The proposed `service-poc-phase-v1` receipt is not produced yet. Its next source
integration can reuse the existing `platform_promotion` job's protected
`governance-evidence` environment, trusted `github.sha` checkout and promotion App
deployment-write authority. It needs no new App or service IAM grant. Preserve
the current TEST+PROD promotion checks and status: a TEST registry result must
publish a distinct receipt and must never set full `Governance Promotion` success.

The concrete remaining producer/consumer work is:

1. Extend the trusted registry runner/result observer to retain bounded metadata
   for the exact final eleven-resource checkpoint and native ECR identities after
   saved apply and clean drift. Bind source/contract, plan, current checkpoint
   version/hash and original run/attempt; keep checkpoint bodies private.
2. Add a TEST-only result preparation/publication path beside
   `governance_promotion.py` that verifies the actual original workflow/jobs and
   immutable observation artifacts before using the existing protected App.
   Return the deployment ID only after payload/issuer/status readback succeeds.
3. Authenticate that deployment and its original run/artifact/checkpoint chain
   before constructing `RegistryReleaseBinding` in publisher/workload admission.
   Reuse the source artifact transport's bounded ZIP/strict metadata checks with
   explicit result member and completed-producer rules; its current in-progress
   `source.json` protocol is not completed registry evidence.
4. Authenticate the application manifest and both ECR images, then connect the
   existing workload component, generated configuration and secret-history checks
   to saved-plan/replay. Workflow selection remains registry-only until these
   checks are executable. No approval flag or phase-file edit replaces them.
