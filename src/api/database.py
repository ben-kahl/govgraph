import os
import json
import time
import boto3
import psycopg2
from psycopg2.extras import RealDictCursor
from neo4j import GraphDatabase
import logging

logger = logging.getLogger(__name__)

# Postgres Config
DB_HOST = os.environ.get("DB_HOST")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN")

# Neo4j Config
NEO4J_SECRET_ARN = os.environ.get("NEO4J_SECRET_ARN")

# Credential cache TTL — refresh Secrets Manager values once per hour so
# rotated credentials are picked up without requiring a Lambda cold start.
_CRED_TTL = 3600

_db_creds = None
_db_creds_ts: float = 0.0

_neo4j_creds = None
_neo4j_creds_ts: float = 0.0
_neo4j_driver = None


def get_secret(secret_arn):
    if not secret_arn:
        return {}
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_arn)
    return json.loads(response['SecretString'])


def get_pg_connection():
    global _db_creds, _db_creds_ts
    if _db_creds is None or (time.time() - _db_creds_ts) > _CRED_TTL:
        _db_creds = get_secret(DB_SECRET_ARN)
        _db_creds_ts = time.time()
        logger.debug("database: pg credentials refreshed from Secrets Manager")

    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=_db_creds.get('username', DB_USER),
        password=_db_creds['password'],
        connect_timeout=5,
        cursor_factory=RealDictCursor
    )


def get_neo4j_driver():
    global _neo4j_creds, _neo4j_creds_ts, _neo4j_driver
    creds_expired = (time.time() - _neo4j_creds_ts) > _CRED_TTL
    if _neo4j_driver is None or creds_expired:
        if creds_expired and _neo4j_driver is not None:
            _neo4j_driver.close()
            _neo4j_driver = None

        _neo4j_creds = get_secret(NEO4J_SECRET_ARN)
        _neo4j_creds_ts = time.time()
        logger.debug("database: neo4j credentials refreshed from Secrets Manager")

        uri = _neo4j_creds.get('uri') or _neo4j_creds.get('NEO4J_URI')
        user = _neo4j_creds.get(
            'username') or _neo4j_creds.get('NEO4J_USERNAME')
        password = _neo4j_creds.get(
            'password') or _neo4j_creds.get('NEO4J_PASSWORD')

        if uri and user and password:
            _neo4j_driver = GraphDatabase.driver(uri, auth=(user, password))
        else:
            logger.error("Neo4j credentials incomplete")

    return _neo4j_driver


def close_drivers():
    global _neo4j_driver
    if _neo4j_driver:
        _neo4j_driver.close()
        _neo4j_driver = None
