# Trusted TEST registry controller

**Disabled installation candidate.** Preflight exits before AWS credentials, and
source/TEST jobs have unconditional false guards. Native registry graph validation
and the aggregate coverage gate must pass before removing these guards.

This candidate replaces legacy PR execution with a fixed TEST registry and SES/DNS
graph. It is extracted from PR #19 commit
`01fc0af038241bbb78225c1697078902e139fb25` onto stage-one boundary commit
`1a9fbb73996ac2c20c6cf66678f80936d8f1909f` (main baseline `e246187`).

The command intake remains unchanged. Only an open PR with the admitted head and
base, current independent human review, effective main protections, and an
unchanged authorized requester can proceed. Apply retains the `test` protected
environment and independent requester/approver rule. These checks repeat before
configuration credentials, execution credentials, each Pulumi program invocation,
saved-plan replay, and publication of preview artifacts.

No job checks out or executes PR Python, Makefiles, project hooks, policy packs,
Dockerfiles, or shell code. A trusted source adapter reads only the bounded contract
blob from the exact PR head and publishes immutable same-run source facts. The
controller authenticates source artifact IDs, archive/content digests, producer run,
workflow revision, repository identity, and the installed schema/validator.

Only installed main selects the runtime, graph, account, backend, KMS provider,
provider versions, and checksums. The graph contains the retained root/environment
metadata, two immutable ECR repositories, one SES identity for
`user.vilnacrmtest.com`, and exactly three provider-derived DKIM CNAMEs in the fixed
TEST hosted zone. Existing resources must match the closed graph. The one permitted
legacy provider hardening transition is bound to the exact recorded checkpoint
resource digest; unrelated state is rejected.

The root verifier runs as PID 1 in a read-only container. Pulumi and policy children
run as UID/GID 2000 without GitHub or Actions authority. Protected configuration and
saved plans are root-owned; tools and provider binaries are read-only. Detached
children are killed before verifier rechecks. Docker sockets and PR source are not
mounted. Worker logs stay private and public output is a fixed success/failure
message plus authenticated plan/preview artifacts.

Preview records the saved-plan hash, preview hash, head, backend, KMS key, provider
configuration, and checkpoint version/ETag. Apply rechecks those identities and the
full old/desired/preview resource semantics immediately before replay. No direct
apply, destructive override, plugin acquisition, or shared-stack initialization is
available. Post-apply drift requires the complete expected graph and rejects
resource changes. AWS credentials are temporary sessions from the existing
configuration-reader and preview/apply/drift OIDC roles.

PROD, workload execution, registry-completion proofs, publisher dispatch, and
promotion are absent from this controller. The existing main-only initialization
and scheduled baseline drift workflows are outside this change. Successful
registry execution is not workload release authority.

## Installation prerequisites

Install the entire reviewed dependency closure atomically on main; new commands
must reference that installed base. Never cherry-pick only the workflow enablement.
Governance must already provide the TEST S3/KMS backend, initialized stack, protected
environments, configuration variables and OIDC roles, plus the reviewed ECR and
SES/Route53 capabilities. Verify live role policies and state separately before
using the controller. This local candidate does not establish live AWS acceptance.

Offline validation uses `tests/unit/test_service_execution_native.py` with an
explicit locally built worker image and networking disabled. The native AWS
provider integration test uses synthetic credentials, a local backend, and only
loopback AWS endpoints; it is not a deployment rehearsal against AWS.

## Local validation on 2026-09-23

- All unit tests: 1,572 passed, 5 skipped. The explicit worker container smoke was
  run separately and passed; its preview and saved-plan replay use a local backend.
- Unit-only coverage: 85% across 5,373 statements; this does not satisfy the required
  aggregate 100% gate. `make test-coverage` could not start its Compose container:
  Docker reported that all predefined address pools had been fully subnetted.
- Pinned native AWS-provider integration: failed on initial registry preview after
  90 seconds and again after 180 seconds. The Pulumi Python child remained CPU-bound
  inside a `--network none` container. The synthetic baseline update completed,
  but native registry/SES/DNS preview semantics remain unverified for this candidate.
- Ruff check/format, Actionlint, YAML lint, Hadolint, Bandit, dependency hygiene, and
  all ten import contracts passed. Bandit emitted existing suppression warnings.
- The base and worker images built successfully from the candidate lockfile and
  verified provider archives. `make start` hit the same exhausted Docker network
  pool; no existing containers or networks were removed.

Do not remove the workflow guards until the native graph failure is understood,
positive/negative native plan and replay checks pass, and the repository aggregate
coverage gate passes. Live TEST capability enrollment, protected-environment and
OIDC configuration, backend state, and exact legacy checkpoint compatibility require
separate verification. No AWS acceptance is claimed, and no AWS state was changed.
