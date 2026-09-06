"""Choix du bord d'entree et orientation qui en decoule.

Rien ici n'ouvre de fenetre : seules la selection du bord et la table des
rotations sont verifiees, ce qui tourne sur un serveur sans affichage.
"""

from __future__ import annotations

import random
import unittest

from doot import window


class ChoixDuBord(unittest.TestCase):
    """`--side` et son tirage au sort."""

    def test_bords_explicites(self):
        for demande in ("left", "right", "top", "bottom"):
            self.assertEqual(window.pick_side(demande), demande)

    def test_noms_francais_acceptes(self):
        self.assertEqual(window.pick_side("gauche"), "left")
        self.assertEqual(window.pick_side("droite"), "right")
        self.assertEqual(window.pick_side("haut"), "top")
        self.assertEqual(window.pick_side("bas"), "bottom")

    def test_valeur_absente_ou_incomprise_tire_au_sort(self):
        for demande in (None, "random", "n'importe quoi"):
            self.assertIn(window.pick_side(demande), window.COTES)

    def test_les_quatre_bords_sortent(self):
        rng = random.Random(4321)
        vus = {window.pick_side(None, rng) for _ in range(400)}
        self.assertEqual(vus, set(window.COTES))


class Orientation(unittest.TestCase):
    """La rotation qui pose le bas de l'image contre le bord d'entree."""

    def test_table_complete(self):
        self.assertEqual(set(window.TOURS), set(window.COTES))

    def test_sens_de_rotation(self):
        """Un quart de tour horaire amene le bas a gauche, trois a droite."""
        self.assertEqual(window.TOURS["left"], 1)
        self.assertEqual(window.TOURS["right"], 3)
        self.assertEqual(window.TOURS["top"], 2)
        self.assertEqual(window.TOURS["bottom"], 0)

    def test_gauche_et_droite_sont_opposees(self):
        self.assertEqual((window.TOURS["left"] + window.TOURS["right"]) % 4, 0)

    def test_entrer_par_le_bas_ne_pivote_rien(self):
        """L'image est deja debout : son bas est deja en bas."""
        self.assertEqual(window.TOURS["bottom"] % 4, 0)

    def test_un_quart_echange_les_cotes(self):
        """Utilise pour ajuster l'echelle : la fenetre change de proportions."""
        for cote in ("left", "right"):
            self.assertEqual(window.TOURS[cote] % 2, 1)
        for cote in ("top", "bottom"):
            self.assertEqual(window.TOURS[cote] % 2, 0)


if __name__ == "__main__":
    unittest.main()
