import os
import psycopg2
from neo4j import GraphDatabase
from psycopg2.extras import RealDictCursor

# Configuration
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "govgraph")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")


def get_pg_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


def get_neo4j_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


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
    print("Syncing Vendors...")
    with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT v.* 
            FROM vendors v
            LEFT JOIN neo4j_sync_status s 
                ON s.entity_type = 'vendor' AND s.entity_id = v.id
            WHERE s.id IS NULL OR s.sync_status != 'synced'
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
                v.syncedAt = datetime()
            """
            neo4j_session.run(query,
                              id=str(vendor['id']),
                              name=vendor['canonical_name'],
                              duns=vendor['duns'],
                              uei=vendor['uei'],
                              state=vendor['state'],
                              city=vendor['city'])
            
            mark_synced(pg_conn, 'vendor', vendor['id'])
    print(f"Synced {len(vendors)} vendors.")


def sync_contracts(pg_conn, neo4j_session):
    print("Syncing Contracts...")
    with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT c.* 
            FROM contracts c
            LEFT JOIN neo4j_sync_status s 
                ON s.entity_type = 'contract' AND s.entity_id = c.id
            WHERE s.id IS NULL OR s.sync_status != 'synced'
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
                              amount=float(contract['obligated_amount']) if contract['obligated_amount'] else 0.0,
                              signed_date=contract['signed_date'])

            # Link to Vendor
            if contract['vendor_id']:
                query_rel_vendor = """
                MATCH (c:Contract {id: $c_id})
                MATCH (v:Vendor {id: $v_id})
                MERGE (v)-[:AWARDED]->(c)
                MERGE (c)-[:AWARDED_TO]->(v)
                """
                neo4j_session.run(query_rel_vendor, c_id=str(contract['id']), v_id=str(contract['vendor_id']))

            # Link to Agency
            if contract['agency_id']:
                query_rel_agency = """
                MATCH (c:Contract {id: $c_id})
                MATCH (a:Agency {id: $a_id})
                MERGE (a)-[:AWARDED_CONTRACT]->(c)
                """
                neo4j_session.run(query_rel_agency, c_id=str(contract['id']), a_id=str(contract['agency_id']))
            
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
            print(f"Failed to update sync status for {entity_type} {entity_id}: {e}")
            pg_conn.rollback()


def main():
    pg_conn = get_pg_connection()
    neo4j_driver = get_neo4j_driver()
    
    print("Starting Sync Process...")
    
    with neo4j_driver.session() as session:
        sync_agencies(pg_conn, session)
        sync_vendors(pg_conn, session)
        sync_contracts(pg_conn, session)
        # sync_subcontracts(pg_conn, session) # TODO: Implement later

    pg_conn.close()
    neo4j_driver.close()
    print("Sync Complete.")


if __name__ == "__main__":
    main()
