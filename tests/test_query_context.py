import importlib
import json
import unittest
from datetime import date
from test_semantic_lexicon import BASE,PKG,mod
qp=importlib.import_module(PKG+".query_planner")
ctx=importlib.import_module(PKG+".query_context")
TODAY=date(2026,11,27)

class PlannerContextTests(unittest.TestCase):
    def setUp(self):
        self.now=0
        self.menu=mod.Menu([json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))],
             settings={"secondary":"次住所"})
        self.p=qp.QueryPlanner(self.menu)
        self.c=ctx.QueryContext(self.p,lambda:self.now,max_sessions=2)
    def focus(self,q):
        r=self.p.plan(q,TODAY)
        self.assertIsNotNone(r.plan,r.message)
        self.c.remember("a",r.plan.focus,TODAY,scene=True)
        return self.c.consume("a")
    def ids(self,q,focus,today=TODAY):
        r=self.c.resolve(q,focus,today)
        self.assertIsNotNone(r.plan,r.message)
        return tuple(s.capability for s in r.plan.primary+r.plan.supplements)
    def test_scene_switch_and_metric_refinement(self):
        f=self.focus("主卧空调多少度")
        self.assertEqual(self.ids("次卧呢？",f),("appliance.ac.secondary.target","appliance.ac.secondary.temp"))
        self.assertEqual(self.ids("设定温度",f),("appliance.ac.master.target",))
        self.assertEqual(self.ids("再查一次",f),("appliance.ac.master.target","appliance.ac.master.temp"))
    def test_cross_module_and_account_guard(self):
        f=self.focus("燃气余额")
        self.assertEqual(self.ids("水费呢",f),("utility.water.balance",))
        self.assertEqual(self.ids("门呢",f),("home.access.door.door_all","home.access.door.lock_all","home.access.door.deadbolt_all"))
        f=self.focus("次住所电费余额")
        self.assertIsNone(self.c.resolve("水费呢",f,TODAY).plan)
        self.assertIn("账户",self.c.resolve("水费呢",f,TODAY).message)
    def test_date_inheritance_and_rollover(self):
        f=self.focus("次住所电费去年三月份花了多少钱")
        r=self.c.resolve("用量呢",f,TODAY)
        step,=r.plan.primary
        self.assertEqual(step.capability,"utility.electric.l.history.h_month_usage.h_month_usage_last_year")
        self.assertEqual(dict(step.params),{"month":3})
        r=self.c.resolve("用量呢",f,date(2027,1,1))
        self.assertIsNone(r.plan)
        self.assertIn("账期",r.message)
    def test_consume_expiry_bound_and_late_result(self):
        f=self.focus("燃气余额")
        self.assertTrue(self.c.remember("a",f.frame,TODAY))
        self.assertIsNone(self.c.consume("b"))
        self.assertIsNotNone(self.c.consume("a"))
        self.assertIsNone(self.c.consume("a"))
        self.assertFalse(self.c.remember("a",f.frame,TODAY,current=False))
        for key in ("a","b","c"):
            self.c.remember(key,f.frame,TODAY)
        self.assertLessEqual(len(self.c.entries),2)
        self.now=300
        self.assertIsNone(self.c.consume("c"))
    def test_registered_focus_is_typed_and_no_control_inheritance(self):
        f=self.c.from_registered("utility.electric.l.history.h_month_cost.h_month_cost_explicit",{"year":2024,"month":3},TODAY)
        self.assertEqual(f.account,"l")
        self.assertEqual(f.time.year,2024)
        self.assertEqual(f.metric,"cost")
        f=self.focus("主卧空调多少度")
        for q in ("把空调打开","关灯","讲个故事","空调调到26度"):
            self.assertIsNone(self.c.resolve(q,f,TODAY).plan)

    def test_aggregate_scope_inheritance_from_structured_and_registered(self):
        for initial in (self.focus("我家水电气余额还有多少"),
                        ctx.Focus(self.c.from_registered("utility.summary.primary.balances",{},TODAY),TODAY,300,False)):
            f=initial
            for q,cid in [
                ("有没有欠费的","utility.summary.primary.debts"),
                ("需要充值吗","utility.summary.primary.low"),
                ("所有账户呢","utility.summary.all.low_all"),
                ("余额呢","utility.summary.all.balances_all"),
                ("主住所呢","utility.summary.primary.balances"),
            ]:
                r=self.c.resolve(q,f,TODAY)
                self.assertIsNotNone(r.plan,(q,r.message))
                self.assertEqual(tuple(s.capability for s in r.plan.primary),(cid,))
                f=ctx.Focus(r.plan.focus,TODAY,300,True)
        f=ctx.Focus(self.c.from_registered("utility.summary.all.balances_all",{},TODAY),TODAY,300,False)
        self.assertEqual(self.ids("有没有欠费的",f),("utility.summary.all.debts_all",))
        self.assertIsNone(self.c.resolve("去年余额",f,TODAY).plan)
