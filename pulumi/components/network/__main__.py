import pulumi
from pulumi import ResourceOptions
from components.vpc import VpcComponent
from components.internet_gateway import InternetGatewayComponent
from components.public_subnets import PublicSubnetsComponent
from components.private_subnets import PrivateSubnetsComponent
from components.nat_gateway import NatGatewayComponent
from components.public_route_table import PublicRouteTableComponent
from components.private_route_table import PrivateRouteTableComponent

class NetworkComponent(pulumi.ComponentResource):
    def __init__(self, name: str, cidr: str = "10.0.0.0/16", opts: ResourceOptions = None):
        super().__init__("custom:feature:NetworkComponent", name, None, opts)

        # Create the VPC.
        self.vpc = VpcComponent(name, cidr_block=cidr, opts=ResourceOptions(parent=self))
        # Create the Internet Gateway.
        self.igw = InternetGatewayComponent(name, vpc_id=self.vpc.vpc.id, opts=ResourceOptions(parent=self))
        # Create public and private subnets.
        self.public_subnets = PublicSubnetsComponent(name, vpc_id=self.vpc.vpc.id, opts=ResourceOptions(parent=self))
        self.private_subnets = PrivateSubnetsComponent(name, vpc_id=self.vpc.vpc.id, opts=ResourceOptions(parent=self))
        # Create a NAT Gateway in the first public subnet.
        self.nat_gateway = NatGatewayComponent(name, public_subnet_id=self.public_subnets.subnets[0].id, opts=ResourceOptions(parent=self))
        # Create route tables.
        self.public_rt = PublicRouteTableComponent(
            name,
            vpc_id=self.vpc.vpc.id,
            igw_id=self.igw.igw.id,
            public_subnet_ids=[s.id for s in self.public_subnets.subnets],
            opts=ResourceOptions(parent=self)
        )
        self.private_rt = PrivateRouteTableComponent(
            name,
            vpc_id=self.vpc.vpc.id,
            nat_gateway_id=self.nat_gateway.nat_gateway.id,
            private_subnet_ids=[s.id for s in self.private_subnets.subnets],
            opts=ResourceOptions(parent=self)
        )

        self.register_outputs({
            "vpc_id": self.vpc.vpc.id,
            "public_subnet_ids": [s.id for s in self.public_subnets.subnets],
            "private_subnet_ids": [s.id for s in self.private_subnets.subnets]
        })
