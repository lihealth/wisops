# Docker 镜像拉取 401（DaoCloud 等）排查与修复

## 现象

执行 `docker compose build` 或 `--build` 时出现类似报错：

```text
unexpected status from HEAD request to https://docker.m.daocloud.io/v2/library/python/manifests/3.10-slim ... 401 Unauthorized
unexpected status ... docker.m.daocloud.io/v2/library/node/manifests/20-alpine ... 401 Unauthorized
```

说明 Docker Desktop 配置了 **`registry-mirrors`** 指向 DaoCloud（或其它镜像站），但该站对当前请求返回 **401**（鉴权/配额/线路变更），导致无法解析官方镜像元数据。

---

## 处理步骤（推荐）

### 1. 打开 Docker Engine 配置

1. 打开 **Docker Desktop**  
2. **Settings（设置）** → **Docker Engine**  
3. 你会看到一段 JSON 配置。

### 2. 修改 `registry-mirrors`

找到其中的 **`registry-mirrors`** 数组：

- **若包含** `https://docker.m.daocloud.io`（或带 `daocloud` 的地址）：  
  - **先删掉该项**，或暂时把整个 **`registry-mirrors`** 键删掉（允许为空 / 不配置镜像加速）。  
- **Apply & restart**，等待 Docker 完全重启。

### 3. 验证能否直连拉官方镜像

在 PowerShell 中执行：

```powershell
docker pull python:3.10-slim
docker pull node:20-alpine
docker pull nginx:alpine
```

均能 **Pull complete** 后，再回到项目目录：

```powershell
cd C:\Users\lijian22\wisops
docker compose --profile graph build portal graph-api
docker compose --profile graph up -d portal graph-api
```

门户容器正常 **Up** 后，在浏览器打开 **http://localhost:8091** 验证（完整图谱栈请用 `docker compose --profile graph up -d` 或 `.\start.ps1 -Graph`，见 [STARTUP_GUIDE.md](STARTUP_GUIDE.md)）。

---

## 可选方案

| 方案 | 说明 |
|------|------|
| **登录 Docker Hub** | Docker Desktop → **Sign in**，减轻匿名拉取限流（仍可能被墙或慢，但与 401 镜像站无关） |
| **换其它镜像加速** | 使用阿里云等控制台生成的 **专属加速地址**，替换写进 `registry-mirrors`（不要使用过期的公共 DaoCloud 地址若持续 401） |
| **仅构建失败时** | 先确认本机已能 `docker pull` 上述基础镜像，再 build；基础镜像在本地缓存后构建会快很多 |

---

## 注意

- 修改 `Docker Engine` JSON 时须保证 **JSON 语法合法**（逗号、引号成对），否则 Docker 无法启动。  
- 若团队统一要求必须走内网镜像，请向运维索取 **当前可用的 registry 地址**，不要沿用已 401 的旧配置。

---

*与本仓库 `graph-api`（`FROM python:3.10-slim`）、`wisops-portal`（`node` + `nginx`）构建直接相关。*
