# -----------------------------------------------------------------------------
# SQS (Contract Processing Queue)
# -----------------------------------------------------------------------------
module "sqs" {
  source  = "terraform-aws-modules/sqs/aws"
  version = "~> 5.0"

  name = "gov-graph-contract-queue"

  visibility_timeout_seconds = 330
  delay_seconds              = 0
  max_message_size           = 262144
  message_retention_seconds  = 86400
  receive_wait_time_seconds  = 10

  create_dlq              = true
  sqs_managed_sse_enabled = true


  tags = {
    Terraform   = "true"
    Environment = "dev"
  }
}
