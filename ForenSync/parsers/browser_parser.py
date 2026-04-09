from __future__ import annotations

import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from engine.models import TimelineEvent, guess_datetime, make_event, windows_filetime_to_datetime


def _to_datetime(raw_value: object) -> datetime | None:
    if isinstance(raw_value, (int, float)) and int(raw_value) > 10**15:
        return windows_filetime_to_datetime(int(raw_value))
    return guess_datetime(raw_value)


def parse_browser_history(file_path: Path) -> tuple[list[TimelineEvent], list[str]]:
    warnings: list[str] = []
    try:
        connection = sqlite3.connect(f"file:{file_path}?mode=ro&immutable=1", uri=True)
        try:
            return _extract_browser_events(connection, file_path), warnings
        finally:
            connection.close()
    except sqlite3.DatabaseError as exc:
        warnings.append(f"SQLite immutable read failed for {file_path.name}; retrying from a temp copy: {exc}")
        temp_root = Path(__file__).resolve().parents[1] / ".forensync_tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        temp_db = temp_root / f"{uuid.uuid4().hex}_{file_path.name}"
        shutil.copy2(file_path, temp_db)
        connection = sqlite3.connect(f"file:{temp_db}?mode=ro", uri=True)
        try:
            return _extract_browser_events(connection, file_path), warnings
        finally:
            connection.close()
            temp_db.unlink(missing_ok=True)


def _extract_browser_events(connection: sqlite3.Connection, file_path: Path) -> list[TimelineEvent]:
    connection.row_factory = sqlite3.Row
    table_rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    tables = [row["name"] for row in table_rows]
    if "urls" in tables and "visits" in tables:
        return _parse_chromium_history(connection, file_path)
    if "moz_places" in tables and "moz_historyvisits" in tables:
        return _parse_firefox_history(connection, file_path)
    return _parse_generic_sqlite(connection, file_path, tables)


def _parse_chromium_history(connection: sqlite3.Connection, file_path: Path) -> list[TimelineEvent]:
    rows = connection.execute(
        """
        SELECT
            urls.url,
            urls.title,
            visits.visit_time,
            visits.transition,
            visits.from_visit,
            visits.id AS visit_id
        FROM visits
        JOIN urls ON urls.id = visits.url
        ORDER BY visits.visit_time
        """
    ).fetchall()
    events: list[TimelineEvent] = []
    for row in rows:
        timestamp = _to_datetime(row["visit_time"])
        if timestamp is None:
            continue
        title = row["title"] or row["url"] or "Browser visit"
        url = row["url"] or "unknown URL"
        events.append(
            make_event(
                dt=timestamp,
                source_type="browser_history",
                artifact_type="sqlite",
                source_file=str(file_path),
                title=title[:140],
                description=f"Visited {url}",
                dedupe_key=url,
                parser="chromium_history",
                confidence=0.88,
                fidelity_rank=70,
                tags=["browser", "web_visit", "chromium"],
                metadata={
                    "browser_family": "chromium",
                    "transition": str(row["transition"] or ""),
                    "from_visit": str(row["from_visit"] or ""),
                    "visit_id": str(row["visit_id"] or ""),
                    "url": url,
                },
                raw_timestamp=str(row["visit_time"]),
            )
        )
    return events


def _parse_firefox_history(connection: sqlite3.Connection, file_path: Path) -> list[TimelineEvent]:
    rows = connection.execute(
        """
        SELECT
            moz_places.url,
            moz_places.title,
            moz_historyvisits.visit_date,
            moz_historyvisits.id AS visit_id,
            moz_places.visit_count
        FROM moz_historyvisits
        JOIN moz_places ON moz_places.id = moz_historyvisits.place_id
        WHERE moz_historyvisits.visit_date IS NOT NULL
        ORDER BY moz_historyvisits.visit_date
        """
    ).fetchall()
    events: list[TimelineEvent] = []
    for row in rows:
        timestamp = _to_datetime(row["visit_date"])
        if timestamp is None:
            continue
        title = row["title"] or row["url"] or "Firefox visit"
        url = row["url"] or "unknown URL"
        events.append(
            make_event(
                dt=timestamp,
                source_type="browser_history",
                artifact_type="sqlite",
                source_file=str(file_path),
                title=title[:140],
                description=f"Visited {url}",
                dedupe_key=url,
                parser="firefox_history",
                confidence=0.88,
                fidelity_rank=70,
                tags=["browser", "web_visit", "firefox"],
                metadata={
                    "browser_family": "firefox",
                    "visit_count": str(row["visit_count"] or ""),
                    "visit_id": str(row["visit_id"] or ""),
                    "url": url,
                },
                raw_timestamp=str(row["visit_date"]),
            )
        )
    return events


def _parse_generic_sqlite(connection: sqlite3.Connection, file_path: Path, tables: list[str]) -> list[TimelineEvent]:
    timestamp_columns = ("timestamp", "time", "visit_time", "visit_date", "last_visit_date", "created_at", "updated_at")
    events: list[TimelineEvent] = []
    for table in tables:
        column_rows = connection.execute(f"PRAGMA table_info('{table}')").fetchall()
        columns = [row["name"] for row in column_rows]
        selected_column = next((column for column in columns if column.lower() in timestamp_columns), None)
        if not selected_column:
            continue
        rows = connection.execute(f"SELECT * FROM '{table}' LIMIT 250").fetchall()
        for index, row in enumerate(rows):
            timestamp = _to_datetime(row[selected_column])
            if timestamp is None:
                continue
            metadata = {key: str(row[key]) for key in row.keys() if row[key] is not None and key != selected_column}
            events.append(
                make_event(
                    dt=timestamp,
                    source_type="browser_history",
                    artifact_type="sqlite",
                    source_file=str(file_path),
                    title=f"{table} row {index + 1}",
                    description=f"Recovered generic SQLite event from table '{table}'.",
                    dedupe_key=f"{table}:{index + 1}",
                    parser="generic_sqlite",
                    confidence=0.55,
                    fidelity_rank=35,
                    tags=["sqlite", "generic"],
                    metadata=metadata,
                    raw_timestamp=str(row[selected_column]),
                )
            )
    return events
