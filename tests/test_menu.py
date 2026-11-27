import copy
from datetime import date
import importlib.util
import json
from pathlib import Path
from types import ModuleType
import sys
import unittest

BASE=Path(__file__).resolve().parents[1]/"custom_components"/"nexora"
pkg=ModuleType("nexora_menu_test")
pkg.__path__=[str(BASE)]
sys.modules[pkg.__name__]=pkg
spec=importlib.util.spec_from_file_location("nexora_menu_test.menu",BASE/"menu.py")
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
        self.m._render(k,node,lambda c:True,i//mod.PAGE_SIZE)
        return self.route(str(i%mod.PAGE_SIZE+1),k)
    def test_all_metrics(self):
        pairs={(x["slots"]["utility_kind"],x["slots"]["utility_metric"]) for x in CAT["capabilities"]}
        self.assertEqual(len(pairs),63)
        self.assertEqual(len({x["id"] for x in CAT["capabilities"]}),len(CAT["capabilities"]))
    def test_help(self):
        self.assertIn("1. ⚡ 水电气",self.route("help").text)
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
        r=self.route("燃气阶梯")
        self.assertIn("第三阶梯",r.text)
        self.assertNotIn("99. 下一页",r.text)
        expected=self.m.sessions["a"].shown[8]
        self.assertEqual(self.route("9").capability,expected)
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

class AllCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalogs=[json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))]
        self.m=mod.Menu(self.catalogs,settings=SET)
    def test_root_exact(self):
        expected="Nexora · 智能家庭助手\n\n1. ⚡ 水电气\n2. 💡 灯光\n3. 🔌 家电\n4. 🏠 全屋状态\n\n"+mod.FOOTER
        self.assertEqual(self.m.route("a","help").text,expected)
        self.assertEqual(self.m.route("a","帮助").text,expected)
        self.assertEqual(self.m.route("a","HELP").text,expected)
    def test_child_icon_and_plain_alias(self):
        self.assertTrue(self.m.route("a","灯光").text.startswith("💡 灯光\n"))
        self.assertTrue(self.m.route("a","1").text.startswith("全屋灯光\n"))
    def test_exit_aliases(self):
        for cmd in ("exit","EXIT","退出"):
            self.m.route("a","help")
            self.assertIn("已退出",self.m.route("a",cmd).text)
            self.assertIn("没有有效",self.m.route("a","1").text)
    def test_page_aliases(self):
        initial=self.m.route("a","燃气阶梯").text
        self.assertIn("第三阶梯",initial)
        self.assertEqual(self.m.route("a","NEXT").text,initial)
        self.assertEqual(self.m.route("a","prev").text,initial)
        self.assertIn("燃气费",self.m.route("a","BACK").text)
    def test_counts(self):
        self.assertEqual({c["module"]["id"]:len(c["capabilities"]) for c in self.catalogs},{"utility":136,"lights":144,"appliance":78,"home":85})
        self.assertEqual(len(self.m.capabilities),443)
    def test_source_fingerprint(self):
        for c in self.catalogs:
            mid=c["module"]["id"]
            if mid not in {"home","appliance"}:continue
            rows=sorted(json.dumps([x["intent"],x["sentence"],dict(sorted(x["slots"].items()))],ensure_ascii=False,separators=(",",":")) for x in c["capabilities"])
            h=2166136261
            for char in "\n".join(rows):h=((h^ord(char))*16777619)&0xffffffff
            self.assertEqual(h,{"home":0xa6ce1596,"appliance":0x797ed3e2}[mid])
    def test_light_combinations(self):
        c=next(x for x in self.catalogs if x["module"]["id"]=="lights")
        single=[x for x in c["capabilities"] if x.get("native_slots")]
        scoped=[x for x in c["capabilities"] if not x.get("native_slots")]
        self.assertEqual(len(single),45)
        self.assertEqual(len({(x["slots"]["luxe_light_scope"],x["slots"]["light_query"]) for x in scoped}),99)
        self.assertTrue(all(not any(isinstance(v,str) and v.startswith("light.") for v in x["slots"].values()) and "luxe_light_id" not in x["slots"] for x in single))
    def test_missing_module_handler(self):
        r=self.m.route("a","help",available=lambda c:c["intent"]=="LuxeUtilityQuery")
        self.assertIn("1. ⚡ 水电气",r.text)
        self.assertNotIn("灯光",r.text)
    def test_native_slot_guard(self):
        c=copy.deepcopy(next(x for x in self.catalogs if x["module"]["id"]=="lights"))
        x=next(x for x in c["capabilities"] if x.get("native_slots"))
        x["native_slots"]={"anything":"light"}
        with self.assertRaises(ValueError):mod.Menu([c])
    def test_all_leaves(self):
        values={"month":{"month":3},"year":{"year":2024},"year_month":{"year":2024,"month":3},"date":{"year":2024,"month":3,"day":5},"month_day":{"month":3,"day":5},None:{}}
        for cap in self.m.capabilities.values():
            q=self.m._query(cap["id"],values[cap.get("parameter")])
            self.assertTrue(q.sentence and "{" not in q.sentence)
            self.assertTrue(all(q.slots[k]==v for k,v in cap["slots"].items()))
    def test_reserved_alias(self):
        c=copy.deepcopy(self.catalogs[0]);c["module"]["aliases"]=["exit"]
        with self.assertRaises(ValueError):mod.Menu([c])

