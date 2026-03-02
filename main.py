from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException
from fastapi.responses import JSONResponse
import os
from utils.scanner import scan_configs
from services.prowlarr import add_app_to_prowlarr
import httpx

app = FastAPI(title="Syncarr", description="Orchestration tool for homelab *arr ecosystem")

# Hardcoded test path as per requirements
TEST_CONFIGS_DIR = os.path.join(os.path.dirname(__file__), "test_configs")

@app.get("/api/discover")
def discover_apps():
    """
    Endpoint to trigger the scan on the test_configs path and return the discovered apps.
    """
    discovered_apps = scan_configs(TEST_CONFIGS_DIR)
    return JSONResponse(content={"status": "success", "data": discovered_apps})

@app.post("/api/link/prowlarr")
async def link_prowlarr():
    """
    Endpoint to automatically connect Sonarr and Radarr to Prowlarr.
    """
    discovered_apps = scan_configs(TEST_CONFIGS_DIR)

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
            app_ip = "localhost" # Defaulting to localhost since config.xml doesn't hold the actual IP
            app_port = app['port']
            app_api_key = app['apiKey']
            app_url_base = app.get('urlBase', '')

            # Use full URL if URL base exists
            app_url = f"http://{app_ip}:{app_port}{app_url_base}"

            try:
                result = await add_app_to_prowlarr(
                    prowlarr_url=prowlarr_url,
                    prowlarr_api_key=prowlarr_api_key,
                    app_name=app_name,
                    app_url=app_url,
                    app_api_key=app_api_key,
                    sync_level="fullSync"
                )
                results.append({"app": app_name, "status": "success", "result": result})
            except httpx.HTTPStatusError as e:
                errors.append({"app": app_name, "status": "error", "message": f"HTTP Error: {e.response.status_code} - {e.response.text}"})
            except Exception as e:
                errors.append({"app": app_name, "status": "error", "message": str(e)})

    return JSONResponse(content={
        "status": "success" if not errors else "partial_success" if results else "error",
        "results": results,
        "errors": errors
    })

# Mount static files to serve the frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
