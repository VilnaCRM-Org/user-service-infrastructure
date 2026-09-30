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
| Bundle revision | 9 (answers readiness round 9: R9-M1, R9-m1, R9-m2, R9-n1…n4; parent commit c61d8d6, which is revision 8) |
| Specs directory | `specs/workload-wa-hardening/` (slug chosen by the caller) |
| Target | pulumi (Python Pulumi), stacks test and prod |
| Environment | none selected; planning is offline |
| Stage | do-sdlc-plan |
| Date (UTC) | 2026-09-30 |

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
- User decisions given in chat on 2026-09-30 and relayed by the coordinator: D-1…D-7 (`decisions.md`). The D-4 and D-5 clarifications came in a second message the same day, and D-8…D-13 (derived details) were confirmed in a third. D-14 (recovery targets RPO ≤ 1 hour, RTO ≤ 24 hours) is a user decision of the same date, recorded in `decisions.md` by commit `68584e1`.
- Read-only cross-repository reconnaissance: bootstrap-infrastructure @debd88b, api-gateway-infrastructure, and user-service @main via `gh api`

## Artifacts (sha256, revision 9)

`run-summary.md` is not hashed here, because it contains the hashes. `decisions.md` is a planning input and is hashed. Commit `68584e1` added its D-14 row after revision 5; revision 6 changed only that row's label (a user decision, not a planning default); revisions 7, 8 and 9 do not change it. `research.md` and `brief.md` are unchanged in revision 9, and `research.md` since revision 4.
Check with `sha256sum -c` over the block below, from `specs/workload-wa-hardening/`.

```
beca16ba9ab95d76cd28ed47ac8e806549b94805ddca9a2d138a790ee0f0ca59  research.md
d4ab4288bd8b99daa5fc9181db040dcd49a22593670c1820412480559c68fd3a  brief.md
287d3c975932b087b2bc4071de2058ba3c87d0eea62445ef004d98905b567947  prd.md
d06b26bb74820acfcfec975d6abbbcd0a6db92da675612d750403e5ea125d626  architecture.md
7e6566e54a491cd7d79a3abb580f07079e0d240f17d4941c0636b21eca7374ce  epics-stories.md
4f2911c3b75d890ad0d37b161cf5568909f049d51bf289509cc14f66d5f2a76e  decisions.md
1d8d6581f2afc74a4cef1b25d61a42d81c1bb1a21ccc6eadc29f42c58989e23c  readiness.md
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

Stage status: **BLOCKED** until an independent review of revision 9 reports
PASS. Round 5 was recorded as the last allowed round, and rounds 6, 7, 8
and 9 ran after it; whether another independent round runs is for the coordinator and
the user to decide. `readiness.md` is written by the author and says PENDING;
it is not a PASS.

**Attempt ledger:** canonical `attempts.json` was NOT initialized. The atomic reservation needs verified host write isolation for the copied ledger_reference package, and a same-user host cannot provide it. The ledger is therefore BLOCKED. Attempt count by caller record: 1 procedure run, with 9 recorded review rounds (round 9: FAIL, answered by revision 9). This count is not canonical.

## Acceptance checklist for the next independent reviewer

A reviewer ticks each item from the bundle text and the cited source, not
from this list.

- [ ] Every round-9 finding in `readiness.md` maps to text that resolves
      it at the cited file and line, and the cited source lines say what
      the plan claims (round-8 rows, recheck residuals A1…A4, round-7 rows
      and audit F2, F6 and F8 stay resolved).
- [ ] Architecture AD-26: the non-weakening evaluation is recorded (the ECR
      token removed by S4.14's `GetDownloadUrlForLayer` config read,
      adopted with a fail-closed live open point; the PR-path certificate
      parameter kept, with the contract-ARN alternative left to the user;
      the Drift SSM read dropped by S4.17). The only narrowing is
      `ssm:GetParameter` on the exact certificate parameter for the
      Preview and Apply roles: TEST through XP-11 (gate 1) and PROD
      through S5.24a (row 50, before gate 2a; the Drift grants are the
      separately approved S5.24b). Every new allow is also added to the
      `GovernanceBoundary-<project>-<env>` permissions boundary. The
      narrowing is under the BI review approved by `@Kravalg`, fails
      closed, and has one simulator matrix per owner (R9-M1).
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
- [ ] D-1…D-7, D-14, and D-8…D-13 are dated 2026-09-30 in `decisions.md`;
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

## Scope limits of revisions 4, 5, 6, 7, 8 and 9

- No aws or pulumi command ran against any account; no repository test, lint
  or preview ran; no secret value was read; nothing was pushed or commented.
- The only local commands were file reads and greps of this repository and
  the read-only bootstrap-infrastructure clone, AWS documentation lookups
  (aws-knowledge MCP, revisions 4 and 9 only), Python text edits and table checks
  over the bundle, `sha256sum`, and a local `git commit` of the bundle.
  Revision 7 also ran one read-only fresh-context audit subagent
  (`claude-router:audit`) over the uncommitted changes. Revision 8 read
  the bootstrap-infrastructure clone and its fetched `origin/main` with
  `git show` and `grep` only (no fetch, no checkout), and ran one
  read-only fresh-context audit subagent over the uncommitted changes.
  Revision 9 did the same over `origin/main` and the `wt-boot-219`
  worktree, made one aws-knowledge MCP documentation lookup, and ran one
  read-only fresh-context audit subagent over the uncommitted changes,
  plus its recheck, before the single commit.
