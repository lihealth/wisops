# WisOps V1.0 产品需求文档（PRD）

> 文档版本：v1.1  
> 更新时间：2026-04-28  
> 编写依据：项目讨论记录、V1.0 研发计划、V1.0 进度看板（2026-04-27）  
> 阅读对象：研发、测试、交付  

---

## 目录

1. [产品概述](#1-产品概述)
2. [用户角色](#2-用户角色)
3. [功能模块总览](#3-功能模块总览)
4. [功能详细说明](#4-功能详细说明)
   - 4.1 [知识库管理（KB）](#41-知识库管理kb--已完成-80)
   - 4.2 [智能问答（QA）](#42-智能问答qa--已完成-80)
   - 4.3 [预置数据（DATA）](#43-预置数据data--进行中-50)
   - 4.4 [图谱查询服务（GR-API）](#44-图谱查询服务gr-api--进行中-35)
   - 4.5 [图谱管理界面（GR-UI）](#45-图谱管理界面gr-ui--未开始-0)
   - 4.6 [用户认证（USR）](#46-用户认证usr--进行中-60)
   - 4.7 [部署与配置（OPS）](#47-部署与配置ops--进行中-70)
5. [系统架构](#5-系统架构)
6. [接口规范](#6-接口规范)
7. [数据规范](#7-数据规范)
8. [非功能性需求](#8-非功能性需求)
9. [交付物清单](#9-交付物清单)
10. [后续开发路线图](#10-后续开发路线图)
11. [验收标准](#11-验收标准)
12. [风险与依赖](#12-风险与依赖)

---

## 1. 产品概述

### 1.1 产品定位

**WisOps**（Wise Operations）是面向中小团队的**智能运维知识融合平台**，旨在把**非结构化运维文档**（知识库 + RAG 问答）与**结构化故障–方案关系图谱**统一管理，让运维工程师：

- 用自然语言提问，快速从海量文档中召回有效答案；
- 通过图谱录入与查询，积累故障–解决方案关联关系；
- 本地私有化部署，数据不出内网。

### 1.2 版本范围

本 PRD 覆盖 **V1.0 MVP 范围**，以「可演示、可验收、可本地一键部署」为最终交付标准。

### 1.3 核心价值主张

| 维度 | 价值 |
|------|------|
| 知识沉淀 | 将运维经验文档化、向量化，不依赖个人记忆 |
| 快速检索 | RAG 语义问答替代全文搜索，返回精确段落与引用 |
| 图谱关联 | 故障与方案形成强关联，支持按故障类型快速查方案 |
| 私有部署 | Docker Compose 一键启动，无外部依赖，数据自主可控 |

---

## 2. 用户角色

| 角色 | 说明 | 典型操作 |
|------|------|----------|
| **管理员** | 系统管理、知识库运营 | 上传文档、管理知识库、录入图谱数据、查看系统状态 |
| **运维工程师** | 日常使用者 | 自然语言问答、按故障名查方案 |
| **只读用户（可选）** | 轻量访问 | 仅查询，不录入、不上传 |

> V1.0 聚焦 **管理员** 与 **运维工程师** 两种角色；只读用户为可选扩展。

---

## 3. 功能模块总览

| 模块 ID | 模块名称 | V1.0 范围 | 完成度 | 状态 |
|---------|----------|-----------|--------|------|
| KB | 知识库管理 | 文档上传、切片、向量化、可检索 | **80%** | ✅ 已完成 |
| QA | 智能问答 | 自然语言问答 + 知识引用 | **80%** | ✅ 已完成 |
| DATA | 预置数据 | 500+ 文档片段、100+ 故障节点导入 | **50%** | 🔄 进行中 |
| GR-API | 图谱查询服务 | 故障–方案写入与查询 REST 接口 | **35%** | 🔄 进行中 |
| GR-UI | 图谱管理界面 | 录入表单 + 查询结果页 | **0%** | ⏳ 未开始 |
| USR | 用户认证 | 管理员/普通用户登录与权限边界 | **60%** | 🔄 进行中 |
| OPS | 部署与配置 | 私有化一键部署、健康检查、安全收口 | **70%** | 🔄 进行中 |

> **图例**：✅ 已完成并通过验证 / 🔄 部分完成或未形成稳定验收 / ⏳ 未开始

---

## 4. 功能详细说明

### 4.1 知识库管理（KB）— ✅ 已完成 80%

#### 已完成

- 通过 **Dify 控制台**创建、命名、删除知识库。
- 支持上传 **txt / md** 格式文档，系统自动完成切片与向量化。
- 文档上传后可在 Dify 应用中检索并召回。
- 文件内容持久化存储（本地存储卷 `api_storage`）。

#### 待完成

- [ ] **文档管理**：支持查看已上传文档列表、删除单条文档。
- [ ] **格式扩展（可选）**：支持 PDF / Word 格式（需 Dify 版本支持，V1 可评估）。
- [ ] **版本说明**：在用户手册中写清知识库的创建与维护操作路径。

#### 验收标准

- 上传一个 txt/md 文档后，在应用中提问能检索到对应内容，并在回答中显示引用来源。

---

### 4.2 智能问答（QA）— ✅ 已完成 80%

#### 已完成

- 通过 **Dify 应用** 创建基于知识库的 RAG 问答应用。
- 自然语言提问，返回答案并附带**文档引用段落**。
- 对话历史可在 Dify 控制台查看。

#### 待完成

- [ ] **问答样例验收**：固定 5～10 个标准问答用例，记录命中率（见 DATA 模块）。
- [ ] **应用发布配置**：确认应用公开地址或 API Key 供外部调用。

#### 验收标准

- 给定 5 个预置问题，全部返回有效答案且带引用，回答准确率 ≥ 80%。

---

### 4.3 预置数据（DATA）— 🔄 进行中 50%

#### 已完成

- `stackoverflow_qa.txt` 已入库并通过基本问答验证。
- 示例故障数据文件 `data/faults_sample.json` 已准备（10 条故障–方案数据）。
- 导入脚本 `scripts/import_faults.py` 已完成，支持 **CSV / JSON / TXT** 格式自动解析。

#### 待完成

- [ ] **知识库扩量**：完成 StackOverflow + GAIA 运维语料规模化导入，达到 **≥ 500 文档片段**。
- [ ] **图谱数据导入**：使用 `scripts/import_faults.py` 批量导入图谱数据，达到 **≥ 100 故障节点**。
- [ ] **导入统计报告**：记录导入条数、失败数、重试数，输出为 `DATA_IMPORT_REPORT.md`。
- [ ] **数据质量验证**：用 5～10 个标准问题复测，记录命中与不命中情况。

#### 导入脚本使用说明

```powershell
# 导入 JSON 格式数据
python scripts/import_faults.py data/faults_sample.json --api http://localhost:8021

# 导入 CSV 格式数据（字段：fault_name,solution_name,solution_description）
python scripts/import_faults.py data/faults.csv --api http://localhost:8021
```

#### 验收标准

- 知识库片段数 ≥ 500，图谱故障节点数 ≥ 100，导入成功率 ≥ 90%，有导入统计报告。

---

### 4.4 图谱查询服务（GR-API）— 🔄 进行中 35%

#### 已完成

- 服务代码位于 `graph-api/main.py`，基于 **FastAPI** 实现。
- 启动时自动建图 schema（`Fault` 顶点、`Solution` 顶点、`HAS_SOLUTION` 边）。
- 三个 HTTP 接口已实现（代码完成，端到端验收未通过）：
  - `GET /health`
  - `POST /graph/add`
  - `GET /graph/query`
- 多 Gremlin endpoint 探活逻辑（兼容 HugeGraph 不同版本路径）。
- Docker Compose 中已配置为 `profile: graph` 按需启动。

#### 待完成

- [ ] **端到端验收**：`graph-api` 容器化后，调通 `/graph/add` 与 `/graph/query` 完整链路。
- [ ] **容器构建问题解决**：解决 Docker Hub 拉取 `python:3.10-slim` 网络问题（镜像加速 / 代理 / 离线包）。
- [ ] **故障列表接口（新增）**：`GET /graph/faults` 返回所有已录入的故障名列表，供 GR-UI 下拉选择。
- [ ] **接口错误码标准化**：统一返回结构 `{status, message, data}`，HTTP 状态码与业务错误分离。
- [ ] **API 文档**：Swagger/OpenAPI 文档页可访问（FastAPI 默认 `/docs`）。

#### 接口列表（最终目标）

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | `/health` | 服务与图库健康检查 | ✅ 代码完成 |
| POST | `/graph/add` | 新增故障–方案关系 | ✅ 代码完成 |
| GET | `/graph/query?fault_name=` | 查询指定故障的方案列表 | ✅ 代码完成 |
| GET | `/graph/faults` | 获取所有故障名列表 | ⏳ 待新增 |

#### 验收标准

- 容器内 `graph-api` 启动后，`/health` 返回 `{"status":"ok"}`；调用 `/graph/add` 写入，再 `/graph/query` 查询能回显同一条数据。

---

### 4.5 图谱管理界面（GR-UI）— ⏳ 未开始 0%

> 根据产品闭环方案讨论（2026-04-28），已定下以下方案。

#### 方案定稿

| 决策项 | 结论 |
|--------|------|
| 技术栈 | Vite + React + TypeScript |
| 部署方式 | Docker 静态资源服务（`nginx:alpine` 镜像） |
| 访问端口 | **8282**（容器 80，对外 8282） |
| 跨域处理 | Nginx 将 `/api/` 反代至 `graph-api:8000`（同源，无 CORS 问题） |
| 启动条件 | 与 `graph-api` 同属 `graph` profile，`docker compose --profile graph up` 一键启动 |
| 第一阶段 | 独立端口（8282），与 Dify（8281）并列 |
| 第二阶段（可选） | Nginx 反代统一入口或 Dify 工作流内嵌 HTTP 节点 |

#### 目录结构

```text
wisops/
  graph-ui/
    src/
      App.tsx
      pages/
        AddFault.tsx      # 录入页
        QueryFault.tsx    # 查询页
      components/
        FaultForm.tsx
        SolutionTable.tsx
        HealthBadge.tsx
    nginx.conf            # 静态资源 + /api/ 反代配置
    Dockerfile
    package.json
```

#### 功能需求

**F1 - 故障录入页（必须）**

- 表单字段：故障名（必填）、方案名（必填）、方案描述（选填，多行文本）。
- 提交按钮，调用 `POST /api/graph/add`。
- 返回结果展示：
  - 成功（`edge_status: created`）：绿色提示「录入成功」。
  - 已存在（`edge_status: exists`）：蓝色提示「关系已存在」。
  - 错误：红色提示，显示 API 返回的 `detail` 字段。

**F2 - 故障查询页（必须）**

- 输入框：故障名（支持手动输入或下拉选择，下拉数据来自 `GET /api/graph/faults`）。
- 查询按钮，调用 `GET /api/graph/query?fault_name=...`。
- 结果以表格展示：方案名、方案描述。
- 若无结果：显示「该故障暂无方案记录，请前往录入」（含录入页跳转链接）。

**F3 - 服务状态（可选）**

- 页脚或页头显示 `graph-api` 健康状态（调用 `GET /api/health`），区分「已连接」和「服务不可用」。

#### UI 风格要求

- 简洁实用，以运维工具风格为主（深色顶导或白底极简皆可）。
- 无需复杂动画，重点在清晰的表单与数据展示。
- 响应式基础支持，适配 1280px 以上宽屏即可。

#### 验收标准

- 浏览器打开 `http://localhost:8282`，无 Postman 完成：录入一条故障–方案 → 在查询页输入故障名 → 看到刚录入的方案 → 全程无控制台报错。

---

### 4.6 用户认证（USR）— 🔄 进行中 60%

#### 已完成

- Dify 提供默认认证机制，管理员账号可登录控制台。
- 知识库操作、应用管理均受登录保护。

#### 待完成

- [ ] **权限矩阵文档**：明确管理员 vs 普通用户可操作范围（Dify 侧 + GR-UI 侧）。
- [ ] **GR-UI 鉴权（V1 最小实现）**：可先不做登录，通过内网访问限制代替（生产前再加）；或在 Nginx 层增加 Basic Auth。
- [ ] **安全收口**（见 OPS 模块）。

#### V1 权限矩阵（目标）

| 操作 | 管理员 | 运维工程师 |
|------|--------|------------|
| 知识库上传/删除 | ✅ | ❌ |
| 应用配置与发布 | ✅ | ❌ |
| RAG 问答 | ✅ | ✅ |
| 图谱故障录入 | ✅ | ✅ |
| 图谱故障查询 | ✅ | ✅ |
| 系统配置 | ✅ | ❌ |

---

### 4.7 部署与配置（OPS）— 🔄 进行中 70%

#### 已完成

- `docker-compose.yml` 覆盖全部服务：PostgreSQL / Redis / Qdrant / HugeGraph / Dify API / Dify Worker / Dify Web。
- Dify 访问地址、CORS 配置已修复（`CONSOLE_API_URL` 等环境变量正确）。
- `README.md` 包含启动步骤、验收流程、常见排障。
- 端口规划避免与系统本地端口冲突（PG→5433、Redis→6380、Qdrant→6334、HugeGraph→8081、Dify→8281/5002、graph-api→8021）。

#### 待完成

- [ ] **`start.ps1` / `stop.ps1`**：封装常用启动/停止命令，含 `--profile graph` 选项。
- [ ] **`graph-ui` 容器化**：在 `docker-compose.yml` 中新增 `graph-ui` 服务，与 `graph-api` 同 profile。
- [ ] **`graph-api` 构建问题**：解决 Docker Hub 网络受阻，可通过以下方案之一处理：
  - 配置 Docker Desktop 的 HTTPS 代理
  - 使用国内镜像源
  - 离线构建后 `docker save / load`
- [ ] **`.env` 安全配置**：将 `POSTGRES_PASSWORD`、`SECRET_KEY` 等敏感项迁至 `.env` 文件，`docker-compose.yml` 使用 `${VAR}` 引用，`.env` 加入 `.gitignore`。
- [ ] **健康检查说明**：在 README 或部署指南中补充各服务健康检查命令。
- [ ] **数据备份说明**：说明 Docker 数据卷的备份与恢复方法。

#### 最终端口规划（含 GR-UI）

| 服务 | 对外端口 | 说明 |
|------|----------|------|
| Dify Web | 8281 | 主控制台与问答界面 |
| Dify API | 5002 | 内部/API 调用 |
| HugeGraph | 8081 | 图数据库管理界面 |
| graph-api | 8021 | 图谱 REST 接口 |
| graph-ui | **8282** | 图谱管理前端（新增） |
| PostgreSQL | 5433 | 数据库（内部） |
| Redis | 6380 | 缓存（内部） |
| Qdrant | 6334 | 向量库（内部） |

---

## 5. 系统架构

### 5.1 整体架构图

```
浏览器
  ├── :8281  →  Dify Web (Next.js)
  │               └── → :5002  Dify API
  │                           ├── PostgreSQL :5433
  │                           ├── Redis :6380
  │                           └── Qdrant :6334 (向量检索)
  │
  └── :8282  →  graph-ui (Nginx)
                  ├── /          → 静态资源 (React)
                  └── /api/      → graph-api :8000 (FastAPI) [反代]
                                       └── HugeGraph :8080 (Gremlin)
                                                   └── hugegraph_data 卷
```

### 5.2 数据流

**RAG 问答链路**

```
用户提问 → Dify Web → Dify API → Qdrant(向量检索) → 召回文档片段 → LLM 生成答案+引用 → 用户
```

**图谱录入链路**

```
用户填表(GR-UI) → POST /api/graph/add → graph-api → Gremlin → HugeGraph 写入节点+边
```

**图谱查询链路**

```
用户输入故障名(GR-UI) → GET /api/graph/query → graph-api → Gremlin → HugeGraph 查询 → 返回方案列表 → GR-UI 表格展示
```

### 5.3 技术选型

| 组件 | 技术 | 来源 |
|------|------|------|
| RAG + 知识库 | Dify 0.12.1 | 官方 Docker 镜像 |
| 向量存储 | Qdrant | 官方 Docker 镜像 |
| 图数据库 | HugeGraph 1.3.0 | 官方 Docker 镜像 |
| 图谱 API | FastAPI + Python | 自研 (`graph-api/`) |
| 图谱前端 | Vite + React + TypeScript | 自研 (`graph-ui/`) 🆕 |
| 前端服务 | Nginx (Alpine) | 官方 Docker 镜像 🆕 |
| 关系数据库 | PostgreSQL 15 | 官方 Docker 镜像 |
| 缓存/消息队列 | Redis 7 | 官方 Docker 镜像 |
| 编排 | Docker Compose v2 | 宿主机 |

---

## 6. 接口规范

### 6.1 graph-api 接口

**基础 URL（容器化）**：`http://localhost:8021`  
**基础 URL（GR-UI 内通过 Nginx 反代）**：`/api`

#### GET /health

```json
// 响应（正常）
{"status": "ok", "hugegraph": "connected"}

// 响应（降级）
{"status": "degraded", "hugegraph": "disconnected"}
```

#### POST /graph/add

```json
// 请求体
{
  "fault_name": "CPU告警",           // 必填，1-200字符
  "solution_name": "检查高负载进程并限流",  // 必填，1-200字符
  "solution_description": "使用 top/htop 定位..."  // 选填，最多2000字符
}

// 成功响应
{"status": "ok", "edge_status": "created"}   // 新建
{"status": "ok", "edge_status": "exists"}    // 已存在（幂等）
```

#### GET /graph/query

```
GET /graph/query?fault_name=CPU告警
```

```json
// 成功响应
{
  "fault_name": "CPU告警",
  "solutions": [
    {
      "id": "...",
      "name": "检查高负载进程并限流",
      "description": "使用 top/htop 定位高占用进程，先限流再排查..."
    }
  ],
  "count": 1
}
```

#### GET /graph/faults（待新增）

```json
// 成功响应
{
  "faults": ["CPU告警", "MySQL连接数过高", "磁盘空间不足"],
  "count": 3
}
```

### 6.2 错误响应格式（统一目标）

```json
{
  "detail": "fault_name cannot be empty"
}
```

HTTP 状态码说明：

| 状态码 | 场景 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 502 | HugeGraph 返回错误 |
| 503 | HugeGraph 不可达 |

---

## 7. 数据规范

### 7.1 图谱数据模型

```
顶点类型 Fault
  属性：name (String, 主键)

顶点类型 Solution
  属性：name (String, 主键)
         description (String)

边类型 HAS_SOLUTION
  起点：Fault → 终点：Solution
```

### 7.2 预置数据要求

| 数据集 | 格式 | 目标量 | 导入方式 |
|--------|------|--------|----------|
| 运维知识文档（StackOverflow/GAIA） | txt/md | ≥ 500 片段 | Dify 知识库上传 |
| 故障–方案关系数据 | JSON/CSV | ≥ 100 故障节点 | `scripts/import_faults.py` |

### 7.3 导入脚本字段映射

`scripts/import_faults.py` 支持以下字段别名，自动归一化：

| 目标字段 | 支持的原始字段名 |
|----------|-----------------|
| `fault_name` | `fault_name`, `fault`, `faultTitle`, `name` |
| `solution_name` | `solution_name`, `solution`, `solutionTitle`, `title` |
| `solution_description` | `solution_description`, `description`, `detail` |

---

## 8. 非功能性需求

| 类别 | 要求 | 当前状态 |
|------|------|----------|
| **可用性** | 本地环境容器重启后 5 分钟内可访问 | ✅ `restart: unless-stopped` 已配置 |
| **性能** | 问答响应 ≤ 10 秒（含 LLM 调用） | 待测量 |
| **图谱查询** | 单次 Gremlin 查询 ≤ 2 秒 | 待测量 |
| **安全** | 密码/密钥不硬编码入 git | ⏳ 待 `.env` 化 |
| **私有化** | 全程无外网依赖（LLM 除外） | ✅ 向量库/图库均本地 |
| **可维护** | 日志可通过 `docker compose logs` 查看 | ✅ 已可用 |
| **可扩展** | 新增数据源或图谱接口不影响现有服务 | ✅ 微服务解耦 |

---

## 9. 交付物清单

| 交付物 | 类型 | 状态 |
|--------|------|------|
| `docker-compose.yml`（含 graph-ui） | 配置 | 🔄 待更新 |
| `graph-api/`（Dockerfile + main.py） | 代码 | ✅ 基本完成 |
| `graph-ui/`（React + Nginx） | 代码 | ⏳ 待开发 |
| `scripts/import_faults.py` | 工具脚本 | ✅ 完成 |
| `data/faults_sample.json` | 示例数据 | ✅ 完成 |
| `README.md` | 部署文档 | 🔄 待补 graph-ui 说明 |
| `PRD.md`（本文档） | 产品文档 | ✅ 本次生成 |
| `TEST_REPORT.md` | 测试报告 | ⏳ 待产出 |
| `DATA_IMPORT_REPORT.md` | 数据导入报告 | ⏳ 待产出 |
| `start.ps1` / `stop.ps1` | 运维脚本 | ⏳ 待开发 |
| `.env.example` | 安全配置模板 | ⏳ 待产出 |
| 演示脚本（5 分钟） | 文档 | ⏳ 待产出 |

---

## 10. 后续开发路线图

### 优先级定义

- **P0**：阻塞交付，必须完成
- **P1**：核心功能完整性，强烈建议完成
- **P2**：提升体验，有时间再做

### 任务清单

#### 阶段一：图谱链路闭环（P0）

| # | 任务 | 模块 | 说明 |
|---|------|------|------|
| 1 | 解决 `graph-api` 容器构建问题 | OPS | 镜像加速 / 代理 / 离线包 |
| 2 | 新增 `GET /graph/faults` 接口 | GR-API | 供 GR-UI 下拉使用 |
| 3 | `graph-api` 端到端验收（`/add` + `/query`） | GR-API | 含容器化运行 |
| 4 | 开发 `graph-ui`（录入 + 查询两页） | GR-UI | React + Nginx，端口 8282 |
| 5 | 更新 `docker-compose.yml`，新增 `graph-ui` 服务 | OPS | 与 `graph-api` 同 profile |

#### 阶段二：数据与质量（P0）

| # | 任务 | 模块 | 说明 |
|---|------|------|------|
| 6 | 规模化导入知识库数据（≥500 片段） | DATA | Dify 批量上传 |
| 7 | 规模化导入图谱数据（≥100 故障节点） | DATA | `import_faults.py` |
| 8 | 产出 `DATA_IMPORT_REPORT.md` | DATA | 含统计数据 |
| 9 | 固定 5～10 问答用例，产出命中率记录 | QA | 写入 TEST_REPORT |

#### 阶段三：交付与安全（P1）

| # | 任务 | 模块 | 说明 |
|---|------|------|------|
| 10 | 敏感配置迁至 `.env`，提供 `.env.example` | OPS | 安全收口 |
| 11 | 产出 `TEST_REPORT.md` | 测试 | 覆盖 RAG + 图谱 |
| 12 | 补充 README（graph-ui 启动、端口说明） | 文档 | — |
| 13 | 编写 `start.ps1` / `stop.ps1` | OPS | 统一启动入口 |
| 14 | 5 分钟演示脚本（固定问题 + 固定结果） | 交付 | — |

#### 阶段四：可选增强（P2）

| # | 任务 | 模块 | 说明 |
|---|------|------|------|
| 15 | GR-UI 与 Dify 统一入口（Nginx 反代） | OPS | 第二阶段统一门户 |
| 16 | Dify 工作流集成图谱查询（HTTP 节点） | QA+GR | 对话式查方案 |
| 17 | GR-UI 添加 Basic Auth | USR | 简易鉴权 |
| 18 | 故障列表管理（查看/删除） | GR-API+UI | 需新增 DELETE 接口 |

---

## 11. 验收标准

### V1.0 最终验收清单（全部通过即可交付）

#### 基础设施

- [ ] `docker compose up -d` 后，所有核心服务（PG/Redis/Qdrant/HugeGraph/Dify API/Web/Worker）均 `Up`。
- [ ] `docker compose --profile graph up -d --build` 后，`graph-api` 与 `graph-ui` 均 `Up`。

#### 知识库 + 问答

- [ ] 能在 Dify 控制台上传文档、完成知识库配置。
- [ ] 提 5 个预置问题，≥4 个返回带引用的有效答案。

#### 图谱服务

- [ ] `GET http://localhost:8021/health` 返回 `{"status":"ok"}`。
- [ ] `POST /graph/add` 写入一条，再 `GET /graph/query` 能查询到。
- [ ] `GET /graph/faults` 返回已有故障列表。

#### 图谱界面

- [ ] 浏览器打开 `http://localhost:8282`，页面正常加载。
- [ ] 通过录入表单新增一条故障–方案，提示「录入成功」。
- [ ] 在查询页输入故障名，表格展示对应方案。
- [ ] `graph-api` 异常时界面有明确错误提示。

#### 数据

- [ ] 知识库文档片段数 ≥ 500。
- [ ] 图谱故障节点数 ≥ 100。

#### 文档与安全

- [ ] `TEST_REPORT.md` 存在且记录了问答命中结果。
- [ ] 无密码/密钥硬编码（使用 `.env` 管理）。
- [ ] README 描述包含 graph-ui 的启动方式与端口说明。

---

## 12. 风险与依赖

| 风险 | 级别 | 影响 | 处理策略 |
|------|------|------|----------|
| Docker Hub 不可达，`graph-api` / `graph-ui` 构建失败 | 高 | 阻塞图谱功能演示 | 优先配置镜像加速；次选本机 `uvicorn` 绕过容器化 |
| LLM 模型服务不稳定（外部依赖） | 中 | 影响问答质量与响应时间 | 预置固定问答用例，离线演示时用缓存结果备份 |
| 预置数据质量参差 | 中 | 影响问答可用性 | 先用高质量样本构建演示集，再逐步扩量 |
| HugeGraph 版本差异导致 Gremlin 路径不一致 | 中 | `graph-api` 连接失败 | 已做多路径探活，测试时记录实际可用 endpoint |
| 权限边界不清晰 | 低 | 影响验收口径 | 在交付前确认权限矩阵，GR-UI 先走内网访问限制 |

---

*本文档随开发进展持续更新。各模块完成度以最新进度看板为准，PRD 应同步修订。*
