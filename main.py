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
from services.servarr_clients import add_download_client, build_qbittorrent_payload, build_nzbget_payload
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

class AppLinkInfo(BaseModel):
    api_key: str
    hostname: str = "localhost"

class SetupAppRequest(BaseModel):
    api_key: str
    host: str = "localhost"
    auth_method: str = "None"
    auth_required: str = "Enabled"
    username: Optional[str] = ""
    password: Optional[str] = ""
    root_folder: Optional[str] = ""

class LinkOverseerrRequest(BaseModel):
    api_key: str
    host: str = "localhost"
    port: int = 5055
    apps_to_link: list[AppLinkInfo] = []

class UpdateSettingsRequest(BaseModel):
    config_dir: str
    log_level: str = "INFO"


SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")

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
    settings = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                settings = json.load(f)
        except Exception:
            pass

    settings["config_dir"] = request.config_dir
    settings["log_level"] = request.log_level

    # Update current logger level
    level = getattr(logging, request.log_level.upper(), logging.INFO)
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)

    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {e}")

    return JSONResponse(content={"status": "success", "message": "Settings updated successfully."})


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

        update_or_add("AuthenticationMethod", request.auth_method)
        if request.auth_method != "None":
            update_or_add("AuthenticationRequired", request.auth_required)
            update_or_add("Username", request.username)
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
        url = f"{app_url}/api/v3/rootfolder"
        payload = {"path": request.root_folder}

        async with httpx.AsyncClient() as client:
            try:
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
    restart_url = f"{app_url}/api/v3/system/restart"
    async with httpx.AsyncClient() as client:
        try:
            restart_response = await client.post(restart_url, headers=headers)
            if restart_response.status_code not in (200, 201):
                logger.error(f"Failed to restart app: {restart_response.status_code} - {restart_response.text}")
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to app to restart: {e}")

    return JSONResponse(content={"status": "success", "message": "App setup updated successfully."})

@app.get("/api/discover")
def discover_apps():
    """
    Endpoint to trigger the scan on the config path and return the discovered apps.
    """
    discovered_apps = scan_configs(get_configs_dir())

    # Check root folders for Sonarr and Radarr directly from their SQLite DBs
    for app in discovered_apps:
        app_name = app['app'].lower()
        if app_name in ['sonarr', 'radarr']:
            config_path = app['path']
            db_path = os.path.join(os.path.dirname(config_path), f"{app_name}.db")

            has_root_folders = False
            root_folders = []
            if os.path.exists(db_path):
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    # First check if the RootFolders table exists
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='RootFolders'")
                    if cursor.fetchone():
                        cursor.execute("SELECT COUNT(*) FROM RootFolders")
                        count = cursor.fetchone()[0]
                        if count > 0:
                            has_root_folders = True
                    conn.close()
                except Exception as e:
                    logger.debug(f"Failed to query SQLite DB {db_path}: {e}")
            else:
                logger.debug(f"Database file not found: {db_path}")

            app['rootFolders'] = root_folders

            auth_method = app.get('authMethod', 'None')
            is_auth_configured = auth_method != 'None' and auth_method != ''

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
async def link_prowlarr():
    """
    Endpoint to automatically connect Sonarr and Radarr to Prowlarr.
    """
    discovered_apps = scan_configs(get_configs_dir())

    prowlarr_config = next((app for app in discovered_apps if app['app'].lower() == 'prowlarr'), None)

    if not prowlarr_config:
        raise HTTPException(status_code=400, detail="Prowlarr configuration not found.")

    prowlarr_url = f"http://localhost:{prowlarr_config.get('port', '9696')}{prowlarr_config.get('urlBase', '')}"
    prowlarr_api_key = prowlarr_config.get('apiKey')

    if not prowlarr_api_key:
        raise HTTPException(status_code=400, detail="Prowlarr API Key not found.")

    results = []
    errors = []

    for app in discovered_apps:
        app_name = app['app']
        if app_name.lower() in ['sonarr', 'radarr']:
            logger.debug(f"Attempting to link {app_name} to Prowlarr at {prowlarr_url}")
            app_ip = "localhost" # Defaulting to localhost since config.xml doesn't hold the actual IP
            app_port = app['port']
            app_api_key = app['apiKey']
            app_url_base = app.get('urlBase', '')

            # Use full URL if URL base exists
            app_url = f"http://{app_ip}:{app_port}{app_url_base}"

            try:
                logger.debug(f"Sending request to Prowlarr at {prowlarr_url} to add {app_name} at {app_url}")
                result = await add_app_to_prowlarr(
                    prowlarr_url=prowlarr_url,
                    prowlarr_api_key=prowlarr_api_key,
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
    Endpoint to automatically connect Sonarr and Radarr to qBittorrent and NZBGet.
    """
    discovered_apps = scan_configs(get_configs_dir())

    results = []
    errors = []

    for app in discovered_apps:
        app_name = app['app']
        if app_name.lower() in ['sonarr', 'radarr']:
            logger.debug(f"Attempting to link Downloaders to {app_name}")
            app_ip = "localhost" # Defaulting to localhost since config.xml doesn't hold the actual IP
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
