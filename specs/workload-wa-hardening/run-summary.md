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
| Bundle revision | 4 (answers readiness round 4; parent commit 1ebbd09, which recorded D-1…D-7) |
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

## Artifacts (sha256, revision 4)

`run-summary.md` is not hashed here, because it contains the hashes. `decisions.md` is a planning input and is hashed.

```
beca16ba9ab95d76cd28ed47ac8e806549b94805ddca9a2d138a790ee0f0ca59  research.md
46c1ba7c79a6f07361df9a2736f7a3454f68c5048a9f946a1d53ac6ce9879036  brief.md
608b4f01dfc1d517dd1882fd4cc8a298a7976e18a563f2befd31bf7688cb9e88  prd.md
019a38fcbbad557396a7f116600b04312102ad5dc7878af33c6f1184af5825c0  architecture.md
f9044df23a124e5bab8dfeef7653d434f011ea82a3f8cff9916b10cdc183930e  epics-stories.md
beaf6b72a82aa0a61936de4edcf9d9b4eb1c3876962a683d62c827de67051048  decisions.md
491d1ac1f9251031772ff8d8f9edbffc2facdc0c9cda1fcd43dc3c804955eebb  readiness.md
```

## Gates

**Independent readiness:**

| Round | Result |
| --- | --- |
| 1 | FAIL (3 blocking, 10 major); fixed in revision 2 |
| 2 | Result not stored in this bundle |
| 3 | FAIL (B-1, B-2, M-1…M-13, m-1…m-12); fixed in revision 3 |
| 4 | FAIL (R4-B1…B3, R4-M1…M10, m1…m12); fixed in revision 4 |
| 5 | Requested; not run (last allowed round) |

Stage status: **BLOCKED** until the independent round-5 review reports PASS.
`readiness.md` is written by the author and says PENDING; it is not a PASS.

**Attempt ledger:** canonical `attempts.json` was NOT initialized. The atomic reservation needs verified host write isolation for the copied ledger_reference package, and a same-user host cannot provide it. The ledger is therefore BLOCKED. Attempt count by caller record: 1 procedure run, with 4 of 5 review rounds used and round 5 (the last) pending. This count is not canonical.

## Acceptance checklist for the round-5 reviewer

A reviewer ticks each item from the bundle text and the cited source, not
from this list.

- [ ] Every round-4 finding in `readiness.md` maps to text that resolves it
      at the cited file and line, and the cited source lines say what the
      plan claims.
- [ ] D-1…D-7 are dated 2026-09-30 resolutions in `decisions.md`, PRD §6,
      the brief and the epics; no "pending", "default" or "only if D-7"
      wording remains; S5.15 is dropped.
- [ ] The PRD §1 counts equal the tables: 35 FRs, 11 NFRs, 46 total; 41
      offline-testable; 5 evidence-only NFRs; 34 FRs with live evidence (all
      but FR-29).
- [ ] FR-35 and the C-runner chain (S4.4 → S4.5 → S4.11 → S4.12 → S4.13 →
      S4.14) precede S4.6; the README line-127 and test line-175/185
      amendment is in S4.13.
- [ ] The `secretsmanager` endpoint policy has no XP-8 value.
- [ ] S4.10 is the only writer of the topology, secret-history checker and
      native integration test; the transition rule is stated.
- [ ] Abandon compares every `delete` of every type 1:1, allows only
      `delete`/`same`, retains the log buckets, names the recovery identity
      and grants, needs Kravalg specifically, and runs at steps 18–20.
- [ ] Step 2 starts tasks with a create-only one-time action (V-23);
      `rollback-zero` is create-only; TEST schedules are in the step-2 set.
- [ ] The V-3 fallback is an update-only `policy-update`, never a delete.
- [ ] S5.18a precedes step 1 and S5.18b follows XP-8.
- [ ] AD-15a lists principal, actions and conditions per key.
- [ ] V-21 and V-22 cover the managed-password and restore grants.
- [ ] XP-9…XP-13 are gate-1 checks.
- [ ] The ordered list has no forward dependency.
- [ ] `readiness.md` does not claim PASS and names its author.
- [ ] The artifact hashes above match the committed files.

## Scope limits of revision 4

- No aws or pulumi command ran against any account; no repository test, lint
  or preview ran; no secret value was read; nothing was pushed or commented.
- The only local commands were file reads and greps of this repository and
  the read-only bootstrap-infrastructure clone, AWS documentation lookups
  (aws-knowledge MCP), a Python table and count check over the bundle, and
  `sha256sum`.
