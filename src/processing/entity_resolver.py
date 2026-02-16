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
import requests
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
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-3-haiku-20240307-v1:0")

SAM_API_BASE_URL = "https://api.sam.gov/entity-information/v3/entities"
SAM_API_KEY_SECRET_ARN = os.environ.get("SAM_API_KEY_SECRET_ARN")
SAM_PROXY_LAMBDA_NAME = os.environ.get("SAM_PROXY_LAMBDA_NAME")

# Clients (initialized lazily)
bedrock = None
lambda_client = None
dynamodb = None
cache_table = None


def get_bedrock_client():
    global bedrock
    if bedrock is None:
        bedrock = boto3.client(service_name="bedrock-runtime")
    return bedrock


def get_lambda_client():
    global lambda_client
    if lambda_client is None:
        lambda_client = boto3.client(service_name="lambda")
    return lambda_client


def get_cache_table():
    global dynamodb, cache_table
    if cache_table is None:
        dynamodb = boto3.resource("dynamodb")
        cache_table = dynamodb.Table(DYNAMODB_CACHE_TABLE)
    return cache_table


# In-memory cache for fuzzy matching (persists across warm Lambda invocations)
CANONICAL_NAMES_CACHE = None
CACHE_EXPIRY = None

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


def refresh_canonical_names_cache(conn):
    """Fetches all canonical names from the database for fuzzy matching."""
    global CANONICAL_NAMES_CACHE, CACHE_EXPIRY

    # Refresh cache every 15 minutes
    if CANONICAL_NAMES_CACHE is not None and CACHE_EXPIRY > datetime.now():
        return CANONICAL_NAMES_CACHE

    logger.info("Refreshing canonical names cache...")
    with conn.cursor() as cur:
        cur.execute("SELECT canonical_name FROM vendors")
        CANONICAL_NAMES_CACHE = [row[0] for row in cur.fetchall()]
        CACHE_EXPIRY = datetime.now() + timedelta(minutes=15)

    return CANONICAL_NAMES_CACHE

# -----------------------------------------------------------------------------
# Entity Resolution Logic (4-Tier)
# -----------------------------------------------------------------------------


def get_sam_entity(uei=None, vendor_name=None):
    """
    Fetches entity data from SAM.gov API via a proxy Lambda.
    This bypasses VPC internet restrictions.
    """
    if not SAM_PROXY_LAMBDA_NAME:
        logger.warning(
            "SAM_PROXY_LAMBDA_NAME not configured. Skipping SAM Tier.")
        return None

    payload = {
        "ueiSAM": uei,
        "entityName": vendor_name if not uei else None
    }

    try:
        response = get_lambda_client().invoke(
            FunctionName=SAM_PROXY_LAMBDA_NAME,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )

        result = json.loads(response['Payload'].read())

        if result.get('statusCode') == 200:
            body = json.loads(result.get('body', '{}'))
            entity_data = body.get('entityData', [])
            if entity_data:
                # Return the first high-confidence match
                entity = entity_data[0]
                return {
                    "canonical_name": entity.get('entityRegistration', {}).get('legalBusinessName'),
                    "uei": entity.get('entityRegistration', {}).get('ueiSAM'),
                    "duns": entity.get('entityRegistration', {}).get('duns'),
                    "confidence": 1.0
                }
    except Exception as e:
        logger.error(f"SAM API Proxy call failed: {e}")

    return None


