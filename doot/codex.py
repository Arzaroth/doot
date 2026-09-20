"""Le Codex des apparitions, construit depuis les rencontres deja vues."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Apparition:
    identifiant: str
    titre: str
    description: str
    indice: str


CATALOGUE = (
    Apparition(
        "parade", "La parade des sans-chair",
        "Six squelettes traversent les ecrans en vague serree.",
        "Quelque chose defile entre les tombes.",
    ),
    Apparition(
        "pluie", "Pluie d'os",
        "Sept trompettistes tombent du plafond numerique.",
        "Le plafond n'est peut-etre pas aussi solide qu'il en a l'air.",
    ),
    Apparition(
        "vortex", "Vortex infernal",
        "Cinq squelettes tournoient a travers les ecrans.",
        "Quand la crypte tourne, mieux vaut ne pas regarder le centre.",
    ),
    Apparition(
        "duel", "Le duel des cuivres",
        "Deux camps se repondent d'un bord a l'autre de l'ecran.",
        "Une trompette seule finit parfois par recevoir une reponse.",
    ),
    Apparition(
        "mimic", "Le Mimic",
        "Une notification presque credible cachait un squelette.",
        "Toutes les notifications ne viennent pas du systeme.",
    ),
    Apparition(
        "faux-bug", "Le faux bug",
        "Le squelette se coince, tremble, puis tombe hors de l'ecran.",
        "Un doot peut cesser de repondre sans vraiment planter.",
    ),
    Apparition(
        "finale", "La derniere nuit",
        "Douze trompettistes ont salue la fermeture de la crypte.",
        "Une crypte ne se referme pas sans un dernier mot.",
    ),
    Apparition(
        "contagion", "Le Doot contagieux",
        "Le doot d'une autre machine a traverse la crypte partagee.",
        "Certaines fanfares savent franchir les machines.",
    ),
)


def vus(etat: dict) -> set[str]:
    """Identifiants decouverts, en tolerant un state.json modifie a la main."""

    stats = etat.get("stats", {})
    if not isinstance(stats, dict):
        return set()
    valeur = stats.get("evenements_vus", [])
    if not isinstance(valeur, list):
        return set()
    return {item for item in valeur if isinstance(item, str)}


def progression(etat: dict) -> tuple[int, int]:
    connus = {item.identifiant for item in CATALOGUE}
    return len(vus(etat) & connus), len(CATALOGUE)
