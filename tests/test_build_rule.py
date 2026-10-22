"""build_catalog.main applies the access level rule before writing anything (both sources)."""
from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

import build_catalog
from tests.test_golden import tree_files

ROOT = Path(__file__).resolve().parent.parent
FIX = "add a public download_url or set access_level to Restricted or Internal"
HEADER_1 = "ACCESS RULE FAILED — 1 error(s); build aborted:"


def _run_main(argv, **patches):
    """build_catalog.main(argv) with module globals patched; returns (exit code, stdout)."""
    buf = io.StringIO()
    with contextlib.ExitStack() as stack:
        for name, value in patches.items():
            stack.enter_context(mock.patch.object(build_catalog, name, value))
        stack.enter_context(contextlib.redirect_stdout(buf))
        rc = build_catalog.main(argv)
    return rc, buf.getvalue()


class BuildRuleTest(unittest.TestCase):
    def test_open_record_without_public_url_aborts_records_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            records = tmp / "records"
            records.mkdir()
            data = yaml.safe_load(
                (ROOT / "records" / "MFL-2026-001.yaml").read_text(encoding="utf-8"))
            data["access_level"] = "Open"
            data["download_url"] = "Available on request"
            (records / "MFL-2026-001.yaml").write_text(
                yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
            rc, out = _run_main([], RECORDS_DIR=records, STAC_DIR=tmp / "stac",
                                DATASETS_JSON=tmp / "datasets.json")
            self.assertEqual(rc, 3, out)
            self.assertIn(HEADER_1, out)
            self.assertIn("  - MFL-2026-001: access_level is Open but there is no usable "
                          "download_url; " + FIX, out)
            self.assertFalse((tmp / "stac").exists())
            self.assertFalse((tmp / "datasets.json").exists())

    def test_open_record_without_url_aborts_excel_build(self):
        bad = [{"id": "MFL-2026-900", "access_level": "Open", "download_url": None,
                "license": "CC-BY-4.0"}]
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            rc, out = _run_main(["--from-excel"], read_registry=mock.Mock(return_value=bad),
                                STAC_DIR=tmp / "stac", DATASETS_JSON=tmp / "datasets.json")
            self.assertEqual(rc, 3, out)
            self.assertIn(HEADER_1, out)
            self.assertFalse((tmp / "stac").exists())
            self.assertFalse((tmp / "datasets.json").exists())

    def test_committed_records_pass_and_rebuild_identically(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            rc, out = _run_main([], STAC_DIR=tmp / "stac", DATASETS_JSON=tmp / "datasets.json")
            self.assertEqual(rc, 0, out)
            self.assertNotIn("ACCESS RULE FAILED", out)
            self.assertEqual((tmp / "datasets.json").read_bytes(),
                             (ROOT / "datasets.json").read_bytes())
            self.assertEqual(tree_files(tmp / "stac"), tree_files(ROOT / "stac"))
            for rel in tree_files(ROOT / "stac"):
                self.assertEqual((tmp / "stac" / rel).read_bytes(),
                                 (ROOT / "stac" / rel).read_bytes(), rel)


if __name__ == "__main__":
    unittest.main()
