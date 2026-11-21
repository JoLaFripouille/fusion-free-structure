from __future__ import annotations

import html
import traceback

import adsk.core
import adsk.fusion

from ..lib import (addin_info, countersink_preparation, fastener_creator as creator,
                   fastener_geometry as geo, fastener_hole_link, rivet_nut,
                   simple_fastener_creator, tapped_fastener, timeline_groups, ui_layout)


COMMAND_ID = "EI_JHR_PlaceBoltsV1"
COMMAND_NAME = "Boulonnerie JHR V{}".format(addin_info.VERSION)
COMMAND_DESCRIPTION = "Pose une vis, son écrou et ses rondelles sur des trous ronds, oblongs ou fraisés."
COPY_MODE = "Copier un ensemble existant"
HEX_MODE = "Modéliser tête H"
COUNTERSUNK_MODE = "Modéliser tête fraisée"
CAP_MODE = "Modéliser tête cylindrique six pans creux"
BUTTON_MODE = "Modéliser tête bombée six pans creux"
SOCKET_MODES = {CAP_MODE: "CHC", BUTTON_MODE: "TBHC"}
TAPPED_MODE = "Vis en trou taraudé"
RIVNUT_MODE = "Écrou à sertir RIVKLE"
PANEL_IDS = (ui_layout.FASTENER_PANEL_ID,)
MODES = (COPY_MODE, HEX_MODE, *SOCKET_MODES, COUNTERSUNK_MODE, TAPPED_MODE, RIVNUT_MODE)
SHORTCUTS = (
    ("EI_JHR_BoltH", "Boulon tête H", "visserie_h_ecrou", HEX_MODE),
    ("EI_JHR_BoltCHC", "Boulon tête cylindrique", "visserie_chc_ecrou", CAP_MODE),
    ("EI_JHR_BoltTBHC", "Boulon tête bombée", "visserie_tbhc_ecrou", BUTTON_MODE),
    ("EI_JHR_BoltTF", "Boulon tête fraisée", "visserie_tf_ecrou", COUNTERSUNK_MODE),
    ("EI_JHR_TappedScrew", "Vis en trou taraudé", "visserie_taraudage", TAPPED_MODE),
    ("EI_JHR_Rivkle", "Écrou à sertir RIVKLE", "visserie_rivkle", RIVNUT_MODE),
)
_handlers = []


def _washers(inputs, mode):
    return {
        "head_washer": mode != COUNTERSUNK_MODE and inputs.itemById("headWasher").value,
        "nut_washer": mode != TAPPED_MODE and inputs.itemById("nutWasher").value,
    }


def _hole_sources(inputs):
    holes = inputs.itemById("holes")
    return tuple(holes.selection(i).entity for i in range(holes.selectionCount))


def _hole_link(design, inputs, head, sources=None):
    if not inputs.itemById("linkHole").value:
        return None
    if sources is None:
        sources = _hole_sources(inputs)

    def bind(pose, occurrence):
        source = fastener_hole_link.source_for_pose(sources, pose, head)
        return fastener_hole_link.bind(design, occurrence, pose, source)

    return bind


def _is_conical(entity):
    face = adsk.fusion.BRepFace.cast(entity)
    return face and adsk.core.Cone.cast(face.geometry)


def _prepare_countersinks(entities, head_face, nut_face, diameter):
    holes, preparations = [], []
    for entity in entities:
        if _is_conical(entity):
            holes.append(creator.read_countersink(entity))
        else:
            preparation = countersink_preparation.plan(entity, head_face, diameter)
            holes.append(preparation.hole)
            preparations.append(preparation)
    if preparations:
        head_face = head_face or preparations[0].head_face
        nut_face = nut_face or preparations[0].backing_face
    return holes, preparations, head_face, nut_face


