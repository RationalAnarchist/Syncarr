import sqlite3
import xml.etree.ElementTree as ET
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException
from fastapi.responses import JSONResponse
import os
import logging
import json
from utils.scanner import scan_configs
from utils.backup import create_backup
from services.prowlarr import add_app_to_prowlarr
from services.servarr_clients import add_download_client, build_qbittorrent_payload, build_nzbget_payload, update_quality_definitions
from services.overseerr import add_radarr_to_overseerr, add_sonarr_to_overseerr, sync_overseerr_profiles
import httpx
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Syncarr", description="Orchestration tool for homelab *arr ecosystem")

class ClientConfig(BaseModel):
    host: str
    port: int
    username: Optional[str] = ""
    password: Optional[str] = ""
    category: Optional[str] = "tv"

class LinkDownloadersRequest(BaseModel):
    qbittorrent: Optional[ClientConfig] = None
    nzbget: Optional[ClientConfig] = None

class AppQualityRequest(BaseModel):
    api_key: str
    min_mb_per_min: float
    max_mb_per_min: float
    preferred_mb_per_min: float

class UpdateQualityRequest(BaseModel):
    apps_to_update: list[AppQualityRequest] = []

class AppLinkInfo(BaseModel):
    api_key: str
    hostname: str = "localhost"

class SetupAppRequest(BaseModel):
    api_key: str
    host: str = "localhost"
    auth_method: Optional[str] = None
    auth_required: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    root_folder: Optional[str] = None

class LinkOverseerrRequest(BaseModel):
    api_key: str
    host: str = "localhost"
    port: int = 5055
    apps_to_link: list[AppLinkInfo] = []

class LinkProwlarrRequest(BaseModel):
    api_key: str
    host: str = "localhost"
    port: int = 9696
    apps_to_link: list[AppLinkInfo] = []

class UpdateSettingsRequest(BaseModel):
    config_dir: str
    log_level: str = "INFO"

class AppTypeOverrideRequest(BaseModel):
    path: str
    app_type: str

class AppHostnameOverrideRequest(BaseModel):
    api_key: str
    hostname: str

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")

def load_settings():
    settings = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except Exception as e:
            logger.error(f"Error reading settings file: {e}")
    return settings

def save_settings_dict(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error writing settings file: {e}")
        return False


# Logging setup
logger = logging.getLogger("syncarr")
logger.setLevel(logging.INFO)

# Console handler
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

def setup_logging():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                settings = json.load(f)
                log_level_str = settings.get("log_level", "INFO").upper()
                level = getattr(logging, log_level_str, logging.INFO)
                logger.setLevel(level)
                ch.setLevel(level)
                logger.info(f"Logging level set to {log_level_str}")
        except Exception as e:
            print(f"Error setting up logging: {e}")

setup_logging()


def get_configs_dir():
    # Allow overriding the config directory via environment variable first
    env_dir = os.environ.get("SYNCARR_CONFIG_DIR")
    if env_dir:
        return env_dir

    # Check settings file
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                settings = json.load(f)
                if "config_dir" in settings and settings["config_dir"]:
                    return settings["config_dir"]
        except Exception as e:
            print(f"Error reading settings file: {e}")

    # Default fallback
    return os.path.join(os.path.dirname(__file__), "test_configs")

@app.get("/api/settings")
def get_settings():
    """
    Endpoint to retrieve current settings.
    """
    settings = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                settings = json.load(f)
        except Exception as e:
            print(f"Error reading settings file: {e}")

    return JSONResponse(content={
        "status": "success",
        "data": {
            "config_dir": settings.get("config_dir", os.path.join(os.path.dirname(__file__), "test_configs")),
            "env_override": os.environ.get("SYNCARR_CONFIG_DIR", None),
            "log_level": settings.get("log_level", "INFO")
        }
    })


@app.post("/api/settings")
def update_settings(request: UpdateSettingsRequest):
    """
    Endpoint to update the settings file.
    """
    settings = load_settings()

    settings["config_dir"] = request.config_dir
    settings["log_level"] = request.log_level

    # Update current logger level
    level = getattr(logging, request.log_level.upper(), logging.INFO)
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)

    if not save_settings_dict(settings):
        raise HTTPException(status_code=500, detail="Failed to save settings")

    return JSONResponse(content={"status": "success", "message": "Settings updated successfully."})

