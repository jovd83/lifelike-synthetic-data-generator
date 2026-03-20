#!/usr/bin/env python

import argparse
import csv
import io
import json
import tempfile
import urllib.request
import zipfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT_DIR / "references" / "belgian_address_catalog.json"

BEST_ADDRESS_SOURCES = {
    "BE-VLG": "https://opendata.bosa.be/download/best/openaddress-bevlg.zip",
    "BE-WAL": "https://opendata.bosa.be/download/best/openaddress-bewal.zip",
    "BE-BRU": "https://opendata.bosa.be/download/best/openaddress-bebru.zip",
}

REGION_ALIAS = {
    "BE-VLG": "VLG",
    "BE-WAL": "WAL",
    "BE-BRU": "BXL",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Belgian address catalog from the official BOSA BeST-address CSV exports.")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Where to write the generated catalog JSON.")
    parser.add_argument(
        "--max-per-locality",
        type=int,
        default=2,
        help="Maximum number of exact addresses to keep per region/postcode/city locality.",
    )
    return parser.parse_args()


def infer_belgian_province(region_code: str, postcode: str) -> str:
    try:
        numeric = int(postcode)
    except ValueError:
        return "Unknown"

    if region_code == "BE-BRU":
        return "Brussels-Capital"

    if region_code == "BE-VLG":
        if 2000 <= numeric <= 2999:
            return "Antwerp"
        if (1500 <= numeric <= 1999) or (3000 <= numeric <= 3499):
            return "Flemish Brabant"
        if 3500 <= numeric <= 3999:
            return "Limburg"
        if 8000 <= numeric <= 8999:
            return "West Flanders"
        if 9000 <= numeric <= 9999:
            return "East Flanders"

    if region_code == "BE-WAL":
        if 1300 <= numeric <= 1499:
            return "Walloon Brabant"
        if 4000 <= numeric <= 4999:
            return "Liege"
        if 5000 <= numeric <= 5999:
            return "Namur"
        if 6000 <= numeric <= 6599 or 7000 <= numeric <= 7999:
            return "Hainaut"
        if 6600 <= numeric <= 6999:
            return "Luxembourg"

    return "Unknown"


def download_to_tempfile(url: str) -> Path:
    temp_path = Path(tempfile.gettempdir()) / Path(url).name
    urllib.request.urlretrieve(url, temp_path)
    return temp_path


def normalized_text(value: str) -> str:
    return " ".join((value or "").strip().split())


def normalized_place_name(value: str) -> str:
    text = normalized_text(value)
    if not text:
        return text
    if text == text.upper():
        return text.title()
    return text


def build_street_address(row: dict) -> str | None:
    street_name = normalized_text(row.get("streetname_nl") or row.get("streetname_fr") or row.get("streetname_de") or "")
    house_number = normalized_text(row.get("house_number", ""))
    if not street_name or not house_number:
        return None
    return f"{street_name} {house_number}"


def build_city_name(row: dict) -> str:
    preferred = row.get("municipality_name_nl") or row.get("postname_nl") or row.get("municipality_name_fr") or row.get("postname_fr") or ""
    return normalized_place_name(preferred)


def collect_addresses_from_source(region_code: str, url: str, *, max_per_locality: int) -> list[dict]:
    zip_path = download_to_tempfile(url)
    by_locality: dict[tuple[str, str, str], list[dict]] = {}
    locality_counts: dict[tuple[str, str, str], int] = {}

    with zipfile.ZipFile(zip_path) as archive:
        csv_name = archive.namelist()[0]
        with archive.open(csv_name) as handle:
            reader = csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8", newline=""))
            for row in reader:
                if normalized_text(row.get("status", "")).lower() != "current":
                    continue
                postcode = normalized_text(row.get("postcode", ""))
                city = build_city_name(row)
                street_address = build_street_address(row)
                if not postcode or not city or not street_address:
                    continue
                locality_key = (region_code, postcode, city)
                locality_counts[locality_key] = locality_counts.get(locality_key, 0) + 1
                current_entries = by_locality.setdefault(locality_key, [])
                if len(current_entries) >= max_per_locality:
                    continue
                current_entries.append(
                    {
                        "region": REGION_ALIAS.get(region_code, region_code.replace("BE-", "")),
                        "province": infer_belgian_province(region_code, postcode),
                        "postcode": postcode,
                        "city": city,
                        "street_address": street_address,
                        "source": {"catalog_id": "data-gov-be", "dataset": "fpsbosa-dis-best-csv-deriv"},
                    }
                )

    addresses = []
    for locality_key in sorted(by_locality):
        locality_weight = locality_counts.get(locality_key, 1)
        kept_entries = by_locality[locality_key]
        for entry in kept_entries:
            entry["locality_weight"] = locality_weight
            entry["locality_size"] = len(kept_entries)
            addresses.append(entry)
    return addresses


def build_catalog(max_per_locality: int) -> dict:
    addresses = []
    for region_code, url in BEST_ADDRESS_SOURCES.items():
        addresses.extend(collect_addresses_from_source(region_code, url, max_per_locality=max_per_locality))
    return {
        "metadata": {
            "source_dataset": "fpsbosa-dis-best-csv-deriv",
            "source_urls": BEST_ADDRESS_SOURCES,
            "max_per_locality": max_per_locality,
            "address_count": len(addresses),
            "note": "Generated from the official weekly BOSA BeST-address CSV exports, keeping a small exact-address sample per locality for deterministic synthetic generation.",
        },
        "addresses": addresses,
    }


def main() -> int:
    args = parse_args()
    catalog = build_catalog(args.max_per_locality)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(output_path), "address_count": catalog["metadata"]["address_count"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
