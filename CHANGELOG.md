# WisOps 版本变更日志

> 遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 规范  
> 版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)

---

## [Unreleased]

---

## [v1.9.0] — 2026-04-30

### 新增

- portal：资产管理页 **`/assets`**（侧栏「资产管理」），资产表格分页、`GET /assets?q=` 筛选、右侧详情与 `GET /alerts?asset_id=` 关联告警列表
- graph-api：`GET /assets` 支持可选查询参数 **`q`**（子串匹配 `asset_id` / `name` / `ip`，有 `q` 时全量拉取 Asset 后内存分页）
- graph-api：抽取审核 **`POST /extract/queue/batch-approve`**、**`POST /extract/queue/batch-reject`**（请求体 `item_ids`，单次最多 50 条，逐条返回成功/失败明细）
- portal：知识抽取「审核队列」支持 **全选 / 多选、批量通过、批量拒绝**
- 数据：`scripts/import_stackoverflow.py` 支持 Stack Exchange 官方 **`Posts.xml`** 两阶段解析、HTML 清洗、运维向标签过滤；说明与样例见 `data/stackoverflow/README.md`
- **SEC**：graph-api 新增 **`X-API-Key` HTTP 中间件**（`GRAPH_API_KEY` 环境变量；未配置跳过校验；写操作 POST/PUT/DELETE 鉴权，读操作及白名单路径豁免）
- **SEC**：graph-api 新增**写操作审计日志**（`audit_middleware`，滚动内存存储）+ **`GET /admin/audit-log`** 查询接口（支持 `method` / `path_kw` 过滤）
- **SEC**：portal 新增**三档角色系统**（`admin` / `engineer` / `readonly`，localStorage 持久化）；左下角角色切换器；导航/路由/按钮按 `can()` 条件渲染
- **SEC**：新增 **`.env.example`** 完整配置示例；`docker-compose.yml` 注入 `GRAPH_API_KEY` / `AUDIT_MAX_ENTRIES`
- **文档**：新增 **`docs/TEST_REPORT_V2.md`**（75 条验收用例，Beta 全部通过）
- **文档**：新增 **`docs/DATA_IMPORT_REPORT_V2.md`**（图谱数据量快照、4 类来源说明、全量恢复命令）
- graph-api：新增 **`GET /incidents/{incident_id}`** 工单详情（含 Fault / Solution / Asset 关联列表）
- graph-api：新增 **`GET /graph/solutions`** 方案名称列表（供前端补全）
- graph-api：**`GET /graph/faults`** 返回格式统一为 `[{name}]` 对象数组，支持 `page_size`
- portal：新增 **`/incidents` 工单沉淀页**（列表 + 详情 + 录入表单，含 Fault/Solution/Asset 关联补全）
- portal：首页新增「工单沉淀」卡片；**首页布局全面重设计**（品牌名渐变大字、特性 Pill 栏、3 列卡片网格、彩色顶栏卡片样式）
- 图谱可视化：**`/graph/visualize` 扩展**返回 Alert（TRIGGERS）、Category（CLASSIFIED_AS）、邻近 Fault（同类）；前端替换为**可拖拽多类型节点图**（分圈初始布局 + 鼠标拖动任意节点）

### 修复

- graph-api：`GET /incidents` 与 `GET /alerts` 排序语法 `decr` → `Order.desc`，修复 HTTP 502 / HugeGraph 400 错误

### 变更

- 宿主机端口：**graph-api** `8002` → **`8021`**，**portal** `8090` → **`8091`**；相关文档全部同步
- graph-api 版本号 `1.8.0` → `1.9.0`；portal `package.json` `1.8.0` → `1.9.0`

## [v1.8.0] — 2026-04-29

> **里程碑**：平台版本 **V1.8**（抽取追溯闭环、TRIGGERS 审计增强）

### 新增

- graph-api：`GET /admin/triggers/audit`，支持按 `method` / `rule_name` / `min_confidence` 分页审计 `TRIGGERS` 边
- graph-api：`TRIGGERS` 边属性增强，写入并回填 `confidence`、`method`、`rule_name`
- graph-api：抽取审核后新增文档追溯索引 `GET /extract/doc-links`
- graph-api：新增 `GET /graph/document-trace?document_id=...`，按 Dify `document_id` 反查 `Solution/Fault` 图谱关联
- graph-api：`approve` 后自动建立 `Solution -> DOCUMENTED_IN -> SOP(dify-doc:document_id)` 映射，并在边上写 `chunk_ref=document_id`
- portal：知识抽取页新增「文档追溯」Tab，支持 `document_id/job_id` 过滤与一键复制
- portal：图谱管理页新增「文档追溯」Tab，支持按 `document_id` 反查图谱关系

### 修复

- TRIGGERS 规则匹配可解释性不足问题（补充规则命中审计字段）
- 抽取审核后「知识库文档 ↔ 图谱关系」追溯链路缺失问题
- 图谱 Schema 启动时序问题：`startup()` 中 Schema 初始化若失败会被静默跳过，导致 `Undefined vertex label: 'Fault'`；在 `_all_fault_names_ordered()` 首次调用前幂等执行 `ensure_schema_v2()`，HugeGraph 晚于 graph-api 就绪时仍可自愈

