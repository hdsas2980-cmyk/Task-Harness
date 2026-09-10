import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dashboard', ROOT / 'references/templates/render_dashboard.py')
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='harness space ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def tasks(self, parent=None, desc='任务'):
        parent = parent or self.root / '.harness'
        parent.mkdir(exist_ok=True)
        path = parent / 'tasks.json'
        path.write_text(json.dumps({'project': '测试项目', 'rev': 1, 'tasks': [
            {'id': 'a', 'status': 'pending', 'desc': desc, 'depends_on': [], 'priority': 1}
        ]}, ensure_ascii=False), encoding='utf-8-sig')
        return path

    def run_generate(self, target=None, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return dashboard.generate(target or self.root, **kwargs)

    def test_empty_project_creates_no_fake_tasks_and_no_open(self):
        with patch.object(dashboard.webbrowser, 'open') as opener:
            out = self.run_generate()
        self.assertTrue(out.exists())
        self.assertFalse((out.parent / 'tasks.json').exists())
        opener.assert_not_called()

    def test_first_orchestration_opens_once_and_explicit_open(self):
        self.tasks()
        with patch.object(dashboard.webbrowser, 'open', return_value=True) as opener:
            out = self.run_generate()
            self.run_generate()
            self.run_generate(force_open=True)
            self.assertEqual(opener.call_count, 2)
            self.assertEqual(opener.call_args.args[0], out.as_uri())

    def test_no_open_does_not_consume_first_open(self):
        self.tasks()
        with patch.object(dashboard.webbrowser, 'open', return_value=True) as opener:
            self.run_generate(no_open=True)
            opener.assert_not_called()
            self.run_generate()
            opener.assert_called_once()

    def test_existing_harness_and_regeneration_preserve_source(self):
        src = self.tasks()
        before = src.read_bytes()
        out = self.run_generate(self.root / '.harness', no_open=True)
        self.assertEqual(src.read_bytes(), before)
        self.assertFalse((out.parent / '.harness').exists())
        self.tasks(desc='更新任务')
        self.run_generate(no_open=True)
        self.assertIn(r'\u66f4\u65b0', out.read_text(encoding='utf-8'))

    def test_root_layout_preserved(self):
        src = self.tasks(self.root)
        before = src.read_bytes()
        out = self.run_generate(no_open=True)
        self.assertEqual(src.read_bytes(), before)
        self.assertFalse((out.parent / 'tasks.json').exists())
        self.assertIn('"base": "../"', out.read_text(encoding='utf-8'))

    def test_script_injection_is_inert(self):
        self.tasks(desc='</script><img src=x onerror=alert(1)>')
        out = self.run_generate(no_open=True)
        html = out.read_text(encoding='utf-8')
        self.assertNotIn('</script><img', html)
        self.assertIn(r'\u003c/script\u003e', html)

    def test_bad_jsonl_preserves_last_html(self):
        self.tasks()
        out = self.run_generate(no_open=True)
        before = out.read_bytes()
        (out.parent / 'reviews.jsonl').write_text('{bad', encoding='utf-8')
        with self.assertRaises(ValueError): self.run_generate(no_open=True)
        self.assertEqual(before, out.read_bytes())

    def test_unknown_status_and_duplicate_id_rejected(self):
        src = self.tasks()
        data = json.loads(src.read_text(encoding='utf-8-sig'))
        data['tasks'][0]['status'] = 'injected'
        src.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(ValueError): self.run_generate(no_open=True)
        data['tasks'][0]['status'] = 'pending'
        data['tasks'] *= 2
        src.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(ValueError): self.run_generate(no_open=True)

    def test_packaging(self):
        src = self.tasks()
        data = json.loads(src.read_text(encoding='utf-8-sig'))
        data['tasks'][0]['priority'] = None
        src.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(ValueError): self.run_generate(no_open=True)
        self.assertFalse((ROOT / 'references/templates/task-harness.html').exists())
        self.assertFalse((ROOT / 'references/visualizer/task-harness.html').exists())
        text = (ROOT / 'references/templates/task-harness.html.template').read_text(encoding='utf-8')
        self.assertNotIn('载入示例', text)
        self.assertNotIn('清空', text)
        self.assertIn('刷新任务', text)
        self.assertIn('评审未通过', text)


if __name__ == '__main__':
    unittest.main()
