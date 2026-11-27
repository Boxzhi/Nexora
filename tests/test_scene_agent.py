import unittest
import test_planner_adapter as adapter
from importlib import import_module

class SceneAgentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        adapter.PlannerAdapterTests.setUp(self)
        Node=import_module("nexora_adapter_test.scene_menu").Node
        self.menu.install_scene_layout([Node("scene.utility","scene","水电气",100,alias_of="utility"),
          Node("scene.utility.water","scene.utility","水费",10,alias_of="utility.water"),
          Node("scene.utility.water.balance","scene.utility.water","账户概况",10,
               ("utility.water.balance","utility.water.debt"),anchor="utility.water.balance")])
    async def ask(self,q,cid="a"):
        return await adapter.PlannerAdapterTests.ask(self,q,cid)
    async def test_scene_dispatch_and_context(self):
        await self.ask("help")
        await self.ask("1.1")
        r=await self.ask("1")
        self.assertEqual(set(self.calls),{"utility.water.balance","utility.water.debt"})
        self.assertIn("93.92元",r)
        self.calls.clear()
        await self.ask("有没有欠费的")
        self.assertEqual(self.calls,["utility.water.debt"])
        self.conv.async_converse.assert_not_awaited()
