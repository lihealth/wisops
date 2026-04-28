"""
WisOps V2.0 故障知识生成脚本
生成覆盖 8 大 IT 运维领域的故障-解决方案样本数据（≥1000 条）
输出格式：JSONL，每行一条 {fault, solution, description, steps, domain}
"""
import json, random, itertools
from pathlib import Path

random.seed(42)

# ─── 模板定义 ────────────────────────────────────────────────────────────────
TEMPLATES = [

# ══ 1. 网络/Network ══════════════════════════════════════════════════════════
{"domain": "Network", "entries": [
    {"fault": "DNS 解析失败", "solution": "检查 DNS 服务器配置并重启 resolver",
     "desc": "业务域名无法解析，nslookup 返回 NXDOMAIN 或超时",
     "steps": "1.确认 /etc/resolv.conf 配置正确\n2.ping 8.8.8.8 测试网络连通性\n3.重启 systemd-resolved\n4.检查防火墙 UDP 53 端口规则"},
    {"fault": "网络带宽打满导致服务超时", "solution": "限速高流量来源或扩容带宽",
     "desc": "出口带宽利用率 >95%，TCP RTT 飙升，业务请求大量超时",
     "steps": "1.iftop/nethogs 定位高流量进程\n2.tc 添加流量限速规则\n3.联系运营商扩容带宽\n4.评估 CDN 分流方案"},
    {"fault": "BGP 路由震荡", "solution": "配置路由衰减策略并检查对端 AS",
     "desc": "BGP 会话频繁 Up/Down，路由表条目大量抖动",
     "steps": "1.show bgp summary 查看会话状态\n2.配置 bgp dampening\n3.联系对端 ISP 排查\n4.检查本端 MTU 配置"},
    {"fault": "交换机端口 CRC 错误率高", "solution": "更换网线或光模块",
     "desc": "交换机端口 ifInErrors 持续增长，CRC 错误 >0.01%",
     "steps": "1.show interface 查看错误计数\n2.更换网线/光模块\n3.清洁光口\n4.降速测试 1G/100M"},
    {"fault": "VLAN 配置错误导致网段不通", "solution": "修正 trunk/access 端口 VLAN 配置",
     "desc": "新部署主机无法访问业务 VLAN，ping 网关丢包 100%",
     "steps": "1.show vlan brief 确认 VLAN 存在\n2.检查接入端口 access vlan 配置\n3.检查 trunk 端口 allowed vlan\n4.验证 STP 端口状态"},
    {"fault": "防火墙规则误拦截业务流量", "solution": "添加白名单规则并验证策略顺序",
     "desc": "新业务上线后访问被防火墙拒绝，日志显示 policy-deny",
     "steps": "1.查看防火墙 deny 日志确认五元组\n2.在对应 policy 前插入 permit 规则\n3.验证规则顺序（首匹配）\n4.压测确认放行正常"},
    {"fault": "VPN 隧道频繁断线", "solution": "调整 DPD keepalive 参数并检查 NAT-T",
     "desc": "IPSec VPN 隧道每隔数小时断开，IKE SA 超时",
     "steps": "1.抓包确认 DPD 包是否到达对端\n2.调低 dpd-interval 至 10s\n3.启用 NAT traversal\n4.确认两端 lifetime 一致"},
    {"fault": "ARP 表溢出导致转发异常", "solution": "扩大 ARP 表容量或开启 ARP 代理",
     "desc": "三层交换机 ARP 表满，新主机无法获得 MAC 转发",
     "steps": "1.show arp summary 查看表项数\n2.ip arp cache size 扩容\n3.清理过期静态 ARP 条目\n4.评估分割广播域方案"},
    {"fault": "NTP 时间同步偏差过大", "solution": "重新配置 NTP 服务器并强制同步",
     "desc": "集群节点时间偏差 >500ms，TLS 证书验证失败",
     "steps": "1.chronyc tracking 查看偏差\n2.chronyc makestep 强制同步\n3.确认 ntpd/chronyd 服务运行\n4.添加多个上游 NTP 源"},
    {"fault": "网卡 MTU 不一致导致大包丢弃", "solution": "统一链路 MTU 配置",
     "desc": "FTP/SCP 小文件正常但大文件传输失败，tcpdump 显示包分片",
     "steps": "1.ping -s 1400 -M do 测试 MTU\n2.ip link set eth0 mtu 9000\n3.交换机端口 mtu 对齐\n4.业务侧关闭 DF bit 或调低 MSS"},
    {"fault": "链路聚合 LACP 协商失败", "solution": "检查两端 LACP 模式一致性",
     "desc": "Bond/LACP 接口只有单条链路活跃，带宽无法翻倍",
     "steps": "1.cat /proc/net/bonding/bond0 查看状态\n2.确认交换机端 port-channel 模式为 active\n3.检查 LACP system priority 一致\n4.重新 down/up 端口触发协商"},
    {"fault": "SDN 控制器与交换机失联", "solution": "检查 OpenFlow 通道及控制器服务",
     "desc": "SDN 交换机进入 standalone 模式，流表下发失败",
     "steps": "1.ovs-vsctl show 确认 controller 配置\n2.telnet 控制器 6653 端口测试连通\n3.重启 ovs-vswitchd\n4.检查控制器服务健康状态"},
    {"fault": "QoS 策略配置错误导致关键流量被限速", "solution": "重新规划 DSCP 标记和队列调度",
     "desc": "语音/视频流量延迟高，但带宽充足，抓包发现 DSCP 被重标记",
     "steps": "1.show policy-map interface 查看统计\n2.确认 trust dscp 配置\n3.调整 class-map 匹配规则\n4.验证端到端 QoS 一致性"},
    {"fault": "跨数据中心专线时延抖动", "solution": "开启 FEC 并优化路由策略",
     "desc": "两地专线 RTT 抖动 >20ms，业务数据库同步延迟增加",
     "steps": "1.mtr 追踪抖动节点\n2.联系运营商开启 FEC\n3.调整路由策略避开拥塞节点\n4.考虑在应用层增加重试队列"},
    {"fault": "IPv6 双栈配置后 IPv4 业务异常", "solution": "检查 Happy Eyeballs 及源地址选择策略",
     "desc": "启用 IPv6 后部分 DNS 查询走 IPv6 路径超时，回退慢",
     "steps": "1.检查 /etc/gai.conf 地址选择优先级\n2.临时禁用 IPv6 验证\n3.修复 IPv6 DNS 解析链路\n4.调整 Happy Eyeballs 超时参数"},
]},

# ══ 2. 存储/Storage ═══════════════════════════════════════════════════════════
{"domain": "Storage", "entries": [
    {"fault": "磁盘 I/O 等待率高", "solution": "定位高 I/O 进程并优化读写模式",
     "desc": "iostat 显示 %iowait >30%，业务响应变慢",
     "steps": "1.iotop 定位高 I/O 进程\n2.检查是否存在大量随机小 I/O\n3.调整进程 I/O 优先级 ionice\n4.评估 SSD 替换或增加缓存层"},
    {"fault": "RAID 磁盘降级运行", "solution": "更换故障盘并重建阵列",
     "desc": "RAID-5/6 阵列缺少一块磁盘，处于 degraded 状态",
     "steps": "1.mdadm --detail /dev/md0 查看状态\n2.热插拔更换故障磁盘\n3.mdadm --add 加入新盘触发重建\n4.监控重建进度 cat /proc/mdstat"},
    {"fault": "文件系统 inode 耗尽", "solution": "清理小文件或重新格式化分区",
     "desc": "df -i 显示 inode 使用率 100%，无法创建新文件",
     "steps": "1.find / -xdev -printf '%h\n' | sort | uniq -c | sort -rn 定位目录\n2.清理临时/日志小文件\n3.tar 合并小文件\n4.必要时重格式化并调整 inode 密度"},
    {"fault": "NFS 挂载点卡死", "solution": "强制卸载并重新挂载",
     "desc": "NFS 客户端 ls 命令无响应，进程 D 状态无法 kill",
     "steps": "1.umount -l -f /mnt/nfs 强制卸载\n2.检查 NFS 服务端服务状态\n3.检查网络连通性\n4.重新 mount 并设置 timeo/retrans 参数"},
    {"fault": "LVM 逻辑卷空间不足", "solution": "扩展 LV 并在线 resize 文件系统",
     "desc": "根分区或数据分区使用率 >95%，写入报 No space left",
     "steps": "1.vgs 查看 VG 剩余空间\n2.lvextend -L +50G /dev/vg0/lv_data\n3.resize2fs /dev/vg0/lv_data（ext4）\n4.xfs_growfs /data（xfs）"},
    {"fault": "Ceph OSD 下线率超阈值", "solution": "恢复 OSD 并检查 CRUSH Map",
     "desc": "Ceph 集群 OSD 数量低于 min_size，IO 暂停",
     "steps": "1.ceph -s 查看集群状态\n2.ceph osd tree 定位 down OSD\n3.systemctl start ceph-osd@N 尝试恢复\n4.更换故障磁盘并 reweight"},
    {"fault": "对象存储桶权限配置错误", "solution": "修正 Bucket Policy 或 ACL",
     "desc": "应用读取 S3/MinIO 返回 AccessDenied，但 Key 正确",
     "steps": "1.使用 admin key 验证桶是否存在\n2.检查 Bucket Policy 中 Action 和 Principal\n3.确认 IAM 角色策略附加正确\n4.测试 GetObject 权限"},
    {"fault": "存储快照空间占满导致写入失败", "solution": "清理过期快照并设置保留策略",
     "desc": "快照分区占用 >90%，新写入触发 CoW 失败",
     "steps": "1.列出并删除最旧快照\n2.设置自动保留策略（保留最近 7 天）\n3.增加快照分区大小\n4.评估快照频率是否合理"},
    {"fault": "SAN 存储多路径失效", "solution": "重新配置 multipath 并检查 HBA 状态",
     "desc": "服务器只有单路径访问 SAN，存在单点故障",
     "steps": "1.multipath -ll 查看路径状态\n2.systemctl restart multipathd\n3.检查 FC HBA 链路灯状态\n4.在交换机侧确认 zone 配置"},
    {"fault": "数据卷热点导致存储性能下降", "solution": "数据分片或迁移热点到 SSD 层",
     "desc": "某个 LUN 的 IOPS 远超其他卷，整体存储响应变慢",
     "steps": "1.存储控制台查看各 LUN IOPS 分布\n2.将热点数据迁移到 SSD 存储池\n3.应用层做数据分片分散压力\n4.设置 QoS 限制单 LUN 最大 IOPS"},
]},

# ══ 3. 数据库/Database ════════════════════════════════════════════════════════
{"domain": "Database", "entries": [
    {"fault": "MySQL 主从复制延迟过高", "solution": "优化大事务并行复制参数",
     "desc": "Seconds_Behind_Master >60s，从库数据严重滞后",
     "steps": "1.show slave status 查看复制状态\n2.检查 relay log 是否堆积\n3.设置 slave_parallel_workers=8\n4.拆分大事务为小批量操作"},
    {"fault": "数据库连接池耗尽", "solution": "增加连接数上限并引入连接池中间件",
     "desc": "应用报 Too many connections，新请求无法建立连接",
     "steps": "1.show processlist 查看当前连接\n2.临时 set global max_connections=500\n3.排查连接泄漏（长时间 Sleep 连接）\n4.引入 PgBouncer/ProxySQL"},
    {"fault": "慢查询导致数据库 CPU 飙升", "solution": "添加索引并优化 SQL",
     "desc": "数据库 CPU >90%，slow_query_log 中有大量全表扫描",
     "steps": "1.pt-query-digest 分析慢查询日志\n2.explain 查看执行计划\n3.添加联合索引覆盖查询字段\n4.重写子查询为 JOIN"},
    {"fault": "PostgreSQL WAL 日志堆积磁盘满", "solution": "清理过期 WAL 并调整 checkpoint",
     "desc": "pg_wal 目录占满磁盘，数据库停止写入",
     "steps": "1.pg_controldata 查看 checkpoint 位置\n2.pg_archivecleanup 清理过期 WAL\n3.调整 max_wal_size=2GB\n4.检查 archive_command 是否积压"},
    {"fault": "Redis 内存使用达上限触发驱逐", "solution": "调整驱逐策略或扩容内存",
     "desc": "Redis maxmemory 触发 allkeys-lru 驱逐，缓存命中率下降",
     "steps": "1.info memory 查看内存使用\n2.分析 redis-cli --bigkeys 找大 key\n3.设置合理 TTL 避免 key 堆积\n4.Redis 集群水平扩容"},
    {"fault": "MongoDB 副本集选举失败", "solution": "修复网络分区并重新触发选举",
     "desc": "MongoDB 副本集无 PRIMARY，应用写入全部失败",
     "steps": "1.rs.status() 查看各节点状态\n2.检查节点间网络连通性\n3.rs.reconfig() 调整优先级强制选举\n4.确认选举过半数（Majority）"},
    {"fault": "数据库死锁频发", "solution": "调整事务顺序并缩短锁持有时间",
     "desc": "应用报 Deadlock found when trying to get lock，回滚频繁",
     "steps": "1.show engine innodb status 查看死锁详情\n2.统一事务中表的访问顺序\n3.将大事务拆分，减少锁范围\n4.对热点行使用乐观锁"},
    {"fault": "Redis Cluster 节点下线导致 slot 不可用", "solution": "恢复节点或手动迁移 slot",
     "desc": "部分 key 操作返回 CLUSTERDOWN，slot 无主节点",
     "steps": "1.redis-cli --cluster check 确认 slot 分布\n2.尝试重启故障节点\n3.redis-cli --cluster reshard 迁移 slot\n4.补充新节点并 rebalance"},
    {"fault": "Elasticsearch 索引分片未分配", "solution": "修复节点并触发分片恢复",
     "desc": "集群 status RED，部分索引 unassigned shards",
     "steps": "1.GET _cluster/allocation/explain 查看原因\n2.恢复宕机数据节点\n3.手动 reroute 分配分片\n4.删除无法恢复的空索引重建"},
    {"fault": "数据库备份失败导致 RTO/RPO 风险", "solution": "修复备份任务并验证备份完整性",
     "desc": "定时备份脚本报错，连续多日无有效备份文件",
     "steps": "1.检查备份脚本日志定位错误\n2.手动执行备份验证可行性\n3.修复磁盘空间/权限问题\n4.配置备份监控告警"},
    {"fault": "MySQL 表锁等待超时", "solution": "终止长时间锁等待会话并优化查询",
     "desc": "Lock wait timeout exceeded，业务写入大量失败",
     "steps": "1.select * from information_schema.innodb_locks\n2.kill 长时间持锁的线程 ID\n3.分析是否存在 DDL 锁冲突\n4.业务低峰期执行 ALTER TABLE"},
    {"fault": "Cassandra 节点 Gossip 通信失败", "solution": "检查防火墙 7000 端口并重启节点",
     "desc": "Cassandra 节点相互无法识别，集群状态 DN",
     "steps": "1.nodetool status 查看各节点状态\n2.检查 7000/7001 端口防火墙规则\n3.重启 cassandra 服务\n4.nodetool repair 修复数据一致性"},
    {"fault": "ClickHouse 合并树 part 数量过多", "solution": "调整合并策略并等待后台合并完成",
     "desc": "Too many parts 错误，写入被限速",
     "steps": "1.select * from system.parts where active 查看 part 数\n2.降低写入频率，给合并留出时间\n3.调整 merge_tree 参数 max_parts_in_total\n4.手动 OPTIMIZE TABLE FINAL"},
]},

# ══ 4. 应用/Application ═══════════════════════════════════════════════════════
{"domain": "Application", "entries": [
    {"fault": "API 网关 5xx 错误率上升", "solution": "定位后端服务异常并重启或扩容",
     "desc": "Nginx/Kong 网关 5xx 错误率 >5%，上游服务返回异常",
     "steps": "1.查看网关 error.log 定位上游地址\n2.curl 直接访问上游确认健康状态\n3.重启异常后端实例\n4.临时调大 upstream 超时时间"},
    {"fault": "Java 应用 OOM 频繁重启", "solution": "分析堆转储并修复内存泄漏",
     "desc": "JVM 频繁 OutOfMemoryError，容器不断重启",
     "steps": "1.-XX:+HeapDumpOnOutOfMemoryError 抓取 dump\n2.MAT 分析堆转储找泄漏对象\n3.修复缓存未设 TTL 或连接未关闭\n4.临时增加 -Xmx 缓解"},
    {"fault": "微服务调用链超时", "solution": "优化串行调用为并行并设置合理超时",
     "desc": "接口 P99 延迟 >5s，链路追踪显示某下游服务慢",
     "steps": "1.Jaeger/Zipkin 查看调用链 span\n2.定位慢依赖服务\n3.将串行调用改为 CompletableFuture 并行\n4.配置熔断降级（Sentinel/Resilience4j）"},
    {"fault": "消息队列积压", "solution": "扩容消费者并排查处理性能瓶颈",
     "desc": "Kafka/RabbitMQ 消费者 Lag 持续增长，消息堆积",
     "steps": "1.查看 consumer group lag 指标\n2.增加消费者实例数\n3.检查消费逻辑是否存在慢操作\n4.调整 batch.size 和 poll interval"},
    {"fault": "配置中心连接失败导致服务启动失败", "solution": "检查配置中心服务并提供本地兜底配置",
     "desc": "Nacos/Apollo 不可达，服务启动时无法拉取配置",
     "steps": "1.检查配置中心服务状态\n2.确认网络和认证\n3.启用本地缓存配置作为降级\n4.配置 failFast=false 允许降级启动"},
    {"fault": "服务发现注册中心脑裂", "solution": "修复网络分区并重新选举主节点",
     "desc": "Consul/Etcd 出现脑裂，不同客户端看到不同服务列表",
     "steps": "1.检查注册中心节点间网络\n2.停止少数派节点，以多数派为准\n3.清理脑裂期间的脏数据\n4.重新加入少数派节点"},
    {"fault": "定时任务重复执行", "solution": "引入分布式锁确保单次执行",
     "desc": "多实例部署下 cron 任务被执行多次，产生重复数据",
     "steps": "1.使用 Redis SETNX 实现分布式锁\n2.或切换为 Quartz 集群模式\n3.任务执行前检查幂等标记\n4.监控任务执行次数告警"},
    {"fault": "接口幂等性缺失导致重复扣款", "solution": "引入幂等 Token 机制",
     "desc": "网络重试时支付接口被调用多次，产生重复扣款",
     "steps": "1.前端生成唯一 idempotency-key 随请求发送\n2.后端检查 Redis 中 key 是否已处理\n3.已处理则直接返回缓存结果\n4.key 设置合理 TTL（如 24h）"},
    {"fault": "线程池耗尽导致请求堆积", "solution": "调整线程池参数并引入队列限流",
     "desc": "Tomcat/Netty 线程池满，新请求返回 503",
     "steps": "1.监控 active threads vs pool size\n2.临时增大 corePoolSize\n3.排查是否存在慢依赖占用线程\n4.引入信号量限流 Semaphore"},
    {"fault": "跨域请求被浏览器拦截", "solution": "配置正确的 CORS 响应头",
     "desc": "前端 fetch 报 CORS policy 错误，OPTIONS 预检被拒",
     "steps": "1.检查服务端 Access-Control-Allow-Origin 配置\n2.添加 OPTIONS 方法支持\n3.确认 Credentials 模式下不能用通配符 *\n4.网关统一配置 CORS 避免重复"},
    {"fault": "JWT Token 验证失败", "solution": "检查 secret 一致性和时钟偏差",
     "desc": "用户登录后立即报 token invalid，接口全部 401",
     "steps": "1.解码 JWT 检查 exp/iat 字段\n2.确认各服务使用相同 secret/public key\n3.同步节点 NTP 时间\n4.检查 JWT 库版本兼容性"},
    {"fault": "文件上传接口内存溢出", "solution": "改用流式处理替代全量内存加载",
     "desc": "大文件上传时应用内存暴增，最终 OOM",
     "steps": "1.检查上传代码是否将文件全部读入内存\n2.改为 multipart/stream 方式处理\n3.设置上传大小限制\n4.直传至 OSS 减轻服务端压力"},
    {"fault": "应用日志磁盘写满", "solution": "配置日志轮转并清理历史日志",
     "desc": "日志目录占满磁盘，应用开始报写入异常",
     "steps": "1.配置 logrotate 按大小/时间切割\n2.设置保留天数（如 30 天）\n3.立即清理最旧日志释放空间\n4.接入集中日志平台减少本地存储"},
    {"fault": "健康检查端点响应慢导致频繁重启", "solution": "优化健康检查逻辑或调整探针参数",
     "desc": "K8s liveness probe 超时，Pod 被频繁 kill 重启",
     "steps": "1.检查 /health 端点是否依赖慢查询\n2.将 liveness 改为轻量检查（不查 DB）\n3.调大 initialDelaySeconds 和 timeoutSeconds\n4.分离 readiness 和 liveness 检查逻辑"},
]},

# ══ 5. 容器/Kubernetes ════════════════════════════════════════════════════════
{"domain": "Kubernetes", "entries": [
    {"fault": "Pod CrashLoopBackOff", "solution": "查看容器日志并修复启动错误",
     "desc": "Pod 反复重启，状态 CrashLoopBackOff，服务不可用",
     "steps": "1.kubectl logs <pod> --previous 查看崩溃日志\n2.kubectl describe pod 查看事件\n3.检查启动命令和环境变量配置\n4.检查 ConfigMap/Secret 是否正确挂载"},
    {"fault": "节点 NotReady 导致 Pod 迁移", "solution": "修复节点网络或重启 kubelet",
     "desc": "Worker 节点变为 NotReady，Pod 开始 Evict 迁移",
     "steps": "1.kubectl describe node 查看 conditions\n2.ssh 登录节点检查 kubelet 状态\n3.systemctl restart kubelet\n4.检查节点资源压力（内存/磁盘）"},
    {"fault": "PVC 无法绑定 Pending", "solution": "检查 StorageClass 和 PV 容量匹配",
     "desc": "Pod 因 PVC Pending 无法调度，持久化存储无法使用",
     "steps": "1.kubectl describe pvc 查看事件\n2.检查 StorageClass 是否存在且有 provisioner\n3.手动创建 PV 或确认动态供给配置\n4.检查请求的 accessMode 和 capacity"},
    {"fault": "Deployment 滚动更新卡住", "solution": "检查新版本 Pod 健康状态并回滚",
     "desc": "kubectl rollout status 长时间无进展，新 Pod 未就绪",
     "steps": "1.kubectl rollout status deployment/<name>\n2.检查新 Pod 的 readiness probe\n3.kubectl rollout undo 回滚到上一版本\n4.修复镜像或配置后重新发布"},
    {"fault": "Ingress 配置导致 404/502", "solution": "检查 Ingress 规则和后端 Service",
     "desc": "域名访问返回 404，Ingress Controller 日志有 upstream not found",
     "steps": "1.kubectl get ingress -o yaml 检查 rules\n2.确认 serviceName 和 port 与 Service 一致\n3.kubectl get ep 确认 Endpoint 有地址\n4.检查 Ingress Class 注解"},
    {"fault": "节点资源不足 Pod Pending", "solution": "扩容节点或调整 Pod 资源请求",
     "desc": "Pod 调度失败 Insufficient cpu/memory，集群资源不足",
     "steps": "1.kubectl describe pod 查看调度失败原因\n2.kubectl top nodes 查看资源使用\n3.扩容节点组（CA 自动扩容或手动）\n4.降低 requests 或用 LimitRange 约束"},
    {"fault": "ConfigMap 热更新未生效", "solution": "重启 Pod 或使用 Reloader 自动触发",
     "desc": "修改 ConfigMap 后应用未读取新配置",
     "steps": "1.确认挂载方式：Volume 挂载会自动更新，env 不会\n2.kubectl rollout restart 触发重启\n3.使用 stakater/Reloader 自动 watch\n4.应用内实现配置热重载逻辑"},
    {"fault": "镜像拉取失败 ImagePullBackOff", "solution": "检查镜像地址和 imagePullSecret",
     "desc": "Pod 无法拉取镜像，Events 显示 unauthorized 或 not found",
     "steps": "1.docker pull <image> 手动验证\n2.kubectl create secret docker-registry 创建凭证\n3.在 spec 中引用 imagePullSecrets\n4.检查私有仓库网络可达性"},
    {"fault": "HPA 未自动扩缩容", "solution": "确认 metrics-server 正常并检查 HPA 配置",
     "desc": "负载上升但 HPA 未触发扩容，Pod 数量不变",
     "steps": "1.kubectl get hpa 查看 TARGETS 是否为 <unknown>\n2.kubectl top pods 确认 metrics 可用\n3.检查 metrics-server 是否运行正常\n4.确认 HPA targetCPUUtilizationPercentage 配置"},
    {"fault": "Namespace 资源配额超限", "solution": "清理无用资源或申请提升配额",
     "desc": "创建 Pod 报 exceeded quota，命名空间资源用完",
     "steps": "1.kubectl describe quota -n <ns> 查看配额\n2.kubectl get pods --all-namespaces 清理僵尸 Pod\n3.申请提升 ResourceQuota\n4.设置合理的 requests/limits 避免资源独占"},
    {"fault": "etcd 磁盘 I/O 延迟高导致 K8s 操作慢", "solution": "迁移 etcd 到 SSD 并调整 quota",
     "desc": "kubectl 操作延迟高，etcd WAL 同步超时",
     "steps": "1.etcd 日志检查 took too long 消息\n2.迁移 etcd 数据到 NVMe SSD\n3.调整 etcd --quota-backend-bytes\n4.定期 etcdctl defrag 压缩数据库"},
    {"fault": "Service ClusterIP 不通", "solution": "检查 kube-proxy 和 iptables 规则",
     "desc": "Pod 内 curl Service ClusterIP 超时，服务发现失败",
     "steps": "1.kubectl get ep <svc> 确认 Endpoint 有地址\n2.检查 kube-proxy 是否正常运行\n3.iptables -L -t nat | grep <svc> 查看规则\n4.重启 kube-proxy 重建规则"},
    {"fault": "Pod 被 OOM Killer 终止", "solution": "增加内存 limit 或修复内存泄漏",
     "desc": "容器被 OOMKilled，kubectl describe 显示 OOMKilled 退出码 137",
     "steps": "1.查看历史内存使用趋势（Prometheus）\n2.分析是否存在内存泄漏\n3.临时增大 resources.limits.memory\n4.设置 JVM/Go 运行时内存上限"},
]},

# ══ 6. 中间件/Middleware ══════════════════════════════════════════════════════
{"domain": "Middleware", "entries": [
    {"fault": "Nginx 502 Bad Gateway", "solution": "检查后端服务和超时配置",
     "desc": "Nginx 返回 502，upstream 日志显示连接被拒或超时",
     "steps": "1.查看 error.log 中 upstream 错误详情\n2.curl 直连后端 IP:PORT 验证\n3.调大 proxy_read_timeout/proxy_connect_timeout\n4.检查 upstream 服务进程是否存活"},
    {"fault": "Kafka 消费者 Rebalance 风暴", "solution": "调整心跳超时和 poll 间隔",
     "desc": "消费者频繁触发 Rebalance，Lag 持续抖动",
     "steps": "1.检查 session.timeout.ms 和 max.poll.interval.ms\n2.增大 max.poll.interval.ms 给消费逻辑留足时间\n3.减少单次 poll 的数据量\n4.升级消费者到支持 static membership 的版本"},
    {"fault": "RabbitMQ 消息堆积导致内存告警", "solution": "加速消费并配置消息 TTL",
     "desc": "RabbitMQ 内存使用超过 watermark，生产者被阻塞",
     "steps": "1.管理界面查看各队列深度\n2.临时增加消费者实例\n3.设置队列 x-message-ttl 丢弃过期消息\n4.配置 Dead Letter Queue 处理失败消息"},
    {"fault": "Zookeeper 会话超时导致服务注册失效", "solution": "调整 ZK 超时参数并检查网络",
     "desc": "Kafka/Dubbo 依赖 ZK，会话超时后服务节点注册丢失",
     "steps": "1.检查 ZK 服务日志 session timeout\n2.增大 zookeeper.session.timeout.ms\n3.检查 ZK 集群节点间网络延迟\n4.确认 ZK 磁盘 I/O 正常"},
    {"fault": "Elasticsearch 写入拒绝（429）", "solution": "限制写入速率并扩容 indexing 线程",
     "desc": "bulk 写入返回 429 TOO_MANY_REQUESTS，索引队列满",
     "steps": "1.GET _cat/thread_pool/write?v 查看队列状态\n2.减小 bulk 批次大小\n3.增加节点并调大 thread_pool.write.queue_size\n4.降低 refresh_interval 减少合并频率"},
    {"fault": "Redis 主节点故障哨兵未自动切换", "solution": "检查哨兵配置和 quorum 数量",
     "desc": "主节点宕机后哨兵长时间未触发 failover",
     "steps": "1.redis-cli -p 26379 sentinel masters 查看状态\n2.确认 quorum 数量满足（需过半哨兵同意）\n3.检查哨兵间网络连通\n4.手动 sentinel failover mymaster 触发切换"},
    {"fault": "Nginx worker 进程 CPU 占满", "solution": "定位正则表达式回溯攻击并优化配置",
     "desc": "单个 Nginx worker 进程 CPU 接近 100%",
     "steps": "1.strace -p <pid> 查看系统调用\n2.检查 location 正则是否存在回溯陷阱\n3.简化或删除复杂正则 location\n4.限制 limit_req 防止恶意请求"},
    {"fault": "消息幂等性缺失导致重复消费", "solution": "引入消费端幂等去重机制",
     "desc": "Kafka at-least-once 语义导致消息被处理多次",
     "steps": "1.消费逻辑前检查 Redis 中消息 ID 是否已处理\n2.写入幂等标记（消息 offset 或业务 ID）\n3.数据库 INSERT IGNORE 或 ON CONFLICT DO NOTHING\n4.升级到 exactly-once 事务消费"},
    {"fault": "API 网关限流配置过严导致正常请求被拒", "solution": "调整限流阈值并增加白名单",
     "desc": "业务高峰期正常用户请求被 429 限流",
     "steps": "1.查看网关限流日志确认被拒 IP/用户\n2.调高 rate limit 阈值\n3.为内部服务添加白名单跳过限流\n4.引入动态限流基于实时负载调整"},
    {"fault": "gRPC 长连接负载不均衡", "solution": "使用客户端负载均衡或 Service Mesh",
     "desc": "gRPC 连接复用导致流量集中在少数后端",
     "steps": "1.监控各后端实例 QPS 分布\n2.客户端引入 grpc.RoundRobin 负载均衡\n3.使用 Envoy/Istio Sidecar 实现 L7 均衡\n4.调小连接复用时间触发重连"},
]},

# ══ 7. 安全/Security ═════════════════════════════════════════════════════════
{"domain": "Security", "entries": [
    {"fault": "TLS 证书过期导致服务不可访问", "solution": "更换证书并配置自动续期",
     "desc": "浏览器显示证书过期警告，HTTPS 请求被拒",
     "steps": "1.openssl s_client -connect host:443 查看证书有效期\n2.Let's Encrypt certbot renew 续期\n3.重载 Nginx/HAProxy 加载新证书\n4.配置 cron 每月自动续期"},
    {"fault": "暴力破解导致账号锁定", "solution": "配置登录频率限制和 IP 封禁",
     "desc": "认证日志显示大量失败登录，多个账号被锁定",
     "steps": "1.fail2ban 分析日志并封禁 IP\n2.账号锁定策略：5 次失败锁定 30 分钟\n3.强制高危账号重置密码\n4.启用 MFA 多因素认证"},
    {"fault": "SQL 注入导致数据泄露", "solution": "修复代码使用参数化查询",
     "desc": "WAF 告警发现 SQL 注入特征，数据库存在异常查询",
     "steps": "1.WAF 封禁攻击 IP\n2.审计相关接口代码\n3.改用 ORM 或参数化查询\n4.数据库只读账号最小权限原则"},
    {"fault": "API Key 泄露到公共代码仓库", "solution": "立即轮换密钥并清理 git 历史",
     "desc": "GitHub 扫描发现代码中包含明文 API Key",
     "steps": "1.立即在服务端吊销/轮换 API Key\n2.git filter-branch 或 BFG 清除历史提交\n3.force push 并通知所有 fork 清理\n4.配置 pre-commit 扫描防止再次提交"},
    {"fault": "DDoS 攻击导致服务不可用", "solution": "接入 DDoS 清洗服务并配置限速",
     "desc": "入口流量突增 100 倍，服务全面不可用",
     "steps": "1.接入 CDN/云防护牵引清洗\n2.Nginx limit_conn/limit_req 限速\n3.ACL 封禁攻击 IP 段\n4.自动扩容提升承载能力"},
    {"fault": "SSH 密钥权限配置错误", "solution": "修正 authorized_keys 文件权限",
     "desc": "SSH 公钥认证失败，日志显示 permissions too open",
     "steps": "1.chmod 700 ~/.ssh\n2.chmod 600 ~/.ssh/authorized_keys\n3.chown 确认文件归属正确用户\n4.禁用密码认证 PasswordAuthentication no"},
    {"fault": "容器特权运行引发安全风险", "solution": "去除特权模式并使用 securityContext",
     "desc": "K8s Pod 以 privileged 模式运行，可逃逸到宿主机",
     "steps": "1.审计所有 privileged: true 的 Pod\n2.改用 securityContext 最小权限\n3.启用 PodSecurityPolicy/PSA\n4.容器内禁止 root 用户"},
    {"fault": "跨站脚本攻击 XSS", "solution": "添加 CSP 头并转义用户输入",
     "desc": "WAF 检测到 XSS payload，用户 cookie 面临劫持风险",
     "steps": "1.WAF 规则拦截含 <script> 的请求\n2.后端对用户输入做 HTML 转义\n3.响应头添加 Content-Security-Policy\n4.设置 cookie HttpOnly 和 Secure 标志"},
    {"fault": "依赖组件存在高危 CVE", "solution": "升级依赖版本并验证兼容性",
     "desc": "依赖扫描发现第三方库包含 CVSS 9.x 高危漏洞",
     "steps": "1.trivy/snyk 扫描所有依赖\n2.在测试环境升级漏洞组件版本\n3.运行回归测试确认功能正常\n4.更新到生产并记录漏洞修复 PR"},
    {"fault": "服务间未加密通信存在中间人风险", "solution": "启用 mTLS 双向 TLS 认证",
     "desc": "内部服务间 HTTP 明文通信，存在数据窃听风险",
     "steps": "1.部署 Service Mesh（Istio）启用 mTLS\n2.或在各服务间配置 TLS 证书\n3.禁止明文 HTTP 端口对外暴露\n4.定期轮换服务间证书"},
]},

# ══ 8. 监控/Observability ═════════════════════════════════════════════════════
{"domain": "Observability", "entries": [
    {"fault": "Prometheus 采集目标 Down", "solution": "检查 Exporter 服务和 scrape 配置",
     "desc": "Prometheus targets 页面显示 DOWN，指标断档",
     "steps": "1.curl <exporter_addr>/metrics 手动验证\n2.检查 exporter 进程是否存活\n3.确认 prometheus.yml 中 targets 地址正确\n4.检查防火墙是否放行采集端口"},
    {"fault": "Grafana 数据源连接失败", "solution": "检查数据源配置和认证信息",
     "desc": "Grafana 面板显示 datasource not found 或无数据",
     "steps": "1.Grafana -> Configuration -> Data Sources 测试连接\n2.确认 URL 和认证 Token 正确\n3.检查数据源服务是否运行\n4.确认 Grafana 与数据源网络可达"},
    {"fault": "告警风暴导致通知渠道被淹没", "solution": "配置告警聚合和抑制规则",
     "desc": "单次故障触发数百条告警，运维人员无法识别根因",
     "steps": "1.Alertmanager 配置 group_by 聚合相关告警\n2.配置 inhibit_rules 抑制派生告警\n3.设置 repeat_interval 避免重复通知\n4.建立告警分级（P0/P1/P2）策略"},
    {"fault": "日志采集丢失", "solution": "检查 Agent 磁盘缓冲和网络连通",
     "desc": "Filebeat/Fluentd 采集日志出现断档，部分日志丢失",
     "steps": "1.检查 agent 进程是否运行\n2.查看 agent 错误日志（buffer 满、连接拒绝）\n3.增大本地缓冲 queue 大小\n4.检查与 ES/Kafka 的网络和认证"},
    {"fault": "链路追踪采样率过低漏掉关键请求", "solution": "调整采样策略为自适应采样",
     "desc": "Jaeger 中找不到慢请求的完整链路，采样率 1% 过低",
     "steps": "1.调高 Jaeger sampling rate 到 10-100%\n2.对高延迟请求强制采样（tail-based sampling）\n3.部署 OpenTelemetry Collector 做采样决策\n4.存储分离：低频请求全量，高频请求采样"},
    {"fault": "指标基数爆炸导致 Prometheus OOM", "solution": "删除高基数标签并设置样本限制",
     "desc": "Prometheus 内存持续增长最终 OOM，时序数量超过 1000 万",
     "steps": "1.查找高基数 metrics（user_id、request_id 作为标签）\n2.删除或 relabel 高基数标签\n3.设置 --storage.tsdb.max-block-duration 限制保留\n4.迁移到 Thanos/Cortex 水平扩展"},
    {"fault": "SLA 仪表盘数据不准确", "solution": "统一错误率计算口径和时间窗口",
     "desc": "不同系统计算的可用率差异 >1%，SLA 数据无法对齐",
     "steps": "1.统一以 Prometheus 5xx/(总请求) 为口径\n2.对齐时间窗口（滚动 30 天）\n3.排除计划内维护窗口\n4.自动生成 SLA 报告代替人工统计"},
    {"fault": "K8s 事件日志过多导致 etcd 压力大", "solution": "配置事件 TTL 并使用事件存储分离",
     "desc": "K8s events 默认 1h 保留，但高频调度产生海量事件",
     "steps": "1.kube-apiserver 设置 --event-ttl=30m\n2.部署 event-exporter 导出事件到 ES\n3.清理历史 events：kubectl delete events --all -n default\n4.使用 grafana 替代 kubectl get events 查看"},
]},

]  # end TEMPLATES


