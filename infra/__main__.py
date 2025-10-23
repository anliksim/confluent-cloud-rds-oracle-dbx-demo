"""Orchestrator: choose which cloud provider modules to run based on Pulumi config.
This script keeps imports lazy so unused providers don't need to be installed when not used.
"""

import resources_manager as resources
import resources_aws as aws
import resources_confluent as cflt
import resources_databricks as dbx


def main():
    rsm = resources.ResourcesManager()
    aws.create_networking(rsm)
    aws.create_kms_key(rsm)
    aws.create_rds_oracle(rsm)
    aws.create_s3_bucket(rsm)
    aws.create_tableflow_access_policy(rsm)

    topicNames = [
        "rds1.ADMIN.PHARMA_DOSE_REGIMENS",
        "rds1.ADMIN.PHARMA_EVENT",
        "rds1.ADMIN.PHARMA_NOTES_ATTACH",
    ]

    run_stage_2 = True
    if (
        run_stage_2
        and rsm.tableflow_access_role_exists()
        and rsm.databricks_access_role_exists()
    ):
        dbx.create_service_principal(rsm)
        dbx.create_storage_credentials(rsm)
        aws.update_dbx_access_role(rsm)

        cflt.create_environment(rsm)
        cflt.create_standard_cluster(rsm)
        cflt.create_service_account(rsm)
        cflt.create_provider_integration(rsm)
        aws.update_tableflow_access_role(rsm)

        for topicName in topicNames:
            cflt.create_tableflow_topic(rsm, topicName)

        cflt.create_xstream_connector(rsm)

        dbx.create_catalog(rsm)
        dbx.create_external_storage(rsm)
        cflt.create_unity_integration(rsm)
    else:
        # we create those deny all roles on the first run so that we can reference them later
        # this is a chicken and egg problem with these roles as both Confluent and Databricks
        # need the reference to bind the resources on their end before being able to provide
        # the external id for the final role setup (done in stage 2)
        rsm.aws_tableflow_access_role = aws.create_deny_all_assume_role(
            rsm,
            rsm.tableflow_access_role_name,
            "Role for Confluent Tableflow to access S3 bucket",
        )
        rsm.aws_databricks_access_role = aws.create_deny_all_assume_role(
            rsm,
            rsm.dbx_access_role_name,
            "Role for Databricks to access S3 bucket",
        )


__main__ = main()
