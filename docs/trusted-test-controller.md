# Trusted TEST registry controller

**Disabled installation candidate.** Preflight exits before AWS credentials, and
source/TEST jobs have unconditional false guards. Local native graph, saved-plan
replay, and aggregate coverage gates pass. Independent review and a live TEST
capability/backend audit remain required before enabling any job.

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

- Official unit gate: 1,576 passed, 5 skipped; 100% required coverage.
- Official policy gate: 249 passed; 100% required coverage.
- Official integration gate: 24 passed; 100% required coverage. The pinned native
  AWS provider validates the fixed registry/SES/DNS graph, replays its saved plan,
  checks readiness changes, and completes a no-change refresh using synthetic
  credentials and loopback endpoints.
- Official aggregate gate: 5,406 statements and 1,604 branches, none missing or
  partial; 100% coverage.
- The explicit worker container smoke passed separately, including real Pulumi
  preview and saved-plan replay with a local backend, UID 2000 isolation, root-only
  authority, protected files, and descendant cleanup.
- Ruff check/format, Actionlint, YAML lint, Hadolint, Bandit, dependency hygiene, and
  all ten import contracts passed. Bandit emitted existing suppression warnings.
- The base and worker images built successfully from the candidate lockfile and
  verified provider archives. No existing containers or networks were removed.

The original native preview timeout came from provider account discovery calling
IAM `GetUser`, which the synthetic fixture had not mapped to loopback. Adding that
fixed synthetic response resolves the timeout without changing production provider
settings or increasing the 90-second fixture timeout. The test asserts that account
discovery occurred and uses saved-plan replay for the registry update.

Docker's default address pools are exhausted on the validation host. The official
gates pass using a local, ignored Compose override that disables networking and
selects the locally built worker image with its verified provider archives:

```yaml
services:
  pulumi:
    network_mode: none
    image: trusted-test-controller-20260923-worker
    environment:
      UV_NO_SYNC: "1"
      POC_TEST_PROVIDER_HOME: /opt/service-plugins
```

Save that override as `.artifacts/controller-validation/compose-offline.yml`, then
run each of `test-unit`, `test-policy`, `test-integration`, and `test-coverage` with:

```sh
make COMPOSE_ENV_FILE=.env.empty \
  DOCKER_COMPOSE='docker compose -f docker-compose.yml -f .artifacts/controller-validation/compose-offline.yml' \
  test-coverage
```

Per-suite coverage files remain separate until the aggregate gate combines them.
Generated native-test entrypoints preserve source attribution through the existing
trusted coverage bootstrap only when the official gate explicitly requests it.
Retained local logs are in `.artifacts/controller-validation/` (ignored by Git).

Keep the workflow guards until independent review and separate verification of live
TEST capability enrollment, protected environments, OIDC configuration, backend
state, and exact legacy checkpoint compatibility are complete. No AWS acceptance
is claimed, and no AWS state was changed.
