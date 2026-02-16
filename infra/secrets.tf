resource "aws_secretsmanager_secret" "neo4j_credentials" {
  name        = "gov-graph/neo4j-credentials"
  description = "Credentials for Neo4j AuraDB (Manually populated)"

  # Recovery window in days (0 forces immediate deletion for dev environments)
  recovery_window_in_days = 0

  tags = {
    Terraform   = "true"
    Environment = "dev"
  }
}

resource "aws_secretsmanager_secret" "sam_api_key" {
  name        = "gov-graph/sam-api-key"
  description = "SAM.gov API Key (Manually populated)"
  recovery_window_in_days = 0

  tags = {
    Terraform   = "true"
    Environment = "dev"
  }
}
