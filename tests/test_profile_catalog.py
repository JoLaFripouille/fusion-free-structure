import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDIN = ROOT / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ADDIN))

from lib import dxf_geometry, profile_catalog


class ProfileCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profiles = profile_catalog.discover_profiles(ADDIN)

    def test_catalog_contains_the_341_profiles_in_12_detected_families(self):
        expected = {
            "Corniere_Egale": 28,
            "Corniere_Inegale": 18,
            "HEA": 15,
            "HEB": 15,
            "IPE": 18,
            "IPN": 10,
            "Te_Egal": 11,
            "Tube_Carre": 65,
            "Tube_Rectangulaire": 92,
            "Tube_Rond": 41,
            "UPE": 14,
            "UPN": 14,
        }
        self.assertEqual(Counter(profile.family_id for profile in self.profiles), expected)
        self.assertEqual(
            Counter(profile.region_id for profile in self.profiles),
            {"Europe": 341},
        )
        self.assertEqual(
            Counter(profile.category_id for profile in self.profiles),
            {"Zones_geographiques": 341},
        )
        self.assertEqual(
            profile_catalog.region_options(self.profiles),
            (("Europe", "Europe"),),
        )
        self.assertEqual(
            profile_catalog.category_options(self.profiles),
            (("Zones_geographiques", "Zones géographiques"),),
        )
        self.assertEqual(len(profile_catalog.family_options(self.profiles)), 12)

    def test_default_selection_preserves_the_validated_ipe_100(self):
        profile = profile_catalog.default_profile(self.profiles)
        self.assertEqual(profile.category_id, "Zones_geographiques")
        self.assertEqual(profile.region_id, "Europe")
        self.assertEqual(profile.family_id, "IPE")
        self.assertEqual(profile.section_label, "100")
        self.assertEqual(profile.designation, "IPE 100")
        self.assertEqual(profile.width_mm, 55.0)
        self.assertEqual(profile.height_mm, 100.0)
        self.assertEqual(profile.center_mm, (0.0, 50.0))
        self.assertEqual(profile.import_offset_cm, (0.0, -5.0))
        self.assertEqual(
            profile.relative_path,
            "profiles/Zones_geographiques/Europe/IPE/IPE_100.dxf",
        )

    def test_legacy_profile_path_resolves_to_the_european_catalog(self):
        resolved = profile_catalog.resolve_profile_source(
            "profiles/IPE/IPE_100.dxf",
            ADDIN,
        )
        self.assertEqual(
            resolved,
            ROOT
            / "profiles"
            / "Zones_geographiques"
            / "Europe"
            / "IPE"
            / "IPE_100.dxf",
        )

    def test_additional_geographic_zones_are_discovered_without_code_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            profiles_root = Path(temp_dir) / "profiles" / "Zones_geographiques"
            for region_id, filename in (
                ("Europe", "IPE_100.dxf"),
                ("Amerique_du_Nord", "IPE_4.dxf"),
            ):
                path = profiles_root / region_id / "IPE" / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("DXF TEST", encoding="ascii")
            profiles = profile_catalog.discover_profiles(Path(temp_dir))
            self.assertEqual(
                profile_catalog.region_options(profiles, "Zones_geographiques"),
                (
                    ("Europe", "Europe"),
                    ("Amerique_du_Nord", "Amerique du Nord"),
                ),
            )
            self.assertEqual(
                len(profile_catalog.profiles_for_family(
                    profiles,
                    "IPE",
                    "Amerique_du_Nord",
                    "Zones_geographiques",
                )),
                1,
            )

    def test_sections_are_sorted_numerically_and_labels_are_unique(self):
        ipe_sections = [
            profile.section_label
            for profile in profile_catalog.profiles_for_family(
                self.profiles,
                "IPE",
                "Europe",
            )
        ]
        self.assertEqual(ipe_sections[:4], ["80", "100", "120", "140"])
        for family_id, _ in profile_catalog.family_options(self.profiles, "Europe"):
            labels = [
                profile.section_label
                for profile in profile_catalog.profiles_for_family(
                    self.profiles,
                    family_id,
                    "Europe",
                )
            ]
            self.assertEqual(len(labels), len(set(labels)), family_id)

    def test_meaningful_tube_labels_are_preserved(self):
        square = next(
            profile for profile in self.profiles
            if profile.dxf_path.name == "Tube_Carre_80x80_ep4.dxf"
        )
        round_profile = next(
            profile for profile in self.profiles
            if profile.dxf_path.name == "Tube_Rond_60.3_ep3.dxf"
        )
        self.assertEqual(square.section_label, "80 × 80 — ép. 4 mm")
        self.assertEqual(round_profile.section_label, "Ø 60.3 — ép. 3 mm")

    def test_every_profile_has_supported_geometry_and_closed_preview_contours(self):
        for profile in self.profiles:
            min_x, min_y, max_x, max_y = dxf_geometry.profile_bounds_mm(profile.dxf_path)
            self.assertGreater(max_x, min_x, profile.relative_path)
            self.assertGreater(max_y, min_y, profile.relative_path)
            contours = dxf_geometry.tessellate_profile_contours_mm(profile.dxf_path)
            self.assertTrue(contours, profile.relative_path)
            self.assertTrue(
                all(len(contour) >= 3 for contour in contours),
                profile.relative_path,
            )

    def test_hollow_profiles_keep_their_inner_contour_in_preview(self):
        for filename in (
            "Tube_Carre_80x80_ep4.dxf",
            "Tube_Rectangulaire_100x50_ep3.dxf",
            "Tube_Rond_60.3_ep3.dxf",
        ):
            profile = next(item for item in self.profiles if item.dxf_path.name == filename)
            contours = dxf_geometry.tessellate_profile_contours_mm(profile.dxf_path)
            self.assertEqual(len(contours), 2, profile.relative_path)


if __name__ == "__main__":
    unittest.main()
