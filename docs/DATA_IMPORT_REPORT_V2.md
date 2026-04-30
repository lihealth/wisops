# WisOps V2.0 数据导入报告

> **版本**：V2.0-Beta  
> **统计日期**：2026-04-30  
> **数据环境**：本地 Docker Compose HugeGraph（`wisops_hugegraph_data` 卷）  
> **统计命令**：`GET http://localhost:8021/ops/stats`

---

## 一、图谱数据总量快照

```json
{
  "node_counts": {
    "Fault":      1432,
    "Solution":   1432,
    "Asset":        10,
    "Alert":      1448,
    "Incident":      0,
    "Category":      8,
    "SopNode":       0,
    "Document":      0
  },
  "edge_counts": {
    "HAS_SOLUTION":     1432,
    "TRIGGERS":         2048,
    "INVOLVES":            0,
    "CAUSED_BY":           0,
    "RESOLVED_BY":         0,
    "CLASSIFIED_AS":    1432,
    "DOCUMENTED_IN":       0
  },
  "incident_count":   0,
  "mttr_avg":      null
}
```

> **说明**：`Incident` / `SopNode` / `Document` 等节点数为 0，表示演示环境尚未通过 Portal 录入或与 Dify 知识库完成同步。上述数值为当前 Beta 基线；生产环境或添加实际运维数据后数值会增长。

---

## 二、数据来源清单

| 来源标识 | 描述 | 节点贡献 | 边贡献 | 导入脚本 / 方式 |
|---------|------|---------|--------|----------------|
| `open_gaia` | GAIA 公开基准数据集（故障–方案对） | Fault ≈ 1000，Solution ≈ 1000 | HAS_SOLUTION，CLASSIFIED_AS | `scripts/import_v2.py data/faults_v2.jsonl` |
| `logHub` | LogHub 可追溯故障库（含 source_file/source_line） | Fault ≈ 432，Solution ≈ 432 | HAS_SOLUTION，CLASSIFIED_AS | `scripts/import_v2.py data/loghub_traceable_faults.jsonl` |
| `gaia_assets` | GAIA 资产 + 告警模拟集 | Asset = 10，Alert = 1448 | TRIGGERS（自动同步） | `scripts/parse_gaia.py` |
| `stackoverflow` | Stack Exchange `Posts.xml`（可选；自行下载） | 按标签/分数过滤后数量不定 | HAS_SOLUTION | `scripts/import_stackoverflow.py` |
| 手工录入（Portal） | 通过 `/incidents`、`/extract` 录入或审核通过 | Incident、Fault、Solution、Document | CAUSED_BY, RESOLVED_BY, DOCUMENTED_IN | Portal 操作 / `POST /graph/add` |

---

## 三、各数据源详细说明

### 3.1 GAIA 公开数据（`open_gaia`）

