# TEST PoC desired contract

`poc-test.json` is the fixed desired-source path for the TEST registry phase.
It declares the two service-owned ECR repositories using the logical names in
`RegistryPlane`. It does not request ECS, networking, secrets or application
deployment.

The central references identify proposed source, not completed installation:

- `inventory_sha256` is the canonical hash of bootstrap's proposed
  `pulumi/seed/catalogs/poc-runtime-test.json` (local source commit `d41c019`).
- `seed_enrollment_revision` pins the proposed TEST policy catalog in bootstrap
  source commit `4a0bd14`, including the bounded ECR capability and bucket
  versioning read for preview, apply and scheduled drift. It is not evidence that
  those policies have been installed.
- The publisher role, workflow and environment are declared by that inventory.
  Registry creation does not establish their existence or activate image publishing.

The document remains `proposed-not-installed`. Its prerequisite strings are
descriptive and cannot authorize deployment. The trusted controller must verify
current review, account/backend identity, actual prior ownership and capability,
then validate and bind the saved plan before execution. Hashes and schema
validation alone do not admit an initial deployment.

After installation, runtime evidence must identify the actual policy revision
and role ownership. A later reviewed workload contract must reference its real
release and external inputs. Never substitute synthetic fixture values for
unresolved runtime evidence.

## Registry execution

The TEST self-deploy workflow authenticates the requested source in a separate
job, then passes its same-run artifact coordinates to the installed-main
`poc_registry_runner.py`. Runtime dependencies are installed before assuming AWS
credentials; execution disables dependency synchronization. The child program
uses the fixed registry implementation and authenticated contract data.

The initial migration preserves the existing stack exports, EnvironmentSettings
component and provider identity. Only the recorded three-resource TEST checkpoint
can use the legacy provider-hardening transition. The resulting eleven-resource
graph contains the original seven registry resources plus the SES identity and
three Easy DKIM DNS records, with no workload or service-owned IAM resources.
Unknown prior state or inaccessible repositories
fail admission.

Apply rechecks requester authorization, reviewed source, backend version and the
complete saved plan immediately before replay. Its postcondition requires the
complete graph. Post-apply drift uses the preview identity and requires every
resource operation to be unchanged. These source controls still require trusted
installation and live acceptance; this document does not claim either is complete.

The scheduled TEST and PROD jobs retain the installed main-only `make test-drift`
route. The candidate `poc_scheduled_registry_drift.py` diagnostic helper is not
connected to that workflow. Integrating it requires separate validation against
the installed controller; the TEST-only launcher does not accept scheduled jobs.
Diagnostic results cannot authorize initialization, a workload transition or
promotion.

Managed workload settings require explicit `executionRoleArn` and `taskRoleArn`
matching the protected account, project and environment. Compute consumes those
central identities and does not create ECS roles or policies. Their existence,
trust, effective permissions and PassRole authorization must still be verified
through the controller before enabling the workload phase.

The internal workload composition generates stable Random/TLS resources and
persists the ten declared secret purposes under their exact names and KMS keys.
Database and Redis connection strings use the same generated credentials as the
services. ECS receives eight distinct consumed secret references through nine
environment names, currently pinned to their versions (planned change: reference
`AWSCURRENT`, see the workload phase switch preconditions below).
`REDIS_LOCKOUT_URL` explicitly uses the same ARN and version as `REDIS_URL`; compiled application defaults do not
recompute that alias. SES uses task-role credentials; social OAuth is disabled.
This source path still needs authenticated secret-history checks and workload
dispatch admission before it can establish first-deployment or rollback acceptance.

The trusted runtime installs AWS 7.23.0, Random 4.19.2 and TLS 5.3.1 before AWS
credentials, using fixed archive and executable SHA-256 pins. Execution rechecks
those binaries and SDK versions, uses a private plugin home, and disables automatic
and ambient plugin acquisition. Installing these binaries does not add provider
resources to the registry graph.

## Release binding prerequisite

Every proposed workload release now declares three registry bindings:

- `registry_phase_receipt_id`: positive GitHub deployment ID, not an artifact ID.
- `registry_contract_digest`: SHA-256 of the complete canonical registry contract.
- `registry_checkpoint_version`: original opaque, non-null S3 checkpoint VersionId.

The existing contract transition validator compares the declared digest with the
supplied previous registry document. `validate_registry_release_binding` also
compares all three fields with a typed `RegistryReleaseBinding` supplied by a
trusted caller. This pure comparison authenticates neither the caller nor the
deployment, checkpoint, application publisher, image digest or secret history.
Updates and rollback retain the release's original registry anchor; it must not
be replaced with the current workload checkpoint version. Synthetic fixtures
remain offline examples and cannot establish deployment readiness.

