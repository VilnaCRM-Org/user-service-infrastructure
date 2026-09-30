# PoC workload recovery runbook

Scope: the TEST stack after a first `workload` phase apply fails, is
interrupted, or must be abandoned. Shipped tooling cannot recover any of these
(section 0): this runbook is a stop-and-escalate procedure plus the requirements
for a future recovery path. It is reviewed source, not permission to run
anything. Never run `pulumi`, `aws` or console changes out of band, never edit or import
state by hand, and never unprotect a resource outside a reviewed change.

The committed `specs/poc/poc-test.json` phase is `registry`. This runbook is one
of the preconditions for switching it to `workload` (see `specs/poc/README.md`).

## 0. What is and is not recoverable with shipped tooling

Status: N-06 is NOT met. Shipped tooling has no recovery path for any first
`workload` apply that changed the checkpoint. Treat every such apply as
stop-and-escalate to governance (CODEOWNERS); do not retry, do not clean up by
hand, and do not improvise a plan.

"Changed the checkpoint" includes all of these, none of which is recoverable:

- `pulumi up` failed part-way, even when Pulumi exited cleanly. The checkpoint
  then holds the registry resources plus some workload resources. Workload
  admission requires the exact registry resource count and receipt checkpoint
  (`scripts/poc_workload_admission.py`), the first-workload topology gate
  requires the prior state to equal the registry baseline
  (`scripts/poc_workload_topology.py`), and registry capture rejects larger state
  (`scripts/poc_registry_plan.py`). A partial checkpoint is therefore rejected by
  both the workload runner and the registry runner. See
  `docs/poc-workload-admission.md`.
- `pulumi up` succeeded but the runner's post-apply inspection of the first
  result then failed (`scripts/poc_workload_runner.py`). The checkpoint holds the
  complete workload state, and no runner accepts it: the first-workload gate
  allows only `create` from the registry baseline, and no acceptance receipt
  exists.
- Runner killed (SIGKILL, job cancel, runner loss) or STS credentials expired
  mid-update. Pulumi leaves the state lock and pending operations behind. The
  trusted backend observer rejects any lock and any pending operation
  (`scripts/poc_backend_observer.py`), and no shipped command exports state,
  releases the lock or clears pending operations.
- Checkpoint writes that failed. Resources created in AWS but never recorded in
  state are unknown to Pulumi.
- Unrecorded resources with fixed names: including the DocumentDB cluster
  and instances, its parameter group, log groups, the Redis replication group,
  the ALB and target group, the web and worker ECS services, the ALB access-log
  bucket and runtime secrets. A re-create returns `AlreadyExists`.
  No import path exists (section 5 lists the future one).

Future procedure (NOT shipped, NOT executable today; hard-stop preconditions in
`specs/poc/README.md`, N-06): (1) an admission path (resume and abandon) for a
non-registry TEST checkpoint; (2) sanitized operator-visible failure
diagnostics; (3) a real import path for fixed-name resources; and (4) a reviewed
CI recovery command, owned by governance (CODEOWNERS), that runs through the
protected environment and performs stack export, lock release, pending-operation
clear and imports, and emits evidence (before and after state hashes, the lock
and pending-operation listings, the import list, run IDs, approver). The runtime
guard that refuses workload apply independent of the PR-head phase is tracked in
issue #57. Until all of these exist and are accepted, sections 2, 3 and the
import steps of section 5 below are design notes, not procedures.

## 1. Triage a failed first apply

The Pulumi output of a workload apply stays in a private temporary log inside the
ephemeral worker (`scripts/service_execution_worker.py`,
`scripts/service_execution_process.py`, `docs/ci-architecture.md`). It is not in
the job summary or any artifact. The operator sees only the stage markers and a
generic failure line, so the failing resource and the AWS error are NOT visible
in CI. Sanitized failure diagnostics are a hard-stop precondition (N-06).

