"""Mise a jour d'une installation existante, sur les trois plateformes.

L'installeur laisse une fiche dans `<data_dir>/install.json` : d'ou le code
vient, quel commit, avec quelles options. `doot --update` la relit pour
rafraichir la source puis rejouer l'installeur avec les memes reglages.

Deux facons de rafraichir la source, dans cet ordre :

  1. si le depot clone est toujours la, `git pull --ff-only` ;
  2. sinon, l'archive de la branche principale est telechargee depuis GitHub
     et depliee dans un dossier temporaire.

La seconde voie ne demande ni git ni le clone d'origine : une installation
faite il y a six mois, dont le dossier a ete efface depuis, se met a jour
quand meme.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from . import cli

DEPOT = "boubou666/doot"
BRANCHE = "main"
ARCHIVE = f"https://codeload.github.com/{DEPOT}/zip/refs/heads/{BRANCHE}"
API_HEAD = f"https://api.github.com/repos/{DEPOT}/commits/{BRANCHE}"
API_LATEST = f"https://api.github.com/repos/{DEPOT}/releases/latest"
DELAI = 30


class UpdateError(RuntimeError):
    """Mise a jour impossible : le message explique quoi faire a la main."""


# ---------------------------------------------------------------- fiche ------

def record_path() -> Path:
    # cli.paths() est appele ici et pas importe une fois pour toutes : lie a
    # l'import, la fonction ne serait plus remplacable, et les tests ecriraient
    # dans le vrai dossier de donnees au lieu de leur bac a sable.
    return cli.paths()["data"] / "install.json"


def read_record() -> dict:
    # utf-8-sig et pas utf-8 : PowerShell 5.1 ecrit l'UTF-8 avec un BOM, et
    # json.loads refuse ce caractere invisible en tete de fichier. La fiche
    # deposee par install.ps1 serait illisible, sans le moindre message.
    try:
        return json.loads(record_path().read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def write_record(data: dict) -> Path:
    chemin = record_path()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return chemin


def local_sha() -> str | None:
    """Commit installe, d'apres la fiche puis d'apres le depot source."""
    fiche = read_record()
    if fiche.get("commit"):
        return fiche["commit"]
    source = fiche.get("source")
    if source:
        return git_sha(Path(source))
    return None


def git_sha(depot: Path) -> str | None:
    if not (depot / ".git").exists():
        return None
    try:
        out = subprocess.run(
            ["git", "-C", str(depot), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=15,
        )
        return out.stdout.strip() or None if out.returncode == 0 else None
    except Exception:
        return None


# ------------------------------------------------------------ installation ---

def managed_elsewhere() -> str | None:
    """Signale une installation qui ne nous appartient pas (paquet systeme)."""
    ici = Path(__file__).resolve()
    for prefixe, outil in (
        ("/usr/lib", "ton gestionnaire de paquets (pacman -Syu, apt upgrade...)"),
        ("/usr/local/lib", "ton gestionnaire de paquets"),
        ("/opt", "ton gestionnaire de paquets"),
    ):
        if str(ici).startswith(prefixe):
            return outil
    return None


def _api(url: str) -> dict | None:
    requete = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "doot-update"},
    )
    try:
        with urllib.request.urlopen(requete, timeout=DELAI) as reponse:
            return json.loads(reponse.read().decode("utf-8"))
    except Exception:
        return None


def remote_sha() -> str | None:
    """Dernier commit publie, ou None si le reseau ne repond pas."""
    donnees = _api(API_HEAD)
    return donnees.get("sha") if donnees else None


def latest_release() -> str | None:
    """Version de la derniere release, sans le v initial.

    Sert aux installations faites depuis une release : elles n'ont pas de
    depot git, donc pas de commit a comparer, mais elles ont un numero de
    version.
    """
    donnees = _api(API_LATEST)
    if not donnees:
        return None
    etiquette = donnees.get("tag_name") or ""
    return etiquette.lstrip("v") or None


def download_source(destination: Path) -> Path:
    """Telecharge et deplie l'archive de la branche ; renvoie sa racine."""
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / "doot.zip"
    requete = urllib.request.Request(ARCHIVE, headers={"User-Agent": "doot-update"})
    try:
        with urllib.request.urlopen(requete, timeout=DELAI) as reponse:
            archive.write_bytes(reponse.read())
    except urllib.error.URLError as erreur:
        raise UpdateError(f"telechargement impossible : {erreur}") from erreur

    try:
        with zipfile.ZipFile(archive) as zip_:
            zip_.extractall(destination)
    except zipfile.BadZipFile as erreur:
        raise UpdateError("archive telechargee illisible") from erreur

    racines = [p for p in destination.iterdir() if p.is_dir()]
    if not racines:
        raise UpdateError("archive telechargee vide")
    return racines[0]


