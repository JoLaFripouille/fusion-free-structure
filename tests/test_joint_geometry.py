import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDIN = ROOT / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ADDIN))

from lib import joint_geometry


class JointGeometryTests(unittest.TestCase):
    def test_perpendicular_secondary_endpoint_is_recognized(self):
        result = joint_geometry.analyze_straight_joint(
            (-10.0, 0.0, 0.0),
            (10.0, 0.0, 0.0),
            (0.0, -8.0, 0.0),
            (0.0, 0.0, 0.0),
        )
        self.assertEqual(result.secondary_joint_endpoint_index, 1)
        self.assertEqual(result.approach_direction, (0.0, 1.0, 0.0))
        self.assertAlmostEqual(result.angle_degrees, 90.0)
        self.assertAlmostEqual(result.main_parameter, 0.5)

    def test_small_endpoint_gap_within_one_millimeter_is_accepted(self):
        result = joint_geometry.analyze_straight_joint(
            (-10.0, 0.0, 0.0),
            (10.0, 0.0, 0.0),
            (0.0, -8.0, 0.0),
            (0.0, -0.05, 0.0),
        )
        self.assertAlmostEqual(result.endpoint_distance_cm, 0.05)

    def test_curved_secondary_uses_its_endpoint_tangent_not_its_chord(self):
        result = joint_geometry.endpoint_joint_geometry(
            main_point=(0.0, 0.0, 0.0),
            main_parameter=0.5,
            joint_endpoint=(0.0, 0.0, 0.0),
            inner_endpoint=(-5.0, -5.0, 0.0),
            endpoint_index=1,
            approach_direction=(0.0, 1.0, 0.0),
            main_direction=(1.0, 0.0, 0.0),
            endpoint_distance_cm=0.0,
        )
        self.assertEqual(result.approach_direction, (0.0, 1.0, 0.0))
        self.assertAlmostEqual(result.angle_degrees, 90.0)

    def test_disconnected_or_parallel_members_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "extrémité"):
            joint_geometry.analyze_straight_joint(
                (-10.0, 0.0, 0.0),
                (10.0, 0.0, 0.0),
                (0.0, -8.0, 0.0),
                (0.0, -2.0, 0.0),
            )
        with self.assertRaisesRegex(ValueError, "parallèles"):
            joint_geometry.analyze_straight_joint(
                (-10.0, 0.0, 0.0),
                (10.0, 0.0, 0.0),
                (-5.0, 0.0, 0.0),
                (0.0, 0.0, 0.0),
            )
        result = joint_geometry.analyze_straight_joint(
            (-10.0, 0.0, 0.0),
            (10.0, 0.0, 0.0),
            (-5.0, -8.660254, 0.0),
            (0.0, 0.0, 0.0),
        )
        self.assertAlmostEqual(result.angle_degrees, 60.0, places=5)
        self.assertAlmostEqual(result.plane_normal[0], 0.0)
        self.assertAlmostEqual(result.plane_normal[1], -1.0)

    def test_support_point_and_positive_gap_follow_the_resolved_plane_normal(self):
        points = ((-2.0, -3.0, 0.0), (2.0, -3.0, 0.0), (2.0, 3.0, 0.0))
        index = joint_geometry.support_point_index(points, (0.0, -1.0, 0.0))
        self.assertIn(index, (0, 1))
        cut = joint_geometry.cut_point_from_support(
            points[index],
            (0.0, -1.0, 0.0),
            0.2,
        )
        self.assertAlmostEqual(cut[1], -3.2)

    def test_preview_point_matches_the_intersection_of_the_two_normal_planes(self):
        point = joint_geometry.normal_plane_intersection_point(
            (1.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 2.0, 0.0),
            (0.0, 1.0, 0.0),
        )
        self.assertAlmostEqual(point[0], 1.0)
        self.assertAlmostEqual(point[1], 2.0)
        self.assertAlmostEqual(point[2], 0.0)

    def test_body_relation_distinguishes_overlap_gap_alignment_and_wrong_side(self):
        plane_point = (0.0, 0.0, 0.0)
        normal = (1.0, 0.0, 0.0)
        interior = (10.0, 0.0, 0.0)
        cases = (
            (((-1.0, 0.0, 0.0), (2.0, 0.0, 0.0)), "overlap"),
            (((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)), "aligned"),
            (((1.0, 0.0, 0.0), (2.0, 0.0, 0.0)), "gap"),
            (((-2.0, 0.0, 0.0), (-1.0, 0.0, 0.0)), "outside"),
        )
        for points, expected in cases:
            relation, sign, _, _ = joint_geometry.body_plane_relation(
                points,
                plane_point,
                normal,
                interior,
            )
            self.assertEqual(relation, expected)
            self.assertEqual(sign, 1.0)

    def test_extension_crosses_the_plane_for_an_initial_gap(self):
        distance = joint_geometry.extension_distance_to_plane(
            ((1.0, -1.0, 0.0), (2.0, 1.0, 0.0)),
            (-1.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            1.0,
        )
        self.assertAlmostEqual(distance, 2.05)

    def test_partial_overlap_extends_the_whole_end_face_before_miter(self):
        distance = joint_geometry.extension_distance_to_plane(
            ((-1.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
            (-1.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            1.0,
        )
        self.assertAlmostEqual(distance, 2.05)

    def test_end_face_already_beyond_the_plane_needs_no_extension(self):
        distance = joint_geometry.extension_distance_to_plane(
            ((-2.0, 0.0, 0.0), (-1.0, 0.0, 0.0)),
            (-1.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            1.0,
        )
        self.assertEqual(distance, 0.0)

    def test_miter_uses_the_common_angle_bisector(self):
        result = joint_geometry.analyze_miter_joint(
            (-10.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            (0.0, -10.0, 0.0),
            (0.0, 0.0, 0.0),
        )
        expected = 1.0 / math.sqrt(2.0)
        self.assertEqual(result.primary_joint_endpoint_index, 1)
        self.assertEqual(result.secondary_joint_endpoint_index, 1)
        self.assertAlmostEqual(result.angle_degrees, 90.0)
        self.assertAlmostEqual(result.plane_normal[0], expected)
        self.assertAlmostEqual(result.plane_normal[1], -expected)
        primary_inner_side = joint_geometry.dot(
            joint_geometry.subtract(result.primary_inner_endpoint, result.joint_point),
            result.plane_normal,
        )
        secondary_inner_side = joint_geometry.dot(
            joint_geometry.subtract(result.secondary_inner_endpoint, result.joint_point),
            result.plane_normal,
        )
        self.assertLess(primary_inner_side, 0.0)
        self.assertGreater(secondary_inner_side, 0.0)

    def test_miter_is_independent_of_line_endpoint_order(self):
        result = joint_geometry.analyze_miter_joint(
            (0.0, 0.0, 0.0),
            (-10.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            (4.0, 8.0, 0.0),
        )
        self.assertEqual(result.primary_joint_endpoint_index, 0)
        self.assertEqual(result.secondary_joint_endpoint_index, 0)
        self.assertAlmostEqual(result.endpoint_distance_cm, 0.0)
        self.assertGreater(result.angle_degrees, 5.0)

    def test_miter_rejects_disconnected_and_aligned_members(self):
        with self.assertRaisesRegex(ValueError, "extrémités"):
            joint_geometry.analyze_miter_joint(
                (-10.0, 0.0, 0.0),
                (0.0, 0.0, 0.0),
                (1.0, 0.0, 0.0),
                (1.0, 10.0, 0.0),
            )
        with self.assertRaisesRegex(ValueError, "alignées"):
            joint_geometry.analyze_miter_joint(
                (-10.0, 0.0, 0.0),
                (0.0, 0.0, 0.0),
                (0.0, 0.0, 0.0),
                (10.0, 0.0, 0.0),
            )

    def test_plane_square_is_perpendicular_and_centered(self):
        center = (2.0, 3.0, 4.0)
        normal = joint_geometry.normalize((1.0, 2.0, 3.0))
        points = joint_geometry.plane_square(center, normal, 5.0)
        self.assertEqual(len(points), 4)
        for point in points:
            self.assertAlmostEqual(
                joint_geometry.dot(joint_geometry.subtract(point, center), normal),
                0.0,
                places=12,
            )
            self.assertAlmostEqual(
                joint_geometry.length(joint_geometry.subtract(point, center)),
                math.sqrt(50.0),
                places=12,
            )


if __name__ == "__main__":
    unittest.main()
