"""La boucle d'animation partagee par les overlays.

Ce qui compte ici est la frontiere : avant que quoi que ce soit soit affiche,
une erreur doit remonter pour que l'appelant se replie sur un autre backend ;
apres, elle doit etre absorbee. Dans les deux cas la surface est fermee.
"""

from __future__ import annotations

import unittest

from doot import overlay, png


class FausseSurface:
    def __init__(self, casse_a=None):
        self.casse_a = casse_a
        self.mappee = False
        self.fermee = False
        self.dessins = 0

    def map(self):
        if self.casse_a == "map":
            raise OSError("surface impossible")
        self.mappee = True

    def draw(self, _pixels):
        self.dessins += 1
        if self.casse_a == "draw":
            raise OSError("tampon perdu")

    def move(self, x, y):
        pass

    def close(self):
        self.fermee = True


def _frame():
    return png.Frame(2, 2, b"\xff\x00\xff\xff" * 4)


class Frontiere(unittest.TestCase):

    def test_un_echec_avant_affichage_remonte(self):
        surface = FausseSurface(casse_a="map")
        with self.assertRaises(OSError):
            overlay.run(surface, _frame(), 0, 0, 0.1)
        self.assertTrue(surface.fermee, "la surface doit etre fermee malgre l'erreur")

    def test_un_echec_apres_affichage_est_absorbe(self):
        surface = FausseSurface(casse_a="draw")
        overlay.run(surface, _frame(), 0, 0, 0.1)
        self.assertTrue(surface.mappee)
        self.assertTrue(surface.fermee)

    def test_le_cas_nominal_dessine_et_ferme(self):
        surface = FausseSurface()
        overlay.run(surface, _frame(), 0, 0, 0.5)
        self.assertGreater(surface.dessins, 1)
        self.assertTrue(surface.fermee)


if __name__ == "__main__":
    unittest.main()
