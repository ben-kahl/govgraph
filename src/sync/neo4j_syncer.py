import os
import json
import boto3
import psycopg2
import logging
from neo4j import GraphDatabase
from psycopg2.extras import RealDictCursor

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

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
    logger.info("SYNC: Starting Agency synchronization...")
    with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Find unsynced or updated agencies
        cur.execute("""
            SELECT a.* 
            FROM agencies a
            LEFT JOIN neo4j_sync_status s 
                ON s.entity_type = 'agency' AND s.entity_id = a.id
            WHERE s.id IS NULL OR s.sync_status != 'synced' OR a.updated_at > s.synced_at
        """)
        agencies = cur.fetchall()

        for agency in agencies:
            # 1. Create/Update Agency Node
            logger.info(f"SYNC: Processing Agency {
                        agency['agency_name']} ({agency['agency_code']})")
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

            # 2. Link to Parent Agency if applicable
            if agency['parent_agency_id']:
                logger.info(f"SYNC: Linking Agency {agency['agency_code']} to parent {
                            agency['parent_agency_id']}")
                query_parent = """
                MATCH (child:Agency {id: $id})
                MATCH (parent:Agency {id: $p_id})
                MERGE (child)-[:SUBAGENCY_OF]->(parent)
                """
                neo4j_session.run(query_parent,
                                  id=str(agency['id']),
                                  p_id=str(agency['parent_agency_id']))

            # Update sync status
            mark_synced(pg_conn, 'agency', agency['id'])
    logger.info(f"SYNC: Successfully synced {len(agencies)} agencies.")


def sync_vendors(pg_conn, neo4j_session):
    logger.info("SYNC: Starting Vendor synchronization (>$1M threshold)...")
    with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Calculate total value and sync vendors > $1M if new or updated
        cur.execute("""
            SELECT v.*, SUM(c.obligated_amount) as total_value
            FROM vendors v
            JOIN contracts c ON v.id = c.vendor_id
            LEFT JOIN neo4j_sync_status s 
                ON s.entity_type = 'vendor' AND s.entity_id = v.id
            WHERE (s.id IS NULL OR s.sync_status != 'synced' OR v.updated_at > s.synced_at)
            GROUP BY v.id
            HAVING SUM(c.obligated_amount) >= 1000000
        """)
        vendors = cur.fetchall()

        for vendor in vendors:
            logger.info(f"SYNC: Processing high-value Vendor {
                        vendor['canonical_name']} (${float(vendor['total_value']):,.2f})")
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
    logger.info(f"SYNC: Successfully synced {
                len(vendors)} high-value vendors.")


def sync_contracts(pg_conn, neo4j_session):
    logger.info("SYNC: Starting Contract synchronization...")
    with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Sync contracts for synced vendors if they are new or updated
        cur.execute("""
            SELECT c.* 
            FROM contracts c
            JOIN neo4j_sync_status s_vendor 
                ON s_vendor.entity_id = c.vendor_id AND s_vendor.entity_type = 'vendor'
            LEFT JOIN neo4j_sync_status s 
                ON s.entity_type = 'contract' AND s.entity_id = c.id
            WHERE (s.id IS NULL OR s.sync_status != 'synced' OR c.updated_at > s.synced_at)
              AND s_vendor.sync_status = 'synced'
        """)
        contracts = cur.fetchall()

        for contract in contracts:
            logger.info(f"SYNC: Processing Contract {contract['contract_id']}")
            # Create/Update Contract Node
            query_node = """
            MERGE (c:Contract {id: $id})
            SET c.contractId = $contract_id,
                c.description = $desc,
                c.obligatedAmount = $amount,
                c.signedDate = date($signed_date),
                c.awardType = $award_type,
                c.syncedAt = datetime()
            """
            neo4j_session.run(query_node,
                              id=str(contract['id']),
                              contract_id=contract['contract_id'],
                              desc=contract['description'],
                              amount=float(
                                  contract['obligated_amount']) if contract['obligated_amount'] else 0.0,
                              signed_date=contract['signed_date'],
                              award_type=contract['award_type'])

            # Link to Vendor
            if contract['vendor_id']:
                logger.info(f"SYNC: Linking Contract {
                            contract['contract_id']} to Vendor {contract['vendor_id']}")
                query_rel_vendor = """
                MATCH (c:Contract {id: $c_id})
                MATCH (v:Vendor {id: $v_id})
                MERGE (v)-[:AWARDED]->(c)
                """
                neo4j_session.run(query_rel_vendor, c_id=str(
                    contract['id']), v_id=str(contract['vendor_id']))

            # 1. Link to Awarding Agency (Top Tier)
            if contract['agency_id']:
                query_rel_agency = """
                MATCH (c:Contract {id: $c_id})
                MATCH (a:Agency {id: $a_id})
                MERGE (a)-[:AWARDED_CONTRACT]->(c)
                """
                neo4j_session.run(query_rel_agency, c_id=str(
                    contract['id']), a_id=str(contract['agency_id']))

            # 2. Link to Awarding Sub Agency
            if contract['awarding_sub_agency_id']:
                query_rel_sub = """
                MATCH (c:Contract {id: $c_id})
                MATCH (a:Agency {id: $a_id})
                MERGE (a)-[:AWARDED_CONTRACT]->(c)
                """
                neo4j_session.run(query_rel_sub, c_id=str(
                    contract['id']), a_id=str(contract['awarding_sub_agency_id']))

            # 3. Link to Funding Agency
            if contract['funding_agency_id']:
                query_rel_fund = """
                MATCH (c:Contract {id: $c_id})
                MATCH (a:Agency {id: $a_id})
                MERGE (a)-[:FUNDED]->(c)
                """
                neo4j_session.run(query_rel_fund, c_id=str(
                    contract['id']), a_id=str(contract['funding_agency_id']))

            # 4. Link to Funding Sub Agency
            if contract['funding_sub_agency_id']:
                query_rel_fund_sub = """
                MATCH (c:Contract {id: $c_id})
                MATCH (a:Agency {id: $a_id})
                MERGE (a)-[:FUNDED]->(c)
                """
                neo4j_session.run(query_rel_fund_sub, c_id=str(
                    contract['id']), a_id=str(contract['funding_sub_agency_id']))

            mark_synced(pg_conn, 'contract', contract['id'])
    logger.info(f"SYNC: Successfully synced {len(contracts)} contracts.")


