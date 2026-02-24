import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from uuid import uuid4

# Set environment variables before importing app
os.environ["DB_HOST"] = "localhost"
os.environ["DB_NAME"] = "testdb"
os.environ["DB_USER"] = "testuser"
os.environ["DB_SECRET_ARN"] = "arn:test"
os.environ["COGNITO_USER_POOL_ID"] = "us-east-1_testpool"
os.environ["COGNITO_REGION"] = "us-east-1"

from src.api.api import app, limiter
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


@pytest.fixture(autouse=True)
def disable_rate_limiting():
    """Disable slowapi rate limiting during tests."""
    limiter.enabled = False
    yield
    limiter.enabled = True


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

    response = client.get("/analytics/market-share")
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
    response = client.get(f"/analytics/agency/{agency_id}/spending-over-time")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["contract_count"] == 5


def test_award_spikes(client, mock_pg):
    mock_pg.fetchall.return_value = [
        {
            "canonical_name": "BIG VENDOR",
            "contract_id": "C-001",
            "obligated_amount": 9999999.0,
            "avg_amount": 100000.0,
            "z_score": 4.5,
        }
    ]

    response = client.get("/analytics/risk/award-spikes?z_threshold=3")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["z_score"] == 4.5


def test_new_entrants(client, mock_pg):
    mock_pg.fetchall.return_value = [
        {
            "canonical_name": "STARTUP LLC",
            "first_award": "2026-01-15",
            "award_count": 2,
            "total_value": 750000.0,
        }
    ]

    response = client.get("/analytics/risk/new-entrants")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["canonical_name"] == "STARTUP LLC"


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
