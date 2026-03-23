import httpx
import logging

logger = logging.getLogger(__name__)

def build_qbittorrent_payload(client_config, target_app_type: str = ""):
    """
    Build the payload for qBittorrent download client.
    """
    fields = [
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

    # Dynamically inject required category fields based on the target Servarr app
    # This prevents the "Object reference not set" on some apps and "missing category" on others
    if target_app_type == 'sonarr':
        fields.append({"name": "tvCategory", "value": "Series"})
    elif target_app_type == 'radarr':
        fields.append({"name": "movieCategory", "value": "Movies"})
    elif target_app_type == 'lidarr':
        fields.append({"name": "musicCategory", "value": "Music"})
    elif target_app_type == 'readarr':
        # Readarr requires either tvCategory or category or booksCategory depending on version. Usually 'category' for qbit.
        fields.append({"name": "category", "value": "Books"})
    elif target_app_type == 'prowlarr':
        fields.append({"name": "category", "value": ""})

    return {
        "enable": True,
        "name": "qBittorrent",
        "implementation": "QBittorrent",
        "configContract": "QBittorrentSettings",
        "priority": 1,
        "fields": fields
    }

def build_nzbget_payload(client_config, target_app_type: str = ""):
    """
    Build the payload for NZBGet download client.
    """
    fields = [
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
        }
    ]

    # Dynamically inject required category fields based on the target Servarr app
    # The user confirmed NZBGet has: Movies, Series, Music, Software
    if target_app_type == 'sonarr':
        fields.append({"name": "tvCategory", "value": "Series"})
    elif target_app_type == 'radarr':
        fields.append({"name": "movieCategory", "value": "Movies"})
    elif target_app_type == 'lidarr':
        fields.append({"name": "musicCategory", "value": "Music"})
    elif target_app_type == 'readarr':
        # User confirmed 'Software' is an available category
        fields.append({"name": "category", "value": "Software"})
        fields.append({"name": "tvCategory", "value": "Software"}) # Sometimes Readarr uses tvCategory in schema for NZBGet
    elif target_app_type == 'prowlarr':
        fields.append({"name": "category", "value": ""})

    return {
        "enable": True,
        "name": "NZBGet",
        "implementation": "Nzbget",
        "configContract": "NzbgetSettings",
        "priority": 1,
        "fields": fields
    }

async def add_download_client(app_url: str, app_api_key: str, payload: dict, api_version: str = "v3"):
    """
    Add a download client to a Servarr instance.
    """
    url = f"{app_url}/api/{api_version}/downloadclient"
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
            # We unconditionally set the standard size-related keys to handle missing/null cases
            df["minSize"] = min_mb_per_min
            df["maxSize"] = max_mb_per_min
            df["preferredSize"] = preferred_mb_per_min

            # Also set the alternative keys just in case older versions use them
            df["min"] = min_mb_per_min
            df["max"] = max_mb_per_min
            df["preferred"] = preferred_mb_per_min

            def_id = df.get('id')
            if def_id:
                # Update individually per the confirmed PUT /api/v3/qualitydefinition/{id}
                update_url = f"{app_url}/api/v3/qualitydefinition/{def_id}"
                try:
                    update_response = await client.put(update_url, headers=headers, json=df)
                    update_response.raise_for_status()
                    updated_definitions.append(update_response.json())
                except httpx.HTTPStatusError as e:
                    logger.warning(f"Failed to update quality definition {def_id} at {update_url}: {e.response.status_code} - {e.response.text}")
                except Exception as e:
                    logger.warning(f"Error updating quality definition {def_id}: {str(e)}")

        return updated_definitions
