# CI Guardrails

This repository treats infrastructure pull requests as high-risk changes. The
guardrail layer below is designed to catch the common failure modes of
AI-generated Pulumi and AWS code before anyone merges or applies it.

For the broader Python, dependency, workflow, Dockerfile, and scheduled
maintainability checks, use [CI quality gates](ci-quality-gates.md).

## Required PR checks

These checks are intended to be marked as required in branch protection:

| Check | Local command | Purpose |
| --- | --- | --- |
| `Preview` | `make test-preview` | Produces a non-destructive Pulumi preview artifact for every configured stack |
| `Destructive Diff Gate` | `make test-destructive-diff` | Blocks deletes and replacements of critical infrastructure unless explicitly approved |
| `Secrets Scan` | `make test-secrets` | Runs Gitleaks against tracked Git content |
| `Dependency Audit` | `make test-deps-security` | Audits Python dependencies with `pip-audit --strict` |
| `Bandit` | `make test-bandit` | Lints repository Python code for common security hazards |
| `Actionlint` | `make test-actionlint` | Lints GitHub Actions workflow syntax and common security issues |
| `CodeQL (python)` | GitHub-native | Scans Python code for security issues |
| `CodeQL (actions)` | GitHub-native | Scans workflow code for insecure patterns |

`make test-security` aggregates Gitleaks, dependency audit, and Bandit.
`make test-repo-hygiene` aggregates Actionlint, Yamllint, and Hadolint.
`make test-guardrails` aggregates preview generation and destructive diff
gating without requiring AWS credentials. `make ci-pr` and `make ci` include
the credential-free guardrail battery. `make test-iam-validation` is a separate
operator command requiring appropriately scoped AWS credentials, not an ordinary
PR workflow job.

## Preview model

The preview workflow uses the same Docker workspace and policy pack that local
developers use:

1. `make start`
2. `make publish-pulumi-preview-summary`
3. `make test-destructive-diff`

Preview artifacts are written under `.artifacts/pulumi-preview/` and uploaded to
GitHub Actions. The preview summary is appended to `GITHUB_STEP_SUMMARY` so
reviewers can inspect the plan without digging through raw logs first.

The ordinary PR workflow explicitly pins `PULUMI_PREVIEW_STACKS=dev` and a
disposable file backend. Local preview commands can select stacks through their
`PULUMI_PREVIEW_STACKS` environment setting; they default to `dev`. Protected
deployment jobs obtain shared-stack selection from the governed configuration.

If local Pulumi plugin downloads hit anonymous GitHub rate limits, pass a token
explicitly only to the preview-oriented command you are running, for example:

```bash
GITHUB_TOKEN="$(gh auth token)" make test-preview
```

The Docker workspace does not inject `GITHUB_TOKEN` by default.

## Destructive change gate

The destructive-diff gate fails when the preview proposes deletes or
replacements against critical resource families such as:

- VPC and networking primitives
- IAM roles and policies
- KMS keys
- S3 buckets
- RDS and other database resources
- Secrets Manager resources
- Route53 records
- EKS resources

Intentional destructive changes must be reviewed manually and then approved with
the pull-request label `allow-destructive-infra-change`. The label is the only
supported override because it leaves an auditable trail in GitHub.

## IAM validation

`scripts/pulumi_ci_guardrails.py validate-iam` extracts IAM policy documents
from the preview artifact and validates them with AWS IAM Access Analyzer.

Current behavior:

- No IAM policies in the preview: the check exits successfully and prints a
  short note
- IAM policies in the preview with valid AWS credentials: findings of type
  `ERROR` and `SECURITY_WARNING` fail the check
- IAM policies in the preview without valid AWS credentials: the check fails so
  maintainers do not accidentally merge unvalidated IAM changes

This complements the custom Pulumi CrossGuard pack. Direct S3 bucket and KMS
key policies retain resource-local `Resource: "*"` and matching service-wide
`s3:*` or `kms:*` compatibility. Their Allow statements still reject global
`Action: "*"`, cross-service wide grants, and nonempty `NotAction`/`NotResource`;
Deny semantics and exact reviewed IAM document pins remain unchanged. This does
not certify principals or conditions; stronger resource-policy pinning is tracked
in bootstrap-infrastructure#210. Access Analyzer adds AWS-native semantic checks.

