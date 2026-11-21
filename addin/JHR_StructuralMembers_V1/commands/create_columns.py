"""Pose des poteaux JHR en Z positif à partir de points de la conception."""
from dataclasses import dataclass
import math
import threading
import time
import traceback

import adsk.core as core
import adsk.fusion as fusion

from ..lib import addin_info, anchors, member_builder, physical_materials
from ..lib import preview_graphics, profile_catalog, timeline_groups, ui_layout


COMMAND_ID = "EI_JHR_CreateColumns"
EVENT_ID = COMMAND_ID + "_Deferred"
TOLERANCE_CM = 1e-5
_handlers = []
_pending = []


def _fire_deferred(app):
    time.sleep(0.1)
    for attempt in range(3):
        if app.fireCustomEvent(EVENT_ID):
            return
        if attempt < 2:
            time.sleep(0.2)


def point_position(entity):
    if not entity or not entity.isValid:
        raise ValueError("Un point de départ n’est plus valide.")
    sketch_point = fusion.SketchPoint.cast(entity)
    construction_point = fusion.ConstructionPoint.cast(entity)
    vertex = fusion.BRepVertex.cast(entity)
    if sketch_point:
        return sketch_point.worldGeometry
    if construction_point:
        return construction_point.geometry
    if vertex:
        return vertex.geometry
    raise ValueError("Sélectionner un point d’esquisse, un point de construction ou un sommet.")


def column_endpoints(entities, height_cm):
    if not math.isfinite(height_cm) or height_cm <= TOLERANCE_CM:
        raise ValueError("La hauteur du poteau doit être strictement positive.")
    paths = []
    for entity in entities:
        base = point_position(entity)
        if any(base.distanceTo(start) <= TOLERANCE_CM for start, _ in paths):
            raise ValueError("Deux points sélectionnés se superposent. Sélectionner un seul point par poteau.")
        paths.append((base, core.Point3D.create(base.x, base.y, base.z + height_cm)))
    return paths


def _create_axis(root, entity, base, top, created):
    planes = root.constructionPlanes
    placement = planes.createInput()
    if not placement.setByOffsetThroughPoint(root.xZConstructionPlane, entity):
        raise RuntimeError("Fusion n’a pas pu définir le plan vertical à travers le point.")
    plane = planes.add(placement)
    created.append(plane)
    plane.name = "Plan de l’axe du poteau"

    sketch = root.sketches.addWithoutEdges(plane)
    created.append(sketch)
    sketch.name = "Axe du poteau"
    projection = sketch.project2([entity], True)
    start = fusion.SketchPoint.cast(projection[0]) if len(projection) == 1 else None
    if not start or start.worldGeometry.distanceTo(base) > TOLERANCE_CM:
        raise RuntimeError("La projection du point de départ a changé sa position.")

    end = sketch.modelToSketchSpace(top)
    axis = sketch.sketchCurves.sketchLines.addByTwoPoints(start, end)
    if not axis:
        raise RuntimeError("Fusion n’a pas créé l’axe du poteau.")
    constraints = sketch.geometricConstraints
    if abs(sketch.yDirection.z) > abs(sketch.xDirection.z):
        direction = constraints.addVertical(axis)
    else:
        direction = constraints.addHorizontal(axis)
    if not direction:
        raise RuntimeError("Fusion n’a pas contraint l’axe à la verticale Z.")
    origin = start.geometry
    text = core.Point3D.create((origin.x + end.x) / 2 + 5, (origin.y + end.y) / 2 + 5, 0)
    height = sketch.sketchDimensions.addDistanceDimension(
        axis.startSketchPoint, axis.endSketchPoint, fusion.DimensionOrientations.AlignedDimensionOrientation, text,
    )
    if not height or axis.endSketchPoint.worldGeometry.distanceTo(top) > TOLERANCE_CM:
        raise RuntimeError("La cote de hauteur a déplacé le sommet du poteau.")
    sketch.isVisible = False
    plane.isLightBulbOn = False
    return axis


