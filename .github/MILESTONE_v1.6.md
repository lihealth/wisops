# GitHub 里程碑 v1.6 — 创建说明

本仓库未配置可自动调 API 的凭证，请任选下面一种方式创建里程碑。

## 方式 A：网页创建（推荐）

1. 打开：<https://github.com/lihealth/wisops/milestones/new>
2. **Title** 填写：`v1.6`
3. **Description** 将下面「里程碑正文」整段复制粘贴
4. （可选）设置 Due date
5. 点击 **Create milestone**

## 方式 B：Personal Access Token + PowerShell

在 [GitHub → Settings → Developer settings → Fine-grained or classic PAT](https://github.com/settings/tokens) 创建 token，勾选对 `lihealth/wisops` 的 **Issues: Read and write**（里程碑归属 Issues API）。

```powershell
cd C:\Users\lijian22\wisops   # 或你的仓库根目录
$env:GITHUB_TOKEN = "ghp_你的令牌"   # 勿提交、勿外传

$desc = Get-Content -Raw ".\.github\MILESTONE_v1.6-body.txt" -Encoding UTF8
$body = @{ title = "v1.6"; description = $desc; state = "open" } | ConvertTo-Json
Invoke-RestMethod `
  -Uri "https://api.github.com/repos/lihealth/wisops/milestones" `
  -Method Post `
  -Headers @{
    Authorization = "Bearer $env:GITHUB_TOKEN"
    Accept        = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
  } `
  -Body $body `
  -ContentType "application/json; charset=utf-8"
```

成功后可在 <https://github.com/lihealth/wisops/milestones> 查看。

---

## 里程碑正文（复制到 Description）

见同目录文件 `MILESTONE_v1.6-body.txt`（纯文本，避免 md 嵌套混乱）。

关联 Git 标签：`v1.6.0`  
详细变更：`CHANGELOG.md` → `[v1.6.0]`
