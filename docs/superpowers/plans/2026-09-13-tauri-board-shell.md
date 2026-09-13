> **已废止（2026-09-13）**
>
> 本文档属于 JSON/JSONL 主存储时代，已被 `docs/superpowers/specs/2026-09-13-tauri-board-shell-db-design.md` 取代。
> **不得按本文档实施。** 用户确认新规格后，应另写 `docs/superpowers/plans/2026-09-13-tauri-board-shell-db.md`。

# Task Harness 看板 Tauri 壳 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变现有 Web 看板的前提下，新增一个只依赖系统 WebView2 的 Windows Tauri 单文件 `TaskBoard.exe`。

**Architecture:** 保留 `board/start.ps1`、Python HTTP 服务和 Web ZIP 发布链；新增独立 `board/tauri/` Tauri v2 工程。Rust 进程内启动仅绑定 `127.0.0.1` 的只读 HTTP 服务，编译期嵌入现有 `board/static/index.html` 与 `app.js`，桌面窗口加载本地 URL，因此 Web 与桌面共享前端和 API 契约，但不共享 Python 运行时。

**Tech Stack:** Rust stable、Tauri v2、serde/serde_json、tiny_http、rfd、Node.js 现有前端测试、Python 现有 Web 发布测试、Windows WebView2 系统运行时。

**Spec:** `docs/superpowers/specs/2026-09-13-tauri-board-shell-design.md`

## Global Constraints

- 保持现有 `board/` Web 看板入口、页面行为、HTTP 启动方式和 ZIP 发布方式可用。
- 最终桌面发布物为单个 `TaskBoard.exe`；不生成 MSI、NSIS、WiX、MSIX 或其他安装包。
- EXE 不携带 WebView2 Runtime、WebView2 安装器、Python、Node.js 或其他外置运行时，仅依赖目标机器已有的系统 WebView2。
- Tauri 壳不增加任务编辑、验证命令执行、证据签署或评审写入功能。
- 桌面服务只读 `tasks.json`、`evidence.jsonl`、`reviews.jsonl`、`progress.txt`、可选 `board.json`，并检查 `board.i18n.json`；任务文件和 Codex sessions JSONL 不得写入。
- HTTP 服务只绑定 `127.0.0.1`；所有本地文件读取必须限制在解析后的 harness 来源目录内。
- Web 与桌面共用 `board/static/index.html`、`board/static/app.js` 和四个 `/api/` 契约；现有 Python 服务不依赖 Rust、Tauri CLI 或 WebView2。
- 构建失败不得删除或覆盖上一份经过验证的桌面 EXE，也不得影响现有 Web ZIP。
- 修改只针对本计划涉及的文件；工作区已有的其他修改不得回退或覆盖。
- 任何桌面任务只有在可重放证据和独立上下文评审同时存在时才能标记 `passed`。

## File Map

- Create: `board/tauri/package.json`，保存 Tauri 开发脚本和版本，不进入发行目录。
- Create: `board/tauri/src-tauri/Cargo.toml`、`tauri.conf.json`、`build.rs`，定义 Tauri、Rust 依赖、编译期资源和无安装包配置。
- Create: `board/tauri/src-tauri/src/main.rs`、`http.rs`、`source.rs`、`sessions.rs`、`contract.rs`、`picker.rs`、`assets.rs`，分别负责应用生命周期、HTTP、来源快照、会话扫描、中文契约、目录选择和资源嵌入。
- Create: `board/tauri/tests/fixtures/`、`test_protocol_fixture.py`、`test_http_protocol.py`、`test_window_config.py`、`test_desktop_build.py`，保存跨实现 fixture、API/配置/发行测试。
- Create: `scripts/build_board_desktop.py`，负责固定目标 release 构建、原子复制、PE/依赖检查和哈希清单。
- Modify: `board/.gitignore`、`README.md`、`board/README.md`、`board/CAPABILITIES.md`、`tests/test_board_release.py`，分别增加缓存忽略、双入口说明和回归门禁。

---

