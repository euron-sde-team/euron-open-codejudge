# The judge workers: ECS tasks on EC2 capacity of their own, in a cluster of their own.
#
#   Redis (job stream) ──► judge task ──► api (/internal/judge/*: test packages, results)
#                             │
#                             └── nsjail: one sandbox per run (namespaces, rlimits, seccomp)
#
# Why EC2 and not Fargate: the sandbox needs Docker's default seccomp profile plus the
# namespace syscalls nsjail uses to build a per-run sandbox without any privilege, and
# Fargate cannot take a custom seccomp profile. These instances run only judge tasks, so
# the profile is the Docker daemon's default here (written by the user data), and nothing
# else on the cluster gets it.
#
# Defense in depth around code that is hostile by assumption:
#
#   - the task: every Linux capability dropped, no-new-privileges, read-only root, tmpfs
#     scratch (/tmp with exec for compiled programs, /var/cache/codejudge for test
#     packages), memory and process limits, non-root user (the image's 10001)
#   - inside it, nsjail gives each run fresh user, PID, network, mount, IPC and UTS
#     namespaces with no network interface (docs/architecture/sandbox.md)
#   - the network: the task may reach the api's container port and Redis, nothing else
#     (no internet, no database, no metadata service); the instance itself reaches only
#     HTTPS for ECS, ECR, CloudWatch Logs and Session Manager
#   - instance metadata: IMDSv2 only with a hop limit of 1, and the ECS agent blocks task
#     access to it (ECS_AWSVPC_BLOCK_IMDS), so a sandbox escape cannot borrow the
#     instance role
#   - IAM: the task role has no policy at all; the execution role injects only JUDGE_TOKEN
#     and REDIS_URL. A compromised judge holds no database, storage or session secret.
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

data "aws_ssm_parameter" "ami" {
  count = var.ami_id == null ? 1 : 0
  name  = "/aws/service/ecs/optimized-ami/amazon-linux-2023/arm64/recommended/image_id"
}

locals {
  region  = data.aws_region.current.region
  ami_id  = coalesce(var.ami_id, try(data.aws_ssm_parameter.ami[0].value, null))
  cluster = "${var.name_prefix}-judge"
}

resource "aws_ecs_cluster" "this" {
  name = local.cluster
  setting {
    name  = "containerInsights"
    value = var.container_insights
  }
}

# ─── Security groups ─────────────────────────────────────────────────────────

# The judge tasks (awsvpc: each task has its own network interface and this group).
resource "aws_security_group" "task" {
  name        = "${var.name_prefix}-judge-task"
  description = "Judge tasks: egress only to the api and Redis, no ingress"
  vpc_id      = var.vpc_id
  tags        = { Name = "${var.name_prefix}-judge-task" }
}

resource "aws_vpc_security_group_egress_rule" "to_api" {
  security_group_id            = aws_security_group.task.id
  description                  = "To the api (internal judge endpoints)"
  referenced_security_group_id = var.api_security_group_id
  ip_protocol                  = "tcp"
  from_port                    = var.api_port
  to_port                      = var.api_port
}

resource "aws_vpc_security_group_ingress_rule" "api_from_judge" {
  security_group_id            = var.api_security_group_id
  description                  = "From judge tasks"
  referenced_security_group_id = aws_security_group.task.id
  ip_protocol                  = "tcp"
  from_port                    = var.api_port
  to_port                      = var.api_port
}

resource "aws_vpc_security_group_egress_rule" "to_cache" {
  security_group_id            = aws_security_group.task.id
  description                  = "To Redis/Valkey (the job stream)"
  referenced_security_group_id = var.cache_security_group_id
  ip_protocol                  = "tcp"
  from_port                    = var.cache_port
  to_port                      = var.cache_port
}

resource "aws_vpc_security_group_ingress_rule" "cache_from_judge" {
  security_group_id            = var.cache_security_group_id
  description                  = "From judge tasks"
  referenced_security_group_id = aws_security_group.task.id
  ip_protocol                  = "tcp"
  from_port                    = var.cache_port
  to_port                      = var.cache_port
}

# Cloud Map names (api.<name_prefix>.internal) resolve through the VPC resolver.
resource "aws_vpc_security_group_egress_rule" "dns" {
  for_each          = toset(["udp", "tcp"])
  security_group_id = aws_security_group.task.id
  description       = "DNS to the VPC resolver (${each.key})"
  cidr_ipv4         = var.vpc_cidr_block
  ip_protocol       = each.key
  from_port         = 53
  to_port           = 53
}

