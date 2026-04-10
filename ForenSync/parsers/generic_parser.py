from __future__ import annotations

import csv
import re
from datetime import UTC
from pathlib import Path
from dateutil import parser as date_parser

from engine.models import TimelineEvent, make_event

# Common regex patterns for log timestamps
TIMESTAMP_PATTERNS = [
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?",
    r"^[A-Z][a-z]{2} +\d{1,2} +\d{2}:\d{2}:\d{2}",
    r"^\d{2}/\d{2}/\d{4} +\d{2}:\d{2}:\d{2}(?:[.,]\d+)?",
]
LOG_PREFIX_SEPARATORS = re.compile(r"^[\s\-\|\:\,\.\[\]\(\)]+")


def _strip_timestamp_prefix(line: str) -> str:
    for pattern in TIMESTAMP_PATTERNS:
        match = re.match(pattern, line, flags=re.IGNORECASE)
        if not match:
            continue
        remainder = line[match.end():]
        cleaned = LOG_PREFIX_SEPARATORS.sub("", remainder).strip()
        return cleaned or line
    return line


def _normalize_log_message(value: str) -> str:
    simplified = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return " ".join(simplified.split())


def parse_csv_file(file_path: Path) -> tuple[list[TimelineEvent], list[str]]:
    events: list[TimelineEvent] = []
    warnings: list[str] = []
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return [], [f"CSV {file_path.name} appears to be empty or missing headers."]
            
            # Identify timestamp column
            time_cols = [c for c in reader.fieldnames if any(k in c.lower() for k in ('time', 'date', 'timestamp', 'created', 'modified'))]
            if not time_cols:
                return [], [f"No obvious timestamp column found in {file_path.name}. Supported headers: time, date, timestamp, etc."]
            
            time_col = time_cols[0]
            for row_idx, row in enumerate(reader, start=1):
                raw_time = row.get(time_col)
                if not raw_time:
                    continue
                
                try:
                    dt = date_parser.parse(raw_time)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=UTC)
                    
                    title = row.get('title') or row.get('event') or row.get('activity') or f"CSV Record from {file_path.name}"
                    description = row.get('description') or row.get('message') or f"Data point in {file_path.name} at row {row_idx}"
                    
                    # Clean up metadata
                    metadata = {k: v for k, v in row.items() if v and k != time_col}
                    
                    events.append(
                        make_event(
                            dt=dt,
                            source_type="generic_csv",
                            artifact_type="csv",
                            source_file=str(file_path),
                            title=title,
                            description=description,
                            dedupe_key=f"{file_path.name}|{row_idx}",
                            parser="generic_csv_parser",
                            confidence=0.6,
                            fidelity_rank=40,
                            tags=["csv", "generic"],
                            metadata=metadata,
                            raw_timestamp=raw_time
                        )
                    )
                except (ValueError, OverflowError):
                    continue
                    
    except Exception as e:
        warnings.append(f"Failed to parse CSV {file_path.name}: {e}")
        
    return events, warnings

def parse_log_file(file_path: Path) -> tuple[list[TimelineEvent], list[str]]:
    events: list[TimelineEvent] = []
    warnings: list[str] = []
    
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
        for line_idx, line in enumerate(content.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            
            # Try to extract timestamp from the beginning of the line
            dt = None
            
            # Fuzzy match first 30 chars
            ts_candidate = line[:40]
            try:
                # We use fuzzy=True but try to ensure it's at the start
                dt = date_parser.parse(ts_candidate, fuzzy=True)
                # Check if it actually found a date (not just a number)
                if dt.year < 1970 or dt.year > 2035: # Basic sanity check
                    dt = None
            except (ValueError, OverflowError):
                dt = None
            
            if dt:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                
                # Keep a semantic message fingerprint so duplicated log text can merge cleanly.
                description = line
                title = "Sequential Log Entry"
                log_message = _strip_timestamp_prefix(line)
                normalized_message = _normalize_log_message(log_message) or _normalize_log_message(line)
                dedupe_key = (
                    f"log_message:{normalized_message}"
                    if normalized_message
                    else f"log_line:{file_path.name}:{line_idx}"
                )
                
                events.append(
                    make_event(
                        dt=dt,
                        source_type="generic_log",
                        artifact_type="log",
                        source_file=str(file_path),
                        title=title,
                        description=description,
                        dedupe_key=dedupe_key,
                        parser="generic_log_parser",
                        confidence=0.5,
                        fidelity_rank=35,
                        tags=["log", "generic"],
                        metadata={
                            "line_number": line_idx,
                            "log_message": log_message,
                        },
                        raw_timestamp="extracted_from_line"
                    )
                )
    except Exception as e:
        warnings.append(f"Failed to parse Log {file_path.name}: {e}")
        
    return events, warnings
