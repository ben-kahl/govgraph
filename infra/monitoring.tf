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
# EventBridge Schedule (Daily 7am UTC for Neo4j Sync)
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_event_rule" "daily_sync" {
  name                = "gov-graph-daily-sync"
  description         = "Triggers Neo4j sync Lambda daily at 7am UTC"
  schedule_expression = "cron(0 7 * * ? *)"
}

resource "aws_cloudwatch_event_target" "sync_target" {
  rule      = aws_cloudwatch_event_rule.daily_sync.name
  target_id = "SyncLambda"
  arn       = module.sync_lambda.lambda_function_arn
}

resource "aws_lambda_permission" "allow_eventbridge_sync" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = module.sync_lambda.lambda_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_sync.arn
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

# -----------------------------------------------------------------------------
# Weekly Resolution Analytics Report (EventBridge + Lambda + SNS)
# -----------------------------------------------------------------------------
resource "aws_sns_topic" "weekly_report" {
  name = "gov-graph-weekly-report"
}

resource "aws_sns_topic_subscription" "weekly_report_email" {
  topic_arn = aws_sns_topic.weekly_report.arn
  protocol  = "email"
  endpoint  = var.admin_email
}

module "weekly_report_lambda" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 8.0"

  function_name = "gov-graph-weekly-report"
  description   = "Generates and emails weekly entity resolution analytics"
  handler       = "weekly_report.lambda_handler"
  runtime       = "python3.12"
  timeout       = 60

  source_path = "${path.module}/../src/monitoring"

  environment_variables = {
    SNS_TOPIC_ARN  = aws_sns_topic.weekly_report.arn
    LOG_GROUP_NAME = "/aws/lambda/${module.processing_lambda.lambda_function_name}"
  }

  attach_policy_json = true
  policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = [aws_sns_topic.weekly_report.arn]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:StartQuery",
          "logs:GetQueryResults",
          "logs:DescribeLogGroups"
        ]
        Resource = [
          "arn:aws:logs:*:*:log-group:/aws/lambda/${module.processing_lambda.lambda_function_name}:*",
          "arn:aws:logs:*:*:log-group:/aws/lambda/${module.processing_lambda.lambda_function_name}"
        ]
      }
    ]
  })

  tags = {
    Terraform   = "true"
    Environment = "dev"
  }
}

resource "aws_cloudwatch_event_rule" "weekly_report_schedule" {
  name                = "gov-graph-weekly-report"
  description         = "Triggers weekly report Lambda on Monday at 12pm UTC"
  schedule_expression = "cron(0 12 ? * MON *)"
}

resource "aws_cloudwatch_event_target" "weekly_report_target" {
  rule      = aws_cloudwatch_event_rule.weekly_report_schedule.name
  target_id = "WeeklyReportLambda"
  arn       = module.weekly_report_lambda.lambda_function_arn
}

resource "aws_lambda_permission" "allow_eventbridge_weekly_report" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = module.weekly_report_lambda.lambda_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.weekly_report_schedule.arn
}
