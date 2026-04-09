from __future__ import annotations

from collections import Counter
from typing import Sequence

from engine.anomaly_detector import find_event_outliers
from engine.models import TimelineEvent


def generate_investigation_narrative(events: Sequence[TimelineEvent]) -> str:
    if not events:
        return "No significant events to narrate."
    
    # Pick top 10 most "important" events based on fidelity and confidence
    significant = sorted(events, key=lambda e: (e.fidelity_rank, e.confidence), reverse=True)[:10]
    significant.sort(key=lambda e: e.timestamp_unix)

    narrative = ["### Detailed Chronology\n"]
    for event in significant:
        time_str = event.timestamp_utc.split('T')[1][:5]
        # Clean up titles that are just file names to make them more readable
        source_label = event.source_type.replace('_', ' ').title()
        event_title = event.title
        if "Log Entry:" in event_title:
            event_title = "Log Activity"
            
        narrative.append(f"- **{time_str}** [{source_label}]\n  > {event_title}: {event.description}\n")
    
    return "\n".join(narrative)


def build_case_summary(
    case_name: str,
    scanned_files: Sequence[str],
    parser_warnings: Sequence[str],
    events: Sequence[TimelineEvent],
) -> str:
    source_breakdown = Counter(event.source_type for event in events)
    outliers = find_event_outliers(events)
    narrative = generate_investigation_narrative(events)

    lines = [
        f"# {case_name}",
        "",
        "## Executive Summary",
        f"This forensic analysis processed **{len(scanned_files)}** artefacts, recovering a unified timeline of **{len(events)}** unique events. "
        f"Data was aggregated from {len(source_breakdown)} distinct source types including {', '.join(sorted(source_breakdown))}.",
        "",
        "## Anomaly Detection Results",
    ]

    if outliers:
        lines.extend(f"> [!CAUTION]\n> {message}\n" for message in outliers)
    else:
        lines.append("> [!NOTE]\n> No critical anomalies were detected by automated heuristics.")

    lines.extend([
        "",
        narrative,
        "",
        "## Technical Statistics",
    ])

    for source_type, count in sorted(source_breakdown.items()):
        lines.append(f"- **{source_type.replace('_', ' ').title()}**: {count} records")

    if parser_warnings:
        lines.extend(["", "## Parser Warnings"])
        lines.extend(f"- {warning}" for warning in parser_warnings)

    return "\n".join(lines) + "\n"
