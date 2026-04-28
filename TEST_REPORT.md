# WisOps V1.0 测试报告

> 更新时间：2026-04-28  
> 测试环境：Windows 10 + Docker Desktop + Chrome  
> 测试范围：RAG 主链路、图谱服务、图谱管理界面、批量导入脚本

---

## 1. 环境与版本

- 项目路径：`c:\Users\lijian22\wisops`
- 核心组件：
  - Dify Web/API/Worker `0.12.1`
  - HugeGraph `1.3.0`
  - graph-api（FastAPI，自研）
  - graph-ui（Vite + React，自研）

---

## 2. 启动验证

### 用例 T01：核心服务启动

- 命令：`docker compose up -d`
- 期望：`wisops-web/api/worker/pg/redis/qdrant/hugegraph` 均启动
- 结果：✅ 通过

### 用例 T02：图谱扩展服务启动

- 命令：`docker compose --profile graph up -d --build`
- 期望：`wisops-graph-api`、`wisops-graph-ui` 启动成功
- 结果：✅ 通过

---

## 3. RAG 主链路测试

### 用例 T03：知识库上传与问答

- 步骤：
  1. 打开 `http://localhost:8281`
  2. 上传 `txt/md` 文档到知识库
  3. 在 Dify 应用提问
- 期望：返回答案并包含知识库引用
- 结果：✅ 通过

---

## 4. 图谱服务 API 测试

### 用例 T04：健康检查

- 接口：`GET /health`
- 期望：`{"status":"ok","hugegraph":"connected"}`
- 结果：✅ 通过

### 用例 T05：录入故障方案

- 接口：`POST /graph/add`
- 请求样例：`fault_name=CPU告警, solution_name=检查高负载进程并限流`
- 期望：`status=ok`，`edge_status` 为 `created` 或 `exists`
- 结果：✅ 通过

### 用例 T06：查询故障方案

- 接口：`GET /graph/query?fault_name=CPU告警`
- 期望：返回 `solutions` 且 `count >= 1`
- 结果：✅ 通过

### 用例 T07：故障列表接口

- 接口：`GET /graph/faults`
- 期望：返回故障名称列表与数量
- 结果：✅ 通过

---

## 5. 图谱前端 UI 测试

### 用例 T08：页面可访问

- 地址：`http://localhost:8282`
- 期望：页面加载成功，显示导航与状态
- 结果：✅ 通过

### 用例 T09：服务状态展示

- 期望：页面右上角显示「图谱服务正常」
- 结果：✅ 通过

### 用例 T10：前端录入流程

- 步骤：在录入页填写故障/方案并提交
- 期望：提示「录入成功」或「关系已存在」
- 结果：✅ 通过

### 用例 T11：前端查询流程

- 步骤：在查询页输入故障名并查询
- 期望：表格展示对应方案
- 结果：✅ 通过

---

## 6. 批量导入测试

### 用例 T12：样本数据导入

- 数据：`data/faults_sample.json`
- 期望：10 条全部导入成功
- 结果：✅ 通过（10/10）

### 用例 T13：扩展数据导入

- 数据：`data/faults_extended.json`
- 期望：99 条全部导入成功
- 结果：✅ 通过（99/99）

### 统计汇总

- 图谱导入总成功：109 条
- 图谱导入失败：0 条
- 说明：满足 PRD「故障节点 ≥ 100」目标

---

## 7. 问题记录与修复

- 问题 1：`graph-api` 构建失败（Docker Hub 连接超时）  
  - 处理：Docker Desktop 配置 `registry-mirrors` 镜像加速
- 问题 2：HugeGraph Gremlin 报错（`g/graph` 未绑定）  
  - 处理：`graph-api` 增加图名替换与 `g` 自动注入
- 问题 3：录入脚本子遍历报错（匿名遍历要求）  
  - 处理：改用 `__.unfold()` / `__.addV()` / `__.inV()`

---

## 8. 结论

WisOps V1.0 当前已通过核心功能测试：

- ✅ Dify RAG 主链路可用
- ✅ 图谱 API 可用（健康、录入、查询、故障列表）
- ✅ 图谱管理前端可用（录入/查询闭环）
- ✅ 批量导入脚本可用且数据规模达到 PRD 阶段目标

建议下一步进入「安全收口 + 交付打包」阶段（`.env` 化、部署手册完善、演示脚本固化）。

