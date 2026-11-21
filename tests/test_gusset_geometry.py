import pathlib
import sys
import unittest
from dataclasses import replace
from math import cos, radians, sin


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "addin" / "JHR_StructuralMembers_V1"))

from lib import joint_geometry as geo
from lib.gusset_geometry import GussetArm, brace_clearance, brace_end_shift, central_gusset, support_weld, supported_gusset


class SupportedGussetTests(unittest.TestCase):
    def setUp(self):
        self.settings = dict(thickness_cm=.8, hole_diameter_cm=1.4, rows=2,
                             end_distance_cm=3., pitch_cm=4., edge_distance_cm=1.8, washer_radius_cm=1.2)
        self.edge = ((0., 0., .3), (90., 0., .3))

    def test_single_brace_has_one_square_return_and_one_diagonal_edge(self):
        for sign in (-1., 1.):
            with self.subTest(sign=sign):
                arm = GussetArm((40., 5., 0.), (40.+sign*20., 35., 0.), (0., 0., 1.), 5., .6)
                plate = supported_gusset([arm], self.edge, **self.settings).plate
                self.assertEqual(len(plate.outline), 4)
                supports = [p for p in plate.outline if p[1] == 0.]
                tips = [p for p in plate.outline if p[1] > 0.]
                self.assertEqual(len(supports), 2)
                self.assertEqual(len(tips), 2)
                square = next(p for p in supports if any(q[0] == p[0] for q in tips))
                foot = next(p for p in supports if p != square)
                tip = next(p for p in tips if p[0] != square[0])
                axis = geo.normalize(geo.subtract(plate.holes[1][:2], plate.holes[0][:2]))
                self.assertAlmostEqual(geo.dot(axis, geo.normalize(geo.subtract(tip, foot))), 1.)
                self.assertAlmostEqual(geo.dot(axis, geo.subtract(tips[1], tips[0])), 0.)
                self.assertLess(abs(tips[1][0]-tips[0][0]), abs(supports[1][0]-supports[0][0]))
                self.assertAlmostEqual(geo.length(geo.subtract(plate.holes[1][:2], plate.holes[0][:2])), 4.)

    def test_shared_weld_and_unchanged_hole_pattern_for_two_and_three_diagonals(self):
        arms = [GussetArm((x, 4., 0.), (x+2., 35., 0.), (0., 0., 1.), 5., .6)
                for x in (24., 44., 64.)]
        for count in (2, 3):
            with self.subTest(count=count):
                expected = supported_gusset(arms[:count], self.edge, **self.settings)
                enlarged = supported_gusset(arms[:count], self.edge, weld_length_cm=52., **self.settings)
                self.assertEqual(expected.plate.holes, enlarged.plate.holes)
                heel = sorted(x for x, y in enlarged.plate.outline if y == 0.)
                self.assertAlmostEqual(heel[1]-heel[0], 52.)
                self.assertEqual(len(enlarged.plate.holes), 2*count)

    def test_single_brace_covers_the_full_asymmetric_flange(self):
        for sign in (-1., 1.):
            with self.subTest(sign=sign):
                arm = GussetArm((40., 6., 0.), (40.+sign*25., 35., 0.), (0., 0., 1.),
                                3.8, .6, bearing_offsets_cm=(-3.8, 2.2))
                plan = supported_gusset([arm], self.edge, **self.settings)
                plate = plan.plate
                self.assertEqual(len(plate.outline), 4)
                along = geo.normalize(geo.subtract(arm.far, arm.near))
                across = geo.cross(arm.normal, along)
                for s in (0., 8.8):
                    for offset in arm.bearing_offsets_cm:
                        point = geo.add(geo.add(arm.near, geo.scale(along, s)), geo.scale(across, offset))
                        delta = geo.subtract(point, plate.origin)
                        x, y = geo.dot(delta, plate.u), geo.dot(delta, plate.v)
                        self.assertGreater(y, 0.)
                        for a, b in zip(plate.outline, plate.outline[1:] + plate.outline[:1:]):
                            edge = geo.subtract(b, a)
                            distance = (edge[0]*(y-a[1])-edge[1]*(x-a[0]))/geo.length(edge)
                            if a[1] or b[1]:
                                self.assertGreaterEqual(distance, -1e-8)
                with self.assertRaisesRegex(ValueError, "trop court"):
                    supported_gusset([arm], self.edge, weld_length_cm=3., **self.settings)

    def test_redrawn_60_mm_brace_matches_reference_outline(self):
        # Local coordinates: along the column first, outward from its face second.
        arm = GussetArm((70., 10., 0.), (200., 178., 0.), (0., 0., 1.), 4.6, .6,
                        bearing_offsets_cm=(-3., 3.))
        plate = supported_gusset([arm], ((0., 0., .3), (300., 0., .3)), **self.settings).plate
        measured_cm = ((58.34217, 0.), (77.75806, 0.), (77.75806, 15.12371),
                       (72.93375, 18.85681))
        for actual, expected in zip(plate.outline, measured_cm, strict=True):
            self.assertLess(geo.length(geo.subtract(actual, expected)), .0001)


