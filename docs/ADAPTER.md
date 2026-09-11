# 新增 ADE 宿主分支

先确认：这个宿主真的需要一条分支，而不是在项目里直接使用 `main` 的模板。只有当宿主有自己的技能目录、命令面、子智能体或安装约定时才开分支。

## 1. 从 `main` 拉分支

```bash
git checkout main
git pull
git checkout -b <host>
```

分支名用宿主常用名的小写短名：`claude`、`codex`、`traework`、`workbuddy`、`dsh`。不要用 `feature/xxx` 当长期发行分支。

## 2. 只改宿主层

保留协议层不动：

- 态机、不变式、`tasks.json` 字段、JSONL 证据/评审、ponytail、护栏
- `HARNESS_STATUS` / `HARNESS_REVIEW` 契约行
- `references/review/` 的判定铁律

可以改：

- `SKILL.md` 的 frontmatter 与「如何在本宿主打开一轮 / 打开独立评审」
- `scripts/install.ps1`、`scripts/install.sh`（只写本宿主目录，先备份再覆盖）
- 斜杠命令、子智能体、宿主规则文件
- 初始化默认入口（紧凑状态或看板）

## 3. 安装脚本硬规则

- 默认只安装到一个宿主根目录。
- 禁止顺手写入其他 ADE（例如 TRAE 安装器不要默认写 `~/.claude`）。
- 覆盖前做时间戳备份。
- 安装 `SKILL.md` + `references/`；`commands/` 与 `agents/` 仅当宿主确实读取这些目录。
- 在 README 写明绝对路径或可覆盖的环境变量（如 `CODEX_HOME`、`DSH_HOME`）。

## 4. README 最低内容

1. 一句说明：这是 Task Harness 的 `<host>` 适配，核心协议在 `main`。
2. 安装命令与目标路径。
3. 本宿主的一轮边界（什么叫一次会话/任务）。
4. 独立评审怎么开（新会话、子智能体、命令）。
5. 指向 `BRANCHES.md` 与 `SKILL.md`。

## 5. 验收

- 在干净目录安装，确认只出现本宿主路径。
- 用模板 `tasks.json` 跑初始化，输出 `PROGRESS` 与下一个 eligible 任务。
- 伪造一条 `evidence_ready`，在独立上下文走完 `HARNESS_REVIEW` 契约。
- 确认本分支没有把其他宿主的命令文件装进去。

## 6. 回写 `main`

新分支稳定后，只把**协议层**的修复 cherry-pick 回 `main`（评审铁律、模板字段、看板缺陷）。宿主路径、frontmatter、安装脚本留在宿主分支。
