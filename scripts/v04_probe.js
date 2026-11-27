// v0.4.0-preview: local read-only semantic/menu checks on the target HA.
// Does not test ordinary AI or send control commands.
(async()=>{
 const hass=document.querySelector("home-assistant")?.hass;
 if(!hass)throw Error("找不到 HA 前端");
 const {agents}=await hass.callWS({type:"conversation/agent/list"});
 const agent=agents.filter(x=>x.name==="Nexora");
 if(agent.length!==1)throw Error("未找到唯一 Nexora");
 const cid="nexora-v04:"+crypto.randomUUID(), other="nexora-v04:"+crypto.randomUUID();
 const report={version:"v0.4.0-preview",checks:[],passed:false};
 async function call(text,id=cid,aid=agent[0].id){
  const start=performance.now();
  const r=await hass.callWS({type:"conversation/process",text,conversation_id:id,agent_id:aid,language:"zh-CN"});
  return {text,speech:r.response?.speech?.plain?.speech||"",type:r.response?.response_type,elapsed_ms:Math.round(performance.now()-start),cid_match:r.conversation_id===id};
 }
 async function check(text,expected,id=cid){
  const r=await call(text,id);
  r.passed=r.cid_match&&r.type!=="error"&&expected(r.speech);
  report.checks.push(r);
 }
 const lux=s=>/阳台光照度[：:]\s*\d+(?:\.\d+)?\s*勒克斯/.test(s);
 const clar=s=>s.includes("环境光照度")&&s.includes("灯具");
 try{
  const ref=await call("阳台光照度是多少",cid,"conversation.home_assistant");
  report.native_reference=ref;
  for(const q of ["阳台光照度是多少","阳台光照度","阳台光照强度是多少","阳台的光照度是多少","阳台环境亮度","请问阳台的光照度是多少？"])await check(q,lux);
  for(const q of ["阳台有多亮","阳台亮度是多少"])await check(q,clar);
  await check("按灯具",s=>/^15\. 晾衣架灯$/m.test(s)&&!/^9[89]\. /m.test(s));
  await check("12",s=>s.startsWith("厨房筒灯"));
  await check("0",s=>s.startsWith("按灯具"));
  await check("help",s=>s.includes("智能家庭助手"));
  await check("1",s=>s.includes("水费"));
  await check("水费",s=>s.includes("账户余额"));
  await check("1",s=>s.includes("水费")&&s.includes("余额"));
  await check("上个月呢",s=>s.includes("用量还是费用"));
  await check("用量",s=>s.includes("账单用水量")||s.includes("数据不可用")||s.includes("暂无"));
  await check("费用呢",s=>s.includes("水费")||s.includes("费用")||s.includes("账单"));
  await check("1",s=>s.includes("没有有效菜单"),other);
  await check("exit",s=>s.includes("已退出"));
  await check("上个月呢",s=>s.includes("上下文已失效"));
  report.passed=lux(ref.speech)&&report.checks.every(x=>x.passed);
 }catch(e){report.error=e.message||String(e)}
 finally{for(const id of [cid,other])try{await call("exit",id)}catch{}}
 window.__nexoraV04Probe=report;
 console.log("========== Nexora v0.4.0-preview 专项验收 ==========");
 console.log(JSON.stringify(report,null,2));
 console.log("========== 验收结束 ==========");
})();
