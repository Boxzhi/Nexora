// Nexora v0.5.4-preview — independent read-only scene traversal.
(async()=>{
 const hass=document.querySelector('home-assistant')?.hass;
 if(!hass)throw Error('找不到 HA 前端');
 if(window.__nexora054Running)throw Error('验收已经运行');
 window.__nexora054Running=true;window.__nexora054Stop=false;
 const report=window.__nexora054Report={version_expected:'0.5.4',requests:0,rows:[],errors:[],skipped_custom_roots:[],complete:false,execution_passed:false,visibility_review_required:true,manual_value_review_required:true};
 const modules=['水电气','灯光','家电','全屋状态'],baseline=[65,37,24,24];
 const footer='回复数字选择，help 返回主菜单，exit 退出菜单。';
 const menu=s=>s.trimEnd().endsWith(footer);
 const choices=s=>[...s.matchAll(/^([1-9]|1[0-9]|20)\.\s+(.+)$/gm)].map(m=>({n:m[1],label:m[2].trim()}));
 const moduleName=s=>modules.find(m=>s===m||s.endsWith(' '+m));
 const parameter=s=>/^请输入/.test(s);
 function classify(r){
  const s=r.speech;
  if(!s||r.type==='error'||menu(s)||parameter(s)||/^(?:输入无效|无效选项|无效数字路径|当前没有有效菜单|该查询(?:已|当前)?不可用|该查询目标已变化|该问句与已安装意图库不匹配|查询参数与已安装意图库不一致|本地严格识别不可用|只读查询配置不可用|本地查询暂时失败|备用对话代理配置错误|会话已更新|该分类暂无已配置)/.test(s)||/对话暂时不可用|AI.{0,12}(?:不可用|失败|超时)|查询未完成|部分查询失败|部分失败|执行失败|查询失败|查询超时/.test(s))return 'error';
  if(/数据不可用|数据尚未获取|数据不足|暂无.{0,8}(账单|数据)|缺失|超出.{0,12}(范围|覆盖)|状态未知|状态无法确认|未提供|无法确认/.test(s))return 'data_gap';
  if(/不支持|未配置/.test(s))return 'capability_limit';
  if(/(?:关机|已关闭).*(?:无法|不判断|无当前运行参数|可能未实时刷新)/s.test(s))return 'state_limit';
  if(/暂未检测到不可用灯具|未检测到异常|未发现异常|无欠费|未检测到浸水|未达到更换提醒阈值|设备未报告故障/.test(s))return 'normal_negative';
  if(/无法|不可用|尚未|异常/.test(s))return 'review';
  return 'reply_received';
 }
 let agent,cid;
 async function call(text,cleanup=false){
  if(!cleanup&&window.__nexora054Stop)throw Error('用户停止');
  if(!cleanup&&++report.requests>3000)throw Error('超过请求上限');
  const start=performance.now(),r=await hass.callWS({type:'conversation/process',text,conversation_id:cid,agent_id:agent.id,language:'zh-CN'});
  if(r.conversation_id!==cid)throw Error('会话 ID 不一致');
  return {speech:r.response?.speech?.plain?.speech||'',type:r.response?.response_type,elapsed_ms:Math.round(performance.now()-start)};
 }
 function requireMenu(r,where){if(r.type==='error'||!menu(r.speech))throw Error('菜单导航失败：'+where+'；'+r.speech);return r.speech;}
 try{
  const list=await hass.callWS({type:'conversation/agent/list'}),agents=(list.agents||[]).filter(a=>a.name==='Nexora');
  if(agents.length!==1)throw Error('未找到唯一 Nexora Agent');
  agent=agents[0];cid='nexora-v054:'+crypto.randomUUID();
  const root=requireMenu(await call('help'),'主菜单');
  if(root.includes('发送 detail 查看完整菜单'))throw Error('仍为旧版双菜单，请核实安装版本');
  if(requireMenu(await call('detail'),'兼容指令')!==root)throw Error('detail 仍开启不同菜单');
  report.compatibility_passed=true;
  const dt=Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:hass.config?.time_zone||'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date()).map(x=>[x.type,x.value]));
  const inputs={'日期（YYYY-MM-DD）':dt.year+'-'+dt.month+'-'+dt.day,'年月（YYYY-MM）':dt.year+'-01','月日（MM-DD）':'01-01','月份（1–12）':'1','年份（2000–2099）':String(Number(dt.year)-1)};
  report.parameters=inputs;
  async function walk(initial,path=[],depth=0){
   if(depth>15)throw Error('菜单深度异常');
   let s=initial,page=0;const seen=new Set();
   while(true){
    if(seen.has(s)||page>=30)throw Error('分页循环：'+path.join(' / '));seen.add(s);
    const entries=choices(s);if(!entries.length&&depth>0)throw Error('空子菜单');
    for(const x of entries){
     if(depth===0&&!moduleName(x.label)){report.skipped_custom_roots.push(x.label);continue;}
     const p=[...path,x.label];let r=await call(x.n),input=null;
     if(r.type!=='error'&&menu(r.speech)){
      await walk(r.speech,p,depth+1);
      let restored=requireMenu(await call('0'),p.join(' / '));
      for(let i=0;i<page;i++)restored=requireMenu(await call('99'),p.join(' / '));
      if(restored!==s)throw Error('菜单数字映射变化：'+p.join(' / '));
      continue;
     }
     if(r.type!=='error'&&parameter(r.speech)){
      const entry=Object.entries(inputs).find(([k])=>r.speech.includes(k));
      if(!entry)throw Error('未知参数提示：'+r.speech);
      input=entry[1];r=await call(input);
     }
     const status=classify(r);
     report.rows.push({module:moduleName(p[0]),path:p.join(' / '),parameter:input,status,...r});
     if(report.rows.length%20===0)console.log('[Nexora 验收进度]',report.rows.length);
     if(status==='error')throw Error('查询路由异常：'+p.join(' / '));
    }
    if(!/^99\. 下一页$/m.test(s))break;
    s=requireMenu(await call('99'),path.join(' / '));page++;
   }
  }
  await walk(root);report.complete=true;
 }catch(e){report.errors.push(e.message||String(e));}
 finally{
  if(agent&&cid){try{const r=await call('exit',true);if(r.type==='error'||!r.speech.includes('已退出'))throw Error(r.speech||'退出无回复');}catch(e){report.errors.push('退出清理：'+e.message);}}
  report.visible=report.rows.length;report.unique_paths=new Set(report.rows.map(r=>r.path)).size;
  report.modules=Object.fromEntries(modules.map((m,i)=>[m,{baseline:baseline[i],visible:report.rows.filter(r=>r.module===m).length}]));
  report.status_counts=Object.fromEntries([...new Set(report.rows.map(r=>r.status))].map(s=>[s,report.rows.filter(r=>r.status===s).length]));
  report.execution_passed=report.complete&&report.compatibility_passed&&!report.errors.length&&report.visible>0&&report.unique_paths===report.visible&&!report.status_counts.error&&Object.values(report.modules).every(m=>m.visible<=m.baseline);
  report.visibility_review_required=Object.values(report.modules).some(m=>m.visible!==m.baseline)||report.skipped_custom_roots.length>0;
  window.__nexora054Running=false;
  console.log('========== Nexora v0.5.4-preview 全量场景只读验收 ==========');console.log(JSON.stringify(report,null,2));
 }
})();
