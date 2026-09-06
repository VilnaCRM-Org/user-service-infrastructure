# AGENTS

This repository is a Pulumi-based infrastructure template. Agents should keep changes minimal, preserve the local developer workflow, and avoid introducing hidden cloud dependencies into CI.

## Working rules

1. Make the smallest change that satisfies the task.
2. Prefer updating tests, docs, and examples before widening release or deployment behavior.
3. Run the narrowest useful validation for the files you touched.
4. Use `pulumi -C pulumi ...` for direct Pulumi CLI commands.
5. Use `uv run ...` for Python CLI commands instead of invoking tools directly from the global environment.
6. Seed local `uv` environments with `export UV_PROJECT_ENVIRONMENT="${HOME}/.venvs/user-service-infrastructure"; uv venv --seed "${UV_PROJECT_ENVIRONMENT}"` before syncing if you need to run Pulumi Automation outside Docker.
7. Keep the structural, policy, quality, unit, integration, mutation, CLI, and aggregate local-battery suites runnable without live AWS credentials.
8. Use `make ci-pr` when you want the non-mutation GitHub PR battery, `make ci` for the full local superset including mutation, and `make test` for the faster non-mutation developer battery.
9. Use `make doctor` before debugging local Docker or Compose issues.
10. Run `make start` when changing Docker-backed CI jobs so workspace preparation stays consistent across workflows and local runs.
11. Keep `./scripts/prepare_policy_pack.py`, `policy/PulumiPolicy.yaml`, `policy/.venv`, and the shared `uv` environment contract aligned when changing Pulumi policy-pack behavior.
12. Reproduce PR safety checks with `make test-security`, `make test-repo-hygiene`, `make test-guardrails`, or `make ci-pr` before pushing infra-related workflow or policy changes.
13. Do not add long-lived static AWS credentials to workflows; use the documented OIDC role variables instead.
14. Treat `allow-destructive-infra-change` as the only supported override for destructive Pulumi diffs.
15. Keep `make test-coverage` green when changing Python code; the repo expects 100% branch coverage across the covered Pulumi, policy, and helper modules, with the unit, integration, and policy suites each held to 100% line coverage.
16. Keep `make test-dependency-hygiene` green when editing `pyproject.toml`, `uv.lock`, or import relationships.
17. Use `make report-quality` when you need the scheduled Wily, Vulture, docstring-coverage, and SBOM reports locally.
18. If local Pulumi plugin downloads hit GitHub rate limits, pass `GITHUB_TOKEN="$(gh auth token)"` only to the specific preview-oriented Make command you are running.
19. Prefer Make targets plus Python helpers under `scripts/*.py`; do not introduce new repository bash helper scripts for CI orchestration.
20. Treat shared Pulumi backends as KMS-backed for CI and maintainer docs; do not document passphrase-backed shared backends as the default path.

## Secret handling

These rules are mandatory for AI coding agents in this repository.

1. Never read, print, summarize, diff, or copy raw secret material.
2. Treat the following as off-limits unless the user explicitly asks for a secret-management task:
   - `.env`, `.env.*`, and shell files that export credentials
   - AWS shared credentials/config files, access keys, session tokens, and STS credentials
   - Pulumi stack files or exports containing `secure:` values or `encryptedkey` metadata
   - GitHub Actions secrets, deploy keys, private keys, certificates, kubeconfigs, and token files
3. Never run commands that reveal secrets in terminal output. This includes `env`, `printenv`, `docker compose config`, `docker inspect`, `pulumi config --show-secrets`, `pulumi stack output --show-secrets`, and cloud-secret fetch commands unless the user explicitly requests that exact action.
4. Prefer metadata-only checks such as `aws sts get-caller-identity`, `pulumi stack ls`, and `pulumi config` without secret-revealing flags.
5. When a secret must be set, write it directly with `pulumi config set --secret ...` or the relevant cloud secret store command without echoing the value back into the terminal transcript.
6. Never commit secret values, decrypted outputs, copied stack exports, or temporary files containing secrets.

## Pulumi workflow

1. Structural, quality, unit, integration, mutation, and CLI checks should stay local-backend-friendly.
2. Preview before apply when working against a real stack.
3. Prefer ephemeral validation stacks such as `pr-<number>` or `smoke` for manual checks.
4. Destroy ephemeral validation stacks after the check completes.

## Review-driven changes

1. Use `gh pr view <PR>` and `gh pr checks <PR>` for context.
2. Pull review threads with `gh api graphql` and resolve every actionable thread.
3. Keep refactors minimal and directly tied to review feedback.
4. Update `docs/` whenever the developer workflow, CI surface, or credential contract changes.
5. Re-run the relevant checks before pushing.
6. Keep the Pulumi policy pack under `policy/` aligned with the runtime guardrails in `pulumi/app/`.

## Finish PR

