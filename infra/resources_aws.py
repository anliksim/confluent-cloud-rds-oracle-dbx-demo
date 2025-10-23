import json
import pulumi
import pulumi_aws as aws
import resources_manager as resources


def create_networking(rsm: resources.ResourcesManager):
    vpc_id = rsm.vpc_id
    if vpc_id:
        # get existing vpc by id
        vpc = aws.ec2.get_vpc(id=vpc_id)
        # get internet gateway by vpc id
        igw = aws.ec2.get_internet_gateway(
            filters=[
                aws.ec2.GetInternetGatewayFilterArgs(
                    name="attachment.vpc-id",
                    values=[vpc.id],
                )
            ]
        )
    else:
        vpc = aws.ec2.Vpc(
            f"{rsm.resource_prefix}-vpc",
            opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
            cidr_block="172.31.0.0/16",
            enable_dns_hostnames=True,
            enable_dns_support=True,
            tags={
                **rsm.default_tags,
            },
        )
        igw = aws.ec2.InternetGateway(
            f"{rsm.resource_prefix}-igw",
            opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
            vpc_id=vpc.id,
            tags={
                **rsm.default_tags,
            },
        )

    # Create subnets in different AZs
    subnet1 = aws.ec2.Subnet(
        f"{rsm.resource_prefix}-rds-subnet-1",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        vpc_id=vpc.id,
        cidr_block="172.31.60.0/24",
        availability_zone=f"{rsm.region}a",
        tags={
            **rsm.default_tags,
        },
    )

    subnet2 = aws.ec2.Subnet(
        f"{rsm.resource_prefix}-rds-subnet-2",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        vpc_id=vpc.id,
        cidr_block="172.31.61.0/24",
        availability_zone=f"{rsm.region}b",
        tags={
            **rsm.default_tags,
        },
    )

    # Route table
    route_table = aws.ec2.RouteTable(
        f"{rsm.resource_prefix}-rds-route-table",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        vpc_id=vpc.id,
        routes=[aws.ec2.RouteTableRouteArgs(cidr_block="0.0.0.0/0", gateway_id=igw.id)],
        tags={
            **rsm.default_tags,
        },
    )

    # Associate route table with subnets
    _ = aws.ec2.RouteTableAssociation(
        f"{rsm.resource_prefix}-rds-rt-assoc-1",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        subnet_id=subnet1.id,
        route_table_id=route_table.id,
    )

    _ = aws.ec2.RouteTableAssociation(
        f"{rsm.resource_prefix}-rds-rt-assoc-2",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        subnet_id=subnet2.id,
        route_table_id=route_table.id,
    )

    # DB subnet group
    db_subnet_group = aws.rds.SubnetGroup(
        f"{rsm.resource_prefix}-rds-subnet-group",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        subnet_ids=[subnet1.id, subnet2.id],
        tags={
            **rsm.default_tags,
        },
    )

    # Security group with whitelisted IPs
    security_group = aws.ec2.SecurityGroup(
        f"{rsm.resource_prefix}-rds-sg",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        vpc_id=vpc.id,
        description="Security group for RDS Oracle instance with whitelisted IP access",
        ingress=[
            aws.ec2.SecurityGroupIngressArgs(
                description="Oracle access from any IP",
                from_port=1521,
                to_port=1521,
                protocol="tcp",
                cidr_blocks=["0.0.0.0/0"],
            ),
            # confluent cloud egress IPs
            # aws.ec2.SecurityGroupIngressArgs(
            #     description="Oracle access from Confluent Cloud egress IPs",
            #     from_port=1521,
            #     to_port=1521,
            #     protocol="tcp",
            #     cidr_blocks=[
            #         "3.65.19.250/32",
            #         "3.65.208.59/32",
            #         "3.66.63.50/32",
            #         "3.120.91.22/32",
            #         "3.127.26.151/32",
            #         "3.127.119.115/32",
            #         "18.156.154.109/32",
            #         "18.157.63.180/32",
            #         "18.157.225.195/32",
            #         "18.159.63.188/32",
            #         "18.193.226.86/32",
            #         "18.195.124.183/32",
            #         "18.198.101.209/32",
            #         "18.198.174.129/32",
            #         "35.157.170.110/32",
            #         "52.28.88.81/32",
            #     ],
            # ),
        ],
        egress=[
            aws.ec2.SecurityGroupEgressArgs(
                from_port=0, to_port=0, protocol="-1", cidr_blocks=["0.0.0.0/0"]
            )
        ],
        tags={
            **rsm.default_tags,
        },
    )
    pulumi.export("aws_vpc_id", vpc.id)
    pulumi.export("aws_security_group_id", security_group.id)

    rsm.aws_subnet_group = db_subnet_group
    rsm.aws_security_group = security_group


