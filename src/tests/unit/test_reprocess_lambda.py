import json
import pytest
from unittest.mock import MagicMock, patch
from src.processing.reprocess_lambda import lambda_handler

@pytest.fixture
def mock_conn():
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    return conn, cur

def test_lambda_handler_reprocesses_correctly(mocker, mock_conn):
    conn, cur = mock_conn
    
    # Mock DB query for records to reprocess
    cur.fetchall.return_value = [
        {'raw_payload': {'Award ID': 'AWARD1'}},
        {'raw_payload': {'Award ID': 'AWARD2'}}
    ]
    
    mocker.patch('src.processing.reprocess_lambda.get_db_connection', return_value=conn)
    mock_process_prime = mocker.patch('src.processing.reprocess_lambda.process_prime_award', return_value=1)
    
    event = {'limit': 10}
    result = lambda_handler(event, None)
    
    assert result['statusCode'] == 200
    body = json.loads(result['body'])
    assert body['reprocessed_prime'] == 2
    
    assert mock_process_prime.call_count == 2