def _create_modeled(design, inputs, poses, diameter, length, head, preparations):
    def create(sources=None):
        return simple_fastener_creator.create_modeled_fasteners(
            design, poses, diameter, length, inputs.itemById("projection").value * 10,
            head=head, bind_to_hole=_hole_link(design, inputs, head, sources),
            **_washers(inputs, inputs.itemById("mode").selectedItem.name))

    needed = {pose.countersink for pose in poses}
    pending = {prep.hole: prep for prep in preparations if prep.hole in needed}
    if not pending:
        return create()
    sources = [entity for entity in _hole_sources(inputs) if _is_conical(entity)]
    start = timeline_groups.creation_start(design.timeline)
    created = []
    try:
        with timeline_groups.defer_grouping():
            for preparation in pending.values():
                face, operations = countersink_preparation.apply(design, preparation)
                created.extend(operations)
                sources.append(face)
            result = create(tuple(sources))
    except Exception:
        for operation in reversed(created):
            if operation.isValid:
                operation.deleteMe()
        raise
    timeline_groups.group_creation(design.timeline, start, "JHR - Fixations tête fraisée")
    return result


class Session:
    def __init__(self, document):
        self.document = document
        self.cached_key = None
        self.prototype = None

    def insert(self, inputs, preview):
        app = adsk.core.Application.get()
        design = adsk.fusion.Design.cast(app.activeProduct)
        hole, face = (inputs.itemById(key) for key in ("holes", "headSupport"))
        if app.activeDocument != self.document or not design or hole.selectionCount != 1 or face.selectionCount != 1:
            raise ValueError("Sélectionner la paroi cylindrique du trou et le plan d’entrée.")
        style = inputs.itemById("rivetHead").selectedItem.name
        head = next(key for key, label in rivet_nut.HEADS.items() if label == style)
        diameter = float(inputs.itemById("rivetDiameter").selectedItem.name[1:])
        screw_options = {}
        if inputs.itemById("rivetAddScrew").value:
            style = inputs.itemById("rivetScrewHead").selectedItem.name
            screw_options = dict(
                screw_head=next(key for key, label in rivet_nut.SCREW_HEADS.items() if label == style),
                screw_length_mm=inputs.itemById("rivetScrewLength").value * 10 or None,
                screw_stack_mm=inputs.itemById("rivetScrewStack").value * 10,
                blind_clearance_mm=inputs.itemById("rivetBackClearance").value * 10 or None,
                screw_washer=inputs.itemById("rivetScrewWasher").value,
            )
        return rivet_nut.place(design, hole.selection(0).entity, face.selection(0).entity,
                              diameter, head, preview=preview,
                              prepare_hole=inputs.itemById("rivetPrepare").value,
                              link_to_hole=inputs.itemById("linkHole").value, **screw_options)

    def tapped(self, inputs, preview):
        app = adsk.core.Application.get()
        design = adsk.fusion.Design.cast(app.activeProduct)
        hole, head = (inputs.itemById(name) for name in ("holes", "headSupport"))
        if app.activeDocument != self.document or not design or hole.selectionCount != 1 or head.selectionCount != 1:
            raise ValueError("Sélectionner l’avant-trou rond et la face d’appui sous tête.")
        countersunk = inputs.itemById("tappedCountersunk").value
        return tapped_fastener.place(
            design, hole.selection(0).entity, head.selection(0).entity,
            inputs.itemById("diameter").value*10, inputs.itemById("engagement").value*10,
            inputs.itemById("modeledThread").value, preview,
            head="TF" if countersunk else "H",
            prepare_countersink=countersunk,
            head_washer=not countersunk and _washers(inputs, TAPPED_MODE)["head_washer"],
            length_mm=None if inputs.itemById("autoLength").value else inputs.itemById("length").value*10,
            link_to_hole=inputs.itemById("linkHole").value,
        )

    def evaluate(self, inputs, occupied=False):
        app = adsk.core.Application.get()
        if app.activeDocument != self.document:
            raise ValueError("Le document actif a changé ; relancer Boulonnerie JHR.")
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            raise ValueError("Ouvrir une conception Fusion.")
        mode = inputs.itemById("mode").selectedItem.name
        modeled = mode != COPY_MODE
        head_kind = SOCKET_MODES.get(mode, "TF" if mode == COUNTERSUNK_MODE else "H")
        selections = [inputs.itemById(name) for name in ("model", "headSupport", "nutSupport")]
        diameter = inputs.itemById("diameter").value * 10
        length = inputs.itemById("length").value * 10
        entities = _hole_sources(inputs)
        head_face, nut_face = (s.selection(0).entity if s.selectionCount else None for s in selections[1:])
        preparations = []
        if head_kind == "TF":
            if not entities:
                raise ValueError("Sélectionner le bord rond côté tête ou une fraisure existante.")
            holes, preparations, head_face, nut_face = _prepare_countersinks(
                entities, head_face, nut_face, diameter)
        else:
            holes = [creator.read_hole(entity) for entity in entities]
        if not head_face or not nut_face:
            raise ValueError("Choisir les deux faces d’appui extérieures.")
        hp = creator.read_support(head_face)
        np = creator.read_support(nut_face)
        reverse = inputs.itemById("reverse").value
        if modeled:
            projection = inputs.itemById("projection").value * 10
            existing = creator.existing_positions(design.rootComponent) if occupied else ()
            _, poses, ignored, length = geo.plan_modeled_fasteners(
                holes, hp, np, diameter,
                None if inputs.itemById("autoLength").value else length,
                projection, existing, reverse, head=head_kind, **_washers(inputs, mode))
            return design, None, poses, ignored, diameter, length, head_kind, preparations
        if selections[0].selectionCount != 1:
            raise ValueError("Choisir un ensemble modèle complet.")
        model = selections[0].selection(0).entity
        model_length = inputs.itemById("modelLength").value * 10
        body = creator.prototype_body(model)
        key = (body, body.revisionId, diameter, model_length)
        if key != self.cached_key:
            self.prototype = creator.read_prototype(body, diameter, model_length)
            self.cached_key = key
        head = inputs.itemById("head").selectedItem.name
        existing = creator.existing_positions(design.rootComponent, self.prototype) if occupied else ()
        poses, ignored = geo.plan_placements(
            holes, hp, np, self.prototype.layout,
            diameter, length, head, existing, reverse)
        return design, self.prototype, poses, ignored, diameter, length, head, preparations


