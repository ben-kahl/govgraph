import json
import os
import pytest
from unittest.mock import MagicMock, patch
from src.processing.sam_proxy import lambda_handler

@pytest.fixture
def mock_secrets(mocker):
    return mocker.patch('src.processing.sam_proxy.get_secret')

@pytest.fixture
def mock_requests(mocker):
    return mocker.patch('src.processing.sam_proxy.requests.get')

def test_lambda_handler_success_uei(mocker, mock_secrets, mock_requests):
    # Mock secrets
    mock_secrets.return_value = {'api_key': 'fake-key'}
    
    # Mock SAM API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = json.dumps({'entityData': [{'name': 'TEST'}]})
    mock_requests.return_value = mock_response

    event = {'ueiSAM': 'UEI123'}
    with patch.dict(os.environ, {"SAM_API_KEY_SECRET_ARN": "arn:aws:secrets:123"}):
        result = lambda_handler(event, None)

    assert result['statusCode'] == 200
    assert 'entityData' in result['body']
    
    # Verify API call
    args, kwargs = mock_requests.call_args
    assert kwargs['params']['ueiSAM'] == 'UEI123'
    assert kwargs['params']['api_key'] == 'fake-key'

def test_lambda_handler_missing_params(mocker, mock_secrets):
    event = {}
    with patch.dict(os.environ, {"SAM_API_KEY_SECRET_ARN": "arn:aws:secrets:123"}):
        mock_secrets.return_value = {'api_key': 'key'}
        result = lambda_handler(event, None)

    assert result['statusCode'] == 400
    assert 'Missing ueiSAM or entityName' in result['body']

def test_lambda_handler_missing_secret_config(mocker):
    event = {'ueiSAM': 'UEI123'}
    # Clear env var
    with patch.dict(os.environ, {}, clear=True):
        result = lambda_handler(event, None)

    assert result['statusCode'] == 500
    assert 'SAM_API_KEY_SECRET_ARN not set' in result['body']
    
def test_lambda_handler_api_failure(mocker, mock_secrets, mock_requests):
    mock_secrets.return_value = {'api_key': 'fake-key'}
    
    # Mock SAM API failure
    mock_requests.side_effect = Exception("API connection error")

    event = {'ueiSAM': 'UEI123'}
    with patch.dict(os.environ, {"SAM_API_KEY_SECRET_ARN": "arn:aws:secrets:123"}):
        result = lambda_handler(event, None)

    assert result['statusCode'] == 500
    assert 'API connection error' in result['body']
