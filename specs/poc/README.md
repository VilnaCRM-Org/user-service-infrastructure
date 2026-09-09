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
can use the legacy provider-hardening transition. The resulting seven-resource
graph contains two ECR repositories and their component records, with no workload
or service-owned IAM resources. Unknown prior state or inaccessible repositories
fail admission.

Apply rechecks requester authorization, reviewed source, backend version and the
complete saved plan immediately before replay. Its postcondition requires the
complete graph. Post-apply drift uses the preview identity and requires every
resource operation to be unchanged. These source controls still require trusted
installation and live acceptance; this document does not claim either is complete.

The scheduled TEST job uses a separate diagnostic entrypoint. It verifies the
native GitHub schedule run and current main revision before AWS configuration,
then uses the central Drift identity to check the complete seven-resource graph.
Missing or partial state fails before preview. A successful no-change result is
diagnostic only: it cannot authorize initialization, a workload transition or
promotion. The scheduled PROD route remains outside this TEST registry change.

Managed workload settings require explicit `executionRoleArn` and `taskRoleArn`
matching the protected account, project and environment. Compute consumes those
central identities and does not create ECS roles or policies. Their existence,
trust, effective permissions and PassRole authorization must still be verified
through the controller before enabling the workload phase.
