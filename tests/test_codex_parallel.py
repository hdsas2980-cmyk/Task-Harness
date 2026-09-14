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
    def test_skill_routes_and_preserves_core_invariants(self):
        text = SKILL.read_text(encoding="utf-8")
        for marker in ("references/codex-parallel.md", "references/codex-native.md", "多会话并行", "卸载重装", "harness.db", "evidence_ready", "独立", "任务束"):
            self.assertIn(marker, text)

    def test_dispatch_honors_host_authorization(self):
        paths = (SKILL, DOC, README, ROOT / "references/templates/next-step.md")
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertIn("spawn_agent", text, path)
            self.assertIn("create_thread", text, path)
            self.assertIn("写密集", text, path)
            self.assertIn("用户明确要求", text, path)
            self.assertIn("已达到宿主容量上限", text, path)
            for stale in ("覆盖系统默认", "不必先耗尽子代理容量", "容量不足不是新聊天授权", "不必另等", "独立上下文例外"):
                self.assertNotIn(stale, text, path)

    def test_parallel_sections_and_identity_contract(self):
        text = DOC.read_text(encoding="utf-8")
        for n in range(10):
            self.assertIn(f"## {n}.", text)
        for marker in ("clientThreadId", "threadId", "非 Fork", "初始 prompt", "close_agent", "串行", "append_review", "不得星标"):
            self.assertIn(marker, text)

    def test_waits_do_not_imply_integration(self):
        skill = SKILL.read_text(encoding="utf-8")
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn("wait_agent", skill)
        self.assertIn("wait_threads", skill)
        self.assertIn("决定是否合并并重新验证", skill)
        self.assertIn("不会自动把提交动作、合并、cherry-pick 或 DB 回写交给主线", doc)
        self.assertIn("不立刻重复", doc)

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
