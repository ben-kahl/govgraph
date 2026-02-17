import os
import json
import boto3
import psycopg2
from neo4j import GraphDatabase
from psycopg2.extras import RealDictCursor

# Configuration
DB_HOST = os.environ.get("DB_HOST")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN")
NEO4J_SECRET_ARN = os.environ.get("NEO4J_SECRET_ARN")


def get_secret(secret_arn):
    """Retrieve secret from AWS Secrets Manager."""
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_arn)
    return json.loads(response['SecretString'])


def get_pg_connection():
    """Connect to PostgreSQL using credentials from Secrets Manager."""
    db_creds = get_secret(DB_SECRET_ARN)
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=db_creds.get('username', DB_USER),
        password=db_creds['password']
    )


def get_neo4j_driver():
    """Connect to Neo4j using credentials from Secrets Manager."""
    neo4j_creds = get_secret(NEO4J_SECRET_ARN)
    uri = neo4j_creds['NEO4J_URI']
    user = neo4j_creds['NEO4J_USERNAME']
    password = neo4j_creds['NEO4J_PASSWORD']
    return GraphDatabase.driver(uri, auth=(user, password))


def sync_agencies(pg_conn, neo4j_session):
    print("Syncing Agencies...")
    with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Find unsynced agencies
        cur.execute("""
            SELECT a.* 
            FROM agencies a
            LEFT JOIN neo4j_sync_status s 
                ON s.entity_type = 'agency' AND s.entity_id = a.id
            WHERE s.id IS NULL OR s.sync_status != 'synced'
        """)
        agencies = cur.fetchall()

        for agency in agencies:
            query = """
            MERGE (a:Agency {id: $id})
            SET a.agencyCode = $code,
                a.agencyName = $name,
                a.department = $dept,
                a.agencyType = $type,
                a.syncedAt = datetime()
            """
            neo4j_session.run(query,
                              id=str(agency['id']),
                              code=agency['agency_code'],
                              name=agency['agency_name'],
                              dept=agency['department'],
                              type=agency['agency_type'])

            # Update sync status
            mark_synced(pg_conn, 'agency', agency['id'])
    print(f"Synced {len(agencies)} agencies.")


def sync_vendors(pg_conn, neo4j_session):
    print("Syncing High-Value Vendors (>$1M)...")
    with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Calculate total value and only sync vendors > $1M to stay in free tier
        cur.execute("""
            SELECT v.*, SUM(c.obligated_amount) as total_value
            FROM vendors v
            JOIN contracts c ON v.id = c.vendor_id
            LEFT JOIN neo4j_sync_status s 
                ON s.entity_type = 'vendor' AND s.entity_id = v.id
            WHERE (s.id IS NULL OR s.sync_status != 'synced')
            GROUP BY v.id
            HAVING SUM(c.obligated_amount) >= 1000000
        """)
        vendors = cur.fetchall()

        for vendor in vendors:
            query = """
            MERGE (v:Vendor {id: $id})
            SET v.canonicalName = $name,
                v.duns = $duns,
                v.uei = $uei,
                v.state = $state,
                v.city = $city,
                v.totalContractValue = $total_value,
                v.syncedAt = datetime()
            """
            neo4j_session.run(query,
                              id=str(vendor['id']),
                              name=vendor['canonical_name'],
                              duns=vendor['duns'],
                              uei=vendor['uei'],
                              state=vendor['state'],
                              city=vendor['city'],
                              total_value=float(vendor['total_value']))

            mark_synced(pg_conn, 'vendor', vendor['id'])
    print(f"Synced {len(vendors)} high-value vendors.")


def sync_contracts(pg_conn, neo4j_session):
    print("Syncing Contracts for High-Value Vendors...")
    with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Only sync contracts for vendors that have been synced to Neo4j
        cur.execute("""
            SELECT c.* 
            FROM contracts c
            JOIN neo4j_sync_status s_vendor 
                ON s_vendor.entity_id = c.vendor_id AND s_vendor.entity_type = 'vendor'
            LEFT JOIN neo4j_sync_status s 
                ON s.entity_type = 'contract' AND s.entity_id = c.id
            WHERE (s.id IS NULL OR s.sync_status != 'synced')
              AND s_vendor.sync_status = 'synced'
        """)
        contracts = cur.fetchall()

        for contract in contracts:
            # Create Contract Node
            query_node = """
            MERGE (c:Contract {id: $id})
            SET c.contractId = $contract_id,
                c.description = $desc,
                c.obligatedAmount = $amount,
                c.signedDate = date($signed_date),
                c.syncedAt = datetime()
            """
            neo4j_session.run(query_node,
                              id=str(contract['id']),
                              contract_id=contract['contract_id'],
                              desc=contract['description'],
                              amount=float(
                                  contract['obligated_amount']) if contract['obligated_amount'] else 0.0,
                              signed_date=contract['signed_date'])

            # Link to Vendor
            if contract['vendor_id']:
                query_rel_vendor = """
                MATCH (c:Contract {id: $c_id})
                MATCH (v:Vendor {id: $v_id})
                MERGE (v)-[:AWARDED]->(c)
                """
                neo4j_session.run(query_rel_vendor, c_id=str(
                    contract['id']), v_id=str(contract['vendor_id']))

            # Link to Agency
            if contract['agency_id']:
                # Ensure agency exists in Neo4j (it should if sync_agencies ran first)
                query_rel_agency = """
                MATCH (c:Contract {id: $c_id})
                MATCH (a:Agency {id: $a_id})
                MERGE (a)-[:AWARDED_CONTRACT]->(c)
                """
                neo4j_session.run(query_rel_agency, c_id=str(
                    contract['id']), a_id=str(contract['agency_id']))

            mark_synced(pg_conn, 'contract', contract['id'])
    print(f"Synced {len(contracts)} contracts.")


def mark_synced(pg_conn, entity_type, entity_id):
    with pg_conn.cursor() as cur:
        try:
            cur.execute("""
                INSERT INTO neo4j_sync_status (id, entity_type, entity_id, sync_status, synced_at)
                VALUES (gen_random_uuid(), %s, %s, 'synced', NOW())
                ON CONFLICT (entity_type, entity_id) 
                DO UPDATE SET sync_status = 'synced', synced_at = NOW()
            """, (entity_type, entity_id))
            pg_conn.commit()
        except Exception as e:
            print(f"Failed to update sync status for {
                  entity_type} {entity_id}: {e}")
            pg_conn.rollback()


def lambda_handler(event, context):
    """AWS Lambda Entry Point"""
    pg_conn = None
    neo4j_driver = None

    try:
        print("Starting Sync Process...")
        pg_conn = get_pg_connection()
        neo4j_driver = get_neo4j_driver()

        with neo4j_driver.session() as session:
            sync_agencies(pg_conn, session)
            sync_vendors(pg_conn, session)
            sync_contracts(pg_conn, session)

        return {
            'statusCode': 200,
            'body': json.dumps('Sync Complete')
        }

    except Exception as e:
        print(f"Sync Failed: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Sync Failed: {str(e)}')
        }

    finally:
        if pg_conn:
            pg_conn.close()
        if neo4j_driver:
            neo4j_driver.close()


if __name__ == "__main__":
    # For local testing, mock the context and event
    lambda_handler({}, {})
