import unittest
import test_v053_menu_regression as regression

class SceneVocabularyTests(unittest.TestCase):
    def setUp(self):
        self.menu=regression.mod.Menu(regression.CATS,settings=regression.SET)
        self.menu.install_scene_layout(regression.build_layout(self.menu))
        self.index=self.menu.scene_language

    def test_scoped_vocabulary_covers_every_scene(self):
        self.assertEqual(len(self.index.paths),150)
        for sid,path in self.index.paths.items():
            self.assertEqual(self.index.match(path),sid)
            self.assertGreaterEqual(sum(v==sid for v in self.index.exact.values()),2,sid)

    def test_payment_and_environment_replays(self):
        cases={
            "燃气缴费查询最近缴费记录":"scene.utility.gas.pay.recent",
            "最近燃气缴费记录":"scene.utility.gas.pay.recent",
            "上次燃气缴费情况":"scene.utility.gas.pay.recent",
            "燃气缴费查询年度缴费统计":"scene.utility.gas.pay.annual",
            "今年燃气缴费情况":"scene.utility.gas.pay.annual",
            "家里温湿度怎么样":"scene.home.env.whole",
            "家里灯光怎么样":"scene.lights.all",
            "客厅照明状态":"scene.lights.rooms.ke_ting.overview",
            "洗衣机的洗涤参数":"scene.appliance.washer.settings",
        }
        for phrase,sid in cases.items():
            self.assertEqual(self.index.match(phrase),sid,phrase)

    def test_precise_and_ambiguous_phrases_not_expanded(self):
        for phrase in ("今年燃气交了多少钱","最近燃气缴费时间","最近燃气缴费金额","账户余额","本月","故障状态","不要查最近燃气缴费记录","最近燃气缴费记录并关灯"):
            self.assertIsNone(self.index.match(phrase),phrase)
