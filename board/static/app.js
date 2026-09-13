'use strict';
try{ document.documentElement.setAttribute('data-boot','pending'); }catch(e){}
const $ = id => document.getElementById(id);
const labels = {pending:'待处理',active:'进行中',evidence_ready:'待独立评审',passed:'已通过',blocked:'已阻塞',regressed:'需回归'};
const colors = {pending:'var(--st-pending)',active:'var(--st-active)',evidence_ready:'var(--st-ready)',passed:'var(--st-passed)',blocked:'var(--st-blocked)',regressed:'var(--st-regressed)'};
const states = Object.keys(labels);
const optional = ['evidence.jsonl','reviews.jsonl','progress.txt','board.json'];
const views = [['all','全部任务'],['blocked','已阻塞'],['evidence_ready','待评审'],['active','进行中'],['passed','已通过'],['eligible','可推进']];
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
let expandedStage = null;
let chain = Promise.resolve(), statusTimer = null;
let errorState = {title:'出错', summary:'', detail:''};
const timers = {
  set(fn, ms){ if(typeof setTimeout === 'function'){ timers.id = setTimeout(fn, ms); } },
  clear(){ if(typeof clearTimeout === 'function' && timers.id != null){ clearTimeout(timers.id); } timers.id = null; }
};
const esc = value => String(typeof value === 'object' ? JSON.stringify(value) : value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const setText = (id,text) => { const el = $(id); if(el) el.textContent = text; };
function status(text, error=false){ timers.clear(); setText('status',text); const el = $('status'); if(el && el.classList && el.classList.toggle){ el.classList.toggle('err',error); el.classList.toggle('has-detail', !!(error && errorState.detail)); } if(el && el.setAttribute) el.setAttribute('title', (error && errorState.detail) ? '查看完整错误' : ''); }
function flash(text){ const el = $('status'); const prev = el ? el.textContent : ''; status(text); timers.set(()=>status(prev), 1600); }
function isLocalFile(){ return location.protocol === 'file:'; }
function localFileHint(){ return '请用 board/start.ps1 启动 HTTP 看板，不要打开 file://。'; }
function parse(texts){
  if(texts && texts.__snapshot){
    const snap = texts.__snapshot;
    const meta = snap.meta && typeof snap.meta === 'object' ? snap.meta : {};
    let taskRows = [];
    if(Array.isArray(snap.tasks)) taskRows = snap.tasks;
    else if(snap.tasks && typeof snap.tasks === 'object' && Array.isArray(snap.tasks.tasks)) taskRows = snap.tasks.tasks;
    else if(snap.tasks && typeof snap.tasks === 'object') taskRows = Object.values(snap.tasks);
    else throw Error('数据库快照必须包含任务数组');
    const tasks = {project: meta.project || snap.project || (snap.tasks && snap.tasks.project) || '', tasks: taskRows};
    if(meta.rev !== undefined) tasks.rev = meta.rev;
    else if(snap.rev !== undefined) tasks.rev = snap.rev;
    else if(snap.tasks && snap.tasks.rev !== undefined) tasks.rev = snap.tasks.rev;
    const ids = new Set();
    for(const t of tasks.tasks){
      if(!t || typeof t.id !== 'string' || !t.id.trim() || ids.has(t.id)) throw Error('任务编号缺失或重复');
      if(!Object.hasOwn(labels,t.status)) throw Error('任务包含未知状态');
      ids.add(t.id);
    }
    return {tasks, evidence:Array.isArray(snap.evidence)?snap.evidence:[], reviews:Array.isArray(snap.reviews)?snap.reviews:[], progress:typeof snap.progress==='string'?snap.progress:'', board:snap.board && typeof snap.board==='object'?snap.board:null};
  }
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
function waveOf(t){ return t.wave || (t.phase != null ? '阶段 ' + t.phase : '未分组'); }
function setTab(tab){
  const tabs = ['list','trajectory','log'];
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
function auditEvents(task){
  if(!task) return [];
  const rows = [
    ...model.evidence.filter(x=>!isMetaRow(x) && x.task === task.id).map(x=>({...x,kind:'e',source:'evidence.jsonl'})),
    ...model.reviews.filter(x=>!isMetaRow(x) && x.task === task.id).map(x=>({...x,kind:'r',source:'reviews.jsonl'}))
  ];
  return rows.sort((a,b)=>{
    const ta = Date.parse(a.ts), tb = Date.parse(b.ts);
    if(Number.isFinite(ta) && Number.isFinite(tb)) return ta-tb;
    if(Number.isFinite(ta)) return -1;
    if(Number.isFinite(tb)) return 1;
    return 0; // Undated records stay in file order; do not invent their chronology.
  });
}
function auditSummary(task){
  const all = auditEvents(task);
  const evs = all.filter(x=>x.kind==='e'), rvs = all.filter(x=>x.kind==='r');
  const ev = evs.at(-1), rv = rvs.at(-1);
  let evidence = !ev ? '尚未提交验证' : ev.exit === 0 ? '最新验证通过' : ev.exit == null ? '验证结果未记录' : '最新验证未通过';
  let review = !rv ? '尚未评审' : rv.verdict === 'pass' ? '评审记录通过' : rv.verdict === 'fail' ? '评审未通过' : '评审结论未明确';
  if(rv && !evs.some(e=>e.id && e.id === rv.ev)) review = '关联证据缺失';
  else if(rv?.verdict === 'pass' && !rv.reviewer_context) review = '缺少独立评审上下文';
  else if(rv?.verdict === 'pass' && ev && rv.ev !== ev.id) review = '最新证据尚待评审';
  const uncertain = all.some(x=>!Number.isFinite(Date.parse(x.ts)));
  if(uncertain){ evidence = evidence.replace('最新','末条'); review = review.replace('最新','末条'); }
  return {evs,rvs,evidence,review,uncertain};
}
function progressMarkup(t){
  const step = stateSteps.indexOf(t.status);
  return '<div class="card-progress" aria-label="状态进度：' + esc(labels[t.status]) + '，不是工时百分比">'
    + stateSteps.map((st,i)=>'<span class="'+(i<=step?'reached':'')+'"><i></i>'+esc(labels[st])+'</span>').join('')
    + '</div>';
}
function renderCards(rows, byId){
  const tasksEl = $('tasks'); if(!tasksEl) return;
  const groups = new Map();
  rows.forEach((t,i)=>{ const key=waveOf(t); if(!groups.has(key)) groups.set(key,[]); groups.get(key).push({t,i}); });
  tasksEl.innerHTML = [...groups].map(([name,items],groupIndex)=>{
    const open = expandedStage === name;
    const passed = items.filter(({t})=>t.status==='passed').length;
    return '<section class="stage-group"><header class="stage-head"><h3><button type="button" class="stage-toggle" id="stage-toggle-'+groupIndex+'" data-stage-toggle="'+esc(name)+'" aria-expanded="'+open+'" aria-controls="stage-cards-'+groupIndex+'"><span class="stage-arrow" aria-hidden="true">›</span>'+esc(name)+'</button></h3>'
      + '<span>'+items.length+' 项 · '+passed+' 项状态已通过</span><div class="stage-progress" role="meter" aria-label="本组状态已通过比例" aria-valuemin="0" aria-valuemax="'+items.length+'" aria-valuenow="'+passed+'"><i style="width:'+(100*passed/items.length)+'%"></i></div></header>'
      + (name==='未分组'?'<p class="group-note">任务源未填写 wave / phase，保留在未分组；不根据编号或状态猜测阶段。</p>':'')
      + '<div class="stage-cards" id="stage-cards-'+groupIndex+'"'+(open?'':' hidden')+'>'+items.map(({t,i})=>{
        const title=t.desc||t.description||'未填写';
        const g=gate(t), a=auditSummary(t), deps=t.depends_on||[];
        return '<article class="tcard is-'+esc(t.status)+'" data-status="'+esc(t.status)+'" data-i="'+i+'" aria-selected="'+(i===selected)+'">'
          + '<div class="row"><span class="id">'+esc(t.id)+'</span><span class="pri">P'+esc(t.priority??'—')+'</span></div>'
          + '<div class="state"><i class="dot" style="background:'+colors[t.status]+'"></i>'+labels[t.status]+'</div>'
          + '<p class="desc" title="'+esc(title)+'">'+esc(title)+'</p>'
          + '<div class="meta">依赖 '+esc(deps.length?deps.map(d=>d+' / '+(byId.has(d)?labels[byId.get(d).status]:'缺失')).join('、'):'无')+'</div>'
          + (t.reason?'<p class="card-warning">'+esc(asText(t.reason))+'</p>':'')
          + '<footer class="card-bottom">'+progressMarkup(t)
          + '<p class="audit-brief">'+esc(a.evidence)+' · '+esc(a.review)+'</p>'
          + (g.startsWith('门禁')?'<p class="card-warning">状态已通过，但证据 / 评审关联不完整</p>':'')
          + '<div class="card-actions"><button type="button" class="btn" data-action="events" data-i="'+i+'" aria-label="查看 '+esc(t.id)+' 的证据与评审">证据 '+a.evs.length+' · 评审 '+a.rvs.length+' ↗</button>'
          + '<button type="button" class="trace-link" data-action="trajectory" data-i="'+i+'">任务轨迹 →</button></div></footer></article>';
      }).join('')+'</div></section>';
  }).join('') || '<div class="empty">暂无匹配任务。按 L 选择项目任务目录，按 R 刷新。</div>';
}
function renderTrajectory(current){
  const box=$('trajectory'); if(!box) return;
  if(!current){ box.innerHTML='<p class="empty-note">当前没有选中任务，请先在任务列表中点击一张任务卡。</p>'; return; }
  const entries=auditEvents(current);
  box.innerHTML = '<div class="trajectory-current"><span>跟随当前行 · 当前快照，不是历史事件</span><h3>'+esc(current.id)+'</h3><p>'+esc(labels[current.status])+' · '+esc(current.desc||current.description||'未填写')+'</p>'
    + '<p class="muted">来源 harness.db · 修订号 '+esc(model.tasks.rev??'未记录')+'。状态变迁未单独记录，不能从当前状态补造创建、开始或完成时间。</p></div>'
    + (entries.length?'<ol class="audit-timeline">'+entries.map(x=>'<li><div class="trace-time">'+esc(x.ts||'时间未记录')+(!x.ts?'':' · '+(Number.isFinite(Date.parse(x.ts))?'':'时间格式无效，顺序未知'))+'</div>'
      + (x.kind==='e'?renderEvidenceCard(x):renderReviewCard(x))+'</li>').join('')+'</ol>'
      : '<p class="empty-note">当前任务暂无可追溯记录；不会根据当前状态补造历史事件。</p>');
}
function progressRows(raw){
  const lines=String(raw||'').split(/\r?\n/);
  return lines.map((line,i)=>{
    const ts=(line.match(/\b20\d{2}-\d{2}-\d{2}(?:T|\s)[^ ]+/)||[])[0]||'';
    const kind=/HARNESS_STATUS|EXIT_SIGNAL/i.test(line)?'门禁':/error|fail|blocked|阻塞|失败/i.test(line)?'异常':/pass|passed|完成|通过/i.test(line)?'通过':/start|active|进行|开始/i.test(line)?'进行中':'记录';
    return {line,ts,kind,no:i+1};
  }).filter(x=>x.line.trim());
}
function renderProgressLog(){
  const box=$('progress-log'); if(!box) return;
  const rows=progressRows(model.progress);
  const recent=rows.slice(-8).reverse();
  const exit=[...model.progress.matchAll(/EXIT_SIGNAL\s*[:=]\s*(true|false)/gi)].at(-1)?.[1];
  const summary=exit ? (exit.toLowerCase()==='true'?'已发出退出信号':'尚未发出退出信号') : '日志中未发现退出信号';
  box.innerHTML='<div class="log-summary"><div><b>日志概览</b><span>'+rows.length+' 条记录</span></div><strong class="log-signal '+(exit==='true'?'ok':exit==='false'?'warn':'muted')+'">'+esc(summary)+'</strong><small>以下按原始日志行展示；标签只是辅助识别，不改变日志含义。</small></div>'
    + (recent.length?'<ol class="progress-list">'+recent.map(x=>'<li class="log-'+x.kind+'"><span class="log-kind">'+x.kind+'</span><span class="log-line">'+esc(x.line)+'</span><span class="log-no">第 '+x.no+' 行</span></li>').join('')+'</ol>':'<p class="empty-note">暂无进度日志。</p>')
    + '<details class="raw-log"><summary>展开全部原始日志（'+rows.length+' 条）</summary><pre>'+esc(model.progress||'暂无进度日志')+'</pre></details>';
}
function render(){
  try{ renderAll(); }
  catch(e){ reportError(e, '界面刷新失败'); }
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
  setText('c-passed', String(counts.passed));
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
  const groups = groupedRows(rows);
  if(expandedStage !== null && !groups.has(expandedStage)) expandedStage = null;
  rows = [...groups.values()].flat();
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
  renderProgressLog();
  renderMap();
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
function sourceLabel(x, filename){
  return filename + (x._sourceLine ? ':'+x._sourceLine : '') + (x.id ? ' · '+asText(x.id) : '');
}
function renderEvidenceCard(x){
  const ok = x.exit === 0, cls = ok?'ok':x.exit==null?'miss':'bad';
  return '<article class="event is-e"><header><b>验证记录</b><span class="badge '+cls+'">'+(ok?'验证通过':x.exit==null?'结果未记录':'验证未通过')+'</span></header>'
    + '<p class="event-summary">'+esc(asText(x.summary)||(ok?'命令成功退出；这不等于任务已完成。':'请展开检查验证结果。'))+'</p>'
    + '<p class="event-source">'+esc(sourceLabel(x,'evidence.jsonl'))+'</p>'
    + '<details class="event-details"><summary>查看命令与技术详情</summary>'
    + kv('任务',x.task)+kv('命令',x.cmd)+kv('退出码',x.exit)+kv('测试摘要',x.tests||x.summary)+kv('修订标识',x.rev)
    + kv('编码',encodingOf(x))+kv('产物',x.artifacts)+kv('环境',x.environment)+kv('时间',x.ts)
    + extrasOf(x,new Set(['id','task','cmd','exit','tests','summary','rev','encoding','artifacts','environment','ts','kind','source']))+'</details></article>';
}
function renderReviewCard(x){
  const ev = model.evidence.find(e=>!isMetaRow(e)&&e.task===x.task&&e.id&&e.id===x.ev);
  const link = !ev?'关联证据缺失':ev.exit!==0?'关联验证未通过':!x.reviewer_context?'缺少独立评审上下文':'已关联证据；评审独立性须人工核验';
  const verdict = x.verdict==='pass'?'评审通过':x.verdict==='fail'?'评审未通过':'结论未明确';
  return '<article class="event is-r"><header><b>评审记录</b><span class="badge '+(x.verdict==='pass'?'ok':x.verdict==='fail'?'bad':'miss')+'">'+verdict+'</span></header>'
    + '<p class="event-summary">'+esc(asText(x.reason||x.note)||'未填写评审理由')+'</p><p class="review-link">'+esc(link)+'</p>'
    + '<p class="event-source">'+esc(sourceLabel(x,'reviews.jsonl'))+' → '+esc(x.ev||'未填写证据编号')+'</p>'
    + '<details class="event-details"><summary>查看评审人、关联与原始字段</summary>'
    + kv('任务',x.task)+kv('评审上下文',x.reviewer_context)+kv('对应证据',x.ev)+kv('时间',x.ts)
    + extrasOf(x,new Set(['id','task','ev','reviewer_context','verdict','reason','note','ts','kind','source']))+'</details></article>';
}
function renderEvents(current){
  const eventsEl = $('events');
  if(!eventsEl) return;
  const currentId = current && current.id;
  const summary = $('events-summary');
  if(summary){
    const a=current?auditSummary(current):null;
    summary.innerHTML=a?'<b>'+esc(a.evidence)+'</b><span>'+esc(a.review)+'</span><small>'+esc(a.uncertain?'部分记录没有有效时间，末条按文件顺序展示。':'按记录时间展示；评审通过也不自动修改任务状态。')+'</small>':'';
  }
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
function errorDialog(){ return $('error-dialog'); }
function firstLine(text){
  const s = String(text || '').replace(/\s+/g,' ').trim();
  return s.length > 72 ? s.slice(0,72) + '…' : s;
}
function isLongError(text){
  const s = String(text || '');
  return /[\n\r]/.test(s) || s.length > 80;
}
function openErrorDialog(title, detail, summary){
  errorState = {title: title || '出错', detail: String(detail || ''), summary: summary || ''};
  const dlg = errorDialog();
  if(dlg) dlg.hidden = false;
  setText('error-title', errorState.title);
  setText('error-sub', errorState.summary);
  const box = $('contract-error');
  if(box){ box.hidden = false; box.textContent = errorState.detail; }
  const close = $('error-close');
  if(close && close.focus) close.focus();
}
function closeErrorDialog(){
  const dlg = errorDialog();
  if(dlg) dlg.hidden = true;
}
function clearErrorDialog(){
  closeErrorDialog();
  errorState = {title:'出错', summary:'', detail:''};
  const box = $('contract-error');
  if(box){ box.hidden = true; box.textContent = ''; }
  setText('error-title', '出错');
  setText('error-sub', '');
}
function reopenErrorDialog(){
  if(!errorState.detail) return false;
  openErrorDialog(errorState.title, errorState.detail, errorState.summary);
  return true;
}
function reportError(e, prefix){
  if(e && e.shown) return;
  const raw = (e && e.message) || e || '未知错误';
  const text = String(raw);
  const head = prefix || '出错';
  if(isLongError(text)){
    openErrorDialog(head, text, '完整内容在弹窗中，关闭后可点底栏再看');
    status(head + '：' + firstLine(text) + '，点此查看', true);
    return;
  }
  status(head + '：' + text, true);
}
function showContractErrors(errors){
  const list = Array.isArray(errors) ? errors.map(String) : [String(errors || '')];
  const title = '中文契约失败';
  const detail = title + '，请修复 harness.db 中的中文原字段：\n' + list.join('\n');
  showEmpty(title);
  openErrorDialog(title, detail, '共 ' + list.length + ' 条，关闭后可点底栏再看');
  status(title + '，共 ' + list.length + ' 条，点此查看', true);
  const err = Error(detail);
  err.shown = true;
  throw err;
}
function showEmpty(message){
  lastStamp = '';
  visibleRows = []; wantedId = null; expandedStage = null;
  model = {tasks:{tasks:[]},evidence:[],reviews:[],progress:''};
  selected = 0;
  render();
  status(message);
}
function guarded(fn){
  const run = chain.then(async()=>{
    const r = $('refresh'), l = $('load');
    try{ await fn(); }
    catch(e){ reportError(e, '读取失败'); }
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
let sessionRequestId = 0;
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
      : '<span class="badge miss">无 harness.db</span>';
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
      return guarded(()=>applySource(row.source || row.cwd, row.has_harness ? '已根据会话载入' : '已绑定目录（尚未编排任务）'));
    });
  });
}
async function refreshSessions(){
  const requestId = ++sessionRequestId;
  const box = $('load-list');
  const note = $('load-session-status');
  sessionCatalog = {projects:[], suggested:null, sessions_dir:''};
  if(box){ box.innerHTML = ''; box.setAttribute('aria-busy','true'); }
  if(note){ note.textContent = '正在读取本机 Codex 会话…'; note.classList.remove('err'); }
  try{
    if(isLocalFile()) throw Error(localFileHint());
    const data = await api('/api/sessions');
    if(!data || !Array.isArray(data.projects) || typeof data.sessions_dir !== 'string'){
      throw Error('会话接口返回格式不正确，请使用配套的独立看板服务，不要混用旧页面或旧服务');
    }
    if(requestId !== sessionRequestId) return null;
    sessionCatalog = data;
    renderLoadList();
    if(note) note.textContent = '已读取 ' + data.projects.length + ' 个工作目录 · 会话根目录：' + data.sessions_dir;
    return data;
  }catch(e){
    if(requestId === sessionRequestId){
      if(note){ note.textContent = '读取会话失败：' + (e.message || e) + '。可点击“刷新会话”重试，或手动指定目录。'; note.classList.add('err'); }
      if(box) box.innerHTML = '';
    }
    throw e;
  }finally{
    if(requestId === sessionRequestId && box) box.setAttribute('aria-busy','false');
  }
}
function snapshotFiles(data){
  if(data?.contract?.errors?.length) showContractErrors(data.contract.errors);
  if(!data?.snapshot){
    clearErrorDialog();
    return null;
  }
  if(!data.contract || !Array.isArray(data.contract.errors)) throw Error('缺少中文契约检查结果，请使用配套服务启动看板');
  clearErrorDialog();
  return {__snapshot:data.snapshot};
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
  selected = 0; visibleRows = []; expandedStage = null;
  snapshotFiles(data);
  if(data.snapshot){
    const payload = {__snapshot:data.snapshot};
    lastStamp = stampOf(payload);
    install(payload, (label || '已载入') + ' ' + (data.source || target));
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
async function loadProject(){
  // 面板和会话扫描不能排在慢轮询/目录对话框之后；关闭操作始终独立。
  openLoad();
  status('正在读取 Codex 会话…');
  try{
    const catalog = await refreshSessions();
    if(catalog && !loadDrawer()?.hidden) status('选择一条 Codex 会话，或手动指定 harness 目录');
  }catch(e){ status('读取会话失败：' + (e.message || e), true); }
}
async function pullLive(){
  if(isLocalFile()) throw Error(localFileHint());
  const data = await api('/api/snapshot');
  if(data.last_source) noteLastSource(data.last_source);
  if(data.source) rememberPath(data.source);
  const payload = snapshotFiles(data);
  return {payload, data};
}

function stampOf(texts){
  if(texts && texts.__snapshot){
    const s=texts.__snapshot;
    if(s.revision && typeof s.revision === 'object') return JSON.stringify(s.revision);
    return JSON.stringify([s.version,s.updated_at,s.task_count,s.evidence_count,s.review_count,s.progress_count]);
  }
  return ['tasks.json','evidence.jsonl','reviews.jsonl','progress.txt','board.json']
    .map(n => (texts && texts[n]) ? texts[n] : '').join('\u0001');
}
let lastStamp = '';
const POLL_MS = 2000;
let pollTimer = 0;
function startPoll(){
  if(isLocalFile()) return;
  const tick = () => guarded(async()=>{
    const live = await pullLive();
    const texts = live && live.payload;
    if(!texts || !texts.__snapshot) return;
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
    const bootPayload = snapshotFiles(snap);
    if(bootPayload){
      lastStamp = stampOf(bootPayload);
      install(bootPayload, '已载入 ' + (snap.source || '任务目录'));
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
    reportError(e, '读取会话失败');
    if(!(e && e.shown)) openLoad(true);
  }
}
async function refreshProject(){ await guarded(async()=>{
  try{
    const live = await pullLive();
    const texts = live && live.payload;
    if(!texts){
      if(model.tasks.tasks.length){ status('刷新失败：未找到 harness.db，已保留上次任务', true); return; }
      showEmpty('尚未编排任务');
      openLoad();
      return;
    }
    lastStamp = stampOf(texts);
    install(texts, '已刷新 ' + (selectedPath || '任务目录'));
  }catch(e){ if(!(e && e.shown)) reportError(e, '刷新失败'); }
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
if($('copy')) $('copy').onclick = copyCmd;
if($('load-close')) $('load-close').onclick = closeLoad;
if($('load-browse')) $('load-browse').onclick = () => guarded(browseDir);
if($('load-path-go')) $('load-path-go').onclick = () => guarded(loadFromPath);
if($('load-refresh-sess')) $('load-refresh-sess').onclick = loadProject;
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
const errEl = errorDialog();
if(errEl) errEl.addEventListener('click', e=>{
  const t = e.target;
  if(t && t.getAttribute && t.getAttribute('data-close-error')) closeErrorDialog();
});
if($('error-close')) $('error-close').addEventListener('click', closeErrorDialog);
if($('status')) $('status').addEventListener('click', ()=>{ if($('status')?.classList?.contains?.('has-detail') || errorState.detail) reopenErrorDialog(); });
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
  const stage = e.target?.closest ? e.target.closest('[data-stage-toggle]') : null;
  if(stage){
    const name = stage.dataset.stageToggle;
    if(!visibleRows.some(t=>waveOf(t) === name)) return;
    expandedStage = expandedStage === name ? null : name;
    render();
    const index = [...groupedRows(visibleRows).keys()].indexOf(name);
    $('stage-toggle-' + index)?.focus();
    return;
  }
  const item = e.target && e.target.closest ? e.target.closest('[data-i]') : null;
  if(!item) return;
  selected = Number(item.dataset.i);
  const action = e.target.closest('[data-action]');
  if(action) eventFilter = 'both';
  render();
  if(action?.dataset.action === 'events') openEvents();
  if(action?.dataset.action === 'trajectory') setTab('trajectory');
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
function moveCurrent(delta){
  if(!visibleRows.length) return;
  selected = Math.max(0, Math.min(visibleRows.length - 1, selected + delta));
  expandedStage = waveOf(visibleRows[selected]);
  render();
}
document.addEventListener('keydown', e=>{
  if(e.key === 'Escape'){ if(errorDialog() && !errorDialog().hidden){ closeErrorDialog(); return; } closeEvents(); closeLoad(); return; }
  if(e.key === 'Tab'){
    const drawer = (errorDialog() && !errorDialog().hidden) ? errorDialog() : !$('load-drawer')?.hidden ? $('load-drawer') : !$('events-drawer')?.hidden ? $('events-drawer') : null;
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
  if(e.key === 'j' || e.key === 'J' || e.key === 'ArrowDown'){ e.preventDefault(); moveCurrent(1); }
  if(e.key === 'k' || e.key === 'K' || e.key === 'ArrowUp'){ e.preventDefault(); moveCurrent(-1); }
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
