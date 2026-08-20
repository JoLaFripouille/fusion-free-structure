from __future__ import annotations

import traceback

import adsk.core

from ..lib import addin_info, default_settings, ui_layout


COMMAND_ID = "EI_JHR_ManageStructuralSettingsV1"
COMMAND_NAME = "Paramètres Structure JHR V{}".format(addin_info.VERSION)
COMMAND_DESCRIPTION = "Règle et mémorise les valeurs par défaut des opérations acier."
DEFAULTS_TAB_ID = "structuralDefaultValuesTab"
PANEL_IDS = (ui_layout.SETTINGS_PANEL_ID,)

STRAIGHT_IH_GAP_ID = "defaultStraightIhGap"
STRAIGHT_LT_GAP_ID = "defaultStraightLtGap"
STRAIGHT_HOLLOW_GAP_ID = "defaultStraightHollowGap"
STRAIGHT_OTHER_GAP_ID = "defaultStraightOtherGap"
COPE_IH_VERTICAL_ID = "defaultCopeIhVertical"
COPE_IH_LONGITUDINAL_ID = "defaultCopeIhLongitudinal"
COPE_IH_SUPPORT_ID = "defaultCopeIhSupport"
COPE_LT_UNDER_WEB_ID = "defaultCopeLtUnderWeb"
COPE_LT_ROOT_RELIEF_ID = "defaultCopeLtRootRelief"
COPE_LT_LONGITUDINAL_ID = "defaultCopeLtLongitudinal"
COPE_LT_SUPPORT_ID = "defaultCopeLtSupport"

VALUE_INPUT_IDS = (
    STRAIGHT_IH_GAP_ID,
    STRAIGHT_LT_GAP_ID,
    STRAIGHT_HOLLOW_GAP_ID,
    STRAIGHT_OTHER_GAP_ID,
    COPE_IH_VERTICAL_ID,
    COPE_IH_LONGITUDINAL_ID,
    COPE_IH_SUPPORT_ID,
    COPE_LT_UNDER_WEB_ID,
    COPE_LT_ROOT_RELIEF_ID,
    COPE_LT_LONGITUDINAL_ID,
    COPE_LT_SUPPORT_ID,
)


_handlers = []
_panel_id = None


def _app_and_ui():
    app = adsk.core.Application.get()
    return app, app.userInterface


def _log(message):
    app, _ = _app_and_ui()
    app.log("{} [PARAMÈTRES] {}".format(addin_info.LOG_PREFIX, message))


def _add_distance(inputs, input_id, label, value_mm):
    command_input = inputs.addValueInput(
        input_id,
        label,
        "mm",
        adsk.core.ValueInput.createByString("{:.9g} mm".format(value_mm)),
    )
    command_input.minimumValue = 0.0
    command_input.isMinimumInclusive = True
    return command_input


def _input_by_id(inputs, input_id):
    direct = inputs.itemById(input_id)
    if direct:
        return direct
    for index in range(inputs.count):
        command_input = inputs.item(index)
        container = adsk.core.TabCommandInput.cast(command_input)
        if not container:
            container = adsk.core.GroupCommandInput.cast(command_input)
        if container:
            nested = _input_by_id(container.children, input_id)
            if nested:
                return nested
    return None


def _distance_mm(inputs, input_id, label):
    command_input = _input_by_id(inputs, input_id)
    if not command_input or not command_input.isValidExpression:
        raise ValueError("{} n'est pas une distance valide.".format(label))
    if command_input.value < 0.0:
        raise ValueError("{} ne peut pas être négatif.".format(label))
    return float(command_input.value) / default_settings.MM_TO_CM


def _values_from_inputs(inputs):
    return default_settings.DefaultValues(
        straight_joint_ih_gap_mm=_distance_mm(
            inputs, STRAIGHT_IH_GAP_ID, "Le jeu de jonction I/H"
        ),
        straight_joint_lt_gap_mm=_distance_mm(
            inputs, STRAIGHT_LT_GAP_ID, "Le jeu de jonction cornières/T"
        ),
        straight_joint_hollow_gap_mm=_distance_mm(
            inputs, STRAIGHT_HOLLOW_GAP_ID, "Le jeu de jonction tubes"
        ),
        straight_joint_other_gap_mm=_distance_mm(
            inputs, STRAIGHT_OTHER_GAP_ID, "Le jeu de jonction autres profils"
        ),
        cope_ih_vertical_mm=_distance_mm(
            inputs, COPE_IH_VERTICAL_ID, "Le jeu vertical I/H"
        ),
        cope_ih_longitudinal_mm=_distance_mm(
            inputs, COPE_IH_LONGITUDINAL_ID, "Le jeu longitudinal I/H"
        ),
        cope_ih_support_mm=_distance_mm(
            inputs, COPE_IH_SUPPORT_ID, "Le jeu contre l'appui I/H"
        ),
        cope_lt_under_web_mm=_distance_mm(
            inputs, COPE_LT_UNDER_WEB_ID, "Le jeu sous l'âme cornières/T"
        ),
        cope_lt_root_relief_mm=_distance_mm(
            inputs, COPE_LT_ROOT_RELIEF_ID, "Le jeu autour du congé cornières/T"
        ),
        cope_lt_longitudinal_mm=_distance_mm(
            inputs, COPE_LT_LONGITUDINAL_ID, "Le jeu longitudinal cornières/T"
        ),
        cope_lt_support_mm=_distance_mm(
            inputs, COPE_LT_SUPPORT_ID, "Le jeu contre l'appui cornières/T"
        ),
    )


class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            event_args = adsk.core.CommandCreatedEventArgs.cast(args)
            command = event_args.command
            command.isRepeatable = False
            inputs = command.commandInputs
            values, warning = default_settings.load_or_factory()

            tab = inputs.addTabCommandInput(
                DEFAULTS_TAB_ID,
                "Valeurs par défaut",
            )
            children = tab.children
            message = (
                "Ces valeurs seront proposées à la prochaine ouverture des commandes. "
                "Elles restent modifiables pour chaque opération."
            )
            if warning:
                message += (
                    "\n\nAttention : {} Les valeurs d'usine sont affichées ; "
                    "OK remplacera le fichier invalide."
                ).format(warning)
            children.addTextBoxCommandInput(
                "defaultValuesInformation",
                "",
                message,
                4 if warning else 3,
                True,
            )

            straight_group = children.addGroupCommandInput(
                "straightJointDefaultsGroup",
                "Jonction ajustée — jeu",
            )
            straight = straight_group.children
            _add_distance(
                straight,
                STRAIGHT_IH_GAP_ID,
                "IPE / HEA / HEB",
                values.straight_joint_ih_gap_mm,
            )
            _add_distance(
                straight,
                STRAIGHT_LT_GAP_ID,
                "Cornières / Tés",
                values.straight_joint_lt_gap_mm,
            )
            _add_distance(
                straight,
                STRAIGHT_HOLLOW_GAP_ID,
                "Tubes",
                values.straight_joint_hollow_gap_mm,
            )
            _add_distance(
                straight,
                STRAIGHT_OTHER_GAP_ID,
                "IPN / UPN / UPE / personnalisés",
                values.straight_joint_other_gap_mm,
            )

            miter_group = children.addGroupCommandInput(
                "miterDefaultsGroup",
                "Coupe d'onglet",
            )
            miter_group.children.addTextBoxCommandInput(
                "miterDefaultsInformation",
                "",
                "Aucune valeur réglable pour le moment.",
                1,
                True,
            )

            cope_ih_group = children.addGroupCommandInput(
                "copeIhDefaultsGroup",
                "Grugeage IPE / HEA / HEB",
            )
            cope_ih = cope_ih_group.children
            _add_distance(
                cope_ih,
                COPE_IH_VERTICAL_ID,
                "Jeu vertical",
                values.cope_ih_vertical_mm,
            )
            _add_distance(
                cope_ih,
                COPE_IH_LONGITUDINAL_ID,
                "Jeu longitudinal",
                values.cope_ih_longitudinal_mm,
            )
            _add_distance(
                cope_ih,
                COPE_IH_SUPPORT_ID,
                "Jeu contre l'appui",
                values.cope_ih_support_mm,
            )

            cope_lt_group = children.addGroupCommandInput(
                "copeLtDefaultsGroup",
                "Grugeage cornières / Tés",
            )
            cope_lt = cope_lt_group.children
            _add_distance(
                cope_lt,
                COPE_LT_UNDER_WEB_ID,
                "Jeu sous l'âme secondaire",
                values.cope_lt_under_web_mm,
            )
            _add_distance(
                cope_lt,
                COPE_LT_ROOT_RELIEF_ID,
                "Jeu autour du congé principal",
                values.cope_lt_root_relief_mm,
            )
            _add_distance(
                cope_lt,
                COPE_LT_LONGITUDINAL_ID,
                "Jeu longitudinal",
                values.cope_lt_longitudinal_mm,
            )
            _add_distance(
                cope_lt,
                COPE_LT_SUPPORT_ID,
                "Jeu contre l'appui",
                values.cope_lt_support_mm,
            )

            validate = ValidateInputsHandler()
            command.validateInputs.add(validate)
            _handlers.append(validate)

            execute = ExecuteHandler()
            command.execute.add(execute)
            _handlers.append(execute)
            _log("Fenêtre ouverte")
        except Exception:
            _, ui = _app_and_ui()
            ui.messageBox(
                "Échec de l'ouverture des paramètres :\n{}".format(
                    traceback.format_exc()
                )
            )


class ValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        event_args = adsk.core.ValidateInputsEventArgs.cast(args)
        try:
            _values_from_inputs(event_args.inputs)
            event_args.areInputsValid = True
        except ValueError:
            event_args.areInputsValid = False


class ExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        event_args = adsk.core.CommandEventArgs.cast(args)
        try:
            path = default_settings.save(
                _values_from_inputs(event_args.command.commandInputs)
            )
            _log("Valeurs enregistrées dans {}".format(path))
        except Exception as error:
            event_args.executeFailed = True
            _log("ÉCHEC: {}\n{}".format(error, traceback.format_exc()))
            _, ui = _app_and_ui()
            ui.messageBox(
                "Les paramètres n'ont pas été enregistrés :\n{}".format(error)
            )


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
        raise RuntimeError("Le groupe Paramètres de STRUCTURE JHR est introuvable.")
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
