from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from mosaic_pipeline.records import RecordValidationError, read_records
from mosaic_pipeline.vocab import Vocab

SOURCE = Path(__file__).resolve().parent.parent / "records" / "MFL-2026-001.yaml"


def _load():
    with open(SOURCE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _dump(data, dest):
    with open(dest, "w", encoding="utf-8") as f:
        f.write(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))


class TestReadRecords(unittest.TestCase):
    def _errors(self, tmp):
        with self.assertRaises(RecordValidationError) as cm:
            read_records(tmp, Vocab())
        return "\n".join(cm.exception.errors)

    def test_valid_copy_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copyfile(SOURCE, Path(tmp) / "MFL-2026-001.yaml")
            out = read_records(tmp, Vocab())
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["id"], "MFL-2026-001")

    def test_unknown_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = _load()
            data["bogus_key"] = "x"
            _dump(data, Path(tmp) / "MFL-2026-001.yaml")
            self.assertIn("unknown key(s) 'bogus_key'", self._errors(tmp))

    def test_missing_contact(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = _load()
            del data["contact"]
            _dump(data, Path(tmp) / "MFL-2026-001.yaml")
            self.assertIn("required key 'contact' is missing or null", self._errors(tmp))

    def test_stray_yml(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copyfile(SOURCE, Path(tmp) / "MFL-2026-001.yaml")
            shutil.copyfile(SOURCE, Path(tmp) / "MFL-2026-001.yml")
            self.assertIn("use the .yaml extension", self._errors(tmp))

    def test_filename_does_not_match_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            _dump(_load(), Path(tmp) / "MFL-2026-999.yaml")
            self.assertIn("filename does not match id", self._errors(tmp))

    def test_duplicate_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copyfile(SOURCE, Path(tmp) / "MFL-2026-001.yaml")
            _dump(_load(), Path(tmp) / "MFL-2026-999.yaml")
            self.assertIn("duplicate id 'MFL-2026-001' (already used by MFL-2026-001.yaml)",
                          self._errors(tmp))

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn("no *.yaml records found", self._errors(tmp))

    def test_blank_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = _load()
            data["title"] = "   "
            _dump(data, Path(tmp) / "MFL-2026-001.yaml")
            self.assertIn("title must not be blank", self._errors(tmp))
