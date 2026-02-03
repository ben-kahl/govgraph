# -----------------------------------------------------------------------------
# RDS (PostgreSQL)
# -----------------------------------------------------------------------------

module "db" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 7.1.0"

  identifier = "gov-graph-postgres-db"

  engine                   = "postgres"
  engine_version           = "17.6"
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

  # Postgres 17 usually doesn't require a custom option group for basic usage
  create_db_option_group = false

  tags = {
    Terraform   = "true"
    Environment = "dev"
  }
}
