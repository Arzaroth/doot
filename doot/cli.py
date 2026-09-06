"""Ligne de commande et boucle de fond de doot."""

from __future__ import annotations

import argparse
import ctypes
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

from . import __version__, art, image, season, sound

DEFAULT_MIN_SECONDS = 600     # 10 min
DEFAULT_MAX_SECONDS = 3600    # 1 h
DEFAULT_DURATION = 2.8
DEFAULT_VOLUME = 0.55
OUT_OF_SEASON_POLL = 3600     # on reverifie la date toutes les heures


# --------------------------------------------------------------- chemins -----

def data_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
        return Path(base) / "doot"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "doot"
    base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / "doot"


def paths() -> dict[str, Path]:
    root = data_dir()
    return {
        "data": root,
        "sound": root / "sound",
        "image": root / "image",
        "wav": root / "doot.wav",
        "log": root / "doot.log",
        "pid": root / "doot.pid",
    }


def log(message: str, quiet: bool = False) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {message}"
    try:
        path = paths()["log"]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        pass
    if not quiet:
        print(line, flush=True)


# ------------------------------------------------------- instance unique -----

def _process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        SYNCHRONIZE = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def running_pid() -> int | None:
    pid_file = paths()["pid"]
    try:
        pid = int(pid_file.read_text().strip())
    except Exception:
        return None
    if _process_alive(pid):
        return pid
    return None


def claim_pid_file() -> bool:
    existing = running_pid()
    if existing and existing != os.getpid():
        return False
    pid_file = paths()["pid"]
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()))
    return True


def release_pid_file() -> None:
    try:
        paths()["pid"].unlink()
    except Exception:
        pass


# ------------------------------------------------------------- actions -------

def resolve_media(args) -> tuple:
    """(son, image, duree) pour le prochain doot.

    Relu a chaque doot : tu peux deposer un son ou une image pendant que le
    daemon tourne, il les prendra sans redemarrage.
    """
    p = paths()

    wav = None
    if not args.no_sound:
        try:
            wav = sound.pick_sound(p["wav"], p["sound"], args.volume)
        except Exception as exc:
            log(f"son indisponible : {exc}", quiet=args.quiet)

    picture = None
    if not args.no_image:
        try:
            picture = image.pick_image(p["image"], args.image)
        except Exception as exc:
            log(f"image indisponible : {exc}", quiet=args.quiet)

    # Sans --duration explicite, on reste affiche le temps du son.
    duration = args.duration
    if duration is None:
        duration = DEFAULT_DURATION
        if wav is not None:
            length = sound.probe_duration(wav)
            if length:
                duration = max(DEFAULT_DURATION, length + 0.4)
    return wav, picture, duration


def do_once(args) -> int:
    from . import window

    if not args.ignore_season and not season.in_season():
        print(f"doot : {season.describe()}")
        print(f"Saison : {season.SEASON_LABEL}. (--ignore-season pour forcer un test.)")
        return 3

    wav, picture, duration = resolve_media(args)
    window.show(
        wav_path=wav,
        duration=duration,
        font_size=args.font_size,
        center=args.center,
        opacity=args.opacity,
        image_path=picture,
        scale=args.scale,
        screen=args.screen,
        spatialise=not args.no_pan,
        slide=not args.no_slide,
        side=args.side,
        slide_ms=args.slide_ms,
    )
    return 0


def do_daemon(args) -> int:
    from . import window

    if not claim_pid_file():
        log(f"une instance tourne deja (pid {running_pid()}), sortie.", quiet=args.quiet)
        return 1

    log(
        f"demarrage (pid {os.getpid()}) - intervalle {args.min}-{args.max}s - "
        f"saison {season.SEASON_LABEL}",
        quiet=args.quiet,
    )
    log("pour tout arreter : doot --stop  (desinstaller : voir le README)", quiet=args.quiet)

    try:
        while True:
            if not args.ignore_season and not season.in_season():
                wait = min(OUT_OF_SEASON_POLL, max(60.0, season.seconds_until_next_season()))
                log(season.describe(), quiet=args.quiet)
                time.sleep(wait)
                continue

            delay = random.randint(args.min, args.max)
            log(f"prochain doot dans {delay}s", quiet=args.quiet)
            time.sleep(delay)

            if not args.ignore_season and not season.in_season():
                continue  # la saison s'est fermee pendant l'attente

            try:
                wav, picture, duration = resolve_media(args)
                window.show(
                    wav_path=wav,
                    duration=duration,
                    font_size=args.font_size,
                    center=args.center,
                    opacity=args.opacity,
                    image_path=picture,
                    scale=args.scale,
                    screen=args.screen,
                    spatialise=not args.no_pan,
                    slide=not args.no_slide,
                    side=args.side,
                    slide_ms=args.slide_ms,
                )
                log("doot !", quiet=args.quiet)
            except window.TkinterMissing as exc:
                log(str(exc), quiet=args.quiet)
                return 4
            except Exception as exc:
                log(f"echec de l'affichage : {exc}", quiet=args.quiet)
    except KeyboardInterrupt:
        log("arret demande.", quiet=args.quiet)
    finally:
        release_pid_file()
        log("arret.", quiet=args.quiet)
    return 0


