from __future__ import annotations

import unittest

from mosaic_pipeline.transform import SPDX_LICENSE_IDS, clean_download_url, map_license

MAP_LICENSE_CASES = [
    ("CC BY 4.0", ("CC-BY-4.0", None, [])),
    ("Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International",
     ("CC-BY-NC-SA-4.0", None, [])),
    ("CC BY-IGO", ("CC-BY-3.0-IGO", None, [])),
    ("Restricted — GADM terms (academic/non-commercial use only, no redistribution)",
     ("Restricted — GADM terms (academic/non-commercial use only, no redistribution)",
      "Restricted — GADM terms (academic/non-commercial use only, no redistribution)",
      ["non_spdx_license"])),
    ("ODbL", ("ODbL-1.0", None, [])),
    ("Open Data Commons", ("Open Data Commons", "Open Data Commons", ["non_spdx_license"])),
    ("CC0", ("CC0-1.0", None, [])),
    ("public domain", ("CC0-1.0", None, [])),
    ("Open access", ("other", "Open access", ["vague_license"])),
    ("CGIAR Open Access", ("CGIAR Open Access", "CGIAR Open Access", ["non_spdx_license"])),
    ("", (None, None, ["missing_license"])),
    (None, (None, None, ["missing_license"])),
    ("CC BY-ND 3.0 IGO", ("CC BY-ND 3.0 IGO", "CC BY-ND 3.0 IGO", ["non_spdx_license"])),
    ("CC-BY-SA-4.0", ("CC-BY-SA-4.0", None, [])),
]

CLEAN_DOWNLOAD_URL_CASES = [
    ("https://a.org/x", ("https://a.org/x", [])),
    ("CHIRPS data (https://chc.ucsb.edu/x).", ("https://chc.ucsb.edu/x", [])),
    ("www.geoboundaries.org", (None, ["non_url_download"])),
    ("Internal Available on request", (None, ["non_url_download"])),
    (None, (None, [])),
]


class TestTransform(unittest.TestCase):
    def test_map_license(self):
        for raw, expected in MAP_LICENSE_CASES:
            with self.subTest(raw=raw):
                self.assertEqual(map_license(raw), expected)

    def test_clean_download_url(self):
        for raw, expected in CLEAN_DOWNLOAD_URL_CASES:
            with self.subTest(raw=raw):
                self.assertEqual(clean_download_url(raw), expected)

    def test_spdx_results_are_known_ids(self):
        for raw, (value, alias, _flags) in MAP_LICENSE_CASES:
            if alias is None and value is not None:
                with self.subTest(raw=raw):
                    self.assertIn(value, SPDX_LICENSE_IDS)