### 变更

- 统一产品版本到 **V1.8 / 1.8.0**（`graph-api` FastAPI、`wisops-portal`、首页/侧栏徽章、README）
- `docs/TESTING.md` 新增 §6「图谱数据丢失：排查与全量恢复」
- `README.md` 新增「图谱数据丢失快速恢复」章节

## [v1.7.0] — 2026-04-29

> **里程碑**：平台版本 **V1.7**（门户与图谱体验、数据全量一致性）

### 新增

- graph-api：**Gremlin `range` 分页**（`_gremlin_collect_paged`），避免 HugeGraph 单次迭代批量上限导致仅返回约 64 条；`/graph/faults`、`/graph/recommend` 关键词候选、**`POST /admin/fault-vectors/sync` 全量**、分类初始化、告警–故障同步等路径均按页拉全量
- graph-api：`GET /graph/faults/detail`（分页、按名称子串筛选、返回 `solution_total` / `has_solution_edges`）
- graph-api：Qdrant **`fault_vectors`** 同步接口 `POST /admin/fault-vectors/sync`（OpenAI 兼容 `/v1/embeddings`）
- `POST /graph/recommend` 优先向量检索，失败或无索引时降级关键词；响应增加 **`method`**：`vector` / `keyword` / `keyword_fallback`
- `POST /graph/add`：写入成功后**后台**增量更新该 Fault 的 Qdrant 向量（配置齐全且维度与 collection 一致时）
- Docker：`graph-api` 依赖 **qdrant**，注入 `QDRANT_URL` 与可选 `EMBEDDING_*`
- portal：图谱管理 **「故障列表」** 表格（分页、每页条数、Fault 去重与统计说明）
- portal：图谱 **可视化**（边/标签外移、箭头、图例、悬停高亮、入场动效、**节点径向间距**约束）

### 修复

- 故障列表 / 向量同步等仅见「前几十条」、与图中实际 Fault 数不一致的问题（Gremlin 未分页）

### 变更

- 统一产品展示与 OpenAPI 版本号为 **V1.7** / **`1.7.0`**（`wisops-portal` npm、侧栏、首页徽章、`graph-api` FastAPI `version`）；图谱领域模型仍为 Schema V2.0

## [v1.6.0] — 2026-04-28

> **里程碑**：V2.0 核心模块全量上线 + 真实 GAIA 数据集接入

### 新增

#### 图谱本体 2.0（SCH）
- 扩展图谱 Schema 至七类顶点：`Fault`、`Solution`、`SOP`、`Asset`、`Alert`、`Incident`、`Category`
- 新增十二类边关系：`HAS_SOP`、`CLASSIFIED_AS`、`SIMILAR_TO`、`HAS_ALERT`、`TRIGGERS`、`INVOLVES`、`CAUSED_BY`、`RESOLVED_BY`、`DOCUMENTED_IN`、`CONTRIBUTED`、`HANDLED_BY`（含已有 `HAS_SOLUTION`）
- 全属性溯源标记：`data_source`、`confidence`、`import_batch_id`、`created_at`
- Schema 幂等初始化接口 `POST /admin/schema/init`，兼容 V1.x 已有数据

#### 真实数据集（DATA）
- 接入 **GAIA-DataSet**（CloudWise 开源 AIOps 数据集）
  - 导入 MicroSS 微服务资产 10 个（Asset 节点）
  - 导入异常注入事件 **1448 条**（Alert 节点，来自 run.zip）
  - 从 error.csv 匹配提取故障–解决方案 **25 对**（Fault + Solution + HAS_SOLUTION）
  - 覆盖 Application / Database / Storage / Security / Network / Middleware / Kubernetes 七个领域
- 新增 GAIA 解析导入脚本 `scripts/parse_gaia.py`

#### Graph-RAG 增强检索（RETR）
- `GET /graph/context`：返回 Fault + Solution + SOP 结构化摘要（供 Dify 工作流调用）
- `POST /graph/recommend`：相似故障推荐接口
- `POST /graph/sop` + `GET /graph/sop`：SOP 创建与查询

#### 知识沉淀管线（EXT）
- `POST /extract/submit`：提交文档，触发知识抽取任务
- `GET /extract/jobs`：任务状态列表
- `GET /extract/queue`：待审核候选条目
- `POST /extract/queue/{id}/approve`：审核通过，写入图谱
- `POST /extract/queue/{id}/reject`：拒绝

#### 资产与告警集成（INT）
- `POST /assets/sync`：批量同步资产（JSON body）
- `GET /assets`：资产列表（分页）
- `POST /alerts/ingest`：接收告警 Webhook（兼容 Prometheus AlertManager 格式）
- `GET /alerts`：查询指定资产告警

#### 工单/事件管理
- `POST /incidents`：手动录入工单（含 Fault/Asset 关联沉淀）
- `GET /incidents`：工单列表（分页）

