import os
from contextlib import asynccontextmanager
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt
from mangum import Mangum
from neo4j.graph import Node, Relationship
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from auth import get_current_user
from database import close_drivers, get_neo4j_driver, get_pg_connection
from models import (
    Agency,
    AgencyStats,
    AnomalyEntry,
    AwardTypeBreakdown,
    CircularChain,
    ConcentrationMetric,
    Contract,
    GraphResponse,
    HubVendor,
    MarketShareEntry,
    NewEntrant,
    PaginatedResponse,
    ResolutionQualityEntry,
    SoleSourceFlag,
    SpendingTimeSeries,
    SubcontractFlow,
    Vendor,
    VendorStats,
    VelocityEntry,
)


# ---------------------------------------------------------------------------
# Rate limiter — keyed on JWT sub, falls back to IP
# ---------------------------------------------------------------------------

def _get_user_key(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1]
        try:
            claims = jwt.get_unverified_claims(token)
            sub = claims.get("sub")
            if sub:
                return sub
        except Exception:
            pass
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=_get_user_key)


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_drivers()


app = FastAPI(
    title="GovGraph API",
    description="OSINT platform for federal procurement analysis",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_allowed_origins = os.environ.get(
    "ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["content-type", "authorization"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def process_graph_result(result):
    nodes = []
    edges = []
    seen_nodes = set()

    for record in result:
        for item in record.values():
            if isinstance(item, Node):
                node_id = item.get("id") or item.element_id
                if node_id not in seen_nodes:
                    label = (
                        item.get("canonicalName")
                        or item.get("agencyName")
                        or item.get("contractId")
                    )
                    if not label:
                        label = list(item.labels)[0] if item.labels else "Node"
                    nodes.append({
                        "data": {
                            "id": node_id,
                            "label": label,
                            "type": list(item.labels)[0].lower() if item.labels else "node",
                            "properties": dict(item),
                        }
                    })
                    seen_nodes.add(node_id)

            elif isinstance(item, Relationship):
                start_node = item.start_node
                end_node = item.end_node

                for n in [start_node, end_node]:
                    n_id = n.get("id") or n.element_id
                    if n_id not in seen_nodes:
                        n_label = (
                            n.get("canonicalName")
                            or n.get("agencyName")
                            or n.get("contractId")
                        )
                        if not n_label:
                            n_label = list(n.labels)[0] if n.labels else "Node"
                        nodes.append({
                            "data": {
                                "id": n_id,
                                "label": n_label,
                                "type": list(n.labels)[0].lower() if n.labels else "node",
                                "properties": dict(n),
                            }
                        })
                        seen_nodes.add(n_id)

                edges.append({
                    "data": {
                        "id": item.element_id,
                        "source": start_node.get("id") or start_node.element_id,
                        "target": end_node.get("id") or end_node.element_id,
                        "label": item.type,
                        "properties": dict(item),
                    }
                })

    return {"nodes": nodes, "edges": edges}


def _require_neo4j():
    driver = get_neo4j_driver()
    if not driver:
        raise HTTPException(
            status_code=503, detail="Graph database unavailable")
    return driver


# ---------------------------------------------------------------------------
# Public endpoints (no auth)
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {
        "name": "GovGraph API",
        "status": "active",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


# ---------------------------------------------------------------------------
# Vendor endpoints
# ---------------------------------------------------------------------------

@app.get("/vendors", response_model=PaginatedResponse)
@limiter.limit("60/minute")
async def get_vendors(
    request: Request,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    offset = (page - 1) * size
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            if q:
                search_query = "%" + q + "%"
                cur.execute(
                    "SELECT COUNT(*) FROM vendors WHERE canonical_name ILIKE %s OR uei = %s",
                    (search_query, q),
                )
                total = cur.fetchone()["count"]
                cur.execute(
                    "SELECT * FROM vendors WHERE canonical_name ILIKE %s OR uei = %s ORDER BY canonical_name LIMIT %s OFFSET %s",
                    (search_query, q, size, offset),
                )
            else:
                cur.execute("SELECT COUNT(*) FROM vendors")
                total = cur.fetchone()["count"]
                cur.execute(
                    "SELECT * FROM vendors ORDER BY canonical_name LIMIT %s OFFSET %s",
                    (size, offset),
                )
            items = cur.fetchall()
            return {"total": total, "page": page, "size": size, "items": items}
    finally:
        conn.close()


@app.get("/vendors/{id}", response_model=Vendor)
@limiter.limit("60/minute")
async def get_vendor_by_id(
    request: Request,
    id: UUID,
    current_user: dict = Depends(get_current_user),
):
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
@limiter.limit("60/minute")
async def get_vendor_stats(
    request: Request,
    id: UUID,
    current_user: dict = Depends(get_current_user),
):
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) as total_awards,
                    SUM(obligated_amount) as total_obligated_amount
                FROM contracts
                WHERE vendor_id = %s
                """,
                (str(id),),
            )
            basic = cur.fetchone()

            cur.execute(
                """
                SELECT a.agency_name, SUM(c.obligated_amount) as amount, COUNT(*) as count
                FROM contracts c
                JOIN agencies a ON c.agency_id = a.id
                WHERE c.vendor_id = %s
                GROUP BY a.agency_name
                ORDER BY amount DESC
                LIMIT 5
                """,
                (str(id),),
            )
            agencies = cur.fetchall()

            cur.execute(
                """
                SELECT EXTRACT(YEAR FROM signed_date)::int as year, SUM(obligated_amount) as amount, COUNT(*) as count
                FROM contracts
                WHERE vendor_id = %s
                GROUP BY year
                ORDER BY year DESC
                """,
                (str(id),),
            )
            history = cur.fetchall()

            return {
                "total_awards": basic["total_awards"] or 0,
                "total_obligated_amount": float(basic["total_obligated_amount"] or 0),
                "top_agencies": agencies,
                "award_count_by_year": history,
            }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Agency endpoints
# ---------------------------------------------------------------------------

@app.get("/agencies", response_model=PaginatedResponse)
@limiter.limit("60/minute")
async def get_agencies(
    request: Request,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    offset = (page - 1) * size
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            if q:
                search_query = "%" + q + "%"
                cur.execute(
                    "SELECT COUNT(*) FROM agencies WHERE agency_name ILIKE %s OR agency_code = %s",
                    (search_query, q),
                )
                total = cur.fetchone()["count"]
                cur.execute(
                    "SELECT * FROM agencies WHERE agency_name ILIKE %s OR agency_code = %s ORDER BY agency_name LIMIT %s OFFSET %s",
                    (search_query, q, size, offset),
                )
            else:
                cur.execute("SELECT COUNT(*) FROM agencies")
                total = cur.fetchone()["count"]
                cur.execute(
                    "SELECT * FROM agencies ORDER BY agency_name LIMIT %s OFFSET %s",
                    (size, offset),
                )
            items = cur.fetchall()
            return {"total": total, "page": page, "size": size, "items": items}
    finally:
        conn.close()


@app.get("/agencies/{id}", response_model=Agency)
@limiter.limit("60/minute")
async def get_agency_by_id(
    request: Request,
    id: UUID,
    current_user: dict = Depends(get_current_user),
):
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
@limiter.limit("60/minute")
async def get_agency_stats(
    request: Request,
    id: UUID,
    current_user: dict = Depends(get_current_user),
):
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) as total_awards,
                    SUM(obligated_amount) as total_obligated_amount
                FROM contracts
                WHERE agency_id = %s
                """,
                (str(id),),
            )
            basic = cur.fetchone()

            cur.execute(
                """
                SELECT v.canonical_name, SUM(c.obligated_amount) as amount, COUNT(*) as count
                FROM contracts c
                JOIN vendors v ON c.vendor_id = v.id
                WHERE c.agency_id = %s
                GROUP BY v.canonical_name
                ORDER BY amount DESC
                LIMIT 5
                """,
                (str(id),),
            )
            vendors = cur.fetchall()

            cur.execute(
                """
                SELECT EXTRACT(YEAR FROM signed_date)::int as year, SUM(obligated_amount) as amount
                FROM contracts
                WHERE agency_id = %s
                GROUP BY year
                ORDER BY year DESC
                """,
                (str(id),),
            )
            history = cur.fetchall()

            return {
                "total_awards": basic["total_awards"] or 0,
                "total_obligated_amount": float(basic["total_obligated_amount"] or 0),
                "top_vendors": vendors,
                "spending_by_year": history,
            }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Contract endpoints
# ---------------------------------------------------------------------------

@app.get("/contracts", response_model=PaginatedResponse)
@limiter.limit("60/minute")
async def get_contracts(
    request: Request,
    vendor_id: Optional[UUID] = None,
    agency_id: Optional[UUID] = None,
    min_amount: Optional[float] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
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
            total = cur.fetchone()["count"]

            cur.execute(
                f"SELECT * FROM contracts {
                    where_clause} ORDER BY signed_date DESC LIMIT %s OFFSET %s",
                params + [size, offset],
            )
            items = cur.fetchall()

            return {"total": total, "page": page, "size": size, "items": items}
    finally:
        conn.close()


@app.get("/contracts/{id}", response_model=Contract)
@limiter.limit("60/minute")
async def get_contract_by_id(
    request: Request,
    id: UUID,
    current_user: dict = Depends(get_current_user),
):
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


# ---------------------------------------------------------------------------
# Graph endpoints (Neo4j)
# ---------------------------------------------------------------------------

@app.get("/graph/vendor/{id}", response_model=GraphResponse)
@limiter.limit("20/minute")
async def get_vendor_graph(
    request: Request,
    id: UUID,
    current_user: dict = Depends(get_current_user),
):
    driver = _require_neo4j()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (v:Vendor {id: $id})
            OPTIONAL MATCH (v)-[ra:AWARDED]->(c:Contract)
            OPTIONAL MATCH (a:Agency)-[:AWARDED_CONTRACT]->(c)
            WITH v, c, a, ra LIMIT 50
            RETURN v, c, a, ra
            """,
            id=str(id),
        )
        return process_graph_result(result)


@app.get("/graph/agency/{id}", response_model=GraphResponse)
@limiter.limit("20/minute")
async def get_agency_graph(
    request: Request,
    id: UUID,
    current_user: dict = Depends(get_current_user),
):
    driver = _require_neo4j()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (a:Agency {id: $id})-[:AWARDED_CONTRACT]->(c:Contract)<-[:AWARDED]-(v:Vendor)
            OPTIONAL MATCH (v)-[:SUBCONTRACTED]->(sub:Vendor)
            OPTIONAL MATCH (child:Agency)-[:SUBAGENCY_OF]->(a)
            RETURN a, c, v, sub, child LIMIT 200
            """,
            id=str(id),
        )
        return process_graph_result(result)


@app.get("/graph/vendor/{id}/supply-chain", response_model=GraphResponse)
@limiter.limit("20/minute")
async def get_vendor_supply_chain(
    request: Request,
    id: UUID,
    depth: int = Query(3, ge=1, le=5),
    current_user: dict = Depends(get_current_user),
):
    driver = _require_neo4j()
    with driver.session() as session:
        result = session.run(
            f"""
            MATCH path = (prime:Vendor {{id: $id}})-[:SUBCONTRACTED*1..{depth}]->(sub:Vendor)
            RETURN prime, sub, relationships(path) AS rels
            LIMIT 100
            """,
            id=str(id),
        )
        return process_graph_result(result)


@app.get("/graph/vendor/{id}/peers", response_model=GraphResponse)
@limiter.limit("20/minute")
async def get_vendor_peers(
    request: Request,
    id: UUID,
    current_user: dict = Depends(get_current_user),
):
    driver = _require_neo4j()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (v1:Vendor {id: $id})-[:AWARDED]->(c1:Contract)<-[:AWARDED_CONTRACT]-(a:Agency)
                  -[:AWARDED_CONTRACT]->(c2:Contract)<-[:AWARDED]-(v2:Vendor)
            WHERE v1 <> v2
            WITH v1, v2, COUNT(DISTINCT a) AS shared_agencies
            WHERE shared_agencies >= 3
            RETURN v1, v2, shared_agencies
            ORDER BY shared_agencies DESC
            LIMIT 30
            """,
            id=str(id),
        )
        return process_graph_result(result)


@app.get("/graph/path", response_model=GraphResponse)
@limiter.limit("20/minute")
async def get_graph_path(
    request: Request,
    from_id: UUID = Query(..., alias="from"),
    to_id: UUID = Query(..., alias="to"),
    current_user: dict = Depends(get_current_user),
):
    driver = _require_neo4j()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (v1:Vendor {id: $from_id}), (v2:Vendor {id: $to_id})
            MATCH path = shortestPath((v1)-[*..6]-(v2))
            RETURN path
            """,
            from_id=str(from_id),
            to_id=str(to_id),
        )
        return process_graph_result(result)


