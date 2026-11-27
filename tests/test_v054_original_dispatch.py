"""All original registered capabilities execute through the internal regression route."""
import json
import unittest
import test_v053_menu_regression as regression

class OriginalDispatchTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        regression.CompleteSceneAgentTests.setUp(self)

    async def ask(self,q,cid="a"):
        return await regression.CompleteSceneAgentTests.ask(self,q,cid)

    async def test_original_443_dispatches_without_public_detail_menu(self):
        count=0
        self.assertEqual(await self.ask("detail"),await self.ask("help"))
        for cid in self.menu.capabilities:
            with self.subTest(capability=cid):
                self.menu._render(("u",None,None,"a"),"root",lambda c:True)
                self.calls.clear()
                result=await self.ask(regression.path_for(self.menu,cid,"root"))
                cap=self.menu._parameter_cap(cid)
                if cap.get("parameter"):
                    self.assertIn("请输入",result)
                    result=await self.ask(regression.INPUTS[cap["parameter"]])
                self.assertEqual(self.calls,[cid],(cid,result))
                count+=1
        self.assertEqual(count,443)
        self.conv.async_converse.assert_not_awaited()
        print("V054_ORIGINAL_AGENT_DISPATCH="+json.dumps({"passed":count}))
