from __future__ import annotations

import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
ADDIN = ROOT / "addin" / "JHR_StructuralMembers_V1"
PROFILES = ROOT / "profiles"


class RepositoryTests(unittest.TestCase):
    def test_release_payload_has_no_python_bytecode(self):
        self.assertEqual(list(ROOT.rglob("*.pyc")), [])
        self.assertEqual(
            [path for path in ROOT.rglob("__pycache__") if path.is_dir()],
            [],
        )

    def test_manifest_matches_version_file(self):
        manifest = json.loads((ADDIN / "JHR_StructuralMembers_V1.manifest").read_text(encoding="utf-8"))
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(manifest["autodeskProduct"], "Fusion")
        self.assertEqual(manifest["type"], "addin")
        self.assertEqual(manifest["version"], version)

    def test_expected_profile_inventory(self):
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
        actual = {
            folder.name: len(list(folder.glob("*.dxf")))
            for folder in PROFILES.iterdir()
            if folder.is_dir()
        }
        self.assertEqual(actual, expected)
        self.assertEqual(sum(actual.values()), 341)

    def test_dxf_files_are_ascii_r12(self):
        for path in PROFILES.rglob("*.dxf"):
            content = path.read_text(encoding="ascii")
            self.assertIn("AC1009", content, path)
            self.assertTrue(content.rstrip().endswith("EOF"), path)

    def test_python_sources_do_not_contain_personal_absolute_paths(self):
        forbidden = re.compile(
            r"\b[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/]|OneDrive",
            re.IGNORECASE,
        )
        for path in ADDIN.rglob("*.py"):
            self.assertIsNone(forbidden.search(path.read_text(encoding="utf-8")), path)

    def test_command_accepts_lines_and_arcs_only(self):
        source = (ADDIN / "commands" / "create_members.py").read_text(encoding="utf-8")
        self.assertIn('selection.addSelectionFilter("SketchCurves")', source)
        self.assertIn("adsk.fusion.SketchLine.cast(entity)", source)
        self.assertIn("adsk.fusion.SketchArc.cast(entity)", source)
        self.assertIn("n'est pas une ligne ou un arc", source)

    def test_command_exposes_linked_family_and_section_lists(self):
        source = (ADDIN / "commands" / "create_members.py").read_text(encoding="utf-8")
        self.assertIn("addDropDownCommandInput", source)
        self.assertIn('FAMILY_INPUT_ID = "profileFamily"', source)
        self.assertIn('SECTION_INPUT_ID = "profileSection"', source)
        self.assertIn("class InputChangedHandler", source)
        self.assertIn("_populate_section_input", source)
        self.assertIn('"profile": profile', source)

    def test_preview_uses_requested_yellow_color(self):
        source = (ADDIN / "lib" / "preview_graphics.py").read_text(encoding="utf-8")
        self.assertIn("PREVIEW_YELLOW = (255, 205, 0)", source)


if __name__ == "__main__":
    unittest.main()
