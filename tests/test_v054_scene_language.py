import unittest
from test_v053_menu_regression import CATS, SET, mod, build_layout

class SceneLanguageTests(unittest.TestCase):
    def setUp(self):
        self.menu=mod.Menu(CATS,settings=SET)
        self.menu.install_scene_layout(build_layout(self.menu))
        self.index=self.menu.scene_language

    def test_every_scene_has_scoped_path(self):
        self.assertEqual(len(self.index.paths),150)
        for sid,path in self.index.paths.items():
            with self.subTest(scene=sid):
                self.assertEqual(self.index.match(path),sid)

    def test_real_replay_phrases(self):
        for text,sid in (
            ("我家水电气账户概况","scene.utility.summary.primary.overview"),
            ("所有账户概况","scene.utility.summary.all.overview"),
            ("全屋照明概况","scene.lights.all"),
            ("洗衣机当前洗衣进度","scene.appliance.washer.progress"),
            ("全屋环境温湿度","scene.home.env.whole"),
        ):
            self.assertEqual(self.index.match(text),sid)

    def test_no_scope_inference_or_control(self):
        for text in ("账户概况","本月","我家水电气余额还有多少","所有账户呢","不要查全屋照明概况","关闭全屋照明概况","全屋照明概况并且关灯"):
            self.assertIsNone(self.index.match(text))

import test_v053_menu_regression as regression
from test_v053_menu_regression import path_for, INPUTS
from collections import Counter

class SceneLanguageRoutingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        regression.CompleteSceneAgentTests.setUp(self)

    async def ask(self,q,cid="a"):
        return await regression.CompleteSceneAgentTests.ask(self,q,cid)

    async def test_scene_replay_same_members_and_reply(self):
        for phrase in ("我家水电气账户概况","所有账户概况","全屋照明概况","洗衣机当前洗衣进度","全屋环境温湿度"):
            sid=self.menu.scene_language.match(phrase)
            await self.ask("help")
            self.calls.clear()
            expected=await self.ask(path_for(self.menu,sid,"scene"))
            members=Counter(self.calls)
            self.calls.clear()
            actual=await self.ask(phrase,"b")
            self.assertEqual(Counter(self.calls),members,phrase)
            self.assertEqual(actual,expected,phrase)
        self.conv.async_converse.assert_not_awaited()

    async def test_all_scoped_paths_execute_same_plan(self):
        for sid,path in self.menu.scene_language.paths.items():
            with self.subTest(scene=sid):
                self.calls.clear()
                result=await self.ask(path)
                cap=self.menu._parameter_cap(sid)
                if cap.get("parameter"):
                    self.assertIn("请输入",result)
                    result=await self.ask(INPUTS[cap["parameter"]])
                self.assertEqual(Counter(self.calls),Counter(self.menu.scenes[sid].members),result)
        self.conv.async_converse.assert_not_awaited()

    async def test_single_and_followups_stay_precise(self):
        await self.ask("我家水电气账户概况")
        self.calls.clear()
        await self.ask("有没有欠费的")
        self.assertEqual(self.calls,["utility.summary.primary.debts"])
        self.calls.clear()
        await self.ask("所有账户呢")
        self.assertEqual(self.calls,["utility.summary.all.debts_all"])
        self.calls.clear()
        await self.ask("余额呢")
        self.assertEqual(self.calls,["utility.summary.all.balances_all"])
        self.conv.async_converse.assert_not_awaited()

    async def test_compound_never_dispatches(self):
        self.calls.clear()
        result=await self.ask("全屋照明概况，同时关灯")
        self.assertFalse(self.calls)
        self.assertIn("混合",result)
        self.conv.async_converse.assert_not_awaited()
