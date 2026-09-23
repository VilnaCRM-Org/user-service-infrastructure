# Connected workload prerequisite checks

The trusted service worker now distinguishes the phase in the authenticated
fixed PoC source contract. Registry requests retain the existing exact graph and
saved-plan runner. Workload requests perform authenticated read checks and stop
before any Pulumi program executes. PROD and scheduled routing are unchanged.

The workload branch reuses the original registry completion verifier, including
its App issuer, successful original workflow/jobs, historical source and immutable
observation artifacts. It compares that receipt with a fresh native checkpoint
and the complete eleven-resource registry/prerequisite graph and ECR controls. An absent,
changed, partial or already-expanded checkpoint cannot become a first-workload
baseline. The original registry contract is recovered by exact Git commit/blob
identity and verified against the receipt digest; it is not reconstructed from
the desired workload declaration.

The release reader verifies the original application publisher workflow, native
App actor and triggering actor, attempt one, all three successful jobs and their
ordering. It reads bounded immutable manifest, quality and provenance artifacts
without extracting archives, checks ZIP and file digests and compares their closed
content with the reviewed release. The large image-transfer archive is checked
by native artifact identity/digest and build-job timing; it is not downloaded by
the service. The trusted publisher remains responsible for its transfer contents.
The registry receipt/current checkpoint is checked again after release reads.
The owned SES identity and its Easy DKIM DNS records are included in that
checkpoint. Workload reads also require current SES verification; see
[poc-ses-prerequisite.md](poc-ses-prerequisite.md).

After release authentication, native ECR reads now check both exact TEST image
digests. The observer hashes the original manifest bytes, requires a single Docker
schema-2 or OCI image manifest, and checks all declared compressed layers for exact
digest, media type, size and native availability. It rejects manifest lists,
external layer URLs, duplicate layers, partial responses and AWS failures. The
fixed root AWS process uses only its admitted session and the TEST ECR endpoint.
It never downloads or executes image layers.

This observes the CI caller's access, not the ECS execution role's pull authority.
The manifest's config blob is now fetched privately and checked against its exact
declared byte size and SHA-256, then its native `os` and `architecture` are compared
with the reviewed `linux/amd64` or `linux/arm64` release platform. Only platform,
config digest and size join the image projection. Image environment, labels,
history and other configuration never enter the projection or diagnostic errors.
The bounded role/input prerequisite reader below now runs before the worker stop.
Full installed runtime capability admission remains required before constructing
workload settings.
The observer supports at most 100 layers and deliberately accepts only compressed
Docker gzip or OCI gzip/zstd layers. A different valid image shape requires a
reviewed extension and its corresponding admission tests.