# The instances: the ECS agent, image pulls, logs and Session Manager, over HTTPS only.
resource "aws_security_group" "instance" {
  name        = "${var.name_prefix}-judge-instance"
  description = "Judge EC2 hosts: HTTPS egress for ECS, ECR, logs and Session Manager; no ingress"
  vpc_id      = var.vpc_id
  tags        = { Name = "${var.name_prefix}-judge-instance" }
}

resource "aws_vpc_security_group_egress_rule" "instance_https" {
  security_group_id = aws_security_group.instance.id
  description       = "HTTPS to ECS, ECR, CloudWatch Logs, Secrets Manager and Session Manager"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

# ─── IAM ─────────────────────────────────────────────────────────────────────

data "aws_iam_policy_document" "assume_ec2" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "instance" {
  name               = "${var.name_prefix}-judge-instance"
  assume_role_policy = data.aws_iam_policy_document.assume_ec2.json
}

resource "aws_iam_role_policy_attachment" "instance" {
  for_each = toset([
    "service-role/AmazonEC2ContainerServiceforEC2Role",
    "AmazonSSMManagedInstanceCore",
  ])
  role       = aws_iam_role.instance.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/${each.key}"
}

resource "aws_iam_instance_profile" "this" {
  name = "${var.name_prefix}-judge"
  role = aws_iam_role.instance.name
}

data "aws_iam_policy_document" "assume_task" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

# Execution role: pull the image, write logs, inject JUDGE_TOKEN and REDIS_URL. Nothing else.
resource "aws_iam_role" "execution" {
  name               = "${var.name_prefix}-judge-execution"
  assume_role_policy = data.aws_iam_policy_document.assume_task.json
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "execution" {
  statement {
    sid       = "InjectJudgeSecrets"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = distinct([for s in var.secrets : regex("^(arn:[^:]+:secretsmanager:[^:]+:[^:]+:secret:[^:]+)", s.valueFrom)[0]])
  }
  statement {
    sid       = "DecryptJudgeSecrets"
    actions   = ["kms:Decrypt"]
    resources = [var.kms_key_arn]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["secretsmanager.${local.region}.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "execution" {
  name   = "judge-secrets"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution.json
}

# Task role: no policy. The judge calls no AWS API.
resource "aws_iam_role" "task" {
  name               = "${var.name_prefix}-judge-task"
  assume_role_policy = data.aws_iam_policy_document.assume_task.json
}

# ─── Capacity: launch template, Auto Scaling group, capacity provider ────────

resource "aws_launch_template" "this" {
  name_prefix            = "${var.name_prefix}-judge-"
  image_id               = local.ami_id
  instance_type          = var.instance_type
  vpc_security_group_ids = [aws_security_group.instance.id]
  ebs_optimized          = true

  iam_instance_profile {
    arn = aws_iam_instance_profile.this.arn
  }

  metadata_options {
    http_tokens                 = "required"
    http_endpoint               = "enabled"
    http_put_response_hop_limit = 1
  }

  monitoring {
    enabled = true
  }

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      encrypted             = true
      kms_key_id            = var.kms_key_arn
      volume_type           = "gp3"
      volume_size           = var.root_volume_gib
      delete_on_termination = true
    }
  }

  # Gzipped (cloud-init unpacks it): the seccomp profile alone is about 9 KB compact, and
  # user data is capped at 16 KB.
  user_data = base64gzip(templatefile("${path.module}/user_data.sh.tftpl", {
    cluster         = local.cluster
    seccomp_profile = jsonencode(jsondecode(var.seccomp_profile_json))
  }))

  tag_specifications {
    resource_type = "instance"
    tags          = { Name = "${var.name_prefix}-judge" }
  }
}

resource "aws_autoscaling_group" "this" {
  name_prefix           = "${var.name_prefix}-judge-"
  vpc_zone_identifier   = var.private_subnet_ids
  min_size              = var.min_instances
  max_size              = var.max_instances
  desired_capacity      = var.min_instances
  protect_from_scale_in = true
  health_check_type     = "EC2"

  launch_template {
    id      = aws_launch_template.this.id
    version = aws_launch_template.this.latest_version
  }

  # A new launch template (a new AMI, a new profile) rolls the fleet gradually.
  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 50
    }
  }

  tag {
    key                 = "AmazonECSManaged"
    value               = "true"
    propagate_at_launch = true
  }

  # The capacity provider owns the instance count after creation.
  lifecycle {
    ignore_changes = [desired_capacity]
  }
}

