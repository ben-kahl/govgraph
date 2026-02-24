# GovGraph Development Plan

## Pinned Items

### Ingestion Scraper Optimization (Approach 2)
*   **Current State:** The scraper fetches a 3-day rolling window of contracts every time it runs. This is highly inefficient and processes the same contracts multiple times.
*   **Proposed Change:** Update `src/ingestion/scraper.py` to fetch exactly 1 day of data, but offset it by 3 days (e.g., on Thursday, fetch Monday's data).
*   **Benefit:** Reduces SQS messages, Lambda invocations, and RDS writes by ~66%, aligning with the strict <$15/month cost goal.
*   **Mitigation:** If a day is missed due to failure, rely on CloudWatch alarms and manually invoke the Lambda with a specific `{"date": "YYYY-MM-DD"}` payload.

### Weekly Resolution Analytics Report (EventBridge + Lambda + SNS)
*   **Goal:** Automate the execution of a CloudWatch Logs Insights query to calculate the percentage breakdown of entity resolution tiers (e.g., Cache Hit, Exact Match, LLM Fallback) and email the results weekly.
*   **Implementation Steps:**
    1.  **Lambda (`src/monitoring/weekly_report.py`):** Create a Python script using `boto3` (`logs.start_query`, `logs.get_query_results`) to run the regex query against the Entity Resolver log group for the past 7 days, calculate percentages, and publish a formatted message to an SNS topic.
    2.  **Terraform (`infra/monitoring.tf` or `infra/lambda.tf`):**
        *   Provision the Lambda function and IAM role (needs `logs:StartQuery`, `logs:GetQueryResults`, `sns:Publish`).
        *   Create an SNS Topic and an Email Subscription (user will need to manually confirm the subscription email).
        *   Create an EventBridge Rule (cron schedule, e.g., `cron(0 12 ? * MON *)` for Monday 12:00 PM UTC) and set the Lambda as the target.
