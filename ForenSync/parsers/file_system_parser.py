from __future__ import annotations

import struct
from datetime import UTC, datetime
from pathlib import Path

from engine.models import TimelineEvent, make_event, windows_filetime_to_datetime


def parse_registry_export(file_path: Path) -> tuple[list[TimelineEvent], list[str]]:
    modified_time = datetime.fromtimestamp(file_path.stat().st_mtime, tz=UTC)
    current_key = "unknown"
    events: list[TimelineEvent] = []
    warnings: list[str] = []

    content = None
    for encoding in ("utf-16", "utf-8", "latin-1"):
        try:
            content = file_path.read_text(encoding=encoding)
            break
        except UnicodeError:
            continue
    if content is None:
        content = file_path.read_text(encoding="utf-8", errors="ignore")

    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith(("Windows Registry Editor", "REGEDIT4")):
            continue
        if line.startswith("[") and line.endswith("]"):
            current_key = line.strip("[]")
            events.append(
                make_event(
                    dt=modified_time,
                    source_type="registry",
                    artifact_type="reg_export",
                    source_file=str(file_path),
                    title="Registry key exported",
                    description=f"Registry key observed: {current_key}",
                    dedupe_key=current_key,
                    parser="reg_export_parser",
                    confidence=0.4,
                    fidelity_rank=25,
                    tags=["registry", "key"],
                    metadata={"registry_key": current_key, "line_number": line_number},
                    raw_timestamp="file_mtime",
                )
            )
            continue
        if "=" in line:
            name, value = line.split("=", 1)
            value_name = name.strip().strip('"') or "(Default)"
            events.append(
                make_event(
                    dt=modified_time,
                    source_type="registry",
                    artifact_type="reg_export",
                    source_file=str(file_path),
                    title=f"Registry value exported: {value_name}",
                    description=f"Value observed under {current_key}: {value[:180]}",
                    dedupe_key=f"{current_key}|{value_name}",
                    parser="reg_export_parser",
                    confidence=0.45,
                    fidelity_rank=30,
                    tags=["registry", "value"],
                    metadata={
                        "registry_key": current_key,
                        "value_name": value_name,
                        "value_preview": value[:180],
                        "line_number": line_number,
                    },
                    raw_timestamp="file_mtime",
                )
            )

    if not events:
        warnings.append(f"No registry entries were parsed from {file_path.name}.")
    return events, warnings


def _decode_prefetch_executable_name(blob: bytes) -> str | None:
    raw_name = blob[16:76]
    try:
        return raw_name.decode("utf-16le", errors="ignore").split("\x00", 1)[0].strip() or None
    except UnicodeError:
        return None


def _parse_prefetch_binary(file_path: Path) -> tuple[dict[str, object], list[str]]:
    warnings: list[str] = []
    blob = file_path.read_bytes()
    placeholder_text = blob.decode("utf-8", errors="ignore").strip().lower()
    if "prefetch placeholder" in placeholder_text:
        raise ValueError("Placeholder prefetch fixture detected.")
    if len(blob) < 160:
        raise ValueError("Prefetch file is too small to contain a valid header.")
    if blob[4:8] != b"SCCA":
        raise ValueError("Invalid prefetch signature.")

    version = int.from_bytes(blob[0:4], "little", signed=False)
    executable_name = _decode_prefetch_executable_name(blob) or file_path.stem.split("-")[0]
    run_time_layout = {
        17: (120, 1, 144),
        23: (128, 1, 152),
        26: (128, 8, 208),
        30: (128, 8, 208),
    }
    run_times: list[datetime] = []
    run_count = None
    if version in run_time_layout:
        run_offset, run_slots, run_count_offset = run_time_layout[version]
        for slot in range(run_slots):
            start = run_offset + (slot * 8)
            end = start + 8
            if end > len(blob):
                break
            dt = windows_filetime_to_datetime(struct.unpack("<Q", blob[start:end])[0])
            if dt is not None:
                run_times.append(dt)
        if run_count_offset + 4 <= len(blob):
            run_count = struct.unpack("<I", blob[run_count_offset:run_count_offset + 4])[0]
    else:
        warnings.append(f"Prefetch version {version} is not explicitly mapped; using filesystem timestamps as fallback.")

    return {
        "version": version,
        "executable_name": executable_name,
        "run_times": run_times,
        "run_count": run_count,
    }, warnings


