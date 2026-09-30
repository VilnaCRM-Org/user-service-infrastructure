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
| Bundle revision | 6 (answers readiness round 6; parent commit 68584e1, which is revision 5 (7d55105) plus the D-14 record) |
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

## Artifacts (sha256, revision 6)

`run-summary.md` is not hashed here, because it contains the hashes. `decisions.md` is a planning input and is hashed. Commit `68584e1` added its D-14 row after revision 5; revision 6 changes only that row's label (a user decision, not a planning default).
Check with `sha256sum -c` over the block below, from `specs/workload-wa-hardening/`.

```
beca16ba9ab95d76cd28ed47ac8e806549b94805ddca9a2d138a790ee0f0ca59  research.md
6633d77ef016cf1c5238ca357011ccec1e47f627063432037711a0c2f274e409  brief.md
94fb859a38d75be101d5b0fd53942976ed23dcab9dd48eae516f728157179aed  prd.md
2b92e27989f20b468a06998a5401da15fe752e7b00fa1d4e1e0ec1a9ec3086e2  architecture.md
99bad4c768de84af3525d3b885811fd001eeeadb96b9cbd48844b98752ce5c0c  epics-stories.md
4f2911c3b75d890ad0d37b161cf5568909f049d51bf289509cc14f66d5f2a76e  decisions.md
266dbe081058f9c2ec81fd6b2d60013b2c106497f57849cc328c6e7405326206  readiness.md
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

Stage status: **BLOCKED** until an independent review of revision 6 reports
PASS. Round 5 was recorded as the last allowed round, and round 6 ran after
it; whether another independent round runs is for the coordinator and the
user to decide. `readiness.md` is written by the author and says PENDING;
it is not a PASS.

**Attempt ledger:** canonical `attempts.json` was NOT initialized. The atomic reservation needs verified host write isolation for the copied ledger_reference package, and a same-user host cannot provide it. The ledger is therefore BLOCKED. Attempt count by caller record: 1 procedure run, with 6 recorded review rounds (round 6: FAIL, answered by revision 6). This count is not canonical.

## Acceptance checklist for the next independent reviewer

A reviewer ticks each item from the bundle text and the cited source, not
from this list.

- [ ] Every round-6 finding in `readiness.md` maps to text that resolves it
      at the cited file and line, and the cited source lines say what the
      plan claims.
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
      S4.13 → S4.14) precede S4.6, and S4.17 follows XP-14; the
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

## Scope limits of revisions 4, 5 and 6

- No aws or pulumi command ran against any account; no repository test, lint
  or preview ran; no secret value was read; nothing was pushed or commented.
- The only local commands were file reads and greps of this repository and
  the read-only bootstrap-infrastructure clone, AWS documentation lookups
  (aws-knowledge MCP, revision 4 only), Python text edits and table checks
  over the bundle, `sha256sum`, and a local `git commit` of the bundle.
