from __future__ import annotations

from collections import Counter
from typing import Iterable

from engine.models import TimelineEvent


def find_event_outliers(events: Iterable[TimelineEvent]) -> list[str]:
    source_counts = Counter(event.source_type for event in events)
    messages: list[str] = []

    for source_type, count in source_counts.items():
        if count == 1:
            messages.append(f"Only one event was parsed from source type '{source_type}'.")

    suspicious_keywords = ("deleted", "disabled", "cleared", "failed", "error", "warning")
    suspicious = [
        event
        for event in events
        if any(keyword in event.description.lower() for keyword in suspicious_keywords)
    ]
    if suspicious:
        messages.append(
            f"{len(suspicious)} events contain high-interest keywords like deleted, failed, or cleared."
        )

    return messages
