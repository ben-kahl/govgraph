import os
import datetime
import requests
import json
import uuid
import psycopg2
import boto3
from psycopg2.extras import Json

# Configuration
API_BASE_URL = "https://api.usaspending.gov/api/v2"
SEARCH_ENDPOINT = "/search/spending_by_award/"

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "govgraph")


def get_db_credentials(secret_arn):
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_arn)
    return json.loads(response['SecretString'])


def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    # Check for local credentials first
    db_user = os.environ.get("DB_USER")
    db_password = os.environ.get("DB_PASSWORD")

    if db_user and db_password:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=db_user,
            password=db_password
        )
    else:
        secret_arn = os.environ.get("DB_SECRET_ARN")
        creds = get_db_credentials(secret_arn)
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=creds['username'],
            password=creds['password']
        )
    return conn


def fetch_contracts(start_date, end_date):
    """Fetches contracts from USAspending API for a given date range."""
    url = f"{API_BASE_URL}{SEARCH_ENDPOINT}"

    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "filters": {
            "time_period": [
                {
                    "start_date": start_date,
                    "end_date": end_date
                }
            ],
            "award_type_codes": ["A", "B", "C", "D"],
            "agencies": [
                {
                    "type": "awarding",
                    "tier": "toptier",
                    "name": "Department of Defense"
                }
            ]
        },
        "fields": [
            "Award ID",
            "Recipient Name",
            "Award Amount",
            "Awarding Agency",
            "Start Date",
            "End Date",
            "Award Type",
            "NAICS Code",
            "PSC Code",
            "Recipient UEI"
        ],
        "limit": 100,
        "page": 1
    }

    all_results = []
    page = 1

    while True:
        print(f"Fetching page {page}...")
        payload["page"] = page
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            print(f"Error fetching data: {
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

    return all_results


def store_raw_contracts(contracts):
    """Stores raw contract data into the PostgreSQL database."""
    conn = get_db_connection()
    cur = conn.cursor()

    inserted_count = 0

    for contract in contracts:
        usaspending_id = contract.get("Award ID")
        if not usaspending_id:
            continue

        # Generate a new UUID for our internal ID
        internal_id = str(uuid.uuid4())

        try:
            cur.execute(
                """
                INSERT INTO raw_contracts (id, usaspending_id, raw_payload, ingested_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (usaspending_id) DO NOTHING
                """,
                (internal_id, usaspending_id, Json(
                    contract), datetime.datetime.now())
            )
            inserted_count += cur.rowcount
        except Exception as e:
            print(f"Error inserting contract {usaspending_id}: {e}")
            conn.rollback()
            continue

    conn.commit()
    cur.close()
    conn.close()
    print(f"Successfully stored {inserted_count} new contracts.")


def main():
    """Main execution flow."""
    # Calculate date range (yesterday)
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    date_str = yesterday.strftime("%Y-%m-%d")

    print(f"Starting ingestion for date: {date_str}")

    contracts = fetch_contracts(date_str, date_str)
    print(f"Fetched {len(contracts)} contracts.")
    if contracts:
        print(contracts)
        store_raw_contracts(contracts)


if __name__ == "__main__":
    main()
