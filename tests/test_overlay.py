"""La boucle d'animation partagee par les overlays.

Ce qui compte ici est la frontiere : avant que quoi que ce soit soit affiche,
une erreur doit remonter pour que l'appelant se replie sur un autre backend ;
apres, elle doit etre absorbee. Dans les deux cas la surface est fermee.
"""

from __future__ import annotations

import itertools
import unittest

from doot import overlay, png


class FausseSurface:
    def __init__(self, casse_a=None):
        self.casse_a = casse_a
        self.mappee = False
        self.fermee = False
        self.dessins = 0
        self.pixels = []

    def map(self):
        if self.casse_a == "map":
            raise OSError("surface impossible")
        self.mappee = True

    def draw(self, pixels):
        self.dessins += 1
        self.pixels.append(bytes(pixels))
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


class TourComplet(unittest.TestCase):
    """Les quatre etapes defilent, puis l'image reste droite.

    Chaque etape ne porte qu'un seul octet non nul par pixel, a un rang qui lui
    est propre : le fondu attenue les valeurs mais ne deplace pas ce rang, une
    image dessinee reste donc reconnaissable a n'importe quelle opacite.
    """

    def etapes(self):
        return [png.Frame(2, 2, bytes(
            120 if octet == quarts else 0 for _ in range(4) for octet in range(4)
        )) for quarts in range(4)]

    def dessine(self, **kwargs):
        surface = FausseSurface()
        etapes = self.etapes()
        # Un tour large devant le pas de 40 ms de la boucle : meme une machine
        # qui bafouille garde plusieurs dessins par quart.
        overlay.run(surface, etapes[0], 0, 0, 1.2, spins=etapes, spin_ms=800,
                    **kwargs)
        vus = []
        for pixels in surface.pixels:
            rangs = {i % 4 for i, octet in enumerate(pixels) if octet}
            if len(rangs) == 1:  # une image entierement effacee ne dit rien
                vus.append(rangs.pop())
        return vus

    def test_les_quatre_etapes_sont_dessinees(self):
        self.assertEqual(set(self.dessine()), {0, 1, 2, 3})

    def test_les_etapes_se_suivent_dans_l_ordre(self):
        """Le squelette tourne dans un sens, il ne clignote pas entre deux."""
        enchainement = [quarts for quarts, _ in itertools.groupby(self.dessine())]
        self.assertEqual(enchainement, [0, 1, 2, 3, 0])

    def test_le_doot_finit_droit(self):
        """La position de repos a ete calculee sur l'image droite."""
        self.assertEqual(self.dessine()[-1], 0)

    def test_sans_spins_rien_ne_tourne(self):
        surface = FausseSurface()
        overlay.run(surface, _frame(), 0, 0, 0.5, spin_ms=400)
        self.assertTrue(surface.pixels)
        self.assertTrue(all(len(pixels) == 16 for pixels in surface.pixels))


if __name__ == "__main__":
    unittest.main()
