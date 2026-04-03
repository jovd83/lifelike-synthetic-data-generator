# Persona Template

Use this template when the user wants one or more synthetic people with richer life context rather than flat tabular rows.

This is a design and prompting template for the skill repository. It defines what a future persona-capable workflow should collect and return. It is not yet a fully native `scripts/generate_data.py` config contract.

## Goal

Create one or more synthetic personas that feel coherent across identity, household, biography, lifestyle, digital footprint, and finances while remaining fake and safe for testing, demos, workshops, and simulation.

The user should be able to express:

- how many personas they want
- locale, country, and language preferences
- realism level
- required and forbidden attributes
- demographic or household constraints
- optional sections to include or omit
- narrative depth

## Intake Template

Use this request-shaping template before generating personas:

```yaml
persona_request:
  count: 1
  locale: "en_US"
  country: "US"
  seed: 42
  output_format: "json"
  realism_goal: "lifelike"
  include_sections:
    - identity
    - introduction
    - contact
    - professional
    - lifestyle
    - digital
    - finance
    - biography
  optional_sections:
    - health
    - spouse
    - children
  user_wishes:
    - "single father with two children"
    - "works in cybersecurity"
    - "lives in a large city"
    - "owns a bike but no car"
  avoid:
    - "luxury lifestyle"
    - "celebrity-like profile"
  narrative_style: "grounded, concise, realistic"
```

## Output Contract

Return personas in a structure like this:

```json
{
  "personas": [
    {
      "identity": {
        "full_name": "",
        "first_name": "",
        "last_name": "",
        "gender": "",
        "age": 0,
        "birth_date": "",
        "nationality": "",
        "marital_status": "",
        "num_children": 0,
        "unique_id": "",
        "preferred_pronouns": "",
        "national_id_type": "",
        "national_id_number": ""
      },
      "introduction": "",
      "contact": {
        "email": "",
        "phone_number": "",
        "address": "",
        "city": "",
        "postal_code": "",
        "country": ""
      },
      "professional": {
        "profession": "",
        "job_title": "",
        "company": "",
        "industry": "",
        "education_level": "",
        "income_bracket": ""
      },
      "household_context": {
        "household_size": 0,
        "housing_type": "",
        "ownership_status": "",
        "neighborhood_type": "",
        "commute_style": ""
      },
      "daily_routine": {
        "wake_time": "",
        "work_pattern": "",
        "weekday_rhythm": "",
        "evening_habits": "",
        "weekend_rhythm": ""
      },
      "goals_and_pressures": {
        "short_term_goals": [],
        "long_term_goals": [],
        "current_frustrations": [],
        "financial_pressures": []
      },
      "lifestyle": {
        "hobbies": [],
        "languages_spoken": [],
        "pet": "",
        "values": [],
        "personality_type": "",
        "computer_model": "",
        "smartphone_model": "",
        "tablet_model": "",
        "car_model": "",
        "bike_model": "",
        "tv_brand": "",
        "favorite_tv_show": "",
        "favorite_movie": "",
        "favorite_documentary": "",
        "favorite_vacation_destinations": []
      },
      "shopping_and_brand_preferences": {
        "favorite_supermarkets": [],
        "favorite_clothing_brands": [],
        "favorite_tech_brands": [],
        "buying_habits": "",
        "brand_loyalty": ""
      },
      "media_and_online_behavior": {
        "favorite_apps": [],
        "newsletter_habits": "",
        "streaming_platforms": [],
        "privacy_awareness": "",
        "posting_frequency": ""
      },
      "mobility": {
        "primary_commute_mode": "",
        "driving_frequency": "",
        "public_transport_use": "",
        "travel_frequency": "",
        "travel_style": ""
      },
      "relationships": {
        "family_closeness": "",
        "social_circle_size": "",
        "community_involvement": ""
      },
      "home_and_environment": {
        "home_office_setup": "",
        "cooking_habits": "",
        "plants": "",
        "sustainability_attitudes": ""
      },
      "decision_style": {
        "research_vs_impulse": "",
        "budget_vs_convenience": "",
        "planning_style": ""
      },
      "health": {
        "weight": "",
        "height": "",
        "skin_tone": "",
        "eye_color": "",
        "hair_color": "",
        "fitness_level": "",
        "known_conditions": [],
        "accessibility_needs": []
      },
      "digital": {
        "social_profiles": [],
        "ip_address": "",
        "user_agent": "",
        "device_use": ""
      },
      "finance": {
        "iban": "",
        "bank_name": "",
        "swift_bic": "",
        "income_level": "",
        "preferred_payment_methods": []
      },
      "family": {
        "spouse": null,
        "children": []
      },
      "biography": "",
      "persona_summary_card": {
        "headline": "",
        "life_stage": "",
        "core_traits": [],
        "primary_needs": [],
        "key_constraints": []
      },
      "usage_context": {
        "intended_use_cases": [],
        "scenario_tags": []
      },
      "grounding_note": {
        "format_valid_fields": [],
        "inferred_fields": [],
        "plausible_fields": []
      },
      "red_flags_to_avoid": []
    }
  ]
}
```

