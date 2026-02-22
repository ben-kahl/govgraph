import os
import json
import boto3
import psycopg2
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DB_HOST = os.environ.get("DB_HOST")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN")

def get_secret(secret_arn):
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_arn)
    return json.loads(response['SecretString'])

def lambda_handler(event, context):
    """Destructive admin task: Resets the database schema."""
    if event.get('confirm_reset') != "YES_DELETE_EVERYTHING":
        return {
            'statusCode': 400,
            'body': "Safety check failed. Must pass {'confirm_reset': 'YES_DELETE_EVERYTHING'}"
        }

    conn = None
    try:
        db_creds = get_secret(DB_SECRET_ARN)
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=db_creds.get('username', DB_USER),
            password=db_creds['password'],
            connect_timeout=10
        )
        conn.autocommit = True
        
        with conn.cursor() as cur:
            tables = [
                "contracts", "subcontracts", "vendors", "agencies",
                "vendor_analytics", "neo4j_sync_status", "entity_resolution_log"
            ]
            for table in tables:
                logger.info(f"ADMIN: Dropping table {table}")
                cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        
        return {'statusCode': 200, 'body': "Database reset successfully."}
    except Exception as e:
        logger.error(f"ADMIN: Reset failed: {str(e)}")
        return {'statusCode': 500, 'body': str(e)}
    finally:
        if conn: conn.close()
