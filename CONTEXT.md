This file is a merged representation of a subset of the codebase, containing files not matching ignore patterns, combined into a single document by Repomix.
The content has been processed where security check has been disabled.

# File Summary

## Purpose
This file contains a packed representation of a subset of the repository's contents that is considered the most important context.
It is designed to be easily consumable by AI systems for analysis, code review,
or other automated processes.

## File Format
The content is organized as follows:
1. This summary section
2. Repository information
3. Directory structure
4. Repository files (if enabled)
5. Multiple file entries, each consisting of:
  a. A header with the file path (## File: path/to/file)
  b. The full contents of the file in a code block

## Usage Guidelines
- This file should be treated as read-only. Any changes should be made to the
  original repository files, not this packed version.
- When processing this file, use the file path to distinguish
  between different files in the repository.
- Be aware that this file may contain sensitive information. Handle it with
  the same level of security as you would the original repository.

## Notes
- Some files may have been excluded based on .gitignore rules and Repomix's configuration
- Binary files are not included in this packed representation. Please refer to the Repository Structure section for a complete list of file paths, including binary files
- Files matching these patterns are excluded: GEMINI.md, README.md, infra/.terraform.lock.hcl
- Files matching patterns in .gitignore are excluded
- Files matching default ignore patterns are excluded
- Security check has been disabled - content may contain sensitive information
- Files are sorted by Git change count (files with more changes are at the bottom)

# Directory Structure
```
.github/
  workflows/
    destroy.yml
    pytest.yml
    terraform.yml
infra/
  scripts/
    build_layer.py
    build_layer.sh
  tests/
    lambda.tftest.hcl
    vpc.tftest.hcl
  dev.tfvars
  dynamodb.tf
  lambda.tf
  monitoring.tf
  outputs.tf
  providers.tf
  rds.tf
  s3.tf
  secrets.tf
  security.tf
  sqs.tf
  variables.tf
  vpc.tf
src/
  db/
    apply_schema.py
    schema.sql
  ingestion/
    scraper.py
  processing/
    entity_resolver.py
  sync/
    neo4j_syncer.py
  tests/
    unit/
      test_clean_names.py
      test_ingest_contracts.py
  README.md
  requirements.txt
.gitignore
```

# Files

## File: .github/workflows/destroy.yml
````yaml
name: "Manually Destroy Infra"

on:
  workflow_dispatch:
    inputs:
      confirmation:
        description: 'Type DESTROY to confirm infrastructure deletion'
        required: true
        default: 'NO'

permissions:
  contents: read

jobs:
  destroy:
    # This ensures the job only runs if the user explicitly types DESTROY
    if: ${{ github.event.inputs.confirmation == 'DESTROY' }}
    name: "Terraform Destroy"
    runs-on: ubuntu-latest

    permissions:
      id-token: write
      contents: read

    defaults:
      run:
        working-directory: ./infra

    steps:
      - name: Checkout
        uses: actions/checkout@v5

      - name: Configure AWS credentials via OIDC
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_TO_ASSUME }}
          aws-region: us-east-1

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3 # Updated to v3

      - name: Terraform Init
        run: terraform init

      - name: Terraform Destroy
        run: terraform destroy -auto-approve -var-file="dev.tfvars"
````

## File: .github/workflows/pytest.yml
````yaml
name: Test Python Scripts

on:
  push:
    branches:
      - main
  pull_request:

jobs:
  build:

    runs-on: ubuntu-latest

    permissions:
      id-token: write
      contents: read
      pull-requests: write

    steps:
      - uses: actions/checkout@v5
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: |
          cd src/
          python -m pip install --upgrade pip
          python install -r requirements.txt

      - name: Test with pytest
        id: test
        run: |
          python -m pytest

      - name: Output test results to PR conversation
        uses: actions/github-script@v6
        if: github.event_name == 'pull_request'
        env:
          RESULTS: "pytest\n${{ steps.test.outputs.stdout }}"
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          script: |
            const output = `### Pytest 🧪\`${{ steps.test.outcome }}\`
            <details><summary>Show Test Output</summary>
            \`\`\`\n
            ${process.env.RESULTS}
            \`\`\`

            </details>`;

            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: output
            })
````

## File: .github/workflows/terraform.yml
````yaml
name: "Terraform Infrastructure"

on:
  push:
    branches:
      - main
  pull_request:

permissions:
  contents: read
  pull-requests: write

jobs:
  terraform:
    name: "Terraform"

    runs-on: ubuntu-latest

    permissions:
      id-token: write
      contents: read
      pull-requests: write

    defaults:
      run:
        working-directory: ./infra

    steps:
      - name: Checkout
        uses: actions/checkout@v5

      - name: Configure AWS credentials via OIDC
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_TO_ASSUME }}
          aws-region: us-east-1

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v2

      # Code style check
      - name: Terraform Format
        id: fmt
        run: terraform fmt -check

      - name: Terraform Init
        id: init
        run: terraform init

      - name: Terraform Validate
        id: validate
        run: terraform validate -no-color

      - name: Terraform Test
        id: test
        run: terraform test

      - name: Terraform Plan
        id: plan
        if: github.event_name == 'pull_request' || github.ref == 'refs/heads/main'
        run: terraform plan -no-color -input=false -var-file="dev.tfvars" -out=tfplan
        continue-on-error: true

      # Posts the Plan output to PR conversation
      - name: Update Pull Request
        uses: actions/github-script@v6
        if: github.event_name == 'pull_request'
        env:
          PLAN: "terraform\n${{ steps.plan.outputs.stdout }}"
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          script: |
            const output = `#### Terraform Format and Style 🖌\`${{ steps.fmt.outcome }}\`
            #### Terraform Initialization ⚙️\`${{ steps.init.outcome }}\`
            #### Terraform Plan 📖\`${{ steps.plan.outcome }}\`
            #### Terraform Validation 🤖\`${{ steps.validate.outcome }}\`
            #### Terraform Test 🧪\`${{ steps.test.outcome }}\`

            <details><summary>Show Plan</summary>

            \`\`\`\n
            ${process.env.PLAN}
            \`\`\`

            </details>`;

            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: output
            })

      - name: Terraform Apply
        if: github.ref == 'refs/heads/main' && github.event_name == 'push'
        run: terraform apply -auto-approve -input=false -var-file="dev.tfvars"
````

## File: infra/scripts/build_layer.py
````python
import os
import subprocess
import shutil
import json
import hashlib
import sys

