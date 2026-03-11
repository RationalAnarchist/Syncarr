import httpx
import logging

logger = logging.getLogger(__name__)

async def get_sync_profile_id(prowlarr_url: str, prowlarr_api_key: str) -> int:
    """Fetch the default Sync Profile ID from Prowlarr."""
    url = f"{prowlarr_url}/api/v1/syncprofile"
    headers = {"X-Api-Key": prowlarr_api_key}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        profiles = response.json()

        # usually 1 is the default
        for profile in profiles:
            if profile.get("name") == "Standard":
                return profile.get("id")

        if profiles:
            return profiles[0].get("id")

    return 1 # Fallback to 1

async def add_app_to_prowlarr(
    prowlarr_url: str,
    prowlarr_api_key: str,
    app_name: str,
    app_url: str,
    app_api_key: str,
    sync_level: str = "fullSync"
):
    """Add a Sonarr/Radarr instance to Prowlarr."""

    sync_profile_id = await get_sync_profile_id(prowlarr_url, prowlarr_api_key)

    url = f"{prowlarr_url}/api/v1/applications"
    headers = {"X-Api-Key": prowlarr_api_key}

    # We need to build the specific payload Prowlarr expects
    # The Implementation string varies based on the app
    app_name_lower = app_name.lower()
    if "sonarr" in app_name_lower:
        implementation = "Sonarr"
    elif "radarr" in app_name_lower:
        implementation = "Radarr"
    elif "lidarr" in app_name_lower:
        implementation = "Lidarr"
    elif "readarr" in app_name_lower:
        implementation = "Readarr"
    else:
        implementation = "Unknown"

    payload = {
        "name": app_name,
        "implementation": implementation,
        "configContract": f"{implementation}Settings",
        "appProfileId": 1, # Default app profile
        "syncLevel": sync_level,
        "syncProfileId": sync_profile_id,
        "fields": [
            {
                "name": "prowlarrUrl",
                "value": prowlarr_url
            },
            {
                "name": "baseUrl",
                "value": app_url
            },
            {
                "name": "apiKey",
                "value": app_api_key
            }
        ]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to add app to Prowlarr. Status: {e.response.status_code}, Response: {e.response.text}, Payload: {payload}, URL: {url}")
            raise
        return response.json()
