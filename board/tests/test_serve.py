import importlib.util
import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from harness_db import HarnessDB, convert_legacy  # noqa: E402

spec = importlib.util.spec_from_file_location('board_serve', ROOT / 'serve.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fetch(url, data=None, method=None):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    headers = {}
    body = None
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'
        method = method or 'POST'
    req = urllib.request.Request(url, data=body, headers=headers, method=method or 'GET')
    with opener.open(req, timeout=3) as resp:
        return resp.status, resp.read()


def seed_harness(harness: Path, tasks_doc: dict, evidence='', reviews='', progress=''):
    harness.mkdir(parents=True, exist_ok=True)
    (harness / 'tasks.json').write_text(json.dumps(tasks_doc, ensure_ascii=False), encoding='utf-8')
    (harness / 'evidence.jsonl').write_text(evidence, encoding='utf-8')
    (harness / 'reviews.jsonl').write_text(reviews, encoding='utf-8')
    if progress:
        (harness / 'progress.txt').write_text(progress, encoding='utf-8')
    convert_legacy(harness)
    return harness / 'harness.db'


class BoardServeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='board ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.harness = self.root / '.harness'
        self.db = seed_harness(self.harness, {
            'project': '测试项目',
            'rev': 1,
            'tasks': [
                {'id': 'a', 'status': 'pending', 'desc': '中文任务', 'depends_on': [], 'priority': 1}
            ],
        })
        self.other = self.root / 'other'
        seed_harness(self.other / '.harness', {
            'project': '另一个',
            'tasks': [{'id': 'b', 'status': 'active', 'desc': '会话任务'}],
        })
        sessions = self.root / 'sessions'
        sess = sessions / '2026' / '09' / '11'
        sess.mkdir(parents=True)
        (sess / 'rollout.jsonl').write_text(
            json.dumps({
                'timestamp': '2026-09-11T12:00:00Z',
                'type': 'session_meta',
                'payload': {'id': 'sid-1', 'cwd': str(self.other), 'timestamp': '2026-09-11T12:00:00Z'},
            }, ensure_ascii=False) + '\n',
            encoding='utf-8',
        )
        (self.root / 'session_index.jsonl').write_text(
            json.dumps({'id': 'sid-1', 'thread_name': '从会话载入'}, ensure_ascii=False) + '\n',
            encoding='utf-8',
        )
        self._old_sessions = os.environ.get('CODEX_SESSIONS_DIR')
        self._old_last = os.environ.get('TASK_HARNESS_LAST_SOURCE')
        os.environ['CODEX_SESSIONS_DIR'] = str(sessions)
        self.last_file = self.root / 'last-source.txt'
        os.environ['TASK_HARNESS_LAST_SOURCE'] = str(self.last_file)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('127.0.0.1', 0))
        self.port = sock.getsockname()[1]
        sock.close()
        self.httpd = mod.make_server(mod.resolve_source(self.root), self.port)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.addCleanup(self._restore_env)
        self.base = 'http://127.0.0.1:%s' % self.port
        deadline = time.time() + 2
        while time.time() < deadline:
            try:
                fetch(self.base + '/')
                break
            except OSError:
                time.sleep(0.05)

    def _restore_env(self):
        if self._old_sessions is None:
            os.environ.pop('CODEX_SESSIONS_DIR', None)
        else:
            os.environ['CODEX_SESSIONS_DIR'] = self._old_sessions
        if self._old_last is None:
            os.environ.pop('TASK_HARNESS_LAST_SOURCE', None)
        else:
            os.environ['TASK_HARNESS_LAST_SOURCE'] = self._old_last

    def _write_db(self, count=1, project='数据库项目'):
        db_path = self.harness / 'harness.db'
        if db_path.exists():
            db_path.unlink()
        db = HarnessDB(db_path, create=True)
        db.set_meta('project', project)
        db.set_meta('description', '数据库快照')
        for i in range(count):
            db.upsert_task({
                'id': f'db-{i}',
                'status': 'pending',
                'name': f'数据库任务 {i}',
                'desc': f'数据库任务 {i}',
                'reason': '暂无阻塞',
                'next': '继续',
                'depends_on': [],
                'priority': i,
            })
        if count:
            db.append_evidence({'id': 'ev-1', 'task': 'db-0', 'summary': '证据'})
            db.append_review({'id': 'rv-1', 'task': 'db-0', 'verdict': 'pass', 'reason': '独立评审'})
            db.append_progress('数据库进度')
        db.close()
        return db_path

    def _task_by_id(self, snapshot, task_id):
        return next(row for row in snapshot['tasks'] if row['id'] == task_id)

    def test_snapshot_prefers_database_and_keeps_frontend_files_shape(self):
        self._write_db()
        data = mod.snapshot(self.harness)
        self.assertEqual(data['files'], {})
        self.assertEqual(data['snapshot']['project'], '数据库项目')
        self.assertIsInstance(data['snapshot']['tasks'], list)
        self.assertEqual(self._task_by_id(data['snapshot'], 'db-0')['desc'], '数据库任务 0')
        self.assertEqual(data['snapshot']['evidence'][0]['id'], 'ev-1')
        self.assertEqual(data['snapshot']['reviews'][0]['id'], 'rv-1')
        self.assertIn('数据库进度', data['snapshot']['progress'])

    def test_snapshot_database_reads_100_tasks_without_json_fallback(self):
        self._write_db(count=100)
        data = mod.snapshot(self.harness)
        tasks = data['snapshot']['tasks']
        self.assertEqual(len(tasks), 100)
        self.assertEqual(self._task_by_id(data['snapshot'], 'db-99')['id'], 'db-99')
        self.assertEqual(data['files'], {})

    def test_missing_db_does_not_fallback_to_json(self):
        only = self.root / 'json-only' / '.harness'
        only.mkdir(parents=True)
        (only / 'tasks.json').write_text(json.dumps({
            'project': '伪装项目',
            'tasks': [{'id': 'x', 'status': 'pending', 'desc': '不该出现'}],
        }, ensure_ascii=False), encoding='utf-8')
        data = mod.snapshot(only)
        self.assertIsNone(data['snapshot'])
        self.assertEqual(data['files'], {})
        blob = '\n'.join(data['contract']['errors'])
        self.assertIn('禁止回退', blob)
        self.assertIn('harness.db', blob)
        self.assertNotIn('伪装项目', json.dumps(data, ensure_ascii=False))

    def test_snapshot_chinese_and_readonly(self):
        before = self.db.read_bytes()
        status, body = fetch(self.base + '/api/snapshot')
        self.assertEqual(status, 200)
        data = json.loads(body.decode('utf-8'))
        self.assertEqual(data['files'], {})
        self.assertEqual(data['snapshot']['project'], '测试项目')
        self.assertEqual(self._task_by_id(data['snapshot'], 'a')['desc'], '中文任务')
        self.assertTrue(data['source'].endswith('.harness'))
        status, html = fetch(self.base + '/')
        self.assertEqual(status, 200)
        self.assertIn(b'app.js', html)
        self.assertIn('load-drawer'.encode('utf-8'), html)
        self.assertEqual(self.db.read_bytes(), before)

    def test_poll_sees_update(self):
        _, body = fetch(self.base + '/api/snapshot')
        first = json.loads(body.decode('utf-8'))['snapshot']['tasks'][0]['desc']
        with HarnessDB(self.db, create=True) as db:
            task = dict(db.get_task('a')['payload'])
            task['desc'] = '已更新'
            db.upsert_task(task)
        _, body = fetch(self.base + '/api/snapshot')
        second = json.loads(body.decode('utf-8'))['snapshot']['tasks'][0]['desc']
        self.assertNotEqual(first, second)
        self.assertEqual(second, '已更新')

    def test_post_snapshot_rejected(self):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(self.base + '/api/snapshot', data=b'{}', method='POST')
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            opener.open(req, timeout=2)
        self.assertEqual(ctx.exception.code, 405)

    def test_sessions_and_switch_source(self):
        before = self.db.read_bytes()
        status, body = fetch(self.base + '/api/sessions')
        self.assertEqual(status, 200)
        catalog = json.loads(body.decode('utf-8'))
        self.assertTrue(catalog['projects'])
        match = [row for row in catalog['projects'] if Path(row['cwd']) == self.other]
        self.assertEqual(len(match), 1)
        self.assertTrue(match[0]['has_harness'])
        self.assertEqual(match[0]['latest_title'], '从会话载入')
        status, body = fetch(self.base + '/api/source', {'path': str(self.other)})
        self.assertEqual(status, 200)
        data = json.loads(body.decode('utf-8'))
        self.assertEqual(data['files'], {})
        self.assertEqual(self._task_by_id(data['snapshot'], 'b')['desc'], '会话任务')
        self.assertTrue(data['source'].endswith('.harness'))
        self.assertEqual(self.db.read_bytes(), before)
        _, body = fetch(self.base + '/api/snapshot')
        live = json.loads(body.decode('utf-8'))
        self.assertEqual(self._task_by_id(live['snapshot'], 'b')['desc'], '会话任务')

    def test_unbound_server(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.close()
        httpd = mod.make_server(None, port)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            deadline = time.time() + 2
            while time.time() < deadline:
                try:
                    status, body = fetch('http://127.0.0.1:%s/api/snapshot' % port)
                    break
                except OSError:
                    time.sleep(0.05)
            self.assertEqual(status, 200)
            data = json.loads(body.decode('utf-8'))
            self.assertIsNone(data['source'])
            self.assertEqual(data['files'], {})
            self.assertIsNone(data['snapshot'])
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_snapshot_reports_language_failure_without_rewriting_source(self):
        original = self.db.read_bytes()
        _, body = fetch(self.base + '/api/snapshot')
        result = json.loads(body.decode('utf-8'))
        self.assertIn('contract', result)
        self.assertTrue(result['contract']['errors'])
        self.assertIn('description', '\n'.join(result['contract']['errors']))
        self.assertEqual(self.db.read_bytes(), original)

    def test_native_chinese_snapshot_uses_shared_checker(self):
        source = self.harness
        if (source / 'harness.db').exists():
            (source / 'harness.db').unlink()
        seed_harness(source, {
            'project': '测试项目',
            'description': '验证只读看板',
            'tasks': [
                {'id': 'a', 'name': '实现任务', 'desc': '实现验证', 'reason': '暂无阻塞', 'next': '执行验证', 'status': 'active'}
            ],
        }, evidence='', reviews='', progress='## 2026-09-12 | a | 执行\n- 进展：已开始实现\n')
        _, body = fetch(self.base + '/api/snapshot')
        result = json.loads(body.decode('utf-8'))
        self.assertEqual(result['contract']['errors'], [])
        (source / 'board.i18n.json').write_text('{}', encoding='utf-8')
        _, body = fetch(self.base + '/api/snapshot')
        self.assertIn('board.i18n.json', str(json.loads(body.decode('utf-8'))['contract']['errors']))

    def test_switch_remembers_last_source(self):
        status, body = fetch(self.base + '/api/source', {'path': str(self.other)})
        self.assertEqual(status, 200)
        data = json.loads(body.decode('utf-8'))
        self.assertTrue(self.last_file.is_file())
        saved = self.last_file.read_text(encoding='utf-8').strip()
        self.assertEqual(saved, data['source'])
        self.assertEqual(data['last_source'], saved)
        _, body = fetch(self.base + '/api/snapshot')
        snap = json.loads(body.decode('utf-8'))
        self.assertEqual(snap['last_source'], saved)

    def test_choose_project_reuses_last_without_tty(self):
        self.last_file.write_text(str(self.harness) + '\n', encoding='utf-8')
        chosen = mod.choose_project(None, prompt=False)
        self.assertEqual(chosen, self.harness)

    def test_start_ps1_is_ascii(self):
        raw = (ROOT / 'start.ps1').read_bytes()
        if raw.startswith(b'\xef\xbb\xbf'):
            raw = raw[3:]
        raw.decode('ascii')

if __name__ == '__main__':
    unittest.main()
