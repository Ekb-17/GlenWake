"""Record that inference did not run.

No segmentation model is integrated. This module does not download weights,
load a model, read frames, or store detections, masks, or measurements.
"""

import os
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

RECORD_KEYS = ("id", "session_id", "requested_at", "status", "reason", "model_version")
UNAVAILABLE_REASON = "No segmentation model is configured."
FAILED_REASON = "Segmentation inference is not integrated, so the named model was not run."


def ensure_table(db: sqlite3.Connection) -> None:
    db.execute(
        """CREATE TABLE IF NOT EXISTS analysis_requests (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            requested_at TEXT NOT NULL,
            status TEXT NOT NULL,
            reason TEXT NOT NULL,
            model_version TEXT
        )"""
    )


def model_version_named() -> str:
    """A name in the environment is not a loaded model and is not stored."""
    return os.environ.get("GLENWAKE_MODEL_VERSION", "").strip()


def model_integrated() -> bool:
    return False


def _outcome() -> tuple[str, str]:
    if model_version_named():
        return "failed", FAILED_REASON
    return "unavailable", UNAVAILABLE_REASON


def _row_to_record(row: sqlite3.Row) -> dict:
    if row["model_version"] is not None:
        raise RuntimeError("Stored analysis must not carry a model version")
    if row["status"] not in {"unavailable", "failed"}:
        raise RuntimeError("Stored analysis must not look completed")
    record = {
        "id": row["id"],
        "session_id": row["session_id"],
        "requested_at": row["requested_at"],
        "status": row["status"],
        "reason": row["reason"],
        "model_version": None,
    }
    if tuple(record) != RECORD_KEYS:
        raise RuntimeError("Stored analysis has an unexpected field")
    return record


def record_analysis(db: sqlite3.Connection, session_id: str) -> dict:
    if model_integrated():
        raise RuntimeError("Segmentation inference is not implemented")
    ensure_table(db)
    status, reason = _outcome()
    identity = str(uuid4())
    requested_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    db.execute(
        """INSERT INTO analysis_requests
           (id, session_id, requested_at, status, reason, model_version)
           VALUES (?, ?, ?, ?, ?, NULL)""",
        (identity, session_id, requested_at, status, reason),
    )
    row = db.execute("SELECT * FROM analysis_requests WHERE id = ?", (identity,)).fetchone()
    return _row_to_record(row)


def analysis_state(db: sqlite3.Connection, session_id: str) -> dict:
    ensure_table(db)
    rows = db.execute(
        """SELECT * FROM analysis_requests
           WHERE session_id = ?
           ORDER BY requested_at DESC, rowid DESC""",
        (session_id,),
    ).fetchall()
    requests = [_row_to_record(row) for row in rows]
    return {
        "session_id": session_id,
        "model_configured": bool(model_version_named()),
        "model_integrated": model_integrated(),
        "latest": requests[0] if requests else None,
        "requests": requests,
    }
