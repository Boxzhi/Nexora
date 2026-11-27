import unittest
import test_scene_response as scene_tests

class ACShutdownTests(unittest.TestCase):
    def setUp(self):
        self.fixture=scene_tests.MenuResponseTests()
        self.fixture.setUp()
    def result(self, status, temps, targets, count="家里已确认开启的空调有0台。"):
        return self.fixture.result("appliance.ac.all",[
            ("ok",status),("ok",count),("state_limit",temps),("state_limit",targets)])
    def test_replay_both_off(self):
        r=self.result("主卧空调已关闭。次卧空调已关闭。",
            "主卧空调设备报告室温：19.5℃（空调已关闭，读数可能未实时刷新）。次卧空调设备报告室温：18.8℃（空调已关闭，读数可能未实时刷新）。",
            "主卧空调已关闭，无当前运行参数。次卧空调已关闭，无当前运行参数。")
        self.assertEqual(r.text.count("状态：已关闭"),2)
        self.assertEqual(r.text.count("可能未实时刷新"),1)
        self.assertIn("设备报告室温：19.5℃",r.text)
        self.assertIn("设备报告室温：18.8℃",r.text)
    def test_conflict_and_mixed_state_preserved(self):
        r=self.result("主卧空调已关闭。次卧空调已开启。",
            "主卧空调设备报告室温：19.5℃（空调已关闭，读数可能未实时刷新）。次卧空调设备报告室温：18.8℃（空调已关闭，读数可能未实时刷新）。",
            "主卧空调已关闭，无当前运行参数。次卧空调已关闭，无当前运行参数。","家里已确认开启的空调有1台。")
        self.assertIn("主卧空调\n状态：已关闭",r.text)
        self.assertIn("次卧空调\n已开启。",r.text)
        self.assertIn("设备报告室温：18.8℃（空调已关闭，读数可能未实时刷新）",r.text)
        self.assertIn("已关闭，无当前运行参数。",r.text)
