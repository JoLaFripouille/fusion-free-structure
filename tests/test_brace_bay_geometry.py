import pathlib
import sys
import unittest
from dataclasses import replace


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "addin" / "JHR_StructuralMembers_V1"))

from lib import brace_bay_geometry as bay
from lib import assembly_geometry, gusset_geometry
from lib import joint_geometry as geo


class BraceBayGeometryTests(unittest.TestCase):
    def setUp(self):
        self.first = bay.SupportFace((0., 20., 40.), (1., 0., 0.), 10., 300.)
        self.second = bay.SupportFace((500., 20., 20.), (-1., 0., 0.), 20., 310.)
        self.up = (0., 0., 1.)
        self.pilot = (0., 20., 40.)

    def test_corners_measure_retractions_on_each_selected_face(self):
        frame = bay.plan(self.first, self.second, self.up, self.pilot,
                         bottom_cm=25., top_cm=50., setback_cm=(5., 8.), offset_cm=3.)
        self.assertEqual(frame.corners, (
            (5., 17., 35.), (5., 17., 250.), (492., 17., 45.), (492., 17., 260.),
        ))
        self.assertEqual(frame.diagonals, ((frame.corners[0], frame.corners[3]),
                                          (frame.corners[1], frame.corners[2])))
        first_centre, second_centre = (geo.scale(geo.add(*diagonal), .5) for diagonal in frame.diagonals)
        self.assertEqual(first_centre, second_centre)
        self.assertEqual(geo.dot(frame.normal, frame.up), 0.)

    def test_replan_follows_both_post_heights_and_the_right_face_with_same_offsets(self):
        settings = dict(bottom_cm=25., top_cm=50., setback_cm=8.)
        initial = bay.plan(self.first, self.second, self.up, self.pilot, **settings)
        moved_first = bay.SupportFace(self.first.origin, self.first.normal, 10., 360.)
        moved_second = bay.SupportFace((550., 20., 30.), self.second.normal, 30., 350.)
        moved = bay.plan(moved_first, moved_second, self.up, self.pilot, **settings)
        self.assertEqual(initial.corners[0][0], moved.corners[0][0])
        self.assertEqual(moved.corners[2], (542., 20., 55.))
        self.assertEqual(moved.corners[3], (542., 20., 300.))

    def test_uses_document_vertical_and_continues_to_face_the_other_pillar_if_reversed(self):
        shift = lambda p: (p[1], p[2], p[0])
        first, second = (bay.SupportFace(shift(face.origin), shift(face.normal), face.low, face.high)
                         for face in (self.first, self.second))
        frame = bay.plan(second, first, (0., 1., 0.), shift(self.pilot), setback_cm=10.)
        self.assertEqual(frame.across, (0., 0., -1.))
        self.assertEqual(frame.corners[0], (20., 20., 490.))
        self.assertEqual(frame.corners[3], (20., 300., 10.))

    def test_rejects_wrong_faces_and_settings_that_remove_the_opening(self):
        with self.assertRaisesRegex(ValueError, "opposées"):
            bay.plan(self.first, bay.SupportFace(self.second.origin, self.first.normal, 20., 310.),
                     self.up, self.pilot)
        with self.assertRaisesRegex(ValueError, "verticales"):
            bay.plan(self.first, bay.SupportFace(self.second.origin, (-1., 0., .1), 20., 310.),
                     self.up, self.pilot)
        with self.assertRaisesRegex(ValueError, "se regardent"):
            bay.plan(self.first, bay.SupportFace((-500., 20., 20.), self.second.normal, 20., 310.),
                     self.up, self.pilot)
        with self.assertRaisesRegex(ValueError, "hauteur de l’une des faces"):
            bay.plan(self.first, self.second, self.up, self.pilot, bottom_cm=160., top_cm=140.)
        with self.assertRaisesRegex(ValueError, "espace entre les deux faces"):
            bay.plan(self.first, self.second, self.up, self.pilot, setback_cm=250.)
        with self.assertRaisesRegex(ValueError, "valeur finie"):
            bay.plan(self.first, self.second, self.up, self.pilot, offset_cm=float("nan"))

    def test_central_plate_follows_four_diagonal_ends_with_hole_margins(self):
        level_second = replace(self.second, low=self.first.low, high=self.first.high)
        frame = bay.plan(self.first, level_second, self.up, self.pilot, bottom_cm=10., top_cm=10.)
        centre = geo.scale(geo.add(*frame.diagonals[0]), .5)
        ends = tuple(point for diagonal in frame.diagonals for point in diagonal)
        arms = tuple(gusset_geometry.GussetArm(
            near=geo.add(centre, geo.scale(geo.normalize(geo.subtract(end, centre)), 6.)),
            far=end, normal=frame.normal, clear_width_cm=4.8, thickness_cm=.6,
        ) for end in ends)
        margin = 1.8
        dimensions = dict(thickness_cm=.8, hole_diameter_cm=1.4, rows=2, end_distance_cm=3.,
                          pitch_cm=4., edge_distance_cm=margin, washer_radius_cm=1.2)
        gusset = gusset_geometry.central_gusset(arms, **dimensions)
        rectangle = gusset_geometry.central_gusset(arms, **dimensions, level_outline=True)
        for group, reference in zip(gusset.centres_by_arm, rectangle.centres_by_arm):
            for hole, expected in zip(group, reference):
                self.assertAlmostEqual(geo.length(geo.subtract(hole, expected)), 0.)

        plate = gusset.plate
        self.assertGreater(len(plate.outline), 4)
        outline = tuple(plate.point(*point) for point in plate.outline)
        edges = tuple(zip(outline, outline[1:] + outline[:1]))
        for arm, holes in zip(arms, gusset.centres_by_arm):
            direction = geo.normalize(geo.subtract(arm.far, arm.near))
            tip = geo.add(holes[-1], geo.scale(direction, margin))
            cut = next(((a, b) for a, b in edges
                        if all(abs(geo.dot(geo.subtract(point, tip), direction)) < 1e-8 for point in (a, b))),
                       None)
            self.assertIsNotNone(cut)
            self.assertAlmostEqual(geo.length(geo.subtract(*cut)), 2*margin)
        full_wing = tuple(replace(arm, bearing_offsets_cm=(-2.1, 3.9)) for arm in arms)
        rectangular = gusset_geometry.central_gusset(full_wing, bearing_vertical=frame.up, **dimensions)
        outline = rectangular.plate.outline
        edges = tuple(geo.subtract(b, a) for a, b in zip(outline, outline[1:]+outline[:1]))
        self.assertEqual(len(edges), 8)
        self.assertEqual(sum(abs(x) < 1e-8 for x, _ in edges), 2)
        self.assertEqual(sum(abs(y) < 1e-8 for _, y in edges), 2)
        for arm in arms:
            direction = geo.normalize(geo.subtract(arm.far, arm.near))
            local = tuple(geo.dot(direction, axis) for axis in (rectangular.plate.u, rectangular.plate.v))
            oblique = [geo.length(edge) for edge in edges if abs(geo.dot(edge, local)) < 1e-8]
            self.assertTrue(oblique)
            self.assertGreaterEqual(min(oblique), 6.-1e-8)
        rounded = gusset_geometry.central_gusset(full_wing, bearing_vertical=frame.up,
                                                 scallop_depth_cm=.5, **dimensions)
        self.assertEqual(rounded.plate.outline, outline)
        self.assertEqual(rounded.centres_by_arm, rectangular.centres_by_arm)
        self.assertEqual(len(rounded.plate.arcs), 4)
        for index, middle in rounded.plate.arcs:
            chord_middle = geo.scale(geo.add(outline[index], outline[(index+1) % 8]), .5)
            self.assertAlmostEqual(geo.length(geo.subtract(middle, chord_middle)), .5)
        with self.assertRaises(assembly_geometry.DimensionError) as caught:
            gusset_geometry.central_gusset(full_wing, bearing_vertical=frame.up,
                                          scallop_depth_cm=20., **dimensions)
        self.assertEqual(caught.exception.keys, ("scallop_depth_mm",))


if __name__ == "__main__":
    unittest.main()
