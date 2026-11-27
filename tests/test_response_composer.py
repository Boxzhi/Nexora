import importlib
import unittest
from test_semantic_lexicon import PKG
bm=importlib.import_module(PKG+".business_model")
qp=importlib.import_module(PKG+".query_planner")
pe=importlib.import_module(PKG+".plan_executor")
rc=importlib.import_module(PKG+".response_composer")

def step(f,t,m):
    return qp.Step(bm.QueryKey(f,t,m),m)
def label(step):
    return step.capability

class ResponseComposerTests(unittest.TestCase):
    def test_closed_ac_duplicate_is_removed_not_invented(self):
        a,b=step("appliance","m","target"),step("appliance","m","temp")
        p=qp.Plan((a,b))
        text="主卧空调已关闭，无当前运行参数。"
        r=pe.PlanRun((pe.Outcome(a,"state_limit",text),pe.Outcome(b,"state_limit",text)))
        c=rc.compose(p,r,label)
        self.assertEqual(c.text,text)
        self.assertTrue(c.primary_completed)

    def test_actual_value_unit_and_missing_data_are_preserved(self):
        a,b=step("utility","g","tier1_remaining"),step("utility","g","tier2_remaining")
        p=qp.Plan((a,b),caveat="以下为阶梯剩余额度，并非实际剩余气量。")
        r=pe.PlanRun((pe.Outcome(a,"ok","第1阶梯剩余气量：377立方米。"),
                      pe.Outcome(b,"data_gap","第2阶梯：数据不可用。")))
        c=rc.compose(p,r,label)
        self.assertIn(p.caveat,c.text)
        self.assertIn("377立方米",c.text)
        self.assertIn("第2阶梯：数据不可用",c.text)
        self.assertNotIn("240",c.text)

    def test_partial_failure_and_optional_skip(self):
        a,b,c=step("appliance","m","target"),step("appliance","m","temp"),step("appliance","m","status")
        p=qp.Plan((a,b),(c,))
        r=pe.PlanRun((pe.Outcome(a,"ok","设定温度：26℃。"),
                      pe.Outcome(b,"error",error="本地查询超时。"),pe.Outcome(c,"skipped")))
        v=rc.compose(p,r,label)
        self.assertIn("26℃",v.text)
        self.assertIn("temp：本地查询超时",v.text)
        self.assertNotIn("status",v.text)
        self.assertFalse(v.primary_completed)

    def test_exact_duplicate_provider_label_cleanup(self):
        a=step("utility","g","balance")
        v=rc.compose(qp.Plan((a,)),pe.PlanRun((pe.Outcome(a,"ok","华润燃气燃气账户余额：83.36元。"),)),label)
        self.assertEqual(v.text,"华润燃气账户余额：83.36元。")
        self.assertTrue(v.primary_completed)

    def test_superseded_and_missing_primary_never_report_success(self):
        a=step("appliance","m","target")
        p=qp.Plan((a,))
        self.assertFalse(rc.compose(p,pe.PlanRun((),True),label).primary_completed)
        self.assertFalse(rc.compose(p,pe.PlanRun(()),label).primary_completed)

    def test_duplicate_values_keep_different_subjects_and_accounts(self):
        a=qp.Step(bm.QueryKey("utility","e","balance",account="j"),"主账户余额")
        b=qp.Step(bm.QueryKey("utility","e","balance",account="l"),"第二账户余额")
        p=qp.Plan((a,b))
        for kind,value in (("ok","余额：20元。"),("data_gap","数据不可用。")):
            r=pe.PlanRun((pe.Outcome(a,kind,value),pe.Outcome(b,kind,value)))
            s=rc.compose(p,r,label).text
            self.assertIn("主账户余额："+value,s)
            self.assertIn("第二账户余额："+value,s)

    def test_response_formatter_preserves_metadata_and_nonplain_speech(self):
        from types import SimpleNamespace
        key=bm.QueryKey("utility","g","balance")
        class Response:
            def __init__(self,kind="action_done",extra=False):
                self.data={"response_type":kind,"speech":{"plain":{"speech":"华润燃气燃气账户余额：83.36元。"}},"data":{"targets":[]}}
                if extra:
                    self.data["speech"]["ssml"]={"speech":"<speak>原文</speak>"}
            def as_dict(self):
                return self.data
            def async_set_speech(self,value,extra_data=None):
                self.data["speech"]["plain"]={"speech":value,"extra_data":extra_data}
        r=Response()
        r.data["speech"]["plain"]["extra_data"]={"marker":"preserve"}
        self.assertIs(rc.format_response(key,r),r)
        self.assertEqual(r.data["speech"]["plain"]["speech"],"华润燃气账户余额：83.36元。")
        self.assertEqual(r.data["data"],{"targets":[]})
        self.assertEqual(r.data["speech"]["plain"]["extra_data"],{"marker":"preserve"})
        for r in (Response("error"),Response(extra=True)):
            rc.format_response(key,r)
            self.assertIn("燃气燃气",r.data["speech"]["plain"]["speech"])

    def test_verified_scene_contracts_and_partial_fallback(self):
        from types import SimpleNamespace
        def build(f,target,goal,metrics,texts,caveat="",kinds=None):
            steps=tuple(qp.Step(bm.QueryKey(*k),k[2]) for k in metrics)
            focus=SimpleNamespace(subject=SimpleNamespace(family=f,target=target),goal=goal)
            p=qp.Plan(steps,focus=focus,caveat=caveat)
            r=pe.PlanRun(tuple(pe.Outcome(x,k,text) for x,k,text in zip(steps,kinds or ["ok"]*len(steps),texts)))
            return p,r
        p,r=build("appliance","w","progress",[("appliance","w",m) for m in ("status","phase","remaining")],
            ["海尔洗衣机正在运行，程序：混合。","海尔洗衣机洗涤阶段：漂洗。","海尔洗衣机正在运行，设备报告剩余时间：10分钟。"])
        self.assertEqual(rc.compose(p,r,label).text,"海尔洗衣机正在运行混合程序，目前处于漂洗阶段，设备报告剩余10分钟。")
        missing=pe.PlanRun((r.outcomes[0],pe.Outcome(p.primary[1],"error",error="超时"),r.outcomes[2]))
        self.assertIn("phase：超时",rc.compose(p,missing,label).text)
        p,r=build("appliance","p","overview",[("appliance","p",m) for m in ("status","filters","replace")],
            ["米家净水器：待机中。","米家净水器PPC滤芯剩余90.0%，RO滤芯剩余95.0%。","米家净水器：PPC滤芯当前未达更换提醒阈值；RO滤芯当前未达更换提醒阈值。"])
        self.assertEqual(rc.compose(p,r,label).text,"米家净水器待机中。\nPPC滤芯剩余90%，RO滤芯剩余95%，均未达到更换提醒阈值。")
        changed=pe.PlanRun(r.outcomes[:2]+(pe.Outcome(p.primary[2],"ok","PPC滤芯需要更换，RO滤芯当前未达更换提醒阈值。"),))
        self.assertIn("PPC滤芯需要更换",rc.compose(p,changed,label).text)
        p,r=build("appliance","m","temperature_unspecified",[("appliance","m","target"),("appliance","m","temp")],
            ["主卧空调已关闭，无当前运行参数。","主卧空调设备报告室温：18.9℃（空调已关闭，读数可能未实时刷新）。"],kinds=["state_limit","ok"])
        self.assertEqual(rc.compose(p,r,label).text,"主卧空调已关闭，暂无运行设定温度。最近报告室温18.9℃，读数可能未实时刷新。")
        p,r=build("home","阳台","brightness_unspecified",[("home","阳台","lux"),("lights","yang_tai","list_on")],
            ["阳台光照度：4勒克斯。","阳台1组灯具均已关闭。"],caveat="环境光照度与灯具开关状态是不同指标。")
        self.assertEqual(rc.compose(p,r,label).text,"阳台环境光照度为4勒克斯，1组灯具均已关闭。")
        wrong=pe.PlanRun((r.outcomes[0],pe.Outcome(p.primary[1],"ok","餐厅2组灯具均已关闭。")))
        self.assertIn(p.caveat,rc.compose(p,wrong,label).text)
        self.assertIn("餐厅2组灯具均已关闭",rc.compose(p,wrong,label).text)

    def test_overview_paragraphs_preserve_every_character(self):
        s="家庭Wi-Fi：2位成员的设备已连接。入户门锁：状态无法确认。15组灯光中，1组开启。已监测家电运行：洗衣机（漂洗）；热水器燃烧状态未统计。3个有效监测区域平均温度：18.3℃。未确认到异常，但部分项目无法核实；数据不可用：入户门锁。"
        v=rc.normalize_speech(bm.QueryKey("home","all","overview"),s)
        self.assertEqual(v.replace("\n",""),s)
        self.assertEqual(len(v.splitlines()),6)

    def test_numeric_formatting_is_lossless_and_does_not_touch_money(self):
        for family,target,metric,before,after in [
            ("appliance","w","temp","海尔洗衣机设定洗涤水温：30.0℃。","海尔洗衣机设定洗涤水温：30℃。"),
            ("appliance","w","spin","海尔洗衣机设定脱水转速：800.0转/分钟。","海尔洗衣机设定脱水转速：800转/分钟。"),
            ("appliance","w","cycles","海尔洗衣机设备报告累计洗涤周期：644.0次。","海尔洗衣机设备报告累计洗涤周期：644次。"),
            ("appliance","w","energy","海尔洗衣机设备报告累计用电：106.95度。","海尔洗衣机设备报告累计用电：106.95度。"),
            ("appliance","p","filters","米家净水器PPC滤芯剩余90.0%，RO滤芯剩余95.0%。","米家净水器PPC滤芯剩余90%，RO滤芯剩余95%。"),
            ("utility","g","balance","华润燃气燃气账户余额：83.00元。","华润燃气账户余额：83.00元。"),
            ("utility","e","cost","京华府2026年10月电费：121.20元（月度账单）。","京华府2026年10月电费：121.20元（月度账单）。"),
            ("appliance","b","heatremain","米家浴霸浴霸延时关闭：未启用。","米家浴霸延时关闭：未启用。"),
            ("home","主卧","temp","主卧温度：-3.0℃，设备版本1.0.0。","主卧温度：-3℃，设备版本1.0.0。"),
        ]:
            with self.subTest(before=before):
                key=bm.QueryKey(family,target,metric)
                self.assertEqual(rc.normalize_speech(key,before),after)
                self.assertEqual(rc.normalize_speech(key,after),after)
