"""
WisOps V2.0 通用数据导入脚本
支持：Fault/Solution/Asset/Incident/Category 多实体类型
格式：JSON / JSONL / CSV / TXT
"""
import argparse
import csv
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# ──────────────────────────────────────────────────────────────────────────────
# 字段别名归一化
# ──────────────────────────────────────────────────────────────────────────────

FAULT_ALIASES = {
    "fault_name": ["fault_name", "fault", "faultTitle", "name", "故障名", "故障"],
    "solution_name": ["solution_name", "solution", "solutionTitle", "title", "方案名", "方案"],
    "solution_description": ["solution_description", "description", "detail", "步骤", "处理方式"],
    "category": ["category", "fault_type", "类型"],
    "severity": ["severity", "level", "等级"],
}

ASSET_ALIASES = {
    "asset_id": ["asset_id", "id", "资产ID"],
    "name":     ["name", "hostname", "asset_name", "名称"],
    "asset_type": ["asset_type", "type", "类型"],
    "ip":       ["ip", "ip_address", "IP"],
    "env":      ["env", "environment", "环境"],
}

CATEGORY_ALIASES = {
    "code":   ["code", "编码", "id"],
    "name":   ["name", "名称"],
    "level":  ["level", "等级", "priority"],
    "domain": ["domain", "领域", "category"],
}

INCIDENT_ALIASES = {
    "incident_id":    ["incident_id", "ticket_id", "id", "工单ID"],
    "title":          ["title", "summary", "标题", "描述"],
    "fault_name":     ["fault_name", "fault", "故障名"],
    "solution_name":  ["solution_name", "solution", "方案名"],
    "asset_id":       ["asset_id", "resource_id", "资产ID"],
    "mttr_minutes":   ["mttr_minutes", "mttr", "处理时长"],
}

ALIASES_MAP = {
    "Fault":    FAULT_ALIASES,
    "Asset":    ASSET_ALIASES,
    "Category": CATEGORY_ALIASES,
    "Incident": INCIDENT_ALIASES,
}


