"""Commande Fusion pour le garde-corps sur appuis en acier."""

import traceback

import adsk.core as core
import adsk.fusion as fusion

from ..lib import addin_info, guardrail_layout, guardrail_operations, ui_layout


COMMAND_ID = "EI_JHR_CreateGuardrail"
_handlers = []


class Form:
    def __init__(self, command):
        command.isRepeatable = False
        self.app = core.Application.get()
        self.design = fusion.Design.cast(self.app.activeProduct)
        self.document_id = self.app.activeDocument.creationId
        inputs = command.commandInputs
        self.paths = inputs.addSelectionInput("paths", "Axe du garde-corps",
                                              "Sélectionner les segments dans l'ordre du parcours.")
        self.paths.addSelectionFilter("SketchLines")
        self.paths.addSelectionFilter("LinearEdges")
        self.paths.setSelectionLimits(1, 25)
        self.faces = inputs.addSelectionInput("supports", "Faces d’appui",
                                              "Sélectionner la face commune ou une face par segment, dans l'ordre.")
        self.faces.addSelectionFilter("PlanarFaces")
        self.faces.setSelectionLimits(1, 25)
        self.model = inputs.addDropDownCommandInput(
            "model", "Modèle", core.DropDownStyles.TextListDropDownStyle,
        )
        self.model.listItems.add("Industriel à lisses", True)
        self.model.listItems.add("Barreaudé", False)
        self.mode = inputs.addDropDownCommandInput("mode", "Pose", core.DropDownStyles.TextListDropDownStyle)
        self.mode.listItems.add("À la française", True)
        self.mode.listItems.add("À l’anglaise", False)
        self.vertical = inputs.addDropDownCommandInput(
            "vertical_axis", "Axe vertical", core.DropDownStyles.TextListDropDownStyle,
        )
        self.vertical.listItems.add("Automatique", True)
        self.vertical.listItems.add("Y (sol XZ)", False)
        self.vertical.listItems.add("Z (sol XY)", False)
        self.support = inputs.addDropDownCommandInput(
            "substrate", "Support", core.DropDownStyles.TextListDropDownStyle,
        )
        self.support.listItems.add("Acier", True)
        self.support.listItems.add("Béton avec ancrages", False)
        self.cut = inputs.addBoolValueInput("drill_support", "Percer les appuis acier", True, "", False)
        self.settings = {}
        self.sections = {}
        for group_name, title, fields in (
                ("placement", "Implantation", (
                    ("height_mm", "Hauteur"), ("post_spacing_max_mm", "Entraxe maximal"),
                    ("start_margin_mm", "Retrait au départ"), ("end_margin_mm", "Retrait à l’arrivée"),
                )),
                ("plates", "Platines et perçages", (
                    ("plate_along_mm", "Largeur dans le sens du parcours"),
                    ("plate_across_mm", "Autre dimension de la platine"),
                    ("plate_thickness_mm", "Épaisseur"), ("hole_pitch_along_mm", "Entraxe longitudinal"),
                    ("hole_pitch_across_mm", "Entraxe transversal ou vertical"),
                    ("hole_diameter_mm", "Diamètre"), ("side_drop_mm", "Descente en pose latérale"),
                )),
                ("kickplate_dims", "Dimensions de la plinthe", (
                    ("kickplate_height_mm", "Hauteur"), ("kickplate_thickness_mm", "Épaisseur"),
                    ("kickplate_clearance_mm", "Vide sous la plinthe"),
                )),
                ("post_head", "Pointe des poteaux plats", (
                    ("post_tip_height_mm", "Hauteur des biais"), ("post_tip_flat_mm", "Largeur du méplat"),
                )),
                ("anchors", "Dimensions des tiges d’ancrage béton", (
                    ("anchor_diameter_mm", "Diamètre"),
                    ("anchor_embedment_mm", "Longueur dans le support"),
                    ("anchor_projection_mm", "Saillie au-delà de la platine"),
                )),
        ):
            section = inputs.addGroupCommandInput(group_name, title)
            section.isExpanded = group_name in ("placement", "plates")
            for key, label in fields:
                value = guardrail_layout.DEFAULTS[key]
                entry = section.children.addValueInput(
                    key, label, "mm", core.ValueInput.createByString(f"{value:g} mm"),
                )
                self.settings[key] = entry
        self.kickplate = inputs.addBoolValueInput("kickplate", "Ajouter une plinthe", True, "", True)
        self.kickplate_side = inputs.addDropDownCommandInput(
            "kickplate_side", "Côté de la plinthe", core.DropDownStyles.TextListDropDownStyle,
        )
        self.kickplate_side.listItems.add("Gauche en suivant le parcours", True)
        self.kickplate_side.listItems.add("Droite en suivant le parcours", False)
        self.infill = inputs.addGroupCommandInput("infill", "Barreaudage")
        self.infill.isVisible = False
        self.bar_shape = self.infill.children.addDropDownCommandInput(
            "bar_shape", "Section des barreaux", core.DropDownStyles.TextListDropDownStyle,
        )
        for label in ("Carré plein", "Rond plein", "Plat"):
            self.bar_shape.listItems.add(label, label == "Carré plein")
        for key, label in (("bar_width_mm", "Largeur ou diamètre"),
                           ("bar_depth_mm", "Épaisseur du plat"),
                           ("max_clear_mm", "Vide maximal"),
                           ("lower_rail_clearance_mm", "Vide sous la lisse basse")):
            default = guardrail_layout.DEFAULTS[key]
            self.settings[key] = self.infill.children.addValueInput(
                key, label, "mm", core.ValueInput.createByString(f"{default:g} mm"),
            )
        self.distribution = inputs.addDropDownCommandInput(
            "distribution", "Mesure de l’entraxe", core.DropDownStyles.TextListDropDownStyle,
        )
        self.distribution.listItems.add("Projection horizontale", True)
        self.distribution.listItems.add("Sur le chemin", False)
        self.count = inputs.addIntegerSpinnerCommandInput("post_count", "Poteaux (0 = auto)", 0, 100, 1, 0)
        self.rows = inputs.addIntegerSpinnerCommandInput("middle", "Nombre de sous-lisses", 0, 10, 1, 1)
        for key, title in (("post", "Section du poteau"), ("handrail", "Section de la main courante"),
                           ("middle", "Section des sous-lisses")):
            group = inputs.addGroupCommandInput(key, title)
            group.isExpanded = False
            section_type = group.children.addDropDownCommandInput(
                f"{key}_type", "Type", core.DropDownStyles.TextListDropDownStyle,
            )
            for value, label in (("flat", "Plat"), ("rectangular_tube", "Tube rectangulaire"),
                                 ("round_tube", "Tube rond")):
                section_type.listItems.add(label, guardrail_layout.DEFAULTS[f"{key}_type"] == value)
            self.sections[key] = section_type
            for dim, label in (("width", "Largeur / diamètre"), ("depth", "Profondeur"),
                               ("wall", "Épaisseur de paroi")):
                field = f"{key}_{dim}_mm"
                value = guardrail_layout.DEFAULTS[field]
                self.settings[field] = group.children.addValueInput(
                    field, label, "mm", core.ValueInput.createByString(f"{value:g} mm"),
                )
        self.report = inputs.addTextBoxCommandInput("details", "", "", 3, True)
        self.industrial_inputs = [self.kickplate, self.kickplate_side, self.rows,
                                  inputs.itemById("middle"), inputs.itemById("kickplate_dims")]

    def show_model(self):
        barreaude = self.model.selectedItem.index == 1
        self.infill.isVisible = barreaude
        for field in self.industrial_inputs:
            field.isVisible = not barreaude
        self.sections["post"].isVisible = not barreaude
        self.sections["handrail"].listItems.item(0 if barreaude else 2).isSelected = True
        for suffix in ("width", "depth"):
            key = f"handrail_{suffix}_mm"
            self.settings[key].value = (self.settings[f"post_{suffix}_mm"].value if barreaude
                                        else guardrail_layout.DEFAULTS[key]*.1)

    def values(self):
        if self.app.activeDocument.creationId != self.document_id or not self.design:
            raise ValueError("La conception a changé pendant la commande.")
        if any(not field.isValidExpression for field in self.settings.values()):
            raise ValueError("Vérifier la syntaxe des cotes.")
        paths = [self.paths.selection(i).entity for i in range(self.paths.selectionCount)]
        faces = [self.faces.selection(i).entity for i in range(self.faces.selectionCount)]
        settings = {key: field.value*10 for key, field in self.settings.items()}
        barreaude = self.model.selectedItem.index == 1
        settings["model"] = "barreaude" if barreaude else "industrial"
        settings["bar_shape"] = ("square", "round", "flat")[self.bar_shape.selectedItem.index]
        settings["mounting"] = "top" if self.mode.selectedItem.index == 0 else "side"
        settings["vertical_axis"] = ("auto", "Y", "Z")[self.vertical.selectedItem.index]
        settings["support"] = "steel" if self.support.selectedItem.index == 0 else "concrete"
        settings["drill_support"] = self.cut.value and settings["support"] == "steel"
        settings["distribution"] = "horizontal" if self.distribution.selectedItem.index == 0 else "along_path"
        settings["post_count"] = self.count.value
        settings["middle_count"] = self.rows.value
        settings["kickplate"] = self.kickplate.value
        settings["kickplate_side"] = "left" if self.kickplate_side.selectedItem.index == 0 else "right"
        for key, choice in self.sections.items():
            kind = ("flat", "rectangular_tube", "round_tube")[choice.selectedItem.index]
            settings[f"{key}_type"] = kind
            if kind == "round_tube":
                settings[f"{key}_depth_mm"] = settings[f"{key}_width_mm"]
        if barreaude:
            settings["post_type"] = "flat"
            settings["kickplate"] = False
        return paths, faces, settings


