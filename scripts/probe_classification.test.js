const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'full_probe.js'),'utf8');
const marker=' let agent,cid;';
assert.ok(source.includes(marker));
// Execute the classifier from the exact browser script, stopping before I/O.
const ctx={document:{querySelector:()=>({hass:{}})},window:{}};
vm.createContext(ctx);
vm.runInContext(source.replace(marker,' globalThis.classifyForTest=classify;return;'),ctx);
const classify=(speech,type='action_done')=>ctx.classifyForTest({speech,type});
test('washer shutdown is a state limitation',()=>{
 for(const s of ['海尔洗衣机已关机，无法确认当前数据。','海尔洗衣机 · 洗涤参数\n\n已关机，无法确认当前数据。','海尔洗衣机 · 洗涤剂余量\n\n已关机，无法确认当前数据。'])assert.equal(classify(s),'state_limit');
});
test('independent missing data and execution failure retain priority',()=>{
 assert.equal(classify('海尔洗衣机 · 筒门及锁状态\n\n已关机，无法确认当前数据。\n筒门：数据不可用。'),'data_gap');
 assert.equal(classify('已关机，无法确认当前数据。','error'),'error');
 assert.equal(classify('AI 对话暂时不可用，请稍后重试。'),'error');
 assert.equal(classify('入户门锁：状态无法确认。洗衣机关机时不判断故障。'),'data_gap');
});
test('normal negatives and unsupported metrics remain distinct',()=>{
 assert.equal(classify('离线检查：暂未检测到不可用灯具。'),'normal_negative');
 assert.equal(classify('亮度调节：不支持。'),'capability_limit');
 assert.equal(classify('当前无欠费'),'normal_negative');
});

test('mixed washer shutdown plus verified lifetime counters is partial state limitation',()=>{
 const valid='海尔洗衣机 · 用水用电统计\n\n已关机，无法确认当前数据。\n设备报告累计用水：12345升。\n设备报告累计用电：72.34度。\n设备报告累计洗涤周期：234次。';
 assert.equal(classify(valid),'partial_state_limit');
 assert.equal(classify(valid.replace('72.34度','数据不可用')),'data_gap');
 assert.equal(classify(valid+'\n另有数据不可用。'),'data_gap');
 assert.equal(classify(valid.replace('设备报告累计洗涤周期：234次。','')),'data_gap');
 assert.equal(classify(valid,'error'),'error');
});
