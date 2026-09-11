# WorkBuddy 安装与冒烟

## 前置

- git
- Python 3（看板与 `init.py`）
- 已安装 WorkBuddy

## 安装

```powershell
git clone https://github.com/hdsas2980-cmyk/Task-Harness.git
cd Task-Harness
git checkout workbuddy
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

目标：`%USERPROFILE%\.workbuddy\skills\task-harness\`。

## 冒烟

1. WorkBuddy 技能列表能看到 `task-harness`。
2. 临时目录复制 `references/templates/tasks.json` 与 `init.py`，运行 `python init.py --project .`，应推荐 `t-01`。
3. 不要在本会话里既实现又给自己 `pass`。
