import os
import json
import uuid
import boto3
import psycopg2
import logging
import time
from datetime import datetime
import requests
from psycopg2.extras import RealDictCursor

# Correct imports for Lambda environment
from entity_resolver import get_db_connection, resolve_vendor, resolve_agency

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

API_BASE_URL = "https://api.usaspending.gov/api/v2"
SEARCH_ENDPOINT = "/search/spending_by_award/"

# "Polite" session - identifying the project is better than faking a browser
# This tells the API admins who you are and what you're doing.
session = requests.Session()
session.headers.update({
    "User-Agent": "GovGraph-Research-Project (Contact: research@example.com)",
    "Accept": "application/json",
    "Content-Type": "application/json"
})

def fetch_batch_details(award_ids):
    """Fetches details for a batch of award IDs in a single API call."""
    url = f"{API_BASE_URL}{SEARCH_ENDPOINT}"
    
    payload = {
        "filters": {
            "award_ids": award_ids
        },
        "fields": [
            "Award ID", "Recipient Name", "Award Amount", "Awarding Agency",
            "Awarding Agency Code", "Start Date", "End Date", "Contract Award Type",
            "Recipient UEI", "Recipient DUNS", "Description"
        ],
        "limit": len(award_ids)
    }
    
    try:
        response = session.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json().get("results", [])
        else:
            logger.error(f"API Error {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"Batch fetch failed: {e}")
    
    return []

def lambda_handler(event, context):
    """
    Reprocesses contracts in efficient batches.
    """
    limit = event.get('limit', 100)
    batch_size = event.get('batch_size', 50)
    
    conn = get_db_connection()
    conn.autocommit = True
    
    processed = 0
    updated = 0
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT rc.usaspending_id, rc.id as raw_id
                FROM raw_contracts rc
                JOIN contracts c ON rc.usaspending_id = c.contract_id
                WHERE c.award_type IS NULL
                LIMIT %s
            """, (limit,))
            
            all_records = cur.fetchall()
            logger.info(f"Starting reprocessing for {len(all_records)} records.")
            
            for i in range(0, len(all_records), batch_size):
                batch = all_records[i:i + batch_size]
                award_ids = [r['usaspending_id'] for r in batch]
                raw_id_map = {r['usaspending_id']: r['raw_id'] for r in batch}
                
                api_results = fetch_batch_details(award_ids)
                
                for api_data in api_results:
                    award_id = api_data.get('Award ID')
                    raw_id = raw_id_map.get(award_id)
                    
                    if not award_id or not raw_id:
                        continue
                        
                    vendor_id, canonical_name, _, _ = resolve_vendor(
                        api_data.get('Recipient Name'), 
                        api_data.get('Recipient DUNS'), 
                        api_data.get('Recipient UEI'), 
                        conn
                    )
                    agency_id = resolve_agency(
                        api_data.get('Awarding Agency'), 
                        api_data.get('Awarding Agency Code'), 
                        conn
                    )
                    
                    award_type = api_data.get('Contract Award Type')
                    raw_desc = api_data.get('Description', 'No description provided')
                    formatted_desc = f"Vendor: {canonical_name} | {raw_desc}"
                    
                    cur.execute(
                        "UPDATE raw_contracts SET raw_payload = %s WHERE id = %s",
                        (json.dumps(api_data), raw_id)
                    )
                    
                    cur.execute(
                        """
                        UPDATE contracts SET 
                            award_type = %s,
                            description = %s,
                            vendor_id = %s,
                            agency_id = %s,
                            updated_at = NOW()
                        WHERE contract_id = %s AND signed_date = %s
                        """,
                        (award_type, formatted_desc, vendor_id, agency_id, award_id, api_data.get('Start Date'))
                    )
                    updated += 1
                
                processed += len(batch)
                logger.info(f"Processed {processed}/{len(all_records)}...")
                time.sleep(2) # Conservative pause for government API

        return {
            "statusCode": 200,
            "body": json.dumps({"processed": processed, "updated": updated})
        }
    finally:
        conn.close()