#### 运营看板（OPS）
- `GET /ops/stats`：知识覆盖率、节点总量、数据源分布、抽取转化率
- `GET /ops/stats/growth`：按时间窗口的节点增长数据

#### 统一门户 V2（PORTAL）
- 新增页面：`/extract`（知识抽取与审核台）
- 新增页面：`/sop`（SOP 管理）
- 新增页面：`/dashboard`（运营看板）
- 扩展图谱管理页可视化能力

### 修复

- `execute_gremlin` 字符串替换 bug：`graph.schema()` → `hugegraph.schema()` 误伤嵌套字符串，改用正则边界匹配 `\bgraph\.schema\(\)`
- HugeGraph Schema 幂等性问题：`getEdgeLabel()` / `getVertexLabel()` 不存在时抛 `NotFoundException` 而非返回 null，改用列表遍历判断
- 边标签创建时缺少 `properties()` 声明导致 `nullableKeys` 报错
- 启动时 Schema 初始化失败被 `try/except` 静默吞掉，新增管理端点暴露错误
- `Alert` 顶点缺少 `data_source` 属性，补充 `append()` 逻辑
- `parse_gaia.py` 中文字符串含非法 `\u` 转义（`多\u租户`），替换为标准 Unicode 码点

### 变更

- `graph-api/main.py`：全量重写为 V2.0（新增 600+ 行，完整 23 个端点）
- `.gitignore`：新增排除规则（`data/gaia/`、`scripts/_*.py`）

### 当前图谱状态

| 节点类型 | 数量 | 来源 |
|---|---|---|
| Asset | 10 | GAIA MicroSS |
| Alert | 1448 | GAIA 异常注入事件 |
| Fault | 25 | GAIA error.csv 模式匹配 |
| Solution | 25 | 与 Fault 一一对应 |
| **合计** | **1508** | 全部真实数据 |

---

## [v1.5.0] — 2026-04-28

> **里程碑**：统一网关 + 自建前端门户  
> **当前仓库**：统一门户宿主机端口已改为 **`:8091`**（见 `[Unreleased]` 与 `docker-compose.yml`）；本节下列 `:8090` 为 v1.5.0 当时记录，勿当作现网默认端口。

### 新增

- 统一网关（Nginx，`:8090`）：将 Dify 问答、graph-api、graph-ui 统一收口
- `wisops-portal`：自建 React 前端，集成 AI 问答（流式 + 知识引用）、图谱管理、可视化
- 图谱可视化（D3.js）：故障子图节点/边交互展示
- `GET /graph/visualize` API：返回子图节点和边数据
- GitHub Actions CI 配置（`.github/`）

### 修复

- 网关端口从 8280 改为 8090（8280 被 Docker Desktop 占用）
- FastAPI `root_path` 配置修复 Swagger UI 在反向代理后不可访问的问题
- Nginx 代理路径前缀剥除 bug（改用 regex location + `$1` 变量）
- Dify CORS 允许来源新增 `:8090`
- portal Dify API Key 持久化到 localStorage

---

## [v1.0.0] — 2026-04-28

> **里程碑**：WisOps MVP 可用

### 新增

- Docker Compose 一键部署（Dify + HugeGraph + graph-api）
- `graph-api`（FastAPI）：故障–方案图谱 REST API
  - `GET /health`、`POST /graph/add`、`GET /graph/query`、`GET /graph/faults`
- HugeGraph 图谱：Fault / Solution 二部图，`HAS_SOLUTION` 边
- Dify RAG 知识库问答（流式输出 + 知识引用）
- 基础导入脚本 `scripts/import_faults.py`

---

## 路线图（待完成）

以下为 PRD V2.0 差距项，优先级见 `PRD_V2.md §11`：

### 第一轮（解锁 alpha 验收）
- [x] 建 Qdrant `fault_vectors` Collection，写入故障 embedding（`POST /admin/fault-vectors/sync`）
- [ ] Dify 工作流接入 `/graph/context`（Graph-RAG 链路打通）
- [ ] 导入 LogHub 数据（补充 Fault 至 ≥ 1000 条）
- [x] 初始化 ITIL Category 分类树（`POST /admin/categories/init`）
- [x] 基于模式匹配批量生成 Alert → Fault `TRIGGERS` 边（`POST /admin/triggers/sync`）

### 第二轮（解锁 beta 验收）
- [ ] extract-worker 接入 LLM 实现真实抽取
- [ ] approve 时同步写 Dify 知识库
- [ ] 手动工单沉淀完整链路（Incident + 关联边）
- [ ] Portal 问答页展示图谱推荐卡片

### 第三轮（GA）
- [ ] 最小化角色权限（运维工程师 / 知识运营 / 管理员）
- [ ] 关键写操作审计日志
- [ ] 修复 `source_distribution` 统计逻辑
- [ ] 补齐交付物（`README_V2.md`、`DATA_IMPORT_REPORT_V2.md`、`TEST_REPORT_V2.md`）