def refresh_source(fiche: dict, travail: Path, verbose=print) -> tuple[Path, str]:
    """Rend une source a jour, et dit d'ou elle vient."""
    source = fiche.get("source")
    if source:
        depot = Path(source)
        if (depot / ".git").exists() and shutil.which("git"):
            verbose(f"  source      : {depot} (depot git)")
            out = subprocess.run(
                ["git", "-C", str(depot), "pull", "--ff-only"],
                capture_output=True, text=True, timeout=120,
            )
            if out.returncode == 0:
                return depot, "git pull"
            verbose(f"  git pull a echoue ({out.stderr.strip().splitlines()[-1:]}), "
                    "on passe par l'archive")

    verbose(f"  source      : archive {BRANCHE} depuis GitHub")
    return download_source(travail), "archive"


def salve_reglee(fiche: dict) -> tuple[str, str, str] | None:
    """(min, max, delai) si la fiche demande des salves, sinon rien.

    Une fiche ecrite avant les salves n'a aucune de ces cles : le defaut les
    ramene a 1, et l'installeur comme le daemon sont alors relances avec
    exactement la commande d'avant. Une fiche abimee ne doit pas non plus
    faire echouer une mise a jour pour si peu, d'ou le repli silencieux.
    """
    try:
        haut = int(fiche.get("burst_max", 1))
        bas = int(fiche.get("burst_min", 1))
        delai = float(fiche.get("burst_delay", 0.6))
    except (TypeError, ValueError):
        return None
    if haut <= 1:
        return None
    return str(bas), str(haut), str(delai)


def run_installer(source: Path, fiche: dict, verbose=print) -> None:
    """Rejoue l'installeur de la plateforme avec les options d'origine."""
    minimum = str(fiche.get("min", 600))
    maximum = str(fiche.get("max", 3600))
    autostart = fiche.get("autostart", True)
    salve = salve_reglee(fiche)

    if sys.platform == "win32":
        script = source / "install.ps1"
        commande = [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(script), "-MinSeconds", minimum, "-MaxSeconds", maximum,
        ]
        if salve:
            commande += ["-BurstMin", salve[0], "-BurstMax", salve[1],
                         "-BurstDelay", salve[2]]
        if not autostart:
            commande.append("-NoAutostart")
    else:
        script = source / "install.sh"
        commande = ["bash", str(script), "--min", minimum, "--max", maximum]
        if salve:
            commande += ["--burst-min", salve[0], "--burst-max", salve[1],
                         "--burst-delay", salve[2]]
        if not autostart:
            commande.append("--no-autostart")

    if not script.is_file():
        raise UpdateError(f"installeur introuvable dans la source : {script}")

    verbose(f"  installeur  : {script.name}")
    out = subprocess.run(commande, capture_output=True, text=True, timeout=600)
    if out.returncode != 0:
        detail = (out.stderr or out.stdout).strip().splitlines()[-5:]
        raise UpdateError("l'installeur a echoue :\n    " + "\n    ".join(detail))


# ------------------------------------------------------------- daemon --------

def daemon_pid() -> int | None:
    from .cli import running_pid

    return running_pid()


def stop_daemon() -> bool:
    from .cli import release_pid_file

    pid = daemon_pid()
    if not pid:
        return False
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                           capture_output=True, timeout=30)
        else:
            import signal

            os.kill(pid, signal.SIGTERM)
        release_pid_file()
        return True
    except Exception:
        return False