Config retrieval uses [ECR Registry HTTP API authentication](https://docs.aws.amazon.com/AmazonECR/latest/userguide/registry_auth.html).
The isolated root worker obtains a fresh token through the fixed ECR API, verifies
its endpoint and expiry, and keeps it in memory. It is never passed on argv,
written into files, exposed to PR code, or emitted in output. Direct HTTPS uses
the installed CA bundle and explicit client TLS context; ambient proxies, CA
overrides, netrc and TLS key-log settings do not configure it.

The initial origin is exactly the TEST ECR registry. At most two redirects are
allowed, only to that same blob path or the documented regional
[ECR layer bucket](https://docs.aws.amazon.com/AmazonECR/latest/userguide/vpc-endpoints.html)
at `prod-eu-central-1-starport-layer-bucket.s3.eu-central-1.amazonaws.com`.
Authorization is dropped on the S3 hop and cannot be restored by a redirect back
to ECR. The reader bounds config bodies to 1 MiB, uses a 15-second socket timeout
and a 60-second redirect/body-read deadline, and rejects partial, encoded,
ambiguous, oversized or mismatched responses. Unsupported redirect destinations
fail closed; actual ECR config retrieval has not been exercised in AWS by these
offline tests. The projection's platform follows the verified
[image config fields](https://github.com/opencontainers/image-spec/blob/main/config.md),
not only the publisher's requested build platform.

The protocol matches `publish-poc-images.yml`: `Validate application release`,
`Build application images`, and `Publish TEST application images`. Exact artifacts
are `poc-release-manifest-{run}-1` (`release-manifest.json`),
`poc-quality-evidence-{run}-1` (`quality.json`),
`poc-build-provenance-{run}-1` (`provenance.json`), and
`poc-image-build-{run}-1`. The release uses the existing `poc-release-v1` fields.
Publisher source and installation must implement this protocol before any real
evidence can pass; these source checks do not establish that it is installed.

## Trusted inputs

The three TEST execution jobs pass the existing protected
`GOVERNANCE_PROMOTION_APP_ID` and `GOVERNANCE_PROMOTION_APP_SLUG` variables, plus
explicit `POC_REGISTRY_WORKFLOW_SHA` and `POC_PUBLISHER_WORKFLOW_SHA` revision pins.
The latter pins must be set to reviewed installed workflow revisions. No value
is inferred from a receipt, PR, dispatch input or current application branch.
Missing values reject workload observation; registry and PROD do not require them.
The host allowlist passes these non-secret inputs only to the root verifier.
The UID 2000 program environment does not receive them or GitHub credentials.

The read adapter uses fixed `/usr/bin/gh`, `api.github.com`, a root-private HOME,
a closed GitHub environment and the existing bounded process runner. Native
checkpoint and ECR reads retain the current service observer/caller checks. A
permission denial fails closed and is not evidence of an empty registry.

## Remaining enabling work

The trusted worker also calls `poc_workload_capabilities.inspect_capabilities`.
It requires the fixed central TEST execution/task role ARNs, native names, root
paths, IAM role IDs, and exact independently enrolled `issue219/test/boundary/`
policy ARNs. Execution trust must match the existing central ECS task service
principal and TEST account/region conditions. The declared ACM certificate must
be issued, currently valid, list the exact application domain and allow TLS server
authentication. Only the current AMD64 settings bridge is supported.

Seven singleton native IAM simulations use the installed execution role: regional
ECR authorization plus each of the three image-pull actions on each fixed
repository. No replacement policy, boundary, resource policy or caller-selected
context is supplied. Every response must be complete, with the exact requested
action/resource, an allowed result, no unresolved context and explicit boundary
allowance. An observed organization denial or resource-specific denial rejects.
AWS documents that [IAM simulation does not perform the operation and cannot
simulate resource policies for roles](https://docs.aws.amazon.com/IAM/latest/APIReference/API_SimulatePrincipalPolicy.html).
This prerequisite is not evidence of an actual ECS pull, an organization-wide
effective grant, or the complete workload capability. Missing organization detail
does not establish organization permission. Native role and certificate metadata
are checked again after simulations; this is not an atomic installation proof.

The adapter uses only the admitted root AWS session and fixed IAM/ACM read APIs
and endpoints, with bounded output, no ambient profiles, credentials files or
endpoint overrides. Access denial fails closed. Offline tests use synthetic native
responses; no AWS validation or successful workload receipt is claimed.

Successful reads currently end with
`workload-native-image-capability-and-plan-gates-required`. No plan artifact is
published and no workload is registered or applied. This is an intentional
execution boundary, not an acceptance result.

Before enabling the full graph, establish actual runtime pulls, authenticated seed
inventory/revision and immutable guard/policy installation, full task and deployer
capabilities and approved endpoint/log/mail metadata,
the generated-settings child entrypoint, and actual workload saved-plan validation
and replay bindings. Extend result observation and scheduled drift for the accepted
workload phase, including native secret version history across releases/rollback.
The current registry completion proof and full TEST+PROD promotion retain their
existing meanings. Workload-to-registry downgrade remains forbidden.

## Automatic publisher dispatch

After successful registry proof publication, a separate `test_registry_dispatch`
job checks out only the installed service workflow revision. It reauthenticates
same-run source and observation artifacts, the completed proof job, native App
receipt readback and the main-only `governance-evidence` boundary. No PR code or
AWS credentials enter the dispatcher. The proof job retains its deployments-only
token; the dispatcher requests a separate `actions:write` token scoped to only
`VilnaCRM-Org/user-service`, and verifies that exact repository selection.

Before minting the dispatch token and again immediately before the POST, the
trusted helper requires App `4853984` (`vilnacrm-user-service-evidence`) to advertise
Actions write, and requires the active application publisher workflow on `main`
at the protected `POC_PUBLISHER_WORKFLOW_SHA` revision. That same revision becomes
the immutable application build source, with `linux/amd64` and the verified
registry receipt/contract/checkpoint binding. There is no caller-selected source.

Both preflight passes also read the effective rules for application `main` and
the native repository ruleset. They require one unambiguous active branch PR rule
with at least one approval, CODEOWNER review, last-push approval, stale-review
dismissal and resolved review threads. A boolean `protected` field, tag rules,
evaluation-only rules, partial responses and absent/unreadable metadata cannot
satisfy this check. This bounded adapter currently accepts repository rulesets;
classic-only protection or inherited organization rules need a reviewed adapter
extension rather than an inferred equivalence.

The dispatcher mirrors the publisher's existing `poc-test-images` environment
contract: custom deployment policies allow only the exact `main` branch, admin
bypass is disabled, and the sole required reviewer is Kravalg with self-review
prevented. This preserves the independent human gate before application OIDC.
The service preflight checks the gate's configuration; the application publisher
continues to require actual environment approval before obtaining AWS credentials.

[GitHub's ruleset API](https://docs.github.com/en/rest/repos/rules#get-a-repository-ruleset)
redacts `bypass_actors` from callers lacking ruleset write access. The read-only
service token therefore does not prove the bypass list is empty, and missing
that field is not treated as proof of an empty list. An administrator must audit
ruleset bypass settings when enabling the route; the protected publisher
environment remains an independent required gate. No read token is widened to
obtain otherwise-hidden settings.

The POST pins GitHub REST version `2026-03-10` and requires the returned native
`workflow_run_id` and repository-bound URLs. It reads that exact run back and
checks the workflow, source revision, attempt one, repository identities and App
actor/triggering actor. See [GitHub's workflow dispatch API](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event).
This confirms dispatch, not image quality, publication success or workload
admission. Release admission still checks the completed publisher independently.
A missing/empty response, readback failure or moved application main fails closed;
the helper never retries an uncertain POST. Inspect the native run before any
operator retry. Reruns of the service workflow remain rejected by attempt-one
admission.

Enabling prerequisites remain external: install the reviewed publisher on
application `main`; set `POC_PUBLISHER_WORKFLOW_SHA` to that installed main commit;
and grant/accept Actions write for the existing App installation with access to
`user-service`. Public App permissions on 2026-09-23 still advertise Actions read,
and application main lacks the publisher workflow. Installation selection could
not be verified with the available organization API access. Token creation fails
if the installation has not accepted the permission or lacks repository access.
The application main review rules and `poc-test-images` environment must also be
installed: operator API inspection on 2026-09-23 found no main branch protection,
only a tag ruleset, and no publisher environment. The runtime must be able to
read the effective rules, ruleset and environment through its existing read
token; API denial remains a blocking prerequisite rather than an admission bypass.
The dispatcher therefore remains fail-closed with the current configuration.
No App setting, workflow pin or AWS permission is changed by this source patch.
