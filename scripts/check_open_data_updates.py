#!/usr/bin/env python

import argparse
import html
import json
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import generate_data


DEFAULT_MONITORING_PATH = generate_data.ROOT_DIR / "references" / "open_data_monitoring.json"


def load_monitoring_snapshot(path: Path) -> dict:
    data = generate_data.load_json(path)
    sources = data.get("sources", [])
    if not isinstance(sources, list):
        raise generate_data.SkillError(f"Expected 'sources' to be an array in {path}")
    return data


def get_monitoring_source(source_id: str, monitoring_snapshot: dict) -> dict:
    for source in monitoring_snapshot.get("sources", []):
        if source.get("id") == source_id:
            return source
    raise generate_data.SkillError(f"Monitoring snapshot does not include source {source_id!r}.")


def get_live_discovery_endpoint(source_id: str) -> str:
    source_catalog_entry = generate_data.get_open_data_source_by_id(source_id)
    discovery_endpoints = source_catalog_entry.get("access", {}).get("discovery_endpoints", [])
    if not isinstance(discovery_endpoints, list):
        raise generate_data.SkillError(f"Source {source_id!r} has invalid discovery endpoint metadata.")

    for endpoint in discovery_endpoints:
        if endpoint.endswith("/rpc/get_tables_columns_grouped"):
            return endpoint

    raise generate_data.SkillError(
        f"Source {source_id!r} does not expose a supported grouped discovery endpoint in references/open_data_sources.json."
    )


def get_source_catalog_entry(source_id: str) -> dict:
    return generate_data.get_open_data_source_by_id(source_id)


def get_source_discovery_endpoints(source_id: str) -> list[str]:
    source_catalog_entry = get_source_catalog_entry(source_id)
    discovery_endpoints = source_catalog_entry.get("access", {}).get("discovery_endpoints", [])
    if not isinstance(discovery_endpoints, list):
        raise generate_data.SkillError(f"Source {source_id!r} has invalid discovery endpoint metadata.")
    return discovery_endpoints


def get_discovery_endpoint_by_suffix(source_id: str, suffix: str) -> str:
    for endpoint in get_source_discovery_endpoints(source_id):
        if endpoint.endswith(suffix):
            return endpoint
    raise generate_data.SkillError(
        f"Source {source_id!r} does not expose a discovery endpoint ending with {suffix!r}."
    )


def normalize_statbel_rows(rows: list[dict]) -> list[dict]:
    normalized = []
    for row in sorted(rows, key=lambda item: item["table_name"]):
        columns = {}
        for column in row.get("columns_info", []):
            column_name = column.get("column_name")
            data_type = column.get("data_type")
            if isinstance(column_name, str) and isinstance(data_type, str):
                columns[column_name] = data_type
        normalized.append(
            {
                "id": row["table_name"],
                "columns": columns,
            }
        )
    return normalized


def discover_statbel_source_snapshot(source_id: str) -> dict:
    endpoint = get_discovery_endpoint_by_suffix(source_id, "/rpc/get_tables_columns_grouped")
    rows = generate_data.fetch_json_url(endpoint)
    if not isinstance(rows, list):
        raise generate_data.SkillError(f"Discovery endpoint {endpoint} did not return a JSON array.")

    return {
        "id": source_id,
        "discovery_endpoint": endpoint,
        "dataset_count": len(rows),
        "datasets": normalize_statbel_rows(rows),
    }


def normalize_eurostat_dataflows(xml_payload: bytes) -> list[dict]:
    ns = {
        "s": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure",
    }
    root = ET.fromstring(xml_payload)
    normalized = []
    for item in sorted(root.findall(".//s:Dataflow", ns), key=lambda element: element.attrib.get("id", "")):
        dataset_id = item.attrib.get("id")
        if not dataset_id:
            continue
        normalized.append(
            {
                "id": dataset_id,
                "metadata": {
                    "agency_id": item.attrib.get("agencyID"),
                    "version": item.attrib.get("version"),
                    "is_final": item.attrib.get("isFinal"),
                },
            }
        )
    return normalized


