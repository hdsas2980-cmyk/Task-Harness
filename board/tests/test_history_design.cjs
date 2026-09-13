// 历史会话原始代码的指纹，不从待测当前实现生成期望值。
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const root = process.env.TASK_BOARD_TEST_STATIC || path.join(__dirname,'../static');
const history = require('./history-design.json');
const html = fs.readFileSync(path.join(root,'index.html'),'utf8').replace(/\r\n/g,'\n');
const code = fs.readFileSync(path.join(root,'app.js'),'utf8').replace(/\r\n/g,'\n');
const hash = text => createHash('sha256').update(text).digest('hex');
// 保留原始指纹；仅撤销用户明确批准的三处布局补丁后比对，不重算期望值。
const adjustments = require('./layout-adjustments.json');
const normalized = {html, code};
for(const patch of [...adjustments.patches].reverse()){
  assert.ok(Object.hasOwn(normalized, patch.target), '未知补丁目标');
  assert.ok(patch.after.length > 0, '补丁匹配不能为空');
  const text = normalized[patch.target];
  assert.equal(text.split(patch.after).length - 1, 1, '批准的布局补丁必须精确匹配一次：' + patch.after.slice(0,80));
  normalized[patch.target] = text.replace(patch.after, () => patch.before);
}
const originalHtml = normalized.html.replace(/^.*id="contract-error".*\n/gm,'').replace(/^.*id="load-session-status".*\n/gm,'');
assert.equal(hash(originalHtml), history.html, '批准的三处调整与两个消息节点之外，HTML 必须与历史源一致');
assert.equal(hash(normalized.html.match(/<style>([\s\S]*?)<\/style>/)[1]), history.style, '批准调整之外，整个样式块必须与历史源一致');
for(const [name, expected] of Object.entries(history.functions)){
  const source = normalized.code.match(new RegExp('^function ' + name + '\\([\\s\\S]*?^}', 'm'))?.[0];
  assert.ok(source, '缺少历史函数 ' + name);
  assert.equal(hash(source), expected, name + ' 必须使用历史原实现，不是重新设计');
}
assert.match(html, /id="tab-btn-trajectory"/);
assert.match(html, /id="events-summary" class="audit-summary"/);
assert.match(html, /id="progress-log"/);
assert.doesNotMatch(html, /group-cards|card-footer|trace-list|trace-select|trajectory-task"/);
console.log('历史设计保护：撤销三处批准调整后，HTML、CSS、卡片及轨迹与原始会话指纹一致。');
