import importlib
import json
import unittest
from datetime import date
from test_semantic_lexicon import BASE,PKG,mod

class ContextTests(unittest.TestCase):
    def setUp(self):
        self.now=0
        self.today=date(2026,11,27)
        self.m=mod.Menu([json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))],
            settings={"secondary":"次住所"},clock=lambda:self.now)
        self.f=self.m.followups
        self.s=importlib.import_module(PKG+".semantic").SemanticIndex(self.m)
    def route(self,text,key="a",available=lambda c:True,today=None):
        return self.m.route(key,text,available,today or self.today)
    def remember(self,cid,params=None):
        self.f.remember("a",cid,params,self.today)
    def test_four_families_switch_targets_and_metrics(self):
        cases=[
            ("home.env.master.temp_master","湿度呢","home.env.master.hum_master"),
            ("home.env.master.hum_master","次卧呢","home.env.secondary.hum_secondary"),
            ("home.family.person_father","妈妈呢","home.family.person_mother"),
            ("home.access.door.lock_all","关闭状态","home.access.door.door_all"),
            ("lights.rooms.ke_ting.list_on","开启数量呢","lights.rooms.ke_ting.count_on"),
            ("lights.rooms.ke_ting.count_on","餐厅呢","lights.rooms.can_ting.count_on"),
            ("lights.fixtures.master_ceiling.single_state","亮度呢","lights.fixtures.master_ceiling.brightness"),
            ("appliance.ac.master.status","调的几度","appliance.ac.master.target"),
            ("appliance.ac.master.target","现在屋里几度","appliance.ac.master.temp"),
            ("appliance.ac.master.temp","次卧呢","appliance.ac.secondary.temp"),
            ("appliance.washer.phase","还要多久呢","appliance.washer.remaining"),
            ("utility.electric.j.basic.balance","另一个账户呢","utility.electric.l.basic.balance"),
        ]
        for source,q,target in cases:
            with self.subTest(q=q,source=source):
                self.remember(source)
                self.assertEqual(self.route(q).capability,target)
    def test_clarification_choices_and_alias_priority(self):
        cases=[("主卧空调多少度","设定温度","appliance.ac.master.target"),
               ("大门好了吗","反锁状态","home.access.door.deadbolt_all"),
               ("阳台有多亮","环境光照度","home.presence.balcony.lux_balcony"),
               ("上个月花了多少","水费","utility.water.history.history_cost.history_cost_previous"),
               ("燃气还剩多少方","第一阶梯","utility.gas.tier.tier1_price")]
        # Resolve the actual tier ID by slots, never by guessed identifier.
        for q,answer,target in cases:
            if q.startswith("燃气"):
                target=next(c["id"] for c in self.m.capabilities.values() if c["slots"].get("utility_metric")=="tier1_remaining")
            match=self.s.match(q,self.today)
            with self.subTest(q=q):
                token=self.f.begin("a")
                self.assertTrue(self.f.remember_clarification("a",token,match.options))
                self.assertEqual(self.route(answer).capability,target)
    def test_parameter_inheritance_and_year_rollover(self):
        cid="utility.electric.j.history.h_month_usage.h_month_usage_explicit"
        self.remember(cid,{"year":2024,"month":3})
        q=self.route("费用呢")
        self.assertEqual(q.slots["utility_metric"],"h_month_cost")
        self.assertEqual(q.slots["luxe_utility_year"],2024)
        self.assertEqual(q.slots["luxe_utility_month"],3)
        self.remember(q.capability,{"year":2024,"month":3})
        q=self.route("另一个账户呢")
        self.assertEqual(q.slots["luxe_utility_property"],"l")
        self.assertEqual(q.slots["luxe_utility_month"],3)
        self.remember("utility.water.history.history_cost.history_cost_year",{"month":3})
        self.assertIn("年份已变化",self.route("用量呢",today=date(2027,1,1)).text)
    def test_isolation_expiry_unavailable_and_cancel(self):
        self.remember("appliance.ac.master.status")
        self.assertIn("失效",self.route("次卧呢","b").text)
        self.assertIn("不可用",self.route("调的几度",available=lambda c:False).text)
        self.remember("home.env.master.temp_master")
        self.now=300
        self.assertIn("失效",self.route("次卧呢").text)
        match=self.s.match("主卧空调多少度",self.today)
        token=self.f.begin("a")
        self.f.remember_clarification("a",token,match.options)
        self.route("exit")
        self.assertIsNone(self.route("设定温度").capability if self.route("设定温度") else None)
    def test_no_cross_family_guess_and_generation(self):
        self.remember("appliance.ac.master.temp")
        self.assertIsNone(self.route("洗衣机呢").capability)
        self.remember("home.env.master.temp_master")
        self.assertIsNone(self.route("亮度呢").capability)
        old=self.f.begin("a")
        newer=self.f.begin("a")
        self.assertFalse(self.f.complete("a",old,"home.family.person_father"))
        self.assertTrue(self.f.complete("a",newer,"home.family.person_mother"))
        self.assertEqual(self.route("爸爸呢").capability,"home.family.person_father")
    def test_independent_question_clears_context_and_clarification(self):
        self.remember("home.env.master.temp_master")
        self.assertIsNone(self.route("讲个故事"))
        self.assertIn("失效",self.route("次卧呢").text)
        match=self.s.match("主卧空调多少度",self.today)
        self.f.remember_clarification("a",self.f.begin("a"),match.options)
        self.assertIsNone(self.route("讲个故事"))
        self.assertFalse(self.f.clarifications)

    def test_temperature_meanings_are_not_interchangeable(self):
        for source,question in (("appliance.washer.status","室温呢"),
                                ("appliance.purifier.status","检测温度呢"),
                                ("appliance.ac.master.status","水温呢"),
                                ("appliance.washer.status","出水温度呢")):
            with self.subTest(source=source,question=question):
                self.remember(source)
                r=self.route(question)
                self.assertIsNone(r.capability)
                self.assertIn("此含义",r.text)
        self.remember("appliance.fan.status")
        self.assertEqual(self.route("风速呢").capability,"appliance.fan.speed")
        self.remember("appliance.ac.master.temp")
        self.assertEqual(self.route("开关状态呢").capability,"appliance.ac.master.status")
