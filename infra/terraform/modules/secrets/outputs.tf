output "secret_arn" {
  description = "ARN of the JSON secret holding SESSION_SECRET and INVITE_TOKEN_PEPPER."
  value       = aws_secretsmanager_secret.app.arn
}

output "judge_secret_arn" {
  description = "ARN of the JSON secret holding JUDGE_TOKEN."
  value       = aws_secretsmanager_secret.judge.arn
}

output "connections_secret_arn" {
  description = "ARN of the JSON secret holding DATABASE_URL and REDIS_URL (null without include_connection_urls)."
  value       = var.include_connection_urls ? aws_secretsmanager_secret.connections[0].arn : null
}

output "keys" {
  description = "Every environment variable the secrets provide."
  value       = sort(concat(local.app_keys, ["JUDGE_TOKEN"], local.connection_keys))
}

output "ecs_secrets" {
  description = "ECS `secrets` entries for the control plane (api, worker, migrate): [{ name, valueFrom = \"<arn>:<key>::\" }]."
  value       = local.ecs_secrets
}

output "judge_secrets" {
  description = "ECS `secrets` entries for the judge workers (JUDGE_TOKEN, REDIS_URL)."
  value       = local.judge_secrets
}
