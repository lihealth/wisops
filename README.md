# WisOps V1.8 本地开发说明

WisOps 是一个面向智能运维场景的融合式平台；**当前发布版本：V1.8**（详见 `CHANGELOG.md`）。以下说明覆盖本地最小闭环能力：

- Dify 知识库文档管理与 RAG 问答
- HugeGraph 图谱存储（故障-方案关系）
- FastAPI 图谱查询服务（可选启用）
- Docker Compose 一键拉起核心服务

## 1. 目录结构

```text
wisops/
├─ docker-compose.yml
├─ start.ps1
├─ stop.ps1
├─ .env.example
├─ graph-api/
│  ├─ Dockerfile
│  ├─ main.py
│  └─ requirements.txt
├─ graph-ui/
│  ├─ Dockerfile
│  ├─ nginx.conf
│  ├─ package.json
│  └─ src/
├─ scripts/
│  └─ import_faults.py
└─ data/
   ├─ faults_sample.json
   └─ faults_extended.json
```

## 2. 运行环境

- Docker Desktop (Windows)
- Docker Compose v2
- 浏览器（Chrome/Edge）

## 3. 快速启动（推荐）

**下次开机怎么启动、怎么停、怎么自检**：见 **[docs/STARTUP_GUIDE.md](docs/STARTUP_GUIDE.md)**（日常推荐 `.\start.ps1 -Graph`，勿用 `down -v` 以免清空图谱卷）。

**各容器端口映射与冲突说明**：见 **[docs/PORTS.md](docs/PORTS.md)**。

### 3.1 统一门户端口与「无法访问」（必读）

| 服务 | 本机地址（默认） | 说明 |
|------|------------------|------|
| **WisOps 统一门户**（首页 / 问答 / 图谱 / 抽取 / 看板 / 资产） | **http://localhost:8091** | `docker-compose` 中 `portal` 映射为 **`8091:80`**，**请勿再使用 8090**（旧文档或书签若仍为 8090 会 `ERR_CONNECTION_REFUSED`） |
| **Graph API**（直连调试） | http://localhost:8021 | 映射 **`8021:8000`** |

若浏览器提示 **「拒绝连接」**：

1. 确认 URL 是否为 **8091**（不是 8090）。  
2. 执行 `docker compose --profile graph ps`，确认 **`wisops-portal`** 为 **Up**，且端口列为 **`0.0.0.0:8091->80/tcp`**。  
3. 若门户未启动，常见原因是 **`docker compose ... --build` 失败**（例如镜像加速 **401**），按 **[docs/DOCKER_MIRROR.md](docs/DOCKER_MIRROR.md)** 处理后再 `up -d --build`。

在项目根目录执行（核心服务）：

```powershell
cd C:\Users\lijian22\wisops
docker compose up -d
docker compose ps
```

或使用脚本：

```powershell
.\start.ps1
```

默认会启动核心服务：

- `wisops-web`（Dify 前端）
- `wisops-api`（Dify API）
- `wisops-worker`
- `wisops-pg`（PostgreSQL）
- `wisops-redis`
- `wisops-qdrant`
- `wisops-hugegraph`

访问地址：

