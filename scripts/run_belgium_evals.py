#!/usr/bin/env python

import argparse
import html
import json
import math
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_data
from evals.belgium_experiments import get_experiments


DEFAULT_OUTPUT_DIR = ROOT_DIR / "artifacts" / "evals" / "belgium"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def summarize_allowed_values(values: list) -> str:
    rendered = [str(value) for value in values]
    if len(rendered) <= 6:
        return ", ".join(rendered)
    return ", ".join(rendered[:6]) + f", ... ({len(rendered)} values)"


def summarize_age_values(values: list) -> str:
    ranges = []
    min_age = None
    max_age = None
    for value in values:
        try:
            current_min, current_max = generate_data.resolve_age_range_from_band(value, {"default_max_age": 105}, "eval")
        except generate_data.SkillError:
            continue
        min_age = current_min if min_age is None else min(min_age, current_min)
        max_age = current_max if max_age is None else max(max_age, current_max)
        ranges.append(f"{value} ({current_min}-{current_max})")
    if min_age is None or max_age is None:
        return summarize_allowed_values(values)
    return f"{min_age}-{max_age}; " + ", ".join(ranges)


def postcode_prefix_summary(postcodes: list[str]) -> str:
    prefixes = {postcode[0] for postcode in postcodes if len(postcode) == 4 and postcode.isdigit()}
    if len(prefixes) == 1:
        prefix = next(iter(prefixes))
        return f"{prefix}xxx"
    return summarize_allowed_values(sorted(postcodes))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Belgium-focused realism and statistical evaluation experiments.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for generated reports and datasets.")
    parser.add_argument("--experiment-id", action="append", dest="experiment_ids", help="Experiment id to run. Repeat to run multiple.")
    return parser.parse_args()


def checksum_insz(value: str) -> bool:
    match = re.fullmatch(r"(\d{6})-(\d{3})-(\d{2})", value)
    if not match:
        return False
    base_number = match.group(1) + match.group(2)
    checksum = int(match.group(3))
    calc_base = int(("2" if int(match.group(1)[:2]) <= date.today().year % 100 else "") + base_number)
    expected = 97 - (calc_base % 97)
    expected = expected or 97
    return checksum == expected


def iban_mod97(value: str) -> bool:
    normalized = value.replace(" ", "").upper()
    if not re.fullmatch(r"[A-Z]{2}\d{14,32}", normalized):
        return False
    rearranged = normalized[4:] + normalized[:4]
    converted = "".join(str(ord(char) - 55) if char.isalpha() else char for char in rearranged)
    return int(converted) % 97 == 1


def age_from_birth_date(birth_date: str, reference_date: str) -> int | None:
    try:
        born = date.fromisoformat(birth_date)
        ref = date.fromisoformat(reference_date)
    except ValueError:
        return None
    return ref.year - born.year - ((ref.month, ref.day) < (born.month, born.day))


def age_in_band(age: int, age_band: str) -> bool:
    params = {"default_max_age": 105}
    min_age, max_age = generate_data.resolve_age_range_from_band(age_band, params, "eval")
    return min_age <= age <= max_age


