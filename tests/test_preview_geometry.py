import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDIN = ROOT / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ADDIN))

from lib import preview_geometry


class PreviewGeometryTests(unittest.TestCase):
    def setUp(self):
        self.dxf_path = ROOT / "profiles" / "IPE" / "IPE_100.dxf"
        self.profile = preview_geometry.tessellate_profile_cm(self.dxf_path)

    def test_preview_reads_real_dxf_and_preserves_extents(self):
        self.assertGreater(len(self.profile), 16)
        xs = [point[0] for point in self.profile]
        ys = [point[1] for point in self.profile]
        self.assertAlmostEqual(min(xs), -2.75, places=9)
        self.assertAlmostEqual(max(xs), 2.75, places=9)
        self.assertAlmostEqual(min(ys), -5.0, places=9)
        self.assertAlmostEqual(max(ys), 5.0, places=9)

    def test_straight_preview_mesh_has_expected_size(self):
        frames = [
            ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
            ((20.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        ]
        coordinates, triangles = preview_geometry.build_swept_side_mesh(self.profile, frames)
        self.assertEqual(len(coordinates), len(self.profile) * len(frames) * 3)
        self.assertEqual(len(triangles), len(self.profile) * 6)
        self.assertEqual(min(coordinates[0::3]), 0.0)
        self.assertEqual(max(coordinates[0::3]), 20.0)

    def test_curved_preview_indices_are_valid(self):
        frames = [
            ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
            ((5.0, 5.0, 0.0), (-0.707, 0.707, 0.0), (0.0, 0.0, 1.0)),
            ((10.0, 5.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        ]
        coordinates, triangles = preview_geometry.build_swept_side_mesh(self.profile, frames)
        wire = preview_geometry.build_wire_indices(len(self.profile), len(frames))
        coordinate_count = len(coordinates) // 3
        self.assertTrue(triangles)
        self.assertTrue(wire)
        self.assertLess(max(triangles), coordinate_count)
        self.assertLess(max(wire), coordinate_count)


if __name__ == "__main__":
    unittest.main()
