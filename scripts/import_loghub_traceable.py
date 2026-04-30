#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LogHub 可追溯导入脚本（open dataset traceable import）

功能：
1) 从本地 LogHub 原始日志逐行匹配异常模式
2) 生成可追溯 JSONL（包含 source_file / line_no / pattern）
3) 导入 graph-api（/graph/add）
4) 产出导入报告（Markdown）

用法：
  python scripts/import_loghub_traceable.py --raw-dir data/loghub/raw --api-url http://localhost:8021
  python scripts/import_loghub_traceable.py --raw-dir data/loghub/raw --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Pattern, Tuple

import requests


@dataclass(frozen=True)
class FaultRule:
    name: str
    pattern: Pattern[str]
    solution: str
    description: str
    steps: str
    domain: str


RULES: List[FaultRule] = [
    # ── HDFS（来源：HDFS_2k.log） ──────────────────────────────────────────
    # 真实日志样例：
    #   081109 214043 2561 WARN dfs.DataNode$DataXceiver: 10.251.30.85:50010:
    #   Got exception while serving blk_-2918118818249673980 to /10.251.90.64:
    FaultRule(
        name="HDFS DataNode 数据块传输异常（DataXceiver Exception）",
        pattern=re.compile(r"Got exception while serving blk_", re.I),
        solution="重启异常 DataNode 并检查数据块副本完整性",
        description=(
            "DataNode DataXceiver 在向客户端传输数据块时抛出异常，"
            "日志关键字：Got exception while serving blk_<block_id>。"
            "常见原因：网络抖动、DataNode 磁盘 I/O 错误或客户端提前断开连接。"
        ),
        steps=(
            "1. 查看 DataNode 日志确认异常栈类型（IOException / SocketTimeoutException）\n"
            "2. 检查对应节点磁盘：smartctl -a /dev/sdX\n"
            "3. hdfs fsck / 检查是否存在 corrupt block\n"
            "4. 若副本数不足，等待 NameNode 自动补副本（或手动 hdfs dfsadmin -report）\n"
            "5. 对高频出现的节点考虑下线并更换磁盘"
        ),
        domain="Storage",
    ),

    # ── Hadoop / YARN（来源：Hadoop_2k.log） ──────────────────────────────
    # 真实日志样例：
    #   TaskAttempt Transitioned from NEW to UNASSIGNED（正常状态流转）
    #   container_1445144423722_0020_01_000002 assigned to attempt_...
    # Hadoop_2k.log 以 INFO 为主，捕获 TaskAttempt 转入失败态
    FaultRule(
        name="Hadoop MapReduce Task 重试超限（Task Attempt Failed）",
        pattern=re.compile(
            r"TaskAttempt Transitioned from \w+ to (FAIL|KILLED)|"
            r"attempt_\S+ failed|task.*failed.*attempt",
            re.I,
        ),
        solution="增大 mapreduce.task.maxattempts 并排查数据倾斜",
        description=(
            "MapReduce TaskAttempt 状态转移到 FAIL/KILLED，说明任务多次重试后仍失败。"
            "日志关键字：TaskAttempt Transitioned from * to FAIL。"
            "常见原因：OOM、磁盘满、数据倾斜或节点网络问题。"
        ),
        steps=(
            "1. YARN UI 找到失败 attempt，查看 Container 日志\n"
            "2. 检查是否为 OOM（exit code 137）或磁盘满\n"
            "3. 增大内存：mapreduce.map.memory.mb / mapreduce.reduce.memory.mb\n"
            "4. 开启 Speculative Execution 对抗慢节点\n"
            "5. 使用 Combiner 减少数据量，分析输入数据是否存在倾斜"
        ),
        domain="Middleware",
    ),

    # ── Linux（来源：Linux_2k.log） ────────────────────────────────────────
    # 真实日志样例：
    #   Jun 14 15:16:01 combo sshd(pam_unix)[19939]: authentication failure;
    #   logname= uid=0 euid=0 tty=NODEVssh ruser= rhost=218.188.2.4
    FaultRule(
        name="SSH 暴力破解攻击（Brute Force Authentication Failure）",
        pattern=re.compile(r"authentication failure.*rhost=|pam_unix.*auth.*fail", re.I),
        solution="封禁攻击来源 IP 并部署 fail2ban",
        description=(
            "sshd pam_unix 记录大量来自同一外网 IP 的认证失败，"
            "日志关键字：authentication failure; logname= ... rhost=<ip>。"
            "典型场景：来自互联网的 SSH 暴力破解，尝试枚举弱密码账号。"
        ),
        steps=(
            "1. 统计高频 rhost IP：grep 'authentication failure' auth.log | awk '{print $NF}' | sort | uniq -c | sort -rn\n"
            "2. 即时封禁：iptables -A INPUT -s <攻击IP> -j DROP\n"
            "3. 部署 fail2ban：配置 maxretry=5, bantime=3600\n"
            "4. 禁止 root 直接登录：PermitRootLogin no（/etc/ssh/sshd_config）\n"
            "5. 强制密钥认证并关闭密码登录：PasswordAuthentication no"
        ),
        domain="Security",
    ),
    # 真实日志样例（Linux_2k.log 中也有）：
    #   Jun 14 ... combo sshd(pam_unix)[19937]: check pass; user unknown
    FaultRule(
        name="SSH 无效用户登录（Unknown User Login Attempt）",
        pattern=re.compile(r"sshd.*invalid user|check pass.*user unknown", re.I),
        solution="过滤无效用户尝试并加固 SSH 用户白名单",
        description=(
            "sshd 记录到攻击者尝试以不存在的用户名登录，"
            "日志关键字：invalid user / check pass; user unknown。"
        ),
        steps=(
            "1. 查看日志确认枚举的用户名列表\n"
            "2. 配置 AllowUsers 白名单（/etc/ssh/sshd_config）\n"
            "3. 使用 fail2ban 自动封禁：配置 sshd jail\n"
            "4. 定期审计 /etc/passwd 删除无用账户\n"
            "5. 更换非标准 SSH 端口（Port 2222）降低扫描命中率"
        ),
        domain="Security",
    ),

    # ── Zookeeper（来源：Zookeeper_2k.log） ───────────────────────────────
    # 真实日志样例：
    #   2015-07-29 19:04:29,071 - WARN [SendWorker:188978561024:...@688]
    #   - Send worker leaving thread
    FaultRule(
        name="ZooKeeper SendWorker 线程退出（SendWorker Leaving Thread）",
        pattern=re.compile(r"Send worker leaving thread", re.I),
        solution="排查节点间网络连通性并重启 ZooKeeper 进程",
        description=(
            "ZooKeeper QuorumCnxManager 的 SendWorker 线程意外退出，"
            "日志关键字：Send worker leaving thread。"
            "通常表示与某个 peer 节点之间的 TCP 连接断开，可能触发 Leader 重选举。"
        ),
        steps=(
            "1. 检查 ZooKeeper 节点间网络：ping / telnet <peer>:3888\n"
            "2. 查看是否有 GC 停顿导致心跳超时：jstat -gcutil <pid>\n"
            "3. 检查防火墙是否封锁了 2888/3888 端口\n"
            "4. 若多节点同时出现，验证 quorum 状态：echo ruok | nc localhost 2181\n"
            "5. 重启问题节点 ZooKeeper 进程，观察选举是否恢复"
        ),
        domain="Middleware",
    ),
    # 真实日志样例：
    #   WARN [RecvWorker:188978561024:...@762]
    #   - Connection broken for id 188978561024, my id = 1, error =
    FaultRule(
        name="ZooKeeper Peer 连接中断（Connection Broken）",
        pattern=re.compile(r"Connection broken for id \d+", re.I),
        solution="修复节点间网络并调整 ZooKeeper 超时配置",
        description=(
            "ZooKeeper RecvWorker 检测到与 peer 节点的连接中断，"
            "日志关键字：Connection broken for id <peer_id>。"
            "持续中断可能导致集群 quorum 丢失，写操作挂起。"
        ),
        steps=(
            "1. 确认对端节点是否存活：echo stat | nc <peer_ip> 2181\n"
            "2. 检查 Zookeeper initLimit / syncLimit 是否过小\n"
            "3. 使用 ss -t 查看 TCP 连接状态，排除 TIME_WAIT 积压\n"
            "4. 调大 tickTime（如 4000）给网络抖动留更多余量\n"
            "5. 若节点频繁宕机，检查硬件健康状态"
        ),
        domain="Middleware",
    ),

    # ── Apache（来源：Apache_2k.log） ─────────────────────────────────────
    # 真实日志样例：
    #   [Sun Dec 04 04:47:44 2005] [error] mod_jk child workerEnv in error state 6
    FaultRule(
        name="Apache mod_jk Worker 进入错误状态（mod_jk Error State）",
        pattern=re.compile(r"mod_jk child workerEnv in error state", re.I),
        solution="重启 Tomcat 后端并检查 mod_jk AJP 连接配置",
        description=(
            "Apache mod_jk 报告后端 Tomcat worker 进入 error state，"
            "日志关键字：mod_jk child workerEnv in error state <N>。"
            "通常因为后端 Tomcat 进程崩溃、AJP 端口不可达或连接数耗尽。"
        ),
        steps=(
            "1. 检查 Tomcat 是否存活：ps aux | grep tomcat\n"
            "2. 查看 Tomcat catalina.out 日志定位崩溃原因\n"
            "3. 验证 AJP 端口（默认 8009）是否可达：telnet <tomcat_host> 8009\n"
            "4. 检查 workers.properties 中 connection_pool_size / socket_timeout 配置\n"
            "5. 重启 Tomcat 并观察 mod_jk 状态页是否恢复绿色"
        ),
        domain="Middleware",
    ),
]