def get_hash(file_path):
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def build():
    # Use paths relative to the script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    req_file = os.path.join(root_dir, "../src/requirements.txt")
    build_dir = os.path.join(root_dir, "builds")
    stage_dir = os.path.join(build_dir, "layer_stage")
    zip_path = os.path.join(build_dir, "layer") # .zip will be added
    
    # Ensure build directory exists
    os.makedirs(build_dir, exist_ok=True)
    
    # Check if we need to rebuild
    # (Simplified: always rebuild if called by Terraform for now, or check hash)
    
    if os.path.exists(stage_dir):
        shutil.rmtree(stage_dir)
        
    site_packages = os.path.join(stage_dir, "python/lib/python3.12/site-packages")
    os.makedirs(site_packages, exist_ok=True)
    
    # Run pip
    try:
        subprocess.check_call([
            "pip", "install", "-r", req_file, 
            "-t", site_packages, 
            "--platform", "manylinux2014_x86_64", 
            "--implementation", "cp", 
            "--python-version", "3.12", 
            "--only-binary=:all:", 
            "--upgrade"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Zip it up
        shutil.make_archive(zip_path, 'zip', stage_dir)
        
        # Cleanup
        shutil.rmtree(stage_dir)
        
        return os.path.abspath(zip_path + ".zip")
    except Exception as e:
        sys.stderr.write(str(e))
        sys.exit(1)

if __name__ == "__main__":
    path = build()
    print(json.dumps({"path": path}))
````

## File: infra/scripts/build_layer.sh
````bash

````

## File: infra/tests/lambda.tftest.hcl
````hcl
# infra/tests/lambda.tftest.hcl
# TODO: Add actual unit tests asap...

# 1. Verify Ingestion Lambda Configuration
run "verify_ingestion_lambda" {
  command = plan

  assert {
    condition     = module.ingestion_lambda.lambda_function_name == "gov-graph-ingestion"
    error_message = "Ingestion Lambda function name mismatch."
  }
}

# 2. Verify Processing Lambda Configuration
run "verify_processing_lambda" {
  command = plan

  assert {
    condition     = module.processing_lambda.lambda_function_name == "gov-graph-processing"
    error_message = "Processing Lambda function name mismatch."
  }
}
````

## File: infra/tests/vpc.tftest.hcl
````hcl
# 1. Check that the module doesn't crash
run "setup_tests" {
  command = plan

  assert {
    condition = module.vpc.natgw_ids != null
    error_message = "NAT Gateway must be enabled"
  }
}

# 2. Assert single NAT Gateway
run "verify_single_nat" {
  command = plan

  assert {
    condition = length(module.vpc.natgw_ids) == 1
    error_message = "More than 1 NAT Gateway detected. single_nat_gateway must be enabled for cost saving"
  }
}

# 3. Scenario Test: Verify that turning OFF cheap mode creates multiple NAT Gateways
run "verify_high_availability_mode" {
  command = plan

  variables {
    enable_single_nat_gateway = false
  }

  assert {
    # If cheap mode is OFF, we should have as many NAT Gateways as AZs (2)
    condition     = length(module.vpc.natgw_ids) == 2
    error_message = "High Availability Mode failed! Expected 2 NAT Gateways."
  }
}
````

## File: infra/dev.tfvars
````hcl
# dev.tfvars
vpc_name    = "gov-graph-vpc-dev"
vpc_cidr    = "10.0.0.0/16"
db_name     = "govgraph"
db_username = "govgraph_admin"
aws_region  = "us-east-1"
admin_email = "admin@example.com"
````

## File: infra/dynamodb.tf
````hcl
# -----------------------------------------------------------------------------
# DynamoDB (Entity Resolution Cache)
# -----------------------------------------------------------------------------
resource "aws_dynamodb_table" "entity_cache" {
  name         = "gov-graph-entity-cache"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "vendor_name"

  attribute {
    name = "vendor_name"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name        = "Entity Resolution Cache"
    Terraform   = "true"
    Environment = "dev"
  }
}
````

## File: infra/lambda.tf
````hcl
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

  source_path = "${path.module}/../src/processing"

  vpc_subnet_ids         = module.vpc.private_subnets
  vpc_security_group_ids = [module.security_group.security_group_id]
  attach_network_policy  = true

  environment_variables = {
    DB_HOST              = module.db.db_instance_address
    DB_NAME              = var.db_name
    DB_USER              = var.db_username
    DB_SECRET_ARN        = module.db.db_instance_master_user_secret_arn
    DYNAMODB_CACHE_TABLE = aws_dynamodb_table.entity_cache.name
    BEDROCK_MODEL_ID     = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    REGION_NAME          = "us-east-1"
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
          "dynamodb:UpdateItem"
        ]
        Resource = [
          module.sqs.queue_arn,
          module.db.db_instance_master_user_secret_arn,
          aws_dynamodb_table.entity_cache.arn,
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
````

## File: infra/monitoring.tf
````hcl
# -----------------------------------------------------------------------------
# CloudWatch Dashboard
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "gov-graph-pipeline"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", "gov-graph-ingestion"],
            [".", ".", ".", "gov-graph-processing"],
            [".", ".", ".", "gov-graph-sync"]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "Lambda Invocations"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", module.sqs.queue_name]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "SQS Queue Depth"
        }
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# AWS Budget Alert
# -----------------------------------------------------------------------------
resource "aws_budgets_budget" "cost_control" {
  name              = "gov-graph-monthly-budget"
  budget_type       = "COST"
  limit_amount      = "20"
  limit_unit        = "USD"
  time_period_end   = "2087-06-15_00:00"
  time_period_start = "2026-01-01_00:00"
  time_unit         = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.admin_email]
  }
}
````

## File: infra/outputs.tf
````hcl
output "rds_endpoint" {
  description = "RDS instance endpoint"
  value       = module.db.db_instance_endpoint
}

output "sqs_queue_url" {
  description = "SQS queue URL"
  value       = module.sqs.queue_url
}

output "sqs_queue_arn" {
  description = "SQS queue ARN"
  value       = module.sqs.queue_arn
}
````

## File: infra/providers.tf
````hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.28.0"
    }
  }

  backend "s3" {
    bucket       = "gov-graph-state"
    key          = "dev/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = "us-east-1"
}
````

## File: infra/rds.tf
````hcl
# -----------------------------------------------------------------------------
# RDS (PostgreSQL)
# -----------------------------------------------------------------------------

