from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import os
from utils.scanner import scan_configs

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

# Mount static files to serve the frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
