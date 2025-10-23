import json
import pulumi
import pulumi_confluentcloud as confluentcloud
import pulumi_command as command
import resources_manager as resources


def create_environment(rsm: resources.ResourcesManager):
    """Create a Confluent Cloud Environment for the RDS Oracle instance."""

    environment = confluentcloud.Environment(
        f"{rsm.resource_prefix}-ccloud-env-oracle-cdc-demo",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        stream_governance={
            "package": "ADVANCED",
        },
    )
    rsm.cflt_environment = environment


def create_standard_cluster(rsm: resources.ResourcesManager):
    """Create a Confluent Cloud Standard Cluster for the RDS Oracle instance."""

    assert rsm.cflt_environment, "Confluent Environment not defined"

    kafka_cluster = confluentcloud.KafkaCluster(
        f"{rsm.resource_prefix}-ccloud-cluster-oracle-cdc-demo",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        availability="SINGLE_ZONE",
        cloud="AWS",
        region=rsm.region,
        standard={},
        environment={
            "id": rsm.cflt_environment.id,
        },
    )
    rsm.cflt_kafka_cluster = kafka_cluster


def create_provider_integration(rsm: resources.ResourcesManager):
    assert rsm.cflt_environment, "Confluent Environment not defined"
    assert rsm.cflt_kafka_cluster, "Confluent Kafka Cluster is not defined"

    tableflow_assume_role_arn = rsm.currentStack.get_output(
        rsm.tableflow_access_role_name
    )
    tableflow_s3_provider_integration = confluentcloud.ProviderIntegration(
        f"{rsm.resource_prefix}-tableflow-s3-integration",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        display_name=f"{rsm.resource_prefix}-tableflow-s3-integration",
        aws={
            "customer_role_arn": tableflow_assume_role_arn.apply(lambda arn: str(arn)),
        },
        environment={
            "id": rsm.cflt_environment.id,
        },
    )
    rsm.cflt_s3_provider_integration = tableflow_s3_provider_integration


def create_service_account(rsm: resources.ResourcesManager):
    assert rsm.cflt_environment, "Confluent Environment not defined"
    assert rsm.cflt_kafka_cluster, "Confluent Kafka Cluster not defined"

    xstream_service_account_name = f"{rsm.resource_prefix}-xstream-sa"
    xstream_service_account = confluentcloud.ServiceAccount(
        xstream_service_account_name,
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        display_name=xstream_service_account_name,
        description=f"{rsm.resource_prefix} Service account for connectors",
    )

    # add cluster admin role to service account
    xstream_service_account_env_admin_role = confluentcloud.RoleBinding(
        f"{xstream_service_account_name}-env-admin",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        principal=xstream_service_account.id.apply(lambda id: f"User:{id}"),
        role_name="EnvironmentAdmin",  # EnvironmentAdmin for demo, too permissive for production
        crn_pattern=rsm.cflt_environment.resource_name,
    )

    kafka_api_key = confluentcloud.ApiKey(
        f"{xstream_service_account_name}-kafka-api-key",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        display_name=f"{xstream_service_account_name}-kafka-api-key",
        description=f"Kafka API Key that is owned by '{xstream_service_account_name}' service account",
        owner=confluentcloud.ApiKeyOwnerArgs(
            id=xstream_service_account.id,
            api_version=xstream_service_account.api_version,
            kind=xstream_service_account.kind,
        ),
        managed_resource={
            "id": rsm.cflt_kafka_cluster.id,
            "api_version": rsm.cflt_kafka_cluster.api_version,
            "kind": rsm.cflt_kafka_cluster.kind,
            "environment": {"id": rsm.cflt_environment.id},
        },
    )

    xstream_service_account_tableflow_api_key = confluentcloud.ApiKey(
        f"{xstream_service_account_name}-tableflow-api-key",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        display_name=f"{xstream_service_account_name}-tableflow-api-key",
        description=f"Tableflow API Key that is owned by '{xstream_service_account_name}' service account",
        owner=confluentcloud.ApiKeyOwnerArgs(
            id=xstream_service_account.id,
            api_version=xstream_service_account.api_version,
            kind=xstream_service_account.kind,
        ),
        managed_resource={
            "id": "tableflow",
            "api_version": "tableflow/v1",
            "kind": "Tableflow",
        },
    )

    rsm.cflt_xstream_service_account = xstream_service_account
    rsm.cflt_xstream_service_account_env_admin_role = (
        xstream_service_account_env_admin_role
    )
    rsm.cflt_xstream_service_account_kafka_api_key = kafka_api_key
    rsm.cflt_xstream_service_account_tableflow_api_key = (
        xstream_service_account_tableflow_api_key
    )


