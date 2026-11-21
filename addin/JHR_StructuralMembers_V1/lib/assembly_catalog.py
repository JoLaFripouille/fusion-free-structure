"""Modèles et réglages publics en millimètres, communs au ruban et au MCP."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    default: float
    signed: bool = False
    unit: str = "mm"
    min_count: int = 1
    max_count: int = 12
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class Template:
    key: str
    family: str
    label: str
    roles: tuple
    groups: tuple


def _base_plate(width, height, thickness):
    return ("Platine", (
        Field("plate_position", "Dimensions de la platine", 0, unit="", min_count=0, max_count=1,
              choices=("Dimensions libres", "Débords autour du poteau")),
        Field("width", "Largeur", width),
        Field("height", "Longueur", height),
        Field("plate_x_minus", "Débord X−", 100),
        Field("plate_x_plus", "Débord X+", 100),
        Field("plate_y_minus", "Débord Y−", 100),
        Field("plate_y_plus", "Débord Y+", 100),
        Field("thickness", "Épaisseur", thickness),
    ))


PLATE = _base_plate(240, 280, 12)


def _base_grid(gauge, pitch, edge_x, edge_y):
    return ("Perçages", (
        Field("hole_position", "Référence des perçages", 0, unit="", min_count=0, max_count=3,
              choices=("Entraxes X et Y", "Dist. aux bords X et Y", "Bords X / entraxe Y", "Entraxe X / bords Y")),
        Field("gauge", "Entraxe transversal X", gauge),
        Field("pitch", "Entraxe longitudinal Y", pitch),
        Field("hole_edge_x", "Axe du trou au bord en X", edge_x),
        Field("hole_edge_y", "Axe du trou au bord en Y", edge_y),
        Field("hole", "Diamètre du trou", 18),
    ))


BOLT_GRID = _base_grid(190, 220, 25, 30)
BASE_GUSSET_GRID = (BOLT_GRID[0], (*BOLT_GRID[1], Field("hole_gusset_clearance", "Jeu mini aux goussets", 3)))
BASE_OPTIONS = ("Cales fourchettes", (Field("shim", "Épaisseur des cales (0 = aucune)", 0),
                                    Field("shim_clearance", "Jeu radial des encoches", 1),
                                    Field("shim_gap", "Séparation des deux cales", 20),
                                    Field("shim_inset", "Retrait aux chants extérieurs", 2)))
BASE_POSITION = ("Position", (Field("offset_x", "Déport transversal", 0, True),
                             Field("offset_y", "Déport longitudinal", 0, True)))
OFFSET_POSITION = ("Position", (Field("offset_x", "Déport transversal", 40, True),
                               Field("offset_y", "Déport longitudinal", 0, True)))
OFFSET_PLATE = _base_plate(340, 320, 15)
OFFSET_GRID = _base_grid(280, 260, 30, 30)
PLATE_CORNERS = ("Angles", (Field("chamfer", "Chanfrein (0 = aucun)", 0),
                           Field("corner_radius", "Rayon (0 = aucun)", 0)))
CUT_CORNERS = ("Angles", (Field("chamfer", "Chanfrein (0 = aucun)", 20),
                         Field("corner_radius", "Rayon (0 = aucun)", 0)))
BASE_STIFFENERS = ("Goussets d’âme", (
    Field("gusset", "Épaisseur (0 = aucun)", 0),
    Field("gusset_width", "Largeur sur la platine (0 = auto)", 0),
    Field("gusset_height", "Hauteur le long du poteau", 70),
    Field("gusset_chamfer", "Chanfrein de soudure à 45°", 0),
    Field("gusset_flat", "Méplat aux pointes", 10),
))
BASE_FLANGE_STIFFENERS = ("Goussets d’ailes", (
    Field("flange_gusset", "Épaisseur (0 = aucun)", 0),
    Field("flange_gusset_width", "Largeur sur la platine (0 = auto)", 0),
    Field("flange_gusset_height", "Hauteur le long du poteau", 70),
    Field("flange_gusset_chamfer", "Chanfrein de soudure à 45°", 0),
    Field("flange_gusset_flat", "Méplat aux pointes", 10),
))
BASE_ANCHORS = ("Ancrages droits", (
    Field("anchor_diameter", "Diamètre de tige (0 = aucune)", 0),
    Field("anchor_length", "Longueur totale de tige", 300),
    Field("anchor_projection", "Dépassement côté poteau", 35),
))
BASE_PRESET_PLATE = ("Préscellement", (
    Field("preset_thickness", "Épaisseur (0 = aucune)", 0),
    Field("preset_left", "Débord gauche (− = retrait)", 0, True),
    Field("preset_right", "Débord droit (− = retrait)", 0, True),
    Field("preset_front", "Débord avant (− = retrait)", 0, True),
    Field("preset_back", "Débord arrière (− = retrait)", 0, True),
    Field("preset_hole", "Diamètre du trou (0 = celui du pied)", 0),
    Field("preset_gap", "Écart sous la platine ou les cales", 0),
))
END_PLATE = ("Platine", (Field("width", "Largeur (0 = auto)", 0), Field("height", "Hauteur (0 = auto)", 0),
                        Field("thickness", "Épaisseur", 12), Field("top_setback", "Retrait sous le dessus de l’IPE", 5)))
RIDGE_PLATE = ("Platines", END_PLATE[1][:-1])


def end_bolts(rows):
    return ("Perçages", (Field("rows", "Rangées de deux trous", rows, unit=""),
                         Field("gauge", "Entraxe transversal (0 = auto)", 0),
                         Field("pitch", "Écart entre rangées extrêmes par zone (0 = auto)", 0),
                         Field("hole", "Diamètre du trou", 14)))


COLUMN_REINFORCEMENT = ("Raidisseurs", (Field("stiffener", "Épaisseur (0 = aucun)", 0),))
HAUNCH = ("Jarret", (Field("reach", "Longueur sous poutre", 220), Field("drop", "Hauteur au poteau", 110),
                    Field("web", "Épaisseur de l’âme", 8), Field("flange", "Épaisseur de la semelle", 10),
                    Field("flange_width", "Largeur de la semelle", 70),
                    Field("weld_relief", "Chanfrein de soudure à 45°", 20)))
SHEAR_PLATE = ("Plat d’âme", (Field("width", "Longueur le long de la poutre", 100),
                            Field("height", "Hauteur du plat", 100), Field("thickness", "Épaisseur", 8)))
SHEAR_BOLTS = ("Perçages", (Field("gauge", "Dernière colonne depuis le support", 70),
                           Field("columns", "Colonnes", 2, unit=""),
                           Field("column_step", "Entraxe longitudinal", 35),
                           Field("rows", "Rangées", 2, unit=""),
                           Field("pitch", "Entraxe vertical", 50), Field("hole", "Diamètre du trou", 14)))
FASTENERS = ("Boulonnerie", (Field("bolt", "Diamètre nominal (0 = aucun)", 12),))
SPLICE_PLATE = ("Éclisses", (Field("width", "Longueur le long des poutres", 250),
                            Field("height", "Hauteur des éclisses (0 = auto)", 0), Field("thickness", "Épaisseur", 8),
                            Field("copies", "Nombre d’éclisses d’âme", 2, unit="", max_count=2)))
SPLICE_FLANGES = ("Couvre-joints d’ailes", (
    Field("flange_covers", "Couvre-joints (0 = aucun, 1 = dessus, 2 = dessus et dessous)", 0,
          unit="", min_count=0, max_count=2),
    Field("cover_width", "Largeur du couvre-joint (0 = largeur de l’aile)", 0),
    Field("cover_thickness", "Épaisseur du couvre-joint", 8),
))
SPLICE_BOLTS = ("Perçages", (Field("end_dist", "Distance à chaque about", 30),
                            Field("column_step", "Entraxe longitudinal", 45),
                            Field("columns", "Colonnes par poutre", 2, unit=""),
                            Field("rows", "Rangées", 2, unit=""),
                            Field("pitch", "Entraxe vertical", 50), Field("hole", "Diamètre du trou", 14)))
GUSSET = ("Gousset", (Field("thickness", "Épaisseur", 8),
                     Field("edge", "Distance des axes au chant", 18),
                     Field("pad", "Largeur aux extrémités (0 = auto)", 0)))
GUSSET_HOLES = ("Perçages", (Field("rows", "Trous par diagonale", 2, unit="", min_count=2, max_count=3),
                            Field("end_dist", "Recul depuis l’about", 30),
                            Field("pitch", "Entraxe", 40),
                            Field("hole", "Diamètre du trou", 14)))
GUSSET_WELD = ("Appui sur le porteur", (
    Field("weld_face", "Face d’appui", 0, unit="", min_count=0, max_count=2,
          choices=("Automatique", "Aile", "Âme")),
    Field("weld_position", "Position de la tôle", 0, unit="", min_count=0, max_count=2,
          choices=("Suivre la cornière", "Centrée sur l’âme", "Déport réglé")),
    Field("weld_offset", "Déport de l’axe de la tôle", 0, signed=True),
    Field("weld_gap", "Jeu cornière–appui (−1 = garder l’about)", -1, signed=True),
    Field("weld_length", "Longueur du chant soudé (0 = auto)", 0),
))

BASE_ROLES = ("Poteau",)
BEAM_ROLES = ("Poteau de référence", "Poutre")
CROSS_CLEARANCE = ("Croisement", (Field("cross_gap", "Jeu entre les cornières recoupées", 2),))

TEMPLATES = (
    Template("base_ih", "Pieds de poteau", "Pied de poteau I/H", BASE_ROLES,
             (PLATE, BASE_POSITION, BASE_GUSSET_GRID, BASE_OPTIONS, BASE_STIFFENERS, BASE_FLANGE_STIFFENERS, PLATE_CORNERS,
              BASE_ANCHORS, BASE_PRESET_PLATE)),
    Template("base_tube", "Pieds de poteau", "Pied de poteau tubulaire", BASE_ROLES,
             (PLATE, BASE_POSITION, BOLT_GRID, BASE_OPTIONS, PLATE_CORNERS, BASE_ANCHORS, BASE_PRESET_PLATE)),
    Template("base_angle", "Pieds de poteau", "Pied de poteau en cornière", BASE_ROLES,
             (PLATE, BASE_POSITION, BOLT_GRID, BASE_OPTIONS, PLATE_CORNERS, BASE_ANCHORS, BASE_PRESET_PLATE)),
    Template("base_cut", "Pieds de poteau", "Pied à platine chanfreinée", BASE_ROLES,
             (PLATE, BASE_POSITION, CUT_CORNERS, BOLT_GRID, BASE_OPTIONS, BASE_ANCHORS, BASE_PRESET_PLATE)),
    Template("base_extended", "Pieds de poteau", "Pied à platine déportée", BASE_ROLES,
             (OFFSET_PLATE, OFFSET_POSITION, OFFSET_GRID, BASE_OPTIONS, PLATE_CORNERS, BASE_ANCHORS, BASE_PRESET_PLATE)),
    Template("beam_column", "Poutre-poteau", "Platine d’about", BEAM_ROLES,
             (END_PLATE, end_bolts(2), COLUMN_REINFORCEMENT, FASTENERS, PLATE_CORNERS)),
    Template("beam_column_rake", "Poutre-poteau", "About d’arbalétrier sur poteau", BEAM_ROLES,
             (END_PLATE, end_bolts(2), COLUMN_REINFORCEMENT, FASTENERS, PLATE_CORNERS)),
    Template("beam_column_haunch", "Poutre-poteau", "Platine d’about avec jarret", BEAM_ROLES,
             (END_PLATE, end_bolts(4), HAUNCH, COLUMN_REINFORCEMENT, FASTENERS, PLATE_CORNERS)),
    Template("shear_plate", "Poutre-poutre", "Plat d’âme soudé", ("Poutre principale", "Poutre secondaire"),
             (SHEAR_PLATE, SHEAR_BOLTS, FASTENERS, PLATE_CORNERS)),
    Template("splice_web", "Poutre-poutre", "Éclisses d’âme", ("Première poutre", "Deuxième poutre"),
             (SPLICE_PLATE, SPLICE_FLANGES, SPLICE_BOLTS, FASTENERS, PLATE_CORNERS)),
    Template("gusset_4", "Contreventements", "Gousset central sur quatre diagonales",
             tuple(f"Diagonale {index} (cornière)" for index in range(1, 5)), (GUSSET, GUSSET_HOLES, FASTENERS)),
    Template("gusset_cross", "Contreventements", "Croisement en X de deux cornières",
             ("Première cornière continue", "Deuxième cornière continue"),
             (GUSSET, GUSSET_HOLES, FASTENERS, CROSS_CLEARANCE)),
    *(Template(f"gusset_end_{arms}", "Contreventements",
               f"Gousset sur porteur – {arms} " + ("cornière" if arms == 1 else "cornières"),
               ("Profil porteur I/H", *(f"Diagonale {index} (cornière)" for index in range(1, arms+1))),
               (GUSSET, GUSSET_WELD, GUSSET_HOLES, FASTENERS)) for arms in (1, 2, 3)),
    Template("ridge_haunch", "Poutre-poutre", "Jarrets inférieurs de faîtage",
             ("Première poutre", "Deuxième poutre"),
             (RIDGE_PLATE, end_bolts(4), HAUNCH, FASTENERS, PLATE_CORNERS)),
    Template("ridge_double", "Poutre-poutre", "Jarrets inférieurs et supérieurs de faîtage",
             ("Première poutre", "Deuxième poutre"),
             (RIDGE_PLATE, end_bolts(6), HAUNCH, FASTENERS, PLATE_CORNERS)),
)


def recorded_parameters(template, settings):
    """Les pieds enregistrés gardent leur profil de gousset et le jeu d’origine."""
    if template.key == "base_ih":
        return {"gusset_flat": 0, "flange_gusset_flat": 0, "hole_gusset_clearance": 0, **settings}
    return settings


def template_for(key):
    for template in TEMPLATES:
        if template.key == key:
            return template
    raise ValueError("Type d’assemblage JHR inconnu.")
