# Landscape profiles

Every living landscape has a page on the MOSAIC website: `/landscapes/<code>/` (for example
`/landscapes/ken-lvb/`). What the page shows is written here, in this repository, and validated like
the records.

- **No folder for a landscape:** its page has the default sections (`mosaic.config.yaml`,
  `landscapes.default_sections`: overview, datasets in the catalogue, data status). All 11
  landscapes have a page this way, with nothing written.
- **`landscapes/<CODE>/profile.yaml`:** the landscape's own page, curated. It lists its sections in
  order. A section can be a core module or a module of its own.

```
landscapes/KEN-LVB/
  profile.yaml     the page: title, summary, status, sections, credits
  explorer.yaml    a map explorer section: data locations, base map, layers, panels, click, about
  story.yaml       its story (chapters that move the map), optional
  studies.yaml     its study cards (verified findings, explore questions), optional
  sources.yaml     source, licence, citation and caveats of each layer, optional
```

The heavy data (map tiles, GeoTIFFs, series) **is not copied here**. It stays where its author serves
it (GitHub Pages, Hugging Face…). `explorer.yaml` only says where each file lives; the visitor's
browser reads them from there.

## Check and publish

```sh
python -m mosaic_catalog validate-landscapes        # every landscape: OK / ERR, and why
python -m mosaic_catalog validate-landscapes KEN-LVB -v
python -m mosaic_catalog build                      # also writes dist/landscapes/index.json + <CODE>.json
```

The checks go beyond the schemas (`schema/landscape/*.schema.json`):

- the folder name is the landscape code, and the code exists in `vocab/landscapes.json`;
- every overlay, toggle and panel belongs to a group of the rail, and its `before` layer exists;
- every layer a toggle switches exists in the base map;
- every overlay a story chapter or a study card names exists;
- every catalogue record named (`record: mosaic:MFL-…`) exists;
- the data routes point to declared roots, and no path leaves its folder;
- a published study card has its finding, citation and the verified claims.

A kind of section or overlay the website does not know is a **warning**, not an error: the website
must register it first (see mosaic-web, `docs/landscape-profiles.md`).

## Sections

| `kind` | What it shows | Configuration |
|---|---|---|
| `overview` | datasets, completeness, countries, code | none |
| `map-explorer` | a map explorer (layers, time, panels, story, studies) | `source: explorer.yaml` |
| `catalogue-datasets` | the catalogue's datasets for the landscape | none |
| `data-status` | what the catalogue holds and what the records still lack | none |

## Map explorer (explorer.yaml)

| Block | Content |
|---|---|
| `data` | `roots` (name → base URL), `default_root`, `routes` (prefix or path → root), `withheld` (never requested), `tiles_version`, `report` |
| `map` | camera and limits, `terrain`, `sky`, `glyphs`, and the base map as MapLibre `sources` and `layers` (files as `{asset: path}` or `{pmtiles: path}`) |
| `groups` | the rail groups, in order |
| `toggles` | switch base layers on and off (place names, admin boundaries, rivers) |
| `panels` | side panels opened from the rail (`kind: series-summary`: KPIs and the monthly chart of a series) |
| `overlays` | the layers people choose, one at a time; `kind` picks the renderer, `inspect` what a click shows |
| `click` | what a click shows with no overlay (place, administrative unit) |
| `story`, `studies`, `about` | the files above |

Overlay kinds: `raster-tiles` (one PMTiles raster, or `variants` switched in the legend),
`year-tiles` (one raster per year, optionally points per year), `climate-grid` (yearly and seasonal
climate stacks with anomalies and a cell panel), `index-grid` (a monthly index such as SPI-3).
Click kinds: `cell-sum`, `class-at-point`, `annual-series`, `region-series`, and the ones a profile
plugin adds (KEN-LVB: `flood-query`).

## A new profile

1. Create `landscapes/<CODE>/profile.yaml` with the sections you want. Without a map explorer,
   that is all.
2. For a map explorer, start from `landscapes/KEN-LVB/explorer.yaml`: change `data`, the camera, the
   base map and the overlays. The same renderers draw any data of the same kind.
3. `python -m mosaic_catalog validate-landscapes <CODE>`.
4. Only when the profile needs something no module does yet (a new kind of layer, a click on a data
   format of its own), the website adds a module or a profile plugin. The rest is configuration.

## Lake Victoria (KEN-LVB)

The profile was converted from the Lake Victoria Basin Explorer by Andrés Aguilar
(https://github.com/anaguilarar/mosaic-lake-victoria, commit 0d22fe2) with
`scripts/migrate_lake_victoria.py`. The explorer's repository is only read. Its own JSON files
(`layers.json`, `story_chapters.json`, `studies.json`) are converted as they are; what it kept in
JavaScript (layers, legends, map style, colours) is transcribed in the script, so the profile shows
exactly what the explorer shows.

Its layers are not catalogue records yet: `review/landscape_KEN-LVB_sources.md` lists them for the
team to register. Licences to confirm before publishing: the ICPAC basin boundary (not specified:
withheld), DAHITI lake levels (non-commercial), HydroSHEDS rivers (display only).
