import pulumi
from pulumi import ResourceOptions
from components.rds_security_group import RDSSecurityGroupComponent
from components.rds_subnet_group import RdsSubnetGroupComponent
from components.rds_instance import RdsInstanceComponent

class SQLDatabaseComponent(pulumi.ComponentResource):
    def __init__(self, name: str, vpc_id, private_subnet_ids: list, db_config: dict, opts: ResourceOptions = None):
        super().__init__("custom:feature:SQLDatabaseComponent", name, None, opts)

        # Create the RDS security group.
        self.rds_sg = RDSSecurityGroupComponent(name, vpc_id=vpc_id, opts=ResourceOptions(parent=self))
        # Create the RDS subnet group using the provided private subnets.
        self.subnet_group = RdsSubnetGroupComponent(name, subnet_ids=private_subnet_ids, opts=ResourceOptions(parent=self))
        # Create the RDS instance.
        self.db_instance = RdsInstanceComponent(
            name,
            subnet_group_name=self.subnet_group.subnet_group.name,
            security_group_ids=[self.rds_sg.sg.id],
            db_name=db_config.get("db_name", "mydb"),
            engine=db_config.get("engine", "mariadb"),
            engine_version=db_config.get("engine_version", "11.4.4"),
            instance_class=db_config.get("instance_class", "db.t4g.micro"),
            allocated_storage=db_config.get("allocated_storage", 20),
            username=db_config.get("username", "admin"),
            password=db_config["password"],
            backup_retention_period=db_config.get("backup_retention_period", 7),
            opts=ResourceOptions(parent=self)
        )

        self.register_outputs({
            "rds_instance_id": self.db_instance.db_instance.id,
            "rds_endpoint": self.db_instance.db_instance.endpoint
        })
