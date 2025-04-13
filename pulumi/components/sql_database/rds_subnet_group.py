import pulumi
import pulumi_aws as aws

class RdsSubnetGroupComponent(pulumi.ComponentResource):
    def __init__(self, name: str, subnet_ids: list, tags: dict = None, opts: pulumi.ResourceOptions = None):
        super().__init__("custom:component:RdsSubnetGroupComponent", name, {}, opts)
        self.subnet_group = aws.rds.SubnetGroup(
            f"{name}-rds-subnet-group",
            subnet_ids=subnet_ids,
            tags=tags or {"Name": f"{name}-rds-subnet-group"},
            opts=pulumi.ResourceOptions(parent=self)
        )
        self.register_outputs({
            "rds_subnet_group_name": self.subnet_group.name
        })
