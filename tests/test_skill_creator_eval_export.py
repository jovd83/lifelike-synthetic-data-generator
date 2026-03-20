import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import export_skill_creator_eval_review  # noqa: E402


class SkillCreatorEvalExportTests(unittest.TestCase):
    def test_export_workspace_creates_skill_creator_run_layout(self):
        experiments = [
            {
                "id": "sample-eval",
                "title": "Sample Eval",
                "prompt": "Generate a tiny dataset.",
                "ask": {
                    "target_population": "Sample population",
                    "record_count": 8,
                    "requested_fields": ["sex", "age_band"],
                    "distribution_backed_dimensions": ["sex", "age_band"],
                },
                "config": {
                    "version": "1.0",
                    "locale": "nl_BE",
                    "seed": 1,
                    "records": 8,
                    "population_model": {
                        "scope": {"country": "BE"},
                        "dimensions": [{"name": "sex"}, {"name": "age_band"}],
                        "segments": [
                            {"weight": 0.5, "values": {"sex": "M", "age_band": "Y18T44"}},
                            {"weight": 0.5, "values": {"sex": "F", "age_band": "Y18T44"}},
                        ],
                    },
                    "fields": [
                        {"name": "sex", "type": "segment_value", "params": {"key": "sex"}},
                        {"name": "age_band", "type": "segment_value", "params": {"key": "age_band"}},
                    ],
                },
            }
        ]

        with tempfile.TemporaryDirectory() as tempdir:
            workspace = Path(tempdir) / "workspace"
            eval_id_map, score_rows = export_skill_creator_eval_review.export_workspace(workspace, experiments)

            self.assertEqual(eval_id_map["sample-eval"], 1)
            self.assertEqual(len(score_rows), 1)

            run_dir = workspace / "eval-001" / "with_skill" / "run-1"
            self.assertTrue((run_dir / "outputs" / "dataset.json").exists())
            self.assertTrue((run_dir / "outputs" / "report.html").exists())
            self.assertTrue((run_dir / "outputs" / "summary.json").exists())
            self.assertTrue((run_dir / "grading.json").exists())
            self.assertTrue((run_dir / "timing.json").exists())
            self.assertTrue((run_dir / "eval_metadata.json").exists())

            grading = json.loads((run_dir / "grading.json").read_text(encoding="utf-8"))
            self.assertEqual(grading["summary"]["total"], 5)
            self.assertGreaterEqual(grading["summary"]["pass_rate"], 0.8)

            manifest = json.loads((workspace / "evals.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["skill_name"], "lifelike-synthetic-data-generator")
            self.assertEqual(manifest["evals"][0]["id"], 1)


if __name__ == "__main__":
    unittest.main()