1. Note the run ID, the reviewed PR head SHA and the last stage marker in the
   `test_apply` job log. A job timeout is not proof that AWS stopped: the
   provider may still be creating resources (DocumentDB instances, Redis
   replica, NAT gateways commonly need 15 to 25 minutes).
2. Do not attempt to classify the failure from the checkpoint. Any failed or
   timed-out first workload apply is a section 0 case: stop and escalate to
   governance; do not wait for a lock, retry, or run `pulumi cancel` or
   `pulumi stack export/import`. Do not run `aws` or console changes to
   investigate out of band.
3. Record the run ID and stage markers for the escalation.

## 2. Resume (FUTURE; not executable with shipped tooling)

There is no resume path today. After a partial or complete first workload
checkpoint, workload admission, the first-workload topology gate and registry
capture all reject the state (section 0). Do not run `/pulumi test plan` or
`/pulumi test up` hoping to continue. A future resume needs the admission path
for a non-registry TEST checkpoint (N-06) with its own reviewed design: the
plan must only create or update unfinished resources, and a plan that replaces
a protected resource is a review finding.

## 3. Abandon (FUTURE; not executable with shipped tooling)

There is no abandon path today. Switching `phase` back to `registry` hits the
same prior-state rejection (registry capture rejects larger state), and the
first-workload gate accepts only `create` operations, so a destroy or delete
plan is rejected. Do not open a PR that claims to abandon.

A future abandon needs the same admission path (N-06), plus a reviewed change
that names each protected resource it unprotects (DocumentDB cluster and
instances, runtime secrets and their versions), disables DocumentDB deletion
protection in the same change, states the data-loss decision explicitly, and
keeps the destructive-diff gate and `@Kravalg` protected-environment approval.

## 4. Final-snapshot name collisions

This section is FUTURE, part of the abandon design (section 3), and not
executable today. The "reviewed operator task" below is a governance-owned manual
decision recorded in the PR; no shipped command performs it.

The DocumentDB cluster keeps a named final snapshot, `<stack-tag>-docdb-final`
(for TEST: `user-service-test-docdb-final`). AWS refuses to create a second
snapshot with an existing identifier, so destroying a second cluster with the
same stack tag fails at DocumentDB if the first snapshot still exists.

The name is deliberately static: a run-dependent value cannot be derived
deterministically inside the program, and changing it on every run would show as
a diff on every plan. Handle a collision with a reviewed decision:

- If the earlier snapshot is still needed, restore or copy it under a new name
  first, through a reviewed operator task, and keep the copy as the evidence.
- If it is not needed, delete the old snapshot through a reviewed operator task
  before the abandon apply. Record the snapshot identifier, the decision and the
  approver in the PR. Do not delete a snapshot unless the abandon decision
  explicitly accepts that loss.

## 5. Secrets Manager recovery-window collisions (FUTURE)

Not executable with shipped tooling: there is no import path (section 0) and no
admission path for the resulting state.

Runtime secrets use fixed names and are Pulumi-protected. After a destroy, AWS
keeps a deleted secret for its recovery window (default 30 days) and refuses to
create another secret with the same name ("scheduled for deletion").

Decide before the next create:

- Restore: if the secret content is still wanted and the KMS key is unchanged,
  a reviewed operator task restores the scheduled-for-deletion secret and the
  a future import path (N-06 precondition; not shipped) would adopt it.
  Do not hand-edit state.
- Force delete: if the content is disposable (generated PoC values), a reviewed
  operator task force-deletes the scheduled secret without recovery, then a
  first-create plan could proceed. Force delete is irreversible; record the secret
  names, the decision and the approver in the PR, and never print secret values.

Neither action is available to the service apply role, which has no IAM or
Secrets Manager administration; an operator with the appropriate governance
grant performs it. Bootstrap governance grants for the new resources are a
separate precondition (N-11).

## 6. Evidence to keep

- The failed and the recovering run IDs and the reviewed PR head SHA.
- The stage markers of the failed run; the plan output of any future recovery change.
- Snapshot and secret decisions with approver and date.
