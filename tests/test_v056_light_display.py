import unittest
import test_scene_response as scene_tests
from nexora_menu_test.scene_response import _light_list_lines

class LightDisplayTests(unittest.TestCase):
    def setUp(self):
        self.fixture=scene_tests.MenuResponseTests()
        self.fixture.setUp()

    def test_scene_label_only(self):
        m=self.fixture.m
        for key,name,old in (("bath_panel","卫生间平板灯","人体存在平板灯"),("bath_heater","浴霸灯","智能浴霸S1灯")):
            original="lights.fixtures."+key
            sid="scene."+original
            self.assertEqual(m.items[sid].name,name)
            self.assertEqual(m.items[original].name,old)
            self.assertEqual(m.scene_language.match(name+"概况"),sid)
            self.assertEqual(m.scene_language.match(old+"概况"),sid)
            self.assertEqual(m.scenes[sid].members,tuple(original+"."+x for x in ("single_state","brightness","temperature")))

    def test_long_list_preserves_names_order_and_count(self):
        names=["示例灯"+str(i) for i in range(1,16)]
        r=self.fixture.result("lights.all",[
            ("ok","全屋共有15组灯具。"),
            ("ok","全屋15组灯具均已关闭。"),
            ("ok","全屋当前有15组灯具关闭："+"、".join(names)+"。"),
            ("ok","全屋暂未检测到不可用灯具。"),
        ])
        self.assertIn("已关闭：15组",r.text)
        self.assertIn("已关闭灯具：\n"+"、".join(names[:3]),r.text)
        for chunk in range(0,15,3):
            self.assertIn("、".join(names[chunk:chunk+3]),r.text)
        self.assertIn("离线检查：暂未检测到不可用灯具",r.text)

    def test_mismatched_and_short_lists_preserved(self):
        for line in ("已关闭：8组（甲、乙、丙、丁、戊）","已开启：2组（甲、乙）","已关闭：5组（甲、乙、、丁、戊）"):
            self.assertEqual(_light_list_lines([line]),[line])
