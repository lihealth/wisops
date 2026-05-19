#!/usr/bin/env python3
"""
Stack Exchange Posts.xml → 清洗为 Fault/Solution 对 → JSONL 与/或 graph-api 批量导入。

输入：官方站点导出中的 Posts.xml（如 serverfault.com / stackoverflow.com 7z 包内）。
输出：JSONL（fault_name / solution_name / solution_description / 元数据），data_source 固定为 stackoverflow。

许可：Stack Exchange 用户贡献内容通常为 CC BY-SA，使用请遵守站点条款与署名要求。
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sqlite3
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set

import requests

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")

# 运维相关站点默认可选标签过滤（任一命中即保留）；可用 --no-tag-filter 关闭
DEFAULT_TAGS_ANY = (
    "linux",
    "windows",
    "ubuntu",
    "debian",
    "nginx",
    "apache",
    "docker",
    "kubernetes",
    "bash",
    "shell",
    "cron",
    "ssh",
    "networking",
    "dns",
    "firewall",
    "powershell",
    "vmware",
    "hyper-v",
    "sql-server",
    "mysql",
    "postgresql",
    "redis",
    "elasticsearch",
    "ansible",
    "puppet",
    "chef",
    "monitoring",
    "zabbix",
    "prometheus",
    "grafana",
    "active-directory",
    "exchange",
    "cisco",
    "routing",
    "subnet",
    "backup",
    "restore",
    "disk",
    "filesystem",
    "memory",
    "cpu",
    "performance",
    "logging",
    "syslog",
    "rsyslog",
    "ssl",
    "tls",
    "certificate",
    "iis",
    "tomcat",
    "java",
    "python",
    "perl",
)


def strip_html(raw: str) -> str:
    if not raw:
        return ""
    t = html_lib.unescape(raw)
    t = TAG_RE.sub(" ", t)
    t = WS_RE.sub(" ", t).strip()
    return t


def parse_tags(tags_attr: str) -> List[str]:
    if not tags_attr:
        return []
    t = html_lib.unescape(tags_attr)
    # 形如 <linux><nginx>
    parts = re.findall(r"<([^>]+)>", t)
    return [p.strip().lower() for p in parts if p.strip()]


def clip(s: str, max_len: int) -> str:
    s = s.strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


def solution_title_from_body(body: str, answer_id: str) -> str:
    plain = strip_html(body)
    if not plain:
        return f"SO-answer-{answer_id}"
    first = plain.split("\n", 1)[0].strip()
    if len(first) < 3:
        return f"SO-answer-{answer_id}"
    return clip(first, 200)


def build_answer_index(xml_path: Path) -> sqlite3.Connection:
    """第一遍扫描：仅索引 Answer（PostTypeId=2），供问题行关联 AcceptedAnswerId。"""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE ans (id INTEGER PRIMARY KEY, body TEXT, score INTEGER)")
    count = 0
    for _, elem in ET.iterparse(str(xml_path), events=("end",)):
        if elem.tag != "row":
            elem.clear()
            continue
        if elem.get("PostTypeId") != "2":
            elem.clear()
            continue
        aid = elem.get("Id")
        if not aid:
            elem.clear()
            continue
        try:
            iid = int(aid)
        except ValueError:
            elem.clear()
            continue
        body = elem.get("Body") or ""
        try:
            sc = int(elem.get("Score") or "0")
        except ValueError:
            sc = 0
        conn.execute("INSERT OR REPLACE INTO ans (id, body, score) VALUES (?,?,?)", (iid, body, sc))
        count += 1
        elem.clear()
    conn.commit()
    sys.stderr.write(f"[INFO] 已索引 {count} 条回答\n")
    return conn


def tag_filter_ok(tags: List[str], required_any: Optional[Set[str]]) -> bool:
    if not required_any:
        return True
    s = set(tags)
    return bool(s & required_any)


def iter_pairs_from_xml(
    xml_path: Path,
    conn: sqlite3.Connection,
    *,
    min_q_score: int,
    min_a_score: int,
    tags_any: Optional[Set[str]],
    limit: Optional[int],
) -> Iterator[Dict[str, Any]]:
    cur = conn.cursor()
    n = 0
    for _, elem in ET.iterparse(str(xml_path), events=("end",)):
        if elem.tag != "row":
            elem.clear()
            continue
        if elem.get("PostTypeId") != "1":
            elem.clear()
            continue
        acc = elem.get("AcceptedAnswerId")
        if not acc:
            elem.clear()
            continue
        try:
            qid = int(elem.get("Id") or "0")
            aid = int(acc)
        except ValueError:
            elem.clear()
            continue
        try:
            q_score = int(elem.get("Score") or "0")
        except ValueError:
            q_score = 0
        if q_score < min_q_score:
            elem.clear()
            continue
        title = strip_html(elem.get("Title") or "")
        if len(title) < 4:
            elem.clear()
            continue
        tags = parse_tags(elem.get("Tags") or "")
        if not tag_filter_ok(tags, tags_any):
            elem.clear()
            continue
        cur.execute("SELECT body, score FROM ans WHERE id=?", (aid,))
        row = cur.fetchone()
        if not row:
            elem.clear()
            continue
        body, a_score = row[0], int(row[1] or 0)
        if a_score < min_a_score:
            elem.clear()
            continue
        desc = strip_html(body)
        if len(desc) < 10:
            elem.clear()
            continue
        fault_name = clip(title, 200)
        sol_name = solution_title_from_body(body, str(aid))
        sol_name = clip(sol_name, 200)
        if len(sol_name) < 1:
            sol_name = f"SO-{aid}"
        record: Dict[str, Any] = {
            "fault_name": fault_name,
            "solution_name": sol_name,
            "solution_description": clip(desc, 2000),
            "question_id": qid,
            "answer_id": aid,
            "question_score": q_score,
            "answer_score": a_score,
            "tags": tags,
        }
        yield record
        n += 1
        if limit is not None and n >= limit:
            elem.clear()
            break
        elem.clear()
    sys.stderr.write(f"[INFO] 产出问答对 {n} 条（受 limit / 过滤条件约束）\n")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rows.append(json.loads(line))
    return rows


def post_graph_add(
    api_url: str,
    row: Dict[str, Any],
    *,
    data_source: str,
    confidence: float,
    batch_id: str,
    timeout: float,
) -> None:
    payload = {
        "fault_name": row["fault_name"],
        "solution_name": row["solution_name"],
        "solution_description": row.get("solution_description") or "",
        "steps": "",
        "domain": ",".join(row.get("tags") or [])[:200],
        "data_source": data_source,
        "confidence": confidence,
        "import_batch_id": batch_id,
    }
    r = requests.post(f"{api_url.rstrip('/')}/graph/add", json=payload, timeout=timeout)
    r.raise_for_status()


def main() -> None:
    p = argparse.ArgumentParser(description="Stack Overflow / ServerFault Posts.xml 清洗与导入")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--posts-xml", type=Path, help="Stack Exchange Posts.xml 路径")
    src.add_argument("--from-jsonl", type=Path, help="已清洗的 JSONL（fault_name/solution_name/solution_description）")
    p.add_argument("--out-jsonl", type=Path, default=None, help="写出清洗结果 JSONL")
    p.add_argument("--api-url", default="", help="graph-api 根 URL，设置则写入图谱（如 http://localhost:8021）")
    p.add_argument("--dry-run", action="store_true", help="仅解析统计，不写文件、不调 API")
    p.add_argument("--limit", type=int, default=5000, help="最多导入问答对（默认 5000）")
    p.add_argument("--min-question-score", type=int, default=0)
    p.add_argument("--min-answer-score", type=int, default=1, help="接受答案最低分数（默认 1，过滤低质回答）")
    p.add_argument(
        "--tags-any",
        default=",".join(DEFAULT_TAGS_ANY),
        help="逗号分隔标签子串，问题标签任一匹配即保留；设为空字符串等同 --no-tag-filter",
    )
    p.add_argument("--no-tag-filter", action="store_true", help="不按标签过滤（仍要求有采纳答案）")
    p.add_argument("--source-tag", default="stackoverflow", help="写入图谱的 data_source")
    p.add_argument("--confidence", type=float, default=0.6, help="公开数据建议 0.6（PRD 原始公开源）")
    p.add_argument("--batch-id", default="", help="import_batch_id，默认自动生成")
    p.add_argument("--delay", type=float, default=0.05, help="每条 API 间隔秒数")
    p.add_argument("--timeout", type=float, default=30.0, help="HTTP 超时")
    args = p.parse_args()

    batch_id = args.batch_id or f"so-{time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    tags_any: Optional[Set[str]] = None
    if not args.no_tag_filter:
        if args.tags_any.strip():
            tags_any = {t.strip().lower() for t in args.tags_any.split(",") if t.strip()}

    records: List[Dict[str, Any]] = []

    if args.from_jsonl:
        records = read_jsonl(args.from_jsonl)
        sys.stderr.write(f"[INFO] 从 JSONL 读取 {len(records)} 条\n")
    else:
        xml_path = args.posts_xml
        if not xml_path.exists():
            print(f"[ERROR] 文件不存在：{xml_path}", file=sys.stderr)
            sys.exit(1)
        sys.stderr.write(f"[INFO] 第一遍扫描（索引回答）…\n")
        conn = build_answer_index(xml_path)
        try:
            sys.stderr.write(f"[INFO] 第二遍扫描（抽取问答对）…\n")
            records = list(
                iter_pairs_from_xml(
                    xml_path,
                    conn,
                    min_q_score=args.min_question_score,
                    min_a_score=args.min_answer_score,
                    tags_any=tags_any,
                    limit=args.limit,
                )
            )
        finally:
            conn.close()

    if args.dry_run:
        print(f"[DRY-RUN] 共 {len(records)} 条，batch_id={batch_id}")
        for r in records[:5]:
            print(json.dumps(r, ensure_ascii=False)[:500])
        return

    if args.out_jsonl:
        args.out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with args.out_jsonl.open("w", encoding="utf-8") as f:
            for r in records:
                # JSONL 仅保留 import_v2 可识别字段 + 元数据
                out = {
                    "fault_name": r["fault_name"],
                    "solution_name": r["solution_name"],
                    "solution_description": r["solution_description"],
                    "question_id": r.get("question_id"),
                    "answer_id": r.get("answer_id"),
                    "tags": r.get("tags"),
                }
                f.write(json.dumps(out, ensure_ascii=False) + "\n")
        sys.stderr.write(f"[INFO] 已写入 {args.out_jsonl}（{len(records)} 行）\n")

    if args.api_url:
        ok, fail = 0, 0
        t0 = time.time()
        for i, r in enumerate(records, 1):
            try:
                post_graph_add(
                    args.api_url,
                    r,
                    data_source=args.source_tag,
                    confidence=args.confidence,
                    batch_id=batch_id,
                    timeout=args.timeout,
                )
                ok += 1
            except Exception as e:
                fail += 1
                print(f"[WARN] {i}/{len(records)} {r.get('fault_name', '')[:40]} -> {e}", file=sys.stderr)
            if args.delay > 0:
                time.sleep(args.delay)
            if i % 50 == 0:
                sys.stderr.write(f"[INFO] 已提交 {i}/{len(records)} …\n")
        sys.stderr.write(
            f"[DONE] API 导入 batch_id={batch_id} 成功 {ok} 失败 {fail} 耗时 {time.time()-t0:.1f}s\n"
        )
        if fail > 0:
            sys.exit(1)
    elif not args.out_jsonl:
        print("[ERROR] 请指定 --out-jsonl 和/或 --api-url", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
