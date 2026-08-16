from __future__ import annotations

import threading
import time
import traceback

import adsk.core
import adsk.fusion

from ..lib.member_builder import create_member
from ..lib.preview_graphics import PreviewManager
from ..lib import profile_catalog


COMMAND_ID = "EI_JHR_CreateStructuralMembersV1"
COMMAND_NAME = "Profil acier V1"
COMMAND_DESCRIPTION = "Crée le profil acier choisi sur chaque ligne ou arc d'esquisse sélectionné."
FAMILY_INPUT_ID = "profileFamily"
SECTION_INPUT_ID = "profileSection"
SELECTION_ID = "skeletonLines"
PANEL_IDS = ("SolidCreatePanel", "SolidScriptsAddinsPanel")
CUSTOM_EVENT_ID = "EI_JHR_CreateStructuralMembersV1_Deferred"

_handlers = []
_panel_id = None
_custom_event = None
_custom_event_handler = None
_pending_jobs = []


def _app_and_ui():
    app = adsk.core.Application.get()
    return app, app.userInterface


def _log(message):
    app, _ = _app_and_ui()
    app.log("[EI_JHR V1] {}".format(message))


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
    def notify(self, args):
        try:
            event_args = adsk.core.CommandCreatedEventArgs.cast(args)
            command = event_args.command
            command.isRepeatable = False
            inputs = command.commandInputs

            profiles = profile_catalog.discover_profiles()
            default_profile = profile_catalog.default_profile(profiles)
            family_input = inputs.addDropDownCommandInput(
                FAMILY_INPUT_ID,
                "Famille",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for family_id, family_label in profile_catalog.family_options(profiles):
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
                default_profile,
            )

            selection = inputs.addSelectionInput(
                SELECTION_ID,
                "Chemins du squelette",
                "Sélectionner une ou plusieurs lignes ou arcs d'esquisse dans le composant racine.",
            )
            selection.addSelectionFilter("SketchCurves")
            selection.setSelectionLimits(1, 0)
            inputs.addTextBoxCommandInput(
                "v1Info",
                "V1 technique",
                "Profil : famille et section au choix<br>Ancrage : C<br>Rotation : 0°<br>Chemins : lignes et arcs<br>Aperçu jaune dynamique<br>Un composant indépendant par chemin.",
                5,
                True,
            )

            preview_manager = PreviewManager()

            execute_handler = ExecuteHandler(preview_manager, profiles)
            command.execute.add(execute_handler)
            _handlers.append(execute_handler)

            preview_handler = ExecutePreviewHandler(preview_manager, profiles)
            command.executePreview.add(preview_handler)
            _handlers.append(preview_handler)

            input_changed_handler = InputChangedHandler(
                preview_manager,
                profiles,
                family_input,
                section_input,
            )
            command.inputChanged.add(input_changed_handler)
            _handlers.append(input_changed_handler)

            destroy_handler = DestroyHandler(preview_manager)
            command.destroy.add(destroy_handler)
            _handlers.append(destroy_handler)

            validate_handler = ValidateInputsHandler()
            command.validateInputs.add(validate_handler)
            _handlers.append(validate_handler)
            _log("Commande ouverte")
        except Exception:
            _, ui = _app_and_ui()
            ui.messageBox("Échec de la création de la commande:\n{}".format(traceback.format_exc()))


class ValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        event_args = adsk.core.ValidateInputsEventArgs.cast(args)
        selection = event_args.inputs.itemById(SELECTION_ID)
        event_args.areInputsValid = bool(selection and selection.selectionCount >= 1)


def _populate_section_input(section_input, profiles, family_id, selected_profile=None):
    section_input.listItems.clear()
    family_profiles = profile_catalog.profiles_for_family(profiles, family_id)
    for index, profile in enumerate(family_profiles):
        is_selected = (
            profile == selected_profile
            if selected_profile is not None
            else index == 0
        )
        section_input.listItems.add(profile.section_label, is_selected, "")


def _selected_profile(inputs, profiles):
    family_input = inputs.itemById(FAMILY_INPUT_ID)
    section_input = inputs.itemById(SECTION_INPUT_ID)
    if not family_input or not family_input.selectedItem:
        raise RuntimeError("Aucune famille de profil n'est sélectionnée.")
    if not section_input or not section_input.selectedItem:
        raise RuntimeError("Aucune section de profil n'est sélectionnée.")
    return profile_catalog.profile_from_labels(
        profiles,
        family_input.selectedItem.name,
        section_input.selectedItem.name,
    )


class InputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self, preview_manager, profiles, family_input, section_input):
        super().__init__()
        self._preview_manager = preview_manager
        self._profiles = profiles
        self._family_input = family_input
        self._section_input = section_input

    def notify(self, args):
        event_args = adsk.core.InputChangedEventArgs.cast(args)
        changed_input = event_args.input
        if not changed_input:
            return
        if changed_input.id == FAMILY_INPUT_ID:
            selected_family = self._family_input.selectedItem
            if selected_family:
                family_id = next(
                    family_id
                    for family_id, family_label in profile_catalog.family_options(self._profiles)
                    if family_label == selected_family.name
                )
                _populate_section_input(
                    self._section_input,
                    self._profiles,
                    family_id,
                )
        if changed_input.id in (FAMILY_INPUT_ID, SECTION_INPUT_ID):
            self._preview_manager.clear()


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
    def __init__(self, preview_manager, profiles):
        super().__init__()
        self._preview_manager = preview_manager
        self._profiles = profiles

    def notify(self, args):
        event_args = adsk.core.CommandEventArgs.cast(args)
        event_args.isValidResult = False
        try:
            app, _ = _app_and_ui()
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                self._preview_manager.clear()
                return
            selection = event_args.command.commandInputs.itemById(SELECTION_ID)
            curves = _supported_curves_from_selection(selection, design.rootComponent, strict=False)
            profile = _selected_profile(event_args.command.commandInputs, self._profiles)
            self._preview_manager.update(design.rootComponent, curves, profile)
        except Exception as error:
            self._preview_manager.clear()
            _log("APERÇU INDISPONIBLE: {}\n{}".format(error, traceback.format_exc()))


class DestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self, preview_manager):
        super().__init__()
        self._preview_manager = preview_manager

    def notify(self, args):
        self._preview_manager.clear()


class ExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self, preview_manager, profiles):
        super().__init__()
        self._preview_manager = preview_manager
        self._profiles = profiles

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
            selection = event_args.command.commandInputs.itemById(SELECTION_ID)
            curves = _supported_curves_from_selection(selection, root_component, strict=True)
            profile = _selected_profile(event_args.command.commandInputs, self._profiles)

            # L'API Fusion interdit l'import DXF depuis un événement de
            # commande. Le travail est donc mis en file puis exécuté par un
            # événement personnalisé lorsque Fusion redevient disponible.
            job = {
                "document": app.activeDocument,
                "design": design,
                "root_component": root_component,
                "curves": curves,
                "profile": profile,
            }
            _pending_jobs.append(job)
            worker = threading.Thread(
                target=_fire_deferred_event_from_worker,
                args=(app,),
                daemon=True,
            )
            worker.start()
            _log(
                "Import DXF {} planifié pour {} chemin(s)"
                .format(profile.designation, len(curves))
            )
        except Exception as error:
            event_args.executeFailed = True
            _log("ÉCHEC: {}\n{}".format(error, traceback.format_exc()))
            _, ui = _app_and_ui()
            ui.messageBox("La création a été annulée:\n{}".format(error))


class DeferredCreateHandler(adsk.core.CustomEventHandler):
    def notify(self, args):
        if not _pending_jobs:
            return

        job = _pending_jobs.pop(0)
        created_occurrences = []
        try:
            app, ui = _app_and_ui()
            if app.activeDocument != job["document"]:
                raise RuntimeError("Le document actif a changé avant l'import du DXF.")
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design or design != job["design"]:
                raise RuntimeError("La conception active a changé avant l'import du DXF.")

            for curve in job["curves"]:
                if not curve or not curve.isValid:
                    raise RuntimeError("Un chemin sélectionné n'est plus valide.")
                occurrence = create_member(job["root_component"], curve, job["profile"])
                created_occurrences.append(occurrence)
                _log("Composant créé depuis le DXF: {}".format(occurrence.component.name))

            ui.messageBox(
                "{} barre(s) {} créée(s) depuis le DXF."
                .format(len(created_occurrences), job["profile"].designation)
            )
        except Exception as error:
            for occurrence in reversed(created_occurrences):
                if occurrence and occurrence.isValid:
                    occurrence.deleteMe()
            _log("ÉCHEC IMPORT DXF: {}\n{}".format(error, traceback.format_exc()))
            _, ui = _app_and_ui()
            ui.messageBox("La création depuis le DXF a été annulée:\n{}".format(error))
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

    command_definition = ui.commandDefinitions.itemById(COMMAND_ID)
    if not command_definition:
        command_definition = ui.commandDefinitions.addButtonDefinition(
            COMMAND_ID,
            COMMAND_NAME,
            COMMAND_DESCRIPTION,
            "",
        )

    created_handler = CommandCreatedHandler()
    command_definition.commandCreated.add(created_handler)
    _handlers.append(created_handler)

    for panel_id in PANEL_IDS:
        panel = ui.allToolbarPanels.itemById(panel_id)
        if panel:
            control = panel.controls.itemById(COMMAND_ID)
            if not control:
                control = panel.controls.addCommand(command_definition)
            control.isPromoted = True
            _panel_id = panel_id
            break
    if not _panel_id:
        raise RuntimeError("Aucun panneau Fusion compatible n'a été trouvé pour ajouter la commande.")
    _log("Extension chargée dans le panneau {}".format(_panel_id))


def stop():
    global _panel_id, _custom_event, _custom_event_handler
    app, ui = _app_and_ui()
    for panel_id in PANEL_IDS:
        panel = ui.allToolbarPanels.itemById(panel_id)
        if panel:
            control = panel.controls.itemById(COMMAND_ID)
            if control:
                control.deleteMe()
    command_definition = ui.commandDefinitions.itemById(COMMAND_ID)
    if command_definition:
        command_definition.deleteMe()
    if _custom_event and _custom_event_handler:
        _custom_event.remove(_custom_event_handler)
    if _custom_event:
        app.unregisterCustomEvent(CUSTOM_EVENT_ID)
    _pending_jobs.clear()
    _handlers.clear()
    _panel_id = None
    _custom_event = None
    _custom_event_handler = None
