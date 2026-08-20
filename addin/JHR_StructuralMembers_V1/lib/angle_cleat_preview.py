from __future__ import annotations

import adsk.core
import adsk.fusion

from . import preview_geometry


CLEAT_PREVIEW_YELLOW = (255, 205, 0)
CLEAT_PREVIEW_EDGE = (170, 105, 0)


def _color_effect(color):
    return adsk.fusion.CustomGraphicsSolidColorEffect.create(
        adsk.core.Color.create(*color, 255)
    )


class DoubleAnglePreviewManager:
    """Affiche deux cornières issues du DXF sans créer d'entité Fusion."""

    def __init__(self):
        self._group = None

    def clear(self):
        if self._group and self._group.isValid:
            self._group.deleteMe()
        self._group = None
        app = adsk.core.Application.get()
        if app and app.activeViewport:
            app.activeViewport.refresh()

    def update(self, root_component, evaluation):
        self.clear()
        group = root_component.customGraphicsGroups.add()
        group.id = "EI_JHR_DOUBLE_ANGLE_PREVIEW"
        self._group = group
        yellow = _color_effect(CLEAT_PREVIEW_YELLOW)
        edge = _color_effect(CLEAT_PREVIEW_EDGE)
        try:
            for placement in evaluation.placements:
                for contour_index, contour in enumerate(
                    evaluation.angle_contours_cm,
                    start=1,
                ):
                    coordinates, triangles = preview_geometry.build_swept_side_mesh(
                        contour,
                        placement.frames,
                    )
                    graphics_coordinates = (
                        adsk.fusion.CustomGraphicsCoordinates.create(coordinates)
                    )
                    mesh = group.addMesh(graphics_coordinates, triangles, [], [])
                    mesh.name = (
                        "Aperçu jaune — cornière {} {} contour {}"
                        .format(
                            placement.side,
                            evaluation.angle_profile.designation,
                            contour_index,
                        )
                    )
                    mesh.color = yellow
                    mesh.setOpacity(0.42, True)
                    mesh.isSelectable = False

                    wires = preview_geometry.build_wire_indices(
                        len(contour),
                        len(placement.frames),
                    )
                    lines = group.addLines(graphics_coordinates, wires, False)
                    lines.name = "Contour — {}".format(mesh.name)
                    lines.color = edge
                    lines.weight = 2.0
                    lines.isSelectable = False
        except Exception:
            self.clear()
            raise
        app = adsk.core.Application.get()
        if app and app.activeViewport:
            app.activeViewport.refresh()