def _refresh(inputs, session):
    report = inputs.itemById("report")
    try:
        if inputs.itemById("mode").selectedItem.name == RIVNUT_MODE:
            result = session.insert(inputs, preview=True)
            report.formattedText = ("{} · {} · perçage Ø{:g} mm · paroi {:g} mm"
                                    .format(result["designation"], result["reference"],
                                            result["hole_diameter_mm"], result["grip_mm"]))
            if result["preparation_required"]:
                report.formattedText += "<br>L’avant-trou sera préparé à ces cotes."
            if screw := result.get("screw"):
                composition = "vis et rondelle" if screw["washer"] else "vis seule"
                report.formattedText += "<br>{} · {} · débord arrière {:.2f} mm".format(
                    html.escape(screw["designation"]), composition, screw["blind_projection_mm"])
            return True
        if inputs.itemById("mode").selectedItem.name == TAPPED_MODE:
            result = session.tapped(inputs, preview=True)
            report.formattedText = "{} · vis {:.2f} mm · engagement {:g} mm".format(
                html.escape(result["designation"]), result["length_mm"], result["engagement_mm"])
            if "countersink_depth_mm" in result:
                report.formattedText += "<br>Tête affleurante. Longueur mesurée tête comprise."
                if result["prepares_countersink"]:
                    report.formattedText += " La fraisure sera usinée à la pose."
            return True
        _, prototype, poses, ignored, _, length, head, preparations = session.evaluate(inputs)
        grips = sorted({round(p.grip_cm * 10, 3) for p in poses})
        modeled_details = ""
        if prototype is None:
            mode = inputs.itemById("mode").selectedItem.name
            count = sum(_washers(inputs, mode).values())
            head_details = "Tête affleurante. " if head == "TF" else ""
            modeled_details = f"<br>{head_details}{count} rondelle(s), modèle sans filetage."
            if preparations:
                modeled_details += "<br>Les fraisures manquantes seront usinées à 90° à la pose."
        report.formattedText = ("<b>{} position(s)</b> — serrage {} mm ; longueur de vis {} mm.<br>"
                                "{} sélection(s) répétée(s) ignorée(s).{}").format(
            len(poses), ", ".join("{:g}".format(g) for g in grips),
            "{:g}".format(length) if length is not None else "—", ignored,
            modeled_details)
        return True
    except Exception as error:
        report.formattedText = html.escape(str(error))
        return False


