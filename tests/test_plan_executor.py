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
