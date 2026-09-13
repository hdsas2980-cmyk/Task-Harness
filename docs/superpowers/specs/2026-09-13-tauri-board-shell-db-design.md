# Task Harness 看板 Tauri 壳设计规格（数据库优先）

**日期：** 2026-09-13
**状态：** 待用户确认后进入实施计划；确认前不得开始 `board/tauri/` 编码
**范围：** 在保留现有 Web 看板的前提下，增加 Windows Tauri 单文件桌面入口
**存储前提：** Task Harness 已从 JSON/JSONL 文件主存储切换为 SQLite；本文件是桌面壳的现行规格

## 0. 废止声明

本规格**取代**以下 JSON 时代文档，不得再按它们实施：

- `docs/superpowers/specs/2026-09-13-tauri-board-shell-design.md`
- `docs/superpowers/plans/2026-09-13-tauri-board-shell.md`

旧文档把 `tasks.json` / `evidence.jsonl` / `reviews.jsonl` / `progress.txt` 当作桌面主路径，并要求 Rust 复刻文件契约。该前提已经失效。

现行权威存储是仓库根目录 `harness_db.py` 的 schema v1 与 `read_snapshot()`。`board/serve.py` 当前工作区里的 SQLite 适配层**不是**契约：它把 `tasks` 收成 id 字典、从任务行找 `project`、查询不存在的 `board` 表，并且在数据库模式下跳过中文契约。桌面实现必须跟随 `harness_db.py`，不得复制该适配层。

本轮只定设计。用户确认本规格后，再另写实施计划 `docs/superpowers/plans/2026-09-13-tauri-board-shell-db.md`。在此之前不得创建 Tauri 工程、不得安装运行时、不得改动未提交的看板/数据库工作区文件。

写本规格时 `harness_db.py` / `docs/HARNESS-DB.md` 可能仍未提交。实施前必须再读工作区现行文件；若 schema 或 `read_snapshot()` 形状变化，先改本规格，不得按过期形状写代码。

## 1. 目标与非目标

### 目标

1. 保持现有 `board/` Web 看板入口、`board/start.ps1` 启动链、Python HTTP 服务和 ZIP 发布方式可用。
2. 新增 Windows Tauri 桌面入口，最终发布物为单个 `TaskBoard.exe`，无安装包。
3. EXE 不携带 WebView2 Runtime、WebView2 安装器/bootstrapper、Python、Node.js 或其他 sidecar。
4. 桌面窗口只使用目标机器已经安装的**系统 WebView2**。
5. 桌面主路径读取 `.harness/harness.db`（SQLite，只读）；无数据库文件时才允许与 Web 相同的 JSON/JSONL/TXT 回退。
6. Web 与桌面共用 `board/static/index.html`、`board/static/app.js`，并共用同一套 HTTP API 外壳和**同一份结构化 snapshot 形状**。
7. 继续提供现有看板能力：来源载入、Codex 会话选择、目录选择、两秒轮询、中文契约错误、证据/评审/进度只读展示。

### 非目标

- 不把看板改成可写任务管理器。
- 不在 EXE 内执行 `import_legacy()`，不创建、迁移、修复或写入 `harness.db`。
- 不把 JSON 文件重新拼成桌面主协议，不伪造 `tasks.json` 给前端。
- 不生成 MSI、NSIS、WiX、MSIX 或其他安装包。
- 不打包、不下载、不修复 WebView2。
- 不改造 `scripts/install.ps1`；Tauri 壳不是 skill 安装内容。
- 不把 Python/Node 作为桌面运行时。
- 不把当前工作区里未提交的看板/UI/数据库改动回退或混入本设计的实现提交。

## 2. 关键约束

### 2.1 WebView2 解释

“不含 WebView2”只表示**发行物不携带 Runtime/安装器**。窗口仍依赖系统 WebView2。

缺少或损坏时必须立即显示中文诊断并退出或停在诊断页，禁止静默白屏，禁止联网安装。提示可包含官方 Evergreen Runtime 说明链接，但程序不得自行下载。

### 2.2 双入口兼容

Web 看板继续由 `board/start.ps1`、`board/start.bat`、`board/start.sh` 启动。桌面不得让 Web 启动链依赖 Rust、Tauri CLI 或 WebView2。

共享范围仅限：

