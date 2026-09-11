# DSH 安装与冒烟

## 前置

- git
- Python 3
- 已安装 DeepSeek Harness（配置根默认 `~/.dsh`）

## 安装

```powershell
git clone https://github.com/hdsas2980-cmyk/Task-Harness.git
cd Task-Harness
git checkout dsh
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

目标：`%USERPROFILE%\.dsh\skills\task-harness\`。

## 冒烟

1. 新开 DSH 会话，技能目录里能加载 `task-harness`（name 为 kebab-case）。
2. 复制模板 `tasks.json` 后运行 `python init.py --project .`，应推荐 `t-01`。
3. 独立评审走新会话或只读 subagent；没有独立上下文就标 `blocked`。
