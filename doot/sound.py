"""Le son du doot : lecture multiplateforme, avec repli synthetise.

Ordre de priorite :
  1. un fichier depose dans <data_dir>/sound/  (`doot --paths` donne le chemin)
  2. le son fourni avec doot (doot/assets/doot.mp3)
  3. un petit motif deux notes synthetise ici meme (harmoniques + vibrato +
     enveloppe ADSR + soft clipping), utilise quand rien ne sait lire le mp3

Formats acceptes : wav, mp3, ogg, opus, flac, m4a, aac.
"""

from __future__ import annotations

import math
import random
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

SAMPLE_RATE = 44100
TOTAL_SECONDS = 1.30

# "doo - doot" : une note breve puis une note tenue, meme hauteur (sol4).
NOTES = (
    {"start": 0.00, "duration": 0.28, "freq": 392.00},
    {"start": 0.34, "duration": 0.78, "freq": 392.00},
)

# Formats acceptes pour les sons perso.
AUDIO_EXTENSIONS = (".wav", ".mp3", ".ogg", ".oga", ".opus", ".flac", ".m4a", ".aac")

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
BUNDLED_SOUND = ASSETS_DIR / "doot.mp3"

# Lecteurs Linux/BSD, dans l'ordre de preference.
# "any" = gere aussi les formats compresses ; sinon wav (+ ce que lit libsndfile).
LINUX_PLAYERS = (
    ("mpv", ["mpv", "--really-quiet", "--no-video"], "any"),
    ("ffplay", ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"], "any"),
    ("play", ["play", "-q"], "any"),                  # SoX
    ("cvlc", ["cvlc", "--play-and-exit", "--intf", "dummy"], "any"),
    ("pw-play", ["pw-play"], "wav"),                  # PipeWire
    ("paplay", ["paplay"], "wav"),                    # PulseAudio
    ("aplay", ["aplay", "-q"], "wav"),                # ALSA
)

MCI_ALIAS = "dootsound"


# ------------------------------------------------------------- synthese ------

def _render_samples(volume: float) -> list[float]:
    count = int(SAMPLE_RATE * TOTAL_SECONDS)
    buffer = [0.0] * count
    two_pi = math.tau

    for note in NOTES:
        offset = int(note["start"] * SAMPLE_RATE)
        length = int(note["duration"] * SAMPLE_RATE)
        attack = int(0.018 * SAMPLE_RATE)
        decay = int(0.070 * SAMPLE_RATE)
        release = int(0.110 * SAMPLE_RATE)
        sustain = 0.78

        for i in range(length):
            t = i / SAMPLE_RATE

            if i < attack:
                envelope = i / attack
            elif i < attack + decay:
                envelope = 1.0 - (1.0 - sustain) * ((i - attack) / decay)
            elif i > length - release:
                envelope = sustain * ((length - i) / release)
            else:
                envelope = sustain

            # petit "scoop" a l'attaque + vibrato leger : ca sonne cuivre
            bend = 1.0 - 0.012 * math.exp(-t * 45.0)
            vibrato = 1.0 + 0.0045 * math.sin(two_pi * 5.4 * t)
            phase = two_pi * note["freq"] * bend * vibrato * t

            value = 0.0
            for harmonic in range(1, 9):
                value += math.sin(phase * harmonic) / harmonic**1.25

            index = offset + i
            if index < count:
                buffer[index] += (value / 2.3) * envelope

    for i in range(count):
        buffer[i] = math.tanh(buffer[i] * 1.35) * volume

    fade = int(0.02 * SAMPLE_RATE)  # evite le clic de fin
    for i in range(fade):
        buffer[count - 1 - i] *= i / fade

    return buffer


def write_wav(path: Path, volume: float = 0.55) -> Path:
    """Ecrit le jingle synthetise en WAV PCM 16 bits mono."""
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = _render_samples(volume)
    frames = b"".join(
        struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32000)) for s in samples
    )
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(frames)
    return path


def ensure_wav(path: Path, volume: float = 0.55, force: bool = False) -> Path:
    if force or not path.exists() or path.stat().st_size == 0:
        write_wav(path, volume)
    return path


def custom_sounds(custom_dir: Path) -> list[Path]:
    """Les fichiers audio deposes par l'utilisateur, tries."""
    if not custom_dir.is_dir():
        return []
    return sorted(
        p for p in custom_dir.iterdir()
        if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
    )


