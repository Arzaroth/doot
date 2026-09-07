"""Le decodeur PNG confronte a des images dont on connait deja les pixels.

test_png.py compare a Pillow. Cette suite-ci ne compare a rien : elle fabrique
le PNG octet par octet a partir d'une liste de pixels connue, puis verifie que
`doot/png.py` rend ces pixels-la. Elle couvre ce que l'oracle Pillow n'atteint
pas :

  - le gris 2 et 4 bits, que Pillow ne sait pas ecrire ;
  - tRNS hors palette, et tRNS sous 8 bits, que Pillow lit sans l'appliquer (il
    ne rend aucun pixel transparent en gris 2 bits, la ou ImageMagick et
    doot/png.py en rendent 16) ;
  - le 16 bits, que Pillow ne convertit pas fidelement ;
  - les cinq filtres de ligne, que Pillow choisit par heuristique ;
  - les entrees refusees, qui doivent lever PngError pour que window.py reprenne
    le chemin tkinter plutot que d'afficher n'importe quoi.

Rien a installer, donc elle tourne aussi la ou Pillow manque.

L'encodeur ci-dessous et le decodeur teste sont ecrits chacun de leur cote a
partir de la norme. Pour qu'un filtre mal compris des deux cotes ne s'annule
pas, test_les_cinq_filtres encode la meme image avec les cinq filtres et exige
le meme resultat : une erreur symetrique devrait alors l'etre pour Paeth, la
moyenne et le report, ce qui n'arrive pas par hasard.
"""

from __future__ import annotations

import os
import struct
import unittest
import zlib
from pathlib import Path
from tempfile import TemporaryDirectory

try:
    from doot import png
except ImportError:  # pragma: no cover - avant l'arrivee de l'overlay X11
    png = None

SIGNATURE = b"\x89PNG\r\n\x1a\n"
GRIS, RVB, PALETTE, GRIS_ALPHA, RVBA = 0, 2, 3, 4, 6
CANAUX = {GRIS: 1, RVB: 3, PALETTE: 1, GRIS_ALPHA: 2, RVBA: 4}


