import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from uuid import uuid4
from neo4j.graph import Node, Relationship

# Set environment variables before importing app
os.environ["DB_HOST"] = "localhost"
os.environ["DB_NAME"] = "testdb"
os.environ["DB_USER"] = "testuser"
os.environ["DB_SECRET_ARN"] = "arn:test"
os.environ["COGNITO_USER_POOL_ID"] = "us-east-1_testpool"
os.environ["COGNITO_REGION"] = "us-east-1"

from src.api.api import app
# Import from the top-level 'auth' module (src/api on pythonpath) so the
# dependency_overrides key matches what api.py registered with FastAPI.
import auth
get_current_user = auth.get_current_user


# ---------------------------------------------------------------------------
# Global test fixtures
# ---------------------------------------------------------------------------

FAKE_USER = {"sub": "test-user-id", "email": "test@example.com", "token_use": "access"}


@pytest.fixture(autouse=True)
def mock_auth(monkeypatch):
    """Bypass JWT validation for all tests."""
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    yield
    app.dependency_overrides.clear()



@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_pg():
    with patch("src.api.api.get_pg_connection") as mock:
        conn = MagicMock()
        cur = conn.cursor.return_value.__enter__.return_value
        mock.return_value = conn
        yield cur


@pytest.fixture
def mock_neo4j():
    with patch("src.api.api.get_neo4j_driver") as mock:
        driver = MagicMock()
        session = driver.session.return_value.__enter__.return_value
        mock.return_value = driver
        yield session


# ---------------------------------------------------------------------------
# Public endpoints (no auth required)
# ---------------------------------------------------------------------------

def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "GovGraph API"


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


# ---------------------------------------------------------------------------
# Auth rejection
# ---------------------------------------------------------------------------

def test_auth_required_on_vendors(client):
    """Without the auth override, a missing token should return 401."""
    app.dependency_overrides.clear()
    try:
        response = client.get("/vendors")
        assert response.status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = lambda: FAKE_USER


# ---------------------------------------------------------------------------
# Vendor endpoints
# ---------------------------------------------------------------------------

def test_get_vendors_empty(client, mock_pg):
    mock_pg.fetchone.return_value = {"count": 0}
    mock_pg.fetchall.return_value = []

    response = client.get("/vendors")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_vendors_sort_by_canonical_name(client, mock_pg):
    """sort_by=canonical_name&sort_dir=asc must be accepted without error."""
    mock_pg.fetchone.return_value = {"count": 0}
    mock_pg.fetchall.return_value = []

    response = client.get("/vendors?sort_by=canonical_name&sort_dir=asc")
    assert response.status_code == 200


def test_vendors_sort_by_contract_count(client, mock_pg):
    """sort_by=contract_count&sort_dir=desc must be accepted without error."""
    mock_pg.fetchone.return_value = {"count": 0}
    mock_pg.fetchall.return_value = []

    response = client.get("/vendors?sort_by=contract_count&sort_dir=desc")
    assert response.status_code == 200


def test_vendors_invalid_sort_col_falls_back_to_default(client, mock_pg):
    """Unknown sort_by values are silently coerced to total_obligated."""
    mock_pg.fetchone.return_value = {"count": 0}
    mock_pg.fetchall.return_value = []

    response = client.get("/vendors?sort_by=INJECTION; DROP TABLE vendors; --")
    assert response.status_code == 200


def test_get_vendor_by_id_success(client, mock_pg):
    vendor_id = uuid4()
    mock_pg.fetchone.return_value = {
        "id": str(vendor_id),
        "canonical_name": "ACME CORP",
        "uei": "UEI123",
        "duns": "DUNS123",
        "resolved_by_llm": False,
        "resolution_confidence": 1.0,
        "created_at": "2023-01-01T00:00:00",
        "updated_at": "2023-01-01T00:00:00",
    }

    response = client.get(f"/vendors/{vendor_id}")
    assert response.status_code == 200
    assert response.json()["canonical_name"] == "ACME CORP"


