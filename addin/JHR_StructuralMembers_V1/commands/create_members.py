from __future__ import annotations

import html
import math
import threading
import time
import traceback

import adsk.core
import adsk.fusion

from ..lib.member_builder import create_member
from ..lib.preview_graphics import PreviewManager
from ..lib import addin_info
from ..lib import anchors
from ..lib import joint_builder
from ..lib import member_links
from ..lib import member_metadata
from ..lib import member_section
from ..lib import physical_materials
from ..lib import profile_catalog
from ..lib import rotation
from ..lib import structural_materials
from ..lib import timeline_groups
from ..lib import ui_layout


COMMAND_ID = "EI_JHR_CreateStructuralMembersV1"
EDIT_COMMAND_ID = "EI_JHR_EditStructuralMember"
EDIT_COMMAND_NAME = "Modifier un profil"
EDIT_SELECTION_ID = "memberToEdit"
COMMAND_NAME = addin_info.DISPLAY_NAME
COMMAND_DESCRIPTION = "Crée le profil acier choisi sur chaque ligne ou arc d'esquisse sélectionné."
ROLE_INPUT_ID = "memberRole"
CATEGORY_INPUT_ID = "profileCategory"
REGION_INPUT_ID = "profileRegion"
FAMILY_INPUT_ID = "profileFamily"
SECTION_INPUT_ID = "profileSection"
PHYSICAL_MATERIAL_INPUT_ID = "physicalMaterial"
ANCHOR_TABLE_ID = "anchorGrid"
ANCHOR_INPUT_PREFIX = "anchor_"
ROTATION_INPUT_ID = "profileRotation"
MIRROR_TABLE_ID = "mirrorControls"
FLIP_X_INPUT_ID = "flipX"
FLIP_Y_INPUT_ID = "flipY"
SELECTION_ID = "skeletonLines"
REPLACE_EXISTING_INPUT_ID = "replaceExistingMembers"
PATH_USAGE_REPORT_ID = "pathUsageReport"
PANEL_IDS = (ui_layout.CREATE_PANEL_ID,)
CUSTOM_EVENT_ID = "EI_JHR_CreateStructuralMembersV1_Deferred"

_handlers = []
_panel_id = None
_custom_event = None
_custom_event_handler = None
_pending_jobs = []

ANCHOR_BLUE_RESOURCES = str(addin_info.ADDIN_ROOT / "resources" / "anchor_blue")
ANCHOR_RED_RESOURCES = str(addin_info.ADDIN_ROOT / "resources" / "anchor_red")
FLIP_X_RESOURCES = str(addin_info.ADDIN_ROOT / "resources" / "flip_x")
FLIP_Y_RESOURCES = str(addin_info.ADDIN_ROOT / "resources" / "flip_y")


def _app_and_ui():
    app = adsk.core.Application.get()
    return app, app.userInterface


def _log(message):
    app, _ = _app_and_ui()
    app.log("{} {}".format(addin_info.LOG_PREFIX, message))


def _fire_deferred_event_from_worker(app):
    """Déclenche l'événement hors du thread de la commande Fusion."""
    # Le court délai laisse l'événement Execute se terminer. Autodesk
    # prévoit fireCustomEvent pour un thread de travail, puis traite l'événement
    # dans le thread principal lorsque Fusion est disponible.
    time.sleep(0.1)
    for attempt in range(3):
        if app.fireCustomEvent(CUSTOM_EVENT_ID):
            return
        if attempt < 2:
            time.sleep(0.2)


