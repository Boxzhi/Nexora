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

    def test_cross_family_scope_metric_contracts(self):
        for q,metric,target in [
            ("全屋环境温度是多少","temp_avg","all"),
            ("全屋环境湿度是多少","hum_avg","all"),
            ("全屋环境光照度是多少","lux_all","all"),
            ("客厅灯是否全部关闭","all_off","ke_ting"),
            ("厨房灯是否全打开了","all_on","chu_fang"),
            ("主卧吸顶灯关了吗","single_state","lights.fixtures.master_ceiling"),
            ("门锁童锁状态","childlock","all"),
            ("两台空调实际温度多少","temp","ac"),
            ("净水器出水温度是多少","temp","p"),
            ("洗衣机洗涤水温多少","temp","w"),
        ]:
            r=self.p.plan(q,TODAY)
            self.assertIsNotNone(r.plan,(q,r.message))
            step,=r.plan.primary
            self.assertEqual((step.key.target,step.key.metric),(target,metric),q)
        for q in ("洗衣机室内温度是多少","净水器室内温度多少","洗衣机设定温度多少",
                  "厨房灯色温多少","主卧灯环境温度多少","阳台湿度多少","全屋环境色温多少"):
            self.assertIsNone(self.p.plan(q,TODAY).plan,q)

    def test_reverse_catalog_planner_audit(self):
        # Not every legacy intent needs a structured grammar. Record which
        # canonical forms are directly planned, scene-expanded, legacy-only
        # or structurally interpreted differently; the separate full mocked
        # adapter test is authoritative for exact registered dispatch.
        from collections import Counter
        from test_semantic_lexicon import PKG
        import importlib
        semantic=importlib.import_module(PKG+".semantic").SemanticIndex(self.menu)
        counts=Counter()
        details=[]
        for cid,cap in self.menu.capabilities.items():
            params={k:{"year":2024,"month":3,"day":9}[k] for k in cap.get("parameter_slots",{})}
            query=self.menu._query(cid,params)
            result=self.p.plan(query.sentence,TODAY)
            keys=tuple((x.capability,dict(x.params)) for x in result.plan.primary+result.plan.supplements) if result.plan else ()
            expected=(cid,params)
            if keys==(expected,):
                kind="direct"
            elif expected in keys:
                kind="scene"
            elif keys:
                kind="different"
            else:
                kind="legacy"
            counts[(cid.split(".")[0],kind)]+=1
            if kind in {"legacy","different","scene"}:
                # Original registration must still be recognized exactly.
                # The adapter test additionally checks actual dispatch.
                match=semantic.match(query.sentence,TODAY)
                self.assertIsNotNone(match,cid)
                self.assertEqual(match.capability,cid,(cid,kind))
            if kind=="different":
                details.append((cid,[k for k,_ in keys]))
        self.assertEqual(sum(counts.values()),443)
        self.assertEqual(details,[],details)
        print("V052_REVERSE_AUDIT="+json.dumps({f+":"+k:v for (f,k),v in sorted(counts.items())}))
        print("V052_REVERSE_DIFFERENT="+json.dumps(details,ensure_ascii=False))

    def test_snapshot_and_formal_bill_meanings_remain_distinct(self):
        self.assertEqual(self.ids("今年电费是多少"),("utility.electric.j.basic.year_cost",))
        self.assertEqual(self.ids("次住所的今年电费是多少"),("utility.electric.l.basic.year_cost",))
        self.assertEqual(self.ids("电费今年账单费用多少"),("utility.electric.j.history.h_year_cost.h_year_cost_year",))
        self.assertEqual(self.ids("洗衣机开机了吗"),("appliance.washer.power",))
        self.assertEqual(self.ids("厨房的灯现在全关了吗"),("lights.rooms.chu_fang.list_on",))
