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
