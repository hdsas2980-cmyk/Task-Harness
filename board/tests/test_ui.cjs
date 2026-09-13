const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const staticRoot = process.env.TASK_BOARD_TEST_STATIC || path.join(__dirname,'../static');
const templatePath = path.join(staticRoot,'index.html');
const jsTemplatePath = path.join(staticRoot,'app.js');
const html = fs.readFileSync(templatePath,'utf8');
const code = fs.readFileSync(jsTemplatePath,'utf8');
const htmlIds = new Set(Array.from(html.matchAll(/\bid="([^"]+)"/g), match=>match[1]));
assert.match(html, /载入任务/);
assert.match(html, /class="build-id">看板 UI 2026\.09\.12-r2/);
assert.match(html, /刷新任务/);
assert.match(html, /\.\/app\.js/);
assert.match(html, /load-drawer/);
assert.match(html, /data-filter="all"[\s\S]*data-filter="blocked"/);
assert.match(html, /id="tab-btn-list"[\s\S]*id="tab-btn-trajectory"/);
assert.match(code, /mainTab = 'list'/);
assert.match(code, /data-status=/);
assert.match(code, /renderEvidenceCard/);
assert.match(html, /event-filters/);
assert.match(html, /从 Codex 会话中选择/);
assert.match(code, /api\/sessions/);
assert.match(code, /api\/source/);
assert.match(code, /bootstrapSource/);
assert.doesNotMatch(code, /showDirectoryPicker|isTauri|__TAURI__|probe_harness_dir/);
assert.match(code, /startPoll/);
assert.doesNotMatch(html, /载入示例|清空|type="file"|__HARNESS_SNAPSHOT__|id="snapshot"/);
assert.match(html, /id="error-dialog"/);
assert.doesNotMatch(html, /<main class="main">\s*<pre id="contract-error"/);
assert.match(html, /id="error-dialog"[\s\S]*id="contract-error"/);

function node(id, nodes){
  if(!nodes.has(id)) nodes.set(id,{textContent:'',innerHTML:'',value:'',checked:false,disabled:false,hidden:true,classList:{toggle(){},add(){},remove(){}},listeners:{},attributes:{},dataset:{},addEventListener(type,fn){(this.listeners[type] ||= []).push(fn);},setAttribute(key,value){this.attributes[key]=String(value);},getAttribute(key){return this.attributes[key] ?? null;},insertAdjacentHTML(_,text){this.innerHTML+=text;},click(){this.clicked=true;},focus(){},matches(){return false;},closest(){return null;},querySelectorAll(){return [];}});
  return nodes.get(id);
}

function run(extras){
  const nodes = new Map();
  const n = id => node(id, nodes);
  n('search').value='';
  n('load-path').value='';
  n('load-q').value='';
  n('load-harness-only').checked=false;
  n('load-drawer').hidden=true;
  n('load-list').querySelectorAll = selector => {
    if(selector !== '.load-row') return [];
    return Array.from(n('load-list').innerHTML.matchAll(/class="load-row[^"\n]*" data-i="(\d+)"/g), match => {
      const button = n('session-row-' + match[1]);
      button.listeners = {}; button.dataset.i = match[1];
      return button;
    });
  };
  const eventButtons = Array.from(html.matchAll(/<button\b[^>]*data-evf="([^"]+)"[^>]*>/g), match => {
    const button = n('event-filter-' + match[1]);
    button.dataset.evf = match[1];
    return button;
  });
  const listeners = {};
  const store = Object.assign({}, extras.store || {});
  const fetches = [];
  const scope = {
    document:{getElementById:id=>htmlIds.has(id) ? n(id) : null,querySelector(){return {addEventListener(){}};},querySelectorAll(selector){return selector === '#event-filters [data-evf]' ? eventButtons : [];},hidden:false,addEventListener(type,fn){listeners[type]=fn;}},
    window: extras.window || {},
    location: extras.location || {protocol:'file:',href:'file:///proj/.harness/task-harness.html',reload(){scope.reloads++;}},
    URL, console, Set, Map, JSON, Error, Promise, Object,
    setInterval(){},
    setTimeout(fn){ fn(); return 1; },
    clearTimeout(){},
    localStorage:{
      getItem(k){ return Object.prototype.hasOwnProperty.call(store,k) ? store[k] : null; },
      setItem(k,v){ store[k] = String(v); },
      removeItem(k){ delete store[k]; }
    },
    fetch: extras.fetch || (async (url, opts)=>{ fetches.push({url:String(url), opts}); throw Error('file protocol blocked'); }),
    reloads:0,
    fetches,
    calls:[]
  };
  if(extras.window) scope.window = extras.window;
  if(extras.fetch) scope.fetch = extras.fetch;
  vm.createContext(scope);
  vm.runInContext(code, scope);
  function fire(id, type, event = {}) {
    const handlers = n(id).listeners[type] || [];
    assert.ok(handlers.length, id + ' must bind ' + type);
    return Promise.all(handlers.map(fn => fn({target:n(id), ...event})));
  }
  function key(value) {
    assert.equal(typeof listeners.keydown, 'function');
    listeners.keydown({key:value, target:{matches(){return false;}}, preventDefault(){}});
  }
  function pick(index, target = 'tasks') {
    fire(target, 'click', {target:{closest(selector){return selector === '[data-i]' ? {dataset:{i:String(index)}} : null;}}});
  }
  function eventKind(value) {
    const button = eventButtons.find(b => b.dataset.evf === value);
    assert.ok(button, 'missing event filter ' + value);
    fire('event-filters', 'click', {target:{closest(selector){return selector === '[data-evf]' ? button : null;}}});
    assert.equal(button.getAttribute('aria-current'), 'true');
    for (const other of eventButtons.filter(b => b !== button)) assert.equal(other.getAttribute('aria-current'), 'false');
  }
  function cardAction(index, action) {
    const card = n('tasks').innerHTML.match(/<article class="tcard[\s\S]*?<\/article>/g)?.[index];
    assert.ok(card && card.includes('data-action="' + action + '"'), '必须点击历史卡片上实际存在的操作');
    fire('tasks', 'click', {target:{closest(selector){
      if(selector === '[data-i]') return {dataset:{i:String(index)}};
      if(selector === '[data-action]') return {dataset:{action,i:String(index)}};
      return null;
    }}});
  }
  function openAudit(index = 0) { cardAction(index, 'events'); }
  function openTrace(index = 0) { cardAction(index, 'trajectory'); }

  return {scope, node:n, store, nodes, fetches, fire, key, pick, eventKind, openAudit, openTrace};
}

