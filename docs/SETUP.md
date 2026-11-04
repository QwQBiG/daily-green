# 配置与运行

想让 Daily Green 每天运行，先用公开模板建一个自己的私有实例。下面的步骤需要 Git、Python 3、已登录的 GitHub CLI，以及实例的管理权限。只想给过去几天生成提交，可以直接去[按年份归档](#按年份归档)。想逛温室的话，打开 [`garden/index.html`](../garden/index.html) 即可。

## 1. 创建实例

在模板仓库点击 **Use this template → Create a new repository**，将可见性设为 **Private**，默认分支用 `main`。建好后，克隆自己的实例并进入它的目录。用模板建仓即可避开从 fork 或旧 `.git` 带入个人历史。

也可以让已获授权的 Agent 代为建库。[Agent 启动文档](AGENT_START.md)

## 2. 预览与应用

在 GitHub CLI 登录账号后，把命令中的 `OWNER/REPOSITORY` 换成你的实例仓库。登录凭据由 CLI 管理。`UTC` 可以换成自己的 IANA 时区。

```sh
python3 scripts/setup.py --repository OWNER/REPOSITORY --timezone UTC
python3 scripts/setup.py --repository OWNER/REPOSITORY --timezone UTC --apply
```

先运行第一条，核对仓库和起始日期。它只读检查，不写文件或更改 GitHub 设置。确认后再运行带 `--apply` 的第二条。脚本会检查仓库归属、默认分支和实例配置，用已登录账号的公开 login 和 id 生成 GitHub noreply 提交身份。

配置默认从当天开始。如果希望日常任务从更早的日期开始，在预览和应用命令中加 `--start YYYY-MM-DD`。首次配置时，起始日期最多往回选 366 天。这会补齐装饰性提交，review 只在实际运行当天发生。更早的日期可以单独[按年份归档](#按年份归档)。

配置默认启用可选 review。如果只要每日提交，预览和应用时都加 `--no-review`。以后重跑配置也保留这个参数。

本地配置写在 Git 忽略的 `.greenhouse.local.json`。GitHub 上的 `GREENHOUSE_CONFIG` Variable 保存运行配置，`GREENHOUSE_ENABLED` 控制任务是否启用。运行配置可能含账号、noreply 邮箱和起始日期，留在自己的实例里即可。

## 3. 可选自动一致性 review

机器人通过仓库的 `GITHUB_TOKEN` 创建并合并当天的快照 PR。你的受限 token 只提交一条标明自动生成的 `COMMENTED` review，用于记录一致性检查。它不会代表你批准 PR。

如果想启用这项功能，请在 GitHub 自己创建一个 fine-grained personal access token。

1. 在 **Resource owner** 选实例所属账号。在 **Repository access** 只选这个实例仓库。
2. 在 **Repository permissions** 为 **Pull requests** 选 **Read and write**。**Metadata** 保持默认只读。
3. 选好有效期，生成 token。到实例仓库的 **Settings → Secrets and variables → Actions → New repository secret**，填入名称 `GREENHOUSE_REVIEW_TOKEN`，由你粘贴并保存。
4. 到期后，用新 token 更新同名 Secret。token 只放在 GitHub Secret 中，别发给 Agent、写入源码或 `.env`，也别把现有 CLI 凭据复制进去。

缺少 Secret 时，任务会在发起 review 请求前跳过。应用配置时脚本会打开实例允许 Actions 创建 PR 的开关。如果创建或合并受阻，按组织策略、现有分支保护和仓库权限排查。保留仓库已有的保护规则。

## 4. 日常行为与运行时间

- 每天 **10:17 UTC** 运行一个任务，最长 5 分钟。GitHub 的定时任务可能延迟或漏跑。
- 配置里的时区决定哪天算“今天”。运行时刻由工作流里的 UTC cron 决定，换算成当地时间时可能受夏令时影响。想换运行时间，调整工作流里的那一条 cron。
- 每天按日期生成 2–6 次提交。同一天重跑会跳过已经完成的部分。漏跑后，下次会补齐提交，review 只在实际运行当天执行。
- review 失败时，已推送的提交会保留。运行摘要里的提示会说明原因，凭据内容不会出现在提示里。
- 定时任务负责实际生成提交。项目没有推送检查、PR 检查、夜间巡检或定时测试。想看温室和植物卡，直接打开温室页面即可。

如果想马上执行首日任务，在 **Actions → Daily green → Run workflow** 手动运行一次，也可以等下次定时任务。想在主页显示私有贡献，可在个人主页的 **Contribution settings** 打开 **Private contributions**。提交是否计入、何时出现，取决于 GitHub 的统计。

## 5. 暂停与恢复

在实例的 **Settings → Secrets and variables → Actions → Variables**，把 `GREENHOUSE_ENABLED` 改为 `false`，任务就会跳过。也可以运行这条命令。

```sh
gh variable set GREENHOUSE_ENABLED --repo OWNER/REPOSITORY --body false
```

改回 `true` 后，下次任务会按配置补齐漏掉的提交。过去的日期仍只补提交。想连定时触发记录也一起停掉，可以在 Actions 页面禁用该工作流。原有记录和 Git 历史可以留在仓库里。

## 按年份归档

假设你想给 2020 年的闰日和 6 月第一周做一份归档，每个选中的日期生成两次提交。在模板目录运行第一条，核对日期、提交数和目标仓库后，再执行第二条。脚本会按需创建私有仓库。

```sh
python3 scripts/archive_year.py 2020 --days 02-29 06-01..06-07 --commits-per-day 2
python3 scripts/archive_year.py 2020 --days 02-29 06-01..06-07 --commits-per-day 2 --apply
```

- 可以选 1970 年至当前年。日期按 UTC 计算，选当年时可以选到今天。用 `MM-DD` 选一天，用 `MM-DD..MM-DD` 选一段，两种写法可以混用。重叠的日期只算一次。
- 仓库名默认随年份变化，例如 `daily-green-2020`。想换名字就加 `--name`。以后想给同一个归档补日期或提高某天的提交数，继续用原来的年份和仓库名。
- 用 `--commits-per-day` 给选中的每一天设定提交数，可填任意正整数。省略时按日期生成 2–6 次。脚本只补到目标次数，已经达到目标的日期会跳过。数量越大，本地生成和推送所需的时间越长。

归档在本地生成，随后推送到归档仓库的默认分支，整个过程无需 Actions 或 review。所选日期写入提交，仓库的创建日期由 GitHub 按实际创建时间记录。贡献图的显示以 GitHub 为准。

## 常见情况

| 现象 | 先检查什么 |
| --- | --- |
| 任务被跳过 | 当前分支是否是实例的 `main`，以及 `GREENHOUSE_ENABLED` 是否为 `true` |
| 记录日期和预想不一样 | 查看 `GREENHOUSE_CONFIG` 的时区和起始日期。已有记录后保留原起始日期 |
| review 被跳过 | review 是否启用，Secret 是否存在或过期 |
| PR 无法创建或合并 | Actions 创建 PR 的开关、组织策略、分支保护和仓库权限 |
| 主页暂时没显示 | noreply 身份、默认分支、私有贡献显示开关，以及 GitHub 是否仍在统计 |
| 配置命令中断 | 先修复命令提示的问题，再重新运行配置。由配置脚本打开启用开关 |

项目运行无需付费 AI。Actions 的额度和费用随账号套餐、仓库可见性和实际用量而定。

## 初始化中断后的恢复

如果已生成初始化提交，但推送失败或没收到响应，脚本会停止，`GREENHOUSE_ENABLED` 仍为 `false`。先运行 `git fetch origin main`，再用 `git status` 和 `git log origin/main..HEAD` 检查本地和远端的差别。

如果本地只多出预期的单文件初始化提交，可以正常推送后重跑配置。如果远端已经收到提交，先同步跟踪分支，再重跑配置。请保留已有记录和历史，使用普通推送，避免 force push。确认初始化完成后重跑配置，由脚本打开启用开关。