def _bloc(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def _lignes(samples, width, height, depth, channels) -> list[bytes]:
    """Range les echantillons ligne par ligne, dans le sens des bits du format."""
    par_ligne = width * channels
    lignes = []
    for y in range(height):
        valeurs = samples[y * par_ligne:(y + 1) * par_ligne]
        if depth == 16:
            lignes.append(b"".join(struct.pack(">H", v) for v in valeurs))
        elif depth == 8:
            lignes.append(bytes(valeurs))
        else:
            par_octet = 8 // depth
            masque = (1 << depth) - 1
            ligne = bytearray((par_ligne + par_octet - 1) // par_octet)
            for i, valeur in enumerate(valeurs):
                ligne[i // par_octet] |= (valeur & masque) << (8 - depth * (i % par_octet + 1))
            lignes.append(bytes(ligne))
    return lignes


def _filtrer(kind: int, ligne: bytes, precedente: bytes, bpp: int) -> bytes:
    """Encode une ligne avec le filtre demande, formules de la norme."""
    out = bytearray(len(ligne))
    for i, valeur in enumerate(ligne):
        a = ligne[i - bpp] if i >= bpp else 0
        b = precedente[i]
        c = precedente[i - bpp] if i >= bpp else 0
        if kind == 1:
            predit = a
        elif kind == 2:
            predit = b
        elif kind == 3:
            predit = (a + b) // 2
        elif kind == 4:
            p = a + b - c
            pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
            predit = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
        else:
            predit = 0
        out[i] = (valeur - predit) & 255
    return bytes(out)


def ecrire_png(path, width, height, depth, color, samples, palette=b"", trns=None,
               filtre=0, interlace=0, hauteur_declaree=None, idat_casse=False) -> Path:
    """Fabrique un PNG a partir d'echantillons bruts.

    `hauteur_declaree` et `idat_casse` servent aux cas malformes.
    """
    channels = CANAUX[color]
    lignes = _lignes(samples, width, height, depth, channels)
    bpp = max(1, channels * depth // 8)
    brut = bytearray()
    precedente = bytes(len(lignes[0])) if lignes else b""
    for ligne in lignes:
        brut.append(filtre)
        brut += _filtrer(filtre, ligne, precedente, bpp)
        precedente = ligne

    entete = struct.pack(">IIBBBBB", width, hauteur_declaree or height, depth, color, 0, 0, interlace)
    body = SIGNATURE + _bloc(b"IHDR", entete)
    if palette:
        body += _bloc(b"PLTE", palette)
    if trns is not None:
        body += _bloc(b"tRNS", trns)
    body += _bloc(b"IDAT", b"pas du zlib" if idat_casse else zlib.compress(bytes(brut)))
    body += _bloc(b"IEND", b"")
    path = Path(path)
    path.write_bytes(body)
    return path


def _egalites_de_paeth(lignes) -> tuple[int, int]:
    """Compte les egalites que le predicteur de Paeth doit departager.

    Sert a garantir que l'image de test touche vraiment ces cas : sans ca, une
    retouche du fixture ferait perdre la couverture sans que rien ne le dise.
    """
    gauche_diagonale = dessus_diagonale = 0
    for y in range(1, len(lignes)):
        for x in range(1, len(lignes[y])):
            a, b, c = lignes[y][x - 1], lignes[y - 1][x], lignes[y - 1][x - 1]
            p = a + b - c
            pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
            if pa == pc and pa <= pb:
                gauche_diagonale += 1
            elif pb == pc and pb < pa:
                dessus_diagonale += 1
    return gauche_diagonale, dessus_diagonale


def attendu(pixels) -> bytes:
    """La reference : BGRA premultiplie, un pixel transparent valant 4 zeros."""
    out = bytearray(len(pixels) * 4)
    for index, (r, g, b, a) in enumerate(pixels):
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
class PngFabrique(unittest.TestCase):
    """Le decodeur doit rendre exactement les pixels qu'on a encodes."""

    def setUp(self):
        dossier = TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        self.root = Path(dossier.name)

    def verifie(self, path, width, height, pixels):
        frame = png.frame(path, 1.0)
        self.assertEqual((frame.width, frame.height), (width, height), "dimensions")
        vise = attendu(pixels)
        faux = sum(1 for i in range(0, len(vise), 4) if frame.data[i:i + 4] != vise[i:i + 4])
        self.assertEqual(faux, 0, f"{faux} pixels sur {len(pixels)} ne sont pas ceux encodes")

    # ------------------------------------------------------------- gris ------

    def test_gris_sous_8_bits(self):
        """1, 2 et 4 bits : les niveaux sont etires sur 0-255."""
        for depth in (1, 2, 4):
            with self.subTest(profondeur=depth):
                maxi = (1 << depth) - 1
                etire = 255 // maxi
                valeurs = [(x + y) % (maxi + 1) for y in range(4) for x in range(4)]
                pixels = [(v * etire,) * 3 + (255,) for v in valeurs]
                path = ecrire_png(self.root / f"gris{depth}.png", 4, 4, depth, GRIS, valeurs)
                self.verifie(path, 4, 4, pixels)

    def test_gris_sous_8_bits_avec_trns(self):
        """tRNS stocke sa cle sur 16 bits : elle doit etre etiree comme les
        echantillons, sans quoi elle ne vaut plus rien sous 8 bits."""
        for depth in (2, 4):
            with self.subTest(profondeur=depth):
                maxi = (1 << depth) - 1
                etire = 255 // maxi
                valeurs = [(x + y) % (maxi + 1) for y in range(4) for x in range(4)]
                pixels = [
                    (0, 0, 0, 0) if v == 1 else (v * etire,) * 3 + (255,)
                    for v in valeurs
                ]
                path = ecrire_png(self.root / f"gris{depth}t.png", 4, 4, depth, GRIS,
                                  valeurs, trns=struct.pack(">H", 1))
                self.verifie(path, 4, 4, pixels)
                self.assertGreater(sum(1 for p in pixels if p[3] == 0), 0, "cas sans effet")

    def test_gris_16_bits(self):
        """La reduction 16 vers 8 garde l'octet de poids fort."""
        valeurs = [(i * 4111) % 65536 for i in range(16)]
        pixels = [(v >> 8,) * 3 + (255,) for v in valeurs]
        path = ecrire_png(self.root / "gris16.png", 4, 4, 16, GRIS, valeurs)
        self.verifie(path, 4, 4, pixels)

    def test_gris_16_bits_avec_trns(self):
        """La cle tRNS suit la meme reduction que les echantillons."""
        valeurs = [(i * 4111) % 65536 for i in range(16)]
        hauts = [v >> 8 for v in valeurs]
        self.assertEqual(len(set(hauts)), len(hauts), "octets de poids fort ambigus")
        cible = valeurs[5]
        pixels = [
            (0, 0, 0, 0) if v == cible else (v >> 8,) * 3 + (255,)
            for v in valeurs
        ]
        path = ecrire_png(self.root / "gris16t.png", 4, 4, 16, GRIS, valeurs,
                          trns=struct.pack(">H", cible))
        self.verifie(path, 4, 4, pixels)

    def test_gris_alpha(self):
        valeurs = []
        pixels = []
        for i in range(16):
            gris, alpha = (i * 17) % 256, (i * 15) % 256
            valeurs += [gris, alpha]
            pixels.append((gris, gris, gris, alpha))
        path = ecrire_png(self.root / "la.png", 4, 4, 8, GRIS_ALPHA, valeurs)
        self.verifie(path, 4, 4, pixels)

    # -------------------------------------------------------------- rvb ------

    def test_rvb_16_bits(self):
        valeurs = []
        pixels = []
        for i in range(16):
            r, g, b = (i * 4111) % 65536, (i * 257) % 65536, (i * 8191) % 65536
            valeurs += [r, g, b]
            pixels.append((r >> 8, g >> 8, b >> 8, 255))
        path = ecrire_png(self.root / "rvb16.png", 4, 4, 16, RVB, valeurs)
        self.verifie(path, 4, 4, pixels)

    def test_rvb_avec_trns(self):
        """Une couleur entiere declaree transparente, hors palette."""
        cle = (10, 20, 30)
        valeurs = []
        pixels = []
        for i in range(16):
            couleur = cle if i % 5 == 0 else ((i * 16) % 256, (i * 8) % 256, (i * 4) % 256)
            valeurs += list(couleur)
            pixels.append((0, 0, 0, 0) if couleur == cle else couleur + (255,))
        trns = struct.pack(">HHH", *cle)
        path = ecrire_png(self.root / "rvbt.png", 4, 4, 8, RVB, valeurs, trns=trns)
        self.verifie(path, 4, 4, pixels)

    # ---------------------------------------------------------- palette ------

    def test_index_de_palette_non_etires(self):
        """Regression : un index de palette n'est pas une intensite.

        En 4 bits, l'index 1 etire vaut 17 et pointe sur la mauvaise entree de
        PLTE, quand il ne sort pas de la palette.
        """
        palette = bytes(v for i in range(16) for v in ((i * 17) % 256, (i * 29) % 256, (i * 53) % 256))
        indices = list(range(16))
        pixels = [(palette[i * 3], palette[i * 3 + 1], palette[i * 3 + 2], 255) for i in indices]
        path = ecrire_png(self.root / "pal4.png", 4, 4, 4, PALETTE, indices, palette=palette)
        self.verifie(path, 4, 4, pixels)

    def test_palette_sous_8_bits_avec_trns(self):
        for depth in (1, 2, 4):
            with self.subTest(profondeur=depth):
                taille = 1 << depth
                palette = bytes(v for i in range(taille) for v in ((i * 11) % 256, (i * 37) % 256, i))
                alphas = bytes([0, 128] + [255] * (taille - 2))[:taille]
                indices = [(x + y) % taille for y in range(4) for x in range(4)]
                pixels = []
                for index in indices:
                    a = alphas[index]
                    r, g, b = palette[index * 3:index * 3 + 3]
                    pixels.append((0, 0, 0, 0) if a == 0 else (r, g, b, a))
                path = ecrire_png(self.root / f"pal{depth}t.png", 4, 4, depth, PALETTE,
                                  indices, palette=palette, trns=alphas)
                self.verifie(path, 4, 4, pixels)

    def test_palette_sans_bloc_plte(self):
        """La norme rend PLTE obligatoire en couleur 3.

        Sans lui, l'image se decodait en pixels entierement transparents : elle
        disparaissait au lieu de dire pourquoi.
        """
        path = ecrire_png(self.root / "sansplte.png", 4, 4, 8, PALETTE, [0] * 16)
        with self.assertRaisesRegex(png.PngError, "sans bloc PLTE"):
            png.frame(path, 1.0)

    def test_index_hors_de_la_palette(self):
        """Un index qu'aucune entree ne couvre est un fichier casse, pas un trou."""
        palette = bytes([10, 20, 30, 40, 50, 60])          # deux entrees
        indices = [0, 1, 3, 1] + [0] * 12                  # 3 n'existe pas
        path = ecrire_png(self.root / "horspalette.png", 4, 4, 8, PALETTE,
                          indices, palette=palette)
        with self.assertRaisesRegex(png.PngError, "index 3 hors"):
            png.frame(path, 1.0)

    def test_trns_plus_long_que_la_palette(self):
        palette = bytes([10, 20, 30, 40, 50, 60])          # deux entrees
        path = ecrire_png(self.root / "trnslong.png", 4, 4, 8, PALETTE, [0] * 16,
                          palette=palette, trns=bytes([0, 128, 255]))
        with self.assertRaisesRegex(png.PngError, "tRNS de 3 entrees"):
            png.frame(path, 1.0)

    def test_plte_non_multiple_de_trois(self):
        """Un PLTE tronque decalerait toutes les couleurs sans que rien ne le dise."""
        path = ecrire_png(self.root / "pltecourt.png", 4, 4, 8, PALETTE, [0] * 16,
                          palette=bytes([10, 20, 30, 40, 50]))
        with self.assertRaisesRegex(png.PngError, "non multiple de 3"):
            png.frame(path, 1.0)

    def test_trns_plus_court_que_la_palette_reste_valide(self):
        """Garde-fou en sens inverse : la norme l'autorise, les entrees non
        couvertes sont simplement opaques. Refuser serait aussi faux."""
        palette = bytes([10, 20, 30, 40, 50, 60, 70, 80, 90])   # trois entrees
        indices = [i % 3 for i in range(16)]
        pixels = []
        for index in indices:
            r, g, b = palette[index * 3:index * 3 + 3]
            pixels.append((0, 0, 0, 0) if index == 0 else (r, g, b, 255))
        path = ecrire_png(self.root / "trnscourt.png", 4, 4, 8, PALETTE, indices,
                          palette=palette, trns=bytes([0]))
        self.verifie(path, 4, 4, pixels)

    # ------------------------------------------------------------ filtres ----

    def test_les_cinq_filtres(self):
        """Les cinq filtres de ligne encodent la meme image, et doivent la rendre."""
        valeurs = []
        pixels = []
        for i in range(64):
            r, g, b, a = (i * 7) % 256, (i * 13) % 256, (i * 29) % 256, (i * 4) % 256
            valeurs += [r, g, b, a]
            pixels.append((r, g, b, a))
        self.tous_les_filtres("degrade", 8, 8, RVBA, valeurs, pixels)

    def test_les_cinq_filtres_sur_les_egalites_de_paeth(self):
        """Paeth departage trois candidats, et les egalites ont un ordre impose.

        La norme veut que la gauche l'emporte quand elle est a egalite avec la
        diagonale, et le dessus quand c'est lui. Un degrade ne tombe jamais sur
        ces deux cas, il faut viser : avec p = gauche + dessus - diagonale, les
        ecarts valent |d1|, |d2| et |d1 + d2| pour d1 = dessus - diagonale et
        d2 = gauche - diagonale, donc l'egalite demande d2 = -2 d1, ou
        l'inverse. Les voisinages (20, 10, 40) et (20, 40, 10) font l'affaire.
        """
        lignes = [[20, 10, 20, 40], [40, 99, 10, 77], [20, 40, 20, 10], [10, 55, 40, 33]]
        gauche_diagonale, dessus_diagonale = _egalites_de_paeth(lignes)
        self.assertGreater(gauche_diagonale, 0, "aucune egalite gauche/diagonale a departager")
        self.assertGreater(dessus_diagonale, 0, "aucune egalite dessus/diagonale a departager")

        valeurs = [v for ligne in lignes for v in ligne]
        pixels = [(v, v, v, 255) for v in valeurs]
        self.tous_les_filtres("paeth", 4, 4, GRIS, valeurs, pixels)

    def tous_les_filtres(self, nom, width, height, color, valeurs, pixels):
        rendus = []
        for filtre in range(5):
            with self.subTest(filtre=filtre):
                path = ecrire_png(self.root / f"{nom}{filtre}.png", width, height, 8,
                                  color, valeurs, filtre=filtre)
                self.verifie(path, width, height, pixels)
                rendus.append(png.frame(path, 1.0).data)
        self.assertEqual(len(set(rendus)), 1, "les cinq filtres divergent")

    # --------------------------------------------------------- refus ---------

    def test_entrelace_refuse(self):
        path = ecrire_png(self.root / "adam7.png", 4, 4, 8, GRIS, [0] * 16, interlace=1)
        with self.assertRaises(png.PngError):
            png.frame(path, 1.0)

    def test_profondeur_interdite_par_la_norme(self):
        """Le RVB n'existe qu'en 8 et 16 bits ; on refuse plutot que d'inventer."""
        path = ecrire_png(self.root / "rvb4.png", 4, 4, 4, RVB, [0] * 48)
        with self.assertRaises(png.PngError):
            png.frame(path, 1.0)

    def test_donnees_tronquees(self):
        """Deux lignes ecrites, quatre annoncees."""
        path = ecrire_png(self.root / "court.png", 4, 2, 8, GRIS, list(range(8)),
                          hauteur_declaree=4)
        with self.assertRaises(png.PngError):
            png.frame(path, 1.0)

    def test_signature_absente(self):
        path = self.root / "pasunpng.png"
        path.write_bytes(b"ceci n'est pas une image")
        with self.assertRaises(png.PngError):
            png.frame(path, 1.0)
        with self.assertRaises(png.PngError):
            png.size(path)

    # ------------------------------------------------- taille, cache, echelle -

    def test_size_ne_decode_pas(self):
        """size() lit l'entete : elle repond meme si les pixels sont illisibles.

        Le decodage, lui, doit refuser en PngError comme n'importe quelle image
        illisible, sans laisser filtrer l'exception de zlib : le contrat du
        module ne demande a l'appelant de connaitre que PngError.
        """
        path = ecrire_png(self.root / "entete.png", 7, 3, 8, GRIS, [0] * 21, idat_casse=True)
        self.assertEqual(png.size(path), (7, 3))
        with self.assertRaises(png.PngError):
            png.frame(path, 1.0)

    def test_cache_suit_la_date_du_fichier(self):
        path = ecrire_png(self.root / "cache.png", 4, 4, 8, GRIS, [10] * 16)
        premier = png.frame(path, 1.0)
        self.assertIs(png.frame(path, 1.0), premier, "le cache devrait resservir l'image")

        date = path.stat().st_mtime_ns
        ecrire_png(path, 4, 4, 8, GRIS, [200] * 16)
        os.utime(path, ns=(date + 10 ** 9, date + 10 ** 9))
        second = png.frame(path, 1.0)
        self.assertIsNot(second, premier, "un fichier modifie doit etre relu")
        self.assertNotEqual(second.data, premier.data)

    def test_agrandissement(self):
        valeurs = [v for i in range(16) for v in ((i * 16) % 256, 0, 0, 255)]
        path = ecrire_png(self.root / "petit.png", 4, 4, 8, RVBA, valeurs)
        grand = png.frame(path, 2.0)
        self.assertEqual((grand.width, grand.height), (8, 8))
        self.assertEqual(len(grand.data), 8 * 8 * 4)

    def test_la_reduction_garde_le_transparent_transparent(self):
        """Moyenner du premultiplie ne fait pas baver la couleur sur le vide."""
        valeurs = []
        for y in range(8):
            for x in range(8):
                valeurs += [255, 0, 0, 0] if x < 4 else [0, 0, 255, 255]
        path = ecrire_png(self.root / "moitie.png", 8, 8, 8, RVBA, valeurs)
        reduit = png.frame(path, 0.5)
        self.assertEqual((reduit.width, reduit.height), (4, 4))
        for y in range(4):
            for x in range(2):
                pixel = reduit.data[(y * 4 + x) * 4:(y * 4 + x) * 4 + 4]
                self.assertEqual(pixel, b"\x00\x00\x00\x00", f"pixel {x},{y} teinte")


@unittest.skipIf(png is None, "doot/png.py absent (arrive avec l'overlay X11)")
class MiroirDeFrame(unittest.TestCase):
    """Le retournement horizontal des pixels, pour l'entree par la droite."""

    def setUp(self):
        dossier = TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        self.root = Path(dossier.name)

        # Une image franchement asymetrique : bande rouge a gauche, bleue a droite
        self.pixels = []
        valeurs = []
        for y in range(4):
            for x in range(8):
                couleur = (200, 0, 0, 255) if x < 4 else (0, 0, 200, 255)
                valeurs += list(couleur)
                self.pixels.append(couleur)
        self.chemin = ecrire_png(self.root / "bandes.png", 8, 4, 8, RVBA, valeurs)

    def test_dimensions_conservees(self):
        frame = png.frame(self.chemin, 1.0)
        miroir = frame.mirrored()
        self.assertEqual((miroir.width, miroir.height), (frame.width, frame.height))
        self.assertEqual(len(miroir.data), len(frame.data))

    def test_les_colonnes_sont_inversees(self):
        frame = png.frame(self.chemin, 1.0)
        miroir = frame.mirrored()
        largeur = frame.width
        for y in range(frame.height):
            for x in range(largeur):
                origine = ((y * largeur) + x) * 4
                cible = ((y * largeur) + (largeur - 1 - x)) * 4
                self.assertEqual(
                    miroir.data[cible:cible + 4], frame.data[origine:origine + 4],
                    f"pixel ({x},{y})",
                )

    def test_les_bandes_changent_de_cote(self):
        frame = png.frame(self.chemin, 1.0)
        miroir = frame.mirrored()
        # BGRA : le rouge est en 3e octet, le bleu en 1er
        self.assertGreater(frame.data[2], 100, "rouge attendu a gauche a l'origine")
        self.assertGreater(miroir.data[0], 100, "bleu attendu a gauche apres miroir")

    def test_double_miroir_est_neutre(self):
        frame = png.frame(self.chemin, 1.0)
        self.assertEqual(frame.mirrored().mirrored().data, frame.data)

    def test_la_source_n_est_pas_modifiee(self):
        frame = png.frame(self.chemin, 1.0)
        avant = bytes(frame.data)
        frame.mirrored()
        self.assertEqual(frame.data, avant)


@unittest.skipIf(png is None, "doot/png.py absent (arrive avec l'overlay X11)")
class RotationDeFrame(unittest.TestCase):
    """La rotation par quarts de tour, pour poser le bas contre un bord."""

    def setUp(self):
        dossier = TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        self.root = Path(dossier.name)

        # 6 x 4, avec une derniere ligne franchement reperable : c'est « le bas »
        valeurs = []
        for y in range(4):
            for x in range(6):
                couleur = (0, 255, 0, 255) if y == 3 else (40, 40, 40, 255)
                valeurs += list(couleur)
        self.chemin = ecrire_png(self.root / "bas.png", 6, 4, 8, RVBA, valeurs)
        self.frame = png.frame(self.chemin, 1.0)

    def alpha_vert(self, frame, ou):
        """Compte les pixels verts d'un bord donne (le « bas » d'origine)."""
        l, h = frame.width, frame.height
        total = 0
        for y in range(h):
            for x in range(l):
                p = (y * l + x) * 4
                vert = frame.data[p + 1] > 200 and frame.data[p + 2] < 100
                if not vert:
                    continue
                if (ou == "bas" and y == h - 1) or (ou == "haut" and y == 0) \
                        or (ou == "gauche" and x == 0) or (ou == "droite" and x == l - 1):
                    total += 1
        return total

    def test_dimensions(self):
        self.assertEqual((self.frame.rotated(0).width, self.frame.rotated(0).height), (6, 4))
        self.assertEqual((self.frame.rotated(1).width, self.frame.rotated(1).height), (4, 6))
        self.assertEqual((self.frame.rotated(2).width, self.frame.rotated(2).height), (6, 4))
        self.assertEqual((self.frame.rotated(3).width, self.frame.rotated(3).height), (4, 6))

    def test_le_bas_va_contre_le_bord_voulu(self):
        """C'est toute la raison d'etre de la rotation."""
        self.assertEqual(self.alpha_vert(self.frame, "bas"), 6, "temoin mal pose")
        self.assertEqual(self.alpha_vert(self.frame.rotated(1), "gauche"), 6,
                         "un quart horaire doit mettre le bas a gauche")
        self.assertEqual(self.alpha_vert(self.frame.rotated(3), "droite"), 6,
                         "trois quarts doivent mettre le bas a droite")
        self.assertEqual(self.alpha_vert(self.frame.rotated(2), "haut"), 6,
                         "un demi-tour doit mettre le bas en haut")
        self.assertEqual(self.alpha_vert(self.frame.rotated(0), "bas"), 6,
                         "sans rotation, le bas reste en bas")

    def test_quatre_quarts_reviennent_au_depart(self):
        tourne = self.frame
        for _ in range(4):
            tourne = tourne.rotated(1)
        self.assertEqual(tourne.data, self.frame.data)
        self.assertEqual((tourne.width, tourne.height), (self.frame.width, self.frame.height))

    def test_quarts_equivalents(self):
        self.assertEqual(self.frame.rotated(5).data, self.frame.rotated(1).data)
        self.assertEqual(self.frame.rotated(-1).data, self.frame.rotated(3).data)

    def test_aller_retour_par_le_fichier(self):
        """L'image pivotee doit pouvoir etre relue a l'identique.

        C'est ainsi qu'elle parvient a tkinter, qui ne sait pas pivoter et
        n'accepte l'alpha que par un fichier.
        """
        pivote = self.frame.rotated(1)
        chemin = self.root / "pivote.png"
        png.write_png(chemin, pivote)
        relu = png.frame(chemin, 1.0)
        self.assertEqual((relu.width, relu.height), (pivote.width, pivote.height))
        self.assertEqual(relu.data, pivote.data)

    def test_l_ecriture_conserve_la_transparence(self):
        valeurs = []
        for y in range(4):
            for x in range(6):
                valeurs += [10, 20, 30, 0 if x < 3 else 255]
        source = png.frame(ecrire_png(self.root / "t.png", 6, 4, 8, RVBA, valeurs), 1.0)
        png.write_png(self.root / "t2.png", source)
        relu = png.frame(self.root / "t2.png", 1.0)
        transparents = sum(1 for i in range(0, len(relu.data), 4) if relu.data[i + 3] == 0)
        self.assertEqual(transparents, 12)


@unittest.skipIf(png is None, "doot/png.py absent (arrive avec l'overlay X11)")
class TourCompletDeFrame(unittest.TestCase):
    """Le carre et ses quatre orientations, pour la rotation complete."""

    def setUp(self):
        dossier = TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        self.root = Path(dossier.name)

        # 6 x 4, derniere ligne verte : « le bas », qu'on suit pendant le tour
        valeurs = []
        for y in range(4):
            for x in range(6):
                couleur = (0, 255, 0, 255) if y == 3 else (40, 40, 40, 255)
                valeurs += list(couleur)
        self.chemin = ecrire_png(self.root / "bas.png", 6, 4, 8, RVBA, valeurs)
        self.frame = png.frame(self.chemin, 1.0)

    def vert_sur_le_bord(self, frame, ou):
        """Nombre de pixels verts poses sur le bord demande."""
        l, h = frame.width, frame.height
        total = 0
        for y in range(h):
            for x in range(l):
                p = (y * l + x) * 4
                if not (frame.data[p + 1] > 200 and frame.data[p + 2] < 100):
                    continue
                if (ou == "bas" and y == h - 1) or (ou == "haut" and y == 0)                         or (ou == "gauche" and x == 0) or (ou == "droite" and x == l - 1):
                    total += 1
        return total

    def test_le_carre_prend_le_plus_grand_cote(self):
        carre = self.frame.squared()
        self.assertEqual((carre.width, carre.height), (6, 6))
        self.assertEqual(len(carre.data), 6 * 6 * 4)

    def test_le_carre_centre_l_image(self):
        """L'image doit rester au milieu, sinon elle tournerait de travers."""
        carre = self.frame.squared()
        for y in range(self.frame.height):
            origine = y * self.frame.width * 4
            cible = ((y + 1) * 6) * 4  # une ligne de marge en haut, aucune a gauche
            self.assertEqual(
                carre.data[cible:cible + self.frame.width * 4],
                self.frame.data[origine:origine + self.frame.width * 4],
                f"ligne {y}",
            )

    def test_les_marges_du_carre_sont_transparentes(self):
        carre = self.frame.squared()
        for y in (0, 5):  # les lignes ajoutees
            for x in range(6):
                p = (y * 6 + x) * 4
                self.assertEqual(carre.data[p:p + 4], bytes(4),
                                 f"pixel ({x},{y}) devrait etre transparent")

    def test_une_image_deja_carree_est_rendue_telle_quelle(self):
        valeurs = [10, 20, 30, 255] * 16
        carree = png.frame(ecrire_png(self.root / "c.png", 4, 4, 8, RVBA, valeurs), 1.0)
        self.assertEqual(carree.squared().data, carree.data)

    def test_les_quatre_etapes_ont_la_meme_taille(self):
        """C'est la raison d'etre du carre : la surface ne change pas en route."""
        etapes = png.spin_frames(self.frame)
        self.assertEqual(len(etapes), 4)
        for etape in etapes:
            self.assertEqual((etape.width, etape.height), (6, 6))

    def test_le_tour_fait_bien_le_tour(self):
        """Le bas passe a gauche, en haut, a droite, et revient en bas.

        Sur une image deja carree, ou le carre ne rajoute aucune marge : la
        bande verte touche donc vraiment le bord a chaque etape.
        """
        valeurs = []
        for y in range(4):
            for x in range(4):
                valeurs += list((0, 255, 0, 255) if y == 3 else (40, 40, 40, 255))
        source = png.frame(ecrire_png(self.root / "carre.png", 4, 4, 8, RVBA, valeurs), 1.0)

        etapes = png.spin_frames(source)
        oppose = {"bas": "haut", "gauche": "droite", "haut": "bas", "droite": "gauche"}
        for quarts, ou in enumerate(("bas", "gauche", "haut", "droite")):
            self.assertEqual(self.vert_sur_le_bord(etapes[quarts], ou), 4,
                             f"apres {quarts} quart(s), la bande devrait border {ou}")
            self.assertEqual(self.vert_sur_le_bord(etapes[quarts], oppose[ou]), 0,
                             f"apres {quarts} quart(s), rien de vert en face")

    def test_le_tour_se_referme_sur_l_image_droite(self):
        """La derniere etape ramenee d'un quart doit redonner la premiere."""
        etapes = png.spin_frames(self.frame)
        self.assertEqual(etapes[3].rotated(1).data, etapes[0].data)
        self.assertEqual(etapes[0].data, self.frame.squared().data)


if __name__ == "__main__":
    unittest.main()
