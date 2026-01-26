# dev.tfvars
vpc_name                  = "gov-graph-vpc-dev"
vpc_cidr                  = "10.0.0.0/16"
enable_single_nat_gateway = true
node_instance_type        = ["t3.medium"]
node_capacity_type        = "SPOT"
