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

resource "aws_s3_bucket_public_access_block" "lambda_builds" {
  bucket = aws_s3_bucket.lambda_builds.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lambda_builds" {
  bucket = aws_s3_bucket.lambda_builds.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
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

resource "aws_s3_bucket_public_access_block" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
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
