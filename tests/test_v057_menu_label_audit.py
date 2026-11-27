"""Independent audit from the actual rendered-layout nodes, not the phrase index."""
import json
import unittest
from collections import defaultdict
import test_v053_menu_regression as regression
from nexora_menu_test.semantic import normalize

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