- `board/static/index.html`
- `board/static/app.js`
- HTTP 路径与 snapshot/contract JSON 形状
- 只读来源解析规则
- 中文契约语义

允许为了收敛 snapshot 形状，对共用前端做**有界适配**。该适配必须同时服务 Web 与桌面，不得做第二套页面。

### 2.3 只读边界

桌面进程对项目目录的唯一合法动作是读取。禁止：

- `INSERT` / `UPDATE` / `DELETE` / `CREATE` / `DROP` / `VACUUM` / `import_legacy`
- 创建 `.harness` 或 `harness.db`
- 改写 `tasks.json`、`evidence.jsonl`、`reviews.jsonl`、`progress.txt`、`board.json`、Codex session JSONL
- 把最近来源写进项目目录或发布目录

唯一允许的持久化是操作系统应用数据目录中的“最近来源”文件。Windows 路径固定为：

`%APPDATA%\\TaskHarness\\TaskBoard\\last-source.txt`

使用临时文件再替换；失败时忽略，不影响只读展示。环境变量 `TASK_HARNESS_LAST_SOURCE` 若存在，只作为该文件路径覆盖，不作为可写项目路径。

### 2.4 SQLite 打开方式

- 用 URI `file:<abs>?mode=ro` 打开已存在的 `harness.db`。
- **禁止** `immutable=1`，以免 WAL 下看不到刚提交的数据。
- **禁止**默认读写连接：普通 `sqlite3.connect(path)` / `Connection::open(path)` 会在缺失时创建空文件。
- 文件不存在就走 JSON 回退或空来源，绝不建库。
- SQLite 引擎通过 `rusqlite` 的 `bundled` 特性编进 EXE；目标机器不需要 `sqlite3.dll` / `sqlite3.exe`。这不是 sidecar，也不是 WebView2。
- 不设置、不改变项目库的 `journal_mode`。`harness_db.py` 当前写库使用 `DELETE` + `synchronous=NORMAL` + `foreign_keys=ON`；桌面只读连接可设置 `foreign_keys=ON`，但不得 `PRAGMA journal_mode=...`。

## 3. 权威数据模型

### 3.1 来源文件

| 角色 | 路径 | 说明 |
|---|---|---|
| Schema 与 snapshot 权威 | `harness_db.py` | `SCHEMA_VERSION = 1`，`read_snapshot()` |
| 模块说明 | `docs/HARNESS-DB.md` | 与实现一致的阅读说明 |
| 回归 | `tests/test_harness_db.py` | 幂等导入、未知字段、重开 |
| 语言规则来源 | `scripts/check_task_harness_language.py` | JSON 时代按文件；数据库模式改为校验 payload 字段 |
| 非权威 | `board/serve.py::_snapshot_from_db` | 工作区草稿，形状错误 |
| 非权威 | `board/sessions.py::_db_task_meta` | 误读 `tasks.project` 列 |
| 已废止 | 旧 Tauri JSON 规格与计划 | 不得执行 |

### 3.2 Schema v1

表：

- `meta(key TEXT PRIMARY KEY, value_json TEXT NOT NULL)`
- `tasks(id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)`
- `evidence(id TEXT PRIMARY KEY, task_id TEXT, payload_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)`
- `reviews(id TEXT PRIMARY KEY, task_id TEXT, evidence_id TEXT, payload_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)`
- `progress(id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL, content_hash TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)`

索引：`idx_evidence_task_id`、`idx_reviews_task_id`、`idx_reviews_evidence_id`。

没有 `board` 表，没有 `tasks.project` 列。`tasks.json` 顶层除 `tasks` 外的键（含 `project`、`description`、`rev` 及未知键）进入 `meta`。每条任务/证据/评审的原始对象进入 `payload_json`；未知字段必须保留。

默认路径：`<project>/.harness/harness.db`。

### 3.3 规范 snapshot

Rust 与 Python 对数据库来源必须产出与 `HarnessDB.read_snapshot()` 相同的语义：

```text
{
  schema_version: 1,
  storage: { type: "sqlite", path: "<绝对路径>" },
  meta: { schema_version: 1, project?: 中文名, description?: ..., rev?: ..., <其它顶层键> },
  tasks: [ { ...payload字段, id, payload } ],
  evidence: [ { ...payload字段, id, payload } ],
  reviews: [ { ...payload字段, id, payload } ],
  progress: string,          // 按 progress.id 升序，用 "\n\n" 连接
  counts: { tasks, evidence, reviews }
}
```

