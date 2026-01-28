# -----------------------------------------------------------------------------
# RDS (PostgreSQL)
# -----------------------------------------------------------------------------

module "db" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 7.1.0"

  identifier = "gov-graph-postgres-db"

  engine                   = "postgresql"
  engine_version           = "17.1"
  engine_lifecycle_support = "open-source-rds-extended-support-disabled"
  family                   = "postgres17"
  major_engine_version     = "17"
  instance_class           = var.db_instance_class

  allocated_storage     = 20
  max_allocated_storage = 100

  db_name                     = var.db_name
  username                    = var.db_username
  manage_master_user_password = true
  port                        = 5432

  db_subnet_group_name   = module.vpc.database_subnet_group_name
  vpc_security_group_ids = [module.security_group.security_group_id]

  skip_final_snapshot = true
  publicly_accessible = false

  tags = {
    Terraform   = "true"
    Environment = "dev"
  }
}
/*
resource "aws_security_group" "rds_sg" {
  name        = "gov-graph-rds-sg"
  description = "Allow inbound traffic to RDS"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "PostgreSQL from VPC"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [module.vpc.vpc_cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "gov-graph-rds-sg"
  }
}

resource "aws_db_subnet_group" "default" {
  name       = "gov-graph-db-subnet-group"
  subnet_ids = module.vpc.private_subnets

  tags = {
    Name = "gov-graph-db-subnet-group"
  }
}

resource "aws_db_instance" "default" {
  allocated_storage      = 20
  storage_type           = "gp2"
  engine                 = "postgres"
  engine_version         = "16.1"
  instance_class         = var.db_instance_class
  db_name                = var.db_name
  username               = var.db_username
  password               = var.db_password
  parameter_group_name   = "default.postgres16"
  skip_final_snapshot    = true
  publicly_accessible    = false
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  db_subnet_group_name   = aws_db_subnet_group.default.name
}
*/
