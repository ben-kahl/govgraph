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
