# -----------------------------------------------------------------------------
# VPC
# -----------------------------------------------------------------------------
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"

  name = var.vpc_name
  cidr = var.vpc_cidr

  azs             = var.vpc_azs
  private_subnets = var.vpc_private_subnets
  public_subnets  = var.vpc_public_subnets

  database_subnets             = var.vpc_database_subnets
  create_database_subnet_group = true

  enable_nat_gateway = true
  single_nat_gateway = var.enable_single_nat_gateway

  enable_dns_hostnames = true
  enable_dns_support   = true

  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
  }

  tags = {
    Terraform                                 = "true"
    Environment                               = "dev"
    "kubernetes.io/cluster/gov-graph-cluster" = "shared"
  }
}
