# Deletes unity catalog integration using the Confluent Cloud API
# Requires a Tableflow scoped API Key
curl --request DELETE \
  --url "https://api.confluent.cloud/tableflow/v1/catalog-integrations/$INTEGRATION_ID?environment=$ENV_ID&spec.kafka_cluster=$KAFKA_ID" \
  --header "Authorization: Basic $(echo -n $TABLEFLOW_KEY:$TABLEFLOW_SECRET | base64 -w 0)"
