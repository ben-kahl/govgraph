import os
import time
import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import boto3
import logging
from typing import Any, Dict, List, Optional

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


def get_session() -> requests.Session:
    """Configures a requests Session with robust retries and connection pooling."""
    session = requests.Session()
    # Retry on 429 Too Many Requests, 500, 502, 503, 504
    retry = Retry(
        total=5,
        read=5,
        connect=5,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=None,  # urllib3 default excludes POST; None retries all methods
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(
        max_retries=retry, pool_connections=10, pool_maxsize=10)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def fetch_contracts(start_date: str, end_date: str, spending_level: str = "awards", award_type_codes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Fetches contracts from USAspending API for a given date range and spending level.

    Args:
        start_date (str): YYYY-MM-DD
        end_date (str): YYYY-MM-DD
        spending_level (str): "awards" for prime awards, "subawards" for sub-contracts
        award_type_codes (list): List of USAspending award type codes (e.g., ['A', 'B'])

    Returns:
        list: List of contract dictionaries
    """
    url = f"{API_BASE_URL}{SEARCH_ENDPOINT}"
    headers = {"Content-Type": "application/json"}

    if award_type_codes is None:
        # Default to contracts if not specified
        award_type_codes = ["A", "B", "C", "D"]

    # Common filters
    filters = {
        "time_period": [{"start_date": start_date, "end_date": end_date}],
        "award_type_codes": award_type_codes
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
    session = get_session()

    while True:
        logger.info(f"Fetching {spending_level} page {page}...")
        payload["page"] = page

        try:
            response = session.post(
                url, headers=headers, json=payload, timeout=30)

            if response.status_code != 200:
                logger.error(f"Error fetching data: {
                             response.status_code} - {response.text}")
                break

            data = response.json()
            results = data.get("results", [])
            if not results:
                break

            all_results.extend(results)
            if not data.get("page_metadata", {}).get("hasNext", False):
                break

            page += 1
            # Prevent rate limiting and connection drops from USAspending API
            time.sleep(0.5)

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch {spending_level} page {
                         page} due to connection error: {e}")
            break

    return all_results


def archive_to_s3(contracts: List[Dict[str, Any]], date_str: str) -> str:
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


def send_to_queue(contracts: List[Dict[str, Any]], data_type: str = "prime") -> None:
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


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
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

    # 1. Fetch Prime Awards (Split into groups to avoid 422 error)
    contract_types = ["A", "B", "C", "D"]
    idv_types = ["IDV_A", "IDV_B", "IDV_C", "IDV_D", "IDV_E"]

    logger.info("Fetching Prime Contracts (A, B, C, D)...")
    prime_contracts = fetch_contracts(
        start_date, end_date, spending_level="awards", award_type_codes=contract_types)

    logger.info("Fetching Prime IDVs (IDV_A, IDV_B, IDV_C, IDV_D, IDV_E)...")
    prime_idvs = fetch_contracts(
        start_date, end_date, spending_level="awards", award_type_codes=idv_types)

    all_primes = prime_contracts + prime_idvs

    if all_primes:
        archive_to_s3(all_primes, f"{start_date}_to_{end_date}/prime")
        send_to_queue(all_primes, data_type="prime")
    else:
        logger.info("No prime contracts or IDVs found.")

    # 2. Fetch Sub-Awards (Sub-awards generally only apply to contracts, not IDVs)
    sub_awards = fetch_contracts(
        start_date, end_date, spending_level="subawards", award_type_codes=contract_types)
    if sub_awards:
        archive_to_s3(sub_awards, f"{start_date}_to_{end_date}/subaward")
        send_to_queue(sub_awards, data_type="subaward")
    else:
        logger.info("No sub-awards found.")

    total_count = len(all_primes) + len(sub_awards)
    return {
        "statusCode": 200,
        "body": f"Ingested {total_count} records (Primes: {len(all_primes)}, Subs: {len(sub_awards)})."
    }


def test_handler() -> Dict[str, Any]:
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