def discover_eurostat_source_snapshot(source_id: str) -> dict:
    endpoint = get_discovery_endpoint_by_suffix(source_id, "/dataflow/ESTAT/all/latest")
    try:
        with generate_data.urllib.request.urlopen(endpoint, timeout=generate_data.DEFAULT_NETWORK_TIMEOUT_SEC) as response:
            payload = response.read()
    except generate_data.urllib.error.URLError as exc:
        raise generate_data.SkillError(f"Failed to fetch Eurostat discovery XML from {endpoint}: {exc.reason}") from exc

    datasets = normalize_eurostat_dataflows(payload)
    return {
        "id": source_id,
        "discovery_endpoint": endpoint,
        "dataset_count": len(datasets),
        "datasets": datasets,
    }


def discover_world_bank_source_snapshot(source_id: str) -> dict:
    endpoint = get_discovery_endpoint_by_suffix(source_id, "/v2/sources?format=json&per_page=200")
    payload = generate_data.fetch_json_url(endpoint)
    if not isinstance(payload, list) or len(payload) != 2:
        raise generate_data.SkillError(f"World Bank discovery endpoint {endpoint} did not return the expected two-item JSON array.")

    meta, rows = payload
    if not isinstance(meta, dict) or not isinstance(rows, list):
        raise generate_data.SkillError(f"World Bank discovery endpoint {endpoint} returned an unexpected payload shape.")

    datasets = []
    for row in sorted(rows, key=lambda item: str(item.get("id", ""))):
        dataset_id = str(row.get("id", ""))
        if not dataset_id:
            continue
        datasets.append(
            {
                "id": dataset_id,
                "metadata": {
                    "code": row.get("code"),
                    "name": row.get("name"),
                    "lastupdated": row.get("lastupdated"),
                    "dataavailability": row.get("dataavailability"),
                    "metadataavailability": row.get("metadataavailability"),
                },
            }
        )

    dataset_count = meta.get("total", len(datasets))
    try:
        dataset_count = int(dataset_count)
    except (TypeError, ValueError):
        dataset_count = len(datasets)

    return {
        "id": source_id,
        "discovery_endpoint": endpoint,
        "dataset_count": dataset_count,
        "datasets": datasets,
    }


def discover_data_gov_be_source_snapshot(source_id: str) -> dict:
    endpoint = get_discovery_endpoint_by_suffix(source_id, "/repos/fedict/dcat/contents/all")
    rows = generate_data.fetch_json_url(endpoint)
    if not isinstance(rows, list):
        raise generate_data.SkillError(f"Data.gov.be discovery endpoint {endpoint} did not return a JSON array.")

    datasets = []
    for row in sorted(rows, key=lambda item: item.get("name", "")):
        if row.get("type") != "file":
            continue
        dataset_id = row.get("name")
        if not isinstance(dataset_id, str) or not dataset_id:
            continue
        datasets.append(
            {
                "id": dataset_id,
                "metadata": {
                    "size": row.get("size"),
                    "sha": row.get("sha"),
                    "download_url": row.get("download_url"),
                },
            }
        )

    return {
        "id": source_id,
        "discovery_endpoint": endpoint,
        "dataset_count": len(datasets),
        "datasets": datasets,
    }


GEONAMES_DUMP_ENTRY_RE = re.compile(
    r'<a href="(?P<href>[^"]+)">(?P<label>[^<]+)</a>\s+'
    r'(?P<last_modified>\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s+'
    r'(?P<size>[-0-9A-Za-z.]+)',
    re.IGNORECASE,
)


def normalize_geonames_dump_listing(html_payload: str) -> list[dict]:
    datasets = []
    for match in GEONAMES_DUMP_ENTRY_RE.finditer(html_payload):
        href = html.unescape(match.group("href")).strip()
        label = html.unescape(match.group("label")).strip()
        if href != label:
            continue
        if href in {"Parent Directory", "Readme.txt"}:
            continue
        if href.endswith("/"):
            continue
        datasets.append(
            {
                "id": href,
                "metadata": {
                    "last_modified": match.group("last_modified"),
                    "size": match.group("size"),
                },
            }
        )
    return sorted(datasets, key=lambda item: item["id"])


