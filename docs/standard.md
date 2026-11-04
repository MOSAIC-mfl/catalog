# MOSAIC metadata standard v0.1 — design notes

Santiago Calderón, 30 Oct 2026. Draft for review with Lizeth Llanos and Steven Sotelo.

## 1. Purpose

A MOSAIC record has to let a person — or a program — **find, understand, cite and access** a
resource without opening its files. It also has to describe resources that come from **any
catalogue**: MOSAIC's own records, the CGIAR Climate Data Hub (CDH), and others later. That is why
the model is small at its core and grows through optional blocks.

MOSAIC is its own system. The CDH standard was the main reference, because it is well built and has
solved many of the same problems. It is a guide, not a rule: §6 lists what was taken and where
MOSAIC differs.

## 2. Principles

1. **Find, understand, cite, access.** This is what the minimum guarantees.
2. **Connect, don't duplicate.** A record points to where the data lives.
3. **Global and federated.** The model must hold resources from any catalogue and region.
4. **Standards where they exist.** Use these wherever one applies:

   | What | Standard |
   |---|---|
   | Licences | SPDX |
   | Countries and regions | ISO 3166-1 alpha-3 and UN M49 |
   | Organizations | ROR |
   | People | ORCID |
   | Persistent identifiers | DOI |
   | Relations between resources | DataCite relation types |
   | Dates | ISO 8601 |
   | Linked keywords | AGROVOC |

5. **Nothing invented.** Unknown values stay empty and are reported for a person to complete.
6. **Ask the author only for what a person knows.** Size, format, CRS or bounding box can be read
   from the data, so they are optional. They are still welcome when the data cannot be opened
   (restricted data).
7. **Small first, extensible later.** The minimum is short; everything else goes in optional blocks.

## 3. Levels

| Level | Failure means | Who acts |
|---|---|---|
| Structure (`record.schema.json`) | **Invalid.** The check fails and the record is not published | Whoever edits the record, before merging |
| Minimum (`levels/minimum`) | **Incomplete.** The record goes into `review/minimum_gaps.csv` and is published flagged as incomplete with its completeness score. `publication.include_incomplete: false` hides it instead | Lizeth / the data owner decide: complete, publish incomplete, or withdraw |
| Recommended (`levels/recommended`) | Warning | Improve when possible |
| Profile `mosaic` | Warning. Set `profiles.mosaic.enforce: true` to make it part of the minimum | — |
| Extension blocks | Invalid if malformed or not declared | Whoever edits the record |

The validator also returns a **completeness score** per level: the share of the level's fields that
pass. The API will publish it as a facet, so users can filter for complete records only.

## 4. The minimum and why each field is in it

| Field | Why |
|---|---|
| `id` | Cite and link. Permanent and never reused. MOSAIC keeps `MFL-YYYY-NNN` ([ADR-0003](adr/0003-identifiers.md)) |
| `title`, `description` | Find and understand |
| `resource_type` | Know what it is before opening it (dataset, service, document, software, model) |
| `themes` | Browse and filter. A closed list; the first value is the primary theme. Same role as the CDH `domain`: the 13 MFL themes plus 3 climate themes taken from the CDH domains |
| `keywords` | Find by search: synonyms, other languages, linked AGROVOC terms |
| `geography` | MOSAIC is global, so "what is there for Peru?" is the first question. Not in the CDH minimum |
| `license` | Know whether the data can be reused. An SPDX id when it is a standard licence; otherwise at least the text. The link to the terms is recommended ([ADR-0002](adr/0002-licence.md)) |
| `contacts` | Who to ask. A `licensor` is recommended, not required |
| `citation` or `doi` | Give credit |
| `access` | Never assume that data is open. In CDH an absent `access` means public; in MOSAIC it is always explicit |
| `data` (+ `access_note`) | Reach the resource. Each access point has a `kind` and a `method`. A public resource needs a URL. A restricted or internal one may have no URL, but must then say how to ask for it |

## 5. Data types and access points

