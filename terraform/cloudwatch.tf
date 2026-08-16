# EKS auto-creates a log group per enabled control-plane log type if none
# exists, but with no retention limit -- declare it so retention is actually
# bounded. App logs (LOG_FORMAT=json stdout from the api/wfw containers)
# need something like Fluent Bit / the CloudWatch Container Insights addon
# shipping them into wfw_app below; that addon isn't set up here.

resource "aws_cloudwatch_log_group" "eks_cluster" {
  name              = "/aws/eks/${var.project}-cluster/cluster"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/${var.project}/app"
  retention_in_days = 30
}

resource "aws_cloudwatch_metric_alarm" "rds_storage_low" {
  alarm_name          = "${var.project}-rds-free-storage-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 2 * 1024 * 1024 * 1024 # 2 GiB
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.this.id
  }
  alarm_description = "RDS free storage below 2 GiB"
}
