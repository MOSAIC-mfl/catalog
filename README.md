# MOSAIC catalog

> **Status: branch `metadata-standard-v0.1`, for review.** 108 records in the MOSAIC metadata
> standard v0.2 and the landscape profiles. Published at https://mosaic-mfl.github.io/catalog/ once
> merged into `main`.

The catalogue of datasets of MOSAIC, the CGIAR Multifunctional Landscapes metadata network. Only
data lives here:

```
records/<id>/record.yaml     one record per dataset (MOSAIC standard v0.2), e.g. records/MFL-2026-079/
landscapes/<CODE>/           what the page of a living landscape shows (profile.yaml; for a map
                             explorer also explorer.yaml, story.yaml, studies.yaml, sources.yaml)
```

Everything else is in other repositories:

| Repository | Holds |
|---|---|
| [mosaic-standard](https://github.com/MOSAIC-mfl/mosaic-standard) | the metadata standard (schemas, vocabularies, crosswalks), the validator and build, examples, docs, review lists |
| [mosaic-api](https://github.com/MOSAIC-mfl/mosaic-api) | harvests this catalogue (and the CGIAR Climate Data Hub) and serves it |
| [website](https://github.com/MOSAIC-mfl/website) | the MOSAIC website |

## Add or change a dataset

1. Copy the template
   ([`docs/record-template.yaml`](https://github.com/MOSAIC-mfl/mosaic-standard/blob/main/docs/record-template.yaml))
   to `records/<id>/record.yaml` (`MFL-YYYY-NNN`, the next free number) and fill it in. Fields and
   levels: [`docs/fields.md`](https://github.com/MOSAIC-mfl/mosaic-standard/blob/main/docs/fields.md).
   Nothing is invented: what the source does not state stays empty.
2. Open a pull request. The **Validate** check runs the standard on every record and profile: an
   invalid record fails it; an incomplete one passes and is listed for review.
3. Once merged into `main`, **Publish** rebuilds the catalogue and the API picks it up.

Not a maintainer? Use the issue form **New dataset** and a maintainer writes the record.

A landscape profile works the same way (`landscapes/<CODE>/`); guide:
[`docs/landscape-profiles.md`](https://github.com/MOSAIC-mfl/mosaic-standard/blob/main/docs/landscape-profiles.md).
MOSAIC team members can write a profile without programming with the Claude Code skill
`mosaic-landscape-profile` (team repository `MOSAIC-mfl/ai-context`).

## Check locally

```sh
git clone https://github.com/MOSAIC-mfl/mosaic-standard.git ../mosaic-standard
pip install -e ../mosaic-standard
python -m mosaic_catalog --catalog . validate              # records
python -m mosaic_catalog --catalog . validate-landscapes   # landscape profiles
python -m mosaic_catalog --catalog . build --out dist      # what the API reads (dist/ is not committed)
```

## Rules for changes

- A branch per topic, pull request, green **Validate**. Lizeth reviews any change to records or
  profiles.
- Changes to the standard (fields, vocabularies, levels) go to mosaic-standard, not here.
