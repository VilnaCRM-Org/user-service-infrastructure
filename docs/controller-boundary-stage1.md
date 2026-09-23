# Stage-one history

The TEST replacement candidate is documented in [trusted-test-controller.md](trusted-test-controller.md).
The following describes the original disabled boundary commit, not candidate installation authority.

# First-stage controller boundary

PR comment intake and result comments remain available. Every legacy PR-head
execution, destructive-diff, and promotion job in `self-deploy.yml` is explicitly
disabled. Authenticated commands fail preflight with an installation message;
the result comment reports that no AWS role was assumed. New commands will be
required after installation because intake still consumes each command once.

Trusted main-only initialization and scheduled drift remain unchanged. This is
not a suspension of independent main automation or a completed controller install.

The installed review-admission helper requires exact open PR head/base identity,
fresh independent human approval, and effective two-reviewer main protections.
It is not wired to credential issuance in this disabled stage. The isolated
process primitive and pinned boundary image provide a credential-free smoke
runtime only. The image defaults to rejecting deployment, accepts only a fixed
smoke command, and contains no Pulumi or AWS tools. No workflow builds or invokes
this image yet. These files are staged foundations, not deployment authorization.

Stage 2 must atomically replace the disabled legacy jobs with the complete trusted
TEST controller. Install its authenticated contract/source artifacts, registry and
SES/DNS graph, backend observer, pinned SDK/provider runtime, protected saved-plan
transport and validation, requester/review rechecks, and matching regression
tests before enabling any job. Do not remove the disable conditions alone.
Registry completion proofs, publisher dispatch, and workload execution require
their own reviewed dependency closure. Keep workload application disabled.

Offline image validation must use a private PID namespace, read-only root,
`--network none`, a private `/tmp` tmpfs, `--cap-drop ALL`, only SETUID/SETGID/KILL
capabilities, and `--security-opt no-new-privileges`. Do not pass host credentials,
Docker sockets, source mounts, or Actions environment variables.
