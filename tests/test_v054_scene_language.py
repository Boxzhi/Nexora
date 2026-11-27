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
