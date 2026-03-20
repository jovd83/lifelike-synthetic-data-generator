# Changelog

All notable changes to this repository are documented here.

The format follows Keep a Changelog and Semantic Versioning.

## [2.2.0] - 2026-03-19

### Added
- Population-shaped generation through top-level `population_model` segments, subset filters, and representativeness summaries.
- Live `source_query` support for deriving weighted population segments directly from public datasets such as the Statbel Open Data API.
- New population-aware field types: `segment_value`, `birth_date_from_age_band`, and `faker_from_segment`.
- Bundled Belgian address catalog support through `references/belgian_address_catalog.json`.
- New `belgian_address_component` field type for coherent Belgian `street_address`, `postcode`, `city`, `province`, and `region` generation with row-level profile reuse and optional region, province, or postcode-prefix filters.
- Native SQL output support plus simple `CREATE TABLE` schema parsing for schema-driven field derivation.
- `references/population-modeling.md` with guidance for source-backed distribution shaping.
- `examples/people-brussels-representative.json`, grounded in current Statbel population proportions for Brussels-Capital.
- `examples/people-brussels-representative-live.json`, showing a live Statbel-backed representative config.
- `references/open_data_monitoring.json` as a stored discovery snapshot for update detection.
- `scripts/check_open_data_updates.py` for checking newly public datasets and schema drift against the stored snapshot.
- `scripts/refresh_open_data_monitoring.py` for refreshing the stored monitoring baseline from live official catalogs.
- `scripts/run_belgium_evals.py`, `evals/belgium_experiments.py`, and `tests/test_belgium_evals.py` for HTML-based Belgium realism and statistical evaluation experiments.
- Belgium evaluation scenarios that exercise coherent regional and province-filtered address generation.

### Changed
- Expanded `references/open_data_sources.json` into a richer, machine-readable catalog with Statbel-first guidance for Belgium plus monitored data.gov.be, Eurostat, GeoNames, WorldPop, and World Bank discovery metadata.
- Updated `SKILL.md`, `README.md`, and `agents/openai.yaml` to cover representative datasets, live source queries, explicit distribution coverage reporting, and the bundled Belgian address workflow.
- Extended the JSON schema to document `population_model`.

### Fixed
- Taught age-band parsing to handle real Statbel codes such as `Y_GE100`.

## [2.0.0] - 2026-03-18

### Changed
- Rewrote `SKILL.md` around a clearer workflow, response contract, guardrails, and scoped memory model.
- Refactored the generator into a validated CLI with deterministic seeding, preview output, structured JSON summaries, and backward-compatible config normalization.
- Reframed project memory so curated references are maintained deliberately instead of being auto-mutated during normal runs.

### Added
- `agents/openai.yaml` for Agent Skills UI metadata.
- `references/schema-config.schema.json` for the versioned config contract.
- `references/field-types.md` for supported field types and extension guidance.
- `examples/` configs for Belgium-focused people data and US organizations.
- `tests/test_generate_data.py` for regression coverage.
- `evals/trigger-eval-queries.json` for skill trigger evaluation.
- `CONTRIBUTING.md` and `.gitignore` for repository maintainability.

### Fixed
- Corrected the mismatch between the previous "deterministic" claim and the script's unseeded behavior.
- Replaced vague success/error messaging with structured output and explicit validation failures.

## [1.0.0] - 2026-03-17

### Added
- Initial creation of the skill, bundled Python generator, and reference files.
