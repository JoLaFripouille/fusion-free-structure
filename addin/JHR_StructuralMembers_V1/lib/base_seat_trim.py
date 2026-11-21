"""Coupe liée à la face intérieure d’une platine de pied."""

from . import joint_builder as joints, joint_geometry as geo


def _seat_geometry(post, plate):
    start, end = joints._line_endpoints(post.curve)
    path = geo.normalize(geo.subtract(end, start))
    inward = geo.normalize(plate.normal)
    alignment = geo.dot(path, inward)
    if abs(alignment) < .9999:
        raise ValueError("La face d’appui de la platine doit être perpendiculaire au poteau.")
    index = int(alignment < 0)
    ends = start, end
    near, far = ends[index], ends[1 - index]
    contact = geo.add(plate.origin, geo.scale(inward, plate.thickness_cm))
    tolerance = geo.PLANE_RELATION_TOLERANCE_CM
    if (geo.plane_signed_distance(near, contact, inward) >= -tolerance
            or geo.plane_signed_distance(far, contact, inward) <= tolerance):
        raise ValueError("L’épaisseur de la platine ne laisse pas un about valide sur le poteau.")
    return index, near, far, inward, contact


def verify_plate_seat(post, plate_plan):
    """Confirme que le solide finit sur la face d’appui, après création ou recalcul."""
    _, near, _, inward, contact = _seat_geometry(post, plate_plan)
    body = joints._single_body(post.occurrence, "à contrôler au droit de la platine")
    _, points = joints._planar_end_face(body, post.occurrence, geo.scale(inward, -1), near)
    if not points or any(abs(geo.plane_signed_distance(point, contact, inward)) > 1e-3 for point in points):
        raise RuntimeError("L’about du poteau ne coïncide pas avec la face d’appui de la platine.")


def trim_to_plate(post, plate_occurrence, plate_plan, created):
    """Lie le plan d’about à la fin d’extrusion de la platine, sans modifier le squelette."""
    index, near, far, inward, contact = _seat_geometry(post, plate_plan)
    outward = geo.scale(inward, -1)
    body = joints._single_body(post.occurrence, "à raccourcir pour la platine")
    treatment = joints._evaluate_treatment(
        post.occurrence, body, post.curve, index, near, far, outward, contact, inward,
    )
    if treatment.relation == "gap":
        raise ValueError("L’about du poteau est déjà en retrait de la face d’appui de la platine.")

    extrusion = plate_occurrence.component.features.extrudeFeatures.itemByName("Épaisseur de la tôle")
    if not extrusion or extrusion.endFaces.count != 1:
        raise RuntimeError("La face intérieure de la platine de pied est introuvable.")
    face = extrusion.endFaces.item(0).createForAssemblyContext(plate_occurrence)
    plane = joints._add_face_offset_plane(
        post.occurrence.component, post.occurrence, face, 0.0, "PLAN_APPUI_PLATINE_PIED",
    )
    created.append(plane)
    joints._validate_plane_match(plane, post.occurrence, contact, inward)
    joints._replace_member_end(
        treatment, joints._treatment_end_face(treatment), plane, contact, inward,
        "Coupe au niveau de la platine de pied", created,
    )
    feature = created[-1]
    verify_plate_seat(post, plate_plan)
    return feature
