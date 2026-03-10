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

async def update_quality_definitions(app_url: str, app_api_key: str, min_mb_per_min: float, max_mb_per_min: float, preferred_mb_per_min: float):
    """
    Updates all quality definitions to use the specified MB/min values for min, max, and preferred.
    """
    url = f"{app_url}/api/v3/qualitydefinition"
    headers = {"X-Api-Key": app_api_key}

    async with httpx.AsyncClient() as client:
        # First get existing definitions
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        definitions = response.json()

        updated_definitions = []
        # Update all definitions
        for df in definitions:
            # We must inspect to identify the correct size-related keys
            if "minSize" in df:
                df["minSize"] = min_mb_per_min
            elif "min" in df:
                df["min"] = min_mb_per_min

            if "maxSize" in df:
                df["maxSize"] = max_mb_per_min
            elif "max" in df:
                df["max"] = max_mb_per_min

            if "preferredSize" in df:
                df["preferredSize"] = preferred_mb_per_min
            elif "preferred" in df:
                df["preferred"] = preferred_mb_per_min

            def_id = df.get('id')
            if def_id:
                # Update individually per the confirmed PUT /api/v3/qualitydefinition/{id}
                update_url = f"{app_url}/api/v3/qualitydefinition/{def_id}"
                update_response = await client.put(update_url, headers=headers, json=df)
                update_response.raise_for_status()
                updated_definitions.append(update_response.json())

        return updated_definitions
