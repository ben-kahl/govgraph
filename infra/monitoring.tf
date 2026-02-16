# -----------------------------------------------------------------------------
# EventBridge Schedule (Daily 6am UTC)
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_event_rule" "daily_ingestion" {
  name                = "gov-graph-daily-ingestion"
  description         = "Triggers ingestion Lambda daily at 6am UTC"
  schedule_expression = "cron(0 6 * * ? *)"
}

resource "aws_cloudwatch_event_target" "ingestion_target" {
  rule      = aws_cloudwatch_event_rule.daily_ingestion.name
  target_id = "IngestionLambda"
  arn       = module.ingestion_lambda.lambda_function_arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = module.ingestion_lambda.lambda_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_ingestion.arn
}

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
