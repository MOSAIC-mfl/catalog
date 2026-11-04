"""Catalogue configuration (mosaic.config.yaml)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = ROOT / "mosaic.config.yaml"


@dataclass(frozen=True)
class Config:
    standard_version: str
    enforced_profiles: frozenset[str]
    include_incomplete: bool
    landscape_sections: tuple[str, ...] = ("overview", "catalogue-datasets", "data-status")

    @classmethod
    def load(cls, path: Path = CONFIG_FILE) -> Config:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        profiles = raw.get("profiles") or {}
        return cls(
            standard_version=str(raw["standard_version"]),
            enforced_profiles=frozenset(n for n, p in profiles.items() if (p or {}).get("enforce")),
            include_incomplete=bool((raw.get("publication") or {}).get("include_incomplete", True)),
            landscape_sections=tuple((raw.get("landscapes") or {}).get("default_sections") or cls.landscape_sections),
        )