def create_columns(design, entities, height_cm, profile, material, material_choice):
    """Crée un lot de poteaux avec des axes liés aux points sélectionnés."""
    root = design.rootComponent
    entities = tuple(entities)
    paths = column_endpoints(entities, height_cm)
    if not paths:
        raise ValueError("Sélectionner au moins un point de départ.")
    start = timeline_groups.creation_start(design.timeline)
    occurrences, created = [], []
    try:
        with timeline_groups.defer_grouping():
            for entity, (base, top) in zip(entities, paths):
                axis = _create_axis(root, entity, base, top, created)
                occurrences.append(member_builder.create_member(
                    root, axis, profile, anchors.DEFAULT_ANCHOR_CODE,
                    physical_material=material, material_choice=material_choice, name_prefix="POTEAU",
                ))
    except Exception:
        for occurrence in reversed(occurrences):
            if occurrence.isValid:
                occurrence.deleteMe()
        for item in reversed(created):
            if item and item.isValid:
                item.deleteMe()
        raise
    timeline_groups.group_creation(design.timeline, start, "Poteaux · " + profile.designation)
    return occurrences


@dataclass
class Job:
    document: object
    design: object
    entities: list
    height_cm: float
    profile: object
    material_choice: object


class ColumnForm:
    def __init__(self, command, app, design):
        self.app = app
        self.document = app.activeDocument
        self.design = design
        self.preview = preview_graphics.PreviewManager()
        inputs = command.commandInputs
        self.points = inputs.addSelectionInput("columnPoints", "Points de départ", "Sélectionner les points de la grille")
        for selection_filter in ("SketchPoints", "ConstructionPoints", "Vertices"):
            self.points.addSelectionFilter(selection_filter)
        self.points.setSelectionLimits(1, 0)
        self.height = inputs.addValueInput("columnHeight", "Hauteur", "mm", core.ValueInput.createByString("2500 mm"))
        style = core.DropDownStyles.TextListDropDownStyle
        self.families = inputs.addDropDownCommandInput("columnFamily", "Famille", style)
        self.sections = inputs.addDropDownCommandInput("columnSection", "Section", style)
        self.material = inputs.addDropDownCommandInput("columnMaterial", "Matériau", style)
        self.report = inputs.addTextBoxCommandInput("columnStatus", "", "Sélectionner les points de départ.", 2, True)
        self.report.isFullWidth = True

        profiles = profile_catalog.discover_profiles()
        default = profile_catalog.default_profile(profiles)
        sections_by_family = {}
        for profile in profiles:
            key = (profile.category_label, profile.region_label, profile.family_label)
            sections_by_family.setdefault(key, []).append(profile)
        self.section_lists = list(sections_by_family.values())
        for key, choices in sections_by_family.items():
            category, region, family = key
            suffix = region if category == profile_catalog.GEOGRAPHIC_CATEGORY_LABEL else category
            self.families.listItems.add(f"{family} · {suffix}", default in choices)
        self.update_sections(default)

        self.materials = physical_materials.discover_steel_materials(app.materialLibraries, design.materials)
        default_material = physical_materials.default_choice(self.materials)
        for material in self.materials:
            self.material.listItems.add(material.display_label, material == default_material)

    def update_sections(self, preferred=None):
        self.visible_profiles = self.section_lists[self.families.selectedItem.index]
        selected = preferred if preferred in self.visible_profiles else self.visible_profiles[0]
        self.sections.listItems.clear()
        for profile in self.visible_profiles:
            self.sections.listItems.add(profile.section_label, profile == selected)

    def plan(self):
        if self.app.activeDocument != self.document or self.app.activeProduct != self.design:
            raise ValueError("Revenir à la conception où la commande a été ouverte.")
        if not self.height.isValidExpression:
            raise ValueError("Vérifier l’expression de la hauteur.")
        entities = [self.points.selection(index).entity for index in range(self.points.selectionCount)]
        if not entities:
            raise ValueError("Sélectionner les points de départ.")
        paths = column_endpoints(entities, self.height.value)
        profile = self.visible_profiles[self.sections.selectedItem.index]
        material_choice = self.materials[self.material.selectedItem.index]
        return Job(self.document, self.design, entities, self.height.value, profile, material_choice), paths

    def show_preview(self, job, paths):
        root = self.design.rootComponent
        normal = root.xZConstructionPlane.geometry.normal
        horizontal = normal.crossProduct(core.Vector3D.create(0, 0, 1))
        frames = [
            [(point.asArray(), horizontal.asArray(), normal.asArray()) for point in path]
            for path in paths
        ]
        self.preview.update_frames(root, frames, job.profile, anchors.DEFAULT_ANCHOR_CODE)


class Changed(core.InputChangedEventHandler):
    def __init__(self, form):
        super().__init__()
        self.form = form

    def notify(self, args):
        event = core.InputChangedEventArgs.cast(args)
        if event.input.id == "columnFamily":
            self.form.update_sections()


