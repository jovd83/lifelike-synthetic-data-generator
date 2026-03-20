#!/usr/bin/env python
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "faker>=24.4.0,<25",
#   "rstr>=3.2.2,<4",
# ]
# ///

import argparse
import csv
import json
import random
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from faker import Faker
import rstr


SUPPORTED_OUTPUT_FORMATS = {"csv", "json", "ndjson", "sql"}
POPULATION_AWARE_FIELD_TYPES = {"segment_value", "birth_date_from_age_band", "faker_from_segment"}
DEFAULT_OUTPUT_NAME = {
    "csv": "synthetic_data.csv",
    "json": "synthetic_data.json",
    "ndjson": "synthetic_data.ndjson",
    "sql": "synthetic_data.sql",
}
ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CUSTOM_FORMATS_PATH = ROOT_DIR / "references" / "custom_formats.json"
DEFAULT_OPEN_DATA_SOURCES_PATH = ROOT_DIR / "references" / "open_data_sources.json"
DEFAULT_BELGIAN_ADDRESS_CATALOG_PATH = ROOT_DIR / "references" / "belgian_address_catalog.json"
DEFAULT_NETWORK_TIMEOUT_SEC = 30
SUPPORTED_SOURCE_FILTER_OPS = {"eq", "neq", "gt", "gte", "lt", "lte", "in"}
NUMERIC_AGE_BAND_PATTERN = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")
NUMERIC_AGE_PLUS_PATTERN = re.compile(r"^\s*(\d+)\s*\+\s*$")
STATBEL_AGE_BAND_PATTERN = re.compile(r"^Y(\d+)T(\d+)$")
STATBEL_AGE_PLUS_PATTERN = re.compile(r"^Y(\d+)PL$")
STATBEL_AGE_GE_PATTERN = re.compile(r"^Y_GE(\d+)$")
STATBEL_AGE_LT_PATTERN = re.compile(r"^Y_LT(\d+)$")
MISSING = object()
SQL_CONSTRAINT_KEYWORDS = {
    "not",
    "null",
    "default",
    "primary",
    "references",
    "unique",
    "check",
    "constraint",
    "collate",
    "generated",
}