module "db" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 7.1.0"

  identifier = "gov-graph-postgres-db"

  engine                   = "postgres"
  engine_version           = "17.6"
  engine_lifecycle_support = "open-source-rds-extended-support-disabled"
  family                   = "postgres17"
  major_engine_version     = "17"
  instance_class           = var.db_instance_class

  allocated_storage     = 20
  max_allocated_storage = 100

  db_name                     = var.db_name
  username                    = var.db_username
  manage_master_user_password = true
  port                        = 5432

  db_subnet_group_name   = module.vpc.database_subnet_group_name
  vpc_security_group_ids = [module.security_group.security_group_id]

  skip_final_snapshot = true
  publicly_accessible = false

  # Postgres 17 usually doesn't require a custom option group for basic usage
  create_db_option_group = false

  tags = {
    Terraform   = "true"
    Environment = "dev"
  }
}
````

## File: infra/s3.tf
````hcl
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "lambda_builds" {
  bucket = "gov-graph-lambda-builds-${random_id.bucket_suffix.hex}"

  tags = {
    Terraform   = "true"
    Environment = "dev"
  }
}

resource "aws_s3_bucket" "raw_data" {
  bucket = "govgraph-raw-data-${random_id.bucket_suffix.hex}"

  tags = {
    Name        = "Raw Contract Data Archive"
    Terraform   = "true"
    Environment = "dev"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id

  rule {
    id     = "archive_old_data"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "GLACIER"
    }
  }
}

output "raw_data_bucket_name" {
  value = aws_s3_bucket.raw_data.id
}
````

## File: infra/secrets.tf
````hcl
resource "aws_secretsmanager_secret" "neo4j_credentials" {
  name        = "gov-graph/neo4j-credentials"
  description = "Credentials for Neo4j AuraDB (Manually populated)"

  # Recovery window in days (0 forces immediate deletion for dev environments)
  recovery_window_in_days = 0

  tags = {
    Terraform   = "true"
    Environment = "dev"
  }
}
````

## File: infra/security.tf
````hcl
module "security_group" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "~> 5.0"

  name        = "gov-graph-rds-sg"
  description = "RDS security group, allows inbound traffic to RDS"
  vpc_id      = module.vpc.vpc_id

  ingress_with_cidr_blocks = [
    {
      from_port   = 5432
      to_port     = 5432
      protocol    = "tcp"
      description = "PostgreSQL access from within VPC"
      cidr_blocks = module.vpc.vpc_cidr_block
    },
    {
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      description = "HTTPS for VPC Endpoints"
      cidr_blocks = module.vpc.vpc_cidr_block
    },
  ]

  egress_with_cidr_blocks = [
    {
      from_port   = 0
      to_port     = 0
      protocol    = "-1"
      description = "Allow all outbound traffic"
      cidr_blocks = "0.0.0.0/0"
    }
  ]

  tags = {
    Terraform   = "true"
    Environment = "dev"
  }
}
````

## File: infra/sqs.tf
````hcl
# -----------------------------------------------------------------------------
# SQS (Contract Processing Queue)
# -----------------------------------------------------------------------------
module "sqs" {
  source  = "terraform-aws-modules/sqs/aws"
  version = "~> 5.0"

  name = "gov-graph-contract-queue"

  visibility_timeout_seconds = 330
  delay_seconds              = 0
  max_message_size          = 262144
  message_retention_seconds = 86400
  receive_wait_time_seconds = 10

  create_dlq              = true
  sqs_managed_sse_enabled = true


  tags = {
    Terraform   = "true"
    Environment = "dev"
  }
}
````

## File: infra/variables.tf
````hcl
# variables.tf

# VPC Variables

variable "vpc_name" {
  description = "Name of the VPC"
  type        = string
  default     = "gov-graph-vpc"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "vpc_azs" {
  description = "Availability Zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "vpc_private_subnets" {
  description = "Private Subnet CIDRs"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "vpc_public_subnets" {
  description = "Public Subnet CIDRs"
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24"]
}

variable "vpc_database_subnets" {
  description = "Database Subnet CIDRs"
  type        = list(string)
  default     = ["10.0.21.0/24", "10.0.22.0/24"]
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "admin_email" {
  description = "Email for budget alerts"
  type        = string
  default     = "admin@example.com"
}

# Database Variables

variable "db_name" {
  description = "Name of the PostgreSQL database"
  type        = string
  default     = "govgraphdb"
}

variable "db_username" {
  description = "Username for the database"
  type        = string
  default     = "govgraph"
}

variable "db_instance_class" {
  description = "RDS Instance Class"
  type        = string
  default     = "db.t3.micro"
}
````

## File: infra/vpc.tf
````hcl
# -----------------------------------------------------------------------------
# VPC
# -----------------------------------------------------------------------------
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"

  name = var.vpc_name
  cidr = var.vpc_cidr

  azs             = var.vpc_azs
  private_subnets = var.vpc_private_subnets
  public_subnets  = var.vpc_public_subnets

  database_subnets             = var.vpc_database_subnets
  create_database_subnet_group = true

  # Cost Optimization: No NAT Gateway
  enable_nat_gateway = false
  single_nat_gateway = false

  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Terraform   = "true"
    Environment = "dev"
  }
}

# -----------------------------------------------------------------------------
# VPC Endpoints (Cost Optimization: Bypass NAT Gateway)
# -----------------------------------------------------------------------------
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = module.vpc.private_route_table_ids

  tags = {
    Name = "s3-endpoint"
  }
}

resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = module.vpc.private_route_table_ids

  tags = {
    Name = "dynamodb-endpoint"
  }
}

resource "aws_vpc_endpoint" "bedrock" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.bedrock-runtime"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [module.security_group.security_group_id]
  private_dns_enabled = true

  tags = {
    Name = "bedrock-endpoint"
  }
}

resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [module.security_group.security_group_id]
  private_dns_enabled = true

  tags = {
    Name = "secretsmanager-endpoint"
  }
}

resource "aws_vpc_endpoint" "logs" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.logs"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [module.security_group.security_group_id]
  private_dns_enabled = true

  tags = {
    Name = "logs-endpoint"
  }
}
````

## File: src/db/apply_schema.py
````python
import os
import json
import boto3
import psycopg2
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configuration
DB_HOST = os.environ.get("DB_HOST")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN")


def get_secret(secret_arn):
    """Retrieve secret from AWS Secrets Manager."""
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_arn)
    return json.loads(response['SecretString'])


