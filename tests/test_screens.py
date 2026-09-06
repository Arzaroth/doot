"""Placement multi-ecrans.

L'enumeration reelle depend de la machine (Win32, xrandr, CoreGraphics) et ne
peut pas etre reproduite en CI. Ce qui est verifie ici, c'est le contrat que
`window.py` utilise : on obtient toujours au moins un ecran, et une fenetre
posee sur un ecran tombe entierement dedans.
"""

from __future__ import annotations

import random
import unittest

from doot import screens


class Enumeration(unittest.TestCase):
    """`monitors()` ne doit jamais laisser l'appelant sans ecran."""

    def test_jamais_vide(self):
        found = screens.monitors()
        self.assertGreaterEqual(len(found), 1)

    def test_dimensions_positives(self):
        for monitor in screens.monitors():
            self.assertGreater(monitor.width, 0, monitor)
            self.assertGreater(monitor.height, 0, monitor)

    def test_repli_sur_les_dimensions_fournies(self):
        """Sur une machine sans serveur graphique, on retombe sur le repli."""
        found = screens.monitors(1280, 800)
        self.assertGreaterEqual(len(found), 1)

    def test_description_lisible(self):
        text = screens.describe(screens.monitors())
        self.assertIn("ecran", text)


class Selection(unittest.TestCase):
    """La semantique de --screen."""

    def setUp(self):
        self.mons = [
            screens.Monitor(0, 0, 1920, 1040, primary=True, name="gauche"),
            screens.Monitor(1920, 0, 2560, 1400, primary=False, name="droite"),
            screens.Monitor(-1080, -200, 1080, 1920, primary=False, name="portrait"),
        ]

    def test_index_explicite(self):
        for index, monitor in enumerate(self.mons):
            self.assertIs(screens.pick(self.mons, index), monitor)

    def test_index_en_texte(self):
        self.assertIs(screens.pick(self.mons, "1"), self.mons[1])

    def test_principal(self):
        self.assertIs(screens.pick(self.mons, "primary"), self.mons[0])

    def test_index_hors_bornes_est_borne(self):
        """Un index farfelu doit borner, pas planter."""
        self.assertIs(screens.pick(self.mons, 99), self.mons[-1])
        self.assertIs(screens.pick(self.mons, -5), self.mons[0])

    def test_valeur_incomprehensible_tire_au_hasard(self):
        self.assertIn(screens.pick(self.mons, "n'importe quoi"), self.mons)

    def test_hasard_touche_tous_les_ecrans(self):
        seen = {screens.pick(self.mons, None).name for _ in range(400)}
        self.assertEqual(seen, {"gauche", "droite", "portrait"})

    def test_liste_vide_ne_plante_pas(self):
        self.assertIsNotNone(screens.pick([], None))


