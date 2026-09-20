"""Le registre de la crypte : l'etat mis en pages, sans rien y ajouter.

Le module est pur comme celui des succes. Il lit le dictionnaire de
``state.json`` et n'y ecrit rien : tout ce qu'il montre y est deja, mais n'etait
visible nulle part autrement qu'additionne dans un score. Ne collecter aucune
statistique neuve est ce qui permet a un registre de parler d'une saison
passee, et a une flotte deja fusionnee de se detailler sans se resynchroniser.

Les jours actifs sont un ensemble de dates, pas des compteurs : la grille dit
qu'un soir a eu son doot, jamais combien. Compter par jour demanderait une
troisieme espece de fusion et ferait grossir le fichier sans fin.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from . import codex, season, succes


SEMAINE = 7

# Ce que le registre montre, et sous quel nom. Les libelles vivent ici et non
# dans les affichages : le terminal, la fenetre et la carte de fin de saison
# doivent nommer la meme chose pareil.
TOTAUX = (
    ("doots", "Doots"),
    ("declenchements", "Declenchements"),
    ("melodies", "Melodies jouees"),
    ("melodies_perso", "dont melodies perso"),
    ("rickrolls", "Rickrolls"),
    ("evenements", "Rencontres rares"),
    ("canons", "Canons a quatre doots"),
    ("tours_imposes", "Tours imposes"),
)

RECORDS = (
    ("plus_grande_salve", "Plus grande salve"),
    ("voix_max", "Voix dans une melodie"),
)

COLLECTIONS = (
    ("formations", "Formations menees"),
    ("bords_imposes", "Bords imposes"),
    ("evenements_vus", "Rencontres reconnues"),
    ("melodies_fournies", "Melodies fournies jouees"),
    ("profils_actifs", "Profils actives"),
)

# Les colonnes de la table par machine. Les autres totaux ne sont pas repris
# poste par poste : une table de huit colonnes ne tient pas dans un terminal.
COLONNES = ("doots", "declenchements", "melodies", "evenements")


@dataclass(frozen=True)
class Poste:
    """La part d'une machine dans les totaux de la flotte."""

    machine: str
    doots: int
    declenchements: int
    melodies: int
    evenements: int


@dataclass(frozen=True)
class Resume:
    """Les chiffres de tete, toutes machines reunies."""

    doots: int
    declenchements: int
    melodies: int
    evenements: int
    jours: int
    plus_grande_salve: int
    voix_max: int
    succes: int
    succes_total: int
    points: int
    codex: int
    codex_total: int


@dataclass(frozen=True)
class Saison:
    """Une saison et les soirs qui y ont eu leur doot."""

    annee: int
    debut: date
    fin: date
    semaines: list
    actifs: frozenset

    @property
    def duree(self) -> int:
        return (self.fin - self.debut).days + 1


def resume(etat: dict) -> Resume:
    vus, codex_total = codex.progression(etat)
    return Resume(
        doots=succes.total(etat, "doots"),
        declenchements=succes.total(etat, "declenchements"),
        melodies=succes.total(etat, "melodies"),
        evenements=succes.total(etat, "evenements"),
        jours=len(jours_actifs(etat)),
        plus_grande_salve=succes.total(etat, "plus_grande_salve"),
        voix_max=succes.total(etat, "voix_max"),
        succes=len(succes.debloques(etat)),
        succes_total=len(succes.CATALOGUE),
        points=succes.score(etat),
        codex=vus,
        codex_total=codex_total,
    )


def postes(etat: dict) -> list:
    """Une ligne par machine ayant contribue, la plus bruyante devant.

    Une machine qui n'apparait que dans un total absent des colonnes garde sa
    ligne, a zero : elle a bien participe, et l'effacer laisserait croire que
    la flotte est plus petite qu'elle ne l'est.
    """
    detail = {cle: succes.parts(etat, cle) for cle in COLONNES}
    noms = set()
    for parts in detail.values():
        noms |= set(parts)
    lignes = [
        Poste(nom, *(succes.entier(detail[cle].get(nom)) for cle in COLONNES))
        for nom in noms
    ]
    return sorted(lignes, key=lambda poste: (-poste.doots, poste.machine))


def totaux(etat: dict) -> list:
    """Les compteurs non nuls, dans l'ordre du catalogue."""
    lignes = [(libelle, succes.total(etat, cle)) for cle, libelle in TOTAUX]
    return [(libelle, valeur) for libelle, valeur in lignes if valeur]


def records(etat: dict) -> list:
    return [(libelle, succes.total(etat, cle)) for cle, libelle in RECORDS]


def collections(etat: dict) -> list:
    return [(libelle, succes.collection(etat, cle)) for cle, libelle in COLLECTIONS]


def jours_actifs(etat: dict) -> set:
    """Les soirs ou un doot a eu lieu. Une date illisible est ecartee."""
    jours = set()
    for texte in succes.collection(etat, "jours_actifs"):
        try:
            jours.add(date.fromisoformat(texte))
        except ValueError:
            continue
    return jours


def bornes(annee: int) -> tuple:
    """Le premier et le dernier jour de la saison d'une annee."""
    debut = season.season_start(annee).date()
    fin = (season.season_end(annee) - timedelta(days=1)).date()
    return debut, fin


def semaines(debut: date, fin: date) -> list:
    """La saison en colonnes, du lundi au dimanche.

    Chaque colonne est une semaine et chaque ligne un jour de la semaine.
    ``None`` remplit les cases d'avant l'ouverture et d'apres la fermeture :
    la grille reste rectangulaire, et l'affichage n'a donc pas a compter les
    bords pour savoir ou commencer.
    """
    if fin < debut:
        return []
    jour = debut - timedelta(days=debut.weekday())
    dernier = fin + timedelta(days=SEMAINE - 1 - fin.weekday())
    colonnes = []
    while jour <= dernier:
        colonne = []
        for _ in range(SEMAINE):
            colonne.append(jour if debut <= jour <= fin else None)
            jour += timedelta(days=1)
        colonnes.append(colonne)
    return colonnes


def saison(etat: dict, annee: int) -> Saison:
    """La grille d'une saison et les soirs qu'elle a vus."""
    debut, fin = bornes(annee)
    actifs = frozenset(
        jour for jour in jours_actifs(etat) if debut <= jour <= fin
    )
    return Saison(annee, debut, fin, semaines(debut, fin), actifs)


def saisons(etat: dict) -> list:
    """Les annees dont un soir au moins a eu son doot, la plus recente devant."""
    return sorted({jour.year for jour in jours_actifs(etat)}, reverse=True)
