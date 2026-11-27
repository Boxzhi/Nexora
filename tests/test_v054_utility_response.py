import unittest
import test_scene_response as scene_tests
from nexora_menu_test.utility_response import format_aggregate

BAL="京华府电费余额89.38元；燃气费余额83.36元；水费余额93.92元。"
DEBT="京华府电费：当前无欠费（按余额判断）；燃气：当前无欠费；水务：当前无欠费。"
LOW="京华府电费：89.38元，余额正常；燃气费：83.36元，余额正常；水费：93.92元，余额正常。"

class UtilityPresentationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=scene_tests.MenuResponseTests()
        self.fixture.setUp()

    def test_single_aggregate_and_idempotence(self):
        for metric,text in (("balances",BAL),("debts",DEBT),("low",LOW)):
            v=format_aggregate(metric,text)
            self.assertEqual(len(v.splitlines()),3)
            self.assertEqual(format_aggregate(metric,v),v)
        self.assertIn("京华府电费：89.38元",format_aggregate("balances",BAL))
        self.assertIn("按余额判断",format_aggregate("debts",DEBT))

    def test_overview_merge_preserves_qualifications(self):
        r=self.fixture.result("utility.summary.primary.overview",[( "ok",BAL),("ok",DEBT),("ok",LOW)])
        for val in ("89.38元","83.36元","93.92元"):
            self.assertEqual(r.text.count(val),1)
        self.assertIn("当前无欠费（按余额判断）",r.text)
        self.assertEqual(r.text.count("余额正常"),3)

    def test_gap_and_conflict_do_not_invent_facts(self):
        bal=BAL.replace("89.38元","数据不可用")
        debt=DEBT.replace("当前无欠费（按余额判断）","欠费情况暂无法确认")
        low=LOW.replace("89.38元，余额正常","数据不可用，暂无法判断")
        r=self.fixture.result("utility.summary.primary.overview",[("partial_data",bal),("partial_data",debt),("partial_data",low)])
        self.assertIn("京华府电费：数据不可用",r.text)
        self.assertIn("欠费情况暂无法确认",r.text)
        self.assertIn("暂无法判断",r.text)
        self.assertNotIn("无需充值",r.text)
        r=self.fixture.result("utility.summary.primary.overview",[("ok",BAL),("ok",DEBT),("ok",LOW.replace("89.38元","80.00元"))])
        self.assertIn("89.38元",r.text)
        self.assertIn("80.00元",r.text)
        self.assertEqual(r.text.count("83.36元"),2)

    def test_unknown_or_duplicate_accounts_unchanged(self):
        for value in ("京华府电费余额10元；未知字段","京华府电费余额10元；京华府电费余额20元"):
            self.assertEqual(format_aggregate("balances",value),value)
