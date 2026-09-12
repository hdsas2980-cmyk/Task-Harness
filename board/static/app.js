'use strict';
try{ document.documentElement.setAttribute('data-boot','pending'); }catch(e){}
const $ = id => document.getElementById(id);
const labels = {pending:'待处理',active:'进行中',evidence_ready:'待独立评审',passed:'已通过',blocked:'已阻塞',regressed:'需回归'};
const colors = {pending:'var(--st-pending)',active:'var(--st-active)',evidence_ready:'var(--st-ready)',passed:'var(--st-passed)',blocked:'var(--st-blocked)',regressed:'var(--st-regressed)'};
const states = Object.keys(labels);
const optional = ['evidence.jsonl','reviews.jsonl','progress.txt','board.json'];
const views = [['all','全部任务'],['blocked','已阻塞'],['evidence_ready','待评审'],['active','进行中'],['eligible','可推进']];
let model = {tasks:{tasks:[]},evidence:[],reviews:[],progress:'',board:null};
// 状态词典：每个词对"人"到底意味着什么 —— 尤其 evidence_ready 最容易误读。
const means = {
  pending:'还没开始',
  active:'正在做，还没交',
  evidence_ready:'做完了，但还没有独立评审确认 —— 既不是"做完"也不是"没做完"，是"等人验"',
  passed:'独立评审通过 —— 只有这个状态能叫"完成"',
  blocked:'卡住了（原因记在任务里，通常是环境缺失）',
  regressed:'曾经通过，但因依赖/接口变更失效，需要重做'
};
const stateSteps = ['pending','active','evidence_ready','passed'];
let visibleRows = [], wantedId = null, loadDismissed = false, dialogTrigger = null;
let selected = 0, filter = 'all', sortBy = 'priority', heroCmd = '', mainTab = 'list', eventFilter = 'both';
let chain = Promise.resolve(), statusTimer = null;
const timers = {
  set(fn, ms){ if(typeof setTimeout === 'function'){ timers.id = setTimeout(fn, ms); } },
  clear(){ if(typeof clearTimeout === 'function' && timers.id != null){ clearTimeout(timers.id); } timers.id = null; }
};
const esc = value => String(typeof value === 'object' ? JSON.stringify(value) : value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const setText = (id,text) => { const el = $(id); if(el) el.textContent = text; };
function status(text, error=false){ timers.clear(); setText('status',text); const el = $('status'); if(el && el.classList && el.classList.toggle) el.classList.toggle('err',error); }
function flash(text){ const el = $('status'); const prev = el ? el.textContent : ''; status(text); timers.set(()=>status(prev), 1600); }
function isLocalFile(){ return location.protocol === 'file:'; }
function localFileHint(){ return '请用 board/start.ps1 启动 HTTP 看板，不要打开 file://。'; }
function parse(texts){
  if(!Object.hasOwn(texts,'tasks.json')) throw Error('缺少任务文件；原任务保持不变');
  let tasks;
  try{tasks = JSON.parse(texts['tasks.json'].replace(/^\uFEFF/,''));}catch{throw Error('任务文件格式错误；原任务保持不变');}
  if(!tasks || !Array.isArray(tasks.tasks)) throw Error('任务文件必须包含任务数组');
  const ids = new Set();
  for(const t of tasks.tasks){
    if(!t || typeof t.id !== 'string' || !t.id.trim() || ids.has(t.id)) throw Error('任务编号缺失或重复');
    if(!Object.hasOwn(labels,t.status)) throw Error('任务包含未知状态');
    if(t.depends_on !== undefined && (!Array.isArray(t.depends_on) || t.depends_on.some(d=>typeof d !== 'string'))) throw Error('任务依赖必须是编号数组');
    ids.add(t.id);
  }
  function jsonl(name){
    return (texts[name] || '').replace(/^\uFEFF/,'').split(/\r?\n/).flatMap((line,i)=>{
      if(!line.trim()) return [];
      try{
        const row = JSON.parse(line);
        if(!row || typeof row !== 'object' || Array.isArray(row)) throw Error();
        return [{...row, _sourceLine:i+1}];
      }catch{
        throw Error((name.startsWith('evidence') ? '证据' : '评审') + '文件第 ' + (i+1) + ' 行格式错误');
      }
    });
  }
  return {tasks, evidence:jsonl('evidence.jsonl'), reviews:jsonl('reviews.jsonl'), progress:texts['progress.txt'] || '', board:parseBoard(texts['board.json'])};
}
function parseBoard(raw){
  try{
    const o = JSON.parse(String(raw || '').replace(/^\uFEFF/,''));
    return (o && typeof o === 'object' && !Array.isArray(o)) ? o : null;
  }catch{ return null; }   // 地图是可选视图，坏了不影响任务队列
}
function install(texts, source){ const parsed = parse(texts); wantedId = visibleRows[selected]?.id || null; model = parsed; render(); status(source + ' · ' + new Date().toLocaleTimeString('zh-CN')); }

function gate(t){
  if(t.status !== 'passed') return '';
  const r = model.reviews.filter(r=>r.task === t.id).at(-1);
  const ev = r && model.evidence.find(e=>e.task === t.id && e.id && e.id === r.ev);
  return r?.verdict === 'pass' && r.reviewer_context && ev?.exit === 0
    ? '已关联记录，独立性须人工核验'
    : '门禁缺口：缺成功证据或独立评审';
}
function eligible(all){
  const byId = new Map(all.map(t=>[t.id,t]));
  return all.filter(t=>(t.status === 'pending' || t.status === 'regressed') && (t.depends_on || []).every(d=>byId.get(d)?.status === 'passed'))
    .sort((a,b)=>Number(a.priority ?? 999999) - Number(b.priority ?? 999999));
}
function depMarkup(byId, deps){
  if(!deps.length) return '<span class="none" title="无依赖">—</span>';
  const done = deps.filter(d=>byId.get(d)?.status === 'passed').length;
  return '<span class="bar" title="依赖 ' + done + '/' + deps.length + ' 已通过"><i style="width:' + (done/deps.length*100) + '%"></i></span>';
}
function waveOf(t){ return t.wave || (t.phase != null ? '阶段 ' + t.phase : '未分组'); }
function setTab(tab){
  const tabs = ['list','trace','log'];
  mainTab = tabs.indexOf(tab) >= 0 ? tab : 'list';
  for(const id of tabs){
    const panel = $('tab-' + id);
    if(panel) panel.hidden = mainTab !== id;
    const btn = $('tab-btn-' + id);
    if(btn && btn.setAttribute) btn.setAttribute('aria-selected', String(mainTab === id));
  }
}
function openEvents(){
  dialogTrigger = document.activeElement;
  const d = $('events-drawer');
  if(d) d.hidden = false;
  $('events-close')?.focus();
}
function closeEvents(){
  const d = $('events-drawer');
  if(d) d.hidden = true;
  if(dialogTrigger?.isConnected) dialogTrigger.focus();
}
function groupedRows(rows){
  const groups = new Map();
  for(const row of rows){
    const key = waveOf(row);
    if(!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  }
  return groups;
}
function stageMarkup(t){
  const index = stateSteps.indexOf(t.status);
  return '<div class="stage-progress" role="img" aria-label="状态阶段：' + esc(labels[t.status]) + '，不代表完成百分比">'
    + stateSteps.map((state,i)=>'<span class="' + (i === index ? 'current' : '') + '"><i></i>' + esc(labels[state]) + '</span>').join('')
    + '</div>';
}
function renderCards(rows, byId){
  const tasksEl = $('tasks');
  if(!tasksEl) return;
  let i = 0;
  tasksEl.innerHTML = [...groupedRows(rows)].map(([stage, items])=>{
    const passed = items.filter(t=>t.status === 'passed').length;
    return '<section class="task-group"><header class="group-head"><h2>' + esc(stage) + '</h2><span>' + passed + '/' + items.length + ' 已通过</span></header>'
      + items.map(t=>{
        const index = i++;
        const deps = t.depends_on || [];
        const evidence = model.evidence.filter(e=>!isMetaRow(e) && e.task === t.id);
        const reviews = model.reviews.filter(r=>!isMetaRow(r) && r.task === t.id);
        const e = evidence.at(-1), r = reviews.at(-1), g = gate(t);
        return '<article class="tcard is-' + esc(t.status) + '" data-status="' + esc(t.status) + '" data-i="' + index + '" aria-selected="' + (index === selected) + '">'
          + '<div class="row"><span class="id">' + esc(t.id) + '</span><span class="pri">优先级 ' + esc(t.priority ?? '—') + '</span></div>'
          + '<div class="state"><i class="dot" style="background:' + colors[t.status] + '"></i>' + labels[t.status] + '</div>'
          + '<button type="button" class="task-select" data-select-task="1">' + esc(t.name || t.desc || '未填写任务名称') + '</button>'
          + '<p class="desc">' + esc(t.desc || '') + '</p>'
          + '<p class="task-reason">当前原因：' + esc(t.reason || '未填写') + '</p>'
          + '<p class="task-next">下一步：' + esc(t.next || '未填写') + '</p>'
          + '<div class="meta"><span>依赖 ' + depMarkup(byId, deps) + ' ' + (deps.length || '无') + '</span>'
          + (g ? '<span class="flag ' + (g.startsWith('门禁') ? 'warn' : '') + '">' + esc(g) + '</span>' : '') + '</div>'
          + '<footer class="card-footer">' + stageMarkup(t)
          + '<div class="card-audits"><button type="button" data-audit="e">证据 ' + evidence.length + '</button><span>' + esc(e?.summary || '暂无验证记录') + '</span>'
          + '<button type="button" data-audit="r">评审 ' + reviews.length + '</button><span>' + esc(r?.reason || '待独立评审') + '</span></div></footer></article>';
      }).join('') + '</section>';
  }).join('') || '<div class="empty">暂无匹配任务。按 L 选择项目任务目录，按 R 刷新。</div>';
}
function progressEntries(){
  const entries = [];
  let current = null;
  let fence = false;
  String(model.progress || '').split(/\r?\n/).forEach((line, i)=>{
    if(line.trim().startsWith('```')) fence = !fence;
    const match = !fence && line.match(/^##\s+([^|]+)\|\s*([^|]+)\|\s*(.+)$/);
    if(match){
      current = {ts:match[1].trim(), task:match[2].trim(), title:match[3].trim(), line:i+1, body:[]};
      entries.push(current);
    }else if(current){ current.body.push(line); }
  });
  return entries;
}
function timeOrder(a,b){
  const at = Date.parse(a.ts), bt = Date.parse(b.ts);
  if(Number.isNaN(at) && Number.isNaN(bt)) return 0;
  if(Number.isNaN(at)) return 1;
  if(Number.isNaN(bt)) return -1;
  return bt - at;
}
function renderTrajectory(current){
  const box = $('trace'); if(!box) return;
  if(!current){ box.innerHTML = '<p class="empty-note">请先在任务列表中选择任务</p>'; return; }
  const rows = [
    ...model.evidence.filter(x=>!isMetaRow(x) && x.task === current.id).map(x=>({...x, title:'验证记录', text:x.summary, source:'evidence.jsonl:' + x._sourceLine})),
    ...model.reviews.filter(x=>!isMetaRow(x) && x.task === current.id).map(x=>({...x, title:'独立评审 · ' + (x.verdict === 'pass' ? '通过' : '未通过'), text:x.reason, source:'reviews.jsonl:' + x._sourceLine})),
    ...progressEntries().filter(x=>x.task === current.id).map(x=>({...x, text:x.body.join('\n'), source:'progress.txt:' + x.line}))
  ].sort(timeOrder);
  box.innerHTML = '<header class="trace-head"><h2>' + esc(current.name || current.desc) + '</h2><span class="id">' + esc(current.id) + '</span><p>当前状态：' + labels[current.status] + ' · 仅展示已落盘记录，不推测历史状态</p></header>'
    + (rows.length ? '<ol class="trace-list">' + rows.slice(0,120).map(x=>'<li><div><b>' + esc(x.title) + '</b><time>' + esc(Number.isNaN(Date.parse(x.ts)) ? '未提供有效时间' : fmtWhen(x.ts)) + '</time></div><pre>' + esc(x.text) + '</pre><small>' + esc(x.source) + (x.id ? ' · ' + esc(x.id) : '') + '</small></li>').join('') + '</ol>'
      + (rows.length > 120 ? '<p>仅展示最近 120 条；完整记录请读取源文件。</p>' : '') : '<p class="empty-note">当前任务暂无轨迹记录</p>');
}
function renderProgress(){
  const box = $('progress'); if(!box) return;
  const entries = progressEntries().reverse();
  box.innerHTML = entries.length ? entries.slice(0,80).map((x,i)=>{
    const summary = x.body.find(line=>line.trim().startsWith('- 进展')) || '展开阅读本轮记录';
    return '<details class="progress-entry"' + (i === 0 ? ' open' : '') + '><summary><span>' + esc(x.title) + ' · ' + esc(x.task) + '</span><time>' + esc(x.ts) + '</time><p>' + esc(summary) + '</p></summary><pre>' + esc(x.body.join('\n').trim()) + '</pre><small>progress.txt:' + x.line + '</small></details>';
  }).join('') + (entries.length > 80 ? '<p>仅展示最近 80 段；完整记录请读取源文件。</p>' : '') : '<p class="empty-note">暂无分段进度；按技能模板追加任务编号与中文进展。</p>';
  box.innerHTML += '<details class="raw-progress"><summary>查看进度原文</summary><pre>' + esc(model.progress || '暂无进度日志') + '</pre></details>';
}
function render(){
  try{ renderAll(); }
  catch(e){ status('界面刷新失败：' + ((e && e.message) || e || '未知错误'), true); }
}
function renderAll(){
  const all = model.tasks.tasks;
  const counts = Object.fromEntries(states.map(s=>[s, all.filter(t=>t.status === s).length]));
  const byId = new Map(all.map(t=>[t.id,t]));
  const ready = eligible(all), next = ready[0];
  const deps = next ? (next.depends_on || []) : [];
  const done = deps.filter(d=>byId.get(d)?.status === 'passed').length;

  setText('proj-name', model.tasks.project || '未命名项目');
  setText('proj-rev', '修订 ' + (model.tasks.rev ?? '—'));
  setText('c-all', String(all.length));
  setText('c-eligible', String(ready.length));
  setText('c-active', String(counts.active));
  setText('c-evidence_ready', String(counts.evidence_ready));
  setText('c-blocked', String(counts.blocked));
  for(const pair of views){
    const id = pair[0];
    let b = null;
    try{ b = document.querySelector('#rail-nav [data-filter="' + id + '"]'); }catch(e){ b = null; }
    if(b && b.setAttribute) b.setAttribute('aria-current', filter === id ? 'page' : 'false');
  }

  const chip = $('filter-chip');
  if(chip){
    if(filter === 'all'){ chip.hidden = true; chip.innerHTML = ''; }
    else{
      const found = views.find(v=>v[0] === filter);
      const name = (found ? found[1] : null) || labels[filter] || filter;
      chip.hidden = false;
      const st = Object.hasOwn(labels, filter) ? filter : ''; if(chip.dataset) chip.dataset.status = st; else if(chip.setAttribute) chip.setAttribute('data-status', st);
      chip.innerHTML = '筛选：' + esc(name) + ' <button type="button" class="chip-x" data-filter="all" aria-label="清除筛选">×</button>';
    }
  }
  const sortEl = $('sort');
  if(sortEl) sortEl.value = sortBy;

  const searchEl = $('search');
  const q = ((searchEl && searchEl.value) || '').toLowerCase();
  const readyIds = new Set(ready.map(t=>t.id));
  let rows = all.filter(t=>{
    if(filter === 'eligible' && !readyIds.has(t.id)) return false;
    if(filter !== 'all' && filter !== 'eligible' && t.status !== filter) return false;
    return JSON.stringify(t).toLowerCase().includes(q);
  });
  rows.sort((a,b)=> sortBy === 'id' ? String(a.id).localeCompare(String(b.id))
    : sortBy === 'status' ? states.indexOf(a.status) - states.indexOf(b.status)
    : Number(a.priority ?? 999999) - Number(b.priority ?? 999999));
  rows = [...groupedRows(rows).values()].flat();
  if(wantedId){ const index = rows.findIndex(t=>t.id === wantedId); if(index >= 0) selected = index; wantedId = null; }
  visibleRows = rows;
  if(selected >= rows.length) selected = Math.max(0, rows.length - 1);
  setText('count', rows.length + ' 条' + (filter === 'all' ? '' : ' · 已筛选') + ' · 第 ' + (rows.length ? selected + 1 : 0) + ' 张');
  setTab(mainTab);

  renderCards(rows, byId);

  const current = rows[selected];
  const detailEl = $('detail');
  if(detailEl){
    if(!current) detailEl.innerHTML = '<p class="empty-note">没有选中任务</p>';
    else{
      const g = gate(current);
      const tDeps = current.depends_on || [];
      detailEl.innerHTML = '<p class="id">' + esc(current.id) + '</p>'
        + '<p>' + labels[current.status] + ' · 优先级 ' + esc(current.priority ?? '—') + '</p>'
        + '<p>' + esc(current.desc || current.description || '未填写') + '</p>'
        + '<p class="muted">依赖 ' + (tDeps.length ? esc(tDeps.join('、')) : '无') + '</p>'
        + (current.reason ? '<p class="warn">当前原因：' + esc(typeof current.reason === 'string' ? current.reason : JSON.stringify(current.reason)) + '</p>' : '')
        + '<p><code>' + esc(current.verify || '未填写验证') + '</code></p>'
        + '<p class="' + (g.startsWith('门禁') ? 'warn' : 'muted') + '">' + esc(g || '无门禁缺口') + '</p>';
    }
  }

  heroCmd = current?.verify || '';
  if($('copy')) $('copy').disabled = !heroCmd;
  renderEvents(current);
  renderTrajectory(current);
  renderProgress();
}
function isMetaRow(x){ return !x || x._comment || x.comment; }
function asText(value){
  if(value == null || value === '') return '';
  if(typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
  try{ return JSON.stringify(value, null, 0); }catch(e){ return String(value); }
}
function kv(label, value){
  const text = asText(value);
  if(!text) return '';
  return '<div class="kv"><span>' + esc(label) + '</span><code>' + esc(text) + '</code></div>';
}
function encodingOf(x){
  const env = (x && typeof x.environment === 'object' && x.environment) ? x.environment : {};
  return x.encoding || x.PYTHONIOENCODING || env.encoding || env.PYTHONIOENCODING || env.PYTHONUTF8 || env.locale || '';
}
function extrasOf(x, known){
  if(!x || typeof x !== 'object') return '';
  return Object.keys(x).filter(k => !known.has(k) && !String(k).startsWith('_') && x[k] != null && x[k] !== '')
    .map(k => kv(k, x[k])).join('');
}
function renderEvidenceCard(x){
  const ok = x.exit === 0;
  return '<article class="event is-e"><header><b>证据 · ' + (ok ? '命令成功' : '未成功验证') + '</b><span class="id">' + esc(x.id) + '</span></header>'
    + '<p class="event-summary">' + esc(x.summary || '缺少中文摘要（契约失败）') + '</p>'
    + '<small>' + esc(x.task) + ' · ' + esc(fmtWhen(x.ts) || '未提供时间') + '</small>'
    + '<details><summary>查看验证细节</summary>' + kv('命令', x.cmd) + kv('退出码', x.exit)
    + kv('原始测试输出', x.tests) + kv('修订标识', x.rev) + kv('编码', encodingOf(x))
    + kv('产物', x.artifacts) + kv('环境', x.environment) + '</details></article>';
}
function renderReviewCard(x){
  return '<article class="event is-r"><header><b>独立评审 · ' + (x.verdict === 'pass' ? '通过' : x.verdict === 'fail' ? '未通过' : '结论未明确') + '</b><span class="id">' + esc(x.id) + '</span></header>'
    + '<p class="event-summary">' + esc(x.reason || '缺少中文理由（契约失败）') + '</p>'
    + '<small>' + esc(x.task) + ' · ' + esc(fmtWhen(x.ts) || '未提供时间') + '</small>'
    + '<details><summary>查看评审依据</summary>' + kv('对应证据', x.ev) + kv('评审上下文', x.reviewer_context) + '</details></article>';
}
function renderEvents(current){
  const eventsEl = $('events');
  if(!eventsEl) return;
  const currentId = current && current.id;
  const belongsToCurrent = x => currentId && !isMetaRow(x) && x.task === currentId;
  const items = [
    ...model.evidence.filter(belongsToCurrent).map(x => ({...x, kind:'e'})),
    ...model.reviews.filter(belongsToCurrent).map(x => ({...x, kind:'r'}))
  ].sort((a,b)=>String(b.ts || '').localeCompare(String(a.ts || '')));
  const filtered = items.filter(x => {
    if(eventFilter === 'e') return x.kind === 'e';
    if(eventFilter === 'r') return x.kind === 'r';
    return true;
  });
  const shown = filtered.slice(0, 80);
  setText('events-count', currentId
    ? (shown.length === filtered.length ? (filtered.length + ' 条') : (shown.length + '/' + filtered.length + ' 条')) + ' · 当前 ' + currentId
    : '未选中任务');
  const filterBtns = (document.querySelectorAll && document.querySelectorAll('#event-filters [data-evf]')) || [];
  filterBtns.forEach(btn => {
    const key = (btn.dataset && btn.dataset.evf) || (btn.getAttribute && btn.getAttribute('data-evf'));
    if(btn.setAttribute) btn.setAttribute('aria-current', eventFilter === key ? 'true' : 'false');
  });
  const empty = !currentId ? '请先在任务列表中选择任务'
    : eventFilter === 'e' ? '当前任务暂无证据'
    : eventFilter === 'r' ? '当前任务暂无评审' : '当前任务暂无证据或评审';
  eventsEl.innerHTML = shown.map(x => x.kind === 'e' ? renderEvidenceCard(x) : renderReviewCard(x)).join('')
    || '<p class="empty-note">' + empty + '</p>';
}
function showEmpty(message){
  lastStamp = '';
  visibleRows = []; wantedId = null;
  model = {tasks:{tasks:[]},evidence:[],reviews:[],progress:''};
  selected = 0;
  render();
  status(message);
}
function guarded(fn){
  const run = chain.then(async()=>{
    const r = $('refresh'), l = $('load');
    try{ await fn(); }
    catch(e){ status('读取失败：' + ((e && e.message) || e || '未知错误'), true); }
    finally{
      if(r) r.disabled = false;
      if(l) l.disabled = false;
    }
  });
  chain = run.catch(()=>{});
  return run;
}
let selectedPath = '';
let lastSource = '';
let sessionCatalog = {projects:[], suggested:null, sessions_dir:''};
let bootTried = false;
function setDirLabel(path){
  const el = $('project');
  if(el) el.textContent = path || (lastSource ? ('上次 ' + lastSource) : '未选择目录');
  const hint = $('source-hint');
  if(hint) hint.textContent = path ? ('只读 · ' + path) : (lastSource ? ('上次路径 ' + lastSource) : '只读，不写任务真相源');
  const lastEl = $('load-last');
  if(lastEl) lastEl.textContent = lastSource ? ('上次路径 ' + lastSource) : '没有上次路径';
}
function rememberPath(path){
  selectedPath = path || '';
  if(selectedPath) lastSource = selectedPath;
  try{ if(lastSource) localStorage.setItem('task-harness-last-source', lastSource); }catch(e){}
  setDirLabel(selectedPath);
}
function noteLastSource(path){
  if(!path) return;
  lastSource = String(path);
  try{ localStorage.setItem('task-harness-last-source', lastSource); }catch(e){}
  if(!selectedPath) setDirLabel('');
}
function loadDrawer(){ return $('load-drawer'); }
function openLoad(automatic=false){
  if(automatic && loadDismissed) return;
  if(!automatic) loadDismissed = false;
  dialogTrigger = document.activeElement;
  const el = loadDrawer();
  if(!el) return;
  el.hidden = false;
  const input = $('load-path');
  if(input && !input.value) input.value = selectedPath || lastSource || '';
  const q = $('load-q');
  if(q) setTimeout(()=>{ if(!el.hidden) q.focus(); }, 0);
}
function closeLoad(){
  loadDismissed = true;
  const el = loadDrawer();
  if(el) el.hidden = true;
  if(dialogTrigger?.isConnected) dialogTrigger.focus();
}
function api(url, opts){
  return fetch(url, Object.assign({cache:'no-store'}, opts || {})).then(async r=>{
    const text = await r.text();
    let data = null;
    try{ data = text ? JSON.parse(text) : {}; }catch(e){ data = {raw:text}; }
    if(!r.ok){
      throw Error((data && data.error) || ('HTTP ' + r.status));
    }
    return data;
  });
}
function fmtWhen(value){
  if(!value) return '';
  const d = new Date(value);
  if(Number.isNaN(d.getTime())) return String(value).replace('T',' ').slice(0,16);
  return d.toLocaleString('zh-CN', {month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit'});
}
function renderLoadList(){
  const box = $('load-list');
  if(!box) return;
  const q = (($('load-q') && $('load-q').value) || '').trim().toLowerCase();
  const only = $('load-harness-only') ? $('load-harness-only').checked : false;
  const suggested = sessionCatalog.suggested || {};
  const rows = (sessionCatalog.projects || []).filter(row=>{
    if(only && !row.has_harness) return false;
    if(!q) return true;
    const blob = [row.cwd, row.latest_title, row.project_name, row.source]
      .concat((row.sessions || []).map(s => [s.id, s.title, s.file].join(' ')))
      .join(' ').toLowerCase();
    return blob.includes(q);
  });
  if(!rows.length){
    const hint = sessionCatalog.sessions_dir
      ? ('没有匹配的会话。会话根 ' + sessionCatalog.sessions_dir)
      : '没有读到 Codex 会话';
    box.innerHTML = '<p class="load-empty">' + esc(hint) + '</p>';
    return;
  }
  box.innerHTML = rows.map((row,i)=>{
    const title = row.latest_title || row.project_name || row.cwd || '未命名会话';
    const badge = row.has_harness
      ? '<span class="badge ok">看板 ' + esc(row.task_count == null ? '' : (row.task_count + ' 项')) + '</span>'
      : '<span class="badge miss">无 tasks.json</span>';
    const isSug = suggested.source && row.source && suggested.source === row.source;
    return '<button type="button" class="load-row' + (isSug ? ' is-suggested' : '') + '" data-i="' + i + '">'
      + '<span><span class="title">' + esc(title) + '</span>'
      + '<span class="cwd">' + esc(row.cwd || '无工作目录') + '</span></span>'
      + '<span class="meta">' + badge
      + '<span class="when">' + esc(fmtWhen(row.latest)) + ' · ' + esc(row.session_count || 0) + ' 会话</span></span>'
      + '</button>';
  }).join('');
  box.querySelectorAll('.load-row').forEach((btn,i)=>{
    btn.addEventListener('click', ()=>{
      const row = rows[i];
      guarded(()=>applySource(row.source || row.cwd, row.has_harness ? '已根据会话载入' : '已绑定目录（尚未编排任务）'));
    });
  });
}
async function refreshSessions(){
  if(isLocalFile()){
    sessionCatalog = {projects:[], suggested:null, sessions_dir:''};
    renderLoadList();
    return null;
  }
  const data = await api('/api/sessions');
  sessionCatalog = data || {projects:[], suggested:null};
  renderLoadList();
  return sessionCatalog;
}
function snapshotFiles(data){
  const files = data?.files;
  if(data?.contract?.errors?.length){
    const message = '中文契约失败，请修复任务原文件：\n' + data.contract.errors.join('\n');
    showEmpty('中文契约失败');
    const box = $('contract-error'); if(box){ box.hidden = false; box.textContent = message; }
    throw Error(message);
  }
  if(!files?.['tasks.json']) return null;
  if(!data.contract || !Array.isArray(data.contract.errors)) throw Error('缺少中文契约检查结果，请使用配套服务启动看板');
  const box = $('contract-error'); if(box){ box.hidden = true; box.textContent = ''; }
  return files;
}
async function applySource(path, label){
  const target = String(path || '').trim();
  if(!target) throw Error('请指定项目根或 .harness 目录');
  const data = await api('/api/source', {
    method:'POST',
    headers:{'Content-Type':'application/json; charset=utf-8'},
    body: JSON.stringify({path: target})
  });
  rememberPath(data.source || target);
  selected = 0; visibleRows = [];
  snapshotFiles(data);
  if(data.files && data.files['tasks.json']){
    lastStamp = stampOf(data.files);
    install(data.files, (label || '已载入') + ' ' + (data.source || target));
    closeLoad();
    return true;
  }
  showEmpty('该目录尚未编排任务');
  closeLoad();
  return false;
}
async function browseDir(){
  status('正在打开目录对话框…');
  const data = await api('/api/pick-dir', {method:'POST', headers:{'Content-Type':'application/json; charset=utf-8'}, body:'{}'});
  if(!data || data.cancelled){ status('已取消选择目录'); return; }
  const input = $('load-path');
  if(input) input.value = data.path || '';
  await applySource(data.path, '已载入所选目录');
}
async function loadFromPath(){
  const input = $('load-path');
  await applySource(input ? input.value : '', '已载入所选目录');
}
async function loadProject(){ await guarded(async()=>{
  if(isLocalFile()) throw Error(localFileHint());
  openLoad();
  status('正在读取 Codex 会话…');
  await refreshSessions();
  status('选择 harness 目录或一条 Codex 会话');
});}
async function pullLive(){
  if(isLocalFile()) throw Error(localFileHint());
  const data = await api('/api/snapshot');
  if(data.last_source) noteLastSource(data.last_source);
  if(data.source) rememberPath(data.source);
  return snapshotFiles(data);
}

function stampOf(texts){
  return ['tasks.json','evidence.jsonl','reviews.jsonl','progress.txt','board.json']
    .map(n => (texts && texts[n]) ? texts[n] : '').join('\u0001');
}
let lastStamp = '';
const POLL_MS = 2000;
let pollTimer = 0;
function startPoll(){
  if(isLocalFile()) return;
  const tick = () => guarded(async()=>{
    const texts = await pullLive();
    if(!texts || !texts['tasks.json']) return;
    const stamp = stampOf(texts);
    if(stamp === lastStamp) return;
    lastStamp = stamp;
    install(texts, '已同步 ' + (selectedPath || '任务目录'));
  });
  tick();
  if(pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(tick, POLL_MS);
}
async function bootstrapSource(){
  if(bootTried || isLocalFile()) return;
  bootTried = true;
  try{
    const snap = await api('/api/snapshot');
    if(snap && snap.last_source) noteLastSource(snap.last_source);
    if(snap && snap.source) rememberPath(snap.source);
    snapshotFiles(snap);
    if(snap && snap.files && snap.files['tasks.json']){
      lastStamp = stampOf(snap.files);
      install(snap.files, '已载入 ' + (snap.source || '任务目录'));
      return;
    }
    openLoad(true);
    const catalog = await refreshSessions();
    const sug = catalog && catalog.suggested;
    if(sug && (sug.source || sug.cwd)){
      const ok = await applySource(sug.source || sug.cwd, sug.reason === 'latest_session' ? '已按最近会话载入' : '已自动载入');
      if(ok) status('已自动载入 ' + (sug.title || sug.cwd || ''));
      return;
    }
    status('选择 harness 目录或一条 Codex 会话');
  }catch(e){
    openLoad(true);
    status('读取会话失败：' + ((e && e.message) || e), true);
  }
}
async function refreshProject(){ await guarded(async()=>{
  try{
    const texts = await pullLive();
    if(!texts){
      if(model.tasks.tasks.length){ status('刷新失败：未找到 tasks.json，已保留上次任务', true); return; }
      showEmpty('尚未编排任务');
      openLoad();
      return;
    }
    lastStamp = stampOf(texts);
    install(texts, '已刷新 ' + (selectedPath || '任务目录'));
  }catch(e){ status('刷新失败：' + e.message + '，已保留上次任务', true); }
});}
function legacyCopy(text){
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.setAttribute('readonly','');
  ta.style.position = 'absolute';
  ta.style.left = '-9999px';
  document.body.appendChild(ta);
  ta.select();
  let ok = false;
  try{ ok = document.execCommand('copy'); }catch(e){ ok = false; }
  ta.remove();
  return ok;
}
async function copyCmd(){
  if(!heroCmd) return;
  let ok = false, err = null;
  try{
    if(navigator.clipboard && window.isSecureContext){ await navigator.clipboard.writeText(heroCmd); ok = true; }
  }catch(e){ err = e; }
  if(!ok){
    try{ ok = legacyCopy(heroCmd); }catch(e){ err = err || e; }
  }
  if(ok) flash('已复制验证命令');
  else status('复制失败：' + ((err && err.message) || '浏览器拒绝访问剪贴板'), true);
}
$('load').onclick = loadProject;
$('refresh').onclick = refreshProject;
$('copy').onclick = copyCmd;
if($('load-close')) $('load-close').onclick = closeLoad;
if($('load-browse')) $('load-browse').onclick = () => guarded(browseDir);
if($('load-path-go')) $('load-path-go').onclick = () => guarded(loadFromPath);
if($('load-refresh-sess')) $('load-refresh-sess').onclick = () => guarded(refreshSessions);
if($('load-q')) $('load-q').addEventListener('input', renderLoadList);
if($('load-harness-only')) $('load-harness-only').addEventListener('change', renderLoadList);
if($('load-path')) $('load-path').addEventListener('keydown', e=>{
  if(e.key === 'Enter'){ e.preventDefault(); guarded(loadFromPath); }
});
const loadEl = loadDrawer();
if(loadEl) loadEl.addEventListener('click', e=>{
  const t = e.target;
  if(t && t.getAttribute && t.getAttribute('data-close-load')) closeLoad();
});
$('search').addEventListener('input', render);
$('sort').addEventListener('change', e=>{ sortBy = e.target.value; render(); });
$('rail-nav').addEventListener('click', e=>{
  const b = e.target.closest ? e.target.closest('[data-filter]') : null;
  if(!b) return;
  filter = b.dataset.filter;
  render();
});
$('filter-chip').addEventListener('click', e=>{
  const b = e.target.closest ? e.target.closest('[data-filter]') : null;
  if(!b) return;
  filter = b.dataset.filter;
  render();
});
function pickRow(e){
  const item = e.target && e.target.closest ? e.target.closest('[data-i]') : null;
  if(!item) return;
  selected = Number(item.dataset.i);
  const audit = e.target.closest('[data-audit]');
  if(audit) eventFilter = audit.dataset.audit;
  render();
  if(audit) openEvents();
}
$('view-tabs').addEventListener('click', e=>{
  const b = e.target.closest ? e.target.closest('[data-tab]') : null;
  if(!b) return;
  setTab(b.dataset.tab);
});
$('tasks').addEventListener('click', pickRow);
const evClose = $('events-close'), evDrawer = $('events-drawer');
if(evClose) evClose.addEventListener('click', closeEvents);
const evFilters = $('event-filters');
if(evFilters) evFilters.addEventListener('click', e=>{
  const b = e.target && e.target.closest ? e.target.closest('[data-evf]') : null;
  if(!b || !['both','e','r'].includes(b.dataset.evf)) return;
  eventFilter = b.dataset.evf;
  render();
});
if(evDrawer) evDrawer.addEventListener('click', e=>{
  const t = e.target;
  if(t && t.getAttribute && t.getAttribute('data-close-drawer')) closeEvents();
});
document.addEventListener('keydown', e=>{
  if(e.key === 'Escape'){ closeEvents(); closeLoad(); return; }
  if(e.key === 'Tab'){
    const drawer = !$('load-drawer')?.hidden ? $('load-drawer') : !$('events-drawer')?.hidden ? $('events-drawer') : null;
    if(drawer){
      const focusable = [...drawer.querySelectorAll('button:not(:disabled),input:not(:disabled),select,summary,[tabindex="0"]')];
      const first = focusable[0], last = focusable.at(-1);
      if(first && e.shiftKey && document.activeElement === first){ e.preventDefault(); last.focus(); }
      else if(last && !e.shiftKey && document.activeElement === last){ e.preventDefault(); first.focus(); }
    }
  }
  if(e.target && e.target.matches && e.target.matches('input,select,textarea')) return;
  if(e.ctrlKey || e.metaKey || e.altKey) return;
  if(e.key === 'l' || e.key === 'L'){ e.preventDefault(); loadProject(); }
  if(e.key === 'r' || e.key === 'R'){ e.preventDefault(); refreshProject(); }
  if(e.key === 'j' || e.key === 'J' || e.key === 'ArrowDown'){ e.preventDefault(); selected++; render(); }
  if(e.key === 'k' || e.key === 'K' || e.key === 'ArrowUp'){ e.preventDefault(); selected = Math.max(0, selected - 1); render(); }
  if(e.key === '/'){ e.preventDefault(); $('search').focus(); }
});
try{ lastSource = localStorage.getItem('task-harness-last-source') || ''; }catch(e){}
render();
setDirLabel('');
try{ document.documentElement.setAttribute('data-boot','ok'); }catch(e){}
if(isLocalFile()){
  status(localFileHint(), true);
}else{
  startPoll();
  bootstrapSource();
}
