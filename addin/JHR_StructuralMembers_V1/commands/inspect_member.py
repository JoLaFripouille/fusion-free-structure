from __future__ import annotations

import html
import traceback

import adsk.core
import adsk.fusion

from ..lib import addin_info, anchors, member_metadata, profile_catalog


COMMAND_ID = "EI_JHR_InspectStructuralMemberV1"
COMMAND_NAME = "Inspecter un profil acier V{}".format(addin_info.VERSION)
COMMAND_DESCRIPTION = "Affiche les réglages enregistrés dans une barre créée par l'extension."
SELECTION_ID = "memberOccurrence"
REPORT_ID = "memberReport"
PANEL_IDS = ("SolidCreatePanel", "SolidScriptsAddinsPanel")

ATTRIBUTE_KEYS = (
    "profile",
    "profile_category",
    "profile_region",
    "profile_family",
    "profile_source",
    "steel_grade",
    "material_name",
    "material_id",
    "material_library_name",
    "material_library_id",
    "material_source_id",
    "material_property_count",
    "anchor",
    "rotation_deg",
    "flip_x",
    "flip_y",
    "source_curve_token",
    "source_line_token",
    "source_curve_type",
    "extension_version",
)

_handlers = []
_panel_id = None


def _app_and_ui():
    app = adsk.core.Application.get()
    return app, app.userInterface


def _log(message):
    app, _ = _app_and_ui()
    app.log("{} [INSPECTION] {}".format(addin_info.LOG_PREFIX, message))


def _attribute_values(component):
    values = {}
    for key in ATTRIBUTE_KEYS:
        attribute = component.attributes.itemByName(member_metadata.ATTRIBUTE_GROUP, key)
        if attribute:
            values[key] = attribute.value
    return values


def _selected_occurrence(inputs):
    selection = inputs.itemById(SELECTION_ID)
    if not selection or selection.selectionCount != 1:
        raise ValueError("Sélectionner une seule barre créée par l'extension.")
    occurrence = adsk.fusion.Occurrence.cast(selection.selection(0).entity)
    if not occurrence or not occurrence.isValid:
        raise ValueError("La sélection n'est pas un composant valide.")
    return occurrence


def _read_member(inputs):
    occurrence = _selected_occurrence(inputs)
    values = _attribute_values(occurrence.component)
    return occurrence, member_metadata.parse_member_attributes(values)


def _linked_curve(design, metadata):
    entities = design.findEntityByToken(metadata.source_curve_token)
    for entity in entities:
        curve = adsk.fusion.SketchLine.cast(entity) or adsk.fusion.SketchArc.cast(entity)
        if curve and curve.isValid:
            return curve
    return None


def _yes_no(value):
    return "Oui" if value else "Non"


def _escaped(value):
    return html.escape(str(value), quote=True)


def _physical_material_status(occurrence, metadata):
    bodies = occurrence.component.bRepBodies
    if bodies.count != 1:
        return (
            "Indisponible",
            "Attention — le composant ne contient pas un corps unique",
            "Indisponible",
        )
    body = bodies.item(0)
    material = body.material
    if not material or not material.isValid:
        return (
            "Aucun",
            "Attention — aucun matériau physique n'est lu sur le corps",
            "0",
        )
    properties = material.materialProperties
    property_count = int(properties.count) if properties else 0
    if not metadata.has_physical_material_metadata:
        status = "Non vérifiable — barre créée sans identifiant de matériau enregistré"
    elif str(material.id) == metadata.material_id:
        status = "OK — l'identifiant relu sur le corps correspond"
    else:
        status = "Attention — le matériau du corps a changé depuis la création"
    return material.name, status, str(property_count)


