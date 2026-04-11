# GitHub Actions Secrets for Pulumi Workflows

The maintained operator guide now lives in
[`docs/github-actions-secrets.md`](../docs/github-actions-secrets.md). Use that
document as the source of truth for repository variables, Pulumi Service
authentication, and template-sync credentials.

## Recommended AWS Authentication

This repository is OIDC-first. Configure GitHub Actions to assume an AWS role
that trusts `token.actions.githubusercontent.com`, then pass that role through
the `role-to-assume` and `role-session-name` inputs of
`aws-actions/configure-aws-credentials@v4`.

- `AWS_OIDC_ROLE_ARN` should be stored as a repository variable.
- `PULUMI_ACCESS_TOKEN` is only required when the backend is Pulumi Cloud.

## Static-Key Fallback

If you are working with a legacy environment that cannot use GitHub OIDC yet,
use static AWS keys only as an explicit fallback:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

Rotate fallback keys regularly and remove them once OIDC is available.
