"""Ou les parts sont deposees : un dossier, ou un seau compatible S3.

Les deux repondent aux memes quatre gestes, deposer, lister, reprendre,
effacer, et le cycle ne sait pas lequel il tient. Chaque machine ecrit un objet
que seule elle ecrit, ce qui retire toute resolution de conflit du dessin :
deux machines n'ecrivent jamais le meme nom.

Le `v1` du chemin laisse la porte ouverte a un format suivant sans melanger les
deux.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import os
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from . import coffre

VERSION = "v1"
DELAI = 20
SHA256_VIDE = hashlib.sha256(b"").hexdigest()
ESPACE_S3 = "{http://s3.amazonaws.com/doc/2006-03-01/}"


class TransportError(RuntimeError):
    """Le depot est injoignable ou refuse : le cycle le note et passe."""


@dataclass(frozen=True)
class Objet:
    """Un objet rencontre dans le depot."""

    nom: str
    modifie: str = ""


def ecrire_atomiquement(chemin: Path, octets: bytes) -> None:
    """Ecrit a cote puis renomme.

    Un pair qui lit pendant l'ecriture recevrait sinon un fichier tronque, ce
    qui est d'autant plus probable sur un dossier synchronise ou un montage
    reseau.
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    tampon = chemin.with_name(f".{chemin.name}.tmp")
    tampon.write_bytes(octets)
    os.replace(tampon, chemin)


class Dossier:
    """Un dossier du disque, que Syncthing ou rclone se charge de faire voyager."""

    def __init__(self, racine):
        self.racine = Path(racine).expanduser() / VERSION

    def decrire(self) -> str:
        return f"dossier {self.racine}"

    def deposer(self, nom: str, octets: bytes) -> None:
        ecrire_atomiquement(self.racine / nom, octets)

    def lister(self) -> list[Objet]:
        try:
            entrees = list(self.racine.iterdir())
        except FileNotFoundError:
            return []   # rien de publie, c'est une flotte d'une machine
        except OSError as exc:
            raise TransportError(str(exc)) from exc
        return [
            Objet(chemin.name, str(int(chemin.stat().st_mtime)))
            for chemin in sorted(entrees)
            if coffre.est_un_objet(chemin.name) and chemin.is_file()
        ]

    def reprendre(self, objet: Objet) -> bytes | None:
        try:
            return (self.racine / objet.nom).read_bytes()
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise TransportError(str(exc)) from exc

    def effacer(self, nom: str) -> None:
        (self.racine / nom).unlink(missing_ok=True)


