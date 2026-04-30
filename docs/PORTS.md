# WisOps 端口说明（宿主机 ↔ 容器）

> **统一门户（推荐入口）**：本仓库默认 **http://localhost:8091**（`8091:80`）。旧资料或书签中的 **8090** 已不适用，除非你在本机改过 compose。  
> 来源：`docker-compose.yml`；未列出的服务**未映射到本机端口**（仅容器内网可访问）。  
> **修改映射**：编辑 `docker-compose.yml` 左侧数字（宿主机端口），改完后执行  
> `docker compose --profile graph up -d`。

---

## 1. 端口一览表

| 服务（compose `service`） | 容器名 | 宿主机地址（本机访问） | 容器内监听 | 说明 |
|---------------------------|--------|-------------------------|------------|------|
| **postgres** | wisops-pg | **5433** → | 5432 | PostgreSQL（Dify DB）；容器内仍用 5432 |
| **redis** | wisops-redis | **6380** → | 6379 | Redis；与常见本机 6379 错开 |
| **qdrant** | wisops-qdrant | **6334** → | 6333 | 向量库 HTTP/gRPC 入口（本机一般走 HTTP） |
| **hugegraph** | wisops-hugegraph | **8081** → | 8080 | HugeGraph Server + Studio 页面 |
| **api**（Dify API） | wisops-api | **5002** → | 5001 | Dify 后端 API（Worker **无对外端口**） |
| **web**（Dify Web） | wisops-web | **8281** → | 3000 | Dify 控制台前端 |
| **graph-api** | wisops-graph-api | **8021** → | 8000 | FastAPI 图谱服务（需 `--profile graph`） |
| **portal** | wisops-portal | **8091** → | 80 | 统一门户（Nginx，反代 `/graph-api`、`/dify-api`） |
| **graph-ui** | wisops-graph-ui | *未映射* | 80（镜像 EXPOSE） | 独立图谱 UI；compose 未绑主机端口，需调试时可自行加 `ports` |

**容器内仅通信、不占用宿主机端口示例**（同一 Docker 网络内用服务名访问）：

- `api:5001`、`graph-api:8000`、`hugegraph:8080`、`qdrant:6333`、`postgres:5432`、`redis:6379`
- **worker**：无 `ports`，仅后台任务

---

## 2. 日常推荐访问方式

| 用途 | URL |
|------|-----|
| 统一门户（问答 / 图谱 / 抽取 / 看板） | http://localhost:8091 |
| Dify 控制台（直连） | http://localhost:8281 |
| Dify API（直连，调试） | http://localhost:5002 |
| Graph API（直连 Swagger） | http://localhost:8021/docs |
| HugeGraph Studio | http://localhost:8081 |
| 经门户的 Graph API | http://localhost:8091/graph-api/docs |

---

## 3. 宿主机端口冲突时要注意什么

启动前请保证下面 **左侧宿主机端口** 未被本机其它程序占用（否则 `docker compose up` 会报 `port is already allocated`）：

**必须空闲（WisOps 默认占用）**

| 端口 | 服务 |
|------|------|
| **8091** | 统一门户 |
| **8281** | Dify Web |
| **5002** | Dify API |
| **8021** | graph-api |
| **8081** | HugeGraph |
| **5433** | PostgreSQL |
| **6380** | Redis |
| **6334** | Qdrant |

**常见与本机软件冲突**

- **5433**：若本机已有 PostgreSQL 占 5432，本 compose 已改用 **5433**，一般不易冲突；若 5433 也被占用，请改 compose 左端口。
- **8081**：部分本地 Java/Tomcat 会占 8080；本项目 HugeGraph 映射在 **8081**，若仍冲突可改为例如 `8082:8080`。
- **8091**：若其它代理/Nginx 占用了 8091，请改 portal 的左端口并同步门户内引用（如有硬编码）。

**排查占用（PowerShell）**

```powershell
netstat -ano | findstr ":8091"
netstat -ano | findstr ":8021"
```

---

## 4. 与 `.env` 的关系

部分 URL 出现在环境变量中（如 `CONSOLE_API_URL` 指向 `http://localhost:5002`）。若你修改了 **对外暴露端口**，需同步更新 `.env` / `docker-compose.yml` 里浏览器可访问的地址，否则 Dify 前端会请求错误端口。

---

*本文随 `docker-compose.yml` 变更而更新。*
