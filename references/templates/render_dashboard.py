"""Generate a read-only project dashboard; standard library only."""
import argparse
import datetime as dt
import json
import math
import os
import sys
from pathlib import Path
import tempfile
import webbrowser

STATES = ('pending', 'active', 'evidence_ready', 'passed', 'blocked', 'regressed')
NAMES = ('tasks.json', 'evidence.jsonl', 'reviews.jsonl', 'progress.txt')


def read_snapshot(source):
    texts = {n: (source / n).read_text(encoding='utf-8-sig') for n in NAMES if (source / n).is_file()}
    raw = json.loads(texts.get('tasks.json', '{"tasks":[]}'))
    tasks = raw.get('tasks') if isinstance(raw, dict) else None
    if not isinstance(tasks, list):
        raise ValueError('任务文件必须包含 tasks 数组')
    ids = set()
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get('id'), str) or not task['id'].strip():
            raise ValueError('任务缺少有效编号')
        if task['id'] in ids:
            raise ValueError('重复任务编号: ' + task['id'])
        ids.add(task['id'])
        try:
            if isinstance(task.get('priority'), bool) or not math.isfinite(float(task.get('priority', 999999))):
                raise ValueError()
        except (TypeError, ValueError):
            raise ValueError('优先级必须是有限数值: ' + task['id']) from None
        if task.get('status') not in STATES:
            raise ValueError('未知任务状态: ' + task['id'])
        deps = task.get('depends_on', [])
        if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
            raise ValueError('依赖必须是编号数组: ' + task['id'])
    for name in ('evidence.jsonl', 'reviews.jsonl'):
        for i, line in enumerate(texts.get(name, '').splitlines(), 1):
            if line.strip():
                try:
                    if not isinstance(json.loads(line), dict):
                        raise ValueError()
                except ValueError:
                    raise ValueError(f'{name} 第 {i} 行无效') from None
    return raw, texts


def generate(project, no_open=False, force_open=False):
    target = Path(project).expanduser().resolve()
    if target.name == '.harness':
        output = source = target
    else:
        output = target / '.harness'
        source = output if (output / 'tasks.json').exists() or not (target / 'tasks.json').exists() else target
    if not target.exists() and target.name != '.harness':
        raise ValueError('项目目录不存在: ' + str(target))
    raw, texts = read_snapshot(source)
    output.mkdir(parents=True, exist_ok=True)
    dest = output / 'task-harness.html'
    template = Path(__file__).with_name('task-harness.html.template').read_text(encoding='utf-8-sig')
    payload = dict(files=texts, project=raw.get('project') or output.parent.name,
                   generated=dt.datetime.now(dt.timezone.utc).isoformat(),
                   base='./' if source == output else '../')
    # JSON is embedded as inert text: never let file contents terminate the script element.
    data = json.dumps(payload, ensure_ascii=True).replace('<', r'\u003c').replace('>', r'\u003e').replace('&', r'\u0026')
    html = template.replace('__HARNESS_SNAPSHOT__', data)
    marker = output / '.dashboard-opened'
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n', dir=output, delete=False) as tmp:
            temp_name = tmp.name
            tmp.write(html)
        os.replace(temp_name, dest)
    finally:
        if temp_name and Path(temp_name).exists():
            Path(temp_name).unlink()
    print('DASHBOARD: ' + str(dest))
    tasks = raw['tasks']
    passed = sum(t['status'] == 'passed' for t in tasks)
    print(f'PROGRESS: {passed}/{len(tasks)}  rev={raw.get("rev", 1)}')
    if tasks and passed == len(tasks):
        print('EXIT_SIGNAL: true  — 全部任务状态为已通过。')
        print('注意: 看板不代替独立评审；passed 须有对应 evidence 与独立 pass review。')
    else:
        print('EXIT_SIGNAL: false  (完成门禁须由独立评审确认)')
    ids = {t['id']: t for t in tasks}
    eligible = [t for t in tasks if t['status'] in ('pending', 'regressed') and
                all(ids.get(d, {}).get('status') == 'passed' for d in t.get('depends_on', []))]
    eligible.sort(key=lambda t: float(t.get('priority', 999999)))
    if eligible:
        print('下一个任务: ' + json.dumps(eligible[0], ensure_ascii=False))
    for state, label in [('active', '进行中'), ('evidence_ready', '待独立评审'), ('blocked', '已阻塞')]:
        items = [t['id'] for t in tasks if t['status'] == state]
        if items:
            print(label + ': ' + ', '.join(items))
    if not tasks:
        print('尚未编排任务；已生成空白页面，任务文件未改动。')
    if tasks and not no_open and (force_open or not marker.exists()):
        if webbrowser.open(dest.as_uri()):
            marker.write_text(str(dest), encoding='utf-8')
        else:
            print('未能自动打开；请打开 DASHBOARD 路径。')
    return dest


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='生成项目任务看板')
    parser.add_argument('project', nargs='?', default='.')
    parser.add_argument('--no-open', action='store_true')
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args()
    try:
        generate(args.project, args.no_open, args.open)
    except (OSError, ValueError) as exc:
        parser.exit(1, '生成失败: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
