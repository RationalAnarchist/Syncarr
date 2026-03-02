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

def test_link_downloaders():
    mock_configs = [
        {"app": "Sonarr", "apiKey": "test_sonarr_key", "port": "8989", "urlBase": "/sonarr"},
        {"app": "Radarr", "apiKey": "test_radarr_key", "port": "7878", "urlBase": "/radarr"}
    ]

    with mock.patch('main.scan_configs', return_value=mock_configs):
        with mock.patch('main.add_download_client', new_callable=mock.AsyncMock) as mock_add_client:
            mock_add_client.return_value = {"id": 1, "name": "qBittorrent"}

            payload = {
                "qbittorrent": {
                    "host": "qbittorrent",
                    "port": 8080,
                    "username": "admin",
                    "password": "password"
                },
                "nzbget": {
                    "host": "nzbget",
                    "port": 6789,
                    "username": "admin",
                    "password": "password",
                    "category": "tv"
                }
            }

            response = client.post("/api/link/downloaders", json=payload)

        print(response.json())
        assert response.status_code == 200
        # Expected to be called 4 times: (Sonarr qbit, Sonarr nzbget, Radarr qbit, Radarr nzbget)
        assert mock_add_client.call_count == 4

if __name__ == "__main__":
    test_link_prowlarr()
    test_link_downloaders()
