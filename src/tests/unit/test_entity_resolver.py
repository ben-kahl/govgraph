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
    # Mock successful SAM proxy response
    mock_lambda = mocker.patch(
        'src.processing.entity_resolver.get_lambda_client')
    mock_lambda_instance = mock_lambda.return_value

    mock_payload = {
        'statusCode': 200,
        'body': json.dumps({
            'entityData': [{
                'entityRegistration': {
                    'legalBusinessName': 'ACME CORP',
                    'ueiSAM': 'UEI123456789',
                    'duns': '123456789'
                }
            }]
        })
    }

    mock_response = MagicMock()
    mock_response.__getitem__.return_value.read.return_value = json.dumps(
        mock_payload).encode('utf-8')
    mock_lambda_instance.invoke.return_value = mock_response

    with patch('src.processing.entity_resolver.SAM_PROXY_LAMBDA_NAME', 'test-proxy'):
        result = get_sam_entity(uei='UEI123456789')

    assert result is not None
    assert result['canonical_name'] == 'ACME CORP'
    assert result['uei'] == 'UEI123456789'


def test_resolve_vendor_sam_match_new_vendor(mocker, mock_conn):

    conn, cur = mock_conn

    mocker.patch('src.processing.entity_resolver.get_cache_table')

    # Tier 1: SAM Match

    mocker.patch('src.processing.entity_resolver.get_sam_entity', return_value={
        'canonical_name': 'SAM VENDOR INC',
        'uei': 'SAMUEI123',
        'duns': 'SAMDUNS123'
    })

    # Mock DB: No existing vendor

    cur.fetchone.return_value = None

    vendor_id, name, method, conf = resolve_vendor(
        "Messy Vendor Name", uei="SAMUEI123", conn=conn
    )

    assert name == 'SAM VENDOR INC'

    assert method == 'SAM_API_MATCH'

    assert conf == 1.0

    # Verify insert was called

    assert any("INSERT INTO vendors" in str(call)
               for call in cur.execute.call_args_list)


def test_resolve_vendor_exact_uei_match(mocker, mock_conn):

    conn, cur = mock_conn

    mocker.patch('src.processing.entity_resolver.get_cache_table')

    # Tier 2: UEI Match in RDS

    mocker.patch('src.processing.entity_resolver.get_sam_entity',
                 return_value=None)

    cur.fetchone.return_value = {
        'id': 'uuid-123', 'canonical_name': 'EXISTING CORP'}

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

    # Tier 4: DynamoDB Cache Match
    mocker.patch('src.processing.entity_resolver.get_sam_entity',
                 return_value=None)
    # Fall through T1, T2, T3
    cur.fetchone.return_value = None

    mock_cache.get_item.return_value = {
        'Item': {
            'vendor_id': 'uuid-cache',
            'canonical_name': 'CACHED CORP',
            'confidence': '0.95'
        }
    }

    vendor_id, name, method, conf = resolve_vendor(
        "Messy Cached Name", conn=conn
    )

    assert name == 'CACHED CORP'
    assert method == 'CACHE_MATCH'


def test_resolve_vendor_fuzzy_match(mocker, mock_conn):

    conn, cur = mock_conn

    mock_fuzzy = mocker.patch('src.processing.entity_resolver.process')

    # Mock getters to avoid actual AWS calls and environment variable errors

    mocker.patch('src.processing.entity_resolver.get_cache_table')

    mocker.patch('src.processing.entity_resolver.get_sam_entity',
                 return_value=None)

    mocker.patch('src.processing.entity_resolver.refresh_canonical_names_cache',
                 return_value=['TARGET CORP'])

    # Tier 5: Fuzzy Match

    # Call 1: Tier 3 (Exact name match) -> returns None

    # Call 2: Tier 5 (Fuzzy name lookup) -> returns the matched record

    cur.fetchone.side_effect = [None, {'id': 'uuid-fuzzy'}]

    mock_fuzzy.extractOne.return_value = ('TARGET CORP', 95, 0)

    vendor_id, name, method, conf = resolve_vendor(
        "Targit Corp", conn=conn
    )

    assert name == 'TARGET CORP'

    assert vendor_id == 'uuid-fuzzy'

    assert method == 'FUZZY_MATCH'

    assert conf == 0.95

    # Verify we didn't fall through to LLM (which would be a 3rd call or more)

    assert cur.fetchone.call_count == 2
