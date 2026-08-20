from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDIN = ROOT / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ADDIN))

from lib import cope_geometry, profile_catalog


class CopeGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profiles = profile_catalog.discover_profiles(include_custom=False)
        cls.ipe100 = next(
            profile
            for profile in profiles
            if profile.family_id == "IPE" and profile.section_label == "100"
        )
        cls.geometry = cope_geometry.analyze_i_profile_dxf(cls.ipe100.dxf_path)

    def test_ipe100_flange_and_web_limits_come_from_the_original_dxf(self):
        self.assertEqual(self.geometry.bounds_mm, (-27.5, 0.0, 27.5, 100.0))
        self.assertAlmostEqual(self.geometry.web_min_y_mm, 12.7)
        self.assertAlmostEqual(self.geometry.web_max_y_mm, 87.3)
        self.assertAlmostEqual(self.geometry.web_min_x_mm, -2.05)
        self.assertAlmostEqual(self.geometry.web_max_x_mm, 2.05)
        self.assertAlmostEqual(self.geometry.bottom_cope_height_mm, 12.7)
        self.assertAlmostEqual(self.geometry.top_cope_height_mm, 12.7)

    def test_every_bundled_i_h_profile_has_a_detectable_double_cope_geometry(self):
        profiles = profile_catalog.discover_profiles(include_custom=False)
        i_h_profiles = [
            profile
            for profile in profiles
            if profile.family_id in ("IPE", "HEA", "HEB")
        ]
        self.assertEqual(len(i_h_profiles), 48)
        for profile in i_h_profiles:
            geometry = cope_geometry.analyze_i_profile_dxf(profile.dxf_path)
            self.assertGreater(geometry.width_mm, 0.0, profile.section_label)
            self.assertGreater(geometry.bottom_cope_height_mm, 0.0, profile.section_label)
            self.assertGreater(geometry.top_cope_height_mm, 0.0, profile.section_label)

    def test_every_primary_i_h_profile_has_a_detectable_web(self):
        profiles = profile_catalog.discover_profiles(include_custom=False)
        primary_profiles = [
            profile
            for profile in profiles
            if profile.family_id in ("IPE", "HEA", "HEB")
        ]
        self.assertEqual(len(primary_profiles), 48)
        for profile in primary_profiles:
            geometry = cope_geometry.analyze_i_profile_dxf(profile.dxf_path)
            self.assertLess(geometry.web_min_x_mm, geometry.web_max_x_mm)
            self.assertGreater(geometry.web_min_y_mm, geometry.min_y_mm)
            self.assertLess(geometry.web_max_y_mm, geometry.max_y_mm)

    def test_double_cope_uses_anchor_depth_and_vertical_clearance(self):
        volumes = cope_geometry.double_cope_volumes(
            self.geometry,
            self.ipe100.anchor_mm("C"),
            depth_cm=3.0,
            vertical_clearance_cm=0.1,
        )
        self.assertEqual(len(volumes), 2)
        bottom, top = volumes
        self.assertEqual(bottom.name, "Grugeage inférieur")
        self.assertEqual(top.name, "Grugeage supérieur")
        self.assertAlmostEqual(bottom.axial_min_cm, -3.0)
        self.assertAlmostEqual(bottom.y_max_cm, -3.63)
        self.assertAlmostEqual(top.y_min_cm, 3.63)
        self.assertLess(bottom.y_max_cm, top.y_min_cm)

    def test_red_preview_box_mesh_is_closed_and_has_eight_vertices(self):
        volume = cope_geometry.double_cope_volumes(
            self.geometry,
            self.ipe100.anchor_mm("C"),
            depth_cm=3.0,
            vertical_clearance_cm=0.1,
        )[0]
        coordinates, triangles, wires = cope_geometry.volume_mesh(
            volume,
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
        )
        self.assertEqual(len(coordinates), 24)
        self.assertEqual(len(triangles), 36)
        self.assertEqual(len(wires), 24)

    def test_orange_web_cut_plane_covers_the_secondary_section(self):
        coordinates, triangles, wires = cope_geometry.section_plane_mesh(
            self.geometry,
            self.ipe100.anchor_mm("C"),
            origin=(0.0, 0.0, 2.0),
            x_axis=(1.0, 0.0, 0.0),
            y_axis=(0.0, 1.0, 0.0),
        )
        points = tuple(zip(coordinates[0::3], coordinates[1::3], coordinates[2::3]))
        self.assertEqual(len(points), 4)
        self.assertAlmostEqual(min(point[0] for point in points), -3.25)
        self.assertAlmostEqual(max(point[0] for point in points), 3.25)
        self.assertAlmostEqual(min(point[1] for point in points), -5.5)
        self.assertAlmostEqual(max(point[1] for point in points), 5.5)
        self.assertTrue(all(point[2] == 2.0 for point in points))
        self.assertEqual(len(triangles), 6)
        self.assertEqual(len(wires), 8)

    def test_depth_uses_the_facing_support_not_the_primary_length(self):
        primary_points = (
            (-100.0, -2.0, -4.0),
            (100.0, -2.0, -4.0),
            (-100.0, 2.0, 4.0),
            (100.0, 2.0, 4.0),
        )
        depth = cope_geometry.depth_to_facing_support(
            joint_point=(0.0, 0.0, 0.0),
            approach_direction=(0.0, 1.0, 0.0),
            plane_normal=(0.0, -1.0, 0.0),
            primary_body_points=primary_points,
        )
        self.assertAlmostEqual(depth, 2.0)

    def test_oblique_depth_covers_the_full_secondary_section(self):
        approach = (0.5, math.sqrt(3.0) / 2.0, 0.0)
        cut_normal = (0.0, -1.0, 0.0)
        profile_x = (-math.sqrt(3.0) / 2.0, 0.5, 0.0)
        section_points = tuple(
            tuple(value * side for value in profile_x)
            for side in (-1.0, 1.0)
        )
        depth = cope_geometry.depth_to_facing_support(
            joint_point=(0.0, 0.0, 0.0),
            approach_direction=approach,
            plane_normal=cut_normal,
            primary_body_points=((-1.0, -2.0, -1.0), (1.0, -2.0, 1.0)),
            secondary_section_points=section_points,
        )
        self.assertAlmostEqual(depth, 2.886751345948128)

    def test_oblique_red_volume_ends_exactly_on_the_web_plane(self):
        approach = (0.5, math.sqrt(3.0) / 2.0, 0.0)
        profile_x = (-math.sqrt(3.0) / 2.0, 0.5, 0.0)
        depth = 2.886751345948128
        start = tuple(-value * depth for value in approach)
        volume = cope_geometry.CopeVolume(
            "Essai oblique",
            -1.0,
            1.0,
            -0.5,
            0.5,
            -depth,
            0.05,
        )
        coordinates, triangles, wires = cope_geometry.clipped_volume_mesh(
            volume,
            start,
            profile_x,
            (0.0, 0.0, 1.0),
            approach,
            (0.0, -0.2, 0.0),
            (0.0, -1.0, 0.0),
        )
        points = tuple(zip(coordinates[0::3], coordinates[1::3], coordinates[2::3]))
        self.assertEqual(len(points), 8)
        self.assertTrue(all(abs(point[1] + 0.2) < 1e-9 for point in points[4:]))
        self.assertEqual(len(triangles), 36)
        self.assertEqual(len(wires), 24)

    def test_oblique_projection_is_valid_at_30_45_and_60_degrees(self):
        cut_normal = (0.0, -1.0, 0.0)
        cut_point = (0.0, -0.2, 0.0)
        primary_points = ((-1.0, -2.0, -1.0), (1.0, -2.0, 1.0))
        for angle_degrees in (30.0, 45.0, 60.0):
            angle = math.radians(angle_degrees)
            approach = (math.cos(angle), math.sin(angle), 0.0)
            profile_x = (-math.sin(angle), math.cos(angle), 0.0)
            section_points = tuple(
                tuple(value * side for value in profile_x)
                for side in (-1.0, 1.0)
            )
            depth = cope_geometry.depth_to_facing_support(
                (0.0, 0.0, 0.0),
                approach,
                cut_normal,
                primary_points,
                section_points,
            )
            start = tuple(-value * depth for value in approach)
            volume = cope_geometry.CopeVolume(
                "Essai {} degrés".format(angle_degrees),
                -1.0,
                1.0,
                -0.5,
                0.5,
                -depth,
                0.05,
            )
            coordinates, _, _ = cope_geometry.clipped_volume_mesh(
                volume,
                start,
                profile_x,
                (0.0, 0.0, 1.0),
                approach,
                cut_point,
                cut_normal,
            )
            points = tuple(
                zip(coordinates[0::3], coordinates[1::3], coordinates[2::3])
            )
            self.assertTrue(
                all(abs(point[1] + 0.2) < 1e-9 for point in points[4:]),
                angle_degrees,
            )

    def test_web_cut_uses_the_face_toward_the_secondary_and_the_gap(self):
        positive = cope_geometry.web_face_cut_point(
            self.geometry,
            self.ipe100.anchor_mm("C"),
            joint_point=(0.0, 0.0, 0.0),
            profile_x_axis=(1.0, 0.0, 0.0),
            toward_secondary=(1.0, 0.0, 0.0),
            web_clearance_cm=0.1,
        )
        negative = cope_geometry.web_face_cut_point(
            self.geometry,
            self.ipe100.anchor_mm("C"),
            joint_point=(0.0, 0.0, 0.0),
            profile_x_axis=(1.0, 0.0, 0.0),
            toward_secondary=(-1.0, 0.0, 0.0),
            web_clearance_cm=0.1,
        )
        self.assertAlmostEqual(positive[0], 0.305)
        self.assertAlmostEqual(negative[0], -0.305)

    def test_web_cut_refuses_a_primary_rotated_away_from_the_secondary(self):
        with self.assertRaisesRegex(ValueError, "orientée face"):
            cope_geometry.web_face_cut_point(
                self.geometry,
                self.ipe100.anchor_mm("C"),
                joint_point=(0.0, 0.0, 0.0),
                profile_x_axis=(0.0, 1.0, 0.0),
                toward_secondary=(1.0, 0.0, 0.0),
                web_clearance_cm=0.1,
            )


if __name__ == "__main__":
    unittest.main()
