import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDIN = ROOT / "addin" / "JHR_StructuralMembers_V1"
SOURCE_DXF = (
    ROOT
    / "profiles"
    / "Zones_geographiques"
    / "Europe"
    / "IPE"
    / "IPE_100.dxf"
)
sys.path.insert(0, str(ADDIN))

from lib import custom_profiles, profile_catalog


class CustomProfileTests(unittest.TestCase):
    def test_validated_dxf_reports_exact_geometry_without_modifying_source(self):
        original = SOURCE_DXF.read_bytes()
        analysis = custom_profiles.validate_dxf(SOURCE_DXF)
        self.assertEqual(analysis.width_mm, 55.0)
        self.assertEqual(analysis.height_mm, 100.0)
        self.assertEqual(analysis.contour_count, 1)
        self.assertGreater(analysis.entity_count, 0)
        self.assertEqual(SOURCE_DXF.read_bytes(), original)

    def test_import_is_byte_identical_and_joins_the_custom_catalog(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            imported = custom_profiles.import_profile(
                SOURCE_DXF,
                "Mes poutres",
                "IPE spécial 100",
                temp_dir,
            )
            self.assertEqual(imported.record.dxf_path.read_bytes(), SOURCE_DXF.read_bytes())
            self.assertEqual(
                imported.record.relative_path,
                "profiles/Personnalises/Mes_poutres/IPE_special_100.dxf",
            )
            metadata = json.loads(
                imported.record.metadata_path.read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["units"], "mm")
            self.assertEqual(metadata["family_label"], "Mes poutres")
            self.assertEqual(metadata["section_label"], "IPE spécial 100")

            profiles = profile_catalog.discover_profiles(
                ADDIN,
                custom_data_root=temp_dir,
            )
            self.assertEqual(len(profiles), 342)
            self.assertEqual(
                profile_catalog.category_options(profiles),
                (
                    ("Zones_geographiques", "Zones géographiques"),
                    ("Personnalises", "Personnalisés"),
                ),
            )
            custom = next(
                profile
                for profile in profiles
                if profile.category_id == custom_profiles.CATEGORY_ID
            )
            self.assertEqual(custom.region_id, custom_profiles.REGION_ID)
            self.assertEqual(custom.family_label, "Mes poutres")
            self.assertEqual(custom.section_label, "IPE spécial 100")
            self.assertEqual(
                profile_catalog.resolve_profile_source(
                    custom.relative_path,
                    ADDIN,
                    custom_data_root=temp_dir,
                ),
                custom.dxf_path,
            )

    def test_duplicate_name_is_rejected_without_overwriting_first_profile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first = custom_profiles.import_profile(
                SOURCE_DXF,
                "Essais",
                "Profil 1",
                temp_dir,
            )
            original = first.record.dxf_path.read_bytes()
            with self.assertRaises(FileExistsError):
                custom_profiles.import_profile(
                    SOURCE_DXF,
                    "Essais",
                    "Profil 1",
                    temp_dir,
                )
            self.assertEqual(first.record.dxf_path.read_bytes(), original)

    def test_newer_dxf_version_is_rejected_before_import(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "profil_ac1027.dxf"
            source.write_text(
                SOURCE_DXF.read_text(encoding="ascii").replace("AC1009", "AC1027", 1),
                encoding="ascii",
            )
            with self.assertRaisesRegex(ValueError, "R12"):
                custom_profiles.validate_dxf(source)

    def test_delete_moves_both_files_to_recoverable_trash(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            imported = custom_profiles.import_profile(
                SOURCE_DXF,
                "Essais",
                "À supprimer",
                temp_dir,
            )
            deleted = custom_profiles.delete_profile(
                imported.record.relative_path,
                active_reference_count=2,
                data_root=temp_dir,
            )
            self.assertFalse(imported.record.dxf_path.exists())
            self.assertFalse(imported.record.metadata_path.exists())
            self.assertEqual(custom_profiles.discover_records(temp_dir), ())
            self.assertEqual(
                (deleted.trash_directory / imported.record.dxf_path.name).read_bytes(),
                SOURCE_DXF.read_bytes(),
            )
            deletion = json.loads(
                (deleted.trash_directory / "suppression.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(deletion["active_reference_count"], 2)
            self.assertEqual(
                deletion["original_relative_path"],
                imported.record.relative_path,
            )

    def test_geographic_profile_cannot_be_deleted_by_custom_manager(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError):
                custom_profiles.delete_profile(
                    "profiles/Zones_geographiques/Europe/IPE/IPE_100.dxf",
                    data_root=temp_dir,
                )


if __name__ == "__main__":
    unittest.main()