def iter_log_files(raw_dir: Path) -> List[Path]:
    exts = {".log", ".txt", ".out"}
    return sorted(
        [p for p in raw_dir.rglob("*") if p.is_file() and p.suffix.lower() in exts]
    )


def extract_records(raw_dir: Path, batch_id: str, source: str) -> Tuple[List[Dict], Dict[str, int]]:
    records: List[Dict] = []
    stats = {"files": 0, "lines": 0, "matches": 0}
    files = iter_log_files(raw_dir)
    stats["files"] = len(files)

    for fp in files:
        rel = fp.as_posix().replace(raw_dir.as_posix() + "/", "")
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
        except Exception:
            text = fp.read_text(encoding="latin-1", errors="replace")
        for line_no, line in enumerate(text.splitlines(), 1):
            stats["lines"] += 1
            stripped = line.strip()
            if not stripped:
                continue
            for rule in RULES:
                if not rule.pattern.search(stripped):
                    continue
                stats["matches"] += 1
                trace = f"[source:{rel}:{line_no}] [pattern:{rule.pattern.pattern}]"
                records.append(
                    {
                        "fault_name": rule.name,
                        "solution_name": rule.solution,
                        "solution_description": f"{rule.description} {trace}",
                        "steps": rule.steps,
                        "domain": rule.domain,
                        "data_source": source,
                        "confidence": 0.8,
                        "import_batch_id": batch_id,
                        "source_file": rel,
                        "source_line": line_no,
                        "matched_line": stripped[:500],
                        "matched_pattern": rule.pattern.pattern,
                    }
                )
                break
    return records, stats


