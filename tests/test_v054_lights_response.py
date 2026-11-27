import unittest
import test_scene_response as scene_tests

class LightsPresentationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=scene_tests.MenuResponseTests()
        self.fixture.setUp()

    def test_room_zero_only_when_corroborated(self):
        data=[("ok","客厅共有3组灯具。"),("ok","客厅3组灯具均已关闭。"),("ok","客厅当前有3组灯具关闭：甲、乙、丙。"),("ok","客厅暂未检测到不可用灯具。")]
        result=self.fixture.result("lights.rooms.ke_ting.overview",data)
        self.assertIn("已开启：0组",result.text)
        self.assertNotIn("均已关闭",result.text)
        data[2]=("ok","客厅当前有2组灯具关闭：甲、乙。")
        result=self.fixture.result("lights.rooms.ke_ting.overview",data)
        self.assertNotIn("已开启：0组",result.text)
        self.assertIn("客厅3组灯具均已关闭",result.text)

    def test_abnormal_normal_merge_keeps_both_meanings(self):
        r=self.fixture.result("lights.rooms.ke_ting.issues",[("ok","客厅暂未检测到不可用灯具。"),("ok","客厅所有灯具状态正常。")])
        self.assertIn("暂未检测到不可用灯具，所有灯具状态正常",r.text)
        r=self.fixture.result("lights.rooms.ke_ting.issues",[("data_gap","客厅离线状态无法确认。"),("ok","客厅所有灯具状态正常。")])
        self.assertIn("离线状态无法确认",r.text)
        self.assertIn("所有灯具状态正常",r.text)

    def test_known_fixture_label_and_conflict(self):
        data=[("ok","卫生间平板灯当前已关闭。"),("state_limit","卫生间平板灯当前已关闭，无法获取实时亮度。"),("ok","卫生间平板灯不支持色温调节。")]
        r=self.fixture.result("lights.fixtures.bath_panel",data)
        self.assertTrue(r.text.startswith("卫生间平板灯\n\n"))
        self.assertIn("状态：已关闭",r.text)
        self.assertIn("色温调节：不支持",r.text)
        self.assertIn("实时亮度：灯具已关闭，无法获取",r.text)
        data[0]=("ok","卫生间平板灯当前已开启。")
        r=self.fixture.result("lights.fixtures.bath_panel",data)
        self.assertIn("状态：已开启",r.text)
        self.assertIn("卫生间平板灯当前已关闭，无法获取实时亮度",r.text)
