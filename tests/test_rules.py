from __future__ import annotations

import unittest

from mosaic_pipeline.rules import check_access_consistency

URL = "https://a.org/x"
FIX = "add a public download_url or set access_level to Restricted or Internal"


def url_message(rid: str) -> str:
    return f"{rid}: access_level is Open but there is no usable download_url; {FIX}"


def licence_message(rid: str) -> str:
    return f"{rid}: access_level is Open but license says 'contact data owner'; {FIX}"


def rec(access_level, download_url, license, rid="MFL-2026-900"):
    return {"id": rid, "access_level": access_level, "download_url": download_url,
            "license": license}


RID = "MFL-2026-900"

CASES = [
    ("open and downloadable", [rec("Open", URL, "CC-BY-4.0")], []),
    ("open, no URL", [rec("Open", None, "CC-BY-4.0")], [url_message(RID)]),
    ("open, owner must be asked", [rec("Open", URL, "Restricted — contact data owner")],
     [licence_message(RID)]),
    ("letter case ignored", [rec("Open", URL, "RESTRICTED — CONTACT DATA OWNER")],
     [licence_message(RID)]),
    ("both problems", [rec("Open", None, "Restricted — contact data owner")],
     [url_message(RID), licence_message(RID)]),
    ("restrictive but public",
     [rec("Open", URL, "Restricted — GADM terms (academic/non-commercial use only, no redistribution)")],
     []),
    ("open, no URL, no licence", [rec("Open", None, None)], [url_message(RID)]),
    ("restricted", [rec("Restricted", None, "Restricted — contact data owner")], []),
    ("internal", [rec("Internal", None, None)], []),
    ("no access level", [rec(None, None, None)], []),
    ("ordering",
     [rec("Open", None, None, rid="MFL-2026-902"), rec("Open", None, None, rid="MFL-2026-901")],
     [url_message("MFL-2026-901"), url_message("MFL-2026-902")]),
    ("empty input", [], []),
]


class AccessConsistencyTest(unittest.TestCase):
    def test_cases(self):
        for name, records, expected in CASES:
            with self.subTest(case=name):
                self.assertEqual(check_access_consistency(records), expected)

    def test_messages_are_written_out_in_full(self):
        self.assertEqual(
            url_message(RID),
            "MFL-2026-900: access_level is Open but there is no usable download_url; "
            "add a public download_url or set access_level to Restricted or Internal")
        self.assertEqual(
            licence_message(RID),
            "MFL-2026-900: access_level is Open but license says 'contact data owner'; "
            "add a public download_url or set access_level to Restricted or Internal")


if __name__ == "__main__":
    unittest.main()
