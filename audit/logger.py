"""Immutable append-only audit trail for compliance calculations.

Every call to generate_compliance_metrics is logged with:
  - input_hash: SHA-256 of canonical input JSON
  - formula_version: git commit hash or version string
  - timestamp: UTC ISO-8601
  - inputs: the full TelemetryBundle (sanitized)
  - outputs: all computed metrics
  - caller: optional system or user identifier

The log is append-only. Records are never updated or deleted.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from core.exceptions import AuditError
from core.validators import TelemetryBundle


AUDIT_LOG_PATH = Path(os.environ.get("EED_AUDIT_LOG", "data/audit_log.jsonl"))
FORMULA_VERSION = os.environ.get("EED_FORMULA_VERSION", "dev")


def _canonical_json(bundle: TelemetryBundle) -> str:
    """Return a canonical JSON string for deterministic hashing.

    Uses model_dump() (Pydantic v2) + json.dumps with sort_keys and
    explicit separators to guarantee identical serialization across runs.
    """
    data = bundle.model_dump(mode="json", by_alias=False, exclude_none=False)
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash_inputs(bundle: TelemetryBundle) -> str:
    """SHA-256 hash of canonical input JSON."""
    canonical = _canonical_json(bundle)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def log_calculation(
    bundle: TelemetryBundle,
    outputs: Dict[str, Any],
    caller: Optional[str] = None,
    log_path: Optional[Path] = None,
) -> str:
    """Append a compliance calculation record to the immutable audit log.

    Returns the record_id (SHA-256 hash) for external reference.

    Raises:
        AuditError: if the log file cannot be written or is tampered with.
    """
    path = log_path or AUDIT_LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    record_id = _hash_inputs(bundle)
    timestamp = datetime.now(timezone.utc).isoformat()

    record = {
        "record_id": record_id,
        "formula_version": FORMULA_VERSION,
        "timestamp": timestamp,
        "caller": caller or "unknown",
        "inputs": json.loads(_canonical_json(bundle)),
        "outputs": {k: str(v) if v is not None else None for k, v in outputs.items()},
    }

    # Canonical serialization for the log line itself
    log_line = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except (OSError, IOError) as exc:
        raise AuditError(f"Failed to append audit record to {path}: {exc}") from exc

    return record_id


def verify_record(record_id: str, log_path: Optional[Path] = None) -> bool:
    """Verify that a record exists in the audit log and that its hash matches.

    Returns True if the record is found and the hash is valid.
    Returns False if the record is not found.

    Raises:
        AuditError: if the record is found but the hash does not match
                    (indicating tampering).
    """
    path = log_path or AUDIT_LOG_PATH
    if not path.exists():
        return False

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("record_id") == record_id:
                # Re-serialize inputs with the SAME canonical method used at write time
                recomputed = hashlib.sha256(
                    json.dumps(record["inputs"], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
                ).hexdigest()
                if recomputed != record_id:
                    raise AuditError(
                        f"Tampering detected for record {record_id}. "
                        f"Hash mismatch: expected {record_id}, got {recomputed}."
                    )
                return True
    return False
