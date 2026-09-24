# CI Architecture

This repository keeps CI intentionally close to the local developer workflow.
Docker-backed pull request checks use the same Docker workspace and the same
`make` entrypoints that developers use locally.

## Design Principles

- local/CI parity over bespoke workflow-only commands
- short feedback loops for structural and unit checks
- explicit isolation for slower suites such as mutation testing
- safe defaults: least privilege, cancellable duplicates, bounded run time

## Workflow Matrix

| Workflow | Primary command | Purpose |
| --- | --- | --- |
| `pulumi-structural.yml` | `make test-pulumi` | Validates Pulumi metadata, workflow contracts, and Dockerfile safeguards |
| `pulumi-policy.yml` | `make test-policy` | Validates the Pulumi policy pack and AWS guardrail coverage |
| `pulumi-pr-guardrails.yml` | `make test-preview`, `make test-destructive-diff`, `make test-iam-validation` | Generates the PR preview artifact and enforces destructive/IAM guardrails |
| `security-scans.yml` | `make test-secrets`, `make test-deps-security`, `make test-bandit`, `make test-actionlint`, `make test-yaml`, `make test-dockerfile` | Runs blocking security and repo-hygiene checks plus GitHub dependency review |
| `codeql.yml` | GitHub-native | Scans Python code and workflow code with CodeQL |
| `python-quality.yml` | `make test-ruff`, `make test-ty`, `make test-maintainability`, `make test-architecture`, `make test-dependency-hygiene`, `make test-coverage` | Blocking Python quality, maintainability, architecture, dependency, and coverage gates |
| `pulumi-unit.yml` | `make test-unit` | Mock-based Pulumi component tests with full coverage |
| `pulumi-integration.yml` | `make test-integration` | Automation API lifecycle tests against a local file backend |
| `pulumi-mutation.yml` | `make test-mutation` | Mutation analysis of the Pulumi component layer |
| `bats-tests.yml` | `make test-cli` | CLI contract tests for the Makefile interface |
| `pulumi-local.yml` | `make ci-pr` | Non-mutation PR-equivalent battery inside Docker |
| `nightly-quality.yml` | `make report-quality` | Publishes maintainability, dead-code, docstring, and SBOM reports |
| `nightly-guardrails.yml` | `make test-drift` | Runs scheduled drift detection and repository-health checks |

## Shared Controls

### Prepared Docker Context

Docker-backed CI workflows call `make start` before running checks. GitHub-native
jobs such as CodeQL, Dependency Review, and Scorecard do not invoke it because
they do not run inside the repository Docker workspace. For the Docker-backed
jobs, `make start` standardizes the expected local state:

- creates `${HOME}/.aws` with restrictive permissions
- materializes `.env` from `.env.empty` when needed
- enforces owner-only permissions on `.env`
- prepares the `.pulumi-backend` directory used by local-backend test flows
- starts the Compose service so later `make` targets share the same prepared workspace

The default Compose service does not mount `${HOME}/.aws` into the container.
Use `ENABLE_AWS_CREDENTIALS=1` only for commands that intentionally need shared
AWS config or host-exported `AWS_*` variables inside Docker.

Centralizing the setup keeps workflows consistent and reduces drift between
checks.

### Concurrency

Every pull-request-oriented validation workflow uses a concurrency group based on
the workflow name and PR number or ref. That prevents multiple stale runs from
contending on the same branch after rapid pushes.

### Timeouts

Every CI job declares `timeout-minutes`. Fast suites fail fast; slower suites
such as mutation testing and the full local battery are allowed more time but
still remain bounded.

### Minimal Permissions

Validation workflows use `contents: read`. Release and synchronization workflows
ask for broader access only where automation actually needs to write tags,
releases, or pull requests.

## Trusted PoC provider runtime

The TEST PoC setup action installs AWS 7.23.0, Random 4.19.2 and TLS 5.3.1
before AWS credentials are acquired. The installed trusted source fixes each
release URL, archive SHA256 and executable SHA256, and checks the frozen SDK
versions. Provider installation uses a fresh private `.trusted/.poc-provider-runtime`
directory; a partial or existing cache is rejected.

Before Pulumi dispatch, the runner verifies the provider executables again and
passes that fixed `PULUMI_HOME` to the CLI. Automatic plugin acquisition and
ambient plugin lookup are disabled. A missing or modified provider fails the run;
it must be repaired in the trusted runtime rather than downloaded with deployment
credentials. Installing the Random/TLS binaries does not activate the internal
workload phase or change registry resource ownership.

## TEST registry completion proof

The completion helpers remain candidate code. The installed controller has no
`test_registry_observation`, `test_registry_proof` or `test_registry_dispatch`
jobs; it cannot publish completion receipts or dispatch image publishing. The
following describes the proposed integration, which requires separate validation
before installation.