def lambda_handler(event, context):
    """
    Lambda handler to apply the database schema.
    Reads schema.sql from the same directory and executes it.
    """
    conn = None
    try:
        logger.info("Starting connection process...")

        logger.info(f"Fetching secret from: {DB_SECRET_ARN}")
        # explicit timeout for boto3 if possible, but logging is key
        db_creds = get_secret(DB_SECRET_ARN)
        logger.info("Successfully retrieved credentials from Secrets Manager.")

        logger.info(f"Connecting to RDS Host: {DB_HOST}")
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=db_creds.get('username', DB_USER),
            password=db_creds['password'],
            connect_timeout=10  # Fail fast if network is down
        )
        logger.info("Successfully connected to PostgreSQL.")
        conn.autocommit = True  # Allow creating tables/types

        # Read schema file
        # Note: In Lambda, the file must be packaged alongside this script
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        logger.info(f"Reading schema from {schema_path}...")

        with open(schema_path, 'r') as f:
            schema_sql = f.read()

        logger.info("Applying schema...")
        with conn.cursor() as cur:
            cur.execute(schema_sql)

        logger.info("Schema applied successfully.")

        return {
            'statusCode': 200,
            'body': json.dumps('Schema applied successfully.')
        }

    except Exception as e:
        logger.error(f"Schema application failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Schema application failed: {str(e)}')
        }

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    # Local testing (requires env vars set manually)
    logging.basicConfig(level=logging.INFO)
    lambda_handler({}, {})
````

## File: src/db/schema.sql
````sql
-- PostgreSQL Schema for GovGraph

-- Enable Extension for UUIDs and utility functions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Raw Contracts (Landing Zone)
CREATE TABLE IF NOT EXISTS raw_contracts (
    id UUID PRIMARY KEY,
    usaspending_id VARCHAR(255) UNIQUE NOT NULL,
    raw_payload JSONB NOT NULL,
    ingested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,
    processing_errors TEXT
);
CREATE INDEX IF NOT EXISTS idx_raw_contracts_processed ON raw_contracts(processed) WHERE processed = FALSE;