class V03Tests(unittest.TestCase):
    def setUp(self):
        self.now=0
        self.catalogs=[json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))]
        self.m=mod.Menu(self.catalogs,settings=SET,clock=lambda:self.now)
    def route(self,text,key="a",**kw):
        return self.m.route(key,text,**kw)
    def test_no_example(self):
        self.assertNotIn("示例：",self.route("水费").text)
        self.assertIn("欠费情况",self.route("水费").text)
    def test_compound_success(self):
        self.route("help")
        self.assertEqual(self.route("1.2.1").capability,"utility.water.balance")
        self.assertEqual(self.route("1").capability,"utility.water.balance")
    def test_compound_atomic_failure(self):
        self.route("help")
        before=self.m.sessions["a"]
        self.assertIn("无效数字路径",self.route("1.2.1.2").text)
        self.assertEqual(self.m.sessions["a"],before)
        self.assertIn("水电气",self.route("1").text)
    def test_compound_requires_session(self):
        self.assertIn("没有有效",self.route("1.2.1").text)
    def test_compound_parameter_boundary(self):
        self.route("help")
        self.assertIn("无效数字路径",self.route("1.1.1.2.1.4.1").text)
        self.assertEqual(self.m.sessions["a"].node,"root")
        self.assertIn("YYYY-MM-DD",self.route("1.1.1.2.1.4").text)
        self.assertIn("先完成",self.route("1.2").text)
        self.assertEqual(self.route("2024-01-02",today=date(2026,11,27)).slots["luxe_utility_day"],2)
    def test_compound_respects_snapshot(self):
        self.route("help")
        self.assertIn("不可用",self.route("1.2.1",available=lambda c:c["intent"]!="LuxeUtilityQuery").text)
        self.assertEqual(self.m.sessions["a"].node,"root")
    def test_context_balance_clarification(self):
        self.m.followups.remember("a","utility.water.balance")
        self.assertIn("用量还是费用",self.route("上个月呢").text)
        q=self.route("用水量")
        self.assertEqual(q.slots["utility_period"],"previous")
        self.assertEqual(q.slots["utility_metric"],"history_usage")
        self.m.followups.remember("a",q.capability)
        self.assertEqual(self.route("这个月呢").slots["utility_period"],"current")
    def test_context_property_switch(self):
        self.m.followups.remember("a","utility.electric.j.basic.balance")
        q=self.route("第二账户呢")
        self.assertEqual(q.slots["luxe_utility_property"],"l")
        self.m.followups.remember("a",q.capability)
        q=self.route("上个月用了多少度")
        self.assertEqual(q.slots["utility_metric"],"h_month_usage")
        self.assertEqual(q.slots["luxe_utility_property"],"l")
    def test_context_timeout_isolation(self):
        self.m.followups.remember("a","utility.water.balance")
        self.assertIn("失效",self.route("上个月呢","b").text)
        self.now=300
        self.assertIn("失效",self.route("上个月呢").text)
    def test_context_exit_and_passthrough(self):
        self.m.followups.remember("a","utility.water.balance")
        self.assertIsNone(self.route("打开客厅灯"))
        self.assertIn("失效",self.route("上个月呢").text)
        self.m.followups.remember("a","utility.water.balance")
        self.route("exit")
        self.assertIn("失效",self.route("上个月呢").text)
    def test_hidden_alias(self):
        self.assertIn("暂无已配置",self.route("灯光",available=lambda c:c["intent"]!="LuxeLightQuery").text)
    def test_bad_requirement(self):
        c=copy.deepcopy(self.catalogs[0])
        c["capabilities"][0]["requires"]=[{"kind":"expression","code":"anything"}]
        with self.assertRaises(ValueError):mod.Menu([c])
    def test_context_does_not_infer_other_unit(self):
        self.m.followups.remember("a","utility.water.balance")
        self.assertIsNone(self.route("上个月用了多少度"))

    def test_fast_context_generation_and_metric_switch(self):
        f=self.m.followups
        cap=next(c for c in self.m.capabilities.values()
                 if c["slots"]=={"utility_kind":"e","utility_metric":"h_month_usage",
                                  "luxe_utility_property":"j","utility_period":"current"})
        old=f.begin("a")
        newer=f.begin("a")
        self.assertFalse(f.complete("a",old,cap["id"]))
        self.assertTrue(f.complete("a",newer,cap["id"]))
        q=self.route("上个月呢")
        self.assertEqual(q.slots["utility_period"],"previous")
        f.remember("a",q.capability)
        q=self.route("费用呢")
        self.assertEqual(q.slots["utility_metric"],"h_month_cost")
        self.assertEqual(q.slots["utility_period"],"previous")
        f.remember("a",q.capability)
        q=self.route("另一个账户呢")
        self.assertEqual(q.slots["luxe_utility_property"],"l")
        self.assertEqual(q.slots["utility_period"],"previous")
        self.assertEqual(q.slots["utility_metric"],"h_month_cost")

    def test_context_clarification_accepts_specific_bare_metric(self):
        f=self.m.followups
        f.remember("a","utility.water.balance")
        self.assertIn("用量还是费用",self.route("上个月呢").text)
        self.assertTrue(f.is_followup_message("用水量"))
        q=self.route("用水量")
        self.assertEqual(q.slots["utility_metric"],"history_usage")
        self.assertEqual(q.slots["utility_period"],"previous")
        f.remember("a",q.capability)
        self.assertTrue(f.is_followup_message("费用"))
        self.assertEqual(self.route("费用").slots["utility_metric"],"history_cost")


