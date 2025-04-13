import pulumi
import pulumi_aws as aws

class PublicRouteTableComponent(pulumi.ComponentResource):
    def __init__(self, name: str, vpc_id, igw_id, public_subnet_ids: list, tags: dict = None, opts: pulumi.ResourceOptions = None):
        super().__init__("custom:component:PublicRouteTableComponent", name, {}, opts)
        self.route_table = aws.ec2.RouteTable(
            f"{name}-public-rt",
            vpc_id=vpc_id,
            routes=[aws.ec2.RouteTableRouteArgs(
                cidr_block="0.0.0.0/0",
                gateway_id=igw_id
            )],
            tags=tags or {"Name": f"{name}-public-rt"},
            opts=pulumi.ResourceOptions(parent=self)
        )
        # Associate route table with each public subnet
        for i, subnet_id in enumerate(public_subnet_ids):
            aws.ec2.RouteTableAssociation(
                f"{name}-public-rt-assoc-{i+1}",
                subnet_id=subnet_id,
                route_table_id=self.route_table.id,
                opts=pulumi.ResourceOptions(parent=self)
            )
        self.register_outputs({
            "public_route_table_id": self.route_table.id
        })
