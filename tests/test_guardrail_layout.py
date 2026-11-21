"""Régression de l'implantation des pièces sur appuis acier."""

import math
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addin" / "JHR_StructuralMembers_V1"))
from lib import guardrail_layout as layout
from lib import joint_geometry as geo


LEVEL = [((0., 0., 0.), (3000., 0., 0.), layout.UP)]


class GuardrailLayoutTests(unittest.TestCase):
    def test_level_top_rail_height_and_hole_orientation(self):
        plan = layout.plan_guardrail(LEVEL)
        self.assertEqual(len(plan["posts"]), 4)
        self.assertEqual(len(plan["plates"]), 4)
        self.assertEqual(len(plan["plates"][0]["holes"]), 4)
        self.assertAlmostEqual(plan["pitch_mm"], 2800/3)
        plate = plan["plates"][0]
        self.assertEqual(geo.cross(plate["u"], plate["v"]), plate["normal"])
        self.assertEqual(plate["center"], (100., 0., 0.))
        rail = plan["rails"][0][0]
        self.assertAlmostEqual(rail["start"][2] + rail["section"]["depth_mm"]/2, 1100.)

    def test_post_at_landing_belongs_to_the_ramp_and_rails_are_mitered(self):
        normal = geo.normalize((-1., 0., 2.))
        plan = layout.plan_guardrail([
            ((0., 0., 0.), (1500., 0., 0.), layout.UP),
            ((1500., 0., 0.), (3000., 0., 750.), normal),
        ], {"post_count": 3, "post_spacing_max_mm": 1500.})
        self.assertEqual([p["segment"] for p in plan["posts"]], [0, 1, 1])
        self.assertEqual(plan["plates"][1]["center"], (1500., 0., 0.))
        self.assertAlmostEqual(plan["posts"][1]["start"][0], 1500.)
        self.assertAlmostEqual(plan["posts"][1]["start"][2], 10.*math.sqrt(1.25))
        for a, b in zip(*plan["rails"]):
            self.assertEqual(a["end"], b["start"])
            self.assertEqual(a["end_plane"], b["start_plane"])
            self.assertAlmostEqual(geo.dot(a["direction"], a["end_plane"]),
                                   geo.dot(b["direction"], b["start_plane"]))

    def test_lateral_plates_face_the_web_on_both_sides(self):
        for sign in (-1., 1.):
            normal = (0., sign, 0.)
            plan = layout.plan_guardrail([(LEVEL[0][0], LEVEL[0][1], normal)], {"mounting": "side"})
            plate, post = plan["plates"][0], plan["posts"][0]
            self.assertEqual(geo.cross(plate["u"], plate["v"]), normal)
            self.assertAlmostEqual(plate["center"][2], -60.)
            self.assertAlmostEqual(post["start"][1], sign*35.)
            self.assertAlmostEqual(plan["rails"][0][0]["start"][1], sign*35.)

    def test_y_up_preserves_placement_on_top_and_side(self):
        def rotate(point):
            x, y, z = point
            return x, z, -y

        ramp = [((0., 0., 0.), (3000., 0., 750.), geo.normalize((-.25, 0., 1.)))]
        side = [(LEVEL[0][0], LEVEL[0][1], (0., -1., 0.))]
        for mounting, segments in (("top", ramp), ("side", side)):
            with self.subTest(mounting=mounting):
                cfg = {"mounting": mounting, "support": "concrete"}
                existing = layout.plan_guardrail(segments, cfg)
                rotated = layout.plan_guardrail([tuple(map(rotate, segment)) for segment in segments],
                                                dict(cfg, vertical_axis="Y"))
                self.assertEqual(existing["pitch_mm"], rotated["pitch_mm"])
                for group, fields in (("posts", ("start", "end", "direction", "foot_normal")),
                                      ("plates", ("center", "normal", "u", "v")),
                                      ("anchors", ("start", "end"))):
                    for old, new in zip(existing[group], rotated[group]):
                        for field in fields:
                            self.assertEqual(rotate(old[field]), new[field])
                for old, new in zip(existing["rails"][0], rotated["rails"][0]):
                    self.assertEqual(rotate(old["start"]), new["start"])
                    self.assertEqual(rotate(old["end"]), new["end"])

    def test_standard_plinth_sits_against_the_post_and_can_be_disabled(self):
        for side, sign in (("left", 1.), ("right", -1.)):
            plan = layout.plan_guardrail(LEVEL, {"kickplate_side": side})
            plinth = next(rail for rail in plan["rails"][0] if rail["name"] == "Plinthe")
            self.assertEqual(plinth["section"]["width_mm"], 6.)
            self.assertEqual(plinth["section"]["depth_mm"], 150.)
            self.assertEqual(plinth["start"], (0., sign*28., 85.))
            underside = plinth["start"][2] - plinth["section"]["depth_mm"]/2
            self.assertEqual(underside, 10.)
        without = layout.plan_guardrail(LEVEL, {"kickplate": False})
        self.assertEqual([rail["name"] for rail in without["rails"][0]], ["Main courante", "Sous-lisse 1"])

    def test_flat_post_has_measured_point_with_tangent_flat(self):
        for slope in (0., .5):
            normal = geo.normalize((-slope, 0., 1.))
            plan = layout.plan_guardrail([((0, 0, 0), (3000, 0, slope*3000), normal)])
            post = plan["posts"][0]
            (center, cap_normal), *sides = post["tip_planes"]
            self.assertEqual(cap_normal, normal)
            distance = geo.dot(geo.subtract(post["end"], center), cap_normal)
            self.assertAlmostEqual(distance, 21.2)
            self.assertAlmostEqual(geo.length(geo.subtract(sides[0][0], sides[1][0])), 10.)
            for sign, (point, bevel) in zip((-1, 1), sides):
                shoulder = geo.add(center, (0., sign*25., -60.))
                self.assertAlmostEqual(geo.dot(geo.subtract(shoulder, point), bevel), 0.)

    def test_tube_post_retains_its_existing_end_treatment(self):
        plan = layout.plan_guardrail(LEVEL, {
            "post_type": "rectangular_tube", "post_width_mm": 40., "post_depth_mm": 40.,
        })
        self.assertEqual(plan["posts"][0]["tip_planes"], ())
        with self.assertRaisesRegex(ValueError, "méplat"):
            layout.plan_guardrail(LEVEL, {"post_tip_flat_mm": 50.})

    def test_rejects_perforation_at_the_edge_and_excess_pitch(self):
        cases = [
            ({"hole_pitch_along_mm": 99.}, "trous"),
            ({"post_count": 2}, "entraxe"),
            ({"post_depth_mm": 90., "hole_pitch_across_mm": 20.}, "poteau"),
        ]
        for cfg, pattern in cases:
            with self.subTest(cfg=cfg), self.assertRaisesRegex(ValueError, pattern):
                layout.plan_guardrail(LEVEL, cfg)

    def test_rejects_offset_or_wrong_support(self):
        with self.assertRaisesRegex(ValueError, "joindre"):
            layout.plan_guardrail(LEVEL + [((3001., 0., 0.), (4000., 0., 0.), layout.UP)])
        with self.assertRaisesRegex(ValueError, "dessus"):
            layout.plan_guardrail([(LEVEL[0][0], LEVEL[0][1], (0., 1., 0.))])

    def test_concrete_anchors_use_explicit_geometry(self):
        plan = layout.plan_guardrail(LEVEL, {
            "support": "concrete", "anchor_diameter_mm": 10.,
            "anchor_embedment_mm": 90., "anchor_projection_mm": 24.,
        })
        self.assertEqual(len(plan["anchors"]), 16)
        anchor = plan["anchors"][0]
        self.assertEqual(anchor["diameter_mm"], 10.)
        self.assertEqual(geo.subtract(anchor["center"], anchor["start"]), (0., 0., 90.))
        self.assertEqual(geo.subtract(anchor["end"], anchor["center"]), (0., 0., 34.))

    def test_steel_drilling_and_concrete_anchors_are_distinct(self):
        default = layout.plan_guardrail(LEVEL, {"drill_support": True})
        self.assertEqual(default["anchors"], [])
        with self.assertRaisesRegex(ValueError, "acier"):
            layout.plan_guardrail(LEVEL, {"support": "concrete", "drill_support": True})
        with self.assertRaisesRegex(ValueError, "diamètre"):
            layout.plan_guardrail(LEVEL, {"support": "concrete", "anchor_diameter_mm": 16.})


if __name__ == "__main__":
    unittest.main()
