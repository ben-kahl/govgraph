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
}

resource "aws_apigatewayv2_integration" "api_lambda" {
  api_id                 = module.api_gateway.api_id
  integration_type       = "AWS_PROXY"
  integration_uri        = module.api_lambda.lambda_function_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 30000
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = module.api_gateway.api_id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.api_lambda.id}"
}

resource "aws_lambda_permission" "api_gateway_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.api_lambda.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${module.api_gateway.api_execution_arn}/*"
}