def create_tableflow_topic(rsm: resources.ResourcesManager, topic_name: str):
    assert rsm.cflt_environment, "Confluent Environment not defined"
    assert rsm.cflt_kafka_cluster, "Confluent Kafka Cluster not defined"
    assert rsm.cflt_xstream_service_account_kafka_api_key, (
        "Confluent Kafka API Key not defined"
    )
    assert rsm.cflt_xstream_service_account_tableflow_api_key, (
        "Confluent Tableflow API Key not defined"
    )
    assert rsm.aws_tableflow_bucket, "AWS Tableflow Bucket not defined"
    assert rsm.cflt_s3_provider_integration, (
        "Confluent S3 Provider Integration not defined"
    )

    topic = confluentcloud.KafkaTopic(
        f"{rsm.resource_prefix}-{topic_name}-topic",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        topic_name=topic_name,
        partitions_count=1,
        config={
            "cleanup.policy": "compact",
        },
        rest_endpoint=rsm.cflt_kafka_cluster.rest_endpoint,
        kafka_cluster={
            "id": rsm.cflt_kafka_cluster.id,
        },
        credentials={
            "key": rsm.cflt_xstream_service_account_kafka_api_key.id,
            "secret": rsm.cflt_xstream_service_account_kafka_api_key.secret,
        },
    )

    _ = confluentcloud.TableflowTopic(
        f"{rsm.resource_prefix}-{topic_name}-tableflow-topic",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources, depends_on=[topic]),
        display_name=topic_name,
        table_formats=[
            "ICEBERG",
            "DELTA",
        ],
        byob_aws=confluentcloud.TableflowTopicByobAwsArgs(
            bucket_name=rsm.aws_tableflow_bucket.bucket,
            provider_integration_id=rsm.cflt_s3_provider_integration.id,
        ),
        credentials=confluentcloud.TableflowTopicCredentialsArgs(
            key=rsm.cflt_xstream_service_account_tableflow_api_key.id,
            secret=rsm.cflt_xstream_service_account_tableflow_api_key.secret,
        ),
        kafka_cluster={
            "id": rsm.cflt_kafka_cluster.id,
        },
        environment={
            "id": rsm.cflt_environment.id,
        },
    )


def create_xstream_connector(rsm: resources.ResourcesManager):
    """Create a Confluent Cloud XStream Connector to capture changes from the RDS Oracle instance."""

    # assert dependencies
    assert rsm.aws_rds_instance, "AWS RDS instance not defined"
    assert rsm.cflt_environment, "Confluent Environment not defined"
    assert rsm.cflt_kafka_cluster, "Confluent Kafka Cluster not defined"
    assert rsm.cflt_xstream_service_account, (
        "Confluent XStream Service Account not defined"
    )
    assert rsm.cflt_xstream_service_account_env_admin_role, (
        "Confluent XStream Service Account Environment Admin Role not defined"
    )

    xstream_config = {}
    # load defaults
    with open("connect_xstream_default.json", "r") as f:
        # add to it instead of replacing it
        xstream_config = json.load(f)["config"]

    # Set required values
    xstream_config["name"] = f"{rsm.resource_prefix}-oracle-cdc-connector-xout"
    xstream_config["topic.prefix"] = "rds1"

    # Kafka auth
    xstream_config["kafka.auth.mode"] = "SERVICE_ACCOUNT"
    xstream_config["kafka.service.account.id"] = rsm.cflt_xstream_service_account.id

    xstream_config["auto.restart.on.user.error"] = "false"

    # Oracle DB connection
    xstream_config["database.hostname"] = rsm.aws_rds_instance.endpoint.apply(
        lambda endpoint: f"{endpoint.split(':')[0]}"
    )
    # xstream_config["database.port"] = oracle_ssl_port
    xstream_config["database.port"] = 1521
    xstream_config["database.user"] = rsm.rds_cflt_user_name
    xstream_config["database.dbname"] = rsm.rds_db_name
    xstream_config["database.service.name"] = rsm.rds_db_name
    xstream_config["database.out.server.name"] = rsm.rds_xout_server_name
    # xstream_config["database.tls.mode"] = "one-way"
    xstream_config["database.tls.mode"] = "disable"
    xstream_config["database.processor.licenses"] = "1"

    xstream_config["table.include.list"] = "ADMIN.*"

    # SMT extract only the data we need
    xstream_config["transforms"] = "transform_0"
    xstream_config["transforms.transform_0.type"] = (
        "io.debezium.transforms.ExtractNewRecordState"
    )
    xstream_config["transforms.transform_0.delete.handling.mode"] = "rewrite"
    xstream_config["transforms.transform_0.delete.tombstone.handling.mode"] = (
        "tombstone"
    )
    xstream_config["transforms.transform_0.add.fields"] = (
        "op:operation_type,source.ts_us:operation_time,ts_ns:sortable_sequence"
    )
    xstream_config["transforms.transform_0.add.fields.prefix"] = "db_"

    # create datagen connector
    xstream_connector = confluentcloud.Connector(
        f"{rsm.resource_prefix}-ccloud-xstream-connector1",
        opts=pulumi.ResourceOptions(
            protect=rsm.protect_resources,
            depends_on=[rsm.cflt_xstream_service_account_env_admin_role],
        ),
        kafka_cluster={
            "id": rsm.cflt_kafka_cluster.id,
        },
        environment={
            "id": rsm.cflt_environment.id,
        },
        config_sensitive={"database.password": rsm.rds_cflt_user_password},
        config_nonsensitive=xstream_config,
    )

    rsm.cflt_xstream_connector = xstream_connector


