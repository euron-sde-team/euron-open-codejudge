# `observability` module

Logs, alarms and a dashboard:

- A KMS-encrypted log group per app: api, worker, web, migrate, judge.
- Metrics extracted from logs: `JudgeErrors` (error lines from the judges), `JudgeInternalErrors` (submissions ending in IE: the judge failed, not the program) and `JudgeQueueWaiting` (the `waiting` field of the background worker's periodic `judge queue` line).
- Alarms to an SNS topic (optionally e-mailed): 5xx, api p95 latency, unhealthy targets, CPU and memory per service, database CPU, storage and connections, cache memory (with `noeviction` a full cache refuses new submissions) and CPU, judge errors, internal errors, and a judge queue backing up for 15 minutes.

## Inputs

| Name | Description | Type | Default |
|---|---|---|---|
| `name_prefix` | Prefix for every resource name. | `string` | required |
| `log_retention_days` | CloudWatch log retention for the app log groups. | `number` | `30` |
| `logs_kms_key_arn` | CMK for the log groups (its key policy must allow CloudWatch Logs, as the kms module's does). Null uses CloudWatch's default encryption. | `string` | `null` |
| `alarm_email` | Address subscribed to alarm notifications (confirm the e-mail AWS sends). Null: subscribe something else to the topic. | `string` | `null` |
| `alb_arn_suffix` | Load balancer ARN suffix. | `string` | required |
| `ecs_cluster_name` | ECS cluster name. | `string` | required |
| `lb_services` | Load-balanced services (service module `services`): { api = { service_name, target_group_arn_suffix }, web = { ... } }. Must contain api. | `map(object)` | required |
| `ecs_services` | Every ECS service to watch for CPU and memory (service module `service_names`): { api = "api", worker = "worker", web = "web" }. | `map(string)` | required |
| `db_instance_identifier` | RDS instance identifier. | `string` | required |
| `db_max_connections` | Connection ceiling the alarm measures against. | `number` | `200` |
| `cache_replication_group_id` | ElastiCache replication group id; nodes are <id>-001, <id>-002, ... | `string` | required |
| `cache_node_count` | Nodes in the replication group (cache module num_cache_clusters). | `number` | `1` |
| `target_5xx_threshold` | 5xx responses per 5 minutes (per app, and at the load balancer) that raise an alarm. | `number` | `25` |
| `api_p95_latency_seconds` | api p95 time to first byte that raises an alarm. Judging is queued, never on a request path. | `number` | `3` |
| `judge_error_log_pattern` | CloudWatch Logs filter pattern matching a judge worker error line (plain text ERROR or JSON level error). | `string` | `"?ERROR ?error"` |
| `judge_internal_error_log_pattern` | CloudWatch Logs filter pattern matching a judged submission whose verdict is IE (internal error). | `string` | `"\"judged\" \": IE in\""` |
| `queue_log_pattern` | CloudWatch Logs JSON filter matching the background worker's periodic judge queue line (its `waiting` field becomes the metric). | `string` | `"{ $.msg = \"judge queue\" }"` |
| `judge_error_threshold` | Judge error lines per 5 minutes that raise an alarm. | `number` | `5` |
| `queue_waiting_threshold` | Jobs waiting for a judge, sustained for 15 minutes, that raise an alarm. | `number` | `50` |
| `judge_cluster_name` | The judge workers' ECS cluster (judge module cluster_name): CPU and memory alarms for the judge service. | `string` | required |
| `judge_service_name` | The judge ECS service name (judge module service_name). | `string` | required |

## Outputs

| Name | Description |
|---|---|
| `log_group_names` | Log group per app: { api, worker, web, migrate, judge } (service and judge modules). |
| `alarm_topic_arn` | SNS topic receiving every alarm. |
| `dashboard_name` | CloudWatch dashboard. |
| `metrics_namespace` | Namespace of the metrics extracted from the judge and worker logs. |
