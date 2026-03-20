# Contributing

Keep changes small, explicit, and testable.

## Development workflow

1. Update the runtime behavior in `scripts/` only when the skill instructions and references justify it.
2. Keep `SKILL.md` concise and agent-facing. Put detailed reference material in `references/`.
3. When adding a new field type or format:
   - update `scripts/generate_data.py`
   - document it in `references/field-types.md`
   - add or refresh an example config
   - add a regression test
4. Preserve backward compatibility where practical, especially for existing config keys.

## Validation

Install dependencies:

```bash
python -m pip install -r scripts/requirements.txt
```

Run tests:

```bash
python -m unittest discover -s tests -v
```

Run the Belgium evaluation bundle:

```bash
python scripts/run_belgium_evals.py
```

Smoke-test the examples:

```bash
python scripts/generate_data.py --config examples/people-belgium.json --validate-only
python scripts/generate_data.py --config examples/organizations-us.json --validate-only
```

## Content rules

- Treat `references/custom_formats.json` and `references/open_data_sources.json` as curated project memory.
- Do not add speculative formats or undocumented sources.
- Do not expand the skill into anonymization or data-ingestion tooling without an intentional scope change.
