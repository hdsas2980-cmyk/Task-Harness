# 环境重建提示词（重装系统 / Claude 被重置后使用）

> 用法：把本文件内容整段贴给 Claude Code（cc），或直接说
> “按仓库根目录 SETUP.md 逐步重建 task-harness 环境”。
> cc 应逐步执行下面的阶段，每步核验通过再进入下一步，遇到不确定先停下问我。

## 你要达成的目标

在一台刚重装或被重置的机器上，把 task-harness v3 技能恢复到可用状态，并保证
它与 CC Switch 主库、git 远端三处一致，之后重装可一次性复现。

核心事实（先读懂，别跳过）：

- task-harness v3 的**权威来源是 git 仓库**：`https://github.com/hdsas2980-cmyk/Task-Harness.git`。
- Claude Code 实际读取技能的目录是 `~/.claude/skills/`。
- 本机还装了 **CC Switch**（多供应商切换 + 技能同步管理器，桌面 app）。它的技能主库在
  `~/.cc-switch/skills/`，且设为 `skillStorageLocation=cc_switch` + `skillSyncMethod=auto`，
  是 **auto 同步权威源**——只装到 `~/.claude/skills` 而不同步它，会被 CC Switch 回滚。
  所以两处都要装（`scripts/install.sh` 已自动处理）。
- v3 的核心（SKILL.md + 5 个模板）**完全自包含**，无外部代码依赖；ralph 循环范式与
  ponytail 懒惰阶梯都以文字协议内联在 SKILL.md 里。唯一外部依赖是评审用的 gstack 技能，
  且评审契约那行 `HARNESS_REVIEW:` 也可由任意技能或人工产出，不硬绑 gstack。

## 阶段 1 · 前置检查

依次确认（缺哪个记下来，别擅自安装重型依赖）：

```sh
git --version           # 需要 git
python --version || python3 --version || py --version   # init.sh 需要任一 Python 3
bash --version          # Windows 用 Git Bash
```

网络注意（本机历史经验，不一定复现）：

- 直连 `github.com:443` 可能被重置。若 `git clone/push` 报 `Connection was reset` 或
  `Failed to connect port 443`，先探测本地代理端口再走代理：
  ```sh
  for p in 7897 7890 10809 1080; do (timeout 3 bash -c "echo > /dev/tcp/127.0.0.1/$p" 2>/dev/null && echo "$p 开放"); done
  # 命中后对单条命令临时加：  git -c http.proxy=http://127.0.0.1:<port> -c https.proxy=http://127.0.0.1:<port> <clone/push...>
  ```
- 私有仓库鉴权用 **HTTPS + Windows 凭据管理器**（不是 SSH——本机通常没有 GitHub SSH key）。

## 阶段 2 · 克隆并安装

```sh
git clone https://github.com/hdsas2980-cmyk/Task-Harness.git
cd Task-Harness

# Linux / macOS / Windows-bash
bash scripts/install.sh
# 或 Windows PowerShell
# powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

脚本会：装到 `~/.claude/skills/task-harness/`；若检测到 `~/.cc-switch` 则一并装到主库。
幂等，可重复运行。

## 阶段 3 · 核验安装

```sh
# 两处应存在且一致
diff -rq ~/.claude/skills/task-harness ~/.cc-switch/skills/task-harness && echo "两处一致 OK"
# SKILL.md 应为 v3（约 84 行，首行是 --- frontmatter）
wc -l ~/.claude/skills/task-harness/SKILL.md
head -1 ~/.claude/skills/task-harness/SKILL.md
# 无 v1/v2 残留关键词
grep -rlE "feature_list|validate_harness|passes\": false" ~/.claude/skills/task-harness && echo "!! 有残留" || echo "干净 OK"
```

若只装了 Claude 没装 CC Switch（机器还没装 CC Switch app），先跳过 diff，等装好 CC Switch
后重跑 `bash scripts/install.sh` 补同步。

## 阶段 4 · 评审依赖（gstack，可选但推荐）

task-harness v3 的相 1/相 3 会调 `gstack/plan-eng-review` 与 `gstack/review`。确认它们在：

```sh
for s in review plan-eng-review careful; do
  [ -f ~/.claude/skills/$s/SKILL.md ] && echo "OK $s" || echo "缺 $s"
done
```

若缺失：gstack 技能族由 CC Switch 主库同步（`~/.cc-switch/skills/`），或其 runtime 在
`D:/Code_Runtime/skills-runtime/gstack`。恢复 CC Switch 技能库后即补齐。gstack 缺席时
task-harness 仍可运行，评审改由人工按 `HARNESS_REVIEW: pass|fail | <task-id> | <理由>` 产出。

## 阶段 5 · 冒烟测试（确认全链路 + 上下文恒定）

在临时目录造 3 任务玩具工程，验证依赖门控与退出信号：

```sh
D=$(mktemp -d); cp ~/.claude/skills/task-harness/references/templates/init.sh "$D"/
cat > "$D"/tasks.json <<'JSON'
{"project":"smoke","rev":1,"tasks":[
 {"id":"t-01","priority":1,"desc":"a","depends_on":[],"verify":"echo ok","status":"pending"},
 {"id":"t-02","priority":2,"desc":"b","depends_on":["t-01"],"verify":"echo ok","status":"pending"}]}
JSON
( cd "$D" && bash init.sh )   # 应只提示 t-01（t-02 依赖未满足）
rm -rf "$D"
```

看到 `PROGRESS: 0/2` 且只列出 t-01，即为通过。init.sh 输出恒定紧凑——无论 2 个还是
200 个任务，只打印进度计数 + 一个 eligible 任务，主会话上下文不随任务数增长。

## 阶段 6 · （可选）保持 Claude “纯净”

若希望复现本机的精简配置（不常驻额外上下文）：

- `~/.claude/settings.json` 里 `enabledPlugins."ponytail@ponytail"` 设为 `false`
  （ponytail 插件的 SessionStart/UserPromptSubmit/SubagentStart hook 每次注入约 5.3k
  字符；v3 已把懒惰阶梯内联进 SKILL.md，无需常驻插件）。**改后需重启会话生效。**
- `~/.claude/mcp.json` 保持 `{"mcpServers": {}}`（不挂会往上下文注入 schema 的 MCP）。
- 项目级 `CLAUDE.md` 不写“Skill routing”自动路由段，只留事实性约束。

## 完成标准

- `~/.claude/skills/task-harness` 与 `~/.cc-switch/skills/task-harness` 一致，且为 v3。
- 阶段 5 冒烟测试通过。
- git 远端 = 本地安装源，三处一致，可再次一次性复现。