def discover_geonames_source_snapshot(source_id: str) -> dict:
    endpoint = get_discovery_endpoint_by_suffix(source_id, "/export/dump/")
    try:
        with generate_data.urllib.request.urlopen(endpoint, timeout=generate_data.DEFAULT_NETWORK_TIMEOUT_SEC) as response:
            payload = response.read().decode("utf-8", errors="replace")
    except generate_data.urllib.error.URLError as exc:
        raise generate_data.SkillError(f"Failed to fetch GeoNames dump listing from {endpoint}: {exc.reason}") from exc

    datasets = normalize_geonames_dump_listing(payload)
    return {
        "id": source_id,
        "discovery_endpoint": endpoint,
        "dataset_count": len(datasets),
        "datasets": datasets,
    }


def discover_worldpop_source_snapshot(source_id: str) -> dict:
    endpoint = get_discovery_endpoint_by_suffix(source_id, "/rest/data")
    root_payload = generate_data.fetch_json_url(endpoint)
    root_rows = root_payload.get("data", [])
    if not isinstance(root_rows, list):
        raise generate_data.SkillError(f"WorldPop discovery endpoint {endpoint} did not return a 'data' array.")

    datasets = []
    base_endpoint = endpoint.rstrip("/")

    for root_row in root_rows:
        root_alias = root_row.get("alias")
        root_name = root_row.get("name")
        if not isinstance(root_alias, str) or not root_alias:
            continue
        root_alias_clean = root_alias.strip()
        if not root_alias_clean:
            continue

        datasets.append(
            {
                "id": f"category:{root_alias_clean}",
                "metadata": {
                    "level": "category",
                    "name": root_name,
                },
            }
        )

        child_endpoint = f"{base_endpoint}/{urllib.parse.quote(root_alias_clean, safe='')}"
        child_payload = generate_data.fetch_json_url(child_endpoint)
        child_rows = child_payload.get("data", [])
        if not isinstance(child_rows, list):
            raise generate_data.SkillError(f"WorldPop child endpoint {child_endpoint} did not return a 'data' array.")

        for child_row in child_rows:
            child_alias = child_row.get("alias")
            child_name = child_row.get("name")
            if not isinstance(child_alias, str) or not child_alias:
                continue
            child_alias_clean = child_alias.strip()
            if not child_alias_clean:
                continue

            datasets.append(
                {
                    "id": f"collection:{root_alias_clean}/{child_alias_clean}",
                    "metadata": {
                        "level": "collection",
                        "root_alias": root_alias_clean,
                        "name": child_name,
                        "source_alias": child_alias,
                    },
                }
            )

            grandchild_endpoint = (
                f"{base_endpoint}/{urllib.parse.quote(root_alias_clean, safe='')}/"
                f"{urllib.parse.quote(child_alias_clean, safe='')}"
            )
            try:
                grandchild_payload = generate_data.fetch_json_url(grandchild_endpoint)
                grandchild_rows = grandchild_payload.get("data", [])
                if not isinstance(grandchild_rows, list):
                    raise generate_data.SkillError(
                        f"WorldPop dataset endpoint {grandchild_endpoint} did not return a 'data' array."
                    )
            except generate_data.SkillError:
                datasets[-1]["metadata"]["terminal_listing_available"] = False
                continue

            for grandchild_row in grandchild_rows:
                dataset_id = grandchild_row.get("id")
                if dataset_id is None:
                    continue
                datasets.append(
                    {
                        "id": f"dataset:{root_alias_clean}/{child_alias_clean}/{dataset_id}",
                        "metadata": {
                            "level": "dataset",
                            "root_alias": root_alias_clean,
                            "collection_alias": child_alias_clean,
                            "title": grandchild_row.get("title"),
                            "iso3": grandchild_row.get("iso3"),
                            "popyear": grandchild_row.get("popyear"),
                        },
                    }
                )

    datasets.sort(key=lambda item: item["id"])
    return {
        "id": source_id,
        "discovery_endpoint": endpoint,
        "dataset_count": len(datasets),
        "datasets": datasets,
    }


def discover_live_source_snapshot(source_id: str) -> dict:
    if source_id == "statbel-open-data-api":
        return discover_statbel_source_snapshot(source_id)
    if source_id == "data-gov-be":
        return discover_data_gov_be_source_snapshot(source_id)
    if source_id == "geonames":
        return discover_geonames_source_snapshot(source_id)
    if source_id == "worldpop":
        return discover_worldpop_source_snapshot(source_id)
    if source_id == "eurostat-api":
        return discover_eurostat_source_snapshot(source_id)
    if source_id == "world-bank-data":
        return discover_world_bank_source_snapshot(source_id)
    raise generate_data.SkillError(f"No live discovery adapter is implemented for source {source_id!r}.")


