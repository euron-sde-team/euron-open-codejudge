output "cluster_name" {
  description = "Judge ECS cluster name."
  value       = aws_ecs_cluster.this.name
}

output "service_name" {
  description = "Judge ECS service name."
  value       = aws_ecs_service.this.name
}

output "security_group_id" {
  description = "Judge task security group."
  value       = aws_security_group.task.id
}

output "autoscaling_group_name" {
  description = "Judge hosts' Auto Scaling group."
  value       = aws_autoscaling_group.this.name
}
