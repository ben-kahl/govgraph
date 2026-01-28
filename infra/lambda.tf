# -----------------------------------------------------------------------------
# Lambda (Ingestion & Processing)
# -----------------------------------------------------------------------------

module "lambda_function" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 8.0"

  function_name = "gov-graph-ingestion"
  description   = "Daily ingestion of USAspending data"
  handler       = "ingest_contracts.main" # Assuming main() is the entry point
  runtime       = "python3.9"
  timeout       = 300

  source_path = "${path.module}/../src/ingestion"

  vpc_subnet_ids         = module.vpc.private_subnets
  vpc_security_group_ids = module.security_group.security_group_id
  attach_network_policy  = true

  environment_variables = {
    DB_HOST       = module.db.db_instance_address
    DB_NAME       = var.db_name
    DB_USER       = var.db_username
    DB_SECRET_ARN = module.db.db_instance_master_user_secret_arn
  }

  attach_policy_json = true
  policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_sqs_queue.contract_queue.arn,
          module.db.db_instance_master_user_secret_arn
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel"]
        Resource = "*"
      }
    ]
  })

  tags = {
    Terraform   = "true"
    Environment = "dev"
  }
}
