"""Ledger system for AITAPES v8.0.

Append-only JSONL ledger that records every decision.
Enables epistemic continuity and failure pattern detection.

v8.0 additions:
    - intent_embedding field for vector grounding
    - oscillation_counter for scorched earth loop
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LedgerEntry:
    """A single ledger entry."""
    entry_type: str  # "plan", "build", "check", "review"
    command: str
    input_hash: str
    output_summary: str
    timestamp: str
    details: dict[str, Any] | None = None
    intent_embedding: list[float] | None = None

    def __post_init__(self) -> None:
        if self.details is None:
            object.__setattr__(self, "details", {})
        if self.intent_embedding is None:
            object.__setattr__(self, "intent_embedding", [])


def compute_hash(text: str) -> str:
    """Compute SHA256 hash of text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# Feature 3: L1 Hashmap Cache (bounded)
_L1_CACHE: dict[str, list[LedgerEntry]] = {}
_L1_MAX_ENTRIES = 1000

def append_entry(
    ledger_path: str | Path,
    entry_type: str,
    command: str,
    input_text: str,
    output_summary: str,
    details: dict[str, Any] | None = None,
    intent_embedding: list[float] | None = None,
) -> LedgerEntry:
    """Append an entry to the L1 Cache."""
    entry = LedgerEntry(
        entry_type=entry_type,
        command=command,
        input_hash=compute_hash(input_text),
        output_summary=output_summary,
        timestamp=datetime.now(UTC).isoformat(),
        details=details or {},
        intent_embedding=intent_embedding or [],
    )

    str_path = str(ledger_path)
    if str_path not in _L1_CACHE:
        _L1_CACHE[str_path] = read_entries(ledger_path)

    _L1_CACHE[str_path].append(entry)
    flush_ledger(ledger_path)

    if len(_L1_CACHE[str_path]) > _L1_MAX_ENTRIES:
        _L1_CACHE[str_path] = _L1_CACHE[str_path][-_L1_MAX_ENTRIES:]

    return entry

