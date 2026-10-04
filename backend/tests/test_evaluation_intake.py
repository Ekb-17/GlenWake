"""Accept and reject local evaluation registrations without counting fixtures as pilot clips."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "docs" / "evaluation" / "scenario-catalog.json"
FORBIDDEN_RESPONSE_KEYS = {
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


def record(**overrides):
    base = {
        "clip_id": "clip-leftover-1",
        "scenario_type": "leftover",
        "location_id": "north-lawn",
        "partition": "development",
        "take": 1,
        "daylight_confirmed": True,
        "stationary_camera_confirmed": True,
        "monitoring_region": {"x": 0.1, "y": 0.2, "width": 0.5, "height": 0.4},
        "cleanup_start_seconds": 2,
        "cleanup_end_seconds": 9,
        "item_histories": [{"item_id": "bag", "human_label": "stayed in place"}],
        "frames_comparable": True,
        "label_source": "human_staging_label",
        "limitations": "Staging label only. No model has looked at this file.",
        "registration_kind": "fixture",
    }
    base.update(overrides)
    return base


def keys_of(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from keys_of(child)
    elif isinstance(value, list):
        for child in value:
            yield from keys_of(child)


class EvaluationIntakeTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        os.environ["GLENWAKE_DATA_DIR"] = self.directory.name
        from app import main

        self.main = main
        self.previous = main.DATA_DIR, main.VIDEO_DIR, main.DB_PATH
        main.DATA_DIR = Path(self.directory.name)
        main.VIDEO_DIR = main.DATA_DIR / "videos"
        main.DB_PATH = main.DATA_DIR / "glenwake.sqlite3"
        self.client = TestClient(main.app)

    def tearDown(self):
        self.main.DATA_DIR, self.main.VIDEO_DIR, self.main.DB_PATH = self.previous
        os.environ.pop("GLENWAKE_DATA_DIR", None)
        self.directory.cleanup()

    def post_clip(self, body, content=b"evaluation-sample", name="scene.mp4"):
        return self.client.post(
            "/api/evaluation/clips",
            data={"record": json.dumps(body)},
            files={"video": (name, content, "video/mp4")},
        )

    def test_fixture_registration_preserves_original_and_is_not_collected(self):
        payload = b"original-bytes-not-a-pilot-clip"
        created = self.post_clip(record(), payload)
        self.assertEqual(created.status_code, 201, created.text)
        saved = created.json()
        self.assertEqual(saved["scenario_type"], "leftover")
        self.assertEqual(saved["partition"], "development")
        self.assertEqual(saved["take"], 1)
        self.assertFalse(saved["counts_toward_collected_pilot"])
        self.assertEqual(saved["analysis"], "not_run")
        self.assertTrue(set(keys_of(saved)).isdisjoint(FORBIDDEN_RESPONSE_KEYS))
        original = self.client.get(saved["original_url"])
        self.assertEqual(original.status_code, 200)
        self.assertEqual(original.content, payload)
        status = self.client.get("/api/evaluation/status").json()
        self.assertEqual(status["collected_pilot_clip_count"], 0)
        self.assertEqual(status["fixture_clip_count"], 1)
        self.assertEqual(status["catalog_collected_clip_count"], 0)
        self.assertFalse(status["model_integrated"])
        self.assertEqual(status["analysis"], "not_run")
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(catalog["pilot"]["collected_clip_count"], 0)

    def test_rejects_unknown_scenario_and_missing_fields(self):
        unknown = self.post_clip(record(clip_id="clip-unknown", scenario_type="not-a-scenario"))
        self.assertEqual(unknown.status_code, 422)
        self.assertIn("Unknown scenario type", unknown.json()["detail"])
        incomplete = record(clip_id="clip-incomplete")
        del incomplete["limitations"]
        del incomplete["item_histories"]
        missing = self.post_clip(incomplete)
        self.assertEqual(missing.status_code, 422)
        self.assertIn("limitations", missing.json()["detail"])
        self.assertIn("item_histories", missing.json()["detail"])
        self.assertEqual(self.client.get("/api/evaluation/status").json()["collected_pilot_clip_count"], 0)
        self.assertEqual(self.client.get("/api/evaluation/status").json()["fixture_clip_count"], 0)

    def test_rejects_a_second_partition_for_one_location(self):
        first = self.post_clip(record())
        self.assertEqual(first.status_code, 201, first.text)
        second = self.post_clip(
            record(clip_id="clip-moved-1", scenario_type="moved", partition="tuning", take=1),
            b"other-bytes",
        )
        self.assertEqual(second.status_code, 409)
        self.assertIn("another partition", second.json()["detail"])
        listed = self.client.get("/api/evaluation/clips").json()
        self.assertEqual([item["clip_id"] for item in listed], ["clip-leftover-1"])
        self.assertEqual(self.client.get("/api/evaluation/status").json()["collected_pilot_clip_count"], 0)

    def test_rejects_a_derivative_or_same_file_in_another_partition(self):
        payload = b"same-recording-bytes"
        created = self.post_clip(record(), payload)
        self.assertEqual(created.status_code, 201, created.text)
        derivative = self.client.post(
            "/api/evaluation/clips",
            data={"record": json.dumps(record(
                clip_id="clip-derivative",
                scenario_type="moved",
                partition="testing",
                derived_from_clip_id="clip-leftover-1",
            ))},
        )
        self.assertEqual(derivative.status_code, 422)
        self.assertIn("one location partition", derivative.json()["detail"])
        same_file = self.post_clip(
            record(clip_id="clip-copy", scenario_type="moved", location_id="south-gate", partition="testing"),
            payload,
        )
        self.assertEqual(same_file.status_code, 409)
        self.assertIn("another partition", same_file.json()["detail"])
        kept = self.client.post(
            "/api/evaluation/clips",
            data={"record": json.dumps(record(
                clip_id="clip-same-partition",
                scenario_type="moved",
                derived_from_clip_id="clip-leftover-1",
            ))},
        )
        self.assertEqual(kept.status_code, 201, kept.text)
        self.assertEqual(self.client.get(kept.json()["original_url"]).content, payload)
        self.assertFalse(kept.json()["counts_toward_collected_pilot"])
        status = self.client.get("/api/evaluation/status").json()
        self.assertEqual(status["collected_pilot_clip_count"], 0)
        self.assertEqual(status["fixture_clip_count"], 1)

    def test_local_pilot_count_does_not_change_the_catalog(self):
        pilot = self.post_clip(record(clip_id="local-pilot", location_id="east-path", partition="tuning", registration_kind="pilot"), b"local-only")
        self.assertEqual(pilot.status_code, 201, pilot.text)
        self.assertTrue(pilot.json()["counts_toward_collected_pilot"])
        self.assertEqual(pilot.json()["analysis"], "not_run")
        status = self.client.get("/api/evaluation/status").json()
        self.assertEqual(status["collected_pilot_clip_count"], 1)
        self.assertEqual(status["catalog_collected_clip_count"], 0)
        self.assertEqual(json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["pilot"]["collected_clip_count"], 0)
        stored = list((Path(self.directory.name) / "evaluation" / "originals").iterdir())
        self.assertEqual(len(stored), 1)
        self.assertTrue(stored[0].is_file())
        self.assertEqual(stored[0].read_bytes(), b"local-only")

    def test_manual_review_still_saves_beside_intake(self):
        review = self.client.post("/api/sessions", files={"video": ("scene.mp4", b"review-video", "video/mp4")})
        self.assertEqual(review.status_code, 201)
        intake = self.post_clip(record(), b"intake-video")
        self.assertEqual(intake.status_code, 201, intake.text)
        self.assertEqual(self.client.get(f"/api/sessions/{review.json()['id']}/video").content, b"review-video")
        self.assertEqual(self.client.get("/api/evaluation/status").json()["collected_pilot_clip_count"], 0)
