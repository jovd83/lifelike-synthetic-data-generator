---
name: lifelike-synthetic-data-generator
metadata:
  dispatcher-layer: information
  dispatcher-lifecycle: active
  author: jovd83
  version: 2.3.0
  dispatcher-category: testing
  dispatcher-capabilities: synthetic-data-generation, dataset-shaping, seeded-data-generation
  dispatcher-accepted-intents: generate_test_data, generate_seed_data, generate_synthetic_dataset
  dispatcher-input-artifacts: schema_config, persona_request, data_requirements, output_constraints
  dispatcher-output-artifacts: synthetic_dataset, generation_config, preview_report
  dispatcher-stack-tags: data-generation, test-data, locale-aware
  dispatcher-risk: medium
  dispatcher-writes-files: true
description: Use when you need realistic or population-shaped synthetic datasets for tests, demos, sandboxes, seed data, CSV/JSON exports, or API/database fixtures, especially when the schema includes locale-aware personal or company fields, repeatable seeded generation, regex-backed custom formats, Belgian-specific identifiers such as INSZ and eID, or distribution-backed sampling across dimensions like age, sex, geography, education, or income. This skill turns user requirements into a validated config and runs the bundled generator instead of fabricating large datasets in the model context.
---

## Telemetry & Logging
> [!IMPORTANT]
> All usage of this skill must be logged via the Skill Dispatcher to ensure audit logs and wallboard analytics are accurate:
> `./log-dispatch.cmd --skill <skill_name> --intent <intent> --reason <reason>` (or `./log-dispatch.sh` on Linux)

# Lifelike Synthetic Data Generator

Generate realistic but fake records through the bundled script. Prefer this skill when the user needs structured synthetic data that should be repeatable, validated, and saved to disk.

## Available assets

- `scripts/generate_data.py`: Validates config, generates records, writes CSV/JSON/NDJSON, and returns a machine-readable summary.
- `scripts/translate_persona_request.py`: Translates plain-language persona wishes into a runnable persona config.
- `scripts/check_open_data_updates.py`: Compares live public-data discovery endpoints against the stored monitoring snapshot.
- `scripts/refresh_open_data_monitoring.py`: Refreshes the stored monitoring snapshot from live discovery endpoints.
- `references/schema-config.schema.json`: Versioned config schema for editors, validation, and examples.
- `references/field-types.md`: Supported field types, parameters, and extension guidance.
- `references/persona-template.md`: Maintainer template for richer synthetic personas with household, biography, and lifestyle detail.
- `references/custom_formats.json`: Curated project-local registry of reusable regex-backed formats.
- `references/open_data_sources.json`: Curated project-local list of public sources for shaping realism.
- `references/open_data_monitoring.json`: Stored discovery snapshot for detecting newly public data or schema drift.
- `references/population-modeling.md`: How to shape datasets to real-world distributions and how to document what is and is not distribution-backed.
- `examples/*.json`: Ready-to-run schema examples.

## Dispatcher Integration

Use `skill-dispatcher` as the preferred integration layer when another skill needs realistic data generation.

- Accept dispatcher-led handoffs for intents such as `generate_test_data`, `generate_seed_data`, or `generate_synthetic_dataset`.
- Prefer explicit schemas, seeds, and output constraints in the handoff payload so this skill can stay deterministic and auditable.
- Keep shared memory outside this skill except for stable cross-project policy supplied by another skill.
- Treat direct sibling-skill references as a fallback only when dispatcher routing is unavailable.

## Workflow

1. Clarify the request.
   Collect the entity type, record count, output format, locale, required fields, realism constraints, and whether the user needs deterministic output.
   Ask whether the user wants merely lifelike rows or a population-representative dataset.
   If representativeness matters, pin down:
   - the geographic scope
   - the subset filters, if any
   - exactly which dimensions must match real-world distributions
   - which dimensions can remain merely plausible

2. Build a config file.
   Prefer the versioned structure documented in `references/schema-config.schema.json`.
   If repeatability matters, set an explicit `seed`.
   If a field is already supported by Faker, use that provider name directly.
   If a field needs a custom regex-backed format, look for it in `references/custom_formats.json`.
   If the dataset must be representative, read `references/population-modeling.md` and add a `population_model` with:
   - `scope` metadata describing the covered population
   - optional `filters` for subsets such as only men, only elderly people, or one city
   - `dimensions` that document which distributions are intentionally grounded in source data
   - either weighted `segments` or a live `source_query` that derives those segments from public data

   Prefer `source_query` when a supported public table can be queried directly and you want the config to stay current without hand-copying distribution weights.

