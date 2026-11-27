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

    def test_ac_grouping_preserves_stale_qualifier(self):
        r=self.fixture.result("appliance.ac.all",[
            ("ok","主卧空调已关闭。次卧空调已关闭。"),
            ("ok","家里已确认开启的空调有0台。"),
            ("state_limit","主卧空调设备报告室温：19.1℃（空调已关闭，读数可能未实时刷新）。次卧空调设备报告室温：18.8℃（空调已关闭，读数可能未实时刷新）。"),
            ("state_limit","主卧空调已关闭，无当前运行参数。次卧空调已关闭，无当前运行参数。")])
        self.assertIn("主卧空调\n已关闭。",r.text)
        self.assertIn("次卧空调\n已关闭。",r.text)
        self.assertEqual(r.text.count("读数可能未实时刷新"),2)
        self.assertIn("0台",r.text)

    def test_filter_health_grouped_without_losing_estimate(self):
        r=self.fixture.result("appliance.purifier.filter_health",[
            ("ok","米家净水器PPC滤芯剩余90%，RO滤芯剩余95%。"),
            ("ok","米家净水器设备估计PPC滤芯剩余654天，RO滤芯剩余2427天。"),
            ("ok","米家净水器：PPC滤芯当前未达更换提醒阈值；RO滤芯当前未达更换提醒阈值。")])
        self.assertIn("PPC滤芯：剩余90%，设备估计剩余654天",r.text)
        self.assertIn("RO滤芯：剩余95%，设备估计剩余2427天",r.text)
        self.assertEqual(r.text.count("当前未达更换提醒阈值"),2)
