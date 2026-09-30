# Run summary: do-sdlc-plan, workload-wa-hardening

This file is the execution ledger. It is not a planning input.

## Identity and scope

| Field | Value |
| --- | --- |
| Task | Well-Architected hardening of the user-service ECS workload |
| Repository | VilnaCRM-Org/user-service-infrastructure |
| Worktree | wt-usi-hardening |
| Branch | feat/workload-wa-hardening |
| Source baseline | 66776772979956de9c5abdbee7c45641a1b533fa (PR #56 head) |
| Bundle revision | 13 (answers readiness round 13: R13-m1, R13-m2, R13-n1…n7; wording only, no new user decision; parent commit b1ed572, which is revision 12) |
| Specs directory | `specs/workload-wa-hardening/` (slug chosen by the caller) |
| Target | pulumi (Python Pulumi), stacks test and prod |
| Environment | none selected; planning is offline |
| Stage | do-sdlc-plan |
| Date (UTC) | 2026-09-30 (revisions 1-11); 2026-10-01 (revisions 12 and 13) |

## Tooling and profile

| Item | Result |
| --- | --- |
| Plugin root | `/home/kravtsov/.claude/plugins/cache/vilnacrm-plugins/devops-sdlc/0.1.0` |
| `plugin.json` sha256 | 44602cf5cbee9fc5eada6d0fa2f3b8fc4b67bc6fdb6f1ffb05b1e8fde7490564 |
| `do-sdlc-plan.md` sha256 | 4f7650b99273ada40fd9dabdf2c883a47e3afa66327cc6dbd86c7be406db9fe6 |
| `bmad-autonomous-planning/SKILL.md` sha256 | 18c523f18bfba8e54279a376097fa2e9a2ab3514310846fb2c518ab04e3e7e76 |
| TRUSTED_PYTHON | `/usr/bin/python3` (3.14.4) |
| `validate-profile` | BLOCKED: "Required repository path is missing"; `.claude/devops-sdlc.json` is absent (XP-7) |
| `agent_cli detect` | READY: backend claude, Claude Code 2.1.280 |
| bmalph | 2.11.0; `bmalph init --platform claude-code` run in the worktree |
| `_bmad/COMMANDS.md` sha256 | da2f78200b2b0a77e4a6db87a6f30de55200fb7494b697301e72387e1757c722 |

`bmalph init` created `_bmad/`, `.ralph/`, `bmalph/`, `.claude/commands/` and `CLAUDE.md`. All of them are left untracked and none is committed. Its edit to `.gitignore` was reverted.

## Scope limits

- No aws or pulumi command ran against any account.
- No repository test, lint or preview command was executed; this was analysis only.
- No secret value was read.

## Inputs

- `specs/poc/README.md` sha256: 8ad9ccf4ae28083c36e30909a21d8ebec4fc0d40a9b716c9bb8b78b6276ed5b7
- `decisions.md` (the user decisions, a planning input; hash below)
- Repository source read for revision 12 at `7bf441c` (the workload
  source is unchanged from the baseline), without executing it:
  `scripts/poc_workload_capabilities.py` (lines 20-35, 86-240, 322-346),
  `pulumi/app/compute.py` (lines 220-236, 720-736). Bootstrap-infrastructure,
  read-only (`sed`, `grep`, `git log`, read-only Python over the
  catalogs; no fetch, no checkout): `wt-boot-urllib3` (`862b4bf`,
  `origin/main` proxy): `docs/governance-stack.md` (lines 470-490),
  `specs/service-test-preview-trust-cutover/runbook.md` (lines 25-40),
  `specs/security-completion/verification.md` (lines 50-62),
  `specs/test-poc-prerequisite-capability/amendment-installation.md`
  (lines 45-56), `…/impact.md` (by grep), `…/review.md` (line 15),
  `pulumi/seed/README.md` (lines 10-26, 160-172),
  `pulumi/seed/catalogs/test.json` and `prod.json` (the principals list,
  lines 1143-1568, counted; the statement definition lines of the
  round-11 and round-12 hashes; a grep for `lambda:` actions);
  `wt-boot-pr280` (`e85534c`):
  `specs/test-poc-prerequisite-capability/post-seed-activation.md`
  (lines 75-90, 196-262, 362-372), `review.md` (lines 10-18),
  `docs/governance-stack.md` (by grep); `wt-boot-219` (`54e9e2f`):
  `pulumi/seed/poc_runtime.py` (lines 1-290),
  `pulumi/infra/poc_runtime_enrollment.py` (lines 60-150),
  `specs/219-test-workload-capability/runtime-enrollment.md` (lines 1-70,
  90-115, 190-245), `…/installability-stop.md` (lines 1-20); a grep of
  all three worktrees and the `bootstrap-infrastructure` clone (branch
  `cost/account-spend-controls`, `debd88b`) for `Issue215CutoverSessions`.
  A read-only `Explore` subagent recomputed the round-11 Location cells
  against `git show 7bf441c:…` (R12-n1).
- **AWS documentation, revision 12 (read 2026-10-01 by the revision-12
  planning agent):** through the aws-knowledge MCP
  (`read_documentation`, `search_documentation`): "Giving Lambda
  functions access to resources in an Amazon VPC",
  <https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc.html>
  (whole page); `AWS::IAM::ManagedPolicy`,
  <https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-iam-managedpolicy.html>
  (properties and update behaviors); the AWS managed policy
  `AWSPCSServiceRolePolicy` (a search result showing
  `ec2:CreateNetworkInterface` on `network-interface`, `subnet` and
  `security-group` ARNs). The aws-knowledge MCP could not render "Actions,
  resources, and condition keys for Amazon EC2"
  (<https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonec2.html>
  redirects to the reference index there), so its published
  machine-readable form was fetched read-only with `curl` from
  <https://servicereference.us-east-1.amazonaws.com/v1/ec2/ec2.json>
  (version v1.4, `last-modified` 2026-09-28), together with the same
  service's `lambda`, `iam`, `ecr`, `sts`, `cloudtrail` and `logs` files,
  and evaluated with read-only Python (the resource types and condition
  keys of each action cited in AD-26 layer 6 and NFR-06). No AWS account
  was called.
- **AWS documentation, revision 11 (recorded late, R12-n2):** the
  revision-11 pre-commit audit's recheck (the `claude-router:audit`
  subagent) read "Giving Lambda functions access to resources in an
  Amazon VPC",
  <https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc.html>,
  through the aws-knowledge MCP on 2026-09-30; its recheck finding N1
  (`readiness.md`, "Pre-commit audit of revision 11") relies on it. That
  read was not listed here in revision 11.
