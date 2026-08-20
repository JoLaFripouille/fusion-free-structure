from __future__ import annotations

import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
ADDIN = ROOT / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ADDIN))

from lib import angle_cleat_geometry


class AngleCleatGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.angle50 = (
            ROOT
            / "profiles"
            / "Zones_geographiques"
            / "Europe"
            / "Corniere_Egale"
            / "Corniere_Egale_50x50_ep5.dxf"
        )

    def test_exact_angle_contour_is_rebased_on_its_outer_corner(self):
        contours = angle_cleat_geometry.profile_contours_from_outer_corner_cm(
            self.angle50
        )
        self.assertEqual(len(contours), 1)
        contour = contours[0]
        self.assertGreater(len(contour), 20)
        self.assertAlmostEqual(min(point[0] for point in contour), 0.0)
        self.assertAlmostEqual(min(point[1] for point in contour), 0.0)
        self.assertAlmostEqual(max(point[0] for point in contour), 5.0)
        self.assertAlmostEqual(max(point[1] for point in contour), 5.0)

    def test_two_angles_are_symmetric_on_the_secondary_web_faces(self):
        placements = angle_cleat_geometry.build_double_angle_frames(
            primary_web_face_point=(0.0, 0.3, 0.0),
            secondary_profile_x_axis=(1.0, 0.0, 0.0),
            vertical_axis=(0.0, 0.0, 1.0),
            toward_secondary_axis=(0.0, 1.0, 0.0),
            secondary_web_face_offsets_cm=(-0.25, 0.25),
            cleat_height_cm=10.0,
            vertical_offset_cm=1.0,
        )
        self.assertEqual(tuple(item.side for item in placements), ("gauche", "droite"))
        left, right = placements
        self.assertEqual(left.frames[0][0], (-0.25, 0.3, -4.0))
        self.assertEqual(left.frames[1][0], (-0.25, 0.3, 6.0))
        self.assertEqual(right.frames[0][0], (0.25, 0.3, -4.0))
        self.assertEqual(right.frames[1][0], (0.25, 0.3, 6.0))
        self.assertEqual(left.frames[0][1], (-1.0, 0.0, 0.0))
        self.assertEqual(right.frames[0][1], (1.0, 0.0, 0.0))
        self.assertEqual(left.frames[0][2], (0.0, 1.0, 0.0))
        self.assertEqual(right.frames[0][2], (0.0, 1.0, 0.0))

    def test_first_phase_rejects_an_oblique_connection(self):
        with self.assertRaisesRegex(ValueError, "uniquement deux axes à 90"):
            angle_cleat_geometry.build_double_angle_frames(
                primary_web_face_point=(0.0, 0.0, 0.0),
                secondary_profile_x_axis=(1.0, 0.0, 0.0),
                vertical_axis=(0.0, 0.0, 1.0),
                toward_secondary_axis=(0.0, 1.0, 0.0),
                secondary_web_face_offsets_cm=(-0.25, 0.25),
                cleat_height_cm=10.0,
                vertical_offset_cm=0.0,
                angle_degrees=60.0,
            )

    def test_invalid_section_axes_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "âme secondaire"):
            angle_cleat_geometry.build_double_angle_frames(
                primary_web_face_point=(0.0, 0.0, 0.0),
                secondary_profile_x_axis=(0.0, 1.0, 0.0),
                vertical_axis=(0.0, 0.0, 1.0),
                toward_secondary_axis=(0.0, 1.0, 0.0),
                secondary_web_face_offsets_cm=(-0.25, 0.25),
                cleat_height_cm=10.0,
                vertical_offset_cm=0.0,
            )

    def test_height_must_be_positive(self):
        with self.assertRaisesRegex(ValueError, "strictement positive"):
            angle_cleat_geometry.build_double_angle_frames(
                primary_web_face_point=(0.0, 0.0, 0.0),
                secondary_profile_x_axis=(1.0, 0.0, 0.0),
                vertical_axis=(0.0, 0.0, 1.0),
                toward_secondary_axis=(0.0, 1.0, 0.0),
                secondary_web_face_offsets_cm=(-0.25, 0.25),
                cleat_height_cm=0.0,
                vertical_offset_cm=0.0,
            )


if __name__ == "__main__":
    unittest.main()
