import unittest
import test_scene_response as scene_tests
from nexora_menu_test.home_response import format_home

class HomePresentationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=scene_tests.MenuResponseTests()
        self.fixture.setUp()

    def test_environment_per_room_and_separate_coverage(self):
        text="主卧温度：21.6℃，主卧湿度：54%；次卧温度：18.9℃，次卧湿度：62%；2个有效监测区域平均温度：20.25℃。1个有效监测区域平均湿度：54%。"
        result=format_home("env",text)
        self.assertIn("主卧：21.6℃ / 54%\n次卧：18.9℃ / 62%",result)
        self.assertIn("平均温度：20.25℃（2个有效监测区域）",result)
        self.assertIn("平均湿度：54%（1个有效监测区域）",result)
        self.assertEqual(format_home("env",result),result)

    def test_unknown_environment_preserves_source(self):
        text="主卧温度：数据不可用；次卧温度：18.9℃，次卧湿度：62%。"
        self.assertEqual(format_home("env",text),text)

    def test_family_caveat_and_battery_attributes(self):
        text="家庭Wi-Fi：1位成员的设备已连接：成员甲；2位未连接：成员乙、成员丙；未配置：成员丁。Wi-Fi仅供在家判断参考。"
        result=format_home("family",text)
        self.assertEqual(result,text.replace("；","\n").replace("。Wi-Fi","。\nWi-Fi"))
        self.assertEqual(format_home("batteries","传感器甲：57%；传感器乙：28%。"),"传感器甲：57%\n传感器乙：28%。")
        self.assertEqual(format_home("water_all","厨房：未检测到浸水；阳台：数据不可用。"),"厨房：未检测到浸水\n阳台：数据不可用。")

    def test_presence_gap_only_deduplicates_agreeing_state(self):
        data=[("ok","阳台：未检测到人体。"),("ok","阳台光照度：7勒克斯。"),("data_gap","阳台：未检测到人体，持续时间数据不可用。")]
        result=self.fixture.result("home.presence.balcony",data)
        self.assertEqual(result.text.count("未检测到人体"),1)
        self.assertIn("持续时间数据不可用",result.text)
        data[2]=("data_gap","阳台：已检测到人体，持续时间数据不可用。")
        result=self.fixture.result("home.presence.balcony",data)
        self.assertIn("未检测到人体",result.text)
        self.assertIn("已检测到人体",result.text)
