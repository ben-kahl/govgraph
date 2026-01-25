# 1. Check that the module doesn't crash
run "setup_tests" {
  command = plan

  assert {
    condition = module.vpc.natgw_ids != null
    error_message = "NAT Gateway must be enabled"
  }
}

# 2. Assert single NAT Gateway
run "verify_single_nat" {
  command = plan

  assert {
    condition = var.single_nat_gateway == true
    error_message = "single_nat_gateway must be enabled for cost saving"
  }
}

# 3. Verify tags for EKS public subnet
run "verify_eks_public_tags" {
  command = plan

  assert {
    condition = lookup(module.vpc.public_subnet_tags, "kubernetes.io/role/elb", "") == "1"
    error_message = "Public subnets are missing 'elb' tag for EKS load balancers"
  }
}

# 4. Verify tags for EKS private subnet
run "verify_eks_private_tags" {
  command = plan

  assert {
    condition = lookup(module.vpc.private_subnet_tags, "kubernetes.io/role/internal-elb", "") == "1"
    error_message = "Private subnets are missing 'internal-elb' tag for private load balancers"
  }
}