def create_unity_integration(rsm: resources.ResourcesManager):
    assert rsm.dbx_catalog, "Databricks Catalog is not defined"
    assert rsm.dbx_service_principal, "Databricks Service Principal is not defined"
    assert rsm.dbx_service_principal_secret, "Databricks Secret is not defined"
    assert rsm.cflt_environment, "Confluent Cloud Environment is not defined"
    assert rsm.cflt_kafka_cluster, "Confluent Kafka Cluster is not defined"
    assert rsm.cflt_xstream_service_account_tableflow_api_key, (
        "Confluent Tableflow API Key is not defined"
    )
    # unity catalog is not yet available via Terraform
    # directly calling the Confluent Cloud API instead

    # cc_unity_catalog_integration = confluentcloud.CatalogIntegration(f"{resource_prefix}-unity-catalog-integration",
    #     opts=pulumi.ResourceOptions(protect=protect_dbx),
    #     display_name=f"{resource_prefix}-unity-catalog-integration",
    # )
    unity_integration = command.local.Command(
        f"{rsm.resource_prefix}-create-unity-integration",
        opts=pulumi.ResourceOptions(protect=rsm.protect_resources),
        create="./scripts/create_unity_integration.sh",
        update="./scripts/update_unity_integration.sh",
        delete="./scripts/delete_unity_integration.sh",
        environment={
            # TODO parse id from output json
            "INTEGRATION_ID": rsm.currentStack.get_output(
                "unity_integration_catalog_id"
            ),
            "KAFKA_ID": rsm.cflt_kafka_cluster.id,
            "ENV_ID": rsm.cflt_environment.id,
            "TABLEFLOW_KEY": rsm.cflt_xstream_service_account_tableflow_api_key.id,
            "TABLEFLOW_SECRET": rsm.cflt_xstream_service_account_tableflow_api_key.secret,
            "DATA": pulumi.Output.all(
                rsm.dbx_catalog.name,
                rsm.dbx_service_principal.application_id,
                rsm.dbx_service_principal_secret.secret,
                rsm.cflt_environment.id,
                rsm.cflt_kafka_cluster.id,
            ).apply(
                lambda args: json.dumps(
                    {
                        "spec": {
                            "display_name": f"{rsm.resource_prefix}-create-unity-integration",
                            "suspended": False,
                            "config": {
                                "kind": "Unity",
                                "workspace_endpoint": rsm.dbx_host,
                                "catalog_name": args[0],
                                "client_id": args[1],
                                "client_secret": args[2],
                            },
                            "environment": {"id": args[3]},
                            "kafka_cluster": {
                                "id": args[4],
                            },
                        }
                    }
                )
            ),
        },
    )
    pulumi.export("unity_integration_id", unity_integration.id)
    pulumi.export("unity_integration_output", unity_integration.stdout)

    # unity_integration_response = unity_integration.stdout.apply(
    #     lambda output: json.loads(output)
    # )

    unity_integration_catalog_id = unity_integration.stdout.apply(
        lambda output: str(json.loads(output)["id"])
        if "id" in json.loads(output)
        else rsm.currentStack.get_output("unity_integration_catalog_id")
    )

    pulumi.export("unity_integration_catalog_id", unity_integration_catalog_id)