@app.get("/graph/hubs", response_model=List[HubVendor])
@limiter.limit("20/minute")
async def get_hub_vendors(
    request: Request,
    min_sub_count: int = Query(5, ge=1),
    current_user: dict = Depends(get_current_user),
):
    driver = _require_neo4j()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (prime:Vendor)-[r:SUBCONTRACTED]->(sub:Vendor)
            WITH prime,
                 COUNT(DISTINCT sub) AS sub_count,
                 SUM(r.amount)       AS total_passed_down
            WHERE sub_count >= $min_sub_count
            RETURN
                prime.canonicalName          AS canonical_name,
                sub_count,
                total_passed_down,
                prime.totalContractValue     AS prime_value,
                CASE WHEN prime.totalContractValue > 0
                     THEN ROUND(total_passed_down * 100.0 / prime.totalContractValue, 2)
                     ELSE null
                END AS passthrough_pct
            ORDER BY sub_count DESC
            LIMIT 50
            """,
            min_sub_count=min_sub_count,
        )
        return [dict(r) for r in result]


# ---------------------------------------------------------------------------
# Analytics endpoints — PostgreSQL
# ---------------------------------------------------------------------------

@app.get("/analytics/summary")
@limiter.limit("30/minute")
async def get_summary_stats(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM vendors")
            vendor_count = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) FROM agencies")
            agency_count = cur.fetchone()["count"]

            cur.execute(
                "SELECT COUNT(*), SUM(obligated_amount) FROM contracts")
            contract_stats = cur.fetchone()

            return {
                "total_vendors": vendor_count,
                "total_agencies": agency_count,
                "total_contracts": contract_stats["count"],
                "total_obligated_amount": float(contract_stats["sum"] or 0),
            }
    finally:
        conn.close()


@app.get("/analytics/market-share", response_model=List[MarketShareEntry])
@limiter.limit("30/minute")
async def get_market_share(
    request: Request,
    limit: int = Query(25, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    v.canonical_name,
                    COUNT(c.id)                                                AS award_count,
                    SUM(c.obligated_amount)                                    AS total_obligated,
                    SUM(c.obligated_amount) * 100.0
                        / NULLIF(SUM(SUM(c.obligated_amount)) OVER (), 0)     AS market_share_pct
                FROM vendors v
                JOIN contracts c ON c.vendor_id = v.id
                GROUP BY v.id, v.canonical_name
                ORDER BY total_obligated DESC
                LIMIT %s
                """,
                (limit,),
            )
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/analytics/agency/{id}/spending-over-time", response_model=List[SpendingTimeSeries])
@limiter.limit("30/minute")
async def get_agency_spending_over_time(
    request: Request,
    id: UUID,
    period: str = Query("month", pattern="^(month|year)$"),
    current_user: dict = Depends(get_current_user),
):
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    DATE_TRUNC(%s, c.signed_date) AS period,
                    COUNT(c.id)                   AS contract_count,
                    SUM(c.obligated_amount)        AS total_obligated
                FROM contracts c
                WHERE c.agency_id = %s
                GROUP BY period
                ORDER BY period
                """,
                (period, str(id)),
            )
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/analytics/vendor/{id}/award-types", response_model=List[AwardTypeBreakdown])
@limiter.limit("30/minute")
async def get_vendor_award_types(
    request: Request,
    id: UUID,
    current_user: dict = Depends(get_current_user),
):
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    award_type,
                    COUNT(*)              AS count,
                    SUM(obligated_amount) AS total_value
                FROM contracts
                WHERE vendor_id = %s
                GROUP BY award_type
                ORDER BY total_value DESC
                """,
                (str(id),),
            )
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/analytics/agency/{id}/vendor-concentration", response_model=List[ConcentrationMetric])
@limiter.limit("30/minute")
async def get_agency_vendor_concentration(
    request: Request,
    id: UUID,
    current_user: dict = Depends(get_current_user),
):
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH vendor_share AS (
                    SELECT
                        agency_id,
                        vendor_id,
                        SUM(obligated_amount) AS vendor_total,
                        SUM(SUM(obligated_amount)) OVER (PARTITION BY agency_id) AS agency_total
                    FROM contracts
                    WHERE agency_id = %s
                    GROUP BY agency_id, vendor_id
                )
                SELECT
                    a.agency_name,
                    ROUND(SUM(POWER(vendor_total / NULLIF(agency_total, 0), 2))::numeric, 4) AS hhi
                FROM vendor_share vs
                JOIN agencies a ON a.id = vs.agency_id
                GROUP BY a.id, a.agency_name
                ORDER BY hhi DESC
                """,
                (str(id),),
            )
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/analytics/vendor/{id}/velocity", response_model=List[VelocityEntry])
@limiter.limit("30/minute")
async def get_vendor_velocity(
    request: Request,
    id: UUID,
    current_user: dict = Depends(get_current_user),
):
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    DATE_TRUNC('quarter', signed_date) AS quarter,
                    COUNT(*)                           AS awards,
                    SUM(obligated_amount)              AS total,
                    AVG(obligated_amount)              AS avg_award_size
                FROM contracts
                WHERE vendor_id = %s
                GROUP BY quarter
                ORDER BY quarter
                """,
                (str(id),),
            )
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/analytics/vendor/{id}/subcontract-flow", response_model=List[SubcontractFlow])
@limiter.limit("30/minute")
async def get_vendor_subcontract_flow(
    request: Request,
    id: UUID,
    current_user: dict = Depends(get_current_user),
):
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    v.canonical_name                        AS prime_vendor,
                    SUM(c.obligated_amount)                 AS prime_value,
                    SUM(sc.subcontract_amount)              AS sub_value,
                    ROUND(
                        SUM(sc.subcontract_amount) * 100.0
                        / NULLIF(SUM(c.obligated_amount), 0), 2
                    )                                       AS subcontract_pct
                FROM vendors v
                JOIN contracts c    ON c.vendor_id = v.id
                LEFT JOIN subcontracts sc ON sc.prime_vendor_id = v.id
                WHERE v.id = %s
                GROUP BY v.id, v.canonical_name
                HAVING SUM(c.obligated_amount) > 0
                """,
                (str(id),),
            )
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/analytics/resolution-quality", response_model=List[ResolutionQualityEntry])
@limiter.limit("30/minute")
async def get_resolution_quality(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    resolution_method,
                    COUNT(*)                                         AS contract_count,
                    ROUND(AVG(resolution_confidence) * 100, 2)      AS avg_confidence_pct,
                    COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER (), 0) AS share_pct
                FROM contracts
                GROUP BY resolution_method
                ORDER BY contract_count DESC
                """
            )
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/analytics/risk/award-spikes", response_model=List[AnomalyEntry])
@limiter.limit("30/minute")
async def get_award_spikes(
    request: Request,
    z_threshold: float = Query(3.0, ge=1.0),
    current_user: dict = Depends(get_current_user),
):
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH vendor_stats AS (
                    SELECT
                        vendor_id,
                        AVG(obligated_amount)    AS avg_amount,
                        STDDEV(obligated_amount) AS stddev_amount
                    FROM contracts
                    GROUP BY vendor_id
                )
                SELECT
                    v.canonical_name,
                    c.contract_id,
                    c.obligated_amount,
                    vs.avg_amount,
                    ROUND(
                        (c.obligated_amount - vs.avg_amount) / NULLIF(vs.stddev_amount, 0), 2
                    ) AS z_score
                FROM contracts c
                JOIN vendors v        ON v.id = c.vendor_id
                JOIN vendor_stats vs  ON vs.vendor_id = c.vendor_id
                WHERE (c.obligated_amount - vs.avg_amount) / NULLIF(vs.stddev_amount, 0) > %s
                ORDER BY z_score DESC
                LIMIT 100
                """,
                (z_threshold,),
            )
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/analytics/risk/new-entrants", response_model=List[NewEntrant])
@limiter.limit("30/minute")
async def get_new_entrants(
    request: Request,
    days: int = Query(90, ge=1, le=365),
    min_value: float = Query(500000.0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    v.canonical_name,
                    MIN(c.signed_date) AS first_award,
                    COUNT(c.id)        AS award_count,
                    SUM(c.obligated_amount) AS total_value
                FROM vendors v
                JOIN contracts c ON c.vendor_id = v.id
                GROUP BY v.id, v.canonical_name
                HAVING MIN(c.signed_date) >= CURRENT_DATE - INTERVAL '1 day' * %s
                   AND SUM(c.obligated_amount) > %s
                ORDER BY total_value DESC
                """,
                (days, min_value),
            )
            return cur.fetchall()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Risk endpoints — Neo4j
