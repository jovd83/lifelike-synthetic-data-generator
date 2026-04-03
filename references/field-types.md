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

## Common field controls

Any field can optionally define a `when` object to make generation conditional.

Simple example:

```json
{
  "name": "spouse",
  "type": "object",
  "when": {
    "path": "identity.marital_status",
    "op": "eq",
    "value": "married"
  },
  "params": {
    "fields": [
      { "name": "full_name", "type": "name" }
    ]
  }
}
```

Supported condition operators:

- `eq`
- `neq`
- `gt`
- `gte`
- `lt`
- `lte`
- `in`
- `not_in`
- `exists`
- `truthy`
- `falsy`

Compound conditions are also supported through:

- `all`
- `any`
- `not`

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

Optional params:

- `weights`: positive-number array aligned to `values`

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

### `child_birth_date_from_parent`

Generate a child's birth date while respecting both the child's age range and the parent's age-at-birth range.

Required params:

- `parent_birth_date_field`

Optional params:

- `reference_date`: defaults to today
- `min_child_age`: default `0`
- `max_child_age`: default `25`
- `min_parent_age_at_birth`: default `16`
- `max_parent_age_at_birth`: default `60`
- `profile`: optional row-scoped sibling profile key
- `min_spacing_days`: optional minimum spacing to the previous child in the same profile, default `0`
- `max_spacing_years_between_siblings`: optional maximum spacing to the previous child in the same profile, default `10`

This is useful for persona family sections where child ages should remain plausible relative to the generated parent.

### `birth_date_relative_to_field`

Generate a birth date relative to another generated birth date, while still respecting an absolute age range at the chosen reference date.

Required params:

- `anchor_birth_date_field`

Optional params:

- `min_years_offset`: default `-5`
- `max_years_offset`: default `5`
- `min_age`: default `18`
- `max_age`: default `92`
- `reference_date`: defaults to today

This is useful for spouse or partner generation when ages should stay near the main persona instead of drifting arbitrarily.

### `age_from_birth_date`

Derive an integer age from an already generated ISO birth date field.

Required params:

- `field`: field name or dotted path to a previously generated birth-date value

Optional params:

- `reference_date`: ISO date used to calculate the age, defaults to today

Example:

```json
{
  "name": "age",
  "type": "age_from_birth_date",
  "params": {
    "field": "birth_date",
    "reference_date": "2026-01-01"
  }
}
```

### `pronouns_from_gender`

Derive a pronoun string from an already generated gender field.

Required params:

- `field`: field name or dotted path to the gender value

Current mappings:

- `F` or `female`-like values -> `she/her`
- `M` or `male`-like values -> `he/him`

### `complementary_gender`

Derive the opposite binary gender code from an already generated gender field.

Required params:

- `field`: field name or dotted path to the source gender value

Current mappings:

- `F` or `female`-like values -> `M`
- `M` or `male`-like values -> `F`

### `faker_from_field`

Choose a Faker provider from another already generated field value in the same row or nested object.

Required params:

- `field`
- `providers`: object mapping resolved field values to Faker provider names

Optional params:

- `fallback_provider`
- `provider_params`

This is especially useful for nested persona fields such as spouse first names that should follow a generated spouse gender instead of the top-level sampled population segment.

### `life_timeline`

Generate a chronological list of synthetic life events from an already generated persona profile.

Required params:

- `birth_date_field`: field name or dotted path to the persona's birth date

Optional params:

- `reference_date`
- `full_name_field`
- `education_level_field`
- `profession_field`
- `company_field`
- `marital_status_field`
- `spouse_field`
- `children_field`
- `city_field`

Output shape:

- array of event objects with `date`, `category`, `title`, and `description`

Notes:

- The timeline is heuristic and plausibility-driven, not source-backed by default.
- Child birth events are grounded in generated child birth dates when those exist.
- The generator now also adds secondary-education, expanded-responsibility, independent-household, and household-routine events when the profile supports them.
- Events are returned in chronological order.
- Event `title` values stay stable for downstream logic, while `description` text follows the row locale when available, including `nl_*` and `fr_*`.