- Dify Web: [http://localhost:8281](http://localhost:8281)
- Dify API: [http://localhost:5002](http://localhost:5002)
- HugeGraph: [http://localhost:8081](http://localhost:8081)

## 4. 最小验收流程（15 分钟）

1. 打开 Dify 控制台：`http://localhost:8281`
2. 新建知识库，上传一个 `txt/md` 文档
3. 创建一个应用并提问
4. 确认返回答案，并带有知识库引用

如果以上 4 步均正常，说明 RAG 主链路可用。

## 5. 图谱服务（graph-api + graph-ui）

> 图谱相关服务按需启用，不会默认随 `docker compose up -d` 启动。

启用命令：

```powershell
docker compose --profile graph up -d --build
```

或使用脚本：

```powershell
.\start.ps1 -Graph -Build
```

服务地址：

- **WisOps 统一门户**：[http://localhost:8091](http://localhost:8091)（推荐入口；经 Nginx 反代 `/graph-api`、`/dify-api`）
- Graph API（直连）：[http://localhost:8021](http://localhost:8021)
- Graph API Docs：[http://localhost:8021/docs](http://localhost:8021/docs)（或 [http://localhost:8091/graph-api/docs](http://localhost:8091/graph-api/docs)）
- Graph UI: [http://localhost:8282](http://localhost:8282)

接口：

- `GET /health`
- `POST /graph/add`
- `GET /graph/faults`
- `GET /graph/query?fault_name=...`

### 5.1 示例请求

新增故障-方案关系：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8021/graph/add `
  -ContentType "application/json" `
  -Body '{"fault_name":"CPU告警","solution_name":"检查高负载进程并限流","solution_description":"先top定位，再优化SQL或限流"}'
```

查询：

```powershell
Invoke-RestMethod "http://localhost:8021/graph/query?fault_name=CPU告警"
```

## 6. 常用运维命令

查看状态：

```powershell
docker compose ps
```

查看日志：

```powershell
docker compose logs api web --tail 100
```

重启单个服务：

```powershell
docker compose up -d web
docker compose up -d api
```

停止并移除容器（保留数据卷）：

```powershell
docker compose down
```

使用脚本停止：

```powershell
.\stop.ps1              # 保留数据卷
.\stop.ps1 -WithVolumes # 删除数据卷（危险操作）
```

批量导入图谱样本数据：

```powershell
python scripts/import_faults.py data/faults_sample.json --api-url http://localhost:8021/graph/add
python scripts/import_faults.py data/faults_extended.json --api-url http://localhost:8021/graph/add
```

## 7. 图谱数据丢失快速恢复

> 完整排查流程见 [docs/TESTING.md §6](docs/TESTING.md)

**现象**：图谱管理页全空，或接口报 `Undefined vertex label: 'Fault'`。

**两步恢复**：

```powershell
# 第一步：初始化 Schema（必须先做）
Invoke-RestMethod -Method POST "http://localhost:8021/admin/schema/init"

# 第二步：重新导入数据（顺序执行）
python scripts/import_v2.py data/faults_v2.jsonl --source open_gaia --entity-type Fault --api-url http://localhost:8021 --batch-id restore-faults-v2
python scripts/import_v2.py data/loghub_traceable_faults.jsonl --source logHub --entity-type Fault --api-url http://localhost:8021 --batch-id restore-loghub
# 可选：Stack Exchange（ServerFault / StackOverflow）Posts.xml 清洗导入，见 data/stackoverflow/README.md
# python scripts/import_stackoverflow.py --posts-xml data/stackoverflow/Posts.xml --api-url http://localhost:8021 --limit 3000
python scripts/parse_gaia.py --api-url http://localhost:8021
Invoke-RestMethod -Method POST "http://localhost:8021/admin/categories/init"
Invoke-RestMethod -Method POST "http://localhost:8021/admin/triggers/sync" -ContentType "application/json" -Body '{}'
```

**验收**：

```powershell
Invoke-RestMethod "http://localhost:8021/ops/stats" | ConvertTo-Json -Depth 3
# Fault ≥ 1430 | Alert = 1448 | TRIGGERS ≥ 2000 说明恢复完成
```

**常见原因**：执行了 `docker compose down -v` / `docker volume prune` 导致卷被清空；
日常停服请用 `docker compose down`（**不加 `-v`**）。

---

## 7. 常见问题排查

### 7.1 Dify 页面一直转圈

现象：

- 控制台 Network 出现 `http://api:5001/... net::ERR_NAME_NOT_RESOLVED`

原因：

- 浏览器无法解析 Docker 内网域名 `api`

修复：

- 确认 `docker-compose.yml` 中 `web.environment` 配置为：
  - `CONSOLE_API_URL=http://localhost:5002`
  - `APP_API_URL=http://localhost:5002`
  - `NEXT_PUBLIC_CONSOLE_API_URL=http://localhost:5002`
  - `NEXT_PUBLIC_APP_API_URL=http://localhost:5002`
- 然后重建 `web`：

```powershell
docker compose stop web
docker compose rm -f web
docker compose up -d --no-deps web
```

### 7.2 `graph-api` / `portal` 构建失败（拉镜像失败）

现象示例：

- `failed to resolve source metadata for docker.io/library/python:3.10-slim`
- `docker.m.daocloud.io` … **`401 Unauthorized`**（拉 `python:3.10-slim`、`node:20-alpine` 等）

原因：

- Docker Desktop 无法直连 Docker Hub；或 **`registry-mirrors` 配置的镜像站返回 401**（常见于 DaoCloud 公共加速失效）

处理：

- **401 + daocloud**：按 **[docs/DOCKER_MIRROR.md](docs/DOCKER_MIRROR.md)** 去掉或更换镜像加速，重启 Docker 后先 `docker pull python:3.10-slim`、`docker pull node:20-alpine`，再 build。
- **单纯网络/超时**：配置 Docker Desktop **HTTPS 代理**或可用的镜像加速后再执行：

```powershell
docker compose --profile graph up -d --build graph-api portal
```

临时方案：

- 先不启用 `graph-api` / `portal`，仅用核心服务验证 Dify。

## 8. 数据与安全说明

- 当前密码和密钥为开发环境占位值，仅用于本地测试
- 进入演示/交付环境前，请替换数据库密码与 `SECRET_KEY`
- 请使用 `.env.example` 复制生成 `.env`，并在本地填写真实密钥
- `.env` 已加入 `.gitignore`，禁止提交敏感配置

## 9. 后续建议

- 扩量导入 Dify 知识库数据到 500+ 片段
- 补充“部署成功检查清单”
- 完善用户手册与演示脚本

## 10. 功能开发与自测流程

每完成一项功能请先按 **[docs/TESTING.md](docs/TESTING.md)** 做最小验收再合入下一项；发起 Pull Request 时会自动出现 **[自测记录](.github/pull_request_template.md)** 清单，请如实勾选。

