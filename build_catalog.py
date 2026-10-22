#!/usr/bin/env python3
"""MOSAIC catalog pipeline — main entrypoint.

Reads the dataset registry (source of truth) and produces:
  A. A static STAC catalog tree under  MOSAIC_catalog/stac/
  B. The frontend data contract at     MOSAIC_catalog/datasets.json

Source of truth (since 2026-07-24):
  - records/<ID>.yaml is the DEFAULT source when the directory exists AND PyYAML
    imports. This is the git-native, one-file-per-dataset model.
  - If PyYAML is missing (today's CI can't install it — the workflow can't be
    edited from here), we print a LOUD banner and fall back to the Excel snapshot.
    Both paths are acceptance-tested to produce byte-identical artifacts.
  - --from-excel forces the Excel path (used by the acceptance test / snapshots).
The chosen source is printed in the header and the coverage report.

Idempotent: wipes/rebuilds stac/ and overwrites datasets.json each run.

Usage:
    python3 build_catalog.py                 # build STAC + datasets.json
    python3 build_catalog.py --from-excel    # force the Excel snapshot as source
    python3 build_catalog.py --sync-frontend # also copy datasets.json to the frontend
"""
from __future__ import annotations

import shutil
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from mosaic_pipeline.frontend_build import build_frontend  # noqa: E402
from mosaic_pipeline.registry import read_registry  # noqa: E402
from mosaic_pipeline.rules import check_access_consistency  # noqa: E402
from mosaic_pipeline.stac_build import build_stac  # noqa: E402
from mosaic_pipeline.validate import validate_tree  # noqa: E402
from mosaic_pipeline.vocab import Vocab  # noqa: E402

# Absolute paths (the environment resets cwd; keep these explicit).
# The registry is committed INSIDE this repo so the build is self-contained and
# CI can rebuild it. NOTE: this Excel is a PROVISIONAL SNAPSHOT for the v1
# exercise (see catalog/SNAPSHOT_NOTE.md) and will be replaced.
REGISTRY_XLSX = HERE / "catalog" / "MFL_Dataset_Registry.xlsx"
RECORDS_DIR = HERE / "records"
STAC_DIR = HERE / "stac"
# Canonical datasets.json lives inside this repo, next to stac/. It is copied
# into the frontend repo as a separate, explicit step (--sync-frontend).
DATASETS_JSON = HERE / "datasets.json"
# Default frontend data path when the frontend repo sits beside this one.
DEFAULT_FRONTEND_DATASETS = (
    HERE.parent
    / "MOSAIC_frontend"
    / "frontend"
    / "data"
    / "datasets.json"
)


