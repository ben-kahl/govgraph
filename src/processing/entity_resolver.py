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
    Fetches entity data directly from SAM.gov API.
    """
    if not SAM_API_KEY_SECRET_ARN:
        logger.warning(
            "SAM_API_KEY_SECRET_ARN not configured. Skipping SAM Tier.")
        return None

    try:
        secrets = get_secret(SAM_API_KEY_SECRET_ARN)
        api_key = secrets.get('api_key')

        params = {"api_key": api_key}
        if uei:
            params["ueiSAM"] = uei
        elif vendor_name:
            params["entityName"] = vendor_name

        url = SAM_API_BASE_URL
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            body = response.json()
            entity_data = body.get('entityData', [])
            if entity_data:
                entity = entity_data[0]
                return {
                    "canonical_name": entity.get('entityRegistration', {}).get('legalBusinessName'),
                    "uei": entity.get('entityRegistration', {}).get('ueiSAM'),
                    "duns": entity.get('entityRegistration', {}).get('duns'),
                    "confidence": 1.0
                }
    except Exception as e:
        logger.error(f"SAM API call failed: {e}")

    return None


def resolve_vendor(vendor_name, duns=None, uei=None, conn=None):
    """
    6-Tier Resolution Strategy:
    1. DynamoDB cache lookup (Fast-path for previously resolved messy names)
    2. DUNS/UEI exact match (RDS)
    3. Canonical name exact match (RDS)
    4. SAM entity API match (External truth)
    5. Fuzzy matching (rapidfuzz)
    6. Bedrock LLM Fallback
    """

    # Tier 1: DynamoDB Cache
    try:
        cache_resp = get_cache_table().get_item(
            Key={'vendor_name': vendor_name})
        if 'Item' in cache_resp:
            item = cache_resp['Item']
            # Quick verification that the vendor still exists in RDS
            vendor_id = item['vendor_id']
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id FROM vendors WHERE id = %s LIMIT 1", (vendor_id,))
                if cur.fetchone():
                    logger.info(f"RESOLVE: Cache Hit for {vendor_name}")
                    return vendor_id, item['canonical_name'], "CACHE_MATCH", float(item.get('confidence', 0.9))
    except Exception as e:
        logger.warning(f"DynamoDB cache lookup failed: {e}")

    # Tier 2: DUNS/UEI exact match
    if duns or uei:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, canonical_name FROM vendors WHERE duns = %s OR uei = %s LIMIT 1",
                (duns, uei)
            )
            result = cur.fetchone()
            if result:
                logger.info(f"RESOLVE: ID Match for {vendor_name}")
                return result['id'], result['canonical_name'], "DUNS_UEI_MATCH", 1.0

    # Tier 3: Canonical name exact match
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT id, canonical_name FROM vendors WHERE canonical_name = %s LIMIT 1",
            (vendor_name,)
        )
        result = cur.fetchone()
        if result:
            logger.info(f"RESOLVE: Exact Name Match for {vendor_name}")
            return result['id'], result['canonical_name'], "EXACT_NAME_MATCH", 1.0

    # Tier 4: SAM entity API match
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
                logger.info(f"RESOLVE: SAM Match (Existing) for {vendor_name}")
                return result['id'], canonical_name, "SAM_API_MATCH", 1.0
            else:
                # Create new vendor from SAM data
                vendor_id = str(uuid.uuid4())
                with conn.cursor(cursor_factory=RealDictCursor) as insert_cur:
                    insert_cur.execute(
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
                    res = insert_cur.fetchone()
                    if res:
                        vendor_id = res['id']
                logger.info(f"RESOLVE: SAM Match (New) for {vendor_name}")
                return vendor_id, canonical_name, "SAM_API_MATCH", 1.0

    # Tier 5: Fuzzy Matching
    canonical_names = refresh_canonical_names_cache(conn)
    logger.info(f"RESOLVE: Fuzzy Tier - {len(canonical_names) if canonical_names else 0} names in cache")
    if canonical_names:
        match = process.extractOne(
            vendor_name, canonical_names, scorer=fuzz.WRatio)
        logger.info(f"RESOLVE: Fuzzy match result for {vendor_name}: {match}")
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
                    logger.info(f"RESOLVE: Fuzzy Match Hit for {vendor_name}")
                    return vendor_id, matched_name, "FUZZY_MATCH", float(match[1])/100.0

    # Tier 6: Bedrock LLM Fallback
    logger.info(f"RESOLVE: LLM Fallback for {vendor_name}")
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
            vendor_id = None
            try:
                new_vendor_id = str(uuid.uuid4())
                with conn.cursor(cursor_factory=RealDictCursor) as insert_cur:
                    insert_cur.execute(
                        """
                        INSERT INTO vendors (id, canonical_name, duns, uei, resolved_by_llm, resolution_confidence)
                        VALUES (%s, %s, %s, %s, TRUE, 0.95)
                        ON CONFLICT (canonical_name) DO UPDATE SET 
                            updated_at = NOW()
                        RETURNING id
                        """,
                        (new_vendor_id, canonical_name, duns, uei)
                    )
                    res = insert_cur.fetchone()
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
            if not vendor_id:
                logger.error(
                    "LLM resolution returned a canonical name but vendor persistence failed; skipping cache update."
                )
                return None, canonical_name, "LLM_RESOLUTION_FAILED", 0.0

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


def resolve_agency(agency_name, agency_code, parent_agency_id=None, conn=None):
    """
    Resolves an agency by code, creating it if it doesn't exist.
    Supports parent/child relationships.
    """
    if not agency_code:
        return None

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT id FROM agencies WHERE agency_code = %s LIMIT 1",
            (agency_code,)
        )
        result = cur.fetchone()
        if result:
            return result['id']

        # Create new agency
        agency_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO agencies (id, agency_code, agency_name, parent_agency_id, updated_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (agency_code) DO UPDATE SET 
                agency_name = EXCLUDED.agency_name,
                parent_agency_id = COALESCE(agencies.parent_agency_id, EXCLUDED.parent_agency_id),
                updated_at = NOW()
            RETURNING id
            """,
            (agency_id, agency_code, agency_name, parent_agency_id)
        )
        res = cur.fetchone()
        return res['id'] if res else agency_id