class Validate(core.ValidateInputsEventHandler):
    def __init__(self, form):
        super().__init__()
        self.form = form

    def notify(self, args):
        args.areInputsValid = False
        try:
            plan = guardrail_operations.evaluate(*self.form.values())
            self.form.report.formattedText = (
                f"{len(plan['posts'])} poteaux · {len(plan['plates'])} platines percées · "
                f"entraxe {plan['pitch_mm']:.1f} mm"
            )
            if plan["support_holes"]:
                self.form.report.formattedText += f" · {len(plan['support_holes'])} trous traversants dans les appuis"
            if plan["anchors"]:
                self.form.report.formattedText += f" · {len(plan['anchors'])} tiges d’ancrage"
            if "bars" in plan:
                self.form.report.formattedText += (
                    f" · {len(plan['bars'])} barreaux · vide maximal "
                    f"{max(plan['max_clear_mm'], plan['bottom_clear_mm']):.1f} mm"
                )
            args.areInputsValid = True
        except ValueError as error:
            self.form.report.formattedText = str(error)
        except Exception:
            self.form.app.log("[JHR] Garde-corps — lecture d’appui\n" + traceback.format_exc())
            self.form.report.formattedText = "Appui illisible. Voir le journal Fusion."


class Action(core.CommandEventHandler):
    def __init__(self, form, destroy=False):
        super().__init__()
        self.form = form
        self.destroy = destroy

    def notify(self, args):
        if self.destroy:
            _handlers.remove(self.form.handlers)
            return
        try:
            guardrail_operations.create(self.form.design, *self.form.values())
        except Exception as error:
            self.form.app.log("[JHR] Garde-corps — création\n" + traceback.format_exc())
            args.executeFailed = True
            args.executeFailedMessage = str(error)