- Repository source read for revision 11 at `9b17199` (the workload
  source is unchanged from the baseline), without executing it:
  `scripts/poc_workload_topology.py` (lines 18, 365-380, 810-842),
  `scripts/poc_workload_phase_entrypoint.py` (lines 50-65, 88-137),
  `scripts/poc_publisher_dispatch.py` (lines 140-180, 211-217, 261-286),
  `.github/workflows/self-deploy.yml` (lines 1-10, 40-53, 60-80,
  718-790), `schemas/poc-test-v1.schema.json` (top-level keys, lines
  440-455 and 815-840), `tests/unit/test_poc_workload_topology.py`
  (lines 160-170, 275-283) and `tests/unit/test_poc_publisher_dispatch.py`
  (line 128). Bootstrap-infrastructure, read-only: `origin/main` through
  `wt-boot-urllib3` (`862b4bf`): `pulumi/seed/catalogs/test.json` and
  `prod.json` (the guard, ceiling and boundary entries and the statements
  cited in the round-11 map, plus read-only Python evaluations of the
  guards' statement lists), `pulumi/seed/policy_registry.py` (lines
  15-24), `pulumi/seed/test_poc_prerequisite_amendment.py` (lines 1-160),
  `pulumi/seed/poc_pass_role.py` (lines 1-94),
  `pulumi/infra/poc_runtime_enrollment.py` (lines 100-135),
  `pulumi/infra/governance_automation.py` (lines 476-492); #284 through
  `wt-boot-pr280` (`e85534c`): `policy_registry.py`, the TEST catalog
  boundary and governance entries, `pulumi/infra/test-poc-identity.json`;
  #285 through `wt-boot-219` (`54e9e2f`):
  `specs/219-test-workload-capability/runtime-enrollment.md` (lines
  1-396), `pulumi/seed/poc_runtime_fence_stack.py` (by grep),
  `pulumi/seed/poc_publisher_stack_verification.py` (line 197), and
  `git merge-base`/`git diff --stat` between `862b4bf`, `e85534c` and
  `54e9e2f`.
