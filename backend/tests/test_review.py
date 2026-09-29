"""Exercise the local upload, save and reopen workflow."""

import os
import tempfile
import unittest

from fastapi.testclient import TestClient


class ReviewWorkflowTest(unittest.TestCase):
    def test_upload_save_reopen_and_video(self):
        with tempfile.TemporaryDirectory() as directory:
            os.environ["GLENWAKE_DATA_DIR"] = directory
            # Import after setting the data path so tests cannot touch a user's sessions.
            from app import main

            previous = main.DATA_DIR, main.VIDEO_DIR, main.DB_PATH
            main.DATA_DIR = main.Path(directory)
            main.VIDEO_DIR = main.DATA_DIR / "videos"
            main.DB_PATH = main.DATA_DIR / "glenwake.sqlite3"
            try:
                client = TestClient(main.app)
                created = client.post("/api/sessions", files={"video": ("scene.mp4", b"sample-video", "video/mp4")})
                self.assertEqual(created.status_code, 201)
                identity = created.json()["id"]
                review = {
                    "region": {"x": 0.1, "y": 0.2, "width": 0.5, "height": 0.6},
                    "start_seconds": 5,
                    "end_seconds": 14,
                    "notes": "The view was blocked briefly.",
                    "annotations": [{"id": "event-1", "seconds": 8, "kind": "visibility_gap", "note": "Van crosses frame", "source": "manual"}],
                }
                saved = client.put(f"/api/sessions/{identity}/review", json=review)
                self.assertEqual(saved.status_code, 200)
                self.assertEqual(client.get(f"/api/sessions/{identity}").json()["review"], review)
                self.assertEqual(client.get("/api/sessions").json()[0]["review"], review)
                self.assertEqual(client.get(f"/api/sessions/{identity}/video").content, b"sample-video")
                self.assertEqual(client.get(f"/api/sessions/{identity}/video", headers={"Range": "bytes=0-5"}).status_code, 206)
                self.assertEqual(client.put(f"/api/sessions/{identity}/review", json={**review, "end_seconds": 4}).status_code, 422)
                self.assertEqual(client.post("/api/sessions", files={"video": ("fake.txt", b"x", "text/plain")}).status_code, 415)
            finally:
                main.DATA_DIR, main.VIDEO_DIR, main.DB_PATH = previous
                os.environ.pop("GLENWAKE_DATA_DIR", None)


if __name__ == "__main__":
    unittest.main()