def parse_prefetch_file(file_path: Path) -> tuple[list[TimelineEvent], list[str]]:
    stat = file_path.stat()
    base_name = file_path.stem
    executable_name = base_name.split("-")[0]
    created = datetime.fromtimestamp(stat.st_ctime, tz=UTC)
    modified = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
    accessed = datetime.fromtimestamp(stat.st_atime, tz=UTC)
    warnings: list[str] = []
    events: list[TimelineEvent] = []

    try:
        parsed, parse_warnings = _parse_prefetch_binary(file_path)
        warnings.extend(parse_warnings)
        executable_name = str(parsed["executable_name"])
        for run_dt in parsed["run_times"]:
            events.append(
                make_event(
                    dt=run_dt,
                    source_type="prefetch",
                    artifact_type="prefetch",
                    source_file=str(file_path),
                    title=f"Program execution inferred for {executable_name}",
                    description="Execution time recovered from the prefetch run timestamp array.",
                    dedupe_key=f"{executable_name}|execution",
                    parser="prefetch_binary",
                    confidence=0.95,
                    fidelity_rank=90,
                    tags=["prefetch", "execution"],
                    metadata={
                        "executable": executable_name,
                        "prefetch_version": parsed["version"],
                        "run_count": parsed["run_count"],
                    },
                    raw_timestamp="prefetch_run_time",
                )
            )
        if parsed["run_count"] is not None:
            events.append(
                make_event(
                    dt=modified,
                    source_type="prefetch",
                    artifact_type="prefetch",
                    source_file=str(file_path),
                    title=f"Prefetch execution count observed for {executable_name}",
                    description=f"Prefetch indicates the executable ran {parsed['run_count']} times.",
                    dedupe_key=f"{executable_name}|run_count",
                    parser="prefetch_binary",
                    confidence=0.72,
                    fidelity_rank=55,
                    tags=["prefetch", "run_count"],
                    metadata={
                        "executable": executable_name,
                        "prefetch_version": parsed["version"],
                        "run_count": parsed["run_count"],
                    },
                    raw_timestamp="file_mtime",
                )
            )
    except ValueError as exc:
        known_fallbacks = {
            "Placeholder prefetch fixture detected.",
            "Prefetch file is too small to contain a valid header.",
            "Invalid prefetch signature.",
        }
        if str(exc) not in known_fallbacks:
            warnings.append(f"Binary prefetch parsing failed for {file_path.name}; falling back to filesystem timestamps: {exc}")
    except Exception as exc:
        warnings.append(f"Binary prefetch parsing failed for {file_path.name}; falling back to filesystem timestamps: {exc}")

    events.extend(
        [
            make_event(
                dt=created,
                source_type="prefetch",
                artifact_type="prefetch",
                source_file=str(file_path),
                title=f"Prefetch created for {executable_name}",
                description="Prefetch artefact discovered on disk.",
                dedupe_key=f"{executable_name}|created",
                parser="prefetch_filesystem_fallback",
                confidence=0.35,
                fidelity_rank=15,
                tags=["prefetch", "filesystem_time"],
                metadata={"timestamp_type": "created", "executable": executable_name},
                raw_timestamp="file_ctime",
            ),
            make_event(
                dt=modified,
                source_type="prefetch",
                artifact_type="prefetch",
                source_file=str(file_path),
                title=f"Prefetch modified for {executable_name}",
                description="Prefetch file modification time used as an execution hint.",
                dedupe_key=f"{executable_name}|modified",
                parser="prefetch_filesystem_fallback",
                confidence=0.5,
                fidelity_rank=20,
                tags=["prefetch", "filesystem_time"],
                metadata={"timestamp_type": "modified", "executable": executable_name},
                raw_timestamp="file_mtime",
            ),
            make_event(
                dt=accessed,
                source_type="prefetch",
                artifact_type="prefetch",
                source_file=str(file_path),
                title=f"Prefetch accessed for {executable_name}",
                description="Prefetch file access time kept as an investigator hint.",
                dedupe_key=f"{executable_name}|accessed",
                parser="prefetch_filesystem_fallback",
                confidence=0.2,
                fidelity_rank=10,
                tags=["prefetch", "filesystem_time"],
                metadata={"timestamp_type": "accessed", "executable": executable_name},
                raw_timestamp="file_atime",
            ),
        ]
    )
    return events, warnings
