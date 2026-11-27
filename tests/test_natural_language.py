import importlib
import json
import unittest
from test_semantic_lexicon import BASE,PKG,mod
bm=importlib.import_module(PKG+".business_model")
nl=importlib.import_module(PKG+".natural_language")

class NaturalLanguageTests(unittest.TestCase):
    def setUp(self):
        self.menu=mod.Menu([json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))],
             settings={"primary_label":"主账户","secondary_label":"第二账户","secondary":"次住所"})
        self.parser=nl.QueryParser(self.menu,bm.BusinessRegistry(self.menu.capabilities))
    def test_unregistered_surface_forms(self):
        cases=[
          ("能不能帮我看看家里的燃气费还剩下多少钱","utility","g","","remaining_unspecified"),
          ("我想知道主卧空调设置的是多少度","appliance","m","target",""),
          ("客厅灯现在还有多少盏灯是开着的","lights","ke_ting","count_on",""),
          ("客厅现在还有多少盏灯是开着的","lights","ke_ting","count_on",""),
          ("我想知道主卧那台空调设置的是多少度","appliance","m","target",""),
          ("帮我看看现在家里都有些什么人在","home","all","","family_presence"),
          ("主卧空调现在温度是多少","appliance","m","","temperature_unspecified"),
          ("我想知道洗衣机目前怎么样","appliance","w","","progress"),
          ("请告诉我阳台有多亮","home","阳台","","brightness_unspecified"),
          ("我想知道入户门关好了吗","home","all","","entry_safety"),
          ("余额多少的天然气","utility","g","balance",""),
        ]
        for q,f,t,m,g in cases:
            with self.subTest(q=q):
                frames=self.parser.parse(q)
                self.assertEqual(len(frames),1,frames)
                x=frames[0]
                self.assertEqual((x.subject.family,x.subject.target,x.metric,x.goal),(f,t,m,g))
    def test_time_and_account_are_independent(self):
        for q in ("次住所去年三月份电费花了多少钱","去年三月份次住所电费花了多少钱","次住所电费去年三月份花了多少钱"):
            with self.subTest(q=q):
                x,=self.parser.parse(q)
                self.assertEqual(x.account,"l")
                self.assertEqual(x.time,nl.TimeSpec(month=3,relative_year=-1))
                self.assertEqual(x.metric,"cost")
    def test_unexplained_text_is_never_ignored(self):
        for q in ("不要查燃气余额","燃气余额然后关灯","燃气余额我乱写","空调调到26度",
                  "主卧空调温度昨天","火星燃气余额","次住所主卧温度","燃气余额2025年",
                  "主卧空调多少度并关灯","主卧空调温度是多少帮我关闭","门锁反锁","大门上锁","主卧窗帘关闭","马桶盖打开"):
            with self.subTest(q=q):
                self.assertFalse(self.parser.parse(q))
