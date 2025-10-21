import ast
import pulumi
import pulumi_aws as aws
import pulumi_confluentcloud as confluentcloud
import pulumi_databricks as databricks


class ResourcesManager:
    """
    Track resources
    """

    def __init__(self):
        cfg = pulumi.Config()
        self.resource_prefix: str = cfg.get("resourcePrefix") or "demo"
        self.protect_resources: bool = cfg.get_bool("protectResources") or False
        self.default_tags: dict[str, str] = ast.literal_eval(
            cfg.get("defaultTags") or "{}"
        )
        self.tableflow_access_role_name: str = (
            f"{self.resource_prefix}-tableflow-access-role"
        )
        self.region: str = cfg.get("region") or "eu-central-1"
        self.vpc_id: str = cfg.get("vpcId") or ""
        rdsConfig = pulumi.Config("rds")
        self.rds_instance_class: str = rdsConfig.get("instanceClass") or "db.t3.small"
        self.rds_allocated_storage: int = int(rdsConfig.get("allocatedStorage") or "20")
        self.rds_db_name: str = rdsConfig.get("dbName") or ""
        self.rds_db_username: str = rdsConfig.get("dbUsername") or ""
        self.rds_cflt_user_name: str = rdsConfig.get("cfltUserName") or ""
        self.rds_cflt_user_password: str = rdsConfig.get("cfltUserPassword") or ""
        self.rds_xout_server_name: str = rdsConfig.get("xoutServerName") or ""
        # AWS resources
        self.aws_kms_key: aws.kms.Key
        self.aws_rds_instance: aws.rds.Instance
        self.aws_tableflow_bucket: aws.s3.Bucket
        self.aws_tableflow_access_policy: aws.iam.Policy
        self.aws_tableflow_access_role: aws.iam.Role
        self.aws_databricks_access_role: aws.iam.Role
        self.aws_subnet_group: aws.rds.SubnetGroup
        self.aws_security_group: aws.ec2.SecurityGroup
        # CFLT resources
        self.cflt_environment: confluentcloud.Environment
        self.cflt_kafka_cluster: confluentcloud.KafkaCluster
        self.cflt_xstream_service_account: confluentcloud.ServiceAccount
        self.cflt_xstream_service_account_env_admin_role: confluentcloud.RoleBinding
        self.cflt_xstream_service_account_tableflow_api_key: confluentcloud.ApiKey
        self.cflt_xstream_connector: confluentcloud.Connector
        self.cflt_s3_provider_integration: confluentcloud.ProviderIntegration
        # DBX resources
        self.dbx_host: str = cfg.get("dbx:host") or ""
        self.dbx_access_role_name: str = f"{self.resource_prefix}-dbx-access-role"
        self.dbx_catalog: databricks.Catalog
        self.dbx_service_principal: databricks.ServicePrincipal
        self.dbx_service_principal_secret: databricks.ServicePrincipalSecret
        self.dbx_external_location: databricks.ExternalLocation

    def tableflow_access_role_exists(self) -> bool:
        """Check if the Tableflow Assume Role exists."""
        return _aws_role_exists(self.tableflow_access_role_name)

    def databricks_access_role_exists(self) -> bool:
        """Check if the Tableflow Assume Role exists."""
        return _aws_role_exists(self.dbx_access_role_name)


def _aws_role_exists(resource_name: str) -> bool:
    """Check if the role exists."""
    try:
        _ = aws.iam.get_role(name=resource_name)
        return True
    except Exception as _:
        pulumi.log.info(f"AWS Role {resource_name} does not exist yet.")
        return False
