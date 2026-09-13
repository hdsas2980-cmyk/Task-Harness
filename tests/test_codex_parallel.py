# -*- coding: utf-8 -*-
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"
DOC = ROOT / "references" / "codex-parallel.md"
README = ROOT / "README.md"

POSITIVE = [
    "领袖v1-T9-门禁收口",
    "前端v1-FE-6-列表配置器",
    "前端v3-FE-6-列表配置器",
    "审计v5-AUD-6-清待评审",
    "后端v3-BE-7-OnlineDev配置",
    "测试v2-T9-台账收口",
    "工具v2-A27-看板回写闸",
    "领袖v1-R6-编排推进",
    "领袖v1-看板-UI改版",
    "归档_审计v5-AUD-5-Upstream作废",
    "归档_前端v1-FE-启动即systemError",
    "归档_工具v1-A-模型名变更作废",
    "审计v5.5-AUD-6-清待评审",
]

NEGATIVE = [
    "推进审计前端与三开发机",
    "前端开发线v3 · FE-6 列表配置器",
    "归档_质量监控审计v5.4（本轮派发Upstream rejected，改由v5.5接AUD-5）",
    "领袖v1 T9 门禁收口",
    "v1-T9-门禁收口",
    "领袖-T9-门禁收口",
    "领袖v1-T9",
    "前端v3-FE-6-列表 配置器",
]


def title_re():
    text = DOC.read_text(encoding="utf-8")
    match = re.search("```regex\\s*(.+?)\\s*```", text, re.S)
    if not match:
        raise AssertionError("references/codex-parallel.md missing regex fence")
    return re.compile(match.group(1).strip())


class CodexParallelDocTests(unittest.TestCase):
    def test_skill_points_to_parallel_reference(self):
        skill = SKILL.read_text(encoding="utf-8")
        self.assertIn("references/codex-parallel.md", skill)
        self.assertIn("多会话并行", skill)
        desc = [line for line in skill.splitlines() if line.startswith("description:")][0]
        for word in ("多会话", "子代理", "会话命名", "派卡", "归档", "任务束", "create_thread", "wait_threads"):
            self.assertIn(word, desc)
        self.assertIn("调度硬规则", skill)
        self.assertIn("卸载重装", skill)

    def test_readme_points_to_parallel_reference(self):
        readme = README.read_text(encoding="utf-8")
        self.assertIn("references/codex-parallel.md", readme)

    def test_parallel_doc_has_required_headings(self):
        text = DOC.read_text(encoding="utf-8")
        for heading in (
            "## 1. 会话标题",
            "## 2. 编成",
            "## 3. 创建与派卡",
            "## 4. 写范围与提交",
            "## 5. 子代理还是会话",
            "## 6. 异步回报契约（create_thread 模式）",
            "## 7. 完成、看板、失败重建",
            "## 8. 子代理同步委托（spawn_agent 模式）",
            "## 9. 红线",
        ):
            self.assertIn(heading, text)
        self.assertIn("一轮仍只推进一张卡", text)
        self.assertIn("tasks.json", text)
        self.assertIn("归档_", text)
        self.assertIn("create_thread", text)
        self.assertIn("spawn", text.lower())
        self.assertIn("## 0. 覆盖系统默认", text)
        self.assertNotIn("只在用户明确要求独立会话时", text)

    def test_title_regex_accepts_canonical_names(self):
        pattern = title_re()
        for title in POSITIVE:
            self.assertRegex(title, pattern, title)

    def test_title_regex_rejects_legacy_names(self):
        pattern = title_re()
        for title in NEGATIVE:
            self.assertIsNone(pattern.fullmatch(title), title)


if __name__ == "__main__":
    unittest.main()
