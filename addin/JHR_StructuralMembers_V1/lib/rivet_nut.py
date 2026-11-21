"""Pose d'un RIVKLE acier moleté ouvert dans un perçage existant."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass

from . import bolt_geometry, bolt_specs, fastener_geometry as geometry, joint_geometry as vec
from . import simple_fastener_creator, timeline_groups


CATALOG_URL = "https://media.boellhoff.com/files/pdf13/2307-rivkle-fr.pdf"
CAD_URL = "https://www.boellhoff.com/fr-fr/services/telechargez-des-donnees-cao-rapidement-facilement-et-gratuitement/"
_COUNTERSUNK_DATASHEET_URL = ("https://eshop.boellhoff.de/out/media/pdf/"
                              "RIVKLE_Blindnietmuttern_Stahl_Senkkopf_Geraendelt_Offen___en.pdf")
HEADS = {"flat": "Tête plate", "countersunk": "Tête fraisée", "reduced": "Tête réduite"}
SCREW_HEADS = {"CHC": "Cylindrique six pans creux", "TBHC": "Bombée six pans creux"}
_BORE_MM = {4: 6., 5: 7., 6: 9., 8: 11., 10: 13.}
_MAX_BULGE_MM = {4: 8.6, 5: 10.1, 6: 13., 8: 15., 10: 18.}
_COARSE_PITCH_MM = {4: .7, 5: .8, 6: 1., 8: 1.25, 10: 1.5}


@dataclass(frozen=True)
class Specification:
    reference: str
    grip_min_mm: float
    grip_max_mm: float
    head_diameter_mm: float
    head_projection_mm: float
    blind_projection_mm: float
    countersink_depth_mm: float = 0.


# Catalogue 2307 pages 13 et 19–21, et fiche eShop des têtes fraisées.
# Finition à préciser à la commande.
# Référence, e min/max, B, E max, L2 et profondeur f (pour les têtes fraisées).
_CATALOG = {
    "flat": {
        4: (Specification("233 07 040 230", .5, 3., 9., 1., 5.8),
            Specification("233 07 040 325", 2.5, 3.25, 8., 1., 6.)),
        5: (Specification("233 07 050 230", .5, 3., 10., 1., 7.3),
            Specification("233 07 050 040", 3., 4., 10., 1., 8.)),
        6: (Specification("233 07 060 230", .5, 3., 13., 1.5, 8.),
            Specification("233 07 060 255", 3., 5.5, 13., 1.5, 8.2)),
        8: (Specification("233 07 080 230", .5, 3., 16., 1.5, 11.),
            Specification("233 07 080 255", 3., 5.5, 16., 1.5, 11.)),
        10: (Specification("233 07 100 235", .7, 3.5, 19., 2., 13.9),
             Specification("233 07 100 450", 3., 4.5, 16., 2., 14.6),
             Specification("233 07 100 600", 4.5, 6., 16., 2., 14.5)),
    },
    "countersunk": {
        4: (Specification("233 17 040 175", 1., 1.75, 8., .1, 6.3, 1.),
            Specification("233 17 040 250", 1.75, 2.5, 8., .1, 6.3, 1.2),
            Specification("233 17 040 325", 2.5, 3.25, 8., .1, 6.4, 1.2)),
        5: (Specification("233 17 050 200", 1., 2., 8.5, .1, 8.5, 1.),
            Specification("233 17 050 300", 1.5, 3., 9., .1, 8.5, 1.4),
            Specification("233 17 050 400", 3., 4., 9., .1, 8.5, 1.4),
            Specification("233 17 050 500", 4., 5., 9., .1, 8.5, 1.4)),
        6: (Specification("233 17 060 300", 1.5, 3., 10.6, .1, 10., 1.2),
            Specification("233 17 060 450", 3., 4.5, 10.6, .1, 10., 1.5),
            Specification("233 17 060 600", 4.5, 6., 10.6, .1, 10., 1.5),
            Specification("233 17 060 750", 6., 7.5, 11., .1, 10.3, 1.5)),
        8: (Specification("233 17 080 300", 1.5, 3., 12.6, .1, 11.5, 1.4),
            Specification("233 17 080 450", 3., 4.5, 13.6, .1, 11.5, 2.),
            Specification("233 17 080 600", 4.5, 6., 14., .1, 11., 2.),
            Specification("233 17 080 750", 6., 7.5, 14., .1, 11.5, 2.)),
        10: (Specification("233 17 100 300", 1.5, 3., 15., .1, 14.6, 1.4),
             Specification("233 17 100 450", 3., 4.5, 16., .1, 14.6, 2.),
             Specification("233 17 100 600", 4.5, 6., 16., .1, 14.6, 2.)),
    },
    "reduced": {
        4: (Specification("343 67 040 230", .5, 3., 6.6, .3, 5.8),
            Specification("343 67 040 040", 2.5, 4., 6.6, .4, 5.9)),
        5: (Specification("343 67 050 230", .5, 3., 8., .3, 7.4),
            Specification("343 67 050 040", 2.5, 4., 7.6, .4, 7.6)),
        6: (Specification("343 67 060 230", .5, 3., 10., .4, 8.5),
            Specification("343 67 060 045", 3., 4.5, 9.6, .3, 8.5),
            Specification("343 67 060 060", 4.5, 6., 9.6, .3, 8.5)),
        8: (Specification("343 67 080 230", .5, 3., 12., .4, 11.1),
            Specification("343 67 080 045", 3., 4.5, 11.8, .4, 11.8),
            Specification("343 67 080 060", 4.5, 6., 11.8, .4, 11.8)),
        10: (Specification("343 67 100 235", .7, 3.5, 14., .5, 14.),
             Specification("343 67 100 045", 3., 4.5, 13.8, .4, 14.),
             Specification("343 67 100 060", 4.5, 6., 13.8, .4, 14.)),
    },
}
DIAMETERS_MM = tuple(_BORE_MM)
_CATALOG_PAGES = {"flat": 20, "countersunk": 21, "reduced": 19}
_TOLERANCE_MM = geometry.POSITION_TOLERANCE_CM * 10


def _specs(diameter_mm, head):
    if head not in HEADS:
        raise ValueError("Choisir une tête plate, fraisée ou réduite.")
    rows = _CATALOG[head].get(diameter_mm)
    if not rows:
        raise ValueError("Le catalogue intégré couvre M4, M5, M6, M8 et M10.")
    return rows


def specification(diameter_mm, head, grip_mm, countersink_depth_mm=None):
    """Sélectionner la première référence compatible avec la paroi et sa préparation."""
    rows = _specs(diameter_mm, head)
    grip = geometry._positive(grip_mm, "L’épaisseur de paroi")
    candidates = [row for row in rows
                  if row.grip_min_mm - _TOLERANCE_MM <= grip <= row.grip_max_mm + _TOLERANCE_MM]
    if not candidates:
        raise ValueError(f"Aucune référence RIVKLE M{diameter_mm:g} {HEADS[head].lower()} "
                         f"pour une paroi de {grip:g} mm.")
    if countersink_depth_mm is None or head != "countersunk":
        return candidates[0]
    for row in candidates:
        if abs(countersink_depth_mm - row.countersink_depth_mm) <= _TOLERANCE_MM:
            return row
    depths = " ou ".join(f"{depth:g}" for depth in sorted({row.countersink_depth_mm for row in candidates}))
    raise ValueError(f"Fraisure à 90° attendue sur une profondeur de {depths} mm pour cette paroi.")


def preparation(diameter_mm, head, grip_mm):
    row = specification(diameter_mm, head, grip_mm)
    return _preparation(diameter_mm, head, row)


def _preparation(diameter_mm, head, row):
    return dict(reference=row.reference, hole_diameter_mm=_BORE_MM[diameter_mm],
                hole_tolerance_plus_mm=.1, countersink_depth_mm=row.countersink_depth_mm,
                countersink_angle_deg=90 if row.countersink_depth_mm else None,
                catalog_url=f"{CATALOG_URL}#page={_CATALOG_PAGES[head]}", cad_url=CAD_URL,
                datasheet_url=_COUNTERSUNK_DATASHEET_URL if head == "countersunk" else None)


def _seat(hole_face, entry_face, diameter_mm, head, allow_pilot=False):
    import adsk.core as core
    import adsk.fusion as fusion

    from . import fastener_creator as creator

    _specs(diameter_mm, head)
    face = fusion.BRepFace.cast(hole_face)
    entry = fusion.BRepFace.cast(entry_face)
    if not face or not entry or face.body != entry.body:
        raise ValueError("Le perçage et l’appui d’entrée doivent appartenir à la même pièce.")
    hole = creator.read_hole(face)
    if not isinstance(hole, geometry.Hole):
        raise ValueError("Sélectionner la paroi cylindrique intérieure du perçage rond.")
    bore_diameter_mm = hole.diameter_cm * 10
    bore_nominal_mm = _BORE_MM[diameter_mm]
    undersize = bore_diameter_mm < bore_nominal_mm - .001
    if bore_diameter_mm > bore_nominal_mm + .101 or (undersize and not allow_pilot):
        raise ValueError(f"RIVKLE M{diameter_mm:g} : perçage Ø{bore_nominal_mm:g} +0,1/0 mm, "
                         f"Ø{bore_diameter_mm:g} relevé.")
    support = creator.read_support(entry)
    alignment = vec.dot(hole.axis, support.normal)
    if abs(alignment) < 1 - geometry.PARALLEL_TOLERANCE:
        raise ValueError("La face d’entrée doit être perpendiculaire au perçage.")
    offset = vec.dot(vec.subtract(support.point, hole.center), support.normal) / alignment
    origin = vec.add(hole.center, vec.scale(hole.axis, offset))
    edges = [(edge, circle) for edge in face.edges if (circle := core.Circle3D.cast(edge.geometry))]
    if len(edges) != 2:
        raise ValueError("Choisir un perçage traversant délimité par deux cercles complets.")
    edges.sort(key=lambda pair: vec.length(vec.subtract(creator.point(pair[1].center), origin)))
    (near_edge, near_circle), (far_edge, far_circle) = edges
    near = creator.point(near_circle.center)
    far = creator.point(far_circle.center)
    axis = vec.normalize(vec.subtract(far, near))
    grip_cm = vec.dot(vec.subtract(far, origin), axis)
    approach_cm = vec.dot(vec.subtract(near, origin), axis)
    near_faces = list(near_edge.faces)
    tol = geometry.POSITION_TOLERANCE_CM

    def same_face(left, right):
        return left == right or (left.body == right.body and left.tempId == right.tempId)

    ok, normal = entry.evaluator.getNormalAtPoint(entry.pointOnFace)
    if not ok or vec.dot(creator.point(normal), axis) > -1 + geometry.PARALLEL_TOLERANCE:
        raise ValueError("Sélectionner la face extérieure du côté introduction de l’écrou.")
    for outer in far_edge.faces:
        if core.Plane.cast(outer.geometry):
            ok, normal = outer.evaluator.getNormalAtPoint(outer.pointOnFace)
            if ok and vec.dot(creator.point(normal), axis) >= 1 - geometry.PARALLEL_TOLERANCE:
                break
    else:
        raise ValueError("La sortie du perçage doit déboucher sur l’autre face plane de la paroi.")

    countersink = None
    attachment_face = face
    if head == "countersunk":
        for cone in near_faces:
            if core.Cone.cast(cone.geometry) and any(
                    same_face(neighbor, entry) for edge in cone.edges for neighbor in edge.faces):
                countersink = creator.read_countersink(cone)
                attachment_face = cone
                break
        if countersink is None:
            if not allow_pilot or abs(approach_cm) > tol or not any(same_face(f, entry) for f in near_faces):
                raise ValueError("Préparer une fraisure à 90° côté introduction avant la pose.")
        elif (vec.length(vec.subtract(countersink.center, origin)) > tol
                or abs(countersink.depth_cm - approach_cm) > tol
                or vec.dot(countersink.axis, axis) < 1 - geometry.PARALLEL_TOLERANCE
                or abs((countersink.opening_diameter_cm - countersink.diameter_cm) / 2
                       - countersink.depth_cm) > tol):
            raise ValueError("La fraisure doit être concentrique au perçage avec un angle de 90°.")
    elif abs(approach_cm) > tol or not any(same_face(candidate, entry) for candidate in near_faces):
        raise ValueError("Le perçage doit déboucher directement sur la face d’entrée plane.")

    row = specification(diameter_mm, head, grip_cm * 10, approach_cm * 10 if countersink else None)
    needs_cut = undersize or (head == "countersunk" and countersink is None)
    position = geometry.Placement(origin, *bolt_geometry.perpendicular_axes(axis), grip_cm, countersink)
    return position, row, needs_cut, attachment_face


def _cut_pilot(hole_face, entry_face, opening_edge, diameter_mm, head, position, row):
    import adsk.core as core
    import adsk.fusion as fusion
    from . import fastener_creator as creator

    body = hole_face.body.nativeObject or hole_face.body
    entry = entry_face.nativeObject or entry_face
    opening = opening_edge.nativeObject or opening_edge
    occurrence = hole_face.assemblyContext
    features = body.parentComponent.features.holeFeatures
    dia = _BORE_MM[diameter_mm]
    value = core.ValueInput.createByReal
    if row.countersink_depth_mm:
        hole = features.createCountersinkInput(value(dia*.1), value((dia+2*row.countersink_depth_mm)*.1),
                                               core.ValueInput.createByString("90 deg"))
    else:
        hole = features.createSimpleInput(value(dia*.1))
    if not hole or not hole.setPositionAtCenter(entry, opening) or not hole.setDistanceExtent(value(position.grip_cm)):
        raise RuntimeError("Fusion a refusé la préparation du perçage RIVKLE.")
    hole.tipAngle = core.ValueInput.createByString("180 deg")
    hole.participantBodies = [body]
    feature = features.add(hole)
    if not feature:
        raise RuntimeError("Fusion n’a pas créé le perçage RIVKLE.")
    try:
        if feature.healthState != fusion.FeatureHealthStates.HealthyFeatureHealthState:
            raise RuntimeError(f"Le perçage RIVKLE est en erreur : {feature.errorOrWarningMessage}")
        feature.name = f"Perçage RIVKLE Ø{dia:g}"
        stock = body.createForAssemblyContext(occurrence) if occurrence else body
        seat = entry.createForAssemblyContext(occurrence) if occurrence else entry
        for face in stock.faces:
            cylinder = core.Cylinder.cast(face.geometry)
            if not cylinder or abs(cylinder.radius-dia*.05) > 1e-4:
                continue
            offset = vec.subtract(creator.point(cylinder.origin), position.origin)
            if vec.length(vec.cross(offset, position.z_axis)) < 1e-4:
                _seat(face, seat, diameter_mm, head)
                return feature, face, seat
        raise RuntimeError("Le perçage n’a pas pu être retrouvé et mesuré après création.")
    except Exception as error:
        if feature.isValid and not feature.deleteMe():
            raise RuntimeError(f"La préparation a échoué et le perçage n’a pas été retiré : {error}") from error
        raise


def _head_front_cm(diameter_mm, row, position):
    if position.countersink:
        seat = position.countersink
        slope = (seat.opening_diameter_cm - seat.diameter_cm) / (2 * seat.depth_cm)
        return (seat.opening_diameter_cm / 2 - row.head_diameter_mm * .05) / slope
    if row.countersink_depth_mm:
        return (_BORE_MM[diameter_mm] - row.head_diameter_mm) * .05 + row.countersink_depth_mm * .1
    return -row.head_projection_mm * .1


def screw_dimensions(diameter_mm, row, position, head, length_mm=None,
                     stack_mm=0., blind_clearance_mm=None, *, screw_washer=True):
    """Longueur sous tête et enveloppe de la vis, à partir de la paroi mesurée."""
    if head not in SCREW_HEADS:
        raise ValueError("Choisir une vis CHC ou TBHC pour l’écrou à sertir.")
    spec, _ = bolt_specs.modeled_spec(diameter_mm, head)
    stack = float(stack_mm)
    if not math.isfinite(stack) or stack < 0:
        raise ValueError("L’épaisseur à serrer doit être positive ou nulle et finie.")
    # Appui sur l'insert ou la surface de la paroi s'il est en retrait.
    front = min(0., _head_front_cm(diameter_mm, row, position))
    support_cm = front - stack * .1
    pitch = _COARSE_PITCH_MM[diameter_mm]
    wall_mm = position.grip_cm * 10
    nut_end_mm = wall_mm + row.blind_projection_mm
    washer_thickness_mm = spec.washer_thickness_mm if screw_washer else 0.
    min_length = nut_end_mm + pitch - support_cm * 10 + washer_thickness_mm
    step = bolt_geometry.LENGTH_STEP_MM
    length = (math.ceil((min_length - 1e-8) / step) * step if length_mm is None else
              geometry._positive(length_mm, "La longueur sous tête"))
    if length + 1e-8 < min_length:
        raise ValueError(f"Prévoir une vis sous tête d’au moins {min_length:.2f} mm "
                         "pour traverser l’insert ouvert et dépasser d’un pas.")
    tip_mm = support_cm * 10 + length - washer_thickness_mm
    blind_projection = tip_mm - wall_mm
    if blind_clearance_mm is not None:
        clearance = geometry._positive(blind_clearance_mm, "La profondeur libre côté aveugle")
        if blind_projection > clearance + 1e-8:
            raise ValueError(f"La vis demande {blind_projection:.2f} mm côté aveugle, "
                             f"pour {clearance:g} mm disponibles.")
    return dict(head=head, designation=f"{head} M{diameter_mm:g} × {length:g}",
                length_mm=length, minimum_length_mm=min_length, stack_mm=stack,
                washer=bool(screw_washer), washer_thickness_mm=washer_thickness_mm, support_cm=support_cm,
                blind_projection_mm=blind_projection, beyond_nut_mm=tip_mm - nut_end_mm)


def _screw_shapes(diameter_mm, position, screw):
    import adsk.core as core
    import adsk.fusion as fusion

    # Générer la fixation dans le repère de la pièce serrée, puis
    # les translater dans le repère de l'insert où l'origine est la paroi.
    grip = (position.grip_cm + screw["blind_projection_mm"] * .1 - screw["support_cm"])
    parts = simple_fastener_creator.build_shapes(
        diameter_mm, screw["length_mm"], grip, projection_mm=0., tapped=True, head=screw["head"],
        head_washer=screw["washer"],
    )
    transform = core.Matrix3D.create()
    transform.translation = core.Vector3D.create(0, 0, screw["support_cm"])
    manager = fusion.TemporaryBRepManager.get()
    if not all(manager.transform(shape, transform) for shape in parts.values()):
        raise RuntimeError("Fusion n’a pas positionné la fixation sur l’insert.")
    shapes = {"Vis " + screw["designation"]: parts["vis"]}
    if screw["washer"]:
        shapes["Rondelle"] = parts["rondelle_tete"]
    return shapes


@dataclass(frozen=True)
class _BlindProfile:
    sleeve_radius: float
    bore_radius: float
    bulge_minor_radius: float
    bulge_station: float
    tip_station: float
    chamfer: float


def _blind_profile(diameter_mm, row, grip_cm):
    """Profil de présentation côté aveugle, en cm dans le repère de pose."""
    sleeve = _BORE_MM[diameter_mm] * .05 - .0005
    bore = diameter_mm * .05 + .0005
    bulge_minor = _MAX_BULGE_MM[diameter_mm] * .05 - sleeve
    # Décaler le sommet hors de la paroi tout en gardant une portée annulaire.
    bulge_station = grip_cm + .65 * bulge_minor
    tip = grip_cm + row.blind_projection_mm * .1
    free_length = tip - (bulge_station + bulge_minor)
    chamfer = min(.05, .35 * (sleeve - bore), free_length / 3)
    return _BlindProfile(sleeve, bore, bulge_minor, bulge_station, tip, chamfer)


def build_shape(diameter_mm, row, placement):
    """Écrou serti de présentation avec bourrelet arrondi et chanfrein arrière."""
    import adsk.core as core
    import adsk.fusion as fusion

    manager = fusion.TemporaryBRepManager.get()
    point = core.Point3D.create
    grip = placement.grip_cm
    blind = _blind_profile(diameter_mm, row, grip)
    sleeve = blind.sleeve_radius
    head_radius = row.head_diameter_mm * .05
    tip = blind.tip_station
    overlap = .001

    def cone(start, end, start_radius, end_radius):
        return manager.createCylinderOrCone(point(0, 0, start), start_radius,
                                            point(0, 0, end), end_radius)

    def combine(body, other, operation):
        if not body or not other or not manager.booleanOperation(body, other, operation) or not body.lumps.count:
            raise RuntimeError("Fusion n’a pas pu former le solide de l’écrou à sertir.")

    if placement.countersink:
        seat = placement.countersink
        # Positionner le cône au contact de la fraisure mesurée, à B catalogue.
        slope = (seat.opening_diameter_cm - seat.diameter_cm) / (2 * seat.depth_cm)
        front = _head_front_cm(diameter_mm, row, placement)
        transition = (seat.opening_diameter_cm / 2 - sleeve) / slope
        shoulder = cone(front, transition, head_radius, sleeve)
    else:
        front = -row.head_projection_mm * .1
        transition = 0.
        shoulder = cone(front, 0., head_radius, head_radius)

    chamfer_start = tip - blind.chamfer
    part = cone(transition - overlap, chamfer_start, sleeve, sleeve)
    combine(part, shoulder, fusion.BooleanTypes.UnionBooleanType)
    combine(part, cone(chamfer_start, tip, sleeve, sleeve - blind.chamfer),
            fusion.BooleanTypes.UnionBooleanType)

    # Tronquer le tore sur la face arrière de la paroi.
    axis = core.Vector3D.create(0, 0, 1)
    bulge = manager.createTorus(point(0, 0, 0), axis, sleeve, blind.bulge_minor_radius)
    # Le noyau peut renvoyer un tore temporaire centré à l'origine malgré le centre demandé.
    move = core.Matrix3D.create()
    move.translation = core.Vector3D.create(0, 0, blind.bulge_station)
    if not bulge or not manager.transform(bulge, move):
        raise RuntimeError("Fusion n’a pas positionné le bourrelet de l’écrou à sertir.")
    bulge_radius = sleeve + blind.bulge_minor_radius
    trim = cone(grip, tip + overlap, bulge_radius + overlap, bulge_radius + overlap)
    combine(bulge, trim, fusion.BooleanTypes.IntersectionBooleanType)
    combine(part, bulge, fusion.BooleanTypes.UnionBooleanType)

    # Passage nominal lisse pour la vis. Le filetage est indiqué par la désignation.
    combine(part, cone(front - overlap, tip + overlap, blind.bore_radius, blind.bore_radius),
            fusion.BooleanTypes.DifferenceBooleanType)
    if not part.isSolid or part.lumps.count != 1:
        raise RuntimeError("L’écrou à sertir doit former un seul solide ouvert.")
    return part


def place(design, hole_face, entry_face, diameter_mm, head, preview=False, created_entities=None,
          prepare_hole=False, *, screw_head=None, screw_length_mm=None, screw_stack_mm=0.,
          blind_clearance_mm=None, screw_washer=True, link_to_hole=False):
    """Contrôler l'implantation ou ajouter la représentation sous VISSERIE."""
    import adsk.core as core
    import adsk.fusion as fusion

    from . import fastener_creator as creator, fastener_hole_link

    if link_to_hole and design.designType != fusion.DesignTypes.ParametricDesignType:
        raise ValueError("Enregistrer l’historique de conception pour lier le RIVKLE à son trou.")
    position, row, needs_cut, attachment_face = _seat(hole_face, entry_face, diameter_mm, head,
                                                      allow_pilot=prepare_hole)
    opening = None
    if needs_cut or link_to_hole:
        opening = fastener_hole_link.source_for_pose((attachment_face,), position,
                                                     "TF" if position.countersink else "H")
    grip_mm = position.grip_cm * 10
    result = dict(_preparation(diameter_mm, head, row), designation=f"RIVKLE M{diameter_mm:g}",
                  head=head, grip_mm=grip_mm, blind_projection_mm=row.blind_projection_mm,
                  max_bulge_diameter_mm=_MAX_BULGE_MM[diameter_mm], preparation_required=needs_cut)
    screw = (screw_dimensions(diameter_mm, row, position, screw_head, screw_length_mm,
                              screw_stack_mm, blind_clearance_mm,
                              screw_washer=screw_washer) if screw_head is not None else None)
    if screw:
        result["screw"] = screw
    if preview:
        return result
    root = design.rootComponent
    if any(geometry.same_position(position, old) for old in creator.existing_positions(root)):
        return dict(result, created=0, occupied=1, parts=0, linked_to_hole=False)
    timeline = design.timeline if created_entities is None and design.designType == fusion.DesignTypes.ParametricDesignType else None
    start = timeline_groups.creation_start(timeline)
    label = "JHR - " + result["designation"] + (" avec vis" if screw else "")
    if needs_cut:
        feature, bore, entry = _cut_pilot(hole_face, entry_face, opening, diameter_mm, head, position, row)
        inserted = []
        try:
            prepared = place(design, bore, entry, diameter_mm, head, created_entities=inserted,
                             screw_head=screw_head, screw_length_mm=screw_length_mm,
                             screw_stack_mm=screw_stack_mm, blind_clearance_mm=blind_clearance_mm,
                             screw_washer=screw_washer, link_to_hole=link_to_hole)
        except Exception as error:
            if feature.isValid and not feature.deleteMe():
                raise RuntimeError(f"La pose a échoué et le perçage n’a pas été retiré : {error}") from error
            raise
        if created_entities is not None:
            created_entities.extend([feature, *inserted])
        if prepared["created"]:
            timeline_groups.group_creation(timeline, start, label)
        return dict(prepared, preparation_feature=feature.name)
    shapes = {"Écrou à sertir": build_shape(diameter_mm, row, position)}
    if screw:
        shapes.update(_screw_shapes(diameter_mm, position, screw))
    groups = [occ for occ in root.occurrences if occ.component.name.upper() == "VISSERIE"]
    if len(groups) > 1:
        raise ValueError("Plusieurs groupes VISSERIE existent ; choisir un groupe unique.")
    group = groups[0] if groups else root.occurrences.addNewComponent(core.Matrix3D.create())
    if group is None:
        raise RuntimeError("Fusion n’a pas créé le groupe VISSERIE.")
    occurrence = None
    joint = None
    try:
        if not groups:
            group.component.name = "VISSERIE"
        inverse = group.transform2.copy()
        if not inverse.invert():
            raise ValueError("Le repère VISSERIE n’est pas inversible.")
        occurrence = group.component.occurrences.addNewComponent(creator._frame_matrix(position, inverse))
        if occurrence is None:
            raise RuntimeError("Fusion n’a pas créé le composant écrou à sertir.")
        component = occurrence.component
        component.name = f"{result['designation']} - {HEADS[head]} - {row.reference}"
        component.partNumber = row.reference.replace(" ", "")
        component.description = ("Acier moleté ouvert. Géométrie installée simplifiée, passage lisse. "
                                 f"Catalogue Böllhoff 2307, page {_CATALOG_PAGES[head]}.")
        if screw:
            component.description += " Vis " + screw["designation"]
            component.description += " et rondelle." if screw["washer"] else "."
        feature = None
        if design.designType == fusion.DesignTypes.ParametricDesignType:
            feature = component.features.baseFeatures.add()
            if not feature or not feature.startEdit():
                raise RuntimeError("Fusion n’a pas ouvert la fonction de base de l’écrou.")
            feature.name = "ÉCROU À SERTIR - ÉTAT POSÉ"
        try:
            for name, shape in shapes.items():
                body = component.bRepBodies.add(shape, feature) if feature else component.bRepBodies.add(shape)
                if not body or not body.isSolid:
                    raise RuntimeError(f"Fusion n’a pas ajouté le solide « {name} ».")
                body.name = name
        finally:
            if feature and not feature.finishEdit():
                raise RuntimeError("Fusion n’a pas terminé la fonction de base de l’écrou.")
        marker = component.attributes.add(creator.ATTRIBUTE_GROUP, "configuration", json.dumps(dict(
            result, model="JHR_rivet_nut", diameter_mm=diameter_mm, grip_cm=position.grip_cm,
            linked_to_hole=bool(link_to_hole),
            screws=int(screw is not None), nuts=1, washers=int(screw is not None and screw["washer"]))))
        if not marker:
            raise RuntimeError("Fusion n’a pas enregistré la référence de l’écrou à sertir.")
        if link_to_hole:
            placed = occurrence.createForAssemblyContext(group)
            if not placed:
                raise RuntimeError("Le RIVKLE est introuvable dans le contexte de l’assemblage.")
            joint = fastener_hole_link.bind(design, placed, position, opening)
    except Exception as error:
        target = occurrence if groups else group
        if target and target.isValid and not target.deleteMe():
            raise RuntimeError(f"La pose a échoué et Fusion n’a pas retiré l’occurrence créée : {error}") from error
        raise
    if created_entities is not None:
        created_entities.append(occurrence if groups else group)
        if joint:
            created_entities.append(joint)
    timeline_groups.group_creation(timeline, start, label)
    return dict(result, created=1, occupied=0, parts=len(shapes), linked_to_hole=joint is not None)
