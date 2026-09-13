"""Conformite du decodeur PNG maison, confronte a Pillow.

`doot/png.py` decode les images pour l'overlay ARGB de X11, la ou tkinter ne
nous donne pas les octets. Un decodeur ecrit a la main merite un garde-fou :
chaque variante de PNG est comparee octet a octet a ce que produit Pillow.

Le module est ignore tant que `doot/png.py` n'existe pas (il arrive avec
l'overlay X11), et tant que Pillow n'est pas installe.
"""

from __future__ import annotations

import unittest
from pathlib import Path

try:
    from doot import png
except ImportError:  # pragma: no cover - avant l'arrivee de l'overlay X11
    png = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow absent en local
    Image = None

ASSET = Path(__file__).resolve().parent.parent / "doot" / "assets" / "doot.png"


def premultiplied_bgra(image) -> bytes:
    """La reference : BGRA premultiplie, un pixel transparent valant 4 zeros."""
    image = image.convert("RGBA")
    out = bytearray(image.width * image.height * 4)
    for index, (r, g, b, a) in enumerate(image.getdata()):
        if a == 0:
            continue
        if a != 255:
            r = (r * a + 127) // 255
            g = (g * a + 127) // 255
            b = (b * a + 127) // 255
        d = index * 4
        out[d] = b
        out[d + 1] = g
        out[d + 2] = r
        out[d + 3] = a
    return bytes(out)


@unittest.skipIf(png is None, "doot/png.py absent (arrive avec l'overlay X11)")
@unittest.skipIf(Image is None, "Pillow absent")
class DecodeurPng(unittest.TestCase):
    """Chaque variante doit sortir exactement ce que Pillow sort."""

    @classmethod
    def setUpClass(cls):
        import tempfile

        cls._dir = tempfile.TemporaryDirectory()
        cls.root = Path(cls._dir.name)

        source = Image.new("RGBA", (16, 12))
        for y in range(12):
            for x in range(16):
                source.putpixel(
                    (x, y),
                    (x * 16, y * 20, 255 - x * 8, 0 if x < 3 else min(255, x * 20)),
                )
        cls.source = source

    @classmethod
    def tearDownClass(cls):
        cls._dir.cleanup()

    def compare(self, path: Path):
        frame = png.frame(path, 1.0)
        want = premultiplied_bgra(Image.open(path))
        self.assertEqual(len(frame.data), len(want), "taille du tampon")

        wrong = sum(
            1 for i in range(0, len(want), 4)
            if frame.data[i:i + 4] != want[i:i + 4]
        )
        self.assertEqual(wrong, 0, f"{wrong} pixels sur {len(want) // 4} different de Pillow")

    def save(self, name: str, image, **options) -> Path:
        path = self.root / name
        image.save(path, **options)
        return path

    def test_rgba_8_bits(self):
        self.compare(self.save("rgba8.png", self.source))

    def test_rgb_8_bits(self):
        self.compare(self.save("rgb8.png", self.source.convert("RGB")))

    def test_gris_8_bits(self):
        self.compare(self.save("gray8.png", self.source.convert("L")))

    def test_gris_alpha_8_bits(self):
        self.compare(self.save("la8.png", self.source.convert("LA")))

    def test_palette_8_bits(self):
        palette = self.source.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=64)
        self.compare(self.save("pal8.png", palette))

    def test_palette_8_bits_avec_trns(self):
        palette = self.source.convert("P", palette=Image.ADAPTIVE, colors=64)
        self.compare(self.save("pal8_trns.png", palette, transparency=0))

    def test_palette_4_bits(self):
        palette = self.source.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=16)
        self.compare(self.save("pal4.png", palette, bits=4))

    def test_palette_2_bits(self):
        palette = self.source.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=4)
        self.compare(self.save("pal2.png", palette, bits=2))

    def test_palette_1_bit(self):
        palette = self.source.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=2)
        self.compare(self.save("pal1.png", palette, bits=1))

    @unittest.skipUnless(ASSET.is_file(), "doot/assets/doot.png absent")
    def test_asset_livre(self):
        """Celle qui compte vraiment : l'image affichee par defaut."""
        self.compare(ASSET)

    @unittest.skipUnless(ASSET.is_file(), "doot/assets/doot.png absent")
    def test_mise_a_l_echelle(self):
        """Reduire ne doit ni changer la taille attendue ni desaturer l'alpha."""
        full = png.frame(ASSET, 1.0)
        half = png.frame(ASSET, 0.5)

        self.assertEqual(len(half.data), half.width * half.height * 4)
        self.assertLess(half.width, full.width)
        self.assertGreater(half.width, 0)

        # alpha premultiplie : aucun canal ne peut depasser l'alpha du pixel
        faulty = sum(
            1 for i in range(0, len(half.data), 4)
            if max(half.data[i], half.data[i + 1], half.data[i + 2]) > half.data[i + 3]
        )
        self.assertEqual(faulty, 0, f"{faulty} pixels mal premultiplies apres reduction")

    @unittest.skipUnless(ASSET.is_file(), "doot/assets/doot.png absent")
    def test_fondu(self):
        """`faded()` attenue, garde la taille, et 0 donne un tampon vide."""
        frame = png.frame(ASSET, 1.0)
        self.assertEqual(frame.faded(1.0), frame.data)
        self.assertEqual(len(frame.faded(0.5)), len(frame.data))
        self.assertEqual(frame.faded(0.0), bytes(len(frame.data)))
        self.assertLess(sum(frame.faded(0.5)), sum(frame.data))

    def test_fichier_invalide(self):
        """Une image illisible leve PngError, pour que l'appelant reprenne tkinter."""
        bad = self.root / "pasunpng.png"
        bad.write_bytes(b"ceci n'est pas une image")
        with self.assertRaises(png.PngError):
            png.frame(bad, 1.0)


