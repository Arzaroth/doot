"""Fenetre saisonniere : du 1er septembre au 31 octobre inclus."""

from __future__ import annotations

from datetime import datetime, timedelta

SEASON_START_MONTH = 9   # septembre
SEASON_START_DAY = 1
SEASON_END_MONTH = 10    # octobre
SEASON_END_DAY = 31

SEASON_LABEL = "1er septembre -> 31 octobre (inclus)"


def in_season(now: datetime | None = None) -> bool:
    """Vrai entre le 1er septembre 00:00 et le 31 octobre 23:59:59 (heure locale)."""
    now = now or datetime.now()
    return (SEASON_START_MONTH, SEASON_START_DAY) <= (now.month, now.day) <= (
        SEASON_END_MONTH,
        SEASON_END_DAY,
    )


def season_start(year: int) -> datetime:
    return datetime(year, SEASON_START_MONTH, SEASON_START_DAY)


def season_end(year: int) -> datetime:
    """Instant exclusif de fin : le 1er novembre a 00:00."""
    return datetime(year, SEASON_END_MONTH, SEASON_END_DAY) + timedelta(days=1)


def next_season_start(now: datetime | None = None) -> datetime:
    """Prochaine ouverture de la saison (si on est dedans, celle de l'an prochain)."""
    now = now or datetime.now()
    start = season_start(now.year)
    if now < start:
        return start
    return season_start(now.year + 1)


def seconds_until_next_season(now: datetime | None = None) -> float:
    now = now or datetime.now()
    return max(0.0, (next_season_start(now) - now).total_seconds())


def describe(now: datetime | None = None) -> str:
    now = now or datetime.now()
    if in_season(now):
        remaining = season_end(now.year) - now
        days = remaining.days
        return f"saison ouverte, encore {days} jour(s) de doot"
    nxt = next_season_start(now)
    days = (nxt - now).days
    return f"hors saison, reouverture le {nxt:%d/%m/%Y} (dans {days} jour(s))"
