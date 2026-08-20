import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDIN = ROOT / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ADDIN))

from lib import default_settings


class DefaultSettingsTests(unittest.TestCase):
    def test_factory_values_preserve_current_command_defaults(self):
        values = default_settings.factory_defaults()
        self.assertEqual(values.straight_joint_gap_mm("IPE"), 0.0)
        self.assertEqual(values.straight_joint_gap_mm("Corniere_Egale"), 0.0)
        self.assertEqual(values.straight_joint_gap_mm("Tube_Carre"), 0.0)
        self.assertEqual(values.straight_joint_gap_mm("Profil_Perso"), 0.0)
        self.assertEqual(values.cope_ih_vertical_mm, 1.0)
        self.assertEqual(values.cope_lt_under_web_mm, 1.0)
        self.assertEqual(values.cope_lt_root_relief_mm, 1.0)

    def test_profile_families_are_grouped_for_straight_joint_defaults(self):
        self.assertEqual(default_settings.profile_group("HEB"), "ih")
        self.assertEqual(default_settings.profile_group("Te_Egal"), "lt")
        self.assertEqual(default_settings.profile_group("Tube_Rond"), "hollow")
        self.assertEqual(default_settings.profile_group("UPN"), "other")

    def test_settings_round_trip_in_the_local_data_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            values = replace(
                default_settings.factory_defaults(),
                straight_joint_hollow_gap_mm=2.5,
                cope_lt_under_web_mm=1.75,
                cope_lt_root_relief_mm=0.5,
            )
            path = default_settings.save(values, temp_dir)
            self.assertEqual(path, Path(temp_dir) / "settings.json")
            loaded = default_settings.load(temp_dir)
            self.assertEqual(loaded, values)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(
                payload["defaults"]["straight_joint"]["hollow"]["gap_mm"],
                2.5,
            )

    def test_invalid_file_falls_back_without_overwriting_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text("{invalide", encoding="utf-8")
            original = path.read_bytes()
            values, warning = default_settings.load_or_factory(temp_dir)
            self.assertEqual(values, default_settings.factory_defaults())
            self.assertTrue(warning)
            self.assertEqual(path.read_bytes(), original)

    def test_negative_value_is_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            values = replace(
                default_settings.factory_defaults(),
                cope_ih_vertical_mm=-1.0,
            )
            with self.assertRaises(ValueError):
                default_settings.save(values, temp_dir)
            self.assertFalse((Path(temp_dir) / "settings.json").exists())


if __name__ == "__main__":
    unittest.main()
