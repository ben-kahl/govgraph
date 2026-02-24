resource "aws_cognito_user_pool" "main" {
  name = "gov-graph-users"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 7
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  tags = {
    Terraform   = "true"
    Environment = "dev"
  }
}

resource "aws_cognito_user_pool_client" "frontend" {
  name         = "gov-graph-frontend"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  allowed_oauth_flows_user_pool_client = true
  supported_identity_providers         = ["COGNITO"]

  # Update callback_urls for production
  callback_urls = ["http://localhost:3000"]
  logout_urls   = ["http://localhost:3000"]

  access_token_validity  = 60    # minutes
  refresh_token_validity = 30    # days
  token_validity_units {
    access_token  = "minutes"
    refresh_token = "days"
  }
}
