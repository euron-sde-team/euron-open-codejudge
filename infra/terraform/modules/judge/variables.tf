variable "name_prefix" {
  description = "Prefix for every resource name."
  type        = string
}

variable "vpc_id" {
  description = "VPC the judges run in."
  type        = string
}

variable "vpc_cidr_block" {
  description = "VPC CIDR (DNS to the VPC resolver for Cloud Map names)."
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnets for the instances and task interfaces (no public IP)."
  type        = list(string)
}

variable "image" {
  description = "Full judge image reference, e.g. <registry>/codejudge-prod/judge:<tag>."
  type        = string
}

variable "api_url" {
  description = "The api as the judges reach it on the private network (service module internal_urls.api)."
  type        = string
}

variable "api_security_group_id" {
  description = "The api tasks' security group (the judges get ingress on api_port)."
  type        = string
}

variable "api_port" {
  description = "The api container port."
  type        = number
  default     = 8080
}

variable "cache_security_group_id" {
  description = "The cache security group (the judges read the job stream)."
  type        = string
}

variable "cache_port" {
  description = "Redis/Valkey port."
  type        = number
  default     = 6379
}

variable "secrets" {
  description = "ECS secrets for the judge (secrets module judge_secrets: JUDGE_TOKEN, REDIS_URL)."
  type = list(object({
    name      = string
    valueFrom = string
  }))
}

variable "environment" {
  description = "Extra judge environment (see docs/guides/configuration.md). Never secrets."
  type        = map(string)
  default     = {}
}

variable "kms_key_arn" {
  description = "CMK for the root volumes and for decrypting the injected secrets."
  type        = string
}

variable "log_group_name" {
  description = "CloudWatch log group for the judge (observability module log_group_names.judge)."
  type        = string
}

variable "seccomp_profile_json" {
  description = "The judge seccomp profile (infra/docker/judge-seccomp.json): the Docker daemon default on the judge hosts."
  type        = string
  validation {
    condition     = can(jsondecode(var.seccomp_profile_json).syscalls)
    error_message = "seccomp_profile_json must be a Docker seccomp profile (JSON with a syscalls list)."
  }
}

variable "ami_id" {
  description = "Judge host AMI. Null: the latest ECS-optimized Amazon Linux 2023 ARM64 AMI."
  type        = string
  default     = null
}

variable "instance_type" {
  description = "ARM64 instance type for judge hosts. Compute optimized (c7g) suits compiling and running programs."
  type        = string
  default     = "c7g.large"
}

variable "root_volume_gib" {
  description = "Root volume size of a judge host (images and logs; scratch space is tmpfs)."
  type        = number
  default     = 30
}

variable "min_instances" {
  description = "Judge hosts kept running."
  type        = number
  default     = 1
}

variable "max_instances" {
  description = "Most judge hosts the capacity provider may run."
  type        = number
  default     = 4
}

variable "min_tasks" {
  description = "Judge workers kept running (each judges one submission at a time)."
  type        = number
  default     = 2
}

variable "max_tasks" {
  description = "Most judge workers autoscaling may run."
  type        = number
  default     = 8
}

variable "task_cpu" {
  description = "CPU units per judge task (1024 = one vCPU)."
  type        = number
  default     = 1024
}

variable "task_memory" {
  description = "Memory per judge task in MiB: the largest problem memory limit plus compiler and worker headroom."
  type        = number
  default     = 3072
}

variable "tmp_mib" {
  description = "tmpfs size for /tmp (the box and compiled programs) in MiB."
  type        = number
  default     = 1024
}

variable "cache_mib" {
  description = "tmpfs size for the unpacked test package cache in MiB."
  type        = number
  default     = 2048
}

variable "max_processes" {
  description = "nproc ulimit for the judge user (the JVM needs a few dozen threads per run)."
  type        = number
  default     = 512
}

variable "cpu_target_percent" {
  description = "Average judge CPU the autoscaler aims for."
  type        = number
  default     = 60
}

variable "container_insights" {
  description = "ECS Container Insights on the judge cluster (enabled, enhanced or disabled)."
  type        = string
  default     = "enabled"
}