Example:

```json
{
  "name": "life_timeline",
  "type": "life_timeline",
  "params": {
    "birth_date_field": "identity.birth_date",
    "full_name_field": "identity.full_name",
    "education_level_field": "professional.education_level",
    "profession_field": "professional.job_title",
    "company_field": "professional.company",
    "marital_status_field": "identity.marital_status",
    "spouse_field": "family.spouse",
    "children_field": "family.children",
    "city_field": "contact.city",
    "reference_date": "2026-01-01"
  }
}
```

### `catalog_choice`

Choose a locale-aware value from the curated persona catalogs in `references/persona_catalogs.json`.

Required params:

- `catalog`

Optional params:

- `return`: key to return from the matched entry, defaults to `value`
- `profile`: optional cache key that makes multiple `catalog_choice` fields reuse the same matched catalog entry within one row
- `locales`: explicit locale priority list; defaults to the config locale and country code
- `filters`: static catalog filters
- `filter_from_fields`: map catalog keys to previously generated row fields

Notes:

- This is intended for banks, supermarkets, telcos, streaming services, and other curated lifestyle vocabularies.
- Use `profile` when one weighted entry should drive several coherent outputs, such as job title plus industry or TV show plus movie preferences.
- It complements source-backed `source_model` rules by providing reviewed locale-specific defaults.

Example:

```json
{
  "name": "bank_name",
  "type": "catalog_choice",
  "params": {
    "catalog": "banks",
    "filters": {
      "country": "BE",
      "segment": "mainstream"
    }
  }
}
```

### `belgian_address_component`

Choose one value from a cached synthetic Belgian address profile backed by the curated BOSA-derived address catalog.

Required params:

- `component`: one of `street_address`, `postcode`, `city`, `province`, `region`, or `locality_size`

Optional params:

- `profile`
- `region`
- `province`
- `postcode_prefix`
- `city`
- `region_segment_key`
- `locality_min_size`
- `locality_max_size`

Notes:

- Fields that share the same `profile` reuse the same sampled locality, so city, postcode, province, and region stay aligned.
- `locality_min_size` and `locality_max_size` can bias generation toward larger or smaller localities while staying grounded in the Belgian address catalog.

### `belgian_bank_account_component`

Generate a coherent synthetic Belgian bank-account component from the bundled bank catalog.

Required params:

- `component`: one of `bank_name`, `bank_code`, `swift_bic`, or `iban`

Optional params:

- `profile`: cache key so multiple fields reuse the same generated bank account profile

Use this when `bank_name`, `swift_bic`, and `iban` need to agree instead of being generated independently.

### `profile_bundle`

Choose a precomposed locale-aware profile object from `references/persona_profile_bundles.json`.

Required params:

- `bundle`

Optional params:

- `locales`: explicit locale priority list; defaults to the config locale and country code
- `filters`: static bundle filters
- `filter_from_fields`: map bundle keys to previously generated row fields

Notes:

- This is useful for coherent grouped outputs such as digital, mobility, or household profiles.
- Unlike `catalog_choice`, it returns an object instead of a scalar value.

Example:

```json
{
  "name": "digital",
  "type": "profile_bundle",
  "params": {
    "bundle": "digital_profiles",
    "filters": {
      "segment": "mainstream_family"
    }
  }
}
```

### `biography_from_timeline`

Generate a biography paragraph from an already generated `life_timeline` plus optional profile fields.

Required params:

- `timeline_field`

Optional params:

- `full_name_field`
- `city_field`
- `education_level_field`
- `profession_field`
- `hobbies_field`
- `income_level_field`
- `housing_type_field`
- `ownership_status_field`
- `neighborhood_type_field`
- `children_field`
- `style`
- `styles`

Notes:

- This is intended to keep biography narrative aligned with generated life events.
- It works best when `life_timeline` is generated earlier in the same row.
- Supported styles include `reflective`, `direct`, and `narrative`.
- When `styles` is provided, the generator picks one deterministically from the row content.
- Within a chosen style, the biography rotates through deterministic sentence variants based on row content so bundles feel less templated while staying repeatable.
- When the row locale is `nl_*` or `fr_*`, the generator switches the biography wording into Dutch or French instead of using English-first prose.
- For `nl_*` and `fr_*` locales, common inserted values such as education labels, job titles, industries, and hobby names are also localized inside the generated prose when the generator knows those terms.
- Housing-related fields let the biography mention owner/renter context, home type, and urban/suburban/small-town setting when available.

Example:

```json
{
  "name": "biography",
  "type": "biography_from_timeline",
  "params": {
    "timeline_field": "life_timeline",
    "full_name_field": "identity.full_name",
    "city_field": "contact.city",
    "education_level_field": "professional.education_level",
    "profession_field": "professional.job_title",
    "hobbies_field": "lifestyle.hobbies",
    "income_level_field": "finance.income_level",
    "housing_type_field": "household_context.housing_type",
    "ownership_status_field": "household_context.ownership_status",
    "neighborhood_type_field": "household_context.neighborhood_type",
    "children_field": "family.children"
  }
}
```

### `persona_introduction`

Generate a short locale-aware persona introduction paragraph.

Required params:

- `full_name_field`
- `age_field`
- `profession_field`

Optional params:

- `city_field`
- `industry_field`
- `neighborhood_type_field`

Notes:

- The output follows the row locale when available, including `nl_BE` and `fr_BE`.
- For `nl_*` and `fr_*` locales, common inserted job-title and industry labels are localized inside the rendered introduction when the generator knows those terms.
- This is useful for persona bundles where a hand-written English `template` would otherwise clash with a non-English locale.

Example:

```json
{
  "name": "introduction",
  "type": "persona_introduction",
  "params": {
    "full_name_field": "identity.full_name",
    "age_field": "identity.age",
    "profession_field": "professional.job_title",
    "city_field": "contact.city",
    "industry_field": "professional.industry",
    "neighborhood_type_field": "household_context.neighborhood_type"
  }
}
```

### `daily_routine_profile`

Generate a routine object from life stage, household shape, profession, and commute context.

Required params:

- `age_field`

Optional params:

- `profession_field`
- `work_pattern_field`
- `primary_commute_mode_field`
- `children_count_field`
- `income_bracket_field`
- `sector_type_field`
- `employer_scale_field`

Output shape:

- object with `wake_time`, `work_pattern`, `weekday_rhythm`, `evening_habits`, and `weekend_rhythm`

This is useful when persona routines should respond to age, commuting, and family obligations instead of remaining static literals.

Notes:

- The structural `work_pattern` value stays stable for downstream logic.
- The human-facing routine prose fields such as `weekday_rhythm`, `evening_habits`, and `weekend_rhythm` follow the row locale when available, including `nl_*` and `fr_*`.

### `belgian_language_profile`

Generate a plausible language list from Belgian regional context.

Optional params:

- `region_field`
- `city_field`

Output shape:

- array of spoken languages ordered by expected day-to-day prominence

This is useful for Belgian personas where language combinations should react to Flanders, Brussels, or Wallonia rather than staying static.

### `belgian_education_profile`

Generate a compact Belgian-oriented education profile object from age and optional regional context.

Required params:

- `age_field`

Optional params:

- `region_field`
- `profession_field`

Output shape:

- object with `level`, `institution_type`, and `instruction_language`

This is useful when education should stay coherent with adult life stage, profession hints, and Belgian regional language context.

### `belgian_company_name`

Generate a synthetic but Belgian-feeling employer name from optional regional and industry context.

Optional params:

- `profile`: row-level cache key, defaults to `default`
- `industry_field`
- `region_field`
- `city_field`
- `collar_type_field`
- `work_pattern_field`
- `industry`
- `region`
- `city`
- `collar_type`
- `work_pattern`

