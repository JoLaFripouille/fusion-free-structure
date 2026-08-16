from __future__ import annotations

import ast
import json
import pathlib
import re
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
ADDIN = ROOT / "addin" / "JHR_StructuralMembers_V1"
PROFILES = ROOT / "profiles"
sys.path.insert(0, str(ADDIN))

from lib import addin_info


class RepositoryTests(unittest.TestCase):
    def test_all_python_sources_parse(self):
        for path in tuple(ADDIN.rglob("*.py")) + tuple((ROOT / "tests").rglob("*.py")):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

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
        self.assertEqual(addin_info.VERSION, version)
        self.assertEqual(addin_info.DISPLAY_NAME, "Profil acier V{}".format(version))

    def test_visible_command_name_uses_the_manifest_version(self):
        command_source = (ADDIN / "commands" / "create_members.py").read_text(encoding="utf-8")
        builder_source = (ADDIN / "lib" / "member_builder.py").read_text(encoding="utf-8")
        self.assertIn("COMMAND_NAME = addin_info.DISPLAY_NAME", command_source)
        self.assertIn('"extension_version", addin_info.VERSION', builder_source)

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

    def test_command_exposes_clickable_three_by_three_anchor_grid(self):
        source = (ADDIN / "commands" / "create_members.py").read_text(encoding="utf-8")
        self.assertIn("addTableCommandInput", source)
        self.assertIn("addBoolValueInput", source)
        self.assertIn("anchors.ANCHOR_DEFINITIONS", source)
        self.assertIn("ANCHOR_BLUE_RESOURCES", source)
        self.assertIn("ANCHOR_RED_RESOURCES", source)
        self.assertIn('"anchor_code": anchor_code', source)

    def test_command_exposes_rotation_and_forwards_it_to_preview_and_creation(self):
        command_source = (ADDIN / "commands" / "create_members.py").read_text(encoding="utf-8")
        preview_source = (ADDIN / "lib" / "preview_graphics.py").read_text(encoding="utf-8")
        builder_source = (ADDIN / "lib" / "member_builder.py").read_text(encoding="utf-8")
        self.assertIn("addAngleValueCommandInput", command_source)
        self.assertIn('ROTATION_INPUT_ID = "profileRotation"', command_source)
        self.assertIn('"rotation_radians": rotation_radians', command_source)
        self.assertIn("rotation.orient_contours", preview_source)
        self.assertIn("rotation.orientation_matrix_2d", builder_source)
        self.assertIn("transform.setCell", builder_source)
        self.assertIn("sketch.move(entities, transform)", builder_source)
        self.assertIn('"rotation_deg",', builder_source)

    def test_command_exposes_two_dynamic_mirror_buttons(self):
        command_source = (ADDIN / "commands" / "create_members.py").read_text(encoding="utf-8")
        preview_source = (ADDIN / "lib" / "preview_graphics.py").read_text(encoding="utf-8")
        builder_source = (ADDIN / "lib" / "member_builder.py").read_text(encoding="utf-8")
        self.assertIn('FLIP_X_INPUT_ID = "flipX"', command_source)
        self.assertIn('FLIP_Y_INPUT_ID = "flipY"', command_source)
        self.assertIn('"flip_x": flip_x', command_source)
        self.assertIn('"flip_y": flip_y', command_source)
        self.assertIn("rotation.orient_contours", preview_source)
        self.assertIn('"flip_x", str(bool(flip_x)).lower()', builder_source)
        self.assertIn('"flip_y", str(bool(flip_y)).lower()', builder_source)

    def test_anchor_icon_resources_are_packaged(self):
        resources = ADDIN / "resources"
        for color in ("anchor_blue", "anchor_red"):
            for size in ("16x16.svg", "32x32.svg"):
                icon = resources / color / size
                self.assertTrue(icon.is_file(), icon)
                self.assertIn("<circle", icon.read_text(encoding="utf-8"))

    def test_mirror_icon_resources_are_packaged(self):
        resources = ADDIN / "resources"
        for axis in ("flip_x", "flip_y"):
            for size in ("16x16.svg", "32x32.svg"):
                icon = resources / axis / size
                self.assertTrue(icon.is_file(), icon)
                self.assertIn("<svg", icon.read_text(encoding="utf-8"))

    def test_preview_uses_requested_yellow_color(self):
        source = (ADDIN / "lib" / "preview_graphics.py").read_text(encoding="utf-8")
        self.assertIn("PREVIEW_YELLOW = (255, 205, 0)", source)


if __name__ == "__main__":
    unittest.main()
