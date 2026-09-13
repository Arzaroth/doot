"""`doot --play` : une melodie jouee tout en doots.

Un seul echantillon, doot/assets/doot-note.wav : le coup de trompette du
doot.mp3 fourni, isole (265 ms, un re5 a 594 Hz). Chaque note est ce meme
coup relu plus ou moins vite, comme une bande qu'on accelere : monter d'un
demi-ton, c'est lire 2^(1/12) fois plus vite. Tout le timbre vient de la,
rien n'est synthetise.

Pourquoi un WAV a cote du mp3 : la bibliotheque standard ne decode pas le mp3,
et ce module doit tenir ses echantillons en main pour les reaccorder. Le WAV
est mono, 16 bits, 48 kHz, comme le mp3 decode.

Les melodies sont des fichiers RTTTL, le format des sonneries Nokia : une
ligne de texte, un nom, trois reglages, puis les notes. Il n'y a rien a
inventer, des milliers de morceaux existent deja sous cette forme et se
collent tels quels dans <data_dir>/melodies/.

    Nom:d=8,o=5,b=130:f,f,e,e,a4,c,4a4,p,...

  d : duree par defaut (1 ronde, 2 blanche, 4 noire, 8 croche, 16, 32)
  o : octave par defaut (la4 = 440 Hz ; la norme dit 4 a 7, on prend 1 a 8)
  b : tempo, en noires par minute
  puis chaque note : [duree]nom[#][octave][.], `p` pour un silence, le point
  allonge de moitie. `4e6.` est une noire pointee de mi6, `8p` une croche de
  silence.

Une melodie ecrite trop haut ou trop bas pour le doot ferait un ecureuil ou
un tuba : elle est ramenee, par octaves entieres, au plus pres du re5 du coup
de trompette. `--transpose` ajoute ensuite des demi-tons a la demande.
"""

from __future__ import annotations

import array
import math
import re
import wave
from dataclasses import dataclass
from pathlib import Path

from .sound import ASSETS_DIR

NOTE_WAV = ASSETS_DIR / "doot-note.wav"
NOTE_FREQ = 594.0          # hauteur mesuree du coup de trompette (re5 + 20 cents)
NOTE_MIDI = 69 + 12 * math.log2(NOTE_FREQ / 440.0)   # ~74.2, sur l'echelle MIDI
MELODIES_DIR = ASSETS_DIR / "melodies"
EXTENSION = ".rtttl"
LEAD = 0.4                 # silence de tete : le squelette apparait avant de jouer
TAIL = 0.6                 # queue apres la derniere note, le temps de s'effacer
NOTE_FILL = 0.92           # part du creneau que la note occupe avant de s'eteindre
FADE = 0.02                # fondu de fin quand la note est coupee, en secondes

DUREES = (1, 2, 4, 8, 16, 32)
DEMI_TONS = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11, "h": 11}
# Le point se rencontre aux trois places : 8.f, 8f., 8f5. -- on prend tout.
# Octaves 1 a 8 : la norme dit 4 a 7, mais les lecteurs acceptent plus large
# et les basses d'un riff descendent volontiers sous le do4.
_NOTE = re.compile(r"^(\d+)?(\.?)([a-hp])(#?)(\.?)([1-8])?(\.?)$")


class MelodieError(ValueError):
    """Fichier RTTTL illisible : le message dit ou."""


@dataclass
class Melodie:
    """Une melodie lue : `notes` sont des (hauteur MIDI ou None, duree en temps)."""

    name: str
    tempo: float
    notes: list

    def pitches(self) -> list:
        return [midi for midi, _ in self.notes if midi is not None]


# ------------------------------------------------------------------ RTTTL ----

