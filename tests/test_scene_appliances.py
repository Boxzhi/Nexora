import unittest
import json
from datetime import date
from test_menu import mod, BASE, SET
from nexora_menu_test.scene_layout import appliance_layout
from nexora_menu_test.query_planner import QueryPlanner
from nexora_menu_test.plan_executor import Outcome,stop_supplements

class ApplianceSceneTests(unittest.TestCase):
    def setUp(self):
        self.m=mod.Menu([json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))],settings=SET)
        self.m.install_scene_layout(appliance_layout())
        self.p=QueryPlanner(self.m)
        self.today=date(2026,11,27)
    def ask(self,q):
        return self.m.route("a",q,today=self.today)
    def plan(self,q):
        return self.p.menu_plan(q.scene,dict(q.params),lambda c:True,None,self.today)
    def test_washer_menu_and_off_gate(self):
        r=self.ask("洗衣机")
        self.assertIn("1. 当前洗衣进度",r.text)
        self.assertIn("6. 故障状态",r.text)
        self.assertNotIn("7.",r.text)
        plan=self.plan(self.ask("1"))
        self.assertEqual([s.key.metric for s in plan.primary],["status","power"])
        self.assertEqual([s.key.metric for s in plan.supplements],["program","phase","remaining"])
        self.assertTrue(stop_supplements(plan,(Outcome(plan.primary[0],"ok","海尔洗衣机已关机。"),)))
        self.assertFalse(stop_supplements(plan,(Outcome(plan.primary[0],"data_gap","海尔洗衣机状态未知。"),)))
        self.assertFalse(stop_supplements(plan,(Outcome(plan.primary[0],"ok","海尔洗衣机正在运行，程序：混合。"),)))
    def test_ac_off_preserves_detected_temperature(self):
        r=self.ask("空调")
        self.assertIn("1. 全部空调",r.text)
        self.assertIn("2. 主卧空调",r.text)
        self.assertIn("运行参数",self.ask("2").text)
        plan=self.plan(self.ask("1"))
        self.assertEqual([s.key.metric for s in plan.primary],["status","temp"])
        self.assertTrue(stop_supplements(plan,(Outcome(plan.primary[0],"ok","主卧空调已关闭。"),)))
        self.assertFalse(stop_supplements(plan,(Outcome(plan.primary[0],"data_gap","主卧空调状态未知。"),)))
    def test_direct_airer_and_fan(self):
        self.ask("家电")
        q=self.ask("4")
        self.assertEqual(q.scene,"scene.appliance.airer")
        self.assertEqual(len(self.plan(q).primary),5)
        q=self.ask("5")
        plan=self.plan(q)
        self.assertEqual([s.key.metric for s in plan.primary],["status","light"])
        self.assertTrue(stop_supplements(plan,(Outcome(plan.primary[0],"ok","餐厅风扇已关闭。"),)))
        self.assertFalse(stop_supplements(plan,(Outcome(plan.primary[0],"data_gap","餐厅风扇数据不可用。"),)))
    def test_purifier_and_count(self):
        self.assertIn("滤芯健康",self.ask("净水器").text)
        plan=self.plan(self.ask("2"))
        self.assertEqual([s.key.metric for s in plan.primary],["filters","days","replace"])
        self.assertEqual(len(self.m.scenes),24)
        self.assertEqual(len([cid for cid in self.m.capabilities if cid.startswith("appliance.")]),78)
