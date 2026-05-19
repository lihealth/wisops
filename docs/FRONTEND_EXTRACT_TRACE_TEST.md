# 前端联调测试文档（抽取审核与文档追溯）

## 1. 测试目标

验证前端页面在以下链路可用：

- 提交抽取任务（`/extract/submit`）
- 查看待审核队列（`/extract/queue`）
- 审核通过（`/extract/queue/{item_id}/approve`）
- 查看文档追溯索引（`/extract/doc-links`）

同时确认 `approve` 后会产生：

- Dify `document_id`
- 图谱文档关联结果 `graph_document_link`

## 2. 前置条件

- 已启动服务：`graph-api`、`hugegraph`、`qdrant`、`dify`（若启用同步）
- `graph-api` 地址：`http://localhost:8021`
- `.env` 中已配置 Dify 数据集参数（若要验证 `document_id`）

## 3. 建议测试数据

可在前端输入以下文本（用于提交抽取）：

```text
故障现象：Redis 主从复制中断，日志出现 Connection reset by peer。
处置建议：检查网络抖动，调大 repl-backlog-size，必要时重建复制链路。
```

`source_hint` 建议填：`frontend-manual-test`

## 4. 接口联调步骤（可对照前端操作）

### 步骤 A：提交抽取任务

- 页面动作：点击“提交抽取”按钮
- 预期：
  - 返回 `status=ok`
  - 返回 `job_id`

示例请求：

```bash
curl -X POST http://localhost:8021/extract/submit \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"故障现象：Redis 主从复制中断...\",\"source_hint\":\"frontend-manual-test\"}"
```

### 步骤 B：查看待审核队列

- 页面动作：打开“待审核”列表并刷新
- 预期：
  - 能看到新记录
  - 字段包含 `id/job_id/fault_name/solution_name/confidence/status`
  - `status` 为 `pending`

示例请求：

```bash
curl "http://localhost:8021/extract/queue?status=pending"
```

### 步骤 C：执行审核通过

- 页面动作：点击“通过/Approve”
- 预期：
  - 返回 `status=ok`
  - 返回 `dify_sync`（若配置了 Dify，`ok=true` 且有 `document_id`）
  - 返回 `graph_document_link.ok=true`

示例请求：

```bash
curl -X POST http://localhost:8021/extract/queue/{item_id}/approve
```

### 步骤 D：验证文档追溯索引

- 页面动作：打开“追溯列表”或调用接口查看
- 预期：
  - 新记录已出现
  - 包含 `item_id/job_id/fault_name/solution_name/document_id`
  - `graph_document_link.message` 为 `created` 或 `updated`

示例请求：

```bash
curl "http://localhost:8021/extract/doc-links?limit=50"
```

## 5. 页面验收清单

- [ ] 提交后可见 `job_id`
- [ ] 队列可刷新并显示 `pending` 项
- [ ] 点击通过后状态变为 `approved`
- [ ] 返回中有 `dify_sync.document_id`（已配置 Dify 时）
- [ ] 返回中有 `graph_document_link.ok=true`
- [ ] `doc-links` 列表可查询到该条追溯记录

## 6. 常见问题排查

- `doc-links` 为空：
  - 确认是否真的执行了 `approve`
  - 确认不是只提交了任务但未审核
- `dify_sync.ok=false`：
  - 检查 `.env` 中 `DIFY_DATASET_API_URL / DIFY_DATASET_ID / DIFY_DATASET_API_KEY`
  - 检查 Dify 服务与网络可达性
- `graph_document_link.ok=false`：
  - 检查 `Solution` 是否成功写入
  - 查看 `graph-api` 日志确认图谱写入报错

## 7. 回归建议

每次改动抽取链路后，至少回归以下两条：

- 一条“正常文本”可走完 submit -> approve -> doc-links
- 一条“低质量文本”不会导致前端报错（允许抽取失败但页面可恢复）