Notes:

- This is useful when Belgian persona examples should avoid generic global Faker company names.
- The generator varies legal forms by region and shapes name tokens from the industry when available.
- When a `profile` is reused within the same row, the same employer name is returned consistently.

Example:

```json
{
  "name": "company",
  "type": "belgian_company_name",
  "params": {
    "profile": "employer",
    "industry_field": "industry",
    "region_field": "contact.region",
    "city_field": "contact.city"
  }
}
```

### `belgian_employer_component`

Return one structured attribute from the same Belgian employer profile used for company-name generation.

Required params:

- `component`: one of `company_name`, `legal_form`, `organization_type`, `sector_type`, or `employer_scale`

Optional params:

- `profile`: row-level cache key, defaults to `default`
- `industry_field`
- `region_field`
- `city_field`
- `collar_type_field`
- `work_pattern_field`
- `industry`
- `region`
- `city`
- `collar_type`
- `work_pattern`

Notes:

- This is useful when persona outputs should expose employer shape such as `public sector`, `office-based firm`, or `local SME` without duplicating generator logic.
- Use the same `profile` value across `belgian_company_name` and `belgian_employer_component` fields to keep them aligned within the same row.

Example:

```json
{
  "name": "organization_type",
  "type": "belgian_employer_component",
  "params": {
    "component": "organization_type",
    "profile": "employer",
    "industry_field": "industry",
    "region_field": "contact.region",
    "city_field": "contact.city",
    "collar_type_field": "collar_type",
    "work_pattern_field": "work_pattern"
  }
}
```

### `template`

Render a string using previously generated fields in the current object or root row.

Required params:

- `template`: Python-style format string such as `"{first_name} {last_name}"`

Notes:

- Templates can reference earlier fields in the same object.
- Templates can also reference root fields or nested paths such as `identity.full_name`.

### `object`

Generate a nested JSON object from an ordered list of subfields.

Required params:

- `fields`: non-empty array of nested field definitions

Notes:

- Nested fields are generated in order.
- Later nested fields can reference earlier nested fields through `template` or `age_from_birth_date`.

### `array`

Generate a JSON array by repeating one nested field definition.

Required params:

- `item`: nested field definition used for each array item

Also requires one of:

- `count`: exact non-negative integer item count
- `count_from_field`: previously generated field name or dotted path containing the item count

Notes:

- Useful for hobbies, payment methods, child records, or nested preference lists.
- Array items can be scalars, objects, or values produced by other field types.

## Persona-oriented config helpers

### `correlation_rules`

Top-level `correlation_rules` let the config align related fields after generation conditions are known.

Typical uses:

- set housing based on income
- set commute style based on geography or household shape
- reduce travel spontaneity when children are present

Example:

```json
{
  "correlation_rules": [
    {
      "name": "low_income_mobility",
      "when": {
        "path": "income_bracket",
        "op": "eq",
        "value": "low"
      },
      "assignments": [
        { "path": "mobility.primary_commute_mode", "value": "public transport" },
        { "path": "mobility.car_ownership", "value": false }
      ]
    }
  ]
}
```

Each assignment supports:

- `path`
- either `value`
- or `choices` with optional `weights`

Correlation rules can also use a `source_model` when the output should be grounded in source-derived behavioral segments.

Example with copied source-derived segments:

```json
{
  "correlation_rules": [
    {
      "name": "regional_mobility_pattern",
      "source_model": {
        "segments": [
          {
            "weight": 0.7,
            "values": {
              "neighborhood_type": "suburban",
              "primary_commute_mode": "car",
              "public_transport_use": "occasional"
            }
          },
          {
            "weight": 0.3,
            "values": {
              "neighborhood_type": "suburban",
              "primary_commute_mode": "train",
              "public_transport_use": "frequent"
            }
          }
        ],
        "match_on": [
          { "path": "household_context.neighborhood_type", "segment_key": "neighborhood_type" }
        ],
        "assign_from_segment": [
          { "path": "mobility.primary_commute_mode", "segment_key": "primary_commute_mode" },
          { "path": "mobility.public_transport_use", "segment_key": "public_transport_use" }
        ]
      }
    }
  ]
}
```

