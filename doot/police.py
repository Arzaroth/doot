"""Une fonte matricielle de 5x7, dessinee a la main.

doot n'embarque aucune fonte et n'en veut pas. Celles du systeme ne sont
lisibles que par tkinter, qui ne sait pas rendre dans un PNG ; en installer une
ajouterait un fichier binaire et une licence a un projet qui tient sur la
bibliotheque standard. Une carte de fin de saison a pourtant besoin de chiffres.

Sept lignes de cinq points par signe, ecrites en clair, dans l'esprit de l'art
ASCII du squelette : on les relit, on les corrige au caractere pres, et elles
ne pesent rien. Les minuscules montent en capitales, une fonte de cette taille
n'ayant pas la place d'une hampe.
"""

from __future__ import annotations

LARGEUR = 5
HAUTEUR = 7
INTERLETTRE = 1

_DESSINS = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": (".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "0": (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": ("#####", "...#.", "..#..", "...#.", "....#", "#...#", ".###."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": ("..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."),
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    ".": (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
    ",": (".....", ".....", ".....", ".....", ".##..", ".##..", ".#..."),
    ":": (".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."),
    "-": (".....", ".....", ".....", "#####", ".....", ".....", "....."),
    "+": (".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."),
    "/": ("....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."),
    "!": ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
    "?": (".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."),
    "'": ("..#..", "..#..", ".....", ".....", ".....", ".....", "....."),
    "(": ("...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."),
    ")": (".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."),
    "%": ("##..#", "##.#.", "...#.", "..#..", ".#...", "#.##.", "..##."),
    "*": (".....", "#.#.#", ".###.", "#####", ".###.", "#.#.#", "....."),
}

# Les accents n'ont pas de place sur sept lignes. Plutot que d'avaler le signe
# entier, on garde la lettre : "MELODIE" vaut mieux qu'un trou.
_SANS_ACCENT = str.maketrans({
    "À": "A", "Â": "A", "Ä": "A", "Ç": "C", "É": "E", "È": "E", "Ê": "E",
    "Ë": "E", "Î": "I", "Ï": "I", "Ô": "O", "Ö": "O", "Ù": "U", "Û": "U",
    "Ü": "U", "Ÿ": "Y", "Œ": "OE", "Æ": "AE", "’": "'", "—": "-", "–": "-",
})


def normaliser(texte: str) -> str:
    """Le texte tel qu'il sera dessine : capitales, sans accent, signes connus.

    Ce qui reste introuvable devient une espace plutot qu'un pave d'erreur. Une
    carte se regarde, elle ne se debogue pas.
    """
    if not isinstance(texte, str):
        texte = str(texte)
    montee = texte.upper().translate(_SANS_ACCENT)
    return "".join(signe if signe in _DESSINS else " " for signe in montee)


def largeur(texte: str, echelle: int = 1) -> int:
    """La place que prendra le texte, sans l'espace qui suivrait le dernier signe."""
    signes = len(normaliser(texte))
    if not signes:
        return 0
    echelle = max(1, int(echelle))
    return (signes * LARGEUR + (signes - 1) * INTERLETTRE) * echelle


def hauteur(echelle: int = 1) -> int:
    return HAUTEUR * max(1, int(echelle))


def ecrire(toile, texte: str, x: int, y: int, couleur, echelle: int = 1) -> int:
    """Pose le texte sur la toile et renvoie la largeur ecrite.

    Chaque point devient un carre de `echelle` cotes. Rendre la largeur evite a
    l'appelant de la recalculer pour enchainer deux morceaux de couleurs
    differentes sur une meme ligne.
    """
    echelle = max(1, int(echelle))
    pas = (LARGEUR + INTERLETTRE) * echelle
    for index, signe in enumerate(normaliser(texte)):
        dessin = _DESSINS[signe]
        origine = int(x) + index * pas
        for ligne, motif in enumerate(dessin):
            for colonne, point in enumerate(motif):
                if point == "#":
                    toile.rectangle(
                        origine + colonne * echelle,
                        int(y) + ligne * echelle,
                        echelle, echelle, couleur,
                    )
    return largeur(texte, echelle)


def centrer(toile, texte: str, y: int, couleur, echelle: int = 1) -> int:
    """Le meme texte, pose au milieu de la toile."""
    return ecrire(
        toile, texte, (toile.width - largeur(texte, echelle)) // 2, y,
        couleur, echelle,
    )
