"""中文契约的真实 CLI 回归；不访问用户项目或已安装技能。"""
import importlib.util
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts/check_task_harness_language.py"
sys.path.insert(0, str(ROOT))
from harness_db import convert_legacy

_spec = importlib.util.spec_from_file_location("task_harness_language", CHECK)
LANGUAGE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(LANGUAGE)


def valid_files():
    return {
        "tasks.json": json.dumps({"project": "任务护栏", "description": "确保任务原文件可读",
            "tasks": [{"id": "t-01", "name": "实现检查", "desc": "检查中文契约",
                       "reason": "暂无阻塞", "next": "运行验证", "status": "active"}]}, ensure_ascii=False),
        "evidence.jsonl": json.dumps({"id": "ev-01", "task": "t-01", "summary": "十二项测试通过",
            "cmd": "pytest -q", "exit": 0, "tests": "12 passed", "rev": "abc123", "ts": "2026-09-12T10:00:00+08:00"}, ensure_ascii=False),
        "reviews.jsonl": json.dumps({"id": "rv-01", "task": "t-01", "ev": "ev-01", "verdict": "pass",
            "reviewer_context": "independent-review", "reason": "验证和范围均通过"}, ensure_ascii=False),
        "progress.txt": "## 2026-09-12 | t-01 | 执行\n- 进展：已完成实现\n- 状态：待独立评审\n- 下一步：提交独立评审\n",
    }


