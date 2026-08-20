from __future__ import annotations

from dataclasses import dataclass

from . import dxf_geometry, joint_geometry


MM_TO_CM = 0.1
PROFILE_TOLERANCE_MM = 1e-5
SIDE_OVERSIZE_CM = 0.05
END_OVERRUN_CM = 0.05
WEB_AXIS_ALIGNMENT_TOLERANCE = 0.995
PLANE_MARGIN_CM = 0.5


@dataclass(frozen=True)
class IProfileGeometry:
    min_x_mm: float
    min_y_mm: float
    max_x_mm: float
    max_y_mm: float
    web_min_x_mm: float
    web_max_x_mm: float
    web_min_y_mm: float
    web_max_y_mm: float

    @property
    def bounds_mm(self):
        return self.min_x_mm, self.min_y_mm, self.max_x_mm, self.max_y_mm

    @property
    def width_mm(self):
        return self.max_x_mm - self.min_x_mm

    @property
    def height_mm(self):
        return self.max_y_mm - self.min_y_mm

    @property
    def bottom_cope_height_mm(self):
        return self.web_min_y_mm - self.min_y_mm

    @property
    def top_cope_height_mm(self):
        return self.max_y_mm - self.web_max_y_mm


@dataclass(frozen=True)
class CopeVolume:
    name: str
    x_min_cm: float
    x_max_cm: float
    y_min_cm: float
    y_max_cm: float
    axial_min_cm: float
    axial_max_cm: float


BOX_TRIANGLES = (
    0, 2, 1, 0, 3, 2,
    4, 5, 6, 4, 6, 7,
    0, 1, 5, 0, 5, 4,
    1, 2, 6, 1, 6, 5,
    2, 3, 7, 2, 7, 6,
    3, 0, 4, 3, 4, 7,
)

BOX_WIRES = (
    0, 1, 1, 2, 2, 3, 3, 0,
    4, 5, 5, 6, 6, 7, 7, 4,
    0, 4, 1, 5, 2, 6, 3, 7,
)


def analyze_i_profile_vertices(vertices):
    """Déduit les limites de semelles et d'âme d'un contour I/H symétrique."""
    points = tuple((float(x), float(y)) for x, y, *_ in vertices)
    if len(points) < 8:
        raise ValueError("Le contour IPE ne contient pas assez de sommets.")
    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    center_x = (min_x + max_x) / 2.0
    distances = sorted(
        {
            abs(point[0] - center_x)
            for point in points
            if abs(point[0] - center_x) > PROFILE_TOLERANCE_MM
        }
    )
    if not distances:
        raise ValueError("L'épaisseur de l'âme du profil IPE est indétectable.")
    web_half_width = distances[0]
    web_points = tuple(
        point
        for point in points
        if abs(abs(point[0] - center_x) - web_half_width) <= PROFILE_TOLERANCE_MM
    )
    if len(web_points) < 4:
        raise ValueError("Les raccords entre l'âme et les semelles sont indétectables.")
    web_min_y = min(point[1] for point in web_points)
    web_max_y = max(point[1] for point in web_points)
    if not (min_y < web_min_y < web_max_y < max_y):
        raise ValueError("Le contour ne présente pas une âme IPE exploitable.")
    return IProfileGeometry(
        min_x_mm=min_x,
        min_y_mm=min_y,
        max_x_mm=max_x,
        max_y_mm=max_y,
        web_min_x_mm=center_x - web_half_width,
        web_max_x_mm=center_x + web_half_width,
        web_min_y_mm=web_min_y,
        web_max_y_mm=web_max_y,
    )


def analyze_i_profile_dxf(dxf_path):
    contours = dxf_geometry.tessellate_profile_contours_mm(dxf_path, 5.0)
    if len(contours) != 1:
        raise ValueError("Le profil I/H doit contenir un unique contour fermé.")
    return analyze_i_profile_vertices(contours[0])


def web_face_cut_point(
    profile,
    anchor_mm,
    joint_point,
    profile_x_axis,
    toward_secondary,
    web_clearance_cm,
):
    """Place la coupe secondaire sur la face de l'âme orientée vers celle-ci."""
    if web_clearance_cm < 0.0:
        raise ValueError("Le jeu contre l'âme ne peut pas être négatif.")
    profile_x = joint_geometry.normalize(profile_x_axis)
    toward = joint_geometry.normalize(toward_secondary)
    alignment = joint_geometry.dot(profile_x, toward)
    if abs(alignment) < WEB_AXIS_ALIGNMENT_TOLERANCE:
        raise ValueError(
            "L'âme de la principale n'est pas orientée face à la secondaire."
        )
    anchor_x_mm = float(anchor_mm[0])
    face_x_mm = (
        profile.web_max_x_mm if alignment > 0.0 else profile.web_min_x_mm
    )
    face_point = joint_geometry.add(
        joint_point,
        joint_geometry.scale(
            profile_x,
            (face_x_mm - anchor_x_mm) * MM_TO_CM,
        ),
    )
    return joint_geometry.add(
        face_point,
        joint_geometry.scale(toward, float(web_clearance_cm)),
    )


