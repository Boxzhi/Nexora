import unittest
from datetime import date
from test_menu import mod, CAT, SET, BASE
import json
from nexora_menu_test.scene_menu import Node
from nexora_menu_test.query_planner import QueryPlanner

class SceneFoundationTests(unittest.TestCase):
    def setUp(self):
        self.m=mod.Menu([json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))],settings=SET)
        self.rows=[Node("scene.utility","scene","水电气",100,alias_of="utility"),
            Node("scene.utility.water","scene.utility","水费",10,alias_of="utility.water"),
            Node("scene.utility.water.balance","scene.utility.water","账户概况",10,
                ("utility.water.balance","utility.water.debt"),anchor="utility.water.balance")]
    def test_overlay_and_original(self):
        self.m.install_scene_layout(self.rows)
        self.assertEqual(len(self.m.capabilities),443)
        self.assertIn("水电气",self.m.route("a","help").text)
        self.assertIn("账户概况",self.m.route("a","1.1").text)
        q=self.m.route("a","1")
        self.assertEqual(q.scene,"scene.utility.water.balance")
        self.assertEqual(len(QueryPlanner(self.m).menu_plan(q.scene,{},lambda c:True,None,date.today()).primary),2)
        self.assertIn("水电气",self.m.route("a","detail").text)
        self.assertIn("水费",self.m.route("a","1").text)
        self.assertIn("欠费情况",self.m.route("a","2").text)
    def test_visibility(self):
        self.m.install_scene_layout(self.rows)
        plan=QueryPlanner(self.m).menu_plan("scene.utility.water.balance",{},lambda c:c["id"].endswith(".balance"),None,date.today())
        self.assertEqual([x.capability for x in plan.primary],["utility.water.balance"])
        self.assertIn("没有可用",self.m.route("a","help",lambda c:False).text)
    def test_invalid_is_atomic(self):
        with self.assertRaises(ValueError):
            self.m.install_scene_layout(self.rows+[Node("scene.bad","scene","错误",1,("absent",))])
        self.assertNotIn("scene",self.m.items)
    def test_incompatible_parameter(self):
        with self.assertRaises(ValueError):
            self.m.install_scene_layout(self.rows+[Node("scene.bad","scene","错误",1,("utility.water.balance","utility.water.history.history_usage.history_usage_year"))])
