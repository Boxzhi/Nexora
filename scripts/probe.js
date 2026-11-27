// Nexora v0.3.1-preview: targeted live HA checks, no LLM or device control.
(async()=>{
 const hass=document.querySelector("home-assistant")?.hass;
 if(!hass)throw Error("找不到 HA 前端");
 const list=await hass.callWS({type:"conversation/agent/list"});
 const agent=(list.agents||[]).find(x=>x.name==="Nexora");
 const report={agent:agent?.name,checks:[],passed:false};
 const cid="nexora-test:"+crypto.randomUUID();
 const other="nexora-test:"+crypto.randomUUID();
 const call=async(text,id=cid,aid=agent.id)=>{
  const start=performance.now();
  const r=await hass.callWS({type:"conversation/process",text,conversation_id:id,agent_id:aid,language:hass.language||"zh-CN"});
  return {text,speech:r.response?.speech?.plain?.speech||"",response_type:r.response?.response_type,elapsed_ms:Math.round(performance.now()-start),conversation_id_match:r.conversation_id===id};
 };
 const check=async(text,expect,id=cid)=>{
  const r=await call(text,id);r.passed=r.conversation_id_match&&r.response_type!=="error"&&!!expect&&r.speech.includes(expect);report.checks.push(r);return r;
 };
 try{
  if(!agent)throw Error("未发现 Nexora");
  const native=await call("水费余额是多少",cid,"conversation.home_assistant");
  if(native.response_type==="error"||!native.speech)throw Error("原生水费查询失败");
  report.native_reference=native.speech;
  await check("help","1. ⚡ 水电气");
  await check("帮助","4. 🏠 全屋状态");
  await check("灯光","💡 灯光");
  await check("家电","🔌 家电");
  await check("全屋状态","🏠 全屋状态");
  await check("HELP","2. 💡 灯光");
  await check("1","水费");
  await check("水费","账户余额");
  await check("1",native.speech);
  await check("上个月呢","用量还是费用");
  await check("用量","账单用水量");
  await check("这个月呢","账单用水量");
  await check("帮助","1. ⚡ 水电气");
  await check("1.2.1",native.speech);
  await check("1","没有有效菜单",other);
  await check("88","无效选项");
  await check("0","水电气");
  await check("电费","电费");
  await check("燃气阶梯","下一页");
  await check("9","第三阶梯");
  await check("上一页","下一页");
  await check("水费历史查询","月度用量");
  await check("EXIT","已退出");
  await check("1","没有有效菜单");
  await check("帮助","水电气");
  await check("退出","已退出");
  await check("1","没有有效菜单");
  const family=await check("家庭成员","奶奶");
  family.passed=family.passed&&!family.speech.includes("爷爷");
  const door=await check("门锁及门窗","入户门");
  door.passed=door.passed&&!door.speech.includes("窗户");
  await check("其他设备","马桶盖");
  await check("exit","已退出");
  report.passed=report.checks.every(x=>x.passed);
 }catch(e){report.error=e.message||String(e);}
 console.log("========== Nexora v0.3.1-preview 真实环境验收 ==========");
 console.log(JSON.stringify(report,null,2));
 console.log("========== 验收结束 ==========");
})();
