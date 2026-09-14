"""Static route-contract tests; not evidence that native host actions executed."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / "references/codex-native.md"
PLAN = ROOT / "docs/plans/2026-09-14-codex-native-task-harness-integration.md"

class CodexNativeDocTests(unittest.TestCase):
    def test_route_is_disclosed_and_referenced(self):
        for file in ("SKILL.md", "README.md", "SETUP.md"):
            self.assertIn("references/codex-native.md", (ROOT / file).read_text(encoding="utf-8"))

    def test_all_eleven_routes_have_entry_and_failure_boundary(self):
        text = ROUTE.read_text(encoding="utf-8")
        rows = [line for line in text.splitlines() if re.match(r"\| N\d{2} ", line)]
        self.assertEqual(len(rows), 11)
        self.assertEqual([line.split()[1] for line in rows], [f"N{i:02}" for i in range(1,12)])
        for row in rows:
            cells = [cell.strip() for cell in row.split("|")[1:-1]]
            self.assertEqual(len(cells), 4, row)
            self.assertTrue(all(cells), row)
        for command in ("/init", "/review", "/fork", "/task", "/compact", "/status", "/goal", "/plan", "/memories"):
            self.assertIn(command, text)

    def test_semantic_guardrails(self):
        text = ROUTE.read_text(encoding="utf-8")
        for marker in ("/init 生成 AGENTS.md", "update_plan 仅维护步骤", "仅用户明确要求创建新聊天", "已达到宿主容量上限", "create_thread 没有 fork_context 参数", "不能作为 threadId 使用", "原生压缩尚未执行", "至少连续三个 goal turns", "不能声称切入 Plan mode", "不直接改 MEMORY.md", "用户指定标题优先", "纯导航操作无需初始化/写入 DB", "逻辑能力不一样", "主会话只有在左侧已有新会话并行时才可星标"):
            self.assertIn(marker, text)
        self.assertNotIn("fork_context=false", text)
        self.assertNotIn("新聊天/分支、pin、rename、compact 等无破坏性影响", text)

    def test_plan_covers_same_routes_without_claiming_runtime_pass(self):
        text = PLAN.read_text(encoding="utf-8")
        for i in range(1,12):
            self.assertIn(f"| N{i:02} |", text)
        for marker in ("未经独立最终评审", "未重装用户全局 skill", "真实宿主动作均未执行"):
            self.assertIn(marker, text)

    def test_markdown_links_fences_and_encoding(self):
        files = [ROUTE, PLAN, ROOT / "SKILL.md", ROOT / "README.md", ROOT / "SETUP.md", ROOT / "references/codex-parallel.md", ROOT / "references/templates/next-step.md"]
        for path in files:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("\ufffd", text, path)
            self.assertNotIn("\x00", text, path)
            self.assertNotIn(chr(96)+"r"+chr(96)+"n", text, path)
            self.assertEqual(sum(line.startswith("```") for line in text.splitlines()) % 2, 0, path)
            for dest in re.findall(r"\]\(([^)]+)\)", text):
                if "://" not in dest and not dest.startswith("#"):
                    self.assertTrue((path.parent / dest.split("#")[0]).exists(), (path, dest))

if __name__ == "__main__":
    unittest.main()
