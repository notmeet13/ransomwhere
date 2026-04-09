from __future__ import annotations

import html
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable, Sequence

from engine.models import TimelineEvent
from parsers.browser_parser import parse_browser_history
from parsers.event_log_parser import parse_event_log
from parsers.file_system_parser import parse_prefetch_file, parse_registry_export


def discover_files(input_paths: Sequence[Path]) -> list[Path]:
    discovered: list[Path] = []
    for path in input_paths:
        if path.is_dir():
            for candidate in path.rglob("*"):
                if candidate.is_file():
                    discovered.append(candidate)
        elif path.is_file():
            discovered.append(path)
    return sorted(discovered)


def collect_artifacts(input_paths: Sequence[Path]) -> tuple[list[TimelineEvent], list[str], list[str]]:
    events: list[TimelineEvent] = []
    warnings: list[str] = []
    files = discover_files(input_paths)
    scanned = [str(path) for path in files]

    for file_path in files:
        suffix = file_path.suffix.lower()
        try:
            if file_path.name.lower().endswith(("-journal", "-wal", "-shm")):
                continue
            if suffix in {".db", ".sqlite", ".sqlite3", ".history"}:
                parsed_events, parser_warnings = parse_browser_history(file_path)
                events.extend(parsed_events)
                warnings.extend(parser_warnings)
            elif suffix == ".evtx":
                parsed_events, parser_warnings = parse_event_log(file_path)
                events.extend(parsed_events)
                warnings.extend(parser_warnings)
            elif suffix == ".reg":
                parsed_events, parser_warnings = parse_registry_export(file_path)
                events.extend(parsed_events)
                warnings.extend(parser_warnings)
            elif suffix == ".pf":
                parsed_events, parser_warnings = parse_prefetch_file(file_path)
                events.extend(parsed_events)
                warnings.extend(parser_warnings)
            else:
                warnings.append(f"Skipped unsupported file: {file_path}")
        except Exception as exc:
            warnings.append(f"Failed to parse {file_path}: {exc}")

    events.sort(key=lambda item: (item.timestamp_unix, item.timestamp_utc, item.source_type))
    return events, warnings, scanned


def deduplicate_events(events: Iterable[TimelineEvent]) -> list[TimelineEvent]:
    retained: list[TimelineEvent] = []
    for event in sorted(events, key=lambda item: (item.timestamp_unix, item.timestamp_utc, -item.fidelity_rank)):
        merged = False
        for index in range(len(retained) - 1, -1, -1):
            candidate = retained[index]
            if event.timestamp_unix - candidate.timestamp_unix > 1:
                break
            if _events_overlap(candidate, event):
                retained[index] = _merge_events(candidate, event)
                merged = True
                break
        if not merged:
            retained.append(event)
    retained.sort(key=lambda item: (item.timestamp_unix, item.timestamp_utc, item.source_type))
    return retained


def export_events_json(events: Sequence[TimelineEvent], target_path: Path) -> None:
    target_path.write_text(
        json.dumps([asdict(event) for event in events], indent=2),
        encoding="utf-8",
    )


def write_text_file(target_path: Path, content: str) -> None:
    target_path.write_text(content, encoding="utf-8")