def create_s3_bucket(rsm: resources.ResourcesManager):
    """Create an S3 bucket for storage and return outputs."""

    name = f"{rsm.resource_prefix}-tableflow-bucket"
    tableflow_bucket = aws.s3.Bucket(
        name,
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        bucket=name,
        # Add tags
        tags={
            **(rsm.default_tags),
            "purpose": "Storage for Delta/Iceberg tables used by Confluent Tableflow and Databricks",
        },
    )
    pulumi.export("aws_tableflow_bucket_name", tableflow_bucket.bucket)
    rsm.aws_tableflow_bucket = tableflow_bucket


def create_kms_key(rsm: resources.ResourcesManager):
    """Create a KMS key for encryption and return outputs.
    cfg is a dict-like object from shared.config.get_config().
    """
    aws_caller_id = aws.get_caller_identity()

    # Create a KMS key for TDE (Transparent Data Encryption)
    tde_kms_key = aws.kms.Key(
        f"{rsm.resource_prefix}-tde-kms-key",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        description="KMS key for RDS Oracle TDE encryption",
        key_usage="ENCRYPT_DECRYPT",
        enable_key_rotation=False,
        deletion_window_in_days=7,  # Minimum deletion window
        policy=json.dumps(
            {
                "Version": "2012-10-17",
                "Id": f"{rsm.resource_prefix}-tde-kms-key-policy-1",
                "Statement": [
                    {
                        "Sid": "Enable IAM User Permissions",
                        "Effect": "Allow",
                        "Principal": {
                            "AWS": f"arn:aws:iam::{aws_caller_id.account_id}:root"
                        },
                        "Action": "kms:*",
                        "Resource": "*",
                    },
                ],
            }
        ),
        # Add tags
        tags={
            **(rsm.default_tags),
            "purpose": "Customer demo for TDE Encryption",
        },
    )
    pulumi.export("aws_tde_kms_key_id", tde_kms_key.id)

    # define alias if needed
    # _ = aws.kms.Alias(
    #     f"{rsm.resource_prefix}-tde-kms-key-alias",
    #     opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
    #     name=f"alias/{rsm.resource_prefix}-tde-kms-key",
    #     target_key_id=tde_kms_key.id,
    # )
    rsm.aws_kms_key = tde_kms_key


def create_deny_all_assume_role(
    rsm: resources.ResourcesManager, resource_name: str, purpose: str
) -> aws.iam.Role:
    """Create an IAM role that can be assumed by the given principal ARN."""

    role = aws.iam.Role(
        resource_name,
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        name=resource_name,
        assume_role_policy=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Deny",
                        "Principal": {"AWS": "*"},
                        "Action": "sts:AssumeRole",
                    }
                ],
            }
        ),
        tags={
            **(rsm.default_tags),
            "purpose": purpose,
        },
    )
    pulumi.export(resource_name, role.arn)

    return role


def create_tableflow_access_policy(rsm: resources.ResourcesManager):
    """Create the AWS Tableflow Role Policy."""

    assert rsm.aws_tableflow_bucket, "AWS Tableflow S3 bucket is not defined"

    # IAM Role Policy for S3 access
    tableflow_policy = aws.iam.Policy(
        f"{rsm.resource_prefix}-tableflow-role-policy",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        policy=rsm.aws_tableflow_bucket.bucket.apply(
            lambda bucket_name: json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": [
                                "s3:GetBucketLocation",
                                "s3:ListBucketMultipartUploads",
                                "s3:ListBucket",
                            ],
                            "Resource": [f"arn:aws:s3:::{bucket_name}"],
                        },
                        {
                            "Effect": "Allow",
                            "Action": [
                                "s3:PutObject",
                                "s3:PutObjectTagging",
                                "s3:GetObject",
                                "s3:DeleteObject",
                                "s3:AbortMultipartUpload",
                                "s3:ListMultipartUploadParts",
                            ],
                            "Resource": [f"arn:aws:s3:::{bucket_name}/*"],
                        },
                    ],
                }
            )
        ),
    )

    rsm.aws_tableflow_access_policy = tableflow_policy


