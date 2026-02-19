import unittest
from unittest.mock import patch, MagicMock
from src.ingestion.scraper import fetch_contracts


class TestIngestContracts(unittest.TestCase):

    @patch('src.ingestion.scraper.requests.post')
    def test_fetch_contracts_single_page(self, mock_post):
        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "page_metadata": {"hasNext": False},
            "results": [{"Award ID": "123", "Recipient Name": "Test Corp"}]
        }
        mock_post.return_value = mock_response

        # Call function
        results = fetch_contracts("2023-01-01", "2023-01-02", spending_level="awards")

        # Assertions
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["Award ID"], "123")
        
        # Verify spending_level in payload
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs['json']['spending_level'], "awards")
        mock_post.assert_called_once()

    @patch('src.ingestion.scraper.requests.post')
    def test_fetch_contracts_pagination(self, mock_post):
        # Mock API response for two pages
        mock_response_p1 = MagicMock()
        mock_response_p1.status_code = 200
        mock_response_p1.json.return_value = {
            "page_metadata": {"hasNext": True},
            "results": [{"Award ID": "123"}]
        }

        mock_response_p2 = MagicMock()
        mock_response_p2.status_code = 200
        mock_response_p2.json.return_value = {
            "page_metadata": {"hasNext": False},
            "results": [{"Award ID": "456"}]
        }

        mock_post.side_effect = [mock_response_p1, mock_response_p2]

        # Call function
        results = fetch_contracts("2023-01-01", "2023-01-02", spending_level="subawards")

        # Assertions
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["Award ID"], "123")
        self.assertEqual(results[1]["Award ID"], "456")
        self.assertEqual(mock_post.call_count, 2)
        
        # Verify spending_level in payload of second call
        args, kwargs = mock_post.call_args_list[1]
        self.assertEqual(kwargs['json']['spending_level'], "subawards")


if __name__ == '__main__':
    unittest.main()
