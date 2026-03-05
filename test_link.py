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

def test_link_overseerr():
    mock_configs = [
        {"app": "Sonarr", "apiKey": "test_sonarr_key", "port": "8989", "urlBase": "/sonarr"},
        {"app": "Radarr", "apiKey": "test_radarr_key", "port": "7878", "urlBase": "/radarr"}
    ]

    with mock.patch('main.scan_configs', return_value=mock_configs):
        with mock.patch('main.add_radarr_to_overseerr', new_callable=mock.AsyncMock) as mock_add_radarr, \
             mock.patch('main.add_sonarr_to_overseerr', new_callable=mock.AsyncMock) as mock_add_sonarr, \
             mock.patch('main.sync_overseerr_profiles', new_callable=mock.AsyncMock) as mock_sync:

            mock_add_radarr.return_value = {"id": 1, "name": "Radarr"}
            mock_add_sonarr.return_value = {"id": 2, "name": "Sonarr"}
            mock_sync.return_value = {"success": True}

            payload = {
                "api_key": "overseerr_test_key",
                "port": 5055,
                "apps_to_link": [
                    {"api_key": "test_sonarr_key", "hostname": "localhost"},
                    {"api_key": "test_radarr_key", "hostname": "192.168.1.10"}
                ]
            }

            response = client.post("/api/link/overseerr", json=payload)
            print(response.json())

            assert response.status_code == 200
            assert mock_add_radarr.call_count == 1
            assert mock_add_sonarr.call_count == 1
            assert mock_sync.call_count == 2

if __name__ == "__main__":
    test_link_prowlarr()
    test_link_downloaders()
    test_link_overseerr()
