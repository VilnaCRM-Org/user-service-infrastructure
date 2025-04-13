import pulumi
import pulumi_aws as aws

class NatGatewayComponent(pulumi.ComponentResource):
    def __init__(self, name: str, public_subnet_id, tags: dict = None, opts: pulumi.ResourceOptions = None):
        super().__init__("custom:component:NatGatewayComponent", name, {}, opts)
        # Allocate an Elastic IP
        self.eip = aws.ec2.Eip(
            f"{name}-eip",
            vpc=True,
            tags=tags or {"Name": f"{name}-eip"},
            opts=pulumi.ResourceOptions(parent=self)
        )
        # Create the NAT Gateway in the specified public subnet
        self.nat_gateway = aws.ec2.NatGateway(
            f"{name}-natgw",
            allocation_id=self.eip.id,
            subnet_id=public_subnet_id,
            tags=tags or {"Name": f"{name}-natgw"},
            opts=pulumi.ResourceOptions(parent=self)
        )
        self.register_outputs({
            "nat_gateway_id": self.nat_gateway.id,
            "eip_id": self.eip.id
        })
