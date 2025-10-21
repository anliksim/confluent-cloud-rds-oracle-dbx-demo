# Create unity catalog integration using the Confluent Cloud API
# Requires a Tableflow scoped API Key
curl --request POST \
  --url https://api.confluent.cloud/tableflow/v1/catalog-integrations \
  --header "Authorization: Basic $(echo -n $TABLEFLOW_KEY:$TABLEFLOW_SECRET | base64 -w 0)" \
  --header 'content-type: application/json' \
  --data "$DATA"
