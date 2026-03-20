#!/usr/bin/env python

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from time import perf_counter

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_data
import run_belgium_evals
from evals.belgium_experiments import get_experiments


DEFAULT_OUTPUT_DIR = ROOT_DIR / "artifacts" / "evals" / "skill-creator"
DEFAULT_WORKSPACE_DIR = DEFAULT_OUTPUT_DIR / "workspace"
DEFAULT_STATIC_REVIEW = DEFAULT_OUTPUT_DIR / "review.html"
DEFAULT_AGGREGATE_SCRIPT = (
    Path.home()
    / ".agents"
    / "skills"
    / "skill-creator"
    / "scripts"
    / "aggregate_benchmark.py"
)
DEFAULT_VIEWER_SCRIPT = (
    Path.home()
    / ".agents"
    / "skills"
    / "skill-creator"
    / "eval-viewer"
    / "generate_review.py"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export the synthetic-data evals into the skill-creator evaluation workspace and render its review HTML."
    )
    parser.add_argument("--workspace-dir", default=str(DEFAULT_WORKSPACE_DIR), help="Skill-creator workspace directory to write.")
    parser.add_argument("--static-review", default=str(DEFAULT_STATIC_REVIEW), help="Path for the generated static HTML review.")
    parser.add_argument("--aggregate-script", default=str(DEFAULT_AGGREGATE_SCRIPT), help="Path to skill-creator aggregate_benchmark.py.")
    parser.add_argument("--viewer-script", default=str(DEFAULT_VIEWER_SCRIPT), help="Path to skill-creator eval-viewer/generate_review.py.")
    parser.add_argument("--experiment-id", action="append", dest="experiment_ids", help="Experiment id to export. Repeat to export multiple.")
    parser.add_argument("--skip-static-review", action="store_true", help="Build the workspace and benchmark only, without rendering the static viewer.")
    return parser.parse_args()


def build_expectations(experiment: dict, rows: list[dict], localization: dict, statistics: dict) -> list[dict]:
    requested_fields = experiment["ask"]["requested_fields"]
    represented_dimensions = experiment["ask"]["distribution_backed_dimensions"]
    row_has_requested_fields = all(all(field in row for field in requested_fields) for row in rows)
    represented_present = all(any(dimension in row for row in rows) for dimension in represented_dimensions)
    expectations = [
        {
            "text": "The dataset contains the requested number of rows.",
            "passed": len(rows) == experiment["ask"]["record_count"],
            "evidence": f"Expected {experiment['ask']['record_count']} rows and generated {len(rows)} rows.",
        },
        {
            "text": "All requested output fields are present in the generated records.",
            "passed": row_has_requested_fields,
            "evidence": f"Requested fields: {', '.join(requested_fields)}.",
        },
        {
            "text": "Localization and format adherence remain at or above 99%.",
            "passed": localization["overall_pass_rate"] >= 0.99,
            "evidence": f"Observed localization score: {localization['overall_pass_rate'] * 100:.2f}%.",
        },
        {
            "text": "Joint statistical fit remains at or above 95% for the represented dimensions.",
            "passed": statistics["joint"]["score"] >= 0.95,
            "evidence": f"Observed joint fit: {statistics['joint']['score'] * 100:.2f}% across {', '.join(statistics['dimensions'])}.",
        },
        {
            "text": "Every requested represented dimension appears in the dataset rows.",
            "passed": represented_present,
            "evidence": f"Represented dimensions: {', '.join(represented_dimensions)}.",
        },
    ]
    return expectations