class Validate(core.ValidateInputsEventHandler):
    def __init__(self, form):
        super().__init__()
        self.form = form

    def notify(self, args):
        event = core.ValidateInputsEventArgs.cast(args)
        try:
            _, paths = self.form.plan()
            self.form.report.formattedText = f"{len(paths)} poteau(x) vers Z positif"
            event.areInputsValid = True
        except (ValueError, RuntimeError) as error:
            self.form.preview.clear()
            self.form.report.formattedText = str(error)
            event.areInputsValid = False


class Action(core.CommandEventHandler):
    def __init__(self, form, action):
        super().__init__()
        self.form = form
        self.action = action

    def notify(self, args):
        event = core.CommandEventArgs.cast(args)
        try:
            if self.action == "destroy":
                self.form.preview.clear()
                _handlers.remove(self.form.handlers)
            elif self.action == "preview":
                event.isValidResult = False
                job, paths = self.form.plan()
                self.form.show_preview(job, paths)
            else:
                self.form.preview.clear()
                job, _ = self.form.plan()
                _pending.append(job)
                # Le DXF ne peut pas être importé dans l’événement Execute de Fusion.
                threading.Thread(target=_fire_deferred, args=(self.form.app,), daemon=True).start()
        except Exception as error:
            self.form.app.log(traceback.format_exc())
            if self.action == "execute":
                event.executeFailed = True
                event.executeFailedMessage = str(error)
                self.form.app.userInterface.messageBox(str(error), "Structure JHR — Poteaux")
            elif self.action == "preview":
                self.form.preview.clear()
                self.form.report.formattedText = f"Aperçu indisponible. {error}"


class DeferredCreate(core.CustomEventHandler):
    def notify(self, args):
        if not _pending:
            return
        job = _pending.pop(0)
        app = core.Application.get()
        try:
            if app.activeDocument != job.document or app.activeProduct != job.design:
                raise ValueError("Le document actif a changé avant la création des poteaux.")
            material = physical_materials.resolve_material(app.materialLibraries, job.material_choice, job.design.materials)
            create_columns(job.design, job.entities, job.height_cm, job.profile, material, job.material_choice)
        except Exception as error:
            app.log(traceback.format_exc())
            app.userInterface.messageBox(str(error), "Structure JHR — Poteaux")


class Created(core.CommandCreatedEventHandler):
    def notify(self, args):
        app = core.Application.get()
        try:
            command = core.CommandCreatedEventArgs.cast(args).command
            design = fusion.Design.cast(app.activeProduct)
            if not design or design.designType != fusion.DesignTypes.ParametricDesignType:
                raise ValueError("Ouvrir une conception Fusion avec historique paramétrique.")
            if design.activeComponent != design.rootComponent:
                raise ValueError("Activer le composant racine pour placer les poteaux dans le repère de la conception.")
            command.isRepeatable = False
            command.isExecutedWhenPreEmpted = False
            form = ColumnForm(command, app, design)
            form.handlers = [
                (command.inputChanged, Changed(form)),
                (command.validateInputs, Validate(form)),
                (command.executePreview, Action(form, "preview")),
                (command.execute, Action(form, "execute")),
                (command.destroy, Action(form, "destroy")),
            ]
            for event, handler in form.handlers:
                event.add(handler)
            _handlers.append(form.handlers)
        except Exception as error:
            app.log(traceback.format_exc())
            app.userInterface.messageBox(str(error), "Structure JHR — Poteaux")


def start():
    app = core.Application.get()
    ui = app.userInterface
    if ui.commandDefinitions.itemById(COMMAND_ID):
        return
    icon = str(addin_info.ADDIN_ROOT / "resources" / "poteaux")
    definition = ui.commandDefinitions.addButtonDefinition(
        COMMAND_ID, "Poteaux", "Crée des poteaux acier en Z positif depuis des points sélectionnés.", icon,
    )
    created = Created()
    definition.commandCreated.add(created)
    deferred = DeferredCreate()
    app.registerCustomEvent(EVENT_ID).add(deferred)
    _handlers.extend((created, deferred))
    ui_layout.panel(ui, ui_layout.CREATE_PANEL_ID).controls.addCommand(definition).isPromoted = True


def stop():
    app = core.Application.get()
    ui = app.userInterface
    panel = ui_layout.panel(ui, ui_layout.CREATE_PANEL_ID)
    control = panel and panel.controls.itemById(COMMAND_ID)
    if control:
        control.deleteMe()
    definition = ui.commandDefinitions.itemById(COMMAND_ID)
    if definition:
        definition.deleteMe()
        app.unregisterCustomEvent(EVENT_ID)
    _pending.clear()
    _handlers.clear()
