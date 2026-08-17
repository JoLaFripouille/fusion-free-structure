import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDIN = ROOT / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ADDIN))

from lib import member_metadata


class MemberMetadataTests(unittest.TestCase):
    def setUp(self):
        self.values = {
            "profile": "Cornière inégale 100 × 50 — ép. 8 mm",
            "profile_family": "Corniere_Inegale",
            "profile_source": "profiles/Corniere_Inegale/Corniere_Inegale_100x50_ep8.dxf",
            "material_name": "Steel, Mild",
            "material_id": "fusion-material-id",
            "material_library_name": "Fusion Material Library",
            "material_library_id": "fusion-library-id",
            "material_source_id": "fusion-material-id",
            "material_property_count": "8",
            "anchor": "TL",
            "rotation_deg": "45",
            "flip_x": "true",
            "flip_y": "false",
            "source_curve_token": "token-fusion",
            "source_curve_type": "line",
            "extension_version": "1.8.0",
        }

    def test_current_member_attributes_are_parsed_exactly(self):
        metadata = member_metadata.parse_member_attributes(self.values)
        self.assertEqual(metadata.profile_family, "Corniere_Inegale")
        self.assertEqual(metadata.anchor, "TL")
        self.assertEqual(metadata.material_name, "Steel, Mild")
        self.assertEqual(metadata.material_id, "fusion-material-id")
        self.assertEqual(metadata.material_property_count, 8)
        self.assertTrue(metadata.has_physical_material_metadata)
        self.assertEqual(metadata.rotation_deg, 45.0)
        self.assertTrue(metadata.flip_x)
        self.assertFalse(metadata.flip_y)
        self.assertEqual(metadata.source_curve_token, "token-fusion")

    def test_older_line_token_and_orientation_defaults_are_supported(self):
        del self.values["source_curve_token"]
        del self.values["rotation_deg"]
        del self.values["flip_x"]
        del self.values["flip_y"]
        for key in (
            "material_name",
            "material_id",
            "material_library_name",
            "material_library_id",
            "material_source_id",
            "material_property_count",
        ):
            del self.values[key]
        self.values["source_line_token"] = "ancien-token"
        metadata = member_metadata.parse_member_attributes(self.values)
        self.assertEqual(metadata.source_curve_token, "ancien-token")
        self.assertEqual(metadata.rotation_deg, 0.0)
        self.assertFalse(metadata.flip_x)
        self.assertFalse(metadata.flip_y)
        self.assertEqual(metadata.material_name, "Non renseigné")
        self.assertFalse(metadata.has_physical_material_metadata)

    def test_legacy_free_text_grade_is_preserved_without_claiming_assignment(self):
        for key in (
            "material_name",
            "material_id",
            "material_library_name",
            "material_library_id",
            "material_source_id",
            "material_property_count",
        ):
            del self.values[key]
        self.values["steel_grade"] = "S235JR"
        metadata = member_metadata.parse_member_attributes(self.values)
        self.assertEqual(metadata.material_name, "S235JR")
        self.assertEqual(metadata.steel_grade, "S235JR")
        self.assertFalse(metadata.has_physical_material_metadata)

    def test_partial_physical_material_metadata_is_rejected(self):
        del self.values["material_library_id"]
        with self.assertRaisesRegex(ValueError, "identifiant de la bibliothèque"):
            member_metadata.parse_member_attributes(self.values)

    def test_unknown_anchor_is_rejected(self):
        self.values["anchor"] = "INCONNU"
        with self.assertRaisesRegex(ValueError, "Point d'ancrage inconnu"):
            member_metadata.parse_member_attributes(self.values)

    def test_invalid_boolean_is_rejected(self):
        self.values["flip_x"] = "peut-être"
        with self.assertRaisesRegex(ValueError, "Valeur booléenne invalide"):
            member_metadata.parse_member_attributes(self.values)

    def test_absolute_or_parent_profile_path_is_rejected(self):
        for source in ("C:/bibliotheque/profil.dxf", "profiles/../secret.dxf"):
            with self.subTest(source=source):
                self.values["profile_source"] = source
                with self.assertRaisesRegex(ValueError, "n'est pas relatif"):
                    member_metadata.parse_member_attributes(self.values)


if __name__ == "__main__":
    unittest.main()