## Protected AWS access and ordinary PR checks

`Pulumi PR Guardrails` runs credential-free previews of the disposable `dev`
stack on a file backend for both forks and same-repository pull requests. It
runs the destructive diff gate on that artifact; it does not assume an AWS role
or run privileged IAM validation. `AWS_REGION` is only its optional region
setting, defaulting to `eu-central-1`.

`Service Self Deploy` handles protected PR-comment deployments through OIDC.
Its trusted configuration loader requires these repository variables:

| Variables | Purpose |
| --- | --- |
| `AWS_TEST_CI_CONFIG_ROLE_ARN` | TEST configuration-read role |
| `AWS_PROD_PREVIEW_CI_CONFIG_ROLE_ARN` | PROD preview/drift configuration-read role |
| `AWS_PROD_CI_CONFIG_ROLE_ARN` | PROD apply configuration-read role |
| `AWS_TEST_ACCOUNT_ID`, `AWS_PROD_ACCOUNT_ID` | Exact target account bindings |
| `AWS_TEST_REGION`, `AWS_PROD_REGION` | Exact target region bindings |

The loader obtains deployment role ARNs, stack settings, the authoritative S3
backend and cloud KMS secrets provider from the governed Secrets Manager
configuration. Missing or mismatched account/region bindings fail closed. These
jobs do not use static AWS keys, a shared passphrase or a Pulumi Service token.
The configuration and deployment role trusts remain governance-owned and bind
the repository identity, main ref, environment and exact workflow name; ordinary
PR subjects are not a substitute for these protected environment claims.

TEST and PROD saved applies download their original same-run preview artifact,
fetch current PR labels and rerun the destructive diff gate immediately before
`make pulumi-up-plan`. Removing `allow-destructive-infra-change` after preview
therefore blocks a destructive apply; artifact or label-fetch failures also stop
execution. This reuses the saved diff without generating a replacement plan.

`LoggingExempt` is a review-controlled IaC tag for approved logging sinks, not
an independently authenticated exemption. The initial service backend-only role
cannot create workload buckets. Stronger approved resource-identity pinning before
expanding that capability remains tracked in bootstrap-infrastructure#210.

## Nightly-only checks

Nightly workflows are visible but do not block pull requests:

| Check | Purpose |
| --- | --- |
| `Scheduled Test Drift`, `Scheduled Prod Drift` | Runs `pulumi preview --refresh --expect-no-changes` against configured shared stacks |
| `Scorecard` | Runs OpenSSF Scorecard and uploads SARIF results for repository health visibility |

Scheduled drift requires the governed S3/KMS configuration and fails when it is
missing; it never substitutes an ephemeral backend for shared-stack evidence.

## Manual maintainer follow-up

Before enabling a new installation, maintainers must verify the governance-owned
roles and configuration, set the exact repository variables above, and protect the
deployment environments and required PR checks. Changes to stack selection or IAM
scopes belong in the reviewed governance configuration, not ad hoc workflow roles.

## Current limitations

- CodeQL is GitHub-native; the repository keeps the workflow under structural
  test coverage, but there is no local `make` equivalent
- The custom VilnaCRM CrossGuard pack is the enforced policy-pack layer in this
  template; the workflow does not vendor the Node-based AWSGuard package into
  the Python/uv Docker image
- IAM validation is only as complete as the preview artifact; policies that are
  created entirely outside Pulumi still need separate review

### Scheduled drift and PR commands

`.github/workflows/scheduled-drift.yml` owns the daily main-only TEST/PROD
read-only drift checks. `.github/workflows/self-deploy.yml` accepts only the
validated repository dispatch used by PR commands. Keeping the schedule trigger
out of the PR-head execution graph prevents that graph from sharing a scheduled
default-branch cache context. The scheduled workflow is named
`Service Scheduled Drift`; the dispatch controller is named `Service Self Deploy`.
These distinct names are governance-owned OIDC workflow claims, not file-path
claims. The scheduled file checks out only `github.sha` on main, uses the
main-only `test-drift` and `prod-drift` environments with read-only drift roles,
and has no apply or promotion jobs.
