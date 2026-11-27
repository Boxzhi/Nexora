import copy
from datetime import date
import importlib.util
import json
from pathlib import Path
import sys
import unittest

BASE=Path(__file__).resolve().parents[1]/"custom_components"/"nexora"
spec=importlib.util.spec_from_file_location("nexora_menu",BASE/"menu.py")
mod=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=mod
spec.loader.exec_module(mod)
CAT=json.loads((BASE/"catalogs"/"utility.json").read_text())
SET={"primary_label":"主账户","secondary_label":"第二账户","secondary":"次住所"}

class Tests(unittest.TestCase):
    def setUp(self):
        self.now=0
        self.m=mod.Menu([copy.deepcopy(CAT)],settings=SET,clock=lambda:self.now)
    def route(self,t,k="a",**kwargs):
        return self.m.route(k,t,**kwargs)
    def select_id(self,node,cap,k="a"):
        children=self.m.children[node]
        i=next(i for i,x in enumerate(children) if x.id==cap)
        self.m._render(k,node,lambda c:True,i//8)
        return self.route(str(i%8+1),k)
    def test_all_metrics(self):
        pairs={(x["slots"]["utility_kind"],x["slots"]["utility_metric"]) for x in CAT["capabilities"]}
        self.assertEqual(len(pairs),63)
        self.assertEqual(len({x["id"] for x in CAT["capabilities"]}),len(CAT["capabilities"]))
    def test_help(self):
        self.assertIn("1. 水电气",self.route("help").text)
        self.assertIn("电费",self.route("1").text)
    def test_water(self):
        self.route("水费")
        q=self.select_id("utility.water","utility.water.balance")
        self.assertEqual(q.slots,{"utility_kind":"w","utility_metric":"balance","luxe_utility_property":"j"})
        self.assertEqual(q.sentence,"水费余额是多少")
    def test_isolation(self):
        self.route("水费")
        self.assertIn("没有有效",self.route("1","b").text)
    def test_expiry(self):
        self.route("水费")
        self.now=600
        self.assertIn("没有有效",self.route("1").text)
    def test_refresh(self):
        self.route("水费")
        self.now=500
        self.select_id("utility.water","utility.water.balance")
        self.now=800
        self.assertNotIn("没有有效",self.route("8").text)
    def test_back(self):
        self.route("水费")
        self.assertIn("水电气",self.route("0").text)
    def test_exit(self):
        self.route("help")
        self.route("退出")
        self.assertIn("没有有效",self.route("1").text)
    def test_passthrough(self):
        self.route("help")
        self.assertIsNone(self.route("详细介绍峰谷电价"))
        self.assertIsNone(self.route("水费余额是多少"))
    def test_invalid(self):
        self.route("help")
        self.assertIn("无效",self.route("88").text)
    def test_fullwidth(self):
        self.route("help")
        self.assertIn("电费",self.route("１").text)
    def test_duplicate(self):
        with self.assertRaises(ValueError):mod.Menu([CAT,CAT])
    def test_action(self):
        c=copy.deepcopy(CAT);c["capabilities"][0]["read_only"]=False
        with self.assertRaises(ValueError):mod.Menu([c])
    def test_external_module(self):
        c={"schema_version":1,"module":{"id":"network","name":"网络","order":200},"categories":[{"id":"network.info","name":"网络信息","order":10}],"capabilities":[{"id":"network.info.status","category":"network.info","name":"网络状态","sentence":"网络状态是多少","intent":"NetworkQuery","slots":{},"read_only":True,"order":10}]}
        m=mod.Menu([CAT,c],settings=SET)
        self.assertIn("2. 网络",m.route("a","help").text)
    def test_hide_missing_handler(self):
        self.assertIn("没有可用",self.route("help",available=lambda _:False).text)
    def test_secondary_disabled(self):
        m=mod.Menu([CAT]);self.assertNotIn("第二账户",m.route("a","电费").text)
    def test_secondary_enabled(self):
        q=self.select_id("utility.electric.l.basic","utility.electric.l.basic.balance")
        self.assertEqual(q.sentence,"次住所的电费余额")
        self.assertEqual(q.slots["luxe_utility_property"],"l")
    def test_snapshot(self):
        self.route("help")
        self.assertIn("不可用",self.route("1",available=lambda _:False).text)
    def test_page(self):
        self.route("燃气阶梯")
        self.assertIn("9. 下一页",self.route("上一页").text)
        self.assertIn("第三阶梯",self.route("9").text)
        self.assertIn("9. 下一页",self.route("上一页").text)
    def test_date(self):
        node="utility.electric.j.history.day"
        self.assertIn("YYYY-MM-DD",self.select_id(node,node+".h_day_explicit").text)
        self.assertIn("无效",self.route("2025-02-29",today=date(2026,11,27)).text)
        q=self.route("2024-02-29",today=date(2026,11,27))
        self.assertEqual(q.slots["luxe_utility_day"],29)
        self.assertEqual(q.sentence,"2024年2月29日用了多少度电")
    def test_month(self):
        node="utility.water.history.history_usage"
        self.select_id(node,node+".history_usage_year")
        q=self.route("3",today=date(2026,11,27))
        self.assertEqual(q.slots["luxe_utility_month"],3)
    def test_future(self):
        with self.assertRaises(ValueError):mod.parse_parameter("date","2027-01-01",date(2026,11,27))
    def test_cancel_parameter(self):
        node="utility.water.history.history_usage"
        self.select_id(node,node+".history_usage_year")
        self.assertIn("月度用量",self.route("0").text)
    def test_bounded(self):
        m=mod.Menu([CAT],max_sessions=1);m.route("a","help");m.route("b","help")
        self.assertIn("没有有效",m.route("a","1").text)
    def test_every_leaf(self):
        values={"month":{"month":3},"year":{"year":2024},"year_month":{"year":2024,"month":3},"date":{"year":2024,"month":3,"day":5},"month_day":{"month":3,"day":5},None:{}}
        for cap in CAT["capabilities"]:
            q=self.m._query(cap["id"],values[cap.get("parameter")])
            self.assertTrue(q.sentence and "{" not in q.sentence)
            self.assertEqual(q.slots["utility_metric"],cap["slots"]["utility_metric"])
    def test_bad_schema(self):
        c=copy.deepcopy(CAT);c["schema_version"]=2
        with self.assertRaises(ValueError):mod.Menu([c])
    def test_bad_placeholder(self):
        c=copy.deepcopy(CAT);c["capabilities"][0]["sentence"]="{secondary.__class__}"
        with self.assertRaises(ValueError):mod.Menu([c])
    def test_category_cycle(self):
        c=copy.deepcopy(CAT);c["categories"][0]["parent"]="utility.electric"
        with self.assertRaises(ValueError):mod.Menu([c])

    def test_last_year_month(self):
        node="utility.water.history.history_usage"
        self.select_id(node,node+".history_usage_last_year")
        q=self.route("12",today=date(2026,11,27))
        self.assertEqual(q.slots["luxe_utility_month"],12)
        self.assertEqual(q.sentence,"去年12月用了多少吨水")
    def test_ambiguous_implicit_alias(self):
        other={"schema_version":1,"module":{"id":"other","name":"其他","order":200},"categories":[{"id":"other.month","name":"月度用量","order":10}],"capabilities":[]}
        m=mod.Menu([CAT,other],settings=SET)
        self.assertNotIn("月度用量",m.aliases)
    def test_parameter_mapping(self):
        other={"schema_version":1,"module":{"id":"other","name":"其他","order":200},"categories":[{"id":"other.date","name":"日期查询","order":10}],"capabilities":[{"id":"other.date.query","category":"other.date","name":"指定日期","order":10,"intent":"OtherQuery","sentence":"{year}年记录","slots":{},"parameter":"year","parameter_slots":{"year":"other_year"},"read_only":True}]}
        m=mod.Menu([CAT,other],settings=SET)
        m.route("a","日期查询");m.route("a","1")
        q=m.route("a","2024",today=date(2026,11,27))
        self.assertEqual(q.slots,{"other_year":2024})
    def test_slot_override_rejected(self):
        c=copy.deepcopy(CAT)
        cap=next(x for x in c["capabilities"] if x.get("parameter")=="date")
        cap["parameter_slots"]["year"]="utility_kind"
        with self.assertRaises(ValueError):mod.Menu([c])

    def test_independent_question_during_date_prompt(self):
        node="utility.water.history.history_usage"
        self.select_id(node,node+".history_usage_year")
        self.assertIsNone(self.route("详细介绍一下峰谷电价"))
        self.assertIsNone(self.m.sessions["a"].pending)

if __name__=="__main__":unittest.main()