@app.post("/api/app/type")
def update_app_type(request: AppTypeOverrideRequest):
    """
    Endpoint to store custom app types.
    """
    settings = load_settings()
    if "app_types" not in settings:
        settings["app_types"] = {}

    settings["app_types"][request.path] = request.app_type

    if not save_settings_dict(settings):
        raise HTTPException(status_code=500, detail="Failed to save app type")

    return JSONResponse(content={"status": "success", "message": "App type updated successfully."})

@app.post("/api/app/hostname")
def update_app_hostname(request: AppHostnameOverrideRequest):
    """
    Endpoint to store custom app hostnames.
    """
    settings = load_settings()
    if "app_hostnames" not in settings:
        settings["app_hostnames"] = {}

    settings["app_hostnames"][request.api_key] = request.hostname

    if not save_settings_dict(settings):
        raise HTTPException(status_code=500, detail="Failed to save app hostname")

    return JSONResponse(content={"status": "success", "message": "App hostname updated successfully."})

@app.post("/api/setup")
async def setup_app(request: SetupAppRequest):
    """
    Endpoint to setup Sonarr or Radarr.
    """
    discovered_apps = scan_configs(get_configs_dir())

    app_config = next((app for app in discovered_apps if app.get('apiKey') == request.api_key), None)
    if not app_config:
        raise HTTPException(status_code=404, detail=f"App with given API key not found.")

    filepath = app_config['path']
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()

        # Helper to update or add element
        def update_or_add(tag, text):
            elem = root.find(tag)
            if elem is None:
                elem = ET.SubElement(root, tag)
            elem.text = text

        if request.auth_method is not None:
            update_or_add("AuthenticationMethod", request.auth_method)
            if request.auth_method != "None":
                if request.auth_required is not None:
                    update_or_add("AuthenticationRequired", request.auth_required)
                if request.username is not None:
                    update_or_add("Username", request.username)
                if request.password is not None:
                    update_or_add("Password", request.password)

        tree.write(filepath, encoding="utf-8", xml_declaration=False)
    except Exception as e:
        logger.error(f"Failed to update config.xml: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update config.xml: {e}")

    app_ip = request.host
    app_port = app_config['port']
    app_api_key = app_config['apiKey']
    app_url_base = app_config.get('urlBase', '')
    app_url = f"http://{app_ip}:{app_port}{app_url_base}"
    headers = {"X-Api-Key": app_api_key}

    if request.root_folder:
        app_type = app_config['app'].lower()
        api_version = "v3"
        if app_type in ['lidarr', 'readarr']:
            api_version = "v1"
        url = f"{app_url}/api/{api_version}/rootfolder"

        payload = {"path": request.root_folder}

        async with httpx.AsyncClient() as client:
            try:
                if app_type in ['lidarr', 'readarr']:
                    payload["name"] = request.root_folder.strip('/').split('/')[-1] or "RootFolder"
                    payload["defaultQualityProfileId"] = 1
                    payload["defaultMetadataProfileId"] = 1

                    try:
                        qp_response = await client.get(f"{app_url}/api/{api_version}/qualityprofile", headers=headers)
                        if qp_response.status_code == 200 and len(qp_response.json()) > 0:
                            payload["defaultQualityProfileId"] = qp_response.json()[0].get("id", 1)

                        mp_response = await client.get(f"{app_url}/api/{api_version}/metadataprofile", headers=headers)
                        if mp_response.status_code == 200 and len(mp_response.json()) > 0:
                            payload["defaultMetadataProfileId"] = mp_response.json()[0].get("id", 1)
                    except httpx.RequestError as e:
                        logger.debug(f"Failed to fetch profiles for {app_type}: {e}")

                # First check if it exists
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    existing_folders = response.json()
                    for f in existing_folders:
                        if f.get('path') == request.root_folder:
                            break
                    else:
                        # If not, add it
                        post_response = await client.post(url, headers=headers, json=payload)
                        if post_response.status_code not in (200, 201):
                            logger.error(f"Failed to add root folder: {post_response.status_code} - {post_response.text}")
                            raise HTTPException(status_code=500, detail=f"Failed to add root folder: {post_response.text}")
            except httpx.RequestError as e:
                logger.error(f"Failed to connect to app: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to connect to app to add root folder: {e}")

    # Restart the app
    api_version = "v3"
    if app_config['app'].lower() in ['lidarr', 'readarr', 'prowlarr']:
        api_version = "v1"
    restart_url = f"{app_url}/api/{api_version}/system/restart"
    async with httpx.AsyncClient() as client:
        try:
            restart_response = await client.post(restart_url, headers=headers)
            if restart_response.status_code not in (200, 201):
                logger.error(f"Failed to restart app: {restart_response.status_code} - {restart_response.text}")
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to app to restart: {e}")

    return JSONResponse(content={"status": "success", "message": "App setup updated successfully."})

