# WisOps V1.0 (MVP) 本地开发说明

WisOps 是一个面向智能运维场景的融合式平台，当前版本聚焦以下最小闭环能力：

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

- Graph API: [http://localhost:8002](http://localhost:8002)
- Graph API Docs: [http://localhost:8002/docs](http://localhost:8002/docs)
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
  -Uri http://localhost:8002/graph/add `
  -ContentType "application/json" `
  -Body '{"fault_name":"CPU告警","solution_name":"检查高负载进程并限流","solution_description":"先top定位，再优化SQL或限流"}'
```

查询：

```powershell
Invoke-RestMethod "http://localhost:8002/graph/query?fault_name=CPU告警"
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
python scripts/import_faults.py data/faults_sample.json --api-url http://localhost:8002/graph/add
python scripts/import_faults.py data/faults_extended.json --api-url http://localhost:8002/graph/add
```

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

### 7.2 `graph-api` 构建失败（拉不到 `python:3.10-slim`）

现象：

- `failed to resolve source metadata for docker.io/library/python:3.10-slim`

原因：

- Docker Desktop 无法连接 Docker Hub（常见为代理/网络问题）

临时方案：

- 先不启用 `graph-api`，优先验证 Dify 主链路

长期方案：

- 配置 Docker Desktop 的 HTTPS 代理或镜像加速后再执行：

```powershell
docker compose --profile graph up -d --build graph-api
```

## 8. 数据与安全说明

- 当前密码和密钥为开发环境占位值，仅用于本地测试
- 进入演示/交付环境前，请替换数据库密码与 `SECRET_KEY`
- 请使用 `.env.example` 复制生成 `.env`，并在本地填写真实密钥
- `.env` 已加入 `.gitignore`，禁止提交敏感配置

## 9. 后续建议

- 扩量导入 Dify 知识库数据到 500+ 片段
- 补充“部署成功检查清单”
- 完善用户手册与演示脚本

