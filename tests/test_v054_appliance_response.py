import unittest
import test_scene_response as scene_tests

class AppliancePresentationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=scene_tests.MenuResponseTests()
        self.fixture.setUp()

    def test_washer_same_power_only(self):
        data=[("ok","海尔洗衣机已关机。"),("ok","海尔洗衣机已关机。"),("skipped",""),("skipped",""),("skipped","")]
        r=self.fixture.result("appliance.washer.progress",data)
        self.assertEqual(r.text.count("已关机。"),1)
        data[1]=("ok","海尔洗衣机已开机。")
        r=self.fixture.result("appliance.washer.progress",data)
        self.assertIn("已关机",r.text)
        self.assertIn("已开机",r.text)

    def test_airer_position_same_or_conflict(self):
        data=[("ok","米家晾衣机已停止，最近上报位置78%。"),("ok","米家晾衣机最近上报位置：78%。"),("ok","米家晾衣机行程限位：上限位9%，下限位100%。"),("ok","米家晾衣机照明：已关闭。"),("ok","米家晾衣机故障：设备未报告故障。")]
        r=self.fixture.result("appliance.airer",data)
        self.assertEqual(r.text.count("78%"),1)
        self.assertIn("已停止。",r.text)
        self.assertIn("设备未报告故障",r.text)
        data[1]=("ok","米家晾衣机最近上报位置：79%。")
        r=self.fixture.result("appliance.airer",data)
        self.assertIn("78%",r.text)
        self.assertIn("79%",r.text)

    def test_bath_timer_keeps_source_scope(self):
        r=self.fixture.result("appliance.bath.timers",[("ok","米家浴霸照明延时关闭：未启用。"),("ok","米家浴霸延时关闭：未启用。")])
        self.assertIn("照明延时关闭：未启用",r.text)
        self.assertIn("浴霸延时关闭：未启用",r.text)
        self.assertNotIn("取暖延时关闭",r.text)
