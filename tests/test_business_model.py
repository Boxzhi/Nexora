"""Phase-one business model audit against the original four catalogs."""
from collections import Counter
from dataclasses import replace
import importlib
import json
import unittest
from test_semantic_lexicon import BASE, PKG, mod, lex

bm = importlib.import_module(PKG+".business_model")

class BusinessModelTests(unittest.TestCase):
    def setUp(self):
        self.menu=mod.Menu([json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))],
             settings={"primary_label":"主账户","secondary_label":"第二账户","secondary":"次住所"})
        self.registry=bm.BusinessRegistry(self.menu.capabilities)
        self.policies=bm.PolicyRegistry(self.registry)

    def test_all_registered_meanings_preserved(self):
        self.assertEqual(Counter(x.key.family for x in self.registry.by_id.values()),
             {"utility":136,"lights":144,"appliance":78,"home":85})
        self.assertEqual(len(self.registry.by_key),443)
        self.assertEqual(sum(bool(x.key.parameter) for x in self.registry.by_id.values()),34)
        self.assertEqual(sum(x.requires_native_target for x in self.registry.by_id.values()),45)
        for cid,cap in self.menu.capabilities.items():
            p=lex.describe(cap)
            item=self.registry.by_id[cid]
            self.assertEqual(item.key,bm.QueryKey(p.family,p.target,p.metric,p.period,p.parameter,p.account))
            self.assertEqual(item.intent,cap["intent"])
            self.assertIs(self.registry.require(item.key),item)
            self.assertTrue(item.dimension)
        print("BUSINESS_PROFILE_COUNT="+str(len(self.registry.by_id)))

    def test_meaning_is_not_unit_only(self):
        ids=self.registry.by_id
        d=lambda cid:ids[cid].dimension
        self.assertNotEqual(d("utility.gas.basic.balance"),d("utility.gas.tier.tier1_remaining"))
        self.assertNotEqual(d("utility.gas.tier.tier1_remaining"),d("utility.gas.basic.meter"))
        self.assertNotEqual(d("utility.gas.tier.tier1_remaining"),d("utility.gas.tier.tier1_limit"))
        self.assertNotEqual(d("appliance.ac.master.target"),d("appliance.ac.master.temp"))
        self.assertNotEqual(d("appliance.ac.master.temp"),d("home.env.master.temp_master"))
        self.assertNotEqual(d("appliance.washer.temp"),d("appliance.purifier.temp"))
        self.assertNotEqual(d("home.presence.balcony.lux_balcony"),d("lights.fixtures.airer.brightness"))
        self.assertNotEqual(d("lights.all.count_on"),d("home.family.family_count_all"))
        self.assertNotEqual(ids["utility.gas.pay.year_pay"].key,ids["utility.gas.history.h_year_cost.h_year_cost_year"].key)

    def test_all_scene_references_are_registered_and_bounded(self):
        for rule in self.policies.by_key.values():
            with self.subTest(key=rule.key):
                keys=rule.scene.primary+rule.scene.supplements
                self.assertLessEqual(len(keys),bm.MAX_SCENE_QUERIES)
                self.assertEqual(len(set(keys)),len(keys))
                for key in keys:
                    self.assertIn(self.registry.require(key).capability_id,self.menu.capabilities)
                    self.assertFalse(key.parameter)
                    self.assertEqual(key.period,rule.key.period)
                    if rule.key.account:
                        self.assertEqual(key.account,rule.key.account)
        self.assertGreaterEqual(len(self.policies.by_key),45)
        print("BUSINESS_POLICY_COUNT="+str(len(self.policies.by_key)))

    def ids(self,f,t,g,a="",period=""):
        r=self.policies.get(bm.PolicyKey(f,t,g,a,period))
        self.assertIsNotNone(r)
        return tuple(self.registry.require(k).capability_id for k in r.scene.primary+r.scene.supplements)

    def test_explicit_default_policy_examples(self):
        self.assertEqual(self.ids("utility","g","remaining_unspecified","j"),("utility.gas.basic.balance",))
        self.assertEqual(self.ids("utility","e","remaining_unspecified","l"),("utility.electric.l.basic.balance",))
        self.assertEqual(self.ids("utility","w","payment_needed","j"),("utility.water.debt","utility.water.balance"))
        self.assertEqual(self.ids("utility","g","remaining_physical","j"),("utility.gas.tier.tier1_remaining","utility.gas.tier.tier2_remaining"))
        self.assertEqual(self.ids("appliance","m","temperature_unspecified"),("appliance.ac.master.target","appliance.ac.master.temp"))
        self.assertEqual(self.ids("appliance","ac","temperature_unspecified"),("appliance.ac.all.target","appliance.ac.all.temp"))
        self.assertEqual(self.ids("home","主卧","environment"),("home.env.master.room_env_master",))
        self.assertEqual(self.ids("home","卫生间","environment"),("home.env.bathroom.temp_bathroom",))
        self.assertEqual(self.ids("home","阳台","brightness_unspecified"),("home.presence.balcony.lux_balcony","lights.rooms.yang_tai.list_on"))
        self.assertEqual(self.ids("lights","ke_ting","any_lights_on"),("lights.rooms.ke_ting.list_on",))
        self.assertEqual(self.ids("home","all","entry_safety"),("home.access.door.door_all","home.access.door.lock_all","home.access.door.deadbolt_all"))

    def test_missing_policy_is_not_a_default_account_or_time(self):
        for key in (bm.PolicyKey("utility","e","remaining_unspecified"),
                    bm.PolicyKey("utility","w","remaining_unspecified","l"),
                    bm.PolicyKey("utility","g","remaining_unspecified","j","previous"),
                    bm.PolicyKey("appliance","unknown","overview"),
                    bm.PolicyKey("lights","lights.fixtures.master_ceiling","overview")):
            self.assertIsNone(self.policies.get(key))
        with self.assertRaises(KeyError):
            self.registry.require(bm.QueryKey("utility","e","balance",account=""))
        self.assertNotEqual(self.ids("utility","all","account_health","j"),
                            self.ids("utility","all","account_health","j","all"))

    def test_scene_guard_and_caveats_are_explicit(self):
        r=self.policies.get(bm.PolicyKey("utility","g","remaining_physical","j"))
        self.assertIn("实际剩余燃气量",r.scene.caveat)
        r=self.policies.get(bm.PolicyKey("appliance","m","temperature_when_off"))
        self.assertIn("并非空调检测温度",r.scene.caveat)
        self.assertIn("cycle_not_running",self.policies.get(bm.PolicyKey("appliance","w","progress")).scene.stop_on)
        self.assertIn("device_off",self.policies.get(bm.PolicyKey("appliance","m","overview")).scene.stop_on)

    def test_invalid_and_duplicate_model_definitions_fail_closed(self):
        caps=dict(self.menu.capabilities)
        cap=dict(caps["utility.gas.basic.balance"])
        cap["id"]="duplicate"
        caps["duplicate"]=cap
        with self.assertRaises(ValueError):
            bm.BusinessRegistry(caps)
        rule=self.policies.get(bm.PolicyKey("utility","e","remaining_unspecified","j"))
        wrong=replace(rule.scene,primary=(bm.QueryKey("utility","e","balance",account="l"),))
        with self.assertRaises(ValueError):
            bm.PolicyRegistry(self.registry,[replace(rule,scene=wrong)])
        duplicate=replace(rule.scene,supplements=rule.scene.primary)
        with self.assertRaises(ValueError):
            bm.PolicyRegistry(self.registry,[replace(rule,scene=duplicate)])
        missing=replace(rule.scene,primary=(bm.QueryKey("utility","e","unknown",account="j"),))
        with self.assertRaises(KeyError):
            bm.PolicyRegistry(self.registry,[replace(rule,scene=missing)])
        with self.assertRaises(TypeError):
            self.registry.by_id["fake"]=None