-- 2. Vendors (Canonical Records)
CREATE TABLE IF NOT EXISTS vendors (
    id UUID PRIMARY KEY,
    duns VARCHAR(20) UNIQUE,
    uei VARCHAR(20) UNIQUE,
    canonical_name VARCHAR(500) UNIQUE NOT NULL,
    legal_name VARCHAR(500),
    doing_business_as TEXT[],
    vendor_type VARCHAR(50),
    
    -- Location
    address_line1 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(2),
    zip_code VARCHAR(10),
    country VARCHAR(3) DEFAULT 'USA',
    
    -- Classification
    business_types TEXT[],
    naics_codes VARCHAR(10)[],
    psc_codes VARCHAR(10)[],
    
    -- Entity Resolution
    resolution_confidence DECIMAL(3,2),
    resolved_by_llm BOOLEAN DEFAULT FALSE,
    alternative_names TEXT[],
    matched_vendor_ids UUID[],
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indices for Entity Resolution Performance
CREATE INDEX IF NOT EXISTS idx_vendors_canonical_name ON vendors (canonical_name);
CREATE INDEX IF NOT EXISTS idx_vendors_duns ON vendors (duns) WHERE duns IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_vendors_uei ON vendors (uei) WHERE uei IS NOT NULL;

-- 3. Agencies
CREATE TABLE IF NOT EXISTS agencies (
    id UUID PRIMARY KEY,
    agency_code VARCHAR(10) UNIQUE NOT NULL,
    agency_name VARCHAR(500) NOT NULL,
    department VARCHAR(255),
    agency_type VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Contracts (Core Data) - Partitioned by signed_date
CREATE TABLE IF NOT EXISTS contracts (
    id UUID NOT NULL,
    contract_id VARCHAR(255) NOT NULL,
    vendor_id UUID REFERENCES vendors(id),
    agency_id UUID REFERENCES agencies(id),
    parent_contract_id UUID, -- References handled manually due to partitioning
    
    description TEXT,
    award_type VARCHAR(100),
    contract_type VARCHAR(100),
    
    -- Financial
    obligated_amount DECIMAL(15,2),
    base_amount DECIMAL(15,2),
    total_value DECIMAL(15,2),
    
    -- Dates
    signed_date DATE NOT NULL,
    start_date DATE,
    end_date DATE,
    current_end_date DATE,
    
    -- Classification
    naics_code VARCHAR(10),
    psc_code VARCHAR(10),
    place_of_performance_state VARCHAR(2),
    
    is_subcontract BOOLEAN DEFAULT FALSE,
    raw_contract_id UUID REFERENCES raw_contracts(id),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    PRIMARY KEY (id, signed_date),
    UNIQUE (contract_id, signed_date)
) PARTITION BY RANGE (signed_date);

-- Create Default Partition to catch any dates not explicitly defined
CREATE TABLE IF NOT EXISTS contracts_default PARTITION OF contracts DEFAULT;

-- Indices for Contracts
CREATE INDEX IF NOT EXISTS idx_contracts_signed_date ON contracts (signed_date);
CREATE INDEX IF NOT EXISTS idx_contracts_vendor_id ON contracts (vendor_id);
CREATE INDEX IF NOT EXISTS idx_contracts_contract_id ON contracts (contract_id);

-- 5. Subcontracts
CREATE TABLE IF NOT EXISTS subcontracts (
    id UUID PRIMARY KEY,
    prime_contract_id UUID, -- Link manually or include partition key
    prime_vendor_id UUID REFERENCES vendors(id),
    subcontractor_vendor_id UUID REFERENCES vendors(id),
    subcontract_amount DECIMAL(15,2),
    subcontract_description TEXT,
    tier_level INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. Entity Resolution Log
CREATE TABLE IF NOT EXISTS entity_resolution_log (
    id UUID PRIMARY KEY,
    source_vendor_name VARCHAR(500) NOT NULL,
    resolved_vendor_id UUID REFERENCES vendors(id),
    
    llm_model VARCHAR(100),
    llm_prompt_tokens INTEGER,
    llm_completion_tokens INTEGER,
    confidence_score DECIMAL(3,2),
    
    reasoning TEXT,
    alternative_matches JSONB,
    
    manually_verified BOOLEAN DEFAULT FALSE,
    verified_by VARCHAR(255),
    verified_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. Neo4j Sync Status
CREATE TABLE IF NOT EXISTS neo4j_sync_status (
    id UUID PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    synced_at TIMESTAMP WITH TIME ZONE,
    neo4j_node_id BIGINT,
    sync_status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,
    UNIQUE(entity_type, entity_id)
);

-- 8. Vendor Analytics
CREATE TABLE IF NOT EXISTS vendor_analytics (
    vendor_id UUID PRIMARY KEY REFERENCES vendors(id),
    total_contracts INTEGER DEFAULT 0,
    total_obligated_amount DECIMAL(15,2) DEFAULT 0,
    active_contracts INTEGER DEFAULT 0,
    first_contract_date DATE,
    last_contract_date DATE,
    top_agencies UUID[],
    top_naics_codes VARCHAR(10)[],
    subcontractor_count INTEGER DEFAULT 0,
    prime_contractor_count INTEGER DEFAULT 0,
    calculated_at TIMESTAMP WITH TIME ZONE
);

-- 9. ETL Runs
CREATE TABLE IF NOT EXISTS etl_runs (
    id UUID PRIMARY KEY,
    run_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    records_fetched INTEGER,
    records_processed INTEGER,
    records_failed INTEGER,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    metadata JSONB
);
````

## File: src/ingestion/scraper.py
````python
import os
import datetime
import requests
import json
import boto3
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configuration
API_BASE_URL = "https://api.usaspending.gov/api/v2"
SEARCH_ENDPOINT = "/search/spending_by_award/"

# AWS Resources
S3_BUCKET = os.environ.get("S3_BUCKET_NAME")
SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL")

s3_client = boto3.client('s3')
sqs_client = boto3.client('sqs')


def fetch_contracts(start_date, end_date):
    """
    Fetches contracts from USAspending API for a given date range.

    Args:
        start_date (str): YYYY-MM-DD
        end_date (str): YYYY-MM-DD

    Returns:
        list: List of contract dictionaries
    """
    url = f"{API_BASE_URL}{SEARCH_ENDPOINT}"
    headers = {"Content-Type": "application/json"}

    payload = {
        "filters": {
            "time_period": [{"start_date": start_date, "end_date": end_date}],
            "award_type_codes": ["A", "B", "C", "D"]
        },
        "fields": [
            "Award ID", "Recipient Name", "Award Amount", "Awarding Agency",
            "Start Date", "End Date", "Award Type", "Recipient UEI", "Recipient DUNS"
        ],
        "limit": 100,
        "page": 1
    }

    all_results = []
    page = 1

    while True:
        logger.info(f"Fetching page {page}...")
        payload["page"] = page
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            logger.error(f"Error fetching data: {
                         response.status_code} - {response.text}")
            break

        data = response.json()
        results = data.get("results", [])
        if not results:
            break

        all_results.extend(results)
        # Limit to 10 pages (1000 records) for testing/prototype
        if not data.get("page_metadata", {}).get("hasNext", False) or page >= 10:
            break
        page += 1

    return all_results


def archive_to_s3(contracts, date_str):
    """Archives raw contract data to S3."""
    file_key = f"{date_str}/contracts.json"
    logger.info(f"Archiving {len(contracts)
                             } contracts to s3://{S3_BUCKET}/{file_key}")

    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=file_key,
        Body=json.dumps(contracts),
        ContentType='application/json'
    )
    return file_key


def send_to_queue(contracts):
    """Sends individual contracts to SQS in batches."""
    logger.info(f"Sending {len(contracts)} contracts to SQS queue...")

    # SQS SendMessageBatch supports up to 10 messages
    for i in range(0, len(contracts), 10):
        batch = contracts[i:i+10]
        entries = []
        for j, contract in enumerate(batch):
            entries.append({
                'Id': str(j),
                'MessageBody': json.dumps(contract)
            })

        sqs_client.send_message_batch(
            QueueUrl=SQS_QUEUE_URL,
            Entries=entries
        )


def lambda_handler(event, context):
    """Main Lambda Entry Point."""
    # Get configuration from event
    days_back = event.get('days', 3)  # Default to 3 days to handle lag
    target_date = event.get('date')
    
    today = datetime.date.today()
    
    if target_date:
        start_date = target_date
        end_date = target_date
    else:
        # Fetch a range to ensure we capture late-reported data
        # Federal data has a 24-72h reporting lag
        start_date = (today - datetime.timedelta(days=days_back)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

    logger.info(f"Starting ingestion: {start_date} to {end_date}")

    contracts = fetch_contracts(start_date, end_date)

    if not contracts:
        logger.info("No contracts found for this period.")
        return {"statusCode": 200, "body": "No data found"}

    # 1. Archive to S3
    archive_to_s3(contracts, f"{start_date}_to_{end_date}")

    # 2. Push to SQS for downstream processing
    send_to_queue(contracts)

    return {
        "statusCode": 200,
        "body": f"Ingested {len(contracts)} contracts. Data archived to S3 and queued in SQS."
    }


def test_handler():
    """Local test run handler"""
    today = datetime.date.today()
    start_date = (today - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")

    contracts = fetch_contracts(start_date, end_date)

    if not contracts:
        return {"statusCode": 200, "body": "No data found"}

    print(len(contracts))
    return {
        "statusCode": 200,
        "body": f"Ingested {len(contracts)} contracts. Data archived to S3 and queued in SQS."
    }


if __name__ == "__main__":
    test_handler()
````

## File: src/processing/entity_resolver.py
````python
import os
import json
import uuid
import boto3
import psycopg2
import logging
import time
import random
from datetime import datetime, date, timedelta
from rapidfuzz import process, fuzz
from psycopg2.extras import RealDictCursor

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configuration
DB_HOST = os.environ.get("DB_HOST")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN")
DYNAMODB_CACHE_TABLE = os.environ.get("DYNAMODB_CACHE_TABLE")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-haiku-4-5-20251001-v1:0")

# Clients
bedrock = boto3.client(service_name="bedrock-runtime")
dynamodb = boto3.resource("dynamodb")
cache_table = dynamodb.Table(DYNAMODB_CACHE_TABLE)

# -----------------------------------------------------------------------------
# Database Utilities
# -----------------------------------------------------------------------------
def get_secret(secret_arn):
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_arn)
    return json.loads(response['SecretString'])

def get_db_connection():
    db_creds = get_secret(DB_SECRET_ARN)
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=db_creds.get('username', DB_USER),
        password=db_creds['password'],
        connect_timeout=10
    )

# -----------------------------------------------------------------------------
# Entity Resolution Logic (4-Tier)
# -----------------------------------------------------------------------------

def resolve_vendor(vendor_name, duns=None, uei=None, conn=None):
    """
    4-Tier Resolution Strategy:
    1. DUNS/UEI exact match (RDS)
    2. Canonical name exact match (RDS)
    3. DynamoDB cache lookup
    4. Fuzzy matching / Bedrock fallback
    """
    
    # Tier 1: DUNS/UEI exact match
    if duns or uei:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, canonical_name FROM vendors WHERE duns = %s OR uei = %s LIMIT 1",
                (duns, uei)
            )
            result = cur.fetchone()
            if result:
                return result['id'], result['canonical_name'], "DUNS_UEI_MATCH", 1.0

    # Tier 2: Canonical name exact match
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT id, canonical_name FROM vendors WHERE canonical_name = %s LIMIT 1",
            (vendor_name,)
        )
        result = cur.fetchone()
        if result:
            return result['id'], result['canonical_name'], "EXACT_NAME_MATCH", 1.0

    # Tier 3: DynamoDB Cache
    try:
        cache_resp = cache_table.get_item(Key={'vendor_name': vendor_name})
        if 'Item' in cache_resp:
            item = cache_resp['Item']
            return item['vendor_id'], item['canonical_name'], "CACHE_MATCH", float(item.get('confidence', 0.9))
    except Exception as e:
        logger.warning(f"DynamoDB cache lookup failed: {e}")

    # Tier 4: Bedrock LLM Fallback
    canonical_name = call_bedrock_standardization_with_retry(vendor_name)
    
    # After LLM, check if the NEW canonical name exists in DB
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT id, canonical_name FROM vendors WHERE canonical_name = %s LIMIT 1",
            (canonical_name,)
        )
        result = cur.fetchone()
        
        if result:
            vendor_id = result['id']
        else:
            # Create new vendor if not found
            vendor_id = str(uuid.uuid4())
            try:
                cur.execute(
                    """
                    INSERT INTO vendors (id, canonical_name, duns, uei, resolved_by_llm, resolution_confidence)
                    VALUES (%s, %s, %s, %s, TRUE, 0.95)
                    ON CONFLICT (canonical_name) DO UPDATE SET updated_at = NOW()
                    RETURNING id
                    """,
                    (vendor_id, canonical_name, duns, uei)
                )
                res = cur.fetchone()
                if res:
                    vendor_id = res[0]
            except Exception as e:
                logger.error(f"Failed to create vendor {canonical_name}: {e}")
                # Fallback to lookup one more time in case of race condition
                cur.execute("SELECT id FROM vendors WHERE canonical_name = %s", (canonical_name,))
                result = cur.fetchone()
                if result:
                    vendor_id = result[0]

    # Update DynamoDB Cache
    try:
        cache_table.put_item(Item={
            'vendor_name': vendor_name,
            'canonical_name': canonical_name,
            'vendor_id': vendor_id,
            'confidence': '0.95',
            'ttl': int(time.time() + (90 * 24 * 60 * 60)) # 90 days
        })
    except Exception as e:
        logger.warning(f"Failed to update DynamoDB cache: {e}")

    return vendor_id, canonical_name, "LLM_RESOLUTION", 0.95

