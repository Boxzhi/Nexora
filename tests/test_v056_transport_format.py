import unittest
import test_v053_menu_regression as regression
from nexora_menu_test.transport_format import format_query_text,format_query_response

class TransportFormatTests(unittest.TestCase):
    def test_compact_lines_and_paragraphs(self):
        text="标题\r\n\r\n第一行\r\n第二行\n\n第三段\n末行"
        expected="标题\n\n第一行\u2028第二行\n\n第三段\u2028末行"
        self.assertEqual(format_query_text("wechat:a:b",text),expected)
        self.assertEqual(format_query_text("wechat:a:b",expected),expected)
        for cid in (None,"normal","feishu:a:b","wechatish:a:b"):
            self.assertEqual(format_query_text(cid,text),text)

    def test_metadata_preserved(self):
        class R:
            def __init__(self):
                self.payload={"response_type":"action_done","speech":{"plain":{"speech":"甲\n乙","extra_data":{"x":1}}},"data":{"test":42}}
            def as_dict(self):
                return self.payload
            def async_set_speech(self,text,extra_data=None):
                self.payload["speech"]["plain"]={"speech":text,"extra_data":extra_data}
        r=R()
        self.assertIs(format_query_response("wechat:a:b",r),r)
        self.assertEqual(r.payload["speech"]["plain"],{"speech":"甲\u2028乙","extra_data":{"x":1}})
        self.assertEqual(r.payload["data"],{"test":42})

class WechatAdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        regression.CompleteSceneAgentTests.setUp(self)

    async def ask(self,q,cid="a"):
        return await regression.CompleteSceneAgentTests.ask(self,q,cid)

    async def test_scene_and_single_query_format_without_menu_change(self):
        cid="wechat:mock:sender"
        self.assertEqual(await self.ask("help",cid),await self.ask("help","normal"))
        for q in ("最近燃气缴费记录","我家水电气账户概况","我家水电气余额还有多少","有没有欠费的"):
            plain=await self.ask(q,"normal")
            wechat=await self.ask(q,cid)
            self.assertEqual(wechat,format_query_text(cid,plain),q)
            if "\n" in plain.replace("\n\n",""):
                self.assertIn("\u2028",wechat,q)
        self.conv.async_converse.assert_not_awaited()

    async def test_canonical_single_query_format(self):
        cid="utility.gas.basic.balance"
        self.speech[cid]="燃气账户余额：83.36元。\n数据更新时间：2026-11-28 01:00:00。"
        q=self.menu._query(cid,{}).sentence
        plain=await self.ask(q,"normal")
        wechat=await self.ask(q,"wechat:mock:sender")
        self.assertIn("\u2028",wechat)
        self.assertEqual(wechat,format_query_text("wechat:mock:sender",plain))