module.exports = {run};

function boardSnap(tasks, extra){
  extra = extra || {};
  const meta = Object.assign({project: extra.project || ''}, extra.meta || {});
  return {
    schema_version: 1,
    storage: {type: 'sqlite', path: extra.path || 'harness.db'},
    meta,
    project: meta.project,
    tasks,
    evidence: extra.evidence || [],
    reviews: extra.reviews || [],
    progress: extra.progress || '',
    board: extra.board || {},
    counts: {tasks: tasks.length, evidence: (extra.evidence||[]).length, reviews: (extra.reviews||[]).length},
    revision: {schema_version: 1, counts: {tasks: tasks.length}}
  };
}
if(require.main === module) (async()=>{
  const file = run({});
  assert.match(file.node('status').textContent,/start\.ps1|file:\/\//);
  assert.doesNotMatch(file.node('tasks').innerHTML,/<img/);
  assert.equal(vm.runInContext('model.tasks.tasks.length',file.scope),0);
  const before=vm.runInContext('JSON.stringify(model)',file.scope);
  assert.throws(()=>vm.runInContext('install({"tasks.json":"{bad}"},"错误")',file.scope));
  assert.equal(vm.runInContext('JSON.stringify(model)',file.scope),before);
  assert.throws(()=>vm.runInContext('parse({"tasks.json":JSON.stringify({tasks:[{id:"x",status:"bad"}]})})',file.scope));
  assert.throws(()=>vm.runInContext('parse({"tasks.json":JSON.stringify({tasks:[]}),"reviews.jsonl":"[]"})',file.scope));
  await file.node('load').onclick();
  assert.equal(file.fetches.length,0);
  assert.match(file.node('status').textContent,/start\.ps1|file:\/\//);

  const httpFetches = [];
  const httpFetch = async (url, opts)=>{
    httpFetches.push({url:String(url), method:(opts && opts.method) || 'GET', body:opts && opts.body});
    const u = String(url);
    if(u.includes('/api/snapshot')){
      return {ok:true, status:200, text:async()=>JSON.stringify({source:null, files:{}})};
    }
    if(u.includes('/api/sessions')){
      return {ok:true, status:200, text:async()=>JSON.stringify({
        sessions_dir:'C:/users/me/.codex/sessions',
        suggested:null,
        projects:[{cwd:'E:/proj', source:'E:/proj/.harness', has_harness:true, task_count:1, latest_title:'演示', session_count:1, latest:'2026-09-11T12:00:00Z', sessions:[]}]
      })};
    }
    if(u.includes('/api/source')){
      return {ok:true, status:200, text:async()=>JSON.stringify({source:'E:/proj/.harness', contract:{errors:[]}, files:{}, snapshot:boardSnap([{id:'picked-1',status:'blocked',priority:1,desc:'from session'}], {project:'演示'})})};
    }
    return {ok:false, status:404, text:async()=>'{}'};
  };
  const http = run({
    location:{protocol:'http:',href:'http://127.0.0.1:8765/',reload(){}},
    fetch: httpFetch
  });
  await new Promise(r=>setTimeout(r, 20));
  await http.node('load').onclick();
  assert.ok(httpFetches.some(x=>x.url.includes('/api/sessions')));
  assert.equal(http.node('load-drawer').hidden, false);
  await vm.runInContext('applySource("E:/proj/.harness","已根据会话载入")', http.scope);
  assert.match(http.node('tasks').innerHTML,/picked-1/);
  assert.match(http.node('status').textContent,/已根据会话载入|已载入/);
  assert.match(http.node('project').textContent,/proj/);
  vm.runInContext(
    'install({"tasks.json":JSON.stringify({project:"demo",tasks:[{id:"t-01",status:"evidence_ready",priority:1,desc:"任务中文标题",verify:"private-verify-command",depends_on:["upstream-task"],reason:"private-blocking-reason"}]}),'
    + '"evidence.jsonl":JSON.stringify({id:"ev-01",task:"t-01",cmd:"go test ./...",exit:0,tests:"12 passed",rev:"abc123",encoding:"utf-8",ts:"2026-09-11T12:00:00Z"}),'
    + '"reviews.jsonl":JSON.stringify({id:"rv-01",task:"t-01",ev:"ev-01",reviewer_context:"codex-independent-task",verdict:"pass",reason:"范围与验证通过",ts:"2026-09-11T12:05:00Z"})}, "证据")',
    http.scope
  );
  assert.match(http.node('events').innerHTML, /go test/);
  assert.match(http.node('events').innerHTML, /12 passed/);
  assert.match(http.node('events').innerHTML, /abc123/);
  assert.match(http.node('events').innerHTML, /utf-8/);
  assert.match(http.node('events').innerHTML, /范围与验证通过/);
  assert.match(http.node('events').innerHTML, /codex-independent-task/);
  // Restore the screenshot's task details, but never duplicate the audit feed in the rail.
  const detail = http.node('detail').innerHTML;
  for (const text of ['t-01', '任务中文标题', '待独立评审', '优先级 1', '依赖', 'upstream-task', 'private-verify-command', 'private-blocking-reason', '无门禁缺口']) {
    assert.ok(detail.includes(text), 'current row is missing ' + text);
  }
  assert.doesNotMatch(detail, /go test|退出码|codex-independent-task|范围与验证通过/);
  assert.equal(http.node('detail-events').innerHTML, '');
  assert.doesNotMatch(html, /detail-events|current-name|current-status/);
  assert.doesNotMatch(code, /detail-events/);

  const stateNames = {pending:'待处理', active:'进行中', evidence_ready:'待独立评审', passed:'已通过', blocked:'已阻塞', regressed:'需回归'};
  for (const [state, label] of Object.entries(stateNames)) {
    vm.runInContext(`model.tasks.tasks[0].status = ${JSON.stringify(state)}; render()`, http.scope);
    assert.ok(http.node('detail').innerHTML.includes(label));
  }
  vm.runInContext('model.tasks.tasks.push({id:"fallback-id",status:"pending"}); selected = 1; render()', http.scope);
  assert.match(http.node('detail').innerHTML, /fallback-id/);
  vm.runInContext(`model.tasks.tasks[1].desc = '<img src=x onerror="alert(1)">'; render()`, http.scope);
  assert.doesNotMatch(http.node('detail').innerHTML, /<img/);
  assert.match(http.node('detail').innerHTML, /&lt;img/);
  http.node('search').value = 'no-such-task';
  http.fire('search', 'input');
  assert.match(http.node('detail').innerHTML, /没有选中任务/);
  assert.doesNotMatch(http.node('detail').innerHTML, /fallback-id|任务中文标题/);
  assert.match(http.node('events').innerHTML, /请先.*选择任务/);
  assert.doesNotMatch(http.node('events').innerHTML, /go test|退出码|范围与验证通过/);

  // Exercise real registered UI callbacks; direct eventFilter assignments would miss missing bindings.
  const linked = run({});
  const texts = {
    'tasks.json':JSON.stringify({project:'current task only', tasks:[
      {id:'task-A', status:'active', priority:1, desc:'任务甲'},
      {id:'task-B', status:'blocked', priority:2, desc:'任务乙'},
      {id:'task-C', status:'pending', priority:3, desc:'无记录任务'}
    ]}),
    'evidence.jsonl':[
      {id:'evidence-A', task:'task-A', cmd:'verify-A-only', exit:0, ts:'2026-09-11T10:00:00Z'},
      {id:'evidence-B', task:'task-B', cmd:'verify-B-only', exit:1, ts:'2026-09-11T10:01:00Z'},
      {id:'orphan-evidence', cmd:'orphan-must-not-leak', exit:0},
      {_comment:'comment-must-not-leak', task:'task-A'}
    ].map(JSON.stringify).join('\n'),
    'reviews.jsonl':[
      {id:'review-A', task:'task-A', ev:'evidence-A', verdict:'pass', reason:'review-A-only'},
      {id:'review-B', task:'task-B', ev:'evidence-B', verdict:'fail', reason:'review-B-only'}
    ].map(JSON.stringify).join('\n')
  };
  function installLinked(source = texts) {
    vm.runInContext(`install(${JSON.stringify(source)}, "联动测试")`, linked.scope);
  }
  function expectCurrent(task, kind = 'both') {
    const content = linked.node('events').innerHTML;
    assert.ok(linked.node('detail').innerHTML.includes('task-' + task));
    assert.ok(linked.node('events-count').textContent.includes('task-' + task));
    for (const other of ['A','B'].filter(x => x !== task)) {
      assert.ok(!content.includes('task-' + other), 'other task must not appear');
    }
    assert.doesNotMatch(content, /orphan-must-not-leak|comment-must-not-leak/);
    assert.equal(content.includes('verify-' + task + '-only'), kind !== 'r');
    assert.equal(content.includes('review-' + task + '-only'), kind !== 'e');
  }
  installLinked();
  linked.openAudit(vm.runInContext('selected', linked.scope));
  linked.eventKind('both');
  assert.equal(linked.node('events-drawer').hidden, false);
  expectCurrent('A');
  linked.pick(1);
  expectCurrent('B');
  linked.key('ArrowUp');
  expectCurrent('A');
  linked.pick(1);
  expectCurrent('B');
  linked.eventKind('e');
  expectCurrent('B', 'e');
  linked.eventKind('r');
  expectCurrent('B', 'r');
  linked.key('ArrowUp');
  expectCurrent('A', 'r');
  linked.eventKind('both');
  expectCurrent('A');
  assert.doesNotMatch(html, /data-evf="(?:all|current)"/);

  linked.pick(2);
  assert.match(linked.node('events-count').textContent, /0 条.*task-C/);
  assert.match(linked.node('events').innerHTML, /当前任务暂无证据或评审/);
  assert.doesNotMatch(linked.node('events').innerHTML, /task-A|task-B/);
  linked.node('search').value = 'no-matching-task';
  linked.fire('search', 'input');
  assert.match(linked.node('events').innerHTML, /请先.*选择任务/);
  assert.doesNotMatch(linked.node('events-count').textContent, /task-A|task-B|task-C/);
  linked.node('search').value = 'task-B';
  linked.fire('search', 'input');
  expectCurrent('B');
  linked.eventKind('r');
  const withoutReviews = {...texts, 'reviews.jsonl':''};
  installLinked(withoutReviews);
  assert.match(linked.node('events').innerHTML, /当前任务暂无评审/);
  assert.doesNotMatch(linked.node('events').innerHTML, /verify-B-only|review-A-only/);

  // Polling installs fresh files through the same path: no cross-task history may appear.
  linked.eventKind('both');
  const updated = {...texts, 'evidence.jsonl':texts['evidence.jsonl'] + '\n' + JSON.stringify({
    id:'new-evidence-B', task:'task-B', cmd:'fresh-B-only', exit:0, ts:'2026-09-11T10:02:00Z'
  })};
  installLinked(updated);
  expectCurrent('B');
  assert.match(linked.node('events').innerHTML, /fresh-B-only/);
  linked.fire('events-close', 'click');
  assert.equal(linked.node('events-drawer').hidden, true);
  linked.openAudit(vm.runInContext('selected', linked.scope));
  linked.eventKind('both');
  expectCurrent('B');
  const otherProject = {'tasks.json':JSON.stringify({tasks:[{id:'task-B', status:'active', desc:'新项目同编号任务'}]})};
  installLinked(otherProject);
  assert.match(linked.node('events').innerHTML, /当前任务暂无证据或评审/);
  assert.doesNotMatch(linked.node('events').innerHTML, /verify-B-only|fresh-B-only/);

  assert.doesNotMatch(html, /id="tab-btn-(?:next|gantt)"|id="events-open"|id="trace-select"/);
  assert.doesNotMatch(code, /name_zh|desc_zh|summary_zh|reason_zh|parseI18n|translated\(/);
  assert.match(html, /\[hidden\]\s*\{\s*display:\s*none\s*!important/);
  const accordion = run({});
  const accordionTexts = {'tasks.json':JSON.stringify({project:'折叠测试',tasks:[
    {id:'a',desc:'第一张任务',status:'active',wave:'第一阶段',priority:1},
    {id:'b',desc:'第二张任务',status:'passed',wave:'第二阶段',priority:2},
    {id:'c',desc:'第三张任务',status:'passed',wave:'第二阶段',priority:3}
  ]})};
  vm.runInContext(`install(${JSON.stringify(accordionTexts)}, '阶段测试')`,accordion.scope);
  const openGroups = () => Array.from(accordion.node('tasks').innerHTML.matchAll(/class="stage-toggle"[^>]*aria-expanded="(true|false)"/g),x=>x[1]);
  const stageClick = stage => accordion.fire('tasks','click',{target:{closest(selector){
    return selector==='[data-stage-toggle]'?{dataset:{stageToggle:stage}}:null;
  }}});
  assert.deepEqual(openGroups(), ['false','false'], '阶段初始必须全部折叠');
  assert.equal((accordion.node('tasks').innerHTML.match(/class="stage-cards"[^>]* hidden/g)||[]).length,2);
  stageClick('第一阶段');
  assert.deepEqual(openGroups(), ['true','false']);
  stageClick('第二阶段');
  assert.deepEqual(openGroups(), ['false','true'], '展开必须互斥');
  assert.match(accordion.node('detail').innerHTML, /第一张任务/, '折叠操作不改变当前行');
  vm.runInContext(`install(${JSON.stringify(accordionTexts)}, '轮询刷新')`,accordion.scope);
  assert.deepEqual(openGroups(), ['false','true'], '轮询不得重置用户展开状态');
  stageClick('第二阶段');
  assert.deepEqual(openGroups(), ['false','false'], '再次点击可全部收起');
  accordion.key('ArrowDown');
  assert.deepEqual(openGroups(), ['false','true'], '键盘选中任务时仅展开所在阶段');
  assert.equal(accordion.node('c-passed').textContent,'2');
  accordion.fire('rail-nav','click',{target:{closest(){return {dataset:{filter:'passed'}};}}});
  assert.match(accordion.node('tasks').innerHTML,/第二张任务[\s\S]*第三张任务/);
  assert.doesNotMatch(accordion.node('tasks').innerHTML,/第一张任务/);
  assert.match(accordion.node('filter-chip').innerHTML,/已通过/);
  vm.runInContext("showEmpty('清空来源')",accordion.scope);
  vm.runInContext(`install(${JSON.stringify(accordionTexts)}, '另一来源')`,accordion.scope);
  assert.ok(openGroups().every(x=>x==='false'), '来源切换后默认折叠');
  const railHtml = html.match(/<aside class="rail">([\s\S]*?)<\/aside>/)[1];
  const topHtml = html.match(/<header class="top">([\s\S]*?)<\/header>/)[1];
  assert.doesNotMatch(railHtml,/class="keys/);
  assert.match(topHtml,/键盘操作[\s\S]*<kbd>J<\/kbd>[\s\S]*<kbd>K<\/kbd>/);
  assert.match(railHtml,/data-filter="passed"[\s\S]*id="c-passed"/);
  const native = run({});
  const nativeTexts = {
    'tasks.json': JSON.stringify({project:'中文项目', description:'中文目标', tasks:[
      {id:'A', name:'实现甲', desc:'完成甲', reason:'暂无阻塞', next:'运行验证', status:'active', wave:'第一阶段', priority:1},
      {id:'B', name:'实现乙', desc:'完成乙', reason:'等待环境', next:'准备环境', status:'blocked', wave:'第二阶段', priority:2}
    ]}),
    'evidence.jsonl': JSON.stringify({id:'ev-A',task:'A',summary:'十二项测试通过',tests:'12 passed',cmd:'pytest -q',exit:0,ts:'2026-09-12T10:00:00Z'}),
    'reviews.jsonl': JSON.stringify({id:'rv-B',task:'B',reason:'环境不齐，尚不能通过',verdict:'fail',ts:'2026-09-12T10:05:00Z'}),
    'progress.txt':'## 2026-09-12T09:00:00Z | A | 执行\n- 进展：甲已开始\n## 2026-09-12T09:30:00Z | B | 执行\n- 进展：乙被阻塞\n'
  };
  vm.runInContext(`install(${JSON.stringify(nativeTexts)}, "中文联动")`, native.scope);
  assert.match(native.node('tasks').innerHTML, /第一阶段[\s\S]*第二阶段/);
  const cards = native.node('tasks').innerHTML.match(/<article class="tcard[\s\S]*?<\/article>/g);
  assert.match(cards[0], /card-bottom[\s\S]*card-progress[\s\S]*audit-brief[\s\S]*card-actions/);
  assert.match(cards[0], /data-action="events"[\s\S]*证据 1 · 评审 0 ↗/);
  assert.match(cards[0], /data-action="trajectory"[\s\S]*任务轨迹 →/);
  assert.doesNotMatch(native.node('tasks').innerHTML, /data-audit=|task-select|最近进展|card-footer/);
  assert.match(cards[1], /已阻塞/);
  assert.doesNotMatch(vm.runInContext("progressMarkup({status:'blocked'})", native.scope), /class="reached"/);
  native.openTrace(0);
  assert.equal(native.node('tab-trajectory').hidden, false);
  assert.match(native.node('trajectory').innerHTML, /trajectory-current[\s\S]*audit-timeline/);
  assert.match(native.node('trajectory').innerHTML, /十二项测试通过/);
  assert.doesNotMatch(native.node('trajectory').innerHTML, /环境不齐|甲已开始/);
  assert.match(native.node('trajectory').innerHTML, /evidence\.jsonl:1/);
  assert.equal(vm.runInContext('parse({"tasks.json":JSON.stringify({tasks:[]}),"evidence.jsonl":"\\n"+JSON.stringify({id:"ev",_sourceLine:99})}).evidence[0]._sourceLine',native.scope), 2, '来源行号取物理行，不能信任记录自带值');
  native.pick(1);
  assert.match(native.node('trajectory').innerHTML, /环境不齐/);
  assert.doesNotMatch(native.node('trajectory').innerHTML, /十二项测试通过/);
  assert.match(native.node('trajectory').innerHTML, /reviews\.jsonl:1/);
  native.openAudit(1);
  assert.equal(vm.runInContext('eventFilter', native.scope), 'both');
  assert.match(native.node('events-summary').innerHTML, /关联证据缺失/);
  native.eventKind('r');
  assert.match(native.node('events').innerHTML, /环境不齐/);
  native.openAudit(0);
  assert.equal(native.node('events-drawer').hidden, false);
  assert.match(native.node('events').innerHTML, /十二项测试通过[\s\S]*<details[\s\S]*12 passed/);
  assert.doesNotMatch(native.node('events').innerHTML.split('<details')[0], /12 passed/);
  native.key('Escape');
  assert.equal(native.node('events-drawer').hidden, true);
  vm.runInContext('openLoad()', native.scope);
  native.key('Escape');
  assert.equal(native.node('load-drawer').hidden, true);
  native.node('load-close').onclick();
  assert.equal(native.node('load-drawer').hidden, true);
  assert.match(native.node('progress-log').innerHTML, /log-summary[\s\S]*progress-list[\s\S]*raw-log/);
  assert.match(native.node('progress-log').innerHTML, /甲已开始|乙被阻塞/);
  const refreshedTexts = {...nativeTexts,
    'progress.txt':'\n\n第一条记录\nEXIT_SIGNAL: true\nEXIT_SIGNAL: false\n',
    'reviews.jsonl':nativeTexts['reviews.jsonl'] + '\n' + JSON.stringify({id:'rv-other',task:'A-other',reason:'不能串入甲任务',ts:'2026-09-12T11:00:00Z'}) + '\n' + JSON.stringify({id:'rv-A',task:'A',reason:'仍待明确结论',ts:'无效时间'})
  };
  vm.runInContext(`install(${JSON.stringify(refreshedTexts)}, "刷新记录")`, native.scope);
  assert.match(native.node('trajectory').innerHTML, /时间格式无效[\s\S]*结论未明确/);
  assert.doesNotMatch(native.node('trajectory').innerHTML, /不能串入甲任务/);
  assert.match(native.node('progress-log').innerHTML, /尚未发出退出信号/);
  assert.match(native.node('progress-log').innerHTML, /第一条记录[\s\S]*第 3 行/);
  assert.ok(native.node('trajectory').innerHTML.indexOf('十二项测试通过') < native.node('trajectory').innerHTML.indexOf('仍待明确结论'));

  vm.runInContext("lastStamp = 'previous valid snapshot'", native.scope);
  assert.throws(()=>vm.runInContext('snapshotFiles({snapshot:{tasks:[]},contract:{errors:["tasks.json.description：必须中文"]}})',native.scope), /必须中文/);
  assert.equal(vm.runInContext('lastStamp', native.scope), '', '修复回原内容也必须触发重新渲染');
  assert.throws(()=>vm.runInContext('snapshotFiles({snapshot:{tasks:[]}})',native.scope), /契约/);
  const invalidBoot = run({location:{protocol:'http:',href:'http://127.0.0.1:8765/'}, fetch:async()=>({ok:true,status:200,text:async()=>JSON.stringify({
    source:'E:/invalid',files:{}, snapshot:boardSnap([{id:'english-task',status:'active',desc:'English only'}]),
    contract:{errors:['tasks.json.description：必须中文']}
  })})});
  vm.runInContext('install = function(){ calls.push("unexpected install"); }', invalidBoot.scope);
  await new Promise(r=>setTimeout(r,20));
  assert.equal(invalidBoot.scope.calls.length, 0, '启动不能先渲染不合格数据再隐藏');
  assert.doesNotMatch(invalidBoot.node('tasks').innerHTML, /English only|english-task/);
  assert.equal(invalidBoot.node('contract-error').hidden, false);
  assert.match(invalidBoot.node('contract-error').textContent, /必须中文/);
  assert.equal(invalidBoot.node('error-dialog').hidden, false, '契约错误必须弹窗，不能占主区');
  assert.doesNotMatch(invalidBoot.node('status').textContent, /\n/, '底栏只能是一行摘要');
  assert.match(invalidBoot.node('status').textContent, /\u70b9\u6b64\u67e5\u770b/);
  invalidBoot.key('Escape');
  assert.equal(invalidBoot.node('error-dialog').hidden, true, 'Esc 关闭错误弹窗');
  assert.match(invalidBoot.node('contract-error').textContent, /\u5fc5\u987b\u4e2d\u6587/);
  invalidBoot.fire('status', 'click');
  assert.equal(invalidBoot.node('error-dialog').hidden, false, '底栏可再次打开错误弹窗');
  // 历史契约：载入先打开会话面板；慢轮询不得阻塞按钮，不得自动调用目录框。
  const restored = run({});
  restored.scope.location.protocol = 'http:';
  let finishPoll, finishSessions;
  restored.scope.pendingPoll = new Promise(resolve => { finishPoll = resolve; });
  vm.runInContext('chain = pendingPoll', restored.scope);
  const loadRequests = [];
  const catalog = {sessions_dir:'C:/isolated/sessions', scanned:2, skipped:0, suggested:null, projects:[
    {cwd:'E:/project-A', source:'E:/project-A/.harness', has_harness:true, latest_title:'重构会话载入', sessions:[]},
    {cwd:'E:/project-B', source:'E:/project-B/.harness', has_harness:true, latest_title:'另一会话', sessions:[]}
  ]};
  restored.scope.fetch = async (url, opts) => {
    loadRequests.push({url:String(url), opts});
    if(url === '/api/sessions') return new Promise(resolve => { finishSessions = () => resolve({ok:true,text:async()=>JSON.stringify(catalog)}); });
    if(url === '/api/source') return {ok:true,text:async()=>JSON.stringify({source:'E:/project-B/.harness',contract:{errors:[]},files:{},snapshot:boardSnap([{id:'selected-from-session',desc:'从会话选择',status:'active'}], {project:'历史会话验证'})})};
    throw Error('不得打开文件窗口：' + url);
  };
  const loading = restored.node('load').onclick();
  assert.equal(restored.node('load-drawer').hidden, false, '载入抽屉不能排队等待轮询');
  assert.ok(loadRequests.some(row=>row.url==='/api/sessions'));
  assert.match(restored.node('load-session-status').textContent, /读取/);
  restored.node('load-close').onclick();
  assert.equal(restored.node('load-drawer').hidden, true);
  finishSessions(); await loading;
  assert.equal(restored.node('load-drawer').hidden, true, '异步会话返回不得重新打开已关闭面板');
  assert.match(restored.node('load-list').innerHTML, /重构会话载入|另一会话/);
  assert.match(restored.node('load-session-status').textContent, /2/);
  finishPoll(); await restored.scope.pendingPoll;
  await restored.fire('session-row-1','click');
  assert.equal(JSON.parse(loadRequests.find(row=>row.url==='/api/source').opts.body).path,'E:/project-B/.harness');
  assert.match(restored.node('tasks').innerHTML,/selected-from-session/);
  assert.equal(restored.node('load-drawer').hidden,true);
  assert.ok(!loadRequests.some(row=>row.url==='/api/pick-dir'));
  restored.scope.fetch = async()=>{throw Error('会话服务不可用');};
  await restored.node('load').onclick();
  assert.equal(restored.node('load-drawer').hidden,false);
  assert.match(restored.node('load-session-status').textContent,/会话服务不可用/);
  assert.doesNotMatch(restored.node('load-list').innerHTML,/session-row|重构会话载入|另一会话/);
  restored.node('load-close').onclick();
  assert.equal(restored.node('load-drawer').hidden,true);
  // 错误后可重试，不把旧服务返回的 HTML 当作空会话。
  restored.scope.fetch = async()=>({ok:true,text:async()=>'<html>旧页面</html>'});
  await restored.node('load').onclick();
  assert.match(restored.node('load-session-status').textContent,/配套|会话接口/);
  restored.scope.fetch = async()=>({ok:true,text:async()=>JSON.stringify(catalog)});
  await restored.node('load').onclick();
  assert.match(restored.node('load-list').innerHTML,/重构会话载入/);
  assert.match(html,/class="build-id"/);
  console.log('UI logic: assertions passed (mock DOM; not browser visual verification)');
})().catch(e=>{console.error(e);process.exitCode=1;});
