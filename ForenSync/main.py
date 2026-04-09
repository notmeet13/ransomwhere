from __future__ import annotations

import argparse
import json
from pathlib import Path

from engine.ai_narrator import build_case_summary
from engine.timeline_gen import (
    collect_artifacts,
    deduplicate_events,
    export_events_json,
    generate_timeline_html,
    write_text_file,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a unified forensic timeline from digital artefacts."
    )
    parser.add_argument(
        "--input",
        dest="inputs",
        nargs="+",
        required=True,
        help="One or more files or directories containing evidence artefacts.",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory where the JSON, HTML, and summary will be written.",
    )
    parser.add_argument(
        "--case-name",
        default="ForenSync MVP Case",
        help="Display name for the generated timeline.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    input_paths = [Path(item).expanduser().resolve() for item in args.inputs]
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_events, parser_warnings, scanned_files = collect_artifacts(input_paths)
    deduped_events = deduplicate_events(raw_events)

    timeline_json_path = output_dir / "timeline.json"
    timeline_html_path = output_dir / "timeline.html"
    summary_path = output_dir / "case_summary.md"

    export_events_json(deduped_events, timeline_json_path)
    write_text_file(
        timeline_html_path,
        generate_timeline_html(
            case_name=args.case_name,
            events=deduped_events,
            scanned_files=scanned_files,
            parser_warnings=parser_warnings,
        ),
    )
    write_text_file(
        summary_path,
        build_case_summary(
            case_name=args.case_name,
            scanned_files=scanned_files,
            parser_warnings=parser_warnings,
            events=deduped_events,
        ),
    )

    print(json.dumps(
        {
            "case_name": args.case_name,
            "scanned_files": len(scanned_files),
            "events_before_dedup": len(raw_events),
            "events_after_dedup": len(deduped_events),
            "timeline_json": str(timeline_json_path),
            "timeline_html": str(timeline_html_path),
            "case_summary": str(summary_path),
            "warnings": parser_warnings,
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
