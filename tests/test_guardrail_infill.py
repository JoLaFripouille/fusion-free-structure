"""Contrôles du vide libre du barreaudage avec la géométrie de parcours."""

import pathlib
import sys
import unittest


ADDIN = pathlib.Path(__file__).resolve().parents[1] / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ADDIN))
from lib import guardrail_layout as layout, joint_geometry as geo


LEVEL = (((0., 0., 0.), (3000., 0., 0.), layout.UP),)
RAMP = (((0., 0., 0.), (3000., 0., 750.), geo.normalize((-.25, 0., 1.))),)
LANDING_RAMP = (
    ((0., 0., 0.), (1500., 0., 0.), layout.UP),
    ((1500., 0., 0.), (3000., 0., 750.), geo.normalize((-.5, 0., 1.))),
)


class GuardrailInfillTests(unittest.TestCase):
    def plan(self, segments=LEVEL, **settings):
        return layout.plan_guardrail(segments, {"model": "barreaude", **settings})

    def test_clear_gaps_use_the_faces_of_posts_and_bars_and_cover_ends(self):
        plan = self.plan(start_margin_mm=240., end_margin_mm=240., max_clear_mm=93.)
        intervals = [
            (item["start"][0] - item["section"]["depth_mm"] / 2.,
             item["start"][0] + item["section"]["depth_mm"] / 2.)
            for item in (*plan["posts"], *plan["bars"])
        ]
        ordered = [(0., 0.), *sorted(intervals), (3000., 3000.)]
        gaps = [right[0] - left[1] for left, right in zip(ordered, ordered[1:])]
        self.assertAlmostEqual(max(gaps), plan["horizontal_clear_mm"])
        self.assertLessEqual(max(gaps), 93.)
        self.assertLessEqual(plan["bars"][0]["start"][0], 235.)
        self.assertGreaterEqual(plan["bars"][-1]["start"][0], 2765.)
        self.assertAlmostEqual(plan["bottom_clear_mm"], 75.)

    def test_vertical_bars_end_at_the_real_inclined_rail_faces(self):
        plan = self.plan(RAMP)
        self.assertAlmostEqual(plan["bottom_clear_mm"], 75.)
        for bar in plan["bars"]:
            self.assertAlmostEqual(bar["start"][0], bar["end"][0])
            self.assertAlmostEqual(bar["start"][1], bar["end"][1])
            low, high = bar["bottom_rail"], bar["top_rail"]
            self.assertAlmostEqual(geo.dot(geo.subtract(bar["start"], low["start"]), low["v"]),
                                   low["section"]["depth_mm"] / 2.)
            self.assertAlmostEqual(geo.dot(geo.subtract(bar["end"], high["start"]), high["v"]),
                                   -high["section"]["depth_mm"] / 2.)
            self.assertEqual(bar["bottom_normal"], geo.scale(low["v"], -1.))
            self.assertEqual(bar["top_normal"], high["v"])

    def test_flat_or_round_bars_use_the_right_dimensions_in_the_guardrail_plane(self):
        flat = self.plan(bar_shape="flat", bar_width_mm=18., bar_depth_mm=6.)["bars"][0]
        self.assertEqual(flat["section"], {"type": "flat", "width_mm": 6., "depth_mm": 18., "wall_mm": 0.})
        round_bar = self.plan(bar_shape="round", bar_width_mm=14., bar_depth_mm=6.)["bars"][0]
        self.assertEqual(round_bar["section"],
                         {"type": "round_solid", "width_mm": 14., "depth_mm": 14., "wall_mm": 0.})

    def test_round_handrail_has_a_planar_tangent_stop(self):
        for segments in (LEVEL, RAMP):
            with self.subTest(segments=segments):
                plan = self.plan(segments, bar_shape="round", handrail_type="round_tube",
                                 handrail_width_mm=42.4, handrail_depth_mm=42.4)
                for bar in plan["bars"]:
                    handrail = bar["top_rail"]
                    normal = bar["top_normal"]
                    self.assertAlmostEqual(geo.dot(normal, handrail["direction"]), 0.)
                    self.assertAlmostEqual(geo.dot(geo.subtract(handrail["start"], bar["end"]), normal), 21.2)

    def test_pitch_change_at_post_passes_and_mid_bay_is_rejected(self):
        plan = self.plan(LANDING_RAMP, post_count=3, post_spacing_max_mm=1500.)
        self.assertEqual(plan["posts"][1]["start"][0], 1500.)
        self.assertAlmostEqual(plan["bottom_clear_mm"], 75.)
        self.assertLessEqual(plan["max_clear_mm"], 100.)
        with self.assertRaisesRegex(ValueError, "poteau au raccord"):
            self.plan(LANDING_RAMP, post_count=4)

    def test_bar_can_span_a_straight_joint_with_flat_rails(self):
        params = {"post_count": 2, "post_spacing_max_mm": 3000.}
        station = self.plan(**params)["bars"][5]["start"][0]
        segments = (((0., 0., 0.), (station, 0., 0.), layout.UP),
                    ((station, 0., 0.), (3000., 0., 0.), layout.UP))
        plan = self.plan(segments, **params)
        self.assertAlmostEqual(plan["bars"][5]["start"][0], station)
        self.assertLessEqual(plan["max_clear_mm"], 100.)

    def test_oversize_opening_is_rejected_above_the_configuration_or_below_the_rail(self):
        with self.assertRaisesRegex(ValueError, "100 mm"):
            self.plan(max_clear_mm=100.1)
        with self.assertRaisesRegex(ValueError, "sous la lisse basse"):
            self.plan(lower_rail_clearance_mm=102.)

    def test_y_up_and_side_mounting_preserve_the_opening(self):
        def rotate(point):
            x, y, z = point
            return x, z, -y

        support = ((LEVEL[0][0], LEVEL[0][1], (0., -1., 0.)),)
        normal = self.plan(support, mounting="side")
        rotated = self.plan([tuple(map(rotate, segment)) for segment in support],
                            mounting="side", vertical_axis="Y")
        self.assertAlmostEqual(normal["max_clear_mm"], rotated["max_clear_mm"])
        for old, new in zip(normal["bars"], rotated["bars"], strict=True):
            self.assertEqual(rotate(old["start"]), new["start"])
            self.assertEqual(rotate(old["end"]), new["end"])


if __name__ == "__main__":
    unittest.main()
