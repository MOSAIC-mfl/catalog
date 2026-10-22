from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from mosaic_pipeline.stac_build import _contact_roles, _looks_spdx
from mosaic_pipeline.transform import SPDX_LICENSE_IDS
from mosaic_pipeline.validate import validate_item, validate_tree

ROOT = Path(__file__).resolve().parent.parent

CONTACT_ROLE_CASES = [
    ({"id": "MFL-2026-066", "license": "CC-BY-4.0"}, ["point-of-contact"]),
    ({"id": "MFL-2026-093", "license": "CC-BY-SA-4.0"}, ["producer", "licensor"]),
    ({"id": "MFL-2026-025", "license": "CGIAR Open Access"}, ["producer"]),
]

MINIMAL_ITEM = {
    "type": "Feature", "stac_version": "1.0.0", "id": "MFL-2026-900",
    "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
    "bbox": [0, 0, 1, 1],
    "properties": {"datetime": "2026-07-21T00:00:00Z"},
    "links": [], "assets": {},
}


class ContactRolesTest(unittest.TestCase):
    def test_contact_roles(self):
        for record, roles in CONTACT_ROLE_CASES:
            with self.subTest(id=record["id"]):
                self.assertEqual(_contact_roles(record), roles)

    def test_looks_spdx(self):
        self.assertIs(_looks_spdx("other"), True)
        self.assertIs(_looks_spdx("CGIAR Open Access"), False)


class ValidateItemTest(unittest.TestCase):
    def test_minimal_item_is_valid(self):
        self.assertEqual(validate_item(MINIMAL_ITEM, Path("MFL-2026-900.json")), [])

    def test_empty_asset_href_is_rejected(self):
        item = copy.deepcopy(MINIMAL_ITEM)
        item["assets"] = {"data": {"href": ""}}
        errors = "\n".join(validate_item(item, Path("MFL-2026-900.json")))
        self.assertIn("asset 'data' needs a non-empty href", errors)

    def test_non_rfc3339_created_is_rejected(self):
        item = copy.deepcopy(MINIMAL_ITEM)
        item["properties"]["created"] = "NA"
        errors = "\n".join(validate_item(item, Path("MFL-2026-900.json")))
        self.assertIn("created must be an RFC 3339 UTC timestamp, got 'NA'", errors)


class CommittedTreeTest(unittest.TestCase):
    def test_committed_tree_validates(self):
        result = validate_tree(ROOT / "stac")
        self.assertEqual(result["failed"], 0, result["errors"][:5])
        self.assertEqual(result["parsed"], result["files"])

    def test_item_licences(self):
        with open(ROOT / "datasets.json", encoding="utf-8") as f:
            datasets = {r["id"]: r for r in json.load(f)}
        items = sorted((ROOT / "stac" / "collections").glob("*/items/*.json"))
        self.assertTrue(items)
        for fp in items:
            with open(fp, encoding="utf-8") as f:
                item = json.load(f)
            props = item["properties"]
            with self.subTest(id=item["id"]):
                if "license" in props:
                    self.assertTrue(props["license"] in SPDX_LICENSE_IDS
                                    or props["license"] == "other", props["license"])
                self.assertEqual("license" in props, bool(datasets[item["id"]]["license"]))


if __name__ == "__main__":
    unittest.main()
