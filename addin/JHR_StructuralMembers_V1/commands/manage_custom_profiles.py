from __future__ import annotations

import html
import traceback
from pathlib import Path

import adsk.core
import adsk.fusion

from ..lib import addin_info, custom_profiles, member_metadata, profile_catalog


COMMAND_ID = "EI_JHR_ManageCustomProfilesV1"
COMMAND_NAME = "Gérer les profils personnalisés V{}".format(addin_info.VERSION)
COMMAND_DESCRIPTION = "Ajoute ou retire de manière récupérable un profil DXF personnel."
ACTION_INPUT_ID = "customProfileAction"
ACTION_ADD = "Ajouter un profil DXF"
ACTION_DELETE = "Supprimer un profil"
FAMILY_INPUT_ID = "customFamily"
DESIGNATION_INPUT_ID = "customDesignation"
UNITS_INPUT_ID = "customUnitsConfirmed"
CHOOSE_FILE_INPUT_ID = "customChooseFile"
FILE_REPORT_INPUT_ID = "customFileReport"
DELETE_PROFILE_INPUT_ID = "customDeleteProfile"
DELETE_REPORT_INPUT_ID = "customDeleteReport"
PANEL_IDS = ("SolidCreatePanel", "SolidScriptsAddinsPanel")

_handlers = []
_panel_id = None


def _app_and_ui():
    app = adsk.core.Application.get()
    return app, app.userInterface


def _log(message):
    app, _ = _app_and_ui()
    app.log("{} [PROFILS PERSONNALISÉS] {}".format(addin_info.LOG_PREFIX, message))


def _escaped(value):
    return html.escape(str(value), quote=True)


def _action_name(inputs):
    action_input = inputs.itemById(ACTION_INPUT_ID)
    if not action_input or not action_input.selectedItem:
        return ""
    return action_input.selectedItem.name


def _custom_profile_choices():
    profiles = profile_catalog.discover_profiles()
    custom = [
        profile
        for profile in profiles
        if profile.category_id == custom_profiles.CATEGORY_ID
    ]
    choices = {}
    for profile in custom:
        label = "{} — {}".format(profile.designation, profile.dxf_path.name)
        if label in choices:
            label = "{} — {}".format(label, profile.relative_path)
        choices[label] = profile
    return choices


def _active_reference_count(relative_path):
    app, _ = _app_and_ui()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        return 0
    count = 0
    for occurrence in design.rootComponent.allOccurrences:
        component = occurrence.component
        category = component.attributes.itemByName(
            member_metadata.ATTRIBUTE_GROUP,
            "profile_category",
        )
        source = component.attributes.itemByName(
            member_metadata.ATTRIBUTE_GROUP,
            "profile_source",
        )
        if (
            category
            and category.value == custom_profiles.CATEGORY_ID
            and source
            and source.value.replace("\\", "/") == relative_path
        ):
            count += 1
    return count


class CommandState:
    def __init__(self, delete_choices):
        self.selected_path = None
        self.analysis = None
        self.delete_choices = delete_choices
        self.is_updating = False

    def clear_file(self):
        self.selected_path = None
        self.analysis = None


def _set_action_visibility(inputs):
    is_add = _action_name(inputs) == ACTION_ADD
    for input_id in (
        FAMILY_INPUT_ID,
        DESIGNATION_INPUT_ID,
        UNITS_INPUT_ID,
        CHOOSE_FILE_INPUT_ID,
        FILE_REPORT_INPUT_ID,
    ):
        command_input = inputs.itemById(input_id)
        if command_input:
            command_input.isVisible = is_add
    for input_id in (DELETE_PROFILE_INPUT_ID, DELETE_REPORT_INPUT_ID):
        command_input = inputs.itemById(input_id)
        if command_input:
            command_input.isVisible = not is_add


def _selected_delete_profile(inputs, state):
    profile_input = inputs.itemById(DELETE_PROFILE_INPUT_ID)
    if not profile_input or not profile_input.selectedItem:
        return None
    return state.delete_choices.get(profile_input.selectedItem.name)


def _update_delete_report(inputs, state):
    report = inputs.itemById(DELETE_REPORT_INPUT_ID)
    if not report:
        return
    profile = _selected_delete_profile(inputs, state)
    if not profile:
        report.formattedText = (
            "<b>Aucun profil personnalisé disponible.</b><br>"
            "Ajouter d'abord un DXF personnel."
        )
        return
    references = _active_reference_count(profile.relative_path)
    report.formattedText = (
        "<b>{}</b><br>"
        "Fichier : {}<br>"
        "Utilisé par {} barre(s) dans le document actif.<br>"
        "La suppression le déplacera dans la corbeille locale."
    ).format(
        _escaped(profile.designation),
        _escaped(profile.dxf_path.name),
        references,
    )


