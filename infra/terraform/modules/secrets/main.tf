# CodeJudge's secrets, in Secrets Manager. ECS injects each JSON key into the containers
# that need it as an environment variable; the values never appear in a task definition,
# a plan diff or a log. Each consumer gets only its own keys (see the outputs).
#
# Three secrets with different lifecycles and readers:
#
#   <name_prefix>/app          SESSION_SECRET, INVITE_TOKEN_PEPPER. Read by the api, the
#                              background worker and the migrate task.
#   <name_prefix>/judge        JUDGE_TOKEN, on its own so the judge workers' execution role
#                              reads it without reading the session keys. The api reads it
#                              too, to authenticate the judges' internal calls.
#   <name_prefix>/connections  DATABASE_URL, REDIS_URL. Derived from the database and
#                              cache modules and kept in step with them on every apply.
#                              The judges get REDIS_URL only (the job stream), never
#                              DATABASE_URL.
#
# Generated once, then rotated out of band; Terraform never rolls them back. The values
# are distinct on purpose (the API refuses to boot in production if any two are equal).
# Locally (Compose) the same values come from deploy/compose/.env; on AWS no master key is
# needed because secrets are sealed with KMS (KEY_MODE=kms).
locals {
  app_keys        = ["INVITE_TOKEN_PEPPER", "SESSION_SECRET"]
  connection_keys = var.include_connection_urls ? ["DATABASE_URL", "REDIS_URL"] : []
}

resource "random_password" "this" {
  for_each = toset(concat(local.app_keys, ["JUDGE_TOKEN"]))
  length   = 64
  special  = false
}

resource "aws_secretsmanager_secret" "app" {
  #checkov:skip=CKV2_AWS_57:These are HMAC keys; rotation is an operator procedure (docs/guides/operations.md), not a Lambda.
  name                    = "${var.name_prefix}/app"
  description             = "CodeJudge signing secrets (sessions, invitation token pepper)"
  kms_key_id              = var.kms_key_arn
  recovery_window_in_days = var.recovery_window_in_days
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id     = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({ for k in local.app_keys : k => random_password.this[k].result })

  # Rotation happens out of band (put a new version by hand or by pipeline). Without
  # this, the next `terraform apply` would quietly roll every secret back.
  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "judge" {
  #checkov:skip=CKV2_AWS_57:A shared bearer token between the api and the judges; rotation is an operator procedure (docs/guides/operations.md).
  name                    = "${var.name_prefix}/judge"
  description             = "CodeJudge judge token (judge workers authenticate to the api's internal endpoints)"
  kms_key_id              = var.kms_key_arn
  recovery_window_in_days = var.recovery_window_in_days
}

resource "aws_secretsmanager_secret_version" "judge" {
  secret_id     = aws_secretsmanager_secret.judge.id
  secret_string = jsonencode({ JUDGE_TOKEN = random_password.this["JUDGE_TOKEN"].result })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "connections" {
  #checkov:skip=CKV2_AWS_57:Derived values; they change when the database or cache module rotates its credential.
  count                   = var.include_connection_urls ? 1 : 0
  name                    = "${var.name_prefix}/connections"
  description             = "CodeJudge connection URLs (PostgreSQL, Redis/Valkey)"
  kms_key_id              = var.kms_key_arn
  recovery_window_in_days = var.recovery_window_in_days
}

resource "aws_secretsmanager_secret_version" "connections" {
  count     = var.include_connection_urls ? 1 : 0
  secret_id = aws_secretsmanager_secret.connections[0].id
  secret_string = jsonencode({
    DATABASE_URL = var.database_url
    REDIS_URL    = var.redis_url
  })
}

locals {
  app_ref   = { for k in local.app_keys : k => "${aws_secretsmanager_secret.app.arn}:${k}::" }
  judge_ref = "${aws_secretsmanager_secret.judge.arn}:JUDGE_TOKEN::"

  # Control plane (api, worker, migrate).
  ecs_secrets = concat(
    [for k in local.app_keys : { name = k, valueFrom = local.app_ref[k] }],
    [{ name = "JUDGE_TOKEN", valueFrom = local.judge_ref }],
    [for k in local.connection_keys : { name = k, valueFrom = "${aws_secretsmanager_secret.connections[0].arn}:${k}::" }],
  )
  # Judge workers: their token and the job stream. No database, no session keys.
  judge_secrets = concat(
    [{ name = "JUDGE_TOKEN", valueFrom = local.judge_ref }],
    var.include_connection_urls ? [{ name = "REDIS_URL", valueFrom = "${aws_secretsmanager_secret.connections[0].arn}:REDIS_URL::" }] : [],
  )
}