### Task 1: 建立 Tauri 工程与资源嵌入边界

**Files:**
- Create: `board/tauri/package.json`
- Create: `board/tauri/src-tauri/Cargo.toml`
- Create: `board/tauri/src-tauri/tauri.conf.json`
- Create: `board/tauri/src-tauri/build.rs`
- Create: `board/tauri/src-tauri/src/main.rs`
- Create: `board/tauri/src-tauri/src/assets.rs`
- Modify: `board/.gitignore`
- Test: `board/tauri/tests/test_desktop_build.py` and `assets.rs` unit tests

**Interfaces:** `assets::index_html() -> &'static [u8]`; `assets::app_js() -> &'static [u8]`; `main::run() -> Result<(), String>`.

- [ ] **Step 1: Write failing resource/config tests.** Assert embedded bytes contain `app.js` and `/api/snapshot`; parse `tauri.conf.json` and assert `bundle.active == false`, no WebView2 installer mode, no remote URL, and no external resource entry.
- [ ] **Step 2: Run `python -X utf8 -m pytest board/tauri/tests/test_desktop_build.py -q` and `cargo test --manifest-path board/tauri/src-tauri/Cargo.toml`; confirm failure because the project is absent.**
- [ ] **Step 3: Create the minimal Tauri v2 project.** Use `x86_64-pc-windows-msvc`, set `bundle.active=false`, keep release configuration free of `devUrl`/remote URLs, and use `include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../static/index.html"))` plus the matching `app.js`. `build.rs` must fail on missing files or forbidden translation hooks (`board.i18n.json`, `parseI18n`, `_zh`). Do not add a Python/Node sidecar.
- [ ] **Step 4: Run `cargo test --manifest-path board/tauri/src-tauri/Cargo.toml assets` and the focused Python config test; confirm PASS.**
- [ ] **Step 5: Commit with `git add board/tauri board/.gitignore; git commit -m "feat: add tauri board project skeleton"`.**

### Task 2: 实现只读来源快照和中文契约

**Files:** `board/tauri/src-tauri/src/source.rs`, `contract.rs`; `board/tauri/tests/fixtures/`; `board/tauri/tests/test_protocol_fixture.py`.

**Interfaces:** `source::resolve_source(&Path) -> Result<PathBuf, SourceError>`; `source::read_snapshot(Option<&Path>, &Path) -> Snapshot`; `source::bind_source(&str, &Path) -> Result<BoundSource, SourceError>`; `contract::validate_files(&BTreeMap<String, String>) -> ContractResult`.

- [ ] **Step 1: Write failing tests.** Cover project root to `.harness`, non-directory and escape rejection, missing core files, UTF-8/BOM, read-error reporting, unchanged project bytes, valid data, duplicate IDs, invalid status, `_zh`, `board.i18n.json`, malformed JSONL, unclosed progress fence, and recursion/depth failure.
- [ ] **Step 2: Run `cargo test --manifest-path board/tauri/src-tauri/Cargo.toml source contract`; confirm failure because the typed modules do not exist.**
- [ ] **Step 3: Port the effective behavior of `board/serve.py::snapshot`, `board/sessions.py::resolve_source`, and `scripts/check_task_harness_language.py`.** Read only the allowed files, preserve physical JSONL line numbers and Chinese error categories, canonicalize and constrain paths below the resolved source, support UTF-8 BOM, and store the last source atomically below the OS app-data directory only.
- [ ] **Step 4: Run the Rust tests and `python -X utf8 -m pytest board/tauri/tests/test_protocol_fixture.py -q`; compare normalized Rust/Python error categories and counts on the same fixtures.**
- [ ] **Step 5: Commit with `git add board/tauri/src-tauri/src/source.rs board/tauri/src-tauri/src/contract.rs board/tauri/tests/fixtures board/tauri/tests/test_protocol_fixture.py; git commit -m "feat: add read-only board source contract"`.**

### Task 3: 移植 Codex 会话发现和原生目录选择

