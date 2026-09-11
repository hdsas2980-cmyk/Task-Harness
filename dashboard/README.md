# 长任务看板（WPF 便携单文件）

只要一个 `TaskHarness.exe`。**不要安装包，不要 Tauri / Electron / WebView2。**

载入任务 = 系统文件夹框，选择项目根或 `.harness`。启动时先探测当前工作目录、exe 目录和上次目录的 `tasks.json`。只读，不写任务真相源。

技能里的 HTTP 看板仍是 `references/templates/` 的 Python SPA，和这个桌面壳分开。

## 依赖边界

| 依赖 | 要不要 |
|------|--------|
| Node / Python / npm / WebView2 / 安装器 | 不要 |
| 本机已装的 .NET 桌面运行时 | 不要。发布的是自包含 win-x64 单文件，运行时打进 exe |

自包含所以体积大约几十 MB，换来的是拷走就能跑。

## 自己编译

```powershell
powershell -ExecutionPolicy Bypass -File .\dashboard\Build.ps1
```

产出：

```text
dashboard\dist\TaskHarness.exe
```

启动：`dashboard\Start.bat`，或直接双击该 exe。

源码/XAML 使用 UTF-8（带 BOM），对齐 JNPF 3.5.X 的 WPF 控制台方案：WPF + .NET 8 + CommunityToolkit.Mvvm。不做托盘，不做 NSIS。