def _report_html(occurrence, metadata, design):
    linked_curve = _linked_curve(design, metadata)
    source_dxf = profile_catalog.resolve_profile_source(
        metadata.profile_source,
        addin_info.ADDIN_ROOT,
    )
    if linked_curve:
        curve_label = "Arc" if adsk.fusion.SketchArc.cast(linked_curve) else "Ligne"
        link_status = "OK — {} du squelette retrouvée".format(curve_label)
    else:
        link_status = "Attention — chemin du squelette introuvable"
    actual_material_name, material_status, actual_property_count = (
        _physical_material_status(occurrence, metadata)
    )
    recorded_library = metadata.material_library_name or "Non enregistrée"
    recorded_properties = (
        str(metadata.material_property_count)
        if metadata.has_physical_material_metadata
        else "Non enregistrées"
    )

    rows = (
        ("Composant", occurrence.component.name),
        ("Profil", metadata.profile),
        ("Catégorie", profile_catalog.category_label(metadata.profile_category)),
        ("Zone géographique", metadata.profile_region),
        ("Famille", metadata.profile_family),
        ("DXF source", metadata.profile_source),
        ("DXF disponible", _yes_no(source_dxf.is_file())),
        ("Matériau enregistré", metadata.material_name),
        ("Bibliothèque source", recorded_library),
        ("Matériau lu sur le corps", actual_material_name),
        ("Affectation physique", material_status),
        (
            "Propriétés physiques",
            "{} lue(s) — {} à la création".format(
                actual_property_count,
                recorded_properties,
            ),
        ),
        ("Ancrage", "{} — {}".format(metadata.anchor, anchors.label(metadata.anchor))),
        ("Rotation", "{}°".format(member_metadata.format_rotation_degrees(metadata.rotation_deg))),
        ("Miroir X", _yes_no(metadata.flip_x)),
        ("Miroir Y", _yes_no(metadata.flip_y)),
        ("Type de chemin", metadata.source_curve_type),
        ("Liaison squelette", link_status),
        ("Version de création", metadata.extension_version),
    )
    content = ["<b>Lecture seule — aucune géométrie ne sera modifiée.</b><br><br>"]
    for label, value in rows:
        content.append("<b>{}</b> : {}<br>".format(_escaped(label), _escaped(value)))
    return "".join(content)


def _update_report(inputs, report_input):
    try:
        app, _ = _app_and_ui()
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            raise ValueError("Ouvrir une conception Fusion.")
        occurrence, metadata = _read_member(inputs)
        report_input.formattedText = _report_html(occurrence, metadata, design)
        return True
    except Exception as error:
        report_input.formattedText = (
            "<b>Barre non reconnue</b><br>{}".format(_escaped(error))
        )
        return False


class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            event_args = adsk.core.CommandCreatedEventArgs.cast(args)
            command = event_args.command
            command.isRepeatable = False
            inputs = command.commandInputs

            selection = inputs.addSelectionInput(
                SELECTION_ID,
                "Barre à inspecter",
                "Sélectionner un composant créé avec Profil acier.",
            )
            selection.addSelectionFilter("Occurrences")
            selection.setSelectionLimits(0, 1)

            report_input = inputs.addTextBoxCommandInput(
                REPORT_ID,
                "Informations",
                "Sélectionner une barre créée par l'extension.",
                13,
                True,
            )

            input_changed_handler = InputChangedHandler(report_input)
            command.inputChanged.add(input_changed_handler)
            _handlers.append(input_changed_handler)

            validate_handler = ValidateInputsHandler(report_input)
            command.validateInputs.add(validate_handler)
            _handlers.append(validate_handler)

            execute_handler = ExecuteHandler()
            command.execute.add(execute_handler)
            _handlers.append(execute_handler)
            _log("Commande de lecture ouverte")
        except Exception:
            _, ui = _app_and_ui()
            ui.messageBox(
                "Échec de l'ouverture de l'inspection:\n{}".format(traceback.format_exc())
            )


class InputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self, report_input):
        super().__init__()
        self._report_input = report_input

    def notify(self, args):
        event_args = adsk.core.InputChangedEventArgs.cast(args)
        if event_args.input and event_args.input.id == SELECTION_ID:
            _update_report(event_args.inputs, self._report_input)


class ValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self, report_input):
        super().__init__()
        self._report_input = report_input

    def notify(self, args):
        event_args = adsk.core.ValidateInputsEventArgs.cast(args)
        event_args.areInputsValid = _update_report(event_args.inputs, self._report_input)


class ExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            event_args = adsk.core.CommandEventArgs.cast(args)
            occurrence, metadata = _read_member(event_args.command.commandInputs)
            _log(
                "Barre reconnue : {} — {} — ancrage {} — rotation {} deg — X={} Y={}"
                .format(
                    occurrence.component.name,
                    metadata.profile,
                    metadata.anchor,
                    member_metadata.format_rotation_degrees(metadata.rotation_deg),
                    metadata.flip_x,
                    metadata.flip_y,
                )
            )
        except Exception as error:
            event_args.executeFailed = True
            _, ui = _app_and_ui()
            ui.messageBox("Inspection annulée :\n{}".format(error))


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
        raise RuntimeError("Aucun panneau Fusion compatible n'a été trouvé pour l'inspection.")
    _log("Commande d'inspection chargée dans le panneau {}".format(_panel_id))


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
