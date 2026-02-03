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

resource "aws_s3_bucket_lifecycle_configuration" "lambda_builds" {
  bucket = aws_s3_bucket.lambda_builds.id

  rule {
    id     = "cleanup_old_builds"
    status = "Enabled"

    expiration {
      days = 1
    }
  }
}
