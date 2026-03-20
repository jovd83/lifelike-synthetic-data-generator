# Lifelike Synthetic Data Generator

An Agent Skill and reference repository for generating realistic synthetic datasets for tests, demos, sandboxes, seed data, and workflow simulations.

The skill translates user requirements into a validated generation config, then runs a bundled Python CLI to produce CSV, JSON, NDJSON, or SQL output. It supports locale-aware Faker providers, curated regex-backed custom formats, seeded repeatability, Belgian-specific identifiers such as INSZ and eID, optional population-shaping through weighted distribution segments, and simple schema-driven SQL generation from `CREATE TABLE` statements.

## What This Repository Contains

This repository includes both:

- the runtime-critical skill assets used by an AI agent
- the GitHub-facing documentation, examples, tests, and contribution materials needed to maintain the skill professionally

Core runtime assets:

- `SKILL.md`
- `agents/openai.yaml`
- `scripts/generate_data.py`
- `references/`

Support assets for maintainers and adopters:

- `examples/`
- `tests/`
- `evals/`
- `CONTRIBUTING.md`

## Responsibilities

This skill is responsible for:

- turning user requirements into a structured synthetic-data config
- validating that config before generation
- generating realistic but fake records to disk
- previewing results in a machine-friendly and agent-friendly way
- documenting supported formats, examples, and extension paths

This skill is not responsible for:

- anonymizing real production datasets
- scraping or cloning live public registries into output files
- maintaining cross-agent shared memory infrastructure
- automatically self-modifying its references without explicit maintainer intent

## Key Features

- Versioned config model with JSON schema reference
- Seeded deterministic runs when repeatability matters
- CSV, JSON, NDJSON, and SQL output
- Structured CLI result summary with preview rows
- Optional population-representativeness layer with weighted segments and subset filters
- Live source-query mode for deriving segments from public datasets at generation time
- Summary reporting for what is and is not distribution-backed
- Segment-aware field types for consistent values such as sex-aligned first names and age-backed birth dates
- Simple SQL schema parsing from `CREATE TABLE` DDL when you want SQL `INSERT` output
- Curated regex-backed custom formats
- Belgian-specific synthetic identifiers
- Example configs for common scenarios
- Tests and trigger-eval prompts for ongoing maintenance

## Install

Add the skill with a compatible Agent Skills client:

```bash
npx skills add jovd83/lifelike-synthetic-data-generator
```

Or clone it into a local skills directory:

```bash
git clone https://github.com/jovd83/lifelike-synthetic-data-generator.git
```

Typical local locations include:

- `~/.agents/skills/`
- `~/.cursor/skills/`
- tool-specific local skill directories supported by your agent platform

## Quick Start

Install the Python dependencies:

```bash
python -m pip install -r scripts/requirements.txt
```

Validate an example config:

```bash
python scripts/generate_data.py --config examples/people-belgium.json --validate-only
```

Generate the dataset:

```bash
python scripts/generate_data.py --config examples/people-belgium.json
```

The script writes the output file defined in the config and prints a JSON summary to stdout with a preview of generated rows.

Generate SQL seed data from a schema-driven config:

```bash
python scripts/generate_data.py --config examples/people-belgium-sql.json
```

## Config Model

The preferred config format is versioned and explicit:

```json
{
  "version": "1.0",
  "locale": "nl_BE",
  "records": 10,
  "seed": 42,
  "output": {
    "format": "csv",
    "path": "artifacts/people-belgium.csv"
  },
  "fields": [
    { "name": "first_name", "type": "first_name" },
    { "name": "last_name", "type": "last_name" },
    { "name": "insz", "type": "belgian_insz" }
  ]
}
```

Reference assets:

- field catalog: `references/field-types.md`
- config schema: `references/schema-config.schema.json`
- reusable regex formats: `references/custom_formats.json`
- representativeness workflow: `references/population-modeling.md`
- source catalog: `references/open_data_sources.json`

Representative datasets can also include a `population_model` block:

```json
{
  "population_model": {
    "scope": {
      "country": "BE",
      "level": "nuts3",
      "code": "BE100",
      "reference_year": 2023
    },
    "filters": {
      "sex": ["F"]
    },
    "dimensions": [
      { "name": "sex" },
      { "name": "age_band" }
    ],
    "segments": [
      {
        "weight": 0.42,
        "values": {
          "sex": "F",
          "age_band": "Y18T44"
        }
      }
    ]
  }
}
```

That model can be as small or as large as the user needs. If the user only cares about sex balance, model only sex. If they also care about age, geography, education, or income, add only those dimensions and report the resulting coverage explicitly.

When a supported public source is available, `population_model` can use `source_query` instead of hard-coded segments. See `examples/people-brussels-representative-live.json` for a live Statbel-backed example.

Legacy config keys (`output_format`, `output_file`) are still accepted for backward compatibility.

## SQL Output And Known Schemas

If you know the target table schema, the skill can now generate SQL `INSERT` output directly.

Two workflows are supported:

- Explicit field mapping:
  Keep using `fields` and set `output.format` to `sql`.
- Schema-derived fields:
  Provide `sql_schema.ddl` or `sql_schema.ddl_path` with a simple `CREATE TABLE` statement and let the skill derive fields automatically.

Example:

```json
{
  "records": 6,
  "locale": "nl_BE",
  "seed": 42,
  "sql_schema": {
    "ddl": "CREATE TABLE customer_profiles (first_name VARCHAR(100), last_name VARCHAR(100), email VARCHAR(255), postal_code VARCHAR(10), mobile_phone VARCHAR(20), active BOOLEAN, loyalty_points INTEGER);"
  },
  "output": {
    "format": "sql",
    "path": "artifacts/customer_profiles.sql"
  }
}
```

