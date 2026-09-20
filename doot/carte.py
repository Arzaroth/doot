"""La carte de fin de saison : ce que la crypte a donne, en une image.

Une saison qui ferme sans rien laisser derriere elle ferme pour rien. La carte
range les chiffres du registre, la grille des soirs et les medailles gagnees
dans un PNG que doot ecrit lui-meme, sans fonte installee ni bibliotheque
d'images : la toile de ``png`` pour le fond, la fonte matricielle de ``police``
pour le texte, et les badges deja livres avec les succes.

Le module ne lit aucun fichier d'etat et n'en ecrit pas : il recoit l'etat,
rend un ``Frame``, et laisse l'appelant decider ou il atterrit.
"""

from __future__ import annotations

from pathlib import Path

from . import png, police, registre, succes


LARGEUR = 760
MARGE = 28

FOND = (14, 11, 20, 255)
CADRE = (215, 168, 74, 255)
OR = (215, 168, 74, 255)
OR_CLAIR = (243, 212, 134, 255)
OS = (242, 231, 207, 255)
SOURDINE = (122, 110, 134, 255)
CASE_VIDE = (38, 27, 50, 255)
BRAISE = (231, 111, 54, 255)

CASE = 12
ECART = 3
BADGE = 64
BADGES_PAR_RANG = 9

# Une valeur s'ecrit en corps 3, soit vingt-et-un points de haut. L'interligne
# doit lui laisser sa place, sinon deux chiffres se marchent dessus.
INTERLIGNE = 30
COLONNE_VALEUR = 230


def _lignes(bilan, saison) -> list:
    """Les chiffres retenus pour la carte, libelles compris.

    Moins que le registre entier : une carte qui dit tout ne dit rien, et les
    totaux a zero d'une saison calme feraient du remplissage.
    """
    lignes = [
        ("DOOTS", f"{bilan.doots}"),
        ("SOIRS", f"{len(saison.actifs)} / {saison.duree}"),
        ("MELODIES", f"{bilan.melodies}"),
        ("RENCONTRES", f"{bilan.evenements}"),
        ("SALVE MAX", f"{bilan.plus_grande_salve}"),
        ("CODEX", f"{bilan.codex} / {bilan.codex_total}"),
    ]
    return [(libelle, valeur) for libelle, valeur in lignes if valeur.split()[0] != "0"]


def _badges(etat: dict) -> list:
    """Les illustrations des succes gagnes, dans l'ordre du catalogue."""
    acquis = succes.debloques(etat)
    chemins = []
    for definition in succes.CATALOGUE:
        if definition.identifiant not in acquis:
            continue
        chemin = succes.badge(definition)
        if chemin is not None:
            chemins.append(chemin)
    return chemins


def _grille(toile, saison, x: int, y: int) -> int:
    """La saison en cases. Renvoie la hauteur occupee."""
    for index, colonne in enumerate(saison.semaines):
        for rang, jour in enumerate(colonne):
            if jour is None:
                continue
            toile.rectangle(
                x + index * (CASE + ECART), y + rang * (CASE + ECART),
                CASE, CASE, OR if jour in saison.actifs else CASE_VIDE,
            )
    return registre.SEMAINE * (CASE + ECART) - ECART


def dessiner(etat: dict, annee: int) -> png.Frame:
    """La carte de la saison `annee`, prete a etre ecrite."""

    bilan = registre.resume(etat)
    saison = registre.saison(etat, annee)
    lignes = _lignes(bilan, saison)
    badges = _badges(etat)

    hauteur_grille = registre.SEMAINE * (CASE + ECART) - ECART
    rangs = (len(badges) + BADGES_PAR_RANG - 1) // BADGES_PAR_RANG
    hauteur = (
        MARGE + 40                                  # titre
        + 26                                        # sous-titre
        + 24 + max(hauteur_grille, len(lignes) * INTERLIGNE)
        + (28 + rangs * (BADGE + 8) if badges else 0)
        + 34                                        # pied
        + MARGE
    )
    toile = png.Toile(LARGEUR, hauteur, FOND)

    toile.rectangle(0, 0, LARGEUR, 3, CADRE)
    toile.rectangle(0, hauteur - 3, LARGEUR, 3, CADRE)
    toile.rectangle(0, 0, 3, hauteur, CADRE)
    toile.rectangle(LARGEUR - 3, 0, 3, hauteur, CADRE)

    y = MARGE
    police.centrer(toile, f"DOOT - SAISON {annee}", y, OR_CLAIR, 5)
    y += police.hauteur(5) + 12
    police.centrer(toile, "1ER SEPTEMBRE - 31 OCTOBRE", y, SOURDINE, 2)
    y += police.hauteur(2) + 22

    colonne_texte = MARGE + 14
    ligne_y = y
    for libelle, valeur in lignes:
        # Le libelle est en corps 2 et la valeur en corps 3 : le decalage pose
        # les deux sur la meme ligne de base plutot que sur le meme haut.
        police.ecrire(toile, libelle, colonne_texte, ligne_y + 4, SOURDINE, 2)
        police.ecrire(toile, valeur, colonne_texte + COLONNE_VALEUR, ligne_y, OS, 3)
        ligne_y += INTERLIGNE

    grille_x = LARGEUR - MARGE - 14 - (
        max(1, len(saison.semaines)) * (CASE + ECART) - ECART
    )
    _grille(toile, saison, grille_x, y)
    y += max(hauteur_grille, len(lignes) * INTERLIGNE) + 18

    if badges:
        for index, chemin in enumerate(badges):
            rang, colonne = divmod(index, BADGES_PAR_RANG)
            # Chaque rang est centre pour lui-meme : un dernier rang incomplet
            # colle a gauche pendrait sous une rangee pleine et centree.
            dans_le_rang = min(len(badges) - rang * BADGES_PAR_RANG, BADGES_PAR_RANG)
            depart = (LARGEUR - (dans_le_rang * (BADGE + 8) - 8)) // 2
            try:
                vignette = png.frame(chemin, BADGE / png.size(chemin)[0])
            except png.PngError:
                continue
            toile.coller(vignette, depart + colonne * (BADGE + 8),
                         y + rang * (BADGE + 8))
        y += rangs * (BADGE + 8) + 6

    pied = (f"{bilan.succes} / {bilan.succes_total} SUCCES - "
            f"{bilan.points} POINTS")
    police.centrer(toile, pied, y, BRAISE, 3)
    return toile.frame()


def ecrire(destination, etat: dict, annee: int) -> Path:
    """Ecrit la carte et renvoie le chemin du fichier.

    Un dossier recoit `doot-saison-<annee>.png`, un chemin complet est pris tel
    quel : la commande sert autant a deposer la carte quelque part qu'a la
    ranger ou vivent deja les donnees.
    """
    chemin = Path(destination)
    if chemin.is_dir():
        chemin = chemin / f"doot-saison-{annee}.png"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    png.write_png(chemin, dessiner(etat, annee))
    return chemin
