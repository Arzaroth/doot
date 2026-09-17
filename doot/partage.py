"""Ce qu'un poste publie de ses succes, et ce qu'il prend aux autres.

Aucun serveur : chaque machine ecrit un fichier que seule elle ecrit, dans un
dossier que la personne synchronise deja. Deux postes n'ecrivent donc jamais au
meme endroit, et il n'y a aucun conflit a resoudre nulle part.

Le fichier publie porte aussi ce que le poste a appris des autres. Deux
machines jamais allumees ensemble se rejoignent par l'intermediaire d'une
troisieme, ce que les parts par machine rendent sans danger : fusionner prend
le maximum part par part, jamais une somme.
"""

from __future__ import annotations

import json
import platform
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import succes

FICHIER_IDENTITE = "replica.json"
MOTIF = "doot-*.json"

_connues: dict[str, str] = {}


def _empreinte(dossier: Path) -> str:
    """De quoi reconnaitre que l'installation n'est plus la meme."""
    return f"{platform.node()}|{dossier}"


def identite(dossier: Path) -> str:
    """L'identifiant de cette replique, garde hors de l'etat sauvegardable.

    Il ne vit pas dans `state.json` : ce fichier se copie et se restaure, et
    deux installations qui partageraient une part verraient leurs progressions
    fusionnees par maximum au lieu d'etre additionnees.

    L'empreinte de l'installation est relue a chaque fois. Quand elle ne
    correspond plus, on bat une identite neuve : les parts deja ecrites restent
    a la machine qui les a gagnees, les suivantes vont a la nouvelle. Se
    re-cler pour rien ne coute qu'une part de plus, et les parts s'additionnent
    ; ne pas se re-cler quand il le fallait coute des doots.
    """
    empreinte = _empreinte(dossier)
    connue = _connues.get(empreinte)
    if connue:
        return connue

    chemin = dossier / FICHIER_IDENTITE
    try:
        note = json.loads(chemin.read_text(encoding="utf-8"))
    except Exception:
        note = {}

    if (isinstance(note, dict) and isinstance(note.get("id"), str) and note["id"]
            and note.get("empreinte") == empreinte):
        _connues[empreinte] = note["id"]
        return note["id"]

    neuve = uuid.uuid4().hex[:12]
    try:
        dossier.mkdir(parents=True, exist_ok=True)
        chemin.write_text(
            json.dumps({"id": neuve, "empreinte": empreinte}, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass
    _connues[empreinte] = neuve
    return neuve


def part_exportable(etat: dict) -> dict:
    """Ce qui voyage d'une machine a l'autre.

    Les compteurs de pitie restent : ils decrivent le rythme de ce poste, pas
    ce qui y a ete accompli.
    """
    return {
        "machine": succes.machine(etat),
        "stats": etat.get("stats", {}),
        "succes": etat.get("succes", {}),
    }


def ecrire_part(etat: dict, cible: Path) -> Path:
    """Depose la part de ce poste ; un dossier recoit doot-<machine>.json."""
    part = part_exportable(etat)
    chemin = cible / f"doot-{part['machine']}.json" if cible.is_dir() else cible
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(part, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    return chemin


@dataclass(frozen=True)
class Lecture:
    """Le sort d'un fichier rencontre : fusionne, ou ecarte et pourquoi."""

    chemin: Path
    machine: str = ""
    refus: str = ""
    debloques: tuple = ()

    @property
    def fusionnee(self) -> bool:
        return not self.refus


def lire_parts(etat: dict, fichiers) -> list[Lecture]:
    """Fait entrer les parts lisibles, et dit ce qu'il est advenu de chacune.

    Rendre le sort de chaque fichier plutot que l'imprimer laisse l'appelant
    choisir : la commande en fait des lignes, le cycle du daemon les compte.
    """
    ici = succes.machine(etat)
    lectures = []
    for chemin in fichiers:
        try:
            distant = json.loads(chemin.read_text(encoding="utf-8"))
        except Exception as exc:
            lectures.append(Lecture(chemin, refus=f"illisible, {exc}"))
            continue
        if not isinstance(distant, dict):
            lectures.append(Lecture(chemin, refus="ce n'est pas un etat doot"))
            continue
        if distant.get("machine") == ici:
            lectures.append(Lecture(chemin, refus="c'est cette machine, ignore"))
            continue
        try:
            nouveaux = succes.fusionner(etat, distant)
        except ValueError as exc:
            lectures.append(Lecture(chemin, refus=str(exc)))
            continue
        lectures.append(Lecture(chemin, machine=str(distant.get("machine")),
                                debloques=tuple(nouveaux)))
    return lectures


def fichiers_de(sources) -> list[Path]:
    """Les fichiers a lire ; un dossier apporte tous ses .json."""
    fichiers = []
    for source in sources:
        chemin = Path(source).expanduser()
        if chemin.is_dir():
            fichiers.extend(sorted(chemin.glob("*.json")))
        else:
            fichiers.append(chemin)
    return fichiers


def dossier_partage(etat: dict) -> Path | None:
    """Le dossier partage, s'il y en a un."""
    valeur = etat.get("sync")
    if isinstance(valeur, str) and valeur:
        return Path(valeur).expanduser()
    return None


def cycle(etat: dict) -> list:
    """Prendre ce que les autres ont publie, fusionner, republier.

    Ne leve jamais : un dossier absent, un disque plein ou un fichier a moitie
    ecrit laissent la progression locale intacte et l'ennui dans `sync_note`.
    Un doot ne doit pas dependre de la synchronisation.
    """
    dossier = dossier_partage(etat)
    if dossier is None:
        return []

    note = {"quand": datetime.now().isoformat(timespec="seconds")}
    nouveaux = []
    try:
        dossier.mkdir(parents=True, exist_ok=True)
        lectures = lire_parts(etat, sorted(dossier.glob(MOTIF)))
        ecrire_part(etat, dossier)
        note["pairs"] = sum(1 for lecture in lectures if lecture.fusionnee)
        nouveaux = [item for lecture in lectures for item in lecture.debloques]
    except Exception as exc:
        note["erreur"] = str(exc)
    etat["sync_note"] = note
    return nouveaux
