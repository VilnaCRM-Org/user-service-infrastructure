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
| Bundle revision | 5 (answers readiness round 5; parent commit 57f38aa, revision 4) |
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
- User decisions given in chat on 2026-09-30 and relayed by the coordinator: D-1…D-7 (`decisions.md`). The D-4 and D-5 clarifications came in a second message the same day, and D-8…D-13 (derived details) were confirmed in a third.
- Read-only cross-repository reconnaissance: bootstrap-infrastructure @debd88b, api-gateway-infrastructure, and user-service @main via `gh api`

## Artifacts (sha256, revision 5)

`run-summary.md` is not hashed here, because it contains the hashes. `decisions.md` is a planning input and is hashed (unchanged in revision 5).
Check with `sha256sum -c` over the block below, from `specs/workload-wa-hardening/`.

```
beca16ba9ab95d76cd28ed47ac8e806549b94805ddca9a2d138a790ee0f0ca59  research.md
bc15290586a30ad04e127dad20bd9e95246d3b7a8633c7a3136a08a78415931b  brief.md
0c25e3c0da7c8b9522c0b9f5cd6aeb7bedb354be34af4eaeb3fa37e6a2e66dea  prd.md
221a09f653abb6e058028805f28766ac076af1a080933e46893e1b562c0d8df1  architecture.md
06f4d6041cc4430a0d34378cab4da0fee04e5fd37aa352deaa1d1287db375dbf  epics-stories.md
d2b75ec8cfbd8bd07790f43db97409ad782c645ccbea88ae3ffae7d3627bb2c3  decisions.md
357f82db218efad3188f46a01a239e8928521481678ba386a05db41f6890db72  readiness.md
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

Stage status: **BLOCKED** until an independent review of revision 5 reports
PASS. Round 5 was recorded as the last allowed round; whether another
independent round runs is for the coordinator and the user to decide.
`readiness.md` is written by the author and says PENDING; it is not a PASS.

**Attempt ledger:** canonical `attempts.json` was NOT initialized. The atomic reservation needs verified host write isolation for the copied ledger_reference package, and a same-user host cannot provide it. The ledger is therefore BLOCKED. Attempt count by caller record: 1 procedure run, with all 5 recorded review rounds used (round 5: FAIL, answered by revision 5). This count is not canonical.

## Acceptance checklist for the next independent reviewer

A reviewer ticks each item from the bundle text and the cited source, not
from this list.

- [ ] Every round-5 finding in `readiness.md` maps to text that resolves it
      at the cited file and line, and the cited source lines say what the
      plan claims.
- [ ] D-1…D-7, D-14, and D-8…D-13 are dated 2026-09-30 in `decisions.md`; the RPO,
      RTO and cost-threshold values are labelled with D-14 references, not user
      decisions.
- [ ] The PRD §1 counts equal the tables: 35 FRs, 11 NFRs, 46 total; 41
      offline-testable; 5 evidence-only NFRs; 34 FRs with live evidence (all
      but FR-29).
- [ ] The FR-32 check is on the executed workload drift path
      (`test_post_apply_drift` → worker → runner → `workload-drift` →
      `poc_workload_reconciliation.validate_drift`), the preview role
      produces the gate-2 clean-drift evidence, `scheduled-drift.yml`
      excludes workload-phase stacks with a recorded reason, and nothing is
      planned in `scripts/run_pulumi_drift_check.py`.
- [ ] Every recovery subcommand that writes the checkpoint writes a receipt;
      `clear-pending` → `resume` is admitted offline.
- [ ] `scaling` has one `at` per action; earlier entries are immutable once
      in state; the window applies only to the new entry.
- [ ] S1.11 follows S2.1 and S1.8 (C-contract S1.1 → S1.7 → S1.9 → S1.8 →
      S1.11 → S4.10).
- [ ] S4.10 owns the narrow `ignoreChanges`/`retainOnDelete` allowance in
      `poc_workload_reconciliation.py` and `poc_workload_topology.py`.
- [ ] FR-35 and the C-runner chain (S4.1 → S4.4 → S4.5 → S4.11 → S4.12 →
      S4.13 → S4.14) precede S4.6; the failure-path receipt is published by
      `test_apply_receipt`.
- [ ] Step 2 starts tasks with a create-only one-time action (V-23);
      `rollback-zero` has three phases: `stop` (create-only), `hold` (TEST
      only, one `suspendedState` update per target) and `start` (flag clear
      plus a create-only start action); V-23(e) is the provider-source first
      case of S2.1 and S4.9; TEST schedules are in the step-2 set.
- [ ] The health observation runs in its own job; the apply's FR-24 bounds
      are unchanged.
- [ ] USI's own repository controls apply the five Kravalg-only
      environments (S5.21) and the pinned `abandon-manifest-approval` check
      (S5.22).
- [ ] The V-3 fallback is an update-only `policy-update`, never a delete.
- [ ] S5.18a precedes step 1 and S5.18b follows XP-8.
- [ ] The ordered list has no forward dependency.
- [ ] `readiness.md` does not claim PASS and names its author.
- [ ] The artifact hashes above match the committed files
      (`sha256sum -c`).

## Scope limits of revisions 4 and 5

- No aws or pulumi command ran against any account; no repository test, lint
  or preview ran; no secret value was read; nothing was pushed or commented.
- The only local commands were file reads and greps of this repository and
  the read-only bootstrap-infrastructure clone, AWS documentation lookups
  (aws-knowledge MCP, revision 4 only), Python text edits and table checks
  over the bundle, `sha256sum`, and a local `git commit` of the bundle.