def normalize(row: Dict[str, Any], aliases: Dict[str, List[str]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for target, candidates in aliases.items():
        for c in candidates:
            if c in row and row[c] not in (None, ""):
                out[target] = row[c]
                break
    return out


# ──────────────────────────────────────────────────────────────────────────────
# 文件解析
# ──────────────────────────────────────────────────────────────────────────────

def parse_file(path: Path) -> List[Dict[str, Any]]:
    suffix = path.suffix.lower()
    text   = path.read_text(encoding="utf-8")

    if suffix in (".jsonl",):
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows

    if suffix == ".json":
        data = json.loads(text)
        return data if isinstance(data, list) else [data]

    if suffix == ".csv":
        rows = []
        reader = csv.DictReader(text.splitlines())
        for row in reader:
            rows.append(dict(row))
        return rows

    # TXT：每行 "故障名 | 方案名 | 方案描述" 或 JSON 行
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("{"):
            try:
                rows.append(json.loads(line))
                continue
            except Exception:
                pass
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2:
            rows.append({
                "fault_name":           parts[0],
                "solution_name":        parts[1],
                "solution_description": parts[2] if len(parts) > 2 else "",
            })
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# 写入逻辑
# ──────────────────────────────────────────────────────────────────────────────

def import_fault(row: Dict[str, Any], api_url: str, args: argparse.Namespace) -> str:
    n = normalize(row, FAULT_ALIASES)
    if not n.get("fault_name") or not n.get("solution_name"):
        return "skip"
    payload = {
        "fault_name":           n["fault_name"],
        "solution_name":        n["solution_name"],
        "solution_description": row.get("description", n.get("solution_description", "")),
        "steps":                row.get("steps", ""),
        "domain":               row.get("domain", ""),
        "data_source":          args.source,
        "confidence":           args.confidence,
        "import_batch_id":      args.batch_id,
    }
    resp = requests.post(f"{api_url}/graph/add", json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json().get("edge_status", "ok")


def import_asset(row: Dict[str, Any], api_url: str, args: argparse.Namespace) -> str:
    n = normalize(row, ASSET_ALIASES)
    if not n.get("asset_id"):
        return "skip"
    payload = [{
        "asset_id":   n["asset_id"],
        "name":       n.get("name", ""),
        "asset_type": n.get("asset_type", "server"),
        "ip":         n.get("ip", ""),
        "env":        n.get("env", "prod"),
        "data_source": args.source,
    }]
    resp = requests.post(f"{api_url}/assets/sync", json=payload, timeout=15)
    resp.raise_for_status()
    return "ok"


def import_category(row: Dict[str, Any], api_url: str, args: argparse.Namespace) -> str:
    n = normalize(row, CATEGORY_ALIASES)
    if not n.get("code") or not n.get("name"):
        return "skip"
    # Category 通过 graph/add 扩展接口写入（简化：直接 POST）
    payload = {
        "fault_name":    f"__category__{n['code']}",
        "solution_name": n["name"],
        "solution_description": f"level={n.get('level','')} domain={n.get('domain','')}",
        "data_source":   args.source,
        "confidence":    1.0,
        "import_batch_id": args.batch_id,
    }
    resp = requests.post(f"{api_url}/graph/add", json=payload, timeout=15)
    resp.raise_for_status()
    return "ok"


def import_incident(row: Dict[str, Any], api_url: str, args: argparse.Namespace) -> str:
    n = normalize(row, INCIDENT_ALIASES)
    if not n.get("incident_id") or not n.get("title"):
        return "skip"
    payload = {
        "incident_id":   n["incident_id"],
        "title":         n["title"],
        "fault_name":    n.get("fault_name"),
        "solution_name": n.get("solution_name"),
        "asset_id":      n.get("asset_id"),
        "mttr_minutes":  int(n.get("mttr_minutes", 0)),
        "data_source":   args.source,
    }
    resp = requests.post(f"{api_url}/incidents", json=payload, timeout=15)
    resp.raise_for_status()
    return "ok"


IMPORT_FN = {
    "Fault":    import_fault,
    "Asset":    import_asset,
    "Category": import_category,
    "Incident": import_incident,
}


# ──────────────────────────────────────────────────────────────────────────────
# 主函数
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="WisOps V2.0 数据导入脚本")
    parser.add_argument("file",                  help="数据文件路径（json/jsonl/csv/txt）")
    parser.add_argument("--api-url",             default="http://localhost:8021", help="graph-api 基础 URL")
    parser.add_argument("--entity-type",         default="Fault",
                        choices=["Fault", "Asset", "Category", "Incident"],
                        help="目标实体类型，默认 Fault")
    parser.add_argument("--source",              default="manual",     help="data_source 标记")
    parser.add_argument("--confidence",          type=float, default=1.0, help="置信度（0.0~1.0）")
    parser.add_argument("--batch-id",            default="",           help="批次 ID，为空则自动生成")
    parser.add_argument("--conflict",            default="skip", choices=["skip", "overwrite"],
                        help="冲突策略（skip=跳过已存在，overwrite=覆盖）")
    parser.add_argument("--dry-run",             action="store_true",  help="仅解析校验，不写入")
    parser.add_argument("--delay",               type=float, default=0.05, help="每条写入间隔秒数")
    args = parser.parse_args()

    if not args.batch_id:
        args.batch_id = f"import-{args.entity_type.lower()}-{str(uuid.uuid4())[:8]}"

    path = Path(args.file)
    if not path.exists():
        print(f"[ERROR] 文件不存在：{path}")
        sys.exit(1)

    rows = parse_file(path)
    print(f"[INFO] 解析完成：{len(rows)} 条记录 | 类型：{args.entity_type} | 来源：{args.source}")
    print(f"[INFO] 批次 ID：{args.batch_id}")

    if args.dry_run:
        print("[DRY-RUN] 校验模式，不写入。前 3 条预览：")
        for r in rows[:3]:
            print(" ", r)
        return

    success, failed, skipped = 0, 0, 0
    import_fn = IMPORT_FN[args.entity_type]
    start = time.time()

    for i, row in enumerate(rows, 1):
        try:
            result = import_fn(row, args.api_url, args)
            if result == "skip":
                skipped += 1
                print(f"[{i}/{len(rows)}] SKIP  {row}")
            else:
                success += 1
                if i % 20 == 0 or i == len(rows):
                    print(f"[{i}/{len(rows)}] 已导入 {success} 条...")
        except Exception as e:
            failed += 1
            print(f"[{i}/{len(rows)}] FAIL  {row} -> {e}")
        if args.delay > 0:
            time.sleep(args.delay)

    elapsed = round(time.time() - start, 1)
    print("\n" + "=" * 50)
    print(f"导入完成")
    print(f"  总解析：{len(rows)} 条")
    print(f"  成功：  {success} 条")
    print(f"  跳过：  {skipped} 条")
    print(f"  失败：  {failed} 条")
    print(f"  耗时：  {elapsed}s")
    print(f"  批次：  {args.batch_id}")
    print("=" * 50)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
