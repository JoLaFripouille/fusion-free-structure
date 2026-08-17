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

    def test_support_point_and_positive_gap_move_cut_away_from_main(self):
        points = ((-2.0, -3.0, 0.0), (2.0, -3.0, 0.0), (2.0, 3.0, 0.0))
        index = joint_geometry.support_point_index(points, (0.0, 1.0, 0.0))
        self.assertIn(index, (0, 1))
        cut = joint_geometry.cut_point_from_support(
            points[index],
            (0.0, 1.0, 0.0),
            0.2,
        )
        self.assertAlmostEqual(cut[1], -3.2)

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
