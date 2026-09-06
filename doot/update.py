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


def remote_sha() -> str | None:
    """Dernier commit publie, ou None si le reseau ne repond pas."""
    requete = urllib.request.Request(
        API_HEAD,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "doot-update"},
    )
    try:
        with urllib.request.urlopen(requete, timeout=DELAI) as reponse:
            return json.loads(reponse.read().decode("utf-8")).get("sha")
    except Exception:
        return None


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


def run_installer(source: Path, fiche: dict, verbose=print) -> None:
    """Rejoue l'installeur de la plateforme avec les options d'origine."""
    minimum = str(fiche.get("min", 600))
    maximum = str(fiche.get("max", 3600))
    autostart = fiche.get("autostart", True)

    if sys.platform == "win32":
        script = source / "install.ps1"
        commande = [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(script), "-MinSeconds", minimum, "-MaxSeconds", maximum,
        ]
        if not autostart:
            commande.append("-NoAutostart")
    else:
        script = source / "install.sh"
        commande = ["bash", str(script), "--min", minimum, "--max", maximum]
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

    try:
        if sys.platform == "win32":
            pythonw = fiche.get("pythonw") or sys.executable
            app = fiche.get("app_dir", "")
            env = {**os.environ}
            if app:
                env["PYTHONPATH"] = app + os.pathsep + env.get("PYTHONPATH", "")
            DETACHED = 0x00000008 | 0x08000000  # DETACHED_PROCESS | CREATE_NO_WINDOW
            subprocess.Popen(
                [pythonw, "-m", "doot", "--min", minimum, "--max", maximum, "--quiet"],
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
                [str(lanceur), "--min", minimum, "--max", maximum, "--quiet"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL, start_new_session=True,
            )
            return True
    except Exception:
        return False
    return False


# ----------------------------------------------------------------- API -------

def check(verbose=print) -> int:
    """Compare le commit installe a celui publie."""
    installe = local_sha()
    publie = remote_sha()

    verbose(f"  installe    : {installe[:8] if installe else 'inconnu'}")
    if publie is None:
        verbose("  publie      : injoignable (pas de reseau ?)")
        return 2
    verbose(f"  publie      : {publie[:8]}")

    if installe and installe == publie:
        verbose("\ndoot est a jour.")
        return 0
    if installe:
        verbose("\nUne version plus recente existe : doot --update")
    else:
        verbose("\nCommit installe inconnu (installation manuelle ?) : "
                "doot --update reinstallera depuis GitHub.")
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
