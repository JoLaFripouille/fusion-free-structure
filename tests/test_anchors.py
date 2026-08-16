import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDIN = ROOT / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ADDIN))

from lib import anchors, preview_geometry, profile_catalog


class AnchorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profiles = profile_catalog.discover_profiles(ADDIN)
        cls.ipe100 = next(
            profile for profile in cls.profiles
            if profile.dxf_path.name == "IPE_100.dxf"
        )

    def test_nine_unique_positions_fill_the_three_by_three_grid(self):
        self.assertEqual(len(anchors.ANCHOR_DEFINITIONS), 9)
        self.assertEqual(
            {(anchor.row, anchor.column) for anchor in anchors.ANCHOR_DEFINITIONS},
            {(row, column) for row in range(3) for column in range(3)},
        )
        self.assertEqual(
            {anchor.code for anchor in anchors.ANCHOR_DEFINITIONS},
            {"TL", "TC", "TR", "ML", "C", "MR", "BL", "BC", "BR"},
        )

    def test_ipe_100_anchor_coordinates_are_exact(self):
        expected = {
            "TL": (-27.5, 100.0),
            "TC": (0.0, 100.0),
            "TR": (27.5, 100.0),
            "ML": (-27.5, 50.0),
            "C": (0.0, 50.0),
            "MR": (27.5, 50.0),
            "BL": (-27.5, 0.0),
            "BC": (0.0, 0.0),
            "BR": (27.5, 0.0),
        }
        for anchor_code, point in expected.items():
            self.assertEqual(self.ipe100.anchor_mm(anchor_code), point)

    def test_import_offsets_put_the_selected_anchor_at_the_origin(self):
        self.assertEqual(self.ipe100.import_offset_cm_for_anchor("C"), (0.0, -5.0))
        self.assertEqual(self.ipe100.import_offset_cm_for_anchor("TL"), (2.75, -10.0))
        self.assertEqual(self.ipe100.import_offset_cm_for_anchor("BR"), (-2.75, 0.0))

    def test_preview_is_translated_around_the_selected_anchor(self):
        contours = preview_geometry.tessellate_profile_contours_cm(
            self.ipe100.dxf_path,
            anchor_mm=self.ipe100.anchor_mm("TL"),
        )
        xs = [point[0] for contour in contours for point in contour]
        ys = [point[1] for contour in contours for point in contour]
        self.assertAlmostEqual(min(xs), 0.0, places=9)
        self.assertAlmostEqual(max(xs), 5.5, places=9)
        self.assertAlmostEqual(min(ys), -10.0, places=9)
        self.assertAlmostEqual(max(ys), 0.0, places=9)

    def test_all_profiles_support_all_nine_anchor_positions(self):
        for profile in self.profiles:
            min_x, min_y, max_x, max_y = profile.bounds_mm
            for anchor in anchors.ANCHOR_DEFINITIONS:
                x, y = profile.anchor_mm(anchor.code)
                self.assertGreaterEqual(x, min_x, profile.relative_path)
                self.assertLessEqual(x, max_x, profile.relative_path)
                self.assertGreaterEqual(y, min_y, profile.relative_path)
                self.assertLessEqual(y, max_y, profile.relative_path)

    def test_unknown_anchor_is_rejected_explicitly(self):
        with self.assertRaisesRegex(ValueError, "Point d'ancrage inconnu"):
            self.ipe100.anchor_mm("INCONNU")


if __name__ == "__main__":
    unittest.main()
