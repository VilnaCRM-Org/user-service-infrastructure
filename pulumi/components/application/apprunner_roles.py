import pulumi
import pulumi_aws as aws
import json

class AppRunnerRolesComponent(pulumi.ComponentResource):
    def __init__(self, name: str, opts: pulumi.ResourceOptions = None):
        super().__init__("custom:component:AppRunnerRolesComponent", name, {}, opts)
        self.apprunner_access_role = aws.iam.Role(
            f"{name}-apprunner-access-role",
            assume_role_policy=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "build.apprunner.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }),
            opts=pulumi.ResourceOptions(parent=self)
        )
        aws.iam.RolePolicyAttachment(
            f"{name}-ecr-read",
            role=self.apprunner_access_role.name,
            policy_arn="arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess",
            opts=pulumi.ResourceOptions(parent=self)
        )
        self.register_outputs({
            "apprunner_access_role_arn": self.apprunner_access_role.arn
        })
