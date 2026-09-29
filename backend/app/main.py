"""GlenWake's local, manual video review API."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator

DATA_DIR = Path(os.environ.get("GLENWAKE_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
VIDEO_DIR = DATA_DIR / "videos"
DB_PATH = DATA_DIR / "glenwake.sqlite3"
MAX_UPLOAD = 200 * 1024 * 1024
ALLOWED = {".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime"}


class Region(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def within_frame(self):
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError("Region must remain inside the video frame")
        return self


class Annotation(BaseModel):
    id: str = Field(max_length=80)
    seconds: float = Field(ge=0)
    kind: str = Field(pattern="^(observation|arrival|movement|removal|visibility_gap)$")
    note: str = Field(min_length=1, max_length=1000)
    source: str = "manual"

    @model_validator(mode="after")
    def manual_only(self):
        if self.source != "manual":
            raise ValueError("Only manual annotations are supported")
        return self


class Review(BaseModel):
    region: Region | None = None
    start_seconds: float | None = Field(default=None, ge=0)
    end_seconds: float | None = Field(default=None, ge=0)
    notes: str = Field(default="", max_length=5000)
    annotations: list[Annotation] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def ordered(self):
        if self.start_seconds is not None and self.end_seconds is not None and self.end_seconds <= self.start_seconds:
            raise ValueError("Cleanup end must be after its start")
        ids = [item.id for item in self.annotations]
        if len(ids) != len(set(ids)):
            raise ValueError("Annotation IDs must be unique")
        return self


def init_db():
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, filename TEXT NOT NULL, stored_name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            review TEXT NOT NULL DEFAULT '{}'
        )""")


@contextmanager
def connection():
    init_db()
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        yield db


def session(row):
    return {
        "id": row["id"], "filename": row["filename"],
        "created_at": row["created_at"], "review": Review.model_validate_json(row["review"]).model_dump(),
        "video_url": f'/api/sessions/{row["id"]}/video',
    }


app = FastAPI(title="GlenWake local review")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type"],
)


@app.get("/api/sessions")
def list_sessions():
    with connection() as db:
        return [session(row) for row in db.execute("SELECT * FROM sessions ORDER BY created_at DESC, id DESC")]


@app.post("/api/sessions", status_code=201)
async def upload_session(video: UploadFile = File(...)):
    filename = Path(video.filename or "").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(415, "Use an MP4, WebM or MOV video")
    identity = str(uuid4())
    stored_name = identity + suffix
    init_db()
    path = VIDEO_DIR / stored_name
    size = 0
    try:
        with path.open("wb") as output:
            while chunk := await video.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise HTTPException(413, "Video exceeds the 200 MB local upload limit")
                output.write(chunk)
        if size == 0:
            raise HTTPException(400, "Video is empty")
        with connection() as db:
            db.execute(
                "INSERT INTO sessions (id, filename, stored_name, review) VALUES (?, ?, ?, ?)",
                (identity, filename, stored_name, Review().model_dump_json()),
            )
            db.commit()
            row = db.execute("SELECT * FROM sessions WHERE id = ?", (identity,)).fetchone()
        return session(row)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await video.close()


def get_row(db, identity):
    row = db.execute("SELECT * FROM sessions WHERE id = ?", (identity,)).fetchone()
    if row is None:
        raise HTTPException(404, "Session not found")
    return row


@app.get("/api/sessions/{identity}")
def get_session(identity: str):
    with connection() as db:
        return session(get_row(db, identity))


@app.put("/api/sessions/{identity}/review")
def save_review(identity: str, review: Review):
    with connection() as db:
        get_row(db, identity)
        db.execute("UPDATE sessions SET review = ? WHERE id = ?", (review.model_dump_json(), identity))
        db.commit()
        return session(get_row(db, identity))


@app.get("/api/sessions/{identity}/video")
def get_video(identity: str):
    with connection() as db:
        row = get_row(db, identity)
    path = VIDEO_DIR / row["stored_name"]
    if not path.is_file():
        raise HTTPException(404, "Video file missing")
    return FileResponse(path, media_type=ALLOWED[Path(path).suffix], filename=row["filename"], content_disposition_type="inline")
