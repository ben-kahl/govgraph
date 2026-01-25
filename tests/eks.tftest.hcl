# tests/eks.tftest.hcl

# 1. Budget Guardrail: Ensure we are using SPOT instances
run "verify_budget_constraints" {
  command = plan

  assert {
    condition     = var.node_capacity_type == "SPOT"
    error_message = "Budget warning: You are trying to deploy On-Demand instances! Revert to SPOT."
  }

  assert {
    condition     = var.node_instance_type[0] == "t3.medium"
    error_message = "Budget warning: Instance type is too large. Stick to t3.medium."
  }
}

# 2. Integration: Verify the Cluster Name output matches
run "verify_cluster_identity" {
  command = plan

  assert {
    condition     = module.eks.cluster_name == "gov-graph-cluster"
    error_message = "Cluster name mismatch."
  }
}
