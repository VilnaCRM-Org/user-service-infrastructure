import pulumi
from pulumi import Config

from features.network import NetworkComponent
from features.sql_database import SQLDatabaseComponent
from features.application import ApplicationComponent
from features.message_broker import MessageBrokerComponent

# Read configuration.
config = Config()
vpc_cidr = config.get("vpcCidr") or "10.0.0.0/16"

# Database configuration.
db_password = config.require_secret("dbPassword")
db_config = {
    "db_name": config.get("dbName") or "mydb",
    "username": config.get("dbUsername") or "admin",
    "engine": "mariadb",
    "engine_version": config.get("dbEngineVersion") or "11.4.4",
    "instance_class": "db.t4g.micro",
    "allocated_storage": 20,
    "password": db_password,
    "backup_retention_period": 7
}

# Application configuration.
app_config = {
    "environment_variables": {},  # Will be updated below.
    "vpc_connector_sg_ids": [],     # Optionally override with your SG IDs.
    "port": "80"
}

# 1. Create network resources.
network = NetworkComponent("app-network", cidr=vpc_cidr)

# 2. Create SQL Database feature using network info.
sql_db = SQLDatabaseComponent("app-db", vpc_id=network.vpc.vpc.id,
    private_subnet_ids=network.private_subnets.subnets,
    db_config=db_config)

# 3. Update application config with DATABASE_URL using the DB endpoint.
app_config["environment_variables"]["DATABASE_URL"] = sql_db.db_instance.db_instance.endpoint.apply(
    lambda ep: f"mysql://{db_config.get('username')}:{db_password}@{ep}:3306/{db_config.get('db_name')}?serverVersion={db_config.get('engine_version')}"
)

# 4. Create Application feature.
application = ApplicationComponent("app", private_subnet_ids=network.private_subnets.subnets, app_config=app_config)

# 5. Create Message Broker feature.
message_broker = MessageBrokerComponent("app")

# Export key outputs.
pulumi.export("vpc_id", network.vpc.vpc.id)
pulumi.export("public_subnet_ids", [s.id for s in network.public_subnets.subnets])
pulumi.export("private_subnet_ids", [s.id for s in network.private_subnets.subnets])
pulumi.export("rds_endpoint", sql_db.db_instance.db_instance.endpoint)
pulumi.export("ecr_repository_url", application.ecr_repo.repo.repository_url)
pulumi.export("apprunner_service_url", application.apprunner_service.service.service_url)
pulumi.export("sqs_main_queue_url", message_broker.sqs_queues.main_queue.url)
pulumi.export("sqs_dlq_url", message_broker.sqs_queues.dlq.url)
