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
