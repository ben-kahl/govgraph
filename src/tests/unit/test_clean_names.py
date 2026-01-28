import unittest
from unittest.mock import patch, MagicMock
from src.processing.clean_names import standardize_name


class TestCleanNames(unittest.TestCase):

    @patch('src.processing.clean_names.get_bedrock_client')
    def test_standardize_name_success(self, mock_get_client):
        # Mock Bedrock response
        mock_client = MagicMock()
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = b'{"content": [{"text": "Lockheed Martin Corporation"}]}'

        mock_client.invoke_model.return_value = {"body": mock_response_body}
        mock_get_client.return_value = mock_client

        # Call function
        result = standardize_name("L.M. Corp")

        # Assertions
        self.assertEqual(result, "Lockheed Martin Corporation")
        mock_client.invoke_model.assert_called_once()

    @patch('src.processing.clean_names.get_bedrock_client')
    def test_standardize_name_error(self, mock_get_client):
        # Mock Bedrock error (exception)
        mock_client = MagicMock()
        mock_client.invoke_model.side_effect = Exception("Bedrock error")
        mock_get_client.return_value = mock_client

        # Call function (should return original name on error)
        result = standardize_name("Bad Name")

        # Assertions
        self.assertEqual(result, "Bad Name")
        mock_client.invoke_model.assert_called_once()


if __name__ == '__main__':
    unittest.main()