def _select_source(force_excel: bool) -> tuple[str, str]:
    """Decide records/ vs Excel. Returns (source, human description).

    Priority: --from-excel > records/ (if present AND PyYAML imports) > Excel.
    When records/ exists but PyYAML is missing (today's CI), fall back to Excel
    with a LOUD banner so the gap is impossible to miss in the logs.
    """
    if force_excel:
        return "excel", "Excel snapshot (forced via --from-excel)"
    if not RECORDS_DIR.is_dir() or not any(RECORDS_DIR.glob("*.yaml")):
        return "excel", "Excel snapshot (records/ not present)"
    try:
        import yaml  # noqa: F401
    except ImportError:
        banner = "!" * 60
        print(banner)
        print("!! WARNING: records/ is the source of truth but PyYAML is NOT")
        print("!! installed here, so it cannot be read. Falling back to the")
        print("!! Excel snapshot (catalog/MFL_Dataset_Registry.xlsx).")
        print("!! Install PyYAML (pip install pyyaml) to build from records/.")
        print(banner)
        return "excel", "Excel snapshot (FALLBACK — PyYAML missing; records/ ignored)"
    return "records", "records/ YAML files (git-native source of truth)"


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="MOSAIC catalog pipeline: registry -> STAC + datasets.json"
    )
    parser.add_argument(
        "--from-excel", action="store_true",
        help="Force the Excel snapshot as the source of truth, even when records/ "
             "exists. Used by the acceptance test and to regenerate the snapshot.",
    )
    parser.add_argument(
        "--sync-frontend", nargs="?", const=str(DEFAULT_FRONTEND_DATASETS),
        default=None, metavar="PATH",
        help="After building, copy datasets.json into the frontend repo. With no "
             "PATH, uses the default sibling location. Local use only — do NOT "
             "use in the catalog repo's CI (no frontend checkout there).",
    )
    args = parser.parse_args(argv)

    source, source_desc = _select_source(args.from_excel)

    print("MOSAIC catalog pipeline")
    print("=" * 60)
    print(f"Source   : {source_desc}")
    print(f"Registry : {REGISTRY_XLSX}")
    print(f"Records  : {RECORDS_DIR}")
    print(f"STAC out : {STAC_DIR}")
    print(f"datasets : {DATASETS_JSON}")
    print("-" * 60)

    vocab = Vocab()
    if source == "records":
        from mosaic_pipeline.records import RecordValidationError, read_records
        try:
            records = read_records(RECORDS_DIR, vocab)
        except RecordValidationError as e:
            print(f"RECORD VALIDATION FAILED — {len(e.errors)} error(s); build aborted:")
            for msg in e.errors:
                print("  -", msg)
            return 3
    else:
        if not REGISTRY_XLSX.exists():
            print(f"ERROR: registry not found: {REGISTRY_XLSX}")
            return 1
        records = read_registry(str(REGISTRY_XLSX), vocab)

    # Canonical build order for BOTH sources: ascending id. (Excel row order is
    # not id order; sorting here guarantees byte-identical output.)
    records.sort(key=lambda r: r["id"])
    print(f"Real records read: {len(records)}")

    # --- access level rule: "Open" = obtainable without asking permission ---
    # Runs on the normalized records of either source, before anything is written.
    access_errors = check_access_consistency(records)
    if access_errors:
        print(f"ACCESS RULE FAILED — {len(access_errors)} error(s); build aborted:")
        for msg in access_errors:
            print("  -", msg)
        return 3

    # --- Artifact B: datasets.json (canonical copy inside this repo) ---
    n_front = build_frontend(records, DATASETS_JSON, vocab)
    print(f"datasets.json written: {n_front} records")

    # --- Artifact A: STAC ---
    stac_summary = build_stac(records, vocab, STAC_DIR)
    print(f"STAC tree written: {stac_summary['collections']} collections, "
          f"{stac_summary['items']} items")

    # --- validation ---
    v = validate_tree(STAC_DIR)
    print("-" * 60)
    print(f"STAC validation: {v['parsed']}/{v['files']} files parsed; "
          f"{v['passed']} passed, {v['failed']} failed")
    if v["errors"]:
        print("Validation errors (first 20):")
        for e in v["errors"][:20]:
            print("  -", e)

    # --- coverage report ---
    _report(records, vocab, stac_summary, source_desc)

    # --- optional: sync datasets.json into the frontend repo (the hand-off) ---
    if args.sync_frontend:
        dest = Path(args.sync_frontend)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DATASETS_JSON, dest)
        print("-" * 60)
        print(f"Synced datasets.json -> {dest}")
        print("Next, in the frontend repo, commit & push to publish:")
        print("  git add frontend/data/datasets.json")
        print('  git commit -m "Update datasets.json from MOSAIC catalog regeneration"')
        print("  git push")

    return 0 if v["failed"] == 0 else 2


def _report(records, vocab, stac_summary, source_desc="") -> None:
    n = len(records)
    ll_mapped = sum(1 for r in records if r["living_landscape"] != "GLB")
    bbox_assigned = sum(1 for r in records if r["bbox"])
    url_ok = sum(1 for r in records if r["download_url"])
    email_ok = sum(1 for r in records if r["contact"])
    readiness_ok = sum(1 for r in records if "missing_readiness" not in r["flags"])
    cov = Counter(r["coverage"] for r in records)

    print("=" * 60)
    print("COVERAGE REPORT")
    print(f"  source of truth            : {source_desc}")
    print(f"  real records processed     : {n}")
    print(f"  living_landscape mapped    : {ll_mapped}/{n} (GLB: {n - ll_mapped})")
    print(f"  coverage                   : " +
          ", ".join(f"{k}={v}" for k, v in cov.most_common()))
    print(f"  bbox assigned              : {bbox_assigned}/{n}")
    print(f"  download_url usable         : {url_ok}/{n} (rest nulled)")
    print(f"  contact email extracted    : {email_ok}/{n}")
    print(f"  readiness_status mapped    : {readiness_ok}/{n} from registry value")

    flag_counts = Counter(f for r in records for f in r["flags"])
    print("  flags emitted:")
    for f, c in flag_counts.most_common():
        print(f"      {c:3} | {f}")

    code_counts = Counter(r["living_landscape"] for r in records)
    print("  records per landscape code:")
    for code, c in sorted(code_counts.items()):
        print(f"      {c:3} | {code:12} {vocab.landscape_name(code)}")

    if vocab.added_codes:
        print("  CODES ADDED at runtime (confirm with specialist/Lizeth):")
        for a in vocab.added_codes:
            print(f"      {a['code']} ({a['country']}): {a['reason']}")

    climate = [r["id"] for r in records if r["is_climate_linked"]]
    print(f"  climate-linked items (link to CDH): {len(climate)}")


if __name__ == "__main__":
    raise SystemExit(main())
