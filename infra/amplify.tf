resource "aws_amplify_app" "frontend" {
  name         = "gov-graph-frontend"
  repository   = var.github_repo_url
  access_token = var.github_oauth_token

  build_spec = file("${path.module}/../frontend/amplify.yml")
  platform   = "WEB_COMPUTE"

  environment_variables = {
    NEXT_PUBLIC_API_URL              = module.api_gateway.api_endpoint
    NEXT_PUBLIC_COGNITO_USER_POOL_ID = aws_cognito_user_pool.main.id
    NEXT_PUBLIC_COGNITO_CLIENT_ID    = aws_cognito_user_pool_client.frontend.id
    NEXT_PUBLIC_COGNITO_REGION       = "us-east-1"
    NEXT_PUBLIC_COGNITO_DOMAIN       = "${var.cognito_domain_prefix}.auth.us-east-1.amazoncognito.com"
    NEXT_PUBLIC_APP_URL              = var.app_url
    _LIVE_UPDATES = jsonencode([{
      name    = "Next.js version"
      pkg     = "next-version"
      type    = "internal"
      version = "latest"
    }])
  }
}

resource "aws_amplify_branch" "main" {
  app_id            = aws_amplify_app.frontend.id
  branch_name       = "main"
  stage             = "PRODUCTION"
  enable_auto_build = true
}
