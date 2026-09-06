# User Service Infrastructure

[![SWUbanner](https://raw.githubusercontent.com/vshymanskyy/StandWithUkraine/main/banner2-direct.svg)](https://supportukrainenow.org/)

[![Pulumi Unit Tests](https://github.com/VilnaCRM-Org/user-service-infrastructure/actions/workflows/pulumi-unit.yml/badge.svg)](https://github.com/VilnaCRM-Org/user-service-infrastructure/actions/workflows/pulumi-unit.yml)
[![Pulumi Integration Tests](https://github.com/VilnaCRM-Org/user-service-infrastructure/actions/workflows/pulumi-integration.yml/badge.svg)](https://github.com/VilnaCRM-Org/user-service-infrastructure/actions/workflows/pulumi-integration.yml)
[![Pulumi Structural Tests](https://github.com/VilnaCRM-Org/user-service-infrastructure/actions/workflows/pulumi-structural.yml/badge.svg)](https://github.com/VilnaCRM-Org/user-service-infrastructure/actions/workflows/pulumi-structural.yml)
[![Pulumi Policy Tests](https://github.com/VilnaCRM-Org/user-service-infrastructure/actions/workflows/pulumi-policy.yml/badge.svg)](https://github.com/VilnaCRM-Org/user-service-infrastructure/actions/workflows/pulumi-policy.yml)
[![Pulumi PR Guardrails](https://github.com/VilnaCRM-Org/user-service-infrastructure/actions/workflows/pulumi-pr-guardrails.yml/badge.svg)](https://github.com/VilnaCRM-Org/user-service-infrastructure/actions/workflows/pulumi-pr-guardrails.yml)
[![Pulumi Mutation Tests](https://github.com/VilnaCRM-Org/user-service-infrastructure/actions/workflows/pulumi-mutation.yml/badge.svg)](https://github.com/VilnaCRM-Org/user-service-infrastructure/actions/workflows/pulumi-mutation.yml)
[![CLI Tests](https://github.com/VilnaCRM-Org/user-service-infrastructure/actions/workflows/bats-tests.yml/badge.svg)](https://github.com/VilnaCRM-Org/user-service-infrastructure/actions/workflows/bats-tests.yml)
[![Python Quality Checks](https://github.com/VilnaCRM-Org/user-service-infrastructure/actions/workflows/python-quality.yml/badge.svg)](https://github.com/VilnaCRM-Org/user-service-infrastructure/actions/workflows/python-quality.yml)
[![Security Scans](https://github.com/VilnaCRM-Org/user-service-infrastructure/actions/workflows/security-scans.yml/badge.svg)](https://github.com/VilnaCRM-Org/user-service-infrastructure/actions/workflows/security-scans.yml)

Pulumi-based infrastructure repository for the VilnaCRM user service, with a
Docker workspace, policy-pack guardrails, and CI checks aligned with the shared
infrastructure template.

## Possibilities

- Pulumi (Python) starter that exports environment metadata and tagging helpers.
- Reproducible Docker Compose workspace with a Pulumi-ready container and helper `make` tasks.
- CI pipelines for structural, policy, preview, security, unit, integration, mutation, and CLI-level checks.
- Release and template-sync automations to keep downstream repos aligned.
- Documentation on AWS credential management for secure automation using GitHub OIDC and short-lived credentials.

## Why You Might Need It

Operate the user-service infrastructure without rewiring every guardrail by hand. This repository gives DevOps teams a single source that:

- Encodes best practices from VilnaCRM’s production stack.
- Works out-of-the-box with AWS and Pulumi.
- Keeps infrastructure changes reviewable with local Pulumi previews, policy-pack guardrails, and CI test suites before deploying.

## License

This software is distributed under the [Creative Commons Zero v1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/deed) license. Please read [`LICENSE`](LICENSE) for details.

## Documentation

All project docs live under `docs/` to keep everything version controlled. Start with the handbook and jump directly to common topics:

- [Quick Start](docs/README.md#quick-start)
- [Local Tooling](docs/README.md#local-tooling)
- [Development Environment](docs/README.md#development)
- [PyCharm Autocomplete](docs/pycharm-autocomplete.md)
- [CI/CD and Secrets](docs/README.md#cicd-and-secrets)
- [CI Quality Gates](docs/ci-quality-gates.md)
- [CI Guardrails](docs/ci-guardrails.md)
- [CI Architecture](docs/ci-architecture.md)
- [Security Baseline](docs/security-baseline.md)
- [Pulumi Guardrails](docs/pulumi-guardrails.md)
- [uv and Rust-native Python tooling](docs/uv-rust-python-tooling-plan.md)
- [SRE Operations](docs/sre-operations.md)
- [Testing and Validation](docs/README.md#testing-and-validation)
- [Security](docs/README.md#security)
- [Contributing](docs/README.md#contributing)
- [Sponsorship](docs/README.md#sponsorship)

Community Q&A lives under the [`vilnacrm` tag on Stack Overflow](https://stackoverflow.com/questions/tagged/vilnacrm). For questions or feature requests, open an issue.

## Local Pulumi test suites

Docker Compose CLI 2.24.0+ is required because `docker-compose.yml` uses the
`env_file.required` flag (older Compose releases fail to parse it).

## Environment files

The Makefile resolves the effective env file as the first existing file from
`.env` and `.env.empty`.

- `.env` is git-ignored and should hold local secrets or developer-specific overrides.
- `.env.empty` is committed and acts as the minimal fallback so Docker Compose and `make` targets still run in a fresh clone.
- `.env.dist` remains an optional example/template file you can copy from when you want a fuller starting point; unlike `.env.empty`, it is not the automatic fallback used by the Makefile.

For onboarding, create or update `.env` with any local overrides you need, keep
`.env.empty` safe to commit, and refresh `.env.dist` only when the example
values or documented setup flow changes.

If you want a local `uv` environment outside Docker, seed it once so Pulumi's
Automation API can still use `pip` for package discovery:

```sh
export UV_PROJECT_ENVIRONMENT="${HOME}/.venvs/user-service-infrastructure"
uv venv --seed "${UV_PROJECT_ENVIRONMENT}"
uv sync --all-groups
```

The Docker workspace already ships with an isolated seeded environment outside
the bind-mounted repository tree, so the `make` targets remain the recommended
way to run the different Pulumi-focused suites (see `docker-compose.yml` for
the canonical workspace layout):

```sh
# Build the dev image used by the local and CI batteries
make build

# Configuration validation
make test-pulumi

# Rust-based quality gates
make test-quality

# Pulumi policy and guardrail validation
make test-policy

# Unit tests (pure Pulumi runtime with mocks)
make test-unit

# Automation-based integration tests
make test-integration

# Mutation analysis (time-consuming)
make test-mutation
```

Use the local batteries that match the scope of your change:

- `make test` runs the faster structural, policy, quality, repo-hygiene, unit, integration, coverage, and CLI battery.
- `make test-security` and `make test-guardrails` focus on infrastructure safety controls.
- `make ci-pr` mirrors the non-mutation GitHub pull-request battery before merge.
- `make ci` runs the full local superset, including the prerequisite check, image build, preview guardrails, security scans, and mutation suite.
- `make report-quality` generates the scheduled Wily, Vulture, docstring-coverage, and SBOM reports locally.

If Pulumi provider plugin downloads hit GitHub rate limits during local preview
or drift commands, pass `GITHUB_TOKEN="$(gh auth token)"` explicitly to that
single Make invocation instead of exporting it globally.

Run `make doctor` when you need a fast prerequisite check before debugging local
Docker or Compose behavior.

`make pulumi-preview` and `make pulumi-up` automatically enable the repository
policy pack. If the shared `uv` environment inside the container is missing
core Pulumi Python dependencies, the bootstrap helper resyncs it from
`uv.lock` before Pulumi starts. The policy runtime is refreshed separately in
`policy/.venv` from `policy/requirements.txt` so Pulumi starts the policy pack
consistently in Docker, CI, and local shells. The interactive Pulumi targets
also log into the configured backend automatically, falling back to the local
file backend under `.pulumi-backend/` when no shared backend is configured,
select the first committed `Pulumi.<stack>.yaml` file by default, and expect
shared backends to use an AWS KMS-backed secrets provider instead of a
passphrase-managed stack secret flow.

The default Docker service is intentionally credential-light. When a local
command needs shared AWS config from `~/.aws` or host-exported `AWS_*`
variables, opt in explicitly with `ENABLE_AWS_CREDENTIALS=1`, for example:

```sh
ENABLE_AWS_CREDENTIALS=1 make pulumi-preview
```

## Security

Please disclose any vulnerabilities found responsibly – report security issues to the maintainers privately.


## Service infrastructure scaffold

Generate a complete repository from the bootstrap repository root:

```sh
uv run python scripts/scaffold_infrastructure_repository.py \
  --repository user-service-infrastructure \
  --destination /tmp/new-user-service-infrastructure
```

The destination must not exist. The generator never merges into or overwrites an
existing service repository. Review the generated files before publishing them.
Copying this template directory alone is insufficient: the generator includes the
pinned Docker runtime, frozen `uv.lock`, shared Python helper closure, local CI
configuration action, policy pack, Make targets, authenticated comment intake,
and saved-plan runner. `scaffold-manifest.json` records every generated file hash,
the project name, CLI pin and initial capability limit. Keep the manifest with the
reviewed onboarding artifact; it records generation, not future repository edits.

The baseline exports configuration metadata only. Governance owns its S3 backend,
KMS key, config secrets and OIDC roles. Operator-owned `github-ci-bootstrap`
provisions the immutable permission boundary. Deploying
actual service workloads requires separately reviewed capability and boundary
changes. Catalog membership grants no general AWS infrastructure authority.

## Governed TEST and PROD deployment

Before granting privileges, create or inspect the actual service GitHub repository
and pin its immutable repository ID and owner ID in the governance catalog. Never
replace these identities with name-only trust. Then provision the catalog entry and bootstrap
boundary inventory in both accounts. Configure the service repository variables
from governance `githubVariables`, including independent `AWS_TEST_ACCOUNT_ID`
and `AWS_PROD_ACCOUNT_ID` pins. Create protected `test`, `prod`, `test-preview`
and `prod-preview` environments with Kravalg as sole reviewer, self-review
prevention, administrator bypass disabled, and exactly one custom deployment
rule for the `main` branch. Verify the separate deployment branch-policy API;
"Protected branches only" can allow every branch. CODEOWNERS covers every file.
Service applies trust `test` or `prod`; the central governor's `governance`
environment belongs to the bootstrap repository.

Provision a dedicated evidence GitHub App installed only on this service
repository. Grant statuses/deployments write and actions/contents/pull-requests
read, with no AWS or repository-administration permission. Store its signing key
as `GOVERNANCE_PROMOTION_APP_PRIVATE_KEY` only in the `governance-evidence`
environment, restricted to exactly the `main` branch with no tags or administrator
bypass. This environment needs no reviewer gate; it only publishes results from
the protected jobs. Set `GOVERNANCE_PROMOTION_APP_ID` and
`GOVERNANCE_PROMOTION_APP_SLUG`, and bind the required `Governance Promotion`
status to that App ID. Preserve code-owner review, current-push approval, stale
review dismissal, all required CI checks, and test/prod deployment requirements.
Use a separate App key per repository to keep signing authority isolated.

Publish the reviewed scaffold to trusted `main`, then dispatch **Initialize
Service Stack** once for `test` and once for `prod`, approving the corresponding
protected environment. It verifies the pinned project, CLI, account, backend and
KMS provider. A successful project-scoped stack listing must confirm absence
before `stack init`; existing stacks are selected, and API/authorization errors
fail closed. Initialization never runs the Pulumi program or any resource update.
Its receipt records the trusted SHA and whether it created backend stack metadata.

After initialization, open a same-repository PR and comment `/pulumi test plan`,
`/pulumi test up`, `/pulumi prod plan` or `/pulumi prod up`. Maintainers can request
plans; protected environment approval remains required before credentials are
issued. Commands bind the original unedited comment, intake run, current PR SHA,
current permissions and immutable request artifact. A prod plan does not apply
test. Prod up requires the same-run successful test saved-plan apply and drift,
then a production saved-plan apply and drift. The service runtime has no IAM
Access Analyzer grant; local policy and destructive-diff gates still run.
The trusted final publisher validates both saved-plan artifacts and all apply
and drift results before recording deployments on the exact PR head. It carries
the original comment, intake run and base SHA in the evidence. Failed, skipped,
test-only and plan-only runs cannot publish promotion success.

`make start` builds the pinned local runtime. Every workflow Make target exists
in the generated checkout; OIDC session variables are forwarded only to the
container at execution time. No static credential file or value is generated.
The test account is 891377212104, production is 933245420672, in eu-central-1.

Apply comments and Initialize Service Stack dispatches must be requested by a
maintainer other than sole environment reviewer Kravalg. Kravalg approves the
protected environment; the original apply commenter cannot also be the approver.

## Existing template compatibility

The original development metadata component and its four exports remain intact.
Local integration fixtures use disposable, credential-free file state only for
stub resources; they do not provide authoritative TEST or PROD state. Shared
stacks require the governance-owned S3 backend, AWS KMS provider and temporary
OIDC credentials. No shared passphrase or Pulumi Cloud token is configured.

The old direct-PR `AWS_OIDC_ROLE_ARN` jobs and generic nightly cloud drift job
are retired. Ordinary PR guardrails preview only the local `dev` metadata program.
Shared previews, saved-plan applies and post-apply drift use Service Self Deploy.
Existing quality, security, mutation, release and template-sync automation remains.
Earlier template documentation describing the generic OIDC/token path is
historical; the governed TEST/PROD contract above governs shared deployments.

Scheduled TEST and PROD drift runs use the protected `test-preview` and `prod-preview` environments in Service Self Deploy, with config-reader and drift OIDC roles only. These runs still require the designated reviewer; unattended drift remains an installation prerequisite, requiring dedicated main-only read-only environments and narrowly extended config-reader/drift trust subjects. Apply trust and approvals remain unchanged.

The default Compose service does not load `.env` or forward AWS access keys. Cloud Make commands forward temporary credentials by variable name only in GitHub Actions when a session token exists. Local host credentials remain an explicit `ENABLE_AWS_CREDENTIALS=1` opt-in. `pulumi-plan`, `pulumi-up-plan`, `test-drift`, and `initialize-stack` export the selected `PULUMI_STACK`; GitHub tokens are forwarded only for these explicit cloud commands.

The credential-free preview helper (`make test-preview` and
`scripts/run_pulumi_preview.py`) defaults to the committed `dev` stack when
`PULUMI_PREVIEW_STACKS` is unset or empty. An explicit stack list overrides that
local fixture default. Shared TEST/PROD previews use `make pulumi-plan` through
the protected controller and its exact account-local stack list, backend and KMS
provider. The general guarded command helper preserves explicit selected-stack
or multi-stack configuration; the local fixture helper does not silently request
shared TEST/PROD credentials.