def build_grading(
    experiment: dict,
    rows: list[dict],
    localization: dict,
    statistics: dict,
    dataset_path: Path,
    report_path: Path,
    duration_seconds: float,
) -> dict:
    expectations = build_expectations(experiment, rows, localization, statistics)
    passed = sum(1 for item in expectations if item["passed"])
    failed = len(expectations) - passed
    config = experiment["config"]
    scenario_backed = [
        dimension["name"]
        for dimension in config["population_model"]["dimensions"]
        if "source" not in dimension
    ]
    notes = []
    if scenario_backed:
        notes.append(
            "Scenario-backed represented dimensions remain in this experiment: " + ", ".join(scenario_backed) + "."
        )
    return {
        "expectations": expectations,
        "summary": {
            "passed": passed,
            "failed": failed,
            "total": len(expectations),
            "pass_rate": passed / len(expectations) if expectations else 0.0,
        },
        "execution_metrics": {
            "tool_calls": {
                "GenerateDataset": 1,
                "EvaluateLocalization": 1,
                "EvaluateStatistics": 1,
                "RenderReport": 1,
            },
            "total_tool_calls": 4,
            "total_steps": 4,
            "errors_encountered": 0,
            "output_chars": dataset_path.stat().st_size + report_path.stat().st_size,
            "transcript_chars": len(experiment["prompt"]),
        },
        "timing": {
            "executor_duration_seconds": round(duration_seconds, 4),
            "grader_duration_seconds": 0.0,
            "total_duration_seconds": round(duration_seconds, 4),
        },
        "claims": [
            {
                "claim": "The generated dataset honors the requested row count.",
                "type": "factual",
                "verified": len(rows) == experiment["ask"]["record_count"],
                "evidence": f"Generated {len(rows)} rows.",
            },
            {
                "claim": "The represented population fit is strong.",
                "type": "analytical",
                "verified": statistics["joint"]["score"] >= 0.95,
                "evidence": f"Joint fit score: {statistics['joint']['score'] * 100:.2f}%.",
            },
        ],
        "user_notes_summary": {
            "uncertainties": notes,
            "needs_review": [],
            "workarounds": [
                "This skill-creator export packages the repo's native eval harness results instead of replaying a separate blind comparator loop."
            ],
        },
        "eval_feedback": {
            "overall": "The packaged eval exposes both localization quality and distribution fit in the skill-creator viewer.",
        },
    }


def build_evals_manifest(experiments: list[dict], eval_id_map: dict[str, int]) -> dict:
    return {
        "skill_name": "lifelike-synthetic-data-generator",
        "evals": [
            {
                "id": eval_id_map[experiment["id"]],
                "prompt": experiment["prompt"],
                "expected_output": (
                    "A realistic synthetic dataset localized to the requested scope while preserving the requested represented dimensions."
                ),
                "expectations": [item["text"] for item in build_expectations(experiment, [{}] * 0, {"overall_pass_rate": 0.0}, {"joint": {"score": 0.0}, "dimensions": experiment["ask"]["distribution_backed_dimensions"]})],
            }
            for experiment in experiments
        ],
    }


def summarize_notes(experiments: list[dict], score_rows: list[dict]) -> list[str]:
    if not score_rows:
        return []
    lowest_joint = min(score_rows, key=lambda item: item["joint_fit"])
    highest_joint = max(score_rows, key=lambda item: item["joint_fit"])
    broad_scope = [item["id"] for item in experiments if item["id"].startswith(("eu-", "world-"))]
    return [
        f"Exported {len(score_rows)} experiments into the skill-creator workspace using only the with_skill configuration.",
        f"Lowest joint statistical fit: {lowest_joint['id']} at {lowest_joint['joint_fit'] * 100:.2f}%.",
        f"Highest joint statistical fit: {highest_joint['id']} at {highest_joint['joint_fit'] * 100:.2f}%.",
        "Broader-than-Belgium scope cases included: " + (", ".join(broad_scope) if broad_scope else "none") + ".",
    ]


