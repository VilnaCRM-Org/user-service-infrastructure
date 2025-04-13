import pulumi
import json
import pulumi_aws as aws

config = pulumi.Config()

engine="mariadb",

db_password = config.require_secret("db_password")
db_name = "mydb"
db_username = "admin"
db_engine_version = "11.4.4"

region = config.require("region")

vpc = aws.ec2.Vpc("app-vpc",
    cidr_block="10.0.0.0/16",
    enable_dns_hostnames=True,
    enable_dns_support=True,
    tags={"Name": "app-vpc"}
)

# Create an Internet Gateway.
igw = aws.ec2.InternetGateway("app-igw",
    vpc_id=vpc.id,
    tags={"Name": "app-igw"}
)

# Create two public subnets (adjust AZs as needed).
public_subnet1 = aws.ec2.Subnet("public-subnet-1",
    vpc_id=vpc.id,
    cidr_block="10.0.1.0/24",
    availability_zone="eu-central-1a",
    map_public_ip_on_launch=True,
    tags={"Name": "public-subnet-1"}
)

public_subnet2 = aws.ec2.Subnet("public-subnet-2",
    vpc_id=vpc.id,
    cidr_block="10.0.2.0/24",
    availability_zone="eu-central-1b",
    map_public_ip_on_launch=True,
    tags={"Name": "public-subnet-2"}
)

# Create two private subnets.
private_subnet1 = aws.ec2.Subnet("private-subnet-1",
    vpc_id=vpc.id,
    cidr_block="10.0.101.0/24",
    availability_zone="eu-central-1a",
    tags={"Name": "private-subnet-1"}
)

private_subnet2 = aws.ec2.Subnet("private-subnet-2",
    vpc_id=vpc.id,
    cidr_block="10.0.102.0/24",
    availability_zone="eu-central-1b",
    tags={"Name": "private-subnet-2"}
)

# Allocate an Elastic IP for the NAT Gateway.
nat_eip = aws.ec2.Eip("nat-eip",
    vpc=True,
    tags={"Name": "nat-eip"}
)

# Create a NAT Gateway in one of the public subnets.
nat_gw = aws.ec2.NatGateway("nat-gw",
    allocation_id=nat_eip.id,
    subnet_id=public_subnet1.id,
    tags={"Name": "nat-gw"}
)

# Create a public route table with a default route via the Internet Gateway.
public_rt = aws.ec2.RouteTable("public-rt",
    vpc_id=vpc.id,
    routes=[aws.ec2.RouteTableRouteArgs(
        cidr_block="0.0.0.0/0",
        gateway_id=igw.id,
    )],
    tags={"Name": "public-rt"}
)

# Associate the public subnets with the public route table.
aws.ec2.RouteTableAssociation("public-rt-assoc-1",
    subnet_id=public_subnet1.id,
    route_table_id=public_rt.id
)
aws.ec2.RouteTableAssociation("public-rt-assoc-2",
    subnet_id=public_subnet2.id,
    route_table_id=public_rt.id
)

# Create a private route table with a default route via the NAT Gateway.
private_rt = aws.ec2.RouteTable("private-rt",
    vpc_id=vpc.id,
    routes=[aws.ec2.RouteTableRouteArgs(
        cidr_block="0.0.0.0/0",
        nat_gateway_id=nat_gw.id,
    )],
    tags={"Name": "private-rt"}
)

# Associate the private subnets with the private route table.
aws.ec2.RouteTableAssociation("private-rt-assoc-1",
    subnet_id=private_subnet1.id,
    route_table_id=private_rt.id
)
aws.ec2.RouteTableAssociation("private-rt-assoc-2",
    subnet_id=private_subnet2.id,
    route_table_id=private_rt.id
)

# Security Group for RDS: allow MySQL access (port 3306) from within the VPC.
rds_sg = aws.ec2.SecurityGroup("rds-sg",
    description="Allow MySQL access",
    vpc_id=vpc.id,
    ingress=[aws.ec2.SecurityGroupIngressArgs(
        protocol="tcp",
        from_port=3306,
        to_port=3306,
        cidr_blocks=["10.0.0.0/16"],
    )],
    egress=[aws.ec2.SecurityGroupEgressArgs(
        protocol="-1",
        from_port=0,
        to_port=0,
        cidr_blocks=["0.0.0.0/0"],
    )],
    tags={"Name": "rds-sg"}
)

# Security Group for the App Runner VPC Connector.
apprunner_sg = aws.ec2.SecurityGroup("apprunner-sg",
    description="Security group for App Runner VPC connector",
    vpc_id=vpc.id,
    # You can further restrict ingress based on your requirements.
    ingress=[aws.ec2.SecurityGroupIngressArgs(
        protocol="tcp",
        from_port=3306,
        to_port=3306,
        security_groups=[rds_sg.id],
    )],
    egress=[aws.ec2.SecurityGroupEgressArgs(
        protocol="-1",
        from_port=0,
        to_port=0,
        cidr_blocks=["0.0.0.0/0"],
    )],
    tags={"Name": "apprunner-sg"}
)

# Create a DB subnet group using the private subnets.
rds_subnet_group = aws.rds.SubnetGroup("rds-subnet-group",
    subnet_ids=[private_subnet1.id, private_subnet2.id],
    tags={"Name": "rds-subnet-group"}
)

# Create an App Runner VPC Connector that uses the private subnets.
vpc_connector = aws.apprunner.VpcConnector("app-runner-vpc-connector",
    vpc_connector_name="app-runner-vpc-connector-name",
    subnets=[private_subnet1.id, private_subnet2.id],
    security_groups=[apprunner_sg.id],
    tags={"Name": "app-runner-vpc-connector"}
)

