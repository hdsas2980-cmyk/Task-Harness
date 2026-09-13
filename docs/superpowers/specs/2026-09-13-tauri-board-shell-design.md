> **已废止（2026-09-13）**
>
> 本文档属于 JSON/JSONL 主存储时代，已被 `docs/superpowers/specs/2026-09-13-tauri-board-shell-db-design.md` 取代。
> **不得按本文档实施或把文件契约当作桌面主路径。**

# Task Harness 看板 Tauri 壳设计规格

**日期：** 2026-09-13
**状态：** 待用户确认后进入实施计划
**范围：** 在保留现有 Web 看板的前提下，增加 Windows Tauri 单文件桌面入口

## 1. 目标与非目标

### 目标

1. 保持现有 `board/` Web 看板入口、页面行为、HTTP 启动方式和 ZIP 发布方式可用。
2. 新增一个 Windows Tauri 桌面入口，最终发布物为单个 `TaskBoard.exe`。
3. EXE 不携带 WebView2 Runtime、WebView2 安装器、Python、Node.js 或其他外置运行时。
4. 桌面入口只依赖目标机器已经安装的系统 WebView2。
5. 桌面入口继续提供现有看板能力：任务目录载入、Codex 会话选择、目录选择、两秒轮询、中文契约错误展示、证据/评审/进度只读展示。
6. Web 入口和桌面入口使用同一份前端静态资源及同一套 HTTP API 契约。

### 非目标

- 不把看板改成可写任务状态的桌面管理器。
- 不在 Tauri 壳中增加任务编辑、验证命令执行、证据签署或评审写入功能。
- 不把 Tauri 壳安装到系统，不生成 MSI、NSIS、WiX、MSIX 或其他安装包。
- 不把 WebView2 Runtime 静态打包进 EXE，也不自动下载安装 WebView2。
- 不在本次工作中改造 `scripts/install.ps1`，Tauri 壳不是 Codex skill 的安装内容。
- 不为桌面入口保留 Python sidecar；若仍需 Python，单文件约束即视为未满足。

## 2. 关键约束

### 2.1 WebView2 解释

“不含 WebView2”定义为发行目录和 EXE 内不包含 WebView2 Runtime 或安装器；Tauri Windows 窗口使用系统 WebView2。目标机器缺少或损坏 WebView2 时，EXE 必须显示明确的中文错误并退出或提供诊断信息，不得静默卡死，也不得联网安装。

### 2.2 双入口兼容

现有 Web 看板是独立项目，继续由 `board/start.ps1`、`board/start.bat` 和 `board/start.sh` 启动。新增桌面实现只能共享前端资源、协议测试和必要的契约样例，不得让 Web 启动链依赖 Rust、Tauri CLI 或 WebView2。

### 2.3 只读边界

桌面服务读取项目中的 `tasks.json`、`evidence.jsonl`、`reviews.jsonl`、`progress.txt` 和可选 `board.json`，并检查禁用文件 `board.i18n.json` 是否存在；不得写入这些任务文件、Codex session JSONL、验证命令输出或评审记录。唯一允许的持久化是看板自己的“最近来源目录”设置，位置应使用操作系统应用数据目录，不能写入项目目录或发布目录。

## 3. 建议架构

### 3.1 目录边界

在 `board/tauri/` 建立独立 Tauri 工程：

```text
board/
  static/
    index.html             # Web 与桌面共用
    app.js                 # Web 与桌面共用
  tauri/
    package.json           # 前端开发/构建元数据，不进入最终 EXE
    vite.config.*          # 仅在需要时使用；不得改变静态资源路径
    src-tauri/
      Cargo.toml
      tauri.conf.json
      build.rs
      src/
        main.rs
        http.rs             # 本地 HTTP 服务与路由
        source.rs           # 来源解析、状态文件读取和只读边界
        sessions.rs         # Codex sessions 索引
        contract.rs         # 中文契约校验
        picker.rs           # Windows 原生目录选择
        assets.rs           # 静态资源嵌入
```

文件名可以按 Rust 工程习惯调整，但职责必须保持独立。不得把 Python 文件复制到 Tauri 工程并通过 sidecar 执行。

### 3.2 进程生命周期

1. `main.rs` 启动 Tauri 应用。
2. Rust 在回环地址选择可用端口，优先沿用现有 `8765-8799` 范围；若范围耗尽，返回明确启动错误。
3. Rust HTTP 服务只绑定 `127.0.0.1`，禁止绑定 `0.0.0.0` 或局域网地址。
4. 服务启动后，将本地 URL 注入 Tauri 窗口，窗口加载 `/`。
5. 应用退出时停止 HTTP 服务并释放端口。
6. HTTP 服务线程异常必须通过 Tauri 错误通道或可见错误页反馈，不得让窗口加载一个无响应页面。