## Section Rules

### Identity

Required base fields:

- `full_name`
- `first_name`
- `last_name`
- `gender`
- `age`
- `birth_date`
- `nationality`
- `marital_status`
- `num_children`
- `unique_id`
- `preferred_pronouns`
- `national_id_type`
- `national_id_number`

Rules:

- `national_id_number` must be fake but format-valid when the locale supports it.
- `age` and `birth_date` must agree.
- `marital_status`, `spouse`, and `children` must agree.

### Introduction

Return one short paragraph summarizing who the person is, what defines their current life stage, and what makes them memorable.

### Contact

Required fields:

- `email`
- `phone_number`
- `address`
- `city`
- `postal_code`
- `country`

Rules:

- Contact details should match the chosen locale.
- Email and social handles should plausibly derive from the person's name or interests.

### Professional

Required fields:

- `profession`
- `job_title`
- `company`
- `industry`
- `education_level`
- `income_bracket`

Rules:

- Career should fit age, education, and income.
- Company should be fake but plausible.

### Household Context

Suggested fields:

- `household_size`
- `housing_type`
- `ownership_status`
- `neighborhood_type`
- `commute_style`

Rules:

- Housing should fit income, life stage, and household composition.
- Commute style should fit geography and job pattern.

### Daily Routine

Suggested fields:

- `wake_time`
- `work_pattern`
- `weekday_rhythm`
- `evening_habits`
- `weekend_rhythm`

Rules:

- Routine should reflect age, profession, commute, family status, and health.
- Parents, shift workers, retirees, and students should not all sound the same.

### Goals And Pressures

Suggested fields:

- `short_term_goals`
- `long_term_goals`
- `current_frustrations`
- `financial_pressures`

Rules:

- Goals should fit life stage.
- Financial pressures should align with income, housing, and household size.

### Lifestyle

Suggested fields:

- `hobbies`
- `languages_spoken`
- `pet`
- `values`
- `personality_type`
- `computer_model`
- `smartphone_model`
- `tablet_model`
- `car_model`
- `bike_model`
- `tv_brand`
- `favorite_tv_show`
- `favorite_movie`
- `favorite_documentary`
- `favorite_vacation_destinations`

Rules:

- Possessions and preferences should fit income, age, country, and personality.
- Allow absent values when the item is not relevant.

### Shopping And Brand Preferences

Suggested fields:

- `favorite_supermarkets`
- `favorite_clothing_brands`
- `favorite_tech_brands`
- `buying_habits`
- `brand_loyalty`

Rules:

- Preferences should fit geography, income, and personality.
- Avoid giving every persona premium-brand habits by default.

### Media And Online Behavior

Suggested fields:

- `favorite_apps`
- `newsletter_habits`
- `streaming_platforms`
- `privacy_awareness`
- `posting_frequency`

Rules:

- Online habits should fit age, profession, and digital literacy.
- Privacy-aware personas should not also have implausibly reckless digital habits unless intentionally designed that way.

### Mobility

Suggested fields:

- `primary_commute_mode`
- `driving_frequency`
- `public_transport_use`
- `travel_frequency`
- `travel_style`

Rules:

- Mobility should fit location, income, household, and vehicle ownership.
- Urban personas can plausibly be bike-first or transit-first; rural personas may depend more on cars.

### Relationships

Suggested fields:

- `family_closeness`
- `social_circle_size`
- `community_involvement`

Rules:

- Relationship style should influence routine, hobbies, and biography.

### Home And Environment

Suggested fields:

- `home_office_setup`
- `cooking_habits`
- `plants`
- `sustainability_attitudes`

Rules:

- Home life should fit housing type, work pattern, and lifestyle.

### Decision Style

Suggested fields:

- `research_vs_impulse`
- `budget_vs_convenience`
- `planning_style`

Rules:

- Decision style should influence brand choices, travel style, payment habits, and digital behavior.

### Health

Optional fields:

- `weight`
- `height`
- `skin_tone`
- `eye_color`
- `hair_color`
- `fitness_level`
- `known_conditions`
- `accessibility_needs`

Rules:

- Include only when requested or useful.
- Keep all health information synthetic and non-diagnostic.

### Digital

Suggested fields:

- `social_profiles`
- `ip_address`
- `user_agent`
- `device_use`

Rules:

- URLs must be fake.
- Device usage should fit profession and lifestyle.