Unpack 规则：

1. `json.loads(payload_json)` 得到对象。
2. 展开到结果对象。
3. 若无 `id` 则补行内 `id`。
4. 始终带 `payload` 原对象。
5. 顺序为各表 `rowid` / `progress.id` 升序。

禁止：

- 把 `tasks` 收成 `{id: row}` 字典作为规范形状。
- 从任务行猜 `project`。
- 查询 `board` 表。
- 把 `progress` 用单换行拼接（必须与 `harness_db.py` 的 `\n\n` 一致）。
- 为了迁就错误测试去接受 `tasks.project` 列那种临时 schema。

### 3.4 轮询修订

前端两秒轮询需要稳定、便宜的变化标记。数据库模式在 snapshot 上**额外**计算只读字段 `revision`（不入库）：

```text
revision: {
  schema_version,
  task_count,
  evidence_count,
  review_count,
  progress_count,
  progress_digest,     // progress 字符串的 SHA-256 hex
  latest_created_at    // tasks/evidence/reviews/progress 的 max(created_at)，无则为 ""
}
```

不得发明 `updated_at` 列。JSON 回退仍可用文件文本拼接作为 stamp。

### 3.5 JSON 回退

仅当解析后的来源目录**没有** `harness.db` 文件时，才读取：

- 必需语义：`tasks.json`
- 可选：`evidence.jsonl`、`reviews.jsonl`、`progress.txt`、`board.json`
- 检测禁用：`board.i18n.json` 若存在则记入契约错误

JSON 回退必须**先规范化**成与 3.3 相同的 snapshot：

- `storage.type = "files"`
- `meta` 来自 `tasks.json` 顶层非 `tasks` 键
- `tasks/evidence/reviews` 为数组
- `board` 仅在文件回退且存在 `board.json` 时出现

若 `harness.db` 存在但无法只读打开或 schema 不是 v1：

- **失败闭合**，报告中文错误。
- **不得**静默改读旁边可能过期的 JSON。
- 不得删除或改写该数据库。

桌面不得把 JSON 导入成 SQLite。Web 看板的 `import_legacy` 仍是独立的 Python 迁移工具，不属于 EXE。

## 4. 建议架构

### 4.1 目录边界

在 `board/tauri/` 建立独立 Tauri v2 工程：

```text
board/
  static/
    index.html
    app.js
  tauri/
    package.json
    src-tauri/
      Cargo.toml
      tauri.conf.json
      build.rs
      src/
        main.rs
        http.rs
        assets.rs
        source.rs
        db.rs
        files.rs
        contract.rs
        sessions.rs
        picker.rs
        last_source.rs
```

职责：

| 模块 | 职责 |
|---|---|
| `main.rs` | 启动 Tauri、拉起回环 HTTP、注入窗口 URL、退出时停服务 |
| `http.rs` | 只绑定 `127.0.0.1`，路由静态资源与四个 API |
| `assets.rs` | `include_bytes!` 嵌入 `board/static` |
| `source.rs` | 来源解析、DB/文件分流、只读边界 |
| `db.rs` | rusqlite `mode=ro` 读取 schema v1 并 unpack |
| `files.rs` | JSON 回退读取，不写、不导入 |
| `contract.rs` | 对结构化 snapshot 做中文契约，不伪造文件 |
| `sessions.rs` | Codex sessions 只读索引；`has_harness` 优先 `harness.db` |
| `picker.rs` | Windows 原生目录选择，单飞锁 |
| `last_source.rs` | 仅写应用数据目录 |

不得把 Python 文件拷进 Tauri 工程当 sidecar。

### 4.2 进程生命周期

1. 启动 Tauri。
2. 在 `127.0.0.1:8765-8799` 选空闲端口；耗尽则给出中文错误，并以非零退出码退出。
3. 禁止绑定 `0.0.0.0` 或局域网地址。
4. 窗口加载 `http://127.0.0.1:<port>/`，不使用远程 URL 作首页。
5. 退出时停止 HTTP 并释放端口。
6. HTTP 线程异常必须变成可见错误，不得留无响应窗口。

前端继续用相对路径 `/api/...`，因此桌面保持 loopback HTTP，不改成 `tauri://` 作为主协议。