def build_validation_checks(config: dict, custom_formats: dict) -> list[dict]:
    checks = []
    allowed_segment_values = {}
    population_model = config.get("population_model")
    if population_model:
        for segment in population_model["segments"]:
            for key, value in segment["values"].items():
                allowed_segment_values.setdefault(key, set()).add(value)

    for field in config["fields"]:
        field_name = field["name"]
        field_type = field["type"]
        params = field.get("params", {})

        if field_type == "literal":
            checks.append({"field": field_name, "kind": "equals", "value": params["value"], "label": "Exact literal"})
        elif field_type == "segment_value":
            key = params["key"]
            constraint = summarize_allowed_values(sorted(allowed_segment_values.get(key, [])))
            if key == "age_band":
                constraint = summarize_age_values(sorted(allowed_segment_values.get(key, [])))
            checks.append(
                {
                    "field": field_name,
                    "kind": "allowed_values",
                    "values": sorted(allowed_segment_values.get(key, [])),
                    "label": "Allowed represented values",
                    "constraint": constraint,
                }
            )
        elif field_type == "birth_date_from_age_band":
            age_band_values = sorted(allowed_segment_values.get(params["segment_key"], []))
            checks.append(
                {
                    "field": field_name,
                    "kind": "birth_date_matches_age_band",
                    "age_band_field": params["segment_key"],
                    "reference_date": params.get("reference_date", date.today().isoformat()),
                    "label": "Birth date aligns with requested age band",
                    "constraint": summarize_age_values(age_band_values) if age_band_values else "Matches the sampled age band",
                }
            )
        elif field_type == "belgian_insz":
            checks.append({"field": field_name, "kind": "insz_checksum", "label": "INSZ checksum and format", "constraint": "YYMMDD-NNN-CC"})
        elif field_type == "email":
            checks.append({"field": field_name, "kind": "email_basic", "label": "Email format", "constraint": "local-part@domain"})
        elif field_type == "iban" and config["locale"].endswith("_BE"):
            checks.append({"field": field_name, "kind": "belgian_iban", "label": "Belgian IBAN format", "constraint": "BE + 14 digits"})
        elif field_type == "belgian_address_component":
            address_params = dict(params)
            region_segment_key = address_params.pop("region_segment_key", None)
            if region_segment_key is not None:
                region_values = sorted(allowed_segment_values.get(region_segment_key, []))
                if len(region_values) == 1:
                    address_params["region"] = region_values[0]
            addresses = generate_data.filter_belgian_address_catalog(
                generate_data.load_belgian_address_catalog(),
                address_params,
                segment_values=None,
                field_name=field_name,
            )
            component = address_params["component"]
            if component == "postcode":
                constraint = postcode_prefix_summary(sorted({item["postcode"] for item in addresses}))
            elif component == "city":
                constraint = summarize_allowed_values(sorted({item["city"] for item in addresses}))
            elif component == "street_address":
                constraint = "Known catalog streets aligned with postcode and city"
            else:
                constraint = summarize_allowed_values(sorted({str(item[component]) for item in addresses}))
            checks.append(
                {
                    "field": field_name,
                    "kind": "allowed_values",
                    "values": sorted({item[component] for item in addresses}),
                    "label": "Allowed represented values",
                    "constraint": constraint,
                }
            )
        elif field_type in custom_formats:
            checks.append(
                {
                    "field": field_name,
                    "kind": "regex",
                    "pattern": custom_formats[field_type]["pattern"],
                    "label": custom_formats[field_type].get("description", "Custom format"),
                    "constraint": custom_formats[field_type]["pattern"],
                }
            )
        elif field_type == "postcode" and config["locale"].endswith("_BE"):
            checks.append(
                {
                    "field": field_name,
                    "kind": "regex",
                    "pattern": r"^[1-9]\d{3}$",
                    "label": "Belgian postal code format",
                    "constraint": "1000-9999",
                }
            )
        elif field_type == "number_int":
            checks.append(
                {
                    "field": field_name,
                    "kind": "number_range",
                    "min": params.get("min", 0),
                    "max": params.get("max", 100),
                    "label": "Numeric range",
                    "constraint": f"{params.get('min', 0)}-{params.get('max', 100)}",
                }
            )
        elif field_type in {"first_name", "last_name", "name", "street_address", "city", "job", "faker_from_segment"}:
            checks.append({"field": field_name, "kind": "not_empty", "label": "Non-empty localized text", "constraint": "non-empty"})

    row_fields = {field["name"] for field in config["fields"]}
    if {"street_address", "postcode", "city"}.issubset(row_fields) and config["locale"].endswith("_BE"):
        checks.append(
            {
                "field": "street_address",
                "kind": "belgian_address_catalog_match",
                "label": "Street exists in the postcode and city catalog",
                "constraint": "street_address + postcode + city must be a known Belgian catalog combination",
            }
        )
    return checks