def test_get_vendor_by_id_not_found(client, mock_pg):
    mock_pg.fetchone.return_value = None
    response = client.get(f"/vendors/{uuid4()}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Analytics endpoints
# ---------------------------------------------------------------------------

def test_market_share(client, mock_pg):
    mock_pg.fetchall.return_value = [
        {
            "canonical_name": "ACME CORP",
            "award_count": 10,
            "total_obligated": 1000000.0,
            "market_share_pct": 25.0,
        }
    ]

    response = client.get("/insights/market-share")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["canonical_name"] == "ACME CORP"
    assert data[0]["market_share_pct"] == 25.0


def test_spending_over_time(client, mock_pg):
    from datetime import datetime

    mock_pg.fetchall.return_value = [
        {
            "period": datetime(2023, 1, 1),
            "contract_count": 5,
            "total_obligated": 500000.0,
        }
    ]

    agency_id = uuid4()
    response = client.get(f"/insights/agency/{agency_id}/spending-over-time")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["contract_count"] == 5

    # Verify agency_id is passed twice so subagency contracts are included
    call_args = mock_pg.execute.call_args
    params = call_args[0][1]
    assert params[1] == str(agency_id), "agency_id should be first id param"
    assert params[2] == str(agency_id), "agency_id should be second id param (awarding_sub_agency_id)"


def test_agency_stats(client, mock_pg):
    mock_pg.fetchone.return_value = {
        "total_awards": 10,
        "total_obligated_amount": 5_000_000.0,
    }
    mock_pg.fetchall.side_effect = [
        [{"canonical_name": "TOP VENDOR", "amount": 3_000_000.0, "count": 6}],
        [{"year": 2023, "amount": 5_000_000.0}],
    ]

    agency_id = uuid4()
    response = client.get(f"/agencies/{agency_id}/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_awards"] == 10
    assert data["total_obligated_amount"] == 5_000_000.0
    assert len(data["top_vendors"]) == 1
    assert data["top_vendors"][0]["canonical_name"] == "TOP VENDOR"
    assert len(data["spending_by_year"]) == 1

    # Verify each query passes agency_id twice for subagency support
    for call in mock_pg.execute.call_args_list:
        params = call[0][1]
        assert params[0] == str(agency_id)
        assert params[1] == str(agency_id)


def test_award_spikes(client, mock_pg):
    mock_pg.fetchall.return_value = [
        {
            "vendor_id": "a1b2c3d4-0000-0000-0000-000000000001",
            "canonical_name": "BIG VENDOR",
            "contract_id": "C-001",
            "obligated_amount": 9999999.0,
            "avg_amount": 100000.0,
            "z_score": 4.5,
        }
    ]

    response = client.get("/insights/risk/award-spikes?z_threshold=3")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["z_score"] == 4.5
    assert data[0]["vendor_id"] == "a1b2c3d4-0000-0000-0000-000000000001"


def test_new_entrants(client, mock_pg):
    mock_pg.fetchall.return_value = [
        {
            "vendor_id": "a1b2c3d4-0000-0000-0000-000000000002",
            "canonical_name": "STARTUP LLC",
            "first_award": "2026-01-15",
            "award_count": 2,
            "total_value": 750000.0,
        }
    ]

    response = client.get("/insights/risk/new-entrants")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["canonical_name"] == "STARTUP LLC"
    assert data[0]["vendor_id"] == "a1b2c3d4-0000-0000-0000-000000000002"


# ---------------------------------------------------------------------------
# Graph endpoints
# ---------------------------------------------------------------------------

def test_vendor_graph_uses_correct_relationships(client, mock_neo4j):
    """Verify the fixed Cypher runs and uses AWARDED_CONTRACT, not AWARDED_BY."""
    mock_neo4j.run.return_value = []

    vendor_id = uuid4()
    response = client.get(f"/graph/vendor/{vendor_id}")
    assert response.status_code == 200

    call_args = mock_neo4j.run.call_args
    cypher = call_args[0][0]
    assert "AWARDED_BY" not in cypher
    assert "AWARDED_CONTRACT" in cypher


def test_graph_path(client, mock_neo4j):
    mock_neo4j.run.return_value = []

    from_id = uuid4()
    to_id = uuid4()
    response = client.get(f"/graph/path?from={from_id}&to={to_id}")
    assert response.status_code == 200

    call_args = mock_neo4j.run.call_args
    cypher = call_args[0][0]
    assert "shortestPath" in cypher


def test_agency_graph_returns_200(client, mock_neo4j):
    """GET /graph/agency/{id} exists and returns the expected envelope."""
    mock_neo4j.run.return_value = []
    agency_id = uuid4()
    response = client.get(f"/graph/agency/{agency_id}")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data


def test_explore_graph_returns_200(client, mock_neo4j):
    """GET /graph/explore returns a graph envelope with default params."""
    mock_neo4j.run.return_value = []
    response = client.get("/graph/explore")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data


def test_explore_graph_cypher_includes_subagency_of(client, mock_neo4j):
    """Explore Cypher must query SUBAGENCY_OF so sub-agencies are included."""
    mock_neo4j.run.return_value = []
    client.get("/graph/explore")
    cypher = mock_neo4j.run.call_args[0][0]
    assert "SUBAGENCY_OF" in cypher


def test_overview_graph_returns_actual_contract_nodes(client, mock_neo4j):
    """Overview now returns actual Contract nodes (not aggregated edges)."""
    mock_neo4j.run.return_value = []
    response = client.get("/graph/overview")
    assert response.status_code == 200
    # Cypher must reference AWARDED relationships (real contract edges)
    cypher = mock_neo4j.run.call_args[0][0]
    assert "AWARDED" in cypher
    assert "Contract" in cypher


# ---------------------------------------------------------------------------
# Helpers for graph unit tests
# ---------------------------------------------------------------------------

def _make_node(labels, properties, element_id="el-1"):
    """Create a MagicMock that passes isinstance(x, Node) checks."""
    node = MagicMock(spec=Node)
    node.labels = frozenset(labels)
    node.element_id = element_id
    node.get.side_effect = lambda k, default=None: properties.get(k, default)
    return node


def _make_rel(rel_type, start_node, end_node, element_id="rel-1"):
    """Create a MagicMock that passes isinstance(x, Relationship) checks."""
    rel = MagicMock(spec=Relationship)
    rel.type = rel_type
    rel.start_node = start_node
    rel.end_node = end_node
    rel.element_id = element_id
    return rel


class _MockRecord:
    """Minimal Neo4j record substitute; supports both [] and .values()."""
    def __init__(self, data):
        self._data = data

    def __getitem__(self, key):
        return self._data[key]

    def values(self):
        return list(self._data.values())


# ---------------------------------------------------------------------------
# _node_to_dict: weight propagation
# ---------------------------------------------------------------------------

def test_node_to_dict_vendor_weight_from_total_contract_value():
    from src.api.api import _node_to_dict
    node = _make_node(["Vendor"], {"id": "v1", "canonicalName": "ACME Corp", "totalContractValue": 5_000_000_000})
    result = _node_to_dict(node)
    assert result["type"] == "Vendor"
    assert result["weight"] == 5_000_000_000.0


def test_node_to_dict_vendor_no_weight_when_missing():
    from src.api.api import _node_to_dict
    node = _make_node(["Vendor"], {"id": "v1", "canonicalName": "ACME Corp"})
    result = _node_to_dict(node)
    assert "weight" not in result


def test_node_to_dict_contract_weight_from_obligated_amount():
    from src.api.api import _node_to_dict
    node = _make_node(["Contract"], {"id": "c1", "obligatedAmount": 1_500_000, "contractId": "CONT-001"})
    result = _node_to_dict(node)
    assert result["type"] == "Contract"
    assert result["weight"] == 1_500_000.0
    # obligatedAmount also present in properties for the detail panel
    assert result["properties"]["obligatedAmount"] == 1_500_000


def test_node_to_dict_agency_no_weight():
    from src.api.api import _node_to_dict
    node = _make_node(["Agency"], {"id": "a1", "agencyName": "DoD"})
    result = _node_to_dict(node)
    assert result["type"] == "Agency"
    assert "weight" not in result


# ---------------------------------------------------------------------------
# process_graph_result: edge weight + sub-agency marking
# ---------------------------------------------------------------------------

def test_process_graph_result_awarded_edge_carries_weight():
    """AWARDED edges should carry obligatedAmount from the Contract end-node."""
    from src.api.api import process_graph_result
    vendor = _make_node(["Vendor"], {"id": "v1", "canonicalName": "ACME"}, element_id="v1")
    contract = _make_node(
        ["Contract"],
        {"id": "c1", "obligatedAmount": 2_000_000, "contractId": "C-001"},
        element_id="c1",
    )
    awarded = _make_rel("AWARDED", vendor, contract, element_id="r1")

    record = _MockRecord({"rel": awarded})
    result = process_graph_result([record])

    assert len(result["edges"]) == 1
    assert result["edges"][0]["data"]["weight"] == 2_000_000.0


def test_process_graph_result_subcontracted_edge_has_no_weight():
    """SUBCONTRACTED edges (vendor→vendor) should not carry a weight."""
    from src.api.api import process_graph_result
    prime = _make_node(["Vendor"], {"id": "v1", "canonicalName": "Prime"}, element_id="v1")
    sub = _make_node(["Vendor"], {"id": "v2", "canonicalName": "Sub"}, element_id="v2")
    rel = _make_rel("SUBCONTRACTED", prime, sub, element_id="r1")

    record = _MockRecord({"rel": rel})
    result = process_graph_result([record])

    assert len(result["edges"]) == 1
    assert "weight" not in result["edges"][0]["data"]


def test_process_graph_result_marks_subagencies():
    """Agencies that are sources of SUBAGENCY_OF edges must be marked isSubagency."""
    from src.api.api import process_graph_result
    parent = _make_node(["Agency"], {"id": "a1", "agencyName": "DoD"}, element_id="a1")
    child = _make_node(["Agency"], {"id": "a2", "agencyName": "Army"}, element_id="a2")
    rel = _make_rel("SUBAGENCY_OF", child, parent, element_id="r1")

    record = _MockRecord({"parent": parent, "child": child, "rel": rel})
    result = process_graph_result([record])

    nodes_by_id = {n["data"]["id"]: n["data"] for n in result["nodes"]}
    assert nodes_by_id["a2"].get("isSubagency") is True
    assert nodes_by_id["a1"].get("isSubagency") is None


def test_process_graph_result_no_subagencies_when_none_present():
    """No isSubagency flag set when graph has no SUBAGENCY_OF relationships."""
    from src.api.api import process_graph_result
    agency = _make_node(["Agency"], {"id": "a1", "agencyName": "DoD"}, element_id="a1")

    record = _MockRecord({"agency": agency})
    result = process_graph_result([record])

    assert result["nodes"][0]["data"].get("isSubagency") is None


# ---------------------------------------------------------------------------
# /graph/overview: edge weight in response
# ---------------------------------------------------------------------------

def test_graph_overview_edges_include_numeric_weight(client, mock_neo4j):
    """Overview edges must carry obligatedAmount as weight from Contract end-node.

    The endpoint now uses process_graph_result with actual AWARDED /
    AWARDED_CONTRACT relationships instead of the old aggregated edge builder.
    """
    vendor = _make_node(["Vendor"], {"id": "v1", "canonicalName": "ACME Corp"}, element_id="v1")
    contract = _make_node(
        ["Contract"],
        {"id": "c1", "obligatedAmount": 50_000_000.0, "contractId": "C-001"},
        element_id="c1",
    )
    agency = _make_node(["Agency"], {"id": "a1", "agencyName": "DoD"}, element_id="a1")
    awarded = _make_rel("AWARDED", vendor, contract, element_id="r1")
    awarded_contract = _make_rel("AWARDED_CONTRACT", agency, contract, element_id="r2")

    record = _MockRecord({"ra": awarded, "rac": awarded_contract})
    mock_neo4j.run.return_value = [record]

    response = client.get("/graph/overview")
    assert response.status_code == 200
    data = response.json()
    # Both AWARDED and AWARDED_CONTRACT edges should have weight from the contract
    edge_weights = [e["data"].get("weight") for e in data["edges"]]
    assert 50_000_000.0 in edge_weights


def test_graph_overview_vendor_node_has_weight(client, mock_neo4j):
    """Overview vendor nodes must expose totalContractValue as weight."""
    vendor = _make_node(
        ["Vendor"],
        {"id": "v1", "canonicalName": "ACME Corp", "totalContractValue": 2e9},
        element_id="v1",
    )
    contract = _make_node(
        ["Contract"],
        {"id": "c1", "obligatedAmount": 2e9, "contractId": "C-001"},
        element_id="c1",
    )
    agency = _make_node(["Agency"], {"id": "a1", "agencyName": "DoD"}, element_id="a1")
    awarded = _make_rel("AWARDED", vendor, contract, element_id="r1")
    awarded_contract = _make_rel("AWARDED_CONTRACT", agency, contract, element_id="r2")

    record = _MockRecord({"ra": awarded, "rac": awarded_contract})
    mock_neo4j.run.return_value = [record]

    response = client.get("/graph/overview")
    assert response.status_code == 200
    data = response.json()
    vendor_node = next(n for n in data["nodes"] if n["data"]["type"] == "Vendor")
    assert vendor_node["data"]["weight"] == 2_000_000_000.0


# ---------------------------------------------------------------------------
# Agency endpoints
# ---------------------------------------------------------------------------

def test_get_agencies_empty(client, mock_pg):
    mock_pg.fetchone.return_value = {"count": 0}
    mock_pg.fetchall.return_value = []

    response = client.get("/agencies")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_get_agencies_with_query(client, mock_pg):
    mock_pg.fetchone.return_value = {"count": 1}
    mock_pg.fetchall.return_value = [
        {"id": str(uuid4()), "agency_name": "Department of Defense", "agency_code": "097"}
    ]

    response = client.get("/agencies?q=defense")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["agency_name"] == "Department of Defense"


def test_get_agencies_pagination(client, mock_pg):
    mock_pg.fetchone.return_value = {"count": 50}
    mock_pg.fetchall.return_value = []

    response = client.get("/agencies?page=3&size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 3
    assert data["size"] == 10


def test_get_agencies_size_too_large(client):
    response = client.get("/agencies?size=200")
    assert response.status_code == 422


def test_get_agency_by_id_success(client, mock_pg):
    agency_id = uuid4()
    mock_pg.fetchone.return_value = {
        "id": str(agency_id),
        "agency_name": "Department of Defense",
        "agency_code": "097",
        "updated_at": "2024-01-01T00:00:00",
    }

    response = client.get(f"/agencies/{agency_id}")
    assert response.status_code == 200
    assert response.json()["agency_name"] == "Department of Defense"


def test_get_agency_by_id_not_found(client, mock_pg):
    mock_pg.fetchone.return_value = None
    response = client.get(f"/agencies/{uuid4()}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Contract endpoints
# ---------------------------------------------------------------------------

def test_get_contracts_empty(client, mock_pg):
    mock_pg.fetchone.return_value = {"count": 0}
    mock_pg.fetchall.return_value = []

    response = client.get("/contracts")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_get_contracts_filter_by_vendor(client, mock_pg):
    vendor_id = uuid4()
    mock_pg.fetchone.return_value = {"count": 2}
    mock_pg.fetchall.return_value = []

    response = client.get(f"/contracts?vendor_id={vendor_id}")
    assert response.status_code == 200
    # vendor_id must appear in the query params passed to execute
    params = mock_pg.execute.call_args_list[0][0][1]
    assert str(vendor_id) in params


def test_get_contract_by_id_success(client, mock_pg):
    contract_id = uuid4()
    mock_pg.fetchone.return_value = {
        "id": str(contract_id),
        "contract_id": "CONT-001",
        "vendor_id": str(uuid4()),
        "description": "IT services",
        "award_type": "A",
        "obligated_amount": 500_000.0,
        "signed_date": "2024-01-15",
        "resolution_method": "exact",
        "resolution_confidence": 1.0,
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
    }

    response = client.get(f"/contracts/{contract_id}")
    assert response.status_code == 200
    assert response.json()["contract_id"] == "CONT-001"


def test_get_contract_by_id_not_found(client, mock_pg):
    mock_pg.fetchone.return_value = None
    response = client.get(f"/contracts/{uuid4()}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Analytics endpoints — additional coverage
# ---------------------------------------------------------------------------

def test_insights_summary(client, mock_pg):
    mock_pg.fetchone.side_effect = [
        {"count": 1200},
        {"count": 85},
        {"count": 45000, "sum": 9_800_000_000.0},
    ]

    response = client.get("/insights/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["total_vendors"] == 1200
    assert data["total_agencies"] == 85
    assert data["total_contracts"] == 45000
    assert data["total_obligated_amount"] == 9_800_000_000.0


def test_insights_summary_null_sum_returns_zero(client, mock_pg):
    """When no contracts exist, SUM returns NULL — endpoint must return 0.0."""
    mock_pg.fetchone.side_effect = [
        {"count": 0},
        {"count": 0},
        {"count": 0, "sum": None},
    ]

    response = client.get("/insights/summary")
    assert response.status_code == 200
    assert response.json()["total_obligated_amount"] == 0.0


def test_agency_market_share(client, mock_pg):
    mock_pg.fetchall.return_value = [
        {
            "agency_name": "Department of Defense",
            "award_count": 500,
            "total_obligated": 5_000_000_000.0,
            "market_share_pct": 42.5,
        }
    ]

    response = client.get("/insights/agency-market-share")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["agency_name"] == "Department of Defense"


def test_agency_market_share_limit_param(client, mock_pg):
    mock_pg.fetchall.return_value = []
    response = client.get("/insights/agency-market-share?limit=5")
    assert response.status_code == 200
    params = mock_pg.execute.call_args[0][1]
    assert params == (5,)


def test_agency_market_share_limit_too_large(client):
    response = client.get("/insights/agency-market-share?limit=200")
    assert response.status_code == 422


def test_spending_over_time_invalid_period(client):
    """period must match ^(month|quarter|year)$ — anything else is 422."""
    agency_id = uuid4()
    response = client.get(f"/insights/agency/{agency_id}/spending-over-time?period=week")
    assert response.status_code == 422


def test_award_spikes_z_threshold_too_low(client):
    """z_threshold must be >= 1.0."""
    response = client.get("/insights/risk/award-spikes?z_threshold=0.5")
    assert response.status_code == 422


def test_new_entrants_days_too_large(client):
    """days must be <= 365."""
    response = client.get("/insights/risk/new-entrants?days=400")
    assert response.status_code == 422


def test_sole_source_returns_200(client, mock_neo4j):
    mock_neo4j.run.return_value = []
    response = client.get("/insights/risk/sole-source")
    assert response.status_code == 200
    assert response.json() == []


def test_sole_source_invalid_award_type(client):
    """award_type must match ^[A-Z]{1,2}$ — lowercase or 3+ chars rejected."""
    response = client.get("/insights/risk/sole-source?award_type=abc")
    assert response.status_code == 422


def test_sole_source_uses_correct_award_type(client, mock_neo4j):
    mock_neo4j.run.return_value = []
    client.get("/insights/risk/sole-source?award_type=B")
    call_kwargs = mock_neo4j.run.call_args[1]
    assert call_kwargs["award_type"] == "B"


def test_circular_subcontracts_returns_200(client, mock_neo4j):
    mock_neo4j.run.return_value = []
    response = client.get("/insights/risk/circular-subcontracts")
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# Graph endpoint — limit parameter validation
# ---------------------------------------------------------------------------

def test_vendor_graph_default_limit_is_500(client, mock_neo4j):
    mock_neo4j.run.return_value = []
    vendor_id = uuid4()
    client.get(f"/graph/vendor/{vendor_id}")
    call_kwargs = mock_neo4j.run.call_args[1]
    assert call_kwargs["limit"] == 500


def test_vendor_graph_custom_limit(client, mock_neo4j):
    mock_neo4j.run.return_value = []
    vendor_id = uuid4()
    client.get(f"/graph/vendor/{vendor_id}?limit=100")
    call_kwargs = mock_neo4j.run.call_args[1]
    assert call_kwargs["limit"] == 100


def test_vendor_graph_limit_too_small_rejected(client):
    response = client.get(f"/graph/vendor/{uuid4()}?limit=5")
    assert response.status_code == 422


def test_vendor_graph_limit_too_large_rejected(client):
    response = client.get(f"/graph/vendor/{uuid4()}?limit=9999")
    assert response.status_code == 422


def test_vendor_graph_cypher_orders_by_obligated_amount(client, mock_neo4j):
    mock_neo4j.run.return_value = []
    client.get(f"/graph/vendor/{uuid4()}")
    cypher = mock_neo4j.run.call_args[0][0]
    assert "obligatedAmount DESC" in cypher


def test_agency_graph_default_limit_is_1000(client, mock_neo4j):
    mock_neo4j.run.return_value = []
    agency_id = uuid4()
    client.get(f"/graph/agency/{agency_id}")
    call_kwargs = mock_neo4j.run.call_args[1]
    assert call_kwargs["limit"] == 1000


def test_agency_graph_limit_too_small_rejected(client):
    response = client.get(f"/graph/agency/{uuid4()}?limit=5")
    assert response.status_code == 422


def test_agency_graph_limit_too_large_rejected(client):
    response = client.get(f"/graph/agency/{uuid4()}?limit=9999")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Graph endpoint — /graph/contract/{id}
# ---------------------------------------------------------------------------

def test_contract_graph_returns_200(client, mock_neo4j):
    mock_neo4j.run.return_value = []
    response = client.get("/graph/contract/some-contract-id")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data


def test_contract_graph_cypher_queries_all_relationships(client, mock_neo4j):
    """Cypher must look for AWARDED, AWARDED_CONTRACT, and FUNDED relationships."""
    mock_neo4j.run.return_value = []
    client.get("/graph/contract/c1")
    cypher = mock_neo4j.run.call_args[0][0]
    assert "AWARDED" in cypher
    assert "AWARDED_CONTRACT" in cypher
    assert "FUNDED" in cypher


def test_contract_graph_passes_id_to_cypher(client, mock_neo4j):
    mock_neo4j.run.return_value = []
    client.get("/graph/contract/abc-123")
    call_kwargs = mock_neo4j.run.call_args[1]
    assert call_kwargs["id"] == "abc-123"


def test_contract_graph_returns_connected_nodes(client, mock_neo4j):
    """Full integration: vendor + contract + agency all appear in the response."""
    vendor = _make_node(["Vendor"], {"id": "v1", "canonicalName": "ACME"}, element_id="v1")
    contract = _make_node(
        ["Contract"],
        {"id": "c1", "obligatedAmount": 1_000_000, "contractId": "C-001"},
        element_id="c1",
    )
    agency = _make_node(["Agency"], {"id": "a1", "agencyName": "DoD"}, element_id="a1")
    awarded = _make_rel("AWARDED", vendor, contract, element_id="r1")
    awarded_contract = _make_rel("AWARDED_CONTRACT", agency, contract, element_id="r2")

    record = _MockRecord({"c": contract, "v": vendor, "ra": awarded, "aw_a": agency, "rac": awarded_contract})
    mock_neo4j.run.return_value = [record]

    response = client.get("/graph/contract/c1")
    assert response.status_code == 200
    data = response.json()
    node_types = {n["data"]["type"] for n in data["nodes"]}
    assert "Vendor" in node_types
    assert "Contract" in node_types
    assert "Agency" in node_types
    assert len(data["edges"]) == 2


# ---------------------------------------------------------------------------
# Graph endpoint — supply-chain, peers, hubs
# ---------------------------------------------------------------------------

def test_vendor_supply_chain_returns_200(client, mock_neo4j):
    mock_neo4j.run.return_value = []
    vendor_id = uuid4()
    response = client.get(f"/graph/vendor/{vendor_id}/supply-chain")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data and "edges" in data


def test_vendor_supply_chain_depth_validation(client):
    vendor_id = uuid4()
    # depth must be 1–5
    assert client.get(f"/graph/vendor/{vendor_id}/supply-chain?depth=0").status_code == 422
    assert client.get(f"/graph/vendor/{vendor_id}/supply-chain?depth=6").status_code == 422


def test_vendor_peers_returns_200(client, mock_neo4j):
    mock_neo4j.run.return_value = []
    vendor_id = uuid4()
    response = client.get(f"/graph/vendor/{vendor_id}/peers")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data and "edges" in data


def test_graph_hubs_returns_200(client, mock_neo4j):
    mock_neo4j.run.return_value = []
    response = client.get("/graph/hubs")
    assert response.status_code == 200
    assert response.json() == []


def test_graph_hubs_min_sub_count_too_low(client):
    response = client.get("/graph/hubs?min_sub_count=0")
    assert response.status_code == 422
