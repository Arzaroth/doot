"""Ce qu'un poste publie de ses succes, et ce qu'il prend aux autres.

Aucun serveur : chaque machine ecrit un objet que seule elle ecrit, dans un
stockage que la personne a deja, dossier synchronise ou seau compatible S3. Les
objets a un seul ecrivain retirent toute resolution de conflit du dessin, et
chaque partie difficile d'un service de synchronisation disparait avec lui,
hebergement, authentification, disponibilite.

L'objet publie porte aussi ce que le poste a appris des autres. Deux machines
jamais allumees ensemble se rejoignent par l'intermediaire d'une troisieme, ce
que les parts par machine rendent sans danger : fusionner prend le maximum part
par part, jamais une somme.

L'identite de la replique et les reglages vivent dans `replica.json`, jamais
dans `state.json` : ce dernier se sauvegarde et se copie, et ni une identite
partagee ni un secret S3 recopie n'y ont leur place.
"""

from __future__ import annotations

import json
import platform
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import coffre, succes, transport

FICHIER = "replica.json"

_connues: dict[str, str] = {}


def _empreinte(dossier: Path) -> str:
    """De quoi reconnaitre que l'installation n'est plus la meme."""
    return f"{platform.node()}|{dossier}"


def _fiche(dossier: Path) -> dict:
    try:
        note = json.loads((dossier / FICHIER).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return note if isinstance(note, dict) else {}


def _ecrire_fiche(dossier: Path, note: dict) -> None:
    try:
        dossier.mkdir(parents=True, exist_ok=True)
        transport.ecrire_atomiquement(
            dossier / FICHIER,
            (json.dumps(note, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
        )
    except OSError:
        pass


def identite(dossier: Path) -> str:
    """L'identifiant de cette replique, garde hors de l'etat sauvegardable.

    Une empreinte qui ne correspond plus fait battre une identite neuve : les
    parts deja ecrites restent a la machine qui les a gagnees, les suivantes
    vont a la nouvelle. Comme les parts s'additionnent, se re-cler pour rien ne
    coute qu'une part de plus ; ne pas se re-cler quand il le fallait coute des
    doots.
    """
    empreinte = _empreinte(dossier)
    connue = _connues.get(empreinte)
    if connue:
        return connue

    note = _fiche(dossier)
    if (isinstance(note.get("id"), str) and note["id"]
            and note.get("empreinte") == empreinte):
        _connues[empreinte] = note["id"]
        return note["id"]

    neuve = uuid.uuid4().hex[:12]
    note.update({"id": neuve, "empreinte": empreinte})
    _ecrire_fiche(dossier, note)
    _connues[empreinte] = neuve
    return neuve


def reglage(dossier: Path) -> dict:
    """Ou et avec quelle cle ce poste publie."""
    valeur = _fiche(dossier).get("sync")
    return valeur if isinstance(valeur, dict) else {}


def poser_reglage(dossier: Path, valeur: dict | None) -> None:
    note = _fiche(dossier)
    note.setdefault("id", identite(dossier))
    note.setdefault("empreinte", _empreinte(dossier))
    if valeur is None:
        note.pop("sync", None)
    else:
        note["sync"] = valeur
    _ecrire_fiche(dossier, note)


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


@dataclass(frozen=True)
class Lecture:
    """Le sort d'un objet rencontre : fusionne, ou ecarte et pourquoi."""

    nom: str
    machine: str = ""
    refus: str = ""
    debloques: tuple = ()

    @property
    def fusionnee(self) -> bool:
        return not self.refus


def lire_objets(etat: dict, depot, cle: bytes, objets) -> list[Lecture]:
    """Fait entrer les parts lisibles, et dit ce qu'il est advenu de chacune.

    Rendre le sort de chaque objet plutot que l'imprimer laisse l'appelant
    choisir : la commande en fait des lignes, le cycle du daemon les compte.
    """
    ici = coffre.nom_objet(cle, succes.machine(etat))
    lectures = []
    for objet in objets:
        if objet.nom == ici:
            continue
        try:
            scelle = depot.reprendre(objet)
            if scelle is None:
                continue
            distant = json.loads(coffre.ouvrir(cle, scelle))
        except coffre.CoffreError as exc:
            lectures.append(Lecture(objet.nom, refus=str(exc)))
            continue
        except Exception as exc:
            lectures.append(Lecture(objet.nom, refus=f"illisible, {exc}"))
            continue
        if not isinstance(distant, dict):
            lectures.append(Lecture(objet.nom, refus="ce n'est pas un etat doot"))
            continue
        try:
            nouveaux = succes.fusionner(etat, distant)
        except ValueError as exc:
            lectures.append(Lecture(objet.nom, refus=str(exc)))
            continue
        lectures.append(Lecture(objet.nom, machine=str(distant.get("machine")),
                                debloques=tuple(nouveaux)))
    return lectures


def fichiers_de(sources) -> list[Path]:
    """Les fichiers a lire pour un transfert a la main ; un dossier apporte ses .json."""
    fichiers = []
    for source in sources:
        chemin = Path(source).expanduser()
        if chemin.is_dir():
            fichiers.extend(sorted(chemin.glob("*.json")))
        else:
            fichiers.append(chemin)
    return fichiers


def lire_parts(etat: dict, fichiers) -> list[Lecture]:
    """La meme chose que `lire_objets`, sur des fichiers clairs.

    C'est le chemin a la main, `--export` et `--merge` : une cle USB, un
    courriel, un dossier qu'on trimballe. Rien n'y est chiffre puisque la
    personne manipule le fichier elle-meme, la ou le partage automatique
    traverse un stockage qu'elle ne controle pas forcement.
    """
    ici = succes.machine(etat)
    lectures = []
    for chemin in fichiers:
        try:
            distant = json.loads(chemin.read_text(encoding="utf-8"))
        except Exception as exc:
            lectures.append(Lecture(chemin.name, refus=f"illisible, {exc}"))
            continue
        if not isinstance(distant, dict):
            lectures.append(Lecture(chemin.name, refus="ce n'est pas un etat doot"))
            continue
        if distant.get("machine") == ici:
            lectures.append(Lecture(chemin.name, refus="c'est cette machine, ignore"))
            continue
        try:
            nouveaux = succes.fusionner(etat, distant)
        except ValueError as exc:
            lectures.append(Lecture(chemin.name, refus=str(exc)))
            continue
        lectures.append(Lecture(chemin.name, machine=str(distant.get("machine")),
                                debloques=tuple(nouveaux)))
    return lectures


def ecrire_part(etat: dict, cible: Path) -> Path:
    """Depose la part en clair ; un dossier recoit doot-<machine>.json."""
    part = part_exportable(etat)
    chemin = cible / f"doot-{part['machine']}.json" if cible.is_dir() else cible
    transport.ecrire_atomiquement(
        chemin, (json.dumps(part, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return chemin


def publier(etat: dict, depot, cle: bytes) -> str:
    """Depose la part de ce poste, chiffree, sous un nom opaque."""
    nom = coffre.nom_objet(cle, succes.machine(etat))
    clair = json.dumps(part_exportable(etat), ensure_ascii=False).encode("utf-8")
    depot.deposer(nom, coffre.fermer(cle, clair))
    return nom


def oublier_sous(etat: dict, fiche: dict, cle_texte: str) -> None:
    """Retire l'objet publie sous une cle qu'on vient de quitter.

    Sans ca, changer de cle laisse dans le depot un objet que plus personne ne
    sait ouvrir, et que rien ne viendra jamais remplacer.
    """
    try:
        cle = coffre.depuis_texte(cle_texte)
        transport.ouvrir(fiche).effacer(coffre.nom_objet(cle, succes.machine(etat)))
    except Exception:
        pass


def cycle(etat: dict, dossier: Path) -> list:
    """Prendre ce que les autres ont publie, fusionner, republier.

    Ne leve jamais : un depot injoignable, un disque plein ou un objet a moitie
    ecrit laissent la progression locale intacte et l'ennui dans `sync_note`.
    Un doot ne doit pas dependre de la synchronisation.
    """
    fiche = reglage(dossier)
    if not fiche or not fiche.get("cle"):
        return []

    note = {"quand": datetime.now().isoformat(timespec="seconds")}
    nouveaux = []
    try:
        cle = coffre.depuis_texte(fiche["cle"])
        depot = transport.ouvrir(fiche)
        note["depot"] = depot.decrire()
        lectures = lire_objets(etat, depot, cle, depot.lister())
        publier(etat, depot, cle)
        note["pairs"] = sum(1 for lecture in lectures if lecture.fusionnee)
        note["ecartes"] = [lecture.refus for lecture in lectures if lecture.refus]
        nouveaux = [item for lecture in lectures for item in lecture.debloques]
    except Exception as exc:
        note["erreur"] = str(exc)
    etat["sync_note"] = note
    return nouveaux
