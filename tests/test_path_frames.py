import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDIN = ROOT / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ADDIN))

from lib import path_frames, rotation


class FakeVector:
    def __init__(self, x, y, z=0.0):
        self.values = (float(x), float(y), float(z))

    def dotProduct(self, other):
        return sum(a * b for a, b in zip(self.values, other.values))


class PathFrameTests(unittest.TestCase):
    def test_opposite_fusion_plane_axes_are_corrected_by_half_turn(self):
        target_x = FakeVector(1, 0)
        target_y = FakeVector(0, 1)
        plane_x = FakeVector(-1, 0)
        plane_y = FakeVector(0, -1)

        alignment = path_frames.basis_change_2d(
            plane_x,
            plane_y,
            target_x,
            target_y,
        )

        self.assertEqual(alignment, (-1.0, 0.0, 0.0, -1.0))
        self.assertEqual(
            rotation.multiply_matrices_2d(
                alignment,
                rotation.orientation_matrix_2d(0.0),
            ),
            (-1.0, 0.0, 0.0, -1.0),
        )

    def test_matching_plane_axes_require_no_correction(self):
        target_x = FakeVector(1, 0)
        target_y = FakeVector(0, 1)
        alignment = path_frames.basis_change_2d(
            target_x,
            target_y,
            target_x,
            target_y,
        )
        self.assertTrue(rotation.is_identity_matrix_2d(alignment))

    def test_user_orientation_is_applied_before_plane_alignment(self):
        alignment = (-1.0, 0.0, 0.0, -1.0)
        flip_both = rotation.orientation_matrix_2d(
            0.0,
            flip_x=True,
            flip_y=True,
        )
        self.assertTrue(
            rotation.is_identity_matrix_2d(
                rotation.multiply_matrices_2d(alignment, flip_both)
            )
        )

    def test_non_orthogonal_plane_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "axes du plan"):
            path_frames.basis_change_2d(
                FakeVector(1, 0),
                FakeVector(1, 0),
                FakeVector(1, 0),
                FakeVector(0, 1),
            )


if __name__ == "__main__":
    unittest.main()
