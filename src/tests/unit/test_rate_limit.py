"""Tests for per-user rate limiting (SlowAPI + in-memory storage).

Covers three areas:
  1. ``get_user_identifier`` key function — sub extraction and IP fallbacks.
  2. Rate limit enforcement — each tier (20/30/60 per minute) blocks at the
     correct threshold.
  3. User isolation — one user's counter does not affect another user's limit.
"""

import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from uuid import uuid4

# ---------------------------------------------------------------------------
# Environment setup — must happen before any app import
# ---------------------------------------------------------------------------

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_NAME", "testdb")
os.environ.setdefault("DB_USER", "testuser")
os.environ.setdefault("DB_SECRET_ARN", "arn:test")
os.environ.setdefault("COGNITO_USER_POOL_ID", "us-east-1_testpool")
os.environ.setdefault("COGNITO_REGION", "us-east-1")

from src.api.api import app  # noqa: E402
import auth  # noqa: E402  (src/api is on pythonpath via pytest.ini)
import rate_limit  # noqa: E402

get_current_user = auth.get_current_user

FAKE_USER = {"sub": "auth-bypass-user", "token_use": "access"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bearer_headers(sub: str) -> dict:
    """Return an Authorization header whose JWT carries the given ``sub``.

    The token is signed with a dummy secret — the rate limiter only decodes
    it *without* verification to extract the key; Cognito validation is
    bypassed by the ``mock_auth`` fixture.
    """
    from jose import jwt

    token = jwt.encode({"sub": sub}, "test-secret", algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _mock_request(auth_header: str = "", client_host: str = "1.2.3.4"):
    """Build a minimal mock ``Request`` for ``get_user_identifier`` unit tests."""
    req = MagicMock()
    req.headers.get = lambda k, default="": auth_header if k == "Authorization" else default
    req.client.host = client_host
    return req


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_auth():
    """Bypass JWT validation for every test in this module."""
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_limiter_storage():
    """Clear the in-memory rate limit counters before and after each test.

    This prevents counter state from a previous test bleeding into the next
    when the same ``sub`` would otherwise be reused.
    """
    try:
        rate_limit.limiter._storage.reset()
    except AttributeError:
        pass
    yield
    try:
        rate_limit.limiter._storage.reset()
    except AttributeError:
        pass


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
# get_user_identifier — key function unit tests
# ---------------------------------------------------------------------------


def test_get_user_identifier_extracts_sub_from_valid_jwt():
    """A well-formed bearer JWT with a ``sub`` claim returns that sub."""
    from jose import jwt

    token = jwt.encode({"sub": "user-abc-123"}, "secret", algorithm="HS256")
    req = _mock_request(auth_header=f"Bearer {token}")
    assert rate_limit.get_user_identifier(req) == "user-abc-123"


def test_get_user_identifier_falls_back_to_ip_when_no_auth_header():
    """No Authorization header → falls back to ``request.client.host``."""
    req = _mock_request(auth_header="", client_host="10.0.0.1")
    assert rate_limit.get_user_identifier(req) == "10.0.0.1"


def test_get_user_identifier_falls_back_to_ip_on_malformed_token():
    """A non-JWT bearer value → falls back to remote address."""
    req = _mock_request(auth_header="Bearer not-a-real-jwt", client_host="10.0.0.2")
    assert rate_limit.get_user_identifier(req) == "10.0.0.2"


def test_get_user_identifier_falls_back_to_ip_when_sub_is_absent():
    """A valid JWT with no ``sub`` claim → falls back to remote address."""
    from jose import jwt

    token = jwt.encode({"scope": "openid"}, "secret", algorithm="HS256")
    req = _mock_request(auth_header=f"Bearer {token}", client_host="10.0.0.3")
    assert rate_limit.get_user_identifier(req) == "10.0.0.3"


# ---------------------------------------------------------------------------
# Rate limit enforcement — threshold tests
# ---------------------------------------------------------------------------


def test_rate_limit_graph_endpoint_blocked_at_21st_request(client, mock_neo4j):
    """Graph endpoints enforce a 20/minute limit: request 21 returns 429."""
    mock_neo4j.run.return_value = []
    sub = f"rl-graph-{uuid4()}"
    headers = _make_bearer_headers(sub)

    for i in range(20):
        r = client.get("/graph/overview", headers=headers)
        assert r.status_code == 200, f"request {i + 1} was unexpectedly rate-limited"

    assert client.get("/graph/overview", headers=headers).status_code == 429


def test_rate_limit_analytics_endpoint_blocked_at_31st_request(client, mock_pg):
    """Analytics endpoints enforce a 30/minute limit: request 31 returns 429."""
    # /insights/summary calls fetchone() 3× per request; return_value satisfies all
    mock_pg.fetchone.return_value = {"count": 0, "sum": None}
    sub = f"rl-analytics-{uuid4()}"
    headers = _make_bearer_headers(sub)

    for i in range(30):
        r = client.get("/insights/summary", headers=headers)
        assert r.status_code == 200, f"request {i + 1} was unexpectedly rate-limited"

    assert client.get("/insights/summary", headers=headers).status_code == 429


def test_rate_limit_standard_endpoint_blocked_at_61st_request(client, mock_pg):
    """Standard endpoints enforce a 60/minute limit: request 61 returns 429."""
    mock_pg.fetchone.return_value = {"count": 0}
    mock_pg.fetchall.return_value = []
    sub = f"rl-standard-{uuid4()}"
    headers = _make_bearer_headers(sub)

    for i in range(60):
        r = client.get("/vendors", headers=headers)
        assert r.status_code == 200, f"request {i + 1} was unexpectedly rate-limited"

    assert client.get("/vendors", headers=headers).status_code == 429


# ---------------------------------------------------------------------------
# User isolation — independent counters per sub
# ---------------------------------------------------------------------------


def test_rate_limit_users_have_independent_counters(client, mock_neo4j):
    """Exhausting user A's limit must not affect user B's counter."""
    mock_neo4j.run.return_value = []
    sub_a = f"rl-user-a-{uuid4()}"
    sub_b = f"rl-user-b-{uuid4()}"

    # Drain user A's graph limit entirely
    for _ in range(20):
        client.get("/graph/overview", headers=_make_bearer_headers(sub_a))

    # A is now blocked
    assert client.get("/graph/overview", headers=_make_bearer_headers(sub_a)).status_code == 429
    # B is unaffected — should still receive 200
    assert client.get("/graph/overview", headers=_make_bearer_headers(sub_b)).status_code == 200


# ---------------------------------------------------------------------------
# Public endpoints — must never be rate-limited
# ---------------------------------------------------------------------------


def test_public_endpoints_not_rate_limited(client):
    """``/`` and ``/health`` have no limiter decorator and must always return 200."""
    for _ in range(100):
        assert client.get("/").status_code == 200
        assert client.get("/health").status_code == 200
