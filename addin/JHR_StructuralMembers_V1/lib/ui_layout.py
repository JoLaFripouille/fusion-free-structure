from __future__ import annotations

import adsk.core


WORKSPACE_ID = "FusionSolidEnvironment"
TAB_ID = "EI_JHR_StructuralTab"
TAB_NAME = "STRUCTURE JHR"
CREATE_PANEL_ID = "EI_JHR_StructuralCreatePanel"
CREATE_PANEL_NAME = "CRÉER"
MODIFY_PANEL_ID = "EI_JHR_StructuralModifyPanel"
MODIFY_PANEL_NAME = "MODIFIER"


def _workspace(ui):
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    if not workspace:
        raise RuntimeError("L'espace de travail Conception de Fusion est introuvable.")
    return workspace


def _tab(ui):
    return _workspace(ui).toolbarTabs.itemById(TAB_ID)


def panel(ui, panel_id):
    tab = _tab(ui)
    if not tab:
        return None
    return tab.toolbarPanels.itemById(panel_id)


def start(ui):
    """Crée l'onglet et ses deux groupes avant l'ajout des commandes."""
    workspace = _workspace(ui)
    tab = workspace.toolbarTabs.itemById(TAB_ID)
    if not tab:
        tab = workspace.toolbarTabs.add(TAB_ID, TAB_NAME)
    if not tab:
        raise RuntimeError("Fusion n'a pas pu créer l'onglet STRUCTURE JHR.")

    create_panel = tab.toolbarPanels.itemById(CREATE_PANEL_ID)
    if not create_panel:
        create_panel = tab.toolbarPanels.add(CREATE_PANEL_ID, CREATE_PANEL_NAME)
    modify_panel = tab.toolbarPanels.itemById(MODIFY_PANEL_ID)
    if not modify_panel:
        modify_panel = tab.toolbarPanels.add(MODIFY_PANEL_ID, MODIFY_PANEL_NAME)
    if not create_panel or not modify_panel:
        raise RuntimeError("Fusion n'a pas pu créer les groupes de l'onglet STRUCTURE JHR.")
    return tab


def stop(ui):
    """Retire uniquement les éléments d'interface créés par le complément."""
    tab = _tab(ui)
    if not tab:
        return
    for panel_id in (MODIFY_PANEL_ID, CREATE_PANEL_ID):
        toolbar_panel = tab.toolbarPanels.itemById(panel_id)
        if toolbar_panel and toolbar_panel.isValid:
            toolbar_panel.deleteMe()
    if tab.isValid and not tab.isNative:
        tab.deleteMe()
