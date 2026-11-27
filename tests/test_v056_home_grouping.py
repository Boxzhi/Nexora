import unittest
import test_scene_response as scene_tests
from nexora_menu_test.home_response import format_overview

class HomeGroupingTests(unittest.TestCase):
    def setUp(self):
        self.fixture=scene_tests.MenuResponseTests()
        self.fixture.setUp()
    def test_room_presence_and_lux(self):
        data=[
            ("ok","玄关：未检测到人体；客厅：未检测到人体；阳台：未检测到人体；厨房：未检测到人体；卫生间：未检测到人体。"),
            ("ok","玄关：0勒克斯；客厅：0勒克斯；阳台：4勒克斯；厨房：0勒克斯；卫生间：2勒克斯。"),
            ("ok","光照度最高的有效监测区域：阳台，4勒克斯。"),
            ("ok","光照度最低的有效监测区域：玄关、客厅、厨房，0勒克斯。"),
        ]
        r=self.fixture.result("home.presence.whole",data)
        self.assertIn("阳台：未检测到人体 · 4 lx",r.text)
        self.assertIn("卫生间：未检测到人体 · 2 lx",r.text)
        self.assertIn("最高光照（有效区域）：阳台 4 lx",r.text)
        self.assertIn("最低光照（有效区域）：玄关、客厅、厨房 0 lx",r.text)
        self.assertNotIn("勒克斯",r.text)
        data[1]=("data_gap","玄关：0勒克斯；客厅：数据不可用。")
        r=self.fixture.result("home.presence.whole",data)
        self.assertIn("客厅：数据不可用",r.text)
        self.assertNotIn("阳台：未检测到人体 ·",r.text)
    def test_region_order_and_conflict(self):
        data=[("ok","阳台：未检测到人体。"),("ok","阳台光照度：4勒克斯。"),("ok","阳台：未检测到人体，设备报告已持续0分钟。")]
        r=self.fixture.result("home.presence.balcony",data)
        self.assertEqual(r.text.count("未检测到人体"),1)
        self.assertLess(r.text.index("设备报告已持续"),r.text.index("光照度"))
        data[2]=("ok","阳台：已检测到人体，设备报告已持续0分钟。")
        r=self.fixture.result("home.presence.balcony",data)
        self.assertIn("未检测到人体",r.text)
        self.assertIn("已检测到人体",r.text)
    def test_environment_statistics(self):
        data=[("ok","主卧温度：20.5℃，主卧湿度：55%；次卧温度：16.9℃，次卧湿度：63%；3个有效监测区域平均温度：17.9℃。2个有效监测区域平均湿度：61.3%。"),
              ("ok","温度最高的有效监测区域：主卧，20.5℃。"),
              ("ok","温度最低的有效监测区域：客餐厅，16.2℃。"),
              ("ok","湿度最高的有效监测区域：客餐厅，66%。"),
              ("ok","湿度最低的有效监测区域：主卧，55%。")]
        r=self.fixture.result("home.env.whole",data)
        self.assertIn("平均温度：17.9℃（3个有效监测区域）",r.text)
        self.assertIn("平均湿度：61.3%（2个有效监测区域）\n\n最高温度（有效区域）：主卧 20.5℃",r.text)
        data[-1]=("data_gap","最低湿度：数据不可用。")
        r=self.fixture.result("home.env.whole",data)
        self.assertIn("最低湿度：数据不可用。",r.text)
    def test_overview_replay_preserves_all_qualifiers(self):
        parts=["家庭Wi-Fi：2位成员的设备已连接；未配置：成员甲。Wi-Fi仅供在家判断参考。",
               "入户门锁：状态无法确认；最近一次事件为上锁（历史记录，不代表当前状态）。",
               "15组灯光均已关闭。",
               "已监测家电运行：无；热水器燃烧状态未统计。",
               "3个有效监测区域平均温度：17.9℃。3个有效监测区域平均湿度：61.3%。",
               "未确认到异常，但部分项目无法核实；数据不可用：入户门锁。未监测窗户、实时烟雾和燃气泄漏；洗衣机关机时不判断故障。"]
        r=format_overview("".join(parts))
        self.assertTrue(r.startswith("全屋概况\n\n家庭成员\n"))
        self.assertEqual(format_overview(r),r)
        for part in parts:
            self.assertIn(part,r)
        self.assertIn("门锁\n入户门锁",r)
        self.assertIn("安全及异常\n未确认到异常",r)

    def test_overview_partial_and_unknown_shapes_keep_source(self):
        for raw in ("全屋状态数据不可用。","家庭Wi-Fi：数据不可用。","入户门锁：状态无法确认。"):
            with self.subTest(raw=raw):
                result=format_overview(raw)
                self.assertEqual(result,"全屋概况\n\n"+raw)
                self.assertEqual(format_overview(result),result)
        self.assertEqual(format_overview(""),"")
        self.assertEqual(format_overview("全屋概况"),"全屋概况")

    def test_lux_units_and_extrema_preserve_qualifiers(self):
        from nexora_menu_test.home_response import format_lux
        from nexora_menu_test.response_composer import normalize_speech
        from nexora_menu_test.business_model import QueryKey
        cases=[
            ("lux","阳台光照度：4.5勒克斯。","阳台光照度：4.5 lx。"),
            ("lux_max","光照度最高的有效监测区域：阳台，4勒克斯。","最高光照（有效区域）：阳台 4 lx"),
            ("lux_min","光照度最低的有效监测区域：玄关、客厅、厨房，0勒克斯。","最低光照（有效区域）：玄关、客厅、厨房 0 lx"),
            ("lux_max","光照度最高的有效监测区域：数据不可用。","光照度最高的有效监测区域：数据不可用。"),
            ("lux_all","玄关：0勒克斯；阳台：数据不可用。","玄关：0 lx\n阳台：数据不可用。"),
            ("lux_max","光照度最高的有效监测区域：阳台，4勒克斯（部分区域数据不可用）。","光照度最高的有效监测区域：阳台，4 lx（部分区域数据不可用）。"),
        ]
        for metric,raw,expected in cases:
            with self.subTest(metric=metric,raw=raw):
                key=QueryKey("home","all" if metric!="lux" else "阳台",metric)
                actual=normalize_speech(key,raw)
                self.assertEqual(actual,expected)
                self.assertEqual(normalize_speech(key,actual),actual)
        self.assertEqual(normalize_speech(QueryKey("home","all","overview"),"设备数据不可用。"),"全屋概况\n\n设备数据不可用。")
        self.assertEqual(normalize_speech(QueryKey("lights","阳台","brightness"),"灯具亮度：10%。"),"灯具亮度：10%。")
