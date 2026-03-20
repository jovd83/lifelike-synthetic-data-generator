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