**来源**：[GAIA 基准数据集](https://github.com/XXX)（内部整理为 `data/faults_v2.jsonl`）

**字段映射**：

| JSONL 字段 | 图谱字段 | 说明 |
|-----------|---------|------|
| `fault_name` | `Fault.name` | 故障标题 |
| `solution_steps` | `Solution.steps` | 处置步骤（`\n` 分隔） |
| `domain` | `Category.domain` | 故障领域 |
| `tags` | `Fault.tags` | 故障标签（逗号分隔） |

**导入命令**：

```powershell
python scripts/import_v2.py data/faults_v2.jsonl `
  --source open_gaia --entity-type Fault `
  --api-url http://localhost:8021 --batch-id restore-faults-v2
```

**验收**：`node_counts.Fault` 达到 ≥ 1000，`HAS_SOLUTION` 与 Fault 数一致。

---

### 3.2 LogHub 可追溯故障（`logHub`）

**来源**：[LogHub](https://github.com/logpai/loghub) 公开日志异常模板库，内部整理为 `data/loghub_traceable_faults.jsonl`

**附加字段（可追溯性）**：

| 字段 | 说明 |
|------|------|
| `source_file` | 原始日志文件名 |
| `source_line` | 日志行号 |
| `matched_pattern` | 匹配的异常正则模式 |

这些字段存储在 `Fault` 节点的属性中，支持 `GET /graph/context` 返回的 `source` 字段展示，实现**知识来源可追溯**。

**导入命令**：

```powershell
python scripts/import_v2.py data/loghub_traceable_faults.jsonl `
  --source logHub --entity-type Fault `
  --api-url http://localhost:8021 --batch-id restore-loghub
```

---

### 3.3 GAIA 资产与告警（`gaia_assets`）

**来源**：GAIA 数据集配套资产与监控告警模拟数据

**说明**：
- 导入 10 个 Asset 节点（服务器、网络设备、数据库实例等）
- 导入 1448 条 Alert 节点（CPU/内存/磁盘/网络告警）
- 自动建立 `Alert → TRIGGERS → Fault` 关联（通过 `POST /admin/triggers/sync`）

**导入命令**：

```powershell
python scripts/parse_gaia.py --api-url http://localhost:8021
```

**TRIGGERS 同步**：

```powershell
Invoke-RestMethod -Method POST "http://localhost:8021/admin/triggers/sync"
# confidence/method/rule_name 字段根据匹配算法自动填充
```

---

### 3.4 Stack Exchange 数据（`stackoverflow`，可选）

**来源**：[Stack Exchange Data Dump](https://archive.org/details/stackexchange)，推荐使用 `ServerFault` 站点的 `Posts.xml`

**数据规模**（ServerFault 完整包，供参考）：
- Posts.xml 约 2.5 GB
- 筛选运维相关标签（`linux`/`networking`/`server`/`docker` 等）后可获约 5 万~20 万 Q&A 对
- 按默认得分阈值（`--min-score 5`）过滤后实际入库约 1 万~5 万对

**目录结构**：

```
data/stackoverflow/
  README.md            # 使用说明
  sample_posts.xml     # 10 条本地测试样例（无需下载）
  sample_curated.jsonl # 样例输出
  Posts.xml            # 需自行下载（已加入 .gitignore）
```

**导入步骤**：

```powershell
# 1. 从 archive.org 下载 Posts.xml 放入 data/stackoverflow/

# 2. 样例验证（不需要真实文件）
python scripts/import_stackoverflow.py `
  --xml data/stackoverflow/sample_posts.xml `
  --dry-run

# 3. 实际导入（直接写图谱）
python scripts/import_stackoverflow.py `
  --xml data/stackoverflow/Posts.xml `
  --api-url http://localhost:8021 `
  --tags linux,networking,server,docker `
  --min-score 5

# 4. 验收
Invoke-RestMethod "http://localhost:8021/ops/stats" | ConvertTo-Json -Depth 3
```

**当前状态**：本地演示环境未导入完整 Posts.xml（文件 > 2GB），图谱中不含 `stackoverflow` 来源数据。用户可按需自行导入。

---

### 3.5 手工录入（Portal / API）

**入口**：
- **工单录入**：`/incidents` 页 → 录入表单 → 关联 Fault/Solution/Asset
- **知识抽取审核**：`/extract` 页 → 审核队列 → 通过后双写图谱 + Dify
- **直接 API**：`POST /graph/add`（含 `X-API-Key` 头，若已配置）

**生成的节点/边**：
- Incident 节点（含 title/status/severity/occurred_at/resolved_at）
- `Incident → CAUSED_BY → Fault`
- `Incident → RESOLVED_BY → Solution`
- `Incident → INVOLVES → Asset`
- 抽取审核通过：Fault + Solution + `HAS_SOLUTION` 边

---

## 四、全量恢复命令（顺序执行）

图谱数据丢失（`docker compose down -v` 或卷被清空）后按此顺序恢复：

```powershell
# 步骤 0：确保服务在运行
docker compose --profile graph up -d

# 步骤 1：初始化 Schema（必须最先执行）
Invoke-RestMethod -Method POST "http://localhost:8021/admin/schema/init"

# 步骤 2：导入 GAIA 故障–方案库
python scripts/import_v2.py data/faults_v2.jsonl `
  --source open_gaia --entity-type Fault `
  --api-url http://localhost:8021 --batch-id restore-faults-v2

# 步骤 3：导入 LogHub 可追溯故障
python scripts/import_v2.py data/loghub_traceable_faults.jsonl `
  --source logHub --entity-type Fault `
  --api-url http://localhost:8021 --batch-id restore-loghub

# 步骤 4：导入 GAIA 资产 + 告警
python scripts/parse_gaia.py --api-url http://localhost:8021

# 步骤 5：初始化分类树
Invoke-RestMethod -Method POST "http://localhost:8021/admin/categories/init"

# 步骤 6：同步 Alert → Fault TRIGGERS 关联
Invoke-RestMethod -Method POST "http://localhost:8021/admin/triggers/sync"

# 步骤 7：（可选）同步向量索引
Invoke-RestMethod -Method POST "http://localhost:8021/admin/fault-vectors/sync"

# 验收
Invoke-RestMethod "http://localhost:8021/ops/stats" | ConvertTo-Json -Depth 3
```

**恢复后期望值**：

| 字段 | 期望 |
|------|------|
| `node_counts.Fault` | ≥ 1430 |
| `node_counts.Solution` | ≥ 1430 |
| `node_counts.Alert` | 1448 |
| `node_counts.Asset` | 10 |
| `node_counts.Category` | 8 |
| `edge_counts.HAS_SOLUTION` | ≥ 1430 |
| `edge_counts.TRIGGERS` | ≥ 2000 |
| `edge_counts.CLASSIFIED_AS` | ≥ 1430 |

---

## 五、数据质量说明

| 维度 | 状态 | 备注 |
|------|------|------|
| **去重** | ✅ | `import_v2.py` 按 `fault_name` 哈希做 upsert，重复导入不增加节点 |
| **来源可追溯** | ✅ | 每个 Fault 节点含 `data_source` / `batch_id` / `source_file` 字段 |
| **HTML 清洗** | ✅ | Stack Exchange 脚本内置 `strip_html()`，去除 `<code>` / `<p>` 等标签 |
| **Schema 版本** | ✅ | 所有导入经过 `ensure_schema_v2()` 幂等保障 |
| **分类映射** | ⚠️ 部分 | LogHub/StackOverflow 部分条目无明确 domain，默认归入 `general` |
| **Solution 质量** | ⚠️ 人工抽样 | LLM 抽取结果已经人工审核队列二次确认，但大批量数据未全量人工复核 |

---

## 六、后续计划

| 任务 | 优先级 | 说明 |
|------|--------|------|
| 导入真实运维工单数据 | P1 | 通过 `/incidents` Portal 或 Webhook 批量写入 |
| Stack Exchange 完整导入 | P2 | 用户自备 Posts.xml，预期增加 1万~5万 Fault/Solution |
| Dify 知识库同步验证 | P1 | 确认抽取审核通过后 Dify 知识库切片数与 `_extract_doc_links` 一致 |
| 审计日志持久化 | P2 | 落库后可对导入操作进行完整追溯 |
