# Stack Exchange 问答导入（StackOverflow / ServerFault 等）

本目录用于放置从 [Stack Exchange 数据 dump](https://archive.org/details/stackexchange) 解压得到的 **`Posts.xml`**（内容许可以各站点与 **CC BY-SA** 为准，使用请遵守署名与相同方式共享要求）。

## 推荐数据源

| 站点 | 说明 |
|------|------|
| **serverfault.com** | 与 WisOps 运维场景更贴近，体积相对小于 stackoverflow.com 全站 |
| stackoverflow.com | 全站 `Posts.xml` 极大；首遍需索引全部 Answer，内存与磁盘要求高 |

将解压后的 `Posts.xml` 放在本目录（例如 `data/stackoverflow/Posts.xml`）。仓库 `.gitignore` 会忽略大型 `Posts.xml`，避免误提交。

## 清洗与导入

**仅清洗为 JSONL**（便于检视或再用 `scripts/import_v2.py`）：

```powershell
cd <仓库根>
python scripts/import_stackoverflow.py --posts-xml data/stackoverflow/Posts.xml --out-jsonl data/stackoverflow/curated.jsonl --limit 3000
```

**清洗并写入 graph-api**（需已启动 HugeGraph + graph-api）：

```powershell
python scripts/import_stackoverflow.py --posts-xml data/stackoverflow/Posts.xml --api-url http://localhost:8021 --limit 3000 --delay 0.05
```

**参数说明（常用）**：

- `--limit`：最多导出/导入的「问答对」条数（有采纳答案且通过过滤的问题）。
- `--min-answer-score`：采纳答案最低分数，默认 `1`。
- `--no-tag-filter`：不按运维相关标签过滤（仍要求存在 `AcceptedAnswerId`）。
- `--tags-any`：逗号分隔标签列表，问题标签与其中任一匹配即保留（默认内置一组运维关键词）。
- `--source-tag`：写入图谱的 `data_source`，默认 `stackoverflow`（与 PRD 一致）。
- `--confidence`：默认 `0.6`（公开原始语料）。

**从已有 JSONL 仅调 API**：

```powershell
python scripts/import_stackoverflow.py --from-jsonl data/stackoverflow/curated.jsonl --api-url http://localhost:8021
```

## 本地样例（无需下载全站）

```powershell
python scripts/import_stackoverflow.py --posts-xml data/stackoverflow/sample_posts.xml --dry-run
python scripts/import_stackoverflow.py --posts-xml data/stackoverflow/sample_posts.xml --out-jsonl data/stackoverflow/sample_curated.jsonl
```

## JSONL 字段

每行 JSON 至少包含：`fault_name`（问题标题）、`solution_name`（由回答首句生成）、`solution_description`（清洗后的回答正文）；另含 `question_id`、`answer_id`、`tags` 等元数据。