def write_jsonl(path: Path, rows: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def import_rows(api_url: str, rows: List[Dict], delay: float) -> Tuple[int, int]:
    success = 0
    failed = 0
    total = len(rows)
    for i, row in enumerate(rows, 1):
        payload = {
            "fault_name": row["fault_name"],
            "solution_name": row["solution_name"],
            "solution_description": row["solution_description"],
            "steps": row["steps"],
            "domain": row["domain"],
            "data_source": row["data_source"],
            "confidence": row["confidence"],
            "import_batch_id": row["import_batch_id"],
        }
        try:
            resp = requests.post(f"{api_url.rstrip('/')}/graph/add", json=payload, timeout=15)
            resp.raise_for_status()
            success += 1
        except Exception:
            failed += 1
        if i % 50 == 0 or i == total:
            print(f"[{i}/{total}] success={success}, failed={failed}")
        if delay > 0:
            time.sleep(delay)
    return success, failed


def write_report(path: Path, *, batch_id: str, raw_dir: Path, out_file: Path, stats: Dict[str, int], rows: List[Dict], success: int, failed: int) -> None:
    unique_sources = len({(r["source_file"], r["source_line"]) for r in rows})
    by_fault: Dict[str, int] = {}
    for r in rows:
        by_fault[r["fault_name"]] = by_fault.get(r["fault_name"], 0) + 1
    top_faults = sorted(by_fault.items(), key=lambda x: x[1], reverse=True)[:10]

    lines = [
        "# DATA_IMPORT_REPORT_V2 (LogHub Traceable)",
        "",
        f"- batch_id: `{batch_id}`",
        f"- raw_dir: `{raw_dir.as_posix()}`",
        f"- output_jsonl: `{out_file.as_posix()}`",
        "",
        "## Summary",
        f"- scanned_files: {stats['files']}",
        f"- scanned_lines: {stats['lines']}",
        f"- matched_lines: {stats['matches']}",
        f"- extracted_records: {len(rows)}",
        f"- unique_trace_points: {unique_sources}",
        f"- import_success: {success}",
        f"- import_failed: {failed}",
        "",
        "## Top Faults",
    ]
    for name, cnt in top_faults:
        lines.append(f"- {name}: {cnt}")
    lines += ["", "## Sample Trace (first 10)", ""]
    for row in rows[:10]:
        lines.append(
            f"- `{row['fault_name']}` <= `{row['source_file']}:{row['source_line']}` | pattern=`{row['matched_pattern']}`"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="LogHub 可追溯导入脚本")
    parser.add_argument("--raw-dir", required=True, help="LogHub 原始日志目录（本地）")
    parser.add_argument("--api-url", default="http://localhost:8021", help="graph-api URL")
    parser.add_argument("--source", default="logHub", help="data_source 值")
    parser.add_argument("--batch-id", default=f"loghub-trace-{int(time.time())}", help="导入批次 ID")
    parser.add_argument("--out-file", default="data/loghub_traceable_faults.jsonl", help="提取结果输出文件")
    parser.add_argument("--report-file", default="DATA_IMPORT_REPORT_V2.md", help="导入报告路径")
    parser.add_argument("--delay", type=float, default=0.01, help="每条导入延迟秒")
    parser.add_argument("--dry-run", action="store_true", help="只提取，不入库")
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    if not raw_dir.exists():
        print(f"[ERROR] raw-dir 不存在: {raw_dir}")
        sys.exit(1)

    rows, stats = extract_records(raw_dir, args.batch_id, args.source)
    out_file = Path(args.out_file)
    write_jsonl(out_file, rows)
    print(f"[INFO] extracted={len(rows)} from files={stats['files']}, lines={stats['lines']}")
    print(f"[INFO] jsonl => {out_file}")

    success = 0
    failed = 0
    if not args.dry_run and rows:
        success, failed = import_rows(args.api_url, rows, args.delay)
        print(f"[INFO] import done: success={success}, failed={failed}")

    report_file = Path(args.report_file)
    write_report(
        report_file,
        batch_id=args.batch_id,
        raw_dir=raw_dir,
        out_file=out_file,
        stats=stats,
        rows=rows,
        success=success,
        failed=failed,
    )
    print(f"[INFO] report => {report_file}")

    if not rows:
        print("[WARN] 未匹配到任何异常模式，请补充规则或确认原始日志内容。")
        sys.exit(2)
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