def _configure_inputs(inputs, *, reset_holes=False, update_filters=False):
    mode = inputs.itemById("mode").selectedItem.name
    modeled = mode != COPY_MODE
    tapped = mode == TAPPED_MODE
    riveted = mode == RIVNUT_MODE
    single_support = tapped or riveted
    tapped_countersunk = tapped and inputs.itemById("tappedCountersunk").value
    automatic = inputs.itemById("autoLength").value
    show_screw = riveted and inputs.itemById("rivetAddScrew").value
    if reset_holes or update_filters:
        holes = inputs.itemById("holes")
        if reset_holes or not tapped_countersunk and any(_is_conical(entity) for entity in _hole_sources(inputs)):
            holes.clearSelection()
        holes.clearSelectionFilter()
        holes.setSelectionLimits(1, 1 if single_support else 100)
        filters = (("CylindricalFaces", "ConicalFaces") if tapped_countersunk
                   else ("CylindricalFaces",) if single_support
                   else ("ConicalFaces", "CylindricalFaces", "Edges") if mode == COUNTERSUNK_MODE
                   else ("Edges", "CylindricalFaces"))
        for kind in filters:
            holes.addSelectionFilter(kind)
    reverse = inputs.itemById("reverse")
    reverse.isVisible = not single_support
    reverse.isEnabled = mode != COUNTERSUNK_MODE
    if mode == COUNTERSUNK_MODE:
        reverse.value = False
    for name in ("model", "modelLength", "head"):
        inputs.itemById(name).isVisible = not modeled
    for name in ("rivetHead", "rivetDiameter", "rivetPrepare", "rivetAddScrew"):
        inputs.itemById(name).isVisible = riveted
    for name in ("rivetScrewHead", "rivetScrewLength", "rivetScrewWasher", "rivetScrewStack", "rivetBackClearance"):
        inputs.itemById(name).isVisible = show_screw
    inputs.itemById("autoLength").isVisible = modeled and not riveted
    inputs.itemById("projection").isVisible = modeled and not single_support
    inputs.itemById("engagement").isVisible = tapped and automatic
    inputs.itemById("modeledThread").isVisible = tapped
    inputs.itemById("tappedCountersunk").isVisible = tapped
    inputs.itemById("diameter").isVisible = not riveted
    inputs.itemById("headWasher").isVisible = modeled and not (riveted or tapped_countersunk or mode == COUNTERSUNK_MODE)
    inputs.itemById("nutWasher").isVisible = modeled and not single_support
    inputs.itemById("linkHole").isVisible = modeled
    nut_support = inputs.itemById("nutSupport")
    nut_support.setSelectionLimits(0 if single_support or mode == COUNTERSUNK_MODE else 1, 1)
    inputs.itemById("headSupport").setSelectionLimits(0 if mode == COUNTERSUNK_MODE else 1, 1)
    nut_support.isVisible = not single_support
    length = inputs.itemById("length")
    length.isVisible = not riveted and (not tapped or not automatic)
    length.isEnabled = not (modeled and automatic)


class Changed(adsk.core.InputChangedEventHandler):
    def __init__(self, session):
        super().__init__(); self.session = session

    def notify(self, args):
        event = adsk.core.InputChangedEventArgs.cast(args)
        if event.input.id in ("mode", "autoLength", "rivetAddScrew", "tappedCountersunk"):
            _configure_inputs(event.inputs, reset_holes=event.input.id == "mode",
                              update_filters=event.input.id == "tappedCountersunk")
        if event.input.id == "model" and event.input.selectionCount == 1:
            try:
                body = creator.prototype_body(event.input.selection(0).entity)
                size = creator.size_from_name(body)
                if size:
                    diameter, length = size
                    for name, value in (("diameter", diameter), ("modelLength", length), ("length", length)):
                        event.inputs.itemById(name).value = value * .1
                    prototype = creator.read_prototype(body, diameter, length)
                    for item in event.inputs.itemById("head").listItems:
                        if item.name == prototype.layout.head:
                            item.isSelected = True
            except Exception:
                # Le rapport ci-dessous explique le refus ; aucune géométrie n'est créée.
                self.session.cached_key = None
        _refresh(event.inputs, self.session)


