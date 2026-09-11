'use strict';
try{ document.documentElement.setAttribute('data-boot','pending'); }catch(e){}
const $ = id => document.getElementById(id);
const labels = {pending:'待处理',active:'进行中',evidence_ready:'待独立评审',passed:'已通过',blocked:'已阻塞',regressed:'需回归'};
const colors = {pending:'var(--st-pending)',active:'var(--st-active)',evidence_ready:'var(--st-ready)',passed:'var(--st-passed)',blocked:'var(--st-blocked)',regressed:'var(--st-regressed)'};
const states = Object.keys(labels);
const optional = ['evidence.jsonl','reviews.jsonl','progress.txt','board.json'];
const views = [['blocked','已阻塞'],['evidence_ready','待评审'],['active','进行中'],['eligible','可推进'],['all','全部任务']];
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
let selected = 0, filter = 'all', sortBy = 'priority', heroCmd = '', mainTab = 'next';
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
function localFileHint(){ return '点「载入任务」选择项目任务目录（.harness 或项目根）。请用脚本启动 HTTP 看板，不要打开 file://。'; }
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
  mainTab = tabs.indexOf(tab) >= 0 ? tab : 'next';
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
    return '<article class="tcard" data-i="' + i + '" aria-selected="' + (i === selected) + '">'
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
  if(hero && hero.classList && hero.classList.toggle) hero.classList.toggle('is-empty', !next);
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
        + '<p class="muted">依赖 ' + (tDeps.length ? esc(tDeps.join('、')) : '无') + '</p>'
        + (current.reason ? '<p class="warn">阻塞原因：' + esc(typeof current.reason === 'string' ? current.reason : JSON.stringify(current.reason)) + '</p>' : '')
        + '<p><code>' + esc(current.verify || '未填写验证') + '</code></p>'
        + '<p class="' + (g.startsWith('门禁') ? 'warn' : 'muted') + '">' + esc(g || '无门禁缺口') + '</p>';
    }
  }

  const verdict = {pass:'通过',fail:'评审未通过'};
  const events = [...model.evidence.map(x=>({...x,kind:'e'})), ...model.reviews.map(x=>({...x,kind:'r'}))]
    .sort((a,b)=>String(b.ts || '').localeCompare(String(a.ts || ''))).slice(0,5);
  const eventsEl = $('events');
  if(eventsEl){
    eventsEl.innerHTML = events.map(x=>'<div class="event"><b>' + (x.kind === 'e' ? '证据' : '评审')
      + ' · <span class="id">' + esc(x.task || '—') + '</span></b><small>'
      + (x.kind === 'e' ? '退出码 ' + esc(x.exit ?? '未知') : (verdict[x.verdict] || '未知') + ' · ' + esc(x.reviewer_context || '未记录上下文'))
      + '</small><small class="ts">' + esc(x.ts || '未记录时间') + '</small></div>').join('')
      || '<p class="empty-note">暂无证据或评审</p>';
  }
  setText('progress', model.progress || '暂无进度日志');
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
function canPickDir(){ return typeof window.showDirectoryPicker === 'function'; }
let selectedPath = '';
let dirHandle = null;
function setDirLabel(path){
  const el = $('project');
  if(el) el.textContent = path || '未选择目录';
  const hint = $('source-hint');
  if(hint) hint.textContent = path ? ('只读 · ' + path) : '只读，不写任务真相源';
}
function rememberPath(path){
  selectedPath = path || '';
  setDirLabel(selectedPath);
}
async function fileFromHandle(dir, name){
  try{
    const fh = await dir.getFileHandle(name);
    return await (await fh.getFile()).text();
  }catch(e){ return null; }
}
async function readFromHandle(root){
  const direct = await fileFromHandle(root, 'tasks.json');
  let nested = null, sub = null;
  try{
    sub = await root.getDirectoryHandle('.harness');
    nested = await fileFromHandle(sub, 'tasks.json');
  }catch(e){}
  let dir = null, tasks = null;
  if(root.name === '.harness' && direct){ dir = root; tasks = direct; }
  else if(nested){ dir = sub; tasks = nested; }
  else if(direct){ dir = root; tasks = direct; }
  if(!dir || tasks == null) return null;
  dirHandle = dir;
  const texts = {'tasks.json': tasks};
  for(const n of optional){
    const text = await fileFromHandle(dir, n);
    if(text !== null) texts[n] = text;
  }
  return texts;
}
async function pickAndRead(){
  if(typeof window.showDirectoryPicker === 'function'){
    status('正在选择项目任务目录…');
    const handle = await window.showDirectoryPicker({mode:'read'});
    const texts = await readFromHandle(handle);
    if(!texts) throw Error('该目录没有 tasks.json（可选 .harness 或项目根）');
    rememberPath(handle.name);
    return {texts};
  }
  if(isLocalFile()) throw Error(localFileHint());
  const texts = await fetchHarness();
  rememberPath('');
  return {texts: texts, via:'http'};
}
async function rereadSelected(){
  if(dirHandle){
    const texts = await readFromHandle(dirHandle);
    if(!texts) throw Error('已选目录里找不到 tasks.json');
    return texts;
  }
  if(!isLocalFile()) return await fetchHarness();
  throw Error('尚未选择项目任务目录');
}
async function loadProject(){ await guarded(async()=>{
  try{
    const result = await pickAndRead();
    if(result.cancelled){ status('已取消选择目录'); return; }
    if(!result.texts){ showEmpty('该目录尚未编排任务'); return; }
    const label = result.via === 'http' ? '已载入当前项目任务' : ('已载入 ' + (selectedPath || '任务目录'));
    install(result.texts, label);
  }catch(e){
    if(e && e.name === 'AbortError'){ status('已取消选择目录'); return; }
    throw e;
  }
});}
async function refreshProject(){ await guarded(async()=>{
  try{
    const texts = await rereadSelected();
    if(!texts){
      if(model.tasks.tasks.length){ status('刷新失败：未找到 tasks.json，已保留上次任务', true); return; }
      showEmpty('尚未编排任务');
      return;
    }
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
  if(e.key === 'Escape'){ closeEvents(); }
  if(e.target && e.target.matches && e.target.matches('input,select,textarea')) return;
  if(e.ctrlKey || e.metaKey || e.altKey) return;
  if(e.key === 'l' || e.key === 'L'){ e.preventDefault(); loadProject(); }
  if(e.key === 'r' || e.key === 'R'){ e.preventDefault(); refreshProject(); }
  if(e.key === 'j' || e.key === 'J' || e.key === 'ArrowDown'){ e.preventDefault(); selected++; render(); }
  if(e.key === 'k' || e.key === 'K' || e.key === 'ArrowUp'){ e.preventDefault(); selected = Math.max(0, selected - 1); render(); }
  if(e.key === '/'){ e.preventDefault(); $('search').focus(); }
});
render();
setDirLabel('');
try{ document.documentElement.setAttribute('data-boot','ok'); }catch(e){}
if(isLocalFile()){
  status(localFileHint(), !canPickDir());
}else{
  guarded(async()=>{
    const texts = await fetchHarness();
    if(!texts){ showEmpty('尚未编排任务'); return; }
    install(texts, '已载入当前项目任务');
  });
}
