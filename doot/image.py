"""Choix de l'image du squelette.

Le depot n'embarque aucune image : par defaut, doot dessine son squelette en
ASCII (voir `art.py`). Depose un PNG ou un GIF dans <data_dir>/image/ et il
prend le relais. `doot --paths` donne le chemin du dossier.

Formats : ceux que tkinter lit sans dependance, c'est-a-dire PNG et GIF
(y compris les GIF animes, dont les images sont jouees en boucle).
"""

from __future__ import annotations

import random
from pathlib import Path

# Ce que tkinter sait ouvrir tel quel.
IMAGE_EXTENSIONS = (".png", ".gif")


def custom_images(image_dir: Path) -> list[Path]:
    """Images deposees par l'utilisateur, triees par nom."""
    if not image_dir.is_dir():
        return []
    return sorted(
        p for p in image_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )


def pick_image(image_dir: Path, explicit: Path | str | None = None) -> Path | None:
    """Image a afficher, ou None pour retomber sur l'ASCII art.

    `explicit` (option --image) l'emporte sur le contenu du dossier.
    """
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.is_file() else None

    images = custom_images(image_dir)
    return random.choice(images) if images else None
