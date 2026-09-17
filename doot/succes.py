"""Succes locaux et statistiques de progression de doot.

Le module est volontairement pur : il transforme le dictionnaire de ``state.json``
sans connaitre les chemins ni la ligne de commande. Le client local reste ainsi la
source de verite, et une eventuelle synchronisation en ligne pourra reutiliser les
memes identifiants de succes sans changer le format du fichier.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable


Progression = Callable[[dict], int]
BADGES_DIR = Path(__file__).resolve().parent / "assets" / "success"


@dataclass(frozen=True)
class Succes:
    """Un succes, son score et la statistique qui le fait progresser."""

    identifiant: str
    titre: str
    description: str
    points: int
    objectif: int
    progression: Progression


def _compteur(stats: dict, cle: str) -> int:
    valeur = stats.get(cle, 0)
    if isinstance(valeur, bool) or not isinstance(valeur, int):
        return 0
    return max(0, valeur)


def _liste(stats: dict, cle: str) -> list[str]:
    valeur = stats.get(cle, [])
    if not isinstance(valeur, list):
        return []
    return sorted({item for item in valeur if isinstance(item, str)})


def _nombre_dans_liste(cle: str) -> Progression:
    return lambda stats: len(_liste(stats, cle))


def _valeur(cle: str) -> Progression:
    return lambda stats: _compteur(stats, cle)


CATALOGUE = (
    Succes("premier_doot", "Premier souffle", "Faire apparaitre son premier squelette.",
           5, 1, _valeur("doots")),
    Succes("dix_doots", "Dix sur dix", "Faire apparaitre 10 squelettes.",
           10, 10, _valeur("doots")),
    Succes("cent_doots", "Cent-os", "Faire apparaitre 100 squelettes.",
           25, 100, _valeur("doots")),
    Succes("mille_doots", "Doot mille", "Faire apparaitre 1 000 squelettes.",
           100, 1000, _valeur("doots")),
    Succes("trio_infernal", "Trio infernal", "Jouer une salve d'au moins 3 doots.",
           15, 3, _valeur("plus_grande_salve")),
    Succes("canon_a_os", "Canon a os", "Jouer une formation canon d'au moins 4 doots.",
           20, 1, _valeur("canons")),
    Succes("choregraphe", "Choregraphe des cryptes",
           "Jouer canon, wave, rain et vortex avec au moins 4 doots.",
           35, 4, _nombre_dans_liste("formations")),
    Succes("ca_tourne", "Ca tourne", "Imposer un tour complet avec --spin.",
           10, 1, _valeur("tours_imposes")),
    Succes("quatre_coins", "Aux quatre coins",
           "Imposer chacun des quatre bords avec --side.",
           25, 4, _nombre_dans_liste("bords_imposes")),
    Succes("maestro", "Maestro macabre", "Jouer une premiere melodie.",
           10, 1, _valeur("melodies")),
    Succes("jukebox_macabre", "Jukebox macabre",
           "Jouer 5 melodies fournies differentes.",
           50, 5, _nombre_dans_liste("melodies_fournies")),
    Succes("orchestre", "Orchestre d'outre-tombe",
           "Jouer une melodie avec au moins 2 voix.",
           20, 2, _valeur("voix_max")),
    Succes("rickroll", "Never gonna give you up", "Jouer rickroll en doots. Evidemment.",
           15, 1, _valeur("rickrolls")),
    Succes("melodie_perso", "Luthier d'outre-tombe",
           "Jouer une melodie RTTTL personnelle.",
           30, 1, _valeur("melodies_perso")),
    Succes("sept_jours", "Sept nuits de doot",
           "Jouer au moins une fois pendant 7 jours differents.",
           40, 7, _nombre_dans_liste("jours_actifs")),
    Succes("premier_evenement", "Quelque chose cloche",
           "Assister a un premier evenement rare.",
           15, 1, _valeur("evenements")),
    Succes("collection_evenements", "Cabinet de curiosites",
           "Assister aux trois evenements rares differents.",
           40, 3, _nombre_dans_liste("evenements_vus")),
    Succes("profil_actif", "Costume sur mesure",
           "Activer un profil persistant.",
           10, 1, _nombre_dans_liste("profils_actifs")),
)


def _stats(etat: dict) -> dict:
    stats = etat.get("stats")
    if not isinstance(stats, dict):
        stats = {}
        etat["stats"] = stats
    return stats


def _ajoute(stats: dict, cle: str, quantite: int = 1) -> None:
    stats[cle] = _compteur(stats, cle) + max(0, quantite)


def _ajoute_unique(stats: dict, cle: str, valeur: str) -> None:
    valeurs = _liste(stats, cle)
    if valeur and valeur not in valeurs:
        valeurs.append(valeur)
    stats[cle] = sorted(valeurs)


def _jour_actif(stats: dict, maintenant: datetime) -> None:
    _ajoute_unique(stats, "jours_actifs", maintenant.date().isoformat())


def enregistrer(etat: dict, evenement: str, maintenant: datetime | None = None,
                **details) -> list[Succes]:
    """Enregistre un evenement reel et renvoie les succes nouvellement debloques."""

    maintenant = maintenant or datetime.now()
    stats = _stats(etat)

    if evenement == "doots":
        quantite = details.get("quantite", 0)
        if isinstance(quantite, bool) or not isinstance(quantite, int):
            quantite = 0
        quantite = max(0, quantite)
        if quantite:
            _ajoute(stats, "doots", quantite)
            _ajoute(stats, "declenchements")
            stats["plus_grande_salve"] = max(
                _compteur(stats, "plus_grande_salve"), quantite
            )
            if details.get("formation") == "canon" and quantite >= 4:
                _ajoute(stats, "canons")
            formation = details.get("formation")
            if formation in ("canon", "wave", "rain", "vortex") and quantite >= 4:
                _ajoute_unique(stats, "formations", formation)
            if details.get("spin") is True:
                _ajoute(stats, "tours_imposes")
            bord = details.get("bord")
            if bord in ("left", "right", "top", "bottom"):
                _ajoute_unique(stats, "bords_imposes", bord)
            rencontre = details.get("rencontre")
            if isinstance(rencontre, str) and rencontre:
                _ajoute(stats, "evenements")
                _ajoute_unique(stats, "evenements_vus", rencontre)
            _jour_actif(stats, maintenant)

    elif evenement == "melodie":
        nom = details.get("nom")
        if not isinstance(nom, str):
            nom = ""
        voix = details.get("voix", 1)
        if isinstance(voix, bool) or not isinstance(voix, int):
            voix = 1
        _ajoute(stats, "melodies")
        _ajoute(stats, "declenchements")
        stats["voix_max"] = max(_compteur(stats, "voix_max"), max(1, voix))
        if details.get("fournie") is True:
            _ajoute_unique(stats, "melodies_fournies", nom)
        else:
            _ajoute(stats, "melodies_perso")
        if nom.casefold() == "rickroll":
            _ajoute(stats, "rickrolls")
        _jour_actif(stats, maintenant)

    elif evenement == "profil":
        nom = details.get("nom")
        if isinstance(nom, str):
            _ajoute_unique(stats, "profils_actifs", nom)

    acquis = etat.get("succes")
    if not isinstance(acquis, dict):
        acquis = {}
        etat["succes"] = acquis

    nouveaux = []
    for definition in CATALOGUE:
        if definition.identifiant in acquis:
            continue
        if definition.progression(stats) >= definition.objectif:
            acquis[definition.identifiant] = maintenant.isoformat(timespec="seconds")
            nouveaux.append(definition)
    return nouveaux


def debloques(etat: dict) -> dict:
    valeur = etat.get("succes", {})
    if not isinstance(valeur, dict):
        return {}
    connus = {item.identifiant for item in CATALOGUE}
    return {identifiant: date for identifiant, date in valeur.items()
            if identifiant in connus}


def score(etat: dict) -> int:
    acquis = debloques(etat)
    return sum(item.points for item in CATALOGUE if item.identifiant in acquis)


def badge(definition: Succes) -> Path | None:
    """Illustration fournie avec le succes, absente seulement si le paquet est incomplet."""

    chemin = BADGES_DIR / f"{definition.identifiant}.png"
    return chemin if chemin.is_file() else None


def progression(etat: dict, definition: Succes) -> tuple[int, int]:
    courant = min(definition.objectif, definition.progression(_stats(etat)))
    return courant, definition.objectif
