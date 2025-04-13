import pulumi
import pulumi_aws as aws

class VpcComponent(pulumi.ComponentResource):
    def __init__(self, name: str, cidr_block: str = "10.0.0.0/16", tags: dict = None, opts: pulumi.ResourceOptions = None):
        super().__init__("custom:component:VpcComponent", name, {}, opts)

        self.vpc = aws.ec2.Vpc(
            f"{name}-vpc",
            cidr_block=cidr_block,
            enable_dns_hostnames=True,
            enable_dns_support=True,
            tags=tags or {"Name": f"{name}-vpc"},
            opts=pulumi.ResourceOptions(parent=self)
        )

        self.register_outputs({
            "vpc_id": self.vpc.id,
            "cidr_block": self.vpc.cidr_block
        })
