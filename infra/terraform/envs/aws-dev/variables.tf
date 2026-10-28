variable "region" {
  description = "AWS region."
  type        = string
}

variable "environment" {
  description = "Environment tag."
  type        = string
  default     = "dev"
}

variable "extra_tags" {
  description = "Tags added to every resource."
  type        = map(string)
  default     = {}
}

variable "name_prefix" {
  description = "Prefix for every resource name (at most 24 characters); the objects bucket name derives from it, so make it globally unique (e.g. \"acme-codejudge-dev\")."
  type        = string
}

variable "hostname" {
  description = "Public host name of the app and API, e.g. judge-dev.example.com."
  type        = string
}

variable "certificate_arn" {
  description = "ACM certificate in the same region covering hostname."
  type        = string
}

variable "route53_zone_id" {
  description = "Hosted zone for the alias record and the DKIM records. Null: create them yourself (load_balancer_dns_name and dkim_records outputs)."
  type        = string
  default     = null
}

variable "mail_domain" {
  description = "Domain invitation mail is sent from (an SES domain identity), e.g. judge-dev.example.com."
  type        = string
}

variable "mail_from_address" {
  description = "From address of invitation mail, on mail_domain, e.g. no-reply@judge-dev.example.com."
  type        = string
}

variable "image_tag" {
  description = "Image tag to deploy (the git commit or a release)."
  type        = string
}

variable "alarm_email" {
  description = "Alarm notification address."
  type        = string
  default     = null
}

variable "api_extra_environment" {
  description = "Extra api/worker environment (see docs/guides/configuration.md). Never secrets."
  type        = map(string)
  default     = {}
}

variable "judge_extra_environment" {
  description = "Extra judge environment (e.g. WALL_FACTOR, COMPILE_TIME_LIMIT_S). Never secrets."
  type        = map(string)
  default     = {}
}

variable "backup_retention_days" {
  description = "Days a database backup in the objects bucket (backups/) is kept."
  type        = number
  default     = 14
}

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.small"
}

variable "cache_node_type" {
  description = "ElastiCache node type."
  type        = string
  default     = "cache.t4g.micro"
}

variable "judge_instance_type" {
  description = "ARM64 instance type for judge hosts."
  type        = string
  default     = "c7g.large"
}

variable "judge_ami_id" {
  description = "AMI for judge hosts. Null: the latest ECS-optimized Amazon Linux 2023 ARM64 AMI."
  type        = string
  default     = null
}

variable "queue_waiting_threshold" {
  description = "Jobs waiting for a judge, sustained 15 minutes, that raise an alarm."
  type        = number
  default     = 50
}

variable "metrics_allowed_cidrs" {
  description = "Source CIDRs allowed to scrape the api's /metrics through the load balancer."
  type        = list(string)
  default     = []
}

variable "worker_metrics_cidrs" {
  description = "In-VPC Prometheus CIDRs allowed to scrape the worker's /metrics on port 9464. Empty: no worker ingress."
  type        = list(string)
  default     = []
}

variable "ai_egress" {
  description = "Extra api egress for a self-hosted AI hint model not on HTTPS 443, as { cidr, port } pairs."
  type = list(object({
    cidr = string
    port = number
  }))
  default = []
}
