# -*- coding: utf-8 -*-
"""
WisOps — LogHub 数据导入脚本
数据来源：LogHub 公开日志数据集（Hadoop / Linux / Spark / K8s / Zookeeper / HDFS / Apache / MySQL）
参考：https://github.com/logpai/loghub

本脚本内置 LogHub 各数据集中典型异常模式，生成标准化 fault-solution 对，
写入 data/loghub_faults.jsonl，并批量导入图谱。

Usage:
  python scripts/parse_loghub.py --api-url http://localhost:8021
  python scripts/parse_loghub.py --generate-only          # 仅生成数据文件，不导入
  python scripts/parse_loghub.py --dry-run                 # 解析预览，不写入
"""
import sys
import os
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import argparse
import json
import time
import uuid
from pathlib import Path
from typing import List, Dict, Any

import requests

ROOT     = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
OUT_FILE = DATA_DIR / "loghub_faults.jsonl"

BATCH_ID = "loghub-2026-04-29"
SOURCE   = "logHub"

# ─────────────────────────────────────────────────────────────────────────────
# LogHub 各数据集的典型异常 → fault-solution 知识对
# ─────────────────────────────────────────────────────────────────────────────

LOGHUB_FAULTS: List[Dict[str, Any]] = [

    # ══════════════════════════════════════════════════════════
    # HDFS（分布式文件系统）
    # ══════════════════════════════════════════════════════════
    {
        "fault": "HDFS 数据块损坏（Block Corruption）",
        "solution": "运行 fsck 修复并重新复制损坏数据块",
        "description": "HDFS 数据节点报告 checksum 校验失败，数据块标记为 CORRUPT",
        "steps": "1. hdfs fsck / -list-corruptfileblocks 列出损坏文件\n"
                 "2. hdfs fsck / -delete 删除无法恢复的损坏块\n"
                 "3. 确认副本数：hdfs dfs -stat '%r' <path>\n"
                 "4. 等待 NameNode 自动触发副本再平衡\n"
                 "5. 检查 DataNode 磁盘健康状态",
        "domain": "Storage",
        "log_pattern": "WARN org.apache.hadoop.hdfs.server.datanode.DataNode: Checksum error",
    },
    {
        "fault": "HDFS NameNode 内存不足（NameNode OOM）",
        "solution": "扩大 NameNode 堆内存并启用 NameNode Federation",
        "description": "NameNode JVM Heap 占用持续 >90%，频繁 Full GC，元数据操作延迟",
        "steps": "1. jstat -gcutil <NameNode_PID> 确认 GC 频率\n"
                 "2. 修改 hadoop-env.sh：HADOOP_NAMENODE_OPTS=-Xmx16g\n"
                 "3. 清理过期快照与已删除文件的元数据\n"
                 "4. 评估是否启用 NameNode Federation 分担命名空间\n"
                 "5. 重启 NameNode 并观察堆内存趋势",
        "domain": "Storage",
        "log_pattern": "java.lang.OutOfMemoryError: Java heap space",
    },
    {
        "fault": "HDFS 副本数不足（Under-Replicated Blocks）",
        "solution": "恢复 DataNode 并触发副本补齐",
        "description": "集群中 DataNode 下线后，大量数据块副本数低于配置值（默认 3）",
        "steps": "1. hdfs dfsadmin -report 查看 DataNode 状态\n"
                 "2. 排查 DataNode 下线原因（硬件/网络/磁盘满）\n"
                 "3. 重启 DataNode 使其重新注册\n"
                 "4. 监控 under-replicated blocks 数量直至归零\n"
                 "5. 设置副本复制带宽限制防止影响业务",
        "domain": "Storage",
        "log_pattern": "INFO BlockManager: Number of blocks under replicated",
    },
    {
        "fault": "HDFS SafeMode 无法退出",
        "solution": "手动强制退出 SafeMode 或修复缺失 Block",
        "description": "NameNode 启动后停在 SafeMode，提示 blocks reported < threshold",
        "steps": "1. hdfs dfsadmin -safemode get 确认原因\n"
                 "2. 检查 DataNode 是否全部在线\n"
                 "3. 若 block 报告率已满足，手动：hdfs dfsadmin -safemode leave\n"
                 "4. 若仍有丢失 block，运行 fsck 删除损坏文件后再退出\n"
                 "5. 检查 NameNode 日志确认无其他错误",
        "domain": "Storage",
        "log_pattern": "INFO NameNode: Safe mode ON",
    },
    {
        "fault": "HDFS 磁盘空间不足导致写入失败",
        "solution": "扩容 DataNode 磁盘或删除过期数据",
        "description": "DataNode 可用磁盘空间 <10%，新数据块分配失败",
        "steps": "1. df -h 查看各 DataNode 磁盘使用情况\n"
                 "2. hdfs dfs -du -s /user 找出大目录\n"
                 "3. 删除过期 YARN 日志：yarn logs --applicationId <id>\n"
                 "4. 扩展 dfs.datanode.data.dir 到新磁盘\n"
                 "5. 触发 Balancer 均衡数据分布",
        "domain": "Storage",
        "log_pattern": "WARN org.apache.hadoop.hdfs.server.datanode.DataNode: Disk space is low",
    },

    # ══════════════════════════════════════════════════════════
    # Hadoop（MapReduce / YARN）
    # ══════════════════════════════════════════════════════════
    {
        "fault": "MapReduce Task 内存溢出（Task OOM）",
        "solution": "增大 mapreduce.map/reduce.memory.mb 并调优 JVM 参数",
        "description": "MapReduce Map/Reduce Task 因内存超限被 YARN 容器杀死，任务失败",
        "steps": "1. 查看 YARN 日志确认 OOM 发生的 task 编号\n"
                 "2. 调整 mapreduce.map.memory.mb / mapreduce.reduce.memory.mb\n"
                 "3. 设置 mapreduce.map.java.opts=-Xmx（约内存限制的 0.8 倍）\n"
                 "4. 启用 uber 模式减少小 job 的容器开销\n"
                 "5. 重新提交任务并监控内存使用",
        "domain": "Middleware",
        "log_pattern": "Container killed by the ApplicationMaster. Exit code is 137",
    },
    {
        "fault": "YARN ResourceManager 连接超时",
        "solution": "重启 ResourceManager 并检查 ZooKeeper 连接",
        "description": "YARN 客户端报 Connection refused 或 ResourceManager 心跳丢失",
        "steps": "1. 检查 ResourceManager 进程是否存活：jps\n"
                 "2. 查看 ResourceManager 日志确认崩溃原因\n"
                 "3. 验证 ZooKeeper 集群可用性\n"
                 "4. 重启 ResourceManager：yarn-daemon.sh start resourcemanager\n"
                 "5. 确认 HA 切换是否生效（若配置了 RM HA）",
        "domain": "Middleware",
        "log_pattern": "ERROR org.apache.hadoop.yarn.client.api.impl.YarnClientImpl: Failed to connect to ResourceManager",
    },
    {
        "fault": "Hadoop Job 长时间 RUNNING 未结束",
        "solution": "定位慢任务（Straggler）并优化数据倾斜",
        "description": "MapReduce Job 中某个 Task 运行时间远超其他 Task，导致 Job 挂起",
        "steps": "1. YARN UI 查看 task 进度，定位慢任务\n"
                 "2. 开启 Speculative Execution：mapreduce.map.speculative=true\n"
                 "3. 检查输入数据是否存在分区倾斜\n"
                 "4. 增加 reduce 任务数量分散压力\n"
                 "5. 使用 Combiner 减少 Shuffle 数据量",
        "domain": "Middleware",
        "log_pattern": "INFO mapreduce.Job: map 95% reduce 0%",
    },
    {
        "fault": "YARN NodeManager 心跳超时后被移除",
        "solution": "修复网络问题并重新注册 NodeManager",
        "description": "NodeManager 因网络抖动或 GC 停顿导致心跳超时，被 ResourceManager 标记为 LOST",
        "steps": "1. 排查 NodeManager 节点网络连通性\n"
                 "2. 检查 JVM GC 日志，若 Stop-the-World 过长则调优\n"
                 "3. 重启 NodeManager：yarn-daemon.sh start nodemanager\n"
                 "4. 调整 yarn.nm.liveness-monitor.expiry-interval-ms 增大超时阈值\n"
                 "5. 监控心跳延迟指标",
        "domain": "Middleware",
        "log_pattern": "WARN org.apache.hadoop.yarn.server.resourcemanager.rmnode: Node is not responding",
    },
    {
        "fault": "Hadoop Shuffle 阶段失败（Fetch Failed）",
        "solution": "增大 shuffle 超时重试次数并检查网络",
        "description": "Reduce Task 在 Shuffle 阶段拉取 Map 输出失败，任务重试多次后整个 Job 失败",
        "steps": "1. 查看 Reduce Task 日志中的 Fetch Failed 来源节点\n"
                 "2. 检查对应 Map 节点是否存活\n"
                 "3. 增大 mapreduce.reduce.shuffle.retry-delay.max.ms\n"
                 "4. 检查磁盘 I/O 是否成为瓶颈\n"
                 "5. 增大 mapreduce.task.timeout 防止任务超时误杀",
        "domain": "Middleware",
        "log_pattern": "WARN org.apache.hadoop.mapreduce.task.reduce.Fetcher: Failed to connect to",
    },

    # ══════════════════════════════════════════════════════════
    # Spark
    # ══════════════════════════════════════════════════════════
    {
        "fault": "Spark Executor OOM（Driver 侧收集数据过大）",
        "solution": "避免 collect()/toPandas() 收集超大数据集到 Driver",
        "description": "Driver 调用 collect() 将 RDD 全量拉回内存导致 OOM，作业失败",
        "steps": "1. 检查 Driver 日志定位 OOM 发生位置\n"
                 "2. 用 take(N) 替代 collect() 限制返回数据量\n"
                 "3. 若必须全量，增大 spark.driver.memory\n"
                 "4. 改用 foreach/foreachPartition 分区处理\n"
                 "5. 使用持久化写出（saveAsTextFile 等）替代内存汇总",
        "domain": "Middleware",
        "log_pattern": "java.lang.OutOfMemoryError: GC overhead limit exceeded",
    },
    {
        "fault": "Spark Executor Lost（频繁重新调度）",
        "solution": "调整 executor 内存与 GC 策略，避免被 YARN 杀死",
        "description": "Spark Executor 因内存超限或 GC 停顿被 YARN 容器杀死，Stage 重试",
        "steps": "1. spark.executor.memory 设为容器内存的 75%\n"
                 "2. spark.executor.memoryOverhead 设为 executor memory 的 20%\n"
                 "3. 启用动态内存分配：spark.dynamicAllocation.enabled=true\n"
                 "4. 调整 GC：-XX:+UseG1GC -XX:G1HeapRegionSize=16m\n"
                 "5. 减小单个 partition 数据量，增加 shuffle 分区数",
        "domain": "Middleware",
        "log_pattern": "ERROR TaskSetManager: Lost executor",
    },
    {
        "fault": "Spark 数据倾斜（Skew Join）导致 Stage 卡住",
        "solution": "使用 Salting 或 AQE 自适应倾斜优化",
        "description": "某个 Reduce 分区数据量远超其他分区，导致该 Task 长时间运行",
        "steps": "1. Spark UI 中查看 Stage 各 task 执行时间分布\n"
                 "2. 启用 AQE：spark.sql.adaptive.enabled=true\n"
                 "3. 对热点 key 使用 Salting（追加随机数前缀）分散\n"
                 "4. 过滤 null key 或单独处理 null 分区\n"
                 "5. 广播小表替代大表 Join（spark.sql.autoBroadcastJoinThreshold）",
        "domain": "Middleware",
        "log_pattern": "WARN TaskSetManager: Stage contains a task of a very large size",
    },
    {
        "fault": "Spark Shuffle 写入磁盘失败",
        "solution": "扩容 Shuffle 磁盘空间并设置多目录",
        "description": "Executor 在 Shuffle Write 阶段磁盘写满，任务失败后整个 Job 重试",
        "steps": "1. 检查 Executor 所在节点磁盘使用率：df -h\n"
                 "2. spark.local.dir 配置多磁盘目录分散写压力\n"
                 "3. 增大 spark.shuffle.file.buffer 减少系统调用\n"
                 "4. 清理 /tmp 或专用 shuffle 目录的历史数据\n"
                 "5. 减少 Shuffle 数据量：过滤、聚合提前下推",
        "domain": "Middleware",
        "log_pattern": "org.apache.spark.SparkException: Failed to write shuffle",
    },
    {
        "fault": "Spark Structured Streaming 消费 Kafka 延迟过高",
        "solution": "增大 maxOffsetsPerTrigger 并扩充 Executor 数",
        "description": "Streaming 作业处理速度跟不上 Kafka 生产速度，消费延迟持续增大",
        "steps": "1. Spark UI Streaming 页查看 inputRate vs processedRate\n"
                 "2. 增大 maxOffsetsPerTrigger 单批次消费量\n"
                 "3. 增加 Executor 数量或提升 Executor 规格\n"
                 "4. 优化处理逻辑，减少不必要的 Shuffle\n"
                 "5. 检查下游写入（如 HDFS/DB）是否成为瓶颈",
        "domain": "Middleware",
        "log_pattern": "WARN MicroBatchExecution: Streaming query is lagging behind",
    },
    {
        "fault": "Spark 作业提交失败（无法连接 Master）",
        "solution": "检查 Spark Master 进程状态并重启",
        "description": "spark-submit 报 Connection refused，Standalone 模式 Master 不可达",
        "steps": "1. 验证 Master 节点进程：jps | grep Master\n"
                 "2. 检查 Master 日志确认崩溃原因\n"
                 "3. 重启 Master：sbin/start-master.sh\n"
                 "4. 验证防火墙 7077 端口是否开放\n"
                 "5. 若使用 HA，确认 ZooKeeper 中活跃 Master 地址",
        "domain": "Middleware",
        "log_pattern": "org.apache.spark.SparkException: Could not connect to Master",
    },

    # ══════════════════════════════════════════════════════════
    # Linux（系统日志）
    # ══════════════════════════════════════════════════════════
    {
        "fault": "Linux OOM Killer 终止进程",
        "solution": "增加物理内存或为关键进程设置 oom_score_adj",
        "description": "内核 OOM Killer 因系统内存耗尽，强制杀死高内存占用进程",
        "steps": "1. dmesg | grep -i 'oom kill' 确认被杀进程\n"
                 "2. free -m 查看内存使用情况\n"
                 "3. 为关键进程降低 OOM 分数：echo -17 > /proc/<PID>/oom_score_adj\n"
                 "4. 排查内存泄漏：valgrind / pmap -x <PID>\n"
                 "5. 扩容内存或增加 Swap（临时缓解）",
        "domain": "System",
        "log_pattern": "kernel: Out of memory: Kill process",
    },
    {
        "fault": "Linux 磁盘 I/O 错误（Block Device Error）",
        "solution": "更换故障磁盘并从 RAID 重建数据",
        "description": "内核日志出现 I/O error 或 EXT4 文件系统错误，磁盘可能面临硬件故障",
        "steps": "1. dmesg | grep -i 'i/o error\\|blk_update_request' 确认故障磁盘\n"
                 "2. smartctl -a /dev/sdX 检查磁盘 SMART 状态\n"
                 "3. 若为 RAID 降级，立即更换故障盘：mdadm --manage /dev/md0 --add /dev/sdX\n"
                 "4. 从备份恢复受损文件\n"
                 "5. 配置磁盘监控告警（smartd / Prometheus node_exporter）",
        "domain": "Storage",
        "log_pattern": "kernel: end_request: I/O error, dev sda, sector",
    },
    {
        "fault": "Linux 系统时钟漂移（NTP 不同步）",
        "solution": "修复 NTP 配置并同步系统时钟",
        "description": "分布式系统节点时钟偏差 >1s，导致 Kerberos/TLS/分布式锁异常",
        "steps": "1. timedatectl status 查看时钟同步状态\n"
                 "2. ntpq -p 或 chronyc sources 查看 NTP 服务器连通性\n"
                 "3. 修复 /etc/chrony.conf 中的 NTP 服务器配置\n"
                 "4. 手动同步：chronyc makestep\n"
                 "5. 重启 chronyd 服务并设置开机自启",
        "domain": "System",
        "log_pattern": "ntpd: time slew +0.123456s",
    },
    {
        "fault": "Linux 文件描述符耗尽（Too many open files）",
        "solution": "调整 ulimit 并优化应用 FD 泄漏",
        "description": "进程打开文件数达到 ulimit 限制，新建连接/文件操作全部失败",
        "steps": "1. lsof -p <PID> | wc -l 查看当前进程 FD 数\n"
                 "2. cat /proc/sys/fs/file-max 查看系统级限制\n"
                 "3. 修改 /etc/security/limits.conf：* hard nofile 65535\n"
                 "4. 对正在运行的进程：ulimit -n 65535（需 root）\n"
                 "5. 排查应用是否存在 FD 泄漏（未关闭的连接/文件）",
        "domain": "System",
        "log_pattern": "Too many open files (errno 24)",
    },
    {
        "fault": "Linux 内核 OOPS / Kernel Panic",
        "solution": "分析 kdump 转储文件定位根因并更新内核",
        "description": "服务器发生内核崩溃，系统自动重启或挂起，日志中出现 Oops/BUG 堆栈",
        "steps": "1. 配置 kdump：yum install kexec-tools; systemctl enable kdump\n"
                 "2. 从 /var/crash 获取 vmcore 转储文件\n"
                 "3. 使用 crash 工具分析：crash /boot/vmlinux <vmcore>\n"
                 "4. 将堆栈信息报告给内核社区或操作系统厂商\n"
                 "5. 升级内核到修复版本或禁用问题驱动模块",
        "domain": "System",
        "log_pattern": "BUG: unable to handle kernel NULL pointer dereference",
    },
    {
        "fault": "Linux 进程 Zombie 堆积",
        "solution": "修复父进程未正确 wait() 子进程的问题",
        "description": "ps 输出大量 <defunct> 状态进程，说明父进程未回收子进程资源",
        "steps": "1. ps aux | grep Z 统计 zombie 进程数量\n"
                 "2. 找到 zombie 父进程：ps -o ppid= -p <zombie_pid>\n"
                 "3. 排查父进程逻辑，确保调用 wait()/waitpid()\n"
                 "4. 若父进程为 init 接管，可直接重启父进程清理\n"
                 "5. 若大量 zombie 影响 PID 资源，检查 /proc/sys/kernel/pid_max",
        "domain": "System",
        "log_pattern": "INFO: task proc:1234 blocked for more than 120 seconds",
    },
    {
        "fault": "Linux SSH 连接超时断开",
        "solution": "配置 SSH KeepAlive 并调整 sshd 超时参数",
        "description": "长时间空闲的 SSH 连接被服务端或中间防火墙断开，运维操作中断",
        "steps": "1. 在 /etc/ssh/sshd_config 设置：ClientAliveInterval 60\n"
                 "2. 设置：ClientAliveCountMax 3（最多 3 次确认）\n"
                 "3. 客户端 ~/.ssh/config：ServerAliveInterval 60\n"
                 "4. 重载 sshd：systemctl reload sshd\n"
                 "5. 对中间防火墙：配置 TCP KeepAlive 超时 >300s",
        "domain": "Network",
        "log_pattern": "sshd: Timeout, client not responding",
    },
    {
        "fault": "Linux 网卡丢包率高（RX dropped packets）",
        "solution": "增大 RX Ring Buffer 并调整 IRQ 亲和性",
        "description": "网卡接收队列满导致数据包丢弃，高流量时 ifconfig 显示 RX dropped 持续增长",
        "steps": "1. ethtool -S eth0 | grep -i drop 查看丢包统计\n"
                 "2. 增大 RX ring buffer：ethtool -G eth0 rx 4096\n"
                 "3. 设置 IRQ 亲和性（多队列网卡）：/etc/irqbalance\n"
                 "4. 检查内核 softirq 积压：cat /proc/net/softnet_stat\n"
                 "5. 升级网卡驱动或考虑 DPDK 用户态网络栈",
        "domain": "Network",
        "log_pattern": "eth0: 1000 dropped packets",
    },

    # ══════════════════════════════════════════════════════════
    # Kubernetes
    # ══════════════════════════════════════════════════════════
    {
        "fault": "K8s Pod CrashLoopBackOff",
        "solution": "检查容器日志定位崩溃原因并修复启动命令或依赖",
        "description": "Pod 容器持续崩溃并重启，kubelet 不断尝试拉起，状态为 CrashLoopBackOff",
        "steps": "1. kubectl describe pod <name> 查看 Events 和 Restart 次数\n"
                 "2. kubectl logs <pod> --previous 查看上一次崩溃日志\n"
                 "3. 检查启动命令、环境变量和配置 ConfigMap 是否正确\n"
                 "4. 确认依赖服务（DB/Redis）是否可访问\n"
                 "5. 修复后滚动更新：kubectl rollout restart deployment/<name>",
        "domain": "Kubernetes",
        "log_pattern": "Back-off restarting failed container",
    },
    {
        "fault": "K8s 镜像拉取失败（ImagePullBackOff）",
        "solution": "修复镜像地址或配置私有镜像仓库凭证",
        "description": "Pod 因无法拉取容器镜像而无法启动，状态停留在 ImagePullBackOff",
        "steps": "1. kubectl describe pod <name> 查看 Image Pull 错误信息\n"
                 "2. 检查镜像名称和 Tag 是否正确（大小写敏感）\n"
                 "3. 若为私有仓库，创建 imagePullSecrets：kubectl create secret docker-registry\n"
                 "4. 检查节点网络是否能访问镜像仓库\n"
                 "5. 手动在节点上 docker pull <image> 验证",
        "domain": "Kubernetes",
        "log_pattern": "Failed to pull image: rpc error: code = Unknown",
    },
    {
        "fault": "K8s Node 内存压力（MemoryPressure）",
        "solution": "驱逐低优先级 Pod 并扩容节点",
        "description": "节点可用内存低于阈值，kubelet 设置 MemoryPressure 条件，触发 Pod 驱逐",
        "steps": "1. kubectl describe node <name> 查看 MemoryPressure 条件\n"
                 "2. 确认高内存使用的 Pod：kubectl top pod --all-namespaces\n"
                 "3. 设置 PriorityClass 确保关键 Pod 不被驱逐\n"
                 "4. 为 Pod 设置合理的 memory request/limit\n"
                 "5. 增加集群节点数量或升级节点规格",
        "domain": "Kubernetes",
        "log_pattern": "kubelet: evicting pod due to memory pressure",
    },
    {
        "fault": "K8s Pod Pending 无法调度（Insufficient CPU/Memory）",
        "solution": "扩容集群节点或降低 Pod Resource Request",
        "description": "Pod 长时间处于 Pending 状态，Scheduler 因资源不足无法找到合适节点",
        "steps": "1. kubectl describe pod <name> 查看 Events 中的调度失败原因\n"
                 "2. kubectl top nodes 查看各节点资源利用率\n"
                 "3. 降低 Pod 的 resources.requests 或使用 HPA 自动伸缩\n"
                 "4. 为集群添加新节点（cluster-autoscaler）\n"
                 "5. 检查是否存在 Taint/Toleration 或 Affinity 导致不匹配",
        "domain": "Kubernetes",
        "log_pattern": "0/3 nodes are available: Insufficient cpu",
    },
    {
        "fault": "K8s etcd 集群写入延迟过高",
        "solution": "使用 SSD 存储并限制 etcd 并发请求",
        "description": "etcd 写入 P99 延迟超过 100ms，API Server 出现超时，集群操作响应慢",
        "steps": "1. etcdctl endpoint status 查看各成员延迟和 leader\n"
                 "2. iostat -x 确认 etcd 数据盘 I/O 是否饱和\n"
                 "3. 迁移 etcd 数据到 SSD 磁盘\n"
                 "4. 定期压缩 etcd：etcdctl compact && etcdctl defrag\n"
                 "5. 限制 API Server 并发：--max-requests-inflight=400",
        "domain": "Kubernetes",
        "log_pattern": "etcdserver: apply request took too long",
    },
    {
        "fault": "K8s Service 无法访问（Endpoints 为空）",
        "solution": "检查 Pod Label 与 Service Selector 是否匹配",
        "description": "Service 的 Endpoints 列表为空，访问 Service ClusterIP 无响应",
        "steps": "1. kubectl get endpoints <service> 确认 Endpoints 是否为空\n"
                 "2. kubectl describe service <name> 查看 Selector\n"
                 "3. kubectl get pod --show-labels 对比 Pod Label\n"
                 "4. 确认 Pod 处于 Running 状态且 readinessProbe 通过\n"
                 "5. 检查 kube-proxy / CNI 插件日志",
        "domain": "Kubernetes",
        "log_pattern": "Warning: Endpoints is not ready",
    },
    {
        "fault": "K8s Ingress 证书过期导致 HTTPS 失败",
        "solution": "更新 TLS Secret 或配置 cert-manager 自动续签",
        "description": "Ingress TLS 证书到期，浏览器拒绝访问，curl 报 SSL certificate has expired",
        "steps": "1. openssl s_client -connect <domain>:443 查看证书有效期\n"
                 "2. 若使用 cert-manager，检查 Certificate 对象状态\n"
                 "3. 手动更新：kubectl create secret tls <name> --cert=new.crt --key=new.key\n"
                 "4. 配置 cert-manager + Let's Encrypt 自动续签\n"
                 "5. 设置证书到期监控告警（提前 30 天）",
        "domain": "Kubernetes",
        "log_pattern": "SSL certificate has expired",
    },
    {
        "fault": "K8s Namespace 删除卡住（Terminating 状态）",
        "solution": "手动移除 finalizers 解除删除卡住",
        "description": "执行 kubectl delete namespace 后，Namespace 长时间处于 Terminating 状态",
        "steps": "1. kubectl get namespace <name> -o json | grep finalizers\n"
                 "2. 编辑移除 finalizers：kubectl edit namespace <name>\n"
                 "3. 或使用 API 强制：kubectl proxy; curl -X PUT http://127.0.0.1:8001/api/v1/namespaces/<name>/finalize\n"
                 "4. 检查是否有 CRD 资源未清理\n"
                 "5. 删除关联 CRD 实例后 Namespace 自动回收",
        "domain": "Kubernetes",
        "log_pattern": "namespace is stuck in Terminating state",
    },

    # ══════════════════════════════════════════════════════════
    # ZooKeeper
    # ══════════════════════════════════════════════════════════
    {
        "fault": "ZooKeeper 会话超时（Session Expired）",
        "solution": "增大 session timeout 并排查网络抖动",
        "description": "客户端 ZooKeeper session 超时过期，临时节点被删除，引发服务异常",
        "steps": "1. 检查 ZooKeeper 服务器与客户端的网络延迟\n"
                 "2. 在客户端增大 sessionTimeout 参数（建议 ≥30s）\n"
                 "3. 检查 ZooKeeper GC：jstat -gcutil <pid>，减少 GC 停顿\n"
                 "4. 调整 tickTime / maxSessionTimeout 匹配业务需求\n"
                 "5. 业务层实现 Watcher 重注册逻辑处理 Session 重建",
        "domain": "Middleware",
        "log_pattern": "ZooKeeper: Session expired",
    },
    {
        "fault": "ZooKeeper Leader 选举失败",
        "solution": "恢复多数 follower 节点以满足 quorum",
        "description": "ZooKeeper 集群中超过半数节点不可用，无法完成 Leader 选举，集群不可写",
        "steps": "1. 检查各 ZooKeeper 节点进程是否存活\n"
                 "2. 恢复宕机节点，确保存活节点 > N/2\n"
                 "3. 查看 leader/follower 状态：echo stat | nc localhost 2181\n"
                 "4. 确认 myid 文件和 zoo.cfg server 列表配置一致\n"
                 "5. 检查端口 2888/3888 防火墙规则",
        "domain": "Middleware",
        "log_pattern": "WARN QuorumPeer: Exception when following the leader",
    },
    {
        "fault": "ZooKeeper 数据目录磁盘满",
        "solution": "清理旧快照与事务日志",
        "description": "ZooKeeper 数据目录堆积大量快照和事务日志文件，磁盘耗尽导致写入失败",
        "steps": "1. du -sh $ZOO_DATA_DIR/* 查看文件占用\n"
                 "2. 配置自动清理：autopurge.snapRetainCount=3, autopurge.purgeInterval=24\n"
                 "3. 手动清理：zkCleanup.sh -n 3\n"
                 "4. 将数据目录迁移到更大磁盘\n"
                 "5. 监控 ZooKeeper 数据目录磁盘使用率，设置告警",
        "domain": "Middleware",
        "log_pattern": "Unable to create new log file: No space left on device",
    },

    # ══════════════════════════════════════════════════════════
    # Apache（Web 服务器）
    # ══════════════════════════════════════════════════════════
    {
        "fault": "Apache 进程耗尽（MaxRequestWorkers 打满）",
        "solution": "调整 MaxRequestWorkers 并切换至 Worker/Event MPM",
        "description": "Apache 并发连接数达到 MaxRequestWorkers 上限，新请求被拒绝或排队",
        "steps": "1. apache2ctl status 查看当前 worker 状态\n"
                 "2. 增大 MaxRequestWorkers（注意 ServerLimit 同步调整）\n"
                 "3. 迁移至 event MPM 提高并发能力（减少线程开销）\n"
                 "4. 检查慢请求/长连接阻塞 worker\n"
                 "5. 在前端加 Nginx 反代，减少直接连到 Apache 的长连接",
        "domain": "Middleware",
        "log_pattern": "server reached MaxRequestWorkers setting, consider raising the MaxRequestWorkers",
    },
    {
        "fault": "Apache SSL 握手失败",
        "solution": "更新证书并修复 SSL 配置",
        "description": "Apache 报 SSL handshake failure，客户端无法建立 HTTPS 连接",
        "steps": "1. openssl s_client -connect host:443 查看握手错误\n"
                 "2. 检查证书文件路径和权限\n"
                 "3. 确认 SSLCertificateFile / SSLCertificateKeyFile 匹配\n"
                 "4. 更新 SSLProtocol / SSLCipherSuite 禁用弱算法\n"
                 "5. 重启 Apache：apachectl graceful",
        "domain": "Middleware",
        "log_pattern": "SSL Library Error: error:140A1175:SSL routines",
    },

    # ══════════════════════════════════════════════════════════
    # MySQL
    # ══════════════════════════════════════════════════════════
    {
        "fault": "MySQL 连接数耗尽（Too many connections）",
        "solution": "增大 max_connections 并优化连接池",
        "description": "MySQL 连接数超过 max_connections 限制，新连接被拒绝",
        "steps": "1. SHOW GLOBAL STATUS LIKE 'Max_used_connections' 查看峰值\n"
                 "2. SET GLOBAL max_connections = 1000（临时）\n"
                 "3. 在 my.cnf 永久配置 max_connections\n"
                 "4. 排查连接泄漏：SHOW PROCESSLIST 找长时间 Sleep 连接\n"
                 "5. 引入连接池（PgBouncer/ProxySQL）复用连接",
        "domain": "Middleware",
        "log_pattern": "ERROR 1040 (HY000): Too many connections",
    },
    {
        "fault": "MySQL 主从复制延迟过高",
        "solution": "开启并行复制并优化大事务",
        "description": "从库复制延迟超过 30s，读写分离业务读到旧数据",
        "steps": "1. SHOW SLAVE STATUS\\G 查看 Seconds_Behind_Master\n"
                 "2. 开启 MTS 并行复制：slave_parallel_workers=4\n"
                 "3. 分拆大事务，避免单个事务超过 1MB\n"
                 "4. 提升从库硬件规格或使用 SSD\n"
                 "5. 业务层使用强制读主库兜底关键操作",
        "domain": "Middleware",
        "log_pattern": "Slave_SQL_Running_State: Waiting to execute in parallel",
    },
    {
        "fault": "MySQL InnoDB 死锁（Deadlock）",
        "solution": "调整事务加锁顺序并减小事务粒度",
        "description": "多个并发事务相互等待锁，InnoDB 检测到死锁并回滚其中一个事务",
        "steps": "1. SHOW ENGINE INNODB STATUS\\G 查看 LATEST DETECTED DEADLOCK\n"
                 "2. 确保不同事务以相同顺序加锁（消除循环依赖）\n"
                 "3. 缩短事务执行时间，减少持锁窗口\n"
                 "4. 减少隔离级别为 READ COMMITTED（视业务允许）\n"
                 "5. 应用层增加死锁重试逻辑",
        "domain": "Middleware",
        "log_pattern": "TRANSACTION: TRANSACTION WAIT, LOCK WAIT",
    },
    {
        "fault": "MySQL 磁盘 binlog 爆满",
        "solution": "清理过期 binlog 并设置自动过期策略",
        "description": "binlog 文件持续增长，磁盘耗尽导致 MySQL 停止写入",
        "steps": "1. SHOW BINARY LOGS 查看 binlog 大小和数量\n"
                 "2. 设置自动过期：binlog_expire_logs_seconds=604800（7天）\n"
                 "3. 手动清理：PURGE BINARY LOGS BEFORE NOW() - INTERVAL 7 DAY\n"
                 "4. 确认从库已消费完要删除的 binlog\n"
                 "5. 将 binlog 目录迁移到独立大容量磁盘",
        "domain": "Middleware",
        "log_pattern": "ERROR: Writing one row to the row-based binary log failed",
    },

    # ══════════════════════════════════════════════════════════
    # 通用分布式系统（LogHub 综合模式）
    # ══════════════════════════════════════════════════════════
    {
        "fault": "分布式系统脑裂（Split-Brain）",
        "solution": "引入 Fencing 机制并优化 quorum 配置",
        "description": "网络分区导致集群两个子集都认为自己是主节点，数据不一致",
        "steps": "1. 确认网络分区是否真实存在（排除误报）\n"
                 "2. 启用 STONITH/Fencing 强制隔离旧主节点\n"
                 "3. 将 quorum 配置为奇数节点（推荐 3/5 节点）\n"
                 "4. 恢复网络后进行数据一致性检验和修复\n"
                 "5. 引入 Raft 或 Paxos 等强一致协议替代弱 HA 方案",
        "domain": "Middleware",
        "log_pattern": "WARN: Detected potential split-brain scenario",
    },
    {
        "fault": "消息队列积压（Queue Backlog）",
        "solution": "扩容消费者并优化消息处理逻辑",
        "description": "消息生产速度持续超过消费速度，队列消息积压不断增大",
        "steps": "1. 监控 Lag 指标定位积压的 topic/partition\n"
                 "2. 扩展消费者实例数量或线程数\n"
                 "3. 优化消费者处理逻辑，减少单条消息耗时\n"
                 "4. 检查下游依赖（DB/外部 API）是否成为瓶颈\n"
                 "5. 临时增加消费者跑批清空积压后再恢复正常数量",
        "domain": "Middleware",
        "log_pattern": "WARN: Consumer lag is too high",
    },
    {
        "fault": "服务注册中心节点失效导致服务发现失败",
        "solution": "恢复注册中心并实现客户端本地缓存兜底",
        "description": "Consul/Nacos/Eureka 注册中心节点故障，微服务无法解析下游地址",
        "steps": "1. 检查注册中心节点健康状态\n"
                 "2. 若为单节点，立即恢复或切换备用节点\n"
                 "3. 客户端开启本地服务发现缓存（容忍注册中心临时不可用）\n"
                 "4. 建立注册中心 HA 集群（多副本 + 选主）\n"
                 "5. 配置断路器防止连锁故障",
        "domain": "Middleware",
        "log_pattern": "ERROR ServiceDiscovery: Failed to resolve service",
    },
    {
        "fault": "配置中心连接失败（Config Server Unreachable）",
        "solution": "恢复配置中心并开启本地配置备份",
        "description": "Spring Cloud Config / Apollo 配置中心不可达，应用启动失败或无法刷新配置",
        "steps": "1. 检查配置中心服务进程和端口可达性\n"
                 "2. 应用开启 spring.cloud.config.fail-fast=false 允许降级\n"
                 "3. 启用本地配置备份（bootstrap.yml fallback）\n"
                 "4. 恢复配置中心服务后触发客户端 /refresh\n"
                 "5. 为配置中心建立 HA 集群",
        "domain": "Middleware",
        "log_pattern": "Could not locate PropertySource, will be allowed to use local bootstrap",
    },
    {
        "fault": "日志采集 Agent 占用 CPU 过高",
        "solution": "限制 Agent 资源并调整采集频率",
        "description": "Filebeat/Fluentd 等日志采集 Agent 在高日志量时 CPU 占用 >30%，影响业务",
        "steps": "1. top/pidstat 确认日志 agent CPU 占用情况\n"
                 "2. 调低采集扫描频率：scan_frequency: 10s\n"
                 "3. 启用多工作线程：workers: 4\n"
                 "4. 对高频日志路径配置 multiline 合并减少事件数\n"
                 "5. 为 Agent 设置 CPU cgroup 限制（如 Kubernetes resources.limits）",
        "domain": "Middleware",
        "log_pattern": "WARN filebeat: High CPU usage detected",
    },
    {
        "fault": "Elasticsearch 集群 Red 状态（分片未分配）",
        "solution": "恢复节点并重新分配未分配分片",
        "description": "Elasticsearch 集群健康状态为 Red，部分主分片未分配导致索引不可用",
        "steps": "1. GET /_cluster/health 查看 unassigned_shards 数量\n"
                 "2. GET /_cluster/allocation/explain 定位未分配原因\n"
                 "3. 恢复宕机数据节点，使分片重新分配\n"
                 "4. 若节点无法恢复，手动重新分配：POST /_cluster/reroute\n"
                 "5. 调整 index.number_of_replicas 为 0 临时解除 Red 状态",
        "domain": "Storage",
        "log_pattern": "ClusterHealthStatus: RED",
    },
    {
        "fault": "Elasticsearch 写入拒绝（rejected execution）",
        "solution": "增大写入队列大小并扩展数据节点",
        "description": "ES bulk 写入被拒绝，报 rejected execution of coordinating operation，写入积压",
        "steps": "1. GET /_nodes/stats/thread_pool/write 查看写入队列状态\n"
                 "2. 增大 thread_pool.write.queue_size（最大 200）\n"
                 "3. 优化 bulk size：建议每批 5-15 MB / 1000-5000 条\n"
                 "4. 客户端实现指数退避重试\n"
                 "5. 扩展数据节点数量分散写入压力",
        "domain": "Storage",
        "log_pattern": "EsRejectedExecutionException: rejected execution of coordinating operation",
    },
    {
        "fault": "Kafka 消费者组重平衡频繁（Rebalance Storm）",
        "solution": "增大 session.timeout 并使用 Sticky 分配策略",
        "description": "Kafka 消费者组不断触发 Rebalance，消费暂停，积压剧增",
        "steps": "1. 检查消费者日志中 Rebalance 触发原因\n"
                 "2. 增大 session.timeout.ms（如 30000）和 heartbeat.interval.ms（10000）\n"
                 "3. max.poll.interval.ms 设置大于最慢消息处理时间\n"
                 "4. 使用 StickyAssignor 减少不必要的分区重分配\n"
                 "5. 避免消费者单次 poll 消费时间过长（拆分处理逻辑）",
        "domain": "Middleware",
        "log_pattern": "INFO AbstractCoordinator: (Re)joining group",
    },
    {
        "fault": "Kafka Topic 分区 Leader 不均衡",
        "solution": "执行 preferred replica 选举重新均衡 Leader",
        "description": "Broker 重启后 Leader 副本集中在少数节点，导致负载不均衡",
        "steps": "1. kafka-topics.sh --describe 查看各分区 Leader 分布\n"
                 "2. 开启自动 Leader 均衡：auto.leader.rebalance.enable=true\n"
                 "3. 手动触发：kafka-preferred-replica-election.sh\n"
                 "4. 确保 Broker 间磁盘容量和 CPU 配置均衡\n"
                 "5. 配置 leader.imbalance.check.interval.seconds=300",
        "domain": "Middleware",
        "log_pattern": "INFO ReplicaManager: Stopped fetching to leader",
    },
    {
        "fault": "Redis 主从复制中断（Replication断开）",
        "solution": "扩大 backlog 缓冲区并排查网络问题",
        "description": "Redis 主从复制因 backlog 缓冲区溢出，从库触发全量 RDB 同步，带宽打满",
        "steps": "1. redis-cli info replication 查看 master_sync_in_progress\n"
                 "2. 增大 repl-backlog-size（如 256MB）减少全量同步频率\n"
                 "3. 设置 min-slaves-to-write=1 防止主库单点写入\n"
                 "4. 检查主从网络带宽和延迟\n"
                 "5. 优化写入量，避免主库 RDB 触发时带宽突增",
        "domain": "Middleware",
        "log_pattern": "MASTER <-> SLAVE sync started",
    },
    {
        "fault": "Nginx upstream 超时（upstream timed out）",
        "solution": "调大超时参数并增加后端实例",
        "description": "Nginx 连接后端服务超时，返回 504 Gateway Timeout",
        "steps": "1. 检查 Nginx 日志确认超时来源（upstream addr）\n"
                 "2. 增大 proxy_read_timeout / proxy_connect_timeout\n"
                 "3. 检查后端服务响应时间，定位慢接口\n"
                 "4. 增加后端实例并在 upstream 配置负载均衡\n"
                 "5. 开启 keepalive 复用连接减少握手开销",
        "domain": "Network",
        "log_pattern": "upstream timed out (110: Connection timed out)",
    },
    {
        "fault": "Nginx 静态文件 permission denied",
        "solution": "修正文件权限或运行用户配置",
        "description": "Nginx 访问静态文件返回 403，日志报 permission denied",
        "steps": "1. nginx -t 确认配置无误\n"
                 "2. 查看 nginx 运行用户：ps aux | grep nginx\n"
                 "3. 确认静态文件目录权限允许 nginx 用户读取：chmod o+r\n"
                 "4. 检查 SELinux/AppArmor 是否阻止访问\n"
                 "5. 修改 nginx.conf user 为静态文件目录的属主",
        "domain": "System",
        "log_pattern": "(13: Permission denied) while reading",
    },
    {
        "fault": "Docker 容器无法启动（端口冲突）",
        "solution": "修改宿主机端口映射或停止占用端口的进程",
        "description": "docker run 时提示 bind: address already in use，容器无法绑定指定端口",
        "steps": "1. netstat -tlnp | grep <port> 查看占用进程\n"
                 "2. 停止冲突进程或修改 docker -p 映射端口\n"
                 "3. 检查是否有残留容器未完全停止：docker ps -a\n"
                 "4. 使用动态端口映射：-p 0:80 让 Docker 自动分配\n"
                 "5. 配置正确的端口分配文档防止重复",
        "domain": "Middleware",
        "log_pattern": "Error starting userland proxy: listen tcp: bind: address already in use",
    },
    {
        "fault": "容器 overlay 文件系统空间不足",
        "solution": "清理无用镜像/容器并扩展 Docker 数据目录",
        "description": "Docker 数据目录（/var/lib/docker）空间耗尽，新容器无法启动",
        "steps": "1. docker system df 查看镜像/容器/卷占用\n"
                 "2. 清理悬空资源：docker system prune -f\n"
                 "3. 删除无用镜像：docker image prune -a\n"
                 "4. 迁移 Docker 数据目录到更大磁盘\n"
                 "5. 配置 docker 日志驱动限制日志大小",
        "domain": "Storage",
        "log_pattern": "No space left on device: /var/lib/docker/overlay2",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# 生成数据文件
# ─────────────────────────────────────────────────────────────────────────────

def generate_jsonl(out_path: Path) -> int:
    records = []
    for item in LOGHUB_FAULTS:
        record = {
            "fault_name":           item["fault"],
            "solution_name":        item["solution"],
            "solution_description": item.get("description", ""),
            "steps":                item.get("steps", ""),
            "domain":               item.get("domain", ""),
            "data_source":          SOURCE,
            "confidence":           0.85,
            "import_batch_id":      BATCH_ID,
        }
        records.append(record)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"[INFO] 已生成 {len(records)} 条 LogHub 故障知识")
    print(f"[INFO] 输出文件：{out_path}")
    return len(records)


# ─────────────────────────────────────────────────────────────────────────────
# 导入到图谱
# ─────────────────────────────────────────────────────────────────────────────

def import_to_graph(records: List[Dict], api_url: str, delay: float = 0.05) -> None:
    success, failed, skipped = 0, 0, 0
    total = len(records)
    start = time.time()

    for i, rec in enumerate(records, 1):
        payload = {
            "fault_name":           rec["fault_name"],
            "solution_name":        rec["solution_name"],
            "solution_description": rec.get("solution_description", ""),
            "steps":                rec.get("steps", ""),
            "domain":               rec.get("domain", ""),
            "data_source":          rec.get("data_source", SOURCE),
            "confidence":           rec.get("confidence", 0.85),
            "import_batch_id":      rec.get("import_batch_id", BATCH_ID),
        }
        try:
            resp = requests.post(f"{api_url}/graph/add", json=payload, timeout=15)
            resp.raise_for_status()
            result = resp.json().get("edge_status", "ok")
            if result in ("created", "existing", "ok"):
                success += 1
            else:
                skipped += 1
            if i % 10 == 0 or i == total:
                print(f"[{i}/{total}] 已处理 {success} 条成功...")
        except Exception as e:
            failed += 1
            print(f"[{i}/{total}] FAIL {rec['fault_name']} -> {e}")
        if delay > 0:
            time.sleep(delay)

    elapsed = round(time.time() - start, 1)
    print("\n" + "=" * 50)
    print("LogHub 导入完成")
    print(f"  总计：{total} 条")
    print(f"  成功：{success} 条")
    print(f"  跳过：{skipped} 条")
    print(f"  失败：{failed} 条")
    print(f"  耗时：{elapsed}s")
    print(f"  批次：{BATCH_ID}")
    print("=" * 50)


# ─────────────────────────────────────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="WisOps LogHub 数据导入脚本")
    parser.add_argument("--api-url",       default="http://localhost:8021", help="graph-api 基础 URL")
    parser.add_argument("--generate-only", action="store_true",             help="仅生成 JSONL 文件，不导入")
    parser.add_argument("--dry-run",       action="store_true",             help="预览前 5 条，不写入")
    parser.add_argument("--delay",         type=float, default=0.05,        help="每条写入间隔（秒）")
    parser.add_argument("--out-file",      default=str(OUT_FILE),           help="输出 JSONL 文件路径")
    args = parser.parse_args()

    out_path = Path(args.out_file)
    count = generate_jsonl(out_path)

    if args.dry_run:
        print("\n[DRY-RUN] 前 5 条预览：")
        with open(out_path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= 5:
                    break
                rec = json.loads(line)
                print(f"  [{i+1}] {rec['fault_name']} -> {rec['solution_name']}")
        return

    if args.generate_only:
        print(f"\n[INFO] 已生成数据文件，跳过导入。运行时去掉 --generate-only 即可导入。")
        return

    print(f"\n[INFO] 开始导入到 {args.api_url} ...")
    with open(out_path, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    import_to_graph(records, args.api_url, args.delay)


if __name__ == "__main__":
    main()
