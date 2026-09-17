"""La cle du partage, l'enveloppe chiffree, et le nom des objets.

La contribution traverse un stockage que la personne ne controle pas des qu'on
sort du disque local, donc elle est chiffree des le depart. Une seule cle
symetrique de 32 octets, partagee par toutes les machines et recopiee a la main
comme un identifiant Syncthing : une flotte d'une personne n'a pas besoin de
distribution de cles, et tout mecanisme qui offrirait une vraie revocation
couterait plus cher que la fonctionnalite.

**Il n'y a donc pas de revocation.** Une machine perdue ou volee peut lire la
progression de la flotte tant que toutes les autres n'ont pas ete rechiffrees a
la main : `--sync-init --force` ici, `--sync-join` sur chacune, et les anciens
objets supprimes. Le dire vaut mieux que laisser croire que « chiffre » veut
dire « revocable ».

Le nom des objets est un `HMAC(cle, identite)`, pour que celui qui heberge le
dossier ne puisse pas relier un objet a une machine. La *taille* de la flotte
n'est pas cachee, un objet par machine se compte quel que soit son nom, et
l'heure des ecritures laisse deviner des horaires.

La possession de la cle est la seule authentification. Une machine ne peut pas
prouver laquelle elle est au-dela de detenir la cle, ce qui est le bon niveau
pour les machines d'une personne et le mauvais pour une equipe.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import hmac
import os

MAGIC = b"DOOTSYNC1"
ALG_CHACHA20_POLY1305 = 1
SANS_COMPRESSION = 0
GZIP = 1
TAILLE_CLE = 32
TAILLE_ID_CLE = 4
TAILLE_NONCE = 12
ENTETE = len(MAGIC) + 2 + TAILLE_ID_CLE

PREFIXE = "dootsync1"
DOMAINE_ID = b"doot.partage.id-cle.v1"
DOMAINE_NOM = b"doot.partage.nom-objet.v1"
SUFFIXE = ".dootsync"


class CoffreError(ValueError):
    """Cle ou enveloppe inutilisable : le message dit laquelle."""


def _aead():
    """L'AEAD, importe tard pour que le reste de doot tourne sans lui."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
    except ImportError as exc:  # pragma: no cover - depend de l'installation
        raise CoffreError(
            "le partage chiffre demande le paquet `cryptography` : "
            "pip install cryptography, ou uv tool install spooky-doot"
        ) from exc
    return ChaCha20Poly1305


def creer() -> bytes:
    """Une cle neuve, tiree de l'aleatoire du systeme."""
    return os.urandom(TAILLE_CLE)


def en_texte(cle: bytes) -> str:
    """La cle telle qu'on la recopie d'une machine a l'autre."""
    corps = base64.b32encode(cle).decode("ascii").lower().rstrip("=")
    return f"{PREFIXE}{corps}"


def depuis_texte(texte: str) -> bytes:
    """Relit une cle recopiee. Leve plutot que de rendre une cle a moitie juste."""
    texte = (texte or "").strip()
    if not texte.startswith(PREFIXE):
        raise CoffreError(f"une cle de partage commence par `{PREFIXE}`")
    corps = texte[len(PREFIXE):].upper()
    corps += "=" * (-len(corps) % 8)
    try:
        cle = base64.b32decode(corps)
    except Exception as exc:
        raise CoffreError(f"cle illisible : {exc}") from exc
    if len(cle) != TAILLE_CLE:
        raise CoffreError(f"une cle fait {TAILLE_CLE} octets, celle-ci en fait {len(cle)}")
    return cle


def identifiant(cle: bytes) -> bytes:
    """De quoi reconnaitre qu'un objet a ete ferme avec une autre cle."""
    return hashlib.sha256(DOMAINE_ID + cle).digest()[:TAILLE_ID_CLE]


def nom_objet(cle: bytes, identite: str) -> str:
    """Le nom sous lequel une machine publie, opaque a qui heberge le dossier."""
    marque = hmac.new(cle, DOMAINE_NOM + identite.encode("utf-8"), hashlib.sha256)
    return marque.hexdigest()[:32] + SUFFIXE


def est_un_objet(nom: str) -> bool:
    """Trente-deux caracteres hexadecimaux et rien d'autre.

    Ce qui ecarte au passage les copies de conflit qu'un outil de
    synchronisation laisse derriere lui, du genre
    `...sync-conflict-20260918-120000-ABCDEFG.dootsync`.
    """
    if not nom.endswith(SUFFIXE):
        return False
    tronc = nom[:-len(SUFFIXE)]
    return len(tronc) == 32 and all(c in "0123456789abcdef" for c in tronc)


def fermer(cle: bytes, clair: bytes) -> bytes:
    """Scelle le contenu : entete lisible, puis nonce et chiffre."""
    corps = gzip.compress(clair, mtime=0)
    compression = GZIP
    if len(corps) >= len(clair):
        corps, compression = clair, SANS_COMPRESSION

    nonce = os.urandom(TAILLE_NONCE)
    entete = MAGIC + bytes([ALG_CHACHA20_POLY1305, compression]) + identifiant(cle)
    scelle = _aead()(cle).encrypt(nonce, corps, entete)
    return entete + nonce + scelle


def ouvrir(cle: bytes, enveloppe: bytes) -> bytes:
    """Rouvre une enveloppe, ou dit precisement pourquoi elle resiste."""
    if len(enveloppe) < ENTETE + TAILLE_NONCE or not enveloppe.startswith(MAGIC):
        raise CoffreError("ce n'est pas une enveloppe doot")

    algorithme, compression = enveloppe[len(MAGIC)], enveloppe[len(MAGIC) + 1]
    if algorithme != ALG_CHACHA20_POLY1305:
        raise CoffreError(f"algorithme inconnu : {algorithme}")

    entete = enveloppe[:ENTETE]
    if entete[-TAILLE_ID_CLE:] != identifiant(cle):
        raise CoffreError("enveloppe fermee avec une autre cle")

    nonce = enveloppe[ENTETE:ENTETE + TAILLE_NONCE]
    try:
        corps = _aead()(cle).decrypt(nonce, enveloppe[ENTETE + TAILLE_NONCE:], entete)
    except CoffreError:
        raise
    except Exception as exc:
        raise CoffreError("enveloppe abimee ou falsifiee") from exc

    if compression == GZIP:
        try:
            return gzip.decompress(corps)
        except Exception as exc:
            raise CoffreError(f"contenu illisible : {exc}") from exc
    return corps
