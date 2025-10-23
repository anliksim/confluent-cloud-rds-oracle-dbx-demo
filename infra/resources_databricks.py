import pulumi
import pulumi_databricks as databricks
import resources_manager as resources


def create_service_principal(rsm: resources.ResourcesManager):
    dbx_sa = databricks.ServicePrincipal(
        f"{rsm.resource_prefix}-dbx-sa",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        display_name=f"{rsm.resource_prefix} dbx service account for rds cdc demo",
        workspace_access=True,
        databricks_sql_access=True,
    )

    dbx_sa_secret = databricks.ServicePrincipalSecret(
        f"{rsm.resource_prefix}-dbx-sa-secret",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        service_principal_id=dbx_sa.id,
    )
    rsm.dbx_service_principal = dbx_sa
    rsm.dbx_service_principal_secret = dbx_sa_secret


def create_catalog(rsm: resources.ResourcesManager):
    assert rsm.dbx_service_principal, "Databricks Service Principal is not defined"

    dbx_catalog_name = f"{rsm.resource_prefix}-rds-cdc-demo"
    dbx_catalog = databricks.Catalog(
        dbx_catalog_name,
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        name=dbx_catalog_name,
        comment=f"{rsm.resource_prefix} CDC demo",
        properties={
            **(rsm.default_tags),
            "purpose": "RDS Oracle CDC Demo",
        },
    )

    _ = databricks.Grants(
        f"{rsm.resource_prefix}-dbx-catalog-grants",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        catalog=dbx_catalog.name,
        grants=[
            {
                "principal": rsm.dbx_service_principal.application_id,
                "privileges": [
                    "ALL_PRIVILEGES",
                ],
            },
            {
                "principal": "account users",
                "privileges": [
                    "BROWSE",
                    "EXECUTE",
                    "READ_VOLUME",
                    "SELECT",
                    "USE_CATALOG",
                    "USE_SCHEMA",
                ],
            },
        ],
    )

    rsm.dbx_catalog = dbx_catalog


def create_storage_credentials(rsm: resources.ResourcesManager):
    assert rsm.dbx_service_principal, "Databricks Service Principal is not defined"

    dbx_assume_role_arn = rsm.currentStack.get_output(rsm.dbx_access_role_name)
    dbx_storage_creds = databricks.StorageCredential(
        f"{rsm.resource_prefix}-dbx-storage-creds",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        aws_iam_role={
            "role_arn": dbx_assume_role_arn.apply(lambda arn: str(arn)),
        },
        comment=f"{rsm.resource_prefix} CDC demo",
    )

    _ = databricks.Grants(
        f"{rsm.resource_prefix}-dbx-storage-creds-grants",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        credential=dbx_storage_creds.id,
        grants=[
            {
                "principal": rsm.dbx_service_principal.application_id,
                "privileges": [
                    "ALL_PRIVILEGES",
                ],
            }
        ],
    )

    rsm.dbx_storage_credentials = dbx_storage_creds


def create_external_storage(rsm: resources.ResourcesManager):
    assert rsm.dbx_service_principal, "Databricks Service Principal is not defined"
    assert rsm.aws_databricks_access_role, "AWS Databricks Access Role is not defined"
    assert rsm.aws_tableflow_bucket, "AWS Tableflow S3 Bucket is not defined"
    assert rsm.dbx_storage_credentials, "Databricks Storage Credentials is not defined"

    dbx_external_location = databricks.ExternalLocation(
        f"{rsm.resource_prefix}-dbx-external-location",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        url=rsm.aws_tableflow_bucket.bucket.apply(lambda bucket: f"s3://{bucket}/"),
        credential_name=rsm.dbx_storage_credentials.name,
        comment=f"{rsm.resource_prefix} external location for cdc demo",
    )

    _ = databricks.Grants(
        f"{rsm.resource_prefix}-dbx-external-location-grants",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        external_location=dbx_external_location.id,
        grants=[
            {
                "principal": rsm.dbx_service_principal.application_id,
                "privileges": [
                    "ALL_PRIVILEGES",
                    # "CREATE_EXTERNAL_TABLE",
                    # "READ_FILES",
                ],
            }
        ],
    )

    rsm.dbx_external_location = dbx_external_location