def do_status(args) -> int:
    p = paths()
    pid = running_pid()
    print(f"doot {__version__}")
    print(f"  saison      : {season.SEASON_LABEL}")
    print(f"  etat        : {season.describe()}")
    print(f"  daemon      : {'actif (pid ' + str(pid) + ')' if pid else 'arrete'}")
    print(f"  donnees     : {p['data']}")

    sounds = sound.custom_sounds(p["sound"])
    if sounds:
        extra = f" (+{len(sounds) - 1} autre(s), tirage au hasard)" if len(sounds) > 1 else ""
        print(f"  son         : {sounds[0].name}{extra}")
    else:
        chosen = sound.pick_sound(p["wav"], p["sound"])
        origin = "fourni" if chosen == sound.BUNDLED_SOUND else "jingle synthetise"
        print(f"  son         : {chosen.name} ({origin})")
    print(f"  sons perso  : {p['sound']}  ({len(sounds)} fichier(s))")

    pictures = image.custom_images(p["image"])
    if pictures:
        extra = f" (+{len(pictures) - 1} autre(s), tirage au hasard)" if len(pictures) > 1 else ""
        print(f"  image       : {pictures[0].name}{extra}")
    elif image.bundled_image():
        print(f"  image       : {image.BUNDLED_IMAGE.name} (fournie)")
    else:
        print("  image       : ASCII art (depose un PNG/GIF dans le dossier ci-dessous)")
    print(f"  images      : {p['image']}  ({len(pictures)} fichier(s))")

    from . import screens

    found = screens.monitors()
    target = "au hasard" if args.screen in (None, "", "random") else f"--screen {args.screen}"
    print(f"  ecrans      : {screens.describe(found)} -> apparition {target}")

    print(f"  journal     : {p['log']}")
    if sys.platform == "win32":
        print("  lecteur     : winsound + MCI (integres)")
    else:
        player = sound.find_player()
        print(f"  lecteur     : {player[0] if player else 'AUCUN (installe mpv/ffmpeg/pipewire/alsa-utils)'}")
    try:
        from . import window  # noqa: F401

        import tkinter  # noqa: F401

        print("  affichage   : tkinter OK")
    except Exception:
        print("  affichage   : tkinter MANQUANT (voir README)")
    return 0


def do_update(args) -> int:
    from . import update

    print(f"doot {__version__} - mise a jour")
    return update.update()


def do_check_update(args) -> int:
    from . import update

    print(f"doot {__version__}")
    return update.check()


def do_screens(args) -> int:
    from . import screens

    found = screens.monitors()
    print(f"doot : {len(found)} ecran(s) detecte(s)")
    for index, monitor in enumerate(found):
        tag = "  (principal)" if monitor.primary else ""
        print(f"  {index}  {monitor.name:<16} {monitor.width}x{monitor.height} "
              f"a +{monitor.x}+{monitor.y}{tag}")
    print("\nPar defaut le squelette surgit sur un ecran au hasard.")
    print("Le fixer :  doot --screen 0   |   doot --screen primary")
    return 0


def do_paths(args) -> int:
    for key, value in paths().items():
        print(f"{key:6} {value}")
    return 0


def do_stop(args) -> int:
    pid = running_pid()
    if not pid:
        print("doot : aucun daemon en cours.")
        return 1
    try:
        if sys.platform == "win32":
            os.system(f"taskkill /PID {pid} /F >NUL 2>&1")
        else:
            import signal

            os.kill(pid, signal.SIGTERM)
        print(f"doot : daemon {pid} arrete.")
        release_pid_file()
        return 0
    except Exception as exc:
        print(f"doot : impossible d'arreter {pid} : {exc}")
        return 1


def do_art(args) -> int:
    print(art.frame(len(art.DOOT_FRAMES) - 1))
    return 0


