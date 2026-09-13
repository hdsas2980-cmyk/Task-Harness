from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class SkillPackagingTests(unittest.TestCase):
    def test_skill_does_not_ship_board(self):
        templates = ROOT / 'references' / 'templates'
        self.assertTrue((templates / 'tasks.json').exists())
        self.assertTrue((templates / 'next-step.md').exists())
        self.assertTrue((ROOT / 'harness_db.py').exists())
        self.assertTrue((ROOT / 'scripts' / 'convert_harness_json.py').exists())
        for name in ('task-harness.html', 'app.js', 'serve_dashboard.py', 'init.ps1', 'init.sh'):
            self.assertFalse((templates / name).exists(), name)
        self.assertFalse((ROOT / 'start-dashboard.ps1').exists())
        skill = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        self.assertIn('board/', skill)
        self.assertNotIn('serve_dashboard.py', skill)
        self.assertIn('harness.db', skill)
        self.assertIn('convert_harness_json.py', skill)
    def test_board_is_independent_dir(self):
        board = ROOT / 'board'
        self.assertTrue((board / 'serve.py').exists())
        self.assertTrue((board / 'start.ps1').exists())
        self.assertTrue((board / 'static' / 'index.html').exists())
        self.assertTrue((board / 'static' / 'app.js').exists())
        js = (board / 'static' / 'app.js').read_text(encoding='utf-8')
        self.assertIn('/api/snapshot', js)
        self.assertIn('startPoll', js)

if __name__ == '__main__':
    unittest.main()
