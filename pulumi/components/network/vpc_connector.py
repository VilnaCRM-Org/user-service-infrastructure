import pulumi
import pulumi_aws as aws

class VpcConnectorComponent(pulumi.ComponentResource):
    def __init__(self, name: str, subnet_ids: list, security_group_ids: list, tags: dict = None, opts: pulumi.ResourceOptions = None):
        super().__init__("custom:component:VpcConnectorComponent", name, {}, opts)
        self.connector = aws.apprunner.VpcConnector(
            f"{name}-vpc-connector",
            vpc_connector_name=f"{name}-vpc-connector",
            subnets=subnet_ids,
            security_groups=security_group_ids,
            tags=tags or {"Name": f"{name}-vpc-connector"},
            opts=pulumi.ResourceOptions(parent=self)
        )
        self.register_outputs({
            "vpc_connector_arn": self.connector.arn
        })
