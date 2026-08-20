import traceback

import adsk.core
import adsk.fusion

from .commands import (
    create_cope,
    create_joint,
    create_members,
    inspect_member,
    manage_custom_profiles,
)
from .lib import addin_info, structural_materials, ui_layout


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if design:
            result = structural_materials.ensure_required_materials(
                design,
                app.materialLibraries,
            )
            app.log(
                "{} Matériaux EI_JHR: {} existant(s), {} créé(s)."
                .format(
                    addin_info.LOG_PREFIX,
                    len(result.existing_names),
                    len(result.created_names),
                )
            )
        ui_layout.start(ui)
        create_members.start()
        create_joint.start()
        create_cope.start()
        inspect_member.start()
        manage_custom_profiles.start()
    except Exception:
        if ui:
            ui.messageBox(
                "Échec du démarrage de {}:\n{}"
                .format(addin_info.DISPLAY_NAME, traceback.format_exc())
            )


def stop(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        manage_custom_profiles.stop()
        inspect_member.stop()
        create_cope.stop()
        create_joint.stop()
        create_members.stop()
        ui_layout.stop(ui)
    except Exception:
        if ui:
            ui.messageBox(
                "Échec de l'arrêt de {}:\n{}"
                .format(addin_info.DISPLAY_NAME, traceback.format_exc())
            )
