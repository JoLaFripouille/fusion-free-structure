import pathlib
import sys
import unittest


REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "addin" / "JHR_StructuralMembers_V1"))
from lib import assembly_geometry as shapes, dxf_geometry, upn_splice


UPN = REPO / "profiles" / "Zones_geographiques" / "Europe" / "UPN"


def profile_seats(path):
    contours = dxf_geometry.tessellate_profile_contours_mm(path)
    segments = [(p, q) for loop in contours for p, q in zip(loop, loop[1:]+loop[:1])]
    return upn_splice.inclined_seats(dxf_geometry.profile_bounds_mm(path), segments)


class UpnSpliceTests(unittest.TestCase):
    def test_two_real_seats_found_on_each_catalogue_section(self):
        for path in sorted(UPN.glob("*.dxf")):
            with self.subTest(profile=path.stem):
                lower, upper = profile_seats(path)
                for seat in (lower, upper):
                    self.assertGreater(seat.start_depth_cm, seat.end_depth_cm)
                    self.assertGreater(seat.start_cm, 0)
                    self.assertGreater(seat.end_cm, seat.start_cm)
                self.assertAlmostEqual(lower.start_depth_cm, upper.start_depth_cm)
                self.assertAlmostEqual(lower.end_depth_cm, upper.end_depth_cm)

    def test_no_assumed_slope_for_different_upn_sizes(self):
        def slope(size):
            seat, _ = profile_seats(UPN / f"UPN_{size}.dxf")
            return (seat.start_depth_cm-seat.end_depth_cm) / (seat.end_cm-seat.start_cm)

        self.assertAlmostEqual(slope(120), .08, places=3)
        self.assertAlmostEqual(slope(400), .05, places=3)

    def test_orthogonal_holes_and_taper_contact_for_both_sides(self):
        lower, upper = profile_seats(UPN / "UPN_120.dxf")
        for sign, seat in ((1, upper), (-1, lower)):
            with self.subTest(sign=sign):
                centre = 2.75
                station, half_width = upn_splice.wedge_row(seat, 0., 5.5, 1.2)
                holes = tuple((x, sign*(station-centre), 1.4) for x in (-7., -3., 3., 7.))
                cover = shapes.rectangle("Couvre-joint", (0., centre, 0.), (1., 0., 0.),
                                         (0., sign, 0.), 25., 5.5, .8, holes)
                wedge, nut_depth = upn_splice.wedge_plate(
                    cover, seat, station, half_width, centre, sign, tuple(x for x, _, _ in holes),
                )
                self.assertEqual(wedge.normal, cover.normal)
                for (x, y, diameter), (wx, wy, wd) in zip(cover.holes, wedge.holes):
                    self.assertEqual(diameter, wd)
                    vertices = cover.point(x, y), wedge.point(wx, wy)
                    self.assertEqual(vertices[0][:2], vertices[1][:2])
                for index, side in enumerate((-1, 1)):
                    position = station+side*sign*half_width
                    self.assertAlmostEqual(nut_depth-wedge.thickness_edges_cm[index], seat.depth_at(position))
                self.assertAlmostEqual(min(wedge.thickness_edges_cm), upn_splice.THIN_EDGE_CM)

    def test_rejects_when_washer_has_no_plane_width(self):
        _, seat = profile_seats(UPN / "UPN_120.dxf")
        with self.assertRaisesRegex(ValueError, "assise biaise"):
            upn_splice.wedge_row(seat, 0., 5.5, 2.0)
        with self.assertRaisesRegex(ValueError, "assise biaise"):
            upn_splice.wedge_row(seat, 3., 4., 1.2)


if __name__ == "__main__":
    unittest.main()