class SemanticTests(unittest.TestCase):
    def setUp(self):
        from importlib import import_module
        SemanticIndex=import_module(mod.__package__+".semantic").SemanticIndex
        self.menu=mod.Menu([json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))],settings=SET)
        self.index=SemanticIndex(self.menu)
    def test_all_four_modules(self):
        for text,cid in {
            "阳台光照度":"home.presence.balcony.lux_balcony",
            "阳台光照强度是多少":"home.presence.balcony.lux_balcony",
            "请问阳台的光照度是多少？":"home.presence.balcony.lux_balcony",
            "主卧的温度":"home.env.master.temp_master",
            "客厅吸顶灯的亮度":"lights.fixtures.living_ceiling.brightness",
            "洗衣机还剩多久":"appliance.washer.remaining",
            "净水器当前状态":"appliance.purifier.status",
            "水费还有多少钱":"utility.water.balance",
            "电费余额是多少":"utility.electric.j.basic.balance",
            "第二账户的电费余额":"utility.electric.l.basic.balance",
        }.items():
            with self.subTest(text=text):
                self.assertEqual(self.index.match(text).capability,cid)
    def test_ambiguous_brightness_and_hidden_capability(self):
        for text in ("阳台有多亮","阳台亮度是多少"):
            self.assertIn("还是",self.index.match(text).clarification)
        match=self.index.match("爷爷在家吗")
        self.assertEqual(match.capability,"home.family.person_grandfather")
        self.assertIn("不可用",self.index.reply(match,lambda c:False).text)
    def test_reject_controls_negation_compound_and_unknown(self):
        for text in ("打开客厅灯","把客厅吸顶灯亮度调到50%","阳台光照度不要查",
                     "阳台光照度是多少然后开灯","主卧温度和水费余额",
                     "昨天阳台光照度","不存在的房间光照度"):
            with self.subTest(text=text):
                self.assertIsNone(self.index.match(text))
        self.assertEqual(self.index.match("阳台无人多久了").capability,"home.presence.balcony.duration_absent_balcony")


