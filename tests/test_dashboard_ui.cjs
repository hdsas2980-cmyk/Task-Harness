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
assert.doesNotMatch(html, /载入示例|清空|type="file"|__HARNESS_SNAPSHOT__|id="snapshot"/);
const code = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const nodes = new Map();
function node(id){if(!nodes.has(id))nodes.set(id,{textContent:'',innerHTML:'',value:'',checked:false,disabled:false,classList:{toggle(){},add(){},remove(){}},addEventListener(){},insertAdjacentHTML(_,text){this.innerHTML+=text;},click(){this.clicked=true;},matches(){return false;},closest(){return null;}});return nodes.get(id);}
node('search').value='';
let reloads=0, fetches=0, picks=0;
const listeners={};
const scope={
  document:{getElementById:node,querySelector(){return {addEventListener(){}};},hidden:false,addEventListener(type,fn){listeners[type]=fn;}},
  window:{},
  location:{protocol:'file:',href:'file:///proj/.harness/task-harness.html',reload(){reloads++;}},
  URL, console, setInterval(){},
  fetch(){fetches++; throw Error('file protocol blocked');}
};
vm.createContext(scope);
vm.runInContext(code,scope);
assert.match(node('status').textContent,/选择项目任务目录/);
assert.doesNotMatch(node('tasks').innerHTML,/<img/);
assert.equal(vm.runInContext('model.tasks.tasks.length',scope),0);
const before=vm.runInContext('JSON.stringify(model)',scope);
assert.throws(()=>vm.runInContext('install({"tasks.json":"{bad}"},"错误")',scope));
assert.equal(vm.runInContext('JSON.stringify(model)',scope),before);
assert.throws(()=>vm.runInContext('parse({"tasks.json":JSON.stringify({tasks:[{id:"x",status:"bad"}]})})',scope));
assert.throws(()=>vm.runInContext('parse({"tasks.json":JSON.stringify({tasks:[]}),"reviews.jsonl":"[]"})',scope));
(async()=>{
  await node('load').onclick();
  assert.equal(fetches,0);
  assert.match(node('status').textContent,/选择项目任务目录|桌面壳|载入任务/);
  await node('refresh').onclick();
  assert.equal(reloads,0);
  assert.equal(fetches,0);
  scope.location.protocol='http:';
  scope.location.href='http://127.0.0.1:8765/task-harness.html';
  scope.fetch=async url=>{fetches++; return {ok:true,status:200,text:async()=>String(url).endsWith('tasks.json')?JSON.stringify({project:'live',tasks:[{id:'updated',status:'active',priority:1}]}):''};};
  await node('load').onclick();
  assert.match(node('tasks').innerHTML,/updated/);
  assert.match(node('status').textContent,/已载入当前项目任务/);
  assert.match(node('tasks').innerHTML,/进行中/);
  const fakeDir = {
    name:'demo',
    async getFileHandle(name){
      if(name!=='tasks.json') throw Error('missing');
      return {async getFile(){ return {async text(){ return JSON.stringify({project:'picked',tasks:[{id:'picked-1',status:'blocked',priority:1,desc:'from dir'}]}); }}; }};
    },
    async getDirectoryHandle(){ throw Error('no nested'); }
  };
  scope.window.showDirectoryPicker = async ()=>{ picks++; return fakeDir; };
  await node('load').onclick();
  assert.equal(picks,1);
  assert.match(node('tasks').innerHTML,/picked-1/);
  assert.match(node('status').textContent,/已载入/);
  assert.match(node('project').textContent,/demo/);
  scope.fetch=async url=>{fetches++; return {ok:true,status:200,text:async()=>String(url).endsWith('tasks.json')?JSON.stringify({project:'live',tasks:[{id:'a',desc:'<img src=x onerror=alert(1)>',status:'passed',priority:1},{id:'b',status:'pending',depends_on:['a'],priority:2}]}):''};};
  await node('refresh').onclick();
  assert.match(node('tasks').innerHTML,/已阻塞|门禁缺口|picked-1|已通过/);
  console.log('UI logic: assertions passed (mock DOM; not browser visual verification)');
})().catch(e=>{console.error(e);process.exitCode=1;});
