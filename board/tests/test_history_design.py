import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class HistoryDesignTests(unittest.TestCase):
    def test_historical_design_and_ui_interactions(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, '历史界面回归需要 Node.js')
        for script in ('test_history_design.cjs', 'test_ui.cjs'):
            result = subprocess.run([node, str(ROOT / 'board/tests' / script)], capture_output=True, timeout=20)
            self.assertEqual(
                result.returncode,
                0,
                (result.stdout + result.stderr).decode('utf-8', errors='replace'),
            )


if __name__ == '__main__':
    unittest.main()
