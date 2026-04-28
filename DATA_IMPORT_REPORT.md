# WisOps 数据导入报告

> 更新时间：2026-04-28

---

## 图谱数据导入

### 批次一：faults_sample.json（基础样本）

| 项目 | 数值 |
|------|------|
| 源文件 | `data/faults_sample.json` |
| 总解析条数 | 10 |
| 有效条数 | 10 |
| 导入成功 | 10 |
| 导入失败 | 0 |
| 导入时间 | 2026-04-28 |
| 导入命令 | `python import_faults.py faults_sample.json --api-url http://localhost:8000/graph/add` |

### 批次二：faults_extended.json（扩展数据集）

| 项目 | 数值 |
|------|------|
| 源文件 | `data/faults_extended.json` |
| 总解析条数 | 99 |
| 有效条数 | 99 |
| 导入成功 | 99 |
| 导入失败 | 0 |
| 导入时间 | 2026-04-28 |
| 导入命令 | `python import_faults.py faults_extended.json --api-url http://localhost:8000/graph/add` |

### 汇总

| 项目 | 数值 |
|------|------|
| **故障节点总数** | **≥ 100**（满足 PRD 要求）|
| **导入成功率** | **100%** |
| 数据覆盖领域 | Linux 系统、数据库、K8s、中间件、监控、CI/CD、网络、安全 |

---

## 数据覆盖领域

| 领域 | 代表故障 |
|------|----------|
| Linux 系统 | CPU告警、磁盘空间不足、文件描述符耗尽、TCP连接数过高 |
| 数据库 | MySQL连接数过高、PostgreSQL锁等待、数据库主库宕机 |
| K8s / 容器 | Pod Pending、CrashLoopBackOff、节点NotReady、容器OOMKilled |
| 中间件 | Kafka消息积压、RabbitMQ队列积压、Redis内存告警、Zookeeper选举异常 |
| 监控告警 | Prometheus采集失败、Grafana数据源连接失败、告警风暴 |
| CI/CD | Jenkins构建堆积、ArgoCD同步失败、Harbor镜像扫描失败 |
| 网络 | DNS解析失败、网络连接超时、CDN缓存异常、WebSocket断开 |
| 安全 | SSL证书过期、证书链不完整、Token过期、权限不足 |

---

## 知识库数据（Dify）

| 项目 | 状态 |
|------|------|
| stackoverflow_qa.txt | 已导入，问答验证通过 |
| 目标片段数 | ≥ 500（待扩量） |

---

## 备注

- 图谱数据通过 `scripts/import_faults.py` 批量导入，支持 JSON/CSV/TXT 三种格式
- 重复录入幂等处理，不会产生重复边
- 数据存储在 `hugegraph_data` Docker 卷中，重启容器不丢失