class Validate(adsk.core.ValidateInputsEventHandler):
    def __init__(self, session):
        super().__init__(); self.session = session

    def notify(self, args):
        event = adsk.core.ValidateInputsEventArgs.cast(args)
        event.areInputsValid = _refresh(event.inputs, self.session)


class Execute(adsk.core.CommandEventHandler):
    def __init__(self, session):
        super().__init__(); self.session = session

    def notify(self, args):
        event = adsk.core.CommandEventArgs.cast(args)
        try:
            inputs = event.command.commandInputs
            if inputs.itemById("mode").selectedItem.name == RIVNUT_MODE:
                self.session.insert(inputs, preview=False)
                return
            if inputs.itemById("mode").selectedItem.name == TAPPED_MODE:
                self.session.tapped(inputs, preview=False)
                return
            design, prototype, poses, ignored, diameter, length, head, preparations = self.session.evaluate(
                inputs, occupied=True)
            if prototype is None:
                result = _create_modeled(design, inputs, poses, diameter, length, head, preparations)
            else:
                result = creator.create_fasteners(design, prototype, poses, diameter, length, head)
            adsk.core.Application.get().userInterface.messageBox(
                "{} ensemble(s) ajouté(s) dans VISSERIE ; {} doublon(s) ignoré(s).\n"
                "Le document n'a pas été enregistré.".format(
                    result["created"], ignored + result["occupied"]))
        except Exception as error:
            event.executeFailed = True
            app = adsk.core.Application.get()
            app.log("Boulonnerie JHR : " + traceback.format_exc())
            app.userInterface.messageBox("Insertion refusée : {}".format(error))


