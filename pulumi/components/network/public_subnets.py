import pulumi
import pulumi_aws as aws

class PublicSubnetsComponent(pulumi.ComponentResource):
    def __init__(self, name: str, vpc_id, cidr_blocks: list = None, availability_zones: list = None, tags: dict = None, opts: pulumi.ResourceOptions = None):
        """
        Creates public subnets. Defaults: two subnets with predefined CIDRs and AZs.
        """
        super().__init__("custom:component:PublicSubnetsComponent", name, {}, opts)
        cidr_blocks = cidr_blocks or ["10.0.1.0/24", "10.0.2.0/24"]
        availability_zones = availability_zones or ["us-west-2a", "us-west-2b"]

        self.subnets = []
        for i, (cidr, az) in enumerate(zip(cidr_blocks, availability_zones)):
            subnet = aws.ec2.Subnet(
                f"{name}-public-subnet-{i+1}",
                vpc_id=vpc_id,
                cidr_block=cidr,
                availability_zone=az,
                map_public_ip_on_launch=True,
                tags=tags or {"Name": f"{name}-public-subnet-{i+1}"},
                opts=pulumi.ResourceOptions(parent=self)
            )
            self.subnets.append(subnet)
        self.register_outputs({
            "public_subnet_ids": [s.id for s in self.subnets]
        })
