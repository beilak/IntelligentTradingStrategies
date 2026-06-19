#!/bin/sh
set -eu

OPENSEARCH_URL="${OPENSEARCH_URL:-http://opensearch:9200}"
DASHBOARDS_URL="${OPENSEARCH_DASHBOARDS_URL:-http://opensearch-dashboards:5601}"
LOG_INDEX_PREFIX="${OPENSEARCH_LOG_INDEX_PREFIX:-its-app-logs}"
LOG_INDEX_PATTERN="${OPENSEARCH_LOG_INDEX_PATTERN:-its-app-logs-*}"
LOG_INDEX_PATTERN_ID="${OPENSEARCH_LOG_INDEX_PATTERN_ID:-its-app-logs}"
LOG_TIME_FIELD="${OPENSEARCH_LOG_TIME_FIELD:-@timestamp}"
DASHBOARDS_VERSION="${OPENSEARCH_DASHBOARDS_VERSION:-2.18.0}"

wait_for_http() {
  url="$1"
  name="$2"
  attempts="${3:-90}"
  i=1
  while [ "$i" -le "$attempts" ]; do
    if curl -fsS "$url" >/dev/null; then
      echo "$name is ready"
      return 0
    fi
    echo "waiting for $name ($i/$attempts)"
    i=$((i + 1))
    sleep 2
  done
  echo "$name is not ready: $url" >&2
  return 1
}

put_json_file() {
  url="$1"
  file="$2"
  curl -fsS -X PUT "$url" \
    -H "Content-Type: application/json" \
    --data-binary "@$file" >/dev/null
}

put_json() {
  url="$1"
  payload="$2"
  curl -fsS -X PUT "$url" \
    -H "Content-Type: application/json" \
    -d "$payload" >/dev/null
}

wait_for_http "$OPENSEARCH_URL" "OpenSearch"
wait_for_http "$DASHBOARDS_URL/api/status" "OpenSearch Dashboards"

echo "installing OpenSearch ISM policy"
curl -fsS -X PUT "$OPENSEARCH_URL/_plugins/_ism/policies/technical-logs-retention" \
  -H "Content-Type: application/json" \
  --data-binary "@/bootstrap/ism-policies/technical-logs-retention.json" >/dev/null

echo "installing OpenSearch index template"
put_json_file "$OPENSEARCH_URL/_index_template/its-app-logs" "/bootstrap/index-templates/its-app-logs.json"

today="$(date -u +%Y.%m.%d)"
log_index="$LOG_INDEX_PREFIX-$today"

if ! curl -fsS "$OPENSEARCH_URL/$log_index" >/dev/null 2>&1; then
  echo "creating default log index $log_index"
  put_json "$OPENSEARCH_URL/$log_index" "{}"
else
  echo "default log index $log_index already exists"
fi

echo "creating OpenSearch Dashboards index pattern $LOG_INDEX_PATTERN"
curl -fsS -X POST "$DASHBOARDS_URL/api/saved_objects/index-pattern/$LOG_INDEX_PATTERN_ID?overwrite=true" \
  -H "Content-Type: application/json" \
  -H "osd-xsrf: true" \
  -d "{\"attributes\":{\"title\":\"$LOG_INDEX_PATTERN\",\"timeFieldName\":\"$LOG_TIME_FIELD\"}}" >/dev/null

echo "setting OpenSearch Dashboards default index pattern"
curl -fsS -X POST "$DASHBOARDS_URL/api/saved_objects/config/$DASHBOARDS_VERSION?overwrite=true" \
  -H "Content-Type: application/json" \
  -H "osd-xsrf: true" \
  -d "{\"attributes\":{\"defaultIndex\":\"$LOG_INDEX_PATTERN_ID\"}}" >/dev/null

echo "OpenSearch logging bootstrap completed"
