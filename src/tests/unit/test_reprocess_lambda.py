import json
import pytest
from unittest.mock import MagicMock, patch
from src.processing.reprocess_lambda import lambda_handler, fetch_batch_details

@pytest.fixture
def mock_conn():
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    return conn, cur

@pytest.fixture
def mock_requests(mocker):
    return mocker.patch('src.processing.reprocess_lambda.session.post')

def test_fetch_batch_details_success(mock_requests):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": [{"Award ID": "AWARD1", "Recipient Name": "VENDOR1"}]}
    mock_requests.return_value = mock_response

    results = fetch_batch_details(["AWARD1"])
    assert len(results) == 1
    assert results[0]["Award ID"] == "AWARD1"
    assert mock_requests.called

def test_fetch_batch_details_failure(mock_requests):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_requests.return_value = mock_response

    results = fetch_batch_details(["AWARD1"])
    assert results == []

def test_lambda_handler_reprocesses_correctly(mocker, mock_conn, mock_requests):
    conn, cur = mock_conn
    
    # Mock DB query for records to reprocess
    cur.fetchall.return_value = [
        {'usaspending_id': 'AWARD1', 'raw_id': 'uuid-raw-1'}
    ]
    
    # Mock API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [{
            "Award ID": "AWARD1",
            "Recipient Name": "REFINED VENDOR",
            "Recipient DUNS": "DUNS123",
            "Recipient UEI": "UEI123",
            "Awarding Agency": "AGENCY1",
            "Awarding Agency Code": "CODE1",
            "Contract Award Type": "TYPE1",
            "Description": "DESC1",
            "Start Date": "2023-01-01"
        }]
    }
    mock_requests.return_value = mock_response
    
    # Mock resolver functions
    mocker.patch('src.processing.reprocess_lambda.get_db_connection', return_value=conn)
    mocker.patch('src.processing.reprocess_lambda.resolve_vendor', return_value=('v-123', 'REFINED VENDOR', 'METHOD', 1.0))
    mocker.patch('src.processing.reprocess_lambda.resolve_agency', return_value='a-123')
    
    event = {'limit': 10, 'batch_size': 5}
    result = lambda_handler(event, None)
    
    assert result['statusCode'] == 200
    body = json.loads(result['body'])
    assert body['processed'] == 1
    assert body['updated'] == 1
    
    # Verify updates were called
    assert any("UPDATE raw_contracts" in str(call) for call in cur.execute.call_args_list)
    assert any("UPDATE contracts" in str(call) for call in cur.execute.call_args_list)
