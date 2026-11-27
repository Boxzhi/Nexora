import unittest
import test_scene_response as scene_tests

WATER=[
    ("ok","抚州公用水务本期用水量：18吨（账单月份：202611）。"),
    ("ok","抚州公用水务本期水费：44.40元（账单月份：202611）。"),
    ("ok","抚州公用水务最近抄表日期：2026-11-20。"),
    ("ok","抚州公用水务本期表读数：210立方米（账单月份：202611）。"),
]
GAS=[
    ("ok","华润燃气本期用气量：28立方米（账单月份：2026-11）。"),
    ("ok","华润燃气本期燃气账单：89.32元（账单月份：2026-11）。"),
    ("ok","华润燃气上期用气量：19立方米（抄表日期：2026-10-24）。"),
    ("ok","华润燃气最近抄表日期：2026-11-24。"),
    ("ok","华润燃气本期表读数：377立方米（账单月份：2026-11）。"),
    ("ok","华润燃气本期结算状态：全部结清（账单月份：2026-11）。"),
    ("ok","华润燃气本年累计用气量：195立方米。"),
]

class LatestBillTests(unittest.TestCase):
    def setUp(self):
        self.fixture=scene_tests.MenuResponseTests()
        self.fixture.setUp()

    def test_water_replay(self):
        r=self.fixture.result("utility.water.bill",WATER)
        self.assertEqual(r.text,"抚州公用水务 · 本期账单\n\n账单月份：2026-11\n本期用水量：18吨\n本期水费：44.40元\n\n最近抄表日期：2026-11-20\n本期表读数：210立方米")

    def test_gas_replay(self):
        r=self.fixture.result("utility.gas.bill",GAS)
        self.assertEqual(r.text.count("账单月份"),1)
        for part in ("2026-11","28立方米","89.32元","全部结清","2026-11-24","377立方米","19立方米（抄表日期：2026-10-24）","195立方米"):
            self.assertIn(part,r.text)

    def test_conflicting_or_missing_period_preserved(self):
        for replacement in [
            ("ok",WATER[1][1].replace("202611","202610")),
            ("data_gap","抚州公用水务本期水费：数据不可用。"),
            ("ok",WATER[1][1].replace("抚州公用水务","其他水务")),
        ]:
            values=list(WATER)
            values[1]=replacement
            r=self.fixture.result("utility.water.bill",values)
            self.assertIn(WATER[0][1],r.text)
            self.assertIn(replacement[1],r.text)
