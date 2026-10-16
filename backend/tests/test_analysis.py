"""Analysis requests stay unavailable until a model is actually integrated."""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

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
    "detection",
    "detections",
    "bbox",
    "boxes",
    "bounding_box",
    "bounding_boxes",
    "polygon",
    "polygons",
    "segment",
    "segments",
    "segmentation",
    "precision",
    "recall",
    "f1",
    "runtime",
    "runtime_seconds",
    "peak_ram",
    "peak_memory",
    "label",
    "labels",
    "class",
    "classes",
    "completed",
    "complete",
}
STORED_TEXT_MARKERS = ("mask", "detection", "confidence", "coverage", "bbox", "percent")
RECORD_KEYS = {"id", "session_id", "requested_at", "status", "reason", "model_version"}


def keys_of(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from keys_of(child)
    elif isinstance(value, list):
        for child in value:
            yield from keys_of(child)


class AnalysisUnavailableTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        os.environ["GLENWAKE_DATA_DIR"] = self.directory.name
        os.environ.pop("GLENWAKE_MODEL_VERSION", None)
        from app import analysis, main

        self.analysis = analysis
        self.main = main
        self.previous = main.DATA_DIR, main.VIDEO_DIR, main.DB_PATH
        main.DATA_DIR = Path(self.directory.name)
        main.VIDEO_DIR = main.DATA_DIR / "videos"
        main.DB_PATH = main.DATA_DIR / "glenwake.sqlite3"
        self.client = TestClient(main.app)

    def tearDown(self):
        self.main.DATA_DIR, self.main.VIDEO_DIR, self.main.DB_PATH = self.previous
        os.environ.pop("GLENWAKE_DATA_DIR", None)
        os.environ.pop("GLENWAKE_MODEL_VERSION", None)
        self.directory.cleanup()

    def upload(self, name="scene.mp4", content=b"sample-video"):
        created = self.client.post("/api/sessions", files={"video": (name, content, "video/mp4")})
        self.assertEqual(created.status_code, 201, created.text)
        return created.json()

    def review_body(self):
        return {
            "region": {"x": 0.1, "y": 0.2, "width": 0.5, "height": 0.6},
            "start_seconds": 5,
            "end_seconds": 14,
            "notes": "The view was blocked briefly.",
            "annotations": [
                {
                    "id": "event-1",
                    "seconds": 8,
                    "kind": "visibility_gap",
                    "note": "Van crosses frame",
                    "source": "manual",
                }
            ],
        }

    def analysis_rows(self):
        with sqlite3.connect(self.main.DB_PATH) as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute("SELECT * FROM analysis_requests ORDER BY rowid")]

    def assert_no_detection_payload(self, payload):
        self.assertTrue(set(keys_of(payload)).isdisjoint(FORBIDDEN_KEYS))
        self.assertNotIn("detections", payload)
        self.assertNotIn("masks", payload)
        self.assertNotIn("coverage", payload)

    def test_no_model_configured_returns_unavailable(self):
        session = self.upload()
        self.assertFalse(self.analysis.model_version_named())
        self.assertFalse(self.analysis.model_integrated())

        recorded = self.client.post(f"/api/sessions/{session['id']}/analysis")
        self.assertEqual(recorded.status_code, 200, recorded.text)
        body = recorded.json()
        self.assertEqual(set(body), RECORD_KEYS)
        self.assertEqual(body["session_id"], session["id"])
        self.assertEqual(body["status"], "unavailable")
        self.assertEqual(body["reason"], "No segmentation model is configured.")
        self.assertIsNone(body["model_version"])
        self.assertRegex(body["requested_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

        state = self.client.get(f"/api/sessions/{session['id']}/analysis")
        self.assertEqual(state.status_code, 200, state.text)
        listed = state.json()
        self.assertFalse(listed["model_configured"])
        self.assertFalse(listed["model_integrated"])
        self.assertEqual(listed["latest"], body)
        self.assertEqual(listed["requests"], [body])

    def test_nothing_stored_looks_like_a_detection(self):
        session = self.upload()
        recorded = self.client.post(f"/api/sessions/{session['id']}/analysis")
        self.assertEqual(recorded.status_code, 200, recorded.text)
        self.assert_no_detection_payload(recorded.json())
        self.assert_no_detection_payload(self.client.get(f"/api/sessions/{session['id']}/analysis").json())

        rows = self.analysis_rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(set(row), {"id", "session_id", "requested_at", "status", "reason", "model_version"})
        self.assertEqual(row["status"], "unavailable")
        self.assertIsNone(row["model_version"])
        stored_text = " ".join("" if value is None else str(value).lower() for value in row.values())
        for marker in STORED_TEXT_MARKERS:
            self.assertNotIn(marker, stored_text)
        self.assertNotIn(b"detection", self.main.DB_PATH.read_bytes().lower())

        files = [path for path in Path(self.directory.name).rglob("*") if path.is_file()]
        videos = [path for path in files if path.suffix.lower() in {".mp4", ".webm", ".mov"}]
        self.assertEqual(videos, [self.main.VIDEO_DIR / f"{session['id']}.mp4"])
        self.assertEqual(sorted(path.name for path in files), [f"{session['id']}.mp4", "glenwake.sqlite3"])

    def test_failed_run_does_not_change_the_manual_review(self):
        session = self.upload()
        identity = session["id"]
        review = self.review_body()
        saved = self.client.put(f"/api/sessions/{identity}/review", json=review)
        self.assertEqual(saved.status_code, 200, saved.text)
        with sqlite3.connect(self.main.DB_PATH) as db:
            review_before = db.execute("SELECT review FROM sessions WHERE id = ?", (identity,)).fetchone()[0]
        video_before = (self.main.VIDEO_DIR / f"{identity}.mp4").read_bytes()

        os.environ["GLENWAKE_MODEL_VERSION"] = "named-but-not-loaded"
        failed = self.client.post(f"/api/sessions/{identity}/analysis")
        self.assertEqual(failed.status_code, 200, failed.text)
        body = failed.json()
        self.assertEqual(body["status"], "failed")
        self.assertEqual(body["reason"], "Segmentation inference is not integrated, so the named model was not run.")
        self.assertIsNone(body["model_version"])
        self.assertNotIn("named-but-not-loaded", failed.text)
        self.assert_no_detection_payload(body)

        reopened = self.client.get(f"/api/sessions/{identity}")
        self.assertEqual(reopened.status_code, 200, reopened.text)
        self.assertEqual(reopened.json()["review"], review)
        self.assertEqual(self.client.get("/api/sessions").json()[0]["review"], review)
        with sqlite3.connect(self.main.DB_PATH) as db:
            review_after = db.execute("SELECT review FROM sessions WHERE id = ?", (identity,)).fetchone()[0]
        self.assertEqual(review_after, review_before)
        self.assertEqual((self.main.VIDEO_DIR / f"{identity}.mp4").read_bytes(), video_before)
        self.assertNotIn(b"named-but-not-loaded", self.main.DB_PATH.read_bytes())
        state = self.client.get(f"/api/sessions/{identity}/analysis").json()
        self.assertTrue(state["model_configured"])
        self.assertFalse(state["model_integrated"])
        self.assertEqual(state["latest"]["status"], "failed")
        self.assertIsNone(state["latest"]["model_version"])

    def test_missing_session_does_not_store_an_analysis(self):
        missing = self.client.post("/api/sessions/missing-session/analysis")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(self.client.get("/api/sessions/missing-session/analysis").status_code, 404)
        self.assertEqual(self.analysis_rows(), [])


if __name__ == "__main__":
    unittest.main()
