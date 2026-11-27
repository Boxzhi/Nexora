// Nexora v0.5.4-preview — local scene and follow-up smoke test.
(async()=>{
 const hass=document.querySelector('home-assistant')?.hass;
 if(!hass)throw Error('找不到 HA 前端');
 const list=await hass.callWS({type:'conversation/agent/list'}),agents=(list.agents||[]).filter(a=>a.name==='Nexora');
 if(agents.length!==1)throw Error('未找到唯一 Nexora Agent');
 const agent=agents[0],cid='nexora-v054-smoke:'+crypto.randomUUID(),other='nexora-v054-smoke:'+crypto.randomUUID();
 const report=window.__nexora054Smoke={version_expected:'0.5.4',checks:[],errors:[],structural_passed:false,manual_value_review_required:true};
 const menu=s=>s.trimEnd().endsWith('回复数字选择，help 返回主菜单，exit 退出菜单。');
 const choices=s=>[...s.matchAll(/^([1-9]|1[0-9]|20)\.\s+(.+)$/gm)].map(m=>({n:m[1],label:m[2].trim()}));
 async function ask(text,id=cid){
  const start=performance.now(),r=await hass.callWS({type:'conversation/process',text,conversation_id:id,agent_id:agent.id,language:'zh-CN'});
  if(r.conversation_id!==id)throw Error('会话 ID 不一致');
  return {speech:r.response?.speech?.plain?.speech||'',type:r.response?.response_type,elapsed_ms:Math.round(performance.now()-start)};
 }
 function usable(r){return !!r.speech&&r.type!=='error'&&!menu(r.speech)&&!/^请输入|^无效|^输入无效|^当前没有有效菜单|^该查询|^本地.*失败|^会话已更新/.test(r.speech)&&!/对话暂时不可用|AI.{0,12}(?:不可用|失败|超时)|查询未完成|查询失败|查询超时|部分失败|缺少.*上下文|没有.*上下文/.test(r.speech);}
 function save(name,r,ok){report.checks.push({name,passed:!!ok,...r});}
 async function select(path){
  let r=await ask('help');
  for(const label of path){
   if(!menu(r.speech))throw Error('提前进入查询：'+label);
   const found=choices(r.speech).filter(x=>x.label===label||x.label.endsWith(' '+label));
   if(found.length!==1)throw Error('路径不存在或不唯一：'+label);
   r=await ask(found[0].n);
  }
  return r;
 }
 try{
  const root=await ask('help');save('help 唯一场景菜单',root,menu(root.speech)&&!root.speech.includes('发送 detail 查看完整菜单'));
  if(!report.checks.at(-1).passed)throw Error('菜单预检失败');
  let r=await ask('detail');save('旧 detail 仅返回同一菜单',r,r.speech===root.speech);
  if(!report.checks.at(-1).passed)throw Error('兼容指令仍开启旧菜单');
  const cases=[
   ['我家水电气账户概况',['水电气','综合查询','主住所','账户概况']],
   ['所有账户概况',['水电气','综合查询','全部账户','账户概况']],
   ['全屋照明概况',['灯光','全屋照明概况']],
   ['洗衣机当前洗衣进度',['家电','洗衣机','当前洗衣进度']],
   ['全屋环境温湿度',['全屋状态','环境温湿度','全屋环境']]
  ];
  for(const [q,path] of cases){
   try{
    const byMenu=await select(path);save('菜单：'+q,byMenu,usable(byMenu));
    await ask('exit');const byLanguage=await ask(q);
    const title=s=>s.split('\n')[0].trim();
    save('自然语言：'+q,byLanguage,usable(byLanguage)&&usable(byMenu)&&title(byLanguage.speech)===title(byMenu.speech));
   }catch(e){report.checks.push({name:q,passed:false,error:e.message,visibility_review_required:true});}
  }
  await ask('exit');
  for(const q of ['我家水电气余额还有多少','有没有欠费的','需要充值吗','所有账户呢','余额呢']){
   r=await ask(q);save('连续追问：'+q,r,usable(r)&&!/请先明确|请先查询/.test(r.speech));
  }
  r=await ask('exit');save('退出',r,r.speech.includes('已退出'));
  r=await ask('1',other);save('独立会话无菜单',r,r.speech.includes('没有有效菜单'));
  r=await ask('1',cid);save('退出后无菜单',r,r.speech.includes('没有有效菜单'));
  report.structural_passed=report.checks.every(x=>x.passed);
 }catch(e){report.errors.push(e.message||String(e));}
 finally{
  for(const id of [cid,other])try{await ask('exit',id);}catch(e){report.errors.push('退出清理：'+e.message);}
  if(report.errors.length)report.structural_passed=false;
  console.log('========== Nexora v0.5.4-preview 场景专项验收 ==========');console.log(JSON.stringify(report,null,2));
 }
})();
