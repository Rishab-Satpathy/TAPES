from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .models import AllocationResult, LedgerCheckpoint

logger = logging.getLogger(__name__)

LEDGER_VERSION = 2

# Checkpoint every N records
CHECKPOINT_INTERVAL = 10


@dataclass(frozen=True)
class LedgerRecord:
    task_hash: str
    recorded_at: str
    allocation: dict
    outcome: str | None = None
    outcome_notes: str | None = None
    version: int = LEDGER_VERSION
    intent_embedding: list[float] | None = None


@dataclass(frozen=True)
class CorruptedLine:
    line_number: int
    raw_content: str
    error: str


@dataclass(frozen=True)
class LedgerReadResult:
    records: list[LedgerRecord]
    corrupted: tuple[CorruptedLine, ...]
    partial: bool
    checkpoints: tuple[LedgerCheckpoint, ...] = ()


@dataclass(frozen=True)
class LedgerFilter:
    task_hash: str | None = None
    outcome: str | None = None
    since: str | None = None
    until: str | None = None


def task_hash(raw_intent: str) -> str:
    return hashlib.sha256(raw_intent.encode("utf-8")).hexdigest()


def build_ledger_record(result: AllocationResult, outcome: str | None = None, outcome_notes: str | None = None) -> LedgerRecord:
    return LedgerRecord(
        task_hash=task_hash(result.contract.raw_intent),
        recorded_at=datetime.now(UTC).isoformat(),
        allocation=asdict(result),
        outcome=outcome,
        outcome_notes=outcome_notes,
    )


# Feature 3: L1 Hashmap Cache
_L1_CACHE: dict[str, list[LedgerRecord]] = {}


def append_ledger(path: str | Path, record: LedgerRecord) -> None:
    """Append a record to the in-memory cache and persist it immediately."""
    ledger_path = Path(path)
    str_path = str(ledger_path)

    if str_path not in _L1_CACHE:
        res = read_ledger_with_recovery(ledger_path)
        _L1_CACHE[str_path] = list(res.records)

    _L1_CACHE[str_path].append(record)
    _atomic_append(ledger_path, json.dumps(asdict(record), sort_keys=True) + "\n")
    _maybe_write_checkpoint(ledger_path, _L1_CACHE[str_path])

