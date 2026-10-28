output "objects_bucket" {
  description = "OBJECTS_BUCKET for the local stack."
  value       = module.storage.bucket_name
}

output "kms_key_alias" {
  description = "KMS_KEY_ID for the local stack."
  value       = module.kms.alias_name
}

output "app_secret_arn" {
  description = "The emulated Secrets Manager secret (SESSION_SECRET, INVITE_TOKEN_PEPPER)."
  value       = module.secrets.secret_arn
}

output "judge_secret_arn" {
  description = "The emulated Secrets Manager secret holding JUDGE_TOKEN."
  value       = module.secrets.judge_secret_arn
}
