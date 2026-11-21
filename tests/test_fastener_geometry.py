from __future__ import annotations

import math
import pathlib
import sys
import unittest


ADDIN = pathlib.Path(__file__).resolve().parents[1] / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ADDIN))
from lib import fastener_geometry as geo, joint_geometry as vec


class PrototypeRecognitionTests(unittest.TestCase):
    def sections(self, head="H"):
        rings = [(.8, 0., 5.), (1.5, 0., .3), (1.5, 2.5, 2.8)]
        sides = [(-1., 0., 1.2, i * math.pi / 3) for i in range(6)]
        sides += [(2.8, 4.1, 1.2, i * math.pi / 3) for i in range(6)]
        if head == "CHC":
            rings.append((1.2, -1.6, 0.))
            sides = [(-1.3, -.3, .7, i * math.pi / 3) for i in range(6)]
            sides += [(2.8, 4.1, 1.2, i * math.pi / 3) for i in range(6)]
        return rings, sides, [(2.8, 4.1)]

    def test_recognizes_existing_complete_h_assembly_dimensions(self):
        layout, origin = geo.recognize_sections(16, 50, 5., *self.sections())
        self.assertEqual(layout.head, "H")
        self.assertAlmostEqual(origin, .3)
        self.assertAlmostEqual(layout.grip_cm, 2.2)
        self.assertAlmostEqual(layout.head_washer_cm, .3)
        self.assertAlmostEqual(layout.nut_washer_cm, .3)
        self.assertAlmostEqual(layout.nut_height_cm, 1.3)

    def test_chc_requires_a_round_head_and_an_actual_hex_socket(self):
        layout, _ = geo.recognize_sections(16, 50, 5., *self.sections("CHC"))
        self.assertEqual(layout.head, "CHC")
        rings, sides, wide = self.sections("CHC")
        with self.assertRaisesRegex(ValueError, "Tête H ou CHC non reconnue"):
            geo.recognize_sections(16, 50, 5., rings, sides[6:], wide)

    def test_a_screw_alone_cannot_be_presented_as_a_complete_set(self):
        rings, sides, wide = self.sections()
        with self.assertRaisesRegex(ValueError, "rondelle côté écrou"):
            geo.recognize_sections(16, 50, 5., rings[:2], sides, wide)
        with self.assertRaisesRegex(ValueError, "écrou hexagonal complet"):
            geo.recognize_sections(16, 50, 5., rings, sides[:6], wide)

    def test_wrong_nominal_source_length_is_refused_before_copying(self):
        with self.assertRaisesRegex(ValueError, "Rondelle sous tête"):
            geo.recognize_sections(16, 40, 5., *self.sections())

    def test_split_cylinder_faces_do_not_invent_extra_washers(self):
        rings, sides, wide = self.sections()
        split = [(-1., 0., 1.2, -1e-8)] + sides
        layout, _ = geo.recognize_sections(16, 50, 5., rings + rings, split, wide)
        self.assertAlmostEqual(layout.grip_cm, 2.2)

    def test_six_arbitrary_flat_faces_are_not_mistaken_for_a_hex_head(self):
        rings, sides, wide = self.sections()
        with self.assertRaisesRegex(ValueError, "Tête H ou CHC non reconnue"):
            geo.recognize_sections(16, 50, 5., rings, [(-1., 0., 1.2, 0.)] * 6 + sides[6:], wide)


