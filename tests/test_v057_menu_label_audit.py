"""Independent audit from the actual rendered-layout nodes, not the phrase index."""
import json
import unittest
from collections import defaultdict
import test_v053_menu_regression as regression
from nexora_menu_test.semantic import normalize, SemanticIndex

class MenuLabelAudit(unittest.TestCase):
    def setUp(self):
        self.menu=regression.mod.Menu(regression.CATS,settings=regression.SET)
        self.menu.install_scene_layout(regression.build_layout(self.menu))

    def test_inventory_all_scene_labels_and_scoped_paths(self):
        m=self.menu
        labels=defaultdict(list)
        for sid in m.scenes:
            labels[normalize(m.items[sid].name)].append(sid)
        rows=[]
        for sid in m.scenes:
            label=m.items[sid].name
            path=m.scene_language.paths[sid]
            self.assertEqual(m.scene_language.match(path),sid)
            key=normalize(label)
            rows.append({"id":sid,"label":label,"duplicate":len(labels[key])>1,
                         "bare_match":m.scene_language.match(label)})
        self.assertEqual(len(rows),150)
        self.assertEqual(len({r["id"] for r in rows}),150)
        print("V057_MENU_LABEL_INVENTORY="+json.dumps(rows,ensure_ascii=False))
        print("V057_MENU_LABEL_BASELINE="+json.dumps({
            "scenes":len(rows),"unique_label_scenes":sum(not r["duplicate"] for r in rows),
            "duplicate_label_scenes":sum(r["duplicate"] for r in rows),
            "direct_index_matches":sum(r["bare_match"]==r["id"] for r in rows),
            "unmatched_unique_labels":[r["label"] for r in rows if not r["duplicate"] and r["bare_match"]!=r["id"]]
        },ensure_ascii=False))

    def test_every_actual_label_has_independent_expected_disposition(self):
        m=self.menu
        index=m.scene_language
        seen=defaultdict(set)
        for sid,node in m.items.items():
            if sid.startswith("scene."):
                seen[normalize(node.name)].add(sid)
        original=SemanticIndex(m)
        scope_labels={"最近缴费记录","年度缴费统计","各阶梯详细数据","用水用电统计",
                      "取暖及温度","通风及吹风","杀菌状态","延时关闭","水质及水温"}
        counts=defaultdict(int)
        for sid,spec in m.scenes.items():
            name=m.items[sid].name
            key=normalize(name)
            with self.subTest(scene=sid,label=name):
                disposition=index.bare_status[sid]
                counts[disposition]+=1
                if disposition=="direct":
                    self.assertEqual(index.match(name),sid)
                    self.assertEqual(seen[key],{sid})
                    self.assertNotIn(key,scope_labels)
                    self.assertFalse(sid.startswith(("scene.home.env.","scene.home.presence.")) and not sid.endswith(".whole"))
                elif disposition=="scope_required":
                    self.assertIsNone(index.match(name))
                    self.assertIn(key,index.scope_required)
                    self.assertTrue(len(seen[key])>1 or key in scope_labels or
                                    sid.startswith(("scene.home.env.","scene.home.presence.")))
                else:
                    self.assertEqual(disposition,"existing_route")
                    self.assertNotEqual(index.match(name),sid)
                    choices=original.exact.get(key,set()) | original.aliases.get(key,set())
                    self.assertTrue(choices or key in original.clarifications or
                                    key in m.scene_aliases or key in index.ambiguous or index.match(name))
        self.assertEqual(sum(counts.values()),150)
        self.assertEqual(index.match("全屋感应概况"),"scene.home.presence.whole")
        self.assertEqual(index.match("全屋环境"),"scene.home.env.whole")
        self.assertIsNone(index.match("卫生间"))
        self.assertIsNone(index.match("最近缴费记录"))
        self.assertIsNone(index.match("本月"))
        print("V057_MENU_LABEL_DISPOSITIONS="+json.dumps(dict(counts)))

