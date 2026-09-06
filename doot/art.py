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


def frame(index: int) -> str:
    """Rend l'image `index` (bornee) : lettres volantes + squelette."""
    index = max(0, min(index, len(DOOT_FRAMES) - 1))
    return DOOT_FRAMES[index] + "\n" + SKULL


def widest_frame() -> str:
    """Image la plus large, pour dimensionner la fenetre avant l'animation."""
    return frame(len(DOOT_FRAMES) - 1)


def size() -> tuple[int, int]:
    """(colonnes, lignes) de l'art complet."""
    lines = widest_frame().split("\n")
    return max(len(line) for line in lines), len(lines)
