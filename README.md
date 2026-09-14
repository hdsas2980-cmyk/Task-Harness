# Task Harness v3.1 — Codex Native

这是 OpenAI Codex 宿主分支 `codex`。共享核心协议在 `main`；分支选择见 [BRANCHES.md](BRANCHES.md)。

这是 `hdsas2980-cmyk/Task-Harness` 的 Codex 专用适配分支：`codex`。

## 本分支当前约定

**中文来自 `harness.db` payload，不来自看板翻译。** 即使不启动看板，也应能直接从 snapshot 读懂目标、现状及下一步。

- `project`、`description` 与任务 `name`、`desc`、`reason`、`next` 使用中文；证据写中文 `summary`，评审写中文 `reason`，进度正文写中文。
- JSON 键、任务 ID、引用、状态/评审枚举、命令、路径、哈希及原始测试输出保持原文；不新增 `_zh` 字段，不使用 `board.i18n.json`，没有翻译兼容层。
- `bundle` 只接受子任务对象数组，每项必须有 `id`、中文 `desc` 和 `verify`；不再接受 ID 字符串数组。
- 推进状态前必须通过随技能安装的语言校验器。它只检查结构与中文最低条件，不替代内容准确性、实际验证和独立评审。

已有不合格文件应在授权范围内修正原字段后重检；看板不会翻译、迁移或自动改写。完整规则见 [中文原字段契约](references/language-contract.md)。

## 保留的核心能力

- 一轮一任务，依赖门控和优先级调度；
- `.harness/harness.db` 作为唯一真相源；JSON/JSONL/TXT 不再是活路径；
- evidence 表 + 独立 reviews 表的 `pass` 才能判定 `passed`；
- `pending → active → evidence_ready → passed` 状态机及 `blocked/regressed` 回退；
- ponytail/YAGNI 阶梯；
- 追加式进度日志、可回放验证和破坏性命令护栏；
- 主上下文恒定、任务状态外置的长时工程哲学。

## Codex 专用改动

- 调度覆盖系统默认：任务束同会话串行；探索、测试执行/分析、分诊、总结和格式校验等读密集工作优先并行 `spawn_agent`；普通任务只有在 `spawn_agent` 满员后才用 `create_thread`，独立评审是独立上下文例外；`wait_agent` 收取子代理，`wait_threads` 等待/收集已创建会话。细则见 `references/codex-parallel.md`。
- 明确把“当前 Codex 任务”定义为一轮，不依赖 Claude Code 会话语义；
- 优先 PowerShell，Git Bash/Linux/macOS 用 POSIX 工具；可视化看板在独立目录 board/，不随技能安装；
- 评审协议改为独立 Codex 上下文，review 记录增加 `reviewer_context`；
- 删除对 gstack、Claude Skill、CC Switch、MCP 的运行时依赖和兜底暗示；
- 安装脚本只写 `$CODEX_HOME/skills/task-harness`，不创建 Claude/CC Switch 副本；
- 安装前自动把既有 Codex Skill 隔离备份，禁止盲目覆盖；
- 安装 `SKILL.md`、`harness_db.py`、`references/`、`scripts/check_task_harness_language.py` 与 `scripts/convert_harness_json.py`；不安装看板、开发测试或 `commands/`。

## 安装（只写 Codex）

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

Git Bash/Linux/macOS：

```bash
bash scripts/install.sh
```

目标默认是：

```text
%USERPROFILE%\.codex\skills\task-harness
```

也可以用 `CODEX_HOME` 指定 Codex 根目录。脚本会对既有目标做时间戳备份；它不会读取或写入 `.cc-switch`、`.claude`。

## 使用

安装到 `$CODEX_HOME/skills/task-harness` 后，每个 Codex 任务只读写项目 `.harness/harness.db`。旧 JSON 先跑一次转换脚本。不要把工作目录切到 skill。

在项目目录运行已安装的校验器（PowerShell）：

```powershell
$CodexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
python -X utf8 (Join-Path $CodexRoot 'skills/task-harness/scripts/check_task_harness_language.py') .
```

必须存在 `harness.db`；证据和评审可以为空，但不代表已经执行。正常任务交付禁止使用 `--templates`。校验失败先修正 DB，不能先推进状态再补检查。

具体执行规则见 [SKILL.md](SKILL.md)，安装与更新见 [SETUP.md](SETUP.md)，独立评审见 [完成评审](references/review/completion-review.md)。

## 可视化看板（独立目录，不随技能安装）

看板在仓库 `board/`，不是 skill 的一部分。`scripts/install.ps1` 不会安装它。

```powershell
powershell -ExecutionPolicy Bypass -File .\board\start.ps1 -ProjectDir "<项目绝对路径>"
```

浏览器打开 `http://127.0.0.1:<port>/`。页面轮询 `harness.db`，改库会自己刷新。Windows 请走 `board\start.ps1` / `start.bat`（UTF-8），避免控制台乱码。

当前三个标签页为 **任务列表 / 任务轨迹 / 进度日志**：任务按阶段分组，卡片内嵌状态阶段条及证据/评审按钮；轨迹跟随当前行，无任务下拉框；日志支持折叠和原文查看。界面文案固定中文，业务说明直接展示源字段；没有下一步、甘特图或依赖图标签页。状态阶段条不是估算完成百分比。

启动与发布见 [看板说明](board/README.md)，功能与限制见 [看板能力清单](board/CAPABILITIES.md)。

## 更新与验证

`git pull` 只更新仓库，不会覆盖已安装技能。技能重大变更必须卸载重装：重新运行 `scripts/install.ps1` / `scripts/install.sh`（先备份旧目录再写入）。不要手工拷 `SKILL.md`。看板需要从更新后的源码重新启动，或重新构建并使用完整发布包。不要只复制 HTML 或 JavaScript 而保留旧服务端。

在仓库根目录运行（开发测试需安装 pytest，前端逻辑测试需 Node.js；看板运行不需要这些测试依赖）：

```powershell
python -X utf8 -m pytest tests board/tests -q
node --check board/static/app.js
node board/tests/test_ui.cjs
python -X utf8 scripts/check_task_harness_language.py references/templates --templates
python -X utf8 scripts/build_board_release.py
```

发布包输出为 `board/release/TaskBoard-windows.zip`，包含同一份语言校验器及 SHA-256 清单。生成物不随源码提交，也不等于已上传 GitHub Release；从源码运行构建命令生成。

自动化测试、模板检查与打包检查不等于浏览器视觉验收，更不等于真实任务的验证与独立评审通过。