3. Validate before generating.
   Run:

   ```bash
   python scripts/generate_data.py --config path/to/config.json --validate-only
   ```

   Fix config issues before generating output.

4. Generate the dataset.
   Run:

   ```bash
   python scripts/generate_data.py --config path/to/config.json
   ```

   The script writes the output file and prints a JSON summary to stdout, including a preview.

5. Report the result.
   Share:
   - what you generated
   - key assumptions
   - if applicable, which dimensions are distribution-backed and which are not
   - the output file path
   - a short preview table
   - the next refinement options

   If the user is asking for richer persona-style output rather than flat rows, first consult `references/persona-template.md` to structure the request and make clear whether you are producing a design template, a structured persona JSON artifact, or extending the runtime generator itself.

6. When maintaining the source catalog, check for newly public data.
   Run:

   ```bash
   python scripts/check_open_data_updates.py --source-id statbel-open-data-api
   python scripts/check_open_data_updates.py --source-id data-gov-be
   python scripts/check_open_data_updates.py --source-id eurostat-api
   python scripts/check_open_data_updates.py --source-id geonames
   python scripts/check_open_data_updates.py --source-id worldpop
   python scripts/check_open_data_updates.py --source-id world-bank-data
   ```

   Use the JSON report to decide whether `references/open_data_sources.json` or `references/open_data_monitoring.json` needs a maintainer update.

7. Refresh the monitoring baseline when you intentionally accept the live catalog as the new baseline.
   Run:

   ```bash
   python scripts/refresh_open_data_monitoring.py
   ```

## Gotchas

- A polished output is not automatically population-representative. Only describe the dataset as representative for the dimensions that are explicitly source-backed in `population_model`.
- Output is only deterministic when a `seed` is set. Without a seed, reruns may change values, ordering, and preview rows.
- `metadata.version` in this `SKILL.md` is the skill version, while config `"version"` in generated dataset configs is the generator config version. They are related to different contracts.
- Public data sources in `references/open_data_sources.json` should shape distributions, vocabularies, or formats. Do not copy public rows directly into generated output.
- Persona bundles can still contain partially English or canonical display values if the selected fields or catalogs are not locale-aware. Check the rendered artifact, not just the raw JSON preview, when locale quality matters.
- `--validate-only` catches many schema and config mistakes early. Skipping validation is one of the easiest ways to waste time on generation runs that were never going to succeed.
- `references/custom_formats.json` and `references/open_data_sources.json` are curated project assets, not scratch space. Only update them intentionally during maintainer work or when the user explicitly asks to extend the skill.

## Response contract

When using this skill, answer with:

1. A one-paragraph summary of the generated dataset and any assumptions.
2. The output path and format.
3. A preview table of a few rows rather than dumping raw file contents.
4. A short note about determinism when a `seed` was or was not used.
5. If `population_model` is used, a concise representativeness note based on the generated summary.
6. Suggested next edits if the user wants refinements.

## Guardrails

- Do not fabricate large datasets directly in the model context. Always use the script.
- Do not describe output as deterministic unless a `seed` is set.
- Do not automatically mutate project memory files. `references/custom_formats.json` and `references/open_data_sources.json` are curated assets, not autonomous scratchpads.
- Only update those project-local references when the user explicitly asks to extend the skill or when you are doing maintainer work inside the skill repository.
- Do not copy rows from public datasets into generated output. Use public sources only to shape distributions, vocabularies, or formats.
- Do not claim a dataset is population-representative in general when only a subset of dimensions is source-backed. Be explicit about the covered dimensions.
- Do not silently assume the source catalog is current. For maintainer work, run the update check instead of guessing whether new data is available.
- Treat sensitive-looking identifiers as synthetic format emulation for testing, not as a license to support fraud, impersonation, or deceptive use.

## Memory model

- Runtime memory:
  Keep the current schema decisions, assumptions, validation notes, and preview observations in the active thread only.

- Project-local persistent memory:
  Use `references/custom_formats.json` and `references/open_data_sources.json` as reviewed, auditable skill-local memory. Promote information here only when it is stable and broadly useful for future executions of this skill.

- Shared memory:
  Keep cross-agent or cross-repository memory out of this skill. If broader reuse is needed, integrate with a separate shared-memory skill instead of embedding that infrastructure here.

## Extension rules

When adding support for a new field type:

1. Update `scripts/generate_data.py`.
2. Document the field in `references/field-types.md`.
3. Add or update an example config in `examples/`.
4. Add a regression test in `tests/`.
5. Only then add a reusable pattern to `references/custom_formats.json` if it is stable enough to keep.