"""Implantation de barreaux et mesure des vides en millimètres."""

import math

from . import joint_geometry as geo


TOL = .01
MAX_CLEAR_MM = 100.


def _dimension(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} doit être une cote positive en millimètres.")
    return float(value)


def _rail_face(rail, sign):
    """Intersection de la face de contact avec les deux coupes de la lisse."""
    normal = geo.normalize(rail["v"])
    direction = geo.normalize(geo.subtract(rail["end"], rail["start"]))
    radial = geo.scale(normal, sign * rail["section"]["depth_mm"] / 2.)
    points = []
    for name in ("start", "end"):
        cut = rail.get(f"{name}_plane", direction)
        alignment = geo.dot(direction, cut)
        if alignment < 1e-4:
            raise ValueError("La coupe de lisse ne rencontre pas la face de contact.")
        offset = geo.subtract(radial, geo.scale(direction, geo.dot(radial, cut) / alignment))
        points.append(geo.add(rail[name], offset))
    return tuple(points)


def _rail_positions(rails, name, sign):
    return [(rail, _rail_face(rail, sign)) for row in rails for rail in row
            if rail["name"] == name]


def _interpolate(edge, position, station):
    start, end = edge
    fraction = (position - station(start)) / (station(end) - station(start))
    return geo.add(start, geo.scale(geo.subtract(end, start), fraction))


def _bar_support(faces, center, width, station):
    minimum, maximum = center - width / 2., center + width / 2.
    for rail, edge in faces:
        if station(edge[0]) <= minimum + TOL and station(edge[1]) >= maximum - TOL:
            return rail, _interpolate(edge, center, station)
    # Un raccord droit de deux plats conserve une même face d'appui.
    for (left, before), (right, after) in zip(faces, faces[1:]):
        if (left["section"]["type"] == right["section"]["type"] == "flat"
                and geo.length(geo.subtract(left["v"], right["v"])) <= 1e-6
                and geo.length(geo.subtract(before[1], after[0])) <= TOL
                and station(before[0]) <= minimum + TOL and station(after[1]) >= maximum - TOL):
            return left, _interpolate(before, center, station)
    raise ValueError("Un barreau chevauche une coupe de lisse. Placer un poteau au raccord.")


def _open_bays(posts, start, end, station):
    positions = sorted((station(post["start"]), post["section"]["depth_mm"] / 2.) for post in posts)
    intervals = []
    previous = start
    for center, half_depth in positions:
        beginning, ending = center - half_depth, center + half_depth
        if intervals and previous - beginning > TOL:
            raise ValueError("Deux poteaux occupent la même ouverture de barreaudage.")
        intervals.append((previous, beginning))
        previous = ending
    intervals.append((previous, end))
    return intervals, positions


def _under_rail_clearance(undersides, floors, station, up):
    gaps = []
    for _, edge in undersides:
        for floor in floors:
            start = max(station(edge[0]), station(floor[0]))
            end = min(station(edge[1]), station(floor[1]))
            if start > end:
                continue
            for position in (start, end):
                underside = _interpolate(edge, position, station)
                support = _interpolate(floor, position, station)
                gaps.append(geo.dot(geo.subtract(underside, support), up))
    if not gaps or min(gaps) < -TOL:
        raise ValueError("La lisse basse traverse le niveau de l’appui.")
    return max(0., max(gaps))