def compare_flat_mapping(expected_mapping: dict, live_mapping: dict, *, label_prefix: str) -> dict:
    expected_keys = set(expected_mapping)
    live_keys = set(live_mapping)
    new_keys = sorted(live_keys - expected_keys)
    removed_keys = sorted(expected_keys - live_keys)
    changed_keys = []

    for key in sorted(expected_keys & live_keys):
        if expected_mapping[key] != live_mapping[key]:
            changed_keys.append(
                {
                    "field": key,
                    "expected_value": expected_mapping[key],
                    "live_value": live_mapping[key],
                }
            )

    return {
        f"new_{label_prefix}": new_keys,
        f"removed_{label_prefix}": removed_keys,
        f"{label_prefix}_changes": changed_keys,
    }


def build_update_report(expected_source: dict, live_source: dict) -> dict:
    expected_map = {dataset["id"]: dataset for dataset in expected_source.get("datasets", [])}
    live_map = {dataset["id"]: dataset for dataset in live_source.get("datasets", [])}

    expected_ids = set(expected_map)
    live_ids = set(live_map)

    new_datasets = sorted(live_ids - expected_ids)
    removed_datasets = sorted(expected_ids - live_ids)
    changed_datasets = []

    for dataset_id in sorted(expected_ids & live_ids):
        expected_dataset = expected_map[dataset_id]
        live_dataset = live_map[dataset_id]

        expected_columns = expected_dataset.get("columns", {})
        live_columns = live_dataset.get("columns", {})
        column_diff = compare_flat_mapping(expected_columns, live_columns, label_prefix="columns")

        expected_metadata = expected_dataset.get("metadata", {})
        live_metadata = live_dataset.get("metadata", {})
        metadata_diff = compare_flat_mapping(expected_metadata, live_metadata, label_prefix="metadata_fields")

        if (
            column_diff["new_columns"]
            or column_diff["removed_columns"]
            or column_diff["columns_changes"]
            or metadata_diff["new_metadata_fields"]
            or metadata_diff["removed_metadata_fields"]
            or metadata_diff["metadata_fields_changes"]
        ):
            changed_datasets.append(
                {
                    "id": dataset_id,
                    "new_columns": column_diff["new_columns"],
                    "removed_columns": column_diff["removed_columns"],
                    "type_changes": [
                        {
                            "column": item["field"],
                            "expected_type": item["expected_value"],
                            "live_type": item["live_value"],
                        }
                        for item in column_diff["columns_changes"]
                    ],
                    "new_metadata_fields": metadata_diff["new_metadata_fields"],
                    "removed_metadata_fields": metadata_diff["removed_metadata_fields"],
                    "metadata_changes": [
                        {
                            "field": item["field"],
                            "expected_value": item["expected_value"],
                            "live_value": item["live_value"],
                        }
                        for item in metadata_diff["metadata_fields_changes"]
                    ],
                }
            )

    status = "up_to_date"
    if new_datasets or removed_datasets or changed_datasets:
        status = "drift_detected"

    return {
        "status": status,
        "source_id": expected_source["id"],
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "expected_last_verified": expected_source.get("last_verified"),
        "expected_dataset_count": len(expected_map),
        "live_dataset_count": len(live_map),
        "new_datasets": new_datasets,
        "removed_datasets": removed_datasets,
        "changed_datasets": changed_datasets,
        "discovery_endpoint": live_source.get("discovery_endpoint"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare live public-data discovery endpoints against the stored monitoring snapshot.",
    )
    parser.add_argument(
        "--source-id",
        default="statbel-open-data-api",
        help="Source id from references/open_data_sources.json and references/open_data_monitoring.json.",
    )
    parser.add_argument(
        "--monitoring-file",
        default=str(DEFAULT_MONITORING_PATH),
        help="Path to the monitoring snapshot JSON file.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 when drift is detected.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        monitoring_snapshot = load_monitoring_snapshot(Path(args.monitoring_file))
        expected_source = get_monitoring_source(args.source_id, monitoring_snapshot)
        live_source = discover_live_source_snapshot(args.source_id)
        report = build_update_report(expected_source, live_source)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if args.strict and report["status"] != "up_to_date":
            return 1
        return 0
    except generate_data.SkillError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