# ---------------------------------------------------------------- parse ------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doot",
        description="Un squelette trompettiste surgit au hasard sur ton ecran, "
        f"uniquement du {season.SEASON_LABEL}.",
    )
    parser.add_argument("--version", action="version", version=f"doot {__version__}")

    parser.add_argument("--once", action="store_true", help="affiche un doot tout de suite puis quitte")
    parser.add_argument("--status", action="store_true", help="affiche l'etat (saison, daemon, audio)")
    parser.add_argument("--stop", action="store_true", help="arrete le daemon en cours")
    parser.add_argument("--paths", action="store_true", help="affiche les chemins utilises")
    parser.add_argument("--art", action="store_true", help="imprime le squelette dans le terminal")
    parser.add_argument("--update", action="store_true",
                        help="met a jour doot depuis GitHub et rejoue l'installeur")
    parser.add_argument("--check-update", action="store_true",
                        help="dit si une version plus recente existe, sans rien installer")

    parser.add_argument("--min", type=int, default=DEFAULT_MIN_SECONDS,
                        help=f"delai minimum entre deux doot, en secondes (defaut {DEFAULT_MIN_SECONDS})")
    parser.add_argument("--max", type=int, default=DEFAULT_MAX_SECONDS,
                        help=f"delai maximum entre deux doot, en secondes (defaut {DEFAULT_MAX_SECONDS})")
    parser.add_argument("--duration", type=float, default=None,
                        help=f"duree d'affichage en secondes (defaut : la duree du son, au moins {DEFAULT_DURATION})")
    parser.add_argument("--image", default=None, metavar="FICHIER",
                        help="PNG ou GIF a afficher au lieu de l'ASCII art")
    parser.add_argument("--no-image", action="store_true",
                        help="force l'ASCII art meme si une image est disponible")
    parser.add_argument("--scale", type=float, default=None,
                        help="echelle de l'image (defaut : ajustee a l'ecran)")
    parser.add_argument("--volume", type=float, default=DEFAULT_VOLUME,
                        help="volume du jingle synthetise, 0.0 a 1.0")
    parser.add_argument("--opacity", type=float, default=1.0, help="opacite maximale, 0.0 a 1.0")
    parser.add_argument("--font-size", type=int, default=15, help="taille de la police (defaut 15)")
    parser.add_argument("--center", action="store_true", help="toujours au centre au lieu du hasard")
    parser.add_argument("--no-slide", action="store_true",
                        help="apparait sur place, sans entrer par le cote")
    parser.add_argument("--side", default=None,
                        choices=("left", "right", "top", "bottom", "random"),
                        help="bord par lequel le squelette entre (defaut : au hasard). "
                             "Le bas de l'image se pose contre ce bord.")
    parser.add_argument("--slide-ms", type=int, default=420,
                        help="duree de l'entree en millisecondes (defaut 420)")
    parser.add_argument("--screen", default=None, metavar="CHOIX",
                        help="ecran d'apparition : 'random' (defaut), 'primary', "
                             "ou un index (0, 1, 2...). Voir 'doot --screens'.")
    parser.add_argument("--screens", action="store_true", help="liste les ecrans detectes")
    parser.add_argument("--no-sound", action="store_true", help="mode muet")
    parser.add_argument("--no-pan", action="store_true",
                        help="son au centre, au lieu de suivre la position du squelette")
    parser.add_argument("--regen-sound", action="store_true", help="regenere le jingle synthetise")
    parser.add_argument("--ignore-season", action="store_true",
                        help="ignore la fenetre 1er sept - 31 oct (tests uniquement)")
    parser.add_argument("--quiet", action="store_true", help="n'ecrit que dans le journal")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.min < 1:
        args.min = 1
    if args.max < args.min:
        args.max = args.min

    p = paths()
    p["data"].mkdir(parents=True, exist_ok=True)
    p["sound"].mkdir(parents=True, exist_ok=True)
    p["image"].mkdir(parents=True, exist_ok=True)

    if args.regen_sound:
        sound.ensure_wav(p["wav"], args.volume, force=True)
        print(f"doot : jingle regenere -> {p['wav']}")

    if args.check_update:
        return do_check_update(args)
    if args.update:
        return do_update(args)
    if args.screens:
        return do_screens(args)
    if args.status:
        return do_status(args)
    if args.paths:
        return do_paths(args)
    if args.stop:
        return do_stop(args)
    if args.art:
        return do_art(args)

    try:
        if args.once:
            return do_once(args)
        return do_daemon(args)
    except Exception as exc:
        from .window import TkinterMissing

        if isinstance(exc, TkinterMissing):
            print(str(exc), file=sys.stderr)
            return 4
        raise


if __name__ == "__main__":
    raise SystemExit(main())
