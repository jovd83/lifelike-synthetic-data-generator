#!/usr/bin/env python

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import check_open_data_updates
import generate_data


DEFAULT_MONITORING_PATH = generate_data.ROOT_DIR / "references" / "open_data_monitoring.json"
DEFAULT_SOURCE_IDS = [
    "statbel-open-data-api",
    "data-gov-be",
    "eurostat-api",
    "geonames",
    "worldpop",
    "world-bank-data",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh the stored open-data monitoring snapshot from live discovery endpoints.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_MONITORING_PATH),
        help="Path to write the refreshed monitoring snapshot JSON file.",
    )
    parser.add_argument(
        "--source-id",
        action="append",
        dest="source_ids",
        help="Source id to refresh. Repeat to include multiple sources. Defaults to the built-in monitored set.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        source_ids = args.source_ids or DEFAULT_SOURCE_IDS
        refreshed_sources = []
        today_utc = datetime.now(timezone.utc).date().isoformat()

        for source_id in source_ids:
            source_snapshot = check_open_data_updates.discover_live_source_snapshot(source_id)
            source_snapshot["last_verified"] = today_utc
            refreshed_sources.append(source_snapshot)

        payload = {
            "version": "1.1",
            "sources": refreshed_sources,
        }
        output_path = Path(args.output)
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"status": "refreshed", "output": str(output_path), "source_ids": source_ids}, indent=2))
        return 0
    except generate_data.SkillError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
