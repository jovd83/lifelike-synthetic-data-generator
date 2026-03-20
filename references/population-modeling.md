# Population Representativeness

Read this file when the user asks for a dataset that should reflect a real population rather than merely contain plausible-looking rows.

## Lifelike vs representative

- Lifelike means each row looks plausible on its own.
- Representative means selected dimensions are intentionally shaped to match a source-backed distribution.
- Keep the modeled dimensions as small as the user needs. If the goal is only sex balance, do not spend tokens modeling age, income, geography, and education too.

## Config surface

Use the top-level `population_model` block:

```json
{
  "population_model": {
    "scope": {
      "country": "BE",
      "level": "nuts3",
      "code": "BE100",
      "label": "Brussels-Capital",
      "reference_year": 2023
    },
    "filters": {
      "sex": ["M"]
    },
    "dimensions": [
      {
        "name": "sex",
        "source": {
          "catalog_id": "statbel-open-data-api",
          "dataset": "tf_hvd_demo_population",
          "column": "CD_SEX"
        }
      },
      {
        "name": "age_band",
        "source": {
          "catalog_id": "statbel-open-data-api",
          "dataset": "tf_hvd_demo_population",
          "column": "CD_AGE"
        }
      }
    ],
    "segments": [
      {
        "weight": 0.42,
        "values": {
          "sex": "M",
          "age_band": "Y18T44"
        }
      }
    ]
  }
}
```

Meaning of each key:

- `scope`: metadata only. Use it to document which real population the distribution targets.
- `filters`: optional subset restriction applied before sampling. Use this for requests like only men, only elderly people, or one province.
- `dimensions`: documentation for which dimensions are intentionally source-backed and where they came from.
- `segments`: the actual weighted sampling cells. These are the authoritative target distribution used at generation time.

If you do not want to hand-copy the weighted cells, use `population_model.source_query` to derive them from a live public dataset at generation time.

## Live source queries

Use `source_query` when the source can be queried directly and the config should stay current.

Key fields:

- `catalog_id`: source id from `references/open_data_sources.json`
- `dataset`: source table or endpoint name
- `dimension_columns`: mapping from output dimension names to source column names
- `dimension_value_maps`: optional remapping or bucketing layer before grouping
- `weight_column`: numeric source column to aggregate into weights
- `filters`: source-side filters to narrow scope before grouping

For a full working example, see `examples/people-brussels-representative-live.json`.

## Field types that consume the sampled segment

The generator now supports these population-aware field types:

- `segment_value`: copies a value from the sampled segment into the output row.
- `birth_date_from_age_band`: converts an age band into a realistic birth date.
- `faker_from_segment`: chooses a Faker provider based on a sampled segment value, for example male vs female first names.

These are useful for keeping fields internally consistent with the chosen distribution.

## Summary semantics

When `population_model` is present, the CLI summary includes `representativeness`:

- `distribution_backed_dimensions`: which dimensions were intentionally modeled
- `distribution_backed_fields`: which output fields were directly tied to those dimensions
- `non_distribution_fields`: generated fields that remain merely plausible, not distribution-backed
- `filters`: the subset restriction that was applied

Use that summary in the final answer instead of making broad claims like "fully representative".

## Building a representative population model

1. Choose the geographic scope first.
2. Choose only the dimensions the user actually cares about.
3. Query an official source for that scope.
4. Collapse the source into non-overlapping weighted segments.
5. Add only the fields that need to be distribution-backed.
6. Let the rest remain lifelike unless the user explicitly wants more dimensions modeled.

## Statbel workflow

For Belgium, prefer Statbel first.

Useful entry points:

- API root: `https://opendata-api.statbel.fgov.be`
- Table discovery: `https://opendata-api.statbel.fgov.be/rpc/get_tables_columns`
- Grouped table discovery: `https://opendata-api.statbel.fgov.be/rpc/get_tables_columns_grouped`
- Open data landing page: `https://statbel.fgov.be/en/open-data?category=190&page=0`

Relevant tables in the current API:

- `tf_hvd_demo_population`: strong fit for age, sex, nationality, country of birth, and NUTS3 geography
- `tf_hvd_lfs_employment`: partial fit for employment and education mix
- `tf_hvd_lfs_unemployment`: partial fit for unemployment and education mix
- `tf_hvd_silc_poverty`: partial fit for age, sex, education, occupation status, income quantile, and NUTS2
- `tf_hvd_silc_inequality`: partial fit for age and sex splits around inequality metrics
- `tf_hvd_healthcare_expenditure`: macro health-spending context, not a direct individual health-status distribution

The skill can now:

- query a live Statbel table
- collapse rows into weighted segments
- sample records from those live-derived segments
- report that the segment origin was `source_query`

Example Statbel query for Brussels population by sex and age:

```text
https://opendata-api.statbel.fgov.be/tf_hvd_demo_population?CD_YEAR=eq.2023&CD_NUTS_LVL3=eq.BE100&CD_CNTRY_BTH=eq.TOTAL&CD_NATLTY=eq.TOTAL&CD_PROPERTY=eq.MS_POP&select=CD_SEX,CD_AGE,MS_VALUE
```

Example Statbel query for poverty-related segmentation dimensions:

```text
https://opendata-api.statbel.fgov.be/tf_hvd_silc_poverty?CD_YEAR=eq.2023&CD_SEX=neq.TOTAL&CD_PVRTY_AGE=neq.TOTAL&CD_PROPERTY=eq.MS_RISK_OF_POVERTY&select=CD_SEX,CD_PVRTY_AGE,CD_ISCED_2011,CD_PVRTY_OCPTN_STS,CD_PVRTY_INCM_QNTL,CD_NUTS_LVL2,MS_VALUE
```

## Geography guidance

Population spread is often not well represented by a plain list of addresses.

For Belgium:

- Use `tf_hvd_demo_population` when NUTS3 or arrondissement-level spread is enough.
- Use Statbel geographic files and population grids from the open-data page when density or spatial spread matters more than administrative labels.
- Use `Code REFNIS`, `NUTS codes`, and related nomenclature files to keep geography codes consistent.

## Limits and cautions

- Open data often supports some dimensions strongly and others only indirectly.
- Do not treat healthcare expenditure as a direct proxy for individual health status.
- Do not describe postcode-level address generation as representative unless you actually grounded it in postcode or grid-level population data.
- Do not confuse "all rows are plausible" with "the dataset matches reality on a distribution level".

## Staying up to date

Use the stored monitoring snapshot in `references/open_data_monitoring.json` and run:

```bash
python scripts/check_open_data_updates.py --source-id statbel-open-data-api
python scripts/check_open_data_updates.py --source-id data-gov-be
python scripts/check_open_data_updates.py --source-id eurostat-api
python scripts/check_open_data_updates.py --source-id geonames
python scripts/check_open_data_updates.py --source-id worldpop
python scripts/check_open_data_updates.py --source-id world-bank-data
```

That report will tell you whether new public datasets appeared or whether existing table schemas changed since the last verified snapshot.

To deliberately refresh the stored baseline after review, run:

```bash
python scripts/refresh_open_data_monitoring.py
```
