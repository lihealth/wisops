import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import requests


Record = Dict[str, str]


def normalize_record(raw: Dict[str, str]) -> Record:
    fault_name = (
        raw.get("fault_name")
        or raw.get("fault")
        or raw.get("faultTitle")
        or raw.get("name")
        or ""
    ).strip()
    solution_name = (
        raw.get("solution_name")
        or raw.get("solution")
        or raw.get("solutionTitle")
        or raw.get("title")
        or ""
    ).strip()
    solution_description = (
        raw.get("solution_description")
        or raw.get("description")
        or raw.get("detail")
        or ""
    ).strip()
    return {
        "fault_name": fault_name,
        "solution_name": solution_name,
        "solution_description": solution_description,
    }


def parse_csv(path: Path) -> List[Record]:
    records: List[Record] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(normalize_record({k: (v or "") for k, v in row.items()}))
    return records


def parse_json(path: Path) -> List[Record]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        data = data.get("data", [])
    if not isinstance(data, list):
        raise ValueError("JSON must be a list of objects or {\"data\": [...]} format")

    records: List[Record] = []
    for item in data:
        if isinstance(item, dict):
            records.append(normalize_record({k: str(v) if v is not None else "" for k, v in item.items()}))
    return records


def parse_txt(path: Path) -> List[Record]:
    """
    Supported line formats:
    - fault_name|solution_name|solution_description
    - fault_name<TAB>solution_name<TAB>solution_description
    - fault_name,solution_name,solution_description
    Description is optional.
    """
    records: List[Record] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts: List[str]
            if "\t" in line:
                parts = [p.strip() for p in line.split("\t")]
            elif "|" in line:
                parts = [p.strip() for p in line.split("|")]
            else:
                parts = [p.strip() for p in line.split(",")]

            if len(parts) < 2:
                continue

            fault_name = parts[0]
            solution_name = parts[1]
            solution_description = parts[2] if len(parts) >= 3 else ""
            records.append(
                {
                    "fault_name": fault_name,
                    "solution_name": solution_name,
                    "solution_description": solution_description,
                }
            )
    return records


def load_records(path: Path) -> List[Record]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return parse_csv(path)
    if suffix == ".json":
        return parse_json(path)
    if suffix == ".txt":
        return parse_txt(path)
    raise ValueError(f"Unsupported file type: {suffix}. Use .txt/.csv/.json")


def validate_records(records: Iterable[Record]) -> Tuple[List[Record], int]:
    valid: List[Record] = []
    skipped = 0
    for r in records:
        if r["fault_name"] and r["solution_name"]:
            valid.append(r)
        else:
            skipped += 1
    return valid, skipped


def import_records(records: List[Record], endpoint: str, timeout: int, dry_run: bool) -> Tuple[int, int]:
    success = 0
    failed = 0

    for idx, record in enumerate(records, start=1):
        if dry_run:
            print(f"[DRY-RUN] #{idx}: {record['fault_name']} -> {record['solution_name']}")
            success += 1
            continue

        try:
            resp = requests.post(endpoint, json=record, timeout=timeout)
            if resp.ok:
                success += 1
                print(f"[OK] #{idx}: {record['fault_name']} -> {record['solution_name']}")
            else:
                failed += 1
                print(f"[FAIL] #{idx}: HTTP {resp.status_code} - {resp.text}")
        except requests.RequestException as exc:
            failed += 1
            print(f"[FAIL] #{idx}: {exc}")

    return success, failed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch import fault-solution relations to WisOps graph-api (/graph/add)."
    )
    parser.add_argument("input_file", help="Path to input file (.txt/.csv/.json)")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8002/graph/add",
        help="graph-api add endpoint (default: http://localhost:8002/graph/add)",
    )
    parser.add_argument("--timeout", type=int, default=10, help="HTTP timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print records without importing")
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    all_records = load_records(input_path)
    valid_records, skipped_invalid = validate_records(all_records)
    success, failed = import_records(valid_records, args.api_url, args.timeout, args.dry_run)

    print("\n=== Import Summary ===")
    print(f"Source file      : {input_path}")
    print(f"Total parsed     : {len(all_records)}")
    print(f"Valid records    : {len(valid_records)}")
    print(f"Skipped invalid  : {skipped_invalid}")
    print(f"Imported success : {success}")
    print(f"Imported failed  : {failed}")

    if failed > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