### Finance

Suggested fields:

- `iban`
- `bank_name`
- `swift_bic`
- `income_level`
- `preferred_payment_methods`

Rules:

- `iban` should be synthetic and format-valid where supported.
- `swift_bic` and bank name should be fake but plausible.

### Family

If applicable, include:

- same identity basics for spouse
- same identity basics for each child

Suggested spouse or child mini-record:

```json
{
  "full_name": "",
  "first_name": "",
  "last_name": "",
  "gender": "",
  "age": 0,
  "birth_date": "",
  "nationality": "",
  "preferred_pronouns": "",
  "national_id_type": "",
  "national_id_number": ""
}
```

Rules:

- Household ages must be coherent.
- Shared surname, address, and nationality can vary, but the differences should make sense.

### Biography

Return a richer life-story paragraph or short multi-paragraph biography that covers background, education, relationships, work, habits, and current aspirations.

### Persona Summary Card

Suggested fields:

- `headline`
- `life_stage`
- `core_traits`
- `primary_needs`
- `key_constraints`

Use this as a compact one-screen summary for design workshops, stakeholder reviews, or demo fixtures.

### Usage Context

Suggested fields:

- `intended_use_cases`
- `scenario_tags`

Example `scenario_tags`:

- `young_parent`
- `remote_worker`
- `retired`
- `urban_cyclist`
- `high_digital_literacy`

### Grounding Note

Suggested fields:

- `format_valid_fields`
- `inferred_fields`
- `plausible_fields`

Use this to distinguish:

- fields that are format-valid synthetic values
- fields inferred from other choices
- fields that are only plausibility-driven narrative details

### Red Flags To Avoid

Store contradictions or anti-patterns the generator should avoid for this persona, such as:

- luxury spending with low-income profile
- inconsistent family timeline
- location and phone mismatch
- biography contradicting structured fields

## Coherence Checklist

Before considering a persona complete, verify:

- age matches birth date
- profession matches education and income
- household composition matches marital status and child count
- contact details match locale
- devices and vehicles match lifestyle and income
- favorites and hobbies feel internally consistent
- introduction and biography do not contradict structured fields
- education, jobs, moves, marriage, and children fit the person's age and timeline
- income, housing, vacations, subscriptions, devices, and transport choices fit the economic profile
- address, phone, language, bank details, shopping habits, and media preferences fit the locale
- spouse and children, when present, affect routine, housing, spending, and long-term goals
- decision style is reflected in shopping, travel, finance, and digital behavior

## Specific-Wishes Prompt Pattern

When the user has strong preferences, gather them in this pattern:

```yaml
specific_wishes:
  demographic:
    age_range: "35-45"
    gender: "female"
    nationality: "Belgian"
  household:
    marital_status: "married"
    children: 2
  geography:
    city_type: "suburban"
    country: "Belgium"
  work:
    industry: "healthcare"
    seniority: "mid-career"
  lifestyle:
    owns_car: false
    owns_bike: true
    pet: "dog"
  tone:
    introduction_style: "warm and practical"
    biography_style: "credible and specific"
```

## Suggested Next Implementation Steps

If this repository is extended to support persona generation natively, the likely next changes are:

1. Add a persona-oriented config contract, either as a new top-level mode or a dedicated example schema.
2. Add structured field generators for narrative text, household members, and correlated possessions.
3. Add locale-aware synthetic spouse and child generators.
4. Add correlation helpers for housing, mobility, digital behavior, shopping preferences, and decision style.
5. Add regression tests for persona coherence, optional sections, and cross-field contradictions.
6. Add one or more runnable examples under `examples/`.

## Natural-Language Request Translation

The repository now includes `scripts/translate_persona_request.py`, a lightweight translator that turns plain-language persona wishes into a runnable persona config.

Current scope:

- Belgium-oriented persona config translation
- request-language-aware Belgian locale resolution, for example `fr_FR` requests resolve to `fr_BE`
- practical Belgian Dutch and Belgian French phrase handling for common persona wishes
- Belgian geography and commute phrase handling for cities, regions, and mobility cues such as Brussels, Antwerp, Flanders, Wallonia, train commuting, and bike-first mobility
- Belgian housing and household phrase handling for renter vs owner, apartment vs house, and living-alone vs family-style household cues
- work-pattern phrase handling for hybrid, remote, shift-based, self-employed, and civil-service style requests
- life-stage phrase handling for student, starter, mid-career, pre-retirement, and retired personas, including Belgian age-band steering
- archetype inference from phrases such as `privacy-conscious urban parent` and `budget-conscious commuter`
- simple wish extraction for children count, marital status, neighborhood type, pet, vehicle ownership, and broad industry hints

Example request file:

- `examples/persona-request-belgium.json`
