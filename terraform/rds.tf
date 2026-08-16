# Replaces the postgis/postgis:16-3.4 container. RDS Postgres supports the
# postgis extension out of the box (no custom parameter group needed) --
# the Alembic migration (src/wildfirewatch/migrations) runs
# `CREATE EXTENSION IF NOT EXISTS postgis` itself on `alembic upgrade head`,
# same as it does against the local docker-compose postgres.

resource "aws_security_group" "rds" {
  name_prefix = "${var.project}-rds-"
  vpc_id      = aws_vpc.this.id

  ingress {
    description     = "Postgres from the app security group (API pods, wfw ingest/process jobs)"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project}-rds" }
}

resource "aws_security_group" "app" {
  name_prefix = "${var.project}-app-"
  vpc_id      = aws_vpc.this.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project}-app" }
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.project}-db"
  subnet_ids = aws_subnet.private[*].id
  tags       = { Name = "${var.project}-db" }
}

resource "aws_db_instance" "this" {
  identifier     = "${var.project}-db"
  engine         = "postgres"
  engine_version = "16"

  instance_class        = var.db_instance_class
  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  multi_az               = false # set true for production HA

  backup_retention_period   = 7
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.project}-db-final"

  deletion_protection = true
}
