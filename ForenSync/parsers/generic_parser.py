from __future__ import annotations

import csv
import re
from datetime import UTC, datetime
from pathlib import Path
from dateutil import parser as date_parser

from engine.models import TimelineEvent, make_event

# Common regex patterns for log timestamps
TIMESTAMP_PATTERNS = [
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}", # 2023-01-01 12:00:00 or ISO
    r"^[A-Z][a-z]{2} \d{2} \d{2}:\d{2}:\d{2}",  # Jan 01 12:00:00 (Syslog)
    r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}",    # 01/01/2023 12:00:00
]

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
            found_ts = None
            
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
                
                # Title is the first bit of text after the timestamp or the whole line
                description = line
                title = "Sequential Log Entry"
                
                events.append(
                    make_event(
                        dt=dt,
                        source_type="generic_log",
                        artifact_type="log",
                        source_file=str(file_path),
                        title=title,
                        description=description,
                        dedupe_key=f"{file_path.name}|{line_idx}",
                        parser="generic_log_parser",
                        confidence=0.5,
                        fidelity_rank=35,
                        tags=["log", "generic"],
                        metadata={"line_number": line_idx},
                        raw_timestamp="extracted_from_line"
                    )
                )
    except Exception as e:
        warnings.append(f"Failed to parse Log {file_path.name}: {e}")
        
    return events, warnings
