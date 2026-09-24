# Internal no-change workload reconciliation

`scripts/poc_workload_reconciliation.py` provides a supplementary pure validator
for Pulumi 3.223.0 saved plans. It does not enable the workload worker. Both existing
execution stops remain, and this module publishes no receipt or plan artifact.

The caller must independently authenticate an accepted workload receipt, its
complete native checkpoint, current capabilities, reviewed source, and original
same-run plan/preview bytes. It must reject pending operations before passing the
resource list. A caller-supplied graph or matching resource count does not establish
an accepted workload. This module does not validate the first workload graph,
native cloud health, runtime-role permissions, or the desired workload contract.

The reducer requires an exact goal for every observed resource, the pinned plan
manifest, and only `same` operations. All input/output diffs must be empty. Goal
parent/provider links, dependencies, protection, secret-output declarations and
timeouts must match the prior resource. Unknown goal fields, missing/extra owners,
foreign graph references, IAM resources, imports and unsafe lifecycle state fail
closed. Advisory saved-plan `state` and preview summary counts cannot replace
complete goals. Every displayed preview row must preserve its prior owner, inputs
and outputs. Pulumi may omit unchanged preview rows, including all rows.

Authenticated Pulumi secret wrappers are projected to the exact `[secret]` token
only when comparing preview states. Unwrapped or differently spelled preview
values cannot substitute for a wrapped secret. Saved-plan input/output changes
remain forbidden even when they contain a wrapper or `[secret]`. Errors contain
only a fixed diagnostic code; the reducer never logs supplied state.

## Integration and replay rules still required

Before using this check, implement authenticated workload-result observation and
native first-workload capability/graph validation. Reconcile the complete prior
checkpoint against its original accepted result; a registry receipt cannot stand
in for a workload receipt. Recheck source/review/requester, installed capabilities,
image evidence and native checkpoint immediately before replay. Changed or revoked
authority, changed checkpoint, or expired/missing original evidence invalidates the
plan and requires a fresh reviewed request. Never automatically replay a failed or
uncertain apply, revoke existing resource owners, downgrade to registry, delete a
lock, or fall back to direct apply. A changed release or reviewed rollback requires
its own mutating-plan validator; it cannot pass this no-change reducer.

Tests include adversarial saved-plan/preview/checkpoint mutations and an actual
pinned CLI local-backend round trip: save and apply a component-only plan, export
its encrypted checkpoint, then validate the second unchanged saved plan and JSON
preview. The local test uses synthetic secrets, no AWS provider and no cloud
credentials. This establishes component/secret wire compatibility, not a full AWS
workload no-change result or deployed acceptance.