def bundled_sound() -> Path | None:
    """Le son livre avec doot, ou None si le paquet n'en contient pas."""
    return BUNDLED_SOUND if BUNDLED_SOUND.is_file() else None


def pick_sound(cache_wav: Path, custom_dir: Path, volume: float = 0.55) -> Path:
    """Son a jouer : perso d'abord, puis celui fourni, puis le jingle synthetise.

    Le son fourni est un mp3 : sur les systemes sans lecteur capable de le lire
    (Linux minimal sans mpv/ffmpeg/sox/vlc), on retombe sur le jingle wav.
    """
    customs = custom_sounds(custom_dir)
    if customs:
        return random.choice(customs)

    default = bundled_sound()
    if default is not None and (sys.platform == "win32" or find_player(default)):
        return default

    return ensure_wav(cache_wav, volume)


# --------------------------------------------------------------- lecture -----

def _mci(command: str) -> tuple[int, str]:
    """Envoie une commande MCI (Windows). Gere le mp3 et compagnie."""
    import ctypes

    buffer = ctypes.create_unicode_buffer(512)
    code = ctypes.windll.winmm.mciSendStringW(command, buffer, 511, 0)
    return code, buffer.value


def find_player(path: Path | None = None) -> list[str] | None:
    """Commande de lecture adaptee au fichier, ou None.

    Windows n'en a pas besoin (winsound / MCI sont integres).
    """
    if sys.platform == "win32":
        return None
    if sys.platform == "darwin":
        return ["afplay"] if shutil.which("afplay") else None

    compressed = path is not None and path.suffix.lower() not in (".wav",)
    for binary, command, formats in LINUX_PLAYERS:
        if compressed and formats != "any":
            continue
        if shutil.which(binary):
            return command
    return None


def play_async(path: Path) -> object | None:
    """Lance le son sans bloquer. Silencieux si aucun lecteur n'est dispo."""
    path = Path(path)

    if sys.platform == "win32":
        if path.suffix.lower() == ".wav":
            try:
                import winsound

                winsound.PlaySound(
                    str(path),
                    winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
                )
                return "winsound"
            except Exception:
                return None
        # mp3, m4a, wma... : MCI sait faire, sans dependance externe
        try:
            _mci(f"close {MCI_ALIAS}")
            code, _ = _mci(f'open "{path}" alias {MCI_ALIAS}')
            if code != 0:
                return None
            _mci(f"play {MCI_ALIAS}")
            return "mci"
        except Exception:
            return None

    command = find_player(path)
    if not command:
        return None
    try:
        return subprocess.Popen(
            command + [str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
    except Exception:
        return None


def release(handle: object | None) -> None:
    """Libere les ressources SANS couper le son en cours.

    Le squelette peut disparaitre avant la fin de la note : on laisse le son
    aller au bout plutot que de le tronquer.
    """
    if handle == "mci":
        # MCI garde le fichier ouvert : on ne ferme qu'a la lecture suivante.
        return
    return


def stop_all() -> None:
    """Coupe net tout son en cours (arret du programme)."""
    if sys.platform == "win32":
        try:
            import winsound

            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass
        try:
            _mci(f"close {MCI_ALIAS}")
        except Exception:
            pass


# --------------------------------------------------------------- duree -------

def probe_duration(path: Path) -> float | None:
    """Duree du fichier en secondes, ou None si on ne sait pas la lire."""
    path = Path(path)

    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as handle:
                rate = handle.getframerate()
                if rate:
                    return handle.getnframes() / float(rate)
        except Exception:
            return None
        return None

    if sys.platform == "win32":
        try:
            alias = MCI_ALIAS + "probe"
            _mci(f"close {alias}")
            code, _ = _mci(f'open "{path}" alias {alias}')
            if code != 0:
                return None
            _mci(f"set {alias} time format milliseconds")
            code, value = _mci(f"status {alias} length")
            _mci(f"close {alias}")
            if code == 0 and value.strip().isdigit():
                return int(value.strip()) / 1000.0
        except Exception:
            return None
        return None

    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        try:
            out = subprocess.run(
                [ffprobe, "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                capture_output=True, text=True, timeout=5,
            )
            return float(out.stdout.strip())
        except Exception:
            return None
    return None
