import pathlib
import sys
from types import SimpleNamespace
import unittest


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "addin" / "JHR_StructuralMembers_V1"))

from lib import crossing_braces as crossing, joint_geometry as geometry


def brace(start, end, width_mm=60, family="Corniere"):
    def point(vector):
        return SimpleNamespace(asArray=lambda: vector)

    curve = SimpleNamespace(worldGeometry=SimpleNamespace(startPoint=point(start), endPoint=point(end)))
    normal = (0., 0., 1.)
    axis = geometry.normalize(geometry.subtract(end, start))
    return SimpleNamespace(
        curve=curve, family=family, anchor=(0., 0.),
        bounds=(-width_mm/2, -30., width_mm/2, 30.),
        section_x=geometry.cross(normal, axis), section_y=normal,
    )


class CrossingBraceTests(unittest.TestCase):
    def check_point(self, actual, expected):
        for value, target in zip(actual, expected):
            self.assertAlmostEqual(value, target)

    def test_angle_and_section_determine_distinct_clearance_lengths(self):
        start, end = (-20., 0., 0.), (30., 0., 0.)
        angled_start, angled_end = (-12., -16., 0.), (18., 24., 0.)
        first, second = crossing.plan((brace(start, end), brace(angled_start, angled_end, 80)), .2)
        for cut in (first, second):
            self.check_point(cut.centre, (0., 0., 0.))
            self.assertAlmostEqual(cut.fraction, .4)
        self.assertAlmostEqual(first.half_gap_cm, 7.5)
        self.assertAlmostEqual(second.half_gap_cm, 7.)
        self.check_point(first.branches[0][0], (-7.5, 0., 0.))
        self.check_point(first.branches[1][0], (7.5, 0., 0.))
        self.check_point(second.branches[0][0], (-4.2, -5.6, 0.))
        self.check_point(second.branches[1][0], (4.2, 5.6, 0.))
        self.assertEqual(tuple(branch[1] for branch in first.branches), (start, end))
        self.assertEqual(tuple(branch[1] for branch in second.branches), (angled_start, angled_end))

    def test_flipping_the_axis_swaps_branches_without_moving_cut(self):
        second = brace((0., -24., 0.), (0., 26., 0.))
        forward = crossing.plan((brace((-25., 0., 0.), (30., 0., 0.)), second), .2)[0]
        reverse = crossing.plan((brace((30., 0., 0.), (-25., 0., 0.)), second), .2)[0]
        self.assertAlmostEqual(reverse.fraction, 1.-forward.fraction)
        for branch, inverse in zip(forward.branches, reversed(reverse.branches)):
            self.check_point(branch[0], inverse[0])
            self.assertEqual(branch[1], inverse[1])

    def test_requires_real_crossing_and_enough_clearance_on_both_sides(self):
        first = brace((-25., 0., 0.), (30., 0., 0.))
        for second in (brace((0., 2., 0.), (0., 25., 0.)), brace((0., -1., 0.), (0., 25., 0.))):
            with self.assertRaisesRegex(ValueError, "dégagement sort"):
                crossing.plan((first, second), .2)
        with self.assertRaisesRegex(ValueError, "même plan"):
            crossing.plan((first, brace((0., -25., .5), (0., 25., .5))), .2)
        with self.assertRaisesRegex(ValueError, "angle trop faible"):
            crossing.plan((first, brace((-25., -.5, 0.), (25., .5, 0.))), .2)

    def test_rejects_wrong_profiles_and_invalid_clearance(self):
        first = brace((-25., 0., 0.), (30., 0., 0.))
        with self.assertRaisesRegex(ValueError, "deux cornières"):
            crossing.plan((first, brace((0., -25., 0.), (0., 25., 0.), family="IPE")), .2)
        with self.assertRaisesRegex(ValueError, "positif ou nul"):
            crossing.plan((first, brace((0., -25., 0.), (0., 25., 0.))), -1.)


if __name__ == "__main__":
    unittest.main()
