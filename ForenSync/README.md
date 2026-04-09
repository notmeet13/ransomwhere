# ForenSync Pro - Forensic Timeline Automation
# By Team RansomWhere?

ForenSync Pro is a high-performance forensic timeline automation tool designed for cyber-investigators. It transforms fragmented digital artefacts into a unified, normalized, and AI-narrated timeline within seconds.

## Key Features

- **Multi-Source Aggregation**: Ingest EVTX, Browser History, Registry Exports, and Prefetch files.
- **Unified UTC Timeline**: Strict normalization to UTC across all artefacts to eliminate manual correlation.
- **AI Narrative Engine**: Automatically generates plain-English investigative stories from raw log data.
- **Forensic Anomaly Detection**: Heuristic-based detection of anti-forensic activity (log clearing), lateral movement tools, and suspicious account manipulation.
- **Interactive Dashboard**: A premium React-based investigator dashboard with density charting, advanced filtering, and detailed provenance viewing.

## Architecture

- **Backend**: FastAPI (Python) with specialized forensic parsers.
- **Frontend**: Vite + React + Vanilla CSS (Premium Cyber Theme).

## Running the Prototype

### 1. Start the Backend
```bash
# From the root directory
pip install -r requirements.txt
python app.py
```

### 2. Start the Frontend
```bash
# From the frontend directory
npm install
npm run dev
```

## Supported Inputs

- **Windows Event Logs**: `.evtx` (Record-level parsing via python-evtx)
- **Browser History**: SQLite databases (Chromium, Firefox)
- **Registry**: `.reg` export files
- **Prefetch**: `.pf` binary files (Deep execution array recovery)

---
*Built for the 36-Hour Hackathon by Team Ransomwhere?*
