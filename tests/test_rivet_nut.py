"""Contrôle du choix de référence et de sa préparation hors Fusion."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace as Entity
import unittest
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addin" / "JHR_StructuralMembers_V1"))
import lib
from lib import fastener_geometry as geometry, rivet_nut


class RivetNutTests(unittest.TestCase):
    def test_m6_three_heads_share_hole_but_have_different_preparations(self):
        expects = {"flat": ("233 07 060 230", 0),
                   "reduced": ("343 67 060 230", 0),
                   "countersunk": ("233 17 060 300", 1.2)}
        for head, (reference, countersink) in expects.items():
            with self.subTest(head=head):
                result = rivet_nut.preparation(6, head, 2)
                self.assertEqual(result["reference"], reference)
                self.assertEqual(result["hole_diameter_mm"], 9)
                self.assertEqual(result["hole_tolerance_plus_mm"], .1)
                self.assertEqual(result["countersink_depth_mm"], countersink)

    def test_countersink_at_grip_boundary_selects_matching_reference(self):
        self.assertEqual(rivet_nut.specification(6, "countersunk", 3, 1.2).reference, "233 17 060 300")
        self.assertEqual(rivet_nut.specification(6, "countersunk", 3, 1.5).reference, "233 17 060 450")
        with self.assertRaisesRegex(ValueError, "1.2 ou 1.5 mm"):
            rivet_nut.specification(6, "countersunk", 3, 1.3)

    def test_grip_outside_selected_head_range_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Aucune référence"):
            rivet_nut.specification(6, "countersunk", 1)
        self.assertEqual(rivet_nut.specification(6, "reduced", 1).reference, "343 67 060 230")

    def test_every_supported_size_has_positive_bore_and_head_relief(self):
        for head in rivet_nut.HEADS:
            for diameter in rivet_nut.DIAMETERS_MM:
                with self.subTest(head=head, diameter=diameter):
                    spec = rivet_nut.specification(diameter, head, 2)
                    bore = rivet_nut.preparation(diameter, head, 2)["hole_diameter_mm"]
                    self.assertGreater(spec.head_diameter_mm, bore)
                    self.assertGreater(bore, diameter)

    @staticmethod
    def position(grip_mm, countersink=None):
        return geometry.Placement((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                                  grip_mm * .1, countersink)

    def test_screw_seat_and_length_include_head_stack_and_washer(self):
        spec = rivet_nut.specification(6, "flat", 2)
        screw = rivet_nut.screw_dimensions(6, spec, self.position(2), "CHC", stack_mm=3)
        self.assertAlmostEqual(screw["minimum_length_mm"], 17.1)
        self.assertEqual(screw["length_mm"], 20)
        self.assertAlmostEqual(screw["support_cm"], -.45)
        self.assertAlmostEqual(screw["blind_projection_mm"], 11.9)
        self.assertAlmostEqual(screw["beyond_nut_mm"], 3.9)
        self.assertTrue(screw["washer"])

    def test_screw_without_washer_uses_the_same_seat_and_reaches_further(self):
        spec = rivet_nut.specification(6, "flat", 2)
        with_washer = rivet_nut.screw_dimensions(6, spec, self.position(2), "CHC", length_mm=15)
        screw = rivet_nut.screw_dimensions(6, spec, self.position(2), "CHC", length_mm=15,
                                          screw_washer=False)
        self.assertFalse(screw["washer"])
        self.assertEqual(screw["washer_thickness_mm"], 0.)
        self.assertEqual(screw["support_cm"], with_washer["support_cm"])
        self.assertAlmostEqual(screw["blind_projection_mm"],
                               with_washer["blind_projection_mm"] + with_washer["washer_thickness_mm"])
        self.assertAlmostEqual(screw["minimum_length_mm"], 12.5)
        with self.assertRaisesRegex(ValueError, "disponibles"):
            rivet_nut.screw_dimensions(6, spec, self.position(2), "CHC", length_mm=15,
                                       blind_clearance_mm=10, screw_washer=False)

    def test_screw_checks_short_length_and_limited_back_clearance(self):
        spec = rivet_nut.specification(6, "flat", 2)
        with self.assertRaisesRegex(ValueError, "d’au moins"):
            rivet_nut.screw_dimensions(6, spec, self.position(2), "TBHC", length_mm=13)
        with self.assertRaisesRegex(ValueError, "disponibles"):
            rivet_nut.screw_dimensions(6, spec, self.position(2), "TBHC", blind_clearance_mm=9)
        screw = rivet_nut.screw_dimensions(6, spec, self.position(2), "TBHC", length_mm=14.1,
                                          blind_clearance_mm=9)
        self.assertAlmostEqual(screw["blind_projection_mm"], 9.)

    def test_countersunk_screw_support_agrees_before_and_after_preparation(self):
        spec = rivet_nut.specification(6, "countersunk", 2)
        centre, axis = (0, 0, 0), (0, 0, 1)
        prepared = geometry.CountersunkHole(centre, axis, .9, 1.14, .12)
        actual = rivet_nut.screw_dimensions(6, spec, self.position(2, prepared), "CHC")
        preview = rivet_nut.screw_dimensions(6, spec, self.position(2), "CHC")
        self.assertEqual(actual, preview)
        self.assertEqual(actual["support_cm"], 0)
        self.assertGreaterEqual(actual["beyond_nut_mm"], 1.)

    def test_second_stage_measures_the_stack_and_checks_the_clearance_opening(self):
        position = geometry.Placement((2., 3., 4.), (0., 1., 0.), (0., 0., 1.), (1., 0., 0.), .2)
        rim = Entity(center=(1.45, 3., 4.), radius=.33)
        support = Entity(geometry=object(), pointOnFace=(1.45, 8., 9.), edges=[Entity(geometry=rim)],
                         evaluator=Entity(getNormalAtPoint=lambda _: (True, (-1., 0., 0.))))
        core = Entity(Plane=Entity(cast=lambda shape: shape), Circle3D=Entity(cast=lambda shape: shape))
        creator = Entity(point=tuple, read_hole=lambda _: geometry.Hole(rim.center, (1., 0., 0.), .66))
        with (patch.dict(sys.modules, {"adsk": Entity(core=core), "adsk.core": core}),
              patch.object(lib, "fastener_creator", creator, create=True)):
            stack = rivet_nut._support_stack_mm(support, position, -.15, 6, "CHC", True)
            self.assertAlmostEqual(stack, 4.)
            rim.center = (1.45, 3.2, 4.)
            with self.assertRaisesRegex(ValueError, "trou rond dans l’axe"):
                rivet_nut._support_stack_mm(support, position, -.15, 6, "CHC", True)
            support.pointOnFace = (2.1, 8., 9.)
            with self.assertRaisesRegex(ValueError, "devant l’insert"):
                rivet_nut._support_stack_mm(support, position, -.15, 6, "CHC", True)

    def test_second_stage_uses_existing_catalog_reference_and_detects_an_existing_screw(self):
        config = dict(model="JHR_rivet_nut", diameter_mm=6, head="flat", grip_cm=.3,
                      reference="233 07 060 255", linked_to_hole=True, screws=0)
        marker = Entity(value=json.dumps(config))
        insert = Entity(name="Insert gauche", boundingBox=Entity(minPoint=Entity(z=-.15)))
        bodies = Mock(count=1)
        bodies.__iter__ = Mock(return_value=iter([insert]))
        bodies.item.return_value = insert
        component = Entity(attributes=Entity(itemByName=lambda *_: marker), bRepBodies=bodies,
                           features=Entity(baseFeatures=[]))
        selected = Entity(component=component, isReferencedComponent=False,
                          transform2=Entity(getAsCoordinateSystem=lambda: ((0., 0., 0.), (1., 0., 0.),
                                                                           (0., 1., 0.), (0., 0., 1.))))
        occurrences = Entity(count=1, item=lambda _: selected)
        design = Entity(designType="parametric", rootComponent=Entity(allOccurrencesByComponent=lambda _: occurrences))
        fusion = Entity(Occurrence=Entity(cast=lambda value: value), BRepBody=Entity(cast=lambda _: None),
                        DesignTypes=Entity(ParametricDesignType="parametric"))
        creator = Entity(ATTRIBUTE_GROUP="test", point=tuple)
        with (patch.dict(sys.modules, {"adsk": Entity(fusion=fusion), "adsk.fusion": fusion}),
              patch.object(lib, "fastener_creator", creator, create=True)):
            result = rivet_nut.attach_screw(design, selected, preview=True, screw_stack_mm=4, screw_washer=False)
            self.assertEqual(result["reference"], "233 07 060 255")
            self.assertEqual(result["screw"]["stack_mm"], 4.)
            self.assertFalse(result["stack_measured"])
            marker.value = json.dumps(dict(config, screws=1))
            with self.assertRaisesRegex(ValueError, "déjà une vis"):
                rivet_nut.attach_screw(design, selected, preview=True)

    def test_preparation_uses_native_opening_and_rolls_back_if_new_bore_cannot_be_resolved(self):
        hole_input = Mock()
        feature = Mock(isValid=True, healthState="healthy")
        features = Mock()
        features.createCountersinkInput.return_value = hole_input
        features.add.return_value = feature
        stock = Entity(faces=[], parentComponent=Entity(features=Entity(holeFeatures=features)))
        wall = Entity(body=Entity(nativeObject=stock), assemblyContext=None)
        entry, opening = object(), object()
        core = Entity(ValueInput=Entity(createByReal=float, createByString=str))
        fusion = Entity(FeatureHealthStates=Entity(HealthyFeatureHealthState="healthy"))
        row = rivet_nut.specification(6, "countersunk", 2)
        with (patch.dict(sys.modules, {"adsk": Entity(core=core, fusion=fusion),
                                      "adsk.core": core, "adsk.fusion": fusion}),
              patch.object(lib, "fastener_creator", Entity(), create=True)):
            with self.assertRaisesRegex(RuntimeError, "retrouvé et mesuré"):
                rivet_nut._cut_pilot(wall, Entity(nativeObject=entry), Entity(nativeObject=opening),
                                     6, "countersunk", self.position(2), row)
        hole_input.setPositionAtCenter.assert_called_once_with(entry, opening)
        hole_input.setPositionByPoint.assert_not_called()
        feature.deleteMe.assert_called_once_with()

    def test_blind_end_keeps_catalogue_envelopes_and_open_bore(self):
        for head in rivet_nut.HEADS:
            for diameter in rivet_nut.DIAMETERS_MM:
                for row in rivet_nut._specs(diameter, head):
                    with self.subTest(head=head, diameter=diameter, reference=row.reference):
                        grip = row.grip_max_mm * .1
                        blind = rivet_nut._blind_profile(diameter, row, grip)
                        self.assertAlmostEqual((blind.tip_station - grip) * 10, row.blind_projection_mm)
                        self.assertAlmostEqual((blind.sleeve_radius + blind.bulge_minor_radius) * 20,
                                               rivet_nut._MAX_BULGE_MM[diameter])
                        self.assertGreater(blind.bulge_station, grip)
                        self.assertLess(blind.bulge_station - blind.bulge_minor_radius, grip)
                        self.assertLess(blind.bulge_station + blind.bulge_minor_radius,
                                        blind.tip_station - blind.chamfer)
                        self.assertGreater(blind.chamfer, 0)
                        self.assertGreater(blind.sleeve_radius - blind.chamfer, blind.bore_radius)


if __name__ == "__main__":
    unittest.main()
