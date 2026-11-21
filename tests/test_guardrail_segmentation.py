"""Régression du tronçonnage au droit d'un poteau plat."""

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addin" / "JHR_StructuralMembers_V1"))
from lib import guardrail_layout as layout
from lib import joint_geometry as geo


class GuardrailSegmentationTests(unittest.TestCase):
    def layout(self, slope=0., **settings):
        points = ((0., 0., 0.), (3000., 0., 3000*slope))
        return layout.plan_guardrail([(*points, geo.normalize((-slope, 0., 1.)))], settings)

    def split(self, plan, mode="halves", gap=0., added=5.):
        return layout.plan_post_split(
            plan["posts"][1], plan["plates"][1], plan["rails"][0], mode, gap, added,
        )

    def test_split_uses_two_equal_flats_and_every_rail(self):
        plan = self.layout()
        split = self.split(plan)
        self.assertEqual(split["existing_thickness_mm"], 5.)
        self.assertEqual(split["added_thickness_mm"], 5.)
        self.assertEqual(split["interface"], plan["posts"][1]["start"])
        self.assertEqual([cut["name"] for cut in split["rail_cuts"]],
                         ["Main courante", "Plinthe", "Sous-lisse 1"])
        self.assertTrue(all(cut["before"] == cut["after"] for cut in split["rail_cuts"]))

    def test_slope_respects_the_flat_joint_except_on_the_handrail(self):
        plan = self.layout(.5)
        for mode, thickness, shift in (("adjacent", 10., 5.), ("halves", 5., 0.)):
            with self.subTest(mode=mode):
                split = self.split(plan, mode, 2.)
                self.assertEqual(split["existing_thickness_mm"], thickness)
                self.assertEqual(split["added_thickness_mm"], 5.)
                self.assertAlmostEqual(split["interface"][0]-plan["posts"][1]["start"][0], shift)
                for rail, cut in zip(plan["rails"][0], split["rail_cuts"]):
                    normal = rail["direction"] if rail["name"] == "Main courante" else split["post_normal"]
                    self.assertEqual(cut["normal"], normal)
                    self.assertAlmostEqual(cut["point"][0], split["interface"][0])
                    self.assertAlmostEqual(geo.dot(geo.subtract(cut["after"], cut["before"]), normal), 2.)
                    self.assertAlmostEqual(geo.length(geo.subtract(cut["after"], cut["before"])), 2.)

    def test_rejects_adjustments_exceeding_the_current_geometry(self):
        plan = self.layout()
        with self.assertRaisesRegex(ValueError, "jeu"):
            self.split(plan, gap=-1.)
        with self.assertRaisesRegex(ValueError, "bouts"):
            self.split(plan, gap=3000.)
        with self.assertRaisesRegex(ValueError, "épaisseur"):
            self.split(plan, "adjacent", added=11.)
        plan["plates"][1]["along_mm"] = 18.
        with self.assertRaisesRegex(ValueError, "platine"):
            self.split(plan, "adjacent")


if __name__ == "__main__":
    unittest.main()
