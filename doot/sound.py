"""Jingle de trompette : synthese maison + lecture multiplateforme.

Aucun fichier audio n'est fourni avec le projet : le petit motif deux notes est
synthetise localement (harmoniques + vibrato + enveloppe ADSR + soft clipping).
Tu peux deposer tes propres .wav dans <data_dir>/sound/ pour les utiliser a la
place (voir `doot --paths`).
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

# Lecteurs en ligne de commande testes dans l'ordre, sous Linux/BSD.
LINUX_PLAYERS = (
    ("pw-play", ["pw-play"]),          # PipeWire (Arch, Fedora, Ubuntu recents)
    ("paplay", ["paplay"]),            # PulseAudio
    ("aplay", ["aplay", "-q"]),        # ALSA (alsa-utils)
    ("ffplay", ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]),
    ("play", ["play", "-q"]),          # SoX
    ("mpv", ["mpv", "--really-quiet", "--no-video"]),
    ("cvlc", ["cvlc", "--play-and-exit", "--intf", "dummy"]),
)


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


def pick_sound(cache_wav: Path, custom_dir: Path, volume: float = 0.55) -> Path:
    """Un .wav perso dans custom_dir a la priorite sur le jingle genere."""
    if custom_dir.is_dir():
        customs = sorted(p for p in custom_dir.glob("*.wav") if p.is_file())
        if customs:
            return random.choice(customs)
    return ensure_wav(cache_wav, volume)


def find_player() -> list[str] | None:
    """Commande de lecture disponible, ou None (Windows utilise winsound)."""
    if sys.platform == "win32":
        return None
    if sys.platform == "darwin":
        return ["afplay"] if shutil.which("afplay") else None
    for binary, command in LINUX_PLAYERS:
        if shutil.which(binary):
            return command
    return None


def play_async(path: Path) -> subprocess.Popen | None:
    """Lance le son sans bloquer. Silencieux si aucun lecteur n'est dispo."""
    if sys.platform == "win32":
        try:
            import winsound

            winsound.PlaySound(
                str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
            )
        except Exception:
            pass
        return None

    command = find_player()
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


def stop(process: subprocess.Popen | None) -> None:
    if sys.platform == "win32":
        try:
            import winsound

            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass
        return
    if process and process.poll() is None:
        try:
            process.terminate()
        except Exception:
            pass
