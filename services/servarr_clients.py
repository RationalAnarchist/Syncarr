import httpx
import logging

logger = logging.getLogger(__name__)

def build_qbittorrent_payload(client_config):
    """
    Build the payload for qBittorrent download client.
    """
    return {
        "enable": True,
        "name": "qBittorrent",
        "implementation": "QBittorrent",
        "configContract": "QBittorrentSettings",
        "fields": [
            {
                "name": "host",
                "value": client_config.get("host", "localhost")
            },
            {
                "name": "port",
                "value": client_config.get("port", 8080)
            },
            {
                "name": "username",
                "value": client_config.get("username", "")
            },
            {
                "name": "password",
                "value": client_config.get("password", "")
            }
        ]
    }

def build_nzbget_payload(client_config):
    """
    Build the payload for NZBGet download client.
    """
    return {
        "enable": True,
        "name": "NZBGet",
        "implementation": "Nzbget",
        "configContract": "NzbgetSettings",
        "fields": [
            {
                "name": "host",
                "value": client_config.get("host", "localhost")
            },
            {
                "name": "port",
                "value": client_config.get("port", 6789)
            },
            {
                "name": "username",
                "value": client_config.get("username", "")
            },
            {
                "name": "password",
                "value": client_config.get("password", "")
            },
            {
                "name": "tvCategory",
                "value": client_config.get("category", "tv")
            }
        ]
    }

async def add_download_client(app_url: str, app_api_key: str, payload: dict):
    """
    Add a download client to a Servarr instance.
    """
    url = f"{app_url}/api/v3/downloadclient"
    headers = {"X-Api-Key": app_api_key}

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
