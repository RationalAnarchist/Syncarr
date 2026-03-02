import asyncio
import httpx
from fastapi.testclient import TestClient
from main import app
from unittest import mock

client = TestClient(app)

def test_link_prowlarr():
    # We will mock the scanner to ensure we have a valid Prowlarr to avoid 400
    # and mock the add_app_to_prowlarr function.

    mock_configs = [
        {"app": "Prowlarr", "apiKey": "test_prowlarr_key", "port": "9696", "urlBase": "/prowlarr"},
        {"app": "Sonarr", "apiKey": "test_sonarr_key", "port": "8989", "urlBase": "/sonarr"}
    ]

    with mock.patch('main.scan_configs', return_value=mock_configs):
        with mock.patch('main.add_app_to_prowlarr', new_callable=mock.AsyncMock) as mock_add_app:
            mock_add_app.return_value = {"id": 1, "name": "Sonarr"}
            response = client.post("/api/link/prowlarr")
        print(response.json())
        assert response.status_code == 200

if __name__ == "__main__":
    test_link_prowlarr()