class Created(adsk.core.CommandCreatedEventHandler):
    def __init__(self, initial_mode):
        super().__init__()
        self.initial_mode = initial_mode

    def notify(self, args):
        event = adsk.core.CommandCreatedEventArgs.cast(args)
        command, inputs = event.command, event.command.commandInputs
        session = Session(adsk.core.Application.get().activeDocument)
        command.isRepeatable = False
        mode = inputs.addDropDownCommandInput("mode", "Méthode", adsk.core.DropDownStyles.TextListDropDownStyle)
        for label in MODES:
            mode.listItems.add(label, label == self.initial_mode)
        model = inputs.addSelectionInput("model", "Ensemble modèle", "Un corps simple : vis, écrou et deux rondelles.")
        model.addSelectionFilter("SolidBodies"); model.addSelectionFilter("Occurrences")
        model.setSelectionLimits(0, 1)
        holes = inputs.addSelectionInput("holes", "Perçages", "Pour créer une fraisure, sélectionner le bord rond côté tête.")
        holes.addSelectionFilter("Edges"); holes.addSelectionFilter("CylindricalFaces")
        holes.setSelectionLimits(1, 100)
        for name, title in (("headSupport", "Appui côté tête"), ("nutSupport", "Appui côté écrou")):
            selection = inputs.addSelectionInput(name, title, "Face extérieure plane de la pièce assemblée.")
            selection.addSelectionFilter("PlanarFaces"); selection.setSelectionLimits(1, 1)
        for name, title, value in (("diameter", "Diamètre nominal", 1.6),
                                   ("modelLength", "Longueur de vis du modèle", 5.0),
                                   ("length", "Longueur de vis", 5.0)):
            inputs.addValueInput(name, title, "mm", adsk.core.ValueInput.createByReal(value))
        head = inputs.addDropDownCommandInput("head", "Tête", adsk.core.DropDownStyles.TextListDropDownStyle)
        head.listItems.add("H", True); head.listItems.add("CHC", False)
        inputs.addBoolValueInput("reverse", "Inverser tête et écrou", True, "", False)
        inputs.addBoolValueInput("headWasher", "Rondelle sous tête", True, "", True)
        inputs.addBoolValueInput("nutWasher", "Rondelle côté écrou", True, "", True)
        inputs.addBoolValueInput("linkHole", "Lier au perçage", True, "", True)
        auto = inputs.addBoolValueInput("autoLength", "Longueur automatique", True, "", True)
        auto.isVisible = False
        projection = inputs.addValueInput("projection", "Dépassement minimal après écrou", "mm", adsk.core.ValueInput.createByString("5 mm"))
        projection.isVisible = False
        inputs.addValueInput("engagement", "Engagement dans le taraudage", "mm",
                             adsk.core.ValueInput.createByString("12 mm")).isVisible = False
        inputs.addBoolValueInput("modeledThread", "Modéliser les filets", True, "", False).isVisible = False
        inputs.addBoolValueInput("tappedCountersunk", "Tête fraisée", True, "", False).isVisible = False
        insert_head = inputs.addDropDownCommandInput(
            "rivetHead", "Tête de l’écrou à sertir", adsk.core.DropDownStyles.TextListDropDownStyle)
        for key, label in rivet_nut.HEADS.items():
            insert_head.listItems.add(label, key == "flat")
        insert_head.isVisible = False
        insert_diameter = inputs.addDropDownCommandInput(
            "rivetDiameter", "Filetage de l’écrou à sertir", adsk.core.DropDownStyles.TextListDropDownStyle)
        for value in rivet_nut.DIAMETERS_MM:
            insert_diameter.listItems.add(f"M{value:g}", value == 6)
        insert_diameter.isVisible = False
        inputs.addBoolValueInput("rivetPrepare", "Préparer l’avant-trou sélectionné", True, "", False).isVisible = False
        inputs.addBoolValueInput("rivetAddScrew", "Ajouter une vis", True, "",
                                 self.initial_mode == RIVNUT_MODE).isVisible = False
        inputs.addBoolValueInput("rivetScrewWasher", "Rondelle sous tête", True, "", True).isVisible = False
        screw_head = inputs.addDropDownCommandInput(
            "rivetScrewHead", "Tête de vis", adsk.core.DropDownStyles.TextListDropDownStyle)
        for key, label in rivet_nut.SCREW_HEADS.items():
            screw_head.listItems.add(label, key == "CHC")
        screw_head.isVisible = False
        for name, title in (
            ("rivetScrewLength", "Longueur sous tête (0 = auto)"),
            ("rivetScrewStack", "Épaisseur à serrer devant l’insert"),
            ("rivetBackClearance", "Profondeur libre côté aveugle (0 = non renseignée)"),
        ):
            inputs.addValueInput(name, title, "mm", adsk.core.ValueInput.createByReal(0.)).isVisible = False
        report = inputs.addTextBoxCommandInput("report", "Contrôle", "", 4, True)
        _configure_inputs(inputs, reset_holes=True)
        for source, handler in ((command.inputChanged, Changed(session)),
                                (command.validateInputs, Validate(session)),
                                (command.execute, Execute(session))):
            source.add(handler); _handlers.append(handler)
        _refresh(inputs, session)


def start():
    ui = adsk.core.Application.get().userInterface
    commands = (*SHORTCUTS, (COMMAND_ID, COMMAND_NAME, "boulonnerie", COPY_MODE))
    panel = ui_layout.panel(ui, PANEL_IDS[0])
    for command_id, label, icon, mode in commands:
        definition = ui.commandDefinitions.itemById(command_id)
        if not definition:
            definition = ui.commandDefinitions.addButtonDefinition(
                command_id, label, COMMAND_DESCRIPTION,
                str(addin_info.ADDIN_ROOT / "resources" / icon),
            )
            handler = Created(mode)
            definition.commandCreated.add(handler)
            _handlers.append(handler)
        if panel and not panel.controls.itemById(command_id):
            panel.controls.addCommand(definition).isPromoted = command_id != COMMAND_ID


def stop():
    ui = adsk.core.Application.get().userInterface
    panel = ui_layout.panel(ui, PANEL_IDS[0])
    for command_id in (*(item[0] for item in SHORTCUTS), COMMAND_ID):
        control = panel.controls.itemById(command_id) if panel else None
        if control:
            control.deleteMe()
        definition = ui.commandDefinitions.itemById(command_id)
        if definition:
            definition.deleteMe()
    _handlers.clear()