def plan_infill(rails, posts, up, settings, *, support_segments):
    """Répartit les barreaux verticaux dans les travées séparées par les poteaux.

    Les faces de contact sont coupées aux extrémités et aux onglets des lisses.
    La mesure sous lisse se réfère au parcours d'appui fourni.
    """
    allowed = _dimension(settings.get("max_clear_mm", MAX_CLEAR_MM), "Le vide maximal")
    if allowed > MAX_CLEAR_MM:
        raise ValueError("Le vide maximal du barreaudage est plafonné à 100 mm.")
    shape = settings.get("bar_shape", "square")
    if shape not in ("square", "round", "flat"):
        raise ValueError("Choisir des barreaux carrés, ronds ou plats.")
    width = _dimension(settings.get("bar_width_mm", 12.), "La largeur du barreau")
    depth = (_dimension(settings.get("bar_depth_mm", 12.), "L’épaisseur du barreau")
             if shape == "flat" else width)
    if not rails or not posts or not support_segments:
        raise ValueError("Le barreaudage exige des lisses, des poteaux et un parcours d’appui.")
    top_faces = _rail_positions(rails, "Main courante", -1.)
    bottom_faces = _rail_positions(rails, "Lisse basse", 1.)
    underside_faces = _rail_positions(rails, "Lisse basse", -1.)
    if len(top_faces) != len(rails) or len(bottom_faces) != len(rails):
        raise ValueError("Prévoir une main courante et une lisse basse par segment.")
    if any(rail["section"]["width_mm"] < depth - TOL for rail, _ in top_faces + bottom_faces):
        raise ValueError("Un barreau dépasse la largeur d’appui de sa lisse.")

    up = geo.normalize(up)
    floors = [(start, end) for start, end, *_ in support_segments]
    origin = floors[0][0]
    axis = geo.subtract(floors[0][1], origin)
    run = geo.normalize(geo.subtract(axis, geo.scale(up, geo.dot(axis, up))))
    side = geo.cross(up, run)

    def station(point):
        return geo.dot(geo.subtract(point, origin), run)

    face_edges = [edge for _, edge in top_faces + bottom_faces + underside_faces]
    if any(station(last) - station(first) <= TOL for first, last in floors + face_edges):
        raise ValueError("Le barreaudage exige un parcours horizontal continu dans le même sens.")
    rail_plane = geo.dot(geo.subtract(top_faces[0][1][0], origin), side)
    if any(abs(geo.dot(geo.subtract(point, origin), side) - rail_plane) > TOL
           for point in (*[p for face in face_edges for p in face], *(post["start"] for post in posts))):
        raise ValueError("Les lisses et les poteaux du barreaudage doivent partager le même plan.")
    start = min(station(floors[0][0]), *(station(edge[0]) for edge in face_edges))
    end = max(station(floors[-1][1]), *(station(edge[1]) for edge in face_edges))
    bays, post_positions = _open_bays(posts, start, end, station)
    for previous, following in zip(floors, floors[1:]):
        left = geo.normalize(geo.subtract(previous[1], previous[0]))
        right = geo.normalize(geo.subtract(following[1], following[0]))
        if geo.length(geo.subtract(left, right)) > 1e-6:
            bend = station(following[0])
            if not any(abs(position - bend) <= TOL for position, _ in post_positions):
                raise ValueError("Placer un poteau au raccord palier-rampant avant de répartir les barreaux.")

    bottom_clear = _under_rail_clearance(underside_faces, floors, station, up)
    if bottom_clear - allowed > 1e-6:
        raise ValueError(f"Le vide sous la lisse basse est de {bottom_clear:.2f} mm, "
                         f"pour {allowed:g} mm autorisés.")

    bars, horizontal_clear = [], 0.
    section = dict(type="round_solid" if shape == "round" else "flat",
                   width_mm=depth, depth_mm=width, wall_mm=0.)
    for beginning, ending in bays:
        opening = max(0., ending - beginning)
        count = max(0, math.ceil((opening - allowed) / (allowed + width) - 1e-12))
        gap = (opening - count * width) / (count + 1)
        if gap < 0.:
            raise ValueError("La largeur des barreaux ne permet pas de respecter le vide demandé.")
        horizontal_clear = max(horizontal_clear, gap)
        for index in range(count):
            center = beginning + gap + width / 2. + index * (width + gap)
            low_rail, bottom = _bar_support(bottom_faces, center, width, station)
            high_rail, top = _bar_support(top_faces, center, width, station)
            if geo.dot(geo.subtract(top, bottom), up) <= TOL:
                raise ValueError("La main courante ne laisse pas de hauteur de barreau au-dessus de la lisse.")
            bars.append(dict(name=f"Barreau {len(bars) + 1}", shape=shape, start=bottom, end=top,
                             direction=up, u=side, v=run, section=section,
                             bottom_normal=geo.scale(low_rail["v"], -1.), top_normal=high_rail["v"],
                             bottom_rail=low_rail, top_rail=high_rail))
    return dict(bars=tuple(bars), max_clear_mm=max(horizontal_clear, bottom_clear),
                horizontal_clear_mm=horizontal_clear, bottom_clear_mm=bottom_clear)