def update_tableflow_access_role(rsm: resources.ResourcesManager):
    """Update the AWS Tableflow IAM Policy with the latest policy document."""

    assert rsm.aws_tableflow_access_policy, "AWS Tableflow IAM Policy is not defined"
    assert rsm.cflt_s3_provider_integration, (
        "Confluent S3 Provider Integration is not defined"
    )

    tableflow_assume_role = aws.iam.Role(
        rsm.tableflow_access_role_name,
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        name=rsm.tableflow_access_role_name,
        # apply on multiple including id
        assume_role_policy=rsm.cflt_s3_provider_integration.aws.apply(
            lambda args: json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"AWS": f"{args.iam_role_arn}"},
                            "Action": "sts:AssumeRole",
                            "Condition": {
                                "StringEquals": {
                                    "sts:ExternalId": f"{args.external_id}",
                                }
                            },
                        },
                        {
                            "Effect": "Allow",
                            "Principal": {"AWS": f"{args.iam_role_arn}"},
                            "Action": "sts:TagSession",
                        },
                    ],
                }
            )
            if args is not None
            else ""
        ),
        tags={
            **(rsm.default_tags),
            "purpose": "IAM role for Confluent Cloud Tableflow",
        },
    )
    pulumi.export(rsm.tableflow_access_role_name, tableflow_assume_role.arn)
    rsm.aws_tableflow_access_role = tableflow_assume_role

    _ = aws.iam.RolePolicyAttachment(
        f"{rsm.tableflow_access_role_name}-policy-attach",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        role=tableflow_assume_role.name,
        policy_arn=rsm.aws_tableflow_access_policy.arn,
    )


def update_dbx_access_role(rsm: resources.ResourcesManager):
    """Update the AWS Databricks Access Role with the latest IAM policy."""

    assert rsm.aws_tableflow_access_policy, "AWS Tableflow IAM Policy is not defined"
    assert rsm.dbx_storage_credentials, "Databricks Storage Credentials is not defined"
    assert rsm.dbx_storage_credentials_external_id, (
        "External ID for Databricks is not defined in pulumi config!"
    )

    aws_caller_id = aws.get_caller_identity()

    dbx_assume_role = aws.iam.Role(
        rsm.dbx_access_role_name,
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        # apply on multiple including id
        name=rsm.dbx_access_role_name,
        # Unfotunately the below does not seem to be possible unless using an admin account setup instead of workspace
        # see https://community.databricks.com/t5/get-started-discussions/terraform-databricks-storage-credential-has-wrong-external-id/td-p/54153
        # assume_role_policy=rsm.dbx_storage_credentials.storage_credential_id.apply(
        #     lambda externalId: json.dumps(
        #         {
        #             "Version": "2012-10-17",
        #             "Statement": [
        #                 {
        #                     "Effect": "Allow",
        #                     "Principal": {
        #                         "AWS": [
        #                             f"arn:aws:iam::{aws_caller_id.account_id}:role/{rsm.dbx_access_role_name}",
        #                             "arn:aws:iam::414351767826:role/unity-catalog-prod-UCMasterRole-14S5ZJVKOTYTL",
        #                         ],
        #                     },
        #                     "Action": "sts:AssumeRole",
        #                     "Condition": {
        #                         "StringEquals": {
        #                             "sts:ExternalId": externalId,
        #                         }
        #                     },
        #                 },
        #                 {
        #                     "Sid": "ExplicitSelfRoleAssumption",
        #                     "Effect": "Allow",
        #                     "Principal": {
        #                         "AWS": f"arn:aws:iam::{aws_caller_id.account_id}:root"
        #                     },
        #                     "Action": "sts:AssumeRole",
        #                     "Condition": {
        #                         "ArnEquals": {
        #                             "aws:PrincipalArn": f"arn:aws:iam::{aws_caller_id.account_id}:role/{rsm.dbx_access_role_name}"
        #                         }
        #                     },
        #                 },
        #             ],
        #         }
        #     ),
        # ),
        assume_role_policy=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "AWS": [
                                "arn:aws:iam::414351767826:role/unity-catalog-prod-UCMasterRole-14S5ZJVKOTYTL",
                                f"arn:aws:iam::{aws_caller_id.account_id}:role/{rsm.dbx_access_role_name}",
                            ],
                        },
                        "Action": "sts:AssumeRole",
                        "Condition": {
                            "StringEquals": {
                                "sts:ExternalId": rsm.dbx_storage_credentials_external_id,
                            }
                        },
                    },
                ],
            }
        ),
        tags={
            **(rsm.default_tags),
            "purpose": "IAM role for DBX Unity Catalog to access S3 storage",
        },
    )
    pulumi.export(rsm.dbx_access_role_name, dbx_assume_role.arn)
    rsm.aws_databricks_access_role = dbx_assume_role

    _ = aws.iam.RolePolicyAttachment(
        f"{rsm.dbx_access_role_name}-policy-attach",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        role=dbx_assume_role.name,
        policy_arn=rsm.aws_tableflow_access_policy.arn,
    )