The reviewed workflow now connects a separate TEST registry observation and
proof after apply and clean drift. The proof reuses the protected
`governance-evidence` environment, trusted `github.sha` checkout and promotion
App deployment-write authority. It needs no new App or service IAM grant. No
live receipt has been produced or accepted yet. The TEST+PROD promotion checks
and status remain separate: a TEST registry result must never set full
`Governance Promotion` success.

The remaining producer/consumer work and acceptance evidence are:

1. Install and live-test the trusted registry observer against the exact final
   eleven-resource checkpoint and native ECR identities after saved apply and
   clean drift. Verify its bounded source/contract, checkpoint version/hash and
   original run/attempt metadata while keeping checkpoint bodies private.
2. Install and live-test the TEST-only proof publication path. Verify the actual
   original workflow/jobs and immutable observation artifacts, the protected App
   issuer and status readback, and the returned deployment ID.
3. Authenticate that deployment and its original run/artifact/checkpoint chain
   before constructing `RegistryReleaseBinding` in publisher/workload admission.
   Install and live-test the source-connected publisher dispatch with an
   application-only Actions token and a pinned protected application revision.
   Reuse the source artifact transport's bounded ZIP/strict metadata checks with
   explicit result member and completed-producer rules; its current in-progress
   `source.json` protocol is not completed registry evidence.
4. Live-test the connected workload path. For a `workload` phase contract the
   worker routes TEST `plan` and `up-plan` through the protected runner, which
   authenticates the application manifest and both ECR images and binds the
   workload component, generated configuration and secret-history checks to
   saved-plan/replay. Workload drift remains rejected until an accepted-workload
   receipt exists. No approval flag or phase-file edit replaces these checks.

## Workload phase hard stop (merge gate, fail closed at CI)

`specs/poc/poc-test.json` `phase` stays `"registry"`. Switching it to
`"workload"` is allowed only in the stacked hardening PR, and only when every
precondition below is met and reviewed. Until then a regression test fails any
change to the phase.

This stop gates merge only: the phase is read from the PR-head contract and
admission checks review, not CI, so it is not a runtime block. A runtime guard
that refuses workload apply independent of the PR-head phase is tracked as a
follow-up (issue #57).

- Secret rotation (F-01) and `AWSCURRENT` references instead of version pinning
  (F-02); see `secret-lifecycle.md`.
- Autoscaling (F-03) and alarms with SNS notification (F-04).
- Network hardening including VPC flow logs and egress restriction (F-08).
- ALB-to-task TLS decision (F-09) and customer-managed key decision (F-14).
- Cost and sustainability review (F-15).
- Worker healthcheck image fix (user-service PR #501) and a non-root image.
- Bootstrap governance grants for the new resources (N-11).
- N-04 apply timeout budget (partial, done here): every service-transport
  `pulumi up` (registry and workload) has a 3300 s (55 min) process timeout,
  below the 3600 s STS session (no `role-duration-seconds` is set, so the
  configure-aws-credentials action's default session duration applies and
  credentials are not refreshed) and below the 70 min `test_apply` job timeout;
  other commands keep the 1200 s default. `MARGIN_SECONDS=300` in
  `tests/unit/test_apply_timeout_budget.py` is an assumption, not a measured
  value. Measurement definition: from OIDC credential issuance to the end of
  result observation must be <= 3600 s, and from job start to the end must be
  <= the job timeout. A first create must finish within 55 min. If a measured
  first create is longer, a bootstrap `MaxSessionDuration` increase plus
  `role-duration-seconds` is required first. Hard stop: no `workload` phase
  until the first create is measured within these bounds or that increase is
  landed. A timeout kills Pulumi without a grace period, so it can leave the
  state lock behind (see N-06).
- N-06 recovery (NOT met): `docs/poc-workload-recovery.md` states that no
  first-workload apply that changed the checkpoint is recoverable with shipped
  tooling: a partial checkpoint or a complete one whose post-apply inspection
  failed is rejected by workload admission, the first-workload topology gate and
  registry capture; runner kill or credential expiry leaves a state lock and
  pending operations; failed checkpoint writes and unrecorded fixed-name
  resources (DocumentDB cluster, parameter group, log groups, secrets) cannot be
  re-created or imported. Hard-stop sub-preconditions, all required before the
  `workload` phase:
  - an admission path (resume and abandon) for a non-registry TEST checkpoint;
  - sanitized operator-visible failure diagnostics (Pulumi output currently
    stays in a private temporary log, so the failing resource and AWS error are
    not visible in CI);
  - a real import path for fixed-name resources (none exists today);
  - a reviewed CI recovery command owned by governance (CODEOWNERS) performing
    stack export, lock release, pending-operation clear and imports, with
    evidence.
  Until then any first workload apply is stop-and-escalate. The runtime guard
  independent of the PR-head phase is tracked in issue #57.
- Live TEST acceptance of the first workload apply, clean drift and rollback.
