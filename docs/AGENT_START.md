# 交给 Agent 启动

先让 GitHub CLI 登录你的账号，再把下面对应的一段话交给能运行终端命令的 Agent。登录账号、创建可选 review 的 token、保存 Secret 这几步由你自己完成。

**每天生成提交**

> 请读一下本项目的 AGENTS.md、docs/SETUP.md 和 docs/EMBED.md，帮我创建一个专用私有实例，从今天起生成每日装饰性提交。用当前 GitHub 账号的 noreply 邮箱，先预览，核对仓库后再应用。只操作这个新仓库，别启动额外的 Actions 检查。请通过 GitHub CLI 正常认证，别向我要 token，也别读取或上传现有的 CLI token。如果我选择自动 review，请引导我在 GitHub 自己创建受限 token 并保存为 GREENHOUSE_REVIEW_TOKEN。最后告诉我任务什么时候跑、怎么暂停，以及怎么把温室放到自己的网站上。

**归档几个过去的日期**

> 帮我做一份 2020 年的私有归档，只选 2 月 29 日和 6 月 1 日到 7 日，每天生成两次提交。用 `scripts/archive_year.py` 先预览，核对日期和仓库后再应用。

可以把例子里的年份、日期和提交次数换成你自己的选择。具体用法见[按年份归档](SETUP.md#按年份归档)。

## 每日实例的配置步骤

### 1. 核对模板和目标仓库

从当前克隆的远程仓库确认模板来源。用 `gh api user` 获取已登录账号的公开 login 和 id，只用它们为这个实例生成 noreply 提交身份。

用户可以在 GitHub 模板页面点 **Use this template → Create a new repository**，选择 **Private** 后克隆实例。用户已授权 Agent 建库时，也可以用这条命令。

```sh
gh repo create OWNER/REPOSITORY --private --template SOURCE_OWNER/SOURCE_TEMPLATE --clone
```

把 `SOURCE_OWNER/SOURCE_TEMPLATE` 换成已核对的模板来源，把 `OWNER/REPOSITORY` 换成用户自己的新实例。接下来的配置命令在新实例目录里运行。

### 2. 先看计划，再配置

默认从配置当天开始。下面以 `UTC` 为例，用户也可以选择自己的 IANA 时区。

```sh
python3 scripts/setup.py --repository OWNER/REPOSITORY --timezone UTC
python3 scripts/setup.py --repository OWNER/REPOSITORY --timezone UTC --apply
```

第一条只读核对并打印计划。确认目标后再执行第二条。脚本会保存被 Git 忽略的本地配置、初始化记录，并设置 GitHub Variables 和 Actions 权限。启用开关最后写入。

工作流默认每天 **10:17 UTC** 运行一次。配置时区决定当天记录算在哪一天，运行时刻由工作流的 cron 决定。[配置与运行指南](SETUP.md)

### 3. 需要 review 时，由用户保存 Secret

告诉用户去哪里设置 Secret，并说明所需权限。用户直接在 GitHub 完成以下操作。

- 创建 fine-grained personal access token，只选择这个实例仓库。
- 给 **Pull requests** 读写权限，并保留 GitHub 默认的 **Metadata** 只读权限。
- 将 token 保存为实例仓库的 Actions Secret `GREENHOUSE_REVIEW_TOKEN`，到期后自行更新。

现有 CLI OAuth token 只通过 CLI 使用，不能拿来替代 review 凭据。review 的 token 只留在 GitHub Secret 中，别发给 Agent 或写进文件。配置默认启用可选 review，缺少 Secret 时每日提交照常运行。只想做每日提交时，在预览和应用命令中都加 `--no-review`。

### 4. 交付实例

按 README 在本地检查，再只读核对目标仓库、起始日期、noreply 身份、定时任务和启用开关。核对配置用本地检查即可。把实例入口、运行时间和暂停方法告诉用户。需要立即执行时，用户可以自己在 Actions 运行一次正式任务，也可以等下一次定时运行。贡献是否计入以 GitHub 的显示为准。

只想逛温室或把页面嵌入网站的用户，可以直接从[温室嵌入指南](EMBED.md)开始。
