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
)


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
    return configured
