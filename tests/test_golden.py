"""Golden rebuild: a fresh build of records/ equals the committed stac/ and datasets.json."""
from __future__ import annotations

import copy
import filecmp
import tempfile
import unittest
from pathlib import Path

import build_catalog
from mosaic_pipeline.frontend_build import build_frontend
from mosaic_pipeline.records import read_records
from mosaic_pipeline.stac_build import build_stac
from mosaic_pipeline.vocab import Vocab

ROOT = Path(__file__).resolve().parent.parent


def tree_files(root: Path) -> list[str]:
    """Sorted POSIX paths of every file under root, relative to it.

    macOS .DS_Store files are skipped: they are git-ignored Finder artefacts, never part of
    the published tree.
    """
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*")
                  if p.is_file() and p.name != ".DS_Store")


def _sorted_records():
    vocab = Vocab()
    records = read_records(ROOT / "records", vocab)
    records.sort(key=lambda r: r["id"])  # the canonical build order of build_catalog.main
    return records, vocab


class GoldenRebuildTest(unittest.TestCase):
    def test_rebuild_equals_committed_outputs(self):
        records, vocab = _sorted_records()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            build_frontend(records, out / "datasets.json", vocab)
            build_stac(records, vocab, out / "stac")
            self.assertEqual((out / "datasets.json").read_bytes(),
                             (ROOT / "datasets.json").read_bytes())
            rebuilt, committed = tree_files(out / "stac"), tree_files(ROOT / "stac")
            self.assertEqual(rebuilt, committed)
            _, mismatch, errors = filecmp.cmpfiles(out / "stac", ROOT / "stac", rebuilt,
                                                   shallow=False)
            self.assertEqual(mismatch, [])
            self.assertEqual(errors, [])

    def test_comparison_detects_a_change(self):
        records, vocab = _sorted_records()
        changed = copy.deepcopy(records)
        changed[0]["title"] += " (changed)"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "datasets.json"
            build_frontend(changed, path, vocab)
            self.assertNotEqual(path.read_bytes(), (ROOT / "datasets.json").read_bytes())

    def test_build_reads_records_not_the_excel_snapshot(self):
        self.assertEqual(build_catalog._select_source(False)[0], "records")


if __name__ == "__main__":
    unittest.main()
