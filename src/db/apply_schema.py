import os
import json
import boto3
import psycopg2
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configuration
DB_HOST = os.environ.get("DB_HOST")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN")

def get_secret(secret_arn):
    """Retrieve secret from AWS Secrets Manager."""
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_arn)
    return json.loads(response['SecretString'])

def get_pg_connection():
    """Connect to PostgreSQL using credentials from Secrets Manager."""
    db_creds = get_secret(DB_SECRET_ARN)
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=db_creds.get('username', DB_USER),
        password=db_creds['password']
    )
    return conn

def lambda_handler(event, context):
    """
    Lambda handler to apply the database schema.
    Reads schema.sql from the same directory and executes it.
    """
    conn = None
    try:
        logger.info("Connecting to database...")
        conn = get_pg_connection()
        conn.autocommit = True  # Allow creating tables/types
        
        # Read schema file
        # Note: In Lambda, the file must be packaged alongside this script
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        logger.info(f"Reading schema from {schema_path}...")
        
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
            
        logger.info("Applying schema...")
        with conn.cursor() as cur:
            cur.execute(schema_sql)
            
        logger.info("Schema applied successfully.")
        
        return {
            'statusCode': 200,
            'body': json.dumps('Schema applied successfully.')
        }
        
    except Exception as e:
        logger.error(f"Schema application failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Schema application failed: {str(e)}')
        }
        
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Local testing (requires env vars set manually)
    logging.basicConfig(level=logging.INFO)
    lambda_handler({}, {})
