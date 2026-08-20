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

    def test_rigid_frames_are_right_handed_and_follow_both_physical_heights(self):
        placements = angle_cleat_geometry.build_double_angle_frames(
            primary_web_face_point=(0.0, 0.3, 0.0),
            secondary_profile_x_axis=(1.0, 0.0, 0.0),
            vertical_axis=(0.0, 0.0, 1.0),
            toward_secondary_axis=(0.0, 1.0, 0.0),
            secondary_web_face_offsets_cm=(-0.25, 0.25),
            cleat_height_cm=10.0,
            vertical_offset_cm=0.0,
        )
        left = angle_cleat_geometry.rigid_frame_for_placement(placements[0])
        right = angle_cleat_geometry.rigid_frame_for_placement(placements[1])
        self.assertEqual(left.origin, placements[0].frames[-1][0])
        self.assertEqual(left.z_axis, (0.0, 0.0, -1.0))
        self.assertEqual(right.origin, placements[1].frames[0][0])
        self.assertEqual(right.z_axis, (0.0, 0.0, 1.0))
        for frame in (left, right):
            self.assertEqual(
                angle_cleat_geometry.joint_geometry.cross(
                    frame.x_axis,
                    frame.y_axis,
                ),
                frame.z_axis,
            )

    def test_preview_hole_centers_map_to_each_local_angle_before_placement(self):
        placements = angle_cleat_geometry.build_double_angle_frames(
            primary_web_face_point=(0.0, 0.3, 0.0),
            secondary_profile_x_axis=(1.0, 0.0, 0.0),
            vertical_axis=(0.0, 0.0, 1.0),
            toward_secondary_axis=(0.0, 1.0, 0.0),
            secondary_web_face_offsets_cm=(-0.25, 0.25),
            cleat_height_cm=10.0,
            vertical_offset_cm=0.0,
        )
        pattern = angle_cleat_geometry.build_hole_pattern(
            10.0, 5.0, 5.0, 1.8, 2, 5.0, 3.0, 3.0
        )
        expected_z = ((7.5, 2.5), (2.5, 7.5))
        for placement, rows in zip(placements, expected_z):
            frame = angle_cleat_geometry.rigid_frame_for_placement(placement)
            primary, secondary = angle_cleat_geometry.hole_centers_for_placement(
                placement,
                pattern,
            )
            primary_local = tuple(
                angle_cleat_geometry.world_point_in_rigid_frame(frame, point)
                for point in primary
            )
            secondary_local = tuple(
                angle_cleat_geometry.world_point_in_rigid_frame(frame, point)
                for point in secondary
            )
            self.assertEqual(
                primary_local,
                ((3.0, 0.0, rows[0]), (3.0, 0.0, rows[1])),
            )
            self.assertEqual(
                secondary_local,
                ((0.0, 3.0, rows[0]), (0.0, 3.0, rows[1])),
            )

    def test_default_hole_pattern_is_centered_and_stays_inside_a_50_mm_angle(self):
        pattern = angle_cleat_geometry.build_hole_pattern(
            cleat_height_cm=10.0,
            angle_width_cm=5.0,
            angle_height_cm=5.0,
            diameter_cm=1.8,
            row_count=2,
            pitch_cm=5.0,
            primary_gauge_cm=3.0,
            secondary_gauge_cm=3.0,
        )
        self.assertEqual(pattern.row_positions_cm, (2.5, 7.5))
        self.assertEqual(pattern.row_count, 2)

    def test_hole_centers_are_aligned_through_both_angles_and_the_secondary_web(self):
        placements = angle_cleat_geometry.build_double_angle_frames(
            primary_web_face_point=(0.0, 0.3, 0.0),
            secondary_profile_x_axis=(1.0, 0.0, 0.0),
            vertical_axis=(0.0, 0.0, 1.0),
            toward_secondary_axis=(0.0, 1.0, 0.0),
            secondary_web_face_offsets_cm=(-0.25, 0.25),
            cleat_height_cm=10.0,
            vertical_offset_cm=0.0,
        )
        pattern = angle_cleat_geometry.build_hole_pattern(
            10.0, 5.0, 5.0, 1.8, 2, 5.0, 3.0, 3.0
        )
        left = angle_cleat_geometry.hole_centers_for_placement(
            placements[0], pattern
        )
        right = angle_cleat_geometry.hole_centers_for_placement(
            placements[1], pattern
        )
        self.assertEqual(left[1][0][1:], right[1][0][1:])
        self.assertEqual(left[1][1][1:], right[1][1][1:])
        self.assertEqual(left[0][0], (-3.25, 0.3, -2.5))
        self.assertEqual(right[0][0], (3.25, 0.3, -2.5))

    def test_invalid_hole_patterns_are_rejected_before_fusion_creation(self):
        with self.assertRaisesRegex(ValueError, "sort de la branche"):
            angle_cleat_geometry.build_hole_pattern(
                10.0, 5.0, 5.0, 1.8, 2, 5.0, 4.5, 3.0
            )
        with self.assertRaisesRegex(ValueError, "motif vertical"):
            angle_cleat_geometry.build_hole_pattern(
                6.0, 5.0, 5.0, 1.8, 2, 5.0, 3.0, 3.0
            )
        with self.assertRaisesRegex(ValueError, "âme secondaire"):
            angle_cleat_geometry.validate_hole_rows_in_web(
                (-3.0, 3.0),
                0.9,
                -3.73,
                3.73,
                "secondaire",
            )


if __name__ == "__main__":
    unittest.main()
