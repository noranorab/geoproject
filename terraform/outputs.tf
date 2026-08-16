output "s3_raw_bucket" {
  value = aws_s3_bucket.raw.id
}

output "s3_processed_bucket" {
  value = aws_s3_bucket.processed.id
}

output "ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "rds_endpoint" {
  value = aws_db_instance.this.endpoint
}

output "database_url" {
  description = "Same shape as the DATABASE_URL used locally/in k8s/, minus the password."
  value       = "postgresql+psycopg2://${var.db_username}:<password>@${aws_db_instance.this.address}:5432/${var.db_name}"
}

output "eks_cluster_name" {
  value = aws_eks_cluster.this.name
}

output "eks_cluster_endpoint" {
  value = aws_eks_cluster.this.endpoint
}

output "configure_kubectl" {
  value = "aws eks update-kubeconfig --region ${var.aws_region} --name ${aws_eks_cluster.this.name}"
}
