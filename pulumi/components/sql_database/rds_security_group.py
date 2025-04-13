import pulumi
import pulumi_aws as aws

class RDSSecurityGroupComponent(pulumi.ComponentResource):
    def __init__(self, name: str, vpc_id, allowed_cidr: str = "10.0.0.0/16", tags: dict = None, opts: pulumi.ResourceOptions = None):
        """
        Creates a security group for RDS allowing MySQL (port 3306) access.
        """
        super().__init__("custom:component:RDSSecurityGroupComponent", name, {}, opts)
        self.sg = aws.ec2.SecurityGroup(
            f"{name}-rds-sg",
            vpc_id=vpc_id,
            description="Allow MySQL access",
            ingress=[aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=3306,
                to_port=3306,
                cidr_blocks=[allowed_cidr]
            )],
            egress=[aws.ec2.SecurityGroupEgressArgs(
                protocol="-1",
                from_port=0,
                to_port=0,
                cidr_blocks=["0.0.0.0/0"]
            )],
            tags=tags or {"Name": f"{name}-rds-sg"},
            opts=pulumi.ResourceOptions(parent=self)
        )
        self.register_outputs({
            "rds_sg_id": self.sg.id
        })