class Pagination20Tests(unittest.TestCase):
    def make_menu(self,n):
        catalog={"schema_version":1,"module":{"id":"paging","name":"分页测试","order":1},
                 "categories":[{"id":"paging.group","name":"查询组","order":1}],
                 "capabilities":[{"id":f"paging.group.q{i}","category":"paging.group",
                                  "name":f"项目{i}","order":i,"intent":"TestQuery",
                                  "sentence":f"测试项目{i}","slots":{"index":i},"read_only":True}
                                  for i in range(1,n+1)]}
        return mod.Menu([catalog])

    def test_exact_20_and_multidigit_selection(self):
        for n in (8,9,15,19,20):
            with self.subTest(n=n):
                m=self.make_menu(n)
                r=m.route("a","查询组")
                self.assertIn(f"{n}. 项目{n}",r.text)
                self.assertNotIn("98. 上一页",r.text)
                self.assertNotIn("99. 下一页",r.text)
                self.assertEqual(m.route("a",str(n)).slots["index"],n)
                self.assertIn("无效选项",m.route("a",str(n+1)).text)
                self.assertIn("无效选项",m.route("a","01").text)

    def test_three_pages_numeric_navigation_and_aliases(self):
        m=self.make_menu(41)
        first=m.route("a","查询组").text
        self.assertIn("20. 项目20",first)
        self.assertIn("99. 下一页",first)
        self.assertNotIn("98. 上一页",first)
        second=m.route("a","99").text
        self.assertIn("1. 项目21",second)
        self.assertIn("20. 项目40",second)
        self.assertIn("98. 上一页",second)
        self.assertIn("99. 下一页",second)
        third=m.route("a","下一页").text
        self.assertIn("1. 项目41",third)
        self.assertNotIn("99. 下一页",third)
        self.assertEqual(m.route("a","99").text,third)
        self.assertEqual(m.route("a","98").text,second)
        self.assertEqual(m.route("a","PREV").text,first)
        self.assertEqual(m.route("a","98").text,first)
        self.assertEqual(m.route("a","NEXT").text,second)
        self.assertEqual(m.route("a","上一页").text,first)
        self.assertEqual(m.route("a","9").slots["index"],9)
        self.assertEqual(m.route("a","0").text.splitlines()[0],"分页测试")

    def test_multi_digit_path_and_atomic_rollback(self):
        m=self.make_menu(20)
        m.route("a","help")
        self.assertEqual(m.route("a","1.1.20").slots["index"],20)
        m.route("a","help")
        for path in ("1.1.99","1.1.98","1.1.21","1.1.01","1.1.12.1"):
            original=m.sessions["a"]
            self.assertIn("无效数字路径",m.route("a",path).text)
            self.assertEqual(m.sessions["a"],original)

    def test_filtering_before_pagination_and_snapshot(self):
        m=self.make_menu(21)
        visible=lambda c:c["slots"]["index"]!=3
        r=m.route("a","查询组",visible)
        self.assertNotIn("99. 下一页",r.text)
        self.assertIn("20. 项目21",r.text)
        self.assertEqual(m.route("a","20",visible).slots["index"],21)
        self.assertIn("不可用",m.route("a","20",lambda c:c["slots"]["index"]!=21).text)

    def test_existing_lights_washer_bath_all_fit_one_page(self):
        m=mod.Menu([json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))],settings=SET)
        for name,n in (("按灯具",15),("洗衣机",19),("浴霸",16)):
            r=m.route("a",name)
            self.assertEqual(len(m.sessions["a"].shown),n)
            self.assertNotIn("99. 下一页",r.text)
            self.assertNotIn("98. 上一页",r.text)
        m.route("a","按灯具")
        self.assertIn("厨房筒灯",m.route("a","12").text)
        m.route("a","按灯具")
        self.assertIn("厨房筒灯",m.route("a","１２").text)

    def test_date_parameter_has_priority_over_numeric_choices_and_pages(self):
        m=mod.Menu([CAT],settings=SET)
        m.route("a","help")
        self.assertIn("YYYY-MM-DD",m.route("a","1.1.1.2.1.4").text)
        for command in ("98","99","12"):
            self.assertIn("输入无效",m.route("a",command).text)
            self.assertIsNotNone(m.sessions["a"].pending)
        self.assertEqual(m.route("a","2024-01-02",today=date(2026,11,27)).slots["luxe_utility_day"],2)

if __name__=="__main__":unittest.main()
