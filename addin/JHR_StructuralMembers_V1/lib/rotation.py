from __future__ import annotations

import math


ANGLE_TOLERANCE_RADIANS = 1e-12


def rotate_point(point, angle_radians):
    """Fait pivoter un point 2D autour de l'origine."""
    x, y = point
    cosine = math.cos(angle_radians)
    sine = math.sin(angle_radians)
    return (
        x * cosine - y * sine,
        x * sine + y * cosine,
    )


def orientation_matrix_2d(angle_radians, flip_x=False, flip_y=False):
    """Retourne la matrice 2D commune à l'aperçu et à l'esquisse finale."""
    scale_x = -1.0 if flip_x else 1.0
    scale_y = -1.0 if flip_y else 1.0
    cosine = math.cos(angle_radians)
    sine = math.sin(angle_radians)
    return (
        cosine * scale_x,
        -sine * scale_y,
        sine * scale_x,
        cosine * scale_y,
    )


def multiply_matrices_2d(first, second):
    """Compose deux matrices 2D, la seconde étant appliquée en premier."""
    axx, axy, ayx, ayy = first
    bxx, bxy, byx, byy = second
    return (
        axx * bxx + axy * byx,
        axx * bxy + axy * byy,
        ayx * bxx + ayy * byx,
        ayx * bxy + ayy * byy,
    )


def determinant_2d(matrix):
    xx, xy, yx, yy = matrix
    return xx * yy - xy * yx


def is_identity_matrix_2d(matrix, tolerance=1e-12):
    return all(
        math.isclose(value, expected, abs_tol=tolerance)
        for value, expected in zip(matrix, (1.0, 0.0, 0.0, 1.0))
    )


def orient_point(point, angle_radians, flip_x=False, flip_y=False):
    """Applique les miroirs locaux puis la rotation autour de l'origine."""
    x, y = point
    xx, xy, yx, yy = orientation_matrix_2d(angle_radians, flip_x, flip_y)
    return (xx * x + xy * y, yx * x + yy * y)


def orient_contours(contours, angle_radians, flip_x=False, flip_y=False):
    """Oriente une copie de tous les contours autour du même ancrage origine."""
    return [
        [
            orient_point(point, angle_radians, flip_x, flip_y)
            for point in contour
        ]
        for contour in contours
    ]


def rotate_contours(contours, angle_radians):
    """Retourne une copie pivotée de tous les contours 2D."""
    return orient_contours(contours, angle_radians)


def is_effectively_zero(angle_radians):
    """Reconnaît aussi les tours complets afin d'éviter un déplacement inutile."""
    remainder = math.fmod(angle_radians, math.tau)
    return min(abs(remainder), abs(abs(remainder) - math.tau)) <= ANGLE_TOLERANCE_RADIANS


def format_degrees(angle_radians):
    """Formate l'angle pour la traçabilité sans bruit numérique."""
    degrees = math.degrees(angle_radians)
    if abs(degrees) < 5e-10:
        degrees = 0.0
    return ("{:.9f}".format(degrees)).rstrip("0").rstrip(".")
