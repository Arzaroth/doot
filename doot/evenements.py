"""Rencontres rares precomposees a partir des formations de doot."""

from __future__ import annotations

import copy
from dataclasses import dataclass


@dataclass(frozen=True)
class Evenement:
    identifiant: str
    titre: str
    description: str
    formation: str
    quantite: int
    delai: float
    duree: float
    mise_en_scene: str = "salve"
    # Une rencontre qui appartient a une date ne se tire pas au sort le reste
    # du temps. Le champ vit ici, avec la rencontre, et non dans le tirage.
    tirable: bool = True


CATALOGUE = (
    Evenement(
        "parade",
        "La parade des sans-chair",
        "Six squelettes traversent les ecrans en vague serree.",
        "wave",
        6,
        0.10,
        1.15,
    ),
    Evenement(
        "pluie",
        "Pluie d'os",
        "Sept trompettistes tombent du plafond numerique.",
        "rain",
        7,
        0.08,
        1.0,
    ),
    Evenement(
        "vortex",
        "Vortex infernal",
        "Cinq squelettes tournoient a travers les ecrans.",
        "vortex",
        5,
        0.10,
        1.2,
    ),
    Evenement(
        "duel",
        "Le duel des cuivres",
        "Deux camps se repondent d'un bord a l'autre de l'ecran.",
        "duel",
        6,
        0.16,
        0.85,
    ),
    Evenement(
        "finale",
        "La derniere nuit",
        "La crypte se vide d'un coup : douze trompettistes saluent la fermeture.",
        "vortex",
        12,
        0.07,
        1.5,
        tirable=False,
    ),
    Evenement(
        "mimic",
        "Le Mimic",
        "Une notification presque credible cache un squelette.",
        "random",
        1,
        0.0,
        2.8,
        "mimic",
    ),
    Evenement(
        "faux-bug",
        "Le faux bug",
        "Le squelette se coince au bord, tremble, puis tombe.",
        "random",
        1,
        0.0,
        3.8,
        "faux-bug",
    ),
)


def tirables() -> tuple:
    """Les rencontres que le hasard peut amener de lui-meme.

    La finale n'en est pas : elle appartient au soir du 31 octobre, et un
    tirage qui la sortirait un 12 septembre lui oterait tout son sens.
    """
    return tuple(item for item in CATALOGUE if item.tirable)


def find(name: str) -> Evenement | None:
    wanted = name.casefold()
    return next((event for event in CATALOGUE if event.identifiant == wanted), None)


def configure(args, event: Evenement):
    """Copie les options puis applique la choregraphie, sans muter le daemon."""

    configured = copy.copy(args)
    configured.burst_min = event.quantite
    configured.burst_max = event.quantite
    configured.burst_delay = event.delai
    configured.duration = event.duree
    configured.formation = event.formation
    configured.mise_en_scene = event.mise_en_scene
    if event.mise_en_scene == "faux-bug":
        configured.side = "bottom"
        configured.no_slide = False
        configured.spin = False
        configured.slide_ms = 650
    return configured
