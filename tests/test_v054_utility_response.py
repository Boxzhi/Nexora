import unittest
import test_scene_response as scene_tests
from nexora_menu_test.utility_response import format_aggregate

BAL="示例甲账户电费余额91.23元；燃气费余额72.34元；水费余额63.45元。"
DEBT="示例甲账户电费：当前无欠费（按余额判断）；燃气：当前无欠费；水务：当前无欠费。"
LOW="示例甲账户电费：91.23元，余额正常；燃气费：72.34元，余额正常；水费：63.45元，余额正常。"

class UtilityPresentationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=scene_tests.MenuResponseTests()
        self.fixture.setUp()

    def test_single_aggregate_and_idempotence(self):
        for metric,text in (("balances",BAL),("debts",DEBT),("low",LOW)):
            v=format_aggregate(metric,text)
            self.assertEqual(len(v.splitlines()),3)
            self.assertEqual(format_aggregate(metric,v),v)
        self.assertIn("示例甲账户电费：91.23元",format_aggregate("balances",BAL))
        self.assertIn("按余额判断",format_aggregate("debts",DEBT))

    def test_overview_merge_preserves_qualifications(self):
        r=self.fixture.result("utility.summary.primary.overview",[( "ok",BAL),("ok",DEBT),("ok",LOW)])
        for val in ("91.23元","72.34元","63.45元"):
            self.assertEqual(r.text.count(val),1)
        self.assertIn("当前无欠费（按余额判断）",r.text)
        self.assertEqual(r.text.count("余额正常"),3)

    def test_gap_and_conflict_do_not_invent_facts(self):
        bal=BAL.replace("91.23元","数据不可用")
        debt=DEBT.replace("当前无欠费（按余额判断）","欠费情况暂无法确认")
        low=LOW.replace("91.23元，余额正常","数据不可用，暂无法判断")
        r=self.fixture.result("utility.summary.primary.overview",[("partial_data",bal),("partial_data",debt),("partial_data",low)])
        self.assertIn("示例甲账户电费：数据不可用",r.text)
        self.assertIn("欠费情况暂无法确认",r.text)
        self.assertIn("暂无法判断",r.text)
        self.assertNotIn("无需充值",r.text)
        r=self.fixture.result("utility.summary.primary.overview",[("ok",BAL),("ok",DEBT),("ok",LOW.replace("91.23元","80.00元"))])
        self.assertIn("91.23元",r.text)
        self.assertIn("80.00元",r.text)
        self.assertEqual(r.text.count("72.34元"),2)

    def test_unknown_or_duplicate_accounts_unchanged(self):
        for value in ("示例甲账户电费余额10元；未知字段","示例甲账户电费余额10元；示例甲账户电费余额20元"):
            self.assertEqual(format_aggregate("balances",value),value)