class SkillError(Exception):
    """Raised when the config or generation workflow is invalid."""


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SkillError(f"Config file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SkillError(f"Invalid JSON in {path}: {exc.msg} at line {exc.lineno}, column {exc.colno}") from exc


def load_custom_formats(path: Path = DEFAULT_CUSTOM_FORMATS_PATH) -> dict:
    if not path.exists():
        return {}

    data = load_json(path)
    formats = data.get("formats", {})
    if not isinstance(formats, dict):
        raise SkillError(f"Expected 'formats' to be an object in {path}")
    return formats


def load_open_data_sources(path: Path = DEFAULT_OPEN_DATA_SOURCES_PATH) -> dict:
    data = load_json(path)
    sources = data.get("sources", [])
    if not isinstance(sources, list):
        raise SkillError(f"Expected 'sources' to be an array in {path}")
    return data


def load_belgian_address_catalog(path: Path = DEFAULT_BELGIAN_ADDRESS_CATALOG_PATH) -> list[dict]:
    data = load_json(path)
    addresses = data.get("addresses", [])
    if not isinstance(addresses, list) or not addresses:
        raise SkillError(f"Expected 'addresses' to be a non-empty array in {path}")
    required_keys = {"region", "province", "postcode", "city", "street_address"}
    for index, address in enumerate(addresses, start=1):
        if not isinstance(address, dict):
            raise SkillError(f"Address catalog entry {index} in {path} must be an object.")
        missing = sorted(required_keys - set(address))
        if missing:
            raise SkillError(f"Address catalog entry {index} in {path} is missing keys: {', '.join(missing)}.")
    return addresses


def split_sql_definitions(definition_block: str) -> list[str]:
    parts = []
    current = []
    depth = 0
    for char in definition_block:
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(depth - 1, 0)
        if char == "," and depth == 0:
            item = "".join(current).strip()
            if item:
                parts.append(item)
            current = []
            continue
        current.append(char)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def normalize_identifier(raw_name: str) -> str:
    name = raw_name.strip()
    if (name.startswith('"') and name.endswith('"')) or (name.startswith("`") and name.endswith("`")):
        return name[1:-1]
    if name.startswith("[") and name.endswith("]"):
        return name[1:-1]
    return name


def parse_sql_type(definition_tail: str) -> str:
    tokens = []
    current = []
    depth = 0
    for raw_token in definition_tail.split():
        lower_token = raw_token.lower()
        depth += raw_token.count("(")
        depth -= raw_token.count(")")
        if depth <= 0 and lower_token in SQL_CONSTRAINT_KEYWORDS:
            break
        tokens.append(raw_token)
    sql_type = " ".join(tokens).strip()
    if not sql_type:
        raise SkillError(f"Could not infer SQL column type from definition: {definition_tail!r}")
    return sql_type


def parse_create_table_ddl(ddl: str) -> dict:
    if not isinstance(ddl, str) or not ddl.strip():
        raise SkillError("'sql_schema.ddl' must be a non-empty string.")
    match = re.search(
        r"create\s+table\s+(?:if\s+not\s+exists\s+)?(?P<table>[^\s(]+)\s*\((?P<body>.*)\)\s*;?\s*$",
        ddl.strip(),
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise SkillError("Only simple CREATE TABLE statements are supported in 'sql_schema.ddl'.")

    raw_table_name = match.group("table")
    body = match.group("body")
    columns = []
    for definition in split_sql_definitions(body):
        stripped = definition.strip()
        if not stripped:
            continue
        leading = stripped.split(None, 1)[0].lower()
        if leading in {"primary", "foreign", "unique", "constraint", "check"}:
            continue

        column_match = re.match(r'(?P<name>"[^"]+"|`[^`]+`|\[[^\]]+\]|[A-Za-z_][\w$]*)\s+(?P<tail>.+)$', stripped, re.DOTALL)
        if not column_match:
            raise SkillError(f"Unsupported column definition in SQL schema: {definition!r}")

        column_name = normalize_identifier(column_match.group("name"))
        sql_type = parse_sql_type(column_match.group("tail"))
        columns.append({"name": column_name, "sql_type": sql_type})

    if not columns:
        raise SkillError("The provided CREATE TABLE statement does not contain any supported column definitions.")

    return {
        "table_name": normalize_identifier(raw_table_name.split(".")[-1]),
        "columns": columns,
    }


def infer_field_from_sql_column(column_name: str, sql_type: str, *, locale: str) -> dict:
    normalized_name = column_name.lower()
    normalized_type = sql_type.lower()

    if normalized_name in {"first_name", "firstname", "given_name"}:
        return {"name": column_name, "type": "first_name", "params": {}}
    if normalized_name in {"last_name", "lastname", "family_name", "surname"}:
        return {"name": column_name, "type": "last_name", "params": {}}
    if normalized_name in {"full_name", "name"}:
        return {"name": column_name, "type": "name", "params": {}}
    if "email" in normalized_name:
        return {"name": column_name, "type": "email", "params": {}}
    if normalized_name in {"city", "town"}:
        return {"name": column_name, "type": "city", "params": {}}
    if "street" in normalized_name or "address" in normalized_name:
        return {"name": column_name, "type": "street_address", "params": {}}
    if "postcode" in normalized_name or "postal_code" in normalized_name or "zip" in normalized_name:
        field_type = "belgian_postal_code" if locale.endswith("_BE") else "postcode"
        return {"name": column_name, "type": field_type, "params": {}}
    if "mobile" in normalized_name:
        field_type = "belgian_mobile_phone" if locale.endswith("_BE") else "phone_number"
        return {"name": column_name, "type": field_type, "params": {}}
    if "phone" in normalized_name:
        return {"name": column_name, "type": "phone_number", "params": {}}
    if normalized_name == "iban":
        return {"name": column_name, "type": "iban", "params": {}}
    if "insz" in normalized_name:
        return {"name": column_name, "type": "belgian_insz", "params": {}}
    if "eid" in normalized_name:
        return {"name": column_name, "type": "belgian_eid", "params": {}}
    if "license_plate" in normalized_name or "licence_plate" in normalized_name:
        field_type = "belgian_license_plate" if locale.endswith("_BE") else "license_plate"
        return {"name": column_name, "type": field_type, "params": {}}
    if any(token in normalized_type for token in {"date", "time"}):
        return {"name": column_name, "type": "date_between", "params": {}}
    if normalized_name in {"birth_date", "date_of_birth"}:
        return {"name": column_name, "type": "date_between", "params": {"start_date": "-90y", "end_date": "-18y"}}
    if "date" in normalized_name or "timestamp" in normalized_name:
        return {"name": column_name, "type": "date_between", "params": {}}
    if normalized_name.startswith("is_") or normalized_type == "boolean":
        return {"name": column_name, "type": "choice", "params": {"values": [True, False]}}
    if any(token in normalized_type for token in {"int", "serial"}):
        return {"name": column_name, "type": "number_int", "params": {"min": 1, "max": 1000000}}
    if any(token in normalized_type for token in {"numeric", "decimal", "real", "double", "float"}):
        return {"name": column_name, "type": "number_float", "params": {"min": 0, "max": 100000, "precision": 2}}
    return {"name": column_name, "type": "word", "params": {}}


def normalize_sql_schema(raw_sql_schema, *, locale: str) -> dict | None:
    if raw_sql_schema is None:
        return None
    if not isinstance(raw_sql_schema, dict):
        raise SkillError("'sql_schema' must be an object when provided.")

    ddl = raw_sql_schema.get("ddl")
    ddl_path = raw_sql_schema.get("ddl_path")
    if ddl is None and ddl_path is None:
        raise SkillError("'sql_schema' requires either 'ddl' or 'ddl_path'.")
    if ddl is not None and ddl_path is not None:
        raise SkillError("'sql_schema' must not define both 'ddl' and 'ddl_path' at the same time.")
    if ddl_path is not None:
        try:
            ddl = Path(ddl_path).read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise SkillError(f"SQL schema file not found: {ddl_path}") from exc

    parsed = parse_create_table_ddl(ddl)
    return {
        "table_name": parsed["table_name"],
        "columns": parsed["columns"],
        "derived_fields": [infer_field_from_sql_column(column["name"], column["sql_type"], locale=locale) for column in parsed["columns"]],
    }


def is_scalar(value) -> bool:
    return isinstance(value, (str, int, float, bool)) and not isinstance(value, complex)


def unique_preserving_order(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


def normalize_source_query_filters(raw_filters) -> dict:
    if raw_filters is None:
        return {}
    if not isinstance(raw_filters, dict):
        raise SkillError("'population_model.source_query.filters' must be an object when provided.")

    normalized = {}
    for column_name, raw_spec in raw_filters.items():
        if not isinstance(column_name, str) or not column_name.strip():
            raise SkillError("Each source-query filter key must be a non-empty string.")

        if isinstance(raw_spec, dict):
            op = raw_spec.get("op", "eq")
            value = raw_spec.get("value")
        elif isinstance(raw_spec, list):
            op = "in"
            value = raw_spec
        else:
            op = "eq"
            value = raw_spec

        if op not in SUPPORTED_SOURCE_FILTER_OPS:
            allowed = ", ".join(sorted(SUPPORTED_SOURCE_FILTER_OPS))
            raise SkillError(f"Source-query filter {column_name!r} uses unsupported op {op!r}. Allowed: {allowed}.")

        if op == "in":
            if not isinstance(value, list) or not value:
                raise SkillError(f"Source-query filter {column_name!r} with op 'in' requires a non-empty array value.")
            normalized_values = []
            for item in value:
                if not is_scalar(item):
                    raise SkillError(
                        f"Source-query filter {column_name!r} only supports string, number, or boolean values."
                    )
                normalized_values.append(item)
            normalized[column_name] = {"op": op, "value": normalized_values}
            continue

        if not is_scalar(value):
            raise SkillError(f"Source-query filter {column_name!r} must use a string, number, or boolean value.")
        normalized[column_name] = {"op": op, "value": value}

    return normalized


def normalize_population_source_query(raw_source_query) -> dict:
    if not isinstance(raw_source_query, dict):
        raise SkillError("'population_model.source_query' must be an object when provided.")

    catalog_id = raw_source_query.get("catalog_id")
    base_url = raw_source_query.get("base_url")
    if catalog_id is None and base_url is None:
        raise SkillError("'population_model.source_query' requires either 'catalog_id' or 'base_url'.")
    if catalog_id is not None and (not isinstance(catalog_id, str) or not catalog_id.strip()):
        raise SkillError("'population_model.source_query.catalog_id' must be a non-empty string when provided.")
    if base_url is not None and (not isinstance(base_url, str) or not base_url.strip()):
        raise SkillError("'population_model.source_query.base_url' must be a non-empty string when provided.")

    dataset = raw_source_query.get("dataset")
    if not isinstance(dataset, str) or not dataset.strip():
        raise SkillError("'population_model.source_query.dataset' must be a non-empty string.")

    weight_column = raw_source_query.get("weight_column", "MS_VALUE")
    if not isinstance(weight_column, str) or not weight_column.strip():
        raise SkillError("'population_model.source_query.weight_column' must be a non-empty string when provided.")

    dimension_columns = raw_source_query.get("dimension_columns")
    if not isinstance(dimension_columns, dict) or not dimension_columns:
        raise SkillError("'population_model.source_query.dimension_columns' must be a non-empty object.")

    normalized_dimension_columns = {}
    for dimension_name, column_name in dimension_columns.items():
        if not isinstance(dimension_name, str) or not dimension_name.strip():
            raise SkillError("Each source-query dimension name must be a non-empty string.")
        if not isinstance(column_name, str) or not column_name.strip():
            raise SkillError(f"Source-query dimension {dimension_name!r} must map to a non-empty column name.")
        normalized_dimension_columns[dimension_name] = column_name

    raw_value_maps = raw_source_query.get("dimension_value_maps", {})
    if raw_value_maps is None:
        raw_value_maps = {}
    if not isinstance(raw_value_maps, dict):
        raise SkillError("'population_model.source_query.dimension_value_maps' must be an object when provided.")

    normalized_value_maps = {}
    for dimension_name, raw_mapping in raw_value_maps.items():
        if dimension_name not in normalized_dimension_columns:
            raise SkillError(
                f"Source-query value map {dimension_name!r} does not match any configured source-query dimension."
            )
        if not isinstance(raw_mapping, dict) or not raw_mapping:
            raise SkillError(f"Source-query value map for {dimension_name!r} must be a non-empty object.")

        normalized_mapping = {}
        for raw_value, mapped_value in raw_mapping.items():
            if not is_scalar(mapped_value):
                raise SkillError(
                    f"Source-query value map for {dimension_name!r} only supports string, number, or boolean outputs."
                )
            normalized_mapping[str(raw_value)] = mapped_value
        normalized_value_maps[dimension_name] = normalized_mapping

    timeout_sec = raw_source_query.get("timeout_sec", DEFAULT_NETWORK_TIMEOUT_SEC)
    if not isinstance(timeout_sec, int) or isinstance(timeout_sec, bool) or timeout_sec < 1:
        raise SkillError("'population_model.source_query.timeout_sec' must be a positive integer when provided.")

    return {
        "catalog_id": catalog_id,
        "base_url": base_url,
        "dataset": dataset,
        "weight_column": weight_column,
        "dimension_columns": normalized_dimension_columns,
        "dimension_value_maps": normalized_value_maps,
        "filters": normalize_source_query_filters(raw_source_query.get("filters", {})),
        "timeout_sec": timeout_sec,
    }


def get_open_data_source_by_id(source_id: str, open_data_sources: dict | None = None) -> dict:
    open_data_sources = open_data_sources or load_open_data_sources()
    for source in open_data_sources.get("sources", []):
        if source.get("id") == source_id:
            return source
    raise SkillError(f"Open-data source {source_id!r} is not present in references/open_data_sources.json.")


def resolve_source_query_base_url(source_query: dict, open_data_sources: dict | None = None) -> str:
    if source_query.get("base_url"):
        return source_query["base_url"].rstrip("/")

    source = get_open_data_source_by_id(source_query["catalog_id"], open_data_sources=open_data_sources)
    source_url = source.get("url")
    if not isinstance(source_url, str) or not source_url.strip():
        raise SkillError(f"Open-data source {source_query['catalog_id']!r} is missing a usable 'url'.")
    return source_url.rstrip("/")


def format_source_filter_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def build_source_filter_expression(filter_spec: dict) -> str:
    op = filter_spec["op"]
    if op == "in":
        values = ",".join(format_source_filter_value(item) for item in filter_spec["value"])
        return f"in.({values})"
    return f"{op}.{format_source_filter_value(filter_spec['value'])}"


def fetch_json_url(url: str, *, timeout_sec: int = DEFAULT_NETWORK_TIMEOUT_SEC):
    try:
        with urllib.request.urlopen(url, timeout=timeout_sec) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise SkillError(f"Failed to fetch remote JSON from {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise SkillError(f"Timed out while fetching remote JSON from {url}.") from exc

    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SkillError(f"Remote endpoint {url} did not return valid JSON.") from exc


def build_source_query_url(source_query: dict, *, open_data_sources: dict | None = None) -> str:
    base_url = resolve_source_query_base_url(source_query, open_data_sources=open_data_sources)
    dataset_path = source_query["dataset"]
    if not dataset_path.startswith("/"):
        dataset_path = f"/{dataset_path}"

    select_columns = unique_preserving_order(
        list(source_query["dimension_columns"].values()) + [source_query["weight_column"]]
    )
    params = {
        "select": ",".join(select_columns),
    }
    for column_name, filter_spec in source_query["filters"].items():
        params[column_name] = build_source_filter_expression(filter_spec)

    query_string = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    return f"{base_url}{dataset_path}?{query_string}"


def coerce_numeric_weight(value, *, label: str) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError as exc:
            raise SkillError(f"{label} must be numeric; received {value!r}.") from exc
    raise SkillError(f"{label} must be numeric; received {value!r}.")


def build_segments_from_source_query(source_query: dict, *, open_data_sources: dict | None = None) -> list[dict]:
    source_url = build_source_query_url(source_query, open_data_sources=open_data_sources)
    rows = fetch_json_url(source_url, timeout_sec=source_query["timeout_sec"])

    if not isinstance(rows, list):
        raise SkillError(f"Source query {source_url} did not return a JSON array.")

    dimension_names = list(source_query["dimension_columns"].keys())
    aggregated = {}
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise SkillError(f"Source query row #{index} is not an object.")

        values = {}
        for dimension_name, column_name in source_query["dimension_columns"].items():
            if column_name not in row:
                raise SkillError(
                    f"Source query row #{index} is missing required column {column_name!r} for dimension {dimension_name!r}."
                )
            raw_value = row[column_name]
            mapped_value = source_query["dimension_value_maps"].get(dimension_name, {}).get(str(raw_value), raw_value)
            if not is_scalar(mapped_value):
                raise SkillError(
                    f"Source query dimension {dimension_name!r} produced unsupported mapped value {mapped_value!r}."
                )
            values[dimension_name] = mapped_value

        if source_query["weight_column"] not in row:
            raise SkillError(
                f"Source query row #{index} is missing weight column {source_query['weight_column']!r}."
            )
        weight = coerce_numeric_weight(
            row[source_query["weight_column"]],
            label=f"Source query weight column {source_query['weight_column']!r}",
        )
        if weight <= 0:
            continue

        key = tuple((dimension_name, values[dimension_name]) for dimension_name in dimension_names)
        if key not in aggregated:
            aggregated[key] = {
                "weight": 0.0,
                "values": values,
            }
        aggregated[key]["weight"] += weight

    if not aggregated:
        raise SkillError("Source query produced no positive-weight segments.")

    normalized_segments = []
    for aggregated_segment in aggregated.values():
        normalized_segments.append(
            {
                "weight": aggregated_segment["weight"],
                "values": aggregated_segment["values"],
                "source": {
                    "catalog_id": source_query.get("catalog_id"),
                    "dataset": source_query["dataset"],
                    "query_url": source_url,
                },
            }
        )

    return normalize_population_segments(normalized_segments)


def parse_iso_date(value: str, *, field_label: str) -> date:
    if not isinstance(value, str):
        raise SkillError(f"{field_label} must be an ISO date string.")

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SkillError(f"{field_label} must be a valid ISO date in YYYY-MM-DD format.") from exc


def normalize_population_filters(raw_filters) -> dict:
    if raw_filters is None:
        return {}
    if not isinstance(raw_filters, dict):
        raise SkillError("'population_model.filters' must be an object when provided.")

    normalized = {}
    for key, raw_value in raw_filters.items():
        if not isinstance(key, str) or not key.strip():
            raise SkillError("Each population filter key must be a non-empty string.")

        if isinstance(raw_value, list):
            if not raw_value:
                raise SkillError(f"Population filter {key!r} must not be an empty array.")
            values = raw_value
        else:
            values = [raw_value]

        normalized_values = []
        for value in values:
            if not is_scalar(value):
                raise SkillError(
                    f"Population filter {key!r} only supports string, number, or boolean values."
                )
            normalized_values.append(value)
        normalized[key] = normalized_values

    return normalized


def normalize_population_dimensions(raw_dimensions) -> list[dict]:
    if raw_dimensions is None:
        return []
    if not isinstance(raw_dimensions, list):
        raise SkillError("'population_model.dimensions' must be an array when provided.")

    normalized = []
    seen = set()
    for index, dimension in enumerate(raw_dimensions, start=1):
        if not isinstance(dimension, dict):
            raise SkillError(f"Population dimension #{index} must be an object.")

        name = dimension.get("name")
        if not isinstance(name, str) or not name.strip():
            raise SkillError(f"Population dimension #{index} is missing a valid 'name'.")
        if name in seen:
            raise SkillError(f"Duplicate population dimension name: {name!r}")

        represented = dimension.get("represented", True)
        if not isinstance(represented, bool):
            raise SkillError(f"Population dimension {name!r} has invalid 'represented'; expected boolean.")

        source = dimension.get("source")
        if source is not None and not isinstance(source, dict):
            raise SkillError(f"Population dimension {name!r} has invalid 'source'; expected an object.")

        description = dimension.get("description")
        if description is not None and not isinstance(description, str):
            raise SkillError(f"Population dimension {name!r} has invalid 'description'; expected a string.")

        normalized_dimension = {
            "name": name,
            "represented": represented,
        }
        if source is not None:
            normalized_dimension["source"] = source
        if description is not None:
            normalized_dimension["description"] = description

        normalized.append(normalized_dimension)
        seen.add(name)

    return normalized


def normalize_population_segments(raw_segments) -> list[dict]:
    if not isinstance(raw_segments, list) or not raw_segments:
        raise SkillError("'population_model.segments' must be a non-empty array.")

    normalized = []
    for index, segment in enumerate(raw_segments, start=1):
        if not isinstance(segment, dict):
            raise SkillError(f"Population segment #{index} must be an object.")

        weight = segment.get("weight")
        if not isinstance(weight, (int, float)) or isinstance(weight, bool) or weight <= 0:
            raise SkillError(f"Population segment #{index} must define a positive numeric 'weight'.")

        values = segment.get("values")
        if not isinstance(values, dict) or not values:
            raise SkillError(f"Population segment #{index} must define a non-empty 'values' object.")

        normalized_values = {}
        for key, value in values.items():
            if not isinstance(key, str) or not key.strip():
                raise SkillError(f"Population segment #{index} contains an invalid value key.")
            if not is_scalar(value):
                raise SkillError(
                    f"Population segment #{index} value {key!r} must be a string, number, or boolean."
                )
            normalized_values[key] = value

        normalized_segment = {
            "weight": float(weight),
            "values": normalized_values,
        }

        label = segment.get("label")
        if label is not None:
            if not isinstance(label, str):
                raise SkillError(f"Population segment #{index} has invalid 'label'; expected a string.")
            normalized_segment["label"] = label

        source = segment.get("source")
        if source is not None:
            if not isinstance(source, dict):
                raise SkillError(f"Population segment #{index} has invalid 'source'; expected an object.")
            normalized_segment["source"] = source

        normalized.append(normalized_segment)

    return normalized


def segment_matches_filters(values: dict, filters: dict) -> bool:
    for key, allowed_values in filters.items():
        if key not in values or values[key] not in allowed_values:
            return False
    return True


def apply_population_filters(segments: list[dict], filters: dict) -> list[dict]:
    filtered = [segment for segment in segments if segment_matches_filters(segment["values"], filters)]
    if not filtered:
        raise SkillError("Population filters removed all population segments.")

    total_weight = sum(segment["weight"] for segment in filtered)
    normalized = []
    for segment in filtered:
        normalized_segment = dict(segment)
        normalized_segment["normalized_weight"] = segment["weight"] / total_weight
        normalized.append(normalized_segment)
    return normalized


def normalize_population_model(raw_population_model) -> dict | None:
    if raw_population_model is None:
        return None
    if not isinstance(raw_population_model, dict):
        raise SkillError("'population_model' must be an object when provided.")

    scope = raw_population_model.get("scope", {})
    if scope is None:
        scope = {}
    if not isinstance(scope, dict):
        raise SkillError("'population_model.scope' must be an object when provided.")

    filters = normalize_population_filters(raw_population_model.get("filters", {}))
    dimensions = normalize_population_dimensions(raw_population_model.get("dimensions", []))
    raw_segments = raw_population_model.get("segments")
    raw_source_query = raw_population_model.get("source_query")
    if raw_segments is not None and raw_source_query is not None:
        raise SkillError("'population_model' must define either 'segments' or 'source_query', not both.")
    if raw_segments is None and raw_source_query is None:
        raise SkillError("'population_model' must define either 'segments' or 'source_query'.")

    source_query = None
    if raw_source_query is not None:
        source_query = normalize_population_source_query(raw_source_query)
        raw_segments = build_segments_from_source_query(source_query)
        segment_origin = "source_query"
    else:
        raw_segments = normalize_population_segments(raw_segments)
        segment_origin = "explicit"
    filtered_segments = apply_population_filters(raw_segments, filters)

    return {
        "scope": scope,
        "filters": filters,
        "dimensions": dimensions,
        "source_query": source_query,
        "segment_origin": segment_origin,
        "segments": filtered_segments,
        "segment_count_before_filters": len(raw_segments),
        "segment_count_after_filters": len(filtered_segments),
    }


def normalize_config(raw_config: dict) -> dict:
    if not isinstance(raw_config, dict):
        raise SkillError("Config must be a JSON object.")

    locale = raw_config.get("locale", "en_US")
    if not isinstance(locale, str) or not locale.strip():
        raise SkillError("'locale' must be a string when provided.")

    records = raw_config.get("records")
    if not isinstance(records, int) or records < 1:
        raise SkillError("'records' must be an integer greater than or equal to 1.")

    fields = raw_config.get("fields")
    sql_schema = normalize_sql_schema(raw_config.get("sql_schema"), locale=locale)
    if fields is None:
        if sql_schema is None:
            raise SkillError("'fields' must be a non-empty array unless 'sql_schema' is provided.")
        fields = sql_schema["derived_fields"]
    if not isinstance(fields, list) or not fields:
        raise SkillError("'fields' must be a non-empty array.")

    output = raw_config.get("output")
    legacy_format = raw_config.get("output_format")
    legacy_file = raw_config.get("output_file")

    if output is not None and not isinstance(output, dict):
        raise SkillError("'output' must be an object when provided.")

    output_format = None
    output_path = None
    if output:
        output_format = output.get("format")
        output_path = output.get("path")

    output_format = output_format or legacy_format or "csv"
    if output_format not in SUPPORTED_OUTPUT_FORMATS:
        allowed = ", ".join(sorted(SUPPORTED_OUTPUT_FORMATS))
        raise SkillError(f"'output.format' must be one of: {allowed}. Received: {output_format!r}")

    output_path = output_path or legacy_file or DEFAULT_OUTPUT_NAME[output_format]
    output_table_name = None
    if output:
        output_table_name = output.get("table_name")
    if output_table_name is None and sql_schema is not None:
        output_table_name = sql_schema["table_name"]
    if output_format == "sql" and (not isinstance(output_table_name, str) or not output_table_name.strip()):
        raise SkillError("'output.table_name' is required for SQL output unless it can be derived from 'sql_schema'.")
    population_model = normalize_population_model(raw_config.get("population_model"))

    normalized_fields = []
    seen_names = set()
    for index, field in enumerate(fields, start=1):
        if not isinstance(field, dict):
            raise SkillError(f"Field #{index} must be an object.")

        name = field.get("name")
        field_type = field.get("type")
        params = field.get("params", {})

        if not isinstance(name, str) or not name.strip():
            raise SkillError(f"Field #{index} is missing a valid 'name'.")
        if name in seen_names:
            raise SkillError(f"Duplicate field name: {name!r}")
        if not isinstance(field_type, str) or not field_type.strip():
            raise SkillError(f"Field {name!r} is missing a valid 'type'.")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise SkillError(f"Field {name!r} has invalid 'params'; expected an object.")

        normalized_fields.append(
            {
                "name": name,
                "type": field_type,
                "params": params,
            }
        )
        seen_names.add(name)

    return {
        "version": raw_config.get("version", "1.0"),
        "locale": locale,
        "seed": raw_config.get("seed"),
        "records": records,
        "population_model": population_model,
        "sql_schema": sql_schema,
        "output": {
            "format": output_format,
            "path": output_path,
            "table_name": output_table_name,
        },
        "fields": normalized_fields,
    }


def validate_faker_provider(fake: Faker, provider_name: str, *, field_name: str) -> None:
    if not isinstance(provider_name, str) or not provider_name.strip():
        raise SkillError(f"Field {field_name!r} must reference a valid Faker provider name.")

    provider = getattr(fake, provider_name, None)
    if provider is None or not callable(provider):
        raise SkillError(f"Field {field_name!r} references unsupported Faker provider {provider_name!r}.")


def validate_age_band_mapping(field_name: str, band_name: str, band_definition: dict) -> None:
    if not isinstance(band_definition, dict):
        raise SkillError(
            f"Field {field_name!r} has invalid custom age-band mapping for {band_name!r}; expected an object."
        )

    min_age = band_definition.get("min_age")
    max_age = band_definition.get("max_age")
    if (
        not isinstance(min_age, int)
        or isinstance(min_age, bool)
        or not isinstance(max_age, int)
        or isinstance(max_age, bool)
        or min_age < 0
        or max_age < min_age
    ):
        raise SkillError(
            f"Field {field_name!r} custom age-band {band_name!r} must define integer min_age/max_age with min_age <= max_age."
        )


def validate_field(fake: Faker, field: dict, custom_formats: dict, population_model: dict | None) -> None:
    field_type = field["type"]
    params = field["params"]
    name = field["name"]

    if field_type == "literal":
        if "value" not in params:
            raise SkillError(f"Field {name!r} of type 'literal' requires params.value.")
        return

    if field_type == "choice":
        values = params.get("values")
        if not isinstance(values, list) or not values:
            raise SkillError(f"Field {name!r} of type 'choice' requires a non-empty params.values array.")
        return

    if field_type == "number_int":
        min_value = params.get("min", 0)
        max_value = params.get("max", 100)
        if not isinstance(min_value, int) or not isinstance(max_value, int) or min_value > max_value:
            raise SkillError(f"Field {name!r} has an invalid integer range.")
        return

    if field_type == "number_float":
        min_value = params.get("min", 0)
        max_value = params.get("max", 100)
        precision = params.get("precision", 2)
        if not isinstance(min_value, (int, float)) or not isinstance(max_value, (int, float)) or min_value > max_value:
            raise SkillError(f"Field {name!r} has an invalid float range.")
        if not isinstance(precision, int) or precision < 0:
            raise SkillError(f"Field {name!r} has an invalid precision.")
        return

    if field_type == "date_between":
        return

    if field_type == "segment_value":
        key = params.get("key")
        if not isinstance(key, str) or not key.strip():
            raise SkillError(f"Field {name!r} of type 'segment_value' requires params.key.")
        if population_model is None:
            raise SkillError(f"Field {name!r} requires 'population_model' because it reads a sampled segment value.")
        return

    if field_type == "birth_date_from_age_band":
        segment_key = params.get("segment_key")
        if not isinstance(segment_key, str) or not segment_key.strip():
            raise SkillError(f"Field {name!r} of type 'birth_date_from_age_band' requires params.segment_key.")

        bands = params.get("bands", {})
        if bands is None:
            bands = {}
        if not isinstance(bands, dict):
            raise SkillError(f"Field {name!r} has invalid params.bands; expected an object.")
        for band_name, band_definition in bands.items():
            validate_age_band_mapping(name, str(band_name), band_definition)

        default_max_age = params.get("default_max_age", 100)
        if not isinstance(default_max_age, int) or isinstance(default_max_age, bool) or default_max_age < 0:
            raise SkillError(f"Field {name!r} has invalid params.default_max_age; expected a non-negative integer.")

        reference_date = params.get("reference_date")
        if reference_date is not None:
            parse_iso_date(reference_date, field_label=f"Field {name!r} params.reference_date")

        if population_model is None:
            raise SkillError(f"Field {name!r} requires 'population_model' because it reads a sampled age band.")
        return

    if field_type == "faker_from_segment":
        segment_key = params.get("segment_key")
        if not isinstance(segment_key, str) or not segment_key.strip():
            raise SkillError(f"Field {name!r} of type 'faker_from_segment' requires params.segment_key.")

        providers = params.get("providers")
        if not isinstance(providers, dict) or not providers:
            raise SkillError(f"Field {name!r} of type 'faker_from_segment' requires a non-empty params.providers object.")
        for provider_name in providers.values():
            validate_faker_provider(fake, provider_name, field_name=name)

        fallback_provider = params.get("fallback_provider")
        if fallback_provider is not None:
            validate_faker_provider(fake, fallback_provider, field_name=name)

        provider_params = params.get("provider_params", {})
        if not isinstance(provider_params, dict):
            raise SkillError(f"Field {name!r} has invalid params.provider_params; expected an object.")

        if population_model is None:
            raise SkillError(f"Field {name!r} requires 'population_model' because it reads a sampled segment value.")
        return

    if field_type == "belgian_address_component":
        component = params.get("component")
        if component not in {"street_address", "postcode", "city", "province", "region"}:
            raise SkillError(
                f"Field {name!r} of type 'belgian_address_component' requires params.component to be one of street_address, postcode, city, province, or region."
            )
        profile = params.get("profile", "default")
        if not isinstance(profile, str) or not profile.strip():
            raise SkillError(f"Field {name!r} has invalid params.profile; expected a non-empty string.")
        region_segment_key = params.get("region_segment_key")
        if region_segment_key is not None and (not isinstance(region_segment_key, str) or not region_segment_key.strip()):
            raise SkillError(f"Field {name!r} has invalid params.region_segment_key; expected a non-empty string.")
        for key in {"region", "province", "postcode_prefix", "city"}:
            value = params.get(key)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise SkillError(f"Field {name!r} has invalid params.{key}; expected a non-empty string.")
        if region_segment_key is not None and population_model is None:
            raise SkillError(f"Field {name!r} requires 'population_model' because it reads a sampled region segment value.")
        load_belgian_address_catalog()
        return

    if field_type in {"belgian_insz", "belgian_eid"}:
        return

    if field_type in custom_formats:
        format_definition = custom_formats[field_type]
        if format_definition.get("type") != "regex" or "pattern" not in format_definition:
            raise SkillError(f"Custom format {field_type!r} must declare type='regex' and a pattern.")
        return

    if hasattr(fake, field_type):
        provider = getattr(fake, field_type)
        if not callable(provider):
            raise SkillError(f"Faker attribute {field_type!r} exists but is not callable.")
        return

    raise SkillError(f"Unsupported field type: {field_type!r}")


def build_fake(locale: str, seed: int | None) -> Faker:
    try:
        fake = Faker(locale)
    except Exception as exc:  # noqa: BLE001
        raise SkillError(f"Unsupported Faker locale: {locale!r}") from exc

    if seed is not None:
        if not isinstance(seed, int):
            raise SkillError("'seed' must be an integer when provided.")
        Faker.seed(seed)
        fake.seed_instance(seed)

    return fake


def random_birth_date(rng: random.Random, start_year: int = 1950, end_year: int = 2010) -> date:
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    offset = rng.randint(0, (end - start).days)
    return start + timedelta(days=offset)


def random_date_between(rng: random.Random, start: date, end: date) -> date:
    if start > end:
        raise SkillError("Date range is invalid because the start date is after the end date.")
    offset = rng.randint(0, (end - start).days)
    return start + timedelta(days=offset)


def shift_years_safe(value: date, years: int) -> date:
    target_year = value.year + years
    try:
        return value.replace(year=target_year)
    except ValueError:
        # Handle leap-day overflow by clamping to February 28.
        return value.replace(month=2, day=28, year=target_year)


def resolve_age_range_from_band(age_band, params: dict, field_name: str) -> tuple[int, int]:
    custom_bands = params.get("bands", {})
    age_band_key = str(age_band)
    if age_band_key in custom_bands:
        band_definition = custom_bands[age_band_key]
        return band_definition["min_age"], band_definition["max_age"]

    if not isinstance(age_band, str):
        raise SkillError(
            f"Field {field_name!r} expected a string age band in the sampled segment but received {age_band!r}."
        )

    normalized_age_band = age_band.strip().upper()
    if normalized_age_band == "TOTAL":
        raise SkillError(f"Field {field_name!r} cannot generate a birth date from the non-specific age band 'TOTAL'.")

    match = NUMERIC_AGE_BAND_PATTERN.match(normalized_age_band)
    if match:
        min_age, max_age = int(match.group(1)), int(match.group(2))
        if min_age > max_age:
            raise SkillError(f"Field {field_name!r} received an invalid age band {age_band!r}.")
        return min_age, max_age

    match = NUMERIC_AGE_PLUS_PATTERN.match(normalized_age_band)
    if match:
        min_age = int(match.group(1))
        max_age = params.get("default_max_age", 100)
        if max_age < min_age:
            raise SkillError(f"Field {field_name!r} has default_max_age smaller than the lower age bound in {age_band!r}.")
        return min_age, max_age

    match = STATBEL_AGE_BAND_PATTERN.match(normalized_age_band)
    if match:
        min_age, max_age = int(match.group(1)), int(match.group(2))
        return min_age, max_age

    match = STATBEL_AGE_PLUS_PATTERN.match(normalized_age_band)
    if match:
        min_age = int(match.group(1))
        max_age = params.get("default_max_age", 100)
        if max_age < min_age:
            raise SkillError(f"Field {field_name!r} has default_max_age smaller than the lower age bound in {age_band!r}.")
        return min_age, max_age

    match = STATBEL_AGE_GE_PATTERN.match(normalized_age_band)
    if match:
        min_age = int(match.group(1))
        max_age = params.get("default_max_age", max(min_age, 100))
        if max_age < min_age:
            raise SkillError(f"Field {field_name!r} has default_max_age smaller than the lower age bound in {age_band!r}.")
        return min_age, max_age

    match = STATBEL_AGE_LT_PATTERN.match(normalized_age_band)
    if match:
        upper_bound = int(match.group(1))
        if upper_bound <= 0:
            raise SkillError(f"Field {field_name!r} received an invalid age band {age_band!r}.")
        return 0, upper_bound - 1

    raise SkillError(
        f"Field {field_name!r} could not parse age band {age_band!r}. Provide params.bands for custom labels."
    )


def birth_date_for_age_range(
    rng: random.Random,
    *,
    min_age: int,
    max_age: int,
    reference_date: date,
) -> date:
    earliest_birth_date = shift_years_safe(reference_date, -(max_age + 1)) + timedelta(days=1)
    latest_birth_date = shift_years_safe(reference_date, -min_age)
    return random_date_between(rng, earliest_birth_date, latest_birth_date)


def generate_belgian_insz(rng: random.Random) -> str:
    birth_date = random_birth_date(rng)
    date_part = birth_date.strftime("%y%m%d")
    seq_part = f"{rng.randint(1, 999):03d}"
    base_number_str = date_part + seq_part
    calc_base = int(("2" if birth_date.year >= 2000 else "") + base_number_str)
    checksum = 97 - (calc_base % 97)
    checksum = checksum or 97
    return f"{date_part}-{seq_part}-{checksum:02d}"


def generate_belgian_eid(rng: random.Random) -> str:
    first_part = f"{rng.randint(0, 999):03d}"
    second_part = f"{rng.randint(0, 9_999_999):07d}"
    base_calc = int(first_part + second_part)
    checksum = base_calc % 97
    checksum = checksum or 97
    return f"{first_part}-{second_part}-{checksum:02d}"


def select_population_segment(rng: random.Random, population_model: dict | None) -> dict | None:
    if population_model is None:
        return None

    weights = [segment["normalized_weight"] for segment in population_model["segments"]]
    return rng.choices(population_model["segments"], weights=weights, k=1)[0]


def resolve_segment_value(segment_values: dict | None, key: str, field_name: str, default=MISSING):
    if segment_values is None:
        raise SkillError(f"Field {field_name!r} requires a sampled population segment, but no population model is active.")
    if key in segment_values:
        return segment_values[key]
    if default is not MISSING:
        return default
    raise SkillError(f"Field {field_name!r} could not find segment value {key!r} in the sampled population segment.")


def filter_belgian_address_catalog(
    addresses: list[dict],
    params: dict,
    *,
    segment_values: dict | None,
    field_name: str,
) -> list[dict]:
    filtered = list(addresses)

    region_value = params.get("region")
    region_segment_key = params.get("region_segment_key")
    if region_segment_key is not None:
        region_value = resolve_segment_value(segment_values, region_segment_key, field_name=field_name)
    if region_value is not None:
        filtered = [address for address in filtered if address["region"] == region_value]

    province_value = params.get("province")
    if province_value is not None:
        filtered = [address for address in filtered if address["province"] == province_value]

    postcode_prefix = params.get("postcode_prefix")
    if postcode_prefix is not None:
        filtered = [address for address in filtered if str(address["postcode"]).startswith(str(postcode_prefix))]

    city_value = params.get("city")
    if city_value is not None:
        filtered = [address for address in filtered if address["city"] == city_value]

    if not filtered:
        raise SkillError(f"Field {field_name!r} could not find any Belgian address catalog entries for the requested filters.")
    return filtered


def get_belgian_address_profile(
    rng: random.Random,
    params: dict,
    *,
    segment_values: dict | None,
    row_context: dict,
    field_name: str,
) -> dict:
    cache_key = f"belgian_address::{params.get('profile', 'default')}"
    cached = row_context.get(cache_key)
    if cached is not None:
        return cached

    addresses = load_belgian_address_catalog()
    filtered = filter_belgian_address_catalog(
        addresses,
        params,
        segment_values=segment_values,
        field_name=field_name,
    )
    weighted_localities = {}
    for address in filtered:
        locality_key = (address["region"], address["postcode"], address["city"])
        weighted_localities.setdefault(locality_key, {"weight": address.get("locality_weight", 1), "entries": []})
        weighted_localities[locality_key]["entries"].append(address)
    locality_keys = list(weighted_localities.keys())
    locality_weights = [weighted_localities[key]["weight"] for key in locality_keys]
    chosen_locality = rng.choices(locality_keys, weights=locality_weights, k=1)[0]
    chosen = rng.choice(weighted_localities[chosen_locality]["entries"])
    row_context[cache_key] = chosen
    return chosen


def generate_field_value(
    fake: Faker,
    rng: random.Random,
    field: dict,
    custom_formats: dict,
    *,
    segment_values: dict | None = None,
    row_context: dict | None = None,
):
    field_type = field["type"]
    params = field["params"]
    field_name = field["name"]

    if field_type == "literal":
        return params["value"]

    if field_type == "choice":
        return rng.choice(params["values"])

    if field_type == "number_int":
        return rng.randint(params.get("min", 0), params.get("max", 100))

    if field_type == "number_float":
        precision = params.get("precision", 2)
        value = rng.uniform(params.get("min", 0), params.get("max", 100))
        return round(value, precision)

    if field_type == "date_between":
        return fake.date_between(
            start_date=params.get("start_date", "-30y"),
            end_date=params.get("end_date", "today"),
        ).isoformat()

    if field_type == "segment_value":
        return resolve_segment_value(
            segment_values,
            params["key"],
            field_name=field_name,
            default=params.get("default", MISSING),
        )

    if field_type == "birth_date_from_age_band":
        age_band = resolve_segment_value(segment_values, params["segment_key"], field_name=field_name)
        min_age, max_age = resolve_age_range_from_band(age_band, params, field_name)
        reference_date = parse_iso_date(
            params.get("reference_date", date.today().isoformat()),
            field_label=f"Field {field_name!r} params.reference_date",
        )
        return birth_date_for_age_range(
            rng,
            min_age=min_age,
            max_age=max_age,
            reference_date=reference_date,
        ).isoformat()

    if field_type == "faker_from_segment":
        segment_value = resolve_segment_value(segment_values, params["segment_key"], field_name=field_name)
        provider_name = params["providers"].get(str(segment_value))
        if provider_name is None:
            provider_name = params.get("fallback_provider")
        if provider_name is None:
            raise SkillError(
                f"Field {field_name!r} has no Faker provider mapped for sampled segment value {segment_value!r}."
            )
        provider = getattr(fake, provider_name)
        return provider(**params.get("provider_params", {}))

    if field_type == "belgian_address_component":
        if row_context is None:
            row_context = {}
        profile = get_belgian_address_profile(
            rng,
            params,
            segment_values=segment_values,
            row_context=row_context,
            field_name=field_name,
        )
        return profile[params["component"]]

    if field_type == "belgian_insz":
        return generate_belgian_insz(rng)

    if field_type == "belgian_eid":
        return generate_belgian_eid(rng)

    if field_type in custom_formats:
        return rstr.Xeger(_random=rng).xeger(custom_formats[field_type]["pattern"])

    provider = getattr(fake, field_type, None)
    if callable(provider):
        return provider(**params)

    raise SkillError(f"Unsupported field type during generation: {field_type!r}")


def any_population_aware_fields(config: dict) -> bool:
    return any(field["type"] in POPULATION_AWARE_FIELD_TYPES for field in config["fields"])


def build_representativeness_summary(config: dict) -> dict | None:
    population_model = config.get("population_model")
    if population_model is None:
        return None
    source_query = population_model.get("source_query")

    covered_fields = []
    covered_field_names = set()
    for field in config["fields"]:
        dimension_name = None
        if field["type"] == "segment_value":
            dimension_name = field["params"]["key"]
        elif field["type"] in {"birth_date_from_age_band", "faker_from_segment"}:
            dimension_name = field["params"]["segment_key"]

        if dimension_name is not None:
            covered_fields.append(
                {
                    "field_name": field["name"],
                    "dimension": dimension_name,
                    "strategy": field["type"],
                }
            )
            covered_field_names.add(field["name"])

    seen_dimensions = set()
    dimension_details = []
    for dimension in population_model["dimensions"]:
        if dimension["name"] in seen_dimensions:
            continue
        dimension_details.append(dimension)
        seen_dimensions.add(dimension["name"])

    if source_query is not None:
        for dimension_name, column_name in source_query["dimension_columns"].items():
            if dimension_name not in seen_dimensions:
                dimension_details.append(
                    {
                        "name": dimension_name,
                        "represented": True,
                        "source": {
                            "catalog_id": source_query.get("catalog_id"),
                            "dataset": source_query["dataset"],
                            "column": column_name,
                        },
                    }
                )
                seen_dimensions.add(dimension_name)

    for key in population_model["filters"]:
        if key not in seen_dimensions:
            dimension_details.append({"name": key, "represented": True})
            seen_dimensions.add(key)

    for segment in population_model["segments"]:
        for key in segment["values"]:
            if key not in seen_dimensions:
                dimension_details.append({"name": key, "represented": True})
                seen_dimensions.add(key)

    summary = {
        "mode": "weighted_population_segments",
        "segment_origin": population_model.get("segment_origin", "explicit"),
        "scope": population_model["scope"],
        "filters": population_model["filters"],
        "distribution_backed_dimensions": dimension_details,
        "distribution_backed_fields": covered_fields,
        "non_distribution_fields": [
            field["name"] for field in config["fields"] if field["name"] not in covered_field_names
        ],
        "segment_count_before_filters": population_model["segment_count_before_filters"],
        "segment_count_after_filters": population_model["segment_count_after_filters"],
        "subset_active": bool(population_model["filters"]),
    }
    if source_query is not None:
        summary["source_query"] = {
            "catalog_id": source_query.get("catalog_id"),
            "dataset": source_query["dataset"],
            "dimension_columns": source_query["dimension_columns"],
            "weight_column": source_query["weight_column"],
            "filters": source_query["filters"],
        }
    return summary


def generate_dataset(config: dict, custom_formats: dict | None = None, *, already_normalized: bool = False) -> list[dict]:
    normalized_config = config if already_normalized else normalize_config(config)
    custom_formats = custom_formats or {}

    fake = build_fake(normalized_config["locale"], normalized_config["seed"])
    rng = random.Random(normalized_config["seed"])

    if any_population_aware_fields(normalized_config) and normalized_config["population_model"] is None:
        raise SkillError("Population-aware field types require a top-level 'population_model'.")

    for field in normalized_config["fields"]:
        validate_field(fake, field, custom_formats, normalized_config["population_model"])

    generated_rows = []
    for _ in range(normalized_config["records"]):
        sampled_segment = select_population_segment(rng, normalized_config["population_model"])
        segment_values = sampled_segment["values"] if sampled_segment else None
        row = {}
        row_context = {}
        for field in normalized_config["fields"]:
            row[field["name"]] = generate_field_value(
                fake,
                rng,
                field,
                custom_formats,
                segment_values=segment_values,
                row_context=row_context,
            )
        generated_rows.append(row)

    return generated_rows


def ensure_output_parent(path: Path) -> None:
    if path.parent and str(path.parent) != ".":
        path.parent.mkdir(parents=True, exist_ok=True)


def quote_sql_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def to_sql_literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def build_sql_insert_script(rows: list[dict], *, table_name: str) -> str:
    column_names = list(rows[0].keys()) if rows else []
    quoted_columns = ", ".join(quote_sql_identifier(name) for name in column_names)
    statement_lines = ["BEGIN;"]
    if rows:
        value_lines = []
        for row in rows:
            value_lines.append(
                "(" + ", ".join(to_sql_literal(row[name]) for name in column_names) + ")"
            )
        statement_lines.append(
            f"INSERT INTO {quote_sql_identifier(table_name)} ({quoted_columns}) VALUES\n  "
            + ",\n  ".join(value_lines)
            + ";"
        )
    statement_lines.append("COMMIT;")
    return "\n".join(statement_lines) + "\n"


def write_output(rows: list[dict], output_format: str, output_path: Path, *, output_options: dict | None = None) -> None:
    ensure_output_parent(output_path)
    output_options = output_options or {}

    if output_format == "csv":
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
            if rows:
                writer.writeheader()
                writer.writerows(rows)
        return

    if output_format == "json":
        output_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        return

    if output_format == "ndjson":
        with output_path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return

    if output_format == "sql":
        table_name = output_options.get("table_name")
        if not isinstance(table_name, str) or not table_name.strip():
            raise SkillError("SQL output requires a non-empty output table_name.")
        output_path.write_text(build_sql_insert_script(rows, table_name=table_name), encoding="utf-8")
        return

    raise SkillError(f"Unsupported output format: {output_format!r}")


def build_summary(config: dict, rows: list[dict], output_path: str | None, validate_only: bool, preview_rows: int) -> dict:
    preview = rows[: max(preview_rows, 0)]
    summary = {
        "status": "validated" if validate_only else "generated",
        "version": config["version"],
        "locale": config["locale"],
        "records_requested": config["records"],
        "records_previewed": len(preview),
        "seed": config["seed"],
        "field_names": [field["name"] for field in config["fields"]],
        "preview": preview,
    }
    representativeness = build_representativeness_summary(config)
    if representativeness is not None:
        summary["representativeness"] = representativeness
    if not validate_only:
        summary["records_written"] = len(rows)
        summary["output"] = {
            "format": config["output"]["format"],
            "path": output_path,
        }
        if config["output"].get("table_name"):
            summary["output"]["table_name"] = config["output"]["table_name"]
    if config.get("sql_schema") is not None:
        summary["sql_schema"] = {
            "table_name": config["sql_schema"]["table_name"],
            "column_count": len(config["sql_schema"]["columns"]),
            "derived_field_names": [field["name"] for field in config["fields"]],
        }
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate realistic synthetic datasets from a JSON config.",
    )
    parser.add_argument("--config", required=True, help="Path to the generation config JSON file.")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the config and generate an in-memory preview without writing an output file.",
    )
    parser.add_argument(
        "--preview-rows",
        type=int,
        default=5,
        help="Number of generated rows to include in the JSON summary preview.",
    )
    parser.add_argument(
        "--output",
        help="Override the output path defined in the config.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        raw_config = load_json(Path(args.config))
        custom_formats = load_custom_formats()
        config = normalize_config(raw_config)
        rows = generate_dataset(config, custom_formats=custom_formats, already_normalized=True)

        output_path = None
        if not args.validate_only:
            output_path = Path(args.output) if args.output else Path(config["output"]["path"])
            write_output(rows, config["output"]["format"], output_path, output_options=config["output"])

        summary = build_summary(
            config=config,
            rows=rows,
            output_path=str(output_path) if output_path else None,
            validate_only=args.validate_only,
            preview_rows=args.preview_rows,
        )
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    except SkillError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
