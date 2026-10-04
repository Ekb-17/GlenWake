"""Register one local evaluation recording. This module does not analyze video."""

import hashlib
import json
import sqlite3
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

CATALOG_PATH = Path(__file__).resolve().parents[2] / "docs" / "evaluation" / "scenario-catalog.json"
EXTRA_REQUIRED = ("registration_kind",)
OPTIONAL_FIELDS = {"derived_from_clip_id"}
ITEM_FIELDS = {"item_id", "human_label", "notes", "visible_from_seconds", "visible_to_seconds"}
FORBIDDEN_KEYS = {
    "confidence",
    "accuracy",
    "percent",
    "percentage",
    "score",
    "probability",
    "coverage",
    "coverage_percent",
    "mask",
    "masks",
    "precision",
    "recall",
    "f1",
    "runtime",
    "runtime_seconds",
    "peak_ram",
    "peak_memory",
}
ID_PATTERN_MAX = 80


def load_catalog():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def originals_dir(data_dir: Path) -> Path:
    return data_dir / "evaluation" / "originals"


def _identifier(value, label):
    if not isinstance(value, str):
        raise HTTPException(422, f"{label} must be text")
    text = value.strip()
    if not text or len(text) > ID_PATTERN_MAX:
        raise HTTPException(422, f"{label} is missing")
    if not text[0].isalnum() or any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-" for character in text):
        raise HTTPException(422, f"{label} must use letters, numbers, hyphens, or underscores")
    return text


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HTTPException(422, f"{label} must be a number of seconds")
    if value < 0:
        raise HTTPException(422, f"{label} cannot be negative")
    return float(value)


