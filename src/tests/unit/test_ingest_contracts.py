import unittest
from unittest.mock import patch, MagicMock
from src.ingestion.ingest_contracts import fetch_contracts, store_raw_contracts


class TestIngestContracts(unittest.TestCase):

    @patch('src.ingestion.ingest_contracts.requests.post')
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
        results = fetch_contracts("2023-01-01", "2023-01-02")

        # Assertions
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["Award ID"], "123")
        mock_post.assert_called_once()

    @patch('src.ingestion.ingest_contracts.requests.post')
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
        results = fetch_contracts("2023-01-01", "2023-01-02")

        # Assertions
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["Award ID"], "123")
        self.assertEqual(results[1]["Award ID"], "456")
        self.assertEqual(mock_post.call_count, 2)

    @patch('src.ingestion.ingest_contracts.get_db_connection')
    def test_store_raw_contracts(self, mock_get_conn):
        # Mock Database connection
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_get_conn.return_value = mock_conn

        # Test Data
        contracts = [
            {"Award ID": "123", "Recipient Name": "Test Corp"},
            {"Award ID": "456", "Recipient Name": "Another Corp"}
        ]

        # Call function
        store_raw_contracts(contracts)

        # Assertions
        self.assertEqual(mock_cur.execute.call_count, 2)
        mock_conn.commit.assert_called_once()
        mock_cur.close.assert_called_once()
        mock_conn.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
