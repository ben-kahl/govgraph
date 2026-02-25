# -----------------------------------------------------------------------------
# VPC
# -----------------------------------------------------------------------------
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 6.6.0"

  name = var.vpc_name
  cidr = var.vpc_cidr

  azs             = var.vpc_azs
  private_subnets = var.vpc_private_subnets
  public_subnets  = var.vpc_public_subnets

  database_subnets             = var.vpc_database_subnets
  create_database_subnet_group = true

  # Cost Optimization: No managed NAT Gateway
  enable_nat_gateway = false
  single_nat_gateway = false

  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Terraform   = "true"
    Environment = "dev"
  }
}

# -----------------------------------------------------------------------------
# Low-Cost NAT (fck-nat)
# -----------------------------------------------------------------------------
module "fck_nat" {
  source  = "RaJiska/fck-nat/aws"
  version = "~> 1.4.0"

  name      = "${var.vpc_name}-fck-nat"
  vpc_id    = module.vpc.vpc_id
  subnet_id = module.vpc.public_subnets[0]

  # Cost optimization: t4g.nano is ~$3/month
  instance_type = "t4g.nano"

  update_route_tables = true
  route_tables_ids    = { for i, id in module.vpc.private_route_table_ids : "private-${i}" => id }
}

# -----------------------------------------------------------------------------
# VPC Endpoints (For AWS Services)
# -----------------------------------------------------------------------------
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = module.vpc.private_route_table_ids

  tags = {
    Name = "s3-endpoint"
  }
}

resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = module.vpc.private_route_table_ids

  tags = {
    Name = "dynamodb-endpoint"
  }
}