class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self, editing=False):
        super().__init__()
        self._editing = editing

    def notify(self, args):
        try:
            event_args = adsk.core.CommandCreatedEventArgs.cast(args)
            command = event_args.command
            command.isRepeatable = False
            if self._editing:
                command.isExecutedWhenPreEmpted = False
            inputs = command.commandInputs

            profiles = profile_catalog.discover_profiles()
            default_profile = profile_catalog.default_profile(profiles)
            app, _ = _app_and_ui()
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                raise RuntimeError(
                    "Ouvrir un document de conception Fusion avant d'utiliser la commande."
                )
            if not self._editing:
                structural_materials.ensure_required_materials(design, app.materialLibraries)
            material_choices = physical_materials.discover_steel_materials(
                app.materialLibraries,
                design.materials,
            )
            default_material = None if self._editing else physical_materials.default_choice(material_choices)
            if self._editing:
                edit_selection = inputs.addSelectionInput(
                    EDIT_SELECTION_ID, "Profil à modifier", "Cliquer sur un profil Structure JHR.",
                )
                edit_selection.addSelectionFilter("Occurrences")
                edit_selection.setSelectionLimits(1, 1)
            role_input = inputs.addDropDownCommandInput(
                ROLE_INPUT_ID, "Fonction du profil", adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for key, label in member_metadata.ROLES.items():
                role_input.listItems.add(label, key == "BARRE")

            category_input = inputs.addDropDownCommandInput(
                CATEGORY_INPUT_ID,
                "Catégorie",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for category_id, category_label in profile_catalog.category_options(profiles):
                category_input.listItems.add(
                    category_label,
                    category_id == default_profile.category_id,
                    "",
                )

            region_input = inputs.addDropDownCommandInput(
                REGION_INPUT_ID,
                "Zone géographique",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            region_input.isVisible = (
                default_profile.category_id
                == profile_catalog.GEOGRAPHIC_CATEGORY_ID
            )
            for region_id, region_label in profile_catalog.region_options(
                profiles,
                default_profile.category_id,
            ):
                region_input.listItems.add(
                    region_label,
                    region_id == default_profile.region_id,
                    "",
                )

            family_input = inputs.addDropDownCommandInput(
                FAMILY_INPUT_ID,
                "Famille",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for family_id, family_label in profile_catalog.family_options(
                profiles,
                default_profile.region_id,
                default_profile.category_id,
            ):
                family_input.listItems.add(
                    family_label,
                    family_id == default_profile.family_id,
                    "",
                )

            section_input = inputs.addDropDownCommandInput(
                SECTION_INPUT_ID,
                "Section",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            _populate_section_input(
                section_input,
                profiles,
                default_profile.family_id,
                default_profile.region_id,
                default_profile.category_id,
                default_profile,
            )

            material_input = inputs.addDropDownCommandInput(
                PHYSICAL_MATERIAL_INPUT_ID,
                "Matériau physique Fusion",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for material_choice in material_choices:
                material_input.listItems.add(
                    material_choice.display_label,
                    material_choice == default_material,
                    "",
                )
            material_input.tooltip = "Matériau acier réellement fourni par Fusion"
            material_input.tooltipDescription = (
                "La liste provient des bibliothèques de matériaux actuellement "
                "chargées dans Fusion. Le matériau choisi sera affecté au corps."
            )

            anchor_table = inputs.addTableCommandInput(
                ANCHOR_TABLE_ID,
                "Point d'ancrage",
                3,
                "1:1:1",
            )
            anchor_table.minimumVisibleRows = 3
            anchor_table.maximumVisibleRows = 3
            anchor_table.hasGrid = False
            anchor_table.columnSpacing = 4
            anchor_table.rowSpacing = 4
            anchor_table.tooltip = "Cliquer sur le point du profil à placer sur le chemin."

            anchor_buttons = {}
            for anchor in anchors.ANCHOR_DEFINITIONS:
                is_selected = anchor.code == anchors.DEFAULT_ANCHOR_CODE
                button = inputs.addBoolValueInput(
                    ANCHOR_INPUT_PREFIX + anchor.code,
                    anchor.label,
                    False,
                    ANCHOR_RED_RESOURCES if is_selected else ANCHOR_BLUE_RESOURCES,
                    False,
                )
                button.isFullWidth = True
                button.tooltip = anchor.label
                anchor_table.addCommandInput(button, anchor.row, anchor.column)
                anchor_buttons[anchor.code] = button
            anchor_state = AnchorInputState(anchor_buttons)

            rotation_input = inputs.addAngleValueCommandInput(
                ROTATION_INPUT_ID,
                "Rotation",
                adsk.core.ValueInput.createByString("0 deg"),
            )
            rotation_input.tooltip = (
                "Angle de rotation du profil autour du point d'ancrage sélectionné."
            )

            mirror_table = inputs.addTableCommandInput(
                MIRROR_TABLE_ID,
                "Miroirs",
                2,
                "1:1",
            )
            mirror_table.minimumVisibleRows = 1
            mirror_table.maximumVisibleRows = 1
            mirror_table.hasGrid = False
            mirror_table.columnSpacing = 4
            flip_x_input = inputs.addBoolValueInput(
                FLIP_X_INPUT_ID,
                "Miroir X",
                True,
                FLIP_X_RESOURCES,
                False,
            )
            flip_x_input.tooltip = (
                "Inverse la coordonnée X du profil autour de l'ancrage."
            )
            flip_x_input.isFullWidth = True
            mirror_table.addCommandInput(flip_x_input, 0, 0)
            flip_y_input = inputs.addBoolValueInput(
                FLIP_Y_INPUT_ID,
                "Miroir Y",
                True,
                FLIP_Y_RESOURCES,
                False,
            )
            flip_y_input.tooltip = (
                "Inverse la coordonnée Y du profil autour de l'ancrage."
            )
            flip_y_input.isFullWidth = True
            mirror_table.addCommandInput(flip_y_input, 0, 1)

            if self._editing:
                report = inputs.addTextBoxCommandInput(
                    PATH_USAGE_REPORT_ID, "", "Sélectionner le profil à modifier.", 2, True,
                )
                report.isFullWidth = True
                edit = EditProfileState(design, profiles, material_choices, anchor_state, inputs)
                edit.load()
            else:
                edit = None
                selection = inputs.addSelectionInput(
                    SELECTION_ID,
                    "Chemins du squelette",
                    "Sélectionner une ou plusieurs lignes ou arcs d'esquisse dans le composant racine.",
                )
                selection.addSelectionFilter("SketchCurves")
                selection.setSelectionLimits(1, 0)
                replace_input = inputs.addBoolValueInput(
                    REPLACE_EXISTING_INPUT_ID,
                    "Remplacer les barres déjà présentes",
                    True,
                    "",
                    False,
                )
                replace_input.tooltip = (
                    "Si un chemin possède déjà une barre créée par l'extension, "
                    "la nouvelle barre est créée et contrôlée avant le retrait de l'ancienne."
                )
                inputs.addTextBoxCommandInput(
                    PATH_USAGE_REPORT_ID,
                    "Utilisation des chemins",
                    "Sélectionner une ligne ou un arc du squelette.",
                    3,
                    True,
                )
                inputs.addTextBoxCommandInput(
                    "v1Info",
                    "Version chargée",
                    "Version : {}<br>Profil : catégorie, zone, famille et section au choix<br>Matériau : liste physique fournie par Fusion et affectée au corps<br>Ancrage : grille 3 × 3, centre par défaut<br>Orientation : rotation et miroirs X/Y autour de l'ancrage<br>Chemins : lignes et arcs<br>Aperçu jaune dynamique<br>Un composant indépendant par chemin."
                    .format(addin_info.VERSION),
                    7,
                    True,
                )

            preview_manager = PreviewManager()

            execute_handler = ExecuteHandler(
                preview_manager,
                profiles,
                material_choices,
                anchor_state,
                edit,
            )
            command.execute.add(execute_handler)
            _handlers.append(execute_handler)

            preview_handler = ExecutePreviewHandler(preview_manager, profiles, anchor_state, edit)
            command.executePreview.add(preview_handler)
            _handlers.append(preview_handler)

            input_changed_handler = InputChangedHandler(
                preview_manager,
                profiles,
                category_input,
                region_input,
                family_input,
                section_input,
                anchor_state,
                edit,
            )
            command.inputChanged.add(input_changed_handler)
            _handlers.append(input_changed_handler)

            destroy_handler = DestroyHandler(preview_manager)
            command.destroy.add(destroy_handler)
            _handlers.append(destroy_handler)

            validate_handler = ValidateInputsHandler(edit)
            command.validateInputs.add(validate_handler)
            _handlers.append(validate_handler)
            if edit:
                activation = ActivateEditHandler(edit, preview_manager)
                command.activate.add(activation)
                _handlers.append(activation)
            _log("Commande ouverte")
        except Exception:
            _, ui = _app_and_ui()
            ui.messageBox("Échec de la création de la commande:\n{}".format(traceback.format_exc()))


class ValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self, edit=None):
        super().__init__()
        self._edit = edit

    def notify(self, args):
        event_args = adsk.core.ValidateInputsEventArgs.cast(args)
        if self._edit:
            event_args.areInputsValid = bool(self._edit.target)
            return
        selection = event_args.inputs.itemById(SELECTION_ID)
        material_input = event_args.inputs.itemById(PHYSICAL_MATERIAL_INPUT_ID)
        app, _ = _app_and_ui()
        design = adsk.fusion.Design.cast(app.activeProduct)
        has_existing = False
        if design and selection:
            curves = _supported_curves_from_selection(
                selection,
                design.rootComponent,
                strict=False,
            )
            has_existing = any(
                usage.occurrences
                for usage in member_links.curve_usages(
                    design,
                    design.rootComponent,
                    curves,
                )
            )
        replace_existing = _replace_existing_selected(event_args.inputs)
        event_args.areInputsValid = bool(
            selection
            and selection.selectionCount >= 1
            and material_input
            and material_input.selectedItem
            and (not has_existing or replace_existing)
        )


def _populate_family_input(
    family_input,
    profiles,
    region_id,
    category_id=None,
    selected_profile=None,
):
    family_input.listItems.clear()
    for index, (family_id, family_label) in enumerate(
        profile_catalog.family_options(profiles, region_id, category_id)
    ):
        is_selected = (
            family_id == selected_profile.family_id
            if selected_profile is not None
            else index == 0
        )
        family_input.listItems.add(family_label, is_selected, "")


def _populate_section_input(
    section_input,
    profiles,
    family_id,
    region_id=None,
    category_id=None,
    selected_profile=None,
):
    section_input.listItems.clear()
    family_profiles = profile_catalog.profiles_for_family(
        profiles,
        family_id,
        region_id,
        category_id,
    )
    for index, profile in enumerate(family_profiles):
        is_selected = (
            profile == selected_profile
            if selected_profile is not None
            else index == 0
        )
        section_input.listItems.add(profile.section_label, is_selected, "")


def _selected_profile(inputs, profiles):
    category_input = inputs.itemById(CATEGORY_INPUT_ID)
    region_input = inputs.itemById(REGION_INPUT_ID)
    family_input = inputs.itemById(FAMILY_INPUT_ID)
    section_input = inputs.itemById(SECTION_INPUT_ID)
    if not category_input or not category_input.selectedItem:
        raise RuntimeError("Aucune catégorie de profil n'est sélectionnée.")
    if not region_input or not region_input.selectedItem:
        raise RuntimeError("Aucune zone géographique n'est sélectionnée.")
    if not family_input or not family_input.selectedItem:
        raise RuntimeError("Aucune famille de profil n'est sélectionnée.")
    if not section_input or not section_input.selectedItem:
        raise RuntimeError("Aucune section de profil n'est sélectionnée.")
    return profile_catalog.profile_from_labels(
        profiles,
        family_input.selectedItem.name,
        section_input.selectedItem.name,
        region_input.selectedItem.name,
        category_input.selectedItem.name,
    )


def _selected_rotation_radians(inputs):
    rotation_input = adsk.core.AngleValueCommandInput.cast(
        inputs.itemById(ROTATION_INPUT_ID)
    )
    if not rotation_input:
        raise RuntimeError("Le réglage de rotation est introuvable.")
    return rotation_input.value


def _selected_physical_material(inputs, material_choices):
    material_input = adsk.core.DropDownCommandInput.cast(
        inputs.itemById(PHYSICAL_MATERIAL_INPUT_ID)
    )
    if not material_input or not material_input.selectedItem:
        raise RuntimeError("Aucun matériau physique Fusion n'est sélectionné.")
    return physical_materials.choice_from_label(
        material_choices,
        material_input.selectedItem.name,
    )


def _selected_flip_state(inputs):
    flip_x_input = adsk.core.BoolValueCommandInput.cast(
        inputs.itemById(FLIP_X_INPUT_ID)
    )
    flip_y_input = adsk.core.BoolValueCommandInput.cast(
        inputs.itemById(FLIP_Y_INPUT_ID)
    )
    if not flip_x_input or not flip_y_input:
        raise RuntimeError("Les réglages de miroir sont introuvables.")
    return flip_x_input.value, flip_y_input.value


def _replace_existing_selected(inputs):
    replace_input = adsk.core.BoolValueCommandInput.cast(
        inputs.itemById(REPLACE_EXISTING_INPUT_ID)
    )
    return bool(replace_input and replace_input.value)


def _update_path_usage_report(inputs):
    report = inputs.itemById(PATH_USAGE_REPORT_ID)
    if not report:
        return
    app, _ = _app_and_ui()
    design = adsk.fusion.Design.cast(app.activeProduct)
    selection = inputs.itemById(SELECTION_ID)
    if not design or not selection:
        report.formattedText = "Ouvrir une conception Fusion."
        return
    curves = _supported_curves_from_selection(
        selection,
        design.rootComponent,
        strict=False,
    )
    if not curves:
        report.formattedText = "Sélectionner une ligne ou un arc du squelette."
        return
    usages = member_links.curve_usages(design, design.rootComponent, curves)
    used = member_links.unique_used_occurrences(usages)
    if not used:
        report.formattedText = (
            "<b>{} chemin(s) libre(s).</b><br>Une nouvelle barre sera créée."
            .format(len(curves))
        )
        return
    names = ", ".join(
        html.escape(occurrence.component.name, quote=True)
        for occurrence in used
    )
    if _replace_existing_selected(inputs):
        report.formattedText = (
            "<b>Remplacement activé pour {} barre(s).</b><br>{}<br>"
            "Les anciennes barres resteront présentes jusqu'à la création complète des nouvelles."
            .format(len(used), names)
        )
    else:
        report.formattedText = (
            "<b>Attention : {} barre(s) utilisent déjà la sélection.</b><br>{}<br>"
            "Cocher « Remplacer les barres déjà présentes » pour éviter un doublon caché."
            .format(len(used), names)
        )


class EditProfileState:
    def __init__(self, design, profiles, material_choices, anchor_state, inputs):
        self.design = design
        self.profiles = profiles
        self.material_choices = material_choices
        self.anchor_state = anchor_state
        self.inputs = inputs
        self.target = None
        self.curve = None
        self.loading = False
        self.selection = inputs.itemById(EDIT_SELECTION_ID)
        self.report = inputs.itemById(PATH_USAGE_REPORT_ID)

    def load(self):
        selected = (adsk.fusion.Occurrence.cast(self.selection.selection(0).entity)
                    if self.selection.selectionCount == 1 else None)
        if selected and selected == self.target:
            return
        self.target = self.curve = None
        controls = (
            ROLE_INPUT_ID, CATEGORY_INPUT_ID, REGION_INPUT_ID, FAMILY_INPUT_ID, SECTION_INPUT_ID,
            PHYSICAL_MATERIAL_INPUT_ID, ROTATION_INPUT_ID, FLIP_X_INPUT_ID, FLIP_Y_INPUT_ID,
            *(ANCHOR_INPUT_PREFIX + anchor.code for anchor in anchors.ANCHOR_DEFINITIONS),
        )
        self.loading = True
        try:
            for key in controls:
                self.inputs.itemById(key).isEnabled = False
            if not selected:
                self.report.formattedText = "Sélectionner le profil à modifier."
                return
            if selected not in self.design.rootComponent.occurrences:
                raise ValueError("Sélectionner un profil JHR dans le composant racine.")
            metadata = joint_builder._member_metadata(selected, "à modifier")
            curve = joint_builder._linked_curve(self.design, metadata, "à modifier", allow_arc=True)
            profile = next((item for item in self.profiles
                            if item.relative_path.casefold() == metadata.profile_source.casefold()), None)
            if not profile:
                raise ValueError(f"La section actuelle de {metadata.profile} est absente du catalogue chargé.")
            self._load_values(selected, profile, metadata)
            self.target = selected
            self.curve = curve
            for key in controls:
                self.inputs.itemById(key).isEnabled = True
            self.report.formattedText = html.escape(selected.component.name)
        except Exception as error:
            self.target = self.curve = None
            self.report.formattedText = html.escape(str(error))
            _log("Impossible de charger le profil sélectionné.\n" + traceback.format_exc())
        finally:
            self.loading = False

    def _load_values(self, occurrence, profile, metadata):
        inputs = self.inputs
        role = member_metadata.ROLES[member_metadata.role_for(occurrence.component)]
        next(item for item in inputs.itemById(ROLE_INPUT_ID).listItems if item.name == role).isSelected = True
        categories = inputs.itemById(CATEGORY_INPUT_ID).listItems
        category = next(item for item in categories if item.name == profile.category_label)
        category.isSelected = True
        region = inputs.itemById(REGION_INPUT_ID)
        region.isVisible = profile.category_id == profile_catalog.GEOGRAPHIC_CATEGORY_ID
        region.listItems.clear()
        for region_id, label in profile_catalog.region_options(self.profiles, profile.category_id):
            region.listItems.add(label, region_id == profile.region_id)
        _populate_family_input(inputs.itemById(FAMILY_INPUT_ID), self.profiles,
                               profile.region_id, profile.category_id, profile)
        _populate_section_input(inputs.itemById(SECTION_INPUT_ID), self.profiles, profile.family_id,
                                profile.region_id, profile.category_id, profile)
        material = joint_builder._single_body(occurrence, "à modifier").material
        material_input = inputs.itemById(PHYSICAL_MATERIAL_INPUT_ID)
        material_input.listItems.clear()
        # Conserver le matériau du corps même lorsque sa bibliothèque n’est plus chargée.
        material_input.listItems.add(f"Conserver le matériau actuel ({material.name if material else 'indéfini'})", True)
        for choice in self.material_choices:
            material_input.listItems.add(choice.display_label, False)
        self.anchor_state.select(metadata.anchor)
        inputs.itemById(ROTATION_INPUT_ID).value = math.radians(metadata.rotation_deg)
        inputs.itemById(FLIP_X_INPUT_ID).value = metadata.flip_x
        inputs.itemById(FLIP_Y_INPUT_ID).value = metadata.flip_y

    def kept_material(self):
        return self.inputs.itemById(PHYSICAL_MATERIAL_INPUT_ID).selectedItem.index == 0


class ActivateEditHandler(adsk.core.CommandEventHandler):
    def __init__(self, edit, preview_manager):
        super().__init__()
        self.edit = edit
        self.preview_manager = preview_manager

    def notify(self, args):
        self.edit.load()
        _refresh_preview_safely(
            self.preview_manager, self.edit.profiles, self.edit.anchor_state, self.edit.inputs, self.edit,
        )


def _refresh_preview(preview_manager, profiles, anchor_state, inputs, edit=None):
    """Dessine l'aperçu même lorsque le chemin occupé maintient OK désactivé."""
    app, _ = _app_and_ui()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        preview_manager.clear()
        return
    if edit:
        if not edit.curve:
            preview_manager.clear()
            return
        curves = (edit.curve,)
    else:
        curves = _supported_curves_from_selection(
            inputs.itemById(SELECTION_ID), design.rootComponent, strict=False,
        )
    profile = _selected_profile(inputs, profiles)
    rotation_radians = _selected_rotation_radians(inputs)
    flip_x, flip_y = _selected_flip_state(inputs)
    preview_manager.update(
        design.rootComponent,
        curves,
        profile,
        anchor_state.selected_code,
        rotation_radians,
        flip_x,
        flip_y,
    )


def _refresh_preview_safely(preview_manager, profiles, anchor_state, inputs, edit=None):
    try:
        _refresh_preview(preview_manager, profiles, anchor_state, inputs, edit)
    except Exception as error:
        preview_manager.clear()
        _log("APERÇU INDISPONIBLE: {}\n{}".format(error, traceback.format_exc()))


class AnchorInputState:
    def __init__(self, buttons):
        self._buttons = buttons
        self._selected_code = anchors.DEFAULT_ANCHOR_CODE
        self._is_updating = False

    @property
    def selected_code(self):
        return self._selected_code

    @property
    def is_updating(self):
        return self._is_updating

    def select(self, anchor_code):
        anchors.definition(anchor_code)
        self._selected_code = anchor_code
        self._is_updating = True
        try:
            for code, button in self._buttons.items():
                is_selected = code == anchor_code
                button.resourceFolder = (
                    ANCHOR_RED_RESOURCES if is_selected else ANCHOR_BLUE_RESOURCES
                )
        finally:
            self._is_updating = False


class InputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(
        self,
        preview_manager,
        profiles,
        category_input,
        region_input,
        family_input,
        section_input,
        anchor_state,
        edit=None,
    ):
        super().__init__()
        self._preview_manager = preview_manager
        self._profiles = profiles
        self._category_input = category_input
        self._region_input = region_input
        self._family_input = family_input
        self._section_input = section_input
        self._anchor_state = anchor_state
        self._edit = edit

    def notify(self, args):
        event_args = adsk.core.InputChangedEventArgs.cast(args)
        changed_input = event_args.input
        if not changed_input:
            return
        if self._anchor_state.is_updating or (self._edit and self._edit.loading):
            return
        if changed_input.id == EDIT_SELECTION_ID:
            self._edit.load()
        if changed_input.id in (SELECTION_ID, REPLACE_EXISTING_INPUT_ID):
            _update_path_usage_report(event_args.inputs)
        if changed_input.id == CATEGORY_INPUT_ID:
            selected_category = self._category_input.selectedItem
            if selected_category:
                category_id = next(
                    category_id
                    for category_id, category_label in profile_catalog.category_options(
                        self._profiles
                    )
                    if category_label == selected_category.name
                )
                self._region_input.isVisible = (
                    category_id == profile_catalog.GEOGRAPHIC_CATEGORY_ID
                )
                self._region_input.listItems.clear()
                for index, (_, region_label) in enumerate(
                    profile_catalog.region_options(self._profiles, category_id)
                ):
                    self._region_input.listItems.add(region_label, index == 0, "")
                selected_region = self._region_input.selectedItem
                if selected_region:
                    region_id = next(
                        region_id
                        for region_id, region_label in profile_catalog.region_options(
                            self._profiles,
                            category_id,
                        )
                        if region_label == selected_region.name
                    )
                    _populate_family_input(
                        self._family_input,
                        self._profiles,
                        region_id,
                        category_id,
                    )
                    selected_family = self._family_input.selectedItem
                    if selected_family:
                        family_id = next(
                            family_id
                            for family_id, family_label in profile_catalog.family_options(
                                self._profiles,
                                region_id,
                                category_id,
                            )
                            if family_label == selected_family.name
                        )
                        _populate_section_input(
                            self._section_input,
                            self._profiles,
                            family_id,
                            region_id,
                            category_id,
                        )
        elif changed_input.id == REGION_INPUT_ID:
            selected_category = self._category_input.selectedItem
            selected_region = self._region_input.selectedItem
            if selected_category and selected_region:
                category_id = next(
                    category_id
                    for category_id, category_label in profile_catalog.category_options(
                        self._profiles
                    )
                    if category_label == selected_category.name
                )
                region_id = next(
                    region_id
                    for region_id, region_label in profile_catalog.region_options(
                        self._profiles,
                        category_id,
                    )
                    if region_label == selected_region.name
                )
                _populate_family_input(
                    self._family_input,
                    self._profiles,
                    region_id,
                    category_id,
                )
                selected_family = self._family_input.selectedItem
                if selected_family:
                    family_id = next(
                        family_id
                        for family_id, family_label in profile_catalog.family_options(
                            self._profiles,
                            region_id,
                            category_id,
                        )
                        if family_label == selected_family.name
                    )
                    _populate_section_input(
                        self._section_input,
                        self._profiles,
                        family_id,
                        region_id,
                        category_id,
                    )
        elif changed_input.id == FAMILY_INPUT_ID:
            selected_category = self._category_input.selectedItem
            selected_region = self._region_input.selectedItem
            selected_family = self._family_input.selectedItem
            if selected_category and selected_region and selected_family:
                category_id = next(
                    category_id
                    for category_id, category_label in profile_catalog.category_options(
                        self._profiles
                    )
                    if category_label == selected_category.name
                )
                region_id = next(
                    region_id
                    for region_id, region_label in profile_catalog.region_options(
                        self._profiles,
                        category_id,
                    )
                    if region_label == selected_region.name
                )
                family_id = next(
                    family_id
                    for family_id, family_label in profile_catalog.family_options(
                        self._profiles,
                        region_id,
                        category_id,
                    )
                    if family_label == selected_family.name
                )
                _populate_section_input(
                    self._section_input,
                    self._profiles,
                    family_id,
                    region_id,
                    category_id,
                )
        anchor_changed = changed_input.id.startswith(ANCHOR_INPUT_PREFIX)
        if anchor_changed:
            self._anchor_state.select(changed_input.id[len(ANCHOR_INPUT_PREFIX):])
        if (
            changed_input.id in (
                CATEGORY_INPUT_ID,
                REGION_INPUT_ID,
                FAMILY_INPUT_ID,
                SECTION_INPUT_ID,
                ROTATION_INPUT_ID,
                FLIP_X_INPUT_ID,
                FLIP_Y_INPUT_ID,
                SELECTION_ID,
                EDIT_SELECTION_ID,
            )
            or anchor_changed
        ):
            _refresh_preview_safely(
                self._preview_manager,
                self._profiles,
                self._anchor_state,
                event_args.inputs,
                self._edit,
            )


def _supported_curves_from_selection(selection, root_component, strict):
    curves = []
    for index in range(selection.selectionCount):
        entity = selection.selection(index).entity
        curve = adsk.fusion.SketchLine.cast(entity) or adsk.fusion.SketchArc.cast(entity)
        if not curve:
            if strict:
                raise RuntimeError(
                    "La sélection {} n'est pas une ligne ou un arc d'esquisse pris en charge."
                    .format(index + 1)
                )
            continue
        native_curve = curve.nativeObject if curve.nativeObject else curve
        if native_curve.parentSketch.parentComponent != root_component:
            if strict:
                raise RuntimeError(
                    "La V1 accepte uniquement les lignes et arcs d'un squelette placé dans le composant racine."
                )
            continue
        if native_curve.length <= 1e-6:
            if strict:
                raise RuntimeError("Un chemin sélectionné a une longueur nulle ou trop petite.")
            continue
        curves.append(native_curve)
    return curves


class ExecutePreviewHandler(adsk.core.CommandEventHandler):
    def __init__(self, preview_manager, profiles, anchor_state, edit=None):
        super().__init__()
        self._preview_manager = preview_manager
        self._profiles = profiles
        self._anchor_state = anchor_state
        self._edit = edit

    def notify(self, args):
        event_args = adsk.core.CommandEventArgs.cast(args)
        event_args.isValidResult = False
        _refresh_preview_safely(
            self._preview_manager,
            self._profiles,
            self._anchor_state,
            event_args.command.commandInputs,
            self._edit,
        )


class DestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self, preview_manager):
        super().__init__()
        self._preview_manager = preview_manager

    def notify(self, args):
        self._preview_manager.clear()


class ExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self, preview_manager, profiles, material_choices, anchor_state, edit=None):
        super().__init__()
        self._preview_manager = preview_manager
        self._profiles = profiles
        self._material_choices = material_choices
        self._anchor_state = anchor_state
        self._edit = edit

    def notify(self, args):
        event_args = adsk.core.CommandEventArgs.cast(args)
        try:
            self._preview_manager.clear()
            app, ui = _app_and_ui()
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                raise RuntimeError("Ouvrir un document de conception Fusion avant d'utiliser la commande.")
            if design.designType != adsk.fusion.DesignTypes.ParametricDesignType:
                raise RuntimeError("La V1 nécessite l'historique de conception paramétrique activé.")

            root_component = design.rootComponent
            inputs = event_args.command.commandInputs
            target = None
            replace_existing = False
            if self._edit:
                if design != self._edit.design or not self._edit.target or not self._edit.target.isValid:
                    raise ValueError("Sélectionner de nouveau le profil à modifier.")
                target = self._edit.target
                curves = (self._edit.curve,)
            else:
                curves = _supported_curves_from_selection(inputs.itemById(SELECTION_ID), root_component, strict=True)
                replace_existing = _replace_existing_selected(inputs)
                if not replace_existing and any(
                    usage.occurrences for usage in member_links.curve_usages(design, root_component, curves)
                ):
                    raise RuntimeError("Des barres occupent déjà les chemins sélectionnés. Choisir des chemins libres "
                                       "ou cocher « Remplacer les barres déjà présentes ».")

            profile = _selected_profile(inputs, self._profiles)
            material_choice = (None if self._edit and self._edit.kept_material()
                               else _selected_physical_material(inputs, self._material_choices))
            anchor_code = self._anchor_state.selected_code
            rotation_radians = _selected_rotation_radians(inputs)
            flip_x, flip_y = _selected_flip_state(inputs)

            # L'API Fusion interdit l'import DXF depuis un événement de
            # commande. Le travail est donc mis en file puis exécuté par un
            # événement personnalisé lorsque Fusion redevient disponible.
            job = {
                "document": app.activeDocument,
                "design": design,
                "root_component": root_component,
                "curves": curves,
                "profile": profile,
                "role": tuple(member_metadata.ROLES)[inputs.itemById(ROLE_INPUT_ID).selectedItem.index],
                "material_choice": material_choice,
                "anchor_code": anchor_code,
                "rotation_radians": rotation_radians,
                "flip_x": flip_x,
                "flip_y": flip_y,
                "replace_existing": replace_existing,
                "edit_target": target,
            }
            _pending_jobs.append(job)
            worker = threading.Thread(
                target=_fire_deferred_event_from_worker,
                args=(app,),
                daemon=True,
            )
            worker.start()
            _log(
                "Import DXF {} avec le matériau Fusion {}, ancrage {}, rotation {} deg, miroirs X={} Y={} et remplacement={} planifié pour {} chemin(s)"
                .format(
                    profile.designation,
                    material_choice.material_name if material_choice else "actuel",
                    anchor_code,
                    rotation.format_degrees(rotation_radians),
                    flip_x,
                    flip_y,
                    replace_existing,
                    len(curves),
                )
            )
        except Exception as error:
            event_args.executeFailed = True
            _log("ÉCHEC: {}\n{}".format(error, traceback.format_exc()))
            _, ui = _app_and_ui()
            action = "La modification" if self._edit else "La création"
            ui.messageBox(f"{action} a été annulée.\n{error}")


class DeferredCreateHandler(adsk.core.CustomEventHandler):
    def notify(self, args):
        if not _pending_jobs:
            return

        job = _pending_jobs.pop(0)
        created_occurrences = []
        creation_completed = False
        try:
            app, ui = _app_and_ui()
            if app.activeDocument != job["document"]:
                raise RuntimeError("Le document actif a changé avant l'import du DXF.")
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design or design != job["design"]:
                raise RuntimeError("La conception active a changé avant l'import du DXF.")

            material_choice = job["material_choice"]
            physical_material = (physical_materials.resolve_material(
                app.materialLibraries, material_choice, design.materials,
            ) if material_choice else None)
            if job["edit_target"] is not None:
                result = member_section.edit_member(
                    design, job["edit_target"], job["profile"], job["anchor_code"], job["rotation_radians"],
                    job["flip_x"], job["flip_y"], physical_material=physical_material, material_choice=material_choice,
                    role=job["role"],
                )
                if result["changed"]:
                    _log("Profil modifié dans son occurrence. {} assemblage(s) contrôlé(s).".format(result["assemblies"]))
                return
            usages = member_links.curve_usages(
                design,
                job["root_component"],
                job["curves"],
            )
            old_occurrences = member_links.unique_used_occurrences(usages)
            if old_occurrences and not job["replace_existing"]:
                raise RuntimeError(
                    "Une barre a été ajoutée sur un chemin avant l'exécution différée. "
                    "La création est annulée pour éviter un doublon."
                )

            attached = [old for old in old_occurrences if member_section.attachments(design, old)]
            if attached:
                if len(old_occurrences) != 1 or len(job["curves"]) != 1:
                    raise ValueError("Pour une barre avec assemblage, changer une section à la fois.")
                result = member_section.replace_section(design, attached[0], job["profile"], placement=(
                    job["anchor_code"], job["rotation_radians"], bool(job["flip_x"]), bool(job["flip_y"]),
                    physical_material.id,
                ))
                ui.messageBox(f"Section changée — {result['assemblies']} assemblage(s) contrôlé(s)."
                              if result["changed"] else "Cette section est déjà en place.")
                return

            for curve in job["curves"]:
                if not curve or not curve.isValid:
                    raise RuntimeError("Un chemin sélectionné n'est plus valide.")
                occurrence = create_member(
                    job["root_component"],
                    curve,
                    job["profile"],
                    job["anchor_code"],
                    job["rotation_radians"],
                    job["flip_x"],
                    job["flip_y"],
                    physical_material,
                    material_choice,
                    name_prefix=job["role"],
                )
                created_occurrences.append(occurrence)
                _log("Composant créé depuis le DXF: {}".format(occurrence.component.name))

            creation_completed = True
            replaced_count = 0
            if job["replace_existing"]:
                for occurrence in old_occurrences:
                    if occurrence and occurrence.isValid:
                        old_name = occurrence.component.name
                        timeline_groups.release_member_group(occurrence)
                        if not occurrence.deleteMe():
                            raise RuntimeError(
                                "Fusion n'a pas pu retirer l'ancienne barre {}."
                                .format(old_name)
                            )
                        replaced_count += 1
                        _log("Ancienne barre remplacée: {}".format(old_name))

            ui.messageBox(
                "{} barre(s) {} en {} créée(s) depuis le DXF avec l'ancrage {}, une rotation de {}° et les miroirs X={} Y={}.\n{} ancienne(s) barre(s) remplacée(s)."
                .format(
                    len(created_occurrences),
                    job["profile"].designation,
                    material_choice.material_name,
                    anchors.label(job["anchor_code"]),
                    rotation.format_degrees(job["rotation_radians"]),
                    job["flip_x"],
                    job["flip_y"],
                    replaced_count,
                )
            )
        except Exception as error:
            if not creation_completed:
                for occurrence in reversed(created_occurrences):
                    if occurrence and occurrence.isValid:
                        timeline_groups.release_member_group(occurrence)
                        occurrence.deleteMe()
                _log("ÉCHEC IMPORT DXF: {}\n{}".format(error, traceback.format_exc()))
                _, ui = _app_and_ui()
                action = "La modification" if job["edit_target"] is not None else "La création"
                ui.messageBox(f"{action} a été annulée.\n{error}")
            else:
                _log("ÉCHEC REMPLACEMENT: {}\n{}".format(error, traceback.format_exc()))
                _, ui = _app_and_ui()
                ui.messageBox(
                    "La nouvelle barre a été créée, mais le retrait d'une ancienne barre a échoué:\n{}"
                    .format(error)
                )
        finally:
            if _pending_jobs:
                app, _ = _app_and_ui()
                threading.Thread(
                    target=_fire_deferred_event_from_worker,
                    args=(app,),
                    daemon=True,
                ).start()


def start():
    global _panel_id, _custom_event, _custom_event_handler
    app, ui = _app_and_ui()

    _custom_event = app.registerCustomEvent(CUSTOM_EVENT_ID)
    if not _custom_event:
        raise RuntimeError("Impossible d'enregistrer l'événement d'import DXF différé.")
    _custom_event_handler = DeferredCreateHandler()
    if not _custom_event.add(_custom_event_handler):
        app.unregisterCustomEvent(CUSTOM_EVENT_ID)
        _custom_event = None
        _custom_event_handler = None
        raise RuntimeError("Impossible de connecter l'événement d'import DXF différé.")
    _handlers.append(_custom_event_handler)

    for command_id, name, description, panel_ids, editing, icon in (
        (COMMAND_ID, COMMAND_NAME, COMMAND_DESCRIPTION, PANEL_IDS, False, "profil_acier"),
        (EDIT_COMMAND_ID, EDIT_COMMAND_NAME, "Reprendre les réglages d’un profil JHR existant.",
         (ui_layout.MODIFY_PANEL_ID,), True, "modifier_profil"),
    ):
        definition = ui.commandDefinitions.itemById(command_id)
        if not definition:
            definition = ui.commandDefinitions.addButtonDefinition(command_id, name, description,
                                                                  addin_info.ribbon_icon(icon))
        handler = CommandCreatedHandler(editing)
        definition.commandCreated.add(handler)
        _handlers.append(handler)
        for panel_id in panel_ids:
            panel = ui_layout.panel(ui, panel_id)
            if panel:
                control = panel.controls.itemById(command_id) or panel.controls.addCommand(definition)
                control.isPromoted = True
                if not editing:
                    _panel_id = panel_id
                break
        else:
            raise RuntimeError(f"Aucun panneau Fusion compatible pour « {name} ».")
    _log("Extension chargée dans le panneau {}".format(_panel_id))


def stop():
    global _panel_id, _custom_event, _custom_event_handler
    app, ui = _app_and_ui()
    for command_id, panel_ids in ((COMMAND_ID, PANEL_IDS), (EDIT_COMMAND_ID, (ui_layout.MODIFY_PANEL_ID,))):
        for panel_id in panel_ids:
            panel = ui_layout.panel(ui, panel_id)
            control = panel.controls.itemById(command_id) if panel else None
            if control:
                control.deleteMe()
        definition = ui.commandDefinitions.itemById(command_id)
        if definition:
            definition.deleteMe()
    if _custom_event and _custom_event_handler:
        _custom_event.remove(_custom_event_handler)
    if _custom_event:
        app.unregisterCustomEvent(CUSTOM_EVENT_ID)
    _pending_jobs.clear()
    _handlers.clear()
    _panel_id = None
    _custom_event = None
    _custom_event_handler = None
