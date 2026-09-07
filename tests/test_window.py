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


class MelangeDesDeuxModes(unittest.TestCase):
    """Entrer par un bord ou surgir sur place, tire au sort a chaque doot."""

    def part_glissee(self, chance, tirages=4000, side=None, slide=True):
        rng = random.Random(1234)
        return sum(
            1 for _ in range(tirages)
            if window.decide_slide(slide, side, chance, rng)
        ) / tirages

    def test_les_deux_modes_coexistent(self):
        """Ni tout par les bords, ni tout sur place."""
        part = self.part_glissee(0.5)
        self.assertGreater(part, 0.4)
        self.assertLess(part, 0.6)

    def test_la_proportion_est_respectee(self):
        for chance in (0.2, 0.5, 0.8):
            self.assertAlmostEqual(self.part_glissee(chance), chance, delta=0.05)

    def test_zero_reste_toujours_sur_place(self):
        self.assertEqual(self.part_glissee(0.0), 0.0)

    def test_un_entre_toujours_par_un_bord(self):
        self.assertEqual(self.part_glissee(1.0), 1.0)

    def test_valeurs_aberrantes_bornees(self):
        self.assertEqual(self.part_glissee(-3.0), 0.0)
        self.assertEqual(self.part_glissee(12.0), 1.0)

    def test_no_slide_coupe_tout(self):
        self.assertEqual(self.part_glissee(1.0, slide=False), 0.0)

    def test_un_bord_demande_impose_le_glissement(self):
        """Sans quoi --side left n'aurait d'effet qu'une fois sur deux."""
        self.assertEqual(self.part_glissee(0.01, side="left"), 1.0)

    def test_un_bord_demande_ne_force_rien_si_no_slide(self):
        self.assertEqual(self.part_glissee(1.0, side="left", slide=False), 0.0)


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


class TourComplet(unittest.TestCase):
    """La rotation complete : le squelette tourne sur lui-meme, sur place."""

    def part_tournee(self, chance, tirages=4000, spin=True, glisse=False):
        rng = random.Random(1234)
        return sum(
            1 for _ in range(tirages)
            if window.decide_spin(spin, chance, glisse, rng)
        ) / tirages

    def test_la_proportion_est_respectee(self):
        for chance in (0.2, 0.25, 0.8):
            self.assertAlmostEqual(self.part_tournee(chance), chance, delta=0.05)

    def test_zero_ne_fait_jamais_tourner(self):
        self.assertEqual(self.part_tournee(0.0), 0.0)

    def test_un_fait_toujours_tourner(self):
        self.assertEqual(self.part_tournee(1.0), 1.0)

    def test_valeurs_aberrantes_bornees(self):
        self.assertEqual(self.part_tournee(-3.0), 0.0)
        self.assertEqual(self.part_tournee(12.0), 1.0)

    def test_no_spin_coupe_tout(self):
        self.assertEqual(self.part_tournee(1.0, spin=False), 0.0)

    def test_jamais_pendant_une_entree_par_un_bord(self):
        """L'image y est deja pivotee pour poser les pieds contre le bord."""
        self.assertEqual(self.part_tournee(1.0, glisse=True), 0.0)


if __name__ == "__main__":
    unittest.main()