@app.get("/api/discover")
async def discover_apps():
    """
    Endpoint to trigger the scan on the config path and return the discovered apps.
    """
    discovered_apps = scan_configs(get_configs_dir())

    for app in discovered_apps:
        app_name = app['app'].lower()
        if app_name in ['sonarr', 'radarr', 'lidarr', 'readarr', 'prowlarr']:
            auth_method = app.get('authMethod', 'None')
            is_auth_configured = auth_method != 'None' and auth_method != ''

            if app_name == 'prowlarr':
                app['isSetupComplete'] = is_auth_configured

                # Fetch linked applications from Prowlarr API
                app_ip = app.get('hostname', 'localhost')
                app_port = app['port']
                app_api_key = app['apiKey']
                app_url_base = app.get('urlBase', '')
                app_url = f"http://{app_ip}:{app_port}{app_url_base}".rstrip('/')

                app['linkedApiKeys'] = []
                try:
                    async with httpx.AsyncClient(timeout=3.0) as client:
                        response = await client.get(f"{app_url}/api/v1/applications", headers={"X-Api-Key": app_api_key})
                        if response.status_code == 200:
                            prowlarr_apps = response.json()
                            linked_keys = []
                            for p_app in prowlarr_apps:
                                for field in p_app.get('fields', []):
                                    if field.get('name') == 'apiKey' and field.get('value'):
                                        linked_keys.append(field['value'])
                            app['linkedApiKeys'] = linked_keys
                except Exception as e:
                    logger.debug(f"Failed to fetch linked applications from Prowlarr at {app_url}: {e}")

            else:
                app_ip = app.get('hostname', 'localhost')
                app_port = app['port']
                app_api_key = app['apiKey']
                app_url_base = app.get('urlBase', '')
                app_url = f"http://{app_ip}:{app_port}{app_url_base}".rstrip('/')
                headers = {"X-Api-Key": app_api_key}

                has_root_folders = False

                api_version = "v3"
                if app_name in ['lidarr', 'readarr']:
                    api_version = "v1"

                try:
                    async with httpx.AsyncClient(timeout=3.0) as client:
                        response = await client.get(f"{app_url}/api/{api_version}/rootfolder", headers=headers)
                        if response.status_code == 200:
                            folders = response.json()
                            if folders and len(folders) > 0:
                                has_root_folders = True
                except Exception as e:
                    logger.debug(f"Failed to connect to {app_name} at {app_url} to check root folders: {e}")

                app['isSetupComplete'] = is_auth_configured and has_root_folders

    return JSONResponse(content={"status": "success", "data": discovered_apps})

