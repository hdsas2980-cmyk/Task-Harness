const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const htmlPath = path.join(__dirname,'../dashboard/ui/index.html');
const templatePath = path.join(__dirname,'../references/templates/task-harness.html');
const html = fs.readFileSync(htmlPath,'utf8');
assert.equal(fs.readFileSync(templatePath,'utf8'), html);
assert.match(html, /载入任务/);
assert.match(html, /刷新任务/);
assert.match(html, /选择项目任务目录/);
assert.match(html, /showDirectoryPicker/);
assert.match(html, /probe_harness_dir/);
assert.match(html, /正在选择项目任务目录/);
assert.doesNotMatch(html, /载入示例|清空|type="file"|__HARNESS_SNAPSHOT__|id="snapshot"/);
const code = html.match(/<script>([\s\S]*?)<\/script>/)[1];

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

  const calls=[];
  const tauriWin = {
    __TAURI__:{
      core:{
        invoke: async (cmd, args)=>{
          calls.push([cmd, args||null]);
          if(cmd==='probe_harness_dir') return 'E:/proj';
          if(cmd==='read_harness') return {path: args.path + '/.harness', files:{'tasks.json': JSON.stringify({project:'cwd',tasks:[{id:'cwd-1',status:'active',priority:1}]})}};
          if(cmd==='pick_harness_dir') return 'E:/other';
          throw Error('unknown '+cmd);
        }
      }
    }
  };
  const tauri = run({window: tauriWin, location:{protocol:'https:',href:'https://tauri.localhost/',reload(){}}});
  await new Promise(r=>setImmediate(r));
  await new Promise(r=>setImmediate(r));
  assert.equal(calls[0][0], 'probe_harness_dir');
  assert.equal(calls[1][0], 'read_harness');
  assert.match(tauri.node('tasks').innerHTML,/cwd-1/);
  assert.match(tauri.node('status').textContent,/已载入/);
  assert.match(tauri.node('project').textContent,/\.harness/);

  calls.length = 0;
  tauriWin.__TAURI__.core.invoke = async (cmd, args)=>{
    calls.push([cmd, args||null]);
    if(cmd==='pick_harness_dir') return 'E:/picked';
    if(cmd==='read_harness') return {path: args.path, files:{'tasks.json': JSON.stringify({project:'picked',tasks:[{id:'pick-1',status:'blocked',priority:1}]})}};
    throw Error('unexpected '+cmd);
  };
  await tauri.node('load').onclick();
  assert.equal(calls[0][0], 'pick_harness_dir');
  assert.equal(calls[1][0], 'read_harness');
  assert.match(tauri.node('tasks').innerHTML,/pick-1/);
  assert.match(tauri.node('status').textContent,/已载入/);

  calls.length = 0;
  tauriWin.__TAURI__.core.invoke = async (cmd)=>{
    calls.push(cmd);
    if(cmd==='pick_harness_dir') return null;
    throw Error('should not '+cmd);
  };
  await tauri.node('load').onclick();
  assert.deepEqual(calls, ['pick_harness_dir']);
  assert.match(tauri.node('status').textContent,/已取消选择目录/);
  assert.match(tauri.node('tasks').innerHTML,/pick-1/);

  const emptyCalls=[];
  const empty = run({
    window:{__TAURI__:{core:{invoke: async (cmd)=>{ emptyCalls.push(cmd); if(cmd==='probe_harness_dir') return null; throw Error('no '+cmd); }}}},
    location:{protocol:'https:',href:'https://tauri.localhost/',reload(){}}
  });
  await new Promise(r=>setImmediate(r));
  await new Promise(r=>setImmediate(r));
  assert.deepEqual(emptyCalls, ['probe_harness_dir']);
  assert.match(empty.node('status').textContent,/当前目录没有任务|载入任务/);

  console.log('UI logic: assertions passed (mock DOM; not browser visual verification)');
})().catch(e=>{console.error(e);process.exitCode=1;});
