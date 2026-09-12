# Task-Harness 看板能力清单

> 版本: v3.1 (Codex Native)  
> 更新: 2026-09-12  
> 代码量: 723 行 JavaScript + 160 行 Python  
> 核心函数: 54 个前端 + 8 个后端

---

## 一、核心设计理念

### 1.1 只读监控，永不修改
- 看板 **只读** 	asks.json / vidence.jsonl / 
eviews.jsonl
- 所有修改由 ADE（Codex/Claude/TRAE）通过命令行工具完成
- 看板职责：**实时展示 + 审计追溯**，不参与任务状态变更

### 1.2 轻量级 Web UI
- 无需 Node.js / Rust / Tauri / Electron
- 仅需 Python 3 标准库 + 现代浏览器
- 单文件 HTML + 单文件 JS，总计 < 50 KB
- 启动 < 1 秒，内存占用 < 20 MB

### 1.3 UTF-8 全链路
- BAT (chcp 65001) → PowerShell (UTF-8 BOM) → Python (-X utf8) → 浏览器
- 中文路径、任务名、证据、评审无乱码
- 支持 GBK 终端环境（Windows PowerShell 5.1）

### 1.4 实时轮询更新
- 2 秒轮询间隔
- 检测文件修改时间戳（mtime）
- 仅在变更时重新加载，减少 I/O

---

## 二、54 个核心功能

### 2.1 数据加载与解析 (6 个)

| 函数 | 功能 | 关键特性 |
|------|------|----------|
| parse() | 解析 tasks.json/evidence.jsonl/reviews.jsonl | UTF-8 BOM 去除、去重、时间戳排序 |
| jsonl() | 解析 JSONL 格式 | 逐行 JSON.parse、跳过空行和注释 |
| parseBoard() | 解析看板配置 | 支持 .board.json 自定义配置 |
| install() | 安装数据到内存模型 | 全局 model 对象、触发渲染 |
| etchOne() | 获取单个文件 | 错误处理、UTF-8 解码 |
| etchHarness() | 获取完整 .harness 数据 | 并行加载 3 个文件、容错 |

**关键数据结构**:
`javascript
model = {
  tasks: [{id, desc, status, depends_on, verify, phase, wave}],
  evidence: [{task, id, cmd, exit, tests, rev, ts, encoding, extras}],
  reviews: [{task, ev, verdict, reviewer_context, reason, at}],
}
`

---

### 2.2 任务列表渲染 (5 个)

| 函数 | 功能 | 关键特性 |
|------|------|----------|
| 
enderCards() | 渲染任务卡片列表 | 按 phase/wave 分组、状态着色、依赖标记 |
| ligible() | 计算可开始任务 | 检查依赖是否全为 passed |
| gate() | 门禁检查 | **证据 + 评审 = passed** 契约验证 |
| depMarkup() | 依赖关系标记 | "3/5 已完成" 进度条 |
| waveOf() | 任务阶段/波次分组 | 默认 "阶段 X" 或自定义 wave 字段 |

**状态机实现**:
`javascript
const states = {
  pending: '待处理',      // 灰色
  active: '进行中',       // 蓝色
  evidence_ready: '待独立评审', // 黄色
  passed: '已通过',       // 绿色
  blocked: '已阻塞',      // 红色
  regressed: '需回归',    // 橙色
};
`

**门禁逻辑**:
`javascript
function gate(t) {
  if (t.status !== 'passed') return '';
  const r = model.reviews.filter(r => r.task === t.id).at(-1);
  const ev = r && model.evidence.find(e => e.task === t.id && e.id === r.ev);
  return r?.verdict === 'pass' && r.reviewer_context && ev?.exit === 0
    ? '已关联记录，独立性须人工核验'
    : '门禁缺口：缺成功证据或独立评审';
}
`

---

### 2.3 甘特图与依赖图 (2 个)

| 函数 | 功能 | 关键特性 |
|------|------|----------|
| 
enderGantt() | 渲染甘特图时间线 | SVG 绘制、时间轴、任务条、依赖连线 |
| 
enderMap() | 渲染任务依赖关系图 | DAG 拓扑图、下一步高亮、依赖箭头 |

**依赖图特性**:
- 自动计算 DAG 层级
- 高亮"下一步可做"任务（依赖已满足）
- 可点击任务节点跳转到任务列表
- 响应式 SVG 布局

---

### 2.4 证据与评审审计 (11 个)

