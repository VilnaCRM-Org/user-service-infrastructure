# Connected workload prerequisite checks

The trusted service worker now distinguishes the phase in the authenticated
fixed PoC source contract. Registry requests retain the existing exact graph and
saved-plan runner. Workload requests perform authenticated read checks and stop
before any Pulumi program executes. PROD and scheduled routing are unchanged.

The workload branch reuses the original registry completion verifier, including
its App issuer, successful original workflow/jobs, historical source and immutable
observation artifacts. It compares that receipt with a fresh native checkpoint
and the complete seven-resource registry graph and ECR controls. An absent,
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
Installed runtime role/capability checks remain required before constructing
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

Successful reads currently end with
`workload-native-image-capability-and-plan-gates-required`. No plan artifact is
published and no workload is registered or applied. This is an intentional
execution boundary, not an acceptance result.

Before enabling the full graph, connect native image/platform and runtime pull
checks, installed central capability/role and approved endpoint/log/mail metadata,
the generated-settings child entrypoint, and actual workload saved-plan validation
and replay bindings. Extend result observation and scheduled drift for the accepted
workload phase, including native secret version history across releases/rollback.
The current registry completion proof and full TEST+PROD promotion retain their
existing meanings. Workload-to-registry downgrade remains forbidden.

Automatic publisher dispatch and its App installation permissions are separate
existing-owner integration work. This change creates no App, token, AWS policy,
stack, manual image flow, new phase flag, or acceptance bypass.
