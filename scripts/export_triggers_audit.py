#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
导出 TRIGGERS 匹配审计 CSV（不写边，纯审计）

Usage:
  python scripts/export_triggers_audit.py
  python scripts/export_triggers_audit.py --api-url http://localhost:8021 --min-confidence 0.8 --top-k 1
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import requests


def main() -> None:
    parser = argparse.ArgumentParser(description="Export TRIGGERS audit CSV")
    parser.add_argument("--api-url", default="http://localhost:8021", help="graph-api 地址")
    parser.add_argument("--min-confidence", type=float, default=0.8, help="最小置信度阈值")
    parser.add_argument("--top-k", type=int, default=1, help="每条告警候选上限")
    parser.add_argument("--candidate-limit", type=int, default=5000, help="最大导出候选数")
    parser.add_argument(
        "--out-file",
        default=f"data/triggers_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        help="输出 CSV 路径",
    )
    args = parser.parse_args()

    url = (
        f"{args.api_url.rstrip('/')}/admin/triggers/sync"
        f"?dry_run=true"
        f"&top_k_per_alert={args.top_k}"
        f"&min_confidence={args.min_confidence}"
        f"&include_candidates=true"
        f"&candidate_limit={args.candidate_limit}"
    )
    resp = requests.post(url, timeout=600)
    resp.raise_for_status()
    data: Dict[str, Any] = resp.json()
    rows: List[Dict[str, Any]] = data.get("candidates", []) or []

    out = Path(args.out_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    headers = ["alert_id", "fault_id", "fault_name", "confidence", "method", "rule_name", "exists"]
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in headers})

    print("=" * 60)
    print("TRIGGERS 审计导出完成")
    print("=" * 60)
    print(f"alerts_scanned   : {data.get('alerts_scanned', 0)}")
    print(f"matched_alerts   : {data.get('matched_alerts', 0)}")
    print(f"candidate_edges  : {data.get('candidate_edges', 0)}")
    print(f"rule_hits        : {data.get('rule_hits', 0)}")
    print(f"fuzzy_hits       : {data.get('fuzzy_hits', 0)}")
    print(f"csv_rows         : {len(rows)}")
    print(f"output_csv       : {out.as_posix()}")
    print("=" * 60)


if __name__ == "__main__":
    main()

