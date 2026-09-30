# PoC workload recovery runbook

Scope: the TEST stack after the first `workload` phase apply fails part-way or
must be abandoned. This runbook is reviewed source; it is not permission to run
anything. Every state-changing step below goes through the reviewed pull request
and the protected saved-plan workflow (`/pulumi test plan`, `/pulumi test up`).
Never run `pulumi`, `aws` or console changes out of band, never edit or import
state by hand, and never unprotect a resource outside a reviewed change.

The committed `specs/poc/poc-test.json` phase is `registry`. This runbook is one
of the preconditions for switching it to `workload` (see `specs/poc/README.md`).

## 1. Triage a failed or partial first apply

1. Read the failed `test_apply` job summary for the failing resource and its
   AWS error. A job timeout is not proof that AWS stopped: the provider may still
   be creating resources (DocumentDB instances, Redis replica, NAT gateways
   commonly need 15 to 25 minutes).
2. Wait for the Pulumi state lock to be released. The workflow's concurrency group
   serializes applies; do not force-cancel a running update and do not run
   `pulumi cancel` or `pulumi stack export/import`.
3. Decide between resume and abandon.

## 2. Resume (default)

Resume when the failure was transient (timeout, throttling, capacity, an ECS
steady-state wait that the fixed image now satisfies).

1. Confirm no update is running and the lock is released.
2. Push the fix (if any) to the same PR, or leave the head unchanged for a pure
   retry. A new head needs a fresh `/pulumi test plan`.
3. Comment `/pulumi test plan` on the current head, review the saved plan (it
   must only create or update the resources that did not finish), then request
   `/pulumi test up` with a maintainer other than the sole environment reviewer.
4. Pulumi records resources created before the failure, so a re-run continues
   from that state. Resources still pending in AWS are reconciled by the refresh
   in the plan; if the plan proposes replacing a protected resource, stop and
   treat that as a review finding.
5. After a green apply, wait for the clean drift job before any acceptance claim.

## 3. Abandon

Abandon when the design is wrong, the image cannot become healthy, or the stack
cannot be resumed safely. Abandon is a reviewed change, never a direct destroy.

1. Open a PR that switches `phase` back to `registry` only if the registry-only
   graph can be admitted, or that removes the failed workload resources.
2. Protected resources (DocumentDB cluster and instances, runtime secrets and
   their versions) refuse deletion. The PR must name each resource it unprotects
   and, for the DocumentDB cluster, disable deletion protection in the same
   reviewed change. It must state the data-loss decision explicitly. Maintainer
   `@Kravalg` approval of the protected environment is still required.
3. Run the plan, review that the destructive diff lists exactly those resources,
   then apply through `/pulumi test up`. The destructive-diff gate applies as for
   any other change; do not bypass it.
4. Verify in the next plan that the stack graph matches the intended state and
   that no orphan resources remain.

## 4. Final-snapshot name collisions

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

## 5. Secrets Manager recovery-window collisions

Runtime secrets use fixed names and are Pulumi-protected. After a destroy, AWS
keeps a deleted secret for its recovery window (default 30 days) and refuses to
create another secret with the same name ("scheduled for deletion").

Decide before the next create:

- Restore: if the secret content is still wanted and the KMS key is unchanged,
  a reviewed operator task restores the scheduled-for-deletion secret and the
  next plan adopts it via the reviewed import path; do not hand-edit state.
- Force delete: if the content is disposable (generated PoC values), a reviewed
  operator task force-deletes the scheduled secret without recovery, then the
  first-create plan proceeds. Force delete is irreversible; record the secret
  names, the decision and the approver in the PR, and never print secret values.

Neither action is available to the service apply role, which has no IAM or
Secrets Manager administration; an operator with the appropriate governance
grant performs it. Bootstrap governance grants for the new resources are a
separate precondition (N-11).

## 6. Evidence to keep

- The failed and the recovering run IDs and the reviewed PR head SHA.
- The plan output for the resume or abandon change.
- Snapshot and secret decisions with approver and date.