def parse(text: str, name: str = "") -> Melodie:
    """Lit une sonnerie RTTTL. Leve MelodieError si elle est mal ecrite."""
    parts = text.strip().split(":")
    if len(parts) != 3:
        raise MelodieError("il faut trois sections separees par ':' : nom, reglages, notes")
    titre, reglages, notes = (p.strip() for p in parts)

    defaults = {"d": 4, "o": 5, "b": 63}
    for item in filter(None, (r.strip() for r in reglages.split(","))):
        cle, _, valeur = item.partition("=")
        cle, valeur = cle.strip().lower(), valeur.strip()
        if cle not in defaults or not valeur.isdigit():
            raise MelodieError(f"reglage incompris : '{item}' (attendu d=, o= ou b=)")
        defaults[cle] = int(valeur)
    if defaults["d"] not in DUREES:
        raise MelodieError(f"duree par defaut d={defaults['d']} : attendu 1, 2, 4, 8, 16 ou 32")
    if not 1 <= defaults["o"] <= 8:
        raise MelodieError(f"octave par defaut o={defaults['o']} : attendu de 1 a 8")
    if defaults["b"] <= 0:
        raise MelodieError("tempo b= : il faut au moins 1")

    lues = []
    for jeton in filter(None, (n.strip().lower() for n in notes.split(","))):
        trouve = _NOTE.match(jeton)
        if not trouve:
            raise MelodieError(f"note incomprise : '{jeton}'")
        duree, point_1, nom, diese, point_2, octave, point_3 = trouve.groups()
        duree = int(duree) if duree else defaults["d"]
        if duree not in DUREES:
            raise MelodieError(f"duree {duree} dans '{jeton}' : attendu 1, 2, 4, 8, 16 ou 32")
        temps = 4.0 / duree
        if point_1 or point_2 or point_3:
            temps *= 1.5
        if nom == "p":
            lues.append((None, temps))
            continue
        octave = int(octave) if octave else defaults["o"]
        midi = 12 * (octave + 1) + DEMI_TONS[nom] + (1 if diese else 0)
        lues.append((midi, temps))
    if not any(midi is not None for midi, _ in lues):
        raise MelodieError("aucune note dans la melodie")
    return Melodie(titre or name, float(defaults["b"]), lues)


def load(path: Path) -> Melodie:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MelodieError(f"{path} : {exc.strerror or exc}") from exc
    try:
        return parse(text, name=path.stem)
    except MelodieError as exc:
        raise MelodieError(f"{path.name} : {exc}") from exc


# --------------------------------------------------------------- catalogue ---

def bundled() -> list:
    """Les melodies livrees avec doot, triees par nom."""
    if not MELODIES_DIR.is_dir():
        return []
    return sorted(p for p in MELODIES_DIR.iterdir()
                  if p.is_file() and p.suffix.lower() == EXTENSION)


def custom(melodies_dir: Path) -> list:
    """Les melodies deposees par l'utilisateur, triees par nom."""
    if not melodies_dir.is_dir():
        return []
    return sorted(p for p in melodies_dir.iterdir()
                  if p.is_file() and p.suffix.lower() == EXTENSION)


def find(wanted: str, melodies_dir: Path) -> Path | None:
    """Le fichier derriere un nom (`rickroll`) ou un chemin (`x/y.rtttl`).

    Un nom se cherche d'abord parmi les melodies deposees par l'utilisateur,
    puis parmi celles fournies : deposer `rickroll.rtttl` chez soi remplace
    celui de doot, comme un son ou une image.
    """
    chemin = Path(wanted).expanduser()
    if chemin.suffix.lower() == EXTENSION and chemin.is_file():
        return chemin
    nom = chemin.stem.lower() if chemin.suffix.lower() == EXTENSION else wanted.lower()
    for candidat in custom(melodies_dir) + bundled():
        if candidat.stem.lower() == nom:
            return candidat
    return None


# --------------------------------------------------------------- accordage ---

def transposition(melodie: Melodie) -> int:
    """Les demi-tons, par octaves entieres, qui ramenent la melodie sur le doot.

    Le milieu de l'ambitus est pose au plus pres du re5 du coup de trompette :
    une sonnerie ecrite a l'octave 6 descend d'une octave, une autre a
    l'octave 4 remonte. Le milieu plutot que la mediane : un riff de basse
    repete cent fois sous un theme aigu tirerait la mediane vers le bas et
    enverrait le theme dans les aigus d'ecureuil, alors que les deux
    extremes comptent autant a l'oreille. Par octaves seulement, pour ne pas
    changer la tonalite du morceau.
    """
    hauteurs = melodie.pitches()
    milieu = (min(hauteurs) + max(hauteurs)) / 2
    return 12 * round((NOTE_MIDI - milieu) / 12)


def rate(demi_tons: float) -> float:
    """Vitesse de lecture du coup de trompette, `demi_tons` au-dessus de lui."""
    return 2 ** (demi_tons / 12)


