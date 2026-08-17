from __future__ import annotations

import math


FRAME_TOLERANCE = 1e-6


def _parameter_bounds(curve):
    evaluator = curve.worldGeometry.evaluator
    success, minimum, maximum = evaluator.getParameterExtents()
    if not success:
        raise RuntimeError("Impossible de lire les limites du chemin.")
    return evaluator, minimum, maximum


def _sketch_normal(curve):
    sketch = curve.parentSketch
    normal = sketch.xDirection.crossProduct(sketch.yDirection)
    if not normal.normalize():
        raise RuntimeError("Impossible de calculer la normale de l'esquisse.")
    return normal


def frame_at_parameter(curve, parameter, evaluator=None, normal=None):
    """Retourne le point et les deux axes de section employés par l'aperçu."""
    if evaluator is None:
        evaluator = curve.worldGeometry.evaluator
    if normal is None:
        normal = _sketch_normal(curve)
    point_ok, point = evaluator.getPointAtParameter(parameter)
    tangent_ok, tangent = evaluator.getTangent(parameter)
    if not point_ok or not tangent_ok or not tangent.normalize():
        raise RuntimeError("Impossible d'évaluer le chemin.")
    x_axis = normal.crossProduct(tangent)
    if not x_axis.normalize():
        raise RuntimeError("Impossible d'orienter la section sur le chemin.")
    return point, x_axis, normal


def frame_at_fraction(curve, fraction):
    if fraction < 0.0 or fraction > 1.0:
        raise ValueError("La position sur le chemin doit être comprise entre 0 et 1.")
    evaluator, minimum, maximum = _parameter_bounds(curve)
    parameter = minimum + (maximum - minimum) * fraction
    return frame_at_parameter(
        curve,
        parameter,
        evaluator=evaluator,
        normal=_sketch_normal(curve),
    )


def frames_for_curve(curve, sample_count):
    if sample_count < 2:
        raise ValueError("L'aperçu exige au moins deux sections du chemin.")
    evaluator, minimum, maximum = _parameter_bounds(curve)
    normal = _sketch_normal(curve)
    return tuple(
        frame_at_parameter(
            curve,
            minimum + (maximum - minimum) * index / (sample_count - 1),
            evaluator=evaluator,
            normal=normal,
        )
        for index in range(sample_count)
    )


def basis_change_2d(current_x, current_y, target_x, target_y):
    """Exprime les axes cibles de l'aperçu dans les axes réels de l'esquisse."""
    matrix = (
        current_x.dotProduct(target_x),
        current_x.dotProduct(target_y),
        current_y.dotProduct(target_x),
        current_y.dotProduct(target_y),
    )
    determinant = matrix[0] * matrix[3] - matrix[1] * matrix[2]
    if not math.isclose(abs(determinant), 1.0, abs_tol=FRAME_TOLERANCE):
        raise RuntimeError(
            "Les axes du plan de profil ne correspondent pas au repère du chemin."
        )
    return matrix
