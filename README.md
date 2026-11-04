# MOSAIC catalog

> **Status: v0.1.0, branch `metadata-standard-v0.1`, for review.** Phase 1: the metadata standard.
> Phase 2: the 108 MOSAIC records migrated from the first pipeline of this repository (main @
> `0dad25c`), and the build. Phase 3, the API, lives in
> [MOSAIC-mfl/mosaic-api](https://github.com/MOSAIC-mfl/mosaic-api). Published at
> https://mosaic-mfl.github.io/catalog/ once merged into `main`.

MOSAIC is a network of metadata. It describes geospatial and related resources wherever they live
and links to them; it does not copy them. This repository holds three things:

1. **The MOSAIC metadata standard.** JSON Schemas, controlled vocabularies and crosswalks to other
   catalogues.
2. **MOSAIC's own records.** One YAML file per resource, in `records/<id>/record.yaml`.
3. **The build.** It validates the records and publishes them as JSON for `mosaic-api`
   (`dist/catalog.json` + `dist/manifest.json`).
4. **Landscape profiles.** What the page of each living landscape shows (`landscapes/<CODE>/`),
   validated and published with the records. Guide: [`docs/landscape-profiles.md`](docs/landscape-profiles.md).

## The standard in one minute

| Level | What | If it is missing |
|---|---|---|
| **Structure** | Every field has the right shape and uses the vocabularies | **Invalid:** the check fails and must be fixed |
| **Minimum** | Enough to find, understand, cite and access the resource without opening its files | **Incomplete:** listed in `review/minimum_gaps.csv` and published flagged (configurable) |
| **Recommended** | Period, bounding box, licensor, link to the licence terms, linked keywords… | Warning |
| **Profile `mosaic`** | Living landscapes, MFL id | Warning (can be enforced in `mosaic.config.yaml`) |
| **Extensions** | Domain blocks (`soil:`, `biodiversity:`…) declared per record | Invalid if malformed or undeclared |

**The minimum** (`schema/levels/minimum.schema.json`):

- `id`, `title`, `description`, `resource_type`
- `themes`, `keywords`, `geography`
- `license` (SPDX, or at least the text)
- `contacts`
- `citation` or `doi`
- `access` (always explicit)
- `data`: at least one access point, each with its `kind` (data type) and `method` (download,
  landing page, service, request). A **public** resource needs a URL; a
  restricted or internal one needs an `access_note` that says how to obtain it.

Further reading:

- All fields with their level, type, values and equivalents (CDH, schema 1):
  [`docs/fields.xlsx`](docs/fields.xlsx), [`docs/fields.md`](docs/fields.md), and a record with every
  field commented: [`docs/record-reference.yaml`](docs/record-reference.yaml). All three are
  generated from the schemas.
- Why each decision was taken: [`docs/standard.md`](docs/standard.md) and [`docs/adr/`](docs/adr/).

## Layout

```
schema/
  record.schema.json             structure of a record (types, vocabularies)
  levels/minimum.schema.json     level 0
  levels/recommended.schema.json level 1
  profiles/mosaic.schema.json    MOSAIC profile (not enforced in v0.1)
  extensions/_template/          how to add a domain extension
  vocab.schema.json              generated from vocab/
vocab/                           themes, landscapes, geography (ISO 3166 / UN M49), access, data kinds, access methods, roles…
crosswalks/cdh.yaml              how a Climate Data Hub record maps to a MOSAIC record (read direction)
crosswalks/mosaic-schema1.yaml   how the old schema-1 records were migrated
records/<id>/record.yaml         the 108 migrated MOSAIC records
landscapes/<CODE>/               landscape profiles (KEN-LVB: the Lake Victoria Basin Explorer)
schema/landscape/                schemas of the profile files
review/                          minimum_gaps, classification_gaps, migration_notes, inference_report
examples/                        real records converted by hand (999 complete, an example id; 079 and 090 incomplete)
tests/fixtures/                  valid / invalid / incomplete cases the suite checks
src/mosaic_catalog/              validator and CLI
scripts/                         build_vocab.py, build_docs.py, build_reference.py, migrate_schema1.py
mosaic.config.yaml               standard version, enforced profiles, publish incomplete records or not
boundaries/                      landscape delineations (GeoJSON), kept from the first pipeline
docs/history/                    decisions, guides and record changelogs of the first pipeline
legacy/                          Excel registry, schema 1, pending submission, frozen STAC (legacy/README.md)
```

## Use

```sh
pip install -e ".[dev]"                     # Python 3.10+
python -m mosaic_catalog validate examples  # check records (text report)
python -m mosaic_catalog validate examples -v --format json
python -m mosaic_catalog validate records --gaps review/minimum_gaps   # writes the review list
python -m mosaic_catalog infer              # read public downloadable files, fill geometry / spatial (needs pyshp)
python -m mosaic_catalog validate-landscapes # the landscape profiles
python -m mosaic_catalog build              # dist/catalog.json + dist/manifest.json + dist/landscapes/ for the API
pytest -q                                   # tests
python scripts/build_vocab.py               # after editing a vocabulary in the script
python scripts/build_docs.py                # after editing a schema
python scripts/build_reference.py           # docs/fields.xlsx + docs/record-reference.yaml
```

Exit code 1 means at least one record is **invalid**. Incomplete records do not fail the check:
they go to the review list.

Editors with the YAML language server can validate while typing (once the schemas are published):

```yaml
# yaml-language-server: $schema=https://mosaic-mfl.github.io/catalog/schema/v0.1.0/record.schema.json
```

## Rules for changes

- A branch per topic, pull request, green checks (`Validate` runs on every pull request). Lizeth reviews any change to records, the
  standard or the build.
- `vocab/*.json`, `schema/vocab.schema.json` and `docs/fields.md` are generated. Change the script
  or the schema, then regenerate.
- Nothing is invented: what the source does not state stays empty and is reported.

## Migration from the old catalogue (phase 2)

The 108 records were converted from the schema-1 records of this repository's first pipeline
(main @ `0dad25c`, see [`legacy/README.md`](legacy/README.md)) by `scripts/migrate_schema1.py`,
which reads them with `git show 0dad25c:records/...` (`--ref`). Mapping: [`crosswalks/mosaic-schema1.yaml`](crosswalks/mosaic-schema1.yaml).

```sh
python scripts/migrate_schema1.py --source . --ref 0dad25c     # reads the first pipeline; rewrites records/ and review/migration_notes.*
python -m mosaic_catalog validate records --gaps review/minimum_gaps
```

**Results:**

- **108 records migrated** (catalog main @ 0dad25c). None is invalid, and none is complete yet: no schema-1 record has
  keywords, and 92 have no citation.
- **`review/minimum_gaps.csv`** lists what is missing for the minimum, with the person to ask. Its
  `decision` column is for the outcome: complete, publish incomplete, or withdraw.
- **`review/migration_notes.csv`** lists conversions a person should check: licence texts that
  describe access, `NATIONAL`/`GLOBAL` landscapes, periods without a year, and so on.
