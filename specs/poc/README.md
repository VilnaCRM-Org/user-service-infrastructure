# TEST PoC desired contract

`poc-test.json` is the fixed desired-source path for the TEST registry phase.
It declares the two service-owned ECR repositories using the logical names in
`RegistryPlane`. It does not request ECS, networking, secrets or application
deployment.

The central references identify proposed source, not completed installation:

- `inventory_sha256` is the canonical hash of bootstrap's proposed
  `pulumi/seed/catalogs/poc-runtime-test.json` (local source commit `d41c019`).
- `seed_enrollment_revision` pins the proposed TEST policy catalog in bootstrap
  source commit `f420851`, including the bounded ECR capability and bucket
  versioning read. It is not evidence that those policies have been installed.
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
