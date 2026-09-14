# Codex 原生能力融合验证记录

日期：2026-09-14。工作目录：E:\D\deep-harness\skill-file\task-harness。分支：codex，起始 HEAD：71e8601。

状态：源码/文档及自动化检查通过；未进行独立最终评审，未重装用户全局 skill，未发布/提交。不将本候选标为 Harness passed，也未修改当前项目控制库或推进工厂任务。

## 本轮用户修订

1. 增强中文契约：写入门禁 + 机器回执白名单 + 失败摘录；看板有 harness.db 时校验数据库 snapshot，忽略 leftover JSON/TXT。这对应其他主机反复出现的 progress.txt:645-648 契约误报。
2. 左侧新会话必须同时满足：用户明确要求、spawn_agent 已满、确需侧栏并行/长期上下文/隔离写入。
3. 官方 /review 是代码差异审查，与 Harness 最终独立评审逻辑能力不一样，不能直接替换；仅等价回执可写入最终 review。
4. 主会话仅在左侧已有新会话并行时可以星标。

## 最终修订验证

| 命令/检查 | 结果 | 边界 |
|---|---|---|
| python -X utf8 -m pytest tests board/tests -q | 91 passed in 55.62s，退出码 0 | 当前工作区测试，包括已有工厂用例；不等于工厂产品验收 |
| Windows 与 Git Bash 安装器测试 | 含于全量 91 passed，临时 CODEX_HOME | 安装副本 references/codex-native.md 与源码逐字节一致；全局目录未替换 |
| node --check board/static/app.js | 退出码 0 | JS 语法 |
| node board/tests/test_ui.cjs | assertions passed，退出码 0 | mock DOM，不是浏览器视觉验收 |
| python -X utf8 scripts/check_task_harness_language.py references/templates --templates | 4 个模板任务通过，退出码 0 | 仅种子模板，不代替真实任务证据 |
| git diff --check | 退出码 0 | 有行尾转换提示，无 whitespace 错误 |
| test_codex_native / 写入门禁 / 看板读库 | 专项通过 | N01–N11 路由、满员门槛、原生审查不等价、主会话星标条件、英文进度拒绝、leftover progress 忽略；不是宿主运行 |

## 未验证与下一道门禁

N01–N11 真实宿主动作均未执行：未新建/Fork/星标/重命名聊天，未原生 compact，未设置持久目标、切换模式或写全局记忆。参考文档基于官方正文和当轮工具定义，不是端到端运行证据。

下一步为明确授权后的新鲜独立审计和范围受限的宿主探针；通过后用安装器完整备份重装，再检查安装文件摘要与新会话加载内容。单次测试成功不能代替该门禁。

## 文件摘要（SHA-256）

以下为本次最终候选；报告自身摘要由交付时另算，避免自引用。

| 文件（相对仓库根） | SHA-256 |
|---|---|
| SKILL.md | 4be8d6c69f631de69c691b852ac5d33f553702f4fd8047e560a45c45cdfbbf3e |
| README.md | 629eb2a9bbb8108130e88cc687ee9db50af78695650696516418660eb4ad119b |
| SETUP.md | 70b8f8da5a14290de7baba017a8f3ebb8af10b592f08577048ab035f0911a575 |
| harness_db.py | a9158c95c0aaa5d642703ce514f739db00a7e2934211e16c50f226c6ae083437 |
| references/codex-native.md | 1b9ecced900daf1ab583ca33b82dd1529e9474853676c428223015b7624445c5 |
| references/codex-parallel.md | f1dcc988255995d4e5a5301183dc1ecfb8d3ea73297b3cedad14e4e6c2864eed |
| references/templates/next-step.md | 73b87f9ef3379f9b4e675ae514b70abe3f1f818e5b36fe6704f452a820da0668 |
| references/language-contract.md | 44f3b38a1839fb851c6a7c23290df9ba85fdee2bd1afb3a7f1123c0b1b8af1c5 |
| references/review/completion-review.md | 7f2a3ee571f910432a0a0f8f1f2297aac5ae44df78b3b5ff3ef828dbfe151134 |
| scripts/check_task_harness_language.py | 0a9c64fa3980f87d1a16088eeaab78a6ba4bb847c39b6d30d5faad6e4f0ed182 |
| board/serve.py | ad71122d1d08a52ace54d8ff8a7e9b5d1c7de2ae25e5e5193c7510a2e97e7bb5 |
| board/sessions.py | b66ccb397860a05cdc12c3a2c81aea46b269096bc8babd7ab6684e9956e621fe |
| board/static/app.js | 0fb384ec729acf0b21e68e0e25db202bc70a43d2aed396802b0966ed90e80e2c |
| tests/test_codex_native.py | 28ed8ff5535d5029c1cb7445942886b66d7c2244986e9a4b8de01da73d8f8686 |
| tests/test_codex_parallel.py | 5947ec42b2a45d5352a03f7add783031e931ad6cbd59d83c272202fc3ad75aa0 |
| tests/test_language_contract.py | addec9321b9a4b0fbfe4da6d18e80d968a0385c305131008dcb1a34ad702d8c4 |
| tests/test_harness_db.py | c3f30f03cd05fadda53179be71d11132085520c04a3e38d08488a353de0bb323 |
| board/tests/test_serve.py | d5a05763caceb5b5aadbe5856d774527bffad591681053ba9a0096eb45bf9320 |
| docs/plans/2026-09-14-codex-native-task-harness-integration.md | 88e376c54509e57fbd2cdad0feedce00759091e06373e77a29d3bb7d7e6591a4 |
