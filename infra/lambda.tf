# -----------------------------------------------------------------------------
# Lambda Layer (Manual Build)
# -----------------------------------------------------------------------------

resource "null_resource" "build_layer" {
  triggers = {
    requirements_hash = filemd5("${path.module}/../src/requirements.txt")
  }

  provisioner "local-exec" {
    command = <<EOT
      mkdir -p ${path.module}/builds/layer_stage/python/lib/python3.12/site-packages
      pip install -r ${path.module}/../src/requirements.txt -t ${path.module}/builds/layer_stage/python/lib/python3.12/site-packages --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --only-binary=:all: --upgrade
      find ${path.module}/builds/layer_stage -type d -exec chmod 755 {} +
      find ${path.module}/builds/layer_stage -type f -exec chmod 644 {} +
      python3 -c "import shutil; shutil.make_archive('${path.module}/builds/layer', 'zip', '${path.module}/builds/layer_stage')"
      rm -rf ${path.module}/builds/layer_stage
    EOT
  }
}

resource "aws_s3_object" "layer_zip" {
  bucket     = aws_s3_bucket.lambda_builds.id
  key        = "layer-${filemd5("${path.module}/../src/requirements.txt")}.zip"
  source     = "${path.module}/builds/layer.zip"
  depends_on = [null_resource.build_layer]

  # Ensure update when zip changes
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
  handler       = "entity_resolver.lambda_handler"
  runtime       = "python3.12"
  timeout       = 300

  layers = [aws_lambda_layer_version.dependencies.arn]

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

module "sync_lambda" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 8.0"

  function_name = "gov-graph-sync"
  description   = "Syncs cleaned data from Postgres to Neo4j"
  handler       = "neo4j_syncer.lambda_handler"
  runtime       = "python3.12"
  timeout       = 900

  layers = [aws_lambda_layer_version.dependencies.arn]

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

  source_path   = "${path.module}/../src/db"
  artifacts_dir = "${path.root}/builds"

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

