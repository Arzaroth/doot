"""Signaux ephemeres du Doot contagieux.

Le signal voyage dans l'objet chiffre deja publie par une machine. Il ne
contient qu'un identifiant, sa source et son heure de depart. Les signaux trop
anciens sont ignores et chaque poste garde une petite liste de ceux qu'il a
deja vus, afin qu'une synchronisation repetee ne rejoue jamais le meme doot.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone


TTL_SECONDS = 5 * 60
MAX_SEEN = 128
MAX_PENDING = 8


def _utc(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def creer(source: str, now: datetime | None = None, token: str | None = None) -> dict:
    maintenant = _utc(now)
    token = token or uuid.uuid4().hex[:12]
    return {
        "id": f"{source}:{token}",
        "source": source,
        "emis": maintenant.isoformat(timespec="seconds"),
    }


def valide(signal, now: datetime | None = None) -> bool:
    if not isinstance(signal, dict):
        return False
    identifiant = signal.get("id")
    source = signal.get("source")
    emis = signal.get("emis")
    if not all(isinstance(item, str) and item for item in (identifiant, source, emis)):
        return False
    if len(identifiant) > 96 or len(source) > 64:
        return False
    try:
        instant = datetime.fromisoformat(emis.replace("Z", "+00:00"))
        age = (_utc(now) - _utc(instant)).total_seconds()
    except (TypeError, ValueError, OverflowError):
        return False
    return -30 <= age <= TTL_SECONDS


def recevoir(etat: dict, signal, now: datetime | None = None) -> bool:
    """Met un signal neuf en attente. Faux signifie invalide, local ou deja vu."""

    if not valide(signal, now):
        return False
    if signal["source"] == etat.get("machine"):
        return False

    vues = etat.get("contagions_vues", [])
    vues = [item for item in vues if isinstance(item, str)] if isinstance(vues, list) else []
    if signal["id"] in vues:
        return False

    attentes = etat.get("contagions_en_attente", [])
    attentes = [item for item in attentes if isinstance(item, dict)] \
        if isinstance(attentes, list) else []
    attentes.append(dict(signal))
    etat["contagions_en_attente"] = attentes[-MAX_PENDING:]
    etat["contagions_vues"] = (vues + [signal["id"]])[-MAX_SEEN:]
    return True


def vider(etat: dict, now: datetime | None = None) -> list[dict]:
    attentes = etat.pop("contagions_en_attente", [])
    if not isinstance(attentes, list):
        return []
    return [item for item in attentes if valide(item, now)]
