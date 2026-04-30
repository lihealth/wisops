# WisOps V2.0 产品需求文档（PRD）

> 文档版本：v1.0  
> 创建时间：2026-04-28  
> 编写依据：WisOps V1.x 现状、浪潮 IT 运维知识图谱落地思路（内部参考文档）、V1.0 PRD & 进度看板  
> 阅读对象：研发、测试、运营、交付  

---

## 目录

1. [版本定位与背景](#1-版本定位与背景)
2. [用户角色](#2-用户角色)
3. [功能模块总览](#3-功能模块总览)
4. [功能详细说明](#4-功能详细说明)
  - 4.1 [SCH — 图谱本体 2.0](#41-sch--图谱本体-20)
  - 4.2 [DATA — 公开数据与混合知识库](#42-data--公开数据与混合知识库)
  - 4.3 [EXT — 动态构建与知识自动沉淀](#43-ext--动态构建与知识自动沉淀)
  - 4.4 [RETR — 图谱增强检索与相似推荐](#44-retr--图谱增强检索与相似推荐)
  - 4.5 [PORTAL — 统一门户 V2](#45-portal--统一门户-v2)
  - 4.6 [INT — 外部系统集成](#46-int--外部系统集成)
  - 4.7 [OPS — 知识运营与看板](#47-ops--知识运营与看板)
  - 4.8 [SEC — 权限、审计与安全收口](#48-sec--权限审计与安全收口)
5. [系统架构](#5-系统架构)
6. [图谱 Schema 规范](#6-图谱-schema-规范)
7. [接口规范](#7-接口规范)
8. [数据规范](#8-数据规范)
9. [非功能性需求](#9-非功能性需求)
10. [交付物清单](#10-交付物清单)
11. [路线图](#11-路线图)
12. [验收标准](#12-验收标准)
13. [风险与依赖](#13-风险与依赖)

---

## 1. 版本定位与背景

### 1.1 V1.x 现状回顾

WisOps V1.x 已完成以下能力：


| 能力                                                           | 状态   |
| ------------------------------------------------------------ | ---- |
| Dify RAG 知识库问答（流式输出 + 知识引用）                                  | ✅ 可用 |
| 故障–方案二部图（Fault / Solution / HAS_SOLUTION）                    | ✅ 可用 |
| graph-api REST 接口（health / add / query / faults / visualize） | ✅ 可用 |
| wisops-portal 统一门户（问答 + 图谱管理 + 轻量可视化）                        | ✅ 可用 |
| Docker Compose 一键部署                                          | ✅ 可用 |


**V1.x 主要瓶颈**：图谱模型过于简单（仅二部图）、RAG 与图谱割裂（未融合推理）、缺乏知识自动沉淀与运营闭环、无外部系统集成能力。

### 1.2 V2.0 核心目标

基于「**知识少、工单少、开源起步**」的现实约束，按照以下路径演进：

```
开源骨架（已有）→ 公开数据打底 → 自有数据替换与增强 → 闭环沉淀与智能推荐
```

V2.0 实现从「**能用**」到「**可运营、可闭环、带轻量推理与推荐**」的跨越，对标行业友商的动态构建、故障推理、知识自动沉淀三项核心能力，且保持**零外部 SaaS 依赖、本地私有化**的定位。

### 1.3 核心价值主张


| 维度   | V1.x      | V2.0 新增                                              |
| ---- | --------- | ---------------------------------------------------- |
| 知识广度 | 手工录入故障–方案 | 公开数据（GAIA / LogHub / StackOverflow）批量打底，≥ 1000 条故障知识 |
| 推理能力 | 关键词查方案    | 向量相似推荐 + 图谱子图融合（Graph-RAG）                           |
| 沉淀闭环 | 无         | 文档/工单 → LLM 抽取 → 审核 → 图谱自动写入                         |
| 模型完备 | 二部图       | 全链路图（资产–告警–故障–方案–SOP–人员–分类）                          |
| 运营可见 | 无         | MTTR、覆盖率、复用率看板                                       |


---

## 2. 用户角色


| 角色           | 说明         | V2.0 典型操作                |
| ------------ | ---------- | ------------------------ |
| **超级管理员**    | 系统配置、安全策略  | 配置集成、管理角色、查看审计日志         |
| **知识运营**     | 知识库日常维护与运营 | 审核抽取结果、批量导入、发布 SOP、维护分类树 |
| **图谱审核员**    | 抽取候选的审核入库  | 审批/拒绝候选知识条目              |
| **运维工程师**    | 日常故障处理     | 智能问答、相似故障推荐、查方案/SOP      |
| **只读用户（可选）** | 查询浏览       | 仅查询，不录入、不审核              |


---

## 3. 功能模块总览


| 模块 ID      | 模块名称       | 核心交付             | V2.0 优先级 |
| ---------- | ---------- | ---------------- | -------- |
| **SCH**    | 图谱本体 2.0   | 全链路 Schema、溯源标记  | P0       |
| **DATA**   | 公开数据与混合知识库 | 批量导入管线、数据分层      | P0       |
| **EXT**    | 动态构建与知识沉淀  | 文档抽取、工单闭环        | P0       |
| **RETR**   | 图谱增强检索与推荐  | Graph-RAG、相似故障推荐 | P0       |
| **PORTAL** | 统一门户 V2    | 看板、审核台、融合搜索      | P1       |
| **INT**    | 外部系统集成     | CMDB/监控/工单对接     | P1~P2    |
| **OPS**    | 知识运营与看板    | 运营指标、闭环规则        | P1       |
| **SEC**    | 权限、审计与安全   | 角色矩阵、审计日志、.env 化 | P1       |


> **图例**：P0 = 阻塞交付 / P1 = 强烈建议 / P2 = 有时间再做

---

## 4. 功能详细说明

### 4.1 SCH — 图谱本体 2.0

#### 背景

V1.x 图谱仅有 Fault / Solution / HAS_SOLUTION，无法承载资产关联、告警溯源、工单归因、SOP 结构化等需求。V2.0 扩展为**七类实体 + 十二类关系**的全链路图模型。

#### 新增实体（顶点）


| 顶点类型             | 主键属性          | 关键附加属性                                                                     | 说明                |
| ---------------- | ------------- | -------------------------------------------------------------------------- | ----------------- |
| **Fault**（保留）    | `name`        | `category`、`severity`、`data_source`、`confidence`                           | 故障现象（扩展属性）        |
| **Solution**（保留） | `name`        | `description`、`data_source`、`confidence`                                   | 解决方案              |
| **SOP**          | `title`       | `steps`（JSON 数组）、`version`、`author`                                        | 标准处置步骤文档          |
| **Asset**        | `asset_id`    | `name`、`type`（server/middleware/cluster/network）、`ip`、`env`（prod/test）     | 业务资产，来自 CMDB 或手工  |
| **Alert**        | `alert_id`    | `content`、`level`（P1–P4）、`source`、`occurred_at`                            | 监控告警事件            |
| **Incident**     | `incident_id` | `title`、`status`、`created_at`、`closed_at`、`mttr_minutes`                   | 工单 / 事件单          |
| **Person**       | `username`    | `name`、`team`、`expertise`                                                  | 处理人 / 领域专家        |
| **Category**     | `code`        | `name`、`level`（P1–P4）、`domain`（hardware/system/network/storage/middleware） | ITIL 分类，作故障/告警分类树 |


#### 新增关系（边）


| 边类型                | 起点       | 终点               | 关键属性                        | 说明           |
| ------------------ | -------- | ---------------- | --------------------------- | ------------ |
| `HAS_SOLUTION`（保留） | Fault    | Solution         | —                           | 故障对应解决方案     |
| `HAS_SOP`          | Fault    | SOP              | —                           | 故障关联处置步骤文档   |
| `DOCUMENTED_IN`    | Solution | 文档 chunk ID（虚属性） | `chunk_ref`                 | 关联 RAG 知识库片段 |
| `CLASSIFIED_AS`    | Fault    | Category         | —                           | 故障的 ITIL 分类  |
| `SIMILAR_TO`       | Fault    | Fault            | `score`（相似度）、`method`       | 向量/规则计算相似故障  |
| `HAS_ALERT`        | Asset    | Alert            | `first_seen_at`             | 资产上产生的告警     |
| `TRIGGERS`         | Alert    | Fault            | `confidence`                | 告警触发的故障现象    |
| `INVOLVES`         | Incident | Asset            | `role`（affected/root_cause） | 工单涉及的资产      |
| `CAUSED_BY`        | Incident | Fault            | —                           | 工单对应的故障原因    |
| `RESOLVED_BY`      | Incident | Solution         | `adopted_at`                | 工单使用的解决方案    |
| `CONTRIBUTED`      | Person   | Solution/SOP     | `created_at`                | 专家贡献的知识      |
| `HANDLED_BY`       | Incident | Person           | `role`（owner/collaborator）  | 工单处理人        |


#### 溯源标记（所有节点/边共有属性）


| 属性                | 类型     | 说明                                                                      |
| ----------------- | ------ | ----------------------------------------------------------------------- |
| `data_source`     | String | `open_gaia` / `stackoverflow` / `logHub` / `internal_ticket` / `manual` |
| `confidence`      | Float  | 0.0 ~ 1.0，人工录入默认 1.0，LLM 抽取按模型置信度                                       |
| `import_batch_id` | String | 导入批次 ID，便于回滚与溯源                                                         |
| `created_at`      | Long   | 创建时间戳                                                                   |


#### 验收标准

- Schema 脚本可幂等执行，已有 V1.x 数据不丢失。
- 新实体类型均可写入/查询，边关系可在 HugeGraph Studio 可视化确认。

---

### 4.2 DATA — 公开数据与混合知识库

#### 背景

「先用公开数据打底，占 70%；自有数据占 30%，逐步替换」——V2.0 的数据策略核心。

#### 数据源清单


| 数据集                       | 类型             | 规模                     | 映射目标                                           | 许可证        |
| ------------------------- | -------------- | ---------------------- | ---------------------------------------------- | ---------- |
| **GAIA AIOps**            | 指标 + 日志 + 故障标签 | 6500+ 指标 / 700 万+ 日志   | Alert → Fault → Category                       | 学术/开源可用    |
| **LogHub**                | 真实故障日志         | Hadoop/Linux/K8s/Spark | Alert → Fault、TRIGGERS 边                       | Apache 2.0 |
| **StackOverflow 运维 Dump** | 问答对            | 500 万+                 | Fault → Solution（`data_source: stackoverflow`） | CC BY-SA   |
| **ITIL 故障分类模板**           | 分类树            | P1–P4 / 硬件/系统/网络/存储    | Category 全量初始化                                 | 公开         |
| **企业自有数据**                | 工单/文档/SOP      | 按实际                    | 全实体，`confidence: 1.0`                          | 内部         |


#### 功能需求

**F1 — 批量导入管线（必须）**

- 支持格式：JSON / CSV / TXT / JSONL
- 导入前：字段映射校验 → 去重检测（主键碰撞策略：`skip` / `overwrite`）
- 导入中：逐条幂等写入，失败条目记录至错误报告
- 导入后：自动打 `import_batch_id`，输出 `DATA_IMPORT_REPORT_V2.md`
- 命令示例：

```powershell
python scripts/import_v2.py data/gaia_faults.jsonl \
  --source open_gaia \
  --target-api http://localhost:8021 \
  --batch-id gaia-2026-04-28 \
  --conflict skip
```

**F2 — 数据分层标识（必须）**

- 所有接口返回的节点均携带 `data_source` 字段
- portal 查询结果可按「优先企业知识 / 显示全部」切换（初期以 `confidence` 排序实现）

**F3 — 分类树初始化（必须）**

- 内置 ITIL Category 数据集，一键初始化 `Category` 顶点树
- 支持在 portal 管理页维护分类（增删改）

**F4 — LLM 辅助数据生成（可选，P2）**

- 运营人员上传设备清单 CSV → LLM 按模板批量生成标准故障–方案草稿 → 进审核队列
- 模板结构：`{asset_type}` 在 `{scenario}` 下发生 `{fault_name}`，标准处置步骤：`...`

#### 验收标准

- 导入后图谱 Fault 节点总数 ≥ 1000，含 GAIA/LogHub/StackOverflow 三源，按 `data_source` 分布可查
- 导入成功率 ≥ 90%，产出 `DATA_IMPORT_REPORT_V2.md`
- Category 分类树完整初始化，Fault 节点可按 `category` 过滤查询

---

### 4.3 EXT — 动态构建与知识自动沉淀

#### 背景

行业友商的核心竞争力之一：**运维文档 / 工单 → 自动结构化 → 知识图谱**，不需要人工录入。V2.0 以 LLM（调用现有 Dify 或独立调用）为引擎实现该管线。

#### F1 — 文档抽取管线（必须，P0）

**流程**：

```
上传文档（txt/md/SOP）
  → 分段（复用 Dify 切片或 langchain text_splitter）
  → 每段调用 LLM 抽取（Prompt 模板见下）
  → 输出候选实体/关系 JSON
  → 写入「待审核队列」
  → 审核员 approve/reject
  → approve → graph-api 写入图谱（同时写 Dify 知识库）
  → reject → 标记丢弃，保留原文备查
```

**LLM 抽取 Prompt 模板（可配置）**：

```
你是一名 IT 运维知识工程师。请从以下文本中提取故障–解决方案关系，
以 JSON 数组输出，每项包含：
  fault_name（字符串）
  solution_name（字符串）
  solution_description（字符串，不超过500字）
  confidence（0.0~1.0，你对提取质量的评估）

文本：
{{chunk_text}}

仅输出 JSON，不要其他内容。
```

**后端新增接口**：

```
POST /extract/submit        # 提交文档，触发异步抽取任务
GET  /extract/jobs          # 查看任务列表与状态
GET  /extract/queue         # 获取待审核条目列表
POST /extract/queue/{id}/approve  # 审核通过，写入图谱
POST /extract/queue/{id}/reject   # 拒绝
```

**前端（portal 新增「知识抽取」页）**：

- 上传文档 / 粘贴文本
- 查看抽取任务状态（pending / running / done / failed）
- 候选条目列表：预览 fault_name / solution_name / confidence
- 逐条或批量 approve/reject

#### F2 — 工单闭环沉淀（P1）

**两种模式**：

- **手动模式（V2.0 必须）**：运维工程师关闭工单时，在 portal 填写「故障摘要 + 解决方案」，点击「沉淀为知识」→ 自动调 graph-api 写入，同时写 Dify 知识库。
- **自动模式（V2.0 可选）**：对接工单系统 API，工单变更为 Closed → Webhook 触发抽取管线 → 进审核队列（见 INT 模块）。

**工单沉淀关联关系**：

- 写入 Incident → Fault（`CAUSED_BY`）
- 写入 Incident → Solution（`RESOLVED_BY`，`adopted_at` = 当前时间）
- 写入 Incident → Asset（`INVOLVES`，若有关联资产）

#### F3 — 口述转知识（P2，可选）

- portal 提供文本输入框：「服务器宕机，先检查电源再检查 RAID 阵列」
- 调用 LLM 格式化为结构化草稿 → 进审核队列

#### 验收标准

- 上传一份运维 SOP（txt/md）→ 抽取出 ≥ 1 条候选 → 通过审核 → portal 图谱查询可命中
- 手动工单沉淀完整链路走通（填写 → 写入 → 查询回显）

---

### 4.4 RETR — 图谱增强检索与相似推荐

#### 背景

V1.x RAG 仅检索向量库，图谱与问答割裂。V2.0 引入 **Graph-RAG**（图谱子图 + RAG 联合上下文）和**相似故障推荐**，提升答案精度与 SOP 可达性。

#### F1 — Graph-RAG 融合问答（P0）

**检索链路**：

```
用户提问
  → 意图识别（LLM / 规则）
      ├─ 故障类问题 → Gremlin 查 Fault + 邻居 Solution/SOP
      │               + Qdrant 向量检索相关 chunk
      │               → 合并上下文 → LLM 生成回答（含结构化图谱摘要）
      └─ 通用知识问题 → 纯 RAG 链路（保持 V1.x 行为）
```

**实现方式**：

- graph-api 新增 `GET /graph/context?fault_name=...`：返回 Fault + Solution + SOP 结构化摘要，供 LLM 拼入上下文
- Dify 工作流新增 HTTP 节点，调用 `/graph/context` 获取图谱摘要，与向量召回结果合并后交给 LLM

**回答格式（参考）**：

```
[图谱推理] 识别到故障类型：CPU 告警（分类：P2 / 系统类）
已有 3 条处置方案：
  1. 检查高负载进程并限流（HugeGraph 图谱）
  2. 调整 JVM 堆内存参数（知识库引用：第 3 段）
  3. 参考 SOP：《CPU 告警标准处置流程》→ [查看详情]

[知识库引用] 来源文档：linux_ops_guide.md，第 12-15 段
```

#### F2 — 相似故障推荐（P0）

**流程**：

```
用户输入故障现象文本
  → embedding（调用现有 Dify embedding 或独立 model）
  → Qdrant 向量检索（fault_vectors collection，Top-K = 5）
  → 按相似度返回历史故障 + 对应方案列表
  → 写入 SIMILAR_TO 边（score 字段更新）
```

**后端新增接口**：

```
POST /graph/recommend
Body: {"query": "服务器 CPU 占用率持续 95%"}
Response:
{
  "query": "...",
  "recommendations": [
    {
      "fault_name": "CPU告警",
      "similarity": 0.92,
      "solutions": [...],
      "sop_title": "CPU 告警标准处置流程"
    }
  ]
}
```

**前端**：

- portal 问答页返回结果下方显示「相关历史故障」卡片区（可折叠）
- 图谱管理页查询结果新增「相似故障」侧栏

#### F3 — SOP 展开（P1）

- 图谱查询结果，Solution 卡片旁展示关联 SOP 按钮
- 点击展开 SOP 步骤列表（`steps` 数组，逐条有序展示）
- 支持「复制步骤」「沉淀为本次工单处置记录」快捷操作

#### 验收标准

- 给定 5 个预置故障现象，Graph-RAG 回答比纯 RAG 多出图谱摘要段落且引用来源有图谱节点 ID
- 相似推荐 Top-3 人工抽检可用率 ≥ 70%（按固定测试集评估）

---

### 4.5 PORTAL — 统一门户 V2

#### V1.5 现状

wisops-portal 已有：首页导航、AI 问答（流式）、图谱管理（查询/可视化/录入），端口 `:8091`。

#### V2.0 新增页面

**P1 — 知识抽取页（`/extract`）**

- 文档上传区 + 粘贴文本区
- 抽取任务列表（状态轮询，每 5s 刷新）
- 候选知识条目审核表格（审核员角色可见）

**P2 — 知识运营看板（`/dashboard`）**


| 指标卡     | 说明                             |
| ------- | ------------------------------ |
| 图谱节点总量  | 按实体类型分布饼图                      |
| 数据源分布   | open vs internal 占比            |
| 知识覆盖率   | 有 Solution 的 Fault 占比          |
| 方案复用率   | Incident RESOLVED_BY 命中已有方案的比率 |
| MTTR 趋势 | 按周/月平均分钟数折线（需 Incident 数据）     |
| 知识增长曲线  | 按周新增节点/边数                      |


**P3 — SOP 管理页（`/sop`）**

- SOP 列表：标题、版本、关联故障数、最后更新时间
- 新建/编辑 SOP：富文本或 Markdown 编辑器，步骤数组结构化存储
- 发布 → 写入 HugeGraph SOP 顶点

**P4 — 资产管理页（`/assets`，P2）**

- 资产列表（CSV 导入 / 手工录入）
- 资产详情：关联告警、历史故障、处理过的工单

**全局交互增强**


| 功能       | 说明                        |
| -------- | ------------------------- |
| 问答模式切换   | 「纯 RAG / 图谱融合 / 自动路由」三选一  |
| 知识沉淀快捷入口 | 问答页右上角「保存为知识」按钮 → 预填录入表单  |
| 角色权限可见性  | 未登录或低权限用户不可见审核台、抽取、看板管理操作 |


---

### 4.6 INT — 外部系统集成

> 分三个子版本逐步推进，避免外部依赖阻塞核心功能。

#### V2.1 — CMDB 集成（P1）

- 对接方式：CSV 导入 / REST API 轮询（每日一次）
- 同步内容：主机名、IP、系统类型、环境（prod/test）→ `Asset` 顶点
- 幂等键：`asset_id`，已存在则更新属性
- 接口（图谱侧）：`POST /assets/sync`，支持 JSON body 批量
- 失败处理：记录同步日志，不影响已有数据

#### V2.2 — 监控告警接入（P2）

- 对接方式：接收 Webhook（Prometheus AlertManager / 自研推送）
- 接口：`POST /alerts/ingest`，写入 `Alert` 顶点 + `HAS_ALERT` 边
- 触发：写入 Alert 后，自动调相似推荐接口，在告警详情页展示「参考方案」

```json
// Webhook 请求体（参考）
{
  "alert_id": "alert-2026-001",
  "asset_id": "server-web-01",
  "content": "CPU usage > 90% for 5 minutes",
  "level": "P2",
  "source": "prometheus",
  "occurred_at": "2026-04-28T14:00:00Z"
}
```

#### V2.3 — 工单系统对接（P2）

- 对接方式：定时拉取 Closed 工单（REST API 或 DB 只读查询）
- 写入 `Incident` 顶点 + 关联 Fault / Asset / Solution 边
- 触发 EXT 抽取管线（进审核队列）

---

### 4.7 OPS — 知识运营与看板

#### 运营指标定义


| 指标        | 计算方式                                          | 目标值（参考）      |
| --------- | --------------------------------------------- | ------------ |
| **知识覆盖率** | 有 ≥1 条 Solution 的 Fault / 总 Fault × 100%      | ≥ 80%        |
| **方案复用率** | `RESOLVED_BY` 边总数 / Closed Incident 总数 × 100% | ≥ 60%（数据足量后） |
| **MTTR**  | Incident.mttr_minutes 平均值，按周/月聚合              | 持续下降趋势       |
| **图谱增长**  | 按周新增 Fault / Solution / SOP 节点数               | 正向增长         |
| **抽取转化率** | approve 数 / 提交抽取总数 × 100%                     | ≥ 50%        |


#### 运营规则


| 规则                   | 实现级别                |
| -------------------- | ------------------- |
| 关单提示：建议关联知识条目        | V2.0 门户提示（非强制）      |
| 新故障：录入后自动触发相似推荐并展示   | V2.0 强制             |
| 抽取候选 48 小时未审核：自动邮件提醒 | V2.0 可选（依赖邮件配置）     |
| 月度知识运营报告             | V2.0 手动导出，V3.0 自动推送 |


#### 后端新增接口

```
GET /ops/stats           # 返回各项运营指标聚合数据
GET /ops/stats/growth    # 按时间窗口返回节点增长数据（周/月）
```

---

### 4.8 SEC — 权限、审计与安全收口

#### 角色权限矩阵


| 操作         | 超级管理员 | 知识运营 | 图谱审核员 | 运维工程师 | 只读用户 |
| ---------- | ----- | ---- | ----- | ----- | ---- |
| 查询问答       | ✅     | ✅    | ✅     | ✅     | ✅    |
| 图谱查询/可视化   | ✅     | ✅    | ✅     | ✅     | ✅    |
| 图谱录入（手工）   | ✅     | ✅    | ❌     | ✅     | ❌    |
| 提交文档抽取     | ✅     | ✅    | ❌     | ✅     | ❌    |
| 审核候选条目     | ✅     | ✅    | ✅     | ❌     | ❌    |
| 管理 SOP     | ✅     | ✅    | ❌     | ❌     | ❌    |
| 查看运营看板     | ✅     | ✅    | ❌     | ❌     | ❌    |
| 管理用户/角色    | ✅     | ❌    | ❌     | ❌     | ❌    |
| 批量数据导入     | ✅     | ✅    | ❌     | ❌     | ❌    |
| 系统配置（.env） | ✅     | ❌    | ❌     | ❌     | ❌    |
| 查看审计日志     | ✅     | ❌    | ❌     | ❌     | ❌    |


#### 审计日志

需记录以下操作（写入日志文件或 DB）：

- 图谱节点/边写入、修改、删除
- 抽取任务提交、审核 approve/reject
- 数据批量导入（记录 batch_id、条数、操作人）
- 用户登录 / 登出

日志格式：`timestamp | user | action | resource | result`

#### 安全收口（承接 V1.x 遗留）

- **必须完成**：`docker-compose.yml` 所有密码/密钥迁至 `.env`，提供 `.env.example`，`.env` 加入 `.gitignore`
- portal 生产部署前，在 Nginx 层加 Basic Auth（最低鉴权）或对接 Dify 认证体系
- `graph-api` 生产部署建议启用 API Key Header 校验（`X-API-Key`）

---

## 5. 系统架构

### 5.1 整体架构（V2.0 目标态）

```
浏览器
  └── :8091  →  wisops-portal V2（Nginx + React）
                  ├── /           首页 / 看板 / SOP 管理
                  ├── /chat       AI 融合问答（RAG + Graph-RAG）
                  ├── /graph      图谱查询 / 可视化 / 录入
                  ├── /extract    知识抽取与审核台
                  ├── /assets     资产管理（P2）
                  └── /dashboard  运营看板
                  │
                  ├── /dify-api/  → Dify API :5001（RAG 问答）
                  │                   ├── Qdrant :6333（向量检索 + fault_vectors collection）
                  │                   ├── PostgreSQL :5432
                  │                   └── Redis :6379
                  │
                  └── /graph-api/ → graph-api V2 :8000（FastAPI）
                                       ├── HugeGraph :8080（全链路图谱 + Schema 2.0）
                                       └── extract-worker（异步 LLM 抽取任务队列）
                                            └── 调用 LLM API（本地/外部）
```

### 5.2 数据流

**Graph-RAG 融合问答链路**

```
用户提问
  → Dify 工作流
      ├── HTTP 节点 → /graph/context → HugeGraph Gremlin → 图谱子图摘要
      └── 向量检索 → Qdrant → 相关 chunk
  → 合并上下文 → LLM → 带图谱摘要 + 知识库引用的回答 → 用户
```

**相似故障推荐链路**

```
用户输入故障文本
  → /graph/recommend
      → embedding → Qdrant fault_vectors 检索 Top-K
      → 匹配 HugeGraph Fault 节点 → 查 Solution / SOP
  → 返回推荐列表 → portal 展示
```

**知识沉淀链路**

```
文档上传 / 工单关闭
  → /extract/submit（异步）→ extract-worker → LLM 抽取
  → 候选 JSON → 写审核队列（Redis 或 DB）
  → 审核员 approve → /extract/queue/{id}/approve
  → graph-api 写 HugeGraph + Dify 知识库
```

### 5.3 技术选型（V2.0 新增/变化）


| 组件       | 技术                                    | 变化说明                                              |
| -------- | ------------------------------------- | ------------------------------------------------- |
| 图谱 API   | FastAPI（自研扩展）                         | 新增 extract / recommend / assets / ops / alerts 路由 |
| 抽取任务队列   | Redis（已有） + Celery 或轻量协程              | 新增，异步化抽取任务                                        |
| 向量相似检索   | Qdrant + 新 `fault_vectors` Collection | 原 collection 留 RAG，新建故障专用                         |
| 前端门户     | Vite + React（扩展 wisops-portal）        | 新增页面、看板、审核台                                       |
| LLM 调用   | 复用 Dify embedding + 外部 Chat API       | 可切换：通义千问 / 文心 / GLM                               |
| 全文检索（P2） | Elasticsearch 7.x                     | 可选，支撑 SOP 全文 + 资产搜索                               |


---

## 6. 图谱 Schema 规范

### 6.1 HugeGraph 初始化脚本（`schema_v2.groovy`）

```groovy
// 属性键
schema.propertyKey('name').asText().ifNotExist().create()
schema.propertyKey('description').asText().ifNotExist().create()
schema.propertyKey('title').asText().ifNotExist().create()
schema.propertyKey('steps').asText().ifNotExist().create()          // JSON 序列化步骤数组
schema.propertyKey('version').asText().ifNotExist().create()
schema.propertyKey('author').asText().ifNotExist().create()
schema.propertyKey('asset_id').asText().ifNotExist().create()
schema.propertyKey('asset_type').asText().ifNotExist().create()
schema.propertyKey('ip').asText().ifNotExist().create()
schema.propertyKey('env').asText().ifNotExist().create()
schema.propertyKey('alert_id').asText().ifNotExist().create()
schema.propertyKey('content').asText().ifNotExist().create()
schema.propertyKey('level').asText().ifNotExist().create()
schema.propertyKey('source').asText().ifNotExist().create()
schema.propertyKey('occurred_at').asLong().ifNotExist().create()
schema.propertyKey('incident_id').asText().ifNotExist().create()
schema.propertyKey('status').asText().ifNotExist().create()
schema.propertyKey('created_at').asLong().ifNotExist().create()
schema.propertyKey('closed_at').asLong().ifNotExist().create()
schema.propertyKey('mttr_minutes').asInt().ifNotExist().create()
schema.propertyKey('username').asText().ifNotExist().create()
schema.propertyKey('team').asText().ifNotExist().create()
schema.propertyKey('expertise').asText().ifNotExist().create()
schema.propertyKey('code').asText().ifNotExist().create()
schema.propertyKey('domain').asText().ifNotExist().create()
schema.propertyKey('data_source').asText().ifNotExist().create()
schema.propertyKey('confidence').asDouble().ifNotExist().create()
schema.propertyKey('import_batch_id').asText().ifNotExist().create()
schema.propertyKey('score').asDouble().ifNotExist().create()
schema.propertyKey('method').asText().ifNotExist().create()
schema.propertyKey('chunk_ref').asText().ifNotExist().create()
schema.propertyKey('role').asText().ifNotExist().create()
schema.propertyKey('adopted_at').asLong().ifNotExist().create()
schema.propertyKey('category').asText().ifNotExist().create()
schema.propertyKey('severity').asText().ifNotExist().create()

// 顶点标签（保留 V1.x）
schema.vertexLabel('Fault').properties('name','description','category','severity','data_source','confidence','import_batch_id','created_at').primaryKeys('name').ifNotExist().create()
schema.vertexLabel('Solution').properties('name','description','data_source','confidence','import_batch_id','created_at').primaryKeys('name').ifNotExist().create()

// 顶点标签（V2.0 新增）
schema.vertexLabel('SOP').properties('title','steps','version','author','data_source','created_at').primaryKeys('title').ifNotExist().create()
schema.vertexLabel('Asset').properties('asset_id','name','asset_type','ip','env','data_source','created_at').primaryKeys('asset_id').ifNotExist().create()
schema.vertexLabel('Alert').properties('alert_id','content','level','source','occurred_at','data_source').primaryKeys('alert_id').ifNotExist().create()
schema.vertexLabel('Incident').properties('incident_id','title','status','created_at','closed_at','mttr_minutes','data_source').primaryKeys('incident_id').ifNotExist().create()
schema.vertexLabel('Person').properties('username','name','team','expertise').primaryKeys('username').ifNotExist().create()
schema.vertexLabel('Category').properties('code','name','level','domain').primaryKeys('code').ifNotExist().create()

// 边标签（保留 V1.x）
schema.edgeLabel('HAS_SOLUTION').sourceLabel('Fault').targetLabel('Solution').ifNotExist().create()

// 边标签（V2.0 新增）
schema.edgeLabel('HAS_SOP').sourceLabel('Fault').targetLabel('SOP').ifNotExist().create()
schema.edgeLabel('DOCUMENTED_IN').sourceLabel('Solution').targetLabel('Solution').properties('chunk_ref').ifNotExist().create()
schema.edgeLabel('CLASSIFIED_AS').sourceLabel('Fault').targetLabel('Category').ifNotExist().create()
schema.edgeLabel('SIMILAR_TO').sourceLabel('Fault').targetLabel('Fault').properties('score','method').ifNotExist().create()
schema.edgeLabel('HAS_ALERT').sourceLabel('Asset').targetLabel('Alert').properties('created_at').ifNotExist().create()
schema.edgeLabel('TRIGGERS').sourceLabel('Alert').targetLabel('Fault').properties('confidence').ifNotExist().create()
schema.edgeLabel('INVOLVES').sourceLabel('Incident').targetLabel('Asset').properties('role').ifNotExist().create()
schema.edgeLabel('CAUSED_BY').sourceLabel('Incident').targetLabel('Fault').ifNotExist().create()
schema.edgeLabel('RESOLVED_BY').sourceLabel('Incident').targetLabel('Solution').properties('adopted_at').ifNotExist().create()
schema.edgeLabel('CONTRIBUTED').sourceLabel('Person').targetLabel('Solution').properties('created_at').ifNotExist().create()
schema.edgeLabel('HANDLED_BY').sourceLabel('Incident').targetLabel('Person').properties('role').ifNotExist().create()
```

---

## 7. 接口规范

### 7.1 保留 V1.x 接口（不变）


| 方法   | 路径                 | 说明                |
| ---- | ------------------ | ----------------- |
| GET  | `/health`          | 健康检查              |
| POST | `/graph/add`       | 新增故障–方案关系         |
| GET  | `/graph/query`     | 查询指定故障的方案列表       |
| GET  | `/graph/faults`    | 获取所有故障名列表         |
| GET  | `/graph/visualize` | 获取故障子图节点/边（SVG 用） |


### 7.2 V2.0 新增接口

#### 图谱增强

```
GET  /graph/context?fault_name=     Graph-RAG 上下文摘要（供 Dify 工作流调用）
POST /graph/recommend               相似故障推荐
POST /graph/sop                     创建/更新 SOP
GET  /graph/sop?fault_name=         获取故障关联 SOP 列表
```

#### 资产与告警

```
POST /assets/sync                   批量同步资产（JSON body）
GET  /assets                        资产列表（分页）
POST /alerts/ingest                 接收告警 Webhook
GET  /alerts?asset_id=              查询指定资产告警
```

#### 工单/事件

```
POST /incidents                     手动录入工单记录（含沉淀）
GET  /incidents                     工单列表（分页）
```

#### 知识抽取

```
POST /extract/submit                提交文档抽取任务
GET  /extract/jobs                  任务列表
GET  /extract/queue                 待审核候选列表
POST /extract/queue/{id}/approve    审核通过，写入图谱
POST /extract/queue/{id}/reject     拒绝
```

#### 运营统计

```
GET  /ops/stats                     各项运营指标汇总
GET  /ops/stats/growth?window=week  节点增长数据
```

### 7.3 统一响应结构

```json
{
  "status": "ok",
  "data": { ... },
  "message": ""
}
```

```json
{
  "status": "error",
  "data": null,
  "message": "fault_name cannot be empty"
}
```

HTTP 状态码：200 成功 / 400 参数错误 / 401 未授权 / 403 权限不足 / 502 HugeGraph 错误 / 503 服务不可达

---

## 8. 数据规范

### 8.1 数据分层策略


| 层级          | data_source 值                            | 说明               | 权重（检索排序） |
| ----------- | ---------------------------------------- | ---------------- | -------- |
| 企业自有        | `internal_ticket` / `manual`             | 最高质量，来自真实工单与人工录入 | 1.0      |
| LLM 抽取（已审核） | `extracted_approved`                     | 可信，经人工审核         | 0.9      |
| 公开精选        | `stackoverflow_curated`                  | 经人工筛选的公开问答       | 0.8      |
| 公开原始        | `open_gaia` / `logHub` / `stackoverflow` | 公开数据，未精选         | 0.6      |


### 8.2 预置数据目标（V2.0）


| 数据集              | 目标量         | 格式       | 导入方式                   |
| ---------------- | ----------- | -------- | ---------------------- |
| GAIA 故障–根因       | ≥ 300 条     | JSONL    | `scripts/import_v2.py` |
| LogHub 告警–故障     | ≥ 200 条     | TXT/JSON | `scripts/import_v2.py` |
| StackOverflow 精选 | ≥ 500 条     | JSON     | `scripts/import_v2.py` |
| ITIL Category 树  | 完整 P1–P4 分类 | JSON     | 一次性初始化脚本               |
| 企业内部（目标）         | ≥ 100 条     | 工单/SOP   | 手动 + 抽取管线              |


### 8.3 导入脚本规范

`scripts/import_v2.py` 在 V1.x `import_faults.py` 基础上扩展：

```
python scripts/import_v2.py <data_file> \
  --source <data_source>         # 必填：open_gaia / stackoverflow / manual ...
  --entity-type <Fault|Asset|Incident|...>  # 目标实体类型
  --api-url <graph-api base>
  --batch-id <唯一批次 ID>
  --conflict <skip|overwrite>    # 冲突策略，默认 skip
  --dry-run                      # 仅校验，不写入
```

---

## 9. 非功能性需求


| 类别       | 要求                                     | 目标值               |
| -------- | -------------------------------------- | ----------------- |
| **可用性**  | 容器重启后服务恢复                              | ≤ 5 分钟            |
| **问答响应** | RAG / Graph-RAG 端到端（含 LLM）             | ≤ 15 秒            |
| **图谱查询** | 单次 Gremlin 查询                          | ≤ 2 秒             |
| **相似推荐** | embedding + Qdrant 检索                  | ≤ 3 秒             |
| **抽取任务** | 单段落 LLM 抽取                             | ≤ 30 秒            |
| **安全**   | 密码/密钥不硬编码入 git                         | 必须                |
| **私有化**  | 全程无外网依赖（LLM API 除外）                    | 必须                |
| **审计**   | 关键写操作有日志                               | 必须                |
| **可维护**  | `docker compose logs` 可查 + 结构化 JSON 日志 | 强烈建议              |
| **可扩展**  | 新增实体类型 / 数据源不影响现有服务                    | 必须（Schema 幂等脚本保证） |


---

## 10. 交付物清单


| 交付物                                                | 类型        | V2.0 状态 |
| -------------------------------------------------- | --------- | ------- |
| `docker-compose.yml`（含 portal V2 + extract-worker） | 配置        | ⏳ 待更新   |
| `graph-api/`（V2.0 扩展接口）                            | 代码        | ⏳ 待开发   |
| `graph-api/schema_v2.groovy`                       | Schema 脚本 | ⏳ 待编写   |
| `wisops-portal/`（新增页面：抽取/看板/SOP）                   | 代码        | ⏳ 待开发   |
| `scripts/import_v2.py`                             | 工具脚本      | ⏳ 待开发   |
| `data/`（GAIA / LogHub / StackOverflow 预置数据）        | 数据        | ⏳ 待准备   |
| `data/itil_category.json`                          | 数据        | ⏳ 待准备   |
| `.env.example`（完整版，含所有配置项）                         | 安全配置      | ⏳ 待更新   |
| `README_V2.md`                                     | 部署文档      | ⏳ 待编写   |
| `PRD_V2.md`（本文档）                                   | 产品文档      | ✅ 已完成   |
| `TEST_REPORT_V2.md`                                | 测试报告      | ⏳ 待产出   |
| `DATA_IMPORT_REPORT_V2.md`                         | 数据导入报告    | ⏳ 待产出   |
| 演示脚本（Graph-RAG + 相似推荐 + 知识沉淀）                      | 文档        | ⏳ 待产出   |


---

## 11. 路线图

### 优先级定义

- **P0**：阻塞交付，必须完成
- **P1**：核心功能完整性，强烈建议
- **P2**：提升体验，有时间再做

### V2.0-alpha（第 1–2 月）：数据与推理基础


| #   | 任务                                                     | 模块     | 优先级 |
| --- | ------------------------------------------------------ | ------ | --- |
| 1   | Schema 2.0 定稿并幂等初始化（含 V1.x 数据迁移）                       | SCH    | P0  |
| 2   | `import_v2.py` 开发，支持多实体类型与 data_source 标记              | DATA   | P0  |
| 3   | GAIA / LogHub / StackOverflow 数据清洗与批量导入                | DATA   | P0  |
| 4   | ITIL Category 树初始化                                     | DATA   | P0  |
| 5   | `/graph/context` 接口实现（Graph-RAG 上下文摘要）                 | GR-API | P0  |
| 6   | `/graph/recommend` 接口实现（相似故障推荐）                        | GR-API | P0  |
| 7   | Qdrant 新建 `fault_vectors` Collection，故障 embedding 批量写入 | GR-API | P0  |
| 8   | Dify 工作流集成 `/graph/context`（HTTP 节点）                   | RETR   | P0  |
| 9   | `.env` 安全收口（承接 V1.x 遗留）                                | SEC    | P0  |


### V2.0-beta（第 3–4 月）：沉淀与运营


| #   | 任务                                        | 模块          | 优先级 |
| --- | ----------------------------------------- | ----------- | --- |
| 10  | `/extract/submit` 及 extract-worker 异步抽取服务 | EXT         | P0  |
| 11  | 审核队列接口（approve / reject）                  | EXT         | P0  |
| 12  | portal 知识抽取页（上传 + 任务状态 + 审核台）             | PORTAL      | P1  |
| 13  | SOP 实体 + `/graph/sop` 接口 + portal SOP 管理页 | RETR/PORTAL | P1  |
| 14  | portal 问答页 Graph-RAG 融合展示（图谱摘要 + 知识库引用）   | PORTAL      | P1  |
| 15  | 手动工单沉淀（portal 表单 → Incident 写入）           | EXT         | P1  |
| 16  | `/ops/stats` 接口 + portal 运营看板 v1（基础指标卡）   | OPS         | P1  |
| 17  | `POST /assets/sync` 接口 + portal 资产导入（CSV） | INT         | P1  |


### V2.0-GA（第 5–6 月）：集成与安全收口


| #   | 任务                                        | 模块  | 优先级 |
| --- | ----------------------------------------- | --- | --- |
| 18  | `POST /alerts/ingest` Webhook 接口 + 相似推荐联动 | INT | P2  |
| 19  | 工单系统 API 对接（定时拉取 Closed 工单）               | INT | P2  |
| 20  | 角色权限矩阵落地（portal 前端鉴权 + API 后端校验）          | SEC | P1  |
| 21  | 审计日志（关键写操作）                               | SEC | P1  |
| 22  | Elasticsearch 评估与可选集成（全文检索 SOP/资产）        | OPS | P2  |
| 23  | 运营看板完整版（MTTR 趋势 / 增长曲线 / 抽取转化率）           | OPS | P2  |
| 24  | `TEST_REPORT_V2.md` 产出（覆盖全模块）             | 测试  | P1  |
| 25  | 演示脚本固化（Graph-RAG + 推荐 + 沉淀全流程）            | 交付  | P1  |


---

## 12. 验收标准

### V2.0-alpha 验收

- `schema_v2.groovy` 幂等执行成功，V1.x 数据无损，新实体类型可写入查询
- 三源数据（GAIA / LogHub / StackOverflow）导入成功，总 Fault 节点 ≥ 1000，`data_source` 分布可查
- Category 分类树完整，Fault 可按 category 过滤
- `/graph/recommend` 对 5 个测试查询返回有效推荐，Top-3 人工可用率 ≥ 70%
- Dify 工作流调通 `/graph/context`，融合问答回答中出现图谱摘要段落

### V2.0-beta 验收

- 上传 1 份 SOP 文档 → 抽取出候选 → approve → portal 图谱查询命中
- 手动工单沉淀完整走通（录入 Incident + Solution + Asset 关联）
- portal 审核台正常展示候选列表，approve/reject 操作可用
- 运营看板展示知识覆盖率、图谱节点总量、数据源分布

### V2.0-GA 验收（最终交付门槛）

#### 基础设施

- `docker compose --profile graph up -d --build` 所有服务均 `Up`
- 无密码/密钥硬编码（使用 `.env` 管理）

#### 数据

- 图谱 Fault 节点总数 ≥ 1000
- Category 分类树完整
- Dify 知识库文档片段 ≥ 500

#### 智能检索

- 给定 5 个预置故障问题，Graph-RAG 模式回答包含图谱摘要且带知识库引用
- 相似故障推荐 Top-3 人工可用率 ≥ 70%（固定测试集）

#### 知识沉淀

- 文档抽取管线端到端走通（提交 → 抽取 → 审核 → 写入 → 可查询）
- 手动工单沉淀端到端走通

#### 运营看板

- `/ops/stats` 返回知识覆盖率、节点总量、数据源分布
- portal 看板页正常加载所有指标卡

#### 安全与权限

- 角色权限矩阵生效（至少区分：运维工程师 vs 知识运营 vs 管理员）
- 关键写操作有审计日志

---

## 13. 风险与依赖


| 风险                    | 级别  | 影响                                | 处理策略                                       |
| --------------------- | --- | --------------------------------- | ------------------------------------------ |
| 公开数据集质量参差，噪声大         | 高   | 影响推荐准确率                           | 分层标记 `confidence`，检索时加权；设置导入前质量过滤规则        |
| LLM 抽取准确率不稳定          | 高   | 大量低质候选进审核队列，运营成本高                 | Prompt 迭代优化；设置 confidence 阈值过滤；审核台批量操作降低成本 |
| HugeGraph Schema 迁移风险 | 高   | 已有 V1.x 数据受影响                     | Schema 脚本全部 `ifNotExist()`，幂等执行；迁移前备份数据卷   |
| Docker Hub 网络问题       | 中   | 影响镜像拉取与构建                         | 配置镜像加速；离线构建 `docker save/load`             |
| 外部 LLM API 不稳定        | 中   | 抽取任务超时/失败                         | 抽取任务重试机制；降级策略（规则抽取兜底）                      |
| 工单/CMDB 系统对接复杂        | 中   | INT 模块延期                          | 先做 CSV 导入手动模式，API 对接作 P2                   |
| 向量 embedding 一致性      | 中   | 相似推荐与 RAG 使用不同 embedding 导致语义空间割裂 | 统一使用 Dify 的 embedding 接口，或指定同一外部模型         |
| 权限体系与 Dify 认证割裂       | 低   | 用户需要两套账号                          | V2.0 先以 Nginx Basic Auth 统一入口，V3.0 再做 SSO  |


---

*本文档随开发进展持续更新。各模块完成度以最新进度看板为准，PRD 应同步修订。*

> 对应 V1.0 PRD：`PRD.md`  
> 当前版本：V2.0 PRD v1.0（2026-04-28）

