from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from engine.timeline_gen import collect_artifacts, deduplicate_events

app = FastAPI(title="ForenSync API")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
if os.environ.get("VERCEL"):
    UPLOAD_DIR = Path("/tmp/uploads")
else:
    UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

class TimelineEventSchema(BaseModel):
    event_id: str
    timestamp_utc: str
    timestamp_unix: int
    source_type: str
    artifact_type: str
    source_file: str
    title: str
    description: str
    dedupe_key: str
    confidence: float
    fidelity_rank: int
    tags: list[str]
    metadata: dict[str, Any]
    raw_timestamp: str | None
    provenance: list[dict[str, Any]]

from engine.ai_narrator import build_case_summary, generate_investigation_narrative
from engine.anomaly_detector import find_event_outliers

class TimelineResponse(BaseModel):
    case_name: str
    events: list[TimelineEventSchema]
    scanned_files: list[str]
    warnings: list[str]
    anomalies: list[str]
    summary_md: str

@app.post("/api/upload", response_model=TimelineResponse)
@app.post("/upload", response_model=TimelineResponse)
async def upload_artefacts(files: list[UploadFile] = File(...), case_name: str = "New Case"):
    case_id = str(uuid.uuid4())
    case_dir = UPLOAD_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    
    saved_paths = []
    seen_hashes = set()
    duplicates_found = []

    for file in files:
        # Read content to calculate hash for deduplication
        content = await file.read()
        file_hash = hashlib.sha256(content).hexdigest()

        if file_hash in seen_hashes:
            duplicates_found.append(file.filename)
            continue

        seen_hashes.add(file_hash)
        file_path = case_dir / file.filename
        with file_path.open("wb") as buffer:
            buffer.write(content)
        saved_paths.append(file_path)
    
    try:
        raw_events, parser_warnings, scanned_files = collect_artifacts(saved_paths)
        
        if duplicates_found:
            parser_warnings.append(f"Deduplication: Skipped {len(duplicates_found)} identical file(s) ({', '.join(duplicates_found[:5])}{'...' if len(duplicates_found) > 5 else ''})")
            
        deduped_events = deduplicate_events(raw_events)
        
        anomalies = find_event_outliers(deduped_events)
        summary = build_case_summary(case_name, scanned_files, parser_warnings, deduped_events)
        
        return {
            "case_name": case_name,
            "events": [event.__dict__ for event in deduped_events],
            "scanned_files": scanned_files,
            "warnings": parser_warnings,
            "anomalies": anomalies,
            "summary_md": summary
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# ... (rest of the file remains same, adding this before the __main__)

# Serve Frontend
frontend_dist = Path("frontend/dist")
if frontend_dist.exists():
    # Mount assets folder for images/css/js
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    # Catch-all for SPA routing
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        
        file_path = frontend_dist / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
            
        return FileResponse(frontend_dist / "index.html")

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