def sync_subcontracts(pg_conn, neo4j_session):
    logger.info("SYNC: Starting Subcontract synchronization...")
    with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Sync subcontracts if both vendors are in Neo4j (or at least the prime)
        # For simplicity, we sync if the prime vendor is already synced
        cur.execute("""
            SELECT sc.* 
            FROM subcontracts sc
            JOIN neo4j_sync_status s_prime 
                ON s_prime.entity_id = sc.prime_vendor_id AND s_prime.entity_type = 'vendor'
            LEFT JOIN neo4j_sync_status s 
                ON s.entity_type = 'subcontract' AND s.entity_id = sc.id
            WHERE (s.id IS NULL OR s.sync_status != 'synced')
              AND s_prime.sync_status = 'synced'
        """)
        subcontracts = cur.fetchall()

        for sub in subcontracts:
            # We need to make sure the subcontractor vendor also exists in Neo4j
            # (Tier 2 vendors might not meet the $1M threshold, so we MERGE them here too)
            # Fetch subcontractor details from RDS
            cur.execute("SELECT * FROM vendors WHERE id = %s",
                        (sub['subcontractor_vendor_id'],))
            sub_vendor = cur.fetchone()

            if sub_vendor:
                logger.info(f"SYNC: Processing Subcontractor {
                            sub_vendor['canonical_name']} for Prime {sub['prime_vendor_id']}")
                # Merge subcontractor node (might be low value, but essential for the graph)
                query_vend = """
                MERGE (v:Vendor {id: $id})
                SET v.canonicalName = $name,
                    v.uei = $uei,
                    v.isSubcontractor = true
                """
                neo4j_session.run(query_vend,
                                  id=str(sub_vendor['id']),
                                  name=sub_vendor['canonical_name'],
                                  uei=sub_vendor['uei'])

                # Link Prime to Subcontractor
                query_rel = """
                MATCH (prime:Vendor {id: $p_id})
                MATCH (sub:Vendor {id: $s_id})
                MERGE (prime)-[r:SUBCONTRACTED]->(sub)
                SET r.amount = $amount,
                    r.description = $desc,
                    r.tier = $tier
                """
                neo4j_session.run(query_rel,
                                  p_id=str(sub['prime_vendor_id']),
                                  s_id=str(sub['subcontractor_vendor_id']),
                                  amount=float(
                                      sub['subcontract_amount']) if sub['subcontract_amount'] else 0.0,
                                  desc=sub['subcontract_description'],
                                  tier=sub['tier_level'])

            mark_synced(pg_conn, 'subcontract', sub['id'])
    logger.info(f"SYNC: Successfully synced {len(subcontracts)} subcontracts.")


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
        logger.info("SYNC: Starting full synchronization process...")
        pg_conn = get_pg_connection()
        neo4j_driver = get_neo4j_driver()

        with neo4j_driver.session() as session:
            sync_agencies(pg_conn, session)
            sync_vendors(pg_conn, session)
            sync_contracts(pg_conn, session)
            sync_subcontracts(pg_conn, session)

        logger.info("SYNC: Full synchronization completed successfully.")
        return {
            'statusCode': 200,
            'body': json.dumps('Sync Complete')
        }

    except Exception as e:
        logger.error(f"SYNC: Process failed with error: {str(e)}")
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
