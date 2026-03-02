import httpx
from typing import Dict, Any

async def add_radarr_to_overseerr(overseerr_url: str, api_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Adds a Radarr server to Overseerr.
    """
    endpoint = f"{overseerr_url}/api/v1/settings/radarr"
    headers = {"X-Api-Key": api_key}

    async with httpx.AsyncClient() as client:
        response = await client.post(endpoint, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

async def add_sonarr_to_overseerr(overseerr_url: str, api_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Adds a Sonarr server to Overseerr.
    """
    endpoint = f"{overseerr_url}/api/v1/settings/sonarr"
    headers = {"X-Api-Key": api_key}

    async with httpx.AsyncClient() as client:
        response = await client.post(endpoint, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

async def sync_overseerr_profiles(overseerr_url: str, api_key: str, app_type: str, server_id: int) -> Dict[str, Any]:
    """
    Triggers profile and root folder sync by calling the service endpoint.
    app_type should be 'radarr' or 'sonarr'.
    """
    endpoint = f"{overseerr_url}/api/v1/service/{app_type}/{server_id}"
    headers = {"X-Api-Key": api_key}

    async with httpx.AsyncClient() as client:
        response = await client.get(endpoint, headers=headers)
        response.raise_for_status()
        return response.json()