# RDS MariaDB instance
db = aws.rds.Instance("mariadb",
    engine="mariadb",
    engine_version=db_engine_version,
    instance_class="db.t4g.micro",
    allocated_storage=20,
    storage_type="gp3",
    db_subnet_group_name=rds_subnet_group.name,
    vpc_security_group_ids=[rds_sg.id],
    db_name=db_name,
    username=db_username,
    password=db_password,
    skip_final_snapshot=True,
    publicly_accessible=False,
    multi_az=False,
    backup_retention_period=7,
    apply_immediately=True,
    tags={"Name": "my-mariadb-instance"},
)

# ECR repository
repo = aws.ecr.Repository(
    "user-service-ecr",
    image_tag_mutability="MUTABLE",
    tags={"Name": "user_service"},
)

# IAM role for App Runner to access ECR
apprunner_access_role = aws.iam.Role("apprunner-access-role",
    assume_role_policy="""{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "build.apprunner.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }"""
)

aws.iam.RolePolicyAttachment(
    "ecr-read",
    role=apprunner_access_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
)

# -----------------------------------------------------------
# SQS Queues and DLQs for App Runner SQS Interactions
# -----------------------------------------------------------

def create_queue(name):
    dlq = aws.sqs.Queue(f"{name}-dlq", visibility_timeout_seconds=30)
    queue = aws.sqs.Queue(
        name,
        visibility_timeout_seconds=30,
        redrive_policy=dlq.arn.apply(
            lambda arn: json.dumps({
                "deadLetterTargetArn": arn, "maxReceiveCount": 5
            })
        )
    )

    aws.sqs.QueuePolicy(f"{name}-queue-policy",
        queue_url=queue.id,
        policy=queue.arn.apply(
            lambda arn: json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "sqs:*",
                    "Resource": arn
                }]
            })
        )
    )

    return queue

send_email_queue = create_queue("send-email")
insert_user_queue = create_queue("insert-user")

# -----------------------------------------------------------
# IAM Role and Policy for App Runner SQS Interactions
# -----------------------------------------------------------

apprunner_instance_role = aws.iam.Role("apprunner-instance-role",
    assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {
                "Service": "tasks.apprunner.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }]
    }),
)

aws.iam.RolePolicyAttachment(
    "apprunner-sqs-ecr-access",
    role=apprunner_instance_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
)

sqs_policy = aws.iam.RolePolicy(
    "apprunner-sqs-policy",
    role=apprunner_instance_role.id,
    policy=pulumi.Output.all(send_message_queue_arn=insert_user_queue.arn, send_email_queue_arn=send_email_queue.arn).apply(
        lambda arns: json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": [
                    "sqs:SendMessage",
                    "sqs:SendMessageBatch"
                ],
                "Resource": [arns['send_message_queue_arn'], arns['send_email_queue_arn']]
            }]
        })
    )
)

db_url = (pulumi.Output.all(db_username, db_password, db.address)
    .apply(lambda args: f"mysql://{args[0]}:{args[1]}@{args[2]}:3306/{db_name}?serverVersion={db_engine_version}"))

service = aws.apprunner.Service(
    resource_name="app-runner-resource",
    service_name="app-runner-service",
    source_configuration=aws.apprunner.ServiceSourceConfigurationArgs(
        image_repository=aws.apprunner.ServiceSourceConfigurationImageRepositoryArgs(
            image_identifier=repo.repository_url.apply(lambda url: f"{url}:latest"),
            image_repository_type="ECR",
            image_configuration=aws.apprunner.ServiceSourceConfigurationImageRepositoryImageConfigurationArgs(
                port="80",
                runtime_environment_variables={
                    "SERVER_NAME": "yx9zwfavpc.eu-central-1.awsapprunner.com:80",
                    "TRUSTED_HOSTS": "yx9zwfavpc.eu-central-1.awsapprunner.com",
                    "DATABASE_URL": db_url
                },
            ),
        ),
        authentication_configuration=aws.apprunner.ServiceSourceConfigurationAuthenticationConfigurationArgs(
            access_role_arn=apprunner_access_role.arn
        ),
        auto_deployments_enabled=True
    ),
    instance_configuration=aws.apprunner.ServiceInstanceConfigurationArgs(
         instance_role_arn=apprunner_instance_role.arn
    ),
    network_configuration=aws.apprunner.ServiceNetworkConfigurationArgs(
        egress_configuration=aws.apprunner.ServiceNetworkConfigurationEgressConfigurationArgs(
            egress_type="VPC",
            vpc_connector_arn=vpc_connector.arn,
        )
    ),
)

# -----------------------------------------------------------
# Outputs
# -----------------------------------------------------------
pulumi.export("vpc_id", vpc.id)
pulumi.export("vpc_cidr_block", vpc.cidr_block)

pulumi.export("rds_security_group_id", rds_sg.id)

pulumi.export("rds_endpoint", db.endpoint)
pulumi.export("rds_arn", db.arn)
pulumi.export("rds_instance_id", db.id)

pulumi.export("ecr_repo_name", repo.name)
pulumi.export("ecr_repository_url", repo.repository_url)

pulumi.export("app_runner_service_url", service.service_url)
pulumi.export("app_runner_service_arn", service.arn)

pulumi.export("vpc_connector_arn", vpc_connector.arn)

pulumi.export("apprunner_access_role_arn", apprunner_access_role.arn)
pulumi.export("apprunner_instance_role_arn", apprunner_instance_role.arn)

pulumi.export("send_email_queue_url", send_email_queue.url)
pulumi.export("insert_user_queue_url", insert_user_queue.url)