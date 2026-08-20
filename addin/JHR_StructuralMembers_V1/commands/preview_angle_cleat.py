from __future__ import annotations

import html
import traceback

import adsk.core
import adsk.fusion

from ..lib import addin_info, angle_cleat_builder, profile_catalog, ui_layout
from ..lib.angle_cleat_preview import DoubleAnglePreviewManager


COMMAND_ID = "EI_JHR_PreviewDoubleAngleCleatV1"
COMMAND_NAME = "Assemblage par cornières — aperçu V{}".format(addin_info.VERSION)
COMMAND_DESCRIPTION = (
    "Prévisualise deux cornières boulonnées de part et d'autre de l'âme secondaire."
)
PRIMARY_SELECTION_ID = "angleCleatPrimaryMember"
SECONDARY_SELECTION_ID = "angleCleatSecondaryMember"
ANGLE_PROFILE_ID = "angleCleatProfile"
CLEAT_HEIGHT_ID = "angleCleatHeight"
VERTICAL_OFFSET_ID = "angleCleatVerticalOffset"
REPORT_ID = "angleCleatReport"
PANEL_IDS = (ui_layout.ASSEMBLY_PANEL_ID,)


_handlers = []
_panel_id = None


def _app_and_ui():
    app = adsk.core.Application.get()
    return app, app.userInterface


def _log(message):
    app, _ = _app_and_ui()
    app.log("{} [ASSEMBLAGE_CORNIERES] {}".format(addin_info.LOG_PREFIX, message))


def _escaped(value):
    return html.escape(str(value), quote=True)


def _selected_occurrence(inputs, input_id, role):
    selection = inputs.itemById(input_id)
    if not selection or selection.selectionCount != 1:
        raise ValueError("Sélectionner une seule barre {}.".format(role))
    occurrence = adsk.fusion.Occurrence.cast(selection.selection(0).entity)
    if not occurrence or not occurrence.isValid:
        raise ValueError("La barre {} sélectionnée n'est pas valide.".format(role))
    return occurrence


def _selected_angle_profile(inputs, profiles):
    profile_input = adsk.core.DropDownCommandInput.cast(
        inputs.itemById(ANGLE_PROFILE_ID)
    )
    if not profile_input or not profile_input.selectedItem:
        raise ValueError("Sélectionner une section de cornière.")
    for profile in angle_cleat_builder.equal_angle_profiles(profiles):
        if profile.section_label == profile_input.selectedItem.name:
            return profile
    raise ValueError("La cornière sélectionnée n'existe plus dans la bibliothèque.")


def _height_value(inputs):
    value_input = inputs.itemById(CLEAT_HEIGHT_ID)
    if not value_input or not value_input.isValidExpression:
        raise ValueError("La hauteur des cornières n'est pas valide.")
    if value_input.value <= 0.0:
        raise ValueError("La hauteur des cornières doit être strictement positive.")
    return value_input.value


def _vertical_offset_value(inputs):
    value_input = inputs.itemById(VERTICAL_OFFSET_ID)
    if not value_input or not value_input.isValidExpression:
        raise ValueError("Le décalage vertical n'est pas valide.")
    return value_input.value


def _evaluate(inputs, profiles):
    app, _ = _app_and_ui()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        raise ValueError("Ouvrir une conception Fusion.")
    evaluation = angle_cleat_builder.evaluate_double_angle_preview(
        design=design,
        primary_occurrence=_selected_occurrence(
            inputs,
            PRIMARY_SELECTION_ID,
            "principale",
        ),
        secondary_occurrence=_selected_occurrence(
            inputs,
            SECONDARY_SELECTION_ID,
            "secondaire",
        ),
        angle_profile=_selected_angle_profile(inputs, profiles),
        cleat_height_cm=_height_value(inputs),
        vertical_offset_cm=_vertical_offset_value(inputs),
    )
    return design, evaluation


