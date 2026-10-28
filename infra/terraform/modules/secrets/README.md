# `secrets` module

Secrets Manager entries, each injected by ECS only into the containers that need it:

- `<name_prefix>/app`: `SESSION_SECRET`, `INVITE_TOKEN_PEPPER` (api, worker, migrate).
- `<name_prefix>/judge`: `JUDGE_TOKEN`, separate so the judges' execution role reads it without the session keys (the api reads it too, to authenticate them).
- `<name_prefix>/connections` (with `include_connection_urls`): `DATABASE_URL`, `REDIS_URL`. The judges get `REDIS_URL` only, never `DATABASE_URL`.

Values are generated once and rotated out of band; Terraform never rolls them back (`ignore_changes`).

## Inputs

| Name | Description | Type | Default |
|---|---|---|---|
| `name_prefix` | Prefix for every resource name. | `string` | required |
| `kms_key_arn` | CMK that encrypts the secrets. Null uses the AWS-managed key. | `string` | `null` |
| `recovery_window_in_days` | Days a deleted secret stays recoverable. 0 deletes immediately (local and throwaway environments). | `number` | `30` |
| `include_connection_urls` | Create the connections secret from database_url and redis_url. false where Compose supplies them (local-floci). | `bool` | `false` |
| `database_url` | DATABASE_URL (database module connection_url), with include_connection_urls. | `string` | `null` |
| `redis_url` | REDIS_URL (cache module connection_url), with include_connection_urls. | `string` | `null` |

## Outputs

| Name | Description |
|---|---|
| `secret_arn` | ARN of the JSON secret holding SESSION_SECRET and INVITE_TOKEN_PEPPER. |
| `judge_secret_arn` | ARN of the JSON secret holding JUDGE_TOKEN. |
| `connections_secret_arn` | ARN of the JSON secret holding DATABASE_URL and REDIS_URL (null without include_connection_urls). |
| `keys` | Every environment variable the secrets provide. |
| `ecs_secrets` | ECS `secrets` entries for the control plane (api, worker, migrate): [{ name, valueFrom = "<arn>:<key>::" }]. |
| `judge_secrets` | ECS `secrets` entries for the judge workers (JUDGE_TOKEN, REDIS_URL). |
