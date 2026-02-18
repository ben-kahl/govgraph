from fastapi import FastAPI, HTTPException, Query, Depends
from typing import List, Optional
from uuid import UUID
import json
from mangum import Mangum
from contextlib import asynccontextmanager

from neo4j.graph import Node, Relationship
from models import (
    Vendor, Agency, Contract, VendorStats, AgencyStats,
    PaginatedResponse, GraphResponse, CypherQuery
)
from database import get_pg_connection, get_neo4j_driver


def process_graph_result(result):
    nodes = []
    edges = []
    seen_nodes = set()

    for record in result:
        for item in record.values():
            if isinstance(item, Node):
                node_id = item.get("id") or item.element_id
                if node_id not in seen_nodes:
                    label = item.get("canonicalName") or item.get(
                        "agencyName") or item.get("contractId")
                    if not label:
                        label = list(item.labels)[0] if item.labels else "Node"

                    nodes.append({
                        "data": {
                            "id": node_id,
                            "label": label,
                            "type": list(item.labels)[0].lower() if item.labels else "node",
                            "properties": dict(item)
                        }
                    })
                    seen_nodes.add(node_id)

            elif isinstance(item, Relationship):
                start_node = item.start_node
                end_node = item.end_node

                # Ensure start and end nodes are in the nodes list
                for n in [start_node, end_node]:
                    n_id = n.get("id") or n.element_id
                    if n_id not in seen_nodes:
                        n_label = n.get("canonicalName") or n.get(
                            "agencyName") or n.get("contractId")
                        if not n_label:
                            n_label = list(n.labels)[
                                0] if n.labels else "Node"
                        nodes.append({
                            "data": {
                                "id": n_id,
                                "label": n_label,
                                "type": list(n.labels)[0].lower() if n.labels else "node",
                                "properties": dict(n)
                            }
                        })
                        seen_nodes.add(n_id)

                edges.append({
                    "data": {
                        "id": item.element_id,
                        "source": start_node.get("id") or start_node.element_id,
                        "target": end_node.get("id") or end_node.element_id,
                        "label": item.type,
                        "properties": dict(item)
                    }
                })
    return {"nodes": nodes, "edges": edges}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    from database import close_drivers
    close_drivers()


app = FastAPI(
    title="GovGraph API",
    description="OSINT platform for federal procurement analysis",
    lifespan=lifespan
)


@app.get("/")
async def root():
    return {
        "name": "GovGraph API",
        "status": "active",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


# --- Vendor Endpoints ---
@app.get("/vendors", response_model=PaginatedResponse)
async def get_vendors(
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100)
):
    offset = (page - 1) * size
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            if q:
                search_query = "%" + q + "%"
                cur.execute(
                    "SELECT COUNT(*) FROM vendors WHERE canonical_name ILIKE %s OR uei = %s",
                    (search_query, q)
                )
                total = cur.fetchone()['count']
                cur.execute(
                    "SELECT * FROM vendors WHERE canonical_name ILIKE %s OR uei = %s ORDER BY canonical_name LIMIT %s OFFSET %s",
                    (search_query, q, size, offset)
                )
            else:
                cur.execute("SELECT COUNT(*) FROM vendors")
                total = cur.fetchone()['count']
                cur.execute(
                    "SELECT * FROM vendors ORDER BY canonical_name LIMIT %s OFFSET %s", (size, offset))

            items = cur.fetchall()
            return {
                "total": total,
                "page": page,
                "size": size,
                "items": items
            }
    finally:
        conn.close()


@app.get("/vendors/{id}", response_model=Vendor)
async def get_vendor_by_id(id: UUID):
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM vendors WHERE id = %s", (str(id),))
            vendor = cur.fetchone()
            if not vendor:
                raise HTTPException(status_code=404, detail="Vendor not found")
            return vendor
    finally:
        conn.close()


@app.get("/vendors/{id}/stats", response_model=VendorStats)
async def get_vendor_stats(id: UUID):
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            # Basic aggregates
            cur.execute("""
                SELECT 
                    COUNT(*) as total_awards,
                    SUM(obligated_amount) as total_obligated_amount
                FROM contracts 
                WHERE vendor_id = %s
            """, (str(id),))
            basic = cur.fetchone()

            # Top Agencies
            cur.execute("""
                SELECT a.agency_name, SUM(c.obligated_amount) as amount, COUNT(*) as count
                FROM contracts c
                JOIN agencies a ON c.agency_id = a.id
                WHERE c.vendor_id = %s
                GROUP BY a.agency_name
                ORDER BY amount DESC
                LIMIT 5
            """, (str(id),))
            agencies = cur.fetchall()

            # Awards by year
            cur.execute("""
                SELECT EXTRACT(YEAR FROM signed_date)::int as year, SUM(obligated_amount) as amount, COUNT(*) as count
                FROM contracts
                WHERE vendor_id = %s
                GROUP BY year
                ORDER BY year DESC
            """, (str(id),))
            history = cur.fetchall()

            return {
                "total_awards": basic['total_awards'] or 0,
                "total_obligated_amount": float(basic['total_obligated_amount'] or 0),
                "top_agencies": agencies,
                "award_count_by_year": history
            }
    finally:
        conn.close()