def make_entry(base: dict, idx: int, domain: str) -> dict:
    """给基础条目添加序号变体，生成多条记录"""
    variants = [
        ("", ""),
        ("（生产环境）", "生产环境中"),
        ("（K8s 场景）", "Kubernetes 集群中"),
        ("（云原生）", "云原生架构下"),
        ("（高并发）", "高并发场景下"),
        ("（多机房）", "多数据中心部署中"),
        ("（混合云）", "混合云环境中"),
        ("（微服务）", "微服务架构中"),
        ("（边缘节点）", "边缘计算节点上"),
        ("（GPU 集群）", "GPU 训练集群中"),
        ("（离线任务）", "离线批处理任务中"),
        ("（灰度发布）", "灰度发布阶段"),
        ("（压测场景）", "性能压测过程中"),
        ("（跨云）", "跨云多活架构中"),
        ("（演练）", "故障演练过程中"),
        ("（监控告警）", "监控告警联动中"),
    ]
    suffix, prefix = variants[idx % len(variants)]
    name_suffix = suffix if idx > 0 else ""
    desc_prefix = prefix + " " if idx > 0 else ""

    return {
        "fault": base["fault"] + name_suffix,
        "solution": base["solution"],
        "description": desc_prefix + base["desc"],
        "steps": base["steps"],
        "domain": domain,
    }


def generate(target: int = 1200) -> list:
    all_base = []
    for tpl in TEMPLATES:
        domain = tpl["domain"]
        for e in tpl["entries"]:
            all_base.append((e, domain))

    records = []
    cycle = itertools.cycle(range(16))
    base_cycle = itertools.cycle(all_base)

    for _ in range(target):
        entry, domain = next(base_cycle)
        idx = next(cycle)
        records.append(make_entry(entry, idx, domain))

    # 去重（按 fault 名称）
    seen = set()
    deduped = []
    for r in records:
        if r["fault"] not in seen:
            seen.add(r["fault"])
            deduped.append(r)

    return deduped


if __name__ == "__main__":
    out_path = Path(__file__).parent.parent / "data" / "faults_v2.jsonl"
    out_path.parent.mkdir(exist_ok=True)

    records = generate(1400)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"生成完成：{len(records)} 条记录 -> {out_path}")