Each entry in `data[]` is one way to reach the resource. A resource can have several: an open
download, a page at the source, an Earth Engine asset, or an internal copy. Each access point says
two separate things:

- **`kind`**: what data is behind it (raster, vector, tabular, document, mixed, other). This drives
  the "data type" facet and decides which detail block may be used (`raster`, `vector`, `tabular`,
  `document`).
- **`method`**: how the point is used (download, landing_page, service, request). A `service`
  block requires `method: service`.

They are kept apart because a page at the source still leads to vector data, and an Earth Engine
asset is still a raster. Merging the two would lose the data type of every landing page, which is
most of the schema-1 records. When an access point's `access` differs from the record's, it carries
its own.

### 5.1 Classifying the data for the website filters

The website filters by data type, geometry and "spatial or not". These come from explicit fields:

| Question | Field | Values |
|---|---|---|
| Raster, vector, table, document? | `data[].kind` (minimum) | raster, vector, tabular, document, mixed, other |
| Points, lines or polygons? | `data[].vector.geometry_type` (recommended for vector data) | point, line, polygon, mixed |
| Does a table have coordinates? | `data[].tabular.spatial` (recommended for tables) + `coordinate_columns` / `geometry_column` | true / false |

The values are **written in the record**, whoever finds them out. When an access point is a public
download that can be read, `python -m mosaic_catalog infer` reads the file and fills what is
absent. It lists the filled paths in `derived` and never overwrites a person's value: a
disagreement goes to `review/inference_report.md` instead. When the file cannot be read (a page at
the source, a restricted dataset, or a raster for now), a person fills the value from
`review/classification_gaps.csv`.

An absent value means "not specified". The API shows it as its own filter option, so
nothing has to be written as "unknown". "Spatial" is derived by the API:

- **yes:** raster or vector data, or a table with `spatial: true`;
- **no:** a table with `spatial: false`, or a document;
- **not specified:** anything else.

## 6. What MOSAIC took from the CDH standard, and where it differs

| Taken as a guide | MOSAIC differs |
|---|---|
| A short minimum to find, understand, cite and access | Adds `geography` and an explicit `access`. Uses `themes` instead of `cdh.domain`. The licensor and the link to the licence terms are recommended, not required. No `cdh_schema_version` per record: the version is declared once per catalogue (`mosaic.config.yaml`) |
| Core + named extensions + profiles | Validation levels with a completeness score. The MOSAIC profile can be enforced, but is off by default |
| SPDX, keywords linked to a vocabulary, contact roles | A licence is `{spdx, url, text}`, so a non-standard licence is still recorded. Roles add `host` and `funder` |
| One bounding box or a list of boxes for disjoint areas | Same |
| Authored values win over values derived from the data; no inheritance between records | Same |
| Negative test fixtures | Same idea, with MOSAIC's own Python validator and CI |
| Structures and variables for data cubes | Simpler blocks per data type. A climate extension can hold the cube detail when MOSAIC needs it |

## 7. Reading other catalogues

Each catalogue keeps its own format. `crosswalks/<source>.yaml` says how its records map to a MOSAIC
record, and the API's translator for that source applies it. The CDH crosswalk is the first one.

The CDH crosswalk first showed one gap: MOSAIC had no theme for climate, adaptation or mitigation.
Three themes were added following the CDH domains (`climate`, `climate-adaptation`,
`climate-mitigation`), so every CDH domain now has a MOSAIC theme.

## 8. Open questions

| # | Question | Proposal |
|---|---|---|
| Q1 | ~~Add themes for climate, adaptation and mitigation?~~ | Done: added following the CDH domains (2026-10-30) |
| Q2 | Should `attribution` (a required credit line, as in CDH) be a MOSAIC field? | Yes if a licence requires one (e.g. ODbL); for now it goes in `citation.text` |
| Q3 | Descriptions of the 13 themes | Draft wording in `scripts/build_vocab.py`; Lizeth to confirm |
| Q4 | AGROVOC URIs for the themes | Not added yet: they were not verified |
