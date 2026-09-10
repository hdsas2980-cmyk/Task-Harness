const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname,'../references/templates/task-harness.html'),'utf8');
assert.match(html, /载入任务/);
assert.match(html, /刷新任务/);
assert.match(html, /http:\/\/127\.0\.0\.1/);
assert.doesNotMatch(html, /载入示例|清空|type="file"|showDirectoryPicker|选择任务目录|__HARNESS_SNAPSHOT__|id="snapshot"/);
const code = html.match(/<script>\n([\s\S]*?)<\/script>/)[1];
const tasks = {project:'测试项目',rev:1,tasks:[
  {id:'a',desc:'<img src=x onerror=alert(1)>',status:'passed',depends_on:[],priority:1},
  {id:'b',status:'pending',depends_on:['a'],priority:2,desc:'下一步'}
]};
const nodes = new Map();
function node(id){if(!nodes.has(id))nodes.set(id,{textContent:'',innerHTML:'',value:'',checked:false,disabled:false,classList:{toggle(){},add(){},remove(){}},addEventListener(){},insertAdjacentHTML(_,text){this.innerHTML+=text;},click(){this.clicked=true;},matches(){return false;},closest(){return null;}});return nodes.get(id);}
node('search').value='';
let reloads=0, fetches=0;
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
assert.match(node('status').textContent,/127\.0\.0\.1/);
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
  assert.match(node('status').textContent,/127\.0\.0\.1/);
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
  scope.fetch=async url=>{fetches++; return {ok:true,status:200,text:async()=>String(url).endsWith('tasks.json')?JSON.stringify({project:'live',tasks:[{id:'a',desc:'<img src=x onerror=alert(1)>',status:'passed',priority:1},{id:'b',status:'pending',depends_on:['a'],priority:2}]}):''};};
  await node('refresh').onclick();
  assert.match(node('tasks').innerHTML,/已通过/);
  assert.match(node('tasks').innerHTML,/门禁缺口/);
  assert.match(node('tasks').innerHTML,/&lt;img/);
  assert.doesNotMatch(node('tasks').innerHTML,/<img/);
  assert.match(node('hero-id').textContent,/b/);
  scope.fetch=async()=>({ok:false,status:500});
  await node('refresh').onclick();
  assert.match(node('status').textContent,/刷新失败|读取失败/);
  assert.match(node('tasks').innerHTML,/updated|已通过/);
  console.log('UI logic: assertions passed (mock DOM; not browser visual verification)');
})().catch(e=>{console.error(e);process.exitCode=1;});
