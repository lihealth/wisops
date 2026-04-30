# WisOps 日常启动指南

在项目根目录 `wisops` 下操作；先确认 **Docker Desktop 已运行**。

---

## 一、每次开机后怎么启动

### 1. 只要 Dify（问答、知识库）

```powershell
cd C:\Users\lijian22\wisops
.\start.ps1
# 等价：docker compose up -d
```

常用入口：**Dify 控制台** [http://localhost:8281](http://localhost:8281)

### 2. 要图谱、门户、抽取、看板（推荐日常用这个）

```powershell
cd C:\Users\lijian22\wisops
.\start.ps1 -Graph
# 等价：docker compose --profile graph up -d
```

- **统一门户**：[http://localhost:8091](http://localhost:8091)（首页 / AI 问答 / 图谱 / 抽取 / 看板 / 资产）— **不是 8090**；若沿用旧书签会拒绝连接
- **Graph API 文档**：[http://localhost:8091/graph-api/docs](http://localhost:8091/graph-api/docs)  
或直连 [http://localhost:8021/docs](http://localhost:8021/docs)
- **HugeGraph Studio**：[http://localhost:8081](http://localhost:8081)

### 3. 改过 `graph-api` 或 `wisops-portal` 代码后

```powershell
.\start.ps1 -Graph -Build
# 等价：docker compose --profile graph up -d --build
```

若 `docker build` 报 **`docker.m.daocloud.io` … `401 Unauthorized`**：说明镜像加速站不可用。请按 **[docs/DOCKER_MIRROR.md](DOCKER_MIRROR.md)** 删除或更换 `registry-mirrors`，重启 Docker 后执行：

```powershell
docker pull python:3.10-slim
docker pull node:20-alpine
```

再重新 `docker compose --profile graph up -d --build`。

构建成功后，用浏览器打开 **http://localhost:8091** 验证门户；若仍为 **连接被拒绝**，见 **§六**。

---

## 二、启动后 30 秒自检（建议养成习惯）

```powershell
docker compose --profile graph ps
Invoke-RestMethod http://localhost:8021/health
Invoke-RestMethod http://localhost:8021/graph/faults | Select-Object count
Invoke-RestMethod http://localhost:8091/graph-api/health
```


| 结果                                  | 含义                                                            |
| ----------------------------------- | ------------------------------------------------------------- |
| `health` 里 `hugegraph: connected`   | 图谱服务正常                                                        |
| `graph/faults` 的 `count` > 0        | 图里有业务数据                                                       |
| `count` 为 0 且无报错                    | 多为**新环境或卷被清空**，需按 [TESTING.md §6](TESTING.md) 做 Schema + 导入恢复 |
| 报 `Undefined vertex label: 'Fault'` | 先执行 `POST /admin/schema/init`，再按需导入数据（见下文「异常」）                |


---

## 三、关机 / 暂停时怎么停（避免误删数据）

**推荐（保留数据卷）：**

```powershell
cd C:\Users\lijian22\wisops
docker compose --profile graph stop
# 或：docker compose stop
```

**不要用**（会删掉命名卷里的图谱等数据）：

```powershell
docker compose down -v   # -v 会删卷，HugeGraph 数据会没
```

日常可用 `.\stop.ps1`（按仓库说明，勿加会删卷的参数）。

---

## 四、常见异常与一步处理


| 现象                                | 处理                                                                              |
| --------------------------------- | ------------------------------------------------------------------------------- |
| 门户能开，图谱页报错或全空                     | 确认已用 `.\start.ps1 -Graph`；再测 `http://localhost:8021/health`                     |
| `Undefined vertex label: 'Fault'` | `Invoke-RestMethod -Method POST "http://localhost:8021/admin/schema/init"`      |
| Schema 正常但 `faults` 仍为 0          | 卷曾清空，按 [TESTING.md §6.3](TESTING.md) 全量导入                                       |
| 只想确认图里大概规模                        | `Invoke-RestMethod "http://localhost:8021/ops/stats" | ConvertTo-Json -Depth 4` |


更完整的恢复命令与验收指标见 **[docs/TESTING.md §6](TESTING.md)**；README 中也有「图谱数据丢失快速恢复」摘要。

---

## 五、与文档的对应关系


| 文档                            | 内容                    |
| ----------------------------- | --------------------- |
| [README.md](../README.md)     | 目录、端口、快速启动、数据恢复摘要     |
| [docs/PORTS.md](PORTS.md)     | 各服务宿主机端口 ↔ 容器端口、冲突说明   |
| 门户 `/assets`               | 资产列表与详情（关联告警）               |
| [docs/TESTING.md](TESTING.md) | 自测流程、图谱丢失排查与全量恢复      |
| 本文                            | **下次开机怎么启动、怎么停、怎么自检** |
| [DOCKER_MIRROR.md](DOCKER_MIRROR.md) | 构建报 **401**、无法拉 `python`/`node` 镜像时排查镜像加速 |


---

## 六、浏览器打不开 `localhost:8091` 或误用 8090

| 现象 | 原因与处理 |
|------|------------|
| 访问 **8090** 提示拒绝连接 | 当前 compose **统一门户映射在 8091**，请改用 **http://localhost:8091** |
| 访问 **8091** 仍拒绝连接 | **`wisops-portal` 未运行**：先 `docker compose --profile graph ps`；若无 Up，检查是否未加 `--profile graph` 或 **build 失败**（见 §一.3 与 [DOCKER_MIRROR.md](DOCKER_MIRROR.md)） |
| 仅 Dify 能开、8091 不通 | 你只执行了 `docker compose up -d`（无 graph），需 **`.\start.ps1 -Graph`** 或 `docker compose --profile graph up -d` |

确认门户已监听：

```powershell
docker compose --profile graph ps
# wisops-portal 应显示 0.0.0.0:8091->80/tcp
```

---

*端口以本仓库 `docker-compose.yml` 为准；若本机改过端口，请同步替换上述 URL。*