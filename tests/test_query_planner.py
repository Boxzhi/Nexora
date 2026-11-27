import importlib
import json
import unittest
from datetime import date
from test_semantic_lexicon import BASE,PKG,mod
qp=importlib.import_module(PKG+".query_planner")
TODAY=date(2026,11,27)

class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.menu=mod.Menu([json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))],
             settings={"primary_label":"主账户","secondary_label":"第二账户","secondary":"次住所"})
        self.p=qp.QueryPlanner(self.menu)
    def ids(self,text):
        r=self.p.plan(text,TODAY)
        self.assertIsNotNone(r.plan,(text,r.message))
        return tuple(x.capability for x in r.plan.primary+r.plan.supplements)
    def test_default_goals_and_existing_aggregates(self):
        cases={
            "天燃气余额":("utility.gas.basic.balance",),
            "能不能帮我看看家里的燃气费还剩下多少钱":("utility.gas.basic.balance",),
            "主卧空条多少度":("appliance.ac.master.target","appliance.ac.master.temp"),
            "空调现在多少度":("appliance.ac.all.target","appliance.ac.all.temp"),
            "燃气还剩多少立方米":("utility.gas.tier.tier1_remaining","utility.gas.tier.tier2_remaining"),
            "水费需要交了吗":("utility.water.debt","utility.water.balance"),
            "我想知道洗衣机目前怎么样":("appliance.washer.status","appliance.washer.phase","appliance.washer.remaining"),
            "净水器怎么样":("appliance.purifier.status","appliance.purifier.filters","appliance.purifier.replace"),
            "客厅灯光情况":("lights.rooms.ke_ting.count_on","lights.rooms.ke_ting.list_on"),
            "大门关好了吗":("home.access.door.door_all","home.access.door.lock_all","home.access.door.deadbolt_all"),
            "家里有人吗":("home.family.family_all",),
            "阳台亮不亮":("home.presence.balcony.lux_balcony","lights.rooms.yang_tai.list_on"),
        }
        for q,expected in cases.items():
            with self.subTest(q=q):
                self.assertEqual(self.ids(q),expected)
    def test_time_account_and_dimension_mapping(self):
        cases=[
          ("次住所电费去年三月份花了多少钱","utility.electric.l.history.h_month_cost.h_month_cost_last_year",{"month":3}),
          ("2024年3月燃气费花了多少钱","utility.gas.history.h_month_cost.h_month_cost_explicit",{"year":2024,"month":3}),
          ("今年三月份水费用了多少吨","utility.water.history.history_usage.history_usage_year",{"month":3}),
          ("2024年2月29日电费用了几度电","utility.electric.j.history.day.h_day_explicit",{"year":2024,"month":2,"day":29}),
          ("电费昨天用量多少","utility.electric.j.history.day.h_day_yesterday",{}),
        ]
        for q,cid,params in cases:
            with self.subTest(q=q):
                r=self.p.plan(q,TODAY)
                self.assertIsNotNone(r.plan,r.message)
                step,=r.plan.primary
                self.assertEqual(step.capability,cid)
                self.assertEqual(dict(step.params),params)
                self.menu._query(cid,dict(step.params))
    def test_no_substitution_for_explicit_unsupported_requests(self):
        for q in ("2025年2月29日电费用了几度电","2026年12月燃气费花了多少钱",
                  "三月份电费花了多少钱","2024年3月水费花了多少钱",
                  "次住所燃气余额","去年燃气余额","燃气用了多少吨","客厅灯温度多少"):
            with self.subTest(q=q):
                self.assertIsNone(self.p.plan(q,TODAY).plan)
        self.menu.settings["secondary"]=""
        self.assertIsNone(self.p.plan("第二账户电费还剩多少",TODAY).plan)
    def test_batch_queries_and_budget(self):
        self.assertEqual(self.ids("燃气余额和水费余额"),("utility.gas.basic.balance","utility.water.balance"))
        self.assertEqual(self.ids("燃气余额，燃气余额"),("utility.gas.basic.balance",))
        self.assertIsNone(self.p.plan("燃气余额，顺便关灯",TODAY).plan)
        self.assertIsNone(self.p.plan("空调现在多少度和大门关好了吗",TODAY).plan)
        self.assertIsNone(self.p.plan("燃气余额和火星温度",TODAY).plan)

    def test_aggregate_metrics_resolve_to_registered_primary_scope(self):
        for q,metric in [
            ("我家水电气余额还有多少","balances"),
            ("水电气有没有欠费","debts"),
            ("水电气还剩多少钱","balances"),
            ("水电气需要充值吗","low"),
            ("水电气数据更新时间","updates"),
        ]:
            with self.subTest(q=q):
                self.assertEqual(self.ids(q),("utility.summary.primary."+metric,))
        for q in ("去年水电气余额","次住所水电气余额","水电气还剩多少立方米","水电气本月费用"):
            self.assertIsNone(self.p.plan(q,TODAY).plan,q)

    def test_aggregate_explicit_scope_and_metric(self):
        for q,expected in [
            ("水电气有没有欠费的","utility.summary.primary.debts"),
            ("所有账户余额还有多少","utility.summary.all.balances_all"),
            ("全部水电气账户需要充值吗","utility.summary.all.low_all"),
            ("所有账户数据更新时间","utility.summary.all.updates_all"),
            ("主住所的水电气欠费情况","utility.summary.primary.debts"),
        ]:
            self.assertEqual(self.ids(q),(expected,),q)
        for q in ("去年所有账户余额","次住所所有账户余额","全部账户本月费用","所有账户还有多少立方米"):
            self.assertIsNone(self.p.plan(q,TODAY).plan,q)