def evaluate_check(row: dict, check: dict) -> tuple[bool, str]:
    value = row.get(check["field"])
    kind = check["kind"]
    if kind == "equals":
        return value == check["value"], repr(value)
    if kind == "allowed_values":
        return value in check["values"], repr(value)
    if kind == "regex":
        return re.fullmatch(check["pattern"], str(value or "")) is not None, str(value)
    if kind == "not_empty":
        return bool(str(value or "").strip()), str(value)
    if kind == "email_basic":
        return EMAIL_PATTERN.fullmatch(str(value or "")) is not None, str(value)
    if kind == "insz_checksum":
        return checksum_insz(str(value or "")), str(value)
    if kind == "belgian_iban":
        normalized = str(value or "").replace(" ", "").upper()
        return normalized.startswith("BE") and iban_mod97(normalized), normalized
    if kind == "number_range":
        return isinstance(value, int) and check["min"] <= value <= check["max"], repr(value)
    if kind == "birth_date_matches_age_band":
        age = age_from_birth_date(str(value or ""), check["reference_date"])
        if age is None:
            return False, str(value)
        try:
            return age_in_band(age, str(row.get(check["age_band_field"], ""))), f"age={age}"
        except generate_data.SkillError:
            return False, f"age={age}"
    if kind == "belgian_address_catalog_match":
        street_address = row.get("street_address")
        postcode = row.get("postcode")
        city = row.get("city")
        region = row.get("region")
        for address in generate_data.load_belgian_address_catalog():
            if (
                address["street_address"] == street_address
                and address["postcode"] == postcode
                and address["city"] == city
                and (region is None or address["region"] == region)
            ):
                return True, f"{street_address}, {postcode} {city}"
        return False, f"{street_address}, {postcode} {city}"
    raise ValueError(f"Unsupported check kind: {kind}")


def evaluate_localization(rows: list[dict], checks: list[dict]) -> dict:
    results = []
    total_checked = 0
    total_passed = 0
    for check in checks:
        passed = 0
        failures = []
        for index, row in enumerate(rows, start=1):
            ok, detail = evaluate_check(row, check)
            total_checked += 1
            if ok:
                passed += 1
                total_passed += 1
            elif len(failures) < 5:
                failures.append({"row": index, "detail": detail})
        checked = len(rows)
        results.append(
            {
                "field": check["field"],
                "label": check["label"],
                "constraint": check.get("constraint", ""),
                "pass_count": passed,
                "checked_count": checked,
                "pass_rate": passed / checked if checked else 0.0,
                "failures": failures,
            }
        )
    return {
        "checks": results,
        "overall_pass_rate": total_passed / total_checked if total_checked else 0.0,
    }


def distribution_from_segments(segments: list[dict], dimensions: list[str]) -> dict[tuple, float]:
    distribution = Counter()
    for segment in segments:
        key = tuple((dimension, segment["values"].get(dimension)) for dimension in dimensions)
        distribution[key] += segment["normalized_weight"]
    return dict(distribution)


def distribution_from_rows(rows: list[dict], dimensions: list[str]) -> dict[tuple, float]:
    counts = Counter()
    for row in rows:
        key = tuple((dimension, row.get(dimension)) for dimension in dimensions)
        counts[key] += 1
    total = len(rows) or 1
    return {key: count / total for key, count in counts.items()}


def compare_distributions(expected: dict[tuple, float], observed: dict[tuple, float]) -> dict:
    keys = sorted(set(expected) | set(observed))
    rows = []
    tvd = 0.0
    max_gap = 0.0
    for key in keys:
        expected_value = expected.get(key, 0.0)
        observed_value = observed.get(key, 0.0)
        gap = abs(expected_value - observed_value)
        tvd += gap
        max_gap = max(max_gap, gap)
        rows.append(
            {
                "label": ", ".join(f"{name}={value}" for name, value in key),
                "expected": expected_value,
                "observed": observed_value,
                "gap": gap,
            }
        )
    tvd *= 0.5
    return {
        "score": 1.0 - tvd,
        "tvd": tvd,
        "max_gap": max_gap,
        "rows": sorted(rows, key=lambda item: item["gap"], reverse=True),
    }


