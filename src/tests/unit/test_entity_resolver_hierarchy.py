import json
import pytest
from unittest.mock import MagicMock, patch
from src.processing.entity_resolver import lambda_handler

@pytest.fixture
def mock_db_stuff(mocker):
    # Mock get_db_connection
    mock_conn = MagicMock()
    mocker.patch('src.processing.entity_resolver.get_db_connection', return_value=mock_conn)
    # Mock get_secret to avoid actual AWS call
    mocker.patch('src.processing.entity_resolver.get_secret', return_value={'username': 'user', 'password': 'pw'})
    return mock_conn

def test_lambda_handler_routes_prime_and_sub(mocker, mock_db_stuff):
    mock_conn = mock_db_stuff
    
    # Mock the processors
    mock_prime = mocker.patch('src.processing.entity_resolver.process_prime_award', return_value=1)
    mock_sub = mocker.patch('src.processing.entity_resolver.process_sub_award', return_value=1)
    
    # Create a dummy event with one prime and one subaward
    event = {
        'Records': [
            {
                'body': json.dumps({
                    'type': 'prime',
                    'data': {'Award ID': 'PRIME1', 'Recipient Name': 'PRIME CORP'}
                })
            },
            {
                'body': json.dumps({
                    'type': 'subaward',
                    'data': {'Sub-Award ID': 'SUB1', 'Sub-Awardee Name': 'SUB CORP'}
                })
            }
        ]
    }
    
    response = lambda_handler(event, None)
    
    assert json.loads(response['body'])['processed'] == 2
    assert mock_prime.call_count == 1
    assert mock_sub.call_count == 1
    
    # Verify data passed to processors
    mock_prime.assert_called_with({'Award ID': 'PRIME1', 'Recipient Name': 'PRIME CORP'}, mock_conn)
    mock_sub.assert_called_with({'Sub-Award ID': 'SUB1', 'Sub-Awardee Name': 'SUB CORP'}, mock_conn)

def test_process_prime_award_agency_hierarchy(mocker, mock_db_stuff):
    mock_conn = mock_db_stuff
    cur = mock_conn.cursor.return_value.__enter__.return_value
    
    # Mock resolve_vendor and resolve_agency
    mock_resolve_vendor = mocker.patch('src.processing.entity_resolver.resolve_vendor', 
                                     return_value=('v-uuid', 'CANONICAL CORP', 'EXACT', 1.0))
    mock_resolve_agency = mocker.patch('src.processing.entity_resolver.resolve_agency',
                                     side_effect=['agency-uuid', 'subagency-uuid', 'funding-uuid', 'fundsub-uuid'])
    
    from src.processing.entity_resolver import process_prime_award
    
    contract_data = {
        'Award ID': 'AWD1',
        'Recipient Name': 'VEND1',
        'Awarding Agency': 'DEPT OF X',
        'Awarding Agency Code': 'X00',
        'Awarding Sub Agency': 'BUREAU OF Y',
        'Awarding Sub Agency Code': 'Y11'
    }
    
    cur.fetchone.return_value = ['raw-uuid']
    
    result = process_prime_award(contract_data, mock_conn)
    
    assert result == 1
    assert mock_resolve_agency.call_count == 4
    # Check hierarchy linkage
    # First call: Awarding Top Tier
    mock_resolve_agency.assert_any_call('DEPT OF X', 'X00', conn=mock_conn)
    # Second call: Awarding Sub Tier (should pass parent_agency_id)
    mock_resolve_agency.assert_any_call('BUREAU OF Y', 'Y11', parent_agency_id='agency-uuid', conn=mock_conn)