After successful TEST registry apply and drift jobs, the proposed
`test_registry_observation` starts on a fresh trusted-main checkout. It
authenticates source, current review
and requester before each credential transition. With the existing Preview
identity it performs version-bound backend reads, validates the exact eleven-resource
graph, and checks both repositories' native immutability, scanning and tags plus
the owned SES identity and three Easy DKIM CNAME records. SES verification may
remain pending here; workload admission requires native verification success.
It runs no PR program or Pulumi child. Only public metadata is uploaded;
checkpoint contents stay private.

`test_registry_proof` runs in the existing main-only `governance-evidence`
environment. It validates source/observation artifact IDs, archive/file hashes,
producer run/attempt/repository/head, successful apply/drift/observer jobs and
observation/upload times. It rechecks requester and review before creating a
`registry-proof` deployment in `poc-test-registry` with the existing promotion
App and only `deployments:write`. The ordinary job token handles reads. Deployment
and latest success status must match the configured App ID and slug. This path
never writes `Governance Promotion` or TEST/PROD full-promotion records.
Time containment comparisons use GitHub's second precision; the authenticated
observation retains its original full timestamp.

`poc_registry_completion.verify_completion` validates the original completed
producer chain using caller-pinned issuer, trusted workflow revision and registry
contract. It returns deployment ID, registry contract digest and observed S3
version. Historical verification does not require the old PR to remain current;
expired or missing artifacts fail closed. Source artifacts currently retain seven
days, which also bounds this verifier's evidence lifetime. The receipt is an
observation anchor, not a fresh AWS check or an atomic lock.

These source changes need deployment and native acceptance before consumers rely
on them. They do not activate image publishing/workloads, prove image availability,
or replace the execution-isolation boundary below.

## Isolated service execution

The installed TEST controller remains closed: preflight fails and all execution
jobs have explicit false guards pending complete controller validation. Its
TEST registry jobs use the installed-main `service_execution_host.py` launcher.
PROD and registry-completion routes are absent. Scheduled drift retains the
existing main-only `make start` / `make test-drift` path; it does not call the
TEST-only launcher. The launcher builds the existing pinned tooling
and locked dependencies before configuration credentials or execution OIDC.
Credentialed jobs no longer execute PR Makefiles, Dockerfiles or dependency setup.
Runtime/dependency upgrades must first be reviewed and installed on trusted main;
unsupported project runtimes and discovery overrides fail before credentials.

The ephemeral worker runs trusted Python as root PID 1 with read-only root,
trusted-source and public-result mounts. Reviewed PR source is not mounted.
Pulumi, including login, stack selection,
export and policy execution, runs as UID 2000 without supplementary groups.
The child receives only its selected AWS session and fixed runtime configuration;
GitHub tokens, OIDC request tokens and Actions command files stay outside its
environment. The container has no host Docker socket. Root-owned configuration
and replay-plan copies are readable but cannot be replaced by the child. Plugins
and runtime paths remain immutable; only private workspaces and result paths are
writable. The process runner kills detached UID-2000 descendants before returning
to native checks, even after a failed command or timeout.

The trusted parent retains the existing requester/review, provider/checkpoint,
saved-plan hash/age, destructive-change and TEST registry graph checks. Admission
is refreshed immediately before each preview or apply program and after execution.
Only the existing plan, preview and manifest artifacts leave the private worker.
The registry completion observer/publisher helpers remain unconnected.

The TEST-only source prerequisite still blocks PROD promotion, and no workload
phase is admitted by this change. Network-disabled Docker tests prove the local
UID/filesystem/process boundary with synthetic state; they do not establish
hosted OIDC, cloud deployment or workload acceptance. Installation and current-head
TEST/PROD evidence remain required before issue 185 can be considered complete.

## Local Parity

The repository intentionally avoids workflow-only logic for the core validation
battery.

- `make test` is the fast inner-loop command for the prerequisite sanity check, Pulumi structural tests, policy, quality, repo hygiene, unit, integration, coverage, and CLI checks.
- `make ci-pr` matches the non-mutation GitHub pull-request battery, including preview and security guardrails.
- `make ci` is the full local superset, including the dedicated mutation suite.
- `make report-quality` mirrors the scheduled quality-report workflow locally.
- `make start` prepares the Docker-backed workspace before CI-style checks or manual Docker sessions.
- `make doctor` provides a quick prerequisite check before developers start
  debugging Docker or Pulumi behavior.

If you add a new CI check, prefer adding a Make target first and making GitHub
Actions call that target.

## Adding a New Workflow

Use this checklist:

1. add or reuse a Make target
2. keep the workflow on pinned actions
3. define `permissions`
4. add `concurrency`
5. set `timeout-minutes`
6. call `make start` if the job uses the Docker workspace
7. extend the structural tests and docs in the same PR

## Failure Triage

When a PR check fails:

1. reproduce with the matching local Make target
2. run `make doctor` if the failure looks environment-related
3. inspect the workflow job log only after the local path is understood
4. fix the underlying contract rather than weakening the check

CodeQL, GitHub Dependency Review, artifact attestations, and Scorecard remain
GitHub-native workflows. The repository keeps their definitions under
structural test coverage, but they are not reproduced inside the local Docker
battery.