# Create RDS Oracle 19 EE non-CDB instance with TDE encryption
def create_rds_oracle(rsm: resources.ResourcesManager):
    """Create an RDS Oracle instance with TDE encryption enabled."""

    assert rsm.aws_kms_key, "AWS KMS key is not defined"
    assert rsm.aws_security_group, "AWS security group is not defined"
    assert rsm.aws_subnet_group, "AWS subnet group is not defined"

    rds_parameter_group = aws.rds.ParameterGroup(
        f"{rsm.resource_prefix}-rds-parameter-group",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        family="oracle-ee-19",  # Parameter group family for Oracle 19c
        parameters=[
            aws.rds.ParameterGroupParameterArgs(
                name="enable_goldengate_replication",
                value="TRUE",  # Enable GoldenGate replication
            )
        ],
        tags={
            **(rsm.default_tags),
        },
    )

    rds_option_group = aws.rds.OptionGroup(
        f"{rsm.resource_prefix}-rds-option-group",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        engine_name="oracle-ee",  # Oracle Enterprise Edition
        major_engine_version="19",  # Major version for Oracle 19c
        options=[
            aws.rds.OptionGroupOptionArgs(
                option_name="TDE",
            ),
        ],
        tags={
            **(rsm.default_tags),
        },
    )

    # Create an RDS Oracle instance with TDE enabled
    rds_oracle_instance = aws.rds.Instance(
        f"{rsm.resource_prefix}-rds-oracle-tde",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        # Basic configuration
        instance_class=rsm.rds_instance_class,
        engine="oracle-ee",  # Oracle Enterprise Edition
        engine_version="19.0.0.0.ru-2025-07.rur-2025-07.r1",  # Latest Oracle 19c version
        license_model="bring-your-own-license",  # BYOL for Oracle
        # Database configuration
        db_name=rsm.rds_db_name,  # Default Oracle database name
        username=rsm.rds_db_username,  # Master username
        # password="",  # Removed - using managed master password
        manage_master_user_password=True,  # Enable managed master password via Secrets Manager
        master_user_secret_kms_key_id=rsm.aws_kms_key.id,  # Use our KMS key for the secret
        port=1521,  # Default Oracle port
        # Storage configuration
        allocated_storage=rsm.rds_allocated_storage,  # 200 GB initial storage
        storage_type="gp3",  # General Purpose SSD
        storage_encrypted=True,  # Enable storage encryption
        kms_key_id=rsm.aws_kms_key.arn,  # Use our KMS key for encryption
        apply_immediately=True,  # Apply changes immediately
        # Network configuration
        db_subnet_group_name=rsm.aws_subnet_group.name,
        vpc_security_group_ids=[rsm.aws_security_group.id],
        # Backup configuration
        backup_retention_period=1,  # Enable backup retention for archive log redo
        backup_window="03:00-04:00",  # Backup window (not used when disabled)
        # Maintenance configuration
        maintenance_window="sun:04:00-sun:05:00",  # Maintenance window
        # Additional options
        multi_az=False,  # Single AZ for cost optimization
        publicly_accessible=True,  # Allow public access from whitelisted IPs
        # Tags
        tags={
            **(rsm.default_tags),
            "purpose": "CDC demo with TDE Encryption",
        },
        # Options for Oracle
        option_group_name=rds_option_group.name,  # Use TDE option group
        parameter_group_name=rds_parameter_group.name,  # Use custom parameter group
        skip_final_snapshot=True,  # skip final snapshot on deletion (for demo purposes only)
    )
    pulumi.export("aws_rds_instance_endpoint", rds_oracle_instance.endpoint)
    rsm.aws_rds_instance = rds_oracle_instance
