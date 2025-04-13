import pulumi
import pulumi_aws as aws

class InternetGatewayComponent(pulumi.ComponentResource):
    def __init__(self, name: str, vpc_id, tags: dict = None, opts: pulumi.ResourceOptions = None):
        super().__init__("custom:component:InternetGatewayComponent", name, {}, opts)
        self.igw = aws.ec2.InternetGateway(
            f"{name}-igw",
            vpc_id=vpc_id,
            tags=tags or {"Name": f"{name}-igw"},
            opts=pulumi.ResourceOptions(parent=self)
        )
        self.register_outputs({
            "igw_id": self.igw.id
        })