def _reject_forbidden(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in FORBIDDEN_KEYS:
                raise HTTPException(422, "Intake does not accept model output or measurements")
            _reject_forbidden(child)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden(child)


def _validate_items(scenario_type, items):
    if not isinstance(items, list):
        raise HTTPException(422, "item_histories must be a list")
    if len(items) > 50:
        raise HTTPException(422, "item_histories is too long")
    if scenario_type != "negative_control" and len(items) < 1:
        raise HTTPException(422, "This scenario needs at least one item history")
    cleaned = []
    for item in items:
        if not isinstance(item, dict):
            raise HTTPException(422, "Each item history must be an object")
        unknown = set(item) - ITEM_FIELDS
        if unknown:
            raise HTTPException(422, "Item history has an unsupported field")
        _reject_forbidden(item)
        item_id = _identifier(item.get("item_id"), "item_id")
        label = item.get("human_label")
        if not isinstance(label, str) or not label.strip():
            raise HTTPException(422, "item history human_label is missing")
        if len(label.strip()) > 200:
            raise HTTPException(422, "item history human_label is too long")
        entry = {"item_id": item_id, "human_label": label.strip()}
        if "notes" in item:
            notes = item["notes"]
            if not isinstance(notes, str) or len(notes) > 1000:
                raise HTTPException(422, "item history notes must be text")
            entry["notes"] = notes
        start = item.get("visible_from_seconds")
        end = item.get("visible_to_seconds")
        if start is not None or end is not None:
            entry["visible_from_seconds"] = _number(start, "visible_from_seconds")
            entry["visible_to_seconds"] = _number(end, "visible_to_seconds")
            if entry["visible_to_seconds"] <= entry["visible_from_seconds"]:
                raise HTTPException(422, "Item visibility end must be after its start")
        cleaned.append(entry)
    return cleaned


def _validate_record(record, catalog):
    if not isinstance(record, dict):
        raise HTTPException(422, "Evaluation record must be a JSON object")
    _reject_forbidden(record)
    allowed = set(catalog["required_record_fields"]) | set(EXTRA_REQUIRED) | OPTIONAL_FIELDS
    unknown = set(record) - allowed
    if unknown:
        raise HTTPException(422, "Evaluation record has an unsupported field")
    missing = [field for field in (*catalog["required_record_fields"], *EXTRA_REQUIRED) if field not in record or record[field] in (None, "")]
    if missing:
        raise HTTPException(422, "Missing evaluation record fields: " + ", ".join(missing))

    scenario_ids = {item["id"] for item in catalog["scenarios"]}
    scenario_type = record["scenario_type"]
    if scenario_type not in scenario_ids:
        raise HTTPException(422, "Unknown scenario type")
    partition = record["partition"]
    if partition not in catalog["pilot"]["partitions"]:
        raise HTTPException(422, "Unknown partition")
    if record["label_source"] != catalog["label_source"]:
        raise HTTPException(422, "Label source must be a human staging label")
    if record["registration_kind"] not in {"fixture", "pilot"}:
        raise HTTPException(422, "registration_kind must be fixture or pilot")
    if record["daylight_confirmed"] is not True or record["stationary_camera_confirmed"] is not True:
        raise HTTPException(422, "Pilot intake only accepts clips confirmed as daylight from a stationary camera")
    if not isinstance(record["frames_comparable"], bool):
        raise HTTPException(422, "frames_comparable must be true or false")
    take = record["take"]
    if type(take) is not int or take < 1 or take > catalog["pilot"]["takes_per_type_per_location"]:
        raise HTTPException(422, "Take must be 1 or 2")
    limitations = record["limitations"]
    if not isinstance(limitations, str) or not limitations.strip() or len(limitations) > 5000:
        raise HTTPException(422, "limitations is missing")
    start = _number(record["cleanup_start_seconds"], "cleanup_start_seconds")
    end = _number(record["cleanup_end_seconds"], "cleanup_end_seconds")
    if end <= start:
        raise HTTPException(422, "Cleanup end must be after its start")
    from app.main import Region

    try:
        region = Region.model_validate(record["monitoring_region"]).model_dump()
    except Exception as error:
        message = "Monitoring region must stay inside the frame"
        if hasattr(error, "errors"):
            message = "Monitoring region is invalid"
        raise HTTPException(422, message) from error
    derived = record.get("derived_from_clip_id")
    if derived is not None:
        derived = _identifier(derived, "derived_from_clip_id")
    return {
        "clip_id": _identifier(record["clip_id"], "clip_id"),
        "scenario_type": scenario_type,
        "location_id": _identifier(record["location_id"], "location_id"),
        "partition": partition,
        "take": take,
        "daylight_confirmed": True,
        "stationary_camera_confirmed": True,
        "monitoring_region": region,
        "cleanup_start_seconds": start,
        "cleanup_end_seconds": end,
        "item_histories": _validate_items(scenario_type, record["item_histories"]),
        "frames_comparable": record["frames_comparable"],
        "label_source": catalog["label_source"],
        "limitations": limitations.strip(),
        "registration_kind": record["registration_kind"],
        "derived_from_clip_id": derived,
    }


def ensure_tables(db):
    db.execute("""CREATE TABLE IF NOT EXISTS evaluation_locations (
        location_id TEXT PRIMARY KEY,
        partition TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS evaluation_clips (
        clip_id TEXT PRIMARY KEY,
        scenario_type TEXT NOT NULL,
        location_id TEXT NOT NULL,
        partition TEXT NOT NULL,
        take INTEGER NOT NULL,
        daylight_confirmed INTEGER NOT NULL,
        stationary_camera_confirmed INTEGER NOT NULL,
        monitoring_region TEXT NOT NULL,
        cleanup_start_seconds REAL NOT NULL,
        cleanup_end_seconds REAL NOT NULL,
        item_histories TEXT NOT NULL,
        frames_comparable INTEGER NOT NULL,
        label_source TEXT NOT NULL,
        limitations TEXT NOT NULL,
        registration_kind TEXT NOT NULL,
        derived_from_clip_id TEXT,
        stored_name TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        UNIQUE (location_id, scenario_type, take)
    )""")


def _connect(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(db_path, isolation_level=None)
    db.row_factory = sqlite3.Row
    ensure_tables(db)
    return db


def _clip_from_row(row):
    return {
        "clip_id": row["clip_id"],
        "scenario_type": row["scenario_type"],
        "location_id": row["location_id"],
        "partition": row["partition"],
        "take": row["take"],
        "daylight_confirmed": bool(row["daylight_confirmed"]),
        "stationary_camera_confirmed": bool(row["stationary_camera_confirmed"]),
        "monitoring_region": json.loads(row["monitoring_region"]),
        "cleanup_start_seconds": row["cleanup_start_seconds"],
        "cleanup_end_seconds": row["cleanup_end_seconds"],
        "item_histories": json.loads(row["item_histories"]),
        "frames_comparable": bool(row["frames_comparable"]),
        "label_source": row["label_source"],
        "limitations": row["limitations"],
        "registration_kind": row["registration_kind"],
        "derived_from_clip_id": row["derived_from_clip_id"],
        "sha256": row["sha256"],
        "original_url": f'/api/evaluation/clips/{row["clip_id"]}/original',
        "counts_toward_collected_pilot": row["registration_kind"] == "pilot" and row["derived_from_clip_id"] is None,
        "analysis": "not_run",
    }


def _counts(db):
    pilot = db.execute(
        "SELECT COUNT(*) FROM evaluation_clips WHERE registration_kind = 'pilot' AND derived_from_clip_id IS NULL"
    ).fetchone()[0]
    fixtures = db.execute(
        "SELECT COUNT(*) FROM evaluation_clips WHERE registration_kind = 'fixture' AND derived_from_clip_id IS NULL"
    ).fetchone()[0]
    return int(pilot), int(fixtures)


def evaluation_status(db_path: Path):
    catalog = load_catalog()
    pilot_count = fixture_count = 0
    if db_path.is_file():
        with _connect(db_path) as db:
            pilot_count, fixture_count = _counts(db)
    return {
        "catalog_status": catalog["catalog_status"],
        "catalog_collected_clip_count": catalog["pilot"]["collected_clip_count"],
        "planned_clip_count": catalog["pilot"]["planned_clip_count"],
        "collected_pilot_clip_count": pilot_count,
        "fixture_clip_count": fixture_count,
        "model_integrated": False,
        "analysis": "not_run",
    }


def list_clips(db_path: Path):
    if not db_path.is_file():
        return []
    with _connect(db_path) as db:
        rows = db.execute("SELECT * FROM evaluation_clips ORDER BY clip_id").fetchall()
    return [_clip_from_row(row) for row in rows]


def original_file(data_dir: Path, db_path: Path, clip_id: str):
    if not db_path.is_file():
        raise HTTPException(404, "Evaluation clip not found")
    with _connect(db_path) as db:
        row = db.execute("SELECT stored_name FROM evaluation_clips WHERE clip_id = ?", (clip_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Evaluation clip not found")
    path = originals_dir(data_dir) / row["stored_name"]
    if not path.is_file():
        raise HTTPException(404, "Original recording file missing")
    return path


def register_clip(data_dir: Path, db_path: Path, record: dict, upload: tuple[str, bytes] | None):
    catalog = load_catalog()
    cleaned = _validate_record(record, catalog)
    created_path = None
    committed = False
    try:
        with _connect(db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                if db.execute("SELECT 1 FROM evaluation_clips WHERE clip_id = ?", (cleaned["clip_id"],)).fetchone():
                    raise HTTPException(409, "Evaluation clip id already exists")
                parent = None
                if cleaned["derived_from_clip_id"]:
                    parent = db.execute(
                        "SELECT * FROM evaluation_clips WHERE clip_id = ?",
                        (cleaned["derived_from_clip_id"],),
                    ).fetchone()
                    if parent is None:
                        raise HTTPException(404, "Derived recording was not found")
                    if cleaned["partition"] != parent["partition"] or cleaned["location_id"] != parent["location_id"]:
                        raise HTTPException(422, "A recording and its derivatives must stay in one location partition")
                    if cleaned["registration_kind"] != parent["registration_kind"]:
                        raise HTTPException(422, "A derivative keeps the registration kind of its original recording")
                elif upload is None:
                    raise HTTPException(422, "Original recording is required")

                locked = db.execute(
                    "SELECT partition FROM evaluation_locations WHERE location_id = ?",
                    (cleaned["location_id"],),
                ).fetchone()
                if locked is not None and locked["partition"] != cleaned["partition"]:
                    raise HTTPException(409, "That location is already registered in another partition")

                slot = db.execute(
                    "SELECT clip_id FROM evaluation_clips WHERE location_id = ? AND scenario_type = ? AND take = ?",
                    (cleaned["location_id"], cleaned["scenario_type"], cleaned["take"]),
                ).fetchone()
                if slot is not None:
                    raise HTTPException(409, "That location already has this scenario take")

                if upload is not None:
                    filename, payload = upload
                    suffix = Path(filename).suffix.lower()
                    digest = hashlib.sha256(payload).hexdigest()
                    clashes = db.execute(
                        "SELECT clip_id, partition, location_id FROM evaluation_clips WHERE sha256 = ?",
                        (digest,),
                    ).fetchall()
                    for clash in clashes:
                        if clash["partition"] != cleaned["partition"] or clash["location_id"] != cleaned["location_id"]:
                            raise HTTPException(409, "This recording or a derivative is already in another partition")
                        if parent is None:
                            raise HTTPException(409, "This recording is already registered")
                    stored_name = uuid4().hex + suffix
                    destination = originals_dir(data_dir) / stored_name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(payload)
                    created_path = destination
                else:
                    stored_name = parent["stored_name"]
                    digest = parent["sha256"]

                if locked is None:
                    db.execute(
                        "INSERT INTO evaluation_locations (location_id, partition) VALUES (?, ?)",
                        (cleaned["location_id"], cleaned["partition"]),
                    )
                db.execute(
                    """INSERT INTO evaluation_clips (
                        clip_id, scenario_type, location_id, partition, take,
                        daylight_confirmed, stationary_camera_confirmed, monitoring_region,
                        cleanup_start_seconds, cleanup_end_seconds, item_histories, frames_comparable,
                        label_source, limitations, registration_kind, derived_from_clip_id, stored_name, sha256
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        cleaned["clip_id"], cleaned["scenario_type"], cleaned["location_id"], cleaned["partition"], cleaned["take"],
                        1, 1, json.dumps(cleaned["monitoring_region"]),
                        cleaned["cleanup_start_seconds"], cleaned["cleanup_end_seconds"], json.dumps(cleaned["item_histories"]),
                        int(cleaned["frames_comparable"]), cleaned["label_source"], cleaned["limitations"],
                        cleaned["registration_kind"], cleaned["derived_from_clip_id"], stored_name, digest,
                    ),
                )
                row = db.execute("SELECT * FROM evaluation_clips WHERE clip_id = ?", (cleaned["clip_id"],)).fetchone()
                saved = _clip_from_row(row)
                db.execute("COMMIT")
                committed = True
            except Exception:
                db.execute("ROLLBACK")
                raise
        return saved
    except Exception:
        if created_path is not None and not committed:
            created_path.unlink(missing_ok=True)
        raise
