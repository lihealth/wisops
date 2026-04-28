# -*- coding: utf-8 -*-
"""
WisOps V2.0 - GAIA Dataset Parser & Importer
Source: https://github.com/CloudWise-OpenSource/GAIA-DataSet

Usage:
  python scripts/parse_gaia.py --api-url http://localhost:8002

Imports:
  data/gaia/run.zip  -> Asset nodes (MicroSS services) + Alert nodes
  data/gaia/log.zip  -> Fault + Solution nodes (from error.csv patterns)
"""
import sys, os
# Force UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import argparse, csv, re, time, zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests

ROOT    = Path(__file__).parent.parent
GAIA    = ROOT / "data" / "gaia"
RUN_ZIP = GAIA / "run.zip"
LOG_ZIP = GAIA / "log.zip"
API_URL = "http://localhost:8002"
SOURCE  = "gaia"
BATCH   = "gaia-2026-04-28"

# ---------------------------------------------------------------------------
# Error pattern -> (fault_name, fault_desc, solution_name, steps, domain)
# ---------------------------------------------------------------------------
PATTERNS: List[Tuple] = [
    (
        re.compile(r"connect.*?fail|connection refused|111.*Connection refused", re.I),
        "\u670d\u52a1\u8fde\u63a5\u88ab\u62d2\u7edd\uff08Connection Refused\uff09",
        "\u4e0a\u6e38\u670d\u52a1\u4e0d\u53ef\u8fbe\uff0cconnect() \u8fd4\u56de errno 111",
        "\u6392\u67e5 Connection Refused \u6839\u56e0\u5e76\u6062\u590d\u670d\u52a1",
        "1.\u786e\u8ba4\u76ee\u6807\u670d\u52a1\u8fdb\u7a0b\u662f\u5426\u8fd0\u884c\n"
        "2.\u68c0\u67e5\u7aef\u53e3\u76d1\u542c\uff1ass -tlnp | grep <port>\n"
        "3.\u786e\u8ba4\u9632\u706b\u5899\u89c4\u5219\uff1aiptables -L\n"
        "4.\u67e5\u770b\u76ee\u6807\u670d\u52a1\u9519\u8bef\u65e5\u5fd7\u5b9a\u4f4d\u542f\u52a8\u5931\u8d25\u539f\u56e0\n"
        "5.\u91cd\u542f\u670d\u52a1\u5e76\u89c2\u5bdf",
        "Application",
    ),
    (
        re.compile(r"no space left|disk full|write.*failed.*28|filesystem.*full", re.I),
        "\u78c1\u76d8\u7a7a\u95f4\u8017\u5c3d\uff08No Space Left on Device\uff09",
        "\u78c1\u76d8\u5199\u5165\u5931\u8d25\uff0cerrno 28\uff0c\u65e5\u5fd7/\u6570\u636e\u6587\u4ef6\u6301\u7eed\u5199\u5165\u5bfc\u81f4\u78c1\u76d8\u6ee1",
        "\u6e05\u7406\u78c1\u76d8\u7a7a\u95f4\u5e76\u914d\u7f6e\u5bb9\u91cf\u544a\u8b66",
        "1.df -h \u67e5\u770b\u5404\u6302\u8f7d\u70b9\u4f7f\u7528\u7387\n"
        "2.du -sh /data/logs/* \u5b9a\u4f4d\u5927\u76ee\u5f55\n"
        "3.\u6e05\u7406\u8fc7\u671f\u65e5\u5fd7\uff1afind /logs -mtime +30 -delete\n"
        "4.\u914d\u7f6e logrotate \u81ea\u52a8\u8f6e\u8f6c\n"
        "5.\u8bbe\u7f6e\u78c1\u76d8\u4f7f\u7528\u7387 >80% \u544a\u8b66",
        "Storage",
    ),
    (
        re.compile(r"authentication failure|auth.*failed|pam_unix.*auth", re.I),
        "SSH \u8ba4\u8bc1\u5931\u8d25\uff08\u66b4\u529b\u7834\u89e3\u98ce\u9669\uff09",
        "sshd \u8bb0\u5f55\u5927\u91cf\u8ba4\u8bc1\u5931\u8d25\uff0c\u53ef\u80fd\u5b58\u5728\u66b4\u529b\u7834\u89e3\u653b\u51fb",
        "\u5c01\u7981\u653b\u51fb IP \u5e76\u52a0\u56fa SSH \u8ba4\u8bc1",
        "1.fail2ban \u5206\u6790 auth.log \u5e76\u81ea\u52a8\u5c01\u7981\n"
        "2.iptables \u624b\u52a8\u5c01\u7981\u9ad8\u9891\u5931\u8d25 IP\n"
        "3.\u7981\u7528\u5bc6\u7801\u8ba4\u8bc1: PasswordAuthentication no\n"
        "4.\u4ec5\u5141\u8bb8\u516c\u9470\u767b\u5f55\n"
        "5.\u4fee\u6539 SSH \u9ed8\u8ba4\u7aef\u53e3",
        "Security",
    ),
    (
        re.compile(r"leader election|replica.*leader|preferred.*leader", re.I),
        "Kafka \u526f\u672c Leader \u9009\u4e3e\u5931\u8d25",
        "Kafka \u5206\u533a preferred leader election \u5931\u8d25\uff0c\u53ef\u80fd\u5bfc\u81f4\u5206\u533a\u8d1f\u8f7d\u4e0d\u5747\u8861",
        "\u4fee\u590d Kafka Leader \u9009\u4e3e\u5f02\u5e38",
        "1.kafka-topics.sh --describe \u67e5\u770b\u5206\u533a ISR \u72b6\u6001\n"
        "2.\u786e\u8ba4 Broker \u95f4\u7f51\u7edc\u8fde\u901a\u6027\n"
        "3.kafka-preferred-replica-election.sh \u624b\u52a8\u89e6\u53d1\u9009\u4e3e\n"
        "4.\u68c0\u67e5 ZooKeeper \u8fde\u63a5\u72b6\u6001\n"
        "5.\u91cd\u542f\u5f02\u5e38 Broker \u8282\u70b9",
        "Middleware",
    ),
    (
        re.compile(r"table.*already exists|duplicate.*table", re.I),
        "\u6570\u636e\u5e93\u8868\u91cd\u590d\u521b\u5efa\u5f02\u5e38",
        "\u6267\u884c CREATE TABLE \u65f6\u76ee\u6807\u8868\u5df2\u5b58\u5728\uff0c\u672a\u4f7f\u7528 IF NOT EXISTS \u4fdd\u62a4",
        "\u4fee\u590d\u5efa\u8868\u8bed\u53e5\u6dfb\u52a0\u5e42\u7b49\u4fdd\u62a4",
        "1.\u6240\u6709 CREATE TABLE \u6dfb\u52a0 IF NOT EXISTS\n"
        "2.ClickHouse: CREATE TABLE IF NOT EXISTS\n"
        "3.\u68c0\u67e5\u521d\u59cb\u5316\u811a\u672c\u5e42\u7b49\u6027\n"
        "4.CI \u6d41\u7a0b\u4e2d\u589e\u52a0 schema \u53d8\u66f4\u6821\u9a8c",
        "Database",
    ),
    (
        re.compile(r"invalid.*configuration.*server|only one server.*zookeeper", re.I),
        "ZooKeeper \u96c6\u7fa4\u914d\u7f6e\u4e0d\u5408\u6cd5",
        "ZooKeeper \u914d\u7f6e\u4e2d\u53ea\u6709\u4e00\u4e2a\u8282\u70b9\uff0c\u65e0\u6cd5\u5f62\u6210\u591a\u6570\u6d3e",
        "\u4fee\u590d ZooKeeper ensemble \u914d\u7f6e",
        "1.\u68c0\u67e5 zoo.cfg \u4e2d server.N \u914d\u7f6e\u9879\n"
        "2.\u786e\u4fdd\u81f3\u5c11\u914d\u7f6e 3 \u4e2a\u8282\u70b9\uff08\u5947\u6570\uff09\n"
        "3.\u786e\u8ba4\u5404\u8282\u70b9 dataDir \u4e2d myid \u6587\u4ef6\u6b63\u786e\n"
        "4.\u91cd\u542f ZooKeeper \u96c6\u7fa4\n"
        "5.zkCli.sh ls / \u9a8c\u8bc1\u8fde\u63a5",
        "Middleware",
    ),
    (
        re.compile(r"operation timeout|connection.*timeout|timed out", re.I),
        "\u670d\u52a1\u8c03\u7528\u8d85\u65f6",
        "RPC/HTTP \u8c03\u7528\u8d85\u65f6\uff0c\u53ef\u80fd\u7531\u4e0b\u6e38\u670d\u52a1\u54cd\u5e94\u6162\u3001\u7f51\u7edc\u62e5\u585e\u6216\u8d44\u6e90\u8017\u5c3d",
        "\u6392\u67e5\u8c03\u7528\u94fe\u8d85\u65f6\u5e76\u4f18\u5316",
        "1.\u94fe\u8def\u8ffd\u8e2a\u5b9a\u4f4d\u8d85\u65f6\u53d1\u751f\u7684\u5177\u4f53 span\n"
        "2.\u68c0\u67e5\u4e0b\u6e38\u670d\u52a1 CPU/\u5185\u5b58/\u8fde\u63a5\u6c60\u72b6\u6001\n"
        "3.\u9002\u5f53\u589e\u52a0\u8d85\u65f6\u9600\u5024\uff08\u77ed\u671f\u7f13\u89e3\uff09\n"
        "4.\u4e32\u884c\u8c03\u7528\u6539\u5e76\u884c\uff0c\u51cf\u5c11\u5173\u952e\u8def\u5f84\u8017\u65f6\n"
        "5.\u5bf9\u6162\u4f9d\u8d56\u914d\u7f6e\u7194\u65ad\u964d\u7ea7",
        "Application",
    ),
    (
        re.compile(r"memory.*limit|out of memory|exceeding memory", re.I),
        "\u5bb9\u5668/\u8fdb\u7a0b\u5185\u5b58\u8d85\u9650\uff08OOM\uff09",
        "\u8fdb\u7a0b\u5185\u5b58\u4f7f\u7528\u8d85\u8fc7\u9650\u5236\uff0c\u88ab OOM Killer \u7ec8\u6b62",
        "\u5b9a\u4f4d\u5185\u5b58\u6cc4\u6f0f\u5e76\u8c03\u6574\u5185\u5b58\u9650\u5236",
        "1.kubectl describe pod \u67e5\u770b OOMKilled \u72b6\u6001\n"
        "2.\u5206\u6790 heap dump\n"
        "3.MAT \u5de5\u5177\u5b9a\u4f4d\u6cc4\u6f0f\u5bf9\u8c61\n"
        "4.\u4fee\u590d\u4ee3\u7801\u4e2d\u7f13\u5b58\u672a\u8bbe TTL \u6216\u8fde\u63a5\u672a\u5173\u95ed\n"
        "5.\u4e34\u65f6\u589e\u52a0\u5185\u5b58 limit \u7f13\u89e3",
        "Kubernetes",
    ),
    (
        re.compile(r"connection reset|read.*socket.*fail|broken pipe", re.I),
        "\u7f51\u7edc\u8fde\u63a5\u88ab\u610f\u5916\u91cd\u7f6e\uff08Connection Reset\uff09",
        "TCP \u8fde\u63a5\u88ab\u5bf9\u7aef\u5f3a\u5236\u5173\u95ed\uff0c\u6536\u5230 RST \u5305",
        "\u6392\u67e5\u8fde\u63a5\u91cd\u7f6e\u6839\u56e0",
        "1.\u6293\u5305\u786e\u8ba4 RST \u6765\u6e90\n"
        "2.\u68c0\u67e5\u8d1f\u8f7d\u5747\u8861\u8d85\u65f6\u914d\u7f6e\n"
        "3.\u6392\u67e5\u670d\u52a1\u7aef\u662f\u5426\u5b58\u5728 panic/crash\n"
        "4.\u589e\u5927 TCP keepalive \u53c2\u6570\n"
        "5.\u68c0\u67e5\u53cd\u5411\u4ee3\u7406 keepalive \u914d\u7f6e\u4e00\u81f4\u6027",
        "Network",
    ),
    (
        re.compile(r"unable to load database|zookeeper.*unable.*load", re.I),
        "ZooKeeper \u6570\u636e\u76ee\u5f55\u635f\u574f\u65e0\u6cd5\u52a0\u8f7d",
        "ZooKeeper \u542f\u52a8\u65f6\u65e0\u6cd5\u52a0\u8f7d\u78c1\u76d8\u6570\u636e\uff0c\u53ef\u80fd\u7531\u975e\u6b63\u5e38\u5173\u673a\u5bfc\u81f4\u4e8b\u52a1\u65e5\u5fd7\u635f\u574f",
        "\u4fee\u590d\u6216\u91cd\u5efa ZooKeeper \u6570\u636e\u76ee\u5f55",
        "1.\u68c0\u67e5 dataDir \u76ee\u5f55\u6743\u9650\u548c\u78c1\u76d8\u5065\u5eb7\n"
        "2.\u5220\u9664\u635f\u574f\u7684 transaction log\uff08\u8c28\u614e\uff09\n"
        "3.\u4ece\u6700\u65b0\u5feb\u7167\u6062\u590d\n"
        "4.\u91cd\u65b0\u521d\u59cb\u5316 ZooKeeper \u5e76\u91cd\u65b0\u540c\u6b65\u6570\u636e\n"
        "5.\u90e8\u7f72\u591a\u8282\u70b9 ZK \u51cf\u5c11\u5355\u70b9\u98ce\u9669",
        "Database",
    ),
    (
        re.compile(r"lock wait timeout|lock.*timeout.*exceed|deadlock", re.I),
        "\u6570\u636e\u5e93\u9501\u7b49\u5f85\u8d85\u65f6",
        "\u4e8b\u52a1\u9501\u7b49\u5f85\u65f6\u95f4\u8d85\u8fc7\u9600\u5024\uff0c\u901a\u5e38\u7531\u957f\u4e8b\u52a1\u6301\u9501\u6216\u5927\u91cf\u5e76\u53d1\u5199\u5165\u540c\u4e00\u884c\u5f15\u8d77",
        "\u7ec8\u6b62\u963b\u585e\u4e8b\u52a1\u5e76\u4f18\u5316\u9501\u4e89\u7528",
        "1.show engine innodb status \u67e5\u770b\u9501\u7b49\u5f85\u94fe\n"
        "2.kill \u6301\u9501\u6700\u4e45\u7684\u7ebf\u7a0b\n"
        "3.\u62c6\u5206\u5927\u4e8b\u52a1\u4e3a\u5c0f\u6279\u91cf\u63d0\u4ea4\n"
        "4.\u70ed\u70b9\u884c\u4f7f\u7528\u4e50\u89c2\u9501\u6216 Redis \u5206\u5e03\u5f0f\u9501\n"
        "5.DDL \u64cd\u4f5c\u5728\u4e1a\u52a1\u4f4e\u5cf0\u671f\u6267\u884c",
        "Database",
    ),
    (
        re.compile(r"permission denied|access.*denied|operation not permitted", re.I),
        "\u6587\u4ef6/\u76ee\u5f55\u6743\u9650\u4e0d\u8db3",
        "\u8fdb\u7a0b\u5c1d\u8bd5\u8bfb\u5199\u6587\u4ef6\u4f46\u6743\u9650\u4e0d\u8db3\uff0c\u5e38\u89c1\u4e8e\u65e5\u5fd7\u76ee\u5f55\u3001\u6570\u636e\u76ee\u5f55\u6743\u9650\u914d\u7f6e\u9519\u8bef",
        "\u4fee\u590d\u6587\u4ef6/\u76ee\u5f55\u6743\u9650\u914d\u7f6e",
        "1.ls -la \u786e\u8ba4\u6587\u4ef6\u6743\u9650\u548c\u6240\u6709\u8005\n"
        "2.chown -R <user>:<group> <dir>\n"
        "3.chmod 755 <dir> \u6216 chmod 644 <file>\n"
        "4.\u68c0\u67e5 SELinux/AppArmor \u7b56\u7565\u662f\u5426\u62e6\u622a\n"
        "5.\u68c0\u67e5 Docker \u5bb9\u5668 volume \u6302\u8f7d\u6743\u9650",
        "Security",
    ),
    (
        re.compile(r"too many connections|connection.*pool.*exhaust|no available.*connection", re.I),
        "\u6570\u636e\u5e93\u8fde\u63a5\u6c60\u8017\u5c3d",
        "\u8fde\u63a5\u6c60\u4e2d\u6240\u6709\u8fde\u63a5\u5747\u88ab\u5360\u7528\uff0c\u65b0\u8bf7\u6c42\u7b49\u5f85\u8d85\u65f6",
        "\u6269\u5bb9\u8fde\u63a5\u6c60\u5e76\u6392\u67e5\u8fde\u63a5\u6cc4\u6f0f",
        "1.show processlist \u67e5\u770b\u5f53\u524d\u8fde\u63a5\u72b6\u6001\n"
        "2.\u5b9a\u4f4d\u957f\u65f6\u95f4 Sleep \u7684\u8fde\u63a5\uff08\u6cc4\u6f0f\uff09\n"
        "3.\u4e34\u65f6\u589e\u5927 max_connections\n"
        "4.\u5f15\u5165\u8fde\u63a5\u6c60\u4e2d\u95f4\u4ef6\uff08PgBouncer/ProxySQL\uff09\n"
        "5.\u786e\u4fdd\u4ee3\u7801\u4e2d\u4f7f\u7528 try-with-resources \u5173\u95ed\u8fde\u63a5",
        "Database",
    ),
    (
        re.compile(r"overcommit_memory|vm\.overcommit|background save.*fail", re.I),
        "Redis \u5185\u5b58\u8fc7\u5ea6\u63d0\u4ea4\u914d\u7f6e\u8b66\u544a",
        "Linux \u5185\u6838 overcommit_memory=0 \u53ef\u80fd\u5bfc\u81f4 Redis BGSAVE \u5931\u8d25",
        "\u914d\u7f6e Linux \u5185\u6838\u5185\u5b58\u8fc7\u5ea6\u63d0\u4ea4\u53c2\u6570",
        "1.echo 1 > /proc/sys/vm/overcommit_memory\n"
        "2./etc/sysctl.conf \u6dfb\u52a0 vm.overcommit_memory = 1\n"
        "3.sysctl -p \u4f7f\u914d\u7f6e\u751f\u6548\n"
        "4.\u5173\u95ed THP: echo never > /sys/kernel/mm/transparent_hugepage/enabled\n"
        "5.\u76d1\u63a7 Redis \u5185\u5b58\u4f7f\u7528\u7387",
        "Database",
    ),
    (
        re.compile(r"shuffle.*block.*fetch|executor.*lost|lost executor", re.I),
        "Spark Executor \u4e22\u5931/Shuffle \u6570\u636e\u62c9\u53d6\u5931\u8d25",
        "Spark \u4efb\u52a1\u6267\u884c\u8fc7\u7a0b\u4e2d Executor \u88ab YARN \u6740\u6b7b\u6216 Shuffle Block \u62c9\u53d6\u5931\u8d25",
        "\u4f18\u5316 Spark \u5185\u5b58\u914d\u7f6e\u548c Shuffle \u7b56\u7565",
        "1.\u68c0\u67e5 YARN \u5bb9\u5668\u5185\u5b58\u914d\u7f6e\n"
        "2.\u589e\u5927 spark.executor.memory \u548c spark.executor.memoryOverhead\n"
        "3.\u5f00\u542f spark.shuffle.service.enabled \u5916\u7f6e Shuffle Service\n"
        "4.\u51cf\u5c11 Shuffle \u6570\u636e\u91cf\uff1a\u63d0\u524d filter/aggregate\n"
        "5.\u9002\u5f53\u589e\u52a0 spark.task.maxFailures",
        "Application",
    ),
    (
        re.compile(r"replicatedmergetree|replica.*restart.*thread", re.I),
        "ClickHouse \u526f\u672c\u91cd\u542f\u7ebf\u7a0b\u5f02\u5e38",
        "ClickHouse ReplicatedMergeTree \u526f\u672c\u91cd\u542f\u7ebf\u7a0b\u62a5\u9519\uff0c\u53ef\u80fd\u5f71\u54cd\u526f\u672c\u540c\u6b65",
        "\u4fee\u590d ClickHouse \u526f\u672c\u540c\u6b65\u5f02\u5e38",
        "1.\u68c0\u67e5 ZooKeeper \u8fde\u63a5\u72b6\u6001\n"
        "2.system.replicas \u67e5\u770b\u526f\u672c\u843d\u540e\u91cf\n"
        "3.SYSTEM RESTART REPLICA <table> \u624b\u52a8\u91cd\u542f\n"
        "4.\u68c0\u67e5\u78c1\u76d8\u7a7a\u95f4\uff08\u526f\u672c\u540c\u6b65\u9700\u8981\u4e34\u65f6\u7a7a\u95f4\uff09\n"
        "5.\u5fc5\u8981\u65f6 DETACH TABLE \u540e ATTACH TABLE \u91cd\u65b0\u6302\u8f7d",
        "Database",
    ),
    (
        re.compile(r"container.*complete.*unknown|mapreduce.*container", re.I),
        "Hadoop MapReduce Container \u72b6\u6001\u5f02\u5e38",
        "RM \u6536\u5230\u672a\u77e5 Container \u7684\u5b8c\u6210\u4e8b\u4ef6\uff0c\u901a\u5e38\u7531 NodeManager \u91cd\u542f\u6216\u7f51\u7edc\u5206\u533a\u5f15\u8d77",
        "\u6392\u67e5 Hadoop NodeManager \u5f02\u5e38",
        "1.\u67e5\u770b NodeManager \u65e5\u5fd7\u786e\u8ba4\u91cd\u542f\u539f\u56e0\n"
        "2.\u68c0\u67e5\u8282\u70b9\u5185\u5b58/\u78c1\u76d8\u662f\u5426\u89e6\u53d1\u5065\u5eb7\u68c0\u67e5\u5931\u8d25\n"
        "3.yarn node -status \u786e\u8ba4\u8282\u70b9\u72b6\u6001\n"
        "4.\u91cd\u65b0\u63d0\u4ea4\u5931\u8d25\u7684 MapReduce \u4f5c\u4e1a\n"
        "5.\u589e\u52a0 mapreduce.task.timeout \u51cf\u5c11\u8d85\u65f6",
        "Application",
    ),
    (
        re.compile(r"no such table|table.*not.*found|table.*does.*not.*exist", re.I),
        "\u6570\u636e\u5e93\u67e5\u8be2\u76ee\u6807\u8868\u4e0d\u5b58\u5728",
        "SQL \u67e5\u8be2\u5f15\u7528\u7684\u8868\u4e0d\u5b58\u5728\uff0c\u901a\u5e38\u7531 schema \u672a\u521d\u59cb\u5316\u3001\u8fc1\u79fb\u5931\u8d25\u6216\u591a\u79df\u6237\u914d\u7f6e\u9519\u8bef\u5f15\u8d77",
        "\u68c0\u67e5\u5e76\u4fee\u590d\u6570\u636e\u5e93 Schema \u521d\u59cb\u5316",
        "1.show tables \u786e\u8ba4\u8868\u662f\u5426\u5b58\u5728\n"
        "2.\u68c0\u67e5\u6570\u636e\u5e93\u8fc1\u79fb\u811a\u672c\u662f\u5426\u6267\u884c\n"
        "3.\u786e\u8ba4\u8fde\u63a5\u7684\u662f\u6b63\u786e\u7684\u6570\u636e\u5e93/schema\n"
        "4.\u624b\u52a8\u6267\u884c\u5efa\u8868 DDL\n"
        "5.\u68c0\u67e5\u591a\u79df\u6237\u9694\u79bb\u914d\u7f6e",
        "Database",
    ),
    (
        re.compile(r"path traversal|\.\.%|%2e%2e|%c0%af", re.I),
        "Web \u8def\u5f84\u7a7f\u8d8a\u653b\u51fb\uff08Path Traversal\uff09",
        "HTTP \u8bf7\u6c42\u4e2d\u5305\u542b\u8def\u5f84\u7a7f\u8d8a\u7279\u5f81\uff08../\uff09\uff0c\u653b\u51fb\u8005\u5c1d\u8bd5\u8bbf\u95ee Web \u6839\u76ee\u5f55\u4ee5\u5916\u7684\u6587\u4ef6",
        "\u4fee\u590d\u8def\u5f84\u7a7f\u8d8a\u6f0f\u6d1e\u5e76\u5c01\u7981\u653b\u51fb\u6e90",
        "1.WAF \u6dfb\u52a0\u8def\u5f84\u7a7f\u8d8a\u89c4\u5219\u62e6\u622a\n"
        "2.\u5c01\u7981\u653b\u51fb\u6765\u6e90 IP\n"
        "3.Web \u6846\u67b6\u5bf9\u8def\u5f84\u8fdb\u884c\u89c4\u8303\u5316\u6821\u9a8c\n"
        "4.\u914d\u7f6e Web \u670d\u52a1\u5668\u53ea\u5141\u8bb8\u8bbf\u95ee\u6307\u5b9a\u76ee\u5f55\n"
        "5.\u5b9a\u671f\u626b\u63cf Web \u5e94\u7528\u6f0f\u6d1e",
        "Security",
    ),
    (
        re.compile(r"ntp.*timeout|timesync.*error|time.*sync.*fail", re.I),
        "NTP \u65f6\u95f4\u540c\u6b65\u5931\u8d25",
        "systemd-timesyncd \u65e0\u6cd5\u8fde\u63a5 NTP \u670d\u52a1\u5668\uff0c\u8282\u70b9\u65f6\u95f4\u53ef\u80fd\u6f02\u79fb",
        "\u4fee\u590d NTP \u65f6\u95f4\u540c\u6b65\u914d\u7f6e",
        "1.systemctl status systemd-timesyncd\n"
        "2.chronyc tracking \u67e5\u770b\u5f53\u524d\u504f\u5dee\n"
        "3.\u786e\u8ba4 NTP \u670d\u52a1\u5668\u5730\u5740\u53ef\u8fbe\uff08UDP 123\uff09\n"
        "4.\u914d\u7f6e\u5185\u7f51 NTP \u670d\u52a1\u5668\n"
        "5.chronyc makestep \u5f3a\u5236\u540c\u6b65",
        "Network",
    ),
    (
        re.compile(r"rocksdb.*error|sst.*file.*error|cannot clear hard error", re.I),
        "RocksDB \u5b58\u50a8\u5f15\u64ce\u786c\u9519\u8bef",
        "RocksDB \u62a5\u544a\u786c\u9519\u8bef\uff0cSST \u6587\u4ef6\u7ba1\u7406\u5f02\u5e38",
        "\u4fee\u590d RocksDB \u78c1\u76d8\u786c\u9519\u8bef",
        "1.\u68c0\u67e5\u78c1\u76d8\u5065\u5eb7: smartctl -a /dev/sda\n"
        "2.\u6392\u67e5\u6587\u4ef6\u7cfb\u7edf\u9519\u8bef: fsck\n"
        "3.\u5907\u4efd\u73b0\u6709\u6570\u636e\n"
        "4.\u6e05\u7406\u635f\u574f\u7684 SST \u6587\u4ef6\uff08\u8c28\u614e\u64cd\u4f5c\uff09\n"
        "5.\u66ff\u6362\u6545\u969c\u78c1\u76d8\u5e76\u6062\u590d\u6570\u636e",
        "Storage",
    ),
    (
        re.compile(r"http.*4[0-9]{2}|status.*4[0-9]{2}|400 bad request|404 not found|429", re.I),
        "HTTP \u5ba2\u6237\u7aef\u9519\u8bef\uff084xx\uff09",
        "\u4e0a\u6e38\u670d\u52a1\u8fd4\u56de 4xx \u9519\u8bef\uff0c\u53ef\u80fd\u662f\u8bf7\u6c42\u53c2\u6570\u975e\u6cd5\u3001\u8ba4\u8bc1\u5931\u8d25\u6216\u88ab\u9650\u6d41",
        "\u6392\u67e5 HTTP 4xx \u9519\u8bef\u539f\u56e0",
        "1.\u67e5\u770b\u8bf7\u6c42\u8be6\u60c5\uff08URL/Headers/Body\uff09\n"
        "2.401/403\uff1a\u68c0\u67e5\u8ba4\u8bc1 Token \u662f\u5426\u8fc7\u671f\n"
        "3.404\uff1a\u786e\u8ba4 API \u8def\u5f84\u548c\u7248\u672c\u662f\u5426\u6b63\u786e\n"
        "4.429\uff1a\u964d\u4f4e\u8bf7\u6c42\u9891\u7387\u6216\u7533\u8bf7\u9650\u6d41\u914d\u989d\u63d0\u5347\n"
        "5.400\uff1a\u6821\u9a8c\u8bf7\u6c42\u53c2\u6570\u683c\u5f0f",
        "Application",
    ),
    (
        re.compile(r"5[0-9]{2} server error|502|503 service", re.I),
        "HTTP \u670d\u52a1\u7aef\u9519\u8bef\uff085xx\uff09",
        "\u670d\u52a1\u8fd4\u56de 5xx\uff0c\u8868\u793a\u670d\u52a1\u7aef\u5f02\u5e38",
        "\u6392\u67e5 HTTP 5xx \u670d\u52a1\u7aef\u9519\u8bef",
        "1.\u67e5\u770b\u670d\u52a1\u7aef\u9519\u8bef\u65e5\u5fd7\n"
        "2.\u68c0\u67e5\u4e0b\u6e38\u4f9d\u8d56\u5065\u5eb7\u72b6\u6001\n"
        "3.\u68c0\u67e5 CPU/\u5185\u5b58/\u8fde\u63a5\u6c60\n"
        "4.\u4e34\u65f6\u56de\u6eda\u5230\u4e0a\u4e00\u4e2a\u7a33\u5b9a\u7248\u672c\n"
        "5.\u91cd\u542f\u670d\u52a1\u5e76\u89c2\u5bdf\u9519\u8bef\u7387",
        "Application",
    ),
    (
        re.compile(r"kafka.*timeout|aborted due to timeout|producer.*timeout", re.I),
        "Kafka \u751f\u4ea7\u8005/\u6d88\u8d39\u8005\u8d85\u65f6",
        "Kafka \u64cd\u4f5c\u8d85\u65f6\uff0c\u53ef\u80fd\u7531 Broker \u8d1f\u8f7d\u9ad8\u3001\u7f51\u7edc\u5ef6\u8fdf\u6216\u5206\u533a Leader \u9009\u4e3e\u4e2d\u5f15\u8d77",
        "\u6392\u67e5 Kafka \u8d85\u65f6\u539f\u56e0\u5e76\u6062\u590d",
        "1.kafka-broker-api-versions.sh \u786e\u8ba4 Broker \u53ef\u8fbe\n"
        "2.\u68c0\u67e5 Broker JVM GC \u65e5\u5fd7\n"
        "3.\u589e\u5927 request.timeout.ms \u548c retry.backoff.ms\n"
        "4.\u68c0\u67e5\u5206\u533a ISR \u72b6\u6001\n"
        "5.\u68c0\u67e5\u6d88\u8d39\u8005 max.poll.interval.ms \u662f\u5426\u8fc7\u5c0f",
        "Middleware",
    ),
    (
        re.compile(r"dubbo.*fail|rpc.*error|motan.*error", re.I),
        "RPC \u6846\u67b6\u8c03\u7528\u5931\u8d25",
        "Dubbo/Motan \u7b49 RPC \u6846\u67b6\u8c03\u7528\u5931\u8d25\uff0c\u53ef\u80fd\u7531\u63d0\u4f9b\u8005\u4e0d\u53ef\u7528\u3001\u8d85\u65f6\u6216\u5e8f\u5217\u5316\u9519\u8bef\u5f15\u8d77",
        "\u6392\u67e5 RPC \u8c03\u7528\u5931\u8d25\u6839\u56e0",
        "1.\u68c0\u67e5\u6ce8\u518c\u4e2d\u5fc3\u4e2d\u63d0\u4f9b\u8005\u8282\u70b9\u662f\u5426\u5728\u7ebf\n"
        "2.\u786e\u8ba4\u63d0\u4f9b\u8005\u670d\u52a1\u7aef\u53e3\u76d1\u542c\u6b63\u5e38\n"
        "3.\u68c0\u67e5 RPC \u6846\u67b6\u65e5\u5fd7\u4e2d\u5177\u4f53\u5f02\u5e38\u7c7b\u578b\n"
        "4.\u6392\u67e5\u5e8f\u5217\u5316\u517c\u5bb9\u6027\n"
        "5.\u914d\u7f6e RPC \u964d\u7ea7/\u5bb9\u9519\u7b56\u7565",
        "Middleware",
    ),
    (
        re.compile(r"nacos.*fail|nacos.*error|beat.*fail|service.*register.*fail", re.I),
        "Nacos \u670d\u52a1\u6ce8\u518c/\u5fc3\u8df3\u5931\u8d25",
        "\u5fae\u670d\u52a1\u5411 Nacos \u6ce8\u518c\u4e2d\u5fc3\u53d1\u9001\u5fc3\u8df3\u5931\u8d25\uff0c\u53ef\u80fd\u5bfc\u81f4\u670d\u52a1\u5b9e\u4f8b\u88ab\u8e22\u4e0b\u7ebf",
        "\u4fee\u590d Nacos \u8fde\u63a5\u5f02\u5e38",
        "1.\u786e\u8ba4 Nacos \u670d\u52a1\u7aef\u6b63\u5e38\u8fd0\u884c\n"
        "2.\u68c0\u67e5\u670d\u52a1\u5230 Nacos \u7684\u7f51\u7edc\u8fde\u901a\u6027\n"
        "3.\u68c0\u67e5 Nacos \u8ba4\u8bc1\u914d\u7f6e\n"
        "4.\u8c03\u5927\u5fc3\u8df3\u8d85\u65f6\u53c2\u6570\n"
        "5.\u67e5\u770b Nacos \u670d\u52a1\u7aef\u65e5\u5fd7",
        "Middleware",
    ),
]

