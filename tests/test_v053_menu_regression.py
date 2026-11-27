"""Scene/menu regression against the complete unchanged catalog and HA doubles."""
import json
import unittest
from collections import Counter
from datetime import date
from types import SimpleNamespace
from importlib import import_module
from time import perf_counter
from unittest.mock import AsyncMock
from test_menu import mod, BASE, SET
from nexora_menu_test.scene_layout import build_layout
from nexora_menu_test.query_planner import QueryPlanner
from nexora_menu_test.query_context import QueryContext
from nexora_menu_test.plan_executor import Outcome,stop_supplements
import test_planner_adapter as adapter

TODAY=date(2026,11,27)
CATS=[json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))]
INPUTS={"month":"3","year":"2024","year_month":"2024-03","date":"2024-03-09","month_day":"03-09"}
PARAMS={"year":2024,"month":3,"day":9}
def path_for(menu,node,root,available=lambda c:True):
    parts=[]
    while node!=root:
        parent=menu.items[node].parent
        choices=[i.id for i in menu.children[parent] if menu._available(i.id,available)]
        parts.append(str(choices.index(node)+1))
        node=parent
    return ".".join(reversed(parts))

class CompleteMenuTests(unittest.TestCase):
    def setUp(self):
        self.menu=mod.Menu(CATS,settings=SET)
        self.original=dict(self.menu.capabilities)
        self.menu.install_scene_layout(build_layout(self.menu))
        self.p=QueryPlanner(self.menu)
    def test_every_scene_and_original_menu_path(self):
        counts=Counter()
        dispatches=0
        started=perf_counter()
        for root,command,items in [("scene","help",self.menu.scenes),("root","detail",self.menu.capabilities)]:
            for cid in items:
                with self.subTest(cid=cid):
                    if root=="scene":
                        self.menu.route("s",command,today=TODAY)
                    else:
                        # Internal regression only: never expose legacy menu via HA.
                        self.menu._render("s","root",lambda c:True)
                    result=self.menu.route("s",path_for(self.menu,cid,root),today=TODAY)
                    cap=self.menu._parameter_cap(cid)
                    if cap.get("parameter"):
                        self.assertIn("请输入",result.text)
                        result=self.menu.route("s",INPUTS[cap["parameter"]],today=TODAY)
                    if root=="scene":
                        self.assertEqual(result.scene,cid)
                        plan=self.p.menu_plan(cid,dict(result.params),lambda c:True,None,TODAY)
                        self.assertEqual(set(s.capability for s in plan.primary+plan.supplements),set(items[cid].members))
                        dispatches+=len(plan.primary+plan.supplements)
                    else:
                        self.assertEqual(result.capability,cid)
                    counts[root]+=1
        self.assertEqual(counts,{"scene":150,"root":443})
        self.assertEqual(self.menu.capabilities,self.original)
        print("V053_MENU_PATHS="+json.dumps({"scene":counts["scene"],"detail":counts["root"],"planned_members":dispatches,"elapsed_ms":round((perf_counter()-started)*1000,2)}))
    def test_visibility_previous_real_profile(self):
        hidden={"home.family.person_grandfather","home.access.door.windows_all"}
        for f in ("living_ceiling","living_spot","living_strip","master_ceiling","secondary_ceiling","child_ceiling","entry_downlight","hall_downlight","kitchen_downlight"):
            hidden.update("lights.fixtures."+f+"."+a for a in ("brightness","temperature"))
        for f in ("bath_panel","bath_heater","airer"):
            hidden.add("lights.fixtures."+f+".temperature")
        visible=lambda c:c["id"] not in hidden
        self.assertEqual(len(hidden),23)
        self.assertEqual(sum(self.menu._available(cid,visible) for cid in self.menu.capabilities),420)
        self.assertEqual(sum(self.menu._available(cid,visible) for cid in self.menu.scenes),149)
        for cid in self.menu.scenes:
            if self.menu._available(cid,visible):
                cap=self.menu._parameter_cap(cid)
                params={k:PARAMS[k] for k in cap.get("parameter_slots",{})}
                plan=self.p.menu_plan(cid,params,visible,None,TODAY)
                self.assertFalse(set(s.capability for s in plan.primary+plan.supplements)&hidden)
        print("V053_VISIBILITY="+json.dumps({"baseline_registered":443,"visible_detail":420,"visible_scenes":149,"hidden_detail":23}))
    def test_custom_navigation_and_detail_mode(self):
        custom={"schema_version":1,"module":{"id":"extra","name":"额外模块","order":500},"categories":[{"id":"extra.info","name":"额外信息","order":10}],"capabilities":[{"id":"extra.info.read","category":"extra.info","name":"状态","sentence":"额外状态如何","intent":"ExtraQuery","slots":{},"read_only":True,"order":10}]}
        menu=mod.Menu(CATS+[custom],settings=SET)
        menu.install_scene_layout(build_layout(menu))
        self.assertIn("5. 额外模块",menu.route("a","help").text)
        self.assertIn("额外模块",menu.route("a","5").text)
        self.assertIn("额外信息",menu.route("a","1").text)
        self.assertEqual(menu.route("a","1").capability,"extra.info.read")
        self.assertIn("额外模块",menu.route("a","0").text)
        root=menu.route("a","0").text
        self.assertNotIn("发送 detail",root)
        self.assertIsNone(menu.route("a","detail"))
        self.assertIsNone(menu.route("a","完整菜单"))
        self.assertEqual(menu.route("a","help").text,root)
        self.assertIn("各阶梯详细数据",menu.route("a","燃气阶梯").text)
        self.assertIsNone(menu.navigation_alias("单个设备电量",menu.sessions["a"]))
        menu._render("internal","root",lambda c:True)
        self.assertIn("第三阶梯",menu.route("internal","燃气阶梯").text)
        menu.route("b","help")
        self.assertIn("各阶梯详细数据",menu.route("b","燃气阶梯").text)
    def test_invalid_params_and_cancel(self):
        with self.assertRaises(ValueError):
            self.p.menu_plan("scene.utility.electric.j.monthly.explicit",{"year":2027,"month":1},lambda c:True,None,TODAY)
        with self.assertRaises(ValueError):
            self.p.menu_plan("scene.utility.electric.j.monthly.explicit",{"year":2026,"month":True},lambda c:True,None,TODAY)
        self.menu.route("a","help")
        self.assertIn("请输入",self.menu.route("a",path_for(self.menu,"scene.utility.electric.j.monthly.explicit","scene"),today=TODAY).text)
        self.assertIn("指定年月",self.menu.route("a","0",today=TODAY).text)
        self.assertIsNone(self.menu.sessions["a"].pending)
    def test_scene_context_rollover_and_no_anchor(self):
        ctx=QueryContext(self.p,lambda:0)
        ctx.remember("a",None,TODAY,scene=True,menu_scene="scene.home.access.curtains")
        f=ctx.consume("a")
        self.assertEqual(len(ctx.resolve_menu("再查一次",f,TODAY,lambda c:True).plan.primary),3)
        self.assertIsNone(ctx.resolve("其他账户呢",f,TODAY).plan)
        self.assertIn("日期已变化",ctx.resolve_menu("再查一次",f,date(2026,11,28),lambda c:True).message)
    def test_contradictory_washer_power_cannot_skip(self):
        plan=self.p.menu_plan("scene.appliance.washer.progress",{},lambda c:True,None,TODAY)
        rows=(Outcome(plan.primary[0],"ok","海尔洗衣机已关机。"),Outcome(plan.primary[1],"ok","海尔洗衣机已开机。"))
        self.assertFalse(stop_supplements(plan,rows))

class CompleteSceneAgentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        adapter.PlannerAdapterTests.setUp(self)
        self.menu.install_scene_layout(import_module("nexora_adapter_test.scene_layout").build_layout(self.menu))
        targets={}
        for cap in self.menu.capabilities.values():
            if not cap.get("native_slots"):
                continue
            target=targets.setdefault(cap["category"],"light.mock_"+cap["category"].rsplit(".",1)[-1])
            query=self.menu._query(cap["id"],{})
            self.by_sentence[query.sentence]=(cap,{**query.slots,"luxe_light_id":target})
        self.agent.hass=SimpleNamespace(states={v:SimpleNamespace(state="on",attributes={"supported_color_modes":["color_temp"]}) for v in targets.values()})
        self.agent.resolver.replace_targets("zh-CN",targets)
    async def ask(self,q,cid="a"):
        return await adapter.PlannerAdapterTests.ask(self,q,cid)
    async def test_all_150_scene_dispatches_through_agent(self):
        count=0
        members=0
        for cid,spec in self.menu.scenes.items():
            with self.subTest(scene=cid):
                await self.ask("help")
                self.calls.clear()
                r=await self.ask(path_for(self.menu,cid,"scene"))
                cap=self.menu._parameter_cap(cid)
                if cap.get("parameter"):
                    self.assertIn("请输入",r)
                    r=await self.ask(INPUTS[cap["parameter"]])
                self.assertEqual(Counter(self.calls),Counter(spec.members),(cid,r))
                self.assertNotIn("查询未完成",r)
                count+=1
                members+=len(self.calls)
        self.assertEqual(count,150)
        self.conv.async_converse.assert_not_awaited()
        print("V053_AGENT_SCENES="+json.dumps({"scenes":count,"member_dispatches":members}))
    async def test_repeat_period_scope_and_exit(self):
        await self.ask("help")
        await self.ask(path_for(self.menu,"scene.utility.electric.j.monthly.explicit","scene"))
        await self.ask("2024-03")
        self.calls.clear()
        await self.ask("再查一次")
        self.assertEqual(Counter(self.calls),Counter(self.menu.scenes["scene.utility.electric.j.monthly.explicit"].members))
        self.calls.clear()
        await self.ask("上月呢")
        self.assertEqual(Counter(self.calls),Counter(self.menu.scenes["scene.utility.electric.j.monthly.previous"].members))
        await self.ask("help")
        await self.ask(path_for(self.menu,"scene.utility.summary.primary.overview","scene"))
        self.calls.clear()
        await self.ask("所有账户呢")
        self.assertEqual(Counter(self.calls),Counter(self.menu.scenes["scene.utility.summary.all.overview"].members))
        self.calls.clear()
        await self.ask("有没有欠费的")
        self.assertEqual(self.calls,["utility.summary.all.debts_all"])
        await self.ask("exit")
        self.calls.clear()
        self.assertIn("上下文",await self.ask("有没有欠费的"))
        self.assertFalse(self.calls)
        self.conv.async_converse.assert_not_awaited()
    async def test_help_and_independent_natural_language(self):
        await self.ask("help")
        self.menu._render(("u",None,None,"a"),"root",lambda c:True)
        self.calls.clear()
        await self.ask(path_for(self.menu,"utility.gas.basic.balance","root"))
        self.assertEqual(self.calls,["utility.gas.basic.balance"])
        self.calls.clear()
        await self.ask("我家水电气余额还有多少")
        self.assertEqual(self.calls,["utility.summary.primary.balances"])
        self.calls.clear()
        await self.ask("有没有欠费的")
        self.assertEqual(self.calls,["utility.summary.primary.debts"])
        self.conv.async_converse.assert_not_awaited()
    async def test_stale_recognition_cannot_dispatch(self):
        await self.ask("help")
        original=self.native.async_recognize_intent.side_effect
        async def recognize(u,**kw):
            self.menu.followups.begin(("u",None,None,"a"))
            return await original(u,**kw)
        self.native.async_recognize_intent=AsyncMock(side_effect=recognize)
        self.calls.clear()
        r=await self.ask(path_for(self.menu,"scene.utility.water.balance","scene"))
        self.assertFalse(self.calls)
        self.assertIn("会话已更新",r)
