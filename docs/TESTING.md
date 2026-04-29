# WisOps 功能开发与自测流程

> 目标：每完成一项功能先做最小验收，再进入下一项，避免末期集中联调爆雷。  
> 适用：graph-api、门户、导入脚本、Docker Compose 变更。

---

## 1. 每项功能的完成定义（DoD）

在开发前或开发中，用几句话写清（可记在 Issue / PR 描述里）：

| 项 | 说明 |
|----|------|
| **范围** | 改动了哪些服务/文件（如 `graph-api/main.py`、`wisops-portal/...`） |
| **成功标准** | 一条可重复执行的验证方式（curl、浏览器路径、期望 JSON 字段） |
| **回归范围** | 与本改动相关的 1～2 条既有能力（如健康检查、看板、问答单模式） |

**原则**：未通过自测的改动，不合并、不打版本标签。

---

## 2. 合入前最小测试包（按改动类型选做）

### 2.1 graph-api（Python / Gremlin）

```powershell
# 图谱栈需已启动
docker compose --profile graph ps

# 健康与 HugeGraph 连通
Invoke-RestMethod http://localhost:8002/health

# 若修改了统计或 Schema，建议再测：
Invoke-RestMethod http://localhost:8002/ops/stats

# M3：Category / CLASSIFIED_AS / TRIGGERS（可用手动三步或脚本一键）
Invoke-RestMethod -Method POST -Uri http://localhost:8002/admin/schema/init
Invoke-RestMethod -Method POST -Uri http://localhost:8002/admin/categories/init -ContentType 'application/json' -Body '{}'
Invoke-RestMethod -Method POST -Uri 'http://localhost:8002/admin/triggers/sync?top_k_per_alert=2'

# 等价：python scripts/bootstrap_m3.py
```

**Alpha #7：Fault 向量（Qdrant）与相似推荐**

需在 `.env` 或 compose 中为 graph-api 配置 **OpenAI 兼容** 的 embedding 端点（`EMBEDDING_*` 或复用 `LLM_*`），且 compose `--profile graph` 已启动 **qdrant**。

```powershell
# 全量同步 HugeGraph Fault → Qdrant collection（默认 fault_vectors）
Invoke-RestMethod -Method POST -Uri 'http://localhost:8002/admin/fault-vectors/sync'

# 换模型或清空重建
Invoke-RestMethod -Method POST -Uri 'http://localhost:8002/admin/fault-vectors/sync?full_reset=true'

# 推荐接口应返回 method=vector（已成功建索引且命中时）
Invoke-RestMethod -Method POST -Uri http://localhost:8002/graph/recommend `
  -ContentType 'application/json' -Body '{"query":"磁盘空间不足","top_k":3}' | ConvertTo-Json
```

若变更涉及子图或上下文：

```powershell
Invoke-RestMethod "http://localhost:8002/graph/context?fault_name=服务连接被拒绝（Connection Refused）"
```

`POST /graph/add` 成功后会**后台尝试**将该 Fault 的向量 upsert 到 Qdrant（已配 embedding 且与现有 collection 维度一致时生效）；仍建议大批量变更后执行一次 `POST /admin/fault-vectors/sync`。

### 2.2 数据导入脚本

- 先用 **小样本** 或 **`--dry-run`**（若脚本支持）验证映射与去重。  
- 试跑后核对：

```powershell
Invoke-RestMethod http://localhost:8002/ops/stats
```

或 HugeGraph Studio / Gremlin：`g.V().hasLabel('Fault').count()` 等。

### 2.3 wisops-portal（前端）

在项目目录执行：

```powershell
cd wisops-portal
npm run build
```

修改过门户代码时，经统一入口验证前需重建镜像：

```powershell
docker compose --profile graph build portal
docker compose --profile graph up -d portal
```

#### 2.3.1 浏览器验收（AI 问答 + 图谱，推荐）

**前置**：`docker compose --profile graph up -d` 已启动；graph-api 已配 `LLM_*`（如阿里云 **DashScope 千问**）且已执行过 `POST /admin/fault-vectors/sync`（`recommend` 返回 `method=vector` 时，前端「相似故障」为向量检索）。

| 步骤 | 操作 | 期望 |
|------|------|------|
| 1 | 浏览器打开 **`http://localhost:8090/chat`** | 页面加载正常 |
| 2 | 模式选 **「图谱融合」** 或 **「自动」** | 可不配置 Dify Key：仅图谱摘要 + 相似推荐 + 说明文案 |
| 3 | 右上角 **🔑** 填入 **Dify 应用 API Key**（`app-…`） | 可与图谱并行：**相似故障推荐卡片** + **知识库流式回答** |
| 4 | 输入自然语言问题，例如：**磁盘空间满了** | 出现 **相似故障推荐**（含相似度百分比）；若已配 Dify，下方为 **RAG 归纳步骤**（如 `df -h`、`/var/log` 等） |
| 5 | 模式切到 **「纯 RAG」** | **仅**走 Dify 知识库，**不**请求图谱推荐（需 Key） |

**首页 → 运营看板 `/dashboard`**：核对节点统计、`source_distribution`、`edge_counts`（修改 graph-api 统计后必选）。

**图谱管理 `/graph`**：至少做一次故障名查询或可视化，确认反代 `8090/graph-api` 正常。

本地开发时亦可 **`npm run dev`** 用 Vite 端口点验，但合入前仍建议按上表走 **`8090` + 重建 portal** 的路径。

### 2.4 经统一入口（Nginx）验证

避免只测直连端口、未测反代：

```powershell
Invoke-RestMethod http://localhost:8090/graph-api/health
```

---

## 3. 推荐节奏

1. 开发功能 → 按 §2 执行对应最小测试包 → 记录结果（PR 描述或评论）。  
2. 通过后再更新 `CHANGELOG.md`、里程碑或对外说明。  
3. 大功能可拆 PR：**每个 PR 自带验证步骤**，便于评审人复现。

---

## 4. 与 CI 的关系

当前仓库若已配置 GitHub Actions（如 `graph-api` 检查），**PR 通过 CI 是合入底线**；CI 未覆盖的路径（如门户 E2E、HugeGraph 联调）仍须按 §2 手动补测。

---

## 5. 常见问题

| 现象 | 优先检查 |
|------|----------|
| 图谱全空、接口 502 | 是否使用 `docker compose --profile graph up -d`；`admin/schema/init` 与导入是否执行 |
| 门户能开、图谱不可用 | `8090/graph-api/health` 与 `8002/health` 对照；Nginx 是否指向 `graph-api` |
| 纯 RAG 无答案、图谱有数据 | 问答模式是否为「纯 RAG」；Dify 知识库是否含该主题切片 |
| 问答无「相似故障推荐」、接口为 `method=keyword` | 是否已 `POST /admin/fault-vectors/sync`；embedding 与 Qdrant 是否正常（见 §2.1 Alpha #7） |

---

*文档随流程演进可修订；重大变更请同步更新本节命令与端口。*