### 4.3 静态资源

编译期嵌入 `board/static/index.html` 与 `board/static/app.js`。只允许提供 `/`、`/index.html`、`/task-harness.html`、`/app.js`。禁止把任意本地路径映射成 URL。

CSP 只加本服务所需最小规则，不得放行任意远程脚本。

`build.rs` 在缺失静态文件或发现禁用翻译钩子（`board.i18n.json`、`parseI18n`、`_zh` 作为看板翻译机制）时失败。

### 4.4 来源解析

输入可以是项目根或 `.harness`。规范化为绝对路径后：

1. 若是文件，改用父目录。
2. 若目录名是 `.harness`，即来源。
3. 否则按以下优先级选择：
   1. `<root>/.harness/harness.db`
   2. `<root>/.harness/tasks.json`
   3. `<root>/harness.db`
   4. `<root>/tasks.json`
   5. 默认仍指向 `<root>/.harness`，即使该目录尚不存在

解析结果即使不存在也不得创建。路径必须拒绝穿越到解析来源之外。非目录输入返回 400。

`POST /api/source` 接受 `path` / `cwd` / `source`，成功后只更新内存当前来源和应用数据目录中的最近来源。

## 5. HTTP 协议

Rust 服务保持现有四个 API，但 snapshot 语义改为数据库优先。

| 方法与路径 | 行为 | 允许的副作用 |
|---|---|---|
| `GET /api/snapshot` | 返回当前来源、规范 snapshot、契约、最近来源；数据库模式 `files` 为空对象 | 只读；更新内存快照 |
| `GET /api/sessions` | 扫描本机 Codex sessions，按 cwd 汇总 | 只读 sessions |
| `POST /api/source` | 解析并切换来源 | 只写应用数据目录最近来源 |
| `POST /api/pick-dir` | 原生目录选择，返回路径或取消 | 不修改项目 |
| 其它写方法 | `405` + 只读错误 | 无 |

JSON 响应 UTF-8、中文不转义、`Cache-Control: no-store`。

`GET /api/snapshot` 外壳：

```text
{
  source: string | null,
  files: { [filename]: text },   // 仅 JSON 回退填充；数据库模式为 {}
  snapshot: CanonicalSnapshot,   // 含 revision；空来源可为规范化空对象
  contract: { errors: string[], counts: { tasks, evidence, reviews } } | null,
  last_source: string | null
}
```

物理文件 GET（`/tasks.json` 等）仅当该文件真实存在于来源目录时返回。数据库模式不合成这些文件；不存在则 404。允许的文件名仍只是 `tasks.json`、`evidence.jsonl`、`reviews.jsonl`、`progress.txt`、`board.json`。

取消目录选择必须返回 `{ "cancelled": true }`，不得当成错误或切换来源。选择器忙返回 409 `已有目录对话框打开`。

## 6. 中文契约

数据库模式**禁止**为了复用 Python 校验器而重建假 `tasks.json`。Rust 必须对规范 snapshot 做与 `scripts/check_task_harness_language.py` 等价的字段检查：

- `meta.project`、`meta.description`：非空中文说明
- 每个 task payload：唯一 `id`、状态枚举、`name`/`desc`/`reason`/`next` 中文；bundle 子任务与 `verify`
- evidence payload：`summary` 中文；跳过仅含 `_comment` 的对象
- review payload：`reason` 中文
- `progress` 字符串：中文叙事、围栏闭合、排除机器协议行
- payload 树禁止 `_zh` 旁挂字段
- 来源目录存在 `board.i18n.json`：禁止翻译文件
- JSON 回退时若有 `board.json`，继续检查 `where/what/why/see/problem/name/desc/description`
- 过深嵌套给出明确错误，而不是崩溃

错误条目尽量保持现有中文类别，便于对照 fixture。位置前缀在数据库模式可用 `meta.project`、`tasks[i]`、`evidence[i]`，不必假装行号来自 JSONL；JSON 回退仍保留物理行号。

数据库存在且可读时，**不得**因为 `files` 为空就跳过契约。当前 Python 适配层的这个行为视为缺陷，桌面不得复制。

契约只检查结构与中文最低条件，不判定任务 `passed`。

## 7. 会话探测

