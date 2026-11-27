// Nexora v0.3.0-preview — full read-only menu traversal.
(async()=>{
 const hass=document.querySelector("home-assistant")?.hass;
 if(!hass)throw Error("找不到 HA 前端");
 const list=await hass.callWS({type:"conversation/agent/list"});
 const agents=(list.agents||[]).filter(x=>x.name==="Nexora");
 if(agents.length!==1)throw Error("未找到唯一 Nexora 代理");
 const agent=agents[0],cid="nexora-full-probe:"+crypto.randomUUID();
 const footer="回复数字选择，help 返回主菜单，exit 退出菜单。";
 const expected={"⚡ 水电气":136,"💡 灯光":144,"🔌 家电":78,"🏠 全屋状态":85};
 const report={agent:agent.name,registered_baseline:443,requests:0,queries:[],navigation_errors:[],complete:false,passed:false};
 window.__nexoraFullProbe=report;window.__nexoraFullProbeStop=false;
 const dt=Object.fromEntries(new Intl.DateTimeFormat("en-CA",{timeZone:hass.config.time_zone||"Asia/Shanghai",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date()).map(x=>[x.type,x.value]));
 const inputs={"日期（YYYY-MM-DD）":dt.year+"-"+dt.month+"-"+dt.day,"年月（YYYY-MM）":dt.year+"-01","月日（MM-DD）":"01-01","月份（1–12）":"1","年份（2000–2099）":String(Number(dt.year)-1)};
 report.test_parameters=inputs;
 const isMenu=s=>s.trimEnd().endsWith(footer);
 const choices=s=>[...s.matchAll(/^([1-8])\.\s+(.+)$/gm)].map(m=>({n:m[1],label:m[2].trim()}));
 const isParam=s=>/^请输入/.test(s);
 const failure=s=>/^(该问句与已安装意图库不匹配|查询参数与已安装意图库不一致|本地严格识别不可用|只读查询配置不可用|本地查询暂时失败|该查询已不可用|该查询目标已变化|当前没有有效菜单|无效选项|输入无效|备用对话代理配置错误|该分类暂无已配置)/.test(s);
 function classify(s){
  if(/不支持|未配置/.test(s))return "capability_limit";
  if(/数据不可用|数据尚未获取|超出.{0,10}(范围|覆盖)|暂无.{0,8}(账单|数据)|数据不足|缺失或异常月份|状态未知|状态无法确认|未提供|未识别到|欠费情况暂无法确认/.test(s))return "data_gap";
  if(/已关闭.{0,12}无法获取|关机.{0,20}(无法|不判断)|未处于色温模式/.test(s))return "state_limit";
  if(/暂无|未检测到|没有|无欠费|未报告/.test(s))return "normal_negative";
  if(/无法|不可用|尚未|缺失/.test(s))return "review";
  return "ok";
 }
 async function call(text){
  if(window.__nexoraFullProbeStop)throw Error("用户已停止测试");
  if(++report.requests>2400)throw Error("超过请求上限");
  const start=performance.now();
  const r=await hass.callWS({type:"conversation/process",text,conversation_id:cid,agent_id:agent.id,language:hass.language||"zh-CN"});
  if(r.conversation_id!==cid)throw Error("会话 ID 不一致");
  return {speech:r.response?.speech?.plain?.speech||"",type:r.response?.response_type,elapsed_ms:Math.round(performance.now()-start)};
 }
 function menu(r,path){if(r.type==="error"||!isMenu(r.speech))throw Error("菜单导航失败："+path+"；"+r.speech);return r.speech}
 function record(r,path,parameter=null){
  const speech=r.speech;
  const status=!speech||failure(speech)||r.type==="error"||isParam(speech)||isMenu(speech)?"error":classify(speech);
  report.queries.push({path,parameter,status,response_type:r.type,elapsed_ms:r.elapsed_ms,speech});
  if(status==="error")console.warn("[查询异常]",path,speech);
  if(report.queries.length%20===0)console.log("[Nexora 进度]",report.queries.length,"（动态可见）");
 }
 async function walk(initial,path=[],depth=0){
  if(depth>15)throw Error("菜单深度异常");
  let page=0,s=initial;const seen=new Set();
  while(true){
   if(seen.has(s)||page>=30)throw Error("分页循环："+path.join(" / "));
   seen.add(s);const entries=choices(s);if(!entries.length)throw Error("空菜单："+path.join(" / "));
   for(const x of entries){
    const next=[...path,x.label],r=await call(x.n);
    if(r.type!=="error"&&isMenu(r.speech)){
     await walk(r.speech,next,depth+1);
     let restored=menu(await call("0"),path.join(" / "));
     for(let i=0;i<page;i++)restored=menu(await call("9"),path.join(" / "));
     if(restored!==s)throw Error("返回后数字映射变化");
    }else if(isParam(r.speech)){
     const input=Object.entries(inputs).find(([k])=>r.speech.includes(k));
     if(!input)throw Error("未知参数提示："+r.speech);
     const result=await call(input[1]);record(result,next.join(" / "),input[1]);
     if(isParam(result.speech)||/^输入无效/.test(result.speech)){
      if(menu(await call("0"),path.join(" / "))!==s)throw Error("取消参数后菜单映射变化");
     }
    }else{
     record(r,next.join(" / "));
     if(/^该查询已不可用/.test(r.speech))throw Error("运行期间能力变化");
    }
   }
   if(!/^9\. 下一页$/m.test(s))break;
   s=menu(await call("9"),path.join(" / "));page++;
  }
 }
 console.log("========== Nexora v0.3.0-preview 全量只读验收 ==========");
 try{
  const root=menu(await call("help"),"主菜单");
  report.visible_modules=choices(root).map(x=>x.label);
  await walk(root);report.complete=true;
 }catch(e){report.navigation_errors.push(e.message||String(e))}
 const summarize=rows=>({total:rows.length,...Object.fromEntries(["ok","normal_negative","state_limit","capability_limit","data_gap","review","error"].map(s=>[s,rows.filter(x=>x.status===s).length]))});
 report.modules=Object.fromEntries(Object.entries(expected).map(([name,n])=>[name,{expected:n,...summarize(report.queries.filter(x=>x.path.startsWith(name+" / ")))}]));
 report.summary=summarize(report.queries);
 report.unique_paths=new Set(report.queries.map(x=>x.path)).size;
 report.not_visible=443-report.summary.total;
 report.visibility_review_required=report.not_visible!==0||report.visible_modules?.length!==4;
 report.execution_passed=report.complete&&report.summary.total>0&&report.summary.error===0&&report.unique_paths===report.summary.total&&Object.values(report.modules).every(x=>x.total<=x.expected);
 report.passed=report.execution_passed&&!report.visibility_review_required;
 // When menus are filtered, execution_passed is not proof that every omitted leaf was correctly hidden.
 if(!window.__nexoraFullProbeStop)try{await call("exit")}catch(e){report.cleanup_error=e.message||String(e)}
 console.log(JSON.stringify(report,null,2));console.log("========== 验收结束 ==========");
})();
