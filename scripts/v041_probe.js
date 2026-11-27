// Nexora v0.4.1-preview — targeted live, local read-only acceptance.
// No device-control input or ordinary AI queries. Run in HA browser console.
(async()=>{
 const hass=document.querySelector("home-assistant")?.hass;
 if(!hass)throw Error("找不到 HA 前端");
 const {agents}=await hass.callWS({type:"conversation/agent/list"});
 const agent=agents.filter(x=>x.name==="Nexora");
 if(agent.length!==1)throw Error("未找到唯一 Nexora 代理");
 const report={version:"v0.4.1-preview",checks:[],passed:false};
 const cid="nexora-v041:"+crypto.randomUUID(),other="nexora-v041:"+crypto.randomUUID();
 const gap=/数据(?:尚未获取|不可用|不足)|暂无.{0,8}(?:账单|数据)|状态未知|超出.{0,10}(?:范围|覆盖)|状态无法确认/;
 const routeError=/严格识别不可用|意图库|参数不一致|本地查询暂时失败|当前不可用|已不可用|目标已变化|无法确认实际数据|上下文已失效|没有足够的本地查询上下文/;
 async function call(text,id=cid){
  const start=performance.now();
  const r=await hass.callWS({type:"conversation/process",text,conversation_id:id,agent_id:agent[0].id,language:"zh-CN"});
  return {text,speech:r.response?.speech?.plain?.speech||"",type:r.response?.response_type,cid_match:r.conversation_id===id,elapsed_ms:Math.round(performance.now()-start)};
 }
 async function check(text,expected,id=cid,allowGap=false){
  const r=await call(text,id);
  r.result=!r.cid_match||r.type==="error"||!r.speech?"fail":allowGap&&routeError.test(r.speech)?"fail":allowGap&&gap.test(r.speech)?"data_gap":expected.test(r.speech)?"pass":"fail";
  report.checks.push(r);
 }
 try{
  await check("燃气剩多少",/燃气.*余额.*元/,cid,true);
  await check("水费还剩几块钱",/水.*余额.*元/,cid,true);
  await check("电费余额还有多少",/电.*余额.*元/,cid,true);
  await check("主卧空调多少度",/设定温度.*检测温度/);
  await check("设定温度",/主卧空调.*设定.*温度/,cid,true);
  await check("次卧呢？",/次卧空调.*设定.*温度/,cid,true);
  await check("主卧现在几度",/主卧.*温度/,cid,true);
  await check("湿度呢？",/主卧.*湿度/,cid,true);
  await check("客厅还有几组灯亮着",/客厅.*(?:灯|组)/,cid,true);
  await check("餐厅呢？",/餐厅.*(?:灯|组)/,cid,true);
  await check("阳台亮不亮",/环境光照度.*灯具/);
  await check("环境光照度",/阳台.*光照度/,cid,true);
  await check("燃气还剩多少方",/剩余气量.*阶梯/);
  await check("第一阶梯",/第一阶梯.*(?:剩|余)/,cid,true);
  await check("2025年2月29日用了几度电",/日期.*无效/);
  await check("去年三月份电费花了多少钱",/电费/,cid,true);
  await check("用量呢",/用电量|度电/,cid,true);
  await check("次卧呢",/上下文|补充查询对象/,other);
  await check("不要查燃气余额",/取消.*查询/);
  await check("exit",/已退出/);
  report.complete=report.checks.length===20;
  report.execution_passed=report.complete&&report.checks.every(r=>r.result!=="fail");
  report.data_gaps=report.checks.filter(r=>r.result==="data_gap").length;
  report.passed=report.execution_passed&&report.data_gaps===0;
 }catch(e){report.error=e.message||String(e)}
 finally{for(const id of [cid,other])try{await call("exit",id)}catch{}}
 window.__nexoraV041Probe=report;
 console.log("========== Nexora v0.4.1-preview 专项验收 ==========");
 console.log(JSON.stringify(report,null,2));
 console.log("========== 验收结束 ==========");
})();
