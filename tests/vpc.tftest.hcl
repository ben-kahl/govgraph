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
    condition = length(module.vpc.natgw_ids) == 1
    error_message = "More than 1 NAT Gateway detected. single_nat_gateway must be enabled for cost saving"
  }
}

