module "api_gateway" {
  source  = "terraform-aws-modules/apigateway-v2/aws"
  version = "~> 6.1.0"

  name          = "gov-graph-http"
  description   = "GovGraph HTTP API Gateway"
  protocol_type = "HTTP"

  create_domain_name = false
  create_certificate = false

  cors_configuration = {
    allow_headers  = ["content-type", "authorization"]
    allow_methods  = ["GET", "POST", "OPTIONS"]
    allow_origins  = ["http://localhost:3000"]
    expose_headers = []
    max_age        = 300
  }

  integrations = {
    "$default" = {
      lambda_arn             = module.api_lambda.lambda_function_arn
      integration_type       = "AWS_PROXY"
      payload_format_version = "2.0"
      timeout_milliseconds   = 30000
    }
  }
}

resource "aws_lambda_permission" "api_gateway_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.api_lambda.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${module.api_gateway.apigatewayv2_api_execution_arn}/*"
}
