"""`doot --rickroll` : le refrain de Never Gonna Give You Up, tout en doots.

Un seul echantillon, doot/assets/doot-note.wav : le coup de trompette du
doot.mp3 fourni, isole (265 ms, un re5 a 594 Hz). Chaque note du refrain est
ce meme coup relu plus ou moins vite, comme une bande qu'on accelere : monter
d'un demi-ton, c'est lire 2^(1/12) fois plus vite. Tout le timbre vient de la,
rien n'est synthetise.

Pourquoi un WAV a cote du mp3 : la bibliotheque standard ne decode pas le mp3,
et ce module doit tenir ses echantillons en main pour les reaccorder. Le WAV
est mono, 16 bits, 48 kHz, comme le mp3 decode.

Le refrain est en la bemol majeur, comme l'original : le la bemol 4 est six
demi-tons sous le re5 du doot, donc la tonique se lit a 2^(-6/12) de la
vitesse normale. La melodie monte jusqu'a l'octave, soit 2^(6/12) au plus :
assez peu pour que le squelette reste un squelette, pas un ecureuil.
"""

from __future__ import annotations

import array
import math
import wave
from pathlib import Path

from .sound import ASSETS_DIR

NOTE_WAV = ASSETS_DIR / "doot-note.wav"
NOTE_FREQ = 594.0          # hauteur mesuree du coup de trompette (re5 + 20 cents)
TONIC_FREQ = 415.3         # la bemol 4 : la tonalite de la chanson
TEMPO = 113                # battements par minute, ceux du disque
LEAD = 0.4                 # silence de tete : le squelette apparait avant de jouer
TAIL = 0.6                 # queue apres la derniere note, le temps de s'effacer
NOTE_FILL = 0.92           # part du creneau que la note occupe avant de s'eteindre
FADE = 0.02                # fondu de fin quand la note est coupee, en secondes

# Le refrain, en demi-tons au-dessus de la tonique et en temps (4/4). Les six
# phrases commencent par la meme levee de quatre doubles-croches, puis chacune
# retombe sur le temps fort. None : un silence.
_LEVEE = ((0, 0.25), (2, 0.25), (5, 0.25), (2, 0.25))
_PHRASE_1 = _LEVEE + ((9, 0.75), (9, 0.75), (7, 1.0), (None, 0.5))
_PHRASE_2 = _LEVEE + ((7, 0.75), (7, 0.75), (5, 0.5), (4, 0.25), (2, 0.75))
_PHRASE_3 = _LEVEE + ((5, 0.75), (7, 0.75), (4, 0.5), (0, 0.5), (0, 0.5),
                      (7, 1.0), (5, 1.5), (None, 1.5))
_PHRASE_5 = _LEVEE + ((12, 0.75), (4, 0.75), (5, 0.5), (4, 0.25), (2, 0.75))
CHORUS = _PHRASE_1 + _PHRASE_2 + _PHRASE_3 + _PHRASE_1 + _PHRASE_5 + _PHRASE_3


def notes(tempo: float = TEMPO) -> list[tuple[float, float, int]]:
    """Le refrain en secondes : (debut, duree, demi-tons), silences exclus."""
    seconde_par_temps = 60.0 / tempo
    out = []
    position = LEAD
    for demi_tons, temps in CHORUS:
        duree = temps * seconde_par_temps
        if demi_tons is not None:
            out.append((position, duree, demi_tons))
        position += duree
    return out


def onsets(tempo: float = TEMPO) -> list[float]:
    """Les instants ou le squelette donne un coup de trompette."""
    return [debut for debut, _, _ in notes(tempo)]


def duration(tempo: float = TEMPO) -> float:
    """Duree totale de l'affichage : tete, refrain, queue."""
    total = sum(temps for _, temps in CHORUS) * 60.0 / tempo
    return LEAD + total + TAIL


def rate(demi_tons: int) -> float:
    """Vitesse de lecture du coup de trompette pour cette note du refrain."""
    tonique = 12 * math.log2(TONIC_FREQ / NOTE_FREQ)
    return 2 ** ((demi_tons + tonique) / 12)


def _read_note() -> tuple[array.array, int]:
    with wave.open(str(NOTE_WAV), "rb") as handle:
        if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
            raise ValueError("doot-note.wav doit etre mono 16 bits")
        rate_hz = handle.getframerate()
        raw = handle.readframes(handle.getnframes())
    samples = array.array("h")
    samples.frombytes(raw)
    return samples, rate_hz


def _resampled(source: array.array, vitesse: float, longueur: int) -> list[int]:
    """`longueur` echantillons de `source` lue a `vitesse`, interpolation lineaire.

    Une lecture acceleree saute des echantillons, une lecture ralentie en
    invente entre deux voisins : c'est la meme formule dans les deux sens, et
    elle suffit a un coup de trompette de 265 ms.
    """
    out = []
    dernier = len(source) - 1
    position = 0.0
    for _ in range(longueur):
        i = int(position)
        if i >= dernier:
            break
        frac = position - i
        out.append(int(source[i] + (source[i + 1] - source[i]) * frac))
        position += vitesse
    return out


def render(dest: Path, tempo: float = TEMPO) -> Path:
    """Ecrit le refrain en WAV mono 16 bits et rend son chemin.

    Chaque note occupe son creneau a `NOTE_FILL` pres, puis s'eteint en `FADE`
    secondes ; une note plus longue que le coup de trompette laisse le coup
    finir seul, sans l'etirer. Les creneaux ne se chevauchent pas, on n'a donc
    jamais deux coups a additionner.
    """
    source, rate_hz = _read_note()
    total = int(duration(tempo) * rate_hz)
    buffer = [0] * total
    fondu = int(FADE * rate_hz)

    for debut, duree, demi_tons in notes(tempo):
        vitesse = rate(demi_tons)
        naturelle = (len(source) - 1) / vitesse
        creneau = duree * NOTE_FILL * rate_hz
        coupe = creneau < naturelle
        longueur = int(min(creneau, naturelle))
        echantillons = _resampled(source, vitesse, longueur)
        if coupe:
            n = len(echantillons)
            for k in range(min(fondu, n)):
                echantillons[n - 1 - k] = echantillons[n - 1 - k] * k // fondu
        offset = int(debut * rate_hz)
        for k, valeur in enumerate(echantillons):
            if offset + k < total:
                buffer[offset + k] = valeur

    frames = array.array("h", (max(-32768, min(32767, v)) for v in buffer))
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dest), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate_hz)
        handle.writeframes(frames.tobytes())
    return dest