**Files:** `board/tauri/src-tauri/src/sessions.rs`, `picker.rs`, `main.rs`; Rust unit tests and session fixtures.

**Interfaces:** `sessions::sessions_dir(&dyn Env) -> PathBuf`; `sessions::list_session_catalog(&Path, Option<&Path>) -> SessionCatalog`; `picker::pick_directory(&str) -> Result<Option<PathBuf>, PickerError>`; `picker::PickerGate::try_acquire() -> Result<PickerGuard, PickerBusy>`.

- [ ] **Step 1: Write failing tests** for environment precedence (`CODEX_SESSIONS_DIR`, `CODEX_HOME/sessions`, user `.codex/sessions`), cwd grouping, title lookup, latest/single-harness suggestions, backup skipping, malformed JSONL, tail cwd recovery, picker lock and cancel.
- [ ] **Step 2: Run `cargo test --manifest-path board/tauri/src-tauri/Cargo.toml sessions picker`; confirm failure.**
- [ ] **Step 3: Implement bounded scanning with first-line limit `256 * 1024`, tail limit `64 * 1024`, skip `__backups__`/`__backup_*`, and preserve `scanned`, `skipped`, `suggested`, `projects`, `sessions_dir`, and current `source`. Use `rfd` or Windows common-item APIs; never spawn PowerShell, Python, Tk, or another runtime. Return `Ok(None)` for cancel.
- [ ] **Step 4: Run the focused Rust tests and verify all malformed files are skipped without changing session JSONL.**
- [ ] **Step 5: Commit with `git add board/tauri/src-tauri/src/sessions.rs board/tauri/src-tauri/src/picker.rs board/tauri/src-tauri/src/main.rs; git commit -m "feat: add native board source selection"`.**

### Task 4: 增加协议兼容的本地 HTTP 服务

**Files:** `board/tauri/src-tauri/src/http.rs`, `main.rs`; `board/tauri/tests/test_http_protocol.py`.

**Interfaces:** `http::choose_port(Option<u16>) -> Result<u16, HttpError>`; `http::ServerState::new(PathBuf) -> ServerState`; `http::ServerState::serve(SocketAddr) -> Result<ServerHandle, HttpError>`; `ServerHandle::url() -> Url`; `ServerHandle::shutdown()`.

- [ ] **Step 1: Write failing route tests** for loopback-only binding, `8765..=8799` selection, embedded assets, `/api/snapshot`, `/api/sessions`, `/api/source`, `/api/pick-dir`, allowed files, traversal, invalid JSON, missing source, 400/404/405/409, UTF-8 JSON and `Cache-Control: no-store`.
- [ ] **Step 2: Run `cargo test --manifest-path board/tauri/src-tauri/Cargo.toml http` and the Python integration test; confirm failure.**
- [ ] **Step 3: Implement the threaded local server with `tiny_http`.** Bind only `127.0.0.1`; route to Tasks 2/3; serve `/`, `/index.html`, `/task-harness.html`, `/app.js`; reject decoded `..` before filesystem access; return exact read-only status behavior and never echo request content into HTML.
- [ ] **Step 4: Run `cargo test --manifest-path board/tauri/src-tauri/Cargo.toml http`, `python -X utf8 -m pytest board/tauri/tests/test_http_protocol.py tests board/tests -q`, `node --check board/static/app.js`, and `node board/tests/test_ui.cjs`; confirm PASS.**
- [ ] **Step 5: Commit with `git add board/tauri/src-tauri/src/http.rs board/tauri/src-tauri/src/main.rs board/tauri/tests/test_http_protocol.py; git commit -m "feat: add tauri board local http service"`.**

### Task 5: 接入 Tauri 窗口生命周期和 WebView2 诊断

**Files:** `board/tauri/src-tauri/src/main.rs`, `tauri.conf.json`; `board/tauri/tests/test_window_config.py`; Windows smoke harness.

**Interfaces:** `main::run() -> Result<(), String>` owns `ServerHandle`; `main::diagnose_startup_error(&str) -> String` returns a Chinese diagnostic without installation.