def evaluate_statistics(rows: list[dict], config: dict) -> dict:
    summary = generate_data.build_representativeness_summary(config)
    dimensions = [item["name"] for item in summary["distribution_backed_dimensions"]]
    expected_joint = distribution_from_segments(config["population_model"]["segments"], dimensions)
    observed_joint = distribution_from_rows(rows, dimensions)
    joint = compare_distributions(expected_joint, observed_joint)

    marginals = []
    for dimension in dimensions:
        expected = Counter()
        for key, value in expected_joint.items():
            mapping = dict(key)
            expected[((dimension, mapping[dimension]),)] += value
        observed = Counter()
        for key, value in observed_joint.items():
            mapping = dict(key)
            observed[((dimension, mapping[dimension]),)] += value
        marginal = compare_distributions(dict(expected), dict(observed))
        marginal["dimension"] = dimension
        marginals.append(marginal)

    return {"joint": joint, "marginals": marginals, "dimensions": dimensions}


def score_label(score: float) -> str:
    if score >= 0.99:
        return "Excellent"
    if score >= 0.95:
        return "Strong"
    if score >= 0.90:
        return "Moderate"
    return "Weak"


def render_table(headers: list[str], rows: list[list[str]]) -> str:
    header_html = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    body_html = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<table><thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody></table>"