def call_bedrock_standardization_with_retry(messy_name, max_retries=3):
    """Calls Bedrock with exponential backoff to handle throttling."""
    prompt = f"""
    Standardize this company name to its canonical legal form.
    Input: "{messy_name}"
    Rules: Return ONLY the name. Expand abbreviations (Corp -> Corporation).
    Name:"""

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 100,
        "messages": [{"role": "user", "content": prompt}]
    })

    for attempt in range(max_retries):
        try:
            response = bedrock.invoke_model(body=body, modelId=BEDROCK_MODEL_ID)
            response_body = json.loads(response.get("body").read())
            return response_body["content"][0]["text"].strip()
        except Exception as e:
            if "ThrottlingException" in str(e) or "Too many requests" in str(e):
                wait_time = (2 ** attempt) + random.random()
                logger.warning(f"Bedrock throttled. Retrying in {wait_time:.2f}s...")
                time.sleep(wait_time)
                continue
            logger.error(f"Bedrock failed: {e}")
            break
            
    return messy_name

# -----------------------------------------------------------------------------
# Main Handler
# -----------------------------------------------------------------------------

def lambda_handler(event, context):
    logger.info(f"Processing batch of {len(event['Records'])} messages")
    
    conn = get_db_connection()
    conn.autocommit = True
    
    processed_count = 0
    
    try:
        for record in event['Records']:
            contract_data = json.loads(record['body'])
            
            vendor_name = contract_data.get('Recipient Name')
            duns = contract_data.get('Recipient DUNS')
            uei = contract_data.get('Recipient UEI')
            
            if not vendor_name:
                continue
                
            # 1. Resolve Vendor
            vendor_id, canonical_name, method, confidence = resolve_vendor(vendor_name, duns, uei, conn)
            
            # 2. Store Contract
            with conn.cursor() as cur:
                contract_uuid = str(uuid.uuid4())
                signed_date = contract_data.get('Start Date')
                if not signed_date:
                    signed_date = date.today().strftime("%Y-%m-%d")
                
                try:
                    # Added signed_date to ON CONFLICT to match partitioned index
                    cur.execute(
                        """
                        INSERT INTO contracts (
                            id, contract_id, vendor_id, description, 
                            obligated_amount, signed_date, award_type, 
                            created_at, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                        ON CONFLICT (contract_id, signed_date) DO UPDATE SET updated_at = NOW()
                        """,
                        (
                            contract_uuid,
                            contract_data.get('Award ID'),
                            vendor_id,
                            f"Contract for {canonical_name}",
                            contract_data.get('Award Amount', 0),
                            signed_date,
                            contract_data.get('Award Type')
                        )
                    )
                    processed_count += 1
                except Exception as e:
                    logger.error(f"Failed to insert contract {contract_data.get('Award ID')}: {e}")
                    
        return {
            "statusCode": 200,
            "body": json.dumps({"processed": processed_count})
        }
    finally:
        conn.close()
````

## File: src/sync/neo4j_syncer.py
````python
import os
import json
import boto3
import psycopg2
from neo4j import GraphDatabase
from psycopg2.extras import RealDictCursor

# Configuration
DB_HOST = os.environ.get("DB_HOST")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN")
NEO4J_SECRET_ARN = os.environ.get("NEO4J_SECRET_ARN")