class SupportWeldTests(unittest.TestCase):
    @staticmethod
    def frame(arm, **settings):
        return support_weld(arm, arm.normal, (0., 0., 0.), ((1., 0., 0.), (0., 1., 0.)),
                            ((-6., 6.), (-12., 12.)), ((-.31, .31), (-9.5, 9.5)),
                            thickness_cm=.8, **settings)

    def test_auto_selects_the_flange_and_can_check_alignment_with_the_web_centre(self):
        arm = GussetArm((-.7, 14., 35.), (-.7, 42., 68.), (1., 0., 0.), 4.7, .6)
        auto, inside = self.frame(arm)
        centred, _ = self.frame(arm, face=1, position=1)
        for point in (auto, centred):
            self.assertAlmostEqual(point[0], -.4)
            self.assertEqual(point[1:], (12., 0.))
        self.assertEqual(inside, (0., -.02, 0.))
        with self.assertRaisesRegex(ValueError, "perpendiculaire"):
            self.frame(arm, face=2)
        with self.assertRaisesRegex(ValueError, "Aligner la face"):
            self.frame(arm, face=1, position=2, offset_cm=.7)

    def test_web_weld_uses_the_real_web_face_for_perpendicular_bracing(self):
        for direction in (-1, 1):
            with self.subTest(direction=direction):
                arm = GussetArm((direction*3., 1.3, 35.), (direction*42., 1.3, 68.),
                                (0., 1., 0.), 4.7, .6)
                auto, inside = self.frame(arm)
                offset, _ = self.frame(arm, face=2, position=2, offset_cm=2.)
                self.assertEqual(auto, offset)
                self.assertAlmostEqual(offset[0], direction*.31)
                self.assertAlmostEqual(offset[1], 1.6)
                self.assertEqual(inside, (-direction*.02, 0., 0.))
                plate = supported_gusset(
                    [arm], (offset, geo.add(offset, (0., 0., 100.))), thickness_cm=.8,
                    hole_diameter_cm=1.4, rows=2, end_distance_cm=3., pitch_cm=4.,
                    edge_distance_cm=1.8, washer_radius_cm=1.2,
                ).plate
                self.assertEqual(len(plate.holes), 2)
                self.assertAlmostEqual(plate.origin[0], direction*.31)

    def test_web_weld_rejects_resting_on_a_flange_fillet(self):
        arm = GussetArm((3., 9., 35.), (38., 9., 61.), (0., 1., 0.), 4.7, .6)
        with self.assertRaisesRegex(ValueError, "entre les congés"):
            self.frame(arm, face=2)

    def test_axial_end_move_adjusts_the_shortest_distance_to_the_weld_face(self):
        axis = (.8, .0, .6)
        plane, outward = (1., 0., 0.), (1., 0., 0.)
        points = ((3., 0., 2.), (4., 0., 1.))
        current = brace_clearance(points, plane, outward)
        self.assertAlmostEqual(current, 2.)
        for wanted in (0., .5, 3.):
            with self.subTest(wanted=wanted):
                shift = brace_end_shift(current, wanted, axis, outward)
                moved = [geo.add(point, geo.scale(axis, shift)) for point in points]
                self.assertAlmostEqual(brace_clearance(moved, plane, outward), wanted)
        with self.assertRaisesRegex(ValueError, "presque parallèle"):
            brace_end_shift(current, 1., (0., 0., 1.), outward)


