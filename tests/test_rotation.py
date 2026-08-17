import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDIN = ROOT / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ADDIN))

from lib import preview_geometry, profile_catalog, rotation


class RotationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profiles = profile_catalog.discover_profiles(ADDIN, include_custom=False)
        cls.ipe100 = next(
            profile for profile in profiles
            if profile.dxf_path.name == "IPE_100.dxf"
        )

    def test_point_rotates_counterclockwise_around_origin(self):
        x, y = rotation.rotate_point((2.0, 0.0), math.radians(90.0))
        self.assertAlmostEqual(x, 0.0, places=12)
        self.assertAlmostEqual(y, 2.0, places=12)

    def test_off_center_anchor_stays_at_origin_while_profile_rotates(self):
        contours = preview_geometry.tessellate_profile_contours_cm(
            self.ipe100.dxf_path,
            anchor_mm=self.ipe100.anchor_mm("TL"),
        )
        rotated = rotation.rotate_contours(contours, math.radians(90.0))
        xs = [point[0] for contour in rotated for point in contour]
        ys = [point[1] for contour in rotated for point in contour]
        self.assertAlmostEqual(min(xs), 0.0, places=9)
        self.assertAlmostEqual(max(xs), 10.0, places=9)
        self.assertAlmostEqual(min(ys), 0.0, places=9)
        self.assertAlmostEqual(max(ys), 5.5, places=9)

    def test_full_turn_is_treated_as_zero_without_altering_points(self):
        point = (3.25, -8.5)
        rotated = rotation.rotate_point(point, math.tau)
        self.assertAlmostEqual(rotated[0], point[0], places=12)
        self.assertAlmostEqual(rotated[1], point[1], places=12)
        self.assertTrue(rotation.is_effectively_zero(math.tau))

    def test_x_and_y_mirrors_are_independent_around_origin(self):
        point = (2.0, 3.0)
        self.assertEqual(rotation.orient_point(point, 0.0, flip_x=True), (-2.0, 3.0))
        self.assertEqual(rotation.orient_point(point, 0.0, flip_y=True), (2.0, -3.0))
        self.assertEqual(
            rotation.orient_point(point, 0.0, flip_x=True, flip_y=True),
            (-2.0, -3.0),
        )

    def test_mirrors_are_applied_before_rotation(self):
        x, y = rotation.orient_point(
            (2.0, 3.0),
            math.radians(90.0),
            flip_x=True,
        )
        self.assertAlmostEqual(x, -3.0, places=12)
        self.assertAlmostEqual(y, -2.0, places=12)

    def test_mirrored_profile_keeps_selected_anchor_at_origin(self):
        contours = preview_geometry.tessellate_profile_contours_cm(
            self.ipe100.dxf_path,
            anchor_mm=self.ipe100.anchor_mm("TL"),
        )
        mirrored = rotation.orient_contours(
            contours,
            0.0,
            flip_x=True,
            flip_y=True,
        )
        xs = [point[0] for contour in mirrored for point in contour]
        ys = [point[1] for contour in mirrored for point in contour]
        self.assertAlmostEqual(min(xs), -5.5, places=9)
        self.assertAlmostEqual(max(xs), 0.0, places=9)
        self.assertAlmostEqual(min(ys), 0.0, places=9)
        self.assertAlmostEqual(max(ys), 10.0, places=9)

    def test_angle_is_formatted_for_component_traceability(self):
        self.assertEqual(rotation.format_degrees(math.radians(45.5)), "45.5")
        self.assertEqual(rotation.format_degrees(math.radians(-30.0)), "-30")
        self.assertEqual(rotation.format_degrees(0.0), "0")


if __name__ == "__main__":
    unittest.main()