def double_cope_volumes(
    profile,
    anchor_mm,
    depth_cm,
    vertical_clearance_cm,
):
    if depth_cm <= joint_geometry.GEOMETRY_TOLERANCE_CM:
        raise ValueError("La profondeur automatique du grugeage est nulle.")
    if vertical_clearance_cm < 0.0:
        raise ValueError("Le jeu vertical du grugeage ne peut pas être négatif.")
    anchor_x_mm, anchor_y_mm = anchor_mm
    x_min = (profile.min_x_mm - anchor_x_mm) * MM_TO_CM - SIDE_OVERSIZE_CM
    x_max = (profile.max_x_mm - anchor_x_mm) * MM_TO_CM + SIDE_OVERSIZE_CM
    bottom_min = (
        (profile.min_y_mm - anchor_y_mm) * MM_TO_CM - SIDE_OVERSIZE_CM
    )
    bottom_max = (
        (profile.web_min_y_mm - anchor_y_mm) * MM_TO_CM
        + vertical_clearance_cm
    )
    top_min = (
        (profile.web_max_y_mm - anchor_y_mm) * MM_TO_CM
        - vertical_clearance_cm
    )
    top_max = (
        (profile.max_y_mm - anchor_y_mm) * MM_TO_CM + SIDE_OVERSIZE_CM
    )
    if bottom_max >= top_min:
        raise ValueError("Le jeu vertical supprimerait toute l'âme de l'IPE.")
    axial_min = -float(depth_cm)
    return (
        CopeVolume(
            "Grugeage inférieur",
            x_min,
            x_max,
            bottom_min,
            bottom_max,
            axial_min,
            END_OVERRUN_CM,
        ),
        CopeVolume(
            "Grugeage supérieur",
            x_min,
            x_max,
            top_min,
            top_max,
            axial_min,
            END_OVERRUN_CM,
        ),
    )


def depth_to_facing_support(
    joint_point,
    approach_direction,
    plane_normal,
    primary_body_points,
):
    """Mesure la profondeur depuis l'axe commun jusqu'à la face principale visible."""
    if not primary_body_points:
        raise ValueError("La barre principale ne contient aucun point exploitable.")
    approach = joint_geometry.normalize(approach_direction)
    normal = joint_geometry.normalize(plane_normal)
    rate = joint_geometry.dot(approach, normal)
    if abs(rate) <= joint_geometry.GEOMETRY_TOLERANCE_CM:
        raise ValueError("L'axe secondaire est parallèle au plan d'appui principal.")
    joint_station = joint_geometry.dot(joint_point, normal)
    facing_station = max(
        joint_geometry.dot(point, normal) for point in primary_body_points
    )
    depth_cm = (joint_station - facing_station) / rate
    if depth_cm <= joint_geometry.PLANE_RELATION_TOLERANCE_CM:
        raise ValueError(
            "L'enveloppe de la principale ne traverse pas l'extrémité secondaire."
        )
    return depth_cm


def world_point(origin, x_axis, y_axis, axial_axis, x, y, axial):
    return tuple(
        origin[index]
        + x_axis[index] * x
        + y_axis[index] * y
        + axial_axis[index] * axial
        for index in range(3)
    )


def section_plane_mesh(profile, anchor_mm, origin, x_axis, y_axis):
    x_axis = joint_geometry.normalize(x_axis)
    y_axis = joint_geometry.normalize(y_axis)
    anchor_x, anchor_y = anchor_mm
    x_min = (profile.min_x_mm - anchor_x) * MM_TO_CM - PLANE_MARGIN_CM
    x_max = (profile.max_x_mm - anchor_x) * MM_TO_CM + PLANE_MARGIN_CM
    y_min = (profile.min_y_mm - anchor_y) * MM_TO_CM - PLANE_MARGIN_CM
    y_max = (profile.max_y_mm - anchor_y) * MM_TO_CM + PLANE_MARGIN_CM
    points = (
        world_point(origin, x_axis, y_axis, (0.0, 0.0, 1.0), x_min, y_min, 0.0),
        world_point(origin, x_axis, y_axis, (0.0, 0.0, 1.0), x_max, y_min, 0.0),
        world_point(origin, x_axis, y_axis, (0.0, 0.0, 1.0), x_max, y_max, 0.0),
        world_point(origin, x_axis, y_axis, (0.0, 0.0, 1.0), x_min, y_max, 0.0),
    )
    return (
        tuple(value for point in points for value in point),
        (0, 1, 2, 0, 2, 3),
        (0, 1, 1, 2, 2, 3, 3, 0),
    )


def volume_mesh(volume, origin, x_axis, y_axis, axial_axis):
    x_axis = joint_geometry.normalize(x_axis)
    y_axis = joint_geometry.normalize(y_axis)
    axial_axis = joint_geometry.normalize(axial_axis)
    local_points = (
        (volume.x_min_cm, volume.y_min_cm, volume.axial_min_cm),
        (volume.x_max_cm, volume.y_min_cm, volume.axial_min_cm),
        (volume.x_max_cm, volume.y_max_cm, volume.axial_min_cm),
        (volume.x_min_cm, volume.y_max_cm, volume.axial_min_cm),
        (volume.x_min_cm, volume.y_min_cm, volume.axial_max_cm),
        (volume.x_max_cm, volume.y_min_cm, volume.axial_max_cm),
        (volume.x_max_cm, volume.y_max_cm, volume.axial_max_cm),
        (volume.x_min_cm, volume.y_max_cm, volume.axial_max_cm),
    )
    points = tuple(
        world_point(origin, x_axis, y_axis, axial_axis, *point)
        for point in local_points
    )
    coordinates = tuple(value for point in points for value in point)
    return coordinates, BOX_TRIANGLES, BOX_WIRES
