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


def fetch_contracts(start_date, end_date, spending_level="awards"):
    """
    Fetches contracts from USAspending API for a given date range and spending level.

    Args:
        start_date (str): YYYY-MM-DD
        end_date (str): YYYY-MM-DD
        spending_level (str): "awards" for prime awards, "subawards" for sub-contracts

    Returns:
        list: List of contract dictionaries
    """
    url = f"{API_BASE_URL}{SEARCH_ENDPOINT}"
    headers = {"Content-Type": "application/json"}

    # Common filters
    filters = {
        "time_period": [{"start_date": start_date, "end_date": end_date}],
        "award_type_codes": ["A", "B", "C", "D", "IDV_A", "IDV_B", "IDV_C", "IDV_D", "IDV_E"]
    }

    if spending_level == "awards":
        fields = [
            "Award ID", "Recipient Name", "Award Amount", "Awarding Agency",
            "Awarding Agency Code", "Awarding Sub Agency", "Awarding Sub Agency Code",
            "Funding Agency", "Funding Agency Code", "Funding Sub Agency", "Funding Sub Agency Code",
            "Start Date", "End Date", "Contract Award Type",
            "Recipient UEI", "Recipient DUNS", "Description"
        ]
    else:  # subawards
        fields = [
            "Sub-Award ID", "Sub-Awardee Name", "Sub-Award Amount", "Sub-Award Date",
            "Sub-Award Description", "Sub-Recipient UEI", "Sub-Recipient DUNS",
            "Prime Award ID", "Prime Recipient Name", "Prime Award Recipient UEI",
            "Awarding Agency", "Awarding Agency Code", "Awarding Sub Agency", "Awarding Sub Agency Code",
        ]

    payload = {
        "filters": filters,
        "fields": fields,
        "spending_level": spending_level,
        "limit": 100,
        "page": 1
    }

    all_results = []
    page = 1

    while True:
        logger.info(f"Fetching {spending_level} page {page}...")
        payload["page"] = page
        response = requests.post(url, headers=headers,
                                 json=payload, timeout=30)

        if response.status_code != 200:
            logger.error(f"Error fetching data: {
                         response.status_code} - {response.text}")
            break

        data = response.json()
        results = data.get("results", [])
        if not results:
            break

        all_results.extend(results)
        # Limit to 20 pages (2000 records) for backfill/prototype limits
        if not data.get("page_metadata", {}).get("hasNext", False) or page >= 20:
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


def send_to_queue(contracts, data_type="prime"):
    """Sends individual contracts to SQS in batches."""
    logger.info(f"Sending {len(contracts)} {
                data_type} messages to SQS queue...")

    # SQS SendMessageBatch supports up to 10 messages
    for i in range(0, len(contracts), 10):
        batch = contracts[i:i+10]
        entries = []
        for j, contract in enumerate(batch):
            # Include type for the processor to differentiate
            message_body = {
                "type": data_type,
                "data": contract
            }
            entries.append({
                'Id': str(j),
                'MessageBody': json.dumps(message_body)
            })

        response = sqs_client.send_message_batch(
            QueueUrl=SQS_QUEUE_URL,
            Entries=entries
        )
        if response.get('Failed'):
            failed_ids = [f['id'] for f in response['Failed']]
            logger.error(f"Failed to send messages: {failed_ids}")
            raise RuntimeError(f"SQS batch send partially failed: {
                               len(response['Failed'])} messages")


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

    # 1. Fetch Prime Awards
    prime_contracts = fetch_contracts(start_date, end_date, spending_level="awards")
    if prime_contracts:
        archive_to_s3(prime_contracts, f"{start_date}_to_{end_date}/prime")
        send_to_queue(prime_contracts, data_type="prime")
    else:
        logger.info("No prime contracts found.")

    # 2. Fetch Sub-Awards
    sub_awards = fetch_contracts(start_date, end_date, spending_level="subawards")
    if sub_awards:
        archive_to_s3(sub_awards, f"{start_date}_to_{end_date}/subaward")
        send_to_queue(sub_awards, data_type="subaward")
    else:
        logger.info("No sub-awards found.")

    total_count = len(prime_contracts) + len(sub_awards)
    return {
        "statusCode": 200,
        "body": f"Ingested {total_count} records (Primes: {len(prime_contracts)}, Subs: {len(sub_awards)})."
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