def notes(melodie: Melodie, transpose: int | None = None) -> list:
    """La melodie en secondes : (debut, duree, demi-tons au-dessus du doot).

    `transpose` : des demi-tons en plus du recentrage automatique.
    """
    decalage = transposition(melodie) + (transpose or 0)
    seconde_par_temps = 60.0 / melodie.tempo
    out = []
    position = LEAD
    for midi, temps in melodie.notes:
        duree = temps * seconde_par_temps
        if midi is not None:
            out.append((position, duree, midi + decalage - NOTE_MIDI))
        position += duree
    return out


def onsets(melodie: Melodie, transpose: int | None = None) -> list:
    """Les instants ou le squelette donne un coup de trompette."""
    return [debut for debut, _, _ in notes(melodie, transpose)]


def duration(melodie: Melodie) -> float:
    """Duree totale de l'affichage : tete, melodie, queue."""
    total = sum(temps for _, temps in melodie.notes) * 60.0 / melodie.tempo
    return LEAD + total + TAIL


# ------------------------------------------------------------------- rendu ---

def _read_note() -> tuple:
    with wave.open(str(NOTE_WAV), "rb") as handle:
        if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
            raise ValueError("doot-note.wav doit etre mono 16 bits")
        rate_hz = handle.getframerate()
        raw = handle.readframes(handle.getnframes())
    samples = array.array("h")
    samples.frombytes(raw)
    return samples, rate_hz


def _resampled(source: array.array, vitesse: float, longueur: int) -> list:
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


# Points de boucle du coup de trompette, en secondes : le plateau stable apres
# l'attaque (le doot est a 96-72 % de son pic entre 30 et 95 ms), boucle de
# 24 periodes du re5 fondue sur 2 periodes.
LOOP_START = 0.040
LOOP_PERIODS = 24
FADE_PERIODS = 2


def sustained(source: array.array, rate_hz: int, longueur: int) -> list:
    """Le coup tenu jusqu'a `longueur` echantillons : attaque, boucle, finale.

    Un doot dure 265 ms ; une blanche a 76 BPM en dure 1 600. Sans ca, une
    note tenue est un toot suivi d'un silence, et un riff de sax legato
    devient du morse. On fait comme un sampleur : l'attaque telle quelle,
    puis la partie stable du son bouclee autant de fois qu'il faut, en
    fondu enchaine d'une periode a l'autre, puis la finale (le 't' du
    doot) telle quelle. Si le coup suffit, il est rendu tel quel.
    """
    if longueur <= len(source):
        return list(source)
    periode = rate_hz / NOTE_FREQ
    debut = int(LOOP_START * rate_hz)
    boucle = int(round(LOOP_PERIODS * periode))
    fondu = int(round(FADE_PERIODS * periode))
    fin = debut + boucle
    attaque = list(source[:fin])
    finale = list(source[fin:])
    tours = -(-(longueur - len(source)) // (boucle - fondu))
    segment = list(source[debut:fin])
    out = attaque
    for _ in range(tours):
        # Fondu enchaine : la queue de ce qu'on a deja avec la tete du segment.
        for k in range(fondu):
            f = k / fondu
            out[-fondu + k] = int(out[-fondu + k] * (1 - f) + segment[k] * f)
        out += segment[fondu:]
    for k in range(fondu):
        f = k / fondu
        out[-fondu + k] = int(out[-fondu + k] * (1 - f) + finale[k] * f)
    out += finale[fondu:]
    return out


def render(dest: Path, melodie: Melodie, transpose: int | None = None) -> Path:
    """Ecrit la melodie en WAV mono 16 bits et rend son chemin.

    Chaque note occupe son creneau a `NOTE_FILL` pres, puis s'eteint en `FADE`
    secondes ; une note plus longue que le coup de trompette le tient en
    bouclant sa partie stable (`sustained`). Les creneaux ne se chevauchent
    pas, on n'a donc jamais deux coups a additionner.
    """
    source, rate_hz = _read_note()
    total = int(duration(melodie) * rate_hz)
    buffer = [0] * total
    fondu = int(FADE * rate_hz)

    for debut, duree, demi_tons in notes(melodie, transpose):
        vitesse = rate(demi_tons)
        creneau = duree * NOTE_FILL * rate_hz
        # Le coup, tenu s'il le faut, dans le domaine de la source : a la
        # vitesse `vitesse`, il en faut `creneau * vitesse` echantillons.
        tenu = sustained(source, rate_hz, int(creneau * vitesse) + 1)
        naturelle = (len(tenu) - 1) / vitesse
        coupe = creneau < naturelle
        longueur = int(min(creneau, naturelle))
        echantillons = _resampled(array.array("h", tenu), vitesse, longueur)
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
