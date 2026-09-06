"""Choix de l'image du squelette.

Ordre de priorite :
  1. l'option --image
  2. un PNG/GIF depose dans <data_dir>/image/  (`doot --paths` donne le chemin)
  3. l'image fournie avec doot (doot/assets/doot.png)
  4. rien -> le squelette ASCII de `art.py`

Formats : ceux que tkinter lit sans dependance, c'est-a-dire PNG et GIF
(y compris les GIF animes, dont les images sont jouees en boucle).
"""

from __future__ import annotations

import random
from pathlib import Path

# Ce que tkinter sait ouvrir tel quel.
IMAGE_EXTENSIONS = (".png", ".gif")

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
BUNDLED_IMAGE = ASSETS_DIR / "doot.png"


def bundled_image() -> Path | None:
    """L'image livree avec doot, ou None si le paquet n'en contient pas."""
    return BUNDLED_IMAGE if BUNDLED_IMAGE.is_file() else None


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

    `explicit` (option --image) l'emporte sur tout le reste, puis les images
    deposees par l'utilisateur, puis celle fournie avec doot.
    """
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.is_file() else None

    images = custom_images(image_dir)
    if images:
        return random.choice(images)
    return bundled_image()