def _success_report(evaluation):
    rows = (
        ("Barre principale", evaluation.primary_occurrence.component.name),
        ("Profil principal", evaluation.primary_metadata.profile),
        ("Barre secondaire", evaluation.secondary_occurrence.component.name),
        ("Profil secondaire", evaluation.secondary_metadata.profile),
        ("Angle entre axes", "{:.2f}°".format(evaluation.geometry.angle_degrees)),
        ("Cornières", "2 × {}".format(evaluation.angle_profile.designation)),
        ("Hauteur", "{:.3f} mm".format(evaluation.cleat_height_cm * 10.0)),
        (
            "Décalage vertical",
            "{:.3f} mm".format(evaluation.vertical_offset_cm * 10.0),
        ),
        (
            "Épaisseur âme secondaire",
            "{:.3f} mm".format(
                evaluation.secondary_profile_geometry.web_max_x_mm
                - evaluation.secondary_profile_geometry.web_min_x_mm
            ),
        ),
    )
    content = [
        "<b>PHASE D'APERÇU UNIQUEMENT</b><br>",
        "Jaune : deux cornières issues du DXF sélectionné.<br>",
        "OK fermera ce test sans créer de pièce, trou ou boulon et sans modifier les barres.<br><br>",
    ]
    for label, value in rows:
        content.append("<b>{}</b> : {}<br>".format(_escaped(label), _escaped(value)))
    return "".join(content)


def _refresh(inputs, profiles, report_input, preview_manager):
    try:
        design, evaluation = _evaluate(inputs, profiles)
        report_input.formattedText = _success_report(evaluation)
        preview_manager.update(design.rootComponent, evaluation)
        return evaluation
    except Exception as error:
        preview_manager.clear()
        report_input.formattedText = (
            "<b>Aperçu non disponible</b><br>{}".format(_escaped(error))
        )
        return None


class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            event_args = adsk.core.CommandCreatedEventArgs.cast(args)
            command = event_args.command
            command.isRepeatable = False
            inputs = command.commandInputs
            profiles = profile_catalog.discover_profiles(include_custom=False)
            angle_profiles = angle_cleat_builder.equal_angle_profiles(profiles)
            default_profile = angle_cleat_builder.default_equal_angle_profile(profiles)
            preview_manager = DoubleAnglePreviewManager()

            primary = inputs.addSelectionInput(
                PRIMARY_SELECTION_ID,
                "Barre principale",
                "Sélectionner l'IPE, HEA ou HEB dont l'âme reçoit les cornières.",
            )
            primary.addSelectionFilter("Occurrences")
            primary.setSelectionLimits(0, 1)

            secondary = inputs.addSelectionInput(
                SECONDARY_SELECTION_ID,
                "Barre secondaire",
                "Sélectionner l'IPE, HEA ou HEB grugé entre les deux cornières.",
            )
            secondary.addSelectionFilter("Occurrences")
            secondary.setSelectionLimits(0, 1)

            angle_input = inputs.addDropDownCommandInput(
                ANGLE_PROFILE_ID,
                "Section des cornières",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for profile in angle_profiles:
                angle_input.listItems.add(
                    profile.section_label,
                    profile == default_profile,
                    "",
                )

            height = inputs.addValueInput(
                CLEAT_HEIGHT_ID,
                "Hauteur des cornières",
                "mm",
                adsk.core.ValueInput.createByString("100 mm"),
            )
            height.minimumValue = 0.0
            height.isMinimumInclusive = False

            inputs.addValueInput(
                VERTICAL_OFFSET_ID,
                "Décalage vertical",
                "mm",
                adsk.core.ValueInput.createByString("0 mm"),
            )

            report = inputs.addTextBoxCommandInput(
                REPORT_ID,
                "Contrôle",
                "Sélectionner la principale puis la secondaire.",
                12,
                True,
            )

            input_changed = InputChangedHandler(
                profiles,
                report,
                preview_manager,
            )
            command.inputChanged.add(input_changed)
            _handlers.append(input_changed)

            validate = ValidateInputsHandler(profiles, report, preview_manager)
            command.validateInputs.add(validate)
            _handlers.append(validate)

            execute_preview = ExecutePreviewHandler(
                profiles,
                report,
                preview_manager,
            )
            command.executePreview.add(execute_preview)
            _handlers.append(execute_preview)

            execute = ExecuteHandler(profiles, preview_manager)
            command.execute.add(execute)
            _handlers.append(execute)

            destroy = DestroyHandler(preview_manager)
            command.destroy.add(destroy)
            _handlers.append(destroy)
            _log("Commande d'aperçu ouverte")
        except Exception:
            _, ui = _app_and_ui()
            ui.messageBox(
                "Échec de l'ouverture de l'aperçu d'assemblage:\n{}"
                .format(traceback.format_exc())
            )


class InputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self, profiles, report_input, preview_manager):
        super().__init__()
        self._profiles = profiles
        self._report_input = report_input
        self._preview_manager = preview_manager

    def notify(self, args):
        event_args = adsk.core.InputChangedEventArgs.cast(args)
        changed = event_args.input
        if changed and changed.id in (
            PRIMARY_SELECTION_ID,
            SECONDARY_SELECTION_ID,
            ANGLE_PROFILE_ID,
            CLEAT_HEIGHT_ID,
            VERTICAL_OFFSET_ID,
        ):
            _refresh(
                event_args.inputs,
                self._profiles,
                self._report_input,
                self._preview_manager,
            )


class ValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self, profiles, report_input, preview_manager):
        super().__init__()
        self._profiles = profiles
        self._report_input = report_input
        self._preview_manager = preview_manager

    def notify(self, args):
        event_args = adsk.core.ValidateInputsEventArgs.cast(args)
        event_args.areInputsValid = (
            _refresh(
                event_args.inputs,
                self._profiles,
                self._report_input,
                self._preview_manager,
            )
            is not None
        )


class ExecutePreviewHandler(adsk.core.CommandEventHandler):
    def __init__(self, profiles, report_input, preview_manager):
        super().__init__()
        self._profiles = profiles
        self._report_input = report_input
        self._preview_manager = preview_manager

    def notify(self, args):
        event_args = adsk.core.CommandEventArgs.cast(args)
        event_args.isValidResult = False
        _refresh(
            event_args.command.commandInputs,
            self._profiles,
            self._report_input,
            self._preview_manager,
        )


class ExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self, profiles, preview_manager):
        super().__init__()
        self._profiles = profiles
        self._preview_manager = preview_manager

    def notify(self, args):
        event_args = adsk.core.CommandEventArgs.cast(args)
        try:
            _, evaluation = _evaluate(
                event_args.command.commandInputs,
                self._profiles,
            )
            self._preview_manager.clear()
            _log(
                "Aperçu validé sans création : principale={}, secondaire={}, cornière={}, hauteur={} mm"
                .format(
                    evaluation.primary_occurrence.component.name,
                    evaluation.secondary_occurrence.component.name,
                    evaluation.angle_profile.designation,
                    evaluation.cleat_height_cm * 10.0,
                )
            )
            _, ui = _app_and_ui()
            ui.messageBox(
                "Aperçu validé.\n\n"
                "Cette phase n'a créé aucune pièce, aucun trou et aucun boulon."
            )
        except Exception as error:
            event_args.executeFailed = True
            _log("ÉCHEC: {}\n{}".format(error, traceback.format_exc()))
            _, ui = _app_and_ui()
            ui.messageBox("L'aperçu a été annulé :\n{}".format(error))


class DestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self, preview_manager):
        super().__init__()
        self._preview_manager = preview_manager

    def notify(self, args):
        self._preview_manager.clear()


def start():
    global _panel_id
    _, ui = _app_and_ui()
    definition = ui.commandDefinitions.itemById(COMMAND_ID)
    if not definition:
        definition = ui.commandDefinitions.addButtonDefinition(
            COMMAND_ID,
            COMMAND_NAME,
            COMMAND_DESCRIPTION,
            "",
        )
    created_handler = CommandCreatedHandler()
    definition.commandCreated.add(created_handler)
    _handlers.append(created_handler)

    for panel_id in PANEL_IDS:
        panel = ui_layout.panel(ui, panel_id)
        if panel:
            control = panel.controls.itemById(COMMAND_ID)
            if not control:
                control = panel.controls.addCommand(definition)
            control.isPromoted = True
            _panel_id = panel_id
            break
    if not _panel_id:
        raise RuntimeError("Le groupe Assemblages de STRUCTURE JHR est introuvable.")
    _log("Commande chargée dans le panneau {}".format(_panel_id))


def stop():
    global _panel_id
    _, ui = _app_and_ui()
    for panel_id in PANEL_IDS:
        panel = ui_layout.panel(ui, panel_id)
        if panel:
            control = panel.controls.itemById(COMMAND_ID)
            if control:
                control.deleteMe()
    definition = ui.commandDefinitions.itemById(COMMAND_ID)
    if definition:
        definition.deleteMe()
    _handlers.clear()
    _panel_id = None
