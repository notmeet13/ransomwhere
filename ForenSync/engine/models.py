from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
import hashlib


@dataclass
class TimelineEvent:
    event_id: str
    timestamp_utc: str
    timestamp_unix: int
    source_type: str
    artifact_type: str
    source_file: str
    title: str
    description: str
    dedupe_key: str
    parser: str
    confidence: float
    fidelity_rank: int
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_timestamp: str | None = None
    merged_event_ids: list[str] = field(default_factory=list)
    provenance: list[dict[str, Any]] = field(default_factory=list)


def isoformat_utc(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def datetime_to_unix(value: datetime) -> int:
    return int(ensure_utc(value).timestamp())


def windows_filetime_to_datetime(raw_value: int | float | str | None) -> datetime | None:
    try:
        if raw_value in (None, "", 0, "0"):
            return None
        ticks = int(raw_value)
    except (TypeError, ValueError):
        return None
    if ticks <= 0:
        return None
    return datetime(1601, 1, 1, tzinfo=UTC) + timedelta(microseconds=ticks / 10)


def guess_datetime(raw_value: object) -> datetime | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, datetime):
        return ensure_utc(raw_value)
    if isinstance(raw_value, bytes):
        raw_value = raw_value.decode("utf-8", errors="ignore")
    if isinstance(raw_value, str):
        candidate = raw_value.strip()
        if not candidate:
            return None
        try:
            return ensure_utc(datetime.fromisoformat(candidate.replace("Z", "+00:00")))
        except ValueError:
            try:
                raw_value = float(candidate)
            except ValueError:
                return None
    if isinstance(raw_value, float):
        raw_value = int(raw_value)
    if not isinstance(raw_value, int):
        return None
    if raw_value > 10**16:
        return windows_filetime_to_datetime(raw_value)
    if raw_value > 10**14:
        return datetime.fromtimestamp(raw_value / 1_000_000, tz=UTC)
    if raw_value > 10**11:
        return datetime.fromtimestamp(raw_value / 1_000, tz=UTC)
    if raw_value > 10**8:
        return datetime.fromtimestamp(raw_value, tz=UTC)
    return None


def build_event_id(*parts: object) -> str:
    digest = hashlib.sha1("|".join(str(part) for part in parts).encode("utf-8", errors="ignore")).hexdigest()
    return digest[:16]


def make_event(
    *,
    dt: datetime,
    source_type: str,
    artifact_type: str,
    source_file: str,
    title: str,
    description: str,
    dedupe_key: str,
    parser: str,
    confidence: float,
    fidelity_rank: int,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    raw_timestamp: str | None = None,
) -> TimelineEvent:
    normalized_dt = ensure_utc(dt)
    event = TimelineEvent(
        event_id=build_event_id(source_type, artifact_type, source_file, dedupe_key, isoformat_utc(normalized_dt), title),
        timestamp_utc=isoformat_utc(normalized_dt),
        timestamp_unix=datetime_to_unix(normalized_dt),
        source_type=source_type,
        artifact_type=artifact_type,
        source_file=source_file,
        title=title,
        description=description,
        dedupe_key=dedupe_key,
        parser=parser,
        confidence=round(max(0.0, min(confidence, 1.0)), 3),
        fidelity_rank=fidelity_rank,
        tags=tags or [],
        metadata=metadata or {},
        raw_timestamp=raw_timestamp,
    )
    event.merged_event_ids = [event.event_id]
    event.provenance = [
        {
            "event_id": event.event_id,
            "source_type": source_type,
            "artifact_type": artifact_type,
            "source_file": source_file,
            "parser": parser,
            "confidence": event.confidence,
        }
    ]
    return event
