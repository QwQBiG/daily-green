# 交给 Agent 启动

把下面的提示词复制给能运行终端命令、已获准使用 GitHub CLI 的 Agent。账号认证、fine-grained token 创建与 Secret 保存仍由本人完成。

> 阅读本项目的 AGENTS.md、docs/SETUP.md 和 docs/EMBED.md。为我创建一个专用私有实例，从今天开始运行每日装饰性提交，并准备可选的自动一致性 review。使用已认证账号的 GitHub noreply 邮箱，先 dry-run 再应用配置。只操作这个新实例，不改其他项目；不读取或上传现有 CLI token，不向我要 token。需要 review 凭据时，引导我自行在 GitHub 创建并保存为 GREENHOUSE_REVIEW_TOKEN。不要启动额外的 Actions 检查。最后告诉我正常运行时间、如何暂停，以及怎样把温室放进自己的网站。

## Agent 执行路线

### 1. 确认来源和目标

查看当前克隆的远程仓库，识别模板来源；不要把某位维护者的账号写死在命令或代码里。通过 `gh api user` 获取已登录用户的公开 login 和 id，仅用来生成该实例的 noreply 身份。

用户可以先在 GitHub 点击 **Use this template → Create a new repository**，选择 **Private**，然后克隆自己的实例。也可以在用户已授权创建实例时使用：

```sh
gh repo create OWNER/REPOSITORY --private --template SOURCE_OWNER/SOURCE_TEMPLATE --clone
```

这里的 `SOURCE_OWNER/SOURCE_TEMPLATE` 应来自当前模板的实际来源，`OWNER/REPOSITORY` 是用户自己的新实例。不要原样执行占位符，也不要在公开模板本身运行应用配置。

### 2. 先看计划，再配置

进入实例目录，默认从配置当天开始：

```sh
python3 scripts/setup.py --repository OWNER/REPOSITORY --timezone UTC
python3 scripts/setup.py --repository OWNER/REPOSITORY --timezone UTC --apply
```

第一条只读核对并显示计划。第二条才写入忽略的本地配置、初始化实例记录、设置 GitHub Variables 和所需 Actions 设置；启用开关最后写入。用户可以选择自己的 IANA 时区，`UTC` 是通用示例。

默认工作流每天 **10:17 UTC** 运行一次。时区用于判断记录属于哪一天，不会自动把 cron 改成该时区的 10:17。具体配置与暂停方式见 [SETUP.md](SETUP.md)。

### 3. 可选 review：请用户自己保存 Secret

为用户打开实例的 GitHub Secret 设置位置并说明权限即可；不要接触 token 的实际内容。

- fine-grained personal access token 只选择这个实例仓库。
- 权限仅需 **Pull requests: Read and write**，以及 GitHub 默认的 **Metadata: Read-only**。
- 用户自行将 token 保存为实例仓库 Actions Secret：`GREENHOUSE_REVIEW_TOKEN`。
- 不使用已有 CLI OAuth token 代替，不给 token 额外仓库权限，不把 token 提交到文件里。

配置工具默认启用可选 review；没有 Secret 时，运行会直接跳过 review，每日提交仍可独立使用。完全不需要 review 时，在配置命令后追加 `--no-review`。已有的本人受限 token 到期后，需要本人更新 Secret。

### 4. 收尾

本地运行 README 中的检查，读取实例配置确认目标仓库、日期、noreply 身份、单一定时任务与启用开关。不自动触发工作流验证，也不声称已产生个人贡献。明确告诉用户可手动在 Actions 运行一次实际任务，或等待下次正常定时运行。

温室不需要上述自动化。用户只想玩温室或嵌入网站时，直接按 [EMBED.md](EMBED.md) 操作即可。
