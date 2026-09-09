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