class Placement(unittest.TestCase):
    """Une fenetre ne doit jamais deborder de l'ecran choisi."""

    def setUp(self):
        self.mons = [
            screens.Monitor(0, 0, 1920, 1040, primary=True, name="gauche"),
            screens.Monitor(1920, 0, 2560, 1400, primary=False, name="droite"),
            screens.Monitor(-1080, -200, 1080, 1920, primary=False, name="portrait"),
        ]

    def assert_inside(self, monitor, x, y, w, h):
        self.assertGreaterEqual(x, monitor.x, monitor)
        self.assertGreaterEqual(y, monitor.y, monitor)
        self.assertLessEqual(x + w, monitor.x + monitor.width, monitor)
        self.assertLessEqual(y + h, monitor.y + monitor.height, monitor)

    def test_aleatoire_reste_dans_l_ecran(self):
        rng = random.Random(1234)
        for monitor in self.mons:
            for _ in range(300):
                x, y = monitor.place(353, 385, center=False, rng=rng)
                self.assert_inside(monitor, x, y, 353, 385)

    def test_centre_reste_dans_l_ecran(self):
        for monitor in self.mons:
            x, y = monitor.place(353, 385, center=True, rng=random)
            self.assert_inside(monitor, x, y, 353, 385)

    def test_centre_est_bien_centre(self):
        monitor = self.mons[0]
        x, y = monitor.place(400, 200, center=True, rng=random)
        self.assertEqual(x, (1920 - 400) // 2)
        self.assertEqual(y, (1040 - 200) // 2)

    def test_ecran_a_coordonnees_negatives(self):
        """Un ecran a gauche du principal a un x negatif : ca doit suivre."""
        monitor = self.mons[2]
        x, y = monitor.place(200, 200, center=True, rng=random)
        self.assertLess(x, 0)
        self.assert_inside(monitor, x, y, 200, 200)

    def test_fenetre_plus_grande_que_l_ecran(self):
        """Cas degenere : on ne plante pas, on colle au coin de l'ecran."""
        monitor = self.mons[0]
        x, y = monitor.place(4000, 4000, center=False, rng=random)
        self.assertEqual((x, y), (monitor.x, monitor.y))


class Panoramique(unittest.TestCase):
    """Le son suit la position du squelette sur le bureau entier."""

    def setUp(self):
        # deux dalles cote a cote : le bureau va de 0 a 3840
        self.deux = [
            screens.Monitor(0, 0, 1920, 1040, primary=True, name="gauche"),
            screens.Monitor(1920, 0, 1920, 1040, primary=False, name="droite"),
        ]
        self.seul = [screens.Monitor(0, 0, 1920, 1080, primary=True, name="seul")]

    def test_bornes_du_bureau_virtuel(self):
        self.assertEqual(screens.virtual_bounds(self.deux), (0, 3840))
        self.assertEqual(screens.virtual_bounds(self.seul), (0, 1920))

    def test_bornes_avec_ecran_a_gauche(self):
        gauche = [
            screens.Monitor(-1920, 0, 1920, 1080, name="a gauche"),
            screens.Monitor(0, 0, 1920, 1080, primary=True, name="principal"),
        ]
        self.assertEqual(screens.virtual_bounds(gauche), (-1920, 1920))

    def test_extremites_et_centre(self):
        self.assertAlmostEqual(screens.pan_for(0, self.deux), -1.0)
        self.assertAlmostEqual(screens.pan_for(3840, self.deux), 1.0)
        self.assertAlmostEqual(screens.pan_for(1920, self.deux), 0.0)

    def test_un_seul_ecran_utilise_toute_sa_largeur(self):
        self.assertAlmostEqual(screens.pan_for(0, self.seul), -1.0)
        self.assertAlmostEqual(screens.pan_for(960, self.seul), 0.0)
        self.assertAlmostEqual(screens.pan_for(1920, self.seul), 1.0)

    def test_le_bord_droit_de_l_ecran_droit_sonne_a_droite(self):
        """Le vrai interet du calcul sur le bureau entier."""
        bord = screens.pan_for(3800, self.deux)
        self.assertGreater(bord, 0.9, "un doot colle a droite doit sonner a droite")

    def test_centre_de_l_ecran_droit(self):
        """Centre de la dalle de droite = trois quarts du bureau = +0.5."""
        self.assertAlmostEqual(screens.pan_for(2880, self.deux), 0.5)

    def test_toujours_borne(self):
        for x in (-10_000, -1, 3841, 99_999):
            valeur = screens.pan_for(x, self.deux)
            self.assertGreaterEqual(valeur, -1.0)
            self.assertLessEqual(valeur, 1.0)

    def test_progression_monotone(self):
        precedent = -2.0
        for x in range(0, 3841, 120):
            valeur = screens.pan_for(x, self.deux)
            self.assertGreaterEqual(valeur, precedent)
            precedent = valeur

    def test_liste_vide_reste_au_centre(self):
        self.assertEqual(screens.pan_for(500, []), 0.0)


if __name__ == "__main__":
    unittest.main()
