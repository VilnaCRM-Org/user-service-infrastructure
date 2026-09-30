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
| Bundle revision | 3 (answers readiness round 3; parent commit 3f0930a) |
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
- AWS documentation, via aws-knowledge MCP (see research §3); revision 3 re-verified A-16 (REST API VPC link V2 → ALB), A-20 (SES API VPC endpoints), A-23 (ElastiCache IAM limits), A-24 (`StsGetCallerIdentityCalls`) and A-25 (managed DocumentDB rotation) on 2026-09-30
- Local provider source: `pulumi_aws` 7.23.0 `apigateway.Integration.integration_target` (read-only grep of the installed SDK)
- User decisions given in chat on 2026-09-30 (D-1, D-2, D-3, D-6; D-4/D-5 defaults pending; D-7 open), relayed by the coordinator
- Read-only cross-repository reconnaissance: bootstrap-infrastructure @debd88b, api-gateway-infrastructure, and user-service @main via `gh api`

## Artifacts (sha256, revision 3)

`run-summary.md` is not hashed here, because it contains the hashes.

```
b96efb367ba2e171cd6d165770f331b0ad1e211c9b0f4503bb67718c0f0ca027  research.md
4d9d402061cb5d86f93e8f21259ada2b962bccc6eef9b12cdf88ef01fd6cbbb9  brief.md
0524f671ef34d27d5d16785c5c146f57c1e9b3fe1bf5b366dcde1a7b0c012d70  prd.md
502a31b063689ed5997ff6a381c44f8be24b21fd911290d4ba5fae52c011fb7a  architecture.md
ad1261321ca80a6437bc8f2871ddfe59e45bbd9c1e7450283703854095f9fe37  epics-stories.md
2065cb7bd344a1970f41c5cc67323019ce040ef3eb26d5f95853f614c3238757  readiness.md
```

## Gates

**Independent readiness:**

| Round | Result |
| --- | --- |
| 1 | FAIL (3 blocking, 10 major); fixed in revision 2 |
| 2 | Result not stored in this bundle |
| 3 | FAIL (B-1, B-2, M-1…M-13, m-1…m-12); fixed in revision 3 |
| 4 | Requested; not run |

Stage status: **BLOCKED** until an independent round-4 review reports PASS.
`readiness.md` is written by the author and says PENDING; it is not a PASS.

**Attempt ledger:** canonical `attempts.json` was NOT initialized. The atomic reservation needs verified host write isolation for the copied ledger_reference package, and a same-user host cannot provide it. The ledger is therefore BLOCKED. Attempt count by caller record: 1 procedure run, with 3 of 5 review rounds used and round 4 pending. This count is not canonical.

## Acceptance checklist for the round-4 reviewer

A reviewer ticks each item from the bundle text, not from this list.

- [ ] Every round-3 finding in `readiness.md` maps to text that resolves it at
      the cited file and line.
- [ ] The PRD §1 counts equal the tables: 34 FRs, 11 NFRs, 45 total; 40
      offline-testable; 5 evidence-only NFRs; 33 FRs with live evidence (all
      but FR-29).
- [ ] No Redis password, Redis secret, Redis rotation Lambda or rotation SG
      remains (D-1); the `default` user with access string `off` remains.
- [ ] Every VPC-attached function has its APIs and network path listed
      (`architecture.md` §2.1), and each path exists in FR-17/FR-18.
- [ ] C-BI creates every role before any key (S5.1 → … → S5.4 → S5.3).
- [ ] Preview and drift read capability (FR-33, S5.17) precedes S4.6.
- [ ] XP-8 carries subnet IDs, the bootstrap-job SG ID and the
      DocumentDB-managed secret ARN; no text claims patterns cover that secret.
- [ ] Every V-item has a method, an offline story and, if live, an S4.6 step
      with a STOP or fallback.
- [ ] Recovery import and abandon run as saved plans through the classifier;
      abandon exists only if D-7 decides so; the manifest carries a
      `secret_recovery_decision` per secret.
- [ ] Endpoint policies are pinned documents, including the ECR layer bucket.
- [ ] The seed is idempotent, its input immutable, and an Invocation replace
      or delete is critical.
- [ ] Step 2 is create-only and its admission lives in C-contract (S4.9).
- [ ] Gate 1 lists stories, BI prerequisites and decisions explicitly; a
      default is not a resolution; D-7 has no default.
- [ ] Gate 2 re-checks gate 1 and requires the schema-validated receipt.
- [ ] Every §5 row has P, N and B cells.
- [ ] `readiness.md` does not claim PASS and names its author.
- [ ] The artifact hashes above match the committed files.

## Scope limits of revision 3

- No aws or pulumi command ran against any account; no repository test, lint
  or preview ran; no secret value was read.
- The only local commands were file reads, greps of the repository and the
  installed Pulumi SDK, and `sha256sum`.
