"""Le squelette ASCII et son miroir.

Le miroir sert quand le squelette entre par la droite : il doit regarder vers
l'interieur de l'ecran, donc du cote ou il avance.
"""

from __future__ import annotations

import unittest

from doot import art


class Squelette(unittest.TestCase):
    """L'art tel quel."""

    def test_lettres_puis_squelette(self):
        rendu = art.frame(0)
        self.assertIn(art.SKULL.split("\n")[0], rendu)

    def test_index_borne(self):
        self.assertEqual(art.frame(-5), art.frame(0))
        self.assertEqual(art.frame(999), art.frame(len(art.DOOT_FRAMES) - 1))

    def test_les_lettres_apparaissent_progressivement(self):
        vides = art.frame(0).split("\n")[0].strip()
        pleines = art.frame(len(art.DOOT_FRAMES) - 1).split("\n")[0].strip()
        self.assertEqual(vides, "")
        self.assertIn("d", pleines)
        self.assertIn("t", pleines)

    def test_taille_annoncee(self):
        colonnes, lignes = art.size()
        rendu = art.widest_frame().split("\n")
        self.assertEqual(lignes, len(rendu))
        self.assertEqual(colonnes, max(len(ligne) for ligne in rendu))


class Miroir(unittest.TestCase):
    """Le retournement horizontal."""

    def dernier(self):
        return len(art.DOOT_FRAMES) - 1

    def test_meme_nombre_de_lignes(self):
        normal = art.frame(self.dernier()).split("\n")
        retourne = art.frame(self.dernier(), mirrored=True).split("\n")
        self.assertEqual(len(normal), len(retourne))

    def test_les_obliques_basculent(self):
        """Un / devient \\ et reciproquement, sinon le dessin se contredit."""
        normal = art.frame(0)
        retourne = art.frame(0, mirrored=True)
        self.assertEqual(normal.count("/"), retourne.count("\\"))
        self.assertEqual(normal.count("\\"), retourne.count("/"))

    def test_les_parentheses_basculent(self):
        normal = art.frame(0)
        retourne = art.frame(0, mirrored=True)
        self.assertEqual(normal.count("("), retourne.count(")"))
        self.assertEqual(normal.count(")"), retourne.count("("))

    def test_double_miroir_revient_au_depart(self):
        """En ignorant le remplissage a droite, retourner deux fois est neutre."""
        largeur = max(art._largeur(art.SKULL), len(art.DOOT_FRAMES[0]))
        une_fois = art._mirror_bloc(art.SKULL, largeur)
        deux_fois = art._mirror_bloc(une_fois, largeur)
        attendu = "\n".join(
            ligne.ljust(largeur) for ligne in art.SKULL.split("\n")
        )
        self.assertEqual(deux_fois, attendu)

    def test_les_lettres_restent_lisibles(self):
        """Renverser betement donnerait « ! t o o d »."""
        ligne = art.frame(self.dernier(), mirrored=True).split("\n")[0]
        lettres = [c for c in ligne if not c.isspace()]
        self.assertEqual(lettres, ["d", "o", "o", "t", "!"])

    def test_les_lettres_changent_de_cote(self):
        """Elles doivent voler du cote oppose une fois l'image retournee."""
        normal = art.frame(self.dernier()).split("\n")[0]
        retourne = art.frame(self.dernier(), mirrored=True).split("\n")[0]

        milieu_normal = normal.index("d")
        milieu_retourne = retourne.rindex("d")
        self.assertGreater(milieu_normal, len(normal) / 2,
                           "les lettres partent a droite dans le sens normal")
        self.assertLess(milieu_retourne, len(retourne) / 2,
                        "et a gauche une fois retournees")

    def test_chaque_colonne_se_retrouve_en_face(self):
        """Propriete exacte : la colonne j du miroir est la colonne largeur-1-j.

        Mesurer un simple « poids a gauche » serait approximatif : la colonne
        centrale se retrouve du meme cote dans les deux sens et fausse le compte.
        """
        largeur = art._largeur(art.SKULL)
        lignes = art.SKULL.split("\n")
        retourne = art._mirror_bloc(art.SKULL, largeur).split("\n")

        def occupees(bloc, colonne):
            return sum(
                1 for ligne in bloc
                if colonne < len(ligne) and not ligne[colonne].isspace()
            )

        for colonne in range(largeur):
            self.assertEqual(
                occupees(retourne, colonne),
                occupees(lignes, largeur - 1 - colonne),
                f"colonne {colonne}",
            )

    def test_le_squelette_change_bien_de_sens(self):
        """Le dessin n'est pas symetrique : le miroir doit donc le modifier."""
        largeur = art._largeur(art.SKULL)
        rembourre = "\n".join(ligne.ljust(largeur) for ligne in art.SKULL.split("\n"))
        self.assertNotEqual(art._mirror_bloc(art.SKULL, largeur), rembourre)


if __name__ == "__main__":
    unittest.main()