@unittest.skipIf(png is None, "doot/png.py absent")
class Hochement(unittest.TestCase):
    """`bob_frames` : trois etapes sur une toile commune, pivot immobile.

    L'image d'essai est un damier de couleurs uniques par pixel : on peut
    ainsi dire de quel pixel d'origine vient chaque pixel de la toile.
    """

    def setUp(self):
        self.width, self.height = 20, 30
        pixels = bytearray()
        for y in range(self.height):
            for x in range(self.width):
                pixels += bytes((x + 1, y + 1, 7, 255))
        self.frame = png.Frame(self.width, self.height, bytes(pixels))
        self.bobs = png.bob_frames(self.frame)

    def origine(self, frame, x, y):
        p = (y * frame.width + x) * 4
        return frame.data[p] - 1, frame.data[p + 1] - 1, frame.data[p + 3]

    def test_trois_etapes_de_meme_taille(self):
        self.assertEqual(len(self.bobs), 3)
        tailles = {(b.width, b.height) for b in self.bobs}
        self.assertEqual(len(tailles), 1)
        largeur, hauteur = tailles.pop()
        self.assertGreater(largeur, self.width)
        self.assertGreater(hauteur, self.height)

    def test_l_etape_droite_est_l_image_posee_sur_la_toile(self):
        droite = self.bobs[0]
        trouves = [(x, y) for y in range(droite.height) for x in range(droite.width)
                   if self.origine(droite, x, y)[2]]
        self.assertEqual(len(trouves), self.width * self.height)
        gauche, haut = min(trouves)
        for y in range(self.height):
            for x in range(self.width):
                self.assertEqual(self.origine(droite, gauche + x, haut + y)[:2], (x, y))

    def test_le_pivot_ne_bouge_pas(self):
        """Le poing sur la trompette reste au meme endroit a chaque etape."""
        pivot = (round(self.width * png.BOB_PIVOT[0]), round(self.height * png.BOB_PIVOT[1]))
        droite = self.bobs[0]
        ou = next((x, y) for y in range(droite.height) for x in range(droite.width)
                  if self.origine(droite, x, y)[2] and self.origine(droite, x, y)[:2] == pivot)
        for etape in self.bobs[1:]:
            self.assertEqual(self.origine(etape, *ou)[:2], pivot)

    def test_penchee_a_gauche_et_un_peu_plus_grande(self):
        droite, penchee = self.bobs[0], self.bobs[2]
        aire = lambda f: sum(f.data[3::4]) // 255
        self.assertGreater(aire(penchee), aire(droite) * 1.08)
        # Le haut de l'image part vers la gauche : le coin superieur droit de
        # l'image droite est, une fois penche, plus a gauche qu'avant.
        def colonne_du_coin(frame):
            return max(x for y in range(frame.height) for x in range(frame.width)
                       if self.origine(frame, x, y)[2]
                       and self.origine(frame, x, y)[:2] == (self.width - 1, 0))
        self.assertLess(colonne_du_coin(penchee), colonne_du_coin(droite))


if __name__ == "__main__":
    unittest.main()
