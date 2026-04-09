# ForenSync MVP

ForenSync is a minimum viable forensic timeline builder for hackathon use. It scans a set of digital artefacts, extracts timestamped events, normalises them to UTC, deduplicates overlapping entries, and generates an interactive HTML timeline plus JSON evidence export.

## Supported Inputs

- Windows Event Logs in `.evtx` format
- Browser history SQLite databases in `.db`, `.sqlite`, `.sqlite3`, and `.history`
- Registry exports in `.reg`
- Prefetch files in `.pf`

## MVP Behaviours

- Normalises timestamps to UTC
- Deduplicates near-identical events from overlapping sources
- Generates:
  - `timeline.json`
  - `timeline.html`
  - `case_summary.md`
- Allows investigator notes and browser-side evidence export from the timeline UI

## Run

```bash
python main.py --input path/to/artefacts --output-dir output --case-name "Demo Case"
```

Then open the generated `output/timeline.html` in a browser.

## Notes

- EVTX record-level parsing uses the optional `python-evtx` package when available.
- Without that dependency, EVTX files still appear in the case output as discovered artefacts with metadata-only events.
- Registry exports use the export file modification time as the event timestamp in this MVP.
- Prefetch parsing currently uses file-system timestamps as execution hints rather than deep binary parsing.