- [ ] **Step 1: Write failing tests** asserting the window has no remote URL, startup diagnostics contain `需要系统 WebView2`, and diagnostics contain no download/install action.
- [ ] **Step 2: Run `python -X utf8 -m pytest board/tauri/tests/test_window_config.py -q`; confirm failure.**
- [ ] **Step 3: In Tauri `setup`, derive OS app-data, start the server, create `main` against `http://127.0.0.1:<port>/`, register shutdown, disable arbitrary navigation, and map WebView2 creation failure to visible Chinese diagnostics without network, installer, registry mutation, or child process.
- [ ] **Step 4: Run config tests, `cargo test`, then a real Windows WebView2 smoke check: page load, load drawer, file update after two seconds, session/folder selection, close cleanup, and no child Python/Node process. Record missing-WebView2 result separately when unavailable.
- [ ] **Step 5: Commit with `git add board/tauri/src-tauri/src/main.rs board/tauri/src-tauri/tauri.conf.json board/tauri/tests/test_window_config.py; git commit -m "feat: wire tauri board window lifecycle"`.**

### Task 6: 构建并验证单文件桌面发布

**Files:** `scripts/build_board_desktop.py`; `board/tauri/tests/test_desktop_build.py`; `board/.gitignore`; `README.md`; `board/README.md`; `board/CAPABILITIES.md`; `tests/test_board_release.py`.

**Interfaces:** `build_board_desktop.py --output <repo-local-dir> --target x86_64-pc-windows-msvc` produces only `TaskBoard.exe` and `manifest.json`; `verify_output(Path) -> None` rejects symlinks, installers, resources, sidecars, WebView2 runtime, Python/Node files, and non-PE/non-x64 output. Manifest records `sha256`, `size`, `target`, `version`, `webview2_mode: "system"`, and static source hashes.

- [ ] **Step 1: Write failing release tests** for exact output whitelist, system WebView2 mode, static hashes, failed build preserving an existing EXE, existing Web ZIP unchanged, and forbidden file/sidecar rejection.
- [ ] **Step 2: Run `python -X utf8 -m pytest board/tauri/tests/test_desktop_build.py tests/test_board_release.py -q`; confirm failure because the builder/verifier do not exist.**
- [ ] **Step 3: Implement non-destructive build.** Validate `cargo`, `rustc`, `cargo-tauri`, MSVC target and static inputs; build release in a temporary repo-local directory; locate and verify PE/x64 output; calculate hashes/metadata; write manifest; atomically publish only after all checks pass. Set `bundle.active=false`, use system WebView2 mode, and reject any external runtime/reference to `board/static`, `serve.py`, `sessions.py`, Python, Node or resources.
- [ ] **Step 4: Update docs and ignores** with both `Web: powershell -ExecutionPolicy Bypass -File .\board\start.ps1 -ProjectDir "E:\path\to\project"` and `Desktop: .\board\release-desktop\TaskBoard.exe`; state one EXE/no installer/no bundled WebView2/system WebView2/read-only/fallback behavior; preserve Web ZIP instructions.
- [ ] **Step 5: Run full verification:** `python -X utf8 -m pytest tests board/tests board/tauri/tests -q`; `node --check board/static/app.js`; `node board/tests/test_ui.cjs`; `python -X utf8 scripts/build_board_release.py`; `python -X utf8 scripts/build_board_desktop.py --output board/release-desktop --target x86_64-pc-windows-msvc`. Copy only the EXE to a clean directory, launch from another cwd, exercise complete harness load, two-second refresh, session/folder selection and byte-identical read-only checks, then confirm no child process after close and perform real-window visual checks.
- [ ] **Step 6: Request independent read-only review, record build command/hash/PE target/output whitelist/WebView2 result/detached startup/byte comparison/reviewer context, then run `git diff --check`, `git status --short`, `git add scripts/build_board_desktop.py board/tauri board/.gitignore README.md board/README.md board/CAPABILITIES.md tests/test_board_release.py`, and commit `feat: add single-file tauri board release`.**
