import json
import unittest
from datetime import date
from test_menu import mod, BASE, SET
from nexora_menu_test.scene_layout import build_layout
from nexora_menu_test.query_planner import QueryPlanner
from nexora_menu_test.plan_executor import Outcome,PlanRun
from nexora_menu_test.response_composer import compose

class MenuResponseTests(unittest.TestCase):
    def setUp(self):
        self.m=mod.Menu([json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))],settings=SET)
        self.m.install_scene_layout(build_layout(self.m))
        self.p=QueryPlanner(self.m)
    def result(self,scene,values,params=None,visible=lambda c:True):
        plan=self.p.menu_plan("scene."+scene,params or {},visible,None,date(2026,11,27))
        steps=plan.primary+plan.supplements
        self.assertEqual(len(steps),len(values))
        run=PlanRun(tuple(Outcome(s,*v) for s,v in zip(steps,values)))
        return compose(plan,run,lambda s:self.m.capabilities[s.capability]["name"])
    def test_same_month_and_coverage(self):
        r=self.result("utility.electric.j.monthly.explicit",[
            ("ok","示例账户2026年4月用电量：120度（月度账单）。"),
            ("ok","示例账户2026年4月电费：69.20元（月度账单）。")],{"year":2026,"month":4})
        self.assertEqual(r.text,"示例账户 · 2026年4月账单\n\n用电量：120度\n电费：69.20元\n\n（月度账单）")
    def test_month_partial_not_mislabelled(self):
        r=self.result("utility.electric.j.monthly.current",[
            ("ok","示例账户2026年5月用电量：25度（截至2026-05-20，20天有效记录）。"),
            ("data_gap","示例账户2026年5月电费：暂无该月正式账单。")])
        self.assertIn("截至2026-05-20",r.text)
        self.assertIn("暂无该月正式账单",r.text)
        self.assertTrue(r.primary_completed)
        self.assertNotIn("（月度账单）",r.text)
    def test_annual_partial_preserved(self):
        q="（4期有效账单；本月暂无账单）"
        r=self.result("utility.electric.j.annual.year",[
            ("partial_data","示例账户2026年账单累计用电量：500度"+q+"。"),
            ("partial_data","示例账户2026年账单累计电费：260.00元"+q+"。")])
        self.assertEqual(r.text.count(q),1)
        self.assertIn("260.00元",r.text)
    def test_different_accounts_never_merge(self):
        r=self.result("utility.electric.j.monthly.previous",[
            ("ok","示例甲2026年4月用电量：100度（月度账单）。"),
            ("ok","示例乙2026年4月电费：58.00元（月度账单）。")])
        self.assertIn("示例甲2026",r.text)
        self.assertIn("示例乙2026",r.text)
    def test_payment_and_partial_error(self):
        r=self.result("utility.gas.pay.recent",[
            ("ok","华润燃气最近缴费金额：50.00元。"),
            ("ok","华润燃气最近缴费时间：2026-05-20 10:20:30。"),
            ("data_gap","华润燃气最近缴费渠道：数据不可用。"),
            ("ok","华润燃气缴费历史更新时间：2026-05-20 11:20:30。")])
        self.assertIn("缴费金额：50.00元",r.text)
        self.assertIn("缴费渠道：数据不可用",r.text)
        self.assertIn("数据更新时间：2026-05-20 11:20:30",r.text)
        self.assertEqual(r.text.count("华润燃气"),1)
        r=self.result("utility.gas.pay.annual",[("ok","华润燃气年度燃气缴费金额：150.00元。"),("error","","接口失败"),("ok","华润燃气缴费历史更新时间：2026-05-20 11:20:30。")])
        self.assertIn("年度缴费次数：接口失败",r.text)
        self.assertFalse(r.primary_completed)
    def test_fixture_state_limits_and_visibility(self):
        r=self.result("lights.fixtures.dining_fan",[
            ("ok","餐厅风扇灯当前已关闭。"),("state_limit","餐厅风扇灯当前已关闭，无法获取实时亮度。"),("state_limit","餐厅风扇灯当前已关闭，无法获取实时色温。")])
        self.assertIn("状态：已关闭",r.text)
        self.assertIn("实时亮度、色温：灯具已关闭，无法获取",r.text)
        r=self.result("lights.fixtures.dining_fan",[("ok","餐厅风扇灯当前已关闭。")],visible=lambda c:c["id"].endswith(".single_state"))
        self.assertNotIn("亮度",r.text)
        self.assertNotIn("色温",r.text)
    def test_light_state_does_not_guess_offline_count(self):
        r=self.result("lights.rooms.ke_ting.overview",[
            ("ok","客厅共有3组灯具。"),("ok","客厅当前有1组灯具开启：示例灯。"),("ok","客厅当前有1组灯具关闭：另一盏灯。"),("data_gap","客厅离线状态无法确认。")])
        self.assertIn("灯具总数：3组",r.text)
        self.assertIn("已开启：1组（示例灯）",r.text)
        self.assertIn("客厅离线状态无法确认",r.text)
        self.assertNotIn("全部关闭",r.text)
    def test_appliance_unknown_and_stale_remain(self):
        r=self.result("appliance.ac.master.overview",[
            ("ok","主卧空调已关闭。"),("state_limit","主卧空调设备报告室温：20.5℃（空调已关闭，读数可能未实时刷新）。"),("skipped",""),("skipped",""),("skipped","")])
        self.assertIn("主卧空调 · 运行状态",r.text)
        self.assertIn("读数可能未实时刷新",r.text)
        self.assertNotIn("查询未完成",r.text)
        r=self.result("appliance.purifier.water",[
            ("ok","米家净水器设备报告出水TDS：25.0（TDS不能单独判断饮水安全）。"),("ok","米家净水器设备报告水温：16.0℃。")])
        self.assertIn("TDS不能单独判断饮水安全",r.text)
        self.assertIn("16℃",r.text)
    def test_presence_consistent_and_inconsistent(self):
        r=self.result("home.presence.balcony",[
            ("ok","阳台：未检测到人体。"),("ok","阳台光照度：7勒克斯。"),("ok","阳台：未检测到人体，设备报告已持续12分钟。")])
        self.assertEqual(r.text.count("未检测到人体"),1)
        r=self.result("home.presence.balcony",[
            ("ok","阳台：未检测到人体。"),("ok","阳台光照度：7勒克斯。"),("ok","阳台：已检测到人体，设备报告已持续1分钟。")])
        self.assertIn("未检测到人体",r.text)
        self.assertIn("已检测到人体",r.text)
