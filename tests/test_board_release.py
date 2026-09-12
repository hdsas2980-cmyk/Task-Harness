import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]

class BoardReleaseTests(unittest.TestCase):
    def test_build_is_exact_and_includes_same_checker(self):
        builder = ROOT / "scripts/build_board_release.py"
        self.assertTrue(builder.is_file(), "缺少统一发布入口")
        with tempfile.TemporaryDirectory(prefix="release-test-", dir=ROOT) as temp:
            output = Path(temp).resolve(); self.assertEqual(output.parent, ROOT)
            result = subprocess.run([sys.executable, str(builder), "--output", str(output)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            bundle = output / "TaskBoard"
            manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
            with zipfile.ZipFile(output / "TaskBoard-windows.zip") as archive:
                self.assertEqual(set(archive.namelist()), {"TaskBoard/" + name for name in [*manifest, "manifest.json"]})
                for name, sha in manifest.items():
                    data = (bundle / name).read_bytes()
                    self.assertEqual(hashlib.sha256(data).hexdigest(), sha)
                    self.assertEqual(data, archive.read("TaskBoard/" + name))
            self.assertEqual((bundle / "static/app.js").read_bytes(), (ROOT / "board/static/app.js").read_bytes())
            self.assertEqual((bundle / "scripts/check_task_harness_language.py").read_bytes(), (ROOT / "scripts/check_task_harness_language.py").read_bytes())
            for name in ("static/app.js", "static/index.html"):
                text = (bundle / name).read_text(encoding="utf-8")
                for forbidden in ("parseI18n", "translated(", "name_zh", "summary_zh"):
                    self.assertNotIn(forbidden, text)
            probe = subprocess.run([sys.executable, "-B", "-c",
                "import importlib.util,sys; from pathlib import Path; "
                "p=Path(sys.argv[1]); s=importlib.util.spec_from_file_location('release_serve',p/'serve.py'); "
                "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                "assert m.CHECKER.resolve()==(p/'scripts/check_task_harness_language.py').resolve(); "
                "assert m.snapshot(None)['contract'] is None", str(bundle)],
                cwd=output, capture_output=True)
            self.assertEqual(probe.returncode, 0, probe.stderr)
            # 意外遗留文件必须阻断打包，不得被不加检查地放进 ZIP。
            (bundle / "stale.js").write_text("stale", encoding="utf-8")
            failed = subprocess.run([sys.executable, str(builder), "--output", str(output)], capture_output=True)
            self.assertNotEqual(failed.returncode, 0)