1. Confirm the current branch still matches the target PR head before making changes.
2. Review unresolved, non-outdated human and CodeRabbit comments before widening the patch.
3. Keep fixes scoped to the active review feedback and the failing checks.
4. Re-run the narrowest local validation that proves the comment or failure is addressed.
5. Reply on every human and CodeRabbit review thread after fixing it, including brief verification context when useful.
6. When a CodeRabbit comment is fixed, explicitly ask CodeRabbit on that same thread to re-check the comment because the fix is now present.
7. Wait until CodeRabbit has answered every per-comment reply before asking for a new PR-wide bot review.
8. After all fixed comments have been re-checked, ask `@coderabbitai review` or `@coderabbitai full review` on the PR only once the new head is ready for another full pass.
9. Do not call the PR finished until all required GitHub CI checks are green, current review threads are resolved, and CodeRabbit has approved the PR.
10. If CodeRabbit still withholds approval, inspect the latest current-head CodeRabbit review summary with `gh pr view <PR> --json reviews`, address any current-head findings even when no inline thread remains open, then repeat the per-comment recheck flow before requesting another PR-wide review.


## Governed service contract

These are the repo-local agent rules for `user-service-infrastructure`. They mirror
the governance gating and secret-handling posture enforced centrally by the
`bootstrap-infrastructure` governance stack. An agent (or human) working in this
repo MUST follow them.

## What this repo is

`user-service-infrastructure` is a **managed `*-infrastructure` service repo**. Its
AWS deploy infrastructure — the Pulumi state bucket, the KMS secrets key/alias, and
the GitHub OIDC deploy/config-read roles — is **provisioned and owned by the central
governance stack**, not by this repo. This repo only:

- holds the service's own Pulumi program (`pulumi/__main__.py` + stacks), and
- self-deploys through governance-provided OIDC roles via `.github/workflows/self-deploy.yml`.

This repo **consumes, never creates** that infrastructure.

## Hard rules

### 1. Never create IAM roles or OIDC trust for yourself
- Do NOT add `aws.iam.Role`, `aws.iam.Policy`, `aws.iam.RolePolicy`,
  `aws.iam.OpenIdConnectProvider`, or any `assume_role_policy` /
  `sts:AssumeRoleWithWebIdentity` trust to this repo's Pulumi program.
- The deploy roles already exist and are governance-owned:
  - `GitHubCiPreview-user-service-infrastructure-{env}`
  - `GitHubCiApply-user-service-infrastructure-{env}`
  - `GitHubCiDrift-user-service-infrastructure-{env}`
  - `GitHubCiConfigRead-user-service-infrastructure-{suffix}`
  Reference them by name/ARN; do not redefine them.

### 2. Consume the governance-provided backend + secrets key
- Pulumi backend: `s3://pulumi-user-service-infrastructure-{env}-state` (set as
  `pulumiBackendUrl` in the stack config).
- Pulumi secrets provider: `awskms://alias/pulumi-user-service-infrastructure-{env}-secrets?region=eu-central-1`
  (the stack `secretsprovider`). Never point at `alias/pulumi-platform-bootstrap-*` —
  that platform key is reserved for the governance stack and is not granted to this repo.

### 3. Two accounts, one region
- `test` stack -> AWS account `891377212104`; `prod` stack -> AWS account `933245420672`;
  region `eu-central-1`. Each stack pins ONLY its own account (no cross-account literal
  in the other stack). Account literals belong in stack config, never in Pulumi program Python; synthetic test fixtures may use explicit account IDs.

### 4. OIDC-only credentials — no static keys, no AdministratorAccess
- All AWS credentials come from **GitHub OIDC role assumption** through
  `./.github/actions/load-aws-ci-env` + `aws-actions/configure-aws-credentials`.
- NEVER commit a static AWS access key id / secret access key (the long-lived
  IAM key pair), Pulumi access token, or passphrase. The committed stack files carry
  non-secret config only (`awskms://` secrets provider, no `secure:`/`encryptionsalt`).
- NEVER request or attach `AdministratorAccess`. The service apply role is
  backend-only and scoped to this repository. Workloads need a separate
  reviewed capability and boundary change.

### 5. IaC-only apply (saved-plan path)
- Applies go through the saved-plan path only: `make pulumi-up-plan`. Never
  `make pulumi-up` (direct apply is rejected under `GITHUB_ACTIONS=true`).
- The deploy flow is PR-comment driven: `/pulumi test up` then `/pulumi prod up`,
  test before prod, with prod gated on test success.

### 6. Kravalg-gated, preview-blocked until operator apply
- Changes that touch IAM/governance/trust are reviewed under the central CODEOWNERS
  `@Kravalg` gate (in `bootstrap-infrastructure`). This repo does not weaken that gate.
- `pulumi preview` cannot run here until the operator has applied governance for this
  repo and set the GitHub repo-variables; until then the assets are validated by
  structure only (no live preview).

## Secret handling

- Source of truth for CI config is **AWS Secrets Manager** (`/user-service-infrastructure/ci/{suffix}`),
  read at runtime via the governance config-read role. Do not duplicate secret values
  into this repo, into stack config, or into workflow files.
- Treat every value loaded from the CI-config secret as sensitive: never echo it,
  never write it to logs or PR comments.

## Executable scaffold contract

Generate this repository with scripts/scaffold_infrastructure_repository.py in the
bootstrap source; never copy only the template directory. Initial permissions are
backend-only. Real workloads require separately reviewed capability grants.
Service apply environments are test/prod, distinct from test-preview/prod-preview.
Initialize missing shared stacks only through trusted main Initialize Service Stack,
never through a preview fallback or an unguarded local resource update.

Apply comments and Initialize Service Stack dispatches must be requested by a
maintainer other than sole environment reviewer Kravalg. Kravalg approves the
protected environment; the original apply commenter cannot also be the approver.
