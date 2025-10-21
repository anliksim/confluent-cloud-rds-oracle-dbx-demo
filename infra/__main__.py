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

    topicNames = [
        "rds1.ADMIN.PHARMA_DOSE_REGIMENS",
        "rds1.ADMIN.PHARMA_EVENT",
        "rds1.ADMIN.PHARMA_NOTES_ATTACH",
    ]

    run_stage_2 = False
    if (
        run_stage_2
        and rsm.tableflow_access_role_exists()
        and rsm.databricks_access_role_exists()
    ):
        cflt.create_environment(rsm)
        cflt.create_standard_cluster(rsm)
        for topicName in topicNames:
            cflt.create_compacted_topic(rsm, topicName)
        cflt.create_service_account(rsm)
        cflt.create_xstream_connector(rsm)
        cflt.create_provider_integration(rsm)
        for topicName in topicNames:
            cflt.create_tableflow_topic(rsm, topicName)
        dbx.create_catalog(rsm)
        dbx.create_service_principal(rsm)
        dbx.create_external_storage(rsm)
        cflt.create_unity_integration(rsm)


__main__ = main()
