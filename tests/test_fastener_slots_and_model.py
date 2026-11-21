from __future__ import annotations

import importlib.util
import math
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

ADDIN = pathlib.Path(__file__).resolve().parents[1] / 'addin' / 'JHR_StructuralMembers_V1'
sys.path.insert(0, str(ADDIN))
from lib import fastener_geometry as geo, simple_fastener_creator as simple


class SlotAndModelPlans(unittest.TestCase):
    head = geo.SupportPlane((0, 0, 0), (0, 0, -1))
    nut = geo.SupportPlane((0, 0, 1.8), (0, 0, 1))

    def test_cap_choice_and_arbitrary_axial_origins_give_same_bolt_axis(self):
        a = geo.slot_from_caps((0, 0, 2), (2.6, 0, 8), (0, 0, 1), .7)
        b = geo.slot_from_caps((2.6, 0, 8), (0, 0, 2), (0, 0, -1), .7)
        self.assertAlmostEqual(a.length_cm, 4.)
        self.assertEqual(a.slot_axis, (1., 0., 0.))
        _, poses, duplicates, length = geo.plan_modeled_fasteners([a, b], self.head, self.nut, 12)
        self.assertEqual(len(poses), 1)
        self.assertEqual(duplicates, 1)
        self.assertAlmostEqual(poses[0].origin[0], 1.3)
        self.assertAlmostEqual(poses[0].origin[2], 0)
        self.assertEqual(length, 40.)

    def test_rotated_slot_has_independent_shaft_and_longitudinal_axes(self):
        slot = geo.slot_from_caps((4, 0, 5), (9, 2.6, 5), (1, 0, 0), .7)
        self.assertEqual(slot.slot_axis, (0., 1., 0.))
        _, poses, _, _ = geo.plan_modeled_fasteners([slot],
            geo.SupportPlane((0, 0, 0), (-1, 0, 0)),
            geo.SupportPlane((1.8, 0, 0), (1, 0, 0)), 12)
        self.assertEqual(poses[0].origin, (0., 1.3, 5.))
        self.assertEqual(poses[0].z_axis, (1., 0., 0.))

    def test_coincident_caps_and_invalid_radius_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'confondues'):
            geo.slot_from_caps((0, 0, 0), (0, 0, 8), (0, 0, 1), .7)
        with self.assertRaisesRegex(ValueError, 'positif'):
            geo.slot_from_caps((0, 0, 0), (2.6, 0, 0), (0, 0, 1), 0)

    def test_actual_live_grips_round_to_40_and_130_mm(self):
        hole = geo.Hole((0, 0, .5), (0, 0, 1), 1.4)
        for grip_cm, expected, projection in [(1.8, 40., 7.), (11., 130., 5.)]:
            _, poses, _, length = geo.plan_modeled_fasteners([hole], self.head,
                geo.SupportPlane((0, 0, grip_cm), (0, 0, 1)), 12)
            self.assertEqual(length, expected)
            dimensions = simple.dimensions(12, length, poses[0].grip_cm)
            self.assertAlmostEqual(dimensions['projection_mm'], projection)
            self.assertAlmostEqual(dimensions['tip_cm'], length / 10 - .25)

    def test_requested_projection_and_manual_length_are_enforced(self):
        hole = geo.Hole((0, 0, .5), (0, 0, 1), 1.4)
        _, _, _, length = geo.plan_modeled_fasteners([hole], self.head, self.nut, 12, projection_mm=12)
        self.assertEqual(length, 45)
        with self.assertRaisesRegex(ValueError, 'trop courte'):
            geo.plan_modeled_fasteners([hole], self.head, self.nut, 12, length_mm=35)
        with self.assertRaisesRegex(ValueError, 'dépassement'):
            geo.plan_modeled_fasteners([hole], self.head, self.nut, 12, projection_mm=-1)
        with self.assertRaisesRegex(ValueError, 'disponible'):
            geo.plan_modeled_fasteners([hole], self.head, self.nut, 15)

    def test_independent_washers_change_stack_and_keep_the_supports(self):
        hole = geo.Hole((0, 0, .5), (0, 0, 1), 1.4)
        for head_washer, nut_washer, expected_length in (
            (False, False, 35.), (True, False, 40.), (False, True, 40.), (True, True, 40.),
        ):
            with self.subTest(head_washer=head_washer, nut_washer=nut_washer):
                options = dict(head_washer=head_washer, nut_washer=nut_washer)
                _, poses, _, length = geo.plan_modeled_fasteners([hole], self.head, self.nut, 12, **options)
                self.assertEqual(length, expected_length)
                self.assertEqual(poses[0].origin, (0., 0., 0.))
                self.assertEqual(poses[0].grip_cm, 1.8)
                dimensions = simple.dimensions(12, length, 1.8, **options)
                self.assertEqual(dimensions["head_washer_cm"], .25 if head_washer else 0.)
                self.assertEqual(dimensions["nut_washer_cm"], .25 if nut_washer else 0.)
                self.assertAlmostEqual(dimensions["tip_cm"], length*.1-dimensions["head_washer_cm"])
                self.assertAlmostEqual(dimensions["projection_mm"],
                                       length-28.-2.5*(head_washer+nut_washer))
        with self.assertRaisesRegex(ValueError, "trop courte"):
            geo.plan_modeled_fasteners([hole], self.head, self.nut, 12, length_mm=35, nut_washer=True)

    def test_washer_options_for_fraisure_and_tapped_hole(self):
        seat = geo.CountersunkHole((0, 0, 0), (0, 0, 1), 1.4, 2.4, .5)
        _, _, _, length = geo.plan_modeled_fasteners([seat], self.head, self.nut, 12, head="TF",
                                                    nut_washer=False)
        self.assertEqual(length, 35.)
        with self.assertRaisesRegex(ValueError, "directement dans la fraisure"):
            simple.dimensions(12, 40, 1.8, countersink=seat, head_washer=True)
        with self.assertRaisesRegex(ValueError, "rondelle côté écrou"):
            simple.dimensions(12, 40, 1.8, tapped=True, nut_washer=True)
        dims = simple.dimensions(12, 18., 1.8, projection_mm=0., tapped=True, head_washer=False)
        self.assertEqual((dims["head_washer_cm"], dims["nut_washer_cm"], dims["nut_height_cm"]), (0., 0., 0.))
        self.assertEqual(dims["tip_cm"], 1.8)
        self.assertEqual(dims["projection_mm"], 0.)
        self.assertEqual(geo.configuration_name(12, 18, "H-Taraudage", 1.8, head_washer=False),
                         "VIS H M12x18 - TARAUDAGE")

    def test_reverse_and_existing_set_do_not_create_a_duplicate(self):
        hole = geo.Hole((0, 0, .5), (0, 0, 1), 1.4)
        _, occupied, _, _ = geo.plan_modeled_fasteners([hole], self.head, self.nut, 12)
        _, poses, ignored, _ = geo.plan_modeled_fasteners([hole], self.head, self.nut, 12,
                                                        occupied=occupied, reverse=True)
        self.assertEqual(poses, ())
        self.assertEqual(ignored, 1)

    def test_simple_dimensions_use_catalogue_and_never_scale_a_different_bolt(self):
        dims = simple.dimensions(12, 40, 1.8)
        self.assertEqual(dims['spec'].head_across_flats_mm, 18.)
        self.assertEqual(dims['spec'].washer_outer_diameter_mm, 24.)
        with self.assertRaisesRegex(ValueError, 'disponible'):
            simple.dimensions(15, 50, 1.8)
        with self.assertRaisesRegex(ValueError, 'trop courte'):
            simple.dimensions(12, 30, 1.8)

    def test_countersunk_rim_fits_the_seat_and_socket_is_blind(self):
        for diameter, socket_flats in [(12, 8), (16, 10), (20, 12), (24, 14)]:
            for depth in [.5, .02]:
                with self.subTest(diameter=diameter, depth=depth):
                    seat = geo.CountersunkHole((0, 0, 0), (0, 0, 1),
                                               diameter * .1 + .2, diameter * .2, depth)
                    dims = simple.dimensions(diameter, 100, 1.8, countersink=seat)
                    slope = (seat.opening_diameter_cm - seat.diameter_cm) / (2 * depth)
                    rim_height = (seat.opening_diameter_cm / 2 - dims['rim_radius_cm']) / slope
                    self.assertAlmostEqual(rim_height, min(.06, depth * .2))
                    self.assertLess(rim_height, depth)
                    self.assertEqual(dims['socket_flats_mm'], socket_flats)
                    self.assertLess(socket_flats * .1 / math.sqrt(3), diameter * .05)
                    self.assertGreater(dims['socket_depth_cm'], 0)
                    self.assertLess(dims['socket_depth_cm'], dims['head_height_cm'])
                    self.assertEqual(dims['tip_cm'], 10.)

    def test_socket_heads_reuse_the_round_or_slot_placement(self):
        hole = geo.Hole((0, 0, .5), (0, 0, 1), .66)
        slot = geo.slot_from_caps((0, 0, .5), (.8, 0, .5), (0, 0, 1), .33)
        for head, aperture, offset, flats, height in (
            ("CHC", hole, 0., 5., .6),
            ("TBHC", slot, .4, 4., .33),
        ):
            with self.subTest(head=head):
                _, poses, _, length = geo.plan_modeled_fasteners(
                    [aperture], self.head, self.nut, 6, head=head,
                )
                self.assertEqual(length, 35.)
                self.assertAlmostEqual(poses[0].origin[0], offset)
                dimensions = simple.dimensions(6, length, poses[0].grip_cm, head=head)
                self.assertAlmostEqual(dimensions["head_height_cm"], height)
                self.assertEqual(dimensions["socket_flats_mm"], flats)
                self.assertLess(dimensions["socket_depth_cm"], height)

    def test_button_head_size_limit_does_not_limit_the_cylindrical_head(self):
        self.assertEqual(simple.dimensions(20, 60, 1.8, head="CHC")["socket_flats_mm"], 17.)
        with self.assertRaisesRegex(ValueError, "Diamètres disponibles"):
            simple.dimensions(20, 60, 1.8, head="TBHC")