class MenuLabelDispatchAudit(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        regression.CompleteSceneAgentTests.setUp(self)

    async def ask(self,q,cid="a"):
        return await regression.CompleteSceneAgentTests.ask(self,q,cid)

    async def test_direct_labels_execute_same_members_as_number_menu(self):
        from collections import Counter
        count=0
        for sid,spec in self.menu.scenes.items():
            label=self.menu.items[sid].name
            if self.menu.scene_language.bare_status[sid]!="direct":
                continue
            with self.subTest(scene=sid,label=label):
                await self.ask("exit")
                self.calls.clear()
                answer=await self.ask(label)
                cap=self.menu._parameter_cap(sid)
                if cap.get("parameter"):
                    self.assertIn("请输入",answer)
                    answer=await self.ask(regression.INPUTS[cap["parameter"]])
                self.assertEqual(Counter(self.calls),Counter(spec.members),answer)
                count+=1
        self.assertGreater(count,1)
        self.conv.async_converse.assert_not_awaited()
        print("V057_DIRECT_LABEL_DISPATCH="+json.dumps({"scenes":count}))

    async def test_scope_required_and_precise_read_stay_safe(self):
        for label in ("最近缴费记录","年度缴费统计","账户概况","本月"):
            await self.ask("exit")
            self.calls.clear()
            answer=await self.ask(label)
            self.assertFalse(self.calls,label)
            self.assertIn("请明确",answer,label)
        self.calls.clear()
        await self.ask("全屋感应概况")
        self.assertEqual(set(self.calls),set(self.menu.scenes["scene.home.presence.whole"].members))
        self.conv.async_converse.assert_not_awaited()


class RegistryCollisionTests(unittest.TestCase):
    def test_extension_collision_requires_scope(self):
        custom={"schema_version":1,"module":{"id":"extra","name":"扩展模块","order":500},
                "categories":[{"id":"extra.info","name":"扩展信息","order":10}],
                "capabilities":[{"id":"extra.info.read","category":"extra.info","name":"全屋感应概况","sentence":"查询扩展信息","intent":"ExtraQuery","slots":{},"read_only":True,"order":10}]}
        m=regression.mod.Menu(regression.CATS+[custom],settings=regression.SET)
        m.install_scene_layout(regression.build_layout(m))
        idx=m.scene_language
        sid="scene.home.presence.whole"
        self.assertIsNone(idx.match("全屋感应概况"))
        self.assertEqual(idx.match(idx.paths[sid]),sid)
        self.assertEqual(idx.bare_status[sid],"scope_required")

    def test_existing_exact_metric_is_not_overridden_by_new_label(self):
        import copy
        cats=copy.deepcopy(regression.CATS)
        cap=next(c for cat in cats for c in cat["capabilities"] if c["id"]=="home.access.door.lock_all")
        cap["sentence"]="全屋感应概况"
        m=regression.mod.Menu(cats,settings=regression.SET)
        m.install_scene_layout(regression.build_layout(m))
        idx=m.scene_language
        self.assertIsNone(idx.match("全屋感应概况"))
        self.assertEqual(idx.bare_status["scene.home.presence.whole"],"existing_route")
        self.assertEqual(SemanticIndex(m).match("全屋感应概况").capability,cap["id"])

    def test_hidden_scene_does_not_disambiguate_or_execute(self):
        m=regression.mod.Menu(regression.CATS,settings=regression.SET)
        m.install_scene_layout(regression.build_layout(m))
        idx=m.scene_language
        sid="scene.home.access.windows"
        self.assertEqual(idx.match("窗户状态"),sid)
        hidden=set(m.scenes[sid].members)
        result=m.select_scene("test",sid,lambda c:c["id"] not in hidden)
        self.assertIsNone(result.scene)
        self.assertIn("不可用",result.text)
        self.assertIsNone(idx.match("账户余额"))
