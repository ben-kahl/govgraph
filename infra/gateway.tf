module "api_gateway" {
  source = "terraform-aws-modules/apigateway-v2/aws"
  version = "~> 6.1.0"

  name = "gov-graph-http"
  description = "GovGraph HTTP API Gateway"
  protocol_type = "HTTP"

  create_domain_name = false
  create_certificate = false

  cors_configuration = {
  allow_headers = ["content-type", "x-amz-date", "authorization", "x-api-key", "x-amz-security-token", "x-amz-user-agent"]
  allow_methods = ["*"]
  allow_origins = ["*"]
  }
}