class Created(core.CommandCreatedEventHandler):
    def notify(self, args):
        command = args.command
        form = Form(command)
        form.handlers = [
            (command.validateInputs, Validate(form)),
            (command.inputChanged, ModelChanged(form)),
            (command.execute, Action(form)),
            (command.destroy, Action(form, destroy=True)),
        ]
        for event, handler in form.handlers:
            event.add(handler)
        _handlers.append(form.handlers)


class ModelChanged(core.InputChangedEventHandler):
    def __init__(self, form):
        super().__init__()
        self.form = form

    def notify(self, args):
        if args.input.id == "model":
            self.form.show_model()
        elif args.input.id == "bar_shape":
            self.form.settings["bar_depth_mm"].isVisible = self.form.bar_shape.selectedItem.index == 2


def start():
    ui = core.Application.get().userInterface
    if ui.commandDefinitions.itemById(COMMAND_ID):
        return
    definition = ui.commandDefinitions.addButtonDefinition(
        COMMAND_ID, "Garde-corps acier", "Implanter un garde-corps sur des faces d'appui acier.",
        addin_info.ribbon_icon("garde_corps"),
    )
    handler = Created()
    definition.commandCreated.add(handler)
    _handlers.append(handler)
    ui_layout.panel(ui, ui_layout.CREATE_PANEL_ID).controls.addCommand(definition).isPromoted = True


def stop():
    ui = core.Application.get().userInterface
    panel = ui_layout.panel(ui, ui_layout.CREATE_PANEL_ID)
    control = panel and panel.controls.itemById(COMMAND_ID)
    if control:
        control.deleteMe()
    definition = ui.commandDefinitions.itemById(COMMAND_ID)
    if definition:
        definition.deleteMe()
    _handlers.clear()