def get_secret(secret_arn):
    """Retrieve secret from AWS Secrets Manager."""
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_arn)
    return json.loads(response['SecretString'])


def get_pg_connection():
    """Connect to PostgreSQL using credentials from Secrets Manager."""
    db_creds = get_secret(DB_SECRET_ARN)
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=db_creds.get('username', DB_USER),
        password=db_creds['password']
    )


def get_neo4j_driver():
    """Connect to Neo4j using credentials from Secrets Manager."""
    neo4j_creds = get_secret(NEO4J_SECRET_ARN)
    uri = neo4j_creds['NEO4J_URI']
    user = neo4j_creds['NEO4J_USERNAME']
    password = neo4j_creds['NEO4J_PASSWORD']
    return GraphDatabase.driver(uri, auth=(user, password))


def sync_agencies(pg_conn, neo4j_session):
    print("Syncing Agencies...")
    with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Find unsynced agencies
        cur.execute("""
            SELECT a.* 
            FROM agencies a
            LEFT JOIN neo4j_sync_status s 
                ON s.entity_type = 'agency' AND s.entity_id = a.id
            WHERE s.id IS NULL OR s.sync_status != 'synced'
        """)
        agencies = cur.fetchall()

        for agency in agencies:
            query = """
            MERGE (a:Agency {id: $id})
            SET a.agencyCode = $code,
                a.agencyName = $name,
                a.department = $dept,
                a.agencyType = $type,
                a.syncedAt = datetime()
            """
            neo4j_session.run(query,
                              id=str(agency['id']),
                              code=agency['agency_code'],
                              name=agency['agency_name'],
                              dept=agency['department'],
                              type=agency['agency_type'])

            # Update sync status
            mark_synced(pg_conn, 'agency', agency['id'])
    print(f"Synced {len(agencies)} agencies.")


def sync_vendors(pg_conn, neo4j_session):
    print("Syncing Vendors...")
    with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT v.* 
            FROM vendors v
            LEFT JOIN neo4j_sync_status s 
                ON s.entity_type = 'vendor' AND s.entity_id = v.id
            WHERE s.id IS NULL OR s.sync_status != 'synced'
        """)
        vendors = cur.fetchall()

        for vendor in vendors:
            query = """
            MERGE (v:Vendor {id: $id})
            SET v.canonicalName = $name,
                v.duns = $duns,
                v.uei = $uei,
                v.state = $state,
                v.city = $city,
                v.syncedAt = datetime()
            """
            neo4j_session.run(query,
                              id=str(vendor['id']),
                              name=vendor['canonical_name'],
                              duns=vendor['duns'],
                              uei=vendor['uei'],
                              state=vendor['state'],
                              city=vendor['city'])

            mark_synced(pg_conn, 'vendor', vendor['id'])
    print(f"Synced {len(vendors)} vendors.")


def sync_contracts(pg_conn, neo4j_session):
    print("Syncing Contracts...")
    with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT c.* 
            FROM contracts c
            LEFT JOIN neo4j_sync_status s 
                ON s.entity_type = 'contract' AND s.entity_id = c.id
            WHERE s.id IS NULL OR s.sync_status != 'synced'
        """)
        contracts = cur.fetchall()

        for contract in contracts:
            # Create Contract Node
            query_node = """
            MERGE (c:Contract {id: $id})
            SET c.contractId = $contract_id,
                c.description = $desc,
                c.obligatedAmount = $amount,
                c.signedDate = date($signed_date),
                c.syncedAt = datetime()
            """
            neo4j_session.run(query_node,
                              id=str(contract['id']),
                              contract_id=contract['contract_id'],
                              desc=contract['description'],
                              amount=float(
                                  contract['obligated_amount']) if contract['obligated_amount'] else 0.0,
                              signed_date=contract['signed_date'])

            # Link to Vendor
            if contract['vendor_id']:
                query_rel_vendor = """
                MATCH (c:Contract {id: $c_id})
                MATCH (v:Vendor {id: $v_id})
                MERGE (v)-[:AWARDED]->(c)
                MERGE (c)-[:AWARDED_TO]->(v)
                """
                neo4j_session.run(query_rel_vendor, c_id=str(
                    contract['id']), v_id=str(contract['vendor_id']))

            # Link to Agency
            if contract['agency_id']:
                query_rel_agency = """
                MATCH (c:Contract {id: $c_id})
                MATCH (a:Agency {id: $a_id})
                MERGE (a)-[:AWARDED_CONTRACT]->(c)
                """
                neo4j_session.run(query_rel_agency, c_id=str(
                    contract['id']), a_id=str(contract['agency_id']))

            mark_synced(pg_conn, 'contract', contract['id'])
    print(f"Synced {len(contracts)} contracts.")


def mark_synced(pg_conn, entity_type, entity_id):
    with pg_conn.cursor() as cur:
        try:
            cur.execute("""
                INSERT INTO neo4j_sync_status (id, entity_type, entity_id, sync_status, synced_at)
                VALUES (gen_random_uuid(), %s, %s, 'synced', NOW())
                ON CONFLICT (entity_type, entity_id) 
                DO UPDATE SET sync_status = 'synced', synced_at = NOW()
            """, (entity_type, entity_id))
            pg_conn.commit()
        except Exception as e:
            print(f"Failed to update sync status for {
                  entity_type} {entity_id}: {e}")
            pg_conn.rollback()


def lambda_handler(event, context):
    """AWS Lambda Entry Point"""
    pg_conn = None
    neo4j_driver = None

    try:
        print("Starting Sync Process...")
        pg_conn = get_pg_connection()
        neo4j_driver = get_neo4j_driver()

        with neo4j_driver.session() as session:
            sync_agencies(pg_conn, session)
            sync_vendors(pg_conn, session)
            sync_contracts(pg_conn, session)

        return {
            'statusCode': 200,
            'body': json.dumps('Sync Complete')
        }

    except Exception as e:
        print(f"Sync Failed: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Sync Failed: {str(e)}')
        }

    finally:
        if pg_conn:
            pg_conn.close()
        if neo4j_driver:
            neo4j_driver.close()


if __name__ == "__main__":
    # For local testing, mock the context and event
    lambda_handler({}, {})
````

## File: src/tests/unit/test_clean_names.py
````python
import unittest
from unittest.mock import patch, MagicMock
from src.processing.clean_names import standardize_name