class GussetGeometryTests(unittest.TestCase):
    def setUp(self):
        self.arms = tuple(GussetArm((8*x, 8*y, 12), (36*x, 36*y, 12), (0, 0, 1), 8, 1)
                          for x, y in ((1, 0), (0, -1), (-1, 0), (0, 1)))
        self.settings = dict(thickness_cm=1.2, hole_diameter_cm=1.8, rows=2, end_distance_cm=3,
                             pitch_cm=5, edge_distance_cm=2.5, washer_radius_cm=1.5)

    def test_contact_plane_rows_and_counterclockwise_outline(self):
        plan = central_gusset(self.arms, **self.settings)
        self.assertEqual(plan.plate.normal, (0, 0, 1))
        self.assertEqual(plan.plate.origin, (0, 0, 12.5))
        self.assertEqual(plan.arm_order, (0, 3, 2, 1))
        self.assertEqual(plan.centres_by_arm[:2], (((11, 0, 12.5), (16, 0, 12.5)),
                                                    ((0, -11, 12.5), (0, -16, 12.5))))
        self.assertEqual(len(plan.plate.holes), 8)
        contour = plan.plate.outline
        self.assertTrue(all(x1*y2 - x2*y1 > 0 for (x1, y1), (x2, y2)
                            in zip(contour, contour[1:] + contour[:1])))

    def test_rotated_plane_and_alternate_side_with_three_rows(self):
        # Passage de XY à XZ, avec normales de profil de signes différents.
        arms = tuple(GussetArm((x, 12, y), (fx, 12, fy), (0, (-1)**index, 0), 8, 1)
                     for index, ((x, y, _), (fx, fy, _)) in
                     enumerate((arm.near, arm.far) for arm in self.arms))
        plan = central_gusset(arms, **dict(self.settings, rows=3, alternate=True))
        self.assertEqual(plan.plate.normal, (0, -1, 0))
        self.assertEqual(plan.centres_by_arm[0], ((11, 11.5, 0), (16, 11.5, 0), (21, 11.5, 0)))
        self.assertEqual(len(plan.plate.holes), 12)
        for local_hole, world_point in zip(plan.plate.holes, sum(plan.centres_by_arm, ())):
            self.assertEqual(plan.plate.point(*local_hole[:2]), world_point)

    def test_reject_non_parallel_or_shifted_face(self):
        for change, message in ((dict(normal=(0, 1, 0)), "parallèles"),
                                (dict(thickness_cm=1.5), "coplanaires"),
                                (dict(far=(0, 36, 11)), "coplanaires")):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, message):
                central_gusset(self.arms[:3] + (replace(self.arms[3], **change),), **self.settings)

    def test_reject_insufficient_member_length_or_width(self):
        for change, message in ((dict(far=(13, 0, 12)), "dépassent"),
                                (dict(clear_width_cm=4), "trop étroite")):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, message):
                central_gusset((replace(self.arms[0], **change),) + self.arms[1:], **self.settings)

    def test_reject_overlapping_washers_across_adjacent_arms(self):
        angles = (0, 12, 170, 270)
        arms = tuple(GussetArm((0, 0, 12), (36*cos(radians(angle)), 36*sin(radians(angle)), 12),
                               (0, 0, 1), 8, 1) for angle in angles)
        with self.assertRaisesRegex(ValueError, "appuis de deux diagonales"):
            central_gusset(arms, **self.settings)

    def test_reject_flange_interference_only_when_web_has_flanges(self):
        with self.assertRaisesRegex(ValueError, "aile ou un congé"):
            central_gusset((replace(self.arms[0], flanges_bound_plate=True),) + self.arms[1:], **self.settings)
        wide_webs = tuple(replace(arm, flanges_bound_plate=True, clear_width_cm=30) for arm in self.arms)
        self.assertEqual(len(central_gusset(wide_webs, **self.settings).plate.holes), 8)

    def test_reject_arms_pointing_back_to_centre(self):
        arms = tuple(replace(arm, near=arm.far, far=arm.near) for arm in self.arms)
        with self.assertRaisesRegex(ValueError, "vers l’extérieur"):
            central_gusset(arms, **self.settings)

    def test_reject_edge_distance_smaller_than_washer(self):
        with self.assertRaisesRegex(ValueError, "distance au chant"):
            central_gusset(self.arms, **dict(self.settings, edge_distance_cm=1.3))

    def test_supports_different_section_thickness_on_common_face(self):
        first = self.arms[0]
        thicker = replace(first, near=geo.add(first.near, (0, 0, -.5)),
                          far=geo.add(first.far, (0, 0, -.5)), thickness_cm=2)
        self.assertEqual(central_gusset((thicker,) + self.arms[1:], **self.settings).plate.origin,
                         (0, 0, 12.5))


if __name__ == "__main__":
    unittest.main()
