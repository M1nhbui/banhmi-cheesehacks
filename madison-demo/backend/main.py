import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_FILE = BASE_DIR / "data" / "madison_map_data.json"

app = FastAPI(title="Madison Map Demo")

# Serve frontend files at /static
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/map-data")
def map_data():
    if not DATA_FILE.exists():
        return JSONResponse(
            {"error": "madison_map_data.json not found. Run: python build_data.py"},
            status_code=404
        )
    data = json.loads(DATA_FILE.read_text())
    return JSONResponse(data)