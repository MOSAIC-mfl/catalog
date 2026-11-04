"""The standard behaves as documented: valid passes, malformed is INVALID, gaps are INCOMPLETE."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from mosaic_catalog.config import Config
from mosaic_catalog.records import load_record
from mosaic_catalog.standard import Standard, Status

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def std() -> Standard:
    return Standard()


def _load(path: Path) -> dict:
    rec = load_record(path)
    assert rec.data is not None, rec.error
    return rec.data


def test_complete_fixture_passes_everything(std: Standard) -> None:
    rep = std.check(_load(FIX / "valid" / "complete.yaml"))
    assert rep.status is Status.COMPLETE
    assert rep.issues == []
    assert rep.completeness == {"minimum": 1.0, "recommended": 1.0}


@pytest.mark.parametrize("path", sorted((FIX / "invalid").glob("*.yaml")), ids=lambda p: p.stem)
def test_invalid_fixtures_are_invalid(std: Standard, path: Path) -> None:
    assert std.check(_load(path)).status is Status.INVALID


@pytest.mark.parametrize("path", sorted((FIX / "incomplete").glob("*.yaml")), ids=lambda p: p.stem)
def test_incomplete_fixtures_are_incomplete_not_invalid(std: Standard, path: Path) -> None:
    rep = std.check(_load(path))
    assert rep.status is Status.INCOMPLETE, rep.as_dict()
    assert rep.completeness["minimum"] < 1.0


def test_messages_name_the_field(std: Standard) -> None:
    rep = std.check(_load(FIX / "incomplete" / "restricted-no-note.yaml"))
    assert [(i.field, i.message) for i in rep.by_level("minimum")] == [
        ("access_note", "restricted/internal resource without access_note (how to obtain it)")
    ]


def test_restricted_without_url_is_fine_when_it_says_how_to_ask(std: Standard) -> None:
    data = _load(FIX / "valid" / "complete.yaml")
    data["access"] = "restricted"
    data["access_note"] = "Write to the contact."
    for point in data["data"]:
        point.pop("url")
    assert std.check(data).status is Status.COMPLETE


def test_license_with_text_only_meets_the_minimum_but_warns(std: Standard) -> None:
    data = _load(FIX / "valid" / "complete.yaml")
    data["license"] = {"spdx": None, "url": None, "text": "Dryad terms of use"}
    rep = std.check(data)
    assert rep.status is Status.COMPLETE
    assert ("license", "non-standard licence without the URL of its terms") in {
        (i.field, i.message) for i in rep.by_level("recommended")
    }


def test_mosaic_profile_is_a_warning_until_enforced() -> None:
    data = _load(FIX / "valid" / "complete.yaml")
    data.pop("mosaic")
    assert Standard().check(data).status is Status.COMPLETE
    assert Standard(enforced_profiles=["mosaic"]).check(data).status is Status.INCOMPLETE


def test_declared_extension_is_validated_against_its_schema(tmp_path: Path) -> None:
    schema_dir = tmp_path / "schema"
    import shutil

    shutil.copytree(ROOT / "schema", schema_dir)
    ext = schema_dir / "extensions" / "soil" / "0.1.0"
    ext.mkdir(parents=True)
    (ext / "schema.json").write_text(
        '{"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "urn:test:soil", '
        '"type": "object", "properties": {"soil": {"type": "object", "additionalProperties": false, '
        '"properties": {"depth": {"type": "string"}}}}}',
        encoding="utf-8",
    )
    std = Standard(schema_dir=schema_dir)
    data = _load(FIX / "valid" / "complete.yaml")
    data |= {"extensions": ["soil@0.1.0"], "soil": {"depth": "0-30 cm"}}
    assert std.check(data).status is Status.COMPLETE
    data["soil"] = {"depth": 30}
    assert std.check(data).status is Status.INVALID


def test_duplicate_yaml_keys_are_rejected(tmp_path: Path) -> None:
    f = tmp_path / "dup.yaml"
    f.write_text("id: A-1\nid: A-2\n", encoding="utf-8")
    assert load_record(f).data is None


def test_examples_have_the_documented_status(std: Standard) -> None:
    status = {p.stem: std.check(_load(p)).status for p in (ROOT / "examples").glob("*.yaml")}
    assert status == {
        "MFL-2026-999": Status.COMPLETE,  # rich record from Dryad / CGSpace
        "MFL-2026-079": Status.INCOMPLETE,  # no keywords, no citation
        "MFL-2026-090": Status.INCOMPLETE,  # restricted; no keywords, no citation
    }


def test_config_matches_schemas() -> None:
    assert Config.load().standard_version == Standard().version


def test_vocabularies_are_up_to_date() -> None:
    import subprocess
    import sys

    res = subprocess.run(  # noqa: S603 - fixed argv, no user input
        [sys.executable, str(ROOT / "scripts" / "build_vocab.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, res.stdout


def test_every_vocabulary_id_is_unique() -> None:
    for f in (ROOT / "vocab").glob("*.json"):
        import json

        ids = [c["id"] for c in json.loads(f.read_text(encoding="utf-8"))["concepts"]]
        assert len(ids) == len(set(ids)), f.name


def test_cdh_crosswalk_targets_exist() -> None:
    import json

    themes = {c["id"] for c in json.loads((ROOT / "vocab" / "themes.json").read_text(encoding="utf-8"))["concepts"]}
    cw = yaml.safe_load((ROOT / "crosswalks" / "cdh.yaml").read_text(encoding="utf-8"))
    for domain, target in cw["vocabularies"]["domain_to_theme"].items():
        assert target is None or target in themes, domain


def test_field_reference_is_up_to_date() -> None:
    import subprocess
    import sys

    res = subprocess.run(  # noqa: S603 - fixed argv, no user input
        [sys.executable, str(ROOT / "scripts" / "build_docs.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, res.stdout
