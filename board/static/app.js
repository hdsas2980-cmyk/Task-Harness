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
const fillOf = {pending:8,active:42,evidence_ready:78,passed:100,blocked:28,regressed:55};
let selected = 0, filter = 'all', sortBy = 'priority', heroCmd = '', mainTab = 'list', eventFilter = 'all';
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
        return [row];
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
function install(texts, source){ model = parse(texts); render(); renderMap(); status(source + ' · ' + new Date().toLocaleTimeString('zh-CN')); }

/* 项目地图：回答"我现在站在哪 / 对不对 / 下一步做什么"。
   数据来自可选的 .harness/board.json —— 缺了就不显示，不影响任务队列。 */
function renderMap(){
  const card = $('map-card'); if(!card) return;
  const b = model.board;
  if(!b || !(b.where || (b.next && b.next.length))){ card.hidden = true; return; }
  card.hidden = false;
  const where = $('map-where');
  if(where) where.textContent = b.where || '';
  const nextEl = $('map-next');
  if(nextEl){
    const next = b.next || [];
    nextEl.innerHTML = next.length ? '<ul>' + next.map(n=>'<li><b>' + esc(n.task) + '</b> —— 为什么是它：' + esc(n.why || '未写')
      + (n.see ? '<br><span class="src">做完你会看到：' + esc(n.see) + '</span>' : '') + '</li>').join('') + '</ul>'
      : '';
  }
}
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
function waveOf(t){ return t.wave || ('阶段 ' + (t.phase ?? '未分组')); }
function setTab(tab){
  const tabs = ['list','gantt','next','log'];
  mainTab = tabs.indexOf(tab) >= 0 ? tab : 'list';
  for(const id of tabs){
    const panel = $('tab-' + id);
    if(panel) panel.hidden = mainTab !== id;
    const btn = $('tab-btn-' + id);
    if(btn && btn.setAttribute) btn.setAttribute('aria-selected', String(mainTab === id));
  }
}
function openEvents(){
  const d = $('events-drawer');
  if(d) d.hidden = false;
}
function closeEvents(){
  const d = $('events-drawer');
  if(d) d.hidden = true;
}
function renderCards(rows, byId){
  const tasksEl = $('tasks');
  if(!tasksEl) return;
  tasksEl.innerHTML = rows.map((t,i)=>{
    const tDeps = t.depends_on || [];
    const depText = tDeps.map(d=>d + '/' + (byId.has(d) ? labels[byId.get(d).status] : '缺失')).join('、') || '无';
    const g = gate(t);
    const cell = g
      ? (g.startsWith('门禁')
          ? '<span class="flag warn" title="' + esc(g) + '">门禁缺口</span>'
          : '<span class="flag" title="' + esc(g) + '">已关联</span>')
      : '';
    const title = t.desc || t.description || '';
    return '<article class="tcard is-' + esc(t.status) + '" data-status="' + esc(t.status) + '" data-i="' + i + '" aria-selected="' + (i === selected) + '">'
      + '<div class="row"><span class="id">' + esc(t.id) + '</span><span class="pri">P' + esc(t.priority ?? '—') + '</span></div>'
      + '<div class="state"><i class="dot" style="background:' + colors[t.status] + '" aria-hidden="true"></i>' + labels[t.status] + '</div>'
      + '<p class="desc" title="' + esc(title) + '">' + esc(title || '未填写') + '</p>'
      + '<div class="meta">'
      + (t.wave || t.phase != null ? '<span class="wave">' + esc(waveOf(t)) + '</span>' : '')
      + '<span>依赖 ' + depMarkup(byId, tDeps) + ' ' + esc(depText === '无' ? '无' : tDeps.length + ' 项') + '</span>'
      + '<span class="cmd mono" title="' + esc(t.verify || '') + '">' + esc(t.verify || '未填写') + '</span>'
      + cell
      + '</div></article>';
  }).join('') || '<div class="empty">暂无匹配任务。按 L 选择项目任务目录，按 R 刷新。</div>';
}
function renderGantt(rows){
  const keyEl = $('gantt-key');
  if(keyEl){
    keyEl.innerHTML = states.map(s=>'<span><i class="dot" style="background:' + colors[s] + '"></i>' + esc(labels[s]) + '</span>').join('')
      + '<span>实心长条 = 已通过 · 短条 = 未完成</span>';
  }
  setText('gantt-count', rows.length + ' 条 · 按 Wave 分组，条长表示完成度');
  const ganttEl = $('gantt');
  if(!ganttEl) return;
  if(!rows.length){
    ganttEl.innerHTML = '<div class="empty">暂无匹配任务。按 L 选择项目任务目录，按 R 刷新。</div>';
    return;
  }
  const groups = [];
  const index = new Map();
  rows.forEach((t,i)=>{
    const key = waveOf(t);
    if(!index.has(key)){ index.set(key, groups.length); groups.push({key, items:[]}); }
    groups[index.get(key)].items.push([t,i]);
  });
  ganttEl.innerHTML = groups.map(g=>{
    const passed = g.items.filter(x=>x[0].status === 'passed').length;
    const pct = Math.round(passed / g.items.length * 100);
    return '<section class="lane"><h3><b>' + esc(g.key) + '</b>'
      + '<span class="lane-meter" title="' + passed + '/' + g.items.length + ' 已通过"><i style="width:' + pct + '%"></i></span>'
      + '<span class="lane-stat">' + passed + '/' + g.items.length + ' 已通过</span></h3>'
      + g.items.map(([t,i])=>{
        const w = fillOf[t.status] ?? 20;
        return '<div class="g-row" data-i="' + i + '" aria-selected="' + (i === selected) + '">'
          + '<span class="id" title="' + esc(t.desc || t.id) + '">' + esc(t.id) + '</span>'
          + '<span class="track" title="' + esc(labels[t.status]) + '"><i style="width:' + w + '%;background:' + colors[t.status] + '"></i></span>'
          + '<span class="g-state"><i class="dot" style="background:' + colors[t.status] + '"></i>' + labels[t.status] + '</span>'
          + '</div>';
      }).join('')
      + '</section>';
  }).join('');
}
function render(){
  try{ renderAll(); }
  catch(e){ status('界面刷新失败：' + ((e && e.message) || e || '未矡错误'), true); }
}
function renderAll(){
  const all = model.tasks.tasks;
  const counts = Object.fromEntries(states.map(s=>[s, all.filter(t=>t.status === s).length]));
  const byId = new Map(all.map(t=>[t.id,t]));
  const ready = eligible(all), next = ready[0];
  const deps = next ? (next.depends_on || []) : [];
  const done = deps.filter(d=>byId.get(d)?.status === 'passed').length;

  setText('proj-name', model.tasks.project || '未命名项目');
  setText('proj-rev', 'rev ' + (model.tasks.rev ?? '—'));
  setText('hero-id', next ? next.id : '—');
  setText('hero-desc', next ? (next.desc || next.description || '未填写描述')
    : (all.length ? '没有可推进任务：依赖未满足或已全部完成' : '尚未编排任务'));
  const hero = $('hero-card');
  if(hero){
    if(hero.classList && hero.classList.toggle) hero.classList.toggle('is-empty', !next);
    if(hero.setAttribute) hero.setAttribute('data-status', next ? next.status : '');
  }
  const dep = $('hero-dep');
  if(dep){
    if(!next) dep.innerHTML = '<span>—</span>';
    else {
      const chain = deps.length
        ? '<span class="ladder">' + deps.map(d=>'<i class="' + (byId.get(d)?.status === 'passed' ? 'on' : 'off') + '"></i>').join('') + '</span>'
          + '<span>依赖 ' + done + '/' + deps.length + ' 已通过</span>'
        : '<span>无前置依赖</span>';
      dep.innerHTML = chain + '<span class="sep"></span><span>优先级 ' + esc(next.priority ?? '—') + '</span>';
    }
  }
  heroCmd = next ? (next.verify || '') : '';
  setText('hero-cmd', heroCmd || '未填写验证命令');
  const copyBtn = $('copy');
  if(copyBtn) copyBtn.disabled = !heroCmd;

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
  const rows = all.filter(t=>{
    if(filter === 'eligible' && !readyIds.has(t.id)) return false;
    if(filter !== 'all' && filter !== 'eligible' && t.status !== filter) return false;
    return JSON.stringify(t).toLowerCase().includes(q);
  });
  rows.sort((a,b)=> sortBy === 'id' ? String(a.id).localeCompare(String(b.id))
    : sortBy === 'status' ? states.indexOf(a.status) - states.indexOf(b.status)
    : Number(a.priority ?? 999999) - Number(b.priority ?? 999999));
  if(selected >= rows.length) selected = Math.max(0, rows.length - 1);
  setText('count', rows.length + ' 条' + (filter === 'all' ? '' : ' · 已筛选') + ' · 第 ' + (rows.length ? selected + 1 : 0) + ' 张');
  setTab(mainTab);

  renderCards(rows, byId);
  renderGantt(rows);

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
        + (tDeps.length ? '<p class="muted">还依赖 ' + esc(tDeps.join('、')) + '</p>' : '')
        + (current.reason ? '<p class="warn">' + esc(typeof current.reason === 'string' ? current.reason : JSON.stringify(current.reason)) + '</p>' : '')
        + (g ? '<p class="' + (g.startsWith('门禁') ? 'warn' : 'muted') + '">' + esc(g) + '</p>' : '');
    }
  }

  renderEvents(rows[selected]);
  setText('progress', model.progress || '暂无进度日志');
}
function isMetaRow(x){ return !x || x._comment || x.comment; }
function asText(value){
  if(value == null || value === '') return '';
  if(typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
  if(Array.isArray(value)) return value.map(asText).filter(Boolean).join('、');
  if(typeof value === 'object'){
    if(value.path || value.name) return asText(value.path || value.name);
    try{ return Object.values(value).map(asText).filter(Boolean).join('、'); }catch(e){ return ''; }
  }
  return String(value);
}
function zhTime(ts){
  if(!ts) return '';
  const d = new Date(ts);
  if(Number.isNaN(d.getTime())) return String(ts);
  return d.toLocaleString('zh-CN', {month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit'});
}
function joinZh(parts){
  const bits = parts.filter(Boolean);
  if(!bits.length) return '';
  return bits.join('，') + '。';
}
function exitMeaning(exit){
  if(exit === 0 || exit === '0') return {cls:'ok', lead:'验证通过', bit:'命令正常结束'};
  if(exit == null || exit === '') return {cls:'miss', lead:'证据不完整', bit:'没写验证结果'};
  return {cls:'bad', lead:'验证失败', bit:'退出码 ' + exit};
}
function reviewContextZh(ctx){
  if(!ctx) return '没写评审是从哪来的';
  const key = String(ctx).trim().toLowerCase();
  const map = {
    'codex-independent-task':'独立 Codex 任务',
    'codex-independent':'独立 Codex 任务',
    'independent':'独立上下文',
    'independent-review':'独立评审上下文',
    'same-session':'同一会话（独立性不够）',
    'same-task':'同一任务里自检（不算独立）',
    'self':'自己评自己（不算独立）'
  };
  return map[key] || ('来源：' + ctx);
}
function renderEvidenceCard(x){
  const ex = exitMeaning(x.exit);
  const tests = asText(x.tests || x.summary);
  const artifacts = asText(x.artifacts);
  const body = joinZh([
    x.cmd ? ('跑了 ' + x.cmd) : '',
    tests ? ('结果是 ' + tests) : '',
    (x.rev && String(x.rev).toUpperCase() !== 'N/A') ? ('代码版本 ' + x.rev) : '',
    artifacts ? ('留下 ' + artifacts) : ''
  ]) || '这条证据没写清到底验证了什么。';
  return '<article class="event is-e">'
    + '<p class="event-lead"><span class="badge ' + ex.cls + '">' + ex.lead + '</span>'
    + '<span>任务 <span class="id">' + esc(x.task || '—') + '</span></span></p>'
    + '<p class="event-body">' + esc(body) + '</p>'
    + '<p class="event-meta">' + esc([ex.bit, x.id ? ('记录 ' + x.id) : '', zhTime(x.ts)].filter(Boolean).join(' · ')) + '</p>'
    + '</article>';
}
function renderReviewCard(x){
  const pass = x.verdict === 'pass';
  const fail = x.verdict === 'fail';
  const cls = pass ? 'ok' : (fail ? 'bad' : 'miss');
  const lead = pass ? '独立评审通过' : (fail ? '独立评审未通过' : '评审结论没写清');
  const reason = asText(x.reason || x.note) || '没写理由。';
  const bits = [
    reviewContextZh(x.reviewer_context),
    x.ev ? ('对照证据 ' + x.ev) : '没挂上对应证据'
  ];
  return '<article class="event is-r">'
    + '<p class="event-lead"><span class="badge ' + cls + '">' + lead + '</span>'
    + '<span>任务 <span class="id">' + esc(x.task || '—') + '</span></span></p>'
    + '<p class="event-body">' + esc(reason.endsWith('。') ? reason : (reason + '。')) + '</p>'
    + '<p class="event-meta">' + esc([bits.join('，'), x.id ? ('记录 ' + x.id) : '', zhTime(x.ts)].filter(Boolean).join(' · ')) + '</p>'
    + '</article>';
}
function renderEvents(current){
  const eventsEl = $('events');
  if(!eventsEl) return;
  const currentId = current && current.id;
  const items = [
    ...model.evidence.filter(x => !isMetaRow(x)).map(x => ({...x, kind:'e'})),
    ...model.reviews.filter(x => !isMetaRow(x)).map(x => ({...x, kind:'r'}))
  ].sort((a,b)=>String(b.ts || '').localeCompare(String(a.ts || '')));
  const filtered = items.filter(x => {
    if(eventFilter === 'e') return x.kind === 'e';
    if(eventFilter === 'r') return x.kind === 'r';
    if(eventFilter === 'current') return currentId && x.task === currentId;
    return true;
  });
  const shown = filtered.slice(0, 80);
  setText('events-count', shown.length === filtered.length
    ? (filtered.length + ' 条记录')
    : ('最近 ' + shown.length + ' / ' + filtered.length + ' 条'));
  const filterBtns = (document.querySelectorAll && document.querySelectorAll('#event-filters [data-evf]')) || [];
  filterBtns.forEach(btn => {
    const key = (btn.dataset && btn.dataset.evf) || (btn.getAttribute && btn.getAttribute('data-evf'));
    if(btn.setAttribute) btn.setAttribute('aria-current', eventFilter === key ? 'true' : 'false');
  });
  eventsEl.innerHTML = shown.map(x => x.kind === 'e' ? renderEvidenceCard(x) : renderReviewCard(x)).join('')
    || '<p class="empty-note">还没有证据或评审记录</p>';
}

async function fetchOne(name){
  const errs = []; let notFound = false;
  for(const base of ['./','../']){
    const rel = base + name;
    try{
      const r = await fetch(new URL(rel, location.href), {cache:'no-store'});
      if(r.ok) return await r.text();
      if(r.status === 404){ notFound = true; continue; }
      errs.push(rel + ' → HTTP ' + r.status);
    }catch(e){ errs.push(rel + ' → ' + ((e && e.message) || '读取异常')); }
  }
  if(!errs.length && notFound) return null;
  throw Error(name + ' 读取失败（' + (errs.join('；') || '未找到') + '）');
}
async function fetchHarness(){
  if(isLocalFile()) throw Error(localFileHint());
  const texts = {};
  const tasks = await fetchOne('tasks.json');
  if(!tasks) return null;
  texts['tasks.json'] = tasks;
  for(const n of optional){
    try{
      const text = await fetchOne(n);
      if(text !== null) texts[n] = text;
    }catch(e){ /* 可选文件缺失或损坏不阻断看板 */ }
  }
  return texts;
}
function showEmpty(message){
  model = {tasks:{tasks:[]},evidence:[],reviews:[],progress:''};
  selected = 0;
  render();
  renderMap();
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
function openLoad(){
  const el = loadDrawer();
  if(!el) return;
  el.hidden = false;
  const input = $('load-path');
  if(input && !input.value) input.value = selectedPath || lastSource || '';
  const q = $('load-q');
  if(q) setTimeout(()=>q.focus(), 0);
}
function closeLoad(){
  const el = loadDrawer();
  if(el) el.hidden = true;
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
async function applySource(path, label){
  const target = String(path || '').trim();
  if(!target) throw Error('请指定项目根或 .harness 目录');
  const data = await api('/api/source', {
    method:'POST',
    headers:{'Content-Type':'application/json; charset=utf-8'},
    body: JSON.stringify({path: target})
  });
  rememberPath(data.source || target);
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
  try{
    const data = await api('/api/snapshot');
    if(data && data.last_source) noteLastSource(data.last_source);
    if(data && data.source) rememberPath(data.source);
    if(data && data.files && data.files['tasks.json']) return data.files;
    return null;
  }catch(e){
    return await fetchHarness();
  }
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
    if(snap && snap.files && snap.files['tasks.json']){
      lastStamp = stampOf(snap.files);
      install(snap.files, '已载入 ' + (snap.source || '任务目录'));
      return;
    }
    openLoad();
    const catalog = await refreshSessions();
    const sug = catalog && catalog.suggested;
    if(sug && (sug.source || sug.cwd)){
      const ok = await applySource(sug.source || sug.cwd, sug.reason === 'latest_session' ? '已按最近会话载入' : '已自动载入');
      if(ok) status('已自动载入 ' + (sug.title || sug.cwd || ''));
      return;
    }
    status('选择 harness 目录或一条 Codex 会话');
  }catch(e){
    openLoad();
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
  render();
}
$('view-tabs').addEventListener('click', e=>{
  const b = e.target.closest ? e.target.closest('[data-tab]') : null;
  if(!b) return;
  setTab(b.dataset.tab);
});
$('tasks').addEventListener('click', pickRow);
$('gantt').addEventListener('click', pickRow);
const evOpen = $('events-open'), evClose = $('events-close'), evDrawer = $('events-drawer');
if(evOpen) evOpen.addEventListener('click', openEvents);
if(evClose) evClose.addEventListener('click', closeEvents);
if(evDrawer) evDrawer.addEventListener('click', e=>{
  const t = e.target;
  if(t && t.getAttribute && t.getAttribute('data-close-drawer')) closeEvents();
});
document.addEventListener('keydown', e=>{
  if(e.key === 'Escape'){ closeEvents(); closeLoad(); }
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
