# 长任务看板（独立桌面壳）

独立于技能模板的只读看板。**载入任务 = 选择项目任务目录**（`.harness` 或含 `tasks.json` 的项目根）。不写 `tasks.json` / 证据 / 评审。

## 运行

```powershell
cd dashboard
npm install
npm run dev
```

打包：

```powershell
npm run build
```

产物在 `src-tauri/target/release/bundle/`。

## 用法

1. 启动后点 **载入任务**（`L`），选项目根或 `.harness`。
2. 目录里要有 `tasks.json`；可选 `evidence.jsonl`、`reviews.jsonl`、`progress.txt`、`board.json`。
3. **刷新任务**（`R`）重读同一目录。桌面壳会记住上次目录。

浏览器里打开 `ui/index.html` 时，Chrome 也可用目录选择器。技能初始化脚本仍可把同一份 SPA 挂到 `127.0.0.1`，未选目录前会读取当前项目。
