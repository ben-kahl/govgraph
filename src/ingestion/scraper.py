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
            "Awarding Agency Code", "Start Date", "End Date", "Award Type", 
            "Recipient UEI", "Recipient DUNS"
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
        # Limit to 5 pages (500 records) for testing/prototype
        if not data.get("page_metadata", {}).get("hasNext", False) or page >= 1:
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
        start_date = (today - datetime.timedelta(days=days_back)
                      ).strftime("%Y-%m-%d")
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
