import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from unittest.mock import patch
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "generate_data.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))

import generate_data  # noqa: E402
import check_open_data_updates  # noqa: E402
import translate_persona_request  # noqa: E402


BELGIAN_BANK_CODES = {
    "KBC Bank": "409",
    "Belfius Bank": "052",
    "ING Belgium": "310",
    "Argenta": "979",
}
BELGIAN_COMPANY_VLG_LEGAL_FORMS = {"BV", "NV", "CommV", "VOF"}
BELGIAN_COMPANY_WAL_LEGAL_FORMS = {"SRL", "SA", "SNC", "SC"}
BELGIAN_COMPANY_PRIVATE_LEGAL_FORMS = BELGIAN_COMPANY_VLG_LEGAL_FORMS | BELGIAN_COMPANY_WAL_LEGAL_FORMS


class FakeUrlopenResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class RawUrlopenResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def find_field_value(config: dict, path: str):
    current_fields = config["fields"]
    parts = path.split(".")
    for index, part in enumerate(parts):
        field = next(field for field in current_fields if field["name"] == part)
        if index == len(parts) - 1:
            return field["params"]["value"]
        current_fields = field["params"]["fields"]


class GenerateDataTests(unittest.TestCase):
    def test_seeded_generation_is_repeatable(self):
        config = {
            "version": "1.0",
            "locale": "en_US",
            "records": 3,
            "seed": 99,
            "output": {"format": "json", "path": "artifacts/test.json"},
            "fields": [
                {"name": "name", "type": "name"},
                {"name": "score", "type": "number_int", "params": {"min": 1, "max": 10}},
            ],
        }

        first = generate_data.generate_dataset(config, custom_formats={})
        second = generate_data.generate_dataset(config, custom_formats={})

        self.assertEqual(first, second)

    def test_custom_regex_format_is_supported(self):
        config = {
            "records": 2,
            "seed": 11,
            "fields": [
                {"name": "swift_code", "type": "swift_code"},
            ],
        }
        custom_formats = {
            "swift_code": {
                "type": "regex",
                "pattern": "^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$",
            }
        }

        first = generate_data.generate_dataset(config, custom_formats=custom_formats)
        second = generate_data.generate_dataset(config, custom_formats=custom_formats)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)
        self.assertIn("swift_code", first[0])

    def test_belgian_insz_aligns_with_birth_date_and_gender_context(self):
        config = {
            "records": 1,
            "seed": 21,
            "fields": [
                {
                    "name": "identity",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "gender", "type": "literal", "params": {"value": "F"}},
                            {"name": "birth_date", "type": "literal", "params": {"value": "1990-02-17"}},
                            {"name": "national_id_number", "type": "belgian_insz"},
                        ]
                    },
                }
            ],
        }

        row = generate_data.generate_dataset(config, custom_formats={})[0]["identity"]
        insz = row["national_id_number"]
        self.assertTrue(insz.startswith("900217-"))
        sequence = int(insz.split("-")[1])
        checksum = int(insz.split("-")[2])
        self.assertEqual(sequence % 2, 0)
        self.assertEqual(checksum, generate_data.compute_belgian_insz_checksum(date(1990, 2, 17), sequence))

    def test_belgian_insz_uses_post_2000_checksum_rule(self):
        config = {
            "records": 1,
            "seed": 22,
            "fields": [
                {"name": "gender", "type": "literal", "params": {"value": "M"}},
                {"name": "birth_date", "type": "literal", "params": {"value": "2014-09-27"}},
                {"name": "national_id_number", "type": "belgian_insz"},
            ],
        }

        row = generate_data.generate_dataset(config, custom_formats={})[0]
        insz = row["national_id_number"]
        self.assertTrue(insz.startswith("140927-"))
        sequence = int(insz.split("-")[1])
        checksum = int(insz.split("-")[2])
        self.assertEqual(sequence % 2, 1)
        self.assertEqual(checksum, generate_data.compute_belgian_insz_checksum(date(2014, 9, 27), sequence))

    def test_email_uses_available_name_context(self):
        config = {
            "records": 1,
            "seed": 7,
            "fields": [
                {"name": "first_name", "type": "literal", "params": {"value": "Anne"}},
                {"name": "last_name", "type": "literal", "params": {"value": "De Smet"}},
                {"name": "email", "type": "email"},
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})
        email = rows[0]["email"]
        self.assertTrue(email.endswith(("@example.com", "@example.org", "@example.net")))
        self.assertRegex(email.split("@", 1)[0], r"(anne|adesmet|annesmet|a?desmet)")

    def test_pronouns_from_gender_aligns_with_gender(self):
        config = {
            "records": 2,
            "seed": 9,
            "fields": [
                {"name": "gender", "type": "choice", "params": {"values": ["F", "M"]}},
                {"name": "preferred_pronouns", "type": "pronouns_from_gender", "params": {"field": "gender"}},
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})
        for row in rows:
            if row["gender"] == "F":
                self.assertEqual(row["preferred_pronouns"], "she/her")
            else:
                self.assertEqual(row["preferred_pronouns"], "he/him")

    def test_complementary_gender_flips_binary_gender(self):
        config = {
            "records": 2,
            "seed": 9,
            "fields": [
                {"name": "gender", "type": "choice", "params": {"values": ["F", "M"]}},
                {"name": "spouse_gender", "type": "complementary_gender", "params": {"field": "gender"}},
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})
        for row in rows:
            if row["gender"] == "F":
                self.assertEqual(row["spouse_gender"], "M")
            else:
                self.assertEqual(row["spouse_gender"], "F")

    def test_birth_date_relative_to_field_stays_within_relative_and_age_bounds(self):
        config = {
            "records": 1,
            "seed": 11,
            "fields": [
                {"name": "birth_date", "type": "literal", "params": {"value": "1988-06-15"}},
                {
                    "name": "spouse_birth_date",
                    "type": "birth_date_relative_to_field",
                    "params": {
                        "anchor_birth_date_field": "birth_date",
                        "min_years_offset": -6,
                        "max_years_offset": 6,
                        "min_age": 30,
                        "max_age": 55,
                        "reference_date": "2026-01-01",
                    },
                },
            ],
        }

        row = generate_data.generate_dataset(config, custom_formats={})[0]
        birth_date = date.fromisoformat(row["birth_date"])
        spouse_birth_date = date.fromisoformat(row["spouse_birth_date"])
        self.assertGreaterEqual(spouse_birth_date, generate_data.shift_years_safe(birth_date, -6))
        self.assertLessEqual(spouse_birth_date, generate_data.shift_years_safe(birth_date, 6))
        spouse_age = generate_data.age_on_date(spouse_birth_date, date(2026, 1, 1))
        self.assertGreaterEqual(spouse_age, 30)
        self.assertLessEqual(spouse_age, 55)

    def test_complementary_gender_mirrors_binary_partner_gender(self):
        config = {
            "records": 2,
            "fields": [
                {"name": "gender", "type": "choice", "params": {"values": ["F", "M"]}},
                {"name": "spouse_gender", "type": "complementary_gender", "params": {"field": "gender"}},
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})
        for row in rows:
            if row["gender"] == "F":
                self.assertEqual(row["spouse_gender"], "M")
            else:
                self.assertEqual(row["spouse_gender"], "F")

    def test_birth_date_relative_to_field_keeps_spouses_in_plausible_age_range(self):
        config = {
            "records": 1,
            "seed": 24,
            "fields": [
                {"name": "birth_date", "type": "literal", "params": {"value": "1988-08-20"}},
                {
                    "name": "spouse_birth_date",
                    "type": "birth_date_relative_to_field",
                    "params": {
                        "anchor_birth_date_field": "birth_date",
                        "min_years_offset": -6,
                        "max_years_offset": 6,
                        "min_age": 30,
                        "max_age": 50,
                        "reference_date": "2026-01-01",
                    },
                },
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})
        birth_date = date.fromisoformat(rows[0]["birth_date"])
        spouse_birth_date = date.fromisoformat(rows[0]["spouse_birth_date"])
        age_gap_days = abs((spouse_birth_date - birth_date).days)
        self.assertLessEqual(age_gap_days, 366 * 6)

    def test_belgian_bank_account_component_keeps_bank_name_bic_and_iban_aligned(self):
        config = {
            "records": 2,
            "seed": 12,
            "fields": [
                {"name": "bank_name", "type": "belgian_bank_account_component", "params": {"profile": "main", "component": "bank_name"}},
                {"name": "bank_code", "type": "belgian_bank_account_component", "params": {"profile": "main", "component": "bank_code"}},
                {"name": "swift_bic", "type": "belgian_bank_account_component", "params": {"profile": "main", "component": "swift_bic"}},
                {"name": "iban", "type": "belgian_bank_account_component", "params": {"profile": "main", "component": "iban"}},
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})
        for row in rows:
            self.assertTrue(row["iban"].startswith("BE"))
            self.assertEqual(row["iban"][4:7], row["bank_code"])
            self.assertGreaterEqual(len(row["swift_bic"]), 8)
            self.assertEqual(row["swift_bic"][4:6], "BE")
            self.assertIn(row["bank_name"], {"KBC Bank", "Belfius Bank", "ING Belgium", "Argenta"})

    def test_child_birth_date_from_parent_respects_parent_age_constraints(self):
        config = {
            "records": 1,
            "seed": 14,
            "fields": [
                {
                    "name": "identity",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "birth_date", "type": "literal", "params": {"value": "1990-06-15"}},
                        ]
                    },
                },
                {
                    "name": "child_birth_date",
                    "type": "child_birth_date_from_parent",
                    "params": {
                        "parent_birth_date_field": "identity.birth_date",
                        "reference_date": "2026-01-01",
                        "min_child_age": 4,
                        "max_child_age": 12,
                        "min_parent_age_at_birth": 26,
                        "max_parent_age_at_birth": 42,
                    },
                },
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})
        parent_birth_date = date.fromisoformat(rows[0]["identity"]["birth_date"])
        child_birth_date = date.fromisoformat(rows[0]["child_birth_date"])
        parent_age_at_birth = child_birth_date.year - parent_birth_date.year - (
            (child_birth_date.month, child_birth_date.day) < (parent_birth_date.month, parent_birth_date.day)
        )
        self.assertGreaterEqual(parent_age_at_birth, 26)
        self.assertLessEqual(parent_age_at_birth, 42)

    def test_child_birth_date_from_parent_can_keep_siblings_plausibly_spaced(self):
        config = {
            "records": 1,
            "seed": 15,
            "fields": [
                {
                    "name": "identity",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "birth_date", "type": "literal", "params": {"value": "1989-04-20"}},
                            {"name": "num_children", "type": "literal", "params": {"value": 2}},
                            {"name": "last_name", "type": "literal", "params": {"value": "Peeters"}},
                        ]
                    },
                },
                {
                    "name": "children",
                    "type": "array",
                    "params": {
                        "count_from_field": "identity.num_children",
                        "item": {
                            "type": "object",
                            "params": {
                                "fields": [
                                    {"name": "first_name", "type": "first_name"},
                                    {"name": "last_name", "type": "template", "params": {"template": "{identity.last_name}"}},
                                    {
                                        "name": "birth_date",
                                        "type": "child_birth_date_from_parent",
                                        "params": {
                                            "parent_birth_date_field": "identity.birth_date",
                                            "profile": "siblings",
                                            "reference_date": "2026-01-01",
                                            "min_child_age": 4,
                                            "max_child_age": 12,
                                            "min_parent_age_at_birth": 27,
                                            "max_parent_age_at_birth": 41,
                                            "min_spacing_days": 540,
                                            "max_spacing_years_between_siblings": 5,
                                        },
                                    },
                                ]
                            },
                        },
                    },
                },
            ],
        }

        row = generate_data.generate_dataset(config, custom_formats={})[0]
        child_birth_dates = sorted(date.fromisoformat(child["birth_date"]) for child in row["children"])
        self.assertEqual(len(child_birth_dates), 2)
        self.assertGreaterEqual((child_birth_dates[1] - child_birth_dates[0]).days, 540)
        self.assertLessEqual(child_birth_dates[1], generate_data.shift_years_safe(child_birth_dates[0], 5))

    def test_child_birth_date_from_parent_can_enforce_sibling_spacing(self):
        config = {
            "records": 1,
            "seed": 18,
            "fields": [
                {
                    "name": "identity",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "birth_date", "type": "literal", "params": {"value": "1987-04-12"}},
                            {"name": "num_children", "type": "literal", "params": {"value": 3}},
                        ]
                    },
                },
                {
                    "name": "children",
                    "type": "array",
                    "params": {
                        "count_from_field": "identity.num_children",
                        "item": {
                            "type": "object",
                            "params": {
                                "fields": [
                                    {
                                        "name": "birth_date",
                                        "type": "child_birth_date_from_parent",
                                        "params": {
                                            "parent_birth_date_field": "identity.birth_date",
                                            "profile": "siblings",
                                            "reference_date": "2026-01-01",
                                            "min_child_age": 5,
                                            "max_child_age": 14,
                                            "min_parent_age_at_birth": 25,
                                            "max_parent_age_at_birth": 42,
                                            "min_spacing_days": 540,
                                            "max_spacing_years_between_siblings": 5,
                                        },
                                    }
                                ]
                            },
                        },
                    },
                },
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})
        child_birth_dates = [date.fromisoformat(child["birth_date"]) for child in rows[0]["children"]]
        self.assertEqual(child_birth_dates, sorted(child_birth_dates))
        for earlier, later in zip(child_birth_dates, child_birth_dates[1:]):
            self.assertGreaterEqual((later - earlier).days, 540)
            self.assertLessEqual((later - earlier).days, 365 * 5 + 2)

    def test_child_birth_date_from_parent_supports_larger_batch_with_reserved_sibling_space(self):
        config = {
            "records": 40,
            "seed": 20260327,
            "population_model": {
                "dimensions": [{"name": "age_band"}],
                "segments": [{"weight": 1.0, "values": {"age_band": "Y35T44"}}],
            },
            "fields": [
                {
                    "name": "identity",
                    "type": "object",
                    "params": {
                        "fields": [
                            {
                                "name": "birth_date",
                                "type": "birth_date_from_age_band",
                                "params": {
                                    "segment_key": "age_band",
                                    "reference_date": "2026-01-01",
                                    "bands": {"Y35T44": {"min_age": 35, "max_age": 44}},
                                },
                            },
                            {"name": "num_children", "type": "literal", "params": {"value": 2}},
                        ]
                    },
                },
                {
                    "name": "children",
                    "type": "array",
                    "params": {
                        "count_from_field": "identity.num_children",
                        "item": {
                            "type": "object",
                            "params": {
                                "fields": [
                                    {
                                        "name": "birth_date",
                                        "type": "child_birth_date_from_parent",
                                        "params": {
                                            "parent_birth_date_field": "identity.birth_date",
                                            "profile": "siblings",
                                            "reference_date": "2026-01-01",
                                            "min_child_age": 6,
                                            "max_child_age": 15,
                                            "min_parent_age_at_birth": 22,
                                            "max_parent_age_at_birth": 42,
                                            "min_spacing_days": 540,
                                            "max_spacing_years_between_siblings": 6,
                                        },
                                    }
                                ]
                            },
                        },
                    },
                },
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})
        self.assertEqual(len(rows), 40)
        for row in rows:
            child_birth_dates = [date.fromisoformat(child["birth_date"]) for child in row["children"]]
            self.assertEqual(child_birth_dates, sorted(child_birth_dates))
            for earlier, later in zip(child_birth_dates, child_birth_dates[1:]):
                self.assertGreaterEqual((later - earlier).days, 540)
                self.assertLessEqual((later - earlier).days, 365 * 6 + 2)

    def test_catalog_choice_returns_locale_aware_value(self):
        config = {
            "records": 3,
            "locale": "nl_BE",
            "seed": 4,
            "fields": [
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
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})
        values = {row["bank_name"] for row in rows}
        self.assertTrue(values.issubset({"KBC Bank", "Belfius Bank", "ING Belgium", "Argenta"}))

    def test_belgian_address_component_can_return_region_and_province_from_same_profile(self):
        config = {
            "records": 1,
            "seed": 5,
            "fields": [
                {"name": "city", "type": "belgian_address_component", "params": {"profile": "home", "component": "city", "province": "Brussels-Capital"}},
                {"name": "province", "type": "belgian_address_component", "params": {"profile": "home", "component": "province", "province": "Brussels-Capital"}},
                {"name": "region", "type": "belgian_address_component", "params": {"profile": "home", "component": "region", "province": "Brussels-Capital"}},
            ],
        }

        row = generate_data.generate_dataset(config, custom_formats={})[0]
        self.assertEqual(row["province"], "Brussels-Capital")
        self.assertEqual(row["region"], "BXL")
        self.assertTrue(row["city"])

    def test_belgian_language_profile_reflects_region(self):
        config = {
            "records": 2,
            "fields": [
                {"name": "region", "type": "choice", "params": {"values": ["WAL", "VLG"]}},
                {"name": "city", "type": "choice", "params": {"values": ["Namur", "Ghent"]}},
                {
                    "name": "languages_spoken",
                    "type": "belgian_language_profile",
                    "params": {"region_field": "region", "city_field": "city"},
                },
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})
        for row in rows:
            if row["region"] == "WAL":
                self.assertEqual(row["languages_spoken"], ["French", "English"])
            else:
                self.assertEqual(row["languages_spoken"], ["Dutch", "French", "English"])

    def test_belgian_address_component_can_filter_from_region_segment(self):
        config = {
            "records": 1,
            "seed": 11,
            "population_model": {
                "dimensions": [{"name": "region"}],
                "segments": [{"weight": 1.0, "values": {"region": "BXL"}}],
            },
            "fields": [
                {"name": "region", "type": "segment_value", "params": {"key": "region"}},
                {
                    "name": "city",
                    "type": "belgian_address_component",
                    "params": {"profile": "home", "region_segment_key": "region", "component": "city"},
                },
                {
                    "name": "province",
                    "type": "belgian_address_component",
                    "params": {"profile": "home", "region_segment_key": "region", "component": "province"},
                },
                {
                    "name": "postcode",
                    "type": "belgian_address_component",
                    "params": {"profile": "home", "region_segment_key": "region", "component": "postcode"},
                },
            ],
        }

        row = generate_data.generate_dataset(config, custom_formats={})[0]
        self.assertEqual(row["region"], "BXL")
        self.assertEqual(row["province"], "Brussels-Capital")
        self.assertTrue(row["city"])
        self.assertTrue(str(row["postcode"]).startswith("1"))

    def test_belgian_education_profile_reflects_age_and_region(self):
        config = {
            "records": 1,
            "fields": [
                {"name": "age", "type": "literal", "params": {"value": 41}},
                {"name": "region", "type": "literal", "params": {"value": "WAL"}},
                {
                    "name": "education_profile",
                    "type": "belgian_education_profile",
                    "params": {"age_field": "age", "region_field": "region"},
                },
            ],
        }

        row = generate_data.generate_dataset(config, custom_formats={})[0]
        self.assertEqual(row["education_profile"]["level"], "Master's degree")
        self.assertEqual(row["education_profile"]["institution_type"], "university")
        self.assertEqual(row["education_profile"]["instruction_language"], "French")

    def test_belgian_education_profile_reflects_profession_hint(self):
        config = {
            "records": 1,
            "fields": [
                {"name": "age", "type": "literal", "params": {"value": 41}},
                {"name": "region", "type": "literal", "params": {"value": "VLG"}},
                {"name": "manual_job", "type": "literal", "params": {"value": "Building Electrician"}},
                {"name": "office_job", "type": "literal", "params": {"value": "Business Analyst"}},
                {
                    "name": "manual_profile",
                    "type": "belgian_education_profile",
                    "params": {"age_field": "age", "region_field": "region", "profession_field": "manual_job"},
                },
                {
                    "name": "office_profile",
                    "type": "belgian_education_profile",
                    "params": {"age_field": "age", "region_field": "region", "profession_field": "office_job"},
                },
            ],
        }

        row = generate_data.generate_dataset(config, custom_formats={})[0]
        self.assertEqual(row["manual_profile"]["level"], "Vocational training")
        self.assertEqual(row["manual_profile"]["institution_type"], "vocational school or adult training")
        self.assertEqual(row["office_profile"]["level"], "Master's degree")
        self.assertEqual(row["office_profile"]["institution_type"], "university")

    def test_belgian_company_name_reuses_profile_and_reflects_flemish_legal_forms(self):
        config = {
            "records": 1,
            "seed": 19,
            "fields": [
                {"name": "region", "type": "literal", "params": {"value": "VLG"}},
                {"name": "city", "type": "literal", "params": {"value": "Ghent"}},
                {"name": "industry", "type": "literal", "params": {"value": "Finance"}},
                {
                    "name": "company",
                    "type": "belgian_company_name",
                    "params": {
                        "profile": "employer",
                        "industry_field": "industry",
                        "region_field": "region",
                        "city_field": "city",
                    },
                },
                {
                    "name": "company_again",
                    "type": "belgian_company_name",
                    "params": {
                        "profile": "employer",
                        "industry_field": "industry",
                        "region_field": "region",
                        "city_field": "city",
                    },
                },
            ],
        }

        row = generate_data.generate_dataset(config, custom_formats={})[0]
        self.assertEqual(row["company"], row["company_again"])
        self.assertTrue(any(row["company"].endswith(f" {suffix}") for suffix in BELGIAN_COMPANY_VLG_LEGAL_FORMS))
        self.assertTrue(
            any(token in row["company"] for token in {"Accountancy", "Finadvies", "Audit", "Kapitaal", "Boekhouding"})
        )

    def test_belgian_company_name_uses_walloon_legal_forms_for_walloon_profiles(self):
        config = {
            "records": 5,
            "seed": 23,
            "fields": [
                {"name": "region", "type": "literal", "params": {"value": "WAL"}},
                {"name": "city", "type": "literal", "params": {"value": "Namur"}},
                {"name": "industry", "type": "literal", "params": {"value": "Construction"}},
                {
                    "name": "company",
                    "type": "belgian_company_name",
                    "params": {
                        "industry_field": "industry",
                        "region_field": "region",
                        "city_field": "city",
                    },
                },
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})
        self.assertTrue(rows)
        self.assertTrue(
            all(any(row["company"].endswith(f" {suffix}") for suffix in BELGIAN_COMPANY_WAL_LEGAL_FORMS) for row in rows)
        )
        self.assertTrue(
            all(
                any(token in row["company"] for token in {"Construction", "Travaux", "Batiment", "Chantiers", "Projets"})
                for row in rows
            )
        )

    def test_belgian_employer_component_marks_teacher_profiles_as_public_sector(self):
        config = {
            "records": 1,
            "seed": 31,
            "fields": [
                {"name": "region", "type": "literal", "params": {"value": "VLG"}},
                {"name": "city", "type": "literal", "params": {"value": "Ghent"}},
                {"name": "industry", "type": "literal", "params": {"value": "Education"}},
                {"name": "collar_type", "type": "literal", "params": {"value": "civil-service"}},
                {"name": "work_pattern", "type": "literal", "params": {"value": "structured daytime schedule"}},
                {
                    "name": "company",
                    "type": "belgian_company_name",
                    "params": {
                        "profile": "employer",
                        "industry_field": "industry",
                        "region_field": "region",
                        "city_field": "city",
                        "collar_type_field": "collar_type",
                        "work_pattern_field": "work_pattern",
                    },
                },
                {
                    "name": "sector_type",
                    "type": "belgian_employer_component",
                    "params": {
                        "component": "sector_type",
                        "profile": "employer",
                        "industry_field": "industry",
                        "region_field": "region",
                        "city_field": "city",
                        "collar_type_field": "collar_type",
                        "work_pattern_field": "work_pattern",
                    },
                },
                {
                    "name": "organization_type",
                    "type": "belgian_employer_component",
                    "params": {
                        "component": "organization_type",
                        "profile": "employer",
                        "industry_field": "industry",
                        "region_field": "region",
                        "city_field": "city",
                        "collar_type_field": "collar_type",
                        "work_pattern_field": "work_pattern",
                    },
                },
                {
                    "name": "employer_scale",
                    "type": "belgian_employer_component",
                    "params": {
                        "component": "employer_scale",
                        "profile": "employer",
                        "industry_field": "industry",
                        "region_field": "region",
                        "city_field": "city",
                        "collar_type_field": "collar_type",
                        "work_pattern_field": "work_pattern",
                    },
                },
                {
                    "name": "legal_form",
                    "type": "belgian_employer_component",
                    "params": {
                        "component": "legal_form",
                        "profile": "employer",
                        "industry_field": "industry",
                        "region_field": "region",
                        "city_field": "city",
                        "collar_type_field": "collar_type",
                        "work_pattern_field": "work_pattern",
                    },
                },
            ],
        }

        row = generate_data.generate_dataset(config, custom_formats={})[0]
        self.assertEqual(row["sector_type"], "public sector")
        self.assertEqual(row["organization_type"], "school network")
        self.assertEqual(row["employer_scale"], "municipal or regional institution")
        self.assertIsNone(row["legal_form"])
        self.assertFalse(any(row["company"].endswith(f" {suffix}") for suffix in BELGIAN_COMPANY_PRIVATE_LEGAL_FORMS))

    def test_belgian_employer_component_marks_childcare_profiles_as_community_sector(self):
        config = {
            "records": 1,
            "seed": 37,
            "fields": [
                {"name": "region", "type": "literal", "params": {"value": "WAL"}},
                {"name": "city", "type": "literal", "params": {"value": "Namur"}},
                {"name": "industry", "type": "literal", "params": {"value": "Childcare"}},
                {"name": "collar_type", "type": "literal", "params": {"value": "white-collar"}},
                {"name": "work_pattern", "type": "literal", "params": {"value": "structured daytime schedule"}},
                {
                    "name": "company",
                    "type": "belgian_company_name",
                    "params": {
                        "profile": "employer",
                        "industry_field": "industry",
                        "region_field": "region",
                        "city_field": "city",
                        "collar_type_field": "collar_type",
                        "work_pattern_field": "work_pattern",
                    },
                },
                {
                    "name": "sector_type",
                    "type": "belgian_employer_component",
                    "params": {
                        "component": "sector_type",
                        "profile": "employer",
                        "industry_field": "industry",
                        "region_field": "region",
                        "city_field": "city",
                        "collar_type_field": "collar_type",
                        "work_pattern_field": "work_pattern",
                    },
                },
                {
                    "name": "organization_type",
                    "type": "belgian_employer_component",
                    "params": {
                        "component": "organization_type",
                        "profile": "employer",
                        "industry_field": "industry",
                        "region_field": "region",
                        "city_field": "city",
                        "collar_type_field": "collar_type",
                        "work_pattern_field": "work_pattern",
                    },
                },
                {
                    "name": "legal_form",
                    "type": "belgian_employer_component",
                    "params": {
                        "component": "legal_form",
                        "profile": "employer",
                        "industry_field": "industry",
                        "region_field": "region",
                        "city_field": "city",
                        "collar_type_field": "collar_type",
                        "work_pattern_field": "work_pattern",
                    },
                },
            ],
        }

        row = generate_data.generate_dataset(config, custom_formats={})[0]
        self.assertEqual(row["sector_type"], "nonprofit or community sector")
        self.assertEqual(row["organization_type"], "community service organization")
        self.assertEqual(row["legal_form"], "ASBL")
        self.assertTrue(row["company"].endswith(" ASBL"))

    def test_catalog_choice_can_filter_from_existing_fields(self):
        config = {
            "records": 3,
            "locale": "nl_BE",
            "seed": 10,
            "fields": [
                {"name": "segment", "type": "literal", "params": {"value": "budget"}},
                {
                    "name": "mobile_provider",
                    "type": "catalog_choice",
                    "params": {
                        "catalog": "telcos",
                        "filters": {
                            "country": "BE"
                        },
                        "filter_from_fields": {
                            "segment": "segment"
                        }
                    }
                }
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})
        self.assertTrue(all(row["mobile_provider"] in {"Mobile Vikings", "BASE"} for row in rows))

    def test_catalog_choice_profile_reuses_same_entry_across_fields(self):
        config = {
            "records": 1,
            "locale": "nl_BE",
            "seed": 10,
            "fields": [
                {
                    "name": "job_title",
                    "type": "catalog_choice",
                    "params": {
                        "catalog": "occupation_profiles",
                        "profile": "occupation",
                        "filters": {
                            "country": "BE"
                        },
                        "return": "job_title"
                    }
                },
                {
                    "name": "industry",
                    "type": "catalog_choice",
                    "params": {
                        "catalog": "occupation_profiles",
                        "profile": "occupation",
                        "filters": {
                            "country": "BE"
                        },
                        "return": "industry"
                    }
                },
                {
                    "name": "collar_type",
                    "type": "catalog_choice",
                    "params": {
                        "catalog": "occupation_profiles",
                        "profile": "occupation",
                        "filters": {
                            "country": "BE"
                        },
                        "return": "collar_type"
                    }
                },
            ],
        }

        row = generate_data.generate_dataset(config, custom_formats={})[0]
        matched_entry = next(
            entry
            for entry in generate_data.load_persona_catalogs()["catalogs"]["occupation_profiles"]
            if entry["job_title"] == row["job_title"]
        )
        self.assertEqual(row["industry"], matched_entry["industry"])
        self.assertEqual(row["collar_type"], matched_entry["collar_type"])

    def test_catalog_choice_supports_regional_belgian_catalogs(self):
        config = {
            "records": 1,
            "locale": "fr_BE",
            "seed": 10,
            "fields": [
                {"name": "region", "type": "literal", "params": {"value": "WAL"}},
                {
                    "name": "preferred_transit_operator",
                    "type": "catalog_choice",
                    "params": {
                        "catalog": "transit_operators",
                        "filters": {
                            "country": "BE"
                        },
                        "filter_from_fields": {
                            "region": "region"
                        }
                    }
                },
                {
                    "name": "preferred_news_brand",
                    "type": "catalog_choice",
                    "params": {
                        "catalog": "news_brands",
                        "filters": {
                            "country": "BE"
                        },
                        "filter_from_fields": {
                            "region": "region"
                        }
                    }
                },
            ],
        }

        row = generate_data.generate_dataset(config, custom_formats={})[0]
        self.assertEqual(row["preferred_transit_operator"], "TEC")
        self.assertIn(row["preferred_news_brand"], {"RTBF", "Le Soir"})

    def test_profile_bundle_returns_object_profile(self):
        config = {
            "records": 2,
            "locale": "nl_BE",
            "seed": 7,
            "fields": [
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
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})
        self.assertTrue(all(isinstance(row["digital"], dict) for row in rows))
        self.assertTrue(all("mobile_provider" in row["digital"] for row in rows))
        self.assertTrue(all("streaming_platform" in row["digital"] for row in rows))

    def test_profile_bundle_can_filter_from_existing_fields(self):
        config = {
            "records": 2,
            "locale": "nl_BE",
            "seed": 3,
            "fields": [
                {"name": "digital_segment", "type": "literal", "params": {"value": "budget_mobile"}},
                {
                    "name": "digital",
                    "type": "profile_bundle",
                    "params": {
                        "bundle": "digital_profiles",
                        "filter_from_fields": {
                            "segment": "digital_segment"
                        }
                    }
                }
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})
        self.assertTrue(all(row["digital"]["mobile_provider"] == "Mobile Vikings" for row in rows))

    def test_translate_persona_request_infers_archetype_and_overrides(self):
        request = {
            "count": 1,
            "locale": "nl_BE",
            "country": "BE",
            "seed": 42,
            "wishes": [
                "privacy-conscious urban parent",
                "works in healthcare",
                "two children",
                "no car",
                "dog",
            ],
        }

        config = translate_persona_request.build_persona_config_from_request(request)

        self.assertIn("privacy-conscious-urban-parent", config["archetypes"])
        self.assertEqual(find_field_value(config, "identity.num_children"), 2)
        self.assertEqual(find_field_value(config, "household_context.neighborhood_type"), "urban")
        self.assertEqual(find_field_value(config, "lifestyle.car_model"), None)
        self.assertEqual(find_field_value(config, "lifestyle.pet"), "dog")
        self.assertEqual(find_field_value(config, "professional.industry"), "Healthcare")

    def test_translate_persona_request_output_validates_with_generator(self):
        request = {
            "count": 1,
            "locale": "nl_BE",
            "country": "BE",
            "wishes": ["budget-conscious commuter", "low income"],
        }

        config = translate_persona_request.build_persona_config_from_request(request)
        normalized = generate_data.normalize_config(config)
        self.assertEqual(normalized["records"], 1)
        self.assertTrue(any(item["name"] == "budget-conscious-commuter" for item in normalized["archetypes"]))

    def test_translate_persona_request_maps_french_request_locale_to_belgian_locale(self):
        request = {
            "count": 1,
            "locale": "fr_FR",
            "country": "BE",
            "wishes": ["privacy-conscious urban parent"],
        }

        config = translate_persona_request.build_persona_config_from_request(request)
        self.assertEqual(config["locale"], "fr_BE")

    def test_translate_persona_request_rejects_non_belgian_country_targets(self):
        request = {
            "count": 1,
            "locale": "fr_FR",
            "country": "FR",
            "wishes": ["privacy-conscious urban parent"],
        }

        with self.assertRaises(generate_data.SkillError):
            translate_persona_request.build_persona_config_from_request(request)

    def test_translate_persona_request_understands_belgian_dutch_phrases(self):
        request = {
            "count": 1,
            "locale": "nl_BE",
            "country": "BE",
            "wishes": [
                "privacybewuste stedelijke ouder",
                "werkt in de zorg",
                "twee kinderen",
                "geen auto",
                "hond",
            ],
        }

        config = translate_persona_request.build_persona_config_from_request(request)
        self.assertIn("privacy-conscious-urban-parent", config["archetypes"])
        self.assertEqual(find_field_value(config, "identity.num_children"), 2)
        self.assertEqual(find_field_value(config, "household_context.neighborhood_type"), "urban")
        self.assertEqual(find_field_value(config, "lifestyle.car_model"), None)
        self.assertEqual(find_field_value(config, "lifestyle.pet"), "dog")
        self.assertEqual(find_field_value(config, "professional.industry"), "Healthcare")

    def test_translate_persona_request_understands_belgian_french_phrases(self):
        request = {
            "count": 1,
            "locale": "fr_BE",
            "country": "BE",
            "wishes": [
                "parent urbain soucieux de la vie privée",
                "travaille dans les soins de santé",
                "deux enfants",
                "sans voiture",
                "chien",
                "faible revenu",
            ],
        }

        config = translate_persona_request.build_persona_config_from_request(request)
        self.assertIn("privacy-conscious-urban-parent", config["archetypes"])
        self.assertEqual(find_field_value(config, "identity.num_children"), 2)
        self.assertEqual(find_field_value(config, "lifestyle.car_model"), None)
        self.assertEqual(find_field_value(config, "lifestyle.pet"), "dog")
        self.assertEqual(find_field_value(config, "professional.industry"), "Healthcare")
        self.assertEqual(find_field_value(config, "professional.income_bracket"), "low")

    def test_translate_persona_request_understands_belgian_city_and_train_commute_hints(self):
        request = {
            "count": 1,
            "locale": "nl_BE",
            "country": "BE",
            "wishes": [
                "woont in Antwerpen",
                "pendelt met de trein",
            ],
        }

        config = translate_persona_request.build_persona_config_from_request(request)
        city_field = translate_persona_request.find_field(config["fields"], "contact.city")
        self.assertEqual(city_field["params"]["city"], "Antwerp")
        self.assertEqual(find_field_value(config, "mobility.primary_commute_mode"), "train")
        self.assertEqual(find_field_value(config, "mobility.public_transport_use"), "frequent")
        self.assertEqual(find_field_value(config, "household_context.commute_style"), "train-based commuter routine")

    def test_translate_persona_request_understands_belgian_region_and_bike_commute_hints(self):
        request = {
            "count": 1,
            "locale": "fr_BE",
            "country": "BE",
            "wishes": [
                "vit en Wallonie",
                "se deplace a velo",
            ],
        }

        config = translate_persona_request.build_persona_config_from_request(request)
        city_field = translate_persona_request.find_field(config["fields"], "contact.city")
        self.assertEqual(city_field["params"]["city"], "Namur")
        self.assertEqual(find_field_value(config, "household_context.neighborhood_type"), "suburban")
        self.assertEqual(find_field_value(config, "mobility.primary_commute_mode"), "bike")

    def test_translate_persona_request_understands_belgian_dutch_housing_and_single_household_hints(self):
        request = {
            "count": 1,
            "locale": "nl_BE",
            "country": "BE",
            "wishes": [
                "huurt een appartement",
                "woont alleen",
            ],
        }

        config = translate_persona_request.build_persona_config_from_request(request)
        self.assertEqual(find_field_value(config, "household_context.ownership_status"), "renter")
        self.assertEqual(find_field_value(config, "household_context.housing_type"), "apartment")
        self.assertEqual(find_field_value(config, "household_context.household_size"), 1)
        self.assertEqual(find_field_value(config, "identity.marital_status"), "single")
        self.assertEqual(find_field_value(config, "identity.num_children"), 0)

    def test_translate_persona_request_understands_belgian_french_housing_and_family_household_hints(self):
        request = {
            "count": 1,
            "locale": "fr_BE",
            "country": "BE",
            "wishes": [
                "proprietaire d'une maison",
                "mariee",
                "deux enfants",
            ],
        }

        config = translate_persona_request.build_persona_config_from_request(request)
        self.assertEqual(find_field_value(config, "household_context.ownership_status"), "owner")
        self.assertEqual(find_field_value(config, "household_context.housing_type"), "house")
        self.assertEqual(find_field_value(config, "household_context.household_size"), 4)
        self.assertEqual(find_field_value(config, "identity.marital_status"), "married")
        self.assertEqual(find_field_value(config, "identity.num_children"), 2)

    def test_translate_persona_request_understands_row_house_hints(self):
        request = {
            "count": 1,
            "locale": "nl_BE",
            "country": "BE",
            "wishes": [
                "huurt een rijwoning",
                "met partner",
            ],
        }

        config = translate_persona_request.build_persona_config_from_request(request)
        self.assertEqual(find_field_value(config, "household_context.ownership_status"), "renter")
        self.assertEqual(find_field_value(config, "household_context.housing_type"), "row house")
        self.assertEqual(find_field_value(config, "identity.marital_status"), "married")

    def test_translate_persona_request_understands_brussels_apartment_cues(self):
        request = {
            "count": 1,
            "locale": "fr_BE",
            "country": "BE",
            "wishes": [
                "loue un appartement bruxellois",
                "saint-gilles",
            ],
        }

        config = translate_persona_request.build_persona_config_from_request(request)
        city_field = translate_persona_request.find_field(config["fields"], "contact.city")
        self.assertEqual(find_field_value(config, "household_context.ownership_status"), "renter")
        self.assertEqual(find_field_value(config, "household_context.housing_type"), "brussels apartment")
        self.assertEqual(find_field_value(config, "household_context.neighborhood_type"), "urban")
        self.assertEqual(city_field["params"]["province"], "Brussels-Capital")
        self.assertIn(city_field["params"]["city"], {"Brussel", "Sint-Gillis"})

    def test_translate_persona_request_understands_hybrid_and_self_employed_work_hints(self):
        request = {
            "count": 1,
            "locale": "nl_BE",
            "country": "BE",
            "wishes": [
                "werkt hybride",
                "zelfstandig consultant",
            ],
        }

        config = translate_persona_request.build_persona_config_from_request(request)
        self.assertEqual(find_field_value(config, "daily_routine.work_pattern"), "hybrid office schedule")
        self.assertEqual(find_field_value(config, "household_context.commute_style"), "structured hybrid commute")
        self.assertEqual(find_field_value(config, "professional.company"), "Self-employed")
        self.assertEqual(find_field_value(config, "professional.job_title"), "Independent Consultant")

    def test_translate_persona_request_understands_french_shift_and_civil_service_hints(self):
        request = {
            "count": 1,
            "locale": "fr_BE",
            "country": "BE",
            "wishes": [
                "travaille en horaires decales",
                "fonctionnaire",
            ],
        }

        config = translate_persona_request.build_persona_config_from_request(request)
        self.assertEqual(find_field_value(config, "daily_routine.work_pattern"), "shift-based schedule")
        self.assertEqual(find_field_value(config, "household_context.commute_style"), "shift-based commute pattern")
        self.assertEqual(find_field_value(config, "professional.company"), "Belgian Public Administration")
        self.assertEqual(find_field_value(config, "professional.industry"), "Public Administration")

    def test_translate_persona_request_understands_student_life_stage_hints(self):
        request = {
            "count": 1,
            "locale": "fr_BE",
            "country": "BE",
            "wishes": [
                "etudiante",
            ],
        }

        config = translate_persona_request.build_persona_config_from_request(request)
        self.assertEqual(config["population_model"]["segments"][0]["values"]["age_band"], "Y18T24")
        self.assertEqual(config["population_model"]["segments"][1]["values"]["age_band"], "Y18T24")
        self.assertEqual(find_field_value(config, "professional.profession"), "Student")
        self.assertEqual(find_field_value(config, "daily_routine.work_pattern"), "study-centered schedule")

    def test_translate_persona_request_understands_retired_life_stage_hints(self):
        request = {
            "count": 1,
            "locale": "nl_BE",
            "country": "BE",
            "wishes": [
                "gepensioneerd",
            ],
        }

        config = translate_persona_request.build_persona_config_from_request(request)
        self.assertEqual(config["population_model"]["segments"][0]["values"]["age_band"], "Y65PL")
        self.assertEqual(find_field_value(config, "professional.profession"), "Retired")
        self.assertEqual(find_field_value(config, "professional.company"), "Retired")
        self.assertEqual(find_field_value(config, "daily_routine.work_pattern"), "retired routine")

    def test_translate_persona_request_understands_divorced_and_co_parenting_household_hints(self):
        request = {
            "count": 1,
            "locale": "nl_BE",
            "country": "BE",
            "wishes": [
                "gescheiden",
                "co-ouderschap",
            ],
        }

        config = translate_persona_request.build_persona_config_from_request(request)
        self.assertEqual(find_field_value(config, "identity.marital_status"), "divorced")
        self.assertEqual(find_field_value(config, "identity.num_children"), 1)
        self.assertEqual(find_field_value(config, "household_context.household_size"), 2)

    def test_translate_persona_request_understands_blended_family_hints(self):
        request = {
            "count": 1,
            "locale": "fr_BE",
            "country": "BE",
            "wishes": [
                "famille recomposee",
            ],
        }

        config = translate_persona_request.build_persona_config_from_request(request)
        self.assertEqual(find_field_value(config, "identity.marital_status"), "married")
        self.assertEqual(find_field_value(config, "identity.num_children"), 2)
        self.assertEqual(find_field_value(config, "household_context.household_size"), 4)

    def test_translate_persona_request_understands_brussels_commune_and_province_hints(self):
        request = {
            "count": 1,
            "locale": "fr_BE",
            "country": "BE",
            "wishes": [
                "vit a Ixelles",
                "region bruxelloise",
            ],
        }

        config = translate_persona_request.build_persona_config_from_request(request)
        city_field = translate_persona_request.find_field(config["fields"], "contact.city")
        self.assertEqual(city_field["params"]["city"], "Elsene")
        self.assertEqual(city_field["params"]["province"], "Brussels-Capital")
        self.assertEqual(find_field_value(config, "household_context.neighborhood_type"), "urban")

    def test_translate_persona_request_understands_metro_and_company_car_hints(self):
        request = {
            "count": 1,
            "locale": "fr_BE",
            "country": "BE",
            "wishes": [
                "metro",
                "voiture de societe",
            ],
        }

        config = translate_persona_request.build_persona_config_from_request(request)
        self.assertEqual(find_field_value(config, "mobility.primary_commute_mode"), "metro")
        self.assertEqual(find_field_value(config, "mobility.public_transport_use"), "frequent")
        self.assertEqual(find_field_value(config, "lifestyle.car_model"), "BMW iX1 company car")

    def test_translate_persona_request_understands_cargo_bike_hints(self):
        request = {
            "count": 1,
            "locale": "nl_BE",
            "country": "BE",
            "wishes": [
                "bakfiets",
            ],
        }

        config = translate_persona_request.build_persona_config_from_request(request)
        self.assertEqual(find_field_value(config, "lifestyle.bike_model"), "Urban Arrow Family")
        self.assertEqual(find_field_value(config, "mobility.primary_commute_mode"), "cargo bike")
        self.assertEqual(find_field_value(config, "household_context.commute_style"), "cargo-bike household routine")

    def test_translate_persona_request_understands_part_time_and_developer_work_hints(self):
        request = {
            "count": 1,
            "locale": "nl_BE",
            "country": "BE",
            "wishes": [
                "deeltijds",
                "ontwikkelaar",
            ],
        }

        config = translate_persona_request.build_persona_config_from_request(request)
        self.assertEqual(find_field_value(config, "daily_routine.work_pattern"), "part-time schedule")
        self.assertEqual(find_field_value(config, "professional.industry"), "Software")
        self.assertEqual(find_field_value(config, "professional.job_title"), "Software Engineer")

    def test_translate_persona_request_understands_colloquial_belgian_phrasing(self):
        request = {
            "count": 1,
            "locale": "fr_BE",
            "country": "BE",
            "wishes": [
                "vit solo en ville",
                "a son compte",
            ],
        }

        config = translate_persona_request.build_persona_config_from_request(request)
        self.assertEqual(find_field_value(config, "identity.marital_status"), "single")
        self.assertEqual(find_field_value(config, "household_context.neighborhood_type"), "urban")
        self.assertEqual(find_field_value(config, "professional.company"), "Self-employed")

    def test_translate_persona_request_adds_translation_metadata_for_ambiguity_and_confidence(self):
        request = {
            "count": 1,
            "locale": "nl_BE",
            "country": "BE",
            "wishes": [
                "single",
                "married",
                "geen auto",
                "bedrijfswagen",
            ],
        }

        config = translate_persona_request.build_persona_config_from_request(request)
        metadata = config["translation_metadata"]
        self.assertEqual(metadata["locale_resolution"]["locale"], "nl_BE")
        self.assertGreaterEqual(len(metadata["ambiguities"]), 2)
        self.assertLess(metadata["confidence"], 0.8)
        self.assertIn("mobility", metadata["matched_signals"])

    def test_archetype_applies_named_overlay(self):
        config = {
            "records": 1,
            "locale": "nl_BE",
            "seed": 5,
            "archetypes": [
                "privacy-conscious-urban-parent"
            ],
            "fields": [
                {
                    "name": "digital",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "privacy_awareness", "type": "literal", "params": {"value": "moderate"}},
                            {"name": "posting_frequency", "type": "literal", "params": {"value": "high"}}
                        ]
                    }
                },
                {
                    "name": "mobility",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "public_transport_use", "type": "literal", "params": {"value": "occasional"}},
                            {"name": "travel_style", "type": "literal", "params": {"value": "spontaneous weekends"}}
                        ]
                    }
                },
                {
                    "name": "daily_routine",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "evening_habits", "type": "literal", "params": {"value": "open-ended evenings"}}
                        ]
                    }
                }
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})
        row = rows[0]
        self.assertEqual(row["digital"]["privacy_awareness"], "high")
        self.assertEqual(row["digital"]["posting_frequency"], "low")
        self.assertEqual(row["mobility"]["public_transport_use"], "frequent")

    def test_conditional_archetype_only_applies_when_condition_matches(self):
        config = {
            "records": 1,
            "locale": "nl_BE",
            "seed": 2,
            "archetypes": [
                {
                    "name": "budget-conscious-commuter",
                    "when": {
                        "path": "professional.income_bracket",
                        "op": "eq",
                        "value": "low"
                    }
                }
            ],
            "fields": [
                {
                    "name": "professional",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "income_bracket", "type": "literal", "params": {"value": "upper-middle"}}
                        ]
                    }
                },
                {
                    "name": "shopping_and_brand_preferences",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "favorite_supermarket", "type": "literal", "params": {"value": "Delhaize"}}
                        ]
                    }
                }
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})
        self.assertEqual(rows[0]["shopping_and_brand_preferences"]["favorite_supermarket"], "Delhaize")

    def test_sql_schema_derives_fields_from_simple_create_table(self):
        config = generate_data.normalize_config(
            {
                "records": 2,
                "locale": "nl_BE",
                "sql_schema": {
                    "ddl": "CREATE TABLE customer_profiles (first_name VARCHAR(100), last_name VARCHAR(100), email VARCHAR(255), postal_code VARCHAR(10), mobile_phone VARCHAR(20), active BOOLEAN, loyalty_points INTEGER);"
                },
                "output": {"format": "sql"},
            }
        )

        self.assertEqual(config["sql_schema"]["table_name"], "customer_profiles")
        self.assertEqual([field["name"] for field in config["fields"]], ["first_name", "last_name", "email", "postal_code", "mobile_phone", "active", "loyalty_points"])
        self.assertEqual(config["fields"][0]["type"], "first_name")
        self.assertEqual(config["fields"][3]["type"], "belgian_postal_code")
        self.assertEqual(config["fields"][4]["type"], "belgian_mobile_phone")
        self.assertEqual(config["fields"][6]["type"], "number_int")
        self.assertEqual(config["output"]["table_name"], "customer_profiles")

    def test_sql_schema_uses_sql_type_for_date_columns(self):
        config = generate_data.normalize_config(
            {
                "records": 1,
                "locale": "nl_BE",
                "sql_schema": {
                    "ddl": "CREATE TABLE audit_log (created_on DATE, updated_at TIMESTAMP, label VARCHAR(30));"
                },
            }
        )

        self.assertEqual(config["fields"][0]["type"], "date_between")
        self.assertEqual(config["fields"][1]["type"], "date_between")

    def test_sql_output_writes_insert_script(self):
        rows = [
            {"first_name": "Anne", "active": True, "loyalty_points": 12},
            {"first_name": "O'Hara", "active": False, "loyalty_points": 7},
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "customers.sql"
            generate_data.write_output(
                rows,
                "sql",
                output_path,
                output_options={"table_name": "customer_profiles"},
            )
            script = output_path.read_text(encoding="utf-8")

        self.assertIn('INSERT INTO "customer_profiles"', script)
        self.assertIn("'Anne'", script)
        self.assertIn("'O''Hara'", script)
        self.assertIn("TRUE", script)
        self.assertIn("FALSE", script)

    def test_choice_requires_values(self):
        config = {
            "records": 1,
            "fields": [
                {"name": "industry", "type": "choice", "params": {}},
            ],
        }

        with self.assertRaises(generate_data.SkillError):
            generate_data.generate_dataset(config, custom_formats={})

    def test_choice_can_use_weights(self):
        config = {
            "records": 50,
            "seed": 7,
            "fields": [
                {"name": "segment", "type": "choice", "params": {"values": ["rare", "common"], "weights": [1, 9]}},
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})
        values = [row["segment"] for row in rows]
        self.assertGreater(values.count("common"), values.count("rare"))

    def test_choice_rejects_invalid_weights(self):
        config = {
            "records": 1,
            "fields": [
                {"name": "industry", "type": "choice", "params": {"values": ["a", "b"], "weights": [1]}},
            ],
        }

        with self.assertRaises(generate_data.SkillError):
            generate_data.generate_dataset(config, custom_formats={})

    def test_nested_persona_fields_support_object_template_array_and_age(self):
        config = {
            "records": 1,
            "locale": "en_US",
            "seed": 12,
            "fields": [
                {
                    "name": "identity",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "first_name", "type": "literal", "params": {"value": "Alex"}},
                            {"name": "last_name", "type": "literal", "params": {"value": "Morgan"}},
                            {
                                "name": "full_name",
                                "type": "template",
                                "params": {"template": "{first_name} {last_name}"},
                            },
                            {"name": "birth_date", "type": "literal", "params": {"value": "1990-06-15"}},
                            {
                                "name": "age",
                                "type": "age_from_birth_date",
                                "params": {"field": "birth_date", "reference_date": "2026-01-01"},
                            },
                            {"name": "num_children", "type": "literal", "params": {"value": 2}},
                        ]
                    },
                },
                {
                    "name": "family",
                    "type": "object",
                    "params": {
                        "fields": [
                            {
                                "name": "children",
                                "type": "array",
                                "params": {
                                    "count_from_field": "identity.num_children",
                                    "item": {
                                        "type": "object",
                                        "params": {
                                            "fields": [
                                                {"name": "role", "type": "literal", "params": {"value": "child"}},
                                                {"name": "status", "type": "literal", "params": {"value": "dependent"}},
                                            ]
                                        },
                                    },
                                },
                            }
                        ]
                    },
                },
                {
                    "name": "introduction",
                    "type": "template",
                    "params": {
                        "template": "{identity.full_name} is {identity.age} and has {identity.num_children} children."
                    },
                },
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})

        self.assertEqual(rows[0]["identity"]["full_name"], "Alex Morgan")
        self.assertEqual(rows[0]["identity"]["age"], 35)
        self.assertEqual(len(rows[0]["family"]["children"]), 2)
        self.assertEqual(rows[0]["introduction"], "Alex Morgan is 35 and has 2 children.")

    def test_persona_introduction_localizes_for_dutch_locale(self):
        config = {
            "records": 1,
            "locale": "nl_BE",
            "fields": [
                {
                    "name": "identity",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "full_name", "type": "literal", "params": {"value": "Alex Morgan"}},
                            {"name": "age", "type": "literal", "params": {"value": 35}},
                        ]
                    },
                },
                {"name": "contact", "type": "object", "params": {"fields": [{"name": "city", "type": "literal", "params": {"value": "Gent"}}]}},
                {
                    "name": "professional",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "job_title", "type": "literal", "params": {"value": "Bookkeeper"}},
                            {"name": "industry", "type": "literal", "params": {"value": "Finance"}},
                        ]
                    },
                },
                {
                    "name": "household_context",
                    "type": "object",
                    "params": {"fields": [{"name": "neighborhood_type", "type": "literal", "params": {"value": "urban"}}]},
                },
                {
                    "name": "introduction",
                    "type": "persona_introduction",
                    "params": {
                        "full_name_field": "identity.full_name",
                        "age_field": "identity.age",
                        "profession_field": "professional.job_title",
                        "city_field": "contact.city",
                        "industry_field": "professional.industry",
                        "neighborhood_type_field": "household_context.neighborhood_type",
                    },
                },
            ],
        }

        introduction = generate_data.generate_dataset(config, custom_formats={})[0]["introduction"]
        self.assertIn("werkt als", introduction)
        self.assertIn("boekhouder", introduction)
        self.assertIn("financien", introduction)
        self.assertIn("stedelijke thuisbasis", introduction)
        self.assertNotIn("Bookkeeper", introduction)
        self.assertNotIn("Finance", introduction)
        self.assertNotIn("Their routine is shaped", introduction)

    def test_persona_introduction_localizes_for_french_locale(self):
        config = {
            "records": 1,
            "locale": "fr_BE",
            "fields": [
                {
                    "name": "identity",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "full_name", "type": "literal", "params": {"value": "Alex Morgan"}},
                            {"name": "age", "type": "literal", "params": {"value": 35}},
                        ]
                    },
                },
                {"name": "contact", "type": "object", "params": {"fields": [{"name": "city", "type": "literal", "params": {"value": "Liege"}}]}},
                {
                    "name": "professional",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "job_title", "type": "literal", "params": {"value": "Bookkeeper"}},
                            {"name": "industry", "type": "literal", "params": {"value": "Finance"}},
                        ]
                    },
                },
                {
                    "name": "household_context",
                    "type": "object",
                    "params": {"fields": [{"name": "neighborhood_type", "type": "literal", "params": {"value": "suburban"}}]},
                },
                {
                    "name": "introduction",
                    "type": "persona_introduction",
                    "params": {
                        "full_name_field": "identity.full_name",
                        "age_field": "identity.age",
                        "profession_field": "professional.job_title",
                        "city_field": "contact.city",
                        "industry_field": "professional.industry",
                        "neighborhood_type_field": "household_context.neighborhood_type",
                    },
                },
            ],
        }

        introduction = generate_data.generate_dataset(config, custom_formats={})[0]["introduction"]
        self.assertIn("travaille comme", introduction)
        self.assertIn("comptable", introduction)
        self.assertIn("finance", introduction)
        self.assertIn("ancrage periurbain", introduction)
        self.assertNotIn("Bookkeeper", introduction)
        self.assertNotIn("Their routine is shaped", introduction)

    def test_conditional_fields_only_generate_when_condition_matches(self):
        config = {
            "records": 1,
            "fields": [
                {"name": "marital_status", "type": "literal", "params": {"value": "single"}},
                {
                    "name": "spouse",
                    "type": "object",
                    "when": {"path": "marital_status", "op": "eq", "value": "married"},
                    "params": {
                        "fields": [
                            {"name": "full_name", "type": "literal", "params": {"value": "Taylor Morgan"}}
                        ]
                    },
                },
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})

        self.assertEqual(rows[0]["marital_status"], "single")
        self.assertNotIn("spouse", rows[0])

    def test_correlation_rules_can_set_nested_fields_from_existing_values(self):
        config = {
            "records": 1,
            "fields": [
                {"name": "income_bracket", "type": "literal", "params": {"value": "low"}},
            ],
            "correlation_rules": [
                {
                    "name": "low_income_mobility",
                    "when": {"path": "income_bracket", "op": "eq", "value": "low"},
                    "assignments": [
                        {"path": "mobility.primary_commute_mode", "value": "public transport"},
                        {"path": "mobility.car_ownership", "value": False}
                    ]
                }
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})

        self.assertEqual(rows[0]["mobility"]["primary_commute_mode"], "public transport")
        self.assertFalse(rows[0]["mobility"]["car_ownership"])

    def test_source_backed_correlation_rule_uses_matching_weighted_segments(self):
        config = {
            "records": 8,
            "seed": 17,
            "fields": [
                {
                    "name": "household_context",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "neighborhood_type", "type": "literal", "params": {"value": "suburban"}}
                        ]
                    },
                }
            ],
            "correlation_rules": [
                {
                    "name": "source_backed_commute",
                    "source_model": {
                        "segments": [
                            {
                                "weight": 0.8,
                                "values": {
                                    "neighborhood_type": "suburban",
                                    "primary_commute_mode": "car"
                                }
                            },
                            {
                                "weight": 0.2,
                                "values": {
                                    "neighborhood_type": "suburban",
                                    "primary_commute_mode": "train"
                                }
                            }
                        ],
                        "match_on": [
                            {"path": "household_context.neighborhood_type", "segment_key": "neighborhood_type"}
                        ],
                        "assign_from_segment": [
                            {"path": "mobility.primary_commute_mode", "segment_key": "primary_commute_mode"}
                        ]
                    }
                }
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})
        modes = {row["mobility"]["primary_commute_mode"] for row in rows}
        self.assertTrue(modes.issubset({"car", "train"}))
        self.assertTrue(modes)

    def test_source_query_backed_correlation_rule_projects_segment_values(self):
        config = {
            "records": 4,
            "seed": 9,
            "fields": [
                {"name": "region", "type": "literal", "params": {"value": "urban"}}
            ],
            "correlation_rules": [
                {
                    "name": "live_style_projection",
                    "source_model": {
                        "source_query": {
                            "base_url": "https://example.test",
                            "dataset": "lifestyle",
                            "weight_column": "weight",
                            "dimension_columns": {
                                "region": "region",
                                "primary_commute_mode": "commute"
                            }
                        },
                        "match_on": [
                            {"path": "region", "segment_key": "region"}
                        ],
                        "assign_from_segment": [
                            {"path": "mobility.primary_commute_mode", "segment_key": "primary_commute_mode"}
                        ]
                    }
                }
            ],
        }
        fake_rows = [
            {"region": "urban", "commute": "metro", "weight": 70},
            {"region": "urban", "commute": "bike", "weight": 30},
            {"region": "rural", "commute": "car", "weight": 90}
        ]

        with patch.object(generate_data.urllib.request, "urlopen", return_value=FakeUrlopenResponse(fake_rows)):
            rows = generate_data.generate_dataset(config, custom_formats={})

        self.assertEqual(len(rows), 4)
        self.assertTrue(
            {row["mobility"]["primary_commute_mode"] for row in rows}.issubset({"metro", "bike"})
        )

    def test_contradiction_checks_fail_invalid_rows(self):
        config = {
            "records": 1,
            "fields": [
                {"name": "income_bracket", "type": "literal", "params": {"value": "low"}},
                {"name": "car_model", "type": "literal", "params": {"value": "Porsche 911"}},
            ],
            "contradiction_checks": [
                {
                    "name": "low_income_luxury_car",
                    "when": {
                        "all": [
                            {"path": "income_bracket", "op": "eq", "value": "low"},
                            {"path": "car_model", "op": "eq", "value": "Porsche 911"}
                        ]
                    },
                    "message": "low-income persona should not own a luxury sports car"
                }
            ],
        }

        with self.assertRaises(generate_data.SkillError) as exc:
            generate_data.generate_dataset(config, custom_formats={})

        self.assertIn("Contradiction checks failed", str(exc.exception))

    def test_timeline_contradiction_checks_fail_impossible_event_age(self):
        config = {
            "records": 1,
            "fields": [
                {
                    "name": "identity",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "birth_date", "type": "literal", "params": {"value": "2010-01-01"}}
                        ]
                    },
                },
                {
                    "name": "life_timeline",
                    "type": "literal",
                    "params": {
                        "value": [
                            {
                                "date": "2020-01-01",
                                "category": "career",
                                "title": "Career start",
                                "description": "Started working very early"
                            }
                        ]
                    },
                }
            ],
            "contradiction_checks": [
                {
                    "name": "career_too_early",
                    "timeline_assertions": [
                        {
                            "type": "minimum_age_at_event",
                            "timeline_field": "life_timeline",
                            "event": {"category": "career", "title": "Career start"},
                            "birth_date_field": "identity.birth_date",
                            "min_age": 16
                        }
                    ],
                    "message": "career start happens too early"
                }
            ],
        }

        with self.assertRaises(generate_data.SkillError) as exc:
            generate_data.generate_dataset(config, custom_formats={})

        self.assertIn("career start happens too early", str(exc.exception))

    def test_timeline_contradiction_checks_allow_valid_ordered_events(self):
        config = {
            "records": 1,
            "fields": [
                {
                    "name": "identity",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "birth_date", "type": "literal", "params": {"value": "1988-01-01"}}
                        ]
                    },
                },
                {
                    "name": "life_timeline",
                    "type": "literal",
                    "params": {
                        "value": [
                            {
                                "date": "2012-06-30",
                                "category": "education",
                                "title": "Completed a master's degree",
                                "description": "Finished higher education"
                            },
                            {
                                "date": "2013-02-01",
                                "category": "career",
                                "title": "Career start",
                                "description": "Started first major role"
                            },
                            {
                                "date": "2021-09-01",
                                "category": "career",
                                "title": "Current role",
                                "description": "Moved into current position"
                            }
                        ]
                    },
                }
            ],
            "contradiction_checks": [
                {
                    "name": "valid_career_sequence",
                    "timeline_assertions": [
                        {
                            "type": "ordered_events",
                            "timeline_field": "life_timeline",
                            "first_event": {"category": "education"},
                            "second_event": {"category": "career", "title": "Current role"},
                            "allow_same_day": False
                        },
                        {
                            "type": "minimum_age_at_event",
                            "timeline_field": "life_timeline",
                            "event": {"category": "career", "title": "Career start"},
                            "birth_date_field": "identity.birth_date",
                            "min_age": 16
                        }
                    ],
                    "message": "timeline is invalid"
                }
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})
        self.assertEqual(len(rows), 1)

    def test_timeline_contradiction_checks_fail_excessive_age_at_event(self):
        config = {
            "records": 1,
            "fields": [
                {
                    "name": "identity",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "birth_date", "type": "literal", "params": {"value": "1950-01-01"}}
                        ]
                    },
                },
                {
                    "name": "life_timeline",
                    "type": "literal",
                    "params": {
                        "value": [
                            {
                                "date": "2015-01-01",
                                "category": "family",
                                "title": "Child born",
                                "description": "Late child birth"
                            }
                        ]
                    },
                }
            ],
            "contradiction_checks": [
                {
                    "name": "child_birth_too_late",
                    "timeline_assertions": [
                        {
                            "type": "maximum_age_at_event",
                            "timeline_field": "life_timeline",
                            "event": {"category": "family", "title": "Child born"},
                            "birth_date_field": "identity.birth_date",
                            "max_age": 52
                        }
                    ],
                    "message": "child birth happens too late"
                }
            ],
        }

        with self.assertRaises(generate_data.SkillError) as exc:
            generate_data.generate_dataset(config, custom_formats={})

        self.assertIn("child birth happens too late", str(exc.exception))

    def test_timeline_contradiction_checks_fail_when_gap_between_events_is_too_small(self):
        config = {
            "records": 1,
            "fields": [
                {
                    "name": "life_timeline",
                    "type": "literal",
                    "params": {
                        "value": [
                            {
                                "date": "2015-01-01",
                                "category": "career",
                                "title": "Career start",
                                "description": "Started work"
                            },
                            {
                                "date": "2015-06-01",
                                "category": "career",
                                "title": "Current role",
                                "description": "Moved too quickly"
                            }
                        ]
                    },
                }
            ],
            "contradiction_checks": [
                {
                    "name": "career_gap_too_small",
                    "timeline_assertions": [
                        {
                            "type": "minimum_gap_between_events",
                            "timeline_field": "life_timeline",
                            "first_event": {"category": "career", "title": "Career start"},
                            "second_event": {"category": "career", "title": "Current role"},
                            "min_gap_days": 365
                        }
                    ],
                    "message": "career events are unrealistically close together"
                }
            ],
        }

        with self.assertRaises(generate_data.SkillError) as exc:
            generate_data.generate_dataset(config, custom_formats={})

        self.assertIn("career events are unrealistically close together", str(exc.exception))

    def test_life_timeline_generates_sorted_profile_events(self):
        config = {
            "records": 1,
            "seed": 21,
            "fields": [
                {
                    "name": "identity",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "full_name", "type": "literal", "params": {"value": "Alex Morgan"}},
                            {"name": "birth_date", "type": "literal", "params": {"value": "1988-05-10"}},
                            {"name": "marital_status", "type": "literal", "params": {"value": "married"}},
                        ]
                    },
                },
                {
                    "name": "contact",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "city", "type": "literal", "params": {"value": "Ghent"}}
                        ]
                    },
                },
                {
                    "name": "professional",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "education_level", "type": "literal", "params": {"value": "Master's degree"}},
                            {"name": "job_title", "type": "literal", "params": {"value": "Operations Manager"}},
                            {"name": "company", "type": "literal", "params": {"value": "Northwind Health"}}                        
                        ]
                    },
                },
                {
                    "name": "family",
                    "type": "object",
                    "params": {
                        "fields": [
                            {
                                "name": "spouse",
                                "type": "object",
                                "params": {
                                    "fields": [
                                        {"name": "full_name", "type": "literal", "params": {"value": "Taylor Morgan"}}
                                    ]
                                },
                            },
                            {
                                "name": "children",
                                "type": "literal",
                                "params": {
                                    "value": [
                                        {"full_name": "Sam Morgan", "birth_date": "2016-02-02"},
                                        {"full_name": "Mila Morgan", "birth_date": "2019-07-14"}
                                    ]
                                },
                            },
                        ]
                    },
                },
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
                    },
                },
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})
        timeline = rows[0]["life_timeline"]

        self.assertGreaterEqual(len(timeline), 5)
        self.assertEqual(timeline[0]["title"], "Birth")
        self.assertEqual([event["date"] for event in timeline], sorted(event["date"] for event in timeline))
        self.assertTrue(any(event["title"] == "Child born" for event in timeline))
        self.assertTrue(any(event["title"] == "Current role" for event in timeline))
        self.assertTrue(any(event["title"] == "Completed secondary education" for event in timeline))
        self.assertTrue(any(event["title"] == "Expanded responsibilities" for event in timeline))
        self.assertTrue(any(event["title"] == "Established an independent household" for event in timeline))
        self.assertTrue(any(event["title"] == "Household routine changed" for event in timeline))
        self.assertTrue(any(event["title"] == "Completed secondary education" for event in timeline))
        self.assertTrue(any(event["title"] == "Expanded responsibilities" for event in timeline))
        self.assertTrue(any(event["title"] == "Established an independent household" for event in timeline))
        self.assertTrue(any(event["title"] == "Household routine changed" for event in timeline))

    def test_life_timeline_localizes_descriptions_for_dutch_locale(self):
        config = {
            "records": 1,
            "seed": 21,
            "locale": "nl_BE",
            "fields": [
                {
                    "name": "identity",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "full_name", "type": "literal", "params": {"value": "Alex Morgan"}},
                            {"name": "birth_date", "type": "literal", "params": {"value": "1988-05-10"}},
                        ]
                    },
                },
                {
                    "name": "contact",
                    "type": "object",
                    "params": {"fields": [{"name": "city", "type": "literal", "params": {"value": "Gent"}}]},
                },
                {
                    "name": "professional",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "education_level", "type": "literal", "params": {"value": "Bachelor's degree"}},
                            {"name": "job_title", "type": "literal", "params": {"value": "Bookkeeper"}},
                            {"name": "company", "type": "literal", "params": {"value": "Northwind Health"}},
                        ]
                    },
                },
                {
                    "name": "life_timeline",
                    "type": "life_timeline",
                    "params": {
                        "birth_date_field": "identity.birth_date",
                        "full_name_field": "identity.full_name",
                        "education_level_field": "professional.education_level",
                        "profession_field": "professional.job_title",
                        "company_field": "professional.company",
                        "city_field": "contact.city",
                        "reference_date": "2026-01-01",
                    },
                },
            ],
        }

        timeline = generate_data.generate_dataset(config, custom_formats={})[0]["life_timeline"]
        descriptions = [item["description"] for item in timeline]
        self.assertIn("werd geboren op", descriptions[0])
        self.assertTrue(any("boekhouder" in description for description in descriptions))
        self.assertTrue(any("bacheloropleiding" in description for description in descriptions))
        self.assertTrue(any("bouwde het dagelijkse leven uit in Gent" in description for description in descriptions))

    def test_life_timeline_localizes_descriptions_for_french_locale(self):
        config = {
            "records": 1,
            "seed": 21,
            "locale": "fr_BE",
            "fields": [
                {
                    "name": "identity",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "full_name", "type": "literal", "params": {"value": "Alex Morgan"}},
                            {"name": "birth_date", "type": "literal", "params": {"value": "1988-05-10"}},
                        ]
                    },
                },
                {
                    "name": "contact",
                    "type": "object",
                    "params": {"fields": [{"name": "city", "type": "literal", "params": {"value": "Namur"}}]},
                },
                {
                    "name": "professional",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "education_level", "type": "literal", "params": {"value": "Master's degree"}},
                            {"name": "job_title", "type": "literal", "params": {"value": "Bookkeeper"}},
                            {"name": "company", "type": "literal", "params": {"value": "Northwind Health"}},
                        ]
                    },
                },
                {
                    "name": "life_timeline",
                    "type": "life_timeline",
                    "params": {
                        "birth_date_field": "identity.birth_date",
                        "full_name_field": "identity.full_name",
                        "education_level_field": "professional.education_level",
                        "profession_field": "professional.job_title",
                        "company_field": "professional.company",
                        "city_field": "contact.city",
                        "reference_date": "2026-01-01",
                    },
                },
            ],
        }

        timeline = generate_data.generate_dataset(config, custom_formats={})[0]["life_timeline"]
        descriptions = [item["description"] for item in timeline]
        self.assertIn("est ne le", descriptions[0])
        self.assertTrue(any("comptable" in description for description in descriptions))
        self.assertTrue(any("master" in description for description in descriptions))
        self.assertTrue(any("a etabli son quotidien a Namur" in description for description in descriptions))

    def test_daily_routine_profile_reflects_life_stage_and_commute(self):
        config = {
            "records": 1,
            "fields": [
                {
                    "name": "identity",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "age", "type": "literal", "params": {"value": 41}},
                            {"name": "num_children", "type": "literal", "params": {"value": 2}},
                        ]
                    },
                },
                {
                    "name": "professional",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "job_title", "type": "literal", "params": {"value": "Operations Program Lead"}},
                        ]
                    },
                },
                {
                    "name": "mobility",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "primary_commute_mode", "type": "literal", "params": {"value": "train"}},
                        ]
                    },
                },
                {
                    "name": "daily_routine",
                    "type": "daily_routine_profile",
                    "params": {
                        "age_field": "identity.age",
                        "profession_field": "professional.job_title",
                        "primary_commute_mode_field": "mobility.primary_commute_mode",
                        "children_count_field": "identity.num_children",
                    },
                },
            ],
        }

        row = generate_data.generate_dataset(config, custom_formats={})[0]
        routine = row["daily_routine"]
        self.assertEqual(routine["work_pattern"], "hybrid office schedule")
        self.assertIn("train-led commute", routine["weekday_rhythm"])
        self.assertEqual(routine["wake_time"], "06:30")

    def test_daily_routine_profile_localizes_text_for_dutch_locale(self):
        config = {
            "records": 1,
            "locale": "nl_BE",
            "fields": [
                {
                    "name": "identity",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "age", "type": "literal", "params": {"value": 41}},
                            {"name": "num_children", "type": "literal", "params": {"value": 2}},
                        ]
                    },
                },
                {
                    "name": "professional",
                    "type": "object",
                    "params": {"fields": [{"name": "job_title", "type": "literal", "params": {"value": "Bookkeeper"}}]},
                },
                {
                    "name": "mobility",
                    "type": "object",
                    "params": {"fields": [{"name": "primary_commute_mode", "type": "literal", "params": {"value": "train"}}]},
                },
                {
                    "name": "daily_routine",
                    "type": "daily_routine_profile",
                    "params": {
                        "age_field": "identity.age",
                        "profession_field": "professional.job_title",
                        "primary_commute_mode_field": "mobility.primary_commute_mode",
                        "children_count_field": "identity.num_children",
                    },
                },
            ],
        }

        routine = generate_data.generate_dataset(config, custom_formats={})[0]["daily_routine"]
        self.assertEqual(routine["work_pattern"], "hybrid office schedule")
        self.assertIn("treinrit", routine["weekday_rhythm"])
        self.assertIn("avondoverdracht", routine["weekday_rhythm"])
        self.assertIn("planning voor de volgende dag", routine["evening_habits"])
        self.assertNotIn("train-led commute", routine["weekday_rhythm"])

    def test_daily_routine_profile_localizes_text_for_french_locale(self):
        config = {
            "records": 1,
            "locale": "fr_BE",
            "fields": [
                {
                    "name": "identity",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "age", "type": "literal", "params": {"value": 43}},
                            {"name": "num_children", "type": "literal", "params": {"value": 0}},
                        ]
                    },
                },
                {
                    "name": "professional",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "job_title", "type": "literal", "params": {"value": "Secondary School Teacher"}},
                            {"name": "work_pattern", "type": "literal", "params": {"value": "structured daytime schedule"}},
                            {"name": "income_bracket", "type": "literal", "params": {"value": "upper-middle"}},
                            {"name": "sector_type", "type": "literal", "params": {"value": "public sector"}},
                            {"name": "employer_scale", "type": "literal", "params": {"value": "municipal or regional institution"}},
                        ]
                    },
                },
                {
                    "name": "mobility",
                    "type": "object",
                    "params": {"fields": [{"name": "primary_commute_mode", "type": "literal", "params": {"value": "train"}}]},
                },
                {
                    "name": "daily_routine",
                    "type": "daily_routine_profile",
                    "params": {
                        "age_field": "identity.age",
                        "profession_field": "professional.job_title",
                        "work_pattern_field": "professional.work_pattern",
                        "primary_commute_mode_field": "mobility.primary_commute_mode",
                        "children_count_field": "identity.num_children",
                        "income_bracket_field": "professional.income_bracket",
                        "sector_type_field": "professional.sector_type",
                        "employer_scale_field": "professional.employer_scale",
                    },
                },
            ],
        }

        routine = generate_data.generate_dataset(config, custom_formats={})[0]["daily_routine"]
        self.assertEqual(routine["work_pattern"], "structured daytime schedule")
        self.assertIn("trajet en train", routine["weekday_rhythm"])
        self.assertIn("coordination avec le public", routine["weekday_rhythm"])
        self.assertIn("activite physique", routine["weekend_rhythm"])
        self.assertNotIn("public-facing coordination", routine["weekday_rhythm"])

    def test_daily_routine_profile_respects_explicit_structured_schedule_and_public_sector_context(self):
        config = {
            "records": 1,
            "fields": [
                {
                    "name": "identity",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "age", "type": "literal", "params": {"value": 43}},
                            {"name": "num_children", "type": "literal", "params": {"value": 0}},
                        ]
                    },
                },
                {
                    "name": "professional",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "job_title", "type": "literal", "params": {"value": "Secondary School Teacher"}},
                            {"name": "work_pattern", "type": "literal", "params": {"value": "structured daytime schedule"}},
                            {"name": "income_bracket", "type": "literal", "params": {"value": "upper-middle"}},
                            {"name": "sector_type", "type": "literal", "params": {"value": "public sector"}},
                            {"name": "employer_scale", "type": "literal", "params": {"value": "municipal or regional institution"}},
                        ]
                    },
                },
                {
                    "name": "mobility",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "primary_commute_mode", "type": "literal", "params": {"value": "train"}},
                        ]
                    },
                },
                {
                    "name": "daily_routine",
                    "type": "daily_routine_profile",
                    "params": {
                        "age_field": "identity.age",
                        "profession_field": "professional.job_title",
                        "work_pattern_field": "professional.work_pattern",
                        "primary_commute_mode_field": "mobility.primary_commute_mode",
                        "children_count_field": "identity.num_children",
                        "income_bracket_field": "professional.income_bracket",
                        "sector_type_field": "professional.sector_type",
                        "employer_scale_field": "professional.employer_scale",
                    },
                },
            ],
        }

        routine = generate_data.generate_dataset(config, custom_formats={})[0]["daily_routine"]
        self.assertEqual(routine["work_pattern"], "structured daytime schedule")
        self.assertIn("train-led commute", routine["weekday_rhythm"])
        self.assertIn("public-facing coordination", routine["weekday_rhythm"])
        self.assertIn("discretionary social or leisure plan", routine["weekend_rhythm"])

    def test_daily_routine_profile_uses_budget_aware_weekend_for_lower_income_service_roles(self):
        config = {
            "records": 1,
            "fields": [
                {
                    "name": "identity",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "age", "type": "literal", "params": {"value": 38}},
                            {"name": "num_children", "type": "literal", "params": {"value": 0}},
                        ]
                    },
                },
                {
                    "name": "professional",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "job_title", "type": "literal", "params": {"value": "Home Care Cleaner"}},
                            {"name": "work_pattern", "type": "literal", "params": {"value": "field-based service schedule"}},
                            {"name": "income_bracket", "type": "literal", "params": {"value": "low"}},
                            {"name": "sector_type", "type": "literal", "params": {"value": "private sector"}},
                            {"name": "employer_scale", "type": "literal", "params": {"value": "local SME"}},
                        ]
                    },
                },
                {
                    "name": "mobility",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "primary_commute_mode", "type": "literal", "params": {"value": "car"}},
                        ]
                    },
                },
                {
                    "name": "daily_routine",
                    "type": "daily_routine_profile",
                    "params": {
                        "age_field": "identity.age",
                        "profession_field": "professional.job_title",
                        "work_pattern_field": "professional.work_pattern",
                        "primary_commute_mode_field": "mobility.primary_commute_mode",
                        "children_count_field": "identity.num_children",
                        "income_bracket_field": "professional.income_bracket",
                        "sector_type_field": "professional.sector_type",
                        "employer_scale_field": "professional.employer_scale",
                    },
                },
            ],
        }

        routine = generate_data.generate_dataset(config, custom_formats={})[0]["daily_routine"]
        self.assertEqual(routine["work_pattern"], "on-site schedule")
        self.assertIn("smaller team", routine["weekday_rhythm"])
        self.assertIn("budget-aware shopping", routine["weekend_rhythm"])

    def test_biography_from_timeline_uses_generated_events(self):
        config = {
            "records": 1,
            "seed": 21,
            "fields": [
                {
                    "name": "identity",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "full_name", "type": "literal", "params": {"value": "Alex Morgan"}},
                            {"name": "birth_date", "type": "literal", "params": {"value": "1988-05-10"}},
                            {"name": "marital_status", "type": "literal", "params": {"value": "married"}},
                        ]
                    },
                },
                {
                    "name": "contact",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "city", "type": "literal", "params": {"value": "Ghent"}}
                        ]
                    },
                },
                {
                    "name": "professional",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "education_level", "type": "literal", "params": {"value": "Master's degree"}},
                            {"name": "job_title", "type": "literal", "params": {"value": "Operations Manager"}},
                            {"name": "company", "type": "literal", "params": {"value": "Northwind Health"}}
                        ]
                    },
                },
                {
                    "name": "lifestyle",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "hobbies", "type": "literal", "params": {"value": ["cycling", "podcasts"]}}
                        ]
                    },
                },
                {
                    "name": "finance",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "income_level", "type": "literal", "params": {"value": "comfortable dual-income household"}}
                        ]
                    },
                },
                {
                    "name": "household_context",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "housing_type", "type": "literal", "params": {"value": "apartment"}},
                            {"name": "ownership_status", "type": "literal", "params": {"value": "owner"}},
                            {"name": "neighborhood_type", "type": "literal", "params": {"value": "urban"}},
                        ]
                    },
                },
                {
                    "name": "family",
                    "type": "object",
                    "params": {
                        "fields": [
                            {
                                "name": "children",
                                "type": "literal",
                                "params": {
                                    "value": [
                                        {"full_name": "Sam Morgan", "birth_date": "2016-02-02"}
                                    ]
                                },
                            }
                        ]
                    },
                },
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
                        "children_field": "family.children",
                        "city_field": "contact.city",
                        "reference_date": "2026-01-01"
                    },
                },
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
                    },
                },
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})
        biography = rows[0]["biography"]

        self.assertIn("Alex Morgan", biography)
        self.assertIn("Operations Manager", biography)
        self.assertIn("Ghent", biography)
        self.assertIn("cycling and podcasts", biography)
        self.assertIn("comfortable dual-income household", biography)
        self.assertIn("owner-occupied apartment in an urban setting", biography)

    def test_biography_from_timeline_supports_direct_style(self):
        config = {
            "records": 1,
            "seed": 21,
            "fields": [
                {
                    "name": "identity",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "full_name", "type": "literal", "params": {"value": "Alex Morgan"}},
                            {"name": "birth_date", "type": "literal", "params": {"value": "1988-05-10"}},
                            {"name": "marital_status", "type": "literal", "params": {"value": "married"}},
                        ]
                    },
                },
                {
                    "name": "contact",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "city", "type": "literal", "params": {"value": "Ghent"}}
                        ]
                    },
                },
                {
                    "name": "professional",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "education_level", "type": "literal", "params": {"value": "Master's degree"}},
                            {"name": "job_title", "type": "literal", "params": {"value": "Operations Manager"}},
                            {"name": "company", "type": "literal", "params": {"value": "Northwind Health"}}
                        ]
                    },
                },
                {
                    "name": "lifestyle",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "hobbies", "type": "literal", "params": {"value": ["cycling", "podcasts"]}}
                        ]
                    },
                },
                {
                    "name": "finance",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "income_level", "type": "literal", "params": {"value": "comfortable dual-income household"}}
                        ]
                    },
                },
                {
                    "name": "household_context",
                    "type": "object",
                    "params": {
                        "fields": [
                            {"name": "housing_type", "type": "literal", "params": {"value": "row house"}},
                            {"name": "ownership_status", "type": "literal", "params": {"value": "renter"}},
                            {"name": "neighborhood_type", "type": "literal", "params": {"value": "suburban"}},
                        ]
                    },
                },
                {
                    "name": "family",
                    "type": "object",
                    "params": {
                        "fields": [
                            {
                                "name": "children",
                                "type": "literal",
                                "params": {
                                    "value": [
                                        {"full_name": "Sam Morgan", "birth_date": "2016-02-02"}
                                    ]
                                },
                            }
                        ]
                    },
                },
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
                        "children_field": "family.children",
                        "city_field": "contact.city",
                        "reference_date": "2026-01-01"
                    },
                },
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
                        "children_field": "family.children",
                        "style": "direct"
                    },
                },
            ],
        }

        biography = generate_data.generate_dataset(config, custom_formats={})[0]["biography"]
        self.assertIn("Spending patterns fit", biography)
        self.assertIn("rented row house", biography)
        self.assertIn("suburban setting", biography)
        self.assertNotIn("has built a life shaped by steady milestones", biography)

    def test_biography_from_timeline_uses_deterministic_sentence_variation(self):
        markers = {
            "is now established",
            "is settled",
            "is at a stage of life that feels steady",
        }
        biographies = []

        for full_name in [
            "Alex Morgan",
            "Taylor Morgan",
            "Jordan Rivera",
            "Chris Laurent",
            "Mina Verhoeven",
            "Noah Diallo",
        ]:
            row = {
                "life_timeline": [
                    {"category": "education", "title": "Completed a bachelor's degree"},
                    {"category": "career", "title": "Current role"},
                    {"category": "location", "title": "Settled in current city"},
                ],
                "identity": {"full_name": full_name},
                "contact": {"city": "Brussels"},
                "professional": {"education_level": "Bachelor's degree", "job_title": "Designer"},
            }
            row_context = {"__root__": row, "__current__": row}
            biographies.append(
                generate_data.build_biography_from_timeline(
                    row_context=row_context,
                    params={
                        "timeline_field": "life_timeline",
                        "full_name_field": "identity.full_name",
                        "city_field": "contact.city",
                        "education_level_field": "professional.education_level",
                        "profession_field": "professional.job_title",
                        "style": "direct",
                    },
                    field_name="biography",
                )
            )

        repeated = generate_data.build_biography_from_timeline(
            row_context={
                "__root__": {
                    "life_timeline": [
                        {"category": "education", "title": "Completed a bachelor's degree"},
                        {"category": "career", "title": "Current role"},
                        {"category": "location", "title": "Settled in current city"},
                    ],
                    "identity": {"full_name": "Alex Morgan"},
                    "contact": {"city": "Brussels"},
                    "professional": {"education_level": "Bachelor's degree", "job_title": "Designer"},
                },
                "__current__": {
                    "life_timeline": [
                        {"category": "education", "title": "Completed a bachelor's degree"},
                        {"category": "career", "title": "Current role"},
                        {"category": "location", "title": "Settled in current city"},
                    ],
                    "identity": {"full_name": "Alex Morgan"},
                    "contact": {"city": "Brussels"},
                    "professional": {"education_level": "Bachelor's degree", "job_title": "Designer"},
                },
            },
            params={
                "timeline_field": "life_timeline",
                "full_name_field": "identity.full_name",
                "city_field": "contact.city",
                "education_level_field": "professional.education_level",
                "profession_field": "professional.job_title",
                "style": "direct",
            },
            field_name="biography",
        )

        seen_markers = {marker for biography in biographies for marker in markers if marker in biography}
        self.assertGreaterEqual(len(seen_markers), 2)
        self.assertEqual(biographies[0], repeated)

    def test_biography_from_timeline_localizes_for_dutch_locale(self):
        config = {
            "records": 1,
            "locale": "nl_BE",
            "fields": [
                {"name": "life_timeline", "type": "literal", "params": {"value": [{"category": "education", "title": "Completed a bachelor's degree"}, {"category": "career", "title": "Current role"}, {"category": "location", "title": "Settled in current city"}]}},
                {"name": "identity", "type": "object", "params": {"fields": [{"name": "full_name", "type": "literal", "params": {"value": "Alex Morgan"}}]}},
                {"name": "contact", "type": "object", "params": {"fields": [{"name": "city", "type": "literal", "params": {"value": "Gent"}}]}},
                {"name": "professional", "type": "object", "params": {"fields": [{"name": "education_level", "type": "literal", "params": {"value": "Master's degree"}}, {"name": "job_title", "type": "literal", "params": {"value": "Bookkeeper"}}]}},
                {"name": "lifestyle", "type": "object", "params": {"fields": [{"name": "hobbies", "type": "literal", "params": {"value": ["cycling", "home cooking", "podcasts"]}}]}},
                {"name": "finance", "type": "object", "params": {"fields": [{"name": "income_level", "type": "literal", "params": {"value": "stable middle-income household"}}]}},
                {"name": "household_context", "type": "object", "params": {"fields": [{"name": "housing_type", "type": "literal", "params": {"value": "apartment"}}, {"name": "ownership_status", "type": "literal", "params": {"value": "owner"}}, {"name": "neighborhood_type", "type": "literal", "params": {"value": "urban"}}]}},
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
                        "style": "direct",
                    },
                },
            ],
        }

        biography = generate_data.generate_dataset(config, custom_formats={})[0]["biography"]
        self.assertTrue(any(marker in biography for marker in {"is vandaag gevestigd", "Vandaag leeft", "heeft vandaag een stabiele plek"}))
        self.assertIn("boekhouder", biography)
        self.assertIn("masteropleiding", biography)
        self.assertIn("fietsen, thuis koken en podcasts", biography)
        self.assertIn("stedelijke omgeving", biography)
        self.assertIn("Uitgaven passen bij", biography)
        self.assertNotIn("Bookkeeper", biography)
        self.assertNotIn("Master's degree", biography)
        self.assertNotIn("Spending patterns fit", biography)

    def test_biography_from_timeline_localizes_for_french_locale(self):
        config = {
            "records": 1,
            "locale": "fr_BE",
            "fields": [
                {"name": "life_timeline", "type": "literal", "params": {"value": [{"category": "education", "title": "Completed a bachelor's degree"}, {"category": "career", "title": "Current role"}, {"category": "location", "title": "Settled in current city"}]}},
                {"name": "identity", "type": "object", "params": {"fields": [{"name": "full_name", "type": "literal", "params": {"value": "Alex Morgan"}}]}},
                {"name": "contact", "type": "object", "params": {"fields": [{"name": "city", "type": "literal", "params": {"value": "Namur"}}]}},
                {"name": "professional", "type": "object", "params": {"fields": [{"name": "education_level", "type": "literal", "params": {"value": "Master's degree"}}, {"name": "job_title", "type": "literal", "params": {"value": "Bookkeeper"}}]}},
                {"name": "lifestyle", "type": "object", "params": {"fields": [{"name": "hobbies", "type": "literal", "params": {"value": ["cycling", "home cooking", "podcasts"]}}]}},
                {"name": "finance", "type": "object", "params": {"fields": [{"name": "income_level", "type": "literal", "params": {"value": "stable middle-income household"}}]}},
                {"name": "household_context", "type": "object", "params": {"fields": [{"name": "housing_type", "type": "literal", "params": {"value": "row house"}}, {"name": "ownership_status", "type": "literal", "params": {"value": "renter"}}, {"name": "neighborhood_type", "type": "literal", "params": {"value": "suburban"}}]}},
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
                        "style": "direct",
                    },
                },
            ],
        }

        biography = generate_data.generate_dataset(config, custom_formats={})[0]["biography"]
        self.assertTrue(any(marker in biography for marker in {"est aujourd'hui installe", "Aujourd'hui, Alex Morgan vit", "a aujourd'hui une situation stable"}))
        self.assertIn("comptable", biography)
        self.assertIn("master", biography)
        self.assertIn("cyclisme, cuisine maison et podcasts", biography)
        self.assertIn("cadre periurbain", biography)
        self.assertIn("Les depenses correspondent", biography)
        self.assertNotIn("Bookkeeper", biography)
        self.assertNotIn("Master's degree", biography)
        self.assertNotIn("Spending patterns fit", biography)

    def test_template_unknown_key_raises_helpful_error(self):
        config = {
            "records": 1,
            "fields": [
                {
                    "name": "summary",
                    "type": "template",
                    "params": {"template": "{missing_field}"},
                }
            ],
        }

        with self.assertRaises(generate_data.SkillError) as exc:
            generate_data.generate_dataset(config, custom_formats={})

        self.assertIn("unknown key", str(exc.exception))

    def test_cli_validate_only_returns_json_summary(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "records": 2,
                        "seed": 5,
                        "fields": [
                            {"name": "first_name", "type": "first_name"},
                            {"name": "country", "type": "literal", "params": {"value": "BE"}},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--config", str(config_path), "--validate-only"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "validated")
            self.assertEqual(payload["records_requested"], 2)
            self.assertEqual(len(payload["preview"]), 2)

    def test_persona_example_validates_and_generates_nested_json(self):
        config_path = REPO_ROOT / "examples" / "persona-belgium.json"
        output_path = REPO_ROOT / "artifacts" / "persona-belgium.test.json"

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--config", str(config_path), "--output", str(output_path)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        try:
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["output"]["format"], "json")
            rows = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(rows)
            self.assertIn("identity", rows[0])
            self.assertIn("contact", rows[0])
            self.assertIn("family", rows[0])
            self.assertIn("introduction", rows[0])
            self.assertIn("thuisbasis", rows[0]["introduction"])
            self.assertIn("life_timeline", rows[0])
            self.assertTrue(rows[0]["life_timeline"])
            self.assertIn("biography", rows[0])
            self.assertTrue(rows[0]["biography"])
            children = rows[0]["family"].get("children", [])
            self.assertIsInstance(children, list)
            self.assertEqual(rows[0]["identity"]["preferred_pronouns"], "she/her" if rows[0]["identity"]["gender"] == "F" else "he/him")
            self.assertEqual(rows[0]["finance"]["iban"][4:7], BELGIAN_BANK_CODES[rows[0]["finance"]["bank_name"]])
            self.assertTrue(any(dimension["name"] == "region" for dimension in payload["representativeness"]["distribution_backed_dimensions"]))
            self.assertTrue(
                any(
                    dimension["name"] == "marital_status" and dimension.get("represented") is False
                    for dimension in payload["representativeness"]["distribution_backed_dimensions"]
                )
            )
            self.assertTrue(any(field["field_name"] == "identity.marital_status" for field in payload["representativeness"]["distribution_backed_fields"]))
            self.assertTrue(any(field["field_name"] == "identity.num_children" for field in payload["representativeness"]["distribution_backed_fields"]))
            self.assertTrue(any(field["field_name"] == "contact.region" for field in payload["representativeness"]["distribution_backed_fields"]))
            self.assertIn(rows[0]["contact"]["region"], {"VLG", "WAL", "BXL"})
            self.assertIn("preferred_insurer", rows[0]["shopping_and_brand_preferences"])
            self.assertIn("preferred_transit_operator", rows[0]["shopping_and_brand_preferences"])
            self.assertIn("preferred_news_brand", rows[0]["shopping_and_brand_preferences"])
            spouse = rows[0]["family"].get("spouse")
            if spouse is not None:
                self.assertEqual(spouse["last_name"], rows[0]["identity"]["last_name"])
            self.assertTrue(str(rows[0]["contact"]["phone_number"]).startswith("+324"))
            self.assertNotIn(rows[0]["identity"]["full_name"].lower(), rows[0]["biography"])
            dutch_housing_labels = {
                "apartment": "appartement",
                "row house": "rijhuis",
                "semi-detached house": "halfopen bebouwing",
                "detached house": "vrijstaande woning",
                "house": "woning",
                "brussels apartment": "Brussels appartement",
            }
            dutch_neighborhood_labels = {
                "urban": "stedelijke omgeving",
                "suburban": "voorstedelijke omgeving",
                "small-town": "kleinstedelijke omgeving",
            }
            self.assertIn(
                dutch_housing_labels.get(rows[0]["household_context"]["housing_type"], rows[0]["household_context"]["housing_type"]),
                rows[0]["biography"],
            )
            self.assertIn(
                dutch_neighborhood_labels.get(rows[0]["household_context"]["neighborhood_type"], rows[0]["household_context"]["neighborhood_type"]),
                rows[0]["biography"],
            )
            child_birth_dates = sorted(date.fromisoformat(child["birth_date"]) for child in children)
            if len(child_birth_dates) > 1:
                self.assertGreaterEqual((child_birth_dates[1] - child_birth_dates[0]).days, 540)
            timeline_titles = [item["title"] for item in rows[0]["life_timeline"]]
            if "Marriage or long-term partnership" in timeline_titles and "Child born" in timeline_titles:
                marriage_date = next(item["date"] for item in rows[0]["life_timeline"] if item["title"] == "Marriage or long-term partnership")
                first_child_date = next(item["date"] for item in rows[0]["life_timeline"] if item["title"] == "Child born")
                self.assertLess(marriage_date, first_child_date)
            for generated_row in rows:
                marital_status = generated_row["identity"]["marital_status"]
                generated_child_count = generated_row["identity"]["num_children"]
                if marital_status == "partnered":
                    self.assertEqual(generated_child_count, 0)
                if marital_status == "single":
                    self.assertIn(generated_child_count, {0, 1})
                if generated_child_count >= 2:
                    self.assertEqual(marital_status, "married")
            commute_mode = rows[0]["mobility"]["primary_commute_mode"]
            child_count = rows[0]["identity"]["num_children"]
            weekday_rhythm = rows[0]["daily_routine"]["weekday_rhythm"]
            professional_pattern = rows[0]["professional"]["work_pattern"]
            routine_pattern = rows[0]["daily_routine"]["work_pattern"]
            if professional_pattern == "structured daytime schedule":
                self.assertEqual(routine_pattern, "structured daytime schedule")
            elif professional_pattern == "shift-based schedule":
                self.assertEqual(routine_pattern, "shift-based schedule")
            elif professional_pattern in {"field-based service schedule", "on-site service schedule"}:
                self.assertEqual(routine_pattern, "on-site schedule")
            elif professional_pattern == "hybrid office schedule":
                self.assertEqual(routine_pattern, "hybrid office schedule")
            if commute_mode == "train":
                self.assertIn("treinrit", weekday_rhythm)
                self.assertEqual(rows[0]["mobility"]["public_transport_use"], "frequent")
                expected_style = "train-based family logistics" if child_count > 0 else "train-based commuter routine"
                self.assertEqual(rows[0]["household_context"]["commute_style"], expected_style)
            elif commute_mode == "car":
                self.assertIn("werkdag met de auto", weekday_rhythm)
                self.assertEqual(rows[0]["mobility"]["public_transport_use"], "occasional")
                expected_style = "car-based family commute" if child_count > 0 else "car-led commute routine"
                self.assertEqual(rows[0]["household_context"]["commute_style"], expected_style)
            elif commute_mode == "bike":
                self.assertIn("korte actieve verplaatsingen", weekday_rhythm)
                self.assertEqual(rows[0]["mobility"]["public_transport_use"], "occasional")
                expected_style = "bike-first family routine" if child_count > 0 else "bike-first local routine"
                self.assertEqual(rows[0]["household_context"]["commute_style"], expected_style)
        finally:
            if output_path.exists():
                output_path.unlink()

    def test_persona_example_housing_profiles_follow_region_and_household_shape(self):
        config = json.loads((REPO_ROOT / "examples" / "persona-belgium.json").read_text(encoding="utf-8"))
        config["records"] = 160

        rows = generate_data.generate_dataset(config, custom_formats=generate_data.load_custom_formats())

        saw_brussels_household = False
        saw_regional_upper_middle_family = False
        saw_regional_budget_family = False

        for row in rows:
            region = row["contact"]["region"]
            income_bracket = row["professional"]["income_bracket"]
            child_count = row["identity"]["num_children"]
            household = row["household_context"]

            if region == "BXL":
                saw_brussels_household = True
                self.assertIn(household["housing_type"], {"apartment", "row house"})
                if household["household_size"] <= 2 and child_count == 0:
                    self.assertEqual(household["neighborhood_type"], "urban")
                if household["household_size"] == 1:
                    self.assertEqual(household["ownership_status"], "renter")

            if region in {"VLG", "WAL"} and child_count > 0 and income_bracket == "upper-middle":
                saw_regional_upper_middle_family = True
                self.assertEqual(household["ownership_status"], "owner")
                self.assertIn(household["housing_type"], {"semi-detached house", "row house"})
                self.assertIn(household["neighborhood_type"], {"suburban", "small-town"})

            if region in {"VLG", "WAL"} and child_count > 0 and income_bracket in {"low", "lower-middle"}:
                saw_regional_budget_family = True
                self.assertIn(household["housing_type"], {"row house", "apartment"})
                self.assertIn(household["neighborhood_type"], {"suburban", "small-town"})

        self.assertTrue(saw_brussels_household)
        self.assertTrue(saw_regional_upper_middle_family)
        self.assertTrue(saw_regional_budget_family)

    def test_persona_example_can_generate_html_bundle_with_index(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = json.loads((REPO_ROOT / "examples" / "persona-belgium.json").read_text(encoding="utf-8"))
            output_path = Path(tmp_dir) / "persona-site"
            config["records"] = 1
            config["output"] = {"format": "html", "path": str(output_path)}
            config_path = Path(tmp_dir) / "persona-html-config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--config", str(config_path)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["output"]["format"], "html")
            index_path = output_path / "index.html"
            self.assertTrue(index_path.exists())
            index_html = index_path.read_text(encoding="utf-8")
            self.assertIn("<table>", index_html)
            self.assertIn('lang="nl-BE"', index_html)
            self.assertIn("Samenvatting", index_html)
            persona_pages = list(output_path.glob("persona-*.html"))
            self.assertEqual(len(persona_pages), 1)
            self.assertIn(persona_pages[0].name, index_html)
            persona_html = persona_pages[0].read_text(encoding="utf-8")
            preview_row = payload["preview"][0]
            self.assertIn("Terug naar overzicht", persona_html)
            self.assertNotIn(preview_row["identity"]["national_id_number"], persona_html)
            self.assertNotIn(preview_row["contact"]["email"], persona_html)
            self.assertNotIn(preview_row["contact"]["address"], persona_html)
            self.assertNotIn(preview_row["finance"]["iban"], persona_html)

    def test_persona_example_can_generate_markdown_bundle_with_index(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = json.loads((REPO_ROOT / "examples" / "persona-belgium.json").read_text(encoding="utf-8"))
            output_path = Path(tmp_dir) / "persona-md"
            config["records"] = 1
            config["output"] = {"format": "markdown", "path": str(output_path)}
            config_path = Path(tmp_dir) / "persona-markdown-config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--config", str(config_path)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["output"]["format"], "markdown")
            index_path = output_path / "index.md"
            self.assertTrue(index_path.exists())
            index_markdown = index_path.read_text(encoding="utf-8")
            self.assertIn("| Naam | Rol | Woonplaats | Samenvatting |", index_markdown)
            persona_pages = list(output_path.glob("persona-*.md"))
            self.assertEqual(len(persona_pages), 1)
            persona_markdown = persona_pages[0].read_text(encoding="utf-8")
            self.assertIn("# ", persona_markdown)
            self.assertIn("## Biografie", persona_markdown)
            self.assertNotIn(payload["preview"][0]["identity"]["national_id_number"], persona_markdown)

    def test_bundle_render_localizes_structured_values_for_dutch_locale(self):
        row = {
            "identity": {
                "first_name": "Alex",
                "last_name": "Morgan",
                "gender": "M",
                "nationality": "Belgian",
                "marital_status": "divorced",
                "preferred_pronouns": "he/him",
            },
            "contact": {
                "region": "BXL",
                "city": "Gent",
                "province": "East Flanders",
                "country": "Belgium",
            },
            "professional": {
                "job_title": "Bookkeeper",
                "industry": "Finance",
                "work_pattern": "structured daytime schedule",
                "sector_type": "public sector",
                "organization_type": "school network",
                "employer_scale": "municipal or regional institution",
                "income_bracket": "upper-middle",
                "education_profile": {
                    "level": "Master's degree",
                    "institution_type": "university",
                    "instruction_language": "Dutch or French",
                },
            },
            "mobility": {
                "driving_frequency": "weekends and occasional errands",
                "travel_frequency": "one or two leisure trips per year",
                "primary_commute_mode": "train",
                "public_transport_use": "occasional",
                "travel_style": "well-planned, family-friendly trips",
            },
            "household_context": {
                "housing_type": "row house",
                "ownership_status": "owner",
                "neighborhood_type": "small-town",
            },
            "lifestyle": {
                "hobbies": ["hiking", "DIY projects"],
                "languages_spoken": ["Dutch", "French", "English"],
                "pet": "dog",
                "values": ["independence", "planning"],
                "personality_type": "pragmatic and calm",
                "favorite_vacation_destinations": ["Black Forest", "Antwerp"],
            },
            "digital": {
                "device_use": "budget-conscious shopping, messaging, and one value-focused streaming subscription",
                "privacy_awareness": "moderate-to-high",
                "posting_frequency": "low",
            },
            "finance": {
                "income_level": "stable middle-income household",
                "preferred_payment_methods": ["debit card", "mobile payment"],
            },
            "life_timeline": [
                {
                    "date": "2024-01-01",
                    "category": "career",
                    "title": "Current role",
                    "description": "Alex Morgan nam de huidige rol als boekhouder op bij Voorbeeld NV.",
                }
            ],
        }
        persona = {
            "name": "Alex Morgan",
            "role": "Bookkeeper",
            "city": "Gent",
            "description": "",
            "short_description": "Alex Morgan is 35 jaar en werkt als boekhouder in Gent.",
            "filename": "persona-001-alex-morgan",
        }

        html_output = generate_data.render_persona_html(row, persona, locale="nl_BE")
        markdown_output = generate_data.render_persona_markdown(row, persona, locale="nl_BE")
        index_html = generate_data.render_persona_index_html([persona], "Test", locale="nl_BE")
        index_markdown = generate_data.render_persona_index_markdown([persona], "Test", locale="nl_BE")

        self.assertIn("boekhouder", html_output)
        self.assertIn("gestructureerd dagschema", html_output)
        self.assertIn("publieke sector", html_output)
        self.assertIn("scholennetwerk", html_output)
        self.assertIn("trein", html_output)
        self.assertIn("Huidige functie", html_output)
        self.assertIn("carriere", html_output)
        self.assertIn("rijwoning", html_output)
        self.assertIn("Nederlands", html_output)
        self.assertIn("Voornaam", html_output)
        self.assertIn("Belgisch", html_output)
        self.assertIn("gescheiden", html_output)
        self.assertIn("hij/hem", html_output)
        self.assertIn("Oost-Vlaanderen", html_output)
        self.assertIn("Belgie", html_output)
        self.assertIn("Opleidingsprofiel", html_output)
        self.assertIn("universiteit", html_output)
        self.assertIn("Nederlands of Frans", html_output)
        self.assertIn("Hobby&#x27;s", html_output)
        self.assertIn("Huisdier", html_output)
        self.assertIn("hond", html_output)
        self.assertIn("wandelen", html_output)
        self.assertIn("onafhankelijkheid", html_output)
        self.assertIn("pragmatisch en kalm", html_output)
        self.assertIn("Zwarte Woud", html_output)
        self.assertIn("Antwerpen", html_output)
        self.assertIn("prijsbewust winkelen, berichten en een voordelig streamingabonnement", html_output)
        self.assertIn("matig tot hoog", html_output)
        self.assertIn("stabiel middeninkomenshuishouden", html_output)
        self.assertIn("betaalkaart", html_output)
        self.assertIn("boekhouder", markdown_output)
        self.assertIn("gestructureerd dagschema", markdown_output)
        self.assertIn("Huidige functie", markdown_output)
        self.assertIn("Nationaliteit", markdown_output)
        self.assertIn("wandelen", markdown_output)
        self.assertIn("| [Alex Morgan](persona-001-alex-morgan.md) | boekhouder | Gent |", index_markdown)
        self.assertIn(">boekhouder<", index_html)

    def test_bundle_render_localizes_structured_values_for_french_locale(self):
        row = {
            "identity": {
                "first_name": "Alex",
                "nationality": "Belgian",
                "marital_status": "married",
                "preferred_pronouns": "she/her",
            },
            "contact": {
                "province": "Brussels-Capital",
                "country": "Belgium",
            },
            "professional": {
                "job_title": "Bookkeeper",
                "industry": "Finance",
                "work_pattern": "hybrid office schedule",
                "sector_type": "nonprofit or community sector",
                "organization_type": "community service organization",
                "employer_scale": "regional support network",
                "education_profile": {
                    "level": "Bachelor's degree",
                    "institution_type": "university college",
                    "instruction_language": "Dutch or French",
                },
            },
            "mobility": {
                "primary_commute_mode": "bike",
                "public_transport_use": "frequent",
            },
            "lifestyle": {
                "hobbies": ["hiking"],
                "pet": "cat",
                "values": ["community"],
                "personality_type": "patient and structured",
                "favorite_vacation_destinations": ["Belgian coast", "Ghent"],
            },
            "digital": {
                "privacy_awareness": "high",
                "posting_frequency": "occasional",
            },
            "finance": {
                "income_level": "carefully budgeted household",
                "preferred_payment_methods": ["credit card", "mobile payment"],
            },
            "life_timeline": [
                {
                    "date": "2024-01-01",
                    "category": "career",
                    "title": "Career start",
                    "description": "Alex Morgan est entre dans la vie professionnelle comme comptable.",
                }
            ],
        }
        persona = {
            "name": "Alex Morgan",
            "role": "Bookkeeper",
            "city": "Namur",
            "description": "",
            "short_description": "Alex Morgan a 35 ans et travaille comme comptable a Namur.",
            "filename": "persona-001-alex-morgan",
        }

        html_output = generate_data.render_persona_html(row, persona, locale="fr_BE")
        self.assertIn("comptable", html_output)
        self.assertIn("organisation hybride bureau-domicile", html_output)
        self.assertIn("secteur associatif ou communautaire", html_output)
        self.assertIn("organisation de service communautaire", html_output)
        self.assertIn("velo", html_output)
        self.assertIn("Debut de carriere", html_output)
        self.assertIn("carriere", html_output)
        self.assertIn("Prenom", html_output)
        self.assertIn("Belge", html_output)
        self.assertIn("marie", html_output)
        self.assertIn("elle", html_output)
        self.assertIn("Bruxelles-Capitale", html_output)
        self.assertIn("Belgique", html_output)
        self.assertIn("Profil D&#x27;etudes", html_output)
        self.assertIn("haute ecole", html_output)
        self.assertIn("neerlandais ou francais", html_output)
        self.assertIn("Loisirs", html_output)
        self.assertIn("Animal De Compagnie", html_output)
        self.assertIn("chat", html_output)
        self.assertIn("randonnee", html_output)
        self.assertIn("esprit de communaute", html_output)
        self.assertIn("patient et structure", html_output)
        self.assertIn("cote belge", html_output)
        self.assertIn("Gand", html_output)
        self.assertIn("elevee", html_output)
        self.assertIn("occasionnelle", html_output)
        self.assertIn("menage au budget soigneusement gere", html_output)
        self.assertIn("carte de credit", html_output)

    def test_persona_html_bundle_can_include_sensitive_fields_when_requested(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = json.loads((REPO_ROOT / "examples" / "persona-belgium.json").read_text(encoding="utf-8"))
            output_path = Path(tmp_dir) / "persona-site-sensitive"
            config["records"] = 1
            config["output"] = {
                "format": "html",
                "path": str(output_path),
                "include_sensitive_fields": True,
                "title": "QA Persona Bundle",
            }
            config_path = Path(tmp_dir) / "persona-html-sensitive-config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--config", str(config_path)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            persona_page = next(output_path.glob("persona-*.html"))
            persona_html = persona_page.read_text(encoding="utf-8")
            preview_row = payload["preview"][0]
            self.assertIn("QA Persona Bundle", (output_path / "index.html").read_text(encoding="utf-8"))
            self.assertIn(preview_row["identity"]["national_id_number"], persona_html)
            self.assertIn(preview_row["contact"]["email"], persona_html)
            self.assertIn(preview_row["finance"]["iban"], persona_html)

    def test_biography_uses_correct_indefinite_article_for_profession(self):
        row = {
            "life_timeline": [
                {"category": "education", "title": "Completed a bachelor's degree"},
                {"category": "career", "title": "Current role"},
            ],
            "identity": {"full_name": "Alex Example"},
            "contact": {"city": "Brussels"},
            "professional": {
                "education_level": "Bachelor's degree",
                "job_title": "Accountant",
            },
        }
        row_context = {"__root__": row, "__current__": row}

        biography = generate_data.build_biography_from_timeline(
            row_context=row_context,
            params={
                "timeline_field": "life_timeline",
                "full_name_field": "identity.full_name",
                "city_field": "contact.city",
                "education_level_field": "professional.education_level",
                "profession_field": "professional.job_title",
                "style": "direct",
            },
            field_name="biography",
        )

        self.assertIn("as an Accountant", biography)

    def test_biography_does_not_invent_relationship_milestones_for_single_persona(self):
        row = {
            "life_timeline": [
                {"category": "education", "title": "Completed a bachelor's degree"},
                {"category": "career", "title": "Current role"},
                {"category": "family", "title": "Established an independent household"},
            ],
            "identity": {"full_name": "Alex Example", "marital_status": "single"},
            "contact": {"city": "Brussels"},
            "professional": {
                "education_level": "Bachelor's degree",
                "job_title": "Designer",
            },
            "family": {},
        }
        row_context = {"__root__": row, "__current__": row}

        biography = generate_data.build_biography_from_timeline(
            row_context=row_context,
            params={
                "timeline_field": "life_timeline",
                "full_name_field": "identity.full_name",
                "city_field": "contact.city",
                "education_level_field": "professional.education_level",
                "profession_field": "professional.job_title",
                "marital_status_field": "identity.marital_status",
                "spouse_field": "family.spouse",
                "style": "direct",
            },
            field_name="biography",
        )

        self.assertNotIn("Partnership milestones", biography)

    def test_cli_can_generate_sql_from_schema_only_config(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.json"
            output_path = Path(tmp_dir) / "profiles.sql"
            config_path.write_text(
                json.dumps(
                    {
                        "records": 2,
                        "locale": "nl_BE",
                        "seed": 4,
                        "sql_schema": {
                            "ddl": "CREATE TABLE profile_seed (first_name VARCHAR(50), email VARCHAR(255), active BOOLEAN);"
                        },
                        "output": {"format": "sql", "path": str(output_path)},
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--config", str(config_path)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["output"]["format"], "sql")
            self.assertEqual(payload["output"]["table_name"], "profile_seed")
            self.assertTrue(output_path.exists())
            script = output_path.read_text(encoding="utf-8")
            self.assertIn('INSERT INTO "profile_seed"', script)

    def test_population_model_filters_subset_and_is_repeatable(self):
        config = {
            "records": 6,
            "seed": 17,
            "population_model": {
                "filters": {
                    "sex": ["M"],
                },
                "segments": [
                    {"weight": 0.49, "values": {"sex": "M", "age_band": "Y18T44"}},
                    {"weight": 0.51, "values": {"sex": "F", "age_band": "Y18T44"}},
                ],
            },
            "fields": [
                {"name": "sex", "type": "segment_value", "params": {"key": "sex"}},
                {
                    "name": "first_name",
                    "type": "faker_from_segment",
                    "params": {
                        "segment_key": "sex",
                        "providers": {
                            "M": "first_name_male",
                            "F": "first_name_female",
                        },
                        "fallback_provider": "first_name",
                    },
                },
            ],
        }

        first = generate_data.generate_dataset(config, custom_formats={})
        second = generate_data.generate_dataset(config, custom_formats={})

        self.assertEqual(first, second)
        self.assertTrue(all(row["sex"] == "M" for row in first))

    def test_birth_date_from_statbel_age_band_stays_within_range(self):
        config = {
            "records": 8,
            "seed": 23,
            "population_model": {
                "segments": [
                    {"weight": 1.0, "values": {"age_band": "Y65PL"}},
                ],
            },
            "fields": [
                {
                    "name": "birth_date",
                    "type": "birth_date_from_age_band",
                    "params": {
                        "segment_key": "age_band",
                        "reference_date": "2023-01-01",
                        "default_max_age": 105,
                    },
                }
            ],
        }

        rows = generate_data.generate_dataset(config, custom_formats={})
        reference_date = date.fromisoformat("2023-01-01")

        for row in rows:
            birth_date = date.fromisoformat(row["birth_date"])
            age = reference_date.year - birth_date.year - (
                (reference_date.month, reference_date.day) < (birth_date.month, birth_date.day)
            )
            self.assertGreaterEqual(age, 65)
            self.assertLessEqual(age, 105)

    def test_cli_summary_includes_representativeness(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "representative.json"
            config_path.write_text(
                json.dumps(
                    {
                        "records": 2,
                        "seed": 31,
                        "population_model": {
                            "scope": {"country": "BE", "level": "nuts3", "code": "BE100"},
                            "dimensions": [
                                {
                                    "name": "sex",
                                    "source": {
                                        "catalog_id": "statbel-open-data-api",
                                        "dataset": "tf_hvd_demo_population",
                                        "column": "CD_SEX",
                                    },
                                }
                            ],
                            "segments": [
                                {"weight": 0.5, "values": {"sex": "M"}},
                                {"weight": 0.5, "values": {"sex": "F"}},
                            ],
                        },
                        "fields": [
                            {"name": "sex", "type": "segment_value", "params": {"key": "sex"}},
                            {"name": "email", "type": "email"},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--config", str(config_path), "--validate-only"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("representativeness", payload)
            self.assertEqual(payload["representativeness"]["mode"], "weighted_population_segments")
            self.assertEqual(
                payload["representativeness"]["distribution_backed_fields"][0]["dimension"],
                "sex",
            )
            self.assertIn("email", payload["representativeness"]["non_distribution_fields"])

    def test_cli_summary_includes_nested_distribution_backed_fields(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "representative-nested.json"
            config_path.write_text(
                json.dumps(
                    {
                        "records": 1,
                        "seed": 31,
                        "population_model": {
                            "scope": {"country": "BE"},
                            "dimensions": [{"name": "sex"}],
                            "segments": [{"weight": 1.0, "values": {"sex": "F"}}],
                        },
                        "fields": [
                            {
                                "name": "identity",
                                "type": "object",
                                "params": {
                                    "fields": [
                                        {"name": "gender", "type": "segment_value", "params": {"key": "sex"}},
                                    ]
                                },
                            },
                            {"name": "email", "type": "email"},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--config", str(config_path), "--validate-only"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            covered_fields = payload["representativeness"]["distribution_backed_fields"]
            self.assertEqual(covered_fields[0]["field_name"], "identity.gender")
            self.assertEqual(covered_fields[0]["dimension"], "sex")

    def test_source_query_builds_segments_from_live_rows(self):
        config = {
            "records": 6,
            "seed": 19,
            "population_model": {
                "source_query": {
                    "base_url": "https://example.test",
                    "dataset": "population",
                    "weight_column": "MS_VALUE",
                    "dimension_columns": {
                        "sex": "CD_SEX",
                        "age_band": "CD_AGE",
                    },
                    "dimension_value_maps": {
                        "age_band": {
                            "Y0T4": "Y0T19",
                            "Y5T9": "Y0T19",
                        }
                    },
                    "filters": {
                        "CD_YEAR": 2023,
                        "CD_SEX": {"op": "in", "value": ["M", "F"]},
                    },
                }
            },
            "fields": [
                {"name": "sex", "type": "segment_value", "params": {"key": "sex"}},
                {"name": "age_band", "type": "segment_value", "params": {"key": "age_band"}},
            ],
        }
        fake_rows = [
            {"CD_SEX": "M", "CD_AGE": "Y0T4", "MS_VALUE": 60},
            {"CD_SEX": "F", "CD_AGE": "Y5T9", "MS_VALUE": 40},
        ]

        with patch.object(generate_data.urllib.request, "urlopen", return_value=FakeUrlopenResponse(fake_rows)):
            rows = generate_data.generate_dataset(config, custom_formats={})

        self.assertEqual(len(rows), 6)
        self.assertTrue(all(row["age_band"] == "Y0T19" for row in rows))
        self.assertTrue({row["sex"] for row in rows}.issubset({"M", "F"}))

    def test_open_data_update_report_detects_new_datasets_and_column_drift(self):
        expected_source = {
            "id": "statbel-open-data-api",
            "last_verified": "2026-03-19",
            "datasets": [
                {
                    "id": "dataset_a",
                    "columns": {
                        "COL_1": "text",
                    },
                }
            ],
        }
        live_source = {
            "id": "statbel-open-data-api",
            "discovery_endpoint": "https://example.test/discovery",
            "datasets": [
                {
                    "id": "dataset_a",
                    "columns": {
                        "COL_1": "bigint",
                        "COL_2": "text",
                    },
                },
                {
                    "id": "dataset_b",
                    "columns": {
                        "COL_X": "text",
                    },
                },
            ],
        }

        report = check_open_data_updates.build_update_report(expected_source, live_source)

        self.assertEqual(report["status"], "drift_detected")
        self.assertEqual(report["new_datasets"], ["dataset_b"])
        self.assertEqual(report["changed_datasets"][0]["id"], "dataset_a")
        self.assertEqual(report["changed_datasets"][0]["new_columns"], ["COL_2"])
        self.assertEqual(report["changed_datasets"][0]["type_changes"][0]["column"], "COL_1")
        self.assertEqual(report["changed_datasets"][0]["metadata_changes"], [])

    def test_normalize_eurostat_dataflows_extracts_ids_and_metadata(self):
        xml_payload = b"""<?xml version="1.0" encoding="UTF-8"?>
<m:Structure xmlns:m="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message"
             xmlns:s="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure">
  <m:Structures>
    <s:Dataflows>
      <s:Dataflow id="ABC_1" agencyID="ESTAT" version="1.0" isFinal="false"/>
      <s:Dataflow id="XYZ_2" agencyID="ESTAT" version="2.1" isFinal="true"/>
    </s:Dataflows>
  </m:Structures>
</m:Structure>
"""

        rows = check_open_data_updates.normalize_eurostat_dataflows(xml_payload)

        self.assertEqual([row["id"] for row in rows], ["ABC_1", "XYZ_2"])
        self.assertEqual(rows[0]["metadata"]["version"], "1.0")
        self.assertEqual(rows[1]["metadata"]["is_final"], "true")

    def test_discover_world_bank_source_snapshot_normalizes_sources(self):
        payload = [
            {"total": "2"},
            [
                {
                    "id": "2",
                    "code": "WDI",
                    "name": "World Development Indicators",
                    "lastupdated": "2026-02-24",
                    "dataavailability": "Y",
                    "metadataavailability": "Y",
                },
                {
                    "id": "1",
                    "code": "DBS",
                    "name": "Doing Business",
                    "lastupdated": "2021-08-18",
                    "dataavailability": "Y",
                    "metadataavailability": "Y",
                },
            ],
        ]

        with patch.object(check_open_data_updates, "get_discovery_endpoint_by_suffix", return_value="https://api.worldbank.org/v2/sources?format=json&per_page=200"), patch.object(
            generate_data,
            "fetch_json_url",
            return_value=payload,
        ):
            snapshot = check_open_data_updates.discover_world_bank_source_snapshot("world-bank-data")

        self.assertEqual(snapshot["dataset_count"], 2)
        self.assertEqual([row["id"] for row in snapshot["datasets"]], ["1", "2"])
        self.assertEqual(snapshot["datasets"][1]["metadata"]["code"], "WDI")

    def test_discover_data_gov_be_source_snapshot_normalizes_export_files(self):
        payload = [
            {
                "name": "datagovbe.nt.gz",
                "type": "file",
                "size": 123,
                "sha": "abc123",
                "download_url": "https://raw.githubusercontent.com/fedict/dcat/main/all/datagovbe.nt.gz",
            },
            {
                "name": "all",
                "type": "dir",
                "size": 0,
                "sha": "ignore-me",
                "download_url": None,
            },
            {
                "name": "licenses.nt",
                "type": "file",
                "size": 456,
                "sha": "def456",
                "download_url": "https://raw.githubusercontent.com/fedict/dcat/main/all/licenses.nt",
            },
        ]

        with patch.object(
            check_open_data_updates,
            "get_discovery_endpoint_by_suffix",
            return_value="https://api.github.com/repos/fedict/dcat/contents/all",
        ), patch.object(
            generate_data,
            "fetch_json_url",
            return_value=payload,
        ):
            snapshot = check_open_data_updates.discover_data_gov_be_source_snapshot("data-gov-be")

        self.assertEqual(snapshot["dataset_count"], 2)
        self.assertEqual([row["id"] for row in snapshot["datasets"]], ["datagovbe.nt.gz", "licenses.nt"])
        self.assertEqual(snapshot["datasets"][0]["metadata"]["sha"], "abc123")

    def test_normalize_geonames_dump_listing_extracts_files_and_metadata(self):
        html_payload = """<pre>
<img src="/icons/compressed.gif" alt="[   ]"> <a href="allCountries.zip">allCountries.zip</a>        2026-03-19 03:29  354M
<img src="/icons/text.gif" alt="[TXT]"> <a href="countryInfo.txt">countryInfo.txt</a>         2026-03-19 03:36   18K
<img src="/icons/text.gif" alt="[TXT]"> <a href="Readme.txt">Readme.txt</a>              2026-03-19 03:36   12K
</pre>"""

        rows = check_open_data_updates.normalize_geonames_dump_listing(html_payload)

        self.assertEqual([row["id"] for row in rows], ["allCountries.zip", "countryInfo.txt"])
        self.assertEqual(rows[0]["metadata"]["last_modified"], "2026-03-19 03:29")
        self.assertEqual(rows[1]["metadata"]["size"], "18K")

    def test_discover_geonames_source_snapshot_normalizes_dump_listing(self):
        html_payload = b"""<pre>
<img src="/icons/compressed.gif" alt="[   ]"> <a href="cities500.zip">cities500.zip</a>            2026-03-19 03:29   12M
<img src="/icons/text.gif" alt="[TXT]"> <a href="featureCodes_en.txt">featureCodes_en.txt</a>   2026-03-19 03:36   83K
</pre>"""

        with patch.object(
            check_open_data_updates,
            "get_discovery_endpoint_by_suffix",
            return_value="https://download.geonames.org/export/dump/",
        ), patch.object(
            generate_data.urllib.request,
            "urlopen",
            return_value=RawUrlopenResponse(html_payload),
        ):
            snapshot = check_open_data_updates.discover_geonames_source_snapshot("geonames")

        self.assertEqual(snapshot["dataset_count"], 2)
        self.assertEqual([row["id"] for row in snapshot["datasets"]], ["cities500.zip", "featureCodes_en.txt"])
        self.assertEqual(snapshot["datasets"][1]["metadata"]["size"], "83K")

    def test_discover_worldpop_source_snapshot_walks_category_tree(self):
        responses = {
            "https://www.worldpop.org/rest/data": {
                "data": [
                    {"alias": "pop", "name": "Population Counts"},
                    {"alias": "births", "name": "Births"},
                ]
            },
            "https://www.worldpop.org/rest/data/pop": {
                "data": [
                    {"alias": "pic", "name": "Individual countries"},
                ]
            },
            "https://www.worldpop.org/rest/data/pop/pic": {
                "data": [
                    {"id": "1", "title": "Armenia 100m Population", "iso3": "ARM", "popyear": None},
                    {"id": "2", "title": "Azerbaijan 100m Population", "iso3": "AZE", "popyear": None},
                ]
            },
            "https://www.worldpop.org/rest/data/births": {
                "data": [
                    {"alias": "bic", "name": "Individual countries"},
                ]
            },
            "https://www.worldpop.org/rest/data/births/bic": {
                "data": [
                    {"id": "10", "title": "Benin births", "iso3": "BEN", "popyear": "2020"},
                ]
            },
        }

        def fake_fetch_json(url):
            return responses[url]

        with patch.object(
            check_open_data_updates,
            "get_discovery_endpoint_by_suffix",
            return_value="https://www.worldpop.org/rest/data",
        ), patch.object(
            generate_data,
            "fetch_json_url",
            side_effect=fake_fetch_json,
        ):
            snapshot = check_open_data_updates.discover_worldpop_source_snapshot("worldpop")

        self.assertEqual(snapshot["dataset_count"], 7)
        self.assertEqual(
            [row["id"] for row in snapshot["datasets"]],
            [
                "category:births",
                "category:pop",
                "collection:births/bic",
                "collection:pop/pic",
                "dataset:births/bic/10",
                "dataset:pop/pic/1",
                "dataset:pop/pic/2",
            ],
        )
        self.assertEqual(snapshot["datasets"][-1]["metadata"]["iso3"], "AZE")


if __name__ == "__main__":
    unittest.main()
