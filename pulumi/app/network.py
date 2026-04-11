"""Networking primitives for the user-service stack."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pulumi_aws as aws

import pulumi
from app.environment import StackSettings, build_resource_name

__all__ = ["NetworkPlane"]


@dataclass(frozen=True)
class NetworkOutputs:
    """Resolved networking outputs shared with downstream planes."""

    vpc_id: pulumi.Input[str]
    public_subnet_ids: list[pulumi.Input[str]]
    app_subnet_ids: list[pulumi.Input[str]]
    data_subnet_ids: list[pulumi.Input[str]]
    alb_security_group_id: pulumi.Input[str]
    service_security_group_id: pulumi.Input[str]
    documentdb_security_group_id: pulumi.Input[str]
    redis_security_group_id: pulumi.Input[str]


class NetworkPlane(pulumi.ComponentResource):
    """Create either preview-safe placeholders or the managed VPC network."""

    outputs: NetworkOutputs

    def __init__(
        self,
        name: str,
        *,
        settings: StackSettings,
        opts: Optional[pulumi.ResourceOptions] = None,
    ) -> None:
        super().__init__("user-service-infrastructure:network:Plane", name, None, opts)

        self.outputs = (
            self._build_managed_network(settings)
            if settings.is_managed
            else self._build_preview_outputs(settings)
        )
        self.register_outputs(
            {
                "vpcId": self.outputs.vpc_id,
                "publicSubnetIds": self.outputs.public_subnet_ids,
                "appSubnetIds": self.outputs.app_subnet_ids,
                "dataSubnetIds": self.outputs.data_subnet_ids,
                "albSecurityGroupId": self.outputs.alb_security_group_id,
                "serviceSecurityGroupId": self.outputs.service_security_group_id,
                "documentDbSecurityGroupId": self.outputs.documentdb_security_group_id,
                "redisSecurityGroupId": self.outputs.redis_security_group_id,
            }
        )

    def _build_preview_outputs(self, settings: StackSettings) -> NetworkOutputs:
        """Expose deterministic placeholders for credential-free previews."""
        return NetworkOutputs(
            vpc_id=pulumi.Output.from_input(
                build_resource_name(settings.stack_tag, "vpc")
            ),
            public_subnet_ids=[
                pulumi.Output.from_input(
                    build_resource_name(settings.stack_tag, f"public-{index + 1}")
                )
                for index, _ in enumerate(settings.network.public_subnet_cidrs)
            ],
            app_subnet_ids=[
                pulumi.Output.from_input(
                    build_resource_name(settings.stack_tag, f"app-{index + 1}")
                )
                for index, _ in enumerate(settings.network.app_subnet_cidrs)
            ],
            data_subnet_ids=[
                pulumi.Output.from_input(
                    build_resource_name(settings.stack_tag, f"data-{index + 1}")
                )
                for index, _ in enumerate(settings.network.data_subnet_cidrs)
            ],
            alb_security_group_id=pulumi.Output.from_input(
                build_resource_name(settings.stack_tag, "alb-sg")
            ),
            service_security_group_id=pulumi.Output.from_input(
                build_resource_name(settings.stack_tag, "svc-sg")
            ),
            documentdb_security_group_id=pulumi.Output.from_input(
                build_resource_name(settings.stack_tag, "docdb-sg")
            ),
            redis_security_group_id=pulumi.Output.from_input(
                build_resource_name(settings.stack_tag, "redis-sg")
            ),
        )

    def _build_managed_network(self, settings: StackSettings) -> NetworkOutputs:
        """Provision the VPC, subnets, routes, and security groups."""
        vpc = aws.ec2.Vpc(
            "user-service-vpc",
            cidr_block=settings.network.vpc_cidr,
            enable_dns_hostnames=True,
            enable_dns_support=True,
            opts=pulumi.ResourceOptions(parent=self),
        )

        internet_gateway = aws.ec2.InternetGateway(
            "user-service-igw",
            vpc_id=vpc.id,
            opts=pulumi.ResourceOptions(parent=self),
        )

        public_route_table = aws.ec2.RouteTable(
            "user-service-public-rt",
            vpc_id=vpc.id,
            routes=[
                aws.ec2.RouteTableRouteArgs(
                    cidr_block="0.0.0.0/0",
                    gateway_id=internet_gateway.id,
                )
            ],
            opts=pulumi.ResourceOptions(parent=self),
        )

        public_subnets: list[aws.ec2.Subnet] = []
        app_subnets: list[aws.ec2.Subnet] = []
        data_subnets: list[aws.ec2.Subnet] = []
        nat_gateways: list[aws.ec2.NatGateway] = []

        for index, availability_zone in enumerate(settings.network.availability_zones):
            public_subnet = aws.ec2.Subnet(
                f"user-service-public-subnet-{index + 1}",
                vpc_id=vpc.id,
                availability_zone=availability_zone,
                cidr_block=settings.network.public_subnet_cidrs[index],
                map_public_ip_on_launch=True,
                opts=pulumi.ResourceOptions(parent=self),
            )
            public_subnets.append(public_subnet)

            aws.ec2.RouteTableAssociation(
                f"user-service-public-rta-{index + 1}",
                subnet_id=public_subnet.id,
                route_table_id=public_route_table.id,
                opts=pulumi.ResourceOptions(parent=self),
            )

            app_subnet = aws.ec2.Subnet(
                f"user-service-app-subnet-{index + 1}",
                vpc_id=vpc.id,
                availability_zone=availability_zone,
                cidr_block=settings.network.app_subnet_cidrs[index],
                opts=pulumi.ResourceOptions(parent=self),
            )
            app_subnets.append(app_subnet)

            eip = aws.ec2.Eip(
                f"user-service-nat-eip-{index + 1}",
                domain="vpc",
                opts=pulumi.ResourceOptions(parent=self),
            )
            nat_gateway = aws.ec2.NatGateway(
                f"user-service-nat-{index + 1}",
                allocation_id=eip.id,
                subnet_id=public_subnet.id,
                opts=pulumi.ResourceOptions(parent=self),
            )
            nat_gateways.append(nat_gateway)

            app_route_table = aws.ec2.RouteTable(
                f"user-service-app-rt-{index + 1}",
                vpc_id=vpc.id,
                routes=[
                    aws.ec2.RouteTableRouteArgs(
                        cidr_block="0.0.0.0/0",
                        nat_gateway_id=nat_gateway.id,
                    )
                ],
                opts=pulumi.ResourceOptions(parent=self),
            )
            aws.ec2.RouteTableAssociation(
                f"user-service-app-rta-{index + 1}",
                subnet_id=app_subnet.id,
                route_table_id=app_route_table.id,
                opts=pulumi.ResourceOptions(parent=self),
            )

            data_subnet = aws.ec2.Subnet(
                f"user-service-data-subnet-{index + 1}",
                vpc_id=vpc.id,
                availability_zone=availability_zone,
                cidr_block=settings.network.data_subnet_cidrs[index],
                opts=pulumi.ResourceOptions(parent=self),
            )
            data_subnets.append(data_subnet)

            data_route_table = aws.ec2.RouteTable(
                f"user-service-data-rt-{index + 1}",
                vpc_id=vpc.id,
                opts=pulumi.ResourceOptions(parent=self),
            )
            aws.ec2.RouteTableAssociation(
                f"user-service-data-rta-{index + 1}",
                subnet_id=data_subnet.id,
                route_table_id=data_route_table.id,
                opts=pulumi.ResourceOptions(parent=self),
            )

        alb_security_group = aws.ec2.SecurityGroup(
            "user-service-alb-sg",
            vpc_id=vpc.id,
            description="Allow public HTTP and HTTPS traffic to the load balancer.",
            ingress=[
                aws.ec2.SecurityGroupIngressArgs(
                    protocol="tcp",
                    from_port=80,
                    to_port=80,
                    cidr_blocks=["0.0.0.0/0"],
                ),
                aws.ec2.SecurityGroupIngressArgs(
                    protocol="tcp",
                    from_port=443,
                    to_port=443,
                    cidr_blocks=["0.0.0.0/0"],
                ),
            ],
            egress=[
                aws.ec2.SecurityGroupEgressArgs(
                    protocol="-1",
                    from_port=0,
                    to_port=0,
                    cidr_blocks=["0.0.0.0/0"],
                )
            ],
            opts=pulumi.ResourceOptions(parent=self),
        )

        service_security_group = aws.ec2.SecurityGroup(
            "user-service-service-sg",
            vpc_id=vpc.id,
            description="Allow application traffic from the public load balancer.",
            ingress=[
                aws.ec2.SecurityGroupIngressArgs(
                    protocol="tcp",
                    from_port=settings.capacity.container_port,
                    to_port=settings.capacity.container_port,
                    security_groups=[alb_security_group.id],
                )
            ],
            egress=[
                aws.ec2.SecurityGroupEgressArgs(
                    protocol="-1",
                    from_port=0,
                    to_port=0,
                    cidr_blocks=["0.0.0.0/0"],
                )
            ],
            opts=pulumi.ResourceOptions(parent=self),
        )

        documentdb_security_group = aws.ec2.SecurityGroup(
            "user-service-documentdb-sg",
            vpc_id=vpc.id,
            description="Allow ECS tasks to reach the DocumentDB cluster.",
            ingress=[
                aws.ec2.SecurityGroupIngressArgs(
                    protocol="tcp",
                    from_port=settings.documentdb.port,
                    to_port=settings.documentdb.port,
                    security_groups=[service_security_group.id],
                )
            ],
            egress=[
                aws.ec2.SecurityGroupEgressArgs(
                    protocol="-1",
                    from_port=0,
                    to_port=0,
                    cidr_blocks=["0.0.0.0/0"],
                )
            ],
            opts=pulumi.ResourceOptions(parent=self),
        )

        redis_security_group = aws.ec2.SecurityGroup(
            "user-service-redis-sg",
            vpc_id=vpc.id,
            description="Allow ECS tasks to reach the Redis replication group.",
            ingress=[
                aws.ec2.SecurityGroupIngressArgs(
                    protocol="tcp",
                    from_port=settings.redis.port,
                    to_port=settings.redis.port,
                    security_groups=[service_security_group.id],
                )
            ],
            egress=[
                aws.ec2.SecurityGroupEgressArgs(
                    protocol="-1",
                    from_port=0,
                    to_port=0,
                    cidr_blocks=["0.0.0.0/0"],
                )
            ],
            opts=pulumi.ResourceOptions(parent=self),
        )

        return NetworkOutputs(
            vpc_id=vpc.id,
            public_subnet_ids=[subnet.id for subnet in public_subnets],
            app_subnet_ids=[subnet.id for subnet in app_subnets],
            data_subnet_ids=[subnet.id for subnet in data_subnets],
            alb_security_group_id=alb_security_group.id,
            service_security_group_id=service_security_group.id,
            documentdb_security_group_id=documentdb_security_group.id,
            redis_security_group_id=redis_security_group.id,
        )