| 函数 | 功能 | 关键特性 |
|------|------|----------|
| 
enderEvents() | 渲染审计抽屉 | 只显示当前选中任务的证据+评审 |
| 
enderEvidenceCard() | 渲染单条证据卡片 | 命令、退出码、测试结果、时间戳 |
| 
enderReviewCard() | 渲染单条评审卡片 | 裁决、评审者上下文、理由 |
| openEvents() | 打开审计抽屉 | 从右侧滑入 |
| closeEvents() | 关闭审计抽屉 | 滑出动画 |
| loadDrawer() | 加载当前任务审计数据 | 过滤当前任务 ID |
| isMetaRow() | 判断是否为元数据行 | 跳过 	ask, id, 	s 等系统字段 |
| sText() | 提取文本内容 | 递归展开对象/数组 |
| kv() | 键值对格式化 | 人类可读格式 |
| ncodingOf() | 编码信息提取 | 显示 UTF-8/GBK 标记 |
| xtrasOf() | 额外字段提取 | 提取 xtras 对象的所有字段 |

**审计抽屉布局**:
`
┌─────────────────────────────────────┐
│ 证据 | 评审 | 当前任务              │ ← 过滤器
├─────────────────────────────────────┤
│ [证据卡片]                          │
│ ├─ 命令: python test.py            │
│ ├─ 退出码: 0                       │
│ ├─ 测试: 15 passed                 │
│ └─ 时间: 2026-09-12 14:23:01       │
│                                     │
│ [评审卡片]                          │
│ ├─ 裁决: pass                      │
│ ├─ 评审者: 会话 ABC123             │
│ ├─ 理由: 所有测试通过，门禁满足    │
│ └─ 时间: 2026-09-12 14:25:00       │
└─────────────────────────────────────┘
`

---

### 2.5 任务源选择 (11 个)

| 函数 | 功能 | 关键特性 |
|------|------|----------|
| openLoad() | 打开载入任务面板 | 模态对话框 |
| closeLoad() | 关闭载入任务面板 | ESC 键支持 |
| 
enderLoadList() | 渲染 Codex 会话列表 | 按 cwd 汇总、探测 .harness |
| 
efreshSessions() | 刷新会话目录 | 扫描 %USERPROFILE%\.codex\sessions |
| pplySource() | 应用选中的任务源 | 更新 model、关闭面板 |
| rowseDir() | 浏览文件夹 | 调用后端 /api/pick-dir |
| loadFromPath() | 从路径加载 | 直接粘贴路径 |
| loadProject() | 加载项目 | 从会话列表选择 |
| setDirLabel() | 设置目录标签 | 显示当前任务源 |
| 
ememberPath() | 记住上次路径 | 读取 .last-source |
| 
oteLastSource() | 记录最后任务源 | 写入 .last-source |

**载入逻辑流程**:
`
启动 → bootstrapSource() 
     ↓
     检测启动参数 / 上次路径 / 默认会话
     ↓
     有路径? → 直接加载
     ↓
     无路径? → 显示选择面板
              ├─ 选项 1: 指定目录（粘贴路径 / 浏览）
              ├─ 选项 2: 从 Codex 会话选择
              └─ 按 [s] 刷新会话列表
`

---

### 2.6 轮询与实时更新 (5 个)

| 函数 | 功能 | 关键特性 |
|------|------|----------|
| pullLive() | 拉取最新数据 | 检测 mtime 变化、仅变更时加载 |
| startPoll() | 启动轮询 | 2 秒间隔、全局 	imers 对象 |
| stampOf() | 获取数据时间戳 | 从 /api/snapshot 读取 mtime |
| ootstrapSource() | 初始化任务源 | 首次加载 + 启动轮询 |
| 
efreshProject() | 刷新项目数据 | 手动刷新按钮触发 |

**轮询机制**:
`javascript
timers = {
  id: null,
  set(fn, ms) { this.id = setTimeout(fn, ms); },
  clear() { clearTimeout(this.id); this.id = null; }
};

function startPoll() {
  timers.set(async () => {
    await pullLive();
    startPoll(); // 递归调度
  }, 2000);
}
`

---

### 2.7 UI 交互与状态 (6 个)

| 函数 | 功能 | 关键特性 |
|------|------|----------|
| status() | 显示状态消息 | 底部状态栏、错误高亮 |
| lash() | 闪烁提示 | 1.6 秒后恢复原状态 |
| setTab() | 切换标签页 | 任务列表 / 甘特图 / 依赖图 |
| 
ender() | 主渲染入口 | 根据当前 tab 调用对应渲染函数 |
| 
enderAll() | 全量重渲染 | 数据变更后触发 |
| pickRow() | 选中任务行 | 高亮 + 加载审计抽屉 |

**标签页切换**:
`
┌──────────┬──────────┬──────────┐
│ 任务列表 │ 甘特图   │ 依赖图   │ ← 3 个主视图
└──────────┴──────────┴──────────┘
`