# MicroSS services
SERVICES = {
    "dbservice1":    {"asset_type": "database",    "ip": "0.0.0.4",  "env": "MicroSS"},
    "dbservice2":    {"asset_type": "database",    "ip": "0.0.0.2",  "env": "MicroSS"},
    "mobservice1":   {"asset_type": "application", "ip": "0.0.0.1",  "env": "MicroSS"},
    "mobservice2":   {"asset_type": "application", "ip": "0.0.0.3",  "env": "MicroSS"},
    "logservice1":   {"asset_type": "application", "ip": "0.0.0.5",  "env": "MicroSS"},
    "logservice2":   {"asset_type": "application", "ip": "0.0.0.6",  "env": "MicroSS"},
    "webservice1":   {"asset_type": "webserver",   "ip": "0.0.0.7",  "env": "MicroSS"},
    "webservice2":   {"asset_type": "webserver",   "ip": "0.0.0.8",  "env": "MicroSS"},
    "redisservice1": {"asset_type": "cache",       "ip": "0.0.0.9",  "env": "MicroSS"},
    "redisservice2": {"asset_type": "cache",       "ip": "0.0.0.10", "env": "MicroSS"},
}


def post(url: str, payload: dict, retries: int = 2) -> Optional[dict]:
    for attempt in range(retries + 1):
        try:
            r = requests.post(url, json=payload, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == retries:
                print(f"    [ERR] {e}")
                return None
            time.sleep(0.5)
    return None


def import_assets() -> int:
    print("\n-- Phase 1: Import Assets (MicroSS services) --")
    assets = [
        {"asset_id": name, "asset_type": info["asset_type"],
         "name": name, "ip": info["ip"], "env": info["env"],
         "data_source": SOURCE}
        for name, info in SERVICES.items()
    ]
    resp = post(f"{API_URL}/assets/sync", assets)
    if resp:
        print(f"  [OK] {len(assets)} assets synced")
        return len(assets)
    print(f"  [FAIL] assets sync failed")
    return 0


def import_alerts() -> int:
    print("\n-- Phase 2: Import Alerts (from run.zip) --")
    if not RUN_ZIP.exists():
        print("  run.zip not found, skip")
        return 0

    z = zipfile.ZipFile(RUN_ZIP)
    alerts, seen = [], set()
    for fname in ["run/run_table_2021-07.csv", "run/run_table_2021-08.csv"]:
        try:
            with z.open(fname) as f:
                content = f.read().decode("utf-8", errors="replace")
        except KeyError:
            continue
        for line in content.splitlines()[1:]:
            if not line.strip():
                continue
            parts = line.split(",", 2)
            if len(parts) < 3:
                continue
            date, service, msg = parts[0].strip(), parts[1].strip(), parts[2]
            m = re.search(r"\[([^\]]*anomal[^\]]*)\]", msg, re.I)
            if not m:
                continue
            atype = m.group(1)
            ts_m = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", msg)
            ts_str = ts_m.group(1) if ts_m else date
            alert_id = f"gaia-{service}-{ts_str}-{atype}".replace(" ", "_")[:200]
            if alert_id in seen:
                continue
            seen.add(alert_id)
            alerts.append({
                "alert_id":    alert_id,
                "content":     f"[{atype}] on {service}: {msg[50:130].strip()}",
                "level":       "WARNING",
                "source":      service,
                "asset_id":    service,
                "data_source": SOURCE,
            })

    success = 0
    for i, a in enumerate(alerts, 1):
        if post(f"{API_URL}/alerts/ingest", a):
            success += 1
        if i % 100 == 0 or i == len(alerts):
            print(f"  [{i}/{len(alerts)}] alerts ingested: {success} ok")
        time.sleep(0.02)
    return success


def extract_pairs() -> List[dict]:
    if not LOG_ZIP.exists():
        return []
    z = zipfile.ZipFile(LOG_ZIP)
    content = None
    for name in z.namelist():
        if "error.csv" in name:
            with z.open(name) as f:
                content = f.read().decode("utf-8", errors="replace")
            break
    if not content:
        return []

    rows = list(csv.DictReader(content.splitlines()))
    matched: Dict[str, dict] = {}
    for row in rows:
        text = row.get("description", "") + " " + row.get("raw_data", "")
        for (pat, fname, fdesc, sname, steps, domain) in PATTERNS:
            if pat.search(text):
                if fname not in matched:
                    matched[fname] = {
                        "fault_name":           fname,
                        "solution_name":        sname,
                        "solution_description": fdesc,
                        "steps":                steps,
                        "domain":               domain,
                        "data_source":          SOURCE,
                        "confidence":           0.9,
                        "import_batch_id":      BATCH,
                    }
                break
    return list(matched.values())


def import_faults(pairs: List[dict]) -> int:
    print(f"\n-- Phase 3: Import Faults+Solutions ({len(pairs)} pairs) --")
    success = 0
    for i, p in enumerate(pairs, 1):
        resp = post(f"{API_URL}/graph/add", p)
        status = "OK  " if resp else "FAIL"
        print(f"  [{i:2d}/{len(pairs)}] {status} {p['fault_name'][:60]}")
        if resp:
            success += 1
        time.sleep(0.1)
    return success


def main():
    parser = argparse.ArgumentParser(description="WisOps GAIA Importer")
    parser.add_argument("--api-url",      default="http://localhost:8002")
    parser.add_argument("--skip-assets",  action="store_true")
    parser.add_argument("--skip-alerts",  action="store_true")
    parser.add_argument("--skip-faults",  action="store_true")
    args = parser.parse_args()

    global API_URL
    API_URL = args.api_url.rstrip("/")

    print("=" * 60)
    print("WisOps -- GAIA Dataset Importer")
    print(f"  API:      {API_URL}")
    print(f"  run.zip:  {'OK' if RUN_ZIP.exists() else 'MISSING'}")
    print(f"  log.zip:  {'OK' if LOG_ZIP.exists() else 'MISSING'}")
    print("=" * 60)

    results = {}
    if not args.skip_assets:
        results["assets"] = import_assets()
    if not args.skip_alerts:
        results["alerts"] = import_alerts()
    if not args.skip_faults:
        pairs = extract_pairs()
        results["faults"] = import_faults(pairs)

    print("\n" + "=" * 60)
    print("Import complete:")
    for k, v in results.items():
        print(f"  {k}: {v}")
    print("=" * 60)


if __name__ == "__main__":
    main()
