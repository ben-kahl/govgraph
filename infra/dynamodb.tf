# -----------------------------------------------------------------------------
# DynamoDB (Entity Resolution Cache)
# -----------------------------------------------------------------------------
resource "aws_dynamodb_table" "entity_cache" {
  name         = "gov-graph-entity-cache"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "vendor_name"

  attribute {
    name = "vendor_name"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name        = "Entity Resolution Cache"
    Terraform   = "true"
    Environment = "dev"
  }
}