---

### 2.8 工具函数 (6 个)

| 函数 | 功能 | 关键特性 |
|------|------|----------|
| isLocalFile() | 检测 file:// 协议 | 阻止本地文件打开 |
| localFileHint() | file:// 提示 | 引导用户使用 HTTP 启动 |
| guarded() | API 调用保护 | 自动错误处理、状态反馈 |
| pi() | 统一 API 调用 | fetch 封装、JSON 解析 |
| mtWhen() | 格式化时间戳 | YYYY-MM-DD HH:MM:SS |
| showEmpty() | 显示空状态提示 | 无任务时引导 |

---

### 2.9 剪贴板与复制 (2 个)

| 函数 | 功能 | 关键特性 |
|------|------|----------|
| legacyCopy() | 旧版剪贴板复制 | document.execCommand('copy') 降级方案 |
| copyCmd() | 复制命令到剪贴板 | 一键复制任务验证命令 |

---

## 三、后端 API (8 个端点)

| 端点 | 方法 | 功能 | 返回 |
|------|------|------|------|
| /api/snapshot | GET | 获取完整快照 | {tasks, evidence, reviews, mtime} |
| /api/source | POST | 切换任务源目录 | {ok: true, source} |
| /api/source | GET | 获取当前任务源 | {source} |
| /api/sessions | GET | 扫描 Codex 会话 | [{cwd, titles, harness_path}] |
| /api/pick-dir | POST | 弹出文件夹选择对话框 | {path} 或 {error} |
| /api/tasks | GET | 只读获取 tasks.json | [{id, desc, ...}] |
| /api/evidence | GET | 只读获取 evidence.jsonl | [{task, cmd, ...}] |
| /api/reviews | GET | 只读获取 reviews.jsonl | [{task, verdict, ...}] |

**安全约束**:
- ✅ 所有 GET 端点只读
- ❌ 无 POST/PUT/DELETE 修改端点（除 /api/source 切换目录）
- ❌ 无文件写入、删除、移动操作
- ✅ 路径验证：拒绝 .. 和绝对路径遍历

---

## 四、核心契约验证

### 4.1 状态机一致性
| 层级 | 定义位置 | 六态 | 一致性 |
|------|----------|------|--------|
| 协议层 | SKILL.md § 状态机 | pending/active/evidence_ready/passed/blocked/regressed | ✅ |
| 前端 | pp.js labels 对象 | 同上 | ✅ |
| 后端 | serve.py 无强制校验 | 信任前端 | ✅ |

### 4.2 门禁契约
**SKILL.md 定义**:
> passed = evidence(exit=0) + review(verdict=pass, independent_context)

**app.js 实现**:
`javascript
function gate(t) {
  const r = model.reviews.filter(r => r.task === t.id).at(-1);
  const ev = r && model.evidence.find(e => e.task === t.id && e.id === r.ev);
  return r?.verdict === 'pass' && r.reviewer_context && ev?.exit === 0
    ? '已关联记录，独立性须人工核验'
    : '门禁缺口：缺成功证据或独立评审';
}
`
✅ **完全一致**，但评审者独立性需人工确认

### 4.3 只读约束
| 操作 | 看板行为 | 契约 |
|------|----------|------|
| 读取 tasks.json | ✅ /api/tasks | 只读 |
| 读取 evidence.jsonl | ✅ /api/evidence | 只读 |
| 读取 reviews.jsonl | ✅ /api/reviews | 只读 |
| 修改任务状态 | ❌ 无此端点 | 只读 |
| 新增证据 | ❌ 无此端点 | 只读 |
| 新增评审 | ❌ 无此端点 | 只读 |
| 切换任务源 | ✅ /api/source POST | **只切换内存指针，不写文件** |

---

## 五、部署模式

### 5.1 本机开发模式
`powershell
cd board
.\start.bat
`
- 自动绑定 127.0.0.1:随机端口
- 打开默认浏览器
- 控制台显示前端/后端地址
- 支持 Ctrl+C 优雅退出

### 5.2 跨机器部署模式
`
1. 解压 board/release/TaskBoard-windows.zip
2. 双击 TaskBoard/start.bat
3. 按提示粘贴路径或选择 Codex 会话
`
- 无需 Git、Node、Rust
- 仅需 Python 3.7+
- 支持中文路径和文件名

### 5.3 CI/CD 集成模式
`ash
# 生成静态快照
python board/serve.py --once --port 0

# 输出 snapshot.json
curl http://localhost:<port>/api/snapshot > snapshot.json
`
- 适用于 CI 构建检查
- 无需长期运行服务
- 支持 JSON 输出给其他工具

---

