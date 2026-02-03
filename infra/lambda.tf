# -----------------------------------------------------------------------------
# Lambda (Ingestion & Processing)
# -----------------------------------------------------------------------------
module "lambda_layer" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 8.0"

  create_layer = true
  layer_name   = "gov-graph-dependencies"
  description  = "Layer for requests and psycopg2-binary"

  source_path = [
    {
      path             = "${path.module}/../src"
      prefix_in_layer  = "python"
      patterns         = ["lambda_requirements.txt"]
      pip_requirements = "lambda_requirements.txt"
    }
  ]

  build_in_docker = false

  compatible_runtimes = ["python3.9"]
}

module "ingestion_lambda" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 8.0"

  function_name = "gov-graph-ingestion"
  description   = "Daily ingestion of USAspending data"
  handler       = "ingest_contracts.main" # Assuming main() is the entry point
  runtime       = "python3.9"
  timeout       = 300

  layers = [module.lambda_layer.lambda_layer_arn]

  source_path = "${path.module}/../src/ingestion"

  vpc_subnet_ids         = module.vpc.private_subnets
  vpc_security_group_ids = [module.security_group.security_group_id]
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
          module.sqs.queue_arn,
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

module "processing_lambda" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 8.0"

  function_name = "gov-graph-processing"
  description   = "Entity resolution using Bedrock"
  handler       = "clean_names.lambda_handler"
  runtime       = "python3.9"
  timeout       = 300

  layers = [module.lambda_layer.lambda_layer_arn]

  source_path = "${path.module}/../src/processing"

  vpc_subnet_ids         = module.vpc.private_subnets
  vpc_security_group_ids = [module.security_group.security_group_id]
  attach_network_policy  = true

  environment_variables = {
    DB_HOST          = module.db.db_instance_address
    DB_NAME          = var.db_name
    DB_USER          = var.db_username
    DB_SECRET_ARN    = module.db.db_instance_master_user_secret_arn
    BEDROCK_MODEL_ID = "anthropic.claude-haiku-4-5-20251001-v1:0"
    REGION_NAME      = "us-east-1"
  }

  attach_policy_json = true
  policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "secretsmanager:GetSecretValue",
          "bedrock:InvokeModel"
        ]
        Resource = [
          module.sqs.queue_arn,
          module.db.db_instance_master_user_secret_arn,
          "*"
        ]
      }
    ]
  })

  tags = {
    Terraform   = "true"
    Environment = "dev"
  }
}