@app.post("/api/backup")
def backup_apps():
    """
    Endpoint to trigger backup of config and db files for all discovered apps.
    """
    try:
        discovered_apps = scan_configs(get_configs_dir())

        if not discovered_apps:
            raise HTTPException(status_code=400, detail="No configurations found to backup.")

        backups_dir = os.path.join(os.path.dirname(__file__), "backups")

        backup_file = create_backup(discovered_apps, backups_dir)

        return JSONResponse(content={
            "status": "success",
            "message": "Backup created successfully",
            "file": os.path.basename(backup_file)
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/link/prowlarr")
async def link_prowlarr(request: LinkProwlarrRequest):
    """
    Endpoint to automatically connect Sonarr, Radarr, Lidarr, and Readarr to Prowlarr.
    """
    discovered_apps = scan_configs(get_configs_dir())

    prowlarr_config = next((app for app in discovered_apps if app['app'].lower() == 'prowlarr'), None)

    if not prowlarr_config:
        raise HTTPException(status_code=400, detail="Prowlarr configuration not found.")

    prowlarr_url_base = prowlarr_config.get('urlBase', '')
    # Ensure no trailing slashes on URLs to prevent 404s when appending /api paths
    prowlarr_url = f"http://{request.host}:{request.port}{prowlarr_url_base}".rstrip('/')

    results = []
    errors = []

    for app in discovered_apps:
        app_name = app['app']

        # Check if this app is in the request's apps_to_link
        app_api_key = app.get('apiKey')
        app_link_info = next((item for item in request.apps_to_link if item.api_key == app_api_key), None)

        if app_name.lower() in ['sonarr', 'radarr', 'lidarr', 'readarr'] and app_link_info:
            logger.debug(f"Attempting to link {app_name} to Prowlarr at {prowlarr_url} with app host {app_link_info.hostname}")
            app_ip = app_link_info.hostname
            app_port = app['port']
            app_api_key = app['apiKey']
            app_url_base = app.get('urlBase', '')

            # Use full URL if URL base exists
            app_url = f"http://{app_ip}:{app_port}{app_url_base}".rstrip('/')

            try:
                logger.debug(f"Sending request to Prowlarr at {prowlarr_url} to add {app_name} at {app_url}")
                result = await add_app_to_prowlarr(
                    prowlarr_url=prowlarr_url,
                    prowlarr_api_key=request.api_key,
                    app_name=app_name,
                    app_url=app_url,
                    app_api_key=app_api_key,
                    sync_level="fullSync"
                )
                logger.info(f"Successfully linked {app_name} to Prowlarr")
                results.append({"app": app_name, "status": "success", "result": result})
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP Error: {e.response.status_code} - {e.response.text}")
                errors.append({"app": app_name, "status": "error", "message": f"HTTP Error: {e.response.status_code} - {e.response.text}"})
            except Exception as e:
                logger.error(f"Error: {str(e)}")
                errors.append({"app": app_name, "status": "error", "message": str(e)})

    return JSONResponse(content={
        "status": "success" if not errors else "partial_success" if results else "error",
        "results": results,
        "errors": errors
    })

@app.post("/api/quality")
async def update_quality(request: UpdateQualityRequest):
    """
    Endpoint to update quality definitions for Sonarr and Radarr.
    """
    discovered_apps = scan_configs(get_configs_dir())

    results = []
    errors = []

    for app_to_update in request.apps_to_update:
        app_config = next((app for app in discovered_apps if app.get('apiKey') == app_to_update.api_key), None)
        if not app_config:
            errors.append({"api_key": app_to_update.api_key, "status": "error", "message": "App not found"})
            continue

        app_name = app_config['app'].lower()
        if app_name not in ['sonarr', 'radarr']:
            errors.append({"app": app_name, "status": "error", "message": "Only Sonarr and Radarr are supported"})
            continue

        app_ip = app_config.get('hostname', 'localhost')
        app_port = app_config['port']
        app_api_key = app_config['apiKey']
        app_url_base = app_config.get('urlBase', '')

        # Use full URL if URL base exists
        app_url = f"http://{app_ip}:{app_port}{app_url_base}"

        logger.debug(f"Attempting to update quality definitions for {app_name} at {app_url}")
        try:
            result = await update_quality_definitions(
                app_url=app_url,
                app_api_key=app_api_key,
                min_mb_per_min=app_to_update.min_mb_per_min,
                max_mb_per_min=app_to_update.max_mb_per_min,
                preferred_mb_per_min=app_to_update.preferred_mb_per_min
            )
            logger.info(f"Successfully updated quality definitions for {app_name}")
            results.append({"app": app_name, "status": "success", "result": result})
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error: {e.response.status_code} - {e.response.text}")
            errors.append({"app": app_name, "status": "error", "message": f"HTTP Error: {e.response.status_code} - {e.response.text}"})
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            errors.append({"app": app_name, "status": "error", "message": str(e)})

    return JSONResponse(content={
        "status": "success" if not errors else "partial_success" if results else "error",
        "results": results,
        "errors": errors
    })

@app.post("/api/link/overseerr")
async def link_overseerr(request: LinkOverseerrRequest):
    """
    Endpoint to automatically connect Sonarr and Radarr to Overseerr.
    """
    discovered_apps = scan_configs(get_configs_dir())

    results = []
    errors = []

    overseerr_url = f"http://{request.host}:{request.port}"

    for app in discovered_apps:
        app_name = app['app'].lower()

        # Check if this app is in the request's apps_to_link
        app_api_key = app.get('apiKey')
        app_link_info = next((item for item in request.apps_to_link if item.api_key == app_api_key), None)

        if app_name in ['sonarr', 'radarr'] and app_link_info:
            logger.debug(f"Attempting to link {app_name} to Overseerr at {overseerr_url} with payload host {app_link_info.hostname}")
            payload = {
                "name": app['app'],
                "hostname": app_link_info.hostname,
                "port": int(app['port']),
                "apiKey": app_api_key,
                "useSsl": False,
                "baseUrl": app.get('urlBase', '') or "",
                "activeProfileId": 1,
                "activeProfileName": "",
                "activeDirectory": "",
                "is4k": False,
                "isDefault": True
            }

            if app_name == 'radarr':
                payload["minimumAvailability"] = ""
            elif app_name == 'sonarr':
                payload["enableSeasonFolders"] = False

            try:
                logger.debug(f"Sending payload to {overseerr_url}: {payload}")
                if app_name == 'radarr':
                    result = await add_radarr_to_overseerr(overseerr_url, request.api_key, payload)
                else:
                    result = await add_sonarr_to_overseerr(overseerr_url, request.api_key, payload)

                server_id = result.get('id')

                logger.info(f"Successfully linked {app_name} to Overseerr")
                # trigger sync
                if server_id:
                    await sync_overseerr_profiles(overseerr_url, request.api_key, app_name, server_id)

                results.append({"app": app_name, "status": "success", "result": result})
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP Error: {e.response.status_code} - {e.response.text}")
                errors.append({"app": app_name, "status": "error", "message": f"HTTP Error: {e.response.status_code} - {e.response.text}"})
            except Exception as e:
                logger.error(f"Error: {str(e)}")
                errors.append({"app": app_name, "status": "error", "message": str(e)})

    return JSONResponse(content={
        "status": "success" if not errors else "partial_success" if results else "error",
        "results": results,
        "errors": errors
    })

@app.post("/api/link/downloaders")
async def link_downloaders(request: LinkDownloadersRequest):
    """
    Endpoint to automatically connect Sonarr, Radarr, Lidarr, and Readarr to qBittorrent and NZBGet.
    """
    discovered_apps = scan_configs(get_configs_dir())

    results = []
    errors = []

    for app in discovered_apps:
        app_name = app['app']
        if app_name.lower() in ['sonarr', 'radarr', 'lidarr', 'readarr']:
            logger.debug(f"Attempting to link Downloaders to {app_name}")
            app_ip = app.get('hostname', 'localhost')
            app_port = app['port']
            app_api_key = app['apiKey']
            app_url_base = app.get('urlBase', '')

            # Use full URL if URL base exists
            app_url = f"http://{app_ip}:{app_port}{app_url_base}"

            if request.qbittorrent:
                logger.debug(f"Attempting to link qBittorrent to {app_name}")
                try:
                    payload = build_qbittorrent_payload(request.qbittorrent.model_dump())
                    result = await add_download_client(
                        app_url=app_url,
                        app_api_key=app_api_key,
                        payload=payload
                    )
                    logger.info(f"Successfully linked qBittorrent to {app_name}")
                    results.append({"app": app_name, "client": "qbittorrent", "status": "success", "result": result})
                except httpx.HTTPStatusError as e:
                    logger.error(f"HTTP Error: {e.response.status_code} - {e.response.text}")
                    errors.append({"app": app_name, "client": "qbittorrent", "status": "error", "message": f"HTTP Error: {e.response.status_code} - {e.response.text}"})
                except Exception as e:
                    logger.error(f"Error: {str(e)}")
                    errors.append({"app": app_name, "client": "qbittorrent", "status": "error", "message": str(e)})

            if request.nzbget:
                logger.debug(f"Attempting to link NZBGet to {app_name}")
                try:
                    payload = build_nzbget_payload(request.nzbget.model_dump())
                    # the payload differs slightly by implementation, map 'category' logic here:
                    if app_name.lower() == 'radarr':
                        # replace tvCategory with movieCategory
                        for field in payload['fields']:
                            if field['name'] == 'tvCategory':
                                field['name'] = 'movieCategory'
                                field['value'] = request.nzbget.category if request.nzbget.category != 'tv' else 'movies'

                    result = await add_download_client(
                        app_url=app_url,
                        app_api_key=app_api_key,
                        payload=payload
                    )
                    logger.info(f"Successfully linked NZBGet to {app_name}")
                    results.append({"app": app_name, "client": "nzbget", "status": "success", "result": result})
                except httpx.HTTPStatusError as e:
                    logger.error(f"HTTP Error: {e.response.status_code} - {e.response.text}")
                    errors.append({"app": app_name, "client": "nzbget", "status": "error", "message": f"HTTP Error: {e.response.status_code} - {e.response.text}"})
                except Exception as e:
                    logger.error(f"Error: {str(e)}")
                    errors.append({"app": app_name, "client": "nzbget", "status": "error", "message": str(e)})

    return JSONResponse(content={
        "status": "success" if not errors else "partial_success" if results else "error",
        "results": results,
        "errors": errors
    })


# Mount static files to serve the frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=9898, reload=True)
