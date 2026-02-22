import json
import logging
import time
from psycopg2.extras import RealDictCursor

# Correct imports for Lambda environment
from entity_resolver import (
    get_db_connection, 
    process_prime_award, 
    process_sub_award
)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Reprocesses all archived contracts from raw_contracts table.
    Useful for schema changes or backfilling missing fields.
    """
    limit = event.get('limit', 5000)
    
    conn = get_db_connection()
    conn.autocommit = True

    processed_count = 0

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Fetch all raw prime contracts
            logger.info(f"Fetching up to {limit} raw prime contracts for reprocessing...")
            cur.execute("""
                SELECT raw_payload 
                FROM raw_contracts 
                ORDER BY ingested_at DESC 
                LIMIT %s
            """, (limit,))
            
            raw_records = cur.fetchall()
            logger.info(f"Reprocessing {len(raw_records)} prime records...")
            
            for record in raw_records:
                payload = record['raw_payload']
                # The payload in raw_contracts is the "data" portion of our new SQS message
                # or the old direct payload. process_prime_award handles it.
                success = process_prime_award(payload, conn)
                processed_count += success
                
                if processed_count % 100 == 0:
                    logger.info(f"Progress: {processed_count} prime contracts reprocessed.")

            # 2. Note on Sub-Awards: 
            # In our current setup, sub-awards were NOT being archived in raw_contracts 
            # before this update (they were ignored). 
            # If you want to reprocess sub-awards, they will need to be ingested 
            # by running the Scraper for previous dates.
            
        logger.info(f"Reprocessing complete. Total processed: {processed_count}")
        return {
            "statusCode": 200,
            "body": json.dumps({"reprocessed_prime": processed_count})
        }
    finally:
        conn.close()