This parser is intentionally simple. It is designed for straightforward `CREATE TABLE` statements and common column types, not full vendor-specific SQL dialect coverage.

## Data Sources

The skill can consult or be configured against the following curated public sources. In practice, they serve different purposes: some are strong enough to shape representative distributions, while others are better for locality realism, geography, or address-like formatting.

| Source | Scope | Representative strength | Best for | Typical use in this skill |
| --- | --- | --- | --- | --- |
| `Statbel Open Data API` | Belgium | Primary | Age, sex, geography, nationality, education, employment, unemployment, income quintiles, occupation status | First choice for Belgium-specific distribution-backed synthetic datasets |
| `Statbel Open Data Files and Geographic Downloads` | Belgium | Supporting | Population grids, density-aware geography, statistical sectors, NUTS mappings, REFNIS normalization | Add spatial spread and Belgian code/geography consistency |
| `Eurostat` | EU | Primary | Cross-country comparability, regional education, labour-market mix, income and social indicators | Use when the target scope is EU-wide or cross-country rather than only Belgium |
| `Belgian Open Data Portal` | Belgium | Supporting | Discovery of Belgian municipal, locality, mobility, environment, and administrative datasets | Find supporting Belgian open data beyond Statbel, then combine with stronger statistics if needed |
| `WorldPop` | Global | Supporting | Gridded population density, spatial weighting, subnational spread | Make dense cities more likely than sparse rural areas and support realistic locality weighting |
| `GeoNames` | Global | Supporting | Place names, locality vocabularies, geographic hierarchies, admin-code normalization | Improve locality realism and hierarchy consistency |
| `OpenAddresses` | Global | Supporting | Address formatting, street-level vocabulary | Make addresses look realistic without claiming population representativeness |
| `World Bank Data` | Global | Supporting | Macro-economic context, national demographic context | Add country-level context, not person-level demographic sampling |

### Notes per source

- `Statbel Open Data API`: strongest current source for Belgian distribution-backed dimensions.
- `Statbel Open Data Files and Geographic Downloads`: especially helpful when postcode-level or grid-level density matters.
- `Eurostat`: strong for region-level and country-level distributions, weaker for street or postcode realism.
- `Belgian Open Data Portal`: mainly a catalog-discovery surface rather than a direct representative population source.
- `WorldPop`: strong for spatial weighting, not a replacement for official demographic distributions.
- `GeoNames`: strong for hierarchical place realism, not enough on its own for population-weighted sampling.
- `OpenAddresses`: useful for structural address realism, not for proving density.
- `World Bank Data`: useful for macro context, not direct synthetic person-level representativeness.

### Practical selection guidance

- If the request is Belgian and distribution-backed: start with `Statbel Open Data API`.
- If the request needs EU comparability: use `Eurostat`.
- If the request needs dense-city versus rural spread: add `WorldPop` or Statbel geographic files.
- If the request needs realistic place names or hierarchy mappings: add `GeoNames`.
- If the request needs realistic-looking addresses: add `OpenAddresses` and/or `data.gov.be` discoveries.
- If the request only needs a few represented dimensions: only model those dimensions to save tokens and complexity.
- Always report which dimensions are truly distribution-backed and which remain only lifelike.

## Repository Layout

```text
agents/
  openai.yaml
evals/
  trigger-eval-queries.json
examples/
  organizations-us.json
  people-belgium.json
  people-brussels-representative.json
  people-brussels-representative-live.json
references/
  custom_formats.json
  field-types.md
  open_data_monitoring.json
  open_data_sources.json
  population-modeling.md
  schema-config.schema.json
scripts/
  check_open_data_updates.py
  generate_data.py
  refresh_open_data_monitoring.py
  requirements.txt
tests/
  test_generate_data.py
CHANGELOG.md
CONTRIBUTING.md
README.md
SKILL.md
```

## Quality and Evaluation

Validation and maintenance surfaces included in this repository:

- `tests/test_generate_data.py`: CLI and generation regression coverage
- `tests/test_belgium_evals.py`: Belgium-focused evaluation harness coverage
- `evals/trigger-eval-queries.json`: realistic prompts for skill-trigger evaluation
- `evals/belgium_experiments.py`: fifteen Belgium-focused realism and statistical experiments, including zipcode, degree, occupation, car-brand, and exact-age cases
- `examples/`: representative configs for manual smoke testing

Run the tests:

```bash
python -m unittest discover -s tests -v
```

Generate the Belgium HTML evaluation bundle:

```bash
python scripts/run_belgium_evals.py
```

Export the experiment suite into the `skill-creator` evaluation workspace and render the `skill-creator` static review HTML:

```bash
python scripts/export_skill_creator_eval_review.py
```

Check whether new public Statbel datasets or schema changes appeared since the stored snapshot:

```bash
python scripts/check_open_data_updates.py --source-id statbel-open-data-api
python scripts/check_open_data_updates.py --source-id data-gov-be
python scripts/check_open_data_updates.py --source-id eurostat-api
python scripts/check_open_data_updates.py --source-id geonames
python scripts/check_open_data_updates.py --source-id worldpop
python scripts/check_open_data_updates.py --source-id world-bank-data
```

Refresh the stored monitoring baseline from the live official catalogs:

```bash
python scripts/refresh_open_data_monitoring.py
```

## Optional Integrations

The curated source list in `references/open_data_sources.json` is an optional realism aid for maintainers. It is meant to guide distribution shaping and source selection, not to imply that live ingestion is fully automated for every dataset.

Cross-agent memory is intentionally out of scope for this repository. If you need that capability, integrate with a dedicated shared-memory skill rather than expanding this skill into infrastructure it does not own.
