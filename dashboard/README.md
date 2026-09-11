# 长任务看板（便携单文件）

只要一个 `TaskHarness.exe`。**不要安装包。** 载入任务 = 选择项目任务目录。只读。

## 依赖边界（说清楚）

| 依赖 | 要不要 |
|------|--------|
| Node / Python / 安装器 / 网络字体 | 不要。运行时零这些东西 |
| WebView2（Win10/11 的 Edge 组件） | 要。不内嵌，否则体积会到 100MB+ |

Windows 11 自带；Windows 10 装了 Edge 一般也有。没有 WebView2 时窗口起不来，去装 [Evergreen Runtime](https://developer.microsoft.com/microsoft-edge/webview2/) 即可，应用本身仍是单文件。

真正「连 WebView2 都不靠」只能改成原生 GUI（egui 等）重画画板，那是另一条路。

## 自己编译

```powershell
cd dashboard
npm install
npm run build
```

`npm run build` 已关掉 NSIS，只产出：

```text
src-tauri\target\release\TaskHarness.exe
```

把它拷走就能用，旁边不需要 dll、不需要 resources 目录。