def render_experiment_report(experiment: dict, rows: list[dict], localization: dict, statistics: dict, config: dict) -> str:
    preview_rows = rows[:8]
    preview_headers = list(preview_rows[0].keys()) if preview_rows else []
    preview_table = render_table(
        preview_headers,
        [[html.escape(str(row.get(header, ""))) for header in preview_headers] for row in preview_rows],
    )
    asked = experiment["ask"]
    asked_table = render_table(
        ["Item", "Value"],
        [
            ["Target population", html.escape(str(asked["target_population"]))],
            ["Requested dataset size", html.escape(str(asked["record_count"]))],
            ["Requested fields", html.escape(", ".join(asked["requested_fields"]))],
            ["Distribution-backed dimensions", html.escape(", ".join(asked["distribution_backed_dimensions"]))],
            ["Locale", html.escape(config["locale"])],
            ["Seed", html.escape(str(config["seed"]))],
        ],
    )
    localization_table = render_table(
        ["Field", "Check", "Allowed values or ranges", "Pass rate", "Sample failures"],
        [
            [
                html.escape(item["field"]),
                html.escape(item["label"]),
                html.escape(item.get("constraint", "")),
                f"{item['pass_rate'] * 100:.2f}%",
                html.escape("; ".join(f"row {failure['row']}: {failure['detail']}" for failure in item["failures"]) or "none"),
            ]
            for item in localization["checks"]
        ],
    )
    joint_top = render_table(
        ["Cell", "Expected", "Observed", "Gap"],
        [
            [
                html.escape(item["label"]),
                f"{item['expected'] * 100:.2f}%",
                f"{item['observed'] * 100:.2f}%",
                f"{item['gap'] * 100:.2f}%",
            ]
            for item in statistics["joint"]["rows"][:12]
        ],
    )
    marginal_html = "".join(
        f"<h3>{html.escape(item['dimension'])}</h3>"
        + render_table(
            ["Value", "Expected", "Observed", "Gap"],
            [
                [
                    html.escape(row["label"]),
                    f"{row['expected'] * 100:.2f}%",
                    f"{row['observed'] * 100:.2f}%",
                    f"{row['gap'] * 100:.2f}%",
                ]
                for row in item["rows"]
            ],
        )
        for item in statistics["marginals"]
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(experiment['title'])}</title>
  <style>
    body {{ font-family: Georgia, serif; margin: 2rem auto; max-width: 1200px; color: #18222d; background: #f6f4ef; }}
    h1, h2, h3 {{ color: #17324d; }}
    .cards {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; margin: 1rem 0 2rem; }}
    .card {{ background: white; border: 1px solid #d9d4c7; padding: 1rem; border-radius: 12px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; margin-bottom: 1.5rem; }}
    th, td {{ border: 1px solid #d9d4c7; padding: 0.55rem; text-align: left; vertical-align: top; }}
    th {{ background: #efe8d8; }}
    .muted {{ color: #556575; }}
  </style>
</head>
<body>
  <h1>{html.escape(experiment['title'])}</h1>
  <p>{html.escape(experiment['prompt'])}</p>
  <div class="cards">
    <div class="card"><strong>Localization score</strong><br>{localization['overall_pass_rate'] * 100:.2f}%<br><span class="muted">{score_label(localization['overall_pass_rate'])}</span></div>
    <div class="card"><strong>Joint statistical fit</strong><br>{statistics['joint']['score'] * 100:.2f}%<br><span class="muted">TVD {statistics['joint']['tvd'] * 100:.2f}%</span></div>
    <div class="card"><strong>Largest cell gap</strong><br>{statistics['joint']['max_gap'] * 100:.2f}%<br><span class="muted">Across all represented dimensions</span></div>
  </div>
  <h2>What Was Asked</h2>
  {asked_table}
  <h2>Localization And Format Adherence</h2>
  {localization_table}
  <h2>Statistical Fit On The Observed Population</h2>
  <p>Joint fit compares the generated distribution against the full requested represented population cells. Marginals show how each represented dimension performs individually.</p>
  {joint_top}
  {marginal_html}
  <h2>Preview</h2>
  {preview_table}
</body>
</html>"""


def render_index(results: list[dict]) -> str:
    experiment_count = len(results)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Synthetic Data Skill Evaluation</title>
  <style>
    body {{ font-family: Georgia, serif; margin: 2rem auto; max-width: 1100px; color: #18222d; background: #f6f4ef; }}
    table {{ width: 100%; border-collapse: collapse; background: white; }}
    th, td {{ border: 1px solid #d9d4c7; padding: 0.6rem; text-align: left; }}
    th {{ background: #efe8d8; }}
  </style>
</head>
<body>
  <h1>Synthetic Data Skill Evaluation</h1>
  <p>{experiment_count} experiments evaluating realistic-looking data and statistical correctness across Belgium, broader Europe, and world-level scenarios.</p>
  {render_table(
      ["Experiment", "Requested size", "Localization", "Joint fit", "Report"],
      [
          [
              html.escape(result["title"]),
              str(result["records"]),
              f"{result['localization'] * 100:.2f}%",
              f"{result['joint_fit'] * 100:.2f}%",
              f'<a href="{html.escape(result["report_name"])}">open</a>',
          ]
          for result in results
      ],
  )}
</body>
</html>"""


def run() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    report_dir = output_dir / "reports"
    dataset_dir = output_dir / "datasets"
    report_dir.mkdir(parents=True, exist_ok=True)
    dataset_dir.mkdir(parents=True, exist_ok=True)

    custom_formats = generate_data.load_custom_formats()
    selected_ids = set(args.experiment_ids or [])
    experiments = [item for item in get_experiments() if not selected_ids or item["id"] in selected_ids]

    index_rows = []
    for experiment in experiments:
        config = json.loads(json.dumps(experiment["config"]))
        config["output"] = {"format": "json", "path": str(dataset_dir / f"{experiment['id']}.json")}
        normalized_config = generate_data.normalize_config(config)
        rows = generate_data.generate_dataset(normalized_config, custom_formats=custom_formats, already_normalized=True)
        generate_data.write_output(rows, normalized_config["output"]["format"], Path(normalized_config["output"]["path"]))

        checks = build_validation_checks(normalized_config, custom_formats)
        localization = evaluate_localization(rows, checks)
        statistics = evaluate_statistics(rows, normalized_config)
        report_html = render_experiment_report(experiment, rows, localization, statistics, normalized_config)
        report_name = f"{experiment['id']}.html"
        (report_dir / report_name).write_text(report_html, encoding="utf-8")
        index_rows.append(
            {
                "title": experiment["title"],
                "records": normalized_config["records"],
                "localization": localization["overall_pass_rate"],
                "joint_fit": statistics["joint"]["score"],
                "report_name": report_name,
            }
        )

    (report_dir / "index.html").write_text(render_index(index_rows), encoding="utf-8")
    print(json.dumps({"status": "ok", "output_dir": str(output_dir), "report_count": len(index_rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
