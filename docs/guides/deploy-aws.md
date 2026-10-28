# Deploy to AWS

The Terraform in `infra/terraform/` builds a production deployment. The maintainers develop
against the local emulator: the AWS environments pass `terraform validate`, tflint and
checkov, and the full `aws-dev` environment is planned, applied, re-planned and destroyed
against Floci in the gates (`make tf-aws-on-floci`). Applying it to a real account is your
step; read the plan before you apply.

## What it builds

| Module | Resources |
| --- | --- |
| `network` | VPC, public and private subnets, NAT, VPC endpoints |
| `database` | RDS PostgreSQL 16, encrypted with KMS, in private subnets |
| `cache` | ElastiCache (Redis-compatible) with `noeviction`: it holds the judge queue |
| `storage` | The objects bucket (test packages), SSE-KMS, versioning, public access blocked |
| `kms` | The key that seals secrets and encrypts storage |
| `secrets` | Secrets Manager entries for `SESSION_SECRET`, `INVITE_TOKEN_PEPPER`, `JUDGE_TOKEN` and the database password |
| `ecr` | Repositories for the api, judge and web images |
| `email` | An SES identity for your mail domain and its DKIM records |
| `service` | ECS Fargate services for api, worker and web behind an ALB; the API also on Cloud Map (`api.<prefix>.internal`) for the judges |
| `judge` | An ECS cluster on EC2 (Auto Scaling group, launch template, ECS-optimised AMI) running the judge tasks |
| `observability` | CloudWatch log groups, metric filters and alarms (5xx, API latency, unhealthy services, judge errors and internal errors, the judge queue backing up) to an SNS topic |

### Why the judges are on EC2

The sandbox needs Docker's default seccomp profile plus the namespace calls nsjail uses
([sandbox.md](../architecture/sandbox.md)). Fargate cannot take a custom seccomp profile, so
the judges run on instances of their own whose Docker daemon uses the judge profile as its
default. The task drops every capability, has a read-only root and tmpfs scratch, and no
permissions; the instances require IMDSv2 with a hop limit of 1 and block task access to
instance metadata; the security groups let a judge reach only the API and the cache.

## Steps

```bash
cd infra/terraform/envs/aws-dev
cp terraform.tfvars.example terraform.tfvars     # region, name prefix, host name, ACM certificate, mail domain
cp backend.tf.example backend.tf                 # optional: remote state in S3
cd -
make aws-deploy ENV=aws-dev TAG=0.1.0            # registries, images, apply, migrations, rollout
CODEJUDGE_ADMIN_PASSWORD=... make aws-admin ENV=aws-dev EMAIL=you@example.com
```

Then add the DKIM records from `terraform output dkim_records` to your DNS and point your
host name at the load balancer (`load_balancer_dns_name`). SES starts in its sandbox: ask
AWS to lift it before inviting candidates outside verified addresses.

`aws-prod` is the same with production settings (a multi-AZ database,
deletion protection).

## After deploying

- Sign in as the admin, set the site name, and decide on sign-up and AI hints in
  **Settings**.
- Watch the judge queue alarm while people use it the first time; scale the judge Auto
  Scaling group and service if jobs wait ([operations.md](operations.md)).
- For a judge open to the public internet, add a kernel boundary around the judges (gVisor
  or Kata) or run them on dedicated hosts ([sandbox.md](../architecture/sandbox.md)).
