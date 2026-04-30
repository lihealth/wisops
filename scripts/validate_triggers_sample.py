#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TRIGGERS 抽样验收脚本

输入：triggers_audit CSV（由 export_triggers_audit.py 生成）
输出：抽样复核报告 markdown（人工勾选）

Usage:
  python scripts/validate_triggers_sample.py
  python scripts/validate_triggers_sample.py --csv data/triggers_audit_latest.csv --sample-size 100
"""
from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def read_rows(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k: (v or "").strip() for k, v in row.items()})
    return rows


def ratio(n: int, d: int) -> float:
    return (n / d * 100.0) if d else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate TRIGGERS audit sample")
    parser.add_argument("--csv", default="data/triggers_audit_latest.csv", help="审计 CSV 路径")
    parser.add_argument("--sample-size", type=int, default=100, help="抽样条数")
    parser.add_argument("--seed", type=int, default=20260429, help="随机种子（保证可复现）")
    parser.add_argument(
        "--out-file",
        default=f"data/TRIGGERS_SAMPLE_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
        help="输出报告路径",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"[ERROR] CSV not found: {csv_path}")

    rows = read_rows(csv_path)
    if not rows:
        raise SystemExit(f"[ERROR] CSV has no data rows: {csv_path}")

    random.seed(args.seed)
    sample_size = max(1, min(int(args.sample_size), len(rows)))
    sample = random.sample(rows, sample_size)

    rule_hits = sum(1 for r in rows if r.get("method") == "rule")
    fuzzy_hits = sum(1 for r in rows if r.get("method") == "fuzzy")
    exists_hits = sum(1 for r in rows if r.get("exists", "").lower() in {"true", "1"})
    avg_conf = sum(float(r.get("confidence", "0") or 0) for r in rows) / len(rows)

    out = Path(args.out_file)
    out.parent.mkdir(parents=True, exist_ok=True)

    lines: List[str] = []
    lines.append("# TRIGGERS 抽样验收报告")
    lines.append("")
    lines.append(f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 数据文件: `{csv_path.as_posix()}`")
    lines.append(f"- 总候选边数: {len(rows)}")
    lines.append(f"- 抽样条数: {sample_size}")
    lines.append(f"- 随机种子: {args.seed}")
    lines.append("")
    lines.append("## 统计概览")
    lines.append(f"- rule 命中: {rule_hits} ({ratio(rule_hits, len(rows)):.1f}%)")
    lines.append(f"- fuzzy 命中: {fuzzy_hits} ({ratio(fuzzy_hits, len(rows)):.1f}%)")
    lines.append(f"- 已存在边: {exists_hits} ({ratio(exists_hits, len(rows)):.1f}%)")
    lines.append(f"- 平均置信度: {avg_conf:.3f}")
    lines.append("")
    lines.append("## 抽样复核清单（人工勾选）")
    lines.append("")
    lines.append("| # | alert_id | fault_name | confidence | method | rule_name | 复核结论 | 备注 |")
    lines.append("|---|---|---|---:|---|---|---|---|")
    for idx, r in enumerate(sample, 1):
        alert_id = r.get("alert_id", "").replace("|", " ")
        fault_name = r.get("fault_name", "").replace("|", " ")
        conf = r.get("confidence", "")
        method = r.get("method", "")
        rule_name = r.get("rule_name", "")
        lines.append(
            f"| {idx} | `{alert_id}` | {fault_name} | {conf} | {method} | {rule_name} | ☐通过 / ☐不通过 | |"
        )

    lines.append("")
    lines.append("## 验收建议")
    lines.append("- 建议抽样通过率 >= 85% 作为当前规则上线阈值。")
    lines.append("- 若不通过样本集中在某类 rule_name，优先调整该规则。")
    lines.append("- 对空 rule_name 且 method=fuzzy 的样本，建议后续沉淀为显式规则。")
    lines.append("")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("=" * 60)
    print("TRIGGERS 抽样验收报告已生成")
    print("=" * 60)
    print(f"input_csv    : {csv_path.as_posix()}")
    print(f"total_rows   : {len(rows)}")
    print(f"sample_size  : {sample_size}")
    print(f"output_report: {out.as_posix()}")
    print("=" * 60)


if __name__ == "__main__":
    main()

