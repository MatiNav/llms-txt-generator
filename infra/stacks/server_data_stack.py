from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_rds as rds
from constructs import Construct


class ServerDataStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        database_name = "llmstxt"
        database_username = "llmstxt"

        # Challenge-mode tradeoff: keep only public subnets to avoid NAT cost/complexity.
        # Production should place RDS in private subnets and use NAT/VPC endpoints as needed.
        service_vpc = ec2.Vpc(
            self,
            "ServiceVpc",
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                )
            ],
        )

        database_security_group = ec2.SecurityGroup(
            self,
            "DatabaseSecurityGroup",
            vpc=service_vpc,
            description="Challenge-mode PostgreSQL security group",
            allow_all_outbound=True,
        )
        database_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(5432),
            description="Challenge-mode only: allow public PostgreSQL access",
        )

        database_instance = rds.DatabaseInstance(
            self,
            "ServerDatabase",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16_3,
            ),
            vpc=service_vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_groups=[database_security_group],
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T4G,
                ec2.InstanceSize.MICRO,
            ),
            credentials=rds.Credentials.from_generated_secret(
                username=database_username,
                exclude_characters='"@/:?&%#',
            ),
            database_name=database_name,
            allocated_storage=20,
            max_allocated_storage=100,
            backup_retention=Duration.days(1),
            delete_automated_backups=True,
            deletion_protection=False,
            removal_policy=RemovalPolicy.DESTROY,
            publicly_accessible=True,
            multi_az=False,
        )

        database_secret = database_instance.secret
        if database_secret is None:
            raise ValueError("Database secret is required for runtime DATABASE_URL")

        database_password = database_secret.secret_value_from_json(
            "password"
        ).to_string()
        self.database_url = (
            f"postgresql+asyncpg://{database_username}:{database_password}@"
            f"{database_instance.db_instance_endpoint_address}:"
            f"{database_instance.db_instance_endpoint_port}/{database_name}"
        )

        CfnOutput(
            self,
            "DatabaseEndpointAddress",
            value=database_instance.db_instance_endpoint_address,
            description="PostgreSQL endpoint hostname",
        )

        CfnOutput(
            self,
            "DatabasePort",
            value=database_instance.db_instance_endpoint_port,
            description="PostgreSQL endpoint port",
        )

        CfnOutput(
            self,
            "DatabaseName",
            value=database_name,
            description="Database name used by the server",
        )

        CfnOutput(
            self,
            "DatabaseSecretArn",
            value=database_secret.secret_arn,
            description="Secrets Manager ARN containing DB credentials",
        )