class S3:
    """Un seau compatible S3 : AWS, Cloudflare R2, MinIO, Backblaze B2.

    Signature version 4 a la main, faute de vouloir tirer un SDK entier dans un
    outil de farce. Seuls quatre gestes sont signes, ce qui tient en une page.
    """

    def __init__(self, endpoint: str, region: str, seau: str, prefixe: str = "",
                 cle_acces: str = "", secret: str = "", jeton: str = ""):
        self.endpoint = endpoint.rstrip("/")
        self.region = region or "auto"
        self.seau = seau
        self.prefixe = f"{prefixe.strip('/')}/{VERSION}/" if prefixe.strip("/") else f"{VERSION}/"
        self.cle_acces = cle_acces or os.environ.get("AWS_ACCESS_KEY_ID", "")
        self.secret = secret or os.environ.get("AWS_SECRET_ACCESS_KEY", "")
        self.jeton = jeton or os.environ.get("AWS_SESSION_TOKEN", "")

    def decrire(self) -> str:
        return f"seau {self.seau} sur {urllib.parse.urlparse(self.endpoint).netloc}"

    # ------------------------------------------------------------ signature --

    def _signer(self, methode: str, chemin: str, requete: dict, charge: bytes) -> tuple:
        maintenant = datetime.datetime.now(datetime.timezone.utc)
        horodatage = maintenant.strftime("%Y%m%dT%H%M%SZ")
        jour = horodatage[:8]
        hote = urllib.parse.urlparse(self.endpoint).netloc
        empreinte = hashlib.sha256(charge).hexdigest() if charge else SHA256_VIDE

        entetes = {"host": hote, "x-amz-content-sha256": empreinte, "x-amz-date": horodatage}
        if self.jeton:
            entetes["x-amz-security-token"] = self.jeton

        noms = sorted(entetes)
        canoniques = "".join(f"{nom}:{entetes[nom]}\n" for nom in noms)
        signes = ";".join(noms)
        query = "&".join(
            f"{urllib.parse.quote(cle, safe='')}={urllib.parse.quote(str(valeur), safe='')}"
            for cle, valeur in sorted(requete.items())
        )
        demande = "\n".join([
            methode, urllib.parse.quote(chemin, safe="/"), query,
            canoniques, signes, empreinte,
        ])

        portee = f"{jour}/{self.region}/s3/aws4_request"
        a_signer = "\n".join([
            "AWS4-HMAC-SHA256", horodatage, portee,
            hashlib.sha256(demande.encode("utf-8")).hexdigest(),
        ])

        cle = f"AWS4{self.secret}".encode("utf-8")
        for morceau in (jour, self.region, "s3", "aws4_request"):
            cle = hmac.new(cle, morceau.encode("utf-8"), hashlib.sha256).digest()
        signature = hmac.new(cle, a_signer.encode("utf-8"), hashlib.sha256).hexdigest()

        entetes["Authorization"] = (
            f"AWS4-HMAC-SHA256 Credential={self.cle_acces}/{portee}, "
            f"SignedHeaders={signes}, Signature={signature}"
        )
        return entetes, query

    def _appeler(self, methode: str, chemin: str, requete: dict = None,
                 charge: bytes = b"") -> bytes | None:
        requete = requete or {}
        entetes, query = self._signer(methode, chemin, requete, charge)
        url = f"{self.endpoint}{urllib.parse.quote(chemin, safe='/')}"
        if query:
            url = f"{url}?{query}"

        demande = urllib.request.Request(url, data=charge or None, method=methode)
        for nom, valeur in entetes.items():
            demande.add_header(nom, valeur)
        try:
            with urllib.request.urlopen(demande, timeout=DELAI) as reponse:
                return reponse.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise TransportError(f"{methode} {chemin} : {exc.code} {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise TransportError(f"{methode} {chemin} : {exc.reason}") from exc

    # -------------------------------------------------------------- gestes ---

    def deposer(self, nom: str, octets: bytes) -> None:
        self._appeler("PUT", f"/{self.seau}/{self.prefixe}{nom}", charge=octets)

    def lister(self) -> list[Objet]:
        trouves = []
        suite = None
        while True:
            requete = {"list-type": "2", "prefix": self.prefixe}
            if suite:
                requete["continuation-token"] = suite
            corps = self._appeler("GET", f"/{self.seau}", requete)
            if not corps:
                return trouves
            arbre = ET.fromstring(corps)
            for entree in arbre.findall(f"{ESPACE_S3}Contents"):
                chemin = (entree.findtext(f"{ESPACE_S3}Key") or "").rsplit("/", 1)[-1]
                if coffre.est_un_objet(chemin):
                    trouves.append(Objet(chemin, entree.findtext(f"{ESPACE_S3}ETag") or ""))
            if arbre.findtext(f"{ESPACE_S3}IsTruncated") != "true":
                return trouves
            suite = arbre.findtext(f"{ESPACE_S3}NextContinuationToken")
            if not suite:
                return trouves

    def reprendre(self, objet: Objet) -> bytes | None:
        return self._appeler("GET", f"/{self.seau}/{self.prefixe}{objet.nom}")

    def effacer(self, nom: str) -> None:
        self._appeler("DELETE", f"/{self.seau}/{self.prefixe}{nom}")


def ouvrir(reglage: dict):
    """Le depot decrit par la fiche de synchronisation."""
    if reglage.get("seau"):
        return S3(
            endpoint=reglage.get("endpoint", ""),
            region=reglage.get("region", ""),
            seau=reglage["seau"],
            prefixe=reglage.get("prefixe", ""),
            cle_acces=reglage.get("cle_acces", ""),
            secret=reglage.get("secret", ""),
        )
    if reglage.get("dossier"):
        return Dossier(reglage["dossier"])
    raise TransportError("ni dossier ni seau dans la fiche de synchronisation")