# --- Agency Endpoints ---
@app.get("/agencies", response_model=PaginatedResponse)
async def get_agencies(
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100)
):
    offset = (page - 1) * size
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            if q:
                search_query = "%" + q + "%"
                cur.execute(
                    "SELECT COUNT(*) FROM agencies WHERE agency_name ILIKE %s OR agency_code = %s", (search_query, q))
                total = cur.fetchone()['count']
                cur.execute("SELECT * FROM agencies WHERE agency_name ILIKE %s OR agency_code = %s ORDER BY agency_name LIMIT %s OFFSET %s",
                            (search_query, q, size, offset))
            else:
                cur.execute("SELECT COUNT(*) FROM agencies")
                total = cur.fetchone()['count']
                cur.execute(
                    "SELECT * FROM agencies ORDER BY agency_name LIMIT %s OFFSET %s", (size, offset))

            items = cur.fetchall()
            return {"total": total, "page": page, "size": size, "items": items}
    finally:
        conn.close()


@app.get("/agencies/{id}", response_model=Agency)
async def get_agency_by_id(id: UUID):
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM agencies WHERE id = %s", (str(id),))
            agency = cur.fetchone()
            if not agency:
                raise HTTPException(status_code=404, detail="Agency not found")
            return agency
    finally:
        conn.close()


@app.get("/agencies/{id}/stats", response_model=AgencyStats)
async def get_agency_stats(id: UUID):
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    COUNT(*) as total_awards,
                    SUM(obligated_amount) as total_obligated_amount
                FROM contracts 
                WHERE agency_id = %s
            """, (str(id),))
            basic = cur.fetchone()

            cur.execute("""
                SELECT v.canonical_name, SUM(c.obligated_amount) as amount, COUNT(*) as count
                FROM contracts c
                JOIN vendors v ON c.vendor_id = v.id
                WHERE c.agency_id = %s
                GROUP BY v.canonical_name
                ORDER BY amount DESC
                LIMIT 5
            """, (str(id),))
            vendors = cur.fetchall()

            cur.execute("""
                SELECT EXTRACT(YEAR FROM signed_date)::int as year, SUM(obligated_amount) as amount
                FROM contracts
                WHERE agency_id = %s
                GROUP BY year
                ORDER BY year DESC
            """, (str(id),))
            history = cur.fetchall()

            return {
                "total_awards": basic['total_awards'] or 0,
                "total_obligated_amount": float(basic['total_obligated_amount'] or 0),
                "top_vendors": vendors,
                "spending_by_year": history
            }
    finally:
        conn.close()


# --- Contract Endpoints ---
@app.get("/contracts", response_model=PaginatedResponse)
async def get_contracts(
    vendor_id: Optional[UUID] = None,
    agency_id: Optional[UUID] = None,
    min_amount: Optional[float] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100)
):
    offset = (page - 1) * size
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            conditions = []
            params = []

            if vendor_id:
                conditions.append("vendor_id = %s")
                params.append(str(vendor_id))
            if agency_id:
                conditions.append("agency_id = %s")
                params.append(str(agency_id))
            if min_amount:
                conditions.append("obligated_amount >= %s")
                params.append(min_amount)

            where_clause = " WHERE " + \
                " AND ".join(conditions) if conditions else ""

            cur.execute(
                f"SELECT COUNT(*) FROM contracts {where_clause}", params)
            total = cur.fetchone()['count']

            query = f"SELECT * FROM contracts {
                where_clause} ORDER BY signed_date DESC LIMIT %s OFFSET %s"
            cur.execute(query, params + [size, offset])
            items = cur.fetchall()

            return {"total": total, "page": page, "size": size, "items": items}
    finally:
        conn.close()


@app.get("/contracts/{id}", response_model=Contract)
async def get_contract_by_id(id: UUID):
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM contracts WHERE id = %s", (str(id),))
            contract = cur.fetchone()
            if not contract:
                raise HTTPException(
                    status_code=404, detail="Contract not found")
            return contract
    finally:
        conn.close()


# --- Graph Endpoints (Neo4j) ---
@app.post("/graph/query", response_model=GraphResponse)
async def custom_graph_query(query_data: CypherQuery):
    driver = get_neo4j_driver()
    if not driver:
        raise HTTPException(
            status_code=503, detail="Graph database unavailable")

    try:
        with driver.session() as session:
            result = session.run(query_data.query,
                                 **(query_data.params or {}))
            return process_graph_result(result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cypher Error: {str(e)}")


@app.get("/graph/vendor/{id}", response_model=GraphResponse)
async def get_vendor_graph(id: UUID):
    driver = get_neo4j_driver()
    if not driver:
        raise HTTPException(
            status_code=503, detail="Graph database unavailable")

    with driver.session() as session:
        # Query for vendor and its direct contract/agency relationships
        # Also include any parent/subsidiary relationships if they exist in graph
        query = """
        MATCH (v:Vendor {id: $id})
        OPTIONAL MATCH (v)-[r:AWARDED]->(c:Contract)-[:AWARDED_BY]->(a:Agency)
        WITH v, c, a, r
        LIMIT 50
        RETURN v, c, a, r
        """
        result = session.run(query, id=str(id))
        return process_graph_result(result)


@app.get("/analytics/summary")
async def get_summary_stats():
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM vendors")
            vendor_count = cur.fetchone()['count']

            cur.execute("SELECT COUNT(*) FROM agencies")
            agency_count = cur.fetchone()['count']

            cur.execute(
                "SELECT COUNT(*), SUM(obligated_amount) FROM contracts")
            contract_stats = cur.fetchone()

            return {
                "total_vendors": vendor_count,
                "total_agencies": agency_count,
                "total_contracts": contract_stats['count'],
                "total_obligated_amount": float(contract_stats['sum'] or 0)
            }
    finally:
        conn.close()

handler = Mangum(app)