### 3.3 静态资源

`board/static/index.html` 和 `board/static/app.js` 必须作为构建输入直接嵌入 EXE。资源服务只允许提供 `/`、`/index.html`、`/task-harness.html` 和 `/app.js`，不允许通过 URL 读取任意本地文件。

桌面页面中的 `fetch` 继续使用相对路径，因此不需要修改 API 地址。若 Tauri 安全策略需要 CSP 调整，只能加入服务自身所需的最小规则，不能打开任意远程脚本或远程页面加载。

## 4. HTTP 协议契约

Rust 服务必须与当前 Python 服务保持以下行为等价：

| 方法与路径 | 行为 | 允许的副作用 |
|---|---|---|
| `GET /api/snapshot` | 返回当前来源、任务文件文本、中文契约结果和最近来源 | 读取项目文件；更新内存快照，不写任务文件 |
| `GET /api/sessions` | 扫描本机 Codex sessions，按 cwd 汇总项目和会话 | 只读 sessions |
| `POST /api/source` | 接收 `path`、`cwd` 或 `source`，解析项目根或 `.harness` 并切换当前来源 | 只写应用数据目录中的最近来源 |
| `POST /api/pick-dir` | 打开一次本机目录选择器并返回选择路径或取消 | 用户主动选择；不修改项目 |
| `GET /tasks.json` 等允许文件 | 返回当前来源下的有限文件 | 只读；禁止路径穿越 |
| 其他写方法 | 返回 `405` 和只读错误 | 不写入任何项目数据 |

允许读取的文件集合固定为：`tasks.json`、`evidence.jsonl`、`reviews.jsonl`、`progress.txt`、`board.json`。缺失文件、UTF-8 读取失败、JSONL 单行错误和目录不可访问都必须保留为结构化契约/读取错误，不得把错误伪装成空任务。

响应保持 UTF-8 JSON，中文不转义。文件响应使用 `Cache-Control: no-store`。路径参数必须经过绝对路径规范化，并要求最终来源是现有目录；文件读取必须限制在解析后的来源目录内。

## 5. 中文契约校验

Rust `contract.rs` 必须实现当前 `scripts/check_task_harness_language.py` 的有效行为子集，并用同一组固定 fixture 与 Python 校验器比对结果。至少覆盖：

- 四份核心文件缺失检测；
- `tasks.json` 对象、任务数组、ID 唯一性、状态枚举、中文说明字段；
- bundle 子任务对象与 `verify`；
- evidence/reviews JSONL 解析、中文摘要/理由和 `_comment` 规则；
- `progress.txt` 中文叙事、代码围栏闭合和机器协议行排除；
- `board.i18n.json` 禁止；
- `_zh` 旁挂字段禁止；
- 递归过深或无效 JSON 的明确错误。

不得把校验规则复制成两份长期漂移的业务规则。推荐把校验 fixture、字段规则说明和错误场景作为跨实现契约；若 Rust 无法完整复刻某一规则，必须在规格变更中明确差异，而不是静默放宽。

## 6. 会话与目录选择

`sessions.rs` 复刻当前会话目录优先级：`CODEX_SESSIONS_DIR`，其次 `CODEX_HOME/sessions`，最后用户目录下 `.codex/sessions`。扫描必须有边界：跳过不可读文件、限制单文件读取大小、避免把 session 正文作为任务证据展示，只提取 cwd、标题、时间和会话 ID 等现有 UI 所需字段。

`picker.rs` 使用 Windows 原生文件夹选择器；同一时间只能有一个选择请求。取消必须返回现有前端可处理的 `{ "cancelled": true }`，不能将取消当成错误或切换来源。非 Windows 构建可暂不提供桌面发行，但 Rust 核心模块应尽量可测试。

## 7. Tauri 配置与发布

### 7.1 配置要求

- Windows 目标为 `x86_64-pc-windows-msvc`，版本号从仓库单一版本来源生成，禁止手工多处漂移。
- `bundle.active` 设为 `false`，或使用等价配置使 `tauri build` 不生成安装器。
- 构建输出只保留经过检查的 `TaskBoard.exe` 和哈希清单；不把 `target/`、调试符号、安装器、资源目录放进发布目录。
- 不配置 WebView2 fixed runtime、offline installer 或 bootstrapper。
- 不使用远程 URL 作为窗口首页。
- 开发依赖可以使用 Node.js/Tauri CLI，但最终 EXE 不得动态查找 Node.js、Python 或项目相对路径。

