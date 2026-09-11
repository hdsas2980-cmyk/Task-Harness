const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const templatePath = path.join(__dirname,'../static/index.html');
const jsTemplatePath = path.join(__dirname,'../static/app.js');
const html = fs.readFileSync(templatePath,'utf8');
const code = fs.readFileSync(jsTemplatePath,'utf8');
assert.match(html, /载入任务/);
assert.match(html, /刷新任务/);
assert.match(html, /\.\/app\.js/);
assert.match(html, /load-drawer/);
assert.match(html, /data-filter="all"[\s\S]*data-filter="blocked"/);
assert.match(html, /id="tab-btn-list"[\s\S]*id="tab-btn-next"/);
assert.match(code, /mainTab = 'list'/);
assert.match(code, /data-status=/);
assert.match(code, /renderEvidenceCard/);
assert.match(html, /event-filters/);
assert.match(html, /从 Codex 会话选择/);
assert.match(code, /api\/sessions/);
assert.match(code, /api\/source/);
assert.match(code, /bootstrapSource/);
assert.doesNotMatch(code, /showDirectoryPicker|isTauri|__TAURI__|probe_harness_dir/);
assert.match(code, /startPoll/);
assert.doesNotMatch(html, /载入示例|清空|type="file"|__HARNESS_SNAPSHOT__|id="snapshot"/);

function node(id, nodes){
  if(!nodes.has(id)) nodes.set(id,{textContent:'',innerHTML:'',value:'',checked:false,disabled:false,hidden:true,classList:{toggle(){},add(){},remove(){}},addEventListener(){},insertAdjacentHTML(_,text){this.innerHTML+=text;},click(){this.clicked=true;},focus(){},matches(){return false;},closest(){return null;},querySelectorAll(){return [];}});
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
  n('load-list').querySelectorAll = () => [];
  const listeners = {};
  const store = Object.assign({}, extras.store || {});
  const fetches = [];
  const scope = {
    document:{getElementById:n,querySelector(){return {addEventListener(){}};},hidden:false,addEventListener(type,fn){listeners[type]=fn;}},
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
  return {scope, node:n, store, nodes, fetches};
}

(async()=>{
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
      return {ok:true, status:200, text:async()=>JSON.stringify({source:'E:/proj/.harness', files:{'tasks.json':JSON.stringify({project:'演示',tasks:[{id:'picked-1',status:'blocked',priority:1,desc:'from session'}]})}})};
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
    'install({"tasks.json":JSON.stringify({project:"demo",tasks:[{id:"t-01",status:"evidence_ready",priority:1,desc:"x"}]}),'
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
  assert.match(http.node('detail-events').innerHTML, /退出码/);

  console.log('UI logic: assertions passed (mock DOM; not browser visual verification)');
})().catch(e=>{console.error(e);process.exitCode=1;});