def flush_ledger(ledger_path: str | Path) -> None:
    """Flush the L1 Cache to disk atomically as a strict JSON array."""
    str_path = str(ledger_path)
    if str_path not in _L1_CACHE or not _L1_CACHE[str_path]:
        return

    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = path.with_suffix(".jsonl.tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump([asdict(e) for e in _L1_CACHE[str_path]], f, indent=2)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError as e:
                logger.warning("fsync failed (non-critical): %s", e)
        tmp_path.replace(path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def read_entries(ledger_path: str | Path) -> list[LedgerEntry]:
    """Read all entries from the ledger (array or JSONL)."""
    path = Path(ledger_path)
    str_path = str(ledger_path)
    
    if str_path in _L1_CACHE:
        return list(_L1_CACHE[str_path])
        
    if not path.exists():
        return []

    entries: list[LedgerEntry] = []
    try:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return entries
        if content.startswith("["):
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                return entries
            for item in data:
                if "details" not in item or item["details"] is None:
                    item["details"] = {}
                if "intent_embedding" not in item or item["intent_embedding"] is None:
                    item["intent_embedding"] = []
                entries.append(LedgerEntry(**{k: v for k, v in item.items() if k in LedgerEntry.__dataclass_fields__}))
        else:
            for line in content.splitlines():
                stripped = line.strip()
                if not stripped: continue
                try:
                    data = json.loads(stripped)
                    if "details" not in data or data["details"] is None:
                        data["details"] = {}
                    if "intent_embedding" not in data or data["intent_embedding"] is None:
                        data["intent_embedding"] = []
                    entries.append(LedgerEntry(**{k: v for k, v in data.items() if k in LedgerEntry.__dataclass_fields__}))
                except (json.JSONDecodeError, TypeError):
                    continue
    except (OSError, json.JSONDecodeError):
        pass
        
    _L1_CACHE[str_path] = entries
    return entries


def get_entries_by_type(ledger_path: str | Path, entry_type: str) -> list[LedgerEntry]:
    """Get entries filtered by type."""
    return [e for e in read_entries(ledger_path) if e.entry_type == entry_type]


def get_recent_entries(ledger_path: str | Path, count: int = 10) -> list[LedgerEntry]:
    """Get the most recent N entries."""
    entries = read_entries(ledger_path)
    return entries[-count:]

def wipe_memory(ledger_path: str | Path) -> None:
    """Feature 11: Amnesiac Retry. Wipe Surgeon's recent memory (last build/check logs)."""
    str_path = str(ledger_path)
    if str_path not in _L1_CACHE:
        _L1_CACHE[str_path] = read_entries(ledger_path)
    if str_path in _L1_CACHE:
        cleaned = [e for e in _L1_CACHE[str_path] if e.entry_type not in ("build", "check")]
        _L1_CACHE[str_path] = cleaned
    flush_ledger(ledger_path)


def get_failure_patterns(ledger_path: str | Path) -> dict[str, int]:
    """Analyze ledger for repeated failure patterns."""
    entries = read_entries(ledger_path)
    patterns: dict[str, int] = {}

    for entry in entries:
        if entry.entry_type == "check":
            details = entry.details or {}
            if details.get("overall") == "fail":
                # Extract pattern from summary
                summary = entry.output_summary
                pattern_key = summary[:50] if summary else "unknown"
                patterns[pattern_key] = patterns.get(pattern_key, 0) + 1

    return patterns


def get_all_embeddings(ledger_path: str | Path) -> list[list[float]]:
    """Extract all non-empty intent embeddings from the ledger."""
    entries = read_entries(ledger_path)
    return [e.intent_embedding for e in entries if e.intent_embedding]


def store_patch_result(ledger_path: str | Path, intent: str, patches: list, applied: int, failed: int, retrieval_contract: dict | None = None, diffs: list[str] | None = None) -> None:
    """Store a successful or failed patch result for future reuse."""
    details = {
        "intent": intent,
        "patches": [(p.file, p.target_symbol, p.search, p.replace) for p in patches[:10]],
        "applied": applied,
        "failed": failed,
        "retrieval_contract": retrieval_contract or {},
    }
    if diffs:
        details["diffs"] = diffs[:5]
    append_entry(
        ledger_path=ledger_path,
        entry_type="patch_result",
        command="tapes build",
        input_text=intent,
        output_summary=f"{applied} applied, {failed} failed",
        details=details,
    )


def find_similar_patches(ledger_path: str | Path, intent: str, max_results: int = 3) -> list[dict]:
    """Find previously successful patches for similar intents."""
    from difflib import SequenceMatcher

    entries = read_entries(ledger_path)
    results = []
    target_lower = intent.lower()

    for e in entries:
        if e.entry_type not in ("patch_result", "build") or not e.details:
            continue
        prev_intent = e.details.get("intent", "")
        if not prev_intent:
            continue
        similarity = SequenceMatcher(None, target_lower, prev_intent.lower()).ratio()
        if similarity > 0.4 and e.details.get("applied", 0) > 0:
            results.append({
                "similarity": similarity,
                "original_intent": prev_intent,
                "patches": e.details.get("patches", [])[:5],
                "applied": e.details.get("applied", 0),
                "retrieval_contract": e.details.get("retrieval_contract", {}),
            })

    results.sort(key=lambda x: -x["similarity"])
    return results[:max_results]


def format_entries(entries: list[LedgerEntry]) -> str:
    """Format entries as human-readable text."""
    if not entries:
        return "No ledger entries."

    lines: list[str] = []
    for entry in entries:
        lines.append(f"[{entry.timestamp}] {entry.command} ({entry.entry_type})")
        lines.append(f"  Hash: {entry.input_hash}")
        lines.append(f"  Summary: {entry.output_summary}")
        if entry.intent_embedding:
            lines.append(f"  Embedding: [{len(entry.intent_embedding)} dims]")
        lines.append("")

    return "\n".join(lines)