resource "aws_ecs_capacity_provider" "this" {
  name = "${var.name_prefix}-judge"
  auto_scaling_group_provider {
    auto_scaling_group_arn         = aws_autoscaling_group.this.arn
    managed_termination_protection = "ENABLED"
    managed_draining               = "ENABLED"
    managed_scaling {
      status                    = "ENABLED"
      target_capacity           = 100
      minimum_scaling_step_size = 1
      maximum_scaling_step_size = 2
    }
  }
}

resource "aws_ecs_cluster_capacity_providers" "this" {
  cluster_name       = aws_ecs_cluster.this.name
  capacity_providers = [aws_ecs_capacity_provider.this.name]
  default_capacity_provider_strategy {
    capacity_provider = aws_ecs_capacity_provider.this.name
    weight            = 1
  }
}

# ─── Task definition and service ─────────────────────────────────────────────

resource "aws_ecs_task_definition" "this" {
  family                   = "${var.name_prefix}-judge"
  requires_compatibilities = ["EC2"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([{
    name                   = "judge"
    image                  = var.image
    essential              = true
    command                = ["judge"]
    user                   = "10001:10001"
    readonlyRootFilesystem = true
    privileged             = false
    dockerSecurityOptions  = ["no-new-privileges"]
    environment = [for n, v in merge({
      API_INTERNAL_URL = var.api_url
      WORK_DIR         = "/tmp/judge"
      CACHE_DIR        = "/var/cache/codejudge"
      # tmpfs counts against task_memory: keep the cache well inside its tmpfs, and
      # task_memory >= cache + tmp + the largest problem memory limit + the worker.
      CACHE_MAX_BYTES = tostring(floor(var.cache_mib * 1048576 * 0.8))
      LOG_LEVEL       = "INFO"
    }, var.environment) : { name = n, value = v }]
    secrets = var.secrets
    linuxParameters = {
      initProcessEnabled = true
      capabilities       = { drop = ["ALL"] }
      tmpfs = [
        # Compiled programs run from here, so it allows exec; private to this task.
        { containerPath = "/tmp", size = var.tmp_mib, mountOptions = ["exec", "nosuid", "nodev", "mode=1777"] },
        { containerPath = "/var/cache/codejudge", size = var.cache_mib, mountOptions = ["noexec", "nosuid", "nodev", "mode=1777"] },
      ]
    }
    ulimits = [
      { name = "nproc", softLimit = var.max_processes, hardLimit = var.max_processes },
      { name = "nofile", softLimit = 4096, hardLimit = 4096 },
      { name = "core", softLimit = 0, hardLimit = 0 },
    ]
    # SIGTERM finishes the job in hand (results are posted before the job is acknowledged).
    stopTimeout = 120
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = var.log_group_name
        awslogs-region        = local.region
        awslogs-stream-prefix = "judge"
      }
    }
  }])
}

resource "aws_ecs_service" "this" {
  name                   = "judge"
  cluster                = aws_ecs_cluster.this.arn
  task_definition        = aws_ecs_task_definition.this.arn
  desired_count          = var.min_tasks
  enable_execute_command = false
  propagate_tags         = "SERVICE"

  capacity_provider_strategy {
    capacity_provider = aws_ecs_capacity_provider.this.name
    weight            = 1
  }

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.task.id]
    assign_public_ip = false
  }

  ordered_placement_strategy {
    type  = "spread"
    field = "attribute:ecs.availability-zone"
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  # A job in flight is reclaimed by another worker after its lease if a task stops, so a
  # rolling deploy never loses a submission.
  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  lifecycle {
    ignore_changes = [desired_count]
  }
  depends_on = [aws_ecs_cluster_capacity_providers.this]
}

resource "aws_appautoscaling_target" "this" {
  service_namespace  = "ecs"
  scalable_dimension = "ecs:service:DesiredCount"
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.this.name}"
  min_capacity       = var.min_tasks
  max_capacity       = var.max_tasks
}

# A judging worker is CPU bound (compiling and running programs), so CPU says when the
# queue needs more of them; the capacity provider then adds instances to fit the tasks.
resource "aws_appautoscaling_policy" "cpu" {
  name               = "${var.name_prefix}-judge-cpu"
  policy_type        = "TargetTrackingScaling"
  service_namespace  = aws_appautoscaling_target.this.service_namespace
  scalable_dimension = aws_appautoscaling_target.this.scalable_dimension
  resource_id        = aws_appautoscaling_target.this.resource_id
  target_tracking_scaling_policy_configuration {
    target_value       = var.cpu_target_percent
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}
