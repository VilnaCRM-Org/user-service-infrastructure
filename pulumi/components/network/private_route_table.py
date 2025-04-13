import pulumi
import pulumi_aws as aws

class PrivateRouteTableComponent(pulumi.ComponentResource):
    def __init__(self, name: str, vpc_id, nat_gateway_id, private_subnet_ids: list, tags: dict = None, opts: pulumi.ResourceOptions = None):
        super().__init__("custom:component:PrivateRouteTableComponent", name, {}, opts)
        self.route_table = aws.ec2.RouteTable(
            f"{name}-private-rt",
            vpc_id=vpc_id,
            routes=[aws.ec2.RouteTableRouteArgs(
                cidr_block="0.0.0.0/0",
                nat_gateway_id=nat_gateway_id
            )],
            tags=tags or {"Name": f"{name}-private-rt"},
            opts=pulumi.ResourceOptions(parent=self)
        )
        # Associate route table with each private subnet
        for i, subnet_id in enumerate(private_subnet_ids):
            aws.ec2.RouteTableAssociation(
                f"{name}-private-rt-assoc-{i+1}",
                subnet_id=subnet_id,
                route_table_id=self.route_table.id,
                opts=pulumi.ResourceOptions(parent=self)
            )
        self.register_outputs({
            "private_route_table_id": self.route_table.id
        })
