from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

from engine.models import TimelineEvent, make_event


def parse_event_log(file_path: Path) -> tuple[list[TimelineEvent], list[str]]:
    warnings: list[str] = []

    try:
        from Evtx.Evtx import Evtx  # type: ignore
    except ImportError:
        warnings.append(
            f"Optional dependency 'python-evtx' is not installed; EVTX file parsed as metadata only: {file_path}"
        )
        stat = file_path.stat()
        return [
            make_event(
                dt=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                source_type="event_log",
                artifact_type="evtx",
                source_file=str(file_path),
                title="EVTX artefact discovered",
                description="Raw EVTX file detected. Install python-evtx for record-level extraction.",
                dedupe_key=file_path.name,
                parser="evtx_metadata_fallback",
                confidence=0.25,
                fidelity_rank=10,
                tags=["evtx", "fallback"],
                metadata={"size_bytes": str(stat.st_size)},
            )
        ], warnings

    events: list[TimelineEvent] = []
    with Evtx(str(file_path)) as log:
        for index, record in enumerate(log.records()):
            try:
                root = ElementTree.fromstring(record.xml())
                namespace = {"e": "http://schemas.microsoft.com/win/2004/08/events/event"}
                system = root.find("e:System", namespace)
                if system is None:
                    continue
                timestamp = system.find("e:TimeCreated", namespace)
                event_id = system.findtext("e:EventID", default="", namespaces=namespace)
                record_id = system.findtext("e:EventRecordID", default="", namespaces=namespace)
                level = system.findtext("e:Level", default="", namespaces=namespace)
                provider = system.find("e:Provider", namespace)
                channel = system.findtext("e:Channel", default="", namespaces=namespace)
                computer = system.findtext("e:Computer", default="", namespaces=namespace)
                utc_value = timestamp.attrib.get("SystemTime", "") if timestamp is not None else ""
                if not utc_value:
                    continue
                provider_name = provider.attrib.get("Name", "") if provider is not None else ""
                event_data = {}
                for data_node in root.findall(".//e:EventData/e:Data", namespace):
                    key = data_node.attrib.get("Name") or f"field_{len(event_data) + 1}"
                    event_data[key] = (data_node.text or "").strip()
                events.append(
                    make_event(
                        dt=datetime.fromisoformat(utc_value.replace("Z", "+00:00")).astimezone(UTC),
                        source_type="event_log",
                        artifact_type="evtx",
                        source_file=str(file_path),
                        title=f"Event ID {event_id} from {provider_name or 'Unknown Provider'}",
                        description=f"Channel: {channel or 'unknown'} on {computer or 'unknown host'}",
                        dedupe_key="|".join(
                            [
                                provider_name or "unknown_provider",
                                channel or "unknown_channel",
                                computer or "unknown_host",
                                event_id or "unknown_event",
                                record_id or str(index),
                            ]
                        ),
                        parser="python_evtx",
                        confidence=0.98,
                        fidelity_rank=100,
                        tags=["evtx", channel.lower()] if channel else ["evtx"],
                        metadata={
                            "event_id": event_id,
                            "event_record_id": record_id,
                            "provider": provider_name,
                            "channel": channel,
                            "computer": computer,
                            "level": level,
                            "event_data": event_data,
                        },
                        raw_timestamp=utc_value,
                    )
                )
            except Exception as exc:
                warnings.append(f"Failed to parse EVTX record {index} in {file_path.name}: {exc}")

    return events, warnings
