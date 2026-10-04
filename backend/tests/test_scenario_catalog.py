"""Lock the evaluation scenario list before any clip is collected."""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "docs" / "evaluation" / "scenario-catalog.json"
PROTOCOL_PATH = ROOT / "docs" / "evaluation" / "data-protocol.md"

REQUIRED_IDS = (
    "leftover",
    "moved",
    "newly_deposited",
    "visible_removal",
    "departure_without_removal",
    "occluded_transition",
    "association_switch",
    "negative_control",
)

OUTCOMES = {
    "leftover": "leftover",
    "moved": "moved",
    "newly_deposited": "newly_deposited",
    "visible_removal": "removal_visible",
    "departure_without_removal": "unresolved",
    "occluded_transition": "unresolved",
    "association_switch": "follow_visible_continuity_or_unresolved",
    "negative_control": "no_event",
}

REQUIRED_REFUSALS = {
    "leftover": {"new_track_id_is_new_deposit", "similar_coverage_is_same_history"},
    "moved": {"new_track_id_is_new_deposit", "similar_coverage_is_same_history"},
    "newly_deposited": {"later_deposit_fails_earlier_cleanup", "new_track_id_is_new_deposit"},
    "visible_removal": {"disappearance_confirms_cleanup", "waste_mass", "disposal_quality"},
    "departure_without_removal": {"disappearance_confirms_cleanup", "disappearance_confirms_disposal"},
    "occluded_transition": {"single_origin_after_occlusion", "filled_measurement"},
    "association_switch": {"new_track_id_is_new_deposit"},
    "negative_control": {"inferred_event", "filled_measurement"},
}

ALLOWED_REFUSALS = set().union(*REQUIRED_REFUSALS.values())
FORBIDDEN_KEYS = {
    "confidence",
    "accuracy",
    "percent",
    "percentage",
    "score",
    "probability",
    "coverage_percent",
    "precision",
    "recall",
    "f1",
}
PERCENTAGE = re.compile(r"\d+(?:\.\d+)?\s*%")


def walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_keys(child)


class ScenarioCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        cls.protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
        cls.by_id = {item["id"]: item for item in cls.catalog["scenarios"]}

    def test_catalog_is_defined_and_empty(self):
        self.assertEqual(self.catalog["catalog_status"], "defined_not_collected")
        self.assertEqual(self.catalog["label_source"], "human_staging_label")
        pilot = self.catalog["pilot"]
        self.assertEqual(pilot["collected_clip_count"], 0)
        self.assertEqual(
            pilot["planned_clip_count"],
            len(REQUIRED_IDS) * pilot["takes_per_type_per_location"] * pilot["location_count"],
        )
        self.assertEqual(pilot["planned_clip_count"], 48)
        self.assertEqual(pilot["partitions"], ["development", "tuning", "testing"])
        self.assertNotIn("clips", self.catalog)

    def test_eight_types_match_the_protocol(self):
        self.assertEqual(tuple(self.by_id), REQUIRED_IDS)
        later = self.catalog["scope"]["later_extensions"]
        for excluded in ("night scenes", "moving cameras", "tiny distant objects", "dense piles"):
            self.assertIn(excluded, later)
        for scenario_id, outcome in OUTCOMES.items():
            scenario = self.by_id[scenario_id]
            self.assertEqual(scenario["protocol_outcome"], outcome)
            self.assertTrue(scenario["primary_question"].strip())
            self.assertTrue(scenario["recording_must_show"].strip())
            self.assertTrue(scenario["supported_statement"].strip())
            refusals = set(scenario["must_not_claim"])
            self.assertTrue(REQUIRED_REFUSALS[scenario_id] <= refusals)
            self.assertTrue(refusals <= ALLOWED_REFUSALS)
            self.assertIn(f"### {scenario_id}", self.protocol)
            self.assertIn(scenario["title"], self.protocol)

    def test_comparison_pairs_use_real_types(self):
        pairs = {item["id"]: item["scenario_ids"] for item in self.catalog["comparison_pairs"]}
        self.assertEqual(pairs["similar_endpoint_coverage"], ["leftover", "moved"])
        self.assertEqual(pairs["item_absent"], ["visible_removal", "departure_without_removal"])
        for scenario_ids in pairs.values():
            for scenario_id in scenario_ids:
                self.assertIn(scenario_id, self.by_id)

    def test_collection_fields_are_named_not_filled(self):
        fields = self.catalog["required_record_fields"]
        self.assertIn("monitoring_region", fields)
        self.assertIn("cleanup_end_seconds", fields)
        self.assertIn("item_histories", fields)
        self.assertIn("frames_comparable", fields)
        self.assertEqual(len(fields), len(set(fields)))
        for field in fields:
            self.assertNotIn(field, self.catalog["pilot"])

    def test_no_invented_measurements(self):
        keys = {key.lower() for key in walk_keys(self.catalog)}
        self.assertTrue(keys.isdisjoint(FORBIDDEN_KEYS))
        for text in (CATALOG_PATH.read_text(encoding="utf-8"), self.protocol):
            self.assertIsNone(PERCENTAGE.search(text))
            self.assertNotIn("confidence", text.lower())
