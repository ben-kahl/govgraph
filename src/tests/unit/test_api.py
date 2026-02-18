from src.api.api import app
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import json
from uuid import uuid4

# Set environment variables before importing app
import os
os.environ["DB_HOST"] = "localhost"
os.environ["DB_NAME"] = "testdb"
os.environ["DB_USER"] = "testuser"
os.environ["DB_SECRET_ARN"] = "arn:test"


client = TestClient(app)


@pytest.fixture
def mock_pg():
    with patch('src.api.api.get_pg_connection') as mock:
        conn = MagicMock()
        cur = conn.cursor.return_value.__enter__.return_value
        mock.return_value = conn
        yield cur


def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "GovGraph API"


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_get_vendors_empty(mock_pg):
    mock_pg.fetchone.return_value = {'count': 0}
    mock_pg.fetchall.return_value = []

    response = client.get("/vendors")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_get_vendor_by_id_success(mock_pg):
    vendor_id = uuid4()
    mock_pg.fetchone.return_value = {
        'id': str(vendor_id),
        'canonical_name': 'ACME CORP',
        'uei': 'UEI123',
        'duns': 'DUNS123',
        'resolved_by_llm': False,
        'resolution_confidence': 1.0,
        'created_at': '2023-01-01T00:00:00',
        'updated_at': '2023-01-01T00:00:00'
    }

    response = client.get(f"/vendors/{vendor_id}")
    assert response.status_code == 200
    assert response.json()["canonical_name"] == "ACME CORP"


def test_get_vendor_by_id_not_found(mock_pg):
    mock_pg.fetchone.return_value = None
    response = client.get(f"/vendors/{uuid4()}")
    assert response.status_code == 404