class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            event_args = adsk.core.CommandCreatedEventArgs.cast(args)
            command = event_args.command
            command.isRepeatable = False
            inputs = command.commandInputs
            delete_choices = _custom_profile_choices()
            state = CommandState(delete_choices)

            action_input = inputs.addDropDownCommandInput(
                ACTION_INPUT_ID,
                "Action",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            action_input.listItems.add(ACTION_ADD, True, "")
            action_input.listItems.add(ACTION_DELETE, False, "")

            inputs.addStringValueInput(
                FAMILY_INPUT_ID,
                "Famille personnalisée",
                "Mes profils",
            )
            inputs.addStringValueInput(
                DESIGNATION_INPUT_ID,
                "Désignation du profil",
                "",
            )
            units_input = inputs.addBoolValueInput(
                UNITS_INPUT_ID,
                "Je confirme que le DXF est dessiné en millimètres",
                True,
                "",
                False,
            )
            units_input.tooltip = (
                "Le DXF R12 ne contient pas d'unité fiable. "
                "Cette première version accepte uniquement les millimètres."
            )
            inputs.addBoolValueInput(
                CHOOSE_FILE_INPUT_ID,
                "Choisir et analyser un fichier DXF",
                False,
                "",
                False,
            )
            inputs.addTextBoxCommandInput(
                FILE_REPORT_INPUT_ID,
                "Contrôle du DXF",
                "Aucun fichier sélectionné.",
                6,
                True,
            )

            delete_input = inputs.addDropDownCommandInput(
                DELETE_PROFILE_INPUT_ID,
                "Profil personnalisé",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for index, label in enumerate(delete_choices):
                delete_input.listItems.add(label, index == 0, "")
            inputs.addTextBoxCommandInput(
                DELETE_REPORT_INPUT_ID,
                "Suppression récupérable",
                "",
                5,
                True,
            )

            _set_action_visibility(inputs)
            _update_delete_report(inputs, state)

            changed_handler = InputChangedHandler(state)
            command.inputChanged.add(changed_handler)
            _handlers.append(changed_handler)

            validate_handler = ValidateInputsHandler(state)
            command.validateInputs.add(validate_handler)
            _handlers.append(validate_handler)

            execute_handler = ExecuteHandler(state)
            command.execute.add(execute_handler)
            _handlers.append(execute_handler)
            _log("Gestionnaire ouvert")
        except Exception:
            _, ui = _app_and_ui()
            ui.messageBox(
                "Échec de l'ouverture des profils personnalisés:\n{}"
                .format(traceback.format_exc())
            )


class InputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self, state):
        super().__init__()
        self._state = state

    def notify(self, args):
        if self._state.is_updating:
            return
        try:
            event_args = adsk.core.InputChangedEventArgs.cast(args)
            changed = event_args.input
            if not changed:
                return
            if changed.id == ACTION_INPUT_ID:
                _set_action_visibility(event_args.inputs)
                _update_delete_report(event_args.inputs, self._state)
                return
            if changed.id == DELETE_PROFILE_INPUT_ID:
                _update_delete_report(event_args.inputs, self._state)
                return
            if changed.id != CHOOSE_FILE_INPUT_ID or not changed.value:
                return

            self._state.is_updating = True
            try:
                changed.value = False
                _, ui = _app_and_ui()
                dialog = ui.createFileDialog()
                dialog.isMultiSelectEnabled = False
                dialog.title = "Choisir un profil personnalisé DXF R12"
                dialog.filter = "Fichiers DXF (*.dxf)"
                if dialog.showOpen() != adsk.core.DialogResults.DialogOK:
                    return
                selected_path = Path(dialog.filename)
                try:
                    analysis = custom_profiles.validate_dxf(selected_path)
                except Exception as error:
                    self._state.clear_file()
                    report = event_args.inputs.itemById(FILE_REPORT_INPUT_ID)
                    report.formattedText = "<b>DXF refusé</b><br>{}".format(
                        _escaped(error)
                    )
                    ui.messageBox("Le profil n'a pas été ajouté:\n{}".format(error))
                    return
                self._state.selected_path = selected_path
                self._state.analysis = analysis
                designation = event_args.inputs.itemById(DESIGNATION_INPUT_ID)
                if designation and not designation.value.strip():
                    designation.value = selected_path.stem.replace("_", " ")
                report = event_args.inputs.itemById(FILE_REPORT_INPUT_ID)
                report.formattedText = (
                    "<b>DXF compatible</b><br>"
                    "Fichier : {}<br>"
                    "Dimensions : {:.6g} × {:.6g} mm<br>"
                    "Contours fermés : {}<br>"
                    "Entités prises en charge : {}"
                ).format(
                    _escaped(selected_path.name),
                    analysis.width_mm,
                    analysis.height_mm,
                    analysis.contour_count,
                    analysis.entity_count,
                )
            finally:
                self._state.is_updating = False
        except Exception:
            _, ui = _app_and_ui()
            ui.messageBox(
                "Échec de l'analyse du DXF:\n{}".format(traceback.format_exc())
            )


class ValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self, state):
        super().__init__()
        self._state = state

    def notify(self, args):
        event_args = adsk.core.ValidateInputsEventArgs.cast(args)
        inputs = event_args.inputs
        if _action_name(inputs) == ACTION_ADD:
            family = inputs.itemById(FAMILY_INPUT_ID)
            designation = inputs.itemById(DESIGNATION_INPUT_ID)
            units = inputs.itemById(UNITS_INPUT_ID)
            event_args.areInputsValid = bool(
                self._state.analysis
                and family
                and family.value.strip()
                and designation
                and designation.value.strip()
                and units
                and units.value
            )
            return
        event_args.areInputsValid = _selected_delete_profile(inputs, self._state) is not None


class ExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self, state):
        super().__init__()
        self._state = state

    def notify(self, args):
        event_args = adsk.core.CommandEventArgs.cast(args)
        try:
            inputs = event_args.command.commandInputs
            _, ui = _app_and_ui()
            if _action_name(inputs) == ACTION_ADD:
                family = inputs.itemById(FAMILY_INPUT_ID).value
                designation = inputs.itemById(DESIGNATION_INPUT_ID).value
                imported = custom_profiles.import_profile(
                    self._state.selected_path,
                    family,
                    designation,
                )
                ui.messageBox(
                    "Le profil personnalisé '{} {}' a été ajouté.\n\n"
                    "Dimensions : {:.6g} × {:.6g} mm\n"
                    "Fermer puis rouvrir Profil acier pour le sélectionner."
                    .format(
                        imported.record.family_label,
                        imported.record.section_label,
                        imported.analysis.width_mm,
                        imported.analysis.height_mm,
                    )
                )
                _log("Profil ajouté: {}".format(imported.record.relative_path))
                return

            profile = _selected_delete_profile(inputs, self._state)
            if not profile:
                raise RuntimeError("Aucun profil personnalisé n'est sélectionné.")
            references = _active_reference_count(profile.relative_path)
            warning = (
                "Supprimer '{}' de la bibliothèque personnalisée ?\n\n"
                "Le DXF sera déplacé dans une corbeille locale récupérable."
                .format(profile.designation)
            )
            if references:
                warning += (
                    "\n\nAttention : {} barre(s) du document actif utilisent ce profil. "
                    "Leur géométrie restera présente, mais leur DXF source ne sera plus disponible."
                    .format(references)
                )
            answer = ui.messageBox(
                warning,
                "Confirmer la suppression",
                adsk.core.MessageBoxButtonTypes.YesNoButtonType,
                adsk.core.MessageBoxIconTypes.WarningIconType,
            )
            if answer != adsk.core.DialogResults.DialogYes:
                _log("Suppression annulée par l'utilisateur")
                return
            deleted = custom_profiles.delete_profile(
                profile.relative_path,
                active_reference_count=references,
            )
            ui.messageBox(
                "Le profil '{}' a été retiré de la bibliothèque.\n"
                "Une copie récupérable est conservée dans la corbeille locale."
                .format(profile.designation)
            )
            _log("Profil déplacé vers la corbeille: {}".format(deleted.relative_path))
        except Exception as error:
            event_args.executeFailed = True
            _log("ÉCHEC: {}\n{}".format(error, traceback.format_exc()))
            _, ui = _app_and_ui()
            ui.messageBox("L'opération a été annulée:\n{}".format(error))


def start():
    global _panel_id
    _, ui = _app_and_ui()
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
        raise RuntimeError(
            "Aucun panneau Fusion compatible n'a été trouvé pour gérer les profils."
        )
    _log("Commande chargée dans le panneau {}".format(_panel_id))


def stop():
    global _panel_id
    _, ui = _app_and_ui()
    for panel_id in PANEL_IDS:
        panel = ui.allToolbarPanels.itemById(panel_id)
        if panel:
            control = panel.controls.itemById(COMMAND_ID)
            if control:
                control.deleteMe()
    command_definition = ui.commandDefinitions.itemById(COMMAND_ID)
    if command_definition:
        command_definition.deleteMe()
    _handlers.clear()
    _panel_id = None
