# `ecr` module

One ECR repository per image: `api` (also the background worker, migrate and seed-demo), `judge` (nsjail and the toolchains) and `web`. Immutable tags, scan on push, KMS encryption, untagged layers expire after 7 days.

## Inputs

| Name | Description | Type | Default |
|---|---|---|---|
| `name_prefix` | Repositories are named <name_prefix>/<image>. | `string` | required |
| `repositories` | Images to create repositories for. api also runs the worker, migrate and seed-demo; judge runs submissions in its sandbox. | `list(string)` | `["api", "judge", "web"]` |
| `kms_key_arn` | CMK for repository encryption. Null uses AES256. | `string` | `null` |
| `keep_images` | Tagged images kept per repository. | `number` | `30` |
| `force_delete` | Allow destroying a repository that still holds images. | `bool` | `false` |

## Outputs

| Name | Description |
|---|---|
| `repository_urls` | Map of image name to repository URL. |
| `repository_arns` | Map of image name to repository ARN. |