def generate_timeline_html(
    case_name: str,
    events: Sequence[TimelineEvent],
    scanned_files: Sequence[str],
    parser_warnings: Sequence[str],
) -> str:
    events_json = json.dumps([asdict(event) for event in events])
    files_json = json.dumps(list(scanned_files))
    warnings_json = json.dumps(list(parser_warnings))
    title = html.escape(case_name)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --bg: #f5f1e8;
      --panel: rgba(255, 252, 246, 0.88);
      --text: #1d1c1a;
      --muted: #625b52;
      --accent: #0f766e;
      --accent-soft: #d7f3ee;
      --line: #d9cdbd;
      --danger: #9a3412;
      --shadow: 0 20px 40px rgba(62, 39, 15, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Trebuchet MS", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(15, 118, 110, 0.16), transparent 28%),
        radial-gradient(circle at top right, rgba(154, 52, 18, 0.10), transparent 32%),
        linear-gradient(180deg, #f8f6f1, var(--bg));
    }}
    .shell {{
      width: min(1180px, calc(100% - 32px));
      margin: 32px auto;
      display: grid;
      gap: 20px;
    }}
    .hero, .panel {{
      background: var(--panel);
      border: 1px solid rgba(217, 205, 189, 0.9);
      border-radius: 24px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(12px);
    }}
    .hero {{ padding: 28px; }}
    h1, h2, h3 {{
      margin: 0 0 12px;
      font-family: Georgia, "Times New Roman", serif;
    }}
    .sub {{ color: var(--muted); max-width: 72ch; line-height: 1.5; }}
    .stats {{ margin-top: 18px; display: flex; flex-wrap: wrap; gap: 12px; }}
    .stat {{
      background: white;
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 12px 16px;
      min-width: 160px;
    }}
    .stat strong {{ display: block; font-size: 1.3rem; }}
    .layout {{ display: grid; grid-template-columns: 300px 1fr; gap: 20px; }}
    .panel {{ padding: 20px; }}
    label {{ display: block; font-size: 0.9rem; color: var(--muted); margin: 12px 0 6px; }}
    input, select, textarea, button {{
      width: 100%;
      border-radius: 12px;
      border: 1px solid var(--line);
      padding: 10px 12px;
      font: inherit;
      background: white;
      color: var(--text);
    }}
    textarea {{ min-height: 100px; resize: vertical; }}
    button {{
      cursor: pointer;
      background: var(--accent);
      border: none;
      color: white;
      font-weight: 600;
      margin-top: 12px;
    }}
    button.secondary {{
      background: white;
      color: var(--accent);
      border: 1px solid var(--accent);
    }}
    .timeline {{ position: relative; padding-left: 28px; }}
    .timeline::before {{
      content: "";
      position: absolute;
      left: 10px;
      top: 8px;
      bottom: 8px;
      width: 2px;
      background: linear-gradient(180deg, var(--accent), rgba(15, 118, 110, 0.15));
    }}
    .event {{
      position: relative;
      background: white;
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
      margin-bottom: 14px;
    }}
    .event::before {{
      content: "";
      position: absolute;
      left: -24px;
      top: 22px;
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: var(--accent);
      box-shadow: 0 0 0 5px var(--accent-soft);
    }}
    .event h3 {{ margin-bottom: 8px; font-size: 1.05rem; }}
    .event .meta {{ color: var(--muted); font-size: 0.92rem; margin-bottom: 10px; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }}
    .chip {{
      background: #f6f3ee;
      color: #5a4d3f;
      border-radius: 999px;
      border: 1px solid var(--line);
      padding: 4px 10px;
      font-size: 0.82rem;
    }}
    .warn {{ color: var(--danger); line-height: 1.5; }}
    @media (max-width: 900px) {{ .layout {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <h1>{title}</h1>
      <p class="sub">Unified UTC timeline generated from browser history databases, Windows Event Logs, registry exports, and prefetch artefacts. The backend strictly normalises timestamps to UTC, preserves provenance, and merges overlapping evidence while prioritising higher-fidelity artefacts.</p>
      <div class="stats">
        <div class="stat"><strong id="stat-events"></strong><span>Events retained</span></div>
        <div class="stat"><strong id="stat-files"></strong><span>Artefacts scanned</span></div>
        <div class="stat"><strong id="stat-sources"></strong><span>Source types</span></div>
      </div>
    </section>
    <section class="layout">
      <aside class="panel">
        <h2>Filters</h2>
        <label for="sourceFilter">Source type</label>
        <select id="sourceFilter"></select>
        <label for="searchInput">Keyword</label>
        <input id="searchInput" placeholder="Search titles, descriptions, files">
        <label for="annotationText">Investigator annotation</label>
        <textarea id="annotationText" placeholder="Add case notes that should appear in the export..."></textarea>
        <button id="saveNotesBtn">Save Notes</button>
        <button id="exportBtn" class="secondary">Export Evidence JSON</button>
        <h3 style="margin-top: 22px;">Parser warnings</h3>
        <div id="warnings" class="warn"></div>
      </aside>
      <main class="panel">
        <h2>Timeline</h2>
        <div id="timeline" class="timeline"></div>
      </main>
    </section>
  </div>
  <script>
    const caseName = {json.dumps(case_name)};
    const events = {events_json};
    const scannedFiles = {files_json};
    const parserWarnings = {warnings_json};
    const storageKey = `forensync-notes-${{caseName}}`;
    const sourceFilter = document.getElementById("sourceFilter");
    const searchInput = document.getElementById("searchInput");
    const annotationText = document.getElementById("annotationText");
    const saveNotesBtn = document.getElementById("saveNotesBtn");
    const exportBtn = document.getElementById("exportBtn");
    const warningsNode = document.getElementById("warnings");
    const timelineNode = document.getElementById("timeline");

    function populateStats() {{
      document.getElementById("stat-events").textContent = events.length.toString();
      document.getElementById("stat-files").textContent = scannedFiles.length.toString();
      document.getElementById("stat-sources").textContent = new Set(events.map((event) => event.source_type)).size.toString();
    }}

    function populateFilters() {{
      const options = ["all", ...Array.from(new Set(events.map((event) => event.source_type))).sort()];
      sourceFilter.innerHTML = options.map((value) => `<option value="${{value}}">${{value === "all" ? "All sources" : value}}</option>`).join("");
    }}

    function renderWarnings() {{
      warningsNode.innerHTML = parserWarnings.length ? parserWarnings.map((warning) => `<div>${{warning}}</div>`).join("") : "None";
    }}

    function loadNotes() {{
      annotationText.value = localStorage.getItem(storageKey) || "";
    }}

    function escapeHtml(text) {{
      return text.replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }}

    function renderTimeline() {{
      const sourceValue = sourceFilter.value;
      const needle = searchInput.value.trim().toLowerCase();
      const notes = annotationText.value.trim();
      const filtered = events.filter((event) => {{
        const haystack = [event.title, event.description, event.source_file, event.artifact_type, JSON.stringify(event.metadata), (event.tags || []).join(" ")].join(" ").toLowerCase();
        return (sourceValue === "all" || event.source_type === sourceValue) && (!needle || haystack.includes(needle));
      }});

      if (!filtered.length) {{
        timelineNode.innerHTML = "<p>No events match the active filters.</p>";
        return;
      }}

      timelineNode.innerHTML = filtered.map((event) => {{
        const chips = Object.entries(event.metadata || {{}})
          .filter(([, value]) => value)
          .slice(0, 6)
          .map(([key, value]) => `<span class="chip">${{key}}: ${{escapeHtml(String(value))}}</span>`)
          .join("");
        const investigatorNote = notes ? `<div class="chips"><span class="chip">investigator_note: ${{escapeHtml(notes)}}</span></div>` : "";
        return `
          <article class="event">
            <h3>${{escapeHtml(event.title)}}</h3>
            <div class="meta">${{escapeHtml(event.timestamp_utc)}} | ${{escapeHtml(event.source_type)}} | ${{escapeHtml(event.artifact_type)}} | confidence=${{escapeHtml(String(event.confidence))}}</div>
            <div>${{escapeHtml(event.description)}}</div>
            <div class="chips">${{chips}}</div>
            ${{investigatorNote}}
          </article>
        `;
      }}).join("");
    }}

    function exportEvidence() {{
      const payload = {{
        case_name: caseName,
        generated_at_utc: new Date().toISOString(),
        investigator_annotation: annotationText.value.trim(),
        artefacts_scanned: scannedFiles,
        parser_warnings: parserWarnings,
        events,
      }};
      const blob = new Blob([JSON.stringify(payload, null, 2)], {{ type: "application/json" }});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "forensync_evidence_export.json";
      link.click();
      URL.revokeObjectURL(url);
    }}

    saveNotesBtn.addEventListener("click", () => {{
      localStorage.setItem(storageKey, annotationText.value);
      renderTimeline();
    }});
    exportBtn.addEventListener("click", exportEvidence);
    searchInput.addEventListener("input", renderTimeline);
    sourceFilter.addEventListener("change", renderTimeline);

    populateStats();
    populateFilters();
    renderWarnings();
    loadNotes();
    renderTimeline();
  </script>
</body>
</html>
"""


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().strip().split())


def _metadata_identity(event: TimelineEvent) -> set[str]:
    identities: set[str] = set()
    if event.source_type == "browser_history":
        url = event.metadata.get("url") or event.dedupe_key
        if url:
            identities.add(f"browser:{_normalize_text(str(url))}")
    elif event.source_type == "prefetch":
        executable = event.metadata.get("executable") or event.dedupe_key
        timestamp_type = event.metadata.get("timestamp_type") or event.raw_timestamp or "execution"
        identities.add(f"prefetch:{_normalize_text(str(executable))}:{_normalize_text(str(timestamp_type))}")
    elif event.source_type == "registry":
        registry_key = event.metadata.get("registry_key") or ""
        value_name = event.metadata.get("value_name")
        if value_name:
            identities.add(f"registry-value:{_normalize_text(str(registry_key))}:{_normalize_text(str(value_name))}")
        elif registry_key:
            identities.add(f"registry-key:{_normalize_text(str(registry_key))}")
    elif event.source_type == "event_log":
        provider = event.metadata.get("provider") or ""
        event_id = event.metadata.get("event_id") or ""
        record_id = event.metadata.get("event_record_id") or ""
        channel = event.metadata.get("channel") or ""
        computer = event.metadata.get("computer") or ""
        identities.add(
            "evtx:"
            + ":".join(
                _normalize_text(str(part))
                for part in (provider, event_id, record_id, channel, computer)
            )
        )
    if event.dedupe_key:
        identities.add(f"dedupe:{_normalize_text(event.dedupe_key)}")
    return identities


def _events_overlap(left: TimelineEvent, right: TimelineEvent) -> bool:
    if abs(left.timestamp_unix - right.timestamp_unix) > 1:
        return False
    if _metadata_identity(left) & _metadata_identity(right):
        return True
    return (
        _normalize_text(left.title) == _normalize_text(right.title)
        and _normalize_text(left.description) == _normalize_text(right.description)
    )


def _merge_values(primary: Any, secondary: Any) -> Any:
    if primary in (None, "", [], {}):
        return secondary
    if isinstance(primary, dict) and isinstance(secondary, dict):
        merged = dict(primary)
        for key, value in secondary.items():
            if key not in merged or merged[key] in (None, "", [], {}):
                merged[key] = value
        return merged
    if isinstance(primary, list) and isinstance(secondary, list):
        merged: list[Any] = []
        for item in primary + secondary:
            if item not in merged:
                merged.append(item)
        return merged
    return primary


def _merge_events(left: TimelineEvent, right: TimelineEvent) -> TimelineEvent:
    primary = left
    secondary = right
    if (right.fidelity_rank, right.confidence, len(right.metadata)) > (left.fidelity_rank, left.confidence, len(left.metadata)):
        primary, secondary = right, left

    merged = TimelineEvent(
        event_id=primary.event_id,
        timestamp_utc=primary.timestamp_utc if primary.timestamp_unix <= secondary.timestamp_unix else secondary.timestamp_utc,
        timestamp_unix=min(primary.timestamp_unix, secondary.timestamp_unix),
        source_type=primary.source_type,
        artifact_type=primary.artifact_type,
        source_file=primary.source_file,
        title=primary.title,
        description=primary.description,
        dedupe_key=primary.dedupe_key,
        parser=primary.parser,
        confidence=max(primary.confidence, secondary.confidence),
        fidelity_rank=max(primary.fidelity_rank, secondary.fidelity_rank),
        tags=_merge_values(primary.tags, secondary.tags),
        metadata=_merge_values(primary.metadata, secondary.metadata),
        raw_timestamp=primary.raw_timestamp or secondary.raw_timestamp,
        merged_event_ids=_merge_values(primary.merged_event_ids, secondary.merged_event_ids),
        provenance=_merge_values(primary.provenance, secondary.provenance),
    )
    merged.metadata["related_sources"] = sorted({left.source_type, right.source_type})
    merged.metadata["merged_count"] = len(merged.merged_event_ids)
    if secondary.source_file != primary.source_file:
        secondary_files = list(primary.metadata.get("secondary_source_files", []) or [])
        secondary_files.extend(secondary.metadata.get("secondary_source_files", []) or [])
        secondary_files.append(secondary.source_file)
        merged.metadata["secondary_source_files"] = sorted({path for path in secondary_files if path})
    return merged
