# `judge` module

The judge workers: ECS tasks on EC2 capacity in a cluster of their own (an Auto Scaling group behind an ECS capacity provider with managed scaling and draining).

Why EC2: the sandbox needs Docker's default seccomp profile plus only the namespace syscalls nsjail uses to build a per-run sandbox without privileges, and Fargate cannot take a custom seccomp profile. The user data writes `infra/docker/judge-seccomp.json` to `/etc/docker/judge-seccomp.json` and makes it the Docker daemon's default on these hosts, which run nothing but judge tasks.

Defense in depth:

- Task: every capability dropped, `no-new-privileges`, privileged containers disabled on the host, read-only root, tmpfs `/tmp` (exec, for compiled programs) and `/var/cache/codejudge` (noexec), nproc and nofile ulimits, no core dumps, non-root user 10001.
- Network: the task may reach only the api's container port, Redis and the VPC resolver; no internet, no database, no metadata service. The hosts reach only HTTPS (ECS, ECR, logs, Session Manager); no SSH.
- Metadata: IMDSv2 required with a hop limit of 1, and `ECS_AWSVPC_BLOCK_IMDS` so a sandbox escape cannot borrow the instance role.
- IAM: the task role has no policy; the execution role injects only `JUDGE_TOKEN` and `REDIS_URL`.

Scaling: target tracking on judge CPU (a judging worker is CPU bound); the capacity provider adds hosts to fit the tasks. A task stopped mid-job loses nothing: its job is reclaimed after the lease.

## Inputs

| Name | Description | Type | Default |
|---|---|---|---|
| `name_prefix` | Prefix for every resource name. | `string` | required |
| `vpc_id` | VPC the judges run in. | `string` | required |
| `vpc_cidr_block` | VPC CIDR (DNS to the VPC resolver for Cloud Map names). | `string` | required |
| `private_subnet_ids` | Private subnets for the instances and task interfaces (no public IP). | `list(string)` | required |
| `image` | Full judge image reference, e.g. <registry>/codejudge-prod/judge:<tag>. | `string` | required |
| `api_url` | The api as the judges reach it on the private network (service module internal_urls.api). | `string` | required |
| `api_security_group_id` | The api tasks' security group (the judges get ingress on api_port). | `string` | required |
| `api_port` | The api container port. | `number` | `8080` |
| `cache_security_group_id` | The cache security group (the judges read the job stream). | `string` | required |
| `cache_port` | Redis/Valkey port. | `number` | `6379` |
| `secrets` | ECS secrets for the judge (secrets module judge_secrets: JUDGE_TOKEN, REDIS_URL). | `list(object)` | required |
| `environment` | Extra judge environment (see docs/guides/configuration.md). Never secrets. | `map(string)` | `{}` |
| `kms_key_arn` | CMK for the root volumes and for decrypting the injected secrets. | `string` | required |
| `log_group_name` | CloudWatch log group for the judge (observability module log_group_names.judge). | `string` | required |
| `seccomp_profile_json` | The judge seccomp profile (infra/docker/judge-seccomp.json): the Docker daemon default on the judge hosts. | `string` | required |
| `ami_id` | Judge host AMI. Null: the latest ECS-optimized Amazon Linux 2023 ARM64 AMI. | `string` | `null` |
| `instance_type` | ARM64 instance type for judge hosts. Compute optimized (c7g) suits compiling and running programs. | `string` | `"c7g.large"` |
| `root_volume_gib` | Root volume size of a judge host (images and logs; scratch space is tmpfs). | `number` | `30` |
| `min_instances` | Judge hosts kept running. | `number` | `1` |
| `max_instances` | Most judge hosts the capacity provider may run. | `number` | `4` |
| `min_tasks` | Judge workers kept running (each judges one submission at a time). | `number` | `2` |
| `max_tasks` | Most judge workers autoscaling may run. | `number` | `8` |
| `task_cpu` | CPU units per judge task (1024 = one vCPU). | `number` | `1024` |
| `task_memory` | Memory per judge task in MiB: the largest problem memory limit plus compiler and worker headroom. | `number` | `3072` |
| `tmp_mib` | tmpfs size for /tmp (the box and compiled programs) in MiB. | `number` | `1024` |
| `cache_mib` | tmpfs size for the unpacked test package cache in MiB. | `number` | `2048` |
| `max_processes` | nproc ulimit for the judge user (the JVM needs a few dozen threads per run). | `number` | `512` |
| `cpu_target_percent` | Average judge CPU the autoscaler aims for. | `number` | `60` |
| `container_insights` | ECS Container Insights on the judge cluster (enabled, enhanced or disabled). | `string` | `"enabled"` |

## Outputs

| Name | Description |
|---|---|
| `cluster_name` | Judge ECS cluster name. |
| `service_name` | Judge ECS service name. |
| `security_group_id` | Judge task security group. |
| `autoscaling_group_name` | Judge hosts' Auto Scaling group. |
