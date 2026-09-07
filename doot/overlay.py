"""La boucle d'animation, commune aux overlays qui composent leurs pixels.

`x11.py` et `wayland.py` posent leur surface par des chemins sans rapport, mais
une fois a l'ecran ils font la meme chose : glisser depuis un bord, monter en
fondu, tenir, redescendre. Seul le support change, donc seule la creation de la
surface leur appartient.

Un overlay est n'importe quel objet qui sait `map()`, `draw(pixels)`,
`move(x, y)` en coordonnees globales, et `close()`.
"""

from __future__ import annotations

import time
from pathlib import Path

from . import png, screens, sound

TICK = 0.04


def run(overlay, frame: png.Frame, x: int, y: int, duration: float,
        opacity: float = 1.0, wav_path: Path | None = None, pan: float = 0.0,
        start: tuple[int, int] | None = None, slide_ms: int = 0,
        spins: list | None = None, spin_ms: int = 0) -> None:
    """Joue l'apparition puis rend la main, l'overlay ferme dans tous les cas.

    `spins` sont les quatre etapes d'un tour complet (`png.spin_frames`) :
    l'image les parcourt en `spin_ms` puis reste droite pour le reste du doot.
    Toutes ont la meme taille, celle de `frame`, sinon la surface changerait de
    dimensions en cours de route.

    Tant que rien n'est affiche, l'erreur remonte : l'appelant doit pouvoir se
    replier sur un autre backend. Une fois la surface a l'ecran on n'echoue
    plus, un doot ecourte valant mieux qu'un doot en double.
    """
    glisse = slide_ms > 0 and start is not None and tuple(start) != (x, y)
    depart_x, depart_y = start if glisse else (x, y)
    tourne = spin_ms > 0 and spins is not None and len(spins) == 4

    try:
        overlay.map()
    except Exception:
        overlay.close()
        raise

    playback = None
    try:
        playback = sound.play_async(wav_path, pan) if wav_path else None

        total = max(0.4, float(duration))
        fade_in = min(0.22, total / 4)
        fade_out = min(0.5, total / 3)
        ceiling = max(0.0, min(1.0, opacity))
        glissement = slide_ms / 1000.0
        rotation = spin_ms / 1000.0
        debut = time.monotonic()
        montre = None
        quart = 0

        while True:
            elapsed = time.monotonic() - debut
            if elapsed >= total:
                break

            # Pendant le glissement, pas de fondu d'apparition : le bord de
            # l'ecran revele deja le squelette.
            if glisse and elapsed <= glissement:
                avance = screens.ease_out(elapsed / glissement)
                overlay.move(depart_x + (x - depart_x) * avance,
                             depart_y + (y - depart_y) * avance)
                factor = 1.0
            elif not glisse and elapsed < fade_in:
                factor = elapsed / fade_in
            elif elapsed > total - fade_out:
                factor = max(0.0, (total - elapsed) / fade_out)
            else:
                factor = 1.0

            # Le tour se joue sur place : les quatre quarts defilent, puis
            # l'image reste droite (quart 0) jusqu'a la fin du doot.
            voulu = int(elapsed / rotation * 4) % 4 if tourne and elapsed < rotation else 0
            image = spins[voulu] if tourne else frame

            level = round(factor * ceiling * 255)
            # Pendant le glissement on redessine a chaque pas : l'opacite ne
            # bouge pas, donc rien ne le declencherait, et le contenu d'une
            # surface qu'on deplace n'est pas garanti d'etre conserve.
            if level != montre or voulu != quart or (glisse and elapsed <= glissement):
                overlay.draw(image.faded(level / 255))
                montre = level
                quart = voulu
            time.sleep(TICK)
    except Exception:
        pass
    finally:
        sound.release(playback)
        overlay.close()
