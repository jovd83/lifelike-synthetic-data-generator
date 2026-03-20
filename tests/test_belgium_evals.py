import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import generate_data  # noqa: E402
import run_belgium_evals  # noqa: E402
from evals.belgium_experiments import get_experiments  # noqa: E402


class BelgiumEvalTests(unittest.TestCase):
    def test_belgian_iban_validator_accepts_known_valid_value(self):
        self.assertTrue(run_belgium_evals.iban_mod97("BE68539007547034"))

    def test_localization_checks_cover_insz_and_birth_date_alignment(self):
        config = generate_data.normalize_config(
            {
                "version": "1.0",
                "locale": "nl_BE",
                "seed": 3,
                "records": 2,
                "population_model": {
                    "scope": {"country": "BE"},
                    "dimensions": [{"name": "sex"}, {"name": "age_band"}],
                    "segments": [
                        {"weight": 1.0, "values": {"sex": "F", "age_band": "Y18T44"}},
                    ],
                },
                "fields": [
                    {"name": "sex", "type": "segment_value", "params": {"key": "sex"}},
                    {"name": "age_band", "type": "segment_value", "params": {"key": "age_band"}},
                    {
                        "name": "birth_date",
                        "type": "birth_date_from_age_band",
                        "params": {"segment_key": "age_band", "reference_date": "2023-01-01"},
                    },
                    {"name": "insz", "type": "belgian_insz"},
                ],
            }
        )
        rows = generate_data.generate_dataset(config, custom_formats=generate_data.load_custom_formats(), already_normalized=True)
        checks = run_belgium_evals.build_validation_checks(config, generate_data.load_custom_formats())
        result = run_belgium_evals.evaluate_localization(rows, checks)

        self.assertGreaterEqual(result["overall_pass_rate"], 0.99)

    def test_statistics_score_is_perfect_when_rows_match_expected_cells(self):
        config = generate_data.normalize_config(
            {
                "version": "1.0",
                "locale": "nl_BE",
                "seed": 1,
                "records": 4,
                "population_model": {
                    "scope": {"country": "BE"},
                    "dimensions": [{"name": "sex"}],
                    "segments": [
                        {"weight": 0.5, "values": {"sex": "M"}},
                        {"weight": 0.5, "values": {"sex": "F"}},
                    ],
                },
                "fields": [
                    {"name": "sex", "type": "segment_value", "params": {"key": "sex"}},
                ],
            }
        )
        rows = [{"sex": "M"}, {"sex": "M"}, {"sex": "F"}, {"sex": "F"}]
        statistics = run_belgium_evals.evaluate_statistics(rows, config)
        self.assertEqual(statistics["joint"]["score"], 1.0)

    def test_east_flanders_address_experiment_uses_coherent_catalog_addresses(self):
        experiment = next(item for item in get_experiments() if item["id"] == "be-04-elderly-women-marital")
        config = generate_data.normalize_config(experiment["config"])
        rows = generate_data.generate_dataset(config, custom_formats=generate_data.load_custom_formats(), already_normalized=True)
        known_addresses = {
            (item["street_address"], item["postcode"], item["city"], item["region"])
            for item in generate_data.load_belgian_address_catalog()
        }
        self.assertTrue(rows)
        self.assertTrue(all(row["postcode"].startswith("9") for row in rows))
        self.assertTrue(
            all((row["street_address"], row["postcode"], row["city"], row["region"]) in known_addresses for row in rows)
        )

    def test_east_flanders_catalog_filter_is_broader_than_three_cities(self):
        filtered = generate_data.filter_belgian_address_catalog(
            generate_data.load_belgian_address_catalog(),
            {"region": "VLG", "postcode_prefix": "9"},
            segment_values=None,
            field_name="test",
        )
        self.assertGreater(len({row["city"] for row in filtered}), 20)
        self.assertGreater(len({row["postcode"] for row in filtered}), 20)

    def test_experiment_catalog_contains_requested_hard_cases(self):
        experiments = get_experiments()
        by_id = {item["id"]: item for item in experiments}

        self.assertIn("be-11-zipcode-hotspots", by_id)
        self.assertIn("postcode", by_id["be-11-zipcode-hotspots"]["ask"]["distribution_backed_dimensions"])

        self.assertIn("be-12-known-degrees", by_id)
        self.assertIn("degree_level", by_id["be-12-known-degrees"]["ask"]["distribution_backed_dimensions"])
        degree_segments = by_id["be-12-known-degrees"]["config"]["population_model"]["segments"]
        degree_values = {segment["values"]["degree_level"] for segment in degree_segments}
        self.assertTrue({"secondary", "bachelor", "master", "phd"}.issubset(degree_values))

        self.assertIn("be-13-full-occupation-taxonomy", by_id)
        occupation_segments = by_id["be-13-full-occupation-taxonomy"]["config"]["population_model"]["segments"]
        occupation_values = {segment["values"]["occupation_status"] for segment in occupation_segments}
        self.assertTrue({"employed", "unemployed", "self-employed", "retired", "student"}.issubset(occupation_values))

        self.assertIn("be-14-car-brand-households", by_id)
        self.assertIn("car_brand", by_id["be-14-car-brand-households"]["ask"]["distribution_backed_dimensions"])

        self.assertIn("be-15-exact-ages", by_id)
        self.assertIn("exact_age", by_id["be-15-exact-ages"]["ask"]["distribution_backed_dimensions"])
        exact_age_segments = by_id["be-15-exact-ages"]["config"]["population_model"]["segments"]
        self.assertTrue(all(isinstance(segment["values"]["exact_age"], int) for segment in exact_age_segments))

        self.assertIn("be-16-elderly-flanders-low-income-widowed", by_id)
        elderly_segments = by_id["be-16-elderly-flanders-low-income-widowed"]["config"]["population_model"]["segments"]
        self.assertTrue(all(segment["values"]["region"] == "VLG" for segment in elderly_segments))
        self.assertTrue(all(segment["values"]["marital_status"] == "widowed" for segment in elderly_segments))
        self.assertTrue(all(segment["values"]["income_quintile"] in {"Q1", "Q2"} for segment in elderly_segments))

        financial_age_values = {
            segment["values"]["age_band"] for segment in by_id["be-08-financial-customers"]["config"]["population_model"]["segments"]
        }
        self.assertIn("Y18T24", financial_age_values)
        self.assertIn("Y65PL", financial_age_values)

        mobility_age_values = {
            segment["values"]["age_band"] for segment in by_id["be-09-mobility-profiles"]["config"]["population_model"]["segments"]
        }
        self.assertIn("Y55T74", mobility_age_values)

        self.assertIn("eu-01-western-europe-education-workforce", by_id)
        eu_dims = by_id["eu-01-western-europe-education-workforce"]["ask"]["distribution_backed_dimensions"]
        self.assertTrue({"country_code", "degree_level", "employment_status"}.issubset(eu_dims))

        self.assertIn("world-01-global-urban-profiles", by_id)
        world_dims = by_id["world-01-global-urban-profiles"]["ask"]["distribution_backed_dimensions"]
        self.assertTrue({"continent", "density_tier", "income_tier"}.issubset(world_dims))

    def test_mixed_sex_experiments_do_not_default_to_exact_parity(self):
        experiments = get_experiments()
        for experiment in experiments:
            totals = {"M": 0.0, "F": 0.0}
            for segment in experiment["config"]["population_model"]["segments"]:
                sex_value = segment["values"].get("sex")
                if sex_value in totals:
                    totals[sex_value] += segment["weight"]
            if totals["M"] and totals["F"]:
                self.assertNotAlmostEqual(
                    totals["M"],
                    totals["F"],
                    places=9,
                    msg=f"{experiment['id']} still uses exact male/female parity instead of an intentional scenario-specific split.",
                )


if __name__ == "__main__":
    unittest.main()