class Point:
    def __init__(self, *xyz): self.xyz = xyz
    def asArray(self): return self.xyz


class Geometry:
    def __init__(self, kind, **kwargs): self.kind = kind; self.__dict__.update(kwargs)


class Face:
    def __init__(self, index, geometry, p=(0, 0, 0), normal=(0, 0, 1)):
        self.tempId, self.geometry, self.edges = index, geometry, []
        self.pointOnFace = Point(*p)
        self.evaluator = types.SimpleNamespace(getNormalAtPoint=lambda _: (True, Point(*normal)))


class Edge:
    def __init__(self, geometry, faces): self.geometry, self.faces = geometry, faces


def cylinder(x): return Geometry('cylinder', radius=.7, origin=Point(x, 0, 0), axis=Point(0, 0, 1))


def capsule(index=1, shift=0):
    left = Face(index, cylinder(shift), (shift-.7, 0, .5), (1, 0, 0))
    right = Face(index+1, cylinder(shift+2.6), (shift+3.3, 0, .5), (-1, 0, 0))
    walls = [Face(index+10+i, Geometry('plane', origin=Point(0, y, 0), normal=Point(0, 1, 0)))
             for i, y in enumerate([-.7, .7])]
    for cap, x in [(left, shift), (right, shift+2.6)]:
        for wall, y in zip(walls, [-.7, .7]):
            edge = Edge(Geometry('line', startPoint=Point(x, y, 0), endPoint=Point(x, y, 1)), [cap, wall])
            cap.edges.append(edge); wall.edges.append(edge)
    return left, right, walls


class NativeTopologyAdapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        core = types.ModuleType('adsk.core'); fusion = types.ModuleType('adsk.fusion')
        for name, kind in [('Cylinder', 'cylinder'), ('Plane', 'plane'), ('Line3D', 'line'),
                           ('Circle3D', 'circle'), ('Arc3D', 'arc')]:
            setattr(core, name, types.SimpleNamespace(cast=lambda g, k=kind: g if getattr(g, 'kind', None)==k else None))
        fusion.BRepFace = types.SimpleNamespace(cast=lambda e: e if isinstance(e, Face) else None)
        fusion.BRepEdge = types.SimpleNamespace(cast=lambda e: e if isinstance(e, Edge) else None)
        module = types.ModuleType('adsk'); module.core=core; module.fusion=fusion
        spec = importlib.util.spec_from_file_location('lib._test_fastener_adapter', ADDIN/'lib'/'fastener_creator.py')
        adapter = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'adsk':module, 'adsk.core':core, 'adsk.fusion':fusion,
                                      spec.name:adapter}):
            spec.loader.exec_module(adapter)
        cls.adapter = adapter

    def test_selecting_either_cap_returns_the_middle_not_a_cap_centre(self):
        left, right, _ = capsule()
        for cap in [left, right]:
            result = self.adapter.read_hole(cap)
            self.assertIsInstance(result, geo.Slot)
            self.assertAlmostEqual(result.center[0], 1.3)
            self.assertAlmostEqual(result.length_cm, 4.)

    def test_arc_edge_and_cap_select_same_axis(self):
        left, _, _ = capsule()
        edge = Edge(Geometry('arc'), [left])
        self.assertEqual(self.adapter.read_hole(edge), self.adapter.read_hole(left))

    def test_unrelated_nearby_hole_cannot_be_used_as_the_other_cap(self):
        left, _, walls = capsule()
        unrelated = Face(99, cylinder(.8), (.1, 0, .5), (1, 0, 0))
        wall = walls[0]
        edge = Edge(Geometry('line', startPoint=Point(.8, -.7, 0), endPoint=Point(.8, -.7, 1)), [unrelated, wall])
        unrelated.edges.append(edge); wall.edges.append(edge)
        self.assertAlmostEqual(self.adapter.read_hole(left).center[0], 1.3)

    def test_incomplete_or_inconsistent_side_walls_are_refused(self):
        left, _, walls = capsule()
        left.edges.pop()
        with self.assertRaisesRegex(ValueError, 'incomplet'):
            self.adapter.read_hole(left)
        left, _, walls = capsule()
        walls[0].geometry.origin = Point(0, -2, 0)
        with self.assertRaisesRegex(ValueError, 'parois'):
            self.adapter.read_hole(left)

    def test_round_holes_keep_the_existing_round_path(self):
        face = Face(1, cylinder(0), (.7, 0, .5), (-1, 0, 0))
        self.assertIsInstance(self.adapter.read_hole(face), geo.Hole)


if __name__ == '__main__': unittest.main()