`sessions.rs` 复刻目录优先级：`CODEX_SESSIONS_DIR`，其次 `CODEX_HOME/sessions`，最后 `%USERPROFILE%\\.codex\\sessions`。

扫描边界与现网一致：首行最多 `256 * 1024` 字节，尾部最多 `64 * 1024`，跳过 `__backups__` / `__backup_*`，坏文件跳过，不展示 session 正文。

`probe_harness` 必须：

1. 先 `resolve_source`。
2. 若存在 `harness.db`：`has_harness=true`，`tasks_file` 为该数据库路径；`task_count = COUNT(*) FROM tasks`；`project_name` 来自 `meta.key='project'` 的 `value_json`（JSON 解码后的字符串），**不是** `tasks.project` 列。
3. 否则若存在 `tasks.json`：沿用文件元数据。
4. 空库仍算有 harness，任务数为 0。

## 8. 共用前端适配

`board/static/app.js` 必须能消费 3.3 的数组 snapshot：

- `model.tasks.tasks = snapshot.tasks`（数组）
- `model.tasks.project = snapshot.meta.project`
- `model.tasks.rev = snapshot.meta.rev`
- evidence / reviews / progress 直接使用 snapshot
- `board` 仅在 snapshot 提供时使用；schema v1 无 board 表，数据库模式默认为空
- 轮询 stamp 使用 `snapshot.revision`，不再依赖不存在的 `updated_at`

过渡期可以容忍错误的 id 字典形状，以免未收敛的 Web 草稿立刻崩溃，但**规范路径是数组 + meta**。桌面实现不得为了“少改前端”去输出错误形状。

Web Python 服务最终应改为调用 `HarnessDB.read_snapshot()` 或复制其 unpack 规则。这项收敛属于共用契约，但不得把当前工作区其它无关 UI 改动打进桌面提交。

## 9. Tauri 配置与发布

### 9.1 配置

- 目标：`x86_64-pc-windows-msvc`
- 版本号单一来源（建议 `board/tauri/package.json`），禁止多处手写漂移
- `bundle.active = false`，`tauri build` 不生成安装器
- 不配置 WebView2 fixed runtime、offline installer、bootstrapper；安装模式为跳过/使用系统 Runtime
- 不使用远程 URL 作为窗口首页
- 开发机可以缺 `cargo-tauri`：构建脚本在**构建时**检查并安装 CLI，但它不进入发行物
- 最终 EXE 不得再查找 Node、Python、仓库相对路径或 `board/static`

### 9.2 发布脚本

新增 `scripts/build_board_desktop.py`，与现有 `scripts/build_board_release.py` 分离。后者继续只打 Web ZIP。

桌面脚本职责：

1. 检查输入文件和工具（`rustc`/`cargo`/`cargo-tauri`）。
2. 以 `board/static/index.html`、`board/static/app.js` 为嵌入输入。
3. 调用固定参数的 release 构建。
4. 原子复制唯一 EXE 到 `board/release-desktop/TaskBoard.exe`。
5. 拒绝未知残留、符号链接、WebView2 目录、Python/Node sidecar、`resources/`。
6. 写 `manifest.json`：SHA-256、大小、PE 架构、版本。
7. 失败不覆盖上一份已验证 EXE，也不动 Web ZIP。

`board/.gitignore` 忽略 Tauri 缓存和 `board/release-desktop/`，不忽略 `board/tauri` 源码。

### 9.3 单文件判定

`board/release-desktop/` 只能有 `TaskBoard.exe` 与 `manifest.json`。必须证明：

- 无 `WebView2Loader.dll`、Runtime 目录、安装器、Python DLL、Node 文件、sidecar
- 任意工作目录启动仍能加载页面
- 不依赖旁边的 `serve.py`、`sessions.py`、`harness_db.py`、`board/static`
- 关闭后无残留 Python/Node 进程
- 有系统 WebView2 时能显示看板；没有时给出中文诊断
- 打开 `harness.db` 不会在项目下生成 `-wal/-shm` 以外的新文件；因 `mode=ro`，也不应主动创建 wal/shm。验证时对比来源目录字节与条目

## 10. 测试与验收

### 10.1 Web 回归必须继续通过

```powershell
python -X utf8 -m pytest tests board/tests -q
node --check board/static/app.js
node board/tests/test_ui.cjs
python -X utf8 scripts/build_board_release.py
```

