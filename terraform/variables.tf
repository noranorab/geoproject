variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project" {
  type    = string
  default = "wildfirewatch"
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "azs" {
  description = "Two AZs -- enough for RDS Multi-AZ + an EKS node group across failure domains."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "db_name" {
  type    = string
  default = "wildfirewatch"
}

variable "db_username" {
  type    = string
  default = "wfw"
}

variable "db_password" {
  description = "Set via TF_VAR_db_password or a tfvars file that's never committed."
  type        = string
  sensitive   = true
}

variable "eks_cluster_version" {
  type    = string
  default = "1.30"
}

variable "eks_node_instance_type" {
  type    = string
  default = "t3.medium"
}

variable "eks_node_desired_size" {
  type    = number
  default = 2
}