class LanguageContractTests(unittest.TestCase):
    def run_check(self, files, *args, convert=True):
        with tempfile.TemporaryDirectory(prefix="language-test-", dir=ROOT) as tmp:
            root = Path(tmp).resolve()
            self.assertEqual(root.parent, ROOT)
            harness = root / ".harness"
            harness.mkdir()
            for name, content in files.items():
                (harness / name).write_text(content, encoding="utf-8")
            if convert and "--templates" not in args:
                try:
                    convert_legacy(harness)
                except ValueError:
                    pass
            return subprocess.run([sys.executable, "-X", "utf8", str(CHECK), str(root), *args],
                capture_output=True, text=True, encoding="utf-8")

    def assert_rejected(self, files, hint):
        result = self.run_check(files)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(hint, result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def assert_rejected_files(self, files, hint):
        result = LANGUAGE.validate_files(files)
        blob = "\n".join(result["errors"])
        self.assertTrue(result["errors"], blob)
        self.assertIn(hint, blob)

    def test_native_chinese_preserves_machine_values(self):
        result = self.run_check(valid_files())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("证据 1", result.stdout)
        self.assertIn("评审 1", result.stdout)

    def test_project_fields(self):
        for key in ("project", "description"):
            with self.subTest(key=key):
                files = valid_files(); data = json.loads(files["tasks.json"])
                data[key] = "English only"
                files["tasks.json"] = json.dumps(data)
                self.assert_rejected(files, key)

    def test_progress_is_required_and_prose_must_be_chinese(self):
        for content in (None, "", "Task finished. Waiting for review."):
            with self.subTest(content=content):
                files = valid_files()
                if content is None: files.pop("progress.txt")
                else: files["progress.txt"] = content
                self.assert_rejected(files, "progress.txt")

    def test_progress_allows_fenced_commands_and_protocol(self):
        files = valid_files()
        files["progress.txt"] += "```sh\npytest -q\n```\nHARNESS_STATUS: t-01 IN_PROGRESS\nPROGRESS: 0/1\nEXIT_SIGNAL: false\n"
        self.assertEqual(self.run_check(files).returncode, 0)

    def test_original_fields_not_translation_companions(self):
        for filename, field in (("tasks.json", "name_zh"), ("evidence.jsonl", "summary_zh"), ("reviews.jsonl", "reason_zh")):
            with self.subTest(filename=filename):
                files = valid_files(); data = json.loads(files[filename])
                target = data["tasks"][0] if filename == "tasks.json" else data
                target[field] = "旁挂中文"
                files[filename] = json.dumps(data)
                self.assert_rejected(files, field)
        files = valid_files(); files["board.i18n.json"] = "{}"
        self.assert_rejected(files, "board.i18n.json")

    def test_missing_or_wrong_task_structure(self):
        for data in ({}, {"tasks": {}}, [], {"project":"中文", "description":"中文", "tasks":[None]}):
            with self.subTest(data=data):
                files = valid_files(); files["tasks.json"] = json.dumps(data)
                self.assert_rejected_files(files, "tasks.json")

    def test_readable_fields_must_be_strings_and_not_placeholders(self):
        for value in ({"中文": "text"}, ["中文"], "{{中文占位符}}", "<中文理由>"):
            with self.subTest(value=value):
                files = valid_files(); data = json.loads(files["tasks.json"])
                data["tasks"][0]["name"] = value
                files["tasks.json"] = json.dumps(data)
                self.assert_rejected(files, "name")

    def test_jsonl_errors_are_located(self):
        for value in ("{broken", "[]", "null", '{"_comment":"说明", "task":"t-01", "summary":"English"}'):
            with self.subTest(value=value):
                files = valid_files(); files["evidence.jsonl"] = "\n" + value
                self.assert_rejected_files(files, "evidence.jsonl:2")

    def test_comments_are_not_counted_as_executed_records(self):
        files = valid_files()
        files["evidence.jsonl"] = '{"_comment":"尚无验证记录"}'
        files["reviews.jsonl"] = '{"_comment":"尚无评审记录"}'
        result = self.run_check(files)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("证据 0", result.stdout)
        self.assertIn("评审 0", result.stdout)

    def test_bundle_uses_object_members_only_and_checks_existing_prose(self):
        for bundle, hint in ((["t-child"], "bundle"), ([{"id":"t-child", "desc":"实现子任务", "reason":"English"}], "reason")):
            with self.subTest(bundle=bundle):
                files=valid_files(); data=json.loads(files["tasks.json"])
                data["tasks"][0]["bundle"] = bundle
                files["tasks.json"] = json.dumps(data)
                self.assert_rejected(files, hint)

    def test_bundle_requires_verify_and_valid_optional_status(self):
        for child, hint in (({"id":"child", "desc":"实现子任务"}, "verify"),
                ({"id":"child", "desc":"实现子任务", "verify":"pytest", "status":"已通过"}, "status"),
                ({"id":"child", "desc":"实现子任务", "verify":"pytest", "status":["passed"]}, "status")):
            files = valid_files(); data = json.loads(files["tasks.json"])
            data["tasks"][0]["bundle"] = [child]
            files["tasks.json"] = json.dumps(data)
            self.assert_rejected(files, hint)

    def test_malformed_status_is_a_diagnostic_not_a_crash(self):
        for value in ({"中文":"状态"}, ["active"], None):
            files = valid_files(); data = json.loads(files["tasks.json"])
            data["tasks"][0]["status"] = value
            files["tasks.json"] = json.dumps(data)
            self.assert_rejected(files, "status")

    def test_documented_json_examples_are_actually_checked(self):
        text = (ROOT / "references/language-contract.md").read_text(encoding="utf-8")
        examples = [json.loads(code) for code in re.findall(r"```json\n(.*?)\n```", text, re.S)]
        self.assertEqual(len(examples), 2)
        files = valid_files()
        for example, filename, field in zip(examples, ("evidence.jsonl", "reviews.jsonl"), ("summary", "reason")):
            files[filename] = json.dumps(example)
            self.assertEqual(self.run_check(files).returncode, 0)
            invalid = dict(files); example[field] = "English only"
            invalid[filename] = json.dumps(example)
            self.assert_rejected(invalid, field)

    def test_templates_and_documented_examples(self):
        result = subprocess.run([sys.executable, "-X", "utf8", str(CHECK), str(ROOT / "references/templates"), "--templates"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("模板", result.stdout)
        self.assertIn("证据 0", result.stdout)

    def test_missing_db_does_not_fallback_to_json(self):
        result = self.run_check(valid_files(), convert=False)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("禁止回退", result.stderr)
        self.assertIn("harness.db", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_leftover_json_is_ignored_after_convert(self):
        with tempfile.TemporaryDirectory(prefix="language-test-", dir=ROOT) as tmp:
            root = Path(tmp).resolve()
            harness = root / ".harness"
            harness.mkdir()
            for name, content in valid_files().items():
                (harness / name).write_text(content, encoding="utf-8")
            convert_legacy(harness)
            (harness / "tasks.json").write_text(json.dumps({
                "project": "English leftover",
                "description": "should be ignored",
                "tasks": [{"id": "bad", "name": "English", "desc": "English", "reason": "English", "next": "English", "status": "active"}],
            }), encoding="utf-8")
            result = subprocess.run([sys.executable, "-X", "utf8", str(CHECK), str(root)],
                capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_bash_install_delivers_checker(self):
        bash = Path("C:/Program Files/Git/bin/bash.exe")
        if not bash.is_file(): self.skipTest("未安装 Git Bash")
        with tempfile.TemporaryDirectory(prefix="bash-install-test-", dir=ROOT) as tmp:
            home = Path(tmp).resolve(); self.assertEqual(home.parent, ROOT)
            result = subprocess.run([str(bash), str(ROOT / "scripts/install.sh")],
                env=dict(os.environ, CODEX_HOME=home.as_posix()), capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = home / "skills/task-harness"
            self.assertEqual((installed / "scripts/check_task_harness_language.py").read_bytes(), CHECK.read_bytes())
            self.assertTrue((installed / "harness_db.py").is_file())
            self.assertTrue((installed / "scripts/convert_harness_json.py").is_file())
            self.assertFalse((installed / "board").exists())

    def test_installed_skill_delivers_checker(self):
        if os.name != "nt": self.skipTest("PowerShell 安装入口")
        with tempfile.TemporaryDirectory(prefix="install-test-", dir=ROOT) as tmp:
            home = Path(tmp).resolve(); self.assertEqual(home.parent, ROOT)
            env = dict(os.environ, CODEX_HOME=str(home))
            result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts/install.ps1")],
                env=env, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = home / "skills/task-harness"
            self.assertTrue((installed / "scripts/check_task_harness_language.py").is_file(), "安装未交付校验器")
            self.assertEqual((installed / "scripts/check_task_harness_language.py").read_bytes(), CHECK.read_bytes())
            self.assertTrue((installed / "harness_db.py").is_file())
            self.assertTrue((installed / "scripts/convert_harness_json.py").is_file())
            self.assertFalse((installed / "board").exists())
            checked = subprocess.run([sys.executable, "-X", "utf8", str(installed / "scripts/check_task_harness_language.py"),
                str(installed / "references/templates"), "--templates"], capture_output=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)

if __name__ == "__main__":
    unittest.main()