# ---------------------------------------------------------------------------

@app.get("/analytics/risk/sole-source", response_model=List[SoleSourceFlag])
@limiter.limit("20/minute")
async def get_sole_source(
    request: Request,
    award_type: str = Query("A"),
    current_user: dict = Depends(get_current_user),
):
    driver = _require_neo4j()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (a:Agency)-[:AWARDED_CONTRACT]->(c:Contract {awardType: $award_type})<-[:AWARDED]-(v:Vendor)
            WITH a, COUNT(DISTINCT v) AS unique_vendors
            WHERE unique_vendors = 1
            MATCH (a)-[:AWARDED_CONTRACT]->(c2:Contract)<-[:AWARDED]-(sole:Vendor)
            RETURN
                a.agencyName          AS agency_name,
                sole.canonicalName    AS sole_vendor,
                COUNT(c2)             AS contracts,
                SUM(c2.obligatedAmount) AS total_spend
            ORDER BY total_spend DESC
            """,
            award_type=award_type,
        )
        return [dict(r) for r in result]


@app.get("/analytics/risk/circular-subcontracts", response_model=List[CircularChain])
@limiter.limit("20/minute")
async def get_circular_subcontracts(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    driver = _require_neo4j()
    with driver.session() as session:
        result = session.run(
            """
            MATCH cycle = (v:Vendor)-[:SUBCONTRACTED*2..4]->(v)
            RETURN
                [n IN nodes(cycle) | n.canonicalName] AS loop_members,
                length(cycle) AS loop_length
            LIMIT 20
            """
        )
        return [dict(r) for r in result]


handler = Mangum(app)
