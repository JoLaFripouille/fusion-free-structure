import traceback

import adsk.core

from .commands import create_members
from .lib import addin_info


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        create_members.start()
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
        create_members.stop()
    except Exception:
        if ui:
            ui.messageBox(
                "Échec de l'arrêt de {}:\n{}"
                .format(addin_info.DISPLAY_NAME, traceback.format_exc())
            )