若工作区已有未提交的数据库看板测试，它们必须改到 `harness_db.py` schema，而不是让桌面去迁就错误 schema。该项可在实施计划中单列，但不得阻塞“桌面跟随权威模型”的决定。

### 10.2 Rust / 协议测试

至少覆盖：

- 来源解析对 `harness.db` / `tasks.json` / 项目根 / `.harness` 的优先级
- 路径穿越、非目录、缺失来源
- `mode=ro`：对只读目录中的 db 可读取；对不存在路径不建文件
- schema v1 unpack、未知 payload 字段、`meta.project`、progress 双换行连接
- schema 非 v1 或缺表：失败闭合，不回退 JSON
- 无 db 时 JSON 回退与 BOM/UTF-8 错误
- 存在 db 时忽略旁边 JSON
- 结构化中文契约：缺字段、重复 id、非法状态、`_zh`、`board.i18n.json`、空进度
- 不调用 `import_legacy`、不写库；测试前后数据库与 JSON 字节不变
- 端口只绑定回环
- 四个 API 的状态码与字段
- 会话探测读 `meta.project` 而不是 `tasks.project` 列
- 选择器单飞与取消
- 发布目录扫描无 WebView2/Python/Node

用同一组 fixture 对照 Python `HarnessDB.read_snapshot()` 的任务 id 顺序、meta、counts 和 progress 文本。

### 10.3 Windows 发行验收

在干净临时目录只放 `TaskBoard.exe`：

1. 从任意 cwd 启动。
2. 载入含 `harness.db` 的 harness，任务列表、证据、评审、进度可见，项目名来自 `meta.project`。
3. 外部用 Python 向该库插入一条任务（测试进程可写；EXE 不可写），两秒内页面更新。
4. 载入无 db、仅有 JSON 的目录，行为与 Web 回退一致。
5. 载入损坏 db，显示错误，不展示旁边 JSON 冒充正常数据。
6. 无效目录与契约失败可见，旧画面不假扮新来源。
7. 会话选择与目录选择各成功一次；取消可关闭。
8. 来源目录、session JSONL、数据库文件字节不变。
9. 关闭窗口后 HTTP 端口释放。
10. 无 WebView2 环境（或模拟失败）显示中文诊断。

视觉验收必须用真实 WebView2 窗口，不以 Node DOM 模拟作为唯一依据。

## 11. 错误与回滚

- 无系统 WebView2：中文诊断，不下载。
- HTTP 启动失败：端口/权限错误，非零退出。
- schema 不支持或 db 损坏：中文错误，失败闭合。
- 来源无效：400，不破坏当前来源。
- 契约失败：清空旧任务渲染并显示来源路径，与 Web 一致。
- 桌面构建失败：不动 Web ZIP，不覆盖上一份已验证 EXE。
- 桌面回归：用户仍用 `board/start.ps1`。两条发布链互不阻断。

## 12. 完成定义

桌面任务只有同时满足以下条件才能标记 `passed`：

- Web 测试与 ZIP 回归通过
- Rust 单元/协议测试通过，且 snapshot 与 `harness_db.read_snapshot()` 对照通过
- 单文件 EXE 验收通过
- 有系统 WebView2 的真实窗口验收通过
- 无 WebView2 时中文诊断通过
- 发布目录与依赖扫描通过（无 Runtime/安装器/sidecar）
- 只读证据：任务文件与 `harness.db` 字节在 EXE 运行前后一致
- 独立上下文评审写入 `reviews.jsonl`
- 构建、哈希、启动验证可重放

`evidence_ready` 不等于 `passed`。

## 13. 实施前必须锁定的决定

以下决定视为已锁定，实施计划不得改写：

1. 保留 Web 看板；Tauri 是附加入口。
2. 单文件 `TaskBoard.exe`，无安装包。
3. 不携带 WebView2，只用系统 WebView2。
4. 主存储是 `harness.db` schema v1；JSON 只是无 db 时的回退。
5. 桌面只读，绝不导入或建库。
6. 规范 snapshot 以 `harness_db.read_snapshot()` 为准。
7. 中文契约校验结构化字段，不伪造 `tasks.json`。
8. 最近来源只写 `%APPDATA%\\TaskHarness\\TaskBoard\\`。
9. 现有 `scripts/build_board_release.py` 继续只打 Web ZIP。
