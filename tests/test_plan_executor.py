import asyncio
import importlib
import unittest
from types import SimpleNamespace
from test_semantic_lexicon import PKG
bm=importlib.import_module(PKG+".business_model")
qp=importlib.import_module(PKG+".query_planner")
pe=importlib.import_module(PKG+".plan_executor")

def step(metric,family="appliance",target="m"):
    return qp.Step(bm.QueryKey(family,target,metric),metric)
def answer(text,kind="action_done"):
    return SimpleNamespace(error=None,response=SimpleNamespace(as_dict=lambda:{
        "response_type":kind,"speech":{"plain":{"speech":text}}}))
def failure(msg="数据接口异常"):
    return SimpleNamespace(error=msg,response=None)

class PlanExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def test_parallel_primary_keeps_order_and_partial_errors(self):
        p=qp.Plan((step("target"),step("temp")), (step("status"),))
        active=peak=0
        async def dispatch(s):
            nonlocal active,peak
            active+=1
            peak=max(peak,active)
            try:
                await asyncio.sleep(.005 if s.capability=="target" else .001)
                return failure() if s.capability=="temp" else answer(s.capability)
            finally:
                active-=1
        r=await pe.run_plan(p,dispatch,lambda:True)
        self.assertEqual(peak,2)
        self.assertEqual([o.step.capability for o in r.outcomes],["target","temp","status"])
        self.assertEqual([o.kind for o in r.outcomes],["ok","error","ok"])
        self.assertEqual(active,0)

    async def test_stop_only_supplement_and_unknown_is_not_off(self):
        count=step("count_on","lights","ke_ting")
        listing=step("list_on","lights","ke_ting")
        p=qp.Plan((count,),(listing,),("no_lights_on",))
        calls=[]
        async def dispatch(s):
            calls.append(s)
            return answer("客厅当前有0组灯具开启。")
        r=await pe.run_plan(p,dispatch,lambda:True)
        self.assertEqual(calls,[count])
        self.assertEqual(r.outcomes[1].kind,"skipped")
        p=qp.Plan((step("status"),),(step("target"),step("temp")),("device_off",))
        calls.clear()
        async def unknown(s):
            calls.append(s)
            return answer("主卧空调状态无法确认。")
        r=await pe.run_plan(p,unknown,lambda:True)
        self.assertEqual(len(calls),3)
        self.assertEqual(r.outcomes[0].kind,"data_gap")
        calls.clear()
        async def off(s):
            calls.append(s)
            return answer("主卧空调：已关闭。")
        r=await pe.run_plan(p,off,lambda:True)
        self.assertEqual(len(calls),1)
        self.assertEqual([o.kind for o in r.outcomes],["ok","skipped","skipped"])
        # Explicit primary temp must not be suppressed by status.
        p=qp.Plan((step("status"),step("temp")),(step("target"),),("device_off",))
        calls.clear()
        await pe.run_plan(p,off,lambda:True)
        self.assertEqual(len(calls),2)

    async def test_timeout_cancels_and_retains_partial_result(self):
        p=qp.Plan((step("target"),step("temp")))
        active=0
        async def dispatch(s):
            nonlocal active
            if s.capability=="target":
                return answer("主卧空调设定温度：26℃。")
            active+=1
            try:
                await asyncio.sleep(30)
            finally:
                active-=1
        r=await pe.run_plan(p,dispatch,lambda:True,timeout=.02)
        self.assertEqual(active,0)
        self.assertEqual([o.kind for o in r.outcomes],["ok","error"])

    async def test_superseded_generation_blocks_future_calls(self):
        p=qp.Plan((step("target"),step("temp")),(step("status"),))
        current=True
        calls=[]
        async def dispatch(s):
            nonlocal current
            calls.append(s)
            current=False
            return answer("已完成")
        r=await pe.run_plan(p,dispatch,lambda:current,concurrency=1)
        self.assertTrue(r.superseded)
        self.assertEqual(calls,[p.primary[0]])

    async def test_invalid_plan_and_bad_speech(self):
        p=qp.Plan((step("target"),step("target")))
        async def dispatch(s):
            return answer("")
        with self.assertRaises(ValueError):
            await pe.run_plan(p,dispatch,lambda:True)
        r=await pe.run_plan(qp.Plan((step("target"),)),dispatch,lambda:True)
        self.assertEqual(r.outcomes[0].kind,"error")
        self.assertEqual(pe.unpack(step("target"),answer("主卧空调已关闭，无当前运行参数。")).kind,"state_limit")

    async def test_wrong_room_reply_cannot_skip_supplement(self):
        a=step("count_on","lights","ke_ting")
        b=step("list_on","lights","ke_ting")
        p=qp.Plan((a,),(b,),("no_lights_on",))
        async def dispatch(s):
            return answer("餐厅当前有0组灯具开启。")
        r=await pe.run_plan(p,dispatch,lambda:True)
        self.assertEqual([o.kind for o in r.outcomes],["ok","ok"])

    async def test_actual_ha_washer_off_text_stops_only_optional_work(self):
        a,b,c=step("status","appliance","w"),step("phase","appliance","w"),step("remaining","appliance","w")
        p=qp.Plan((a,),(b,c),("device_off","cycle_not_running"))
        calls=[]
        async def dispatch(s):
            calls.append(s)
            return answer("海尔洗衣机已关机。")
        r=await pe.run_plan(p,dispatch,lambda:True)
        self.assertEqual(calls,[a])
        self.assertEqual([o.kind for o in r.outcomes],["ok","skipped","skipped"])
        self.assertEqual(pe.unpack(b,answer("海尔洗衣机已关机，无法确认当前数据。")).kind,"state_limit")
        self.assertNotEqual(pe.unpack(step("temp"),answer("海尔洗衣机已关机，无法确认当前数据。")).kind,"state_limit")

    def test_real_ha_quality_classification(self):
        cases=[
            ("utility","e","h_year_usage","示例甲账户2026年账单累计用电量：1500度（10期有效账单；本月暂无账单）。","partial_data"),
            ("utility","w","h_year_cost","示例水务2025年账单累计水费：18.80元（1期有效账单；缺失或异常月份：1、2、3、4、5、6、7、8、9、10、11月，仅为已知账单合计）。","partial_data"),
            ("utility","g","h_year_usage","华润燃气2025年账单累计用气量：180立方米（10期有效账单；缺失或异常月份：1、8月，仅为已知账单合计）。","partial_data"),
            ("utility","e","h_year_cost","示例甲账户2025年账单累计电费：暂无有效账单数据。","data_gap"),
            ("utility","e","h_day","示例甲账户2026-05-20用电量：数据尚未获取（最新记录：2026-05-19）。","data_gap"),
            ("utility","e","h_day","示例甲账户2026-02-01用电量：超出每日历史覆盖范围（最早记录：2026-04-16）。","data_gap"),
            ("utility","all","balances","示例甲账户电费余额数据不可用；燃气费余额57.25元；水费余额61.50元。","partial_data"),
            ("utility","e","debt","示例甲账户电费：欠费情况暂无法确认。","data_gap"),
            ("home","all","lock","入户门锁：状态无法确认；最近一次事件为上锁（历史记录，不代表当前状态）。","data_gap"),
            ("home","all","family","家庭Wi-Fi：1位成员的设备已连接：成员甲；2位未连接：成员乙、成员丙；未配置：成员丁。Wi-Fi仅供在家判断参考。","capability_limit"),
            ("lights","lights.fixtures.dining_fan","brightness","餐厅风扇灯当前已关闭，无法获取实时亮度。","state_limit"),
            ("appliance","m","temp","主卧空调设备报告室温：18.9℃（空调已关闭，读数可能未实时刷新）。","state_limit"),
            ("appliance","b","target","米家浴霸取暖设定温度：暖风未开启。","state_limit"),
            ("appliance","m","status","主卧空调已关闭。","ok"),
            ("utility","e","h_month_usage","示例甲账户2026年5月用电量：137.08度（截至2026-05-19，26天有效记录）。","ok"),
        ]
        for f,t,m,s,k in cases:
            with self.subTest(s=s):
                self.assertEqual(pe.unpack(step(m,f,t),answer(s)).kind,k)

    def test_quality_annotation_cannot_break_nonstandard_response(self):
        from types import SimpleNamespace
        key=step("balance","utility","g").key
        for data in ({},{"speech":None},{"speech":{"plain":[]}},{"speech":{"plain":{"speech":42}}}):
            self.assertEqual(pe.response_quality(key,SimpleNamespace(as_dict=lambda:data)),"unclassified")
