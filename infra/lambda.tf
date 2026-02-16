# -----------------------------------------------------------------------------
# Lambda Layer (Automatic Build during Plan)
# -----------------------------------------------------------------------------

data "external" "build_layer" {
  program = ["python3", "${path.module}/scripts/build_layer.py"]
}

resource "aws_s3_object" "layer_zip" {
  bucket      = aws_s3_bucket.lambda_builds.id
  key         = "layer-${filemd5("${path.module}/../src/requirements.txt")}.zip"
  source      = data.external.build_layer.result.path
  source_hash = filemd5("${path.module}/../src/requirements.txt")
}

resource "aws_lambda_layer_version" "dependencies" {
  layer_name          = "gov-graph-dependencies"
  description         = "Layer for requests, psycopg2-binary, neo4j, and rapidfuzz"
  s3_bucket           = aws_s3_bucket.lambda_builds.id
  s3_key              = aws_s3_object.layer_zip.key
  compatible_runtimes = ["python3.12"]
}

module "ingestion_lambda" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 8.0"

  function_name = "gov-graph-ingestion"
  description   = "Daily ingestion of USAspending data"
  handler       = "scraper.lambda_handler"
  runtime       = "python3.12"
  timeout       = 300

  layers = [aws_lambda_layer_version.dependencies.arn]

  source_path = "${path.module}/../src/ingestion"

  ignore_source_code_hash = true

  # Removed VPC config to allow public internet access for USAspending API
  # S3 and SQS are reached via public AWS endpoints

  environment_variables = {
    DB_HOST        = module.db.db_instance_address
    DB_NAME        = var.db_name
    DB_USER        = var.db_username
    DB_SECRET_ARN  = module.db.db_instance_master_user_secret_arn
    SQS_QUEUE_URL  = module.sqs.queue_url
    S3_BUCKET_NAME = aws_s3_bucket.raw_data.id
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
          "secretsmanager:GetSecretValue",
          "s3:PutObject"
        ]
        Resource = [
          module.sqs.queue_arn,
          module.db.db_instance_master_user_secret_arn,
          "${aws_s3_bucket.raw_data.arn}/*"
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
  handler       = "entity_resolver.lambda_handler"
  runtime       = "python3.12"
  timeout       = 300

  layers = [aws_lambda_layer_version.dependencies.arn]

  ignore_source_code_hash = true

  source_path = "${path.module}/../src/processing"

  vpc_subnet_ids         = module.vpc.private_subnets
  vpc_security_group_ids = [module.security_group.security_group_id]
  attach_network_policy  = true

  environment_variables = {
    DB_HOST                = module.db.db_instance_address
    DB_NAME                = var.db_name
    DB_USER                = var.db_username
    DB_SECRET_ARN          = module.db.db_instance_master_user_secret_arn
    DYNAMODB_CACHE_TABLE   = aws_dynamodb_table.entity_cache.name
    BEDROCK_MODEL_ID       = "us.anthropic.claude-3-haiku-20240307-v1:0"
    REGION_NAME            = "us-east-1"
    SAM_API_KEY_SECRET_ARN = aws_secretsmanager_secret.sam_api_key.arn
    SAM_PROXY_LAMBDA_NAME  = module.sam_proxy_lambda.lambda_function_name
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
          "bedrock:InvokeModel",
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "lambda:InvokeFunction"
        ]
        Resource = [
          module.sqs.queue_arn,
          module.db.db_instance_master_user_secret_arn,
          aws_dynamodb_table.entity_cache.arn,
          module.sam_proxy_lambda.lambda_function_arn,
          "*"
        ]
      }
    ]
  })

  tags = {
    Terraform   = "true"
    Environment = "dev"
  }

  event_source_mapping = {
    sqs = {
      event_source_arn = module.sqs.queue_arn
      batch_size       = 10
      scaling_config = {
        maximum_concurrency = 2
      }
    }
  }
}

module "sam_proxy_lambda" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 8.0"

  function_name = "gov-graph-sam-proxy"
  description   = "Proxy for SAM.gov API calls (Outside VPC)"
  handler       = "sam_proxy.lambda_handler"
  runtime       = "python3.12"
  timeout       = 30

  layers = [aws_lambda_layer_version.dependencies.arn]

  ignore_source_code_hash = true

  source_path = "${path.module}/../src/processing/sam_proxy.py"

  # No VPC config to allow public internet access

  environment_variables = {
    SAM_API_KEY_SECRET_ARN = aws_secretsmanager_secret.sam_api_key.arn
  }

  attach_policy_json = true
  policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_secretsmanager_secret.sam_api_key.arn
        ]
      }
    ]
  })

  tags = {
    Terraform   = "true"
    Environment = "dev"
  }
}

module "sync_lambda" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 8.0"

  function_name = "gov-graph-sync"
  description   = "Syncs cleaned data from Postgres to Neo4j"
  handler       = "neo4j_syncer.lambda_handler"
  runtime       = "python3.12"
  timeout       = 900

  layers = [aws_lambda_layer_version.dependencies.arn]

  ignore_source_code_hash = true

  source_path = "${path.module}/../src/sync"

  vpc_subnet_ids         = module.vpc.private_subnets
  vpc_security_group_ids = [module.security_group.security_group_id]
  attach_network_policy  = true

  environment_variables = {
    DB_HOST          = module.db.db_instance_address
    DB_NAME          = var.db_name
    DB_USER          = var.db_username
    DB_SECRET_ARN    = module.db.db_instance_master_user_secret_arn
    NEO4J_SECRET_ARN = aws_secretsmanager_secret.neo4j_credentials.arn
  }

  attach_policy_json = true
  policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          module.db.db_instance_master_user_secret_arn,
          aws_secretsmanager_secret.neo4j_credentials.arn
        ]
      }
    ]
  })

  tags = {
    Terraform   = "true"
    Environment = "dev"
  }
}

module "schema_migration_lambda" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 8.0"

  function_name = "gov-graph-schema-migration"
  description   = "Applies database schema to RDS"
  handler       = "apply_schema.lambda_handler"
  runtime       = "python3.12"
  timeout       = 300 # Increased timeout

  layers = [aws_lambda_layer_version.dependencies.arn]

  source_path = "${path.module}/../src/db"

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
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          module.db.db_instance_master_user_secret_arn
        ]
      }
    ]
  })

  tags = {
    Terraform   = "true"
    Environment = "dev"
  }
}