### 7.2 发布脚本

新增独立脚本，例如 `scripts/build_board_desktop.py`，职责为：

1. 检查当前仓库状态所需的输入文件和工具版本。
2. 将 `board/static/index.html`、`board/static/app.js` 作为 Tauri 构建输入。
3. 调用固定参数的 Tauri release 构建。
4. 将唯一 EXE 复制到仓库内受控的 `board/release-desktop/`。
5. 拒绝发布目录中的未知残留、符号链接和额外运行时文件。
6. 计算 EXE SHA-256、文件大小、PE 架构和版本信息，生成 `manifest.json`。
7. 只在所有检查通过后报告成功；失败时不覆盖旧的已验证 EXE。

现有 `scripts/build_board_release.py` 继续只负责 Web ZIP，不与桌面构建脚本合并。`board/.gitignore` 应忽略 Tauri 的构建缓存和桌面发布目录，但不能忽略源码工程文件。

### 7.3 单文件判定

桌面发行验证必须证明：

- `release-desktop/` 只有 `TaskBoard.exe` 与约定的 `manifest.json`；
- 不存在 `WebView2Loader.dll`、WebView2 Runtime 目录、安装器、Python DLL、Node 文件、`resources` 目录或 sidecar；
- EXE 启动时工作目录改到任意临时目录仍能加载页面；
- EXE 不要求旁边存在 `board/static`、`serve.py`、`sessions.py` 或 `scripts/`；
- 关闭 EXE 后无残留 Python/Node 进程；
- 目标机器已有系统 WebView2 时能显示看板；无 WebView2 时给出可诊断错误。

## 8. 测试与验收

### 8.1 保留 Web 回归

现有 Python、Node 和发布测试必须继续通过：

```powershell
python -X utf8 -m pytest tests board/tests -q
node --check board/static/app.js
node board/tests/test_ui.cjs
python -X utf8 scripts/build_board_release.py
```

### 8.2 Rust 单元与协议测试

新增测试覆盖：

- 来源解析与 `.harness`/项目根互转；
- 路径穿越和非目录输入被拒绝；
- 快照读取、缺失文件、UTF-8 错误和禁用翻译文件；
- 端口选择和仅绑定回环地址；
- 四个 API 路由的状态码、响应字段和只读方法；
- 会话目录优先级、坏文件跳过和 cwd 汇总；
- 目录选择器并发锁和取消返回；
- Python 与 Rust 对固定中文契约 fixture 的错误类别一致。

### 8.3 Windows 发行验收

在干净临时目录中执行：

1. 仅复制 `TaskBoard.exe`，不复制其他文件。
2. 从任意工作目录启动 EXE。
3. 载入一个包含完整四份文件的 harness，确认任务列表、轨迹和进度日志可见。
4. 修改 `tasks.json`，确认两秒轮询后页面更新。
5. 选择无效目录和不合格中文文件，确认错误可见且旧快照不会冒充正常数据。
6. 通过会话选择和目录选择各完成一次载入，确认取消可关闭。
7. 检查任务文件、session JSONL 和目录内容没有被写入。
8. 关闭窗口，确认 HTTP 服务和子进程结束。

视觉验收仍需使用真实 WebView2 窗口，不以 Node 模拟 DOM 作为唯一依据；至少检查窗口首次加载、载入面板、抽屉、中文字体、错误状态和窄窗口布局。

## 9. 错误与回滚

- 系统 WebView2 缺失：展示“需要系统 WebView2”及安装/修复提示链接或诊断信息，但不自动下载、不写系统安装状态。
- 本地 HTTP 服务启动失败：展示端口/权限/绑定错误，进程退出码非零。
- 来源目录无效：沿用前端可读的 400 错误，保持当前来源不被破坏。
- 契约失败：清空旧任务渲染状态并显示源文件位置，保持与 Web 看板一致。
- 桌面构建失败：不删除或覆盖现有 Web ZIP，也不覆盖上一份经过验证的桌面 EXE。
- 桌面入口出现回归时，用户可以继续使用现有 `board/start.ps1` Web 入口；两条发布链互不阻断。

## 10. 完成定义

本设计只有在以下证据齐全后才可把桌面任务标记为 `passed`：

- 现有 Web 测试和发布包回归通过；
- Rust 单元/协议测试通过；
- Windows 单文件 EXE 验收通过；
- 目标机器有系统 WebView2 时真实窗口验收通过；
- 无 WebView2 时显示可诊断错误；
- 发布目录和 EXE 依赖扫描通过；
- 有独立上下文完成只读评审并写入 `reviews.jsonl`；
- 具备可重放的构建、哈希和启动验证证据。
