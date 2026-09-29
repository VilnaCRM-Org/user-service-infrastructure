# Generated workload ALB logs and worker health

The internal generated workload composition owns the previously missing ALB log
bucket. It derives `user-service-infrastructure-test-<account>-alb-logs` from the
already validated descriptor and preserved service metadata. No external bucket
name is generated or requested. `generated_secrets=True` selects this internal
composition; legacy manual deployments keep their existing bucket setting.

`AlbAccessLogs` is a child of the existing ComputePlane, using the inherited AWS
provider. It creates one protected bucket (`force_destroy=False`), bucket-owner
enforced object ownership, all four public-access blocks, SSE-S3 encryption,
versioning, a lifecycle policy and a delivery policy. Objects under the ALB log
prefix expire after 90 days; noncurrent versions expire after 30 days and
incomplete multipart uploads abort after seven days. Bucket deletion/replacement
requires an explicit later reviewed lifecycle decision; this unit does not
disable protection or empty a bucket.

The sole delivery Allow grants `s3:PutObject` to
`logdelivery.elasticloadbalancing.amazonaws.com`, for the exact bucket prefix and
`AWSLogs/<account>/` subtree. SourceArn includes the validated account/region and
the same physical ALB name used by ComputePlane, with only AWS's generated ALB ID
as a wildcard. It does not reference the not-yet-created ALB ARN, avoiding a
resource dependency cycle. A separate Deny requires HTTPS for non-service
clients; the AWS-service exception handles redacted service-to-service network
context. It adds no resource-based log-read grant.

The ALB depends on the bucket policy; that policy depends on ownership, public
access, encryption, versioning and retention. This prevents ALB logging validation
from racing its prerequisite bucket setup. Existing registry parent/resource names,
provider links and root metadata exports are preserved. New resources retain the
baseline tags. No IAM roles or policies are created by this service unit.

The descriptor's detached worker argument list becomes ECS `healthCheck.command`
with a `CMD` prefix. It runs directly, preserving arguments without shell
interpretation. Defaults are interval 30 seconds, timeout 5 seconds, three retries
and a 60-second start period. The existing worker supervisor launch and web ALB
health path remain in place. Native image inspection and running health checks
must still establish that this declared executable works in the selected image.

AWS documents the same-region/SSE-S3 requirement and scoped delivery policy in
[ALB access log setup](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/enable-access-logging.html).
Its [S3 condition guidance](https://docs.aws.amazon.com/AmazonS3/latest/userguide/amazon-s3-policy-keys.html)
explains the service-principal exception for redacted network context.
[ECS health checks](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/healthcheck.html)
distinguish direct `CMD` from shell execution.

This is uninstalled source. Central service capabilities and all immutable
identity/boundary/guard intersections must permit this exact additional S3
resource graph and ALB configuration. Native bucket uniqueness/ownership,
delivery test object, metadata/default encryption/retention, TLS/public-access
posture, workload health and saved-plan/replay/drift still need authenticated
acceptance. The existing workload execution stops remain enabled.
