# 配置与运行

建议把公开模板当作源码，在自己的专用私有实例里运行自动化。需要 Git、Python 3、GitHub CLI，以及对该实例的管理权限；浏览器打开温室不需要这些工具。

## 1. 创建实例

在模板仓库选择 **Use this template → Create a new repository**，将可见性设为 **Private**，默认分支使用 `main`。克隆实例并进入目录。不要用 fork 或复制旧 `.git` 的方式迁入个人历史。

也可由已授权的 Agent 使用 GitHub CLI 创建实例，见 [Agent 启动文档](AGENT_START.md)。

## 2. 预览与应用

确认 `gh` 已按正常流程登录，不读取或输出 CLI token。替换以下命令中的目标仓库和时区：

```sh
python3 scripts/setup.py --repository OWNER/REPOSITORY --timezone UTC
python3 scripts/setup.py --repository OWNER/REPOSITORY --timezone UTC --apply
```

不带 `--apply` 时只显示计划，不修改文件或 GitHub。应用时会核对仓库归属、专用实例、默认分支和配置；从已登录账号的公开 login/id 生成 noreply 身份，避免误用设备邮箱。

本地配置 `.greenhouse.local.json` 被 Git 忽略。GitHub Variable `GREENHOUSE_CONFIG` 保存实例运行设置，`GREENHOUSE_ENABLED` 是启用开关。配置不是 token，但可能含使用者自己选择的账号、noreply 邮箱和日期，不应反向复制到公开模板。

默认从当天开始。若本人明确希望补齐较早日期，可追加 `--start YYYY-MM-DD`；首次配置时，起点不得早于今天 366 天。这会生成装饰性历史提交，不代表过去真实工作，也不会补写过去的 review。不要把自己实例的起始日期写进公共示例。

配置工具默认启用可选 review。只想运行每日提交时，在 dry-run 和应用命令中都追加 `--no-review`；以后重跑配置时也应保留该选项，避免重新启用 review。

## 3. 可选自动一致性 review

review 流程使用两个身份：仓库 `GITHUB_TOKEN` 代表 bot 创建并合并当天快照 PR；本人受限 token 只提交明确标注自动化的 `COMMENTED` review。它不是批准，也不是人工审核。

本人在 GitHub 创建 fine-grained personal access token：

1. Resource owner 选择实例所属账号，Repository access 只选择实例仓库。
2. Repository permissions 选择 **Pull requests: Read and write**；Metadata 保持默认只读。
3. 设置自己接受的有效期，生成后直接进入实例仓库 **Settings → Secrets and variables → Actions → New repository secret**。
4. 名称填写 `GREENHOUSE_REVIEW_TOKEN`，由本人粘贴并保存 token。

不要把 token 发给 Agent、写入源码或 `.env`，也不要上传当前 CLI 的宽权限凭据。到期时由本人更新同名 Secret。未配置 Secret 时 review 会在网络操作前跳过。

实例需允许 Actions 创建 PR；应用配置会设置相关开关。组织策略、分支保护和仓库权限仍可能阻止自动创建或合并，不应通过取消既有保护来强行运行。

## 4. 日常行为与运行时间

- 每天 **10:17 UTC** 只有一个实际任务，最长 5 分钟；GitHub 定时触发可能延迟或漏跑。
- 配置的时区决定“今天”的边界。cron 固定按 UTC，夏令时也可能改变对应的本地时间；需要其他时刻时，自行调整工作流中的单条 cron。
- 每天按日期生成 2–6 次提交；同日重复运行跳过已完成部分。漏跑后，下次任务补齐提交，但 review 仅发生在实际运行当天。
- 提交成功后，可选 review 失败不会抹去已推送的提交；具体原因以运行摘要中的脱敏 warning 为准。
- 没有 `push`/PR 检查、额外夜间检查或定时测试。不要为了查看植物卡单独启动 Actions。

需要首日结果时，可以自己在 **Actions → Daily green → Run workflow** 运行一次实际任务；否则等待正常计划。不要把一次未触发的配置核对描述成“贡献已计入”。

如果需要在个人主页显示私有贡献，可自行在 GitHub 个人主页的 Contribution settings 打开 **Private contributions**。贡献是否计入及显示时间由 GitHub 决定。

## 5. 暂停与恢复

在实例 **Settings → Secrets and variables → Actions → Variables**，将 `GREENHOUSE_ENABLED` 设为 `false` 即可暂停 job。也可使用：

```sh
gh variable set GREENHOUSE_ENABLED --repo OWNER/REPOSITORY --body false
```

设置为 `true` 恢复；恢复后的实际任务会按配置补齐提交，不会补写历史 review。若要连定时触发记录也停止，可在 Actions 页面禁用该工作流。不要删除个人记录或重写历史来达到暂停目的。

## 常见情况

| 现象 | 先检查什么 |
| --- | --- |
| job 被跳过 | 是否在实例的 `main`，以及 `GREENHOUSE_ENABLED` 是否为 `true` |
| 记录日期不合预期 | `GREENHOUSE_CONFIG` 中的时区与起始日期；不要在已有记录后随意改起始日期 |
| review 跳过 | review 是否启用、Secret 是否存在及是否过期 |
| PR 无法创建或合并 | Actions 创建 PR 开关、组织策略、分支保护和实例权限 |
| 主页暂时没显示 | noreply 身份、默认分支、私有贡献显示设置和 GitHub 统计延迟 |
| 配置命令中断 | 修复提示的问题后重跑配置；不要手动开启开关掩盖未完成配置 |

本项目不调用付费 AI。Actions 额度和计费取决于用户自己的账号、实例可见性及实际使用；不要假定所有情况下永远免费。

## 初始化中断后的恢复

如果初始化提交已经创建，但 push 失败或响应丢失，配置工具会保守停止，调度开关仍为 `false`。让 Agent 先 `git fetch origin main`，检查 `git status` 与 `git log origin/main..HEAD`。只有确认本地超前的提交是预期的单文件初始化记录时，才普通 push 后重跑 setup；如果远端已经收到提交，正常同步跟踪分支后再运行即可。不要 force push、删除个人记录，或直接开启调度掩盖错误。
