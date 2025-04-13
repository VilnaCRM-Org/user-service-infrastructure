import pulumi
import pulumi_aws as aws

class AppRunnerServiceComponent(pulumi.ComponentResource):
    def __init__(self, name: str, ecr_repo_url, apprunner_role_arn, vpc_connector_arn,
                 environment_variables: dict = None, port: str = "80", tags: dict = None, opts: pulumi.ResourceOptions = None):
        super().__init__("custom:component:AppRunnerServiceComponent", name, {}, opts)
        default_env = {
            "SERVER_NAME": "default-server",
            "TRUSTED_HOSTS": "default-trusted"
        }
        if environment_variables:
            default_env.update(environment_variables)
        self.service = aws.apprunner.Service(
            f"{name}-apprunner-service",
            service_name=f"{name}-apprunner",
            source_configuration=aws.apprunner.ServiceSourceConfigurationArgs(
                image_repository=aws.apprunner.ServiceSourceConfigurationImageRepositoryArgs(
                    image_repository_type="ECR",
                    image_identifier=ecr_repo_url.apply(lambda url: f"{url}:latest"),
                    image_configuration=aws.apprunner.ServiceSourceConfigurationImageRepositoryImageConfigurationArgs(
                        port=port,
                        runtime_environment_variables=default_env
                    )
                ),
                authentication_configuration=aws.apprunner.ServiceSourceConfigurationAuthenticationConfigurationArgs(
                    access_role_arn=apprunner_role_arn
                ),
                auto_deployments_enabled=True
            ),
            network_configuration=aws.apprunner.ServiceNetworkConfigurationArgs(
                egress_configuration=aws.apprunner.ServiceNetworkConfigurationEgressConfigurationArgs(
                    egress_type="VPC",
                    vpc_connector_arn=vpc_connector_arn
                )
            ),
            tags=tags or {"Name": f"{name}-apprunner-service"},
            opts=pulumi.ResourceOptions(parent=self)
        )
        self.register_outputs({
            "apprunner_service_url": self.service.service_url,
            "apprunner_service_arn": self.service.arn
        })
