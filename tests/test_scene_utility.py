import unittest
import json
from datetime import date
from test_menu import mod, BASE, SET
from nexora_menu_test.scene_layout import utility_layout
from nexora_menu_test.query_planner import QueryPlanner

class UtilitySceneTests(unittest.TestCase):
    def setUp(self):
        self.m=mod.Menu([json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))],settings=SET)
        self.m.install_scene_layout(utility_layout())
        self.p=QueryPlanner(self.m)
        self.today=date(2026,11,27)
    def ask(self,q,**kw):
        return self.m.route("a",q,today=self.today,**kw)
    def test_covers_all_utility_capabilities(self):
        used={cid for spec in self.m.scenes.values() for cid in spec.members}
        self.assertEqual(used,{cid for cid in self.m.capabilities if cid.startswith("utility.")})
        self.assertEqual(len(self.m.scenes),65)
    def test_payment_menu_and_data(self):
        r=self.ask("燃气缴费")
        self.assertIn("1. 最近缴费记录",r.text)
        self.assertIn("2. 年度缴费统计",r.text)
        self.assertNotIn("3.",r.text)
        q=self.ask("1")
        plan=self.p.menu_plan(q.scene,dict(q.params),lambda c:True,None,self.today)
        self.assertEqual([s.capability.rsplit(".",1)[1] for s in plan.primary],["last_pay","last_pay_date","last_pay_channel","payment_update"])
    def test_shared_date_and_return(self):
        self.ask("help")
        self.assertIn("指定年月",self.ask("1.1.1.6").text)
        self.assertIn("YYYY-MM",self.ask("5").text)
        self.assertIn("无效",self.ask("2027-01").text)
        q=self.ask("2026-10")
        plan=self.p.menu_plan(q.scene,dict(q.params),lambda c:True,None,self.today)
        self.assertEqual(len(plan.primary),2)
        for s in plan.primary:
            self.assertEqual(dict(s.params),{"year":2026,"month":10})
        self.assertIn("主账户",self.ask("0").text)
    def test_old_menu_retains_original_paths(self):
        self.assertEqual(self.ask("detail").text,self.ask("help").text)
        self.m._render("a","root",lambda c:True)
        self.assertIn("余额及基本查询",self.ask("1.1.1").text)
    def test_tiers_stay_bounded(self):
        self.ask("燃气阶梯")
        q=self.ask("2")
        plan=self.p.menu_plan(q.scene,{},lambda c:True,None,self.today)
        self.assertEqual(len(plan.primary),11)
