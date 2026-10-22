"""Cross-field consistency rules evaluated on the normalized records.

Access level rule (approved by Lizeth Llanos, 2026-10-22): "Open" means anyone can obtain
the data without asking permission. So a record marked Open needs a usable public
download_url, and its licence text must not tell people to contact the data owner.
Licences that restrict use but let anyone download (for example GADM's non-commercial
terms) stay allowed.

The rule reads the dicts returned by records.read_records and registry.read_registry,
after the R8 cleaning in transform.clean_download_url: download_url is None when no URL
survived. It therefore covers both build sources. It reads and writes no file.
"""
from __future__ import annotations

FIX = "add a public download_url or set access_level to Restricted or Internal"
CONTACT_OWNER = "contact data owner"


def check_access_consistency(records: list[dict]) -> list[str]:
    """One message per violation, records in ascending id order; empty list = pass."""
    errors: list[str] = []
    for r in sorted(records, key=lambda rec: rec["id"]):
        if r.get("access_level") != "Open":
            continue
        if not r.get("download_url"):
            errors.append(f"{r['id']}: access_level is Open but there is no usable "
                          f"download_url; {FIX}")
        if CONTACT_OWNER in (r.get("license") or "").lower():
            errors.append(f"{r['id']}: access_level is Open but license says "
                          f"'{CONTACT_OWNER}'; {FIX}")
    return errors