def start_daemon(fiche: dict) -> bool:
    """Relance le daemon en tache de fond, par le chemin de la plateforme."""
    minimum = str(fiche.get("min", 600))
    maximum = str(fiche.get("max", 3600))
    salve = salve_reglee(fiche)
    options = ["--min", minimum, "--max", maximum]
    if salve:
        options += ["--burst-min", salve[0], "--burst-max", salve[1],
                    "--burst-delay", salve[2]]
    options.append("--quiet")

    try:
        if sys.platform == "win32":
            pythonw = fiche.get("pythonw") or sys.executable
            app = fiche.get("app_dir", "")
            env = {**os.environ}
            if app:
                env["PYTHONPATH"] = app + os.pathsep + env.get("PYTHONPATH", "")
            DETACHED = 0x00000008 | 0x08000000  # DETACHED_PROCESS | CREATE_NO_WINDOW
            subprocess.Popen(
                [pythonw, "-m", "doot", *options],
                cwd=app or None, env=env, creationflags=DETACHED,
                close_fds=True,
            )
            return True

        if shutil.which("systemctl"):
            out = subprocess.run(["systemctl", "--user", "restart", "doot.service"],
                                 capture_output=True, timeout=60)
            if out.returncode == 0:
                return True

        lanceur = Path.home() / ".local" / "bin" / "doot"
        if lanceur.is_file():
            subprocess.Popen(
                [str(lanceur), *options],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL, start_new_session=True,
            )
            return True
    except Exception:
        return False
    return False


# ----------------------------------------------------------------- API -------

def check(verbose=print) -> int:
    """Dit si une version plus recente existe.

    Deux facons de comparer, selon ce qu'on sait de l'installation. Avec un
    depot git derriere, on compare les commits, c'est le plus precis. Installe
    depuis une release il n'y a pas de commit, mais il y a un numero de
    version : on le compare alors a celui de la derniere release. Sans ce
    second recours, `--check-update` ne repondait jamais rien d'utile a qui
    avait installe depuis une release.
    """
    from . import __version__

    installe = local_sha()

    if installe:
        publie = remote_sha()
        verbose(f"  installe    : {installe[:8]} (commit)")
        if publie is None:
            verbose("  publie      : injoignable (pas de reseau ?)")
            return 2
        verbose(f"  publie      : {publie[:8]}")
        if installe == publie:
            verbose("\ndoot est a jour.")
            return 0
        verbose("\nUne version plus recente existe : doot --update")
        return 1

    publiee = latest_release()
    verbose(f"  installe    : {__version__} (version, pas de depot git)")
    if publiee is None:
        verbose("  publie      : injoignable (pas de reseau, ou aucune release)")
        return 2
    verbose(f"  publie      : {publiee}")

    if __version__ == publiee:
        verbose("\ndoot est a jour.")
        verbose("(compare de version a version : `doot --update` ira quand meme "
                "chercher les derniers changements de la branche principale.)")
        return 0
    verbose("\nUne version plus recente existe : doot --update")
    return 1


def update(verbose=print) -> int:
    """Rafraichit la source, rejoue l'installeur, relance le daemon."""
    gestionnaire = managed_elsewhere()
    if gestionnaire:
        verbose(f"doot est installe par {gestionnaire}.")
        verbose("Mets-le a jour par ce biais, pas avec --update.")
        return 3

    fiche = read_record()
    if not fiche:
        verbose("Aucune fiche d'installation : doot n'a pas ete installe par")
        verbose("install.sh ou install.ps1, ou elle a ete effacee.")
        verbose("On tente quand meme depuis GitHub.\n")

    avant = local_sha()
    tournait = daemon_pid() is not None
    if tournait:
        verbose("  daemon      : arret le temps de la mise a jour")
        stop_daemon()

    with tempfile.TemporaryDirectory(prefix="doot-update-") as travail:
        source, voie = refresh_source(fiche, Path(travail), verbose)
        run_installer(source, fiche, verbose)
        apres = git_sha(source) or remote_sha()
        source_durable = source if git_sha(source) else None

    # L'installeur vient de reecrire la fiche. Par une archive il n'a pas de
    # commit a y mettre, et il y laisse le dossier temporaire qu'on efface a
    # l'instant : on rectifie, sans quoi la fiche pointerait un chemin mort et
    # --check-update resterait muet jusqu'a la fin des temps.
    fraiche = read_record()
    if fraiche:
        if apres and not fraiche.get("commit"):
            fraiche["commit"] = apres
        if not source_durable:
            fraiche["source"] = ""
        write_record(fraiche)

    if tournait:
        verbose("  daemon      : redemarrage")
        if not start_daemon(read_record() or fiche):
            verbose("  (relance automatique impossible, lance `doot` toi-meme)")

    verbose("")
    if avant and apres and avant == apres:
        verbose(f"Deja a jour ({avant[:8]}), reinstalle par acquit de conscience.")
    elif apres:
        verbose(f"Mis a jour : {avant[:8] if avant else '?'} -> {apres[:8]} (via {voie}).")
    else:
        verbose(f"Reinstalle depuis la source ({voie}).")
    return 0
