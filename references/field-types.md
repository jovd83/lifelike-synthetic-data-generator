# Field Types

This file documents the supported field types for `scripts/generate_data.py`.

## Native Faker providers

Any Faker provider available on the configured locale can be used directly as a field `type`.

Common examples:

- `first_name`
- `last_name`
- `name`
- `email`
- `company`
- `street_address`
- `city`
- `postcode`
- `phone_number`
- `url`
- `iban`

If a provider accepts keyword arguments, pass them through `params`.

## Built-in structured field types

### `literal`

Always emit the same value.

Example:

```json
{ "name": "country", "type": "literal", "params": { "value": "BE" } }
```

### `choice`

Pick one value from a provided list.

Required params:

- `values`: non-empty array

### `number_int`

Generate an integer in a closed range.

Optional params:

- `min`: default `0`
- `max`: default `100`

### `number_float`

Generate a float in a closed range.

Optional params:

- `min`: default `0`
- `max`: default `100`
- `precision`: number of decimal places, default `2`

### `date_between`

Generate an ISO date string using Faker's relative-date parsing.

Optional params:

- `start_date`: default `-30y`
- `end_date`: default `today`

## Population-aware field types

These field types are meant to be used with top-level `population_model` segments. Those segments can be declared explicitly or derived live through `population_model.source_query`.

For the broader workflow, read `references/population-modeling.md`.

### `segment_value`

Copy a value from the sampled population segment into the row.

Required params:

- `key`: segment key to read

Optional params:

- `default`: fallback value when that key is absent from the segment

Example:

```json
{ "name": "sex", "type": "segment_value", "params": { "key": "sex" } }
```

### `birth_date_from_age_band`

Convert an age band from the sampled population segment into a realistic ISO birth date.

Required params:

- `segment_key`: segment key containing the age band

Optional params:

- `reference_date`: ISO date used to interpret age, defaults to today
- `default_max_age`: upper bound used for open-ended bands such as `65+` or `Y_GE100`
- `bands`: custom mapping for non-standard labels

Supported built-in age-band formats:

- `18-24`
- `65+`
- `Y15T19`
- `Y_GE100`
- `Y_LT5`

Example:

```json
{
  "name": "birth_date",
  "type": "birth_date_from_age_band",
  "params": {
    "segment_key": "age_band",
    "reference_date": "2023-01-01",
    "default_max_age": 105
  }
}
```

### `faker_from_segment`

Choose a Faker provider based on a value from the sampled population segment.

Required params:

- `segment_key`: segment key to inspect
- `providers`: object mapping segment values to Faker provider names

Optional params:

- `fallback_provider`: provider to use when the sampled segment value has no explicit mapping
- `provider_params`: shared kwargs passed to the chosen Faker provider

Example:

```json
{
  "name": "first_name",
  "type": "faker_from_segment",
  "params": {
    "segment_key": "sex",
    "providers": {
      "M": "first_name_male",
      "F": "first_name_female"
    },
    "fallback_provider": "first_name"
  }
}
```

## Belgian synthetic identifiers

### `belgian_insz`

Generates a checksum-valid synthetic INSZ-like value for testing workflows.

### `belgian_eid`

Generates a checksum-valid synthetic Belgian eID-like card number for testing workflows.

## Regex-backed custom formats

If `type` matches a key in `references/custom_formats.json`, the generator uses the configured regex pattern.

Example:

```json
{ "name": "swift_code", "type": "swift_code" }
```

## Backward compatibility

Older configs that use the flat output keys below are still accepted:

- `output_format`
- `output_file`

## Adding a new field type

1. Implement the generator in `scripts/generate_data.py`.
2. Add a short section here with required params and example usage.
3. Add or update an example config in `examples/`.
4. Add a regression test in `tests/test_generate_data.py`.
