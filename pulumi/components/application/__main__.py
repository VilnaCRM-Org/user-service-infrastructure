import pulumi
from pulumi import ResourceOptions
from components.ecr_repository import EcrRepositoryComponent
from components.apprunner_roles import AppRunnerRolesComponent
from components.vpc_connector import VpcConnectorComponent
from components.apprunner_service import AppRunnerServiceComponent

class ApplicationComponent(pulumi.ComponentResource):
    def __init__(self, name: str, private_subnet_ids: list, app_config: dict, opts: ResourceOptions = None):
        super().__init__("custom:feature:ApplicationComponent", name, None, opts)

        # Create the ECR repository.
        self.ecr_repo = EcrRepositoryComponent(name, opts=ResourceOptions(parent=self))
        # Create App Runner IAM roles.
        self.apprunner_roles = AppRunnerRolesComponent(name, opts=ResourceOptions(parent=self))
        # Create the VPC Connector using private subnets.
        # Expects an optional list of security group IDs in app_config.
        self.vpc_connector = VpcConnectorComponent(
            name,
            subnet_ids=private_subnet_ids,
            security_group_ids=app_config.get("vpc_connector_sg_ids", []),
            opts=ResourceOptions(parent=self)
        )
        # Create the App Runner service.
        self.apprunner_service = AppRunnerServiceComponent(
            name,
            ecr_repo_url=self.ecr_repo.repo.repository_url,
            apprunner_role_arn=self.apprunner_roles.apprunner_access_role.arn,
            vpc_connector_arn=self.vpc_connector.connector.arn,
            environment_variables=app_config.get("environment_variables", {}),
            port=app_config.get("port", "80"),
            opts=ResourceOptions(parent=self)
        )

        self.register_outputs({
            "apprunner_service_url": self.apprunner_service.service.service_url,
            "repository_url": self.ecr_repo.repo.repository_url
        })
