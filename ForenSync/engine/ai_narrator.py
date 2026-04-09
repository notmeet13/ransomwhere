from __future__ import annotations

from collections import Counter
from typing import Sequence

from engine.anomaly_detector import find_event_outliers
from engine.models import TimelineEvent


def build_case_summary(
    case_name: str,
    scanned_files: Sequence[str],
    parser_warnings: Sequence[str],
    events: Sequence[TimelineEvent],
) -> str:
    source_breakdown = Counter(event.source_type for event in events)
    outliers = find_event_outliers(events)

    lines = [
        f"# {case_name}",
        "",
        "## Overview",
        f"- Artefacts scanned: {len(scanned_files)}",
        f"- Timeline events retained: {len(events)}",
        f"- Source types observed: {', '.join(sorted(source_breakdown)) or 'none'}",
        "",
        "## Source Breakdown",
    ]

    for source_type, count in sorted(source_breakdown.items()):
        lines.append(f"- {source_type}: {count}")

    lines.extend(["", "## Key Observations"])
    if events:
        lines.append(f"- Earliest event: {events[0].timestamp_utc}")
        lines.append(f"- Latest event: {events[-1].timestamp_utc}")
    else:
        lines.append("- No events were parsed from the supplied artefacts.")

    if outliers:
        lines.extend(f"- {message}" for message in outliers)
    else:
        lines.append("- No obvious outliers were detected by the MVP heuristics.")

    lines.extend(["", "## Parser Warnings"])
    if parser_warnings:
        lines.extend(f"- {warning}" for warning in parser_warnings)
    else:
        lines.append("- None")

    return "\n".join(lines) + "\n"
