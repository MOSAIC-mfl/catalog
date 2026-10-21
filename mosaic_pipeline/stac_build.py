"""Artifact A: build a static STAC catalog tree (plain JSON, no pystac).

Structure:
  stac/catalog.json                       (root Catalog)
  stac/collections/<CODE>/collection.json (one per living-landscape code)
  stac/collections/<CODE>/items/<id>.json (one per dataset)

Uses cgiar-cdh:* and mosaic:* namespaces per MOSAIC_CDH_Interoperability_STAC_
Assessment_202606.md. Approximate bboxes are flagged. Climate-themed items link
to the CDH via links[rel=via|related] rather than re-describing them.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import date
from pathlib import Path

from .config import STAC_BASE_URL
from .transform import SPDX_LICENSE_IDS
from .vocab import COUNTRY_M49, MULTI_LANDSCAPE_COUNTRIES, Vocab

BOUNDARIES_SRC = Path(__file__).resolve().parent.parent / "boundaries"
# Source, licence and attribution of each delineation (also stamped into the GeoJSON).
PROVENANCE_SRC = Path(__file__).resolve().parent.parent / "spec" / "boundary_provenance.json"
BOUNDARY_PROVENANCE = (
    json.loads(PROVENANCE_SRC.read_text(encoding="utf-8")) if PROVENANCE_SRC.is_file() else {}
)

STAC_VERSION = "1.0.0"
MOSAIC_SCHEMA_VERSION = "0.3.0"

# Custom extension identifiers (mirrored locally; schemas hosted later).
EXT_MOSAIC = f"https://mosaic.cgiar.org/stac-extensions/mosaic/v{MOSAIC_SCHEMA_VERSION}/schema.json"
# CDH standard release the cgiar-cdh:* fields follow (one tag covers standard, vocab and extension).
CDH_STANDARD_VERSION = "0.3.0"
EXT_CDH = (
    "https://cgiar-climate-data-hub.github.io/cdh-metadata-standard/"
    f"v{CDH_STANDARD_VERSION}/encodings/stac/schema.json"
)

# Canonical registry snapshot. Every record without a registration date is older than it.
SNAPSHOT_DATE = "2026-07-21"

MEDIA_TYPE = {
    "GeoTIFF": "image/tiff; application=geotiff",
    "GeoPackage": "application/geopackage+sqlite3",
    "GeoJSON": "application/geo+json",
    "NetCDF": "application/x-netcdf",
    "CSV": "text/csv",
    "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "JSON": "application/json",
    "Shapefile": "application/octet-stream",
}


def _self_link(path_from_root: str) -> dict:
    return {"rel": "self", "href": path_from_root}


def _rfc3339(value) -> str | None:
    """A full calendar date ('2026-09-15') as RFC 3339 midnight UTC; anything else -> None."""
    v = str(value).strip() if value is not None else ""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        return None
    try:
        date.fromisoformat(v)
    except ValueError:
        return None
    return f"{v}T00:00:00Z"


def build_stac(records: list[dict], vocab: Vocab, stac_dir: Path) -> dict:
    """Writes the full tree. Returns a small summary dict."""
    if stac_dir.exists():
        shutil.rmtree(stac_dir)  # idempotent: wipe and rebuild
    (stac_dir / "collections").mkdir(parents=True, exist_ok=True)

    # Publish the committed landscape boundaries alongside the STAC tree so the
    # existing Pages CI (which publishes stac/) serves them with zero changes.
    if BOUNDARIES_SRC.is_dir():
        shutil.copytree(BOUNDARIES_SRC, stac_dir / "boundaries")

    # Group records by living-landscape code. Every canonical delineated
    # landscape gets a collection even with zero items yet — the catalog is the
    # published home of the landscape delineations (2026 objective #4).
    by_code: dict[str, list[dict]] = {c: [] for c in vocab.delineated_codes()}
    for r in records:
        by_code.setdefault(r["living_landscape"], []).append(r)

    n_items = 0
    catalog_links = [
        {"rel": "root", "href": "./catalog.json", "type": "application/json"},
        # self is ABSOLUTE (citable endpoint); internal nav links stay relative.
        {"rel": "self", "href": f"{STAC_BASE_URL}/catalog.json", "type": "application/json"},
    ]

    for code in sorted(by_code):
        recs = by_code[code]
        coll_dir = stac_dir / "collections" / code
        (coll_dir / "items").mkdir(parents=True, exist_ok=True)

        collection = _build_collection(code, recs, vocab)
        item_links = []
        for r in recs:
            item = _build_item(r, code, vocab)
            item_path = coll_dir / "items" / f"{r['_safe_id']}.json"
            _write_json(item_path, item)
            n_items += 1
            item_links.append({
                "rel": "item",
                "href": f"./items/{r['_safe_id']}.json",
                "type": "application/json",
                "title": r["title"],
            })
        collection["links"] = [
            {"rel": "root", "href": "../../catalog.json", "type": "application/json"},
            {"rel": "parent", "href": "../../catalog.json", "type": "application/json"},
            {"rel": "self",
             "href": f"{STAC_BASE_URL}/collections/{code}/collection.json",
             "type": "application/json"},
        ] + item_links
        _write_json(coll_dir / "collection.json", collection)

        catalog_links.append({
            "rel": "child",
            "href": f"./collections/{code}/collection.json",
            "type": "application/json",
            "title": vocab.landscape_name(code),
        })

    catalog_links.append({
        "rel": "related",
        "href": f"{STAC_BASE_URL}/boundaries/landscapes.geojson",
        "type": "application/geo+json",
        "title": "Living Landscape boundaries that MOSAIC may redistribute (simplified; licence per feature)",
    })
    catalog = {
        "type": "Catalog",
        "stac_version": STAC_VERSION,
        "id": "mosaic-mfl-catalog",
        "title": "MOSAIC — MFL Multifunctional Landscapes Catalog",
        "description": (
            "MOSAIC coordination-network metadata catalog for the CGIAR MFL Science "
            "Programme (AoW2). One STAC Collection per Living Landscape, one Item per "
            "registered dataset. Collection extents derive from the canonical landscape "
            "delineations (2026-07-21); each collection publishes its simplified boundary "
            "as a GeoJSON asset. Climate layers link to the CGIAR Climate Data Hub "
            "(connect, don't duplicate)."
        ),
        "links": catalog_links,
        "mosaic:schema_version": MOSAIC_SCHEMA_VERSION,
    }
    _write_json(stac_dir / "catalog.json", catalog)

    return {
        "collections": len(by_code),
        "items": n_items,
        "codes": sorted(by_code),
    }


def _collect_temporal(recs: list[dict]) -> list:
    starts, ends = [], []
    for r in recs:
        iv = r["temporal_interval"][0]
        if iv[0]:
            starts.append(iv[0])
        if iv[1]:
            ends.append(iv[1])
    start = min(starts) if starts else None
    end = max(ends) if ends else None
    return [[start, end]]


def _union_bbox(recs: list[dict]) -> list:
    boxes = [r["bbox"] for r in recs if r.get("bbox")]
    if not boxes:
        return [-180.0, -90.0, 180.0, 90.0]
    w = min(b[0] for b in boxes)
    s = min(b[1] for b in boxes)
    e = max(b[2] for b in boxes)
    n = max(b[3] for b in boxes)
    return [w, s, e, n]


def _build_collection(code: str, recs: list[dict], vocab: Vocab) -> dict:
    delineated = vocab.is_delineated(code)
    # Delineated landscapes use the REAL boundary-derived bbox; the union of
    # member items still widens it when national-coverage items are included.
    if delineated:
        bbox = _union_bbox(recs + [{"bbox": vocab.entry(code)["bbox"]}])
    else:
        bbox = _union_bbox(recs)
    temporal = _collect_temporal(recs)

    # Geography (UN M49) union across member items.
    geos: list[str] = []
    for r in recs:
        for g in COUNTRY_M49.get(r["country"], (None,))[:1] if r["country"] in COUNTRY_M49 else []:
            if g and g not in geos:
                geos.append(g)
    geographies = sorted({COUNTRY_M49[r["country"]][0] for r in recs if r["country"] in COUNTRY_M49})

    themes = sorted({r["mfl_theme"] for r in recs if r["mfl_theme"]})
    access_levels = sorted({r["access_level"] for r in recs if r["access_level"]})

    # Collection license: if all members share one SPDX id use it, else "various".
    lics = {r["license"] for r in recs if r["license"]}
    if len(lics) == 1:
        license_val = next(iter(lics))
        # STAC license must be SPDX or "other"/"proprietary"; non-SPDX -> "other".
        if not _looks_spdx(license_val):
            license_val = "other"
    elif lics:
        license_val = "other"
    else:
        license_val = "other"

    boundary_published = (BOUNDARIES_SRC / f"{code}.geojson").is_file()
    if delineated:
        boundary_sentence = (
            "the simplified boundary is published as this collection's 'boundary' asset"
            if boundary_published else
            "the boundary geometry is not redistributed here because its licence does not "
            "allow it; the 'boundary-source' asset names the source"
        )
        description = (
            f"Datasets registered under the '{vocab.landscape_name(code)}' Living "
            f"Landscape ({len(recs)} item(s)). Spatial extent derives from the "
            f"canonical landscape delineation (2026-07-21); {boundary_sentence}. "
            f"National-coverage member items can widen the extent beyond the boundary."
        )
        if vocab.pending_confirmation(code):
            description += (
                " NOTE: this landscape's name and delineation are PENDING "
                "CONFIRMATION with the country team."
            )
        bbox_note = (
            "Bbox derived from the canonical delineation shapefile (dissolved, "
            "EPSG:4326), union-ed with member-item locator boxes."
        )
    else:
        description = (
            f"Datasets registered as '{vocab.landscape_name(code)}' "
            f"({len(recs)} item(s)). Spatial extent is an APPROXIMATE locator box."
        )
        bbox_note = "Approximate locator box from MOSAIC bbox_lookup (EPSG:4326)."

    coll = {
        "type": "Collection",
        "stac_version": STAC_VERSION,
        "stac_extensions": [EXT_MOSAIC, EXT_CDH],
        "id": code,
        "title": vocab.landscape_name(code),
        "description": description,
        "license": license_val,
        "extent": {
            "spatial": {"bbox": [bbox]},
            "temporal": {"interval": temporal},
        },
        "keywords": themes,
        "providers": _collection_providers(recs),
        # STAC summaries need at least one value per field (KEN-LEI has no items yet).
        "summaries": {k: v for k, v in (("mosaic:access_level", access_levels),
                                        ("mosaic:theme", themes)) if v},
        "cgiar-cdh:geography": geographies,
        "mosaic:living_landscape": code,
        "mosaic:bbox_approximate": not delineated,
        "mosaic:bbox_note": bbox_note,
        "mosaic:item_count": len(recs),
        "links": [],  # filled by caller
    }
    if not geographies:
        del coll["cgiar-cdh:geography"]  # CDH v0.3.0: minItems 1; omit when unknown
    if vocab.landscape_system(code):
        coll["mosaic:landscape_system"] = vocab.landscape_system(code)
    if vocab.landscape_countries(code):
        coll["mosaic:countries"] = vocab.landscape_countries(code)
    if vocab.pending_confirmation(code):
        coll["mosaic:pending_confirmation"] = True
    if delineated:
        asset = _boundary_asset(code, boundary_published)
        if asset:
            coll["assets"] = {"boundary" if boundary_published else "boundary-source": asset}
    return coll


def _boundary_asset(code: str, published: bool) -> dict | None:
    """The boundary GeoJSON when it may be redistributed; otherwise a pointer to its source.

    Either way the asset carries the delineation's licence (SPDX id or 'other'), source
    and required attribution from spec/boundary_provenance.json.
    """
    prov = BOUNDARY_PROVENANCE.get(code, {})
    if published:
        asset = {
            "href": f"{STAC_BASE_URL}/boundaries/{code}.geojson",
            "type": "application/geo+json",
            "title": "Landscape boundary (canonical delineation, simplified, EPSG:4326)",
            "roles": ["data"],
        }
    elif prov.get("source_url"):
        asset = {
            "href": prov["source_url"],
            "type": "text/html",
            "title": "Source of the landscape boundary (geometry not redistributed by MOSAIC)",
            "roles": ["metadata"],
        }
    else:
        return None
    if prov:
        asset["license"] = prov["license"]
        if prov.get("license_url"):
            asset["mosaic:license_url"] = prov["license_url"]
        asset["mosaic:source"] = prov["source"]
        asset["mosaic:attribution"] = prov["attribution"]
    return asset


def _looks_spdx(value: str) -> bool:
    return value in SPDX_LICENSE_IDS or value == "other"


# Records whose data belongs to a third party. The registered contact neither
# produced nor licensed it — they are only who to ask — so their STAC role is
# 'point-of-contact'. Grouped by rights holder; the sweep behind the list is
# `MFL SP docs/project docs/MOSAIC internal/stac_contact_roles_sweep_2026-10-15.md`
# (Lizeth approved it 2026-10-15). The ids are the record id's last segment.
#
# This lives here, and not in the record schema, by decision: the judgement is
# about who holds the rights, which the registry does not record. Add an id here
# when a new record turns out to re-describe someone else's data.
THIRD_PARTY_RIGHTS = {
    # National government (external)
    "013", "014", "015", "039", "040", "042",
    # GADM
    "018", "019", "021", "026", "044",
    # Open Development Cambodia
    "059", "060", "061", "062",
    # Open Development Mekong
    "058",
    # COD-AB Tunisia (UN OCHA) — per the 2026-09-22 intake, not ICARDA
    "030", "031", "032",
    # MINAM / GEOBOSQUES / SERNANP / INEI (Peruvian government)
    "072", "073", "074", "076", "077", "078", "079", "080",
    # Mekong River Commission
    "050", "051", "052",
    # MOSAIC landscape delineations (2026-10-21): derived from GADM, HydroSHEDS, World Bank, INEI
    # and an unattributed source; the rights stay with those sources, MOSAIC is the point of contact
    "098", "099", "100", "101", "102", "103", "104", "105",
    # MapBiomas Peru
    "081", "082",
    # Mission Antyodaya (gov.in)
    "004", "005",
    # NASA / USGS, NASA POWER
    "002", "024", "036",
    # data.gov.in
    "008", "009",
    # soilhealth.dac.gov.in
    "010",
    # India Meteorological Department (imdpune.gov.in)
    "003",
    # National government, via Zenodo
    "012",
    # National government (external), Landsat/Sentinel derived
    "001",
    # ARCWeather / Sodexam
    "046",
    # ATREE / GEE (2026-09-04 audit)
    "063",
    # CHIRPS / AgERA5
    "067",
    # ESA / Copernicus
    "011",
    # Esri Living Atlas
    "017",
    # IFPRI — 045 (contact is AfricaRice), 048 (IFPRI Dataverse)
    "045", "048",
    # RAISG
    "075",
    # iSDAsoil
    "066",
}


def _contact_roles(r: dict) -> list[str]:
    """STAC roles for the record's contact.

    'licensor' names the party that GRANTED the licence, so it is only true when
    the contact's own institution both produced the data and granted an SPDX
    licence for it. An SPDX id alone is not enough: MFL-2026-066 is iSDAsoil
    under CC BY 4.0, but iSDA is the licensor, not the AfricaRice contact.
    """
    if r["id"].split("-")[-1] in THIRD_PARTY_RIGHTS:
        return ["point-of-contact"]
    if r["license"] and r["license"] in SPDX_LICENSE_IDS:
        return ["producer", "licensor"]
    return ["producer"]


def _collection_providers(recs: list[dict]) -> list[dict]:
    names = sorted({r["source"] for r in recs if r["source"]})
    return [{"name": n, "roles": ["producer"]} for n in names] or [
        {"name": "MOSAIC / CGIAR MFL Science Programme", "roles": ["host"]}
    ]


def _build_item(r: dict, code: str, vocab: Vocab) -> dict:
    bbox = r["bbox"]
    geometry = _bbox_to_polygon(bbox)

    geography, _ = Vocab.country_m49(r["country"])
    start, end = r["temporal_interval"][0]
    catalogued = _rfc3339(r["date_registered"])

    props = {
        "title": r["title"],
        "description": r["description"],
        "datetime": None,  # closed interval below; null datetime is valid with start/end
        "start_datetime": start,
        "end_datetime": end,
        "created": catalogued,
        # cgiar-cdh:* (CDH-defined where applicable)
        "cgiar-cdh:geography": geography,
        # mosaic:* (MOSAIC-specific)
        "mosaic:living_landscape": code,
        "mosaic:coverage": r["coverage"],
        "mosaic:theme": r["mfl_theme"],
        "mosaic:access_level": r["access_level"],
        "mosaic:processing_status": r["readiness_status"],
        "mosaic:migration_status": r["migration_status"],
        "mosaic:update_frequency": r["update_frequency"],
        "mosaic:bbox_approximate": r["bbox_approximate"],
        "mosaic:bbox_note": _item_bbox_note(r),
        "mosaic:formats": r["formats"],
    }
    if not geography:
        del props["cgiar-cdh:geography"]  # CDH v0.3.0: minItems 1; omit when unknown
    # Free text ("30m", "Village level"): CDH v0.3.0 takes only structured point/polygon
    # objects in cgiar-cdh:spatial_resolution (grid spacing -> cube:dimensions), so it stays MOSAIC's.
    if r["spatial_resolution"]:
        props["mosaic:spatial_resolution"] = r["spatial_resolution"]
    # STAC needs a real time on every Item. With no period recorded, the date the record was
    # catalogued stands in, flagged; an open end ("1981 - present") closes on that date.
    stand_in = catalogued or f"{SNAPSHOT_DATE}T00:00:00Z"
    stand_in_source = ("its registration date" if catalogued
                       else f"{SNAPSHOT_DATE}, the canonical registry snapshot it predates")
    if not start:
        del props["start_datetime"], props["end_datetime"]
        props["datetime"] = stand_in
        props["mosaic:datetime_note"] = (
            "No temporal coverage recorded. datetime is a stand-in: the date the record was "
            f"catalogued ({stand_in_source}), not a time of the data.")
    elif not end:
        props["end_datetime"] = stand_in
        props["mosaic:datetime_note"] = (
            "Open-ended coverage ('present'). end_datetime is the date the record was "
            f"catalogued ({stand_in_source}).")
    if not catalogued:
        del props["created"]  # missing, or not a date (text typed in the wrong column)
    # The registry's 'Last updated' describes the data and is mostly a bare year, so it stays
    # verbatim here; STAC 'updated' is the metadata's own RFC 3339 timestamp.
    if r["last_updated"]:
        props["mosaic:last_updated"] = r["last_updated"]
    # proj: CRS unknown in registry -> explicit null + note.
    props["proj:code"] = None
    props["mosaic:crs_note"] = "CRS not recorded in registry (missing_crs)."

    # Item license: the SPDX id, else "other" (the text travels as mosaic:license_original).
    # Omitted when the record states none; clients then fall back to the collection.
    if r["license"]:
        props["license"] = r["license"] if _looks_spdx(r["license"]) else "other"

    # Set for verbatim (non-SPDX) strings and for the vague branch ("other").
    if r["license_alias"]:
        props["mosaic:license_original"] = r["license_alias"]

    # An ID, not a URL: no link until the asset is public (a private asset link is a dead end).
    # Once public, add an 'earth-engine' asset with the CDH's form (CDH issue #34):
    # https://earthengine.googleapis.com/v1/<gee_asset_id>
    if r.get("gee_asset_id"):
        props["mosaic:gee_asset_id"] = r["gee_asset_id"]

    if r["contact"] or r["contact_name"]:
        props["contacts"] = [{
            "name": r["contact_name"] or r["contact"] or "Unknown",
            "emails": ([{"value": r["contact"]}] if r["contact"] else []),
            "roles": _contact_roles(r),
        }]

    # Drop None datetime keys that STAC validators dislike? datetime=null is allowed
    # when start/end present, so keep it.

    assets, access_note = _build_assets(r)
    if access_note:
        props["mosaic:access_note"] = access_note

    links = [
        {"rel": "root", "href": "../../../catalog.json", "type": "application/json"},
        {"rel": "parent", "href": "../collection.json", "type": "application/json"},
        {"rel": "collection", "href": "../collection.json", "type": "application/json"},
        {"rel": "self",
         "href": f"{STAC_BASE_URL}/collections/{code}/items/{r['_safe_id']}.json",
         "type": "application/json"},
    ]
    if r["download_url"]:
        links.append({"rel": "via", "href": r["download_url"], "title": "Primary source / download"})
    # National-coverage items in a multi-landscape country also serve the
    # country's other landscape collections — cross-link them.
    if r["coverage"] == "national":
        for other in MULTI_LANDSCAPE_COUNTRIES.get(r["country"] or "", []):
            if other != code:
                links.append({
                    "rel": "related",
                    "href": f"{STAC_BASE_URL}/collections/{other}/collection.json",
                    "type": "application/json",
                    "title": f"Also covers: {vocab.landscape_name(other)} (national-coverage dataset)",
                })
    # connect, don't duplicate: climate layers point at the CDH.
    if r["is_climate_linked"] and r["cdh_link"]:
        links.append({
            "rel": "related",
            "href": r["cdh_link"],
            "title": "CGIAR Climate Data Hub (source of truth for climate layers) [placeholder URL]",
        })

    item = {
        "type": "Feature",
        "stac_version": STAC_VERSION,
        "stac_extensions": [EXT_MOSAIC, EXT_CDH],
        "id": r["id"],
        "geometry": geometry,
        "bbox": bbox,
        "properties": props,
        "collection": code,
        "links": links,
        "assets": assets,
    }
    return item


def _item_bbox_note(r: dict) -> str:
    if r["coverage"] == "national":
        return ("Country-level locator box (dataset covers the whole country); "
                "not the dataset's own extent.")
    if r["coverage"] == "global":
        return "Global/world locator box; not the dataset's own extent."
    return ("Bbox of the canonical landscape delineation, used as a proxy for the "
            "dataset's own (unrecorded) extent.")


def _build_assets(r: dict) -> tuple[dict, str | None]:
    """Returns (assets, access note). Only resolvable URLs become assets: a STAC asset href
    must not be empty, so locations and source notes travel as mosaic:access_note."""
    assets: dict[str, dict] = {}
    primary_media = MEDIA_TYPE.get(r["formats"][0]) if r["formats"] else None

    # Primary asset href: prefer cleaned download_url, then a usable current_location.
    href = r["download_url"]
    if href:
        asset = {
            "href": href,
            "title": "Primary data source",
            "roles": ["data"],
        }
        if primary_media:
            asset["type"] = primary_media
        if r["file_size"] and str(r["file_size"]).strip().isdigit():
            asset["file:size"] = int(r["file_size"])
        assets["data"] = asset

    # Operational pointers that are not resolvable URLs become access notes, not hrefs.
    notes = []
    if r["current_location"]:
        notes.append(f"Current location: {r['current_location']}")
    if r["server_path"]:
        notes.append(f"Server path: {r['server_path']}")
    if r["download_raw"] and not r["download_url"]:
        notes.append(f"Source note: {r['download_raw']}")
    if not notes and not assets:
        notes.append("No download URL or location recorded")
    return assets, " | ".join(notes) or None


def _bbox_to_polygon(bbox: list) -> dict:
    w, s, e, n = bbox
    return {
        "type": "Polygon",
        "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
    }


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")
