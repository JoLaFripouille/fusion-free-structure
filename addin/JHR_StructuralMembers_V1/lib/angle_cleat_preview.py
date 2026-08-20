from __future__ import annotations

import adsk.core
import adsk.fusion

from . import angle_cleat_geometry, joint_geometry, preview_geometry


CLEAT_PREVIEW_YELLOW = (255, 205, 0)
CLEAT_PREVIEW_EDGE = (170, 105, 0)
HOLE_PREVIEW_RED = (235, 55, 45)
BOLT_PREVIEW_BLUE = (30, 125, 255)


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
        hole_red = _color_effect(HOLE_PREVIEW_RED)
        bolt_blue = _color_effect(BOLT_PREVIEW_BLUE)
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

                primary_centers, secondary_centers = (
                    angle_cleat_geometry.hole_centers_for_placement(
                        placement,
                        evaluation.hole_pattern,
                    )
                )
                bottom = placement.frames[0][0]
                top = placement.frames[-1][0]
                vertical = joint_geometry.normalize(
                    joint_geometry.subtract(top, bottom)
                )
                outward = placement.frames[0][1]
                toward_secondary = placement.frames[0][2]
                for branch, centers, first_axis in (
                    ("principale", primary_centers, outward),
                    ("secondaire", secondary_centers, toward_secondary),
                ):
                    for row_index, center in enumerate(centers, start=1):
                        coordinates, indices = preview_geometry.build_circle_wire(
                            center,
                            first_axis,
                            vertical,
                            evaluation.hole_pattern.diameter_cm / 2.0,
                        )
                        graphics_coordinates = (
                            adsk.fusion.CustomGraphicsCoordinates.create(coordinates)
                        )
                        ring = group.addLines(
                            graphics_coordinates,
                            indices,
                            False,
                        )
                        ring.name = (
                            "Perçage rouge — cornière {} branche {} rangée {}"
                            .format(placement.side, branch, row_index)
                        )
                        ring.color = hole_red
                        ring.weight = 3.0
                        ring.isSelectable = False

            spec = evaluation.bolt_spec
            head_height_cm = spec.head_height_mm * 0.1
            for bolt in evaluation.bolt_placements:
                pieces = (
                    (
                        joint_geometry.subtract(
                            bolt.origin,
                            joint_geometry.scale(bolt.z_axis, head_height_cm),
                        ),
                        spec.head_across_flats_mm * 0.1 / 2.0,
                        head_height_cm,
                        "tête",
                    ),
                    (
                        bolt.origin,
                        spec.nominal_diameter_mm * 0.1 / 2.0,
                        bolt.bolt_length_cm,
                        "tige",
                    ),
                )
                for origin, radius, length, label in pieces:
                    coordinates, indices = preview_geometry.build_cylinder_wire(
                        origin,
                        bolt.z_axis,
                        radius,
                        length,
                    )
                    graphics_coordinates = (
                        adsk.fusion.CustomGraphicsCoordinates.create(coordinates)
                    )
                    wire = group.addLines(graphics_coordinates, indices, False)
                    wire.name = "Boulon bleu — {} — {}".format(
                        bolt.name_suffix,
                        label,
                    )
                    wire.color = bolt_blue
                    wire.weight = 2.0
                    wire.isSelectable = False
        except Exception:
            self.clear()
            raise
        app = adsk.core.Application.get()
        if app and app.activeViewport:
            app.activeViewport.refresh()