def resolve_vendor(vendor_name, duns=None, uei=None, conn=None):
    """
    6-Tier Resolution Strategy:
    1. Check SAM entity API
    2. DUNS/UEI exact match (RDS)
    3. Canonical name exact match (RDS)
    4. DynamoDB cache lookup
    5. Fuzzy matching (rapidfuzz)
    6. Bedrock LLM Fallback
    """

    # Tier 1: SAM entity API match
    sam_result = get_sam_entity(uei=uei, vendor_name=vendor_name)
    if sam_result:
        canonical_name = sam_result['canonical_name']
        sam_uei = sam_result['uei']
        sam_duns = sam_result['duns']

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id FROM vendors WHERE uei = %s OR canonical_name = %s LIMIT 1",
                (sam_uei, canonical_name)
            )
            result = cur.fetchone()

            if result:
                return result['id'], canonical_name, "SAM_API_MATCH", 1.0
            else:
                # Create new vendor from SAM data
                vendor_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO vendors (id, canonical_name, duns, uei, resolved_by_llm, resolution_confidence)
                    VALUES (%s, %s, %s, %s, FALSE, 1.0)
                    ON CONFLICT (canonical_name) DO UPDATE SET 
                        uei = EXCLUDED.uei,
                        duns = EXCLUDED.duns,
                        updated_at = NOW()
                    RETURNING id
                    """,
                    (vendor_id, canonical_name, sam_duns, sam_uei)
                )
                res = cur.fetchone()
                if res:
                    vendor_id = res['id']
                return vendor_id, canonical_name, "SAM_API_MATCH", 1.0

    # Tier 2: DUNS/UEI exact match
    if duns or uei:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, canonical_name FROM vendors WHERE duns = %s OR uei = %s LIMIT 1",
                (duns, uei)
            )
            result = cur.fetchone()
            if result:
                return result['id'], result['canonical_name'], "DUNS_UEI_MATCH", 1.0

    # Tier 3: Canonical name exact match
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT id, canonical_name FROM vendors WHERE canonical_name = %s LIMIT 1",
            (vendor_name,)
        )
        result = cur.fetchone()
        if result:
            return result['id'], result['canonical_name'], "EXACT_NAME_MATCH", 1.0

    # Tier 4: DynamoDB Cache (Previous resolution results for this messy name)
    try:
        cache_resp = get_cache_table().get_item(
            Key={'vendor_name': vendor_name})
        if 'Item' in cache_resp:
            item = cache_resp['Item']
            return item['vendor_id'], item['canonical_name'], "CACHE_MATCH", float(item.get('confidence', 0.9))
    except Exception as e:
        logger.warning(f"DynamoDB cache lookup failed: {e}")

    # Tier 5: Fuzzy Matching
    canonical_names = refresh_canonical_names_cache(conn)
    if canonical_names:
        match = process.extractOne(
            vendor_name, canonical_names, scorer=fuzz.WRatio)
        if match and match[1] >= 90:  # High threshold for automatic fuzzy matching
            matched_name = match[0]
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT id FROM vendors WHERE canonical_name = %s LIMIT 1",
                    (matched_name,)
                )
                res = cur.fetchone()
                if res:
                    vendor_id = res['id']
                    # Store in cache for next time
                    update_cache(vendor_name, matched_name,
                                 vendor_id, float(match[1])/100.0)
                    return vendor_id, matched_name, "FUZZY_MATCH", float(match[1])/100.0

    # Tier 6: Bedrock LLM Fallback
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
                    ON CONFLICT (canonical_name) DO UPDATE SET 
                        updated_at = NOW()
                    RETURNING id
                    """,
                    (vendor_id, canonical_name, duns, uei)
                )
                res = cur.fetchone()
                if res:
                    vendor_id = res['id']
            except Exception as e:
                logger.error(f"Failed to create vendor {canonical_name}: {e}")
                # Fallback to lookup one more time in case of race condition or other constraint failure
                cur.execute(
                    "SELECT id FROM vendors WHERE canonical_name = %s OR (uei = %s AND uei IS NOT NULL) OR (duns = %s AND duns IS NOT NULL) LIMIT 1",
                    (canonical_name, uei, duns)
                )
                result = cur.fetchone()
                if result:
                    vendor_id = result['id']

    # Update DynamoDB Cache
    update_cache(vendor_name, canonical_name, vendor_id, 0.95)

    return vendor_id, canonical_name, "LLM_RESOLUTION", 0.95


def update_cache(vendor_name, canonical_name, vendor_id, confidence):
    """Updates the DynamoDB entity resolution cache."""
    try:
        get_cache_table().put_item(Item={
            'vendor_name': vendor_name,
            'canonical_name': canonical_name,
            'vendor_id': vendor_id,
            'confidence': str(confidence),
            'ttl': int(time.time() + (90 * 24 * 60 * 60))  # 90 days
        })
    except Exception as e:
        logger.warning(f"Failed to update DynamoDB cache: {e}")


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
            response = get_bedrock_client().invoke_model(
                body=body, modelId=BEDROCK_MODEL_ID)
            response_body = json.loads(response.get("body").read())
            return response_body["content"][0]["text"].strip()
        except Exception as e:
            if "ThrottlingException" in str(e) or "Too many requests" in str(e):
                # More aggressive backoff for Bedrock
                wait_time = (2 ** (attempt + 2)) + random.uniform(0, 1)
                logger.warning(f"Bedrock throttled. Retrying in {
                               wait_time:.2f}s (Attempt {attempt + 1}/{max_retries})...")
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
            vendor_id, canonical_name, method, confidence = resolve_vendor(
                vendor_name, duns, uei, conn)

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
                    logger.error(f"Failed to insert contract {
                                 contract_data.get('Award ID')}: {e}")

        return {
            "statusCode": 200,
            "body": json.dumps({"processed": processed_count})
        }
    finally:
        conn.close()
