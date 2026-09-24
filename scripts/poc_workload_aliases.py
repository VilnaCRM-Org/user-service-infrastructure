"""Closed Pulumi SDK alias projections for the accepted workload graph."""

SDK_TYPE_ALIASES = {
    f"aws:lb/{kind}": f"aws:elasticloadbalancingv2/{kind}"
    for kind in (
        "listener:Listener",
        "loadBalancer:LoadBalancer",
        "targetGroup:TargetGroup",
    )
}
SDK_TYPE_ALIASES.update(
    {
        token: token
        for token in (
            f"aws:s3/{kind[0].lower() + kind[1:]}:{kind}"
            for kind in (
                "BucketLifecycleConfigurationV2",
                "BucketServerSideEncryptionConfigurationV2",
                "BucketVersioningV2",
            )
        )
    }
)


def structured_aliases(resource_type):
    """Return the sole SDK structured alias allowed for a resource type."""
    previous_type = SDK_TYPE_ALIASES.get(resource_type)
    if previous_type is None:
        return []
    return [
        {
            "URN": "",
            "Name": "",
            "Type": previous_type,
            "Project": "",
            "Stack": "",
            "Parent": "",
            "NoParent": False,
        }
    ]


def state_aliases(urn, resource_type):
    """Return the sole legacy URN projection allowed in checkpoint state."""
    previous_type = SDK_TYPE_ALIASES.get(resource_type)
    marker = f"::{resource_type}::"
    if previous_type is None or marker not in urn:
        return []
    return [urn.replace(marker, f"::{previous_type}::", 1)]
