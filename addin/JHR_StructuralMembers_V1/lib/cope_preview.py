from __future__ import annotations

import adsk.core
import adsk.fusion

from . import cope_geometry, preview_geometry


COPE_PREVIEW_RED = (230, 35, 35)
COPE_PREVIEW_EDGE = (130, 0, 0)
WEB_CUT_ORANGE = (255, 140, 0)
WEB_CUT_EDGE = (180, 55, 0)
PRIMARY_EXTENSION_GREEN = (35, 190, 90)
PRIMARY_EXTENSION_EDGE = (0, 105, 45)


def _color_effect(color):
    return adsk.fusion.CustomGraphicsSolidColorEffect.create(
        adsk.core.Color.create(*color, 255)
    )


def _add_graphics(
    group,
    coordinates,
    triangles,
    wires,
    name,
    mesh_color,
    edge_color,
    opacity,
):
    graphics_coordinates = adsk.fusion.CustomGraphicsCoordinates.create(coordinates)
    mesh = group.addMesh(graphics_coordinates, triangles, [], [])
    mesh.name = name
    mesh.color = mesh_color
    mesh.setOpacity(opacity, True)
    mesh.isSelectable = False
    lines = group.addLines(graphics_coordinates, wires, False)
    lines.name = "Contour — {}".format(name)
    lines.color = edge_color
    lines.weight = 2.0
    lines.isSelectable = False


class CopePreviewManager:
    """Affiche retraits, coupe d'âme et prolongements sans fonction Fusion."""

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
        group.id = "EI_JHR_COPE_PREVIEW"
        self._group = group
        red = _color_effect(COPE_PREVIEW_RED)
        red_edge = _color_effect(COPE_PREVIEW_EDGE)
        orange = _color_effect(WEB_CUT_ORANGE)
        orange_edge = _color_effect(WEB_CUT_EDGE)
        green = _color_effect(PRIMARY_EXTENSION_GREEN)
        green_edge = _color_effect(PRIMARY_EXTENSION_EDGE)
        try:
            for volume in evaluation.volumes:
                coordinates, triangles, wires = cope_geometry.volume_mesh(
                    volume,
                    evaluation.origin,
                    evaluation.profile_x_axis,
                    evaluation.profile_y_axis,
                    evaluation.axial_axis,
                )
                _add_graphics(
                    group,
                    coordinates,
                    triangles,
                    wires,
                    "Retrait rouge — {}".format(volume.name),
                    red,
                    red_edge,
                    0.38,
                )

            plane_coordinates, plane_triangles, plane_wires = (
                cope_geometry.section_plane_mesh(
                    evaluation.profile_geometry,
                    evaluation.secondary_anchor_mm,
                    evaluation.web_cut_point,
                    evaluation.profile_x_axis,
                    evaluation.profile_y_axis,
                )
            )
            _add_graphics(
                group,
                plane_coordinates,
                plane_triangles,
                plane_wires,
                "Plan orange — coupe contre l'âme principale",
                orange,
                orange_edge,
                0.32,
            )

            if evaluation.primary_extension_segments:
                contours = preview_geometry.tessellate_profile_contours_cm(
                    evaluation.primary_profile_source,
                    evaluation.primary_anchor_mm,
                )
                for extension_index, (start_point, end_point) in enumerate(
                    evaluation.primary_extension_segments,
                    start=1,
                ):
                    frames = (
                        (
                            start_point,
                            evaluation.primary_profile_x_axis,
                            evaluation.primary_profile_y_axis,
                        ),
                        (
                            end_point,
                            evaluation.primary_profile_x_axis,
                            evaluation.primary_profile_y_axis,
                        ),
                    )
                    for contour_index, contour in enumerate(contours, start=1):
                        coordinates, triangles = (
                            preview_geometry.build_swept_side_mesh(contour, frames)
                        )
                        wires = preview_geometry.build_wire_indices(len(contour), 2)
                        _add_graphics(
                            group,
                            coordinates,
                            triangles,
                            wires,
                            "Ajout vert — prolongement principal {}.{}".format(
                                extension_index,
                                contour_index,
                            ),
                            green,
                            green_edge,
                            0.34,
                        )
        except Exception:
            self.clear()
            raise
        app = adsk.core.Application.get()
        if app and app.activeViewport:
            app.activeViewport.refresh()
