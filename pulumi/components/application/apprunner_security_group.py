import pulumi
import pulumi_aws as aws

class AppRunnerSecurityGroupComponent(pulumi.ComponentResource):
    def __init__(self, name: str, vpc_id, ingress_from_sg_id=None, tags: dict = None, opts: pulumi.ResourceOptions = None):
        """
        Creates a security group for the App Runner VPC connector.
        If `ingress_from_sg_id` is provided, allows ingress on port 3306 from that SG.
        """
        super().__init__("custom:component:AppRunnerSecurityGroupComponent", name, {}, opts)
        ingress_rules = []
        if ingress_from_sg_id:
            ingress_rules.append(aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=3306,
                to_port=3306,
                security_groups=[ingress_from_sg_id]
            ))
        self.sg = aws.ec2.SecurityGroup(
            f"{name}-apprunner-sg",
            vpc_id=vpc_id,
            description="Security group for App Runner VPC connector",
            ingress=ingress_rules,
            egress=[aws.ec2.SecurityGroupEgressArgs(
                protocol="-1",
                from_port=0,
                to_port=0,
                cidr_blocks=["0.0.0.0/0"]
            )],
            tags=tags or {"Name": f"{name}-apprunner-sg"},
            opts=pulumi.ResourceOptions(parent=self)
        )
        self.register_outputs({
            "apprunner_sg_id": self.sg.id
        })