def lambda_handler(event, context):
    logger.info(f"Processing batch of {len(event['Records'])} messages")

    conn = get_db_connection()
    conn.autocommit = True

    processed_count = 0

    try:
        for record in event['Records']:
            raw_payload = json.loads(record['body'])
            msg_type = raw_payload.get('type', 'prime')
            contract_data = raw_payload.get('data', raw_payload)

            if msg_type == "prime":
                processed_count += process_prime_award(contract_data, conn)
            elif msg_type == "subaward":
                processed_count += process_sub_award(contract_data, conn)

        return {
            "statusCode": 200,
            "body": json.dumps({"processed": processed_count})
        }
    finally:
        conn.close()


def process_prime_award(contract_data, conn):
    """Processes a prime award record."""
    usaspending_id = contract_data.get('Award ID')
    vendor_name = contract_data.get('Recipient Name')
    duns = contract_data.get('Recipient DUNS')
    uei = contract_data.get('Recipient UEI')

    if not usaspending_id:
        return 0

    # 1. Insert into Raw Contracts (Landing Zone)
    raw_contract_id = str(uuid.uuid4())
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO raw_contracts (id, usaspending_id, raw_payload, ingested_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (usaspending_id) DO UPDATE SET 
                raw_payload = EXCLUDED.raw_payload,
                ingested_at = NOW()
            RETURNING id
            """,
            (raw_contract_id, usaspending_id, json.dumps(contract_data))
        )
        res = cur.fetchone()
        if res:
            raw_contract_id = res[0]

    # 2. Resolve Agency Hierarchy
    # Awarding Agency (Top Tier)
    agency_id = resolve_agency(
        contract_data.get('Awarding Agency'),
        contract_data.get('Awarding Agency Code'),
        conn=conn
    )
    # Awarding Sub Agency
    sub_agency_id = resolve_agency(
        contract_data.get('Awarding Sub Agency'),
        contract_data.get('Awarding Sub Agency Code'),
        parent_agency_id=agency_id,
        conn=conn
    )

    # Funding Agency
    funding_agency_id = resolve_agency(
        contract_data.get('Funding Agency'),
        contract_data.get('Funding Agency Code'),
        conn=conn
    )
    funding_sub_agency_id = resolve_agency(
        contract_data.get('Funding Sub Agency'),
        contract_data.get('Funding Sub Agency Code'),
        parent_agency_id=funding_agency_id,
        conn=conn
    )

    # 3. Resolve Vendor
    vendor_id, canonical_name, method, confidence = resolve_vendor(
        vendor_name, duns, uei, conn)

    # 4. Store Contract
    with conn.cursor() as cur:
        contract_uuid = str(uuid.uuid4())
        signed_date = contract_data.get('Start Date')
        if not signed_date:
            signed_date = date.today().strftime("%Y-%m-%d")

        # Enhanced description
        raw_desc = contract_data.get('Description', 'No description provided')
        formatted_desc = f"Vendor: {canonical_name} | {raw_desc}"

        try:
            cur.execute(
                """
                INSERT INTO contracts (
                    id, contract_id, vendor_id, agency_id, awarding_sub_agency_id,
                    funding_agency_id, funding_sub_agency_id, raw_contract_id,
                    description, obligated_amount, signed_date, award_type, 
                    created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (contract_id, signed_date) DO UPDATE SET 
                    vendor_id = EXCLUDED.vendor_id,
                    agency_id = EXCLUDED.agency_id,
                    awarding_sub_agency_id = EXCLUDED.awarding_sub_agency_id,
                    funding_agency_id = EXCLUDED.funding_agency_id,
                    funding_sub_agency_id = EXCLUDED.funding_sub_agency_id,
                    obligated_amount = EXCLUDED.obligated_amount,
                    description = EXCLUDED.description,
                    award_type = EXCLUDED.award_type,
                    updated_at = NOW()
                """,
                (
                    contract_uuid, usaspending_id, vendor_id, agency_id, sub_agency_id,
                    funding_agency_id, funding_sub_agency_id, raw_contract_id,
                    formatted_desc, contract_data.get('Award Amount', 0),
                    signed_date, contract_data.get('Contract Award Type')
                )
            )
            cur.execute("UPDATE raw_contracts SET processed = TRUE WHERE id = %s", (raw_contract_id,))
            return 1
        except Exception as e:
            logger.error(f"Failed to insert prime contract {usaspending_id}: {e}")
            cur.execute("UPDATE raw_contracts SET processing_errors = %s WHERE id = %s", (str(e), raw_contract_id))
            return 0


def process_sub_award(contract_data, conn):
    """Processes a sub-award record and links it to prime awards."""
    sub_award_id = contract_data.get('Sub-Award ID')
    prime_id = contract_data.get('Prime Award ID')
    sub_vendor_name = contract_data.get('Sub-Awardee Name')
    sub_uei = contract_data.get('Sub-Recipient UEI')
    prime_uei = contract_data.get('Prime Award Recipient UEI')

    if not sub_award_id:
        return 0

    # 1. Resolve Sub-contractor Vendor
    sub_vendor_id, _, _, _ = resolve_vendor(sub_vendor_name, uei=sub_uei, conn=conn)

    # 2. Resolve Prime Vendor
    prime_vendor_id, _, _, _ = resolve_vendor(contract_data.get('Prime Recipient Name'), uei=prime_uei, conn=conn)

    # 3. Resolve Agency (limited for sub-awards in USAspending API)
    agency_id = resolve_agency(
        contract_data.get('Awarding Agency'),
        contract_data.get('Awarding Agency Code'),
        conn=conn
    )

    # 4. Persistence
    with conn.cursor() as cur:
        try:
            # First find the prime contract record in our DB if it exists
            cur.execute("SELECT id FROM contracts WHERE contract_id = %s LIMIT 1", (prime_id,))
            prime_contract_row = cur.fetchone()
            prime_contract_uuid = prime_contract_row[0] if prime_contract_row else None

            sub_uuid = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO subcontracts (
                    id, prime_contract_id, prime_vendor_id, subcontractor_vendor_id,
                    subcontract_amount, subcontract_description, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    sub_uuid, prime_contract_uuid, prime_vendor_id, sub_vendor_id,
                    contract_data.get('Sub-Award Amount', 0),
                    contract_data.get('Sub-Award Description')
                )
            )
            return 1
        except Exception as e:
            logger.error(f"Failed to insert sub-award {sub_award_id}: {e}")
            return 0