def flush_ledger(path: str | Path) -> None:
    """Append only new entries from L1 Cache to the disk ledger in JSONL format."""
    ledger_path = Path(path)
    str_path = str(ledger_path)
    
    if str_path not in _L1_CACHE or not _L1_CACHE[str_path]:
        return
    
    cache = _L1_CACHE[str_path]
    flushed_count = _FLUSH_COUNTER.get(str_path, 0)
    new_entries = cache[flushed_count:]
    
    if not new_entries:
        return
    
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as f:
        for r in new_entries:
            f.write(json.dumps(asdict(r), sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())
    
    _FLUSH_COUNTER[str_path] = len(cache)


def _atomic_append(path: Path, data: str) -> None:
    """Append a JSONL record to disk."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    except OSError:
        logger.warning("Ledger append failed for %s; continuing without persistence", path)


# Rolling counter for checkpoint decisions (avoids O(n) read on every append)
_record_count = 0
_FLUSH_COUNTER: dict[str, int] = {}


def _maybe_write_checkpoint(ledger_path: Path, records: list[LedgerRecord]) -> None:
    """Write a SHA256 checkpoint every N records using rolling counter.

    v8.0: Also triggers dynamic ontology update on checkpoint.
    """
    global _record_count
    _record_count += 1
    if _record_count >= CHECKPOINT_INTERVAL:
        try:
            if records:
                _write_checkpoint(ledger_path, records)
                # v8.0: Trigger dynamic ontology update
                _trigger_ontology_update(records)
            _record_count = 0
        except Exception:
            logger.warning("Checkpoint write failed for %s", ledger_path)


def _trigger_ontology_update(records: list[LedgerRecord]) -> None:
    """Trigger dynamic ontology update on checkpoint.

    Scans failed records for novel terms to add to the ontology.
    """
    try:
        from ..semantics.dynamic_ontology import DynamicOntology

        # Extract failed patch reasoning and check evidence
        failed_patches: list[dict] = []
        failed_checks: list[dict] = []

        for record in records:
            if record.outcome == "failure" and isinstance(record.allocation, dict):
                alloc = record.allocation
                # Look for patch reasoning in allocation data
                if "reasoning" in alloc:
                    failed_patches.append({"reasoning": alloc["reasoning"]})
                if record.outcome_notes:
                    failed_checks.append({"evidence": record.outcome_notes})

        if failed_patches or failed_checks:
            ontology = DynamicOntology()
            new_entries = ontology.synchronous_update(
                failed_patches=failed_patches,
                failed_checks=failed_checks,
            )
            if new_entries:
                logger.info("Dynamic ontology: %d new terms at checkpoint", len(new_entries))
    except Exception:
        logger.debug("Dynamic ontology update skipped (import or processing error)")


def _write_checkpoint(ledger_path: Path, records: list[LedgerRecord]) -> None:
    """Write a SHA256 checkpoint of the last N records."""
    checkpoint_path = ledger_path.with_suffix(".checkpoint.jsonl")

    # Hash last CHECKPOINT_INTERVAL records
    start_idx = max(0, len(records) - CHECKPOINT_INTERVAL)
    recent_records = records[start_idx:]
    content = json.dumps([asdict(r) for r in recent_records], sort_keys=True)
    record_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    checkpoint = LedgerCheckpoint(
        index=len(records),
        hash=record_hash,
        record_count=len(recent_records),
        timestamp=datetime.now(UTC).isoformat(),
    )

    try:
        with checkpoint_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(checkpoint), sort_keys=True) + "\n")
    except OSError:
        logger.warning("Checkpoint write failed for %s", checkpoint_path)


def verify_checkpoint(ledger_path: str | Path) -> bool:
    """Verify ledger integrity against the last checkpoint."""
    path = Path(ledger_path)
    checkpoint_path = path.with_suffix(".checkpoint.jsonl")

    if not checkpoint_path.exists():
        return True  # No checkpoint to verify against

    try:
        checkpoints = _read_checkpoints(checkpoint_path)
        if not checkpoints:
            return True

        last_checkpoint = checkpoints[-1]
        result = read_ledger_with_recovery(path)

        if len(result.records) < last_checkpoint.index:
            return False  # Ledger is shorter than checkpoint

        # Verify the records match
        start_idx = max(0, last_checkpoint.index - last_checkpoint.record_count)
        relevant_records = result.records[start_idx:last_checkpoint.index]
        content = json.dumps([asdict(r) for r in relevant_records], sort_keys=True)
        computed_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        return computed_hash == last_checkpoint.hash
    except Exception:
        logger.warning("Checkpoint verification failed for %s", path)
        return False


def _read_checkpoints(checkpoint_path: Path) -> list[LedgerCheckpoint]:
    """Read all checkpoints from the checkpoint file."""
    checkpoints: list[LedgerCheckpoint] = []
    try:
        with checkpoint_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    data = json.loads(stripped)
                    checkpoints.append(LedgerCheckpoint(**data))
                except (json.JSONDecodeError, TypeError):
                    continue
    except OSError:
        pass
    return checkpoints


def read_ledger(path: str | Path) -> list[LedgerRecord]:
    result = read_ledger_with_recovery(path)
    return result.records


def read_ledger_with_recovery(path: str | Path) -> LedgerReadResult:
    """Read ledger from JSON array or JSONL (for backwards compat)."""
    ledger_path = Path(path)
    str_path = str(ledger_path)
    
    if not ledger_path.exists():
        return LedgerReadResult(records=(), corrupted=(), partial=False)

    records: list[LedgerRecord] = []
    corrupted: list[CorruptedLine] = []

    try:
        content = ledger_path.read_text(encoding="utf-8").strip()
        if content.startswith("["):
            # Strict JSON array
            data = json.loads(content)
            for i, item in enumerate(data):
                try:
                    records.append(_migrate_record(item))
                except Exception as exc:
                    corrupted.append(CorruptedLine(line_number=i, raw_content=str(item), error=str(exc)))
        else:
            # JSONL backwards compat
            for line_num, line in enumerate(content.splitlines(), start=1):
                stripped = line.strip()
                if not stripped: continue
                try:
                    data = json.loads(stripped)
                    records.append(_migrate_record(data))
                except Exception as exc:
                    corrupted.append(CorruptedLine(line_number=line_num, raw_content=stripped, error=str(exc)))
    except OSError:
        logger.warning("Failed to read ledger at %s", path)
        return LedgerReadResult(records=(), corrupted=(), partial=True)
    except json.JSONDecodeError as exc:
        corrupted.append(CorruptedLine(line_number=0, raw_content="", error=str(exc)))

    if corrupted:
        _quarantine_corrupt_lines(ledger_path, corrupted)

    _L1_CACHE[str_path] = records

    # Read checkpoints
    checkpoint_path = ledger_path.with_suffix(".checkpoint.jsonl")
    checkpoints = tuple(_read_checkpoints(checkpoint_path))

    return LedgerReadResult(
        records=records,
        corrupted=tuple(corrupted),
        partial=len(corrupted) > 0,
        checkpoints=checkpoints,
    )


def _migrate_record(data: dict) -> LedgerRecord:
    """Migrate a record from any schema version to current."""
    version = data.get("version", 1)

    if version == 1:
        data["version"] = LEDGER_VERSION
    elif version == LEDGER_VERSION:
        pass
    else:
        logger.warning("Unknown ledger version %d; attempting to read as current", version)

    data["version"] = data.get("version", LEDGER_VERSION)
    return LedgerRecord(**data)


def read_ledger_filtered(path: str | Path, filter: LedgerFilter) -> list[LedgerRecord]:
    """Partial replay: read ledger with filtering."""
    result = read_ledger_with_recovery(path)
    records = result.records

    if filter.task_hash is not None:
        records = [r for r in records if r.task_hash == filter.task_hash]
    if filter.outcome is not None:
        records = [r for r in records if r.outcome == filter.outcome]
    if filter.since is not None:
        records = [r for r in records if r.recorded_at >= filter.since]
    if filter.until is not None:
        records = [r for r in records if r.recorded_at <= filter.until]

    return records


def deduplicate_ledger(path: str | Path) -> int:
    """Remove duplicate records by task_hash, keeping the most recent."""
    ledger_path = Path(path)
    result = read_ledger_with_recovery(ledger_path)
    if not result.records:
        return 0

    seen: dict[str, LedgerRecord] = {}
    for record in result.records:
        existing = seen.get(record.task_hash)
        if existing is None or record.recorded_at > existing.recorded_at:
            seen[record.task_hash] = record

    deduped = list(seen.values())
    removed = len(result.records) - len(deduped)

    if removed > 0:
        _write_ledger(ledger_path, deduped)
        _L1_CACHE[str(ledger_path)] = deduped

    return removed


def merge_quarantine(path: str | Path) -> int:
    """Attempt to repair quarantined records and merge back into ledger."""
    ledger_path = Path(path)
    quarantine_path = ledger_path.with_suffix(".corrupt.jsonl")

    if not quarantine_path.exists():
        return 0

    recovered = 0
    remaining: list[dict] = []

    try:
        with quarantine_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entry = json.loads(stripped)
                    original_content = entry.get("raw_content", "")
                    try:
                        data = json.loads(original_content)
                        if isinstance(data, dict):
                            record = _migrate_record(data)
                            append_ledger(ledger_path, record)
                            recovered += 1
                            continue
                    except (json.JSONDecodeError, ValueError, TypeError):
                        pass
                    remaining.append(entry)
                except json.JSONDecodeError:
                    remaining.append({"raw_content": stripped, "error": "unparseable"})

        if remaining:
            with quarantine_path.open("w", encoding="utf-8") as handle:
                for entry in remaining:
                    handle.write(json.dumps(entry, sort_keys=True) + "\n")
        else:
            quarantine_path.unlink(missing_ok=True)

    except OSError:
        logger.warning("Failed to merge quarantine at %s", quarantine_path)

    return recovered


def _write_ledger(path: Path, records: list[LedgerRecord]) -> None:
    """Write entire ledger atomically."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(asdict(r), sort_keys=True) + "\n" for r in records]
        content = "".join(lines)
        tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as tmp_file:
                tmp_file.write(content)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
            Path(tmp_path).replace(path)
        except OSError:
            Path(tmp_path).unlink(missing_ok=True)
            raise
    except OSError:
        logger.warning("Failed to write ledger at %s", path)


def _quarantine_corrupt_lines(ledger_path: Path, corrupted: list[CorruptedLine]) -> None:
    """Write corrupt lines to quarantine file."""
    quarantine_path = ledger_path.with_suffix(".corrupt.jsonl")
    try:
        with quarantine_path.open("a", encoding="utf-8") as handle:
            for entry in corrupted:
                quarantine_payload = json.dumps({
                    "original_file": str(ledger_path),
                    "line_number": entry.line_number,
                    "raw_content": entry.raw_content,
                    "error": entry.error,
                    "quarantined_at": datetime.now(UTC).isoformat(),
                }, sort_keys=True)
                handle.write(quarantine_payload + "\n")
    except OSError:
        logger.warning("Failed to write quarantine file %s", quarantine_path)


def append_failure(path: str | Path, record: LedgerRecord) -> None:
    if record.outcome != "failure":
        return
    append_ledger(path, record)


def rollback(path: str | Path, snapshot_count: int) -> int:
    """Rollback ledger to a prior state.

    Truncates all records added after ``snapshot_count``.
    Called by the orchestrator when InsufficientTokensError is raised
    to restore ledger state to the exact moment before the task began.

    Args:
        path: Ledger file path
        snapshot_count: Number of records that existed when the snapshot
                        was taken (before the current task started)

    Returns:
        Number of records removed
    """
    ledger_path = Path(path)
    result = read_ledger_with_recovery(ledger_path)
    current = list(result.records)

    if len(current) <= snapshot_count:
        return 0

    removed = len(current) - snapshot_count
    kept = current[:snapshot_count]
    _write_ledger(ledger_path, kept)
    _L1_CACHE[str(ledger_path)] = kept

    logger.info(
        "Ledger rollback: removed %d records (kept %d, was %d)",
        removed, snapshot_count, len(current),
    )
    return removed


def snapshot_count(path: str | Path) -> int:
    """Return the current number of records — used to take a rollback snapshot."""
    result = read_ledger_with_recovery(path)
    return len(result.records)
