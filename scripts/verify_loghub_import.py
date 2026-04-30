#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WisOps LogHub 一键验收脚本

检查项：
1) /ops/stats 的 Fault 节点是否达到阈值
2) loghub 数据文件是否存在且行数 > 0
3) 从 loghub 文件抽样，逐条调用 /graph/query 验证可查询命中

Usage:
  python scripts/verify_loghub_import.py
  python scripts/verify_loghub_import.py --api-url http://localhost:8021 --sample-size 10
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote

import requests


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def query_has_result(api_url: str, fault_name: str, timeout: int) -> bool:
    encoded = quote(fault_name, safe="")
    url = f"{api_url.rstrip('/')}/graph/query?fault_name={encoded}"
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    # 兼容不同返回结构
    if isinstance(data, dict):
        if isinstance(data.get("solutions"), list) and len(data["solutions"]) > 0:
            return True
        if isinstance(data.get("data"), dict):
            solutions = data["data"].get("solutions")
            if isinstance(solutions, list) and len(solutions) > 0:
                return True
        if isinstance(data.get("status"), str) and data["status"].lower() == "ok":
            # 一些实现返回 ok 且只给 message
            return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="WisOps LogHub 一键验收脚本")
    parser.add_argument("--api-url", default="http://localhost:8021", help="graph-api 地址")
    parser.add_argument(
        "--loghub-file",
        default="data/loghub_faults.jsonl",
        help="LogHub 数据文件路径",
    )
    parser.add_argument("--min-fault", type=int, default=1000, help="Fault 最小验收值")
    parser.add_argument("--sample-size", type=int, default=10, help="抽样查询数量")
    parser.add_argument("--min-hit-rate", type=float, default=0.8, help="最小抽样命中率")
    parser.add_argument("--timeout", type=int, default=10, help="HTTP 请求超时时间（秒）")
    args = parser.parse_args()

    checks: List[tuple[str, bool, str]] = []

    # 1) Fault 总量校验
    try:
        stats_url = f"{args.api_url.rstrip('/')}/ops/stats"
        stats_resp = requests.get(stats_url, timeout=args.timeout)
        stats_resp.raise_for_status()
        stats = stats_resp.json()
        fault_count = int(stats.get("node_counts", {}).get("Fault", 0))
        ok = fault_count >= args.min_fault
        checks.append(
            (
                "Fault 节点总量",
                ok,
                f"{fault_count} (阈值: >= {args.min_fault})",
            )
        )
    except Exception as exc:
        checks.append(("Fault 节点总量", False, f"请求失败: {exc}"))
        fault_count = 0

    # 2) 文件行数校验
    loghub_path = Path(args.loghub_file)
    if not loghub_path.exists():
        checks.append(("LogHub 文件存在", False, f"不存在: {loghub_path}"))
        rows: List[Dict[str, Any]] = []
    else:
        try:
            rows = load_jsonl(loghub_path)
            checks.append(("LogHub 文件行数", len(rows) > 0, f"{len(rows)} 行"))
        except Exception as exc:
            rows = []
            checks.append(("LogHub 文件可解析", False, f"解析失败: {exc}"))

    # 3) 抽样查询校验
    if rows:
        sample_size = min(args.sample_size, len(rows))
        sampled = random.sample(rows, sample_size)
        hit = 0
        failed_faults: List[str] = []
        for item in sampled:
            fault_name = (
                item.get("fault_name")
                or item.get("fault")
                or item.get("name")
                or ""
            ).strip()
            if not fault_name:
                failed_faults.append("<empty fault_name>")
                continue
            try:
                if query_has_result(args.api_url, fault_name, args.timeout):
                    hit += 1
                else:
                    failed_faults.append(fault_name)
            except Exception:
                failed_faults.append(fault_name)

        hit_rate = (hit / sample_size) if sample_size else 0.0
        checks.append(
            (
                "抽样查询命中率",
                hit_rate >= args.min_hit_rate,
                f"{hit}/{sample_size} = {hit_rate:.2%} (阈值: >= {args.min_hit_rate:.0%})",
            )
        )
        if failed_faults:
            preview = "；".join(failed_faults[:5])
            checks.append(("抽样未命中样本", False, preview))
    else:
        checks.append(("抽样查询命中率", False, "无可用样本"))

    # 汇总输出
    print("=" * 64)
    print("WisOps LogHub 一键验收报告")
    print("=" * 64)
    for name, ok, detail in checks:
        flag = "PASS" if ok else "FAIL"
        print(f"[{flag}] {name}: {detail}")

    hard_fail = any(
        (name in {"Fault 节点总量", "LogHub 文件行数", "抽样查询命中率"} and not ok)
        for name, ok, _ in checks
    )

    print("-" * 64)
    print(f"Fault 当前总量: {fault_count}")
    print(f"验收结论: {'FAIL' if hard_fail else 'PASS'}")
    print("=" * 64)

    sys.exit(1 if hard_fail else 0)


if __name__ == "__main__":
    main()