`source_model` supports either:

- `segments`: copied source-derived weighted segments
- `source_query`: the same live query shape used by `population_model.source_query`

Additional keys:

- `filters`: optional static subset filter on the source-derived segments
- `match_on`: row fields used to select relevant source-derived segments
- `assign_from_segment`: segment values to project back into the persona

### `archetypes`

Top-level `archetypes` apply curated named overlays from `references/persona_archetypes.json`.

They are useful when the user asks for a recognizable persona style such as:

- `privacy-conscious-urban-parent`
- `budget-conscious-commuter`

Each archetype can stamp coordinated values across digital behavior, mobility, routine, finance, or shopping preferences.

Simple example:

```json
{
  "archetypes": [
    "privacy-conscious-urban-parent"
  ]
}
```

Conditional example:

```json
{
  "archetypes": [
    {
      "name": "budget-conscious-commuter",
      "when": {
        "path": "professional.income_bracket",
        "op": "eq",
        "value": "low"
      }
    }
  ]
}
```

### `contradiction_checks`

Top-level `contradiction_checks` fail generation when a persona violates an explicit realism rule.

Example:

```json
{
  "contradiction_checks": [
    {
      "name": "low_income_luxury_car",
      "when": {
        "all": [
          { "path": "income_bracket", "op": "eq", "value": "low" },
          { "path": "car_model", "op": "eq", "value": "Porsche 911" }
        ]
      },
      "message": "low-income persona should not own a luxury sports car"
    }
  ]
}
```

Contradiction checks can also include `timeline_assertions` for event-level validation.

Supported timeline assertion types:

- `event_exists`
- `ordered_events`
- `minimum_age_at_event`
- `maximum_age_at_event`
- `minimum_gap_between_events`

Example:

```json
{
  "contradiction_checks": [
    {
      "name": "career_after_education",
      "timeline_assertions": [
        {
          "type": "ordered_events",
          "timeline_field": "life_timeline",
          "first_event": {
            "category": "education"
          },
          "second_event": {
            "category": "career",
            "title": "Current role"
          },
          "allow_same_day": false
        },
        {
          "type": "minimum_age_at_event",
          "timeline_field": "life_timeline",
          "event": {
            "category": "career",
            "title": "Career start"
          },
          "birth_date_field": "identity.birth_date",
          "min_age": 16
        }
      ],
      "message": "timeline contains implausible career sequencing"
    }
  ]
}
```

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

### `faker_from_field`

Choose a Faker provider based on a previously generated field value instead of a sampled population segment.

Required params:

- `field`: field name or dotted path to inspect
- `providers`: object mapping field values to Faker provider names

Optional params:

- `fallback_provider`: provider to use when the source field value has no explicit mapping
- `provider_params`: shared kwargs passed to the chosen Faker provider

Example:

```json
{
  "name": "first_name",
  "type": "faker_from_field",
  "params": {
    "field": "gender",
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

Behavior:

- Uses the persona birth date for digits 1-6 (`YYMMDD`) when it can resolve a nearby or configured birth-date field.
- Uses an odd sequence number for male values and an even sequence number for female values when it can resolve gender.
- Applies the Belgian checksum rule, including the post-2000 `2` prefix in the checksum calculation.

Optional params:

- `birth_date_field`: explicit field path to an ISO birth date
- `gender_field`: explicit field path to a gender value such as `M` or `F`

If these params are omitted, the generator first looks for sibling fields such as `birth_date` and `gender`, then falls back to root-level `identity.birth_date` and `identity.gender`.

Example:

```json
{
  "name": "national_id_number",
  "type": "belgian_insz",
  "params": {
    "birth_date_field": "identity.birth_date",
    "gender_field": "identity.gender"
  }
}
```

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
