"""ASCII art du squelette trompettiste et animation du "doot"."""

from __future__ import annotations

SKULL = r'''
            .-"""""""-.
          .'           '.
         /   .-.   .-.   \
        |   ( o ) ( o )   |                  .-----.
        |       ___       |             ,--''       '.
        |      /   \      |            /             \
        |     |=====|     |   ,-------'               |
         \    |||||||========(                        |
          '.  |||||  .'       '------.                |
            '-._____.-'               \              /
             /|     |\                 '--.        ,'
            / |     | \                     '-----'
'''.strip("\n")

# Les lettres qui s'echappent du pavillon, image par image.
DOOT_FRAMES = (
    "                                                            ",
    "                                                    d       ",
    "                                                 d    o     ",
    "                                              d    o    o   ",
    "                                           d    o    o    t ",
    "                                        d    o    o    t   !",
)

FRAME_MS = 240  # duree d'affichage d'une image du "doot"


# Caracteres qui pointent d'un cote et doivent basculer avec l'image.
_MIROIR = str.maketrans("/\\()[]{}<>", "\\/)(][}{><")


def _largeur(bloc: str) -> int:
    return max(len(ligne) for ligne in bloc.split("\n"))


def _mirror_bloc(bloc: str, largeur: int) -> str:
    lignes = bloc.split("\n")
    return "\n".join(
        ligne.ljust(largeur)[::-1].translate(_MIROIR) for ligne in lignes
    )


def _mirror_lettres(ligne: str, largeur: int) -> str:
    """Renvoie les lettres de l'autre cote, sans les rendre illisibles.

    Renverser la ligne telle quelle donnerait « ! t o o d ». On renverse donc
    les positions, puis on y repose les lettres dans leur ordre de lecture.
    """
    renverse = list(ligne.ljust(largeur)[::-1])
    lettres = [c for c in ligne if not c.isspace()]
    places = [i for i, c in enumerate(renverse) if not c.isspace()]
    for place, lettre in zip(places, lettres):
        renverse[place] = lettre
    return "".join(renverse)


def frame(index: int, mirrored: bool = False) -> str:
    """Rend l'image `index` (bornee) : lettres volantes + squelette.

    `mirrored` retourne l'ensemble, pour que le squelette regarde vers
    l'interieur de l'ecran quand il entre par la droite.
    """
    index = max(0, min(index, len(DOOT_FRAMES) - 1))
    lettres = DOOT_FRAMES[index]
    if not mirrored:
        return lettres + "\n" + SKULL

    largeur = max(_largeur(SKULL), len(lettres))
    return _mirror_lettres(lettres, largeur) + "\n" + _mirror_bloc(SKULL, largeur)


def widest_frame() -> str:
    """Image la plus large, pour dimensionner la fenetre avant l'animation."""
    return frame(len(DOOT_FRAMES) - 1)


def size() -> tuple[int, int]:
    """(colonnes, lignes) de l'art complet."""
    lines = widest_frame().split("\n")
    return max(len(line) for line in lines), len(lines)
