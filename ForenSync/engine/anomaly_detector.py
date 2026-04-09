from __future__ import annotations

from collections import Counter
from typing import Iterable

from engine.models import TimelineEvent


def find_event_outliers(events: Iterable[TimelineEvent]) -> list[str]:
    events_list = list(events)
    source_counts = Counter(event.source_type for event in events_list)
    messages: list[str] = []

    for source_type, count in source_counts.items():
        if count == 1:
            messages.append(f"Persistence Indicator: Only one event was found for '{source_type}', possible outlier.")

    # 1. Detect Log Clearing (Critical)
    log_cleared_events = [
        event for event in events_list 
        if event.source_type == "event_log" and (
            event.metadata.get("event_id") in ("1102", "104") or 
            "cleared" in event.title.lower() or 
            "deleted" in event.description.lower()
        )
    ]
    if log_cleared_events:
        messages.append(f"CRITICAL: {len(log_cleared_events)} Audit Log Clearing events detected. This often indicates anti-forensic activity.")

    # 2. Suspicious Binary Executions (Prefetch)
    suspicious_binaries = ("cmd.exe", "powershell.exe", "whoami.exe", "net.exe", "vssadmin.exe", "certutil.exe")
    executions = [
        event for event in events_list
        if event.source_type == "prefetch" and any(b in event.title.lower() for b in suspicious_binaries)
    ]
    if executions:
        unique_bins = set(e.metadata.get("executable", "unknown") for e in executions)
        messages.append(f"SUSPICIOUS: Execution of system administration tools discovered: {', '.join(unique_bins)}.")

    # 3. Browser Anomaly (Suspicious URLs)
    suspicious_urls = ("temp.sh", "mega.nz", "anonfiles", "githubusercontent", ".onion")
    browser_hits = [
        event for event in events_list
        if event.source_type == "browser_history" and any(u in event.description.lower() for u in suspicious_urls)
    ]
    if browser_hits:
        messages.append(f"WARNING: {len(browser_hits)} browser visits to known lateral movement or data exfiltration domains.")

    # 4. Account Manipulation
    account_events = [
        event for event in events_list
        if event.source_type == "event_log" and event.metadata.get("event_id") in ("4720", "4722", "4723", "4724", "4725", "4726", "4738")
    ]
    if account_events:
        messages.append(f"ALERT: {len(account_events)} User Account Management events detected (Creation/Modification/Disabling).")

    return messages
