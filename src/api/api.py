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
from database import close_drivers, get_neo4j_driver, get_pg_connection
from auth import get_current_user
from rate_limit import limiter
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from neo4j.graph import Node, Path, Relationship
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup: ALLOWED_ORIGINS=%s", os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000"))
    yield
    close_drivers()


_debug = os.environ.get("DEBUG", "false").lower() == "true"

app = FastAPI(
    title="GovGraph API",
    description="OSINT platform for federal procurement analysis",
    lifespan=lifespan,
    docs_url="/docs" if _debug else None,
    redoc_url="/redoc" if _debug else None,
    openapi_url="/openapi.json" if _debug else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s",
                     request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


_allowed_origins = os.environ.get(
    "ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["content-type", "authorization"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every request and response, including CORS-relevant headers."""
    origin = request.headers.get("origin", "<no-origin>")
    origin_allowed = origin in _allowed_origins
    logger.info(
        "request  method=%s path=%s origin=%s origin_allowed=%s auth=%s",
        request.method,
        request.url.path,
        origin,
        origin_allowed,
        "present" if request.headers.get("authorization") else "missing",
    )
    response = await call_next(request)
    logger.info(
        "response method=%s path=%s status=%d acao=%s",
        request.method,
        request.url.path,
        response.status_code,
        response.headers.get("access-control-allow-origin", "<not-set>"),
    )
    return response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node_to_dict(item: Node) -> dict:
    node_id = item.get("id") or item.element_id
    node_type = list(item.labels)[0] if item.labels else "Node"
    raw_label = (
        item.get("canonicalName")
        or item.get("agencyName")
        or item.get("description")
        or item.get("contractId")
    )
    if not raw_label:
        raw_label = node_type
    label = raw_label[:38] + "…" if len(raw_label) > 38 else raw_label

    properties: Dict[str, Any] = {}
    weight = None
    if node_type == "Contract":
        for key in ("obligatedAmount", "contractId", "description", "signedDate", "awardType"):
            val = item.get(key)
            if val is not None:
                properties[key] = str(val) if key == "signedDate" else val
        amount = item.get("obligatedAmount")
        if amount is not None:
            weight = float(amount)
    elif node_type == "Vendor":
        for key in ("canonicalName", "totalContractValue"):
            val = item.get(key)
            if val is not None:
                properties[key] = val
        val = item.get("totalContractValue")
        if val is not None:
            weight = float(val)
    elif node_type == "Agency":
        for key in ("agencyName", "agencyCode"):
            val = item.get(key)
            if val is not None:
                properties[key] = val

    result: Dict[str, Any] = {
        "id": node_id,
        "label": label,
        "type": node_type,
        "properties": properties,
    }
    if weight is not None:
        result["weight"] = weight
    return result


def process_graph_result(result):
    nodes = []
    edges = []
    seen_nodes = set()

    def _add_node(item: Node):
        node_id = item.get("id") or item.element_id
        if node_id not in seen_nodes:
            nodes.append({"data": _node_to_dict(item)})
            seen_nodes.add(node_id)

    def _add_relationship(item: Relationship):
        for n in [item.start_node, item.end_node]:
            _add_node(n)
        edge_data: Dict[str, Any] = {
            "id": item.element_id,
            "source": item.start_node.get("id") or item.start_node.element_id,
            "target": item.end_node.get("id") or item.end_node.element_id,
            "label": item.type,
        }
        # Propagate obligated amount from Contract end-node onto the edge for visual weighting
        if item.type in ("AWARDED", "AWARDED_CONTRACT", "FUNDED"):
            amount = item.end_node.get("obligatedAmount")
            if amount is not None:
                edge_data["weight"] = float(amount)
        edges.append({"data": edge_data})

    for record in result:
        for item in record.values():
            if isinstance(item, Node):
                _add_node(item)
            elif isinstance(item, Relationship):
                _add_relationship(item)
            elif isinstance(item, Path):
                for n in item.nodes:
                    _add_node(n)
                for r in item.relationships:
                    _add_relationship(r)
            elif isinstance(item, list):
                for element in item:
                    if isinstance(element, Node):
                        _add_node(element)
                    elif isinstance(element, Relationship):
                        _add_relationship(element)

    # Mark sub-agencies: any Agency that is a source of a SUBAGENCY_OF edge
    subagency_ids = {e["data"]["source"] for e in edges if e["data"]["label"] == "SUBAGENCY_OF"}
    if subagency_ids:
        for node in nodes:
            if node["data"]["type"] == "Agency" and node["data"]["id"] in subagency_ids:
                node["data"]["isSubagency"] = True

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
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


# ---------------------------------------------------------------------------
# Vendor endpoints
# ---------------------------------------------------------------------------

# Whitelist prevents SQL injection — order_col is never interpolated from
# raw user input, only from this mapping.
_VENDOR_SORT_COLS: Dict[str, str] = {
    "canonical_name": "v.canonical_name",
    "contract_count": "COALESCE(cs.contract_count, 0)",
    "total_obligated": "COALESCE(cs.total_obligated, 0)",
}

_CONTRACT_JOIN = """
    LEFT JOIN (
        SELECT vendor_id,
               COUNT(*) AS contract_count,
               SUM(obligated_amount) AS total_obligated
        FROM contracts GROUP BY vendor_id
    ) cs ON cs.vendor_id = v.id
"""

@app.get("/vendors", response_model=PaginatedResponse)
@limiter.limit("60/minute")
async def get_vendors(
    request: Request,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("total_obligated"),
    sort_dir: str = Query("desc"),
    current_user: dict = Depends(get_current_user),
):
    if sort_by not in _VENDOR_SORT_COLS:
        sort_by = "total_obligated"
    if sort_dir not in ("asc", "desc"):
        sort_dir = "desc"

    order_col = _VENDOR_SORT_COLS[sort_by]
    order_dir = "ASC" if sort_dir == "asc" else "DESC"
    nulls_clause = "NULLS LAST" if sort_dir == "desc" else "NULLS FIRST"

    offset = (page - 1) * size
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            select_cols = f"""
                SELECT v.*,
                       COALESCE(cs.contract_count, 0) AS contract_count,
                       COALESCE(cs.total_obligated, 0.0) AS total_obligated
                FROM vendors v {_CONTRACT_JOIN}
            """
            if q:
                search_query = "%" + q + "%"
                cur.execute(
                    "SELECT COUNT(*) FROM vendors WHERE canonical_name ILIKE %s OR uei = %s",
                    (search_query, q),
                )
                total = cur.fetchone()["count"]
                cur.execute(
                    f"{select_cols} WHERE v.canonical_name ILIKE %s OR v.uei = %s"
                    f" ORDER BY {order_col} {order_dir} {nulls_clause}"
                    f" LIMIT %s OFFSET %s",
                    (search_query, q, size, offset),
                )
            else:
                cur.execute("SELECT COUNT(*) FROM vendors")
                total = cur.fetchone()["count"]
                cur.execute(
                    f"{select_cols} ORDER BY {order_col} {order_dir} {nulls_clause}"
                    f" LIMIT %s OFFSET %s",
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
                SELECT a.id::text as agency_id, a.agency_name, SUM(c.obligated_amount) as amount, COUNT(*) as count
                FROM contracts c
                JOIN agencies a ON c.agency_id = a.id
                WHERE c.vendor_id = %s
                GROUP BY a.id, a.agency_name
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
                WHERE (agency_id = %s OR awarding_sub_agency_id = %s)
                """,
                (str(id), str(id)),
            )
            basic = cur.fetchone()

            cur.execute(
                """
                SELECT v.id::text as vendor_id, v.canonical_name, SUM(c.obligated_amount) as amount, COUNT(*) as count
                FROM contracts c
                JOIN vendors v ON c.vendor_id = v.id
                WHERE (c.agency_id = %s OR c.awarding_sub_agency_id = %s)
                GROUP BY v.id, v.canonical_name
                ORDER BY amount DESC
                LIMIT 5
                """,
                (str(id), str(id)),
            )
            vendors = cur.fetchall()

            cur.execute(
                """
                SELECT EXTRACT(YEAR FROM signed_date)::int as year, SUM(obligated_amount) as amount
                FROM contracts
                WHERE (agency_id = %s OR awarding_sub_agency_id = %s)
                GROUP BY year
                ORDER BY year DESC
                """,
                (str(id), str(id)),
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
    limit: int = Query(500, ge=10, le=5000),
    current_user: dict = Depends(get_current_user),
):
    driver = _require_neo4j()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (v:Vendor {id: $id})
            OPTIONAL MATCH (v)-[ra:AWARDED]->(c:Contract)
            WITH v, c, ra
            ORDER BY c.obligatedAmount DESC
            LIMIT $limit
            WITH v,
                 COLLECT(DISTINCT c)  AS contracts,
                 COLLECT(DISTINCT ra) AS ra_rels
            UNWIND contracts AS c
            OPTIONAL MATCH (aw_a:Agency)-[rac:AWARDED_CONTRACT]->(c)
            OPTIONAL MATCH (fu_a:Agency)-[rf:FUNDED]->(c)
            WITH v, contracts, ra_rels,
                 COLLECT(DISTINCT aw_a) AS aw_agencies,
                 COLLECT(DISTINCT rac)  AS rac_rels,
                 COLLECT(DISTINCT fu_a) AS fu_agencies,
                 COLLECT(DISTINCT rf)   AS rf_rels
            OPTIONAL MATCH (v)-[rs:SUBCONTRACTED]->(sub:Vendor)
            RETURN v, contracts, ra_rels, aw_agencies, rac_rels,
                   fu_agencies, rf_rels,
                   COLLECT(DISTINCT sub) AS subs,
                   COLLECT(DISTINCT rs)  AS sub_rels
            """,
            id=str(id),
            limit=limit,
        )
        return process_graph_result(result)


@app.get("/graph/agency/{id}", response_model=GraphResponse)
@limiter.limit("20/minute")
async def get_agency_graph(
    request: Request,
    id: UUID,
    limit: int = Query(1000, ge=10, le=5000),
    current_user: dict = Depends(get_current_user),
):
    driver = _require_neo4j()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (a:Agency {id: $id})-[r1:AWARDED_CONTRACT]->(c:Contract)<-[r2:AWARDED]-(v:Vendor)
            WITH a, c, v, r1, r2
            ORDER BY c.obligatedAmount DESC
            LIMIT $limit
            OPTIONAL MATCH (a2:Agency)-[rf:FUNDED]->(c)
            OPTIONAL MATCH (v)-[r3:SUBCONTRACTED]->(sub:Vendor)
            OPTIONAL MATCH (child:Agency)-[r4:SUBAGENCY_OF]->(a)
            RETURN a, c, v, sub, child, a2, r1, r2, rf, r3, r4
            """,
            id=str(id),
            limit=limit,
        )
        return process_graph_result(result)


@app.get("/graph/contract/{id}", response_model=GraphResponse)
@limiter.limit("20/minute")
async def get_contract_graph(
    request: Request,
    id: str,
    current_user: dict = Depends(get_current_user),
):
    """Return a contract node with its directly connected vendors and agencies.

    Matches by ``id`` property first, then falls back to elementId so that
    contracts without an explicit UUID property are still retrievable.
    """
    driver = _require_neo4j()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (c:Contract)
            WHERE c.id = $id OR elementId(c) = $id
            OPTIONAL MATCH (v:Vendor)-[ra:AWARDED]->(c)
            OPTIONAL MATCH (aw_a:Agency)-[rac:AWARDED_CONTRACT]->(c)
            OPTIONAL MATCH (fu_a:Agency)-[rf:FUNDED]->(c)
            RETURN c, v, ra, aw_a, rac, fu_a, rf
            """,
            id=id,
        )
        return process_graph_result(result)


@app.get("/graph/overview", response_model=GraphResponse)
@limiter.limit("20/minute")
async def get_overview_graph(
    request: Request,
    limit: int = Query(30, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """Top vendors by contract value with their actual awarded contracts and agencies.

    Uses ``limit`` to control how many top vendors (by totalContractValue) are
    included.  Contract nodes are included so edge thickness and node sizing
    reflect real dollar amounts rather than aggregated totals.
    """
    driver = _require_neo4j()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (v:Vendor)
            WHERE v.totalContractValue IS NOT NULL
            WITH v ORDER BY v.totalContractValue DESC LIMIT $limit
            MATCH (v)-[ra:AWARDED]->(c:Contract)<-[rac:AWARDED_CONTRACT]-(a:Agency)
            RETURN v, ra, c, rac, a
            LIMIT 300
            """,
            limit=limit,
        )
        return process_graph_result(result)


@app.get("/graph/explore", response_model=GraphResponse)
@limiter.limit("20/minute")
async def get_explore_graph(
    request: Request,
    agency_limit: int = Query(8, ge=1, le=20),
    min_amount: float = Query(5_000_000, ge=0),
    contract_limit: int = Query(150, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    """Broad exploration graph for new users.

    Returns the top parent agencies (agencies with no parent), up to five of
    each agency's sub-agencies, and the highest-value contracts (>= min_amount)
    those agencies awarded together with their vendors.
    """
    driver = _require_neo4j()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (a:Agency)
            WHERE NOT (a)-[:SUBAGENCY_OF]->()
            WITH a LIMIT $agency_limit
            OPTIONAL MATCH (sub:Agency)-[r_sub:SUBAGENCY_OF]->(a)
            WITH a,
                 COLLECT(DISTINCT sub)[0..5]   AS subs,
                 COLLECT(DISTINCT r_sub)[0..5]  AS sub_rels
            MATCH (a)-[rac:AWARDED_CONTRACT]->(c:Contract)<-[ra:AWARDED]-(v:Vendor)
            WHERE c.obligatedAmount >= $min_amount
            RETURN a, subs, sub_rels, rac, c, ra, v
            ORDER BY c.obligatedAmount DESC
            LIMIT $contract_limit
            """,
            agency_limit=agency_limit,
            min_amount=min_amount,
            contract_limit=contract_limit,
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
    # depth is validated by FastAPI (int, ge=1, le=5) but we assert here as
    # defense-in-depth because it is f-string interpolated into the Cypher
    # query. Neo4j does not support parameterized variable-length patterns.
    assert isinstance(depth, int) and 1 <= depth <= 5
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
    from_type: str = Query("vendor", alias="from_type"),
    to_type: str = Query("vendor", alias="to_type"),
    current_user: dict = Depends(get_current_user),
):
    """Return the shortest path between any two graph entities (Vendor or Agency)."""
    label_map = {"vendor": "Vendor", "agency": "Agency"}
    from_label = label_map.get(from_type.lower(), "Vendor")
    to_label = label_map.get(to_type.lower(), "Vendor")
    driver = _require_neo4j()
    with driver.session() as session:
        result = session.run(
            f"""
            MATCH (n1:{from_label} {{id: $from_id}}), (n2:{to_label} {{id: $to_id}})
            MATCH path = shortestPath((n1)-[*..6]-(n2))
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
    logger.info("hub_vendors: entry min_sub_count=%d", min_sub_count)
    driver = get_neo4j_driver()
    if not driver:
        logger.error("hub_vendors: Neo4j driver unavailable")
        raise HTTPException(status_code=503, detail="Graph database unavailable")
    logger.info("hub_vendors: driver acquired, executing Cypher")
    try:
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
            rows = [dict(r) for r in result]
        logger.info("hub_vendors: query returned %d rows", len(rows))
        return rows
    except Exception:
        logger.exception("hub_vendors: Cypher query failed")
        raise


# ---------------------------------------------------------------------------
# Analytics endpoints — PostgreSQL
# ---------------------------------------------------------------------------

@app.get("/insights/summary")
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


@app.get("/insights/market-share", response_model=List[MarketShareEntry])
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


@app.get("/insights/agency-market-share")
@limiter.limit("30/minute")
async def get_agency_market_share(
    request: Request,
    limit: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """Top agencies by total obligated contract value.

    Returns agencies ranked by total obligated amount with award counts and
    percentage share of total spend.

    Args:
        limit: Maximum number of agencies to return (1–100, default 10).
        current_user: Injected JWT payload from Cognito.

    Returns:
        List of dicts with agency_name, award_count, total_obligated, market_share_pct.
    """
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    a.agency_name,
                    COUNT(c.id)                                                AS award_count,
                    SUM(c.obligated_amount)                                    AS total_obligated,
                    SUM(c.obligated_amount) * 100.0
                        / NULLIF(SUM(SUM(c.obligated_amount)) OVER (), 0)     AS market_share_pct
                FROM agencies a
                JOIN contracts c ON c.agency_id = a.id
                GROUP BY a.id, a.agency_name
                ORDER BY total_obligated DESC
                LIMIT %s
                """,
                (limit,),
            )
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/insights/agency/{id}/spending-over-time", response_model=List[SpendingTimeSeries])
@limiter.limit("30/minute")
async def get_agency_spending_over_time(
    request: Request,
    id: UUID,
    period: str = Query("month", pattern="^(month|quarter|year)$"),
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
                WHERE (c.agency_id = %s OR c.awarding_sub_agency_id = %s)
                GROUP BY period
                ORDER BY period
                """,
                (period, str(id), str(id)),
            )
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/insights/vendor/{id}/award-types", response_model=List[AwardTypeBreakdown])
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


@app.get("/insights/agency/{id}/vendor-concentration", response_model=List[ConcentrationMetric])
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


@app.get("/insights/vendor/{id}/velocity", response_model=List[VelocityEntry])
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


@app.get("/insights/vendor/{id}/subcontract-flow", response_model=List[SubcontractFlow])
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


@app.get("/insights/resolution-quality", response_model=List[ResolutionQualityEntry])
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
                    COUNT(*)                                              AS contract_count,
                    ROUND(AVG(resolution_confidence) * 100, 2)           AS avg_confidence_pct,
                    COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER (), 0)  AS share_pct
                FROM contracts
                GROUP BY resolution_method
                ORDER BY contract_count DESC
                """
            )
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/insights/risk/award-spikes", response_model=List[AnomalyEntry])
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
                    v.id AS vendor_id,
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


@app.get("/insights/risk/new-entrants", response_model=List[NewEntrant])
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
                    v.id AS vendor_id,
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

@app.get("/insights/risk/sole-source", response_model=List[SoleSourceFlag])
@limiter.limit("20/minute")
async def get_sole_source(
    request: Request,
    award_type: str = Query("A", pattern=r"^[A-Z]{1,2}$"),
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


@app.get("/insights/risk/circular-subcontracts", response_model=List[CircularChain])
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
                [n IN nodes(cycle) | {id: n.id, name: n.canonicalName}] AS loop_members,
                length(cycle) AS loop_length
            LIMIT 20
            """
        )
        return [dict(r) for r in result]


handler = Mangum(app)
