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
        joint_source = (ADDIN / "commands" / "create_joint.py").read_text(encoding="utf-8")
        cope_source = (ADDIN / "commands" / "create_cope.py").read_text(encoding="utf-8")
        inspection_source = (ADDIN / "commands" / "inspect_member.py").read_text(encoding="utf-8")
        settings_source = (ADDIN / "commands" / "manage_settings.py").read_text(
            encoding="utf-8"
        )
        builder_source = (ADDIN / "lib" / "member_builder.py").read_text(encoding="utf-8")
        self.assertIn("COMMAND_NAME = addin_info.DISPLAY_NAME", command_source)
        self.assertIn('COMMAND_NAME = "Jonctions acier V{}".format(addin_info.VERSION)', joint_source)
        self.assertIn(
            'COMMAND_NAME = "Grugeage profils ouverts V{}".format(addin_info.VERSION)',
            cope_source,
        )
        self.assertIn('COMMAND_NAME = "Inspecter un profil acier V{}".format(addin_info.VERSION)', inspection_source)
        self.assertIn(
            'COMMAND_NAME = "Paramètres Structure JHR V{}".format(addin_info.VERSION)',
            settings_source,
        )
        self.assertIn('"extension_version", addin_info.VERSION', builder_source)

    def test_first_straight_joint_is_registered_previewed_and_parametric(self):
        entry_source = (ADDIN / "JHR_StructuralMembers_V1.py").read_text(
            encoding="utf-8"
        )
        command_source = (ADDIN / "commands" / "create_joint.py").read_text(
            encoding="utf-8"
        )
        builder_source = (ADDIN / "lib" / "joint_builder.py").read_text(
            encoding="utf-8"
        )
        preview_source = (ADDIN / "lib" / "joint_preview.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("create_joint.start()", entry_source)
        self.assertIn("create_joint.stop()", entry_source)
        self.assertEqual(command_source.count('addSelectionFilter("Occurrences")'), 4)
        self.assertIn('"Barre principale"', command_source)
        self.assertIn('"Barre secondaire"', command_source)
        self.assertIn('MITER_FIRST_SELECTION_ID = "miterFirstMember"', command_source)
        self.assertIn('MITER_SECOND_SELECTION_ID = "miterSecondMember"', command_source)
        self.assertIn('GAP_INPUT_ID = "jointGap"', command_source)
        self.assertIn('JOINT_TYPE_INPUT_ID = "jointType"', command_source)
        self.assertIn("Coupe d'onglet symétrique", command_source)
        self.assertIn("JointPreviewManager", command_source)
        self.assertIn("setByOffsetThroughPoint", builder_source)
        self.assertIn("adsk.fusion.SketchArc.cast", builder_source)
        self.assertIn("evaluator.getTangent", builder_source)
        self.assertIn("setByDistanceOnPath", builder_source)
        self.assertIn("component.constructionAxes.createInput", builder_source)
        self.assertIn("axis_input.setByTwoPlanes", builder_source)
        self.assertIn("plane_input.setByAngle", builder_source)
        self.assertIn("create_miter_joint", builder_source)
        self.assertIn("component.features.splitBodyFeatures", builder_source)
        self.assertIn("split_features.createInput", builder_source)
        self.assertIn("component.features.removeFeatures.add", builder_source)
        self.assertIn("JOINT_ATTRIBUTE_GROUP = joint_records.ATTRIBUTE_GROUP", builder_source)
        self.assertIn("component.features.extrudeFeatures", builder_source)
        self.assertIn("DistanceExtentDefinition.create", builder_source)
        self.assertIn("PositiveExtentDirection", builder_source)
        self.assertIn("NegativeExtentDirection", builder_source)
        self.assertIn("_remaining_end_extension", builder_source)
        self.assertIn("PROLONGEMENT_BARRE_PRINCIPALE", builder_source)
        self.assertIn("_evaluate_primary_extensions", builder_source)
        self.assertIn("project_points_along_direction_to_plane", builder_source)
        self.assertIn("joint_records.next_record_name", builder_source)
        self.assertNotIn("def _existing_joint", builder_source)
        self.assertIn("CustomGraphicsCoordinates.create", preview_source)
        self.assertIn("CUT_PREVIEW_ORANGE", preview_source)

    def test_all_commands_use_the_dedicated_structural_tab(self):
        entry_source = (ADDIN / "JHR_StructuralMembers_V1.py").read_text(
            encoding="utf-8"
        )
        layout_source = (ADDIN / "lib" / "ui_layout.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('TAB_NAME = "STRUCTURE JHR"', layout_source)
        self.assertIn('CREATE_PANEL_NAME = "CRÉER"', layout_source)
        self.assertIn('MODIFY_PANEL_NAME = "MODIFIER"', layout_source)
        self.assertIn('SETTINGS_PANEL_NAME = "PARAMÈTRES"', layout_source)
        self.assertIn("workspace.toolbarTabs.add", layout_source)
        self.assertIn("tab.toolbarPanels.add", layout_source)
        self.assertIn("ui_layout.start(ui)", entry_source)
        self.assertIn("ui_layout.stop(ui)", entry_source)

        expected_panels = {
            "create_members.py": "ui_layout.CREATE_PANEL_ID",
            "manage_custom_profiles.py": "ui_layout.CREATE_PANEL_ID",
            "create_joint.py": "ui_layout.MODIFY_PANEL_ID",
            "create_cope.py": "ui_layout.MODIFY_PANEL_ID",
            "inspect_member.py": "ui_layout.MODIFY_PANEL_ID",
            "manage_settings.py": "ui_layout.SETTINGS_PANEL_ID",
        }
        for filename, panel_id in expected_panels.items():
            source = (ADDIN / "commands" / filename).read_text(encoding="utf-8")
            self.assertIn("PANEL_IDS = ({},)".format(panel_id), source)
            self.assertNotIn("SolidCreatePanel", source)
            self.assertNotIn("SolidModifyPanel", source)
            self.assertNotIn("SolidScriptsAddinsPanel", source)

    def test_local_default_values_are_managed_and_used_by_operations(self):
        entry_source = (ADDIN / "JHR_StructuralMembers_V1.py").read_text(
            encoding="utf-8"
        )
        settings_source = (ADDIN / "commands" / "manage_settings.py").read_text(
            encoding="utf-8"
        )
        storage_source = (ADDIN / "lib" / "default_settings.py").read_text(
            encoding="utf-8"
        )
        joint_source = (ADDIN / "commands" / "create_joint.py").read_text(
            encoding="utf-8"
        )
        cope_source = (ADDIN / "commands" / "create_cope.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("manage_settings.start()", entry_source)
        self.assertIn("manage_settings.stop()", entry_source)
        self.assertIn("addTabCommandInput", settings_source)
        self.assertIn("Valeurs par défaut", settings_source)
        self.assertIn("default_settings.save", settings_source)
        self.assertIn('SETTINGS_FILENAME = "settings.json"', storage_source)
        self.assertIn("os.replace", storage_source)
        self.assertIn("straight_joint_gap_mm", joint_source)
        self.assertIn("_apply_saved_gap", joint_source)
        self.assertIn("_apply_saved_defaults", cope_source)
        self.assertIn("cope_lt_under_web_mm", cope_source)
        self.assertNotIn("C:\\Users\\", storage_source)

    def test_open_profile_cope_is_previewed_validated_and_created(self):
        entry_source = (ADDIN / "JHR_StructuralMembers_V1.py").read_text(
            encoding="utf-8"
        )
        command_source = (ADDIN / "commands" / "create_cope.py").read_text(
            encoding="utf-8"
        )
        preview_source = (ADDIN / "lib" / "cope_preview.py").read_text(
            encoding="utf-8"
        )
        creator_source = (ADDIN / "lib" / "cope_creator.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("create_cope.start()", entry_source)
        self.assertIn("create_cope.stop()", entry_source)
        self.assertEqual(command_source.count('addSelectionFilter("Occurrences")'), 2)
        self.assertIn('"Barre principale"', command_source)
        self.assertIn('"Barre secondaire"', command_source)
        self.assertIn("evaluate_profile_cope", command_source)
        self.assertIn('UNDER_WEB_CLEARANCE_ID = "copeUnderWebClearance"', command_source)
        self.assertIn(
            'ROOT_RELIEF_CLEARANCE_ID = "copeRootReliefClearance"',
            command_source,
        )
        self.assertIn("Jeu sous l'âme secondaire", command_source)
        self.assertIn("Jeu autour du congé principal", command_source)
        self.assertIn("CopePreviewManager", command_source)
        self.assertIn('WEB_CLEARANCE_ID = "copeWebClearance"', command_source)
        self.assertIn("ValidateInputsHandler", command_source)
        self.assertIn("ExecuteHandler", command_source)
        self.assertIn("create_profile_cope", command_source)
        self.assertNotIn("command.isOKButtonVisible = False", command_source)
        self.assertIn("COPE_PREVIEW_RED", preview_source)
        self.assertIn("WEB_CUT_ORANGE", preview_source)
        self.assertIn("PRIMARY_EXTENSION_GREEN", preview_source)
        self.assertIn("bounded_volume_mesh", preview_source)
        self.assertIn("fillet_relief_mesh", preview_source)
        self.assertIn("evaluation.web_cut_normal", preview_source)
        cope_builder_source = (ADDIN / "lib" / "cope_builder.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("_evaluate_primary_extensions", cope_builder_source)
        self.assertIn("L_T_FAMILIES", cope_builder_source)
        self.assertIn("analyze_single_flange_profile_dxf", cope_builder_source)
        self.assertIn("single_cope_volumes", cope_builder_source)
        self.assertIn("if not (both_i_h or both_l_t)", cope_builder_source)
        cope_tree = ast.parse(cope_builder_source)
        profile_axes = next(
            node
            for node in cope_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_profile_axes"
        )
        self.assertTrue(any(isinstance(node, ast.Return) for node in profile_axes.body))
        self.assertIn("CutFeatureOperation", creator_source)
        self.assertIn("ToEntityExtentDefinition.create", creator_source)
        self.assertIn("_extend_primary_end", creator_source)
        self.assertIn("_extend_body", creator_source)
        self.assertIn("_split_and_keep_interior", creator_source)
        self.assertIn("_add_intersection_axis", creator_source)
        self.assertIn("_add_oriented_plane", creator_source)
        self.assertIn('COPE_TYPE = "open_profile_cope"', creator_source)
        self.assertIn(
            'LEGACY_COPE_TYPES = frozenset(("double_ipe_cope", "double_ih_cope"))',
            creator_source,
        )
        self.assertIn('ENDPOINT_PLANE_NAME = "PLAN_GRUGEAGE_EXTREMITE"', creator_source)
        self.assertIn('WEB_CUT_PLANE_NAME = "PLAN_COUPE_AME_PRINCIPALE"', creator_source)
        self.assertIn('FLANGE_START_PLANE_NAME = "PLAN_DEBUT_GRUGEAGE"', creator_source)
        self.assertIn(
            'COPE_REFERENCE_PLANE_NAME = "PLAN_REFERENCE_ESQUISSE_GRUGEAGE"',
            creator_source,
        )
        self.assertIn(
            'COPE_CUT_FEATURE_NAME = "GRUGEAGE_PROFIL_OUVERT"',
            creator_source,
        )
        self.assertIn("expected_profile_count = len(evaluation.volumes)", creator_source)
        self.assertIn(
            'ROOT_RELIEF_FEATURE_NAME = "DEGAGEMENT_CONGE_PRINCIPAL"',
            creator_source,
        )
        self.assertIn("component.features.filletFeatures", creator_source)
        self.assertIn("addConstantRadiusEdgeSet", creator_source)
        self.assertIn("_create_root_relief", creator_source)
        self.assertIn("FromEntityStartDefinition.create", creator_source)
        self.assertIn("extrude_input.startExtent = start_extent", creator_source)
        self.assertIn("removed_volume_cm3", creator_source)
        self.assertIn("for entity in reversed(created_entities)", creator_source)
        self.assertIn("for attribute in reversed(created_attributes)", creator_source)

    def test_github_installation_guide_covers_profiles_and_updates(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        guide = (ROOT / "docs" / "INSTALLATION_FUSION.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("docs/INSTALLATION_FUSION.md", readme)
        self.assertIn("Download ZIP", guide)
        self.assertIn("Scripts et compléments", guide)
        self.assertIn("API/AddIns", guide)
        self.assertIn("JHR_StructuralMembers_V1/profiles", guide)
        self.assertIn("Arrêter", guide)
        self.assertIn("Exécuter", guide)
        self.assertIn("341 profils", guide)

    def test_read_only_inspection_command_is_registered(self):
        entry_source = (ADDIN / "JHR_StructuralMembers_V1.py").read_text(encoding="utf-8")
        inspection_source = (ADDIN / "commands" / "inspect_member.py").read_text(encoding="utf-8")
        self.assertIn("inspect_member.start()", entry_source)
        self.assertIn("inspect_member.stop()", entry_source)
        self.assertIn('selection.addSelectionFilter("Occurrences")', inspection_source)
        self.assertIn("member_metadata.parse_member_attributes", inspection_source)
        self.assertIn("design.findEntityByToken", inspection_source)
        self.assertIn("Lecture seule", inspection_source)
        self.assertNotIn("deleteMe()", inspection_source.split("def _update_report", 1)[0])

    def test_custom_profile_manager_is_registered_and_keeps_user_data_local(self):
        entry_source = (ADDIN / "JHR_StructuralMembers_V1.py").read_text(encoding="utf-8")
        manager_source = (
            ADDIN / "commands" / "manage_custom_profiles.py"
        ).read_text(encoding="utf-8")
        custom_source = (ADDIN / "lib" / "custom_profiles.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("manage_custom_profiles.start()", entry_source)
        self.assertIn("manage_custom_profiles.stop()", entry_source)
        self.assertIn("ui.createFileDialog()", manager_source)
        self.assertIn("YesNoButtonType", manager_source)
        self.assertIn("custom_profiles.delete_profile", manager_source)
        self.assertIn('CATEGORY_ID = "Personnalises"', custom_source)
        self.assertIn('os.environ.get("APPDATA"', custom_source)
        self.assertFalse((PROFILES / "Personnalises").exists())

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
        geographic = PROFILES / "Zones_geographiques"
        europe = geographic / "Europe"
        actual = {
            folder.name: len(list(folder.glob("*.dxf")))
            for folder in europe.iterdir()
            if folder.is_dir()
        }
        self.assertEqual(
            [folder.name for folder in PROFILES.iterdir() if folder.is_dir()],
            ["Zones_geographiques"],
        )
        self.assertEqual(
            [folder.name for folder in geographic.iterdir() if folder.is_dir()],
            ["Europe"],
        )
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

    def test_command_exposes_linked_category_region_family_and_section_lists(self):
        source = (ADDIN / "commands" / "create_members.py").read_text(encoding="utf-8")
        self.assertIn("addDropDownCommandInput", source)
        self.assertIn('CATEGORY_INPUT_ID = "profileCategory"', source)
        self.assertIn('REGION_INPUT_ID = "profileRegion"', source)
        self.assertIn('FAMILY_INPUT_ID = "profileFamily"', source)
        self.assertIn('SECTION_INPUT_ID = "profileSection"', source)
        self.assertIn("class InputChangedHandler", source)
        self.assertIn("_populate_section_input", source)
        self.assertIn("profile_catalog.category_options", source)
        self.assertIn("profile_catalog.region_options", source)
        self.assertIn("region_input.isVisible", source)
        self.assertIn('"profile": profile', source)
        builder_source = (ADDIN / "lib" / "member_builder.py").read_text(encoding="utf-8")
        self.assertIn('"profile_category", profile.category_id', builder_source)
        self.assertIn('"profile_region", profile.region_id', builder_source)

    def test_command_exposes_and_persists_real_fusion_material(self):
        command_source = (ADDIN / "commands" / "create_members.py").read_text(encoding="utf-8")
        builder_source = (ADDIN / "lib" / "member_builder.py").read_text(encoding="utf-8")
        inspection_source = (ADDIN / "commands" / "inspect_member.py").read_text(encoding="utf-8")
        self.assertIn('PHYSICAL_MATERIAL_INPUT_ID = "physicalMaterial"', command_source)
        self.assertIn("physical_materials.discover_steel_materials", command_source)
        self.assertIn("physical_materials.resolve_material", command_source)
        self.assertIn('"material_choice": material_choice', command_source)
        self.assertIn("body.material = physical_material", builder_source)
        self.assertIn('"material_id", assigned_material.id', builder_source)
        self.assertIn('("Affectation physique", material_status)', inspection_source)
        self.assertNotIn("addStringValueInput", command_source)

    def test_startup_ensures_three_document_materials_idempotently(self):
        entry_source = (ADDIN / "JHR_StructuralMembers_V1.py").read_text(encoding="utf-8")
        command_source = (ADDIN / "commands" / "create_members.py").read_text(encoding="utf-8")
        material_source = (ADDIN / "lib" / "structural_materials.py").read_text(encoding="utf-8")
        self.assertIn("structural_materials.ensure_required_materials", entry_source)
        self.assertIn("structural_materials.ensure_required_materials", command_source)
        self.assertIn("S235JR EN 10025-2 - t<=16 mm", material_source)
        self.assertIn("S275JR EN 10025-2 - t<=16 mm", material_source)
        self.assertIn("S355J2 EN 10025-2 - t<=16 mm", material_source)
        self.assertIn("design.materials.addByCopy", material_source)
        self.assertIn("Il n'a pas été modifié", material_source)

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

    def test_existing_member_replacement_is_explicit_and_create_first(self):
        source = (ADDIN / "commands" / "create_members.py").read_text(
            encoding="utf-8"
        )
        links_source = (ADDIN / "lib" / "member_links.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('REPLACE_EXISTING_INPUT_ID = "replaceExistingMembers"', source)
        self.assertIn("Remplacer les barres déjà présentes", source)
        self.assertIn("member_links.curve_usages", source)
        self.assertIn("source_curve_token", links_source)
        self.assertIn("source_line_token", links_source)
        deferred = source.split("class DeferredCreateHandler", 1)[1]
        self.assertLess(
            deferred.index("created_occurrences.append(occurrence)"),
            deferred.index("occurrence.deleteMe()"),
        )

    def test_occupied_path_keeps_preview_visible_while_ok_is_blocked(self):
        source = (ADDIN / "commands" / "create_members.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("and (not has_existing or replace_existing)", source)
        self.assertIn("def _refresh_preview", source)
        input_changed = source.split("class InputChangedHandler", 1)[1].split(
            "def _supported_curves_from_selection",
            1,
        )[0]
        self.assertIn("SELECTION_ID", input_changed)
        self.assertIn("_refresh_preview_safely", input_changed)

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

    def test_preview_and_final_member_share_the_path_frame(self):
        preview_source = (ADDIN / "lib" / "preview_graphics.py").read_text(
            encoding="utf-8"
        )
        builder_source = (ADDIN / "lib" / "member_builder.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("path_frames.frames_for_curve", preview_source)
        self.assertIn("path_frames.frame_at_fraction", builder_source)
        self.assertIn("path_frames.basis_change_2d", builder_source)
        self.assertIn("rotation.multiply_matrices_2d", builder_source)


if __name__ == "__main__":
    unittest.main()