- Repository source read for revision 10 at `8e097aa` (the workload
  source is unchanged from the baseline), without executing it:
  `scripts/poc_workload_runner.py` (lines 160-190),
  `scripts/poc_workload_capabilities.py` (lines 20-60, 236-346),
  `scripts/poc_workload_admission.py` (lines 455-478),
  `scripts/poc_workload_phase_entrypoint.py` (lines 52-60, 96-123,
  220-231), `scripts/poc_workload_images.py` (line 243, by grep),
  `scripts/poc_workload_topology.py` (line 828, by grep),
  `schemas/poc-test-v1.schema.json` (lines 440-530),
  `specs/poc/poc-test.json` (keys only), `specs/poc-workload-runner.md`
  (lines 1-30, 100-120), `specs/poc-api-gateway-backend.md` (lines
  30-60), `docs/poc-workload-admission.md` (lines 100-126), and the tests
  `tests/unit/test_poc_workload_runner.py` (lines 310-345),
  `tests/unit/test_poc_workload_image_config.py` (lines 295-340) and, by
  grep, `tests/unit/test_poc_contract.py`,
  `tests/unit/test_poc_workload_capabilities.py` and
  `tests/unit/test_poc_workload_phase_entrypoint.py`; bootstrap-infrastructure
  `origin/main` `bea5252` through the worktree `wt-boot-urllib3`
  (`862b4bf`; only `uv.lock` differs from `origin/main`):
  `pulumi/seed/catalogs/test.json` and `prod.json` (the boundary, guard
  and statement entries cited in `readiness.md`, plus a read-only Python
  evaluation of every USI guard statement against the planned actions
  and of the boundary's rendered size), `pulumi/seed/policy_registry.py`
  (lines 1-30), `pulumi/seed/test_poc_prerequisite_amendment.py` (lines
  1-80), `pulumi/infra/governance.py` (lines 212, 262-272, 410-500),
  `pulumi/infra/governance_automation.py` (lines 180-200, 418-458),
  `pulumi/infra/ci_bootstrap.py` (lines 128-168, 634-705) and
  `pulumi/infra/platform_iam.py` (lines 636-650); and `wt-boot-219`
  (`54e9e2f`) for the identical amendment module
- Repository source read for revision 9 at `c61d8d6` (the workload source
  is unchanged from the baseline), without executing it:
  `scripts/poc_workload_images.py` (whole file),
  `scripts/poc_workload_capabilities.py` (lines 1-60, 89-120, 193-340),
  `scripts/poc_workload_runner.py` (lines 45-62, 165-185),
  `scripts/poc_workload_admission.py` (lines 455-480),
  `scripts/poc_backend_observer.py` (lines 125-130, 160-185, 419-490),
  `scripts/poc_mail_prerequisite.py` (AWS call set),
  `docs/poc-workload-admission.md` (lines 36-125),
  `specs/poc-workload-runner.md` (lines 108-114), `specs/poc/README.md`
  (lines 105-128), `.github/workflows/scheduled-drift.yml` (lines 30-40,
  94-102), the tests `tests/unit/test_poc_workload_image_config.py` and
  `tests/unit/test_poc_workload_images.py` (the authorization and
  registry-hop cases, by grep); bootstrap-infrastructure (read-only
  local clone; fetched `origin/main` `bea5252` read with `git show`):
  `pulumi/infra/governance.py` (lines 140-300, 300-470),
  `pulumi/infra/ci_bootstrap.py` (lines 45-60, 120-175, 600-670),
  `pulumi/infra/test-poc-identity.json`; and the unmerged worktree
  `wt-boot-219` (`54e9e2f`): `pulumi/infra/governance.py` (lines
  276-515), `pulumi/infra/test-poc-identity.json`, and greps of
  `pulumi/` for SSM, ACM, IAM, ECR and `RepositoryPolicy` grants.
  AWS documentation (aws-knowledge MCP, 2026-09-30): the ECR API
  reference for `GetDownloadUrlForLayer`
- Repository source read for revision 8 at `72873f9` (the workload source is
  unchanged from the baseline; `git diff --stat 66776772 72873f9 --
  scripts schemas tests .github docs specs/poc` is empty), without
  executing it: the three grep inventories over `scripts/` (87, 38 and 41
  lines; commands in `epics-stories.md` S4.14), `scripts/service_execution_worker.py`
  (lines 120-135), `scripts/service_execution_host.py` (lines 20-60,
  125-170, 200-220), `scripts/poc_contract.py` (lines 90-200),
  `scripts/poc_secret_observation.py`, `scripts/poc_workload_capabilities.py`
  (lines 20-50, 88-96, 185-340), `scripts/poc_workload_phase_entrypoint.py`
  (lines 20-120, 185-215), `scripts/poc_workload_materializer.py` (lines
  18-30, 78-145), `scripts/poc_workload_runner.py` (lines 155-205),
  `scripts/poc_workload_topology.py` (lines 1-20, 140-155, 950-958,
  1155-1165), `scripts/poc_backend_observer.py` (lines 76-79, 160-235,
  315-330, 420-440), `scripts/poc_registry_runner.py` (lines 34-36,
  183-265), `scripts/poc_registry_plan.py` (lines 20-72),
  `scripts/poc_registry_phase_entrypoint.py` (lines 10-54),
  `scripts/poc_registry_completion.py` (lines 100-108, 252-259, 360-370),
  `scripts/poc_mail_prerequisite.py` (lines 13-16, 295-312, 385-440),
  `scripts/poc_scheduled_registry_drift.py` (lines 104-140),
  `scripts/poc_phase_admission.py`, `scripts/poc_source_artifact.py`,
  `scripts/poc_phase_source_adapter.py`, `scripts/poc_workload_admission.py`
  (lines 100-140), `scripts/pulumi_command_preflight.py`,
  `scripts/pulumi_pr_comment.py`, `scripts/poc_publisher_dispatch.py`,
  `.github/workflows/self-deploy.yml` (upload steps),
  `.github/workflows/scheduled-drift.yml`, `specs/poc/README.md` (lines
  48-60), `docs/poc-workload-admission.md` (lines 1-20),
  `docs/ci-guardrails.md` (lines 140-185), and the tests
  `tests/unit/test_service_execution_host.py` (lines 75-145, 228-322),
  `tests/unit/test_service_execution_worker.py` (lines 75-131),
  `tests/pulumi/test_ci_guardrails.py` (lines 245-286) and
  `tests/unit/test_workload_apply_docs_consistency.py` (lines 168-190);
  bootstrap-infrastructure (read-only local clone, checked-out `debd88b`,
  fetched `origin/main` `bea5252`, read with `git show`):
  `pulumi/infra/governance.py`, `pulumi/infra/ci_bootstrap.py`,
  `pulumi/seed/catalogs/test.json`; and the unmerged worktree
  `wt-boot-219` (`0933d8b`) for comparison only
- Repository source read for revision 7 at `5cc069c` (the workload source is
  unchanged from the baseline), without executing it: `self-deploy.yml`
  (lines 62, 79-86, 135, 274, 284, 570-697, 783-797), `scheduled-drift.yml`,
  `.github/actions/setup-service-execution/action.yml`,
  `scripts/service_execution_host.py`, `scripts/service_execution_worker.py`,
  `scripts/poc_workload_runner.py`, `scripts/poc_workload_materializer.py`
  (lines 80-143), `scripts/poc_workload_phase_entrypoint.py` (lines 100-118),
  `scripts/poc_workload_capabilities.py` (lines 20-48, 92-133, 286),
  `scripts/poc_workload_images.py` (lines 44-126, 200-212, 282, 349),
  `scripts/poc_workload_admission.py` (lines 464-475),
  `scripts/poc_registry_runner.py` (lines 94-103, 236-283, 335-368),
  `scripts/poc_registry_plan.py` (lines 18-40, 60-73),
  `scripts/poc_registry_completion.py` (lines 103-200, 635-680),
  `scripts/reviewed_source_admission.py` (lines 118-140),
  `scripts/poc_backend_observer.py` (lines 160-205, 415-480),
  `scripts/poc_scheduled_registry_drift.py` (lines 1-140),
  `scripts/poc_source_artifact.py` (lines 60-70),
  `scripts/poc_phase_source_adapter.py` (lines 176-186, 236-246, 280-292),
  `scripts/poc_phase_admission.py` (lines 24, 34-43),
  `scripts/poc_contract.py` (line 17), `scripts/run_pulumi_command.py`
  (lines 483-510, 585-639), `scripts/poc_workload_reconciliation.py` (lines
  1-10), `schemas/poc-test-v1.schema.json` (lines 155-215), and the tests
  `tests/pulumi/test_ci_guardrails.py`,
  `tests/unit/test_trusted_test_controller_workflow.py`,
  `tests/unit/test_poc_source_workflow.py`,
  `tests/unit/test_poc_registry_workflow.py`,
  `tests/unit/test_service_execution_host.py`,
  `tests/unit/test_service_execution_worker.py`,
  `tests/unit/test_service_reviewed_credentials.py`,
  `tests/unit/test_service_execution_workflow.py`,
  `tests/unit/test_poc_scheduled_registry_workflow.py`,
  `tests/unit/test_poc_registry_completion_workflow.py`,
  `tests/unit/test_poc_phase_source_adapter.py`,
  `tests/unit/test_service_initializer.py` and
  `tests/pulumi/test_quality_contracts.py`
- Repository source read for revision 6 at `68584e1` (the workload source is
  unchanged from the baseline), without executing it: `self-deploy.yml`
  (job graph, lines 62, 79-86, 478-730), `scheduled-drift.yml`,
  `scripts/run_pulumi_command.py` (lines 53-68, 592-639, 816-839,
  842-864), `scripts/_pulumi_command_support.py` (lines 50-72, 159-190),
  `scripts/poc_registry_runner.py` (lines 254-258, 330-367),
  `scripts/poc_workload_runner.py`, `scripts/service_execution_worker.py`,
  `scripts/service_execution_host.py`, `scripts/poc_backend_observer.py`
  (lines 37-43, 170-195, 358-470), `scripts/poc_workload_reconciliation.py`
  (lines 15-49, 90-104), `scripts/poc_registry_plan.py` (lines 21-30,
  74-86, 297-324, 365-376), `scripts/poc_phase_source_adapter.py`,
  `scripts/poc_phase_admission.py` (line 24),
  `scripts/poc_scheduled_registry_drift.py`, `pulumi/app/environment.py`
  (lines 677-681), and the workflow-shape tests
  `tests/pulumi/test_ci_guardrails.py`,
  `tests/unit/test_trusted_test_controller_workflow.py`,
  `tests/unit/test_service_execution_workflow.py`,
  `tests/unit/test_poc_registry_completion_workflow.py`,
  `tests/unit/test_poc_registry_workflow.py`,
  `tests/unit/test_poc_source_workflow.py`,
  `tests/unit/test_poc_phase_source_adapter.py`,
  `tests/unit/test_service_initializer.py`,
  `tests/unit/test_service_execution_host.py`,
  `tests/unit/test_poc_scheduled_registry_workflow.py` and
  `tests/unit/test_service_execution_worker.py`
- Repository source read for revision 5 at `57f38aa`, without executing it:
  `Makefile`, `scripts/run_pulumi_command.py`,
  `scripts/_pulumi_command_support.py`, `scripts/run_pulumi_drift_check.py`,
  `.github/workflows/scheduled-drift.yml`, `.github/workflows/self-deploy.yml`,
  `pulumi/__main__.py`, `pulumi/app/workload_phase.py`,
  `pulumi/app/environment.py`, `pulumi/app/data.py`,
  `scripts/poc_workload_reconciliation.py`, `scripts/poc_registry_plan.py`,
  `scripts/poc_workload_secret_result.py`, `scripts/poc_gateway_backend.py`,
  `scripts/poc_workload_topology.py`, `scripts/poc_workload_runner.py`,
  `scripts/service_execution_worker.py`, `scripts/service_execution_host.py`,
  `scripts/poc_scheduled_registry_drift.py`,
  `scripts/configure_github_repository_controls.py`,
  `scripts/_github_repository_controls.py`,
  `scripts/_github_environment_controls.py`,
  `scripts/_github_evidence_environment.py`,
  `specs/poc-workload-runner.md`, `docs/poc-workload-reconciliation.md`, the
  test tree listing; bootstrap-infrastructure @debd88b
  `scripts/configure_github_repository_controls.py` (read-only)
- Repository source read for revision 4 at `1ebbd09`, without executing it:
  `scripts/poc_workload_runner.py`, `scripts/poc_workload_topology.py`,
  `scripts/poc_workload_secret_result.py`, `scripts/pulumi_ci_guardrails.py`,
  `policy/reviewed_iam.py`, `policy/guardrails.py`,
  `policy/vilnacrm_guardrails.yaml`, `specs/poc-workload-runner.md`,
  `specs/poc/README.md`, `tests/unit/test_workload_apply_docs_consistency.py`,
  `tests/integration/test_poc_first_topology_native.py`, `AGENTS.md`,
  `.github/CODEOWNERS`; bootstrap-infrastructure @debd88b
  `scripts/_github_repository_controls.py` and
  `scripts/_github_environment_controls.py` (read-only)
- AWS documentation via aws-knowledge MCP, verified 2026-09-30 for revision 4:
  A-26 (Application Auto Scaling one-time scheduled actions), A-27 (managed
  master password caller permissions; the DocumentDB page is silent), A-28
  (CloudWatch Logs KMS)
- AWS documentation, via aws-knowledge MCP (see research §3); revision 3 re-verified A-16 (REST API VPC link V2 → ALB), A-20 (SES API VPC endpoints), A-23 (ElastiCache IAM limits), A-24 (`StsGetCallerIdentityCalls`) and A-25 (managed DocumentDB rotation) on 2026-09-30
- Local provider source: `pulumi_aws` 7.23.0 `apigateway.Integration.integration_target` (read-only grep of the installed SDK)
- User decisions given in chat on 2026-09-30 and relayed by the coordinator: D-1…D-7 (`decisions.md`). The D-4 and D-5 clarifications came in a second message the same day, and D-8…D-13 (derived details) were confirmed in a third. D-14 (recovery targets RPO ≤ 1 hour, RTO ≤ 24 hours) is a user decision of the same date, recorded in `decisions.md` by commit `68584e1`. **D-15** (the gateway certificate ARN pinned in the reviewed USI workload contract and checked only with `acm:DescribeCertificate`; no CI role gets any `ssm:GetParameter` read; no identity deny, seed guard, seed boundary or catalog hash loosened for SSM) is a user decision given in chat on 2026-09-30, answering the coordinator's question, and relayed with round 10; revision 10 records it in `decisions.md`.
- Read-only cross-repository reconnaissance: bootstrap-infrastructure @debd88b, api-gateway-infrastructure, and user-service @main via `gh api`

## Artifacts (sha256, revision 13)

`run-summary.md` is not hashed here, because it contains the hashes. `decisions.md` is a planning input and is hashed. Commit `68584e1` added its D-14 row after revision 5; revision 6 changed only that row's label (a user decision, not a planning default); revisions 7, 8 and 9 do not change it; revision 10 adds the D-15 row (a user decision of 2026-09-30); revision 11 changes only D-15's note text (R11-n3); revisions 12 and 13 do not change it. `research.md` is unchanged since revision 4; `brief.md` changed last in revision 10 (front matter and AS-4, D-15).
Check with `sha256sum -c` over the block below, from `specs/workload-wa-hardening/`.

```
beca16ba9ab95d76cd28ed47ac8e806549b94805ddca9a2d138a790ee0f0ca59  research.md
5d7d1e37b9417de7cbe7b4fa0bcafe28ed723da997c22be7ef5902b384e302e4  brief.md
807345cc4de89ee36a50b52b5c26ed782dd3cc107c11a1b48902459e20849033  prd.md
dc1fb43514c252a8b3d2cc01010a6b4d364133b28a8ea9ee69a797679ea4fc80  architecture.md
d1a4e453c90bef8d6e3ade5a88d7f88f2680be17400d4f29a2f35fc198e7bf61  epics-stories.md
86df7c4f7b72ad49cbca328ec79884c792c1b3f833567f4a34586eb60d5259c6  decisions.md
bd4f9e98fda9753408e6fb4c073b7ef2126ac2d93f1b2506cee55e56ea333691  readiness.md
```

## Gates

**Independent readiness:**

| Round | Result |
| --- | --- |
| 1 | FAIL (3 blocking, 10 major); fixed in revision 2 |
| 2 | Result not stored in this bundle |
| 3 | FAIL (B-1, B-2, M-1…M-13, m-1…m-12); fixed in revision 3 |
| 4 | FAIL (R4-B1…B3, R4-M1…M10, m1…m12); fixed in revision 4 |
| 5 | FAIL (R5-M1…M5, m1…m18; every round-4 finding confirmed resolved); fixed in revision 5 |
| 6 | FAIL (R6-M1, R6-M2; R6-m1 and R6-m3…m14; no R6-m2 was relayed); fixed in revision 6 |
| 7 | FAIL (R7-M1, R7-M2; R7-m1…m9; R7-n1…n3), plus a fresh-context audit of revision 6 (F1…F8; F2, F6 and F8 not covered by round 7); fixed in revision 7, after a pre-commit fresh-context audit of the revision-7 changes (recorded in `readiness.md`) |
| 8 | FAIL (R8-M1; R8-m1…m7; R8-n1…n4), plus the residuals A1…A4 of the recheck of the revision-7 pre-commit audit (A2 merged into R8-m1); fixed in revision 8, after a pre-commit fresh-context audit of the revision-8 changes (recorded in `readiness.md`) |
| 9 | FAIL (1 major, R9-M1: the Preview and Apply roles are blocked by explicit secret-read denies on every workload `plan` and `up-plan`, and no story owned the TEST fix fully or the PROD one; 2 minor, R9-m1 and R9-m2; 4 nits, R9-n1…n4); fixed in revision 9, after a pre-commit fresh-context audit of the revision-9 changes and its recheck (both recorded in `readiness.md`) |
| 10 | FAIL against `8e097aa` (1 major, R10-M1: the seed-owned IAM layers, the hash-pinned `immutable_managed_guard` of every USI CI role and the seed-owned permissions boundary, were not planned; 2 minor, R10-m1 (the 6144-character boundary) and R10-m2 (concurrent seed amendments); 6 nits, R10-n1…n6). The coordinator relayed the new user decision **D-15** with it (the certificate ARN in the reviewed USI contract, no `ssm:GetParameter` for any CI role). Fixed in revision 10, after a pre-commit fresh-context audit of the revision-10 changes and its recheck (REFUTED; 9 of 12 fixed, 3 partly, N1-N3 new; all folded in; both recorded in `readiness.md`) |
| 11 | FAIL (R11-M1 and the round-11 findings); fixed in revision 11, after a pre-commit fresh-context audit of the revision-11 changes (REFUTED: 2 major, 3 minor, 3 nits) and its recheck (REFUTED: all 8 fixed; N1 (major), N2 and N3 new, all folded in); both recorded in `readiness.md` |
| 12 | FAIL against `7bf441c` (2 major: R12-M1, the TEST Apply role's deny-all hold `Issue215CutoverSessions` not planned; R12-M2, no creator for the ECS roles' permissions boundaries and execution-role grants; 4 minor: R12-m1 installer identity, R12-m2 Lambda ENI scope, R12-m3 step-18 detach ownership, R12-m4 S5.24a fit-first; 3 nits: R12-n1…n3); fixed in revision 12, after a pre-commit fresh-context audit of the revision-12 changes (REFUTED: 1 major, 9 minor, 8 nits, all fixed) and its recheck (REFUTED on minors only; the new items A-H folded in by the final pass; both recorded in `readiness.md`) |
| 13 | FAIL against `b1ed572` (0 major; 2 minor: R13-m1 GetRole returns no managed attachments, R13-m2 row-8 PassRole allow half; 7 nits: R13-n1…n7); fixed in revision 13 (wording only; no pre-commit audit, the next independent round verifies it) |

Stage status: **BLOCKED** until an independent review of revision 13 reports
PASS. Round 5 was recorded as the last allowed round, and rounds 6, 7, 8,
9, 10, 11, 12 and 13 ran after it; whether another independent round runs is for the coordinator and
the user to decide. `readiness.md` is written by the author and says PENDING;
it is not a PASS.

**Attempt ledger:** canonical `attempts.json` was NOT initialized. The atomic reservation needs verified host write isolation for the copied ledger_reference package, and a same-user host cannot provide it. The ledger is therefore BLOCKED. Attempt count by caller record: 1 procedure run, with 13 recorded review rounds (round 13: FAIL, answered by revision 13). This count is not canonical.

## Acceptance checklist for the next independent reviewer

A reviewer ticks each item from the bundle text and the cited source, not
from this list.

- [ ] Every round-12 finding in `readiness.md` maps to text that
      resolves it at the cited file and line, and the cited source lines
      say what the plan claims (round-11, round-10, round-9 and round-8
      rows, recheck residuals A1…A4, round-7 rows and audit F2, F6 and F8
      stay resolved).
- [ ] `Issue215CutoverSessions` is named in AD-26 layer 2, XP-11 and PRD
      §7; XP-18 (its BI retirement, read back absent, and the PROD Apply
      read-back) precedes row 9 with a STOP; gate 1, S4.6 steps 3-4, S5.2's
      matrix and S4.7 check it; step 4 routes an explicit-deny
      `AccessDenied` to XP-18 before any `resume` (R12-M1).
- [ ] S5.1's ECS runtime stacks create each ECS role's retained
      `-Boundary` policy at `/issue219/{env}/boundary/` and workload-shaped
      `-Guard`, the execution role's log-stream writes and, for TEST, its
      `execution_policy()` pull grant; the PROD pull part is S5.24a's PROD
      ECS amendment after XP-14; S5.4 lists `Modify` rows on the
      boundaries and guards; the verifier, S4.6 step 3, S4.7 and S4.14's
      `_role`/`_pull` fixtures cover them; XP-16 is S5.1's and row 49
      holds XP-15 only (R12-M2).
- [ ] XP-17 names the reviewed installer role, its minimum permissions,
      its per-install evidence, the unguarded-identity residual and the
      condition under which it becomes a user decision (R12-m1).
- [ ] Only `ec2:DescribeNetworkInterfaces` and `ec2:DescribeSubnets` stay
      on `*`; the four mutating ENI actions are resource-scoped with V-29
      live and fallback steps never wider than
      `arn:aws:ec2:eu-central-1:<account>:*` without a user decision;
      `lambda:UpdateFunctionConfiguration` and `lambda:UpdateFunctionCode`
      rows deny every CI and operator principal from S5.3 on; NFR-06
      states the no-resource-type rule (R12-m2).
- [ ] S5.5 owns the bootstrap job's step-18 detach and step-20 re-attach,
      both are serialized in row 43, and XP-8 items 1-4 repeat after the
      rebuild (R12-m3); S5.24a's PROD Apply reads go fit-first (R12-m4).
- [ ] Every new IAM principal (the TEST and PROD ECS roles, the function
      roles, the restore, exercise and recovery roles, and any missing
      service-linked role) is created by an independent CloudFormation
      stack per role family with a reviewed template and hash, a human
      non-root installer, change-set evidence, a post-create verifier
      and `@Kravalg`'s approval, and every later grant on it is a
      reviewed stack amendment; no guard's Resource-`*` deny is narrowed
      and the governor-guard route is recorded as a user decision not
      taken (R11-M1).
- [ ] The TEST ECS roles have one owner, S5.1, which adopts #219's names
      and PassRole fragments, and S5.2's PassRole depends on it (R11-M1).
- [ ] Every seed operation (catalog amendment, stack install, stack
      amendment) is in the one-open serialization with its row; guard
      rows compare with each story's baseline catalog; the matrices carry
      `iam:CreateRole`-denied and exact-ARN applier rows (R11-M1).
- [ ] A new managed policy lists the five governance changes and names
      `G-GitHubGovernanceApply` (R11-m1); no CI role gets
      `iam:CreateServiceLinkedRole`, and the five SLRs are an S4.6 step-1
      `iam:GetRole` precondition with an independent-owner creator
      (R11-m2); S4.10's ARM64 tests need no higher row (R11-m3); the
      publisher platform is the committed `publish_platform` field at job
      level, never `client_payload` (R11-m4); the #284 and #285 facts,
      S5.2's post-#284 baseline, D-15 option (a) and the layer count are
      exact (R11-n1…n4).
- [ ] D-15 is recorded in `decisions.md` with the user's wording and date,
      in PRD §6, in every D-1…D-15 range and list (PRD, architecture,
      epics, brief), the epics inventory and ordered row 0; S4.14 owns the
      code change (both contract schemas carry `certificate_arn`, the
      runner rule becomes `workload-certificate-arn-required`, the SSM read
      path is removed, the pinned tests and `specs/poc-workload-runner.md`
      are updated); XP-10 and XP-15 are the gateway-supplied ARN pinned by
      a reviewed USI contract PR, with the fail-closed replacement window
      recorded as an operating residual; S4.17 takes the ARN from the
      applied contract.
- [ ] Architecture AD-26: no `ssm:GetParameter` carve-out remains for any
      role; XP-11 and S5.24a grant only `iam:GetRole`,
      `iam:SimulatePrincipalPolicy` (execution role only for Apply),
      the three ECR pull reads and `acm:DescribeCertificate`; the ECR
      token stays removed with the fail-closed open point V-28 (S4.6 step
      1); the IAM layers are named (six since revision 11, R11-n4: identity allows scoped to the USI
      identity; `DenySecretLeakingReads` and `DenySecretLeakingReadsApply`
      unchanged; the seed guards unchanged (relative to each story's baseline catalog since revision 11); the seed-owned boundary
      amended only through seed catalog amendments with a new catalog hash
      pin, a named seed owner, CloudFormation change-set evidence,
      `@Kravalg`'s approval and a 6144-character size check or the
      service-family ceiling fallback); the XP-11, S5.24a and S5.24b
      matrices carry SSM-denied, guard-layer, renderer-scope, ConfigRead
      and attachment rows; the seed's Apply attachment constraint is
      AD-26 layer 5 (R10-M1, R10-m1, R10-n3; pre-commit audit 1 and 4).
- [ ] The certificate-replacement residual (PRD §7 XP-10) is exact, and
      its gap with D-15's accepted rationale is surfaced to the user in
      `readiness.md` "Remaining user decisions", not decided.
- [ ] FR-14 (a) ARM64 has owners for every AMD64 pin (S4.9 admission,
      S4.10 topology, S4.14 capabilities, projection and the publisher
      request's platform, `docs/poc-workload-admission.md` line 111;
      R10-n6, recheck of audit 2).
- [ ] Seed amendments are serialized in C-BI order (#219's, S5.2, S5.17,
      S5.4, XP-11 in row 42, XP-14's PROD addition, S5.24a, S5.24b), with
      no forward dependency (R10-m2).
- [ ] S5.24 and S4.17 name `s3:GetBucketVersioning`; the TEST grants need
      the capability `enabled`, and `withdrawn` is a STOP; XP-14 owns the
      PROD Preview and Apply versioning read (R9-m1).
- [ ] The Drift role's deny is unchanged, and AD-26 has its
      reachable-privilege table and the repository-policy check (R9-m2).
- [ ] S4.17 publishes one record per successful run: worker copy to
      `/public/workload-drift-result/record.json`, host copy-out, one
      pinned upload directly after `execute` with
      `if-no-files-found: error`; the S4.15 items carry `artifact_id` and
      `artifact_sha256` (R8-M1).
- [ ] S4.17 is data-driven per stack (`registry-phase` record on
      `phase: registry`), and gate 2b needs a TEST `checked` record and a
      PROD `before-acceptance` record with `null` success-receipt fields
      after the flip, plus the S5.24a/S5.24b PROD simulator evidence
      (R8-m1, R9-n1).
- [ ] S4.14's first case is the grep inventory, and every hit has an owner
      or an exclusion reason (R8-m2).
- [ ] The S4.17 projection is built only from the receipt, fresh reads are
      comparisons, and an installed program that differs from the applied
      base fails with `workload-drift-installed-program-changed` (R8-m4).
- [ ] S4.14 lists every workflow-shape pin the PROD jobs break with its
      exact new assertion (R7-M1), and every TEST-only pin on the PROD path
      has a PROD fixture or an XP-14 assignment (R7-m3); the PROD host tests
      stub the XP-14 observer coordinates, and S4.7 owns the unstubbed case.
- [ ] S4.17 runs in the isolated worker container with scheduled-main
      provenance, calls no PR-bound function, projects from the latest
      success receipt and the contract it applied, and writes a
      `checked`/`before-acceptance` record; only `checked` satisfies gate 2b.
- [ ] `workload_route` comes from the authenticated receipt lineage; a
      pre-acceptance `rollback-zero` or `policy-update` runs no drift job.
- [ ] The PROD contract schema is S4.14's, S4.7 owns the PROD workload
      contract PRs, and S5.24 grants the Drift-role reads before S4.17 and
      the PROD Preview and Apply observation reads before gate 2a.
- [ ] D-1…D-7, D-14, D-15 and D-8…D-13 are dated 2026-09-30 in `decisions.md`;
      RPO ≤ 1 hour and RTO ≤ 24 hours are labelled user decision D-14
      everywhere, and only the 20% TEST cost threshold and the PROD
      justification rule are labelled planning defaults.
- [ ] The PRD §1 counts equal the tables: 35 FRs, 11 NFRs, 46 total; 41
      offline-testable; 5 evidence-only NFRs; 34 FRs with live evidence (all
      but FR-29).
- [ ] The FR-32 check is on the executed workload drift path (the new
      `test_workload_drift` job → worker → runner → `_dispatch_command("plan")`
      with the drift gate → `poc_workload_reconciliation.validate_drift`),
      the preview role produces the gate-2 clean-drift evidence, the
      registry chain (`test_post_apply_drift` → `test_registry_*`) is
      unchanged, `scheduled-drift.yml` excludes workload-phase stacks with
      a recorded reason, S4.17 adds scheduled workload drift before gate
      2b, and nothing is planned in `scripts/run_pulumi_drift_check.py`.
- [ ] Every workflow-shape test that pins the CI graph has an owning story
      (S4.11, S4.13, S4.14, S4.17), a new closed set with the negatives
      kept, and a `@Kravalg`-specific approval requirement.
- [ ] Every recovery subcommand that writes the checkpoint writes a receipt;
      `clear-pending` → `resume` is admitted offline.
- [ ] `scaling` has one `at` per action; earlier entries are immutable once
      in state; the window applies only to the new entry.
- [ ] S1.11 follows S2.1 and S1.8 (C-contract S1.1 → S1.7 → S1.9 → S1.8 →
      S1.11 → S4.10), and S4.9 precedes S4.2 (S4.10 → S4.11 → S4.9 → S4.2 →
      S4.3).
- [ ] S4.10 owns the narrow `ignoreChanges`/`retainOnDelete` allowance in
      `poc_workload_reconciliation.py` and `poc_workload_topology.py`.
- [ ] FR-35 and the C-runner chain (S4.1 → S4.4 → S4.5 → S4.11 → S4.12 →
      S4.13 → S4.14) precede S4.6, S4.17 follows XP-14, XP-15, XP-16 and
      S5.24, and S4.7 follows S4.17 in C-runner (R8-m7); the
      failure-path receipt, including one after a failed result inspection,
      is published by `test_apply_receipt`.
- [ ] Step 2 starts tasks with a create-only one-time action (V-23);
      `rollback-zero` has three phases: `stop` (create-only), `hold` (TEST
      only, one `suspendedState` update per target) and `start` (flag clear
      plus a create-only start action); V-23(e) is the provider-source first
      case of S2.1 and S4.9; TEST schedules are in the step-2 set.
- [ ] The observation runs in its own job for start and stop actions,
      captures the checkpoint under the preview role, and the credential-free
      acceptance job verifies that artifact; `hold` needs the stop
      observation and only `hold`/`start` change
      `scaling.scheduled_scaling_suspended`; the apply's FR-24 bounds are
      unchanged.
- [ ] S4.14 lists every TEST-only pin with a PROD fixture or assigns it to
      XP-14, and the PROD stack-to-contract mapping is defined.
- [ ] The restore rehearsal is a point-in-time restore
      (`UseLatestRestorableTime`), and the achieved recovery point is the
      RPO evidence.
- [ ] USI's own repository controls apply the five Kravalg-only
      environments (S5.21) and the pinned `abandon-manifest-approval` check
      (S5.22).
- [ ] The V-3 fallback is an update-only `policy-update`, never a delete.
- [ ] S5.18a precedes step 1 and S5.18b follows XP-8.
- [ ] The ordered list has no forward dependency.
- [ ] `readiness.md` does not claim PASS and names its author.
- [ ] The artifact hashes above match the committed files
      (`sha256sum -c`).

## Scope limits of revisions 4, 5, 6, 7, 8, 9, 10, 11 and 12

- No aws or pulumi command ran against any account; no repository test, lint
  or preview ran; no secret value was read; nothing was pushed or commented.
- The only local commands were file reads and greps of this repository and
  the read-only bootstrap-infrastructure clone, AWS documentation lookups
  (aws-knowledge MCP in revisions 4, 9 and 12, and by the revision-11
  recheck auditor; revision 12 also fetched the public Service
  Authorization Reference JSON files with `curl`), Python text edits and table checks
  over the bundle, `sha256sum`, and a local `git commit` of the bundle.
  Revision 7 also ran one read-only fresh-context audit subagent
  (`claude-router:audit`) over the uncommitted changes. Revision 8 read
  the bootstrap-infrastructure clone and its fetched `origin/main` with
  `git show` and `grep` only (no fetch, no checkout), and ran one
  read-only fresh-context audit subagent over the uncommitted changes.
  Revision 9 did the same over `origin/main` and the `wt-boot-219`
  worktree, made one aws-knowledge MCP documentation lookup, and ran one
  read-only fresh-context audit subagent over the uncommitted changes,
  plus its recheck, before the single commit. Revision 10 read BI
  `origin/main` through the `wt-boot-urllib3` worktree and `wt-boot-219`
  with `git log`, `git diff --stat`, `sed` and `grep` only (no fetch, no
  checkout), ran read-only Python evaluations of the seed catalogs (the
  guard statements against the planned actions, and the boundary size),
  and ran one read-only fresh-context audit subagent over the uncommitted
  changes, plus its recheck, before the single commit. No AWS
  documentation lookup ran in revision 10. Revision 11 read BI
  `origin/main` through `wt-boot-urllib3`, #284 through `wt-boot-pr280`
  and #285 through `wt-boot-219` with `sed`, `grep`, `git log`,
  `git diff --stat` and `git merge-base` only (no fetch, no checkout),
  ran read-only Python evaluations of the seed catalogs (the guard
  statement lists and the post-#284 boundary size), made no AWS
  documentation lookup itself (corrected in revision 12, R12-n2: its
  recheck auditor read the Lambda VPC page through the aws-knowledge MCP,
  now recorded in Inputs), and ran one read-only fresh-context audit
  subagent over the uncommitted changes, plus its recheck, before the
  single commit. Revision 12 read BI `origin/main` through
  `wt-boot-urllib3`, #284 through `wt-boot-pr280` and #285 through
  `wt-boot-219` with `sed`, `grep` and `git log` only (no fetch, no
  checkout), ran read-only Python over the seed catalogs (the principal
  count, statement lines), read AWS documentation (Inputs), ran one
  read-only `Explore` subagent over `git show 7bf441c`, and ran one
  read-only fresh-context audit subagent over the uncommitted changes,
  plus its recheck, before the single commit.
