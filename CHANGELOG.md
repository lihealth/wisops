# WisOps 版本变更日志

> 遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 规范  
> 版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)

---

## [Unreleased]

### 新增

- graph-api：Qdrant **`fault_vectors`** 同步接口 `POST /admin/fault-vectors/sync`（OpenAI 兼容 `/v1/embeddings`）
- `POST /graph/recommend` 优先向量检索，失败或无索引时降级关键词；响应增加 **`method`**：`vector` / `keyword` / `keyword_fallback`
- `POST /graph/add`：写入成功后**后台**增量更新该 Fault 的 Qdrant 向量（配置齐全且维度与 collection 一致时）
- Docker：`graph-api` 依赖 **qdrant**，注入 `QDRANT_URL` 与可选 `EMBEDDING_*`

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