def enrich_benchmark(benchmark_path: Path, experiments: list[dict], eval_id_map: dict[str, int], score_rows: list[dict]) -> None:
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    title_by_eval_id = {eval_id_map[experiment["id"]]: experiment["title"] for experiment in experiments}
    score_by_eval_id = {eval_id_map[row["id"]]: row for row in score_rows}
    for run in benchmark.get("runs", []):
        eval_id = run.get("eval_id")
        run["eval_name"] = title_by_eval_id.get(eval_id, f"Eval {eval_id}")
        score_row = score_by_eval_id.get(eval_id)
        if score_row:
            run.setdefault("notes", []).append(
                f"Localization {score_row['localization'] * 100:.2f}% and joint fit {score_row['joint_fit'] * 100:.2f}%."
            )
    benchmark["metadata"]["skill_name"] = "lifelike-synthetic-data-generator"
    benchmark["metadata"]["skill_path"] = str(ROOT_DIR)
    benchmark["metadata"]["executor_model"] = "repo-native-eval-runner"
    benchmark["metadata"]["analyzer_model"] = "skill-creator-aggregate-benchmark"
    benchmark["metadata"]["runs_per_configuration"] = 1
    config_keys = [key for key in benchmark.get("run_summary", {}) if key != "delta"]
    if len(config_keys) < 2:
        benchmark["run_summary"]["delta"] = {
            "pass_rate": "n/a",
            "time_seconds": "n/a",
            "tokens": "n/a",
        }
    benchmark["notes"] = summarize_notes(experiments, score_rows)
    benchmark_path.write_text(json.dumps(benchmark, indent=2) + "\n", encoding="utf-8")
    benchmark_path.with_suffix(".md").write_text(render_benchmark_markdown(benchmark), encoding="utf-8")


def render_benchmark_markdown(benchmark: dict) -> str:
    with_skill = benchmark["run_summary"].get("with_skill", {})
    pass_rate = with_skill.get("pass_rate", {})
    time_seconds = with_skill.get("time_seconds", {})
    tokens = with_skill.get("tokens", {})
    lines = [
        "# Skill Benchmark: lifelike-synthetic-data-generator",
        "",
        "This package represents a single-configuration `with_skill` review exported from the repository's native eval harness into the `skill-creator` workspace format.",
        "",
        "## Summary",
        "",
        f"- Pass rate: {pass_rate.get('mean', 0) * 100:.0f}% +/- {pass_rate.get('stddev', 0) * 100:.0f}%",
        f"- Time: {time_seconds.get('mean', 0):.1f}s +/- {time_seconds.get('stddev', 0):.1f}s",
        f"- Output size proxy: {tokens.get('mean', 0):.0f} +/- {tokens.get('stddev', 0):.0f} bytes",
        "",
        "## Notes",
        "",
    ]
    lines.extend(f"- {note}" for note in benchmark.get("notes", []))
    return "\n".join(lines) + "\n"


def run_subprocess(command: list[str], workdir: Path) -> None:
    subprocess.run(command, cwd=str(workdir), check=True)