class TestCleanNames(unittest.TestCase):

    @patch('src.processing.clean_names.get_bedrock_client')
    def test_standardize_name_success(self, mock_get_client):
        # Mock Bedrock response
        mock_client = MagicMock()
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = b'{"content": [{"text": "Lockheed Martin Corporation"}]}'

        mock_client.invoke_model.return_value = {"body": mock_response_body}
        mock_get_client.return_value = mock_client

        # Call function
        result = standardize_name("L.M. Corp")

        # Assertions
        self.assertEqual(result, "Lockheed Martin Corporation")
        mock_client.invoke_model.assert_called_once()

    @patch('src.processing.clean_names.get_bedrock_client')
    def test_standardize_name_error(self, mock_get_client):
        # Mock Bedrock error (exception)
        mock_client = MagicMock()
        mock_client.invoke_model.side_effect = Exception("Bedrock error")
        mock_get_client.return_value = mock_client

        # Call function (should return original name on error)
        result = standardize_name("Bad Name")

        # Assertions
        self.assertEqual(result, "Bad Name")
        mock_client.invoke_model.assert_called_once()


if __name__ == '__main__':
    unittest.main()
````

## File: src/tests/unit/test_ingest_contracts.py
````python
import unittest
from unittest.mock import patch, MagicMock
from src.ingestion.ingest_contracts import fetch_contracts, store_raw_contracts


class TestIngestContracts(unittest.TestCase):

    @patch('src.ingestion.ingest_contracts.requests.post')
    def test_fetch_contracts_single_page(self, mock_post):
        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "page_metadata": {"hasNext": False},
            "results": [{"Award ID": "123", "Recipient Name": "Test Corp"}]
        }
        mock_post.return_value = mock_response

        # Call function
        results = fetch_contracts("2023-01-01", "2023-01-02")

        # Assertions
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["Award ID"], "123")
        mock_post.assert_called_once()

    @patch('src.ingestion.ingest_contracts.requests.post')
    def test_fetch_contracts_pagination(self, mock_post):
        # Mock API response for two pages
        mock_response_p1 = MagicMock()
        mock_response_p1.status_code = 200
        mock_response_p1.json.return_value = {
            "page_metadata": {"hasNext": True},
            "results": [{"Award ID": "123"}]
        }

        mock_response_p2 = MagicMock()
        mock_response_p2.status_code = 200
        mock_response_p2.json.return_value = {
            "page_metadata": {"hasNext": False},
            "results": [{"Award ID": "456"}]
        }

        mock_post.side_effect = [mock_response_p1, mock_response_p2]

        # Call function
        results = fetch_contracts("2023-01-01", "2023-01-02")

        # Assertions
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["Award ID"], "123")
        self.assertEqual(results[1]["Award ID"], "456")
        self.assertEqual(mock_post.call_count, 2)

    @patch('src.ingestion.ingest_contracts.get_db_connection')
    def test_store_raw_contracts(self, mock_get_conn):
        # Mock Database connection
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_get_conn.return_value = mock_conn

        # Test Data
        contracts = [
            {"Award ID": "123", "Recipient Name": "Test Corp"},
            {"Award ID": "456", "Recipient Name": "Another Corp"}
        ]

        # Call function
        store_raw_contracts(contracts)

        # Assertions
        self.assertEqual(mock_cur.execute.call_count, 2)
        mock_conn.commit.assert_called_once()
        mock_cur.close.assert_called_once()
        mock_conn.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
````

## File: src/README.md
````markdown
# GovGraph Source Code

## Deployment Instructions

### Lambda Dependencies
The Python scripts in `ingestion/` and `processing/` rely on external libraries (`requests`, `psycopg2-binary`).
The standard AWS Lambda runtime includes `boto3` and `json`, but NOT `requests` or `psycopg2`.

To successfully deploy the `ingest_contracts` function, you must create a deployment package that includes these dependencies.

#### Option 1: AWS Lambda Layers (Recommended)
1. Create a Lambda Layer containing `requests` and `psycopg2-binary` (compiled for Amazon Linux 2).
2. Attach this layer to the `aws_lambda_function` resource in `infra/main.tf`.

#### Option 2: Vendor Dependencies in Zip
Before running `terraform apply`, install the dependencies into the `src/ingestion` folder:

```bash
cd src/ingestion
pip install --target . requests psycopg2-binary
```

*Note: `psycopg2-binary` may cause issues on AWS Lambda if installed from a non-Linux machine. It is safer to use `aws-psycopg2` or build inside a Docker container.*

### Database Setup
The `infra/main.tf` creates an RDS instance. You will need to apply the schema manually after creation:

1. Connect to the RDS instance (you may need to use a Bastion host or allow your IP in the Security Group temporarily).
2. Run the SQL commands from `src/db/schema.sql`.

```bash
psql -h <RDS_ENDPOINT> -U postgres -d govgraph -f src/db/schema.sql
```

## Local Development & Testing

### 1. Start a Local Database
Use Docker to run a PostgreSQL 17 container:

```bash
docker run --name govgraph-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=govgraph -p 5432:5432 -d postgres:17
```

### 2. Apply Database Schema
Apply the schema to the local database:

```bash
docker exec -i govgraph-postgres psql -U postgres -d govgraph < src/db/schema.sql
```

### 3. Run Ingestion Script Locally
To test the ingestion pipeline without AWS dependencies, set the following environment variables:

```bash
export DB_HOST=localhost
export DB_NAME=govgraph
export DB_USER=postgres
export DB_PASSWORD=postgres

# Run using the project's virtual environment
python src/ingestion/ingest_contracts.py
```

The script will detect these environment variables and bypass AWS Secrets Manager.

### 4. Start Neo4j (Graph DB)
Run a local Neo4j instance for the knowledge graph:

```bash
docker run --name govgraph-neo4j -e NEO4J_AUTH=neo4j/password -p 7474:7474 -p 7687:7687 -d neo4j:5
```

Access the Neo4j Browser at [http://localhost:7474](http://localhost:7474).

### 5. Run Graph Sync
Sync data from PostgreSQL to Neo4j:

```bash
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=password

python src/processing/sync_to_graph.py
```
````

## File: src/requirements.txt
````
requests
psycopg2-binary
neo4j
rapidfuzz
````

## File: .gitignore
````
.terraform/
builds/
terraform.tfstate
terraform.tfstate.backup
tfplan
PLAN.md
usaspending_api_guide.md
.pytest_cache/
__pycache__/
venv/
*.zip
````
