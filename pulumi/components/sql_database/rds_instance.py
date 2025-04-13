import pulumi
import pulumi_aws as aws

class RdsInstanceComponent(pulumi.ComponentResource):
    def __init__(self, name: str, subnet_group_name, security_group_ids: list, db_name: str = "mydb",
                 engine: str = "mariadb", engine_version: str = "11.4.4", instance_class: str = "db.t4g.micro",
                 allocated_storage: int = 20, username: str = "admin",  storage_type: str = "gp3", password: str = None,
                 backup_retention_period: int = 7, tags: dict = None, opts: pulumi.ResourceOptions = None):
        super().__init__("custom:component:RdsInstanceComponent", name, {}, opts)
        if not password:
            raise Exception("Password must be provided for the RDS instance.")
        self.db_instance = aws.rds.Instance(
            f"{name}-rds-instance",
            engine=engine,
            engine_version=engine_version,
            instance_class=instance_class,
            allocated_storage=allocated_storage,
            storage_type=storage_type,
            db_subnet_group_name=subnet_group_name,
            vpc_security_group_ids=security_group_ids,
            db_name=db_name,
            username=username,
            password=password,
            skip_final_snapshot=True,
            publicly_accessible=False,
            multi_az=False,
            backup_retention_period=backup_retention_period,
            apply_immediately=True,
            tags=tags or {"Name": f"{name}-rds-instance"},
            opts=pulumi.ResourceOptions(parent=self)
        )
        self.register_outputs({
            "rds_instance_id": self.db_instance.id,
            "rds_endpoint": self.db_instance.endpoint
        })
