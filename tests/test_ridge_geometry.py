import pathlib
import sys
import unittest
from dataclasses import replace


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "addin" / "JHR_StructuralMembers_V1"))

from lib import joint_geometry as geo, ridge_geometry as ridge


POINT = (40., -15., 120.)
DIMS = dict(width=0, height=0, thickness=1.2, hole=1.4, gauge=0, rows=4, pitch=0,
            reach=22, drop=11, web=.8, flange=1, flange_width=7, weld_relief=2)


def beam(side, slope, width=(-4.1, 4.1), height=(-8., 8.)):
    return ridge.RidgeBeam(
        POINT, geo.normalize((side, 0, -slope)), geo.normalize((side*slope, 0, 1)),
        (0, 1, 0), width, height, 250.,
    )


class RidgeGeometryTests(unittest.TestCase):
    def test_end_plates_share_holes_and_match_opposite_cut_planes(self):
        first = beam(-1, .3)
        second = beam(1, .6, width=(-2.5, 7.5), height=(-13., 7.))
        second = replace(second, height_axis=geo.scale(second.height_axis, -1), height_limits=(-7., 13.))
        plan = ridge.plan_ridge(POINT, first, second, DIMS, washer_radius=1.2)
        self.assertEqual(len(plan.plates), 6)
        self.assertEqual(len(plan.bolt_centres), 8)
        for plate, cut in zip(plan.plates, plan.cuts):
            self.assertEqual(plate.normal, cut.interior_normal)
            for point in (plate.point(x, y) for x, y in plate.outline):
                back = geo.add(point, geo.scale(plate.normal, plate.thickness_cm))
                self.assertAlmostEqual(geo.plane_signed_distance(back, cut.point, cut.interior_normal), 0.)
            holes = (plate.point(x, y) for x, y, _ in plate.holes)
            self.assertEqual(sorted(holes), sorted(plan.bolt_centres))
        for _, y, _ in plan.bolt_centres:
            self.assertTrue(y < POINT[1]-4.1-1.2 or y > POINT[1]+7.5+1.2)

    def test_double_haunches_fit_their_own_cut_and_keep_constant_sole_thickness(self):
        plan = ridge.plan_ridge(POINT, beam(-1, .25), beam(1, .55), DIMS, double=True)
        self.assertEqual(len(plan.plates), 10)
        for index, cut in enumerate(plan.cuts):
            for web, sole in zip(plan.plates[2+4*index:6+4*index:2], plan.plates[3+4*index:6+4*index:2]):
                self.assertEqual(web.outline[0], (DIMS["weld_relief"], 0.))
                for plate, heel_vertices in ((web, web.outline[1:3]), (sole, (sole.outline[0], sole.outline[-1]))):
                    for vertex in heel_vertices:
                        self.assertAlmostEqual(geo.plane_signed_distance(plate.point(*vertex), cut.point, cut.interior_normal), 0.)
                    for vertex in plate.outline:
                        self.assertGreaterEqual(geo.plane_signed_distance(plate.point(*vertex), cut.point, cut.interior_normal), -1e-8)
                heel, toe, toe_back, heel_back = (sole.point(*xy) for xy in sole.outline)
                direction = geo.normalize(geo.subtract(toe, heel))
                for end in (toe_back, heel_back):
                    self.assertAlmostEqual(geo.length(geo.cross(geo.subtract(end, heel), direction)), DIMS["flange"])

    def test_rejects_invalid_meeting_slopes_and_plate_clearance(self):
        first = beam(-1, .3)
        second = beam(1, .6)
        scenarios = (
            (replace(second, endpoint=(40., -14., 120.)), DIMS),
            (replace(second, interior_axis=(1., .2, -.6)), DIMS),
            (replace(second, across_axis=(0., 0., 1.)), DIMS),
            (replace(second, length=10.), DIMS),
            (second, {**DIMS, "gauge": 8.5}),
            (second, {**DIMS, "reach": 5.}),
        )
        for changed_beam, dims in scenarios:
            with self.subTest(changed_beam=changed_beam, dims=dims), self.assertRaises(ValueError):
                ridge.plan_ridge(POINT, first, changed_beam, dims, washer_radius=1.2)


if __name__ == "__main__":
    unittest.main()
