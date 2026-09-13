// 真实 HTTP 服务 + 发布包实际脚本 + 模拟 DOM 事件，不是浏览器视觉测试。
const assert = require('node:assert/strict');
const vm = require('node:vm');
const {run} = require('./test_ui.cjs');
const base = process.env.TASK_BOARD_TEST_URL;
const target = process.env.TASK_BOARD_TEST_TARGET;
assert.ok(base && target, '仅由隔离发布测试提供服务地址和任务目录');
(async()=>{
  const requests = [];
  const ui = run({}); // 阻止隐式启动，随后使用真实 HTTP 重跑启动流程。
  ui.scope.location = {protocol:'http:',href:base + '/'};
  ui.scope.fetch = async(url,opts)=>{
    requests.push(String(url));
    return fetch(new URL(url,base),opts);
  };
  await vm.runInContext('bootstrapSource()',ui.scope);
  assert.match(ui.node('tasks').innerHTML,/task-A/);
  await ui.node('load').onclick();
  assert.equal(ui.node('load-drawer').hidden,false);
  assert.match(ui.node('load-list').innerHTML,/会话甲|会话乙/);
  const rows = vm.runInContext('sessionCatalog.projects',ui.scope);
  const index = rows.findIndex(row=>row.cwd===target);
  assert.ok(index>=0, '真实扫描结果必须包含测试会话乙');
  await ui.fire('session-row-' + index,'click');
  assert.match(ui.node('tasks').innerHTML,/task-B/);
  assert.doesNotMatch(ui.node('tasks').innerHTML,/task-A/);
  assert.equal(ui.node('load-drawer').hidden,true);
  assert.ok(requests.includes('/api/sessions') && requests.includes('/api/source'));
  assert.ok(!requests.includes('/api/pick-dir'), '载入会话不能调用文件夹窗口');
  // 选择后依然能刷新、切换标签、打开卡片证据与关闭抽屉。
  await ui.node('refresh').onclick();
  ui.fire('view-tabs','click',{target:{closest(){return {dataset:{tab:'trajectory'}};}}});
  assert.equal(ui.node('tab-trajectory').hidden,false);
  assert.match(ui.node('trajectory').innerHTML,/task-B/);
  ui.openAudit(0);
  assert.equal(ui.node('events-drawer').hidden,false);
  ui.key('Escape');
  assert.equal(ui.node('events-drawer').hidden,true);
  assert.equal(ui.node('load-drawer').hidden,true);
  console.log('独立 ZIP：真实 HTTP 会话扫描 → 实际按钮回调 → 切换来源 → 刷新与轨迹，通过（模拟 DOM）。');
})().catch(error=>{console.error(error);process.exitCode=1;});