class FastenerPlacementTests(unittest.TestCase):
    def setUp(self):
        self.layout = geo.PrototypeLayout(16., 50., "H", .3, .3, 1.3, 2.2)
        self.head = geo.SupportPlane((10., 20., 30.), (0., 0., -1.))
        self.nut = geo.SupportPlane((10., 20., 32.2), (0., 0., 1.))

    def plan(self, holes=None, **overrides):
        values = dict(holes=[geo.Hole((10., 20., 31.), (0., 0., 1.), 1.8)] if holes is None else holes,
                      head_plane=self.head, nut_plane=self.nut, layout=self.layout,
                      diameter_mm=16., length_mm=50., head="H")
        values.update(overrides)
        return geo.plan_placements(**values)

    def test_each_hole_is_projected_to_the_head_support(self):
        poses, ignored = self.plan()
        self.assertEqual(ignored, 0)
        self.assertEqual(poses[0].origin, (10., 20., 30.))
        self.assertAlmostEqual(poses[0].grip_cm, 2.2)

    def test_top_and_bottom_edges_of_one_hole_create_one_set(self):
        poses, ignored = self.plan([
            geo.Hole((10., 20., 30.), (0., 0., 1.), 1.8),
            geo.Hole((10., 20., 32.2), (0., 0., -1.), 1.8),
            geo.Hole((15., 20., 32.2), (0., 0., -1.), 1.8)])
        self.assertEqual(len(poses), 2)
        self.assertEqual(ignored, 1)

    def test_existing_marked_or_template_instances_are_not_duplicated(self):
        poses, _ = self.plan()
        again, ignored = self.plan(occupied=poses)
        self.assertEqual(again, ())
        self.assertEqual(ignored, 1)

    def test_reversed_installation_changes_appui_and_axis(self):
        poses, _ = self.plan(reverse=True)
        self.assertEqual(poses[0].origin, (10., 20., 32.2))
        self.assertEqual(poses[0].z_axis, (0., 0., -1.))

    def test_reversing_the_head_cannot_add_a_second_bolt_in_an_occupied_hole(self):
        occupied, _ = self.plan()
        poses, ignored = self.plan(reverse=True, occupied=occupied)
        self.assertEqual(poses, ())
        self.assertEqual(ignored, 1)

    def test_separate_connections_on_the_same_axis_remain_available(self):
        occupied, _ = self.plan()
        poses, ignored = self.plan(
            head_plane=geo.SupportPlane((10., 20., 40.), (0., 0., -1.)),
            nut_plane=geo.SupportPlane((10., 20., 42.2), (0., 0., 1.)), occupied=occupied)
        self.assertEqual(len(poses), 1)
        self.assertEqual(ignored, 0)

    def test_arbitrary_direction_produces_a_right_handed_frame(self):
        axis = vec.normalize((1., 2., 3.))
        origin = (12., -3., 8.)
        poses, _ = self.plan(
            [geo.Hole(vec.add(origin, vec.scale(axis, .8)), vec.scale(axis, -1), 1.8)],
            head_plane=geo.SupportPlane(origin, axis),
            nut_plane=geo.SupportPlane(vec.add(origin, vec.scale(axis, 2.2)), axis))
        for actual, expected in zip(poses[0].origin, origin):
            self.assertAlmostEqual(actual, expected)
        for actual, expected in zip(vec.cross(poses[0].x_axis, poses[0].y_axis), poses[0].z_axis):
            self.assertAlmostEqual(actual, expected)

    def test_exported_tilted_axes_intersect_each_support_independently_of_face_points(self):
        slope = .0001414
        for direction in (1., -1.):
            holes = [geo.Hole((x, 4., .7), (direction * tilt, 0., direction), 1.8)
                     for x, tilt in ((0., slope), (25., -slope))]
            expected = 1.65 / abs(vec.normalize(holes[0].axis)[2])
            for reverse in (False, True):
                baseline = None
                for hx, nx in ((0., 0.), (-120., 135.), (3500., -7000.)):
                    head = geo.SupportPlane((hx, 12., 0.), (0., 0., 1.))
                    nut = geo.SupportPlane((nx, -30., 1.65), (0., 0., -1.))
                    poses, ignored = self.plan(holes, head_plane=head, nut_plane=nut, reverse=reverse)
                    self.assertEqual(ignored, 0)
                    self.assertEqual(len(poses), 2)
                    for pose in poses:
                        self.assertAlmostEqual(pose.grip_cm, expected, places=12)
                        self.assertAlmostEqual(pose.origin[2], 1.65 if reverse else 0., places=12)
                        end = vec.add(pose.origin, vec.scale(pose.z_axis, pose.grip_cm))
                        self.assertAlmostEqual(end[2], 0. if reverse else 1.65, places=12)
                    if baseline is None:
                        baseline = poses
                    self.assertEqual(poses, baseline)
                    repeated, repeats = self.plan(holes, head_plane=head, nut_plane=nut,
                                                  reverse=reverse, occupied=poses)
                    self.assertEqual(repeated, ())
                    self.assertEqual(repeats, 2)
                    opposite, repeats = self.plan(holes, head_plane=head, nut_plane=nut,
                                                  reverse=not reverse, occupied=poses)
                    self.assertEqual(opposite, ())
                    self.assertEqual(repeats, 2)

    def test_wrong_faces_and_small_holes_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "parallèles"):
            self.plan(nut_plane=geo.SupportPlane((10, 20, 32), (1, 0, 0)))
        with self.assertRaisesRegex(ValueError, "perpendiculaire"):
            self.plan([geo.Hole((10, 20, 30), (1, 0, 0), 1.8)])
        with self.assertRaisesRegex(ValueError, "trop petit"):
            self.plan([geo.Hole((10, 20, 30), (0, 0, 1), 1.6)])

    def test_changes_of_length_diameter_and_head_do_not_change_the_prototype(self):
        for length in (50, 60, 55, 50):
            self.assertEqual(len(self.plan(length_mm=length)[0]), 1)
        with self.assertRaisesRegex(ValueError, "trop courte"):
            self.plan(length_mm=40)
        with self.assertRaisesRegex(ValueError, "modèle sélectionné est M16"):
            self.plan(diameter_mm=12)
        with self.assertRaisesRegex(ValueError, "tête H"):
            self.plan(head="CHC")
        chc = geo.PrototypeLayout(16., 50., "CHC", .3, .3, 1.3, 2.2)
        self.assertEqual(len(self.plan(layout=chc, head="CHC")[0]), 1)
        self.assertEqual(self.layout.head, "H")
        self.assertEqual(self.layout.length_mm, 50)

    def test_shorter_grip_does_not_place_the_cut_in_the_nut_or_head(self):
        plan = geo.adaptation_plan(self.layout, 50., .3)
        self.assertGreater(plan["cut_cm"], 0)
        self.assertLess(plan["cut_cm"], .3)
        self.assertAlmostEqual(plan["new_tip_cm"], 4.7)

    def test_the_selected_nominal_length_keeps_the_head_washer_offset(self):
        for length in (50., 60., 55., 50.):
            plan = geo.adaptation_plan(self.layout, length, 2.2)
            self.assertAlmostEqual(plan["new_tip_cm"] + self.layout.head_washer_cm, length / 10)

    def test_empty_nonfinite_and_coincident_inputs_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "au moins un perçage"):
            self.plan([])
        with self.assertRaisesRegex(ValueError, "positif et fini"):
            self.plan(length_mm=math.nan)
        with self.assertRaisesRegex(ValueError, "confondus"):
            self.plan(nut_plane=self.head)
        with self.assertRaisesRegex(ValueError, "invalide"):
            self.plan([geo.Hole((math.inf, 0, 0), (0, 0, 1), 1.8)])

    def test_names_contain_type_diameter_length_grip_and_set_composition(self):
        self.assertEqual(geo.configuration_name(16, 50, "H", 2.2),
                         "BOULON H M16x50 - SERRAGE 22 mm - 1 ECROU + 2 RONDELLES")


if __name__ == "__main__":
    unittest.main()
