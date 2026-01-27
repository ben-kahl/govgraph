terraform {
  required_providers {
    aws = {
      source  = "hashicorp.aws"
      version = "~> 6.2.0"
    }
  }

  backend "s3" {
    bucket         = "gov-graph-state"
    key            = "dev/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "gov-graph-lock"
  }
}

provider "aws" {
  region = "us-east-1"
}


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

  enable_nat_gateway = true
  single_nat_gateway = var.enable_single_nat_gateway

  enable_dns_hostnames = true
  enable_dns_support   = true

  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
  }

  tags = {
    Terraform                                 = "true"
    Environment                               = "dev"
    "kubernetes.io/cluster/gov-graph-cluster" = "shared"
  }
}

# -----------------------------------------------------------------------------
# EKS
# -----------------------------------------------------------------------------
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.0"

  name               = "gov-graph-cluster"
  kubernetes_version = "1.34"

  addons = {
    coredns = {}
    eks-pod-identity-agent = {
      before_compute = true
    }
    kube-proxy = {}
    vpc-cni = {
      before_compute = true
    }
  }

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  enable_cluster_creator_admin_permissions = true

  endpoint_public_access = true

  eks_managed_node_groups = {
    initial = {
      min_size     = 1
      max_size     = 2
      desired_size = 1

      instance_types = ["t3.medium"]
      capacity_type  = "SPOT"
    }
  }

  tags = {
    Environment = "dev"
    Terraform   = "true"
  }
}

# -----------------------------------------------------------------------------
# RDS (PostgreSQL)
# -----------------------------------------------------------------------------

resource "aws_security_group" "rds_sg" {
  name        = "gov-graph-rds-sg"
  description = "Allow inbound traffic to RDS"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "PostgreSQL from VPC"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [module.vpc.vpc_cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "gov-graph-rds-sg"
  }
}

resource "aws_db_subnet_group" "default" {
  name       = "gov-graph-db-subnet-group"
  subnet_ids = module.vpc.private_subnets

  tags = {
    Name = "gov-graph-db-subnet-group"
  }
}

resource "aws_db_instance" "default" {
  allocated_storage      = 20
  storage_type           = "gp2"
  engine                 = "postgres"
  engine_version         = "16.1"
  instance_class         = var.db_instance_class
  db_name                = var.db_name
  username               = var.db_username
  password               = var.db_password
  parameter_group_name   = "default.postgres16"
  skip_final_snapshot    = true
  publicly_accessible    = false
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  db_subnet_group_name   = aws_db_subnet_group.default.name
}

# -----------------------------------------------------------------------------
# SQS (Contract Processing Queue)
# -----------------------------------------------------------------------------
resource "aws_sqs_queue" "contract_queue" {
  name                      = "gov-graph-contract-queue"
  delay_seconds             = 0
  max_message_size          = 262144
  message_retention_seconds = 86400
  receive_wait_time_seconds = 10
}

# -----------------------------------------------------------------------------
# Lambda (Ingestion & Processing)
# -----------------------------------------------------------------------------

# IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "gov-graph-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# IAM Policy for Lambda (Logging, RDS, SQS, Bedrock)
resource "aws_iam_role_policy" "lambda_policy" {
  name = "gov-graph-lambda-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.contract_queue.arn
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = "*" # Scope down to specific model ARN in prod
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface"
        ]
        Resource = "*" # Required for Lambda in VPC
      }
    ]
  })
}

# Archive the python code (Zip)
data "archive_file" "ingestion_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src/ingestion"
  output_path = "${path.module}/ingestion.zip"
}

# Lambda Function: Ingestion
resource "aws_lambda_function" "ingestion_lambda" {
  filename         = data.archive_file.ingestion_zip.output_path
  function_name    = "gov-graph-ingestion"
  role             = aws_iam_role.lambda_role.arn
  handler          = "ingest_contracts.main" # Assuming main() is the entry point
  source_code_hash = data.archive_file.ingestion_zip.output_base64sha256
  runtime          = "python3.9"
  timeout          = 300

  vpc_config {
    subnet_ids         = module.vpc.private_subnets
    security_group_ids = [aws_security_group.rds_sg.id]
  }

  environment {
    variables = {
      DB_HOST = aws_db_instance.default.address
      DB_NAME = var.db_name
      DB_USER = var.db_username
      DB_PASS = var.db_password
    }
  }
}

