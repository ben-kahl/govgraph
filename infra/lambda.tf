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

  vpc_subnet_ids         = module.vpc.private_subnets
  vpc_security_group_ids = [module.security_group.security_group_id]
  attach_network_policy  = true

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
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem"
        ]
        Resource = [
          module.sqs.queue_arn,
          module.db.db_instance_master_user_secret_arn,
          aws_dynamodb_table.entity_cache.arn,
          aws_secretsmanager_secret.sam_api_key.arn
        ]
      },
      {
        Effect = "Allow"
        Action = ["bedrock:InvokeModel"]
        Resource = [
          "arn:aws:bedrock:us-east-1:*:inference-profile/us.anthropic.claude-3-haiku-20240307-v1:0",
          "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
          "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
          "arn:aws:bedrock:::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
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
        maximum_concurrency = 10
      }
    }
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

module "reprocess_lambda" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 8.0"

  function_name = "gov-graph-reprocess"
  description   = "One-time reprocessing of contracts to fix missing fields"
  handler       = "reprocess_lambda.lambda_handler"
  runtime       = "python3.12"
  timeout       = 900 # 15 minutes for batch processing

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
    SAM_API_KEY_SECRET_ARN = aws_secretsmanager_secret.sam_api_key.arn
  }

  attach_policy_json = true
  policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem"
        ]
        Resource = [
          module.db.db_instance_master_user_secret_arn,
          aws_dynamodb_table.entity_cache.arn,
          aws_secretsmanager_secret.sam_api_key.arn
        ]
      },
      {
        Effect = "Allow"
        Action = ["bedrock:InvokeModel"]
        Resource = [
          "arn:aws:bedrock:us-east-1:*:inference-profile/us.anthropic.claude-3-haiku-20240307-v1:0",
          "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
          "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
          "arn:aws:bedrock:::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
        ]
      }
    ]
  })

  tags = {
    Terraform   = "true"
    Environment = "dev"
  }
}

module "api_lambda" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 8.0"

  function_name = "gov-graph-api"
  description   = "FastAPI + Mangum serving the GovGraph HTTP API"
  handler       = "api.handler"
  runtime       = "python3.12"
  timeout       = 30

  layers = [aws_lambda_layer_version.dependencies.arn]

  source_path = "${path.module}/../src/api"

  ignore_source_code_hash = true

  vpc_subnet_ids         = module.vpc.private_subnets
  vpc_security_group_ids = [module.security_group.security_group_id]
  attach_network_policy  = true

  environment_variables = {
    DB_HOST              = module.db.db_instance_address
    DB_NAME              = var.db_name
    DB_USER              = var.db_username
    DB_SECRET_ARN        = module.db.db_instance_master_user_secret_arn
    NEO4J_SECRET_ARN     = aws_secretsmanager_secret.neo4j_credentials.arn
    COGNITO_USER_POOL_ID = aws_cognito_user_pool.main.id
    COGNITO_REGION       = "us-east-1"
    ALLOWED_ORIGINS      = var.allowed_origins
  }

  attach_policy_json = true
  policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = [
          module.db.db_instance_master_user_secret_arn,
          aws_secretsmanager_secret.neo4j_credentials.arn,
        ]
      }
    ]
  })

  tags = {
    Terraform   = "true"
    Environment = "dev"
  }
}

module "apply_schema_lambda" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 8.0"

  function_name = "gov-graph-apply-schema"
  description   = "Applies SQL schema to RDS"
  handler       = "apply_schema.lambda_handler"
  runtime       = "python3.12"
  timeout       = 300

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
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [module.db.db_instance_master_user_secret_arn]
      }
    ]
  })

  tags = {
    Terraform   = "true"
    Environment = "dev"
  }
}