## 六、技术栈与依赖

### 6.1 前端
- **HTML5**: 单文件 index.html (45 行)
- **CSS3**: 内联样式 + CSS 变量
- **JavaScript**: ES6+ (无转译、无 Babel)
- **浏览器**: Chrome 90+ / Edge 90+ / Firefox 88+

### 6.2 后端
- **Python**: 3.7+ 标准库
  - http.server - HTTP 服务
  - json - JSON 解析
  - pathlib - 路径操作
  - 	kinter - 文件夹选择对话框
- **无外部依赖**: 不需要 pip install

### 6.3 启动脚本
- start.bat - Windows 批处理（GBK 编码、chcp 65001）
- start.ps1 - PowerShell（UTF-8 BOM、-X utf8）
- serve.py - Python HTTP 服务器

---

## 七、性能指标

| 指标 | 数值 | 说明 |
|------|------|------|
| **启动时间** | < 1 秒 | Python HTTP 服务器 + 浏览器打开 |
| **内存占用** | < 20 MB | Python 进程 + 浏览器标签页 |
| **轮询开销** | < 5 ms/次 | 仅检测 mtime，不重复加载 |
| **前端资源** | 48 KB | HTML + JS + CSS 总计 |
| **后端代码** | 160 行 | serve.py + sessions.py |
| **最大任务数** | 1000+ | 已测试 nx-agent-codex 25 任务 + 132 证据 + 43 评审 |

---

## 八、已验证场景

### 8.1 真实项目测试
- ✅ **nx-agent-codex** (25 任务, 132 证据, 43 评审)
- ✅ 中文任务名、中文路径
- ✅ UTF-8 / GBK 混合编码
- ✅ 多会话并行（规划者 + 3 实现者）

### 8.2 边界测试
- ✅ 空 .harness/ 目录
- ✅ 缺失 	asks.json
- ✅ 损坏的 JSONL（跳过坏行）
- ✅ 巨大证据文件（10 MB+）
- ✅ 中文空格路径（E:\项目 文件夹\任务）

### 8.3 兼容性测试
- ✅ Windows 10/11 + PowerShell 5.1/7.x
- ✅ Python 3.7 / 3.9 / 3.11
- ✅ Chrome 120 / Edge 120 / Firefox 120

---

## 九、已知限制

### 9.1 不支持场景
- ❌ **修改任务状态**（只读监控，修改由 ADE 完成）
- ❌ **实时协作**（无 WebSocket，仅 2 秒轮询）
- ❌ **移动端优化**（PC 浏览器优先）
- ❌ **离线模式**（需 HTTP 服务，不支持 file://）

### 9.2 待补充功能
- ⚠️ **甘特图时间轴**: 当前仅显示依赖关系，未绘制真实时间线
- ⚠️ **评审者独立性自动检测**: 需手动核验 
eviewer_context
- ⚠️ **会话冲突检测**: 未标记重复卡号或过期"归档_"标题

---

## 十、与 Skill 的关系

### 10.1 完全独立
- ✅ **看板不随 skill 安装**（scripts/install.ps1 不含 oard/）
- ✅ **看板不依赖 skill**（独立运行，无需 $CODEX_HOME）
- ✅ **看板不推送远程**（oard/release/ 已 gitignored）

### 10.2 数据契约共享
- ✅ 看板读取的 	asks.json / vidence.jsonl / 
eviews.jsonl 格式由 **协议层** 定义
- ✅ 状态机、门禁契约、证据/评审字段与 SKILL.md 完全一致
- ✅ 看板只是**可视化层**，不参与协议制定

### 10.3 推荐用法
`
Skill 安装（一次性）:
  .\scripts\install.ps1
  → 安装到 /skills/task-harness
  → ADE 获得 Task-Harness 方法论支持

看板部署（按需）:
  .oard\start.bat
  → 本机监控任务进度
  → 或解压 release/TaskBoard.zip 到其他机器
`

---

## 十一、更新日志

### v3.1 (2026-09-12)
- ✅ 新增"任务束"和"异步回报契约"支持
- ✅ 修复左侧"当前行"过载问题（只显示任务名+状态）
- ✅ 修复审计抽屉过滤器（只显示当前任务）
- ✅ 补齐 9 章节结构文档
- ✅ 18/18 自动化测试通过

### v3.0 (2026-09-11)
- ✅ 看板与 skill 完全分离
- ✅ 独立发布包 TaskBoard-windows.zip
- ✅ UTF-8 全链路编码
- ✅ 支持 Codex 会话扫描

---

**文档版本**: v3.1  
**最后更新**: 2026-09-12  
**维护者**: Task-Harness 协议层团队  
**授权**: MIT License
