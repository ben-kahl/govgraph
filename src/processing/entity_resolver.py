import os
import json
import uuid
import boto3
import psycopg2
import logging
import time
import random
from datetime import datetime, date, timedelta
from rapidfuzz import process, fuzz
from psycopg2.extras import RealDictCursor

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configuration
DB_HOST = os.environ.get("DB_HOST")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN")
DYNAMODB_CACHE_TABLE = os.environ.get("DYNAMODB_CACHE_TABLE")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-haiku-4-5-20251001-v1:0")

# Clients
bedrock = boto3.client(service_name="bedrock-runtime")
dynamodb = boto3.resource("dynamodb")
cache_table = dynamodb.Table(DYNAMODB_CACHE_TABLE)

# -----------------------------------------------------------------------------
# Database Utilities
# -----------------------------------------------------------------------------
def get_secret(secret_arn):
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_arn)
    return json.loads(response['SecretString'])

def get_db_connection():
    db_creds = get_secret(DB_SECRET_ARN)
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=db_creds.get('username', DB_USER),
        password=db_creds['password'],
        connect_timeout=10
    )

# -----------------------------------------------------------------------------
# Entity Resolution Logic (4-Tier)
# -----------------------------------------------------------------------------

def resolve_vendor(vendor_name, duns=None, uei=None, conn=None):
    """
    4-Tier Resolution Strategy:
    1. DUNS/UEI exact match (RDS)
    2. Canonical name exact match (RDS)
    3. DynamoDB cache lookup
    4. Fuzzy matching / Bedrock fallback
    """
    
    # Tier 1: DUNS/UEI exact match
    if duns or uei:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, canonical_name FROM vendors WHERE duns = %s OR uei = %s LIMIT 1",
                (duns, uei)
            )
            result = cur.fetchone()
            if result:
                return result['id'], result['canonical_name'], "DUNS_UEI_MATCH", 1.0

    # Tier 2: Canonical name exact match
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT id, canonical_name FROM vendors WHERE canonical_name = %s LIMIT 1",
            (vendor_name,)
        )
        result = cur.fetchone()
        if result:
            return result['id'], result['canonical_name'], "EXACT_NAME_MATCH", 1.0

    # Tier 3: DynamoDB Cache
    try:
        cache_resp = cache_table.get_item(Key={'vendor_name': vendor_name})
        if 'Item' in cache_resp:
            item = cache_resp['Item']
            return item['vendor_id'], item['canonical_name'], "CACHE_MATCH", float(item.get('confidence', 0.9))
    except Exception as e:
        logger.warning(f"DynamoDB cache lookup failed: {e}")

    # Tier 4: Bedrock LLM Fallback
    canonical_name = call_bedrock_standardization_with_retry(vendor_name)
    
    # After LLM, check if the NEW canonical name exists in DB
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT id, canonical_name FROM vendors WHERE canonical_name = %s LIMIT 1",
            (canonical_name,)
        )
        result = cur.fetchone()
        
        if result:
            vendor_id = result['id']
        else:
            # Create new vendor if not found
            vendor_id = str(uuid.uuid4())
            try:
                cur.execute(
                    """
                    INSERT INTO vendors (id, canonical_name, duns, uei, resolved_by_llm, resolution_confidence)
                    VALUES (%s, %s, %s, %s, TRUE, 0.95)
                    ON CONFLICT (canonical_name) DO UPDATE SET updated_at = NOW()
                    RETURNING id
                    """,
                    (vendor_id, canonical_name, duns, uei)
                )
                res = cur.fetchone()
                if res:
                    vendor_id = res[0]
            except Exception as e:
                logger.error(f"Failed to create vendor {canonical_name}: {e}")
                # Fallback to lookup one more time in case of race condition
                cur.execute("SELECT id FROM vendors WHERE canonical_name = %s", (canonical_name,))
                result = cur.fetchone()
                if result:
                    vendor_id = result[0]

    # Update DynamoDB Cache
    try:
        cache_table.put_item(Item={
            'vendor_name': vendor_name,
            'canonical_name': canonical_name,
            'vendor_id': vendor_id,
            'confidence': '0.95',
            'ttl': int(time.time() + (90 * 24 * 60 * 60)) # 90 days
        })
    except Exception as e:
        logger.warning(f"Failed to update DynamoDB cache: {e}")

    return vendor_id, canonical_name, "LLM_RESOLUTION", 0.95

def call_bedrock_standardization_with_retry(messy_name, max_retries=3):
    """Calls Bedrock with exponential backoff to handle throttling."""
    prompt = f"""
    Standardize this company name to its canonical legal form.
    Input: "{messy_name}"
    Rules: Return ONLY the name. Expand abbreviations (Corp -> Corporation).
    Name:"""

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 100,
        "messages": [{"role": "user", "content": prompt}]
    })

    for attempt in range(max_retries):
        try:
            response = bedrock.invoke_model(body=body, modelId=BEDROCK_MODEL_ID)
            response_body = json.loads(response.get("body").read())
            return response_body["content"][0]["text"].strip()
        except Exception as e:
            if "ThrottlingException" in str(e) or "Too many requests" in str(e):
                wait_time = (2 ** attempt) + random.random()
                logger.warning(f"Bedrock throttled. Retrying in {wait_time:.2f}s...")
                time.sleep(wait_time)
                continue
            logger.error(f"Bedrock failed: {e}")
            break
            
    return messy_name

# -----------------------------------------------------------------------------
# Main Handler
# -----------------------------------------------------------------------------

def lambda_handler(event, context):
    logger.info(f"Processing batch of {len(event['Records'])} messages")
    
    conn = get_db_connection()
    conn.autocommit = True
    
    processed_count = 0
    
    try:
        for record in event['Records']:
            contract_data = json.loads(record['body'])
            
            vendor_name = contract_data.get('Recipient Name')
            duns = contract_data.get('Recipient DUNS')
            uei = contract_data.get('Recipient UEI')
            
            if not vendor_name:
                continue
                
            # 1. Resolve Vendor
            vendor_id, canonical_name, method, confidence = resolve_vendor(vendor_name, duns, uei, conn)
            
            # 2. Store Contract
            with conn.cursor() as cur:
                contract_uuid = str(uuid.uuid4())
                signed_date = contract_data.get('Start Date')
                if not signed_date:
                    signed_date = date.today().strftime("%Y-%m-%d")
                
                try:
                    # Added signed_date to ON CONFLICT to match partitioned index
                    cur.execute(
                        """
                        INSERT INTO contracts (
                            id, contract_id, vendor_id, description, 
                            obligated_amount, signed_date, award_type, 
                            created_at, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                        ON CONFLICT (contract_id, signed_date) DO UPDATE SET updated_at = NOW()
                        """,
                        (
                            contract_uuid,
                            contract_data.get('Award ID'),
                            vendor_id,
                            f"Contract for {canonical_name}",
                            contract_data.get('Award Amount', 0),
                            signed_date,
                            contract_data.get('Award Type')
                        )
                    )
                    processed_count += 1
                except Exception as e:
                    logger.error(f"Failed to insert contract {contract_data.get('Award ID')}: {e}")
                    
        return {
            "statusCode": 200,
            "body": json.dumps({"processed": processed_count})
        }
    finally:
        conn.close()