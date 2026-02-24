import json
import os
import uuid
import pytest
from unittest.mock import MagicMock, patch
from src.processing.entity_resolver import resolve_vendor, get_sam_entity


@pytest.fixture
def mock_conn():
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    return conn, cur


def test_get_sam_entity_success(mocker):
    # Mock secrets and requests
    mock_get_secret = mocker.patch('src.processing.entity_resolver.get_secret')
    mock_get_secret.return_value = {'api_key': 'fake-key'}
    
    mock_requests = mocker.patch('src.processing.entity_resolver.requests.get')
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'entityData': [{
            'entityRegistration': {
                'legalBusinessName': 'ACME CORP',
                'ueiSAM': 'UEI123456789',
                'duns': '123456789'
            }
        }]
    }
    mock_requests.return_value = mock_response

    with patch('src.processing.entity_resolver.SAM_API_KEY_SECRET_ARN', "arn:aws:secrets:123"):
        result = get_sam_entity(uei='UEI123456789')

    assert result is not None
    assert result['canonical_name'] == 'ACME CORP'
    assert result['uei'] == 'UEI123456789'
    
    # Verify API call
    args, kwargs = mock_requests.call_args
    assert kwargs['params']['ueiSAM'] == 'UEI123456789'
    assert kwargs['params']['api_key'] == 'fake-key'

def test_get_sam_entity_no_config(mocker):
    with patch('src.processing.entity_resolver.SAM_API_KEY_SECRET_ARN', None):
        result = get_sam_entity(uei='UEI123')
    assert result is None


def test_resolve_vendor_sam_match_new_vendor(mocker, mock_conn):
    conn, cur = mock_conn
    mocker.patch('src.processing.entity_resolver.get_cache_table', 
                 return_value=MagicMock(**{'get_item.return_value': {}}))
    # Mock uuid to return a predictable value
    mocker.patch('src.processing.entity_resolver.uuid.uuid4', return_value='new-uuid')

    # Tier 4: SAM Match
    mocker.patch('src.processing.entity_resolver.get_sam_entity', return_value={
        'canonical_name': 'SAM VENDOR INC',
        'uei': 'SAMUEI123',
        'duns': 'SAMDUNS123'
    })

    # Sequence for Tier 1-4: 
    # 1. Tier 1 Cache ID check (miss)
    # 2. Tier 2 Exact ID check (miss)
    # 3. Tier 3 Exact Name check (miss)
    # 4. Tier 4 SAM result existing check (miss)
    # 5. Tier 4 SAM Insert RETURNING id
    cur.fetchone.side_effect = [None, None, None, None, {'id': 'new-uuid'}]

    vendor_id, name, method, conf = resolve_vendor(
        "Messy Vendor Name", uei="SAMUEI123", conn=conn
    )

    assert name == 'SAM VENDOR INC'
    assert method == 'SAM_API_MATCH'
    assert vendor_id == 'new-uuid'


def test_resolve_vendor_exact_uei_match(mocker, mock_conn):
    conn, cur = mock_conn
    mocker.patch('src.processing.entity_resolver.get_cache_table', 
                 return_value=MagicMock(**{'get_item.return_value': {}}))
    mocker.patch('src.processing.entity_resolver.get_sam_entity', return_value=None)

    # Tier 2: UEI Match in RDS
    cur.fetchone.return_value = {'id': 'uuid-123', 'canonical_name': 'EXISTING CORP'}

    vendor_id, name, method, conf = resolve_vendor(
        "Existing Corp Inc", uei="UEI123", conn=conn
    )

    assert vendor_id == 'uuid-123'
    assert name == 'EXISTING CORP'
    assert method == 'DUNS_UEI_MATCH'


def test_resolve_vendor_cache_match(mocker, mock_conn):
    conn, cur = mock_conn
    mock_get_cache = mocker.patch(
        'src.processing.entity_resolver.get_cache_table')
    mock_cache = mock_get_cache.return_value

    # Tier 1: DynamoDB Cache Match
    # Mock cache hit
    mock_cache.get_item.return_value = {
        'Item': {
            'vendor_id': 'uuid-cache',
            'canonical_name': 'CACHED CORP',
            'confidence': '0.95'
        }
    }
    
    # Mock the verification check in RDS (Tier 1 now includes a check)
    cur.fetchone.return_value = ('uuid-cache',)

    vendor_id, name, method, conf = resolve_vendor(
        "Messy Cached Name", conn=conn
    )

    assert name == 'CACHED CORP'
    assert method == 'CACHE_MATCH'
    assert vendor_id == 'uuid-cache'
    
    # Should only have 1 DB call for verification
    assert cur.fetchone.call_count == 1


def test_resolve_vendor_fuzzy_match(mocker, mock_conn):
    conn, cur = mock_conn
    
    # Reset global cache to ensure it fetches from our mock
    import src.processing.entity_resolver as er
    er.CANONICAL_NAMES_CACHE = None
    er.CACHE_EXPIRY = None

    mock_fuzzy = mocker.patch('src.processing.entity_resolver.process')
    mocker.patch('src.processing.entity_resolver.get_cache_table', 
                 return_value=MagicMock(**{'get_item.return_value': {}}))
    mocker.patch('src.processing.entity_resolver.get_sam_entity', return_value=None)
    mocker.patch('src.processing.entity_resolver.refresh_canonical_names_cache',
                 return_value=(['TARGET CORP'], {'TARGET': 'TARGET CORP'}))
    # Mock LLM fallback just in case it falls through
    mocker.patch('src.processing.entity_resolver.call_bedrock_standardization_with_retry', 
                 return_value='LLM FALLBACK')

    # Tier 1 Cache: Skip (mocked miss)
    # Tier 2 Exact ID: cur.fetchone() -> None
    # Tier 3 Exact Name: cur.fetchone() -> None
    # Tier 4 SAM: Skip (mocked None from get_sam_entity)
    # Tier 5 Fuzzy Match lookup: cur.fetchone() -> {'id': 'uuid-fuzzy'}
    
    cur.fetchone.side_effect = [None, None, {'id': 'uuid-fuzzy'}]
    mock_fuzzy.extractOne.return_value = ('TARGET CORP', 95, 0)

    # Pass both duns and uei to ensure Tier 2 is fully covered
    vendor_id, name, method, conf = resolve_vendor("Targit Corp", duns="DUNS-FUZZY", uei="UEI-FUZZY", conn=conn)

    assert name == 'TARGET CORP'
    assert vendor_id == 'uuid-fuzzy'
    assert method == 'FUZZY_MATCH'
    
    # Total 3 DB calls (ID check, Name check, Matched name lookup)
    assert cur.fetchone.call_count == 3
