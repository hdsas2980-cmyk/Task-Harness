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
assert.match(code, /选择项目任务目录/);
assert.match(code, /showDirectoryPicker/);
assert.doesNotMatch(code, /isTauri|__TAURI__|probe_harness_dir/);
assert.match(code, /api\/snapshot/);
assert.match(code, /startPoll/);
assert.match(code, /正在选择项目任务目录/);
assert.doesNotMatch(html, /载入示例|清空|type="file"|__HARNESS_SNAPSHOT__|id="snapshot"/);

function node(id, nodes){
  if(!nodes.has(id)) nodes.set(id,{textContent:'',innerHTML:'',value:'',checked:false,disabled:false,classList:{toggle(){},add(){},remove(){}},addEventListener(){},insertAdjacentHTML(_,text){this.innerHTML+=text;},click(){this.clicked=true;},matches(){return false;},closest(){return null;}});
  return nodes.get(id);
}

function run(extras){
  const nodes = new Map();
  const n = id => node(id, nodes);
  n('search').value='';
  const listeners = {};
  const store = Object.assign({}, extras.store || {});
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
    fetch: extras.fetch || (()=>{ scope.fetches++; throw Error('file protocol blocked'); }),
    reloads:0,
    fetches:0,
    calls:[]
  };
  if(extras.window) scope.window = extras.window;
  vm.createContext(scope);
  vm.runInContext(code, scope);
  return {scope, node:n, store, nodes};
}

(async()=>{
  const file = run({});
  assert.match(file.node('status').textContent,/选择项目任务目录/);
  assert.doesNotMatch(file.node('tasks').innerHTML,/<img/);
  assert.equal(vm.runInContext('model.tasks.tasks.length',file.scope),0);
  const before=vm.runInContext('JSON.stringify(model)',file.scope);
  assert.throws(()=>vm.runInContext('install({"tasks.json":"{bad}"},"错误")',file.scope));
  assert.equal(vm.runInContext('JSON.stringify(model)',file.scope),before);
  assert.throws(()=>vm.runInContext('parse({"tasks.json":JSON.stringify({tasks:[{id:"x",status:"bad"}]})})',file.scope));
  assert.throws(()=>vm.runInContext('parse({"tasks.json":JSON.stringify({tasks:[]}),"reviews.jsonl":"[]"})',file.scope));
  await file.node('load').onclick();
  assert.equal(file.scope.fetches,0);
  assert.match(file.node('status').textContent,/选择项目任务目录|桌面壳|载入任务/);
  await file.node('refresh').onclick();
  assert.equal(file.scope.reloads,0);
  assert.equal(file.scope.fetches,0);

  file.scope.location.protocol='http:';
  file.scope.location.href='http://127.0.0.1:8765/task-harness.html';
  file.scope.fetch=async url=>{file.scope.fetches++; return {ok:true,status:200,text:async()=>String(url).endsWith('tasks.json')?JSON.stringify({project:'live',tasks:[{id:'updated',status:'active',priority:1}]}):''};};
  await file.node('load').onclick();
  assert.match(file.node('tasks').innerHTML,/updated/);
  assert.match(file.node('status').textContent,/已载入当前项目任务/);
  assert.match(file.node('tasks').innerHTML,/进行中/);
  const fakeDir = {
    name:'demo',
    async getFileHandle(name){
      if(name!=='tasks.json') throw Error('missing');
      return {async getFile(){ return {async text(){ return JSON.stringify({project:'picked',tasks:[{id:'picked-1',status:'blocked',priority:1,desc:'from dir'}]}); }}; }};
    },
    async getDirectoryHandle(){ throw Error('no nested'); }
  };
  let picks=0;
  file.scope.window.showDirectoryPicker = async ()=>{ picks++; return fakeDir; };
  await file.node('load').onclick();
  assert.equal(picks,1);
  assert.match(file.node('tasks').innerHTML,/picked-1/);
  assert.match(file.node('status').textContent,/已载入/);
  assert.match(file.node('project').textContent,/demo/);
  file.scope.fetch=async url=>{file.scope.fetches++; return {ok:true,status:200,text:async()=>String(url).endsWith('tasks.json')?JSON.stringify({project:'live',tasks:[{id:'a',desc:'<img src=x onerror=alert(1)>',status:'passed',priority:1},{id:'b',status:'pending',depends_on:['a'],priority:2}]}):''};};
  await file.node('refresh').onclick();
  assert.match(file.node('tasks').innerHTML,/已阻塞|门禁缺口|picked-1|已通过/);

  console.log('UI logic: assertions passed (mock DOM; not browser visual verification)');
})().catch(e=>{console.error(e);process.exitCode=1;});