def export_workspace(workspace_dir: Path, experiments: list[dict]) -> tuple[dict[str, int], list[dict]]:
    if workspace_dir.exists():
        shutil.rmtree(workspace_dir)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    custom_formats = generate_data.load_custom_formats()
    eval_id_map = {experiment["id"]: index for index, experiment in enumerate(experiments, start=1)}
    score_rows = []

    for experiment in experiments:
        eval_id = eval_id_map[experiment["id"]]
        run_dir = workspace_dir / f"eval-{eval_id:03d}" / "with_skill" / "run-1"
        outputs_dir = run_dir / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)

        config = json.loads(json.dumps(experiment["config"]))
        config["output"] = {"format": "json", "path": str(outputs_dir / "dataset.json")}
        normalized_config = generate_data.normalize_config(config)

        started = perf_counter()
        rows = generate_data.generate_dataset(normalized_config, custom_formats=custom_formats, already_normalized=True)
        generate_data.write_output(rows, normalized_config["output"]["format"], Path(normalized_config["output"]["path"]))
        checks = run_belgium_evals.build_validation_checks(normalized_config, custom_formats)
        localization = run_belgium_evals.evaluate_localization(rows, checks)
        statistics = run_belgium_evals.evaluate_statistics(rows, normalized_config)
        report_html = run_belgium_evals.render_experiment_report(experiment, rows, localization, statistics, normalized_config)
        duration_seconds = perf_counter() - started

        report_path = outputs_dir / "report.html"
        report_path.write_text(report_html, encoding="utf-8")

        summary_path = outputs_dir / "summary.json"
        summary_path.write_text(
            json.dumps(
                {
                    "experiment_id": experiment["id"],
                    "title": experiment["title"],
                    "localization_score": localization["overall_pass_rate"],
                    "joint_fit_score": statistics["joint"]["score"],
                    "largest_joint_gap": statistics["joint"]["max_gap"],
                    "records": normalized_config["records"],
                    "represented_dimensions": statistics["dimensions"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        grading = build_grading(
            experiment,
            rows,
            localization,
            statistics,
            Path(normalized_config["output"]["path"]),
            report_path,
            duration_seconds,
        )
        (run_dir / "grading.json").write_text(json.dumps(grading, indent=2) + "\n", encoding="utf-8")
        (run_dir / "timing.json").write_text(
            json.dumps(
                {
                    "total_tokens": 0,
                    "duration_ms": round(duration_seconds * 1000, 2),
                    "total_duration_seconds": round(duration_seconds, 4),
                    "executor_duration_seconds": round(duration_seconds, 4),
                    "grader_duration_seconds": 0.0,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (run_dir / "eval_metadata.json").write_text(
            json.dumps(
                {
                    "eval_id": eval_id,
                    "eval_slug": experiment["id"],
                    "title": experiment["title"],
                    "prompt": experiment["prompt"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        score_rows.append(
            {
                "id": experiment["id"],
                "title": experiment["title"],
                "localization": localization["overall_pass_rate"],
                "joint_fit": statistics["joint"]["score"],
            }
        )

    (workspace_dir / "feedback.json").write_text(json.dumps({"reviews": []}, indent=2) + "\n", encoding="utf-8")
    (workspace_dir / "evals.json").write_text(
        json.dumps(
            {
                "skill_name": "lifelike-synthetic-data-generator",
                "evals": [
                    {
                        "id": eval_id_map[experiment["id"]],
                        "prompt": experiment["prompt"],
                        "expected_output": "A localized synthetic dataset with strong realism and strong represented-dimension fit.",
                        "expectations": [
                            "The dataset contains the requested number of rows.",
                            "All requested output fields are present in the generated records.",
                            "Localization and format adherence remain at or above 99%.",
                            "Joint statistical fit remains at or above 95% for the represented dimensions.",
                            "Every requested represented dimension appears in the dataset rows.",
                        ],
                    }
                    for experiment in experiments
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return eval_id_map, score_rows


def main() -> int:
    args = parse_args()
    workspace_dir = Path(args.workspace_dir)
    static_review = Path(args.static_review)
    aggregate_script = Path(args.aggregate_script)
    viewer_script = Path(args.viewer_script)

    selected_ids = set(args.experiment_ids or [])
    experiments = [item for item in get_experiments() if not selected_ids or item["id"] in selected_ids]
    if not experiments:
        raise SystemExit("No experiments selected.")

    eval_id_map, score_rows = export_workspace(workspace_dir, experiments)

    if not aggregate_script.exists():
        raise SystemExit(f"Skill-creator aggregate script not found: {aggregate_script}")
    run_subprocess(
        [
            sys.executable,
            str(aggregate_script),
            str(workspace_dir),
            "--skill-name",
            "lifelike-synthetic-data-generator",
            "--skill-path",
            str(ROOT_DIR),
        ],
        ROOT_DIR,
    )

    benchmark_path = workspace_dir / "benchmark.json"
    enrich_benchmark(benchmark_path, experiments, eval_id_map, score_rows)

    if not args.skip_static_review:
        if not viewer_script.exists():
            raise SystemExit(f"Skill-creator viewer script not found: {viewer_script}")
        run_subprocess(
            [
                sys.executable,
                str(viewer_script),
                str(workspace_dir),
                "--skill-name",
                "lifelike-synthetic-data-generator",
                "--benchmark",
                str(benchmark_path),
                "--static",
                str(static_review),
            ],
            ROOT_DIR,
        )

    print(
        json.dumps(
            {
                "status": "ok",
                "workspace_dir": str(workspace_dir),
                "benchmark_path": str(benchmark_path),
                "static_review": str(static_review) if not args.skip_static_review else None,
                "experiments": [item["id"] for item in experiments],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
