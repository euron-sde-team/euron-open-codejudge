# Local stack against real AWS

`make up-aws` runs the same containers as `make up`, but the API and the background worker
use a real KMS key and S3 bucket instead of Floci. Postgres, Redis, Mailpit, the judges and
the web app stay local. Use it to check the AWS code paths with your own account.

```bash
cd infra/terraform/envs/aws-dev && terraform apply -target=module.kms -target=module.storage   # or use your own key and bucket
cd -
cp deploy/compose/.env.aws.example deploy/compose/.env.aws    # fill in OBJECTS_BUCKET and KMS_KEY_ID from terraform output
make up-aws
```

Credentials come from your AWS CLI profile, mounted read-only into the containers that call
AWS (api, worker, migrate); nothing in the repository holds a static key. The judges never
call AWS in any mode.

What changes: test packages are written to and read from S3 (SSE-KMS), and the AI provider
key is sealed with KMS Encrypt. Everything else behaves exactly as in `make up`.
