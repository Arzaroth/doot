"""Les melodies en doots : lecture RTTTL, catalogue, accordage et rendu.

Le rendu est confronte a la partition : chaque note doit commencer ou elle
est annoncee, et la vitesse de lecture doit poser chaque hauteur au bon
endroit par rapport au coup de trompette, sinon le squelette chante faux.
"""

from __future__ import annotations

import array
import tempfile
import unittest
import wave
from pathlib import Path

from doot import melodie

RICKROLL = melodie.MELODIES_DIR / "rickroll.rtttl"
SPOOKY = melodie.MELODIES_DIR / "spooky-scary-skeletons.rtttl"
CARELESS = melodie.MELODIES_DIR / "careless-whisper.rtttl"
MEGALOVANIA = melodie.MELODIES_DIR / "megalovania.rtttl"
HALLOWEEN = melodie.MELODIES_DIR / "this-is-halloween.rtttl"


class LectureRtttl(unittest.TestCase):

    def test_reglages_et_notes(self):
        m = melodie.parse("Essai:d=8,o=5,b=120:c,4d#6,p,2.e4,16f.,g#,h")
        self.assertEqual(m.name, "Essai")
        self.assertEqual(m.tempo, 120)
        self.assertEqual(m.notes, [
            (72, 0.5),      # croche de do5 (d=8, o=5)
            (87, 1.0),      # noire de re#6
            (None, 0.5),    # silence d'une croche
            (64, 3.0),      # blanche pointee de mi4
            (77, 0.375),    # double-croche pointee de fa5
            (80, 0.5),      # sol#5
            (83, 0.5),      # h = si, a l'allemande
        ])

    def test_le_point_aux_trois_places(self):
        for jeton in ("8.f", "8f.", "8f5."):
            m = melodie.parse(f"x:d=4,o=5,b=60:{jeton}")
            self.assertEqual(m.notes, [(77, 0.75)], jeton)

    def test_reglages_par_defaut_et_casse(self):
        m = melodie.parse("x::C,D")
        self.assertEqual(m.tempo, 63)
        self.assertEqual(m.notes, [(72, 1.0), (74, 1.0)])

    def test_octaves_sous_la_norme(self):
        """La norme s'arrete au do4 ; les basses d'un riff vont plus bas."""
        self.assertEqual(melodie.parse("x:o=3:c,a#2").notes, [(48, 1.0), (46, 1.0)])

    def test_le_nom_du_fichier_supplee_un_titre_vide(self):
        self.assertEqual(melodie.parse(":d=4:c", name="sans-titre").name, "sans-titre")

    def test_erreurs_lisibles(self):
        cas = {
            "pas de sections": "il faut trois sections",
            "x:d=3:c": "duree par defaut d=3",
            "x:o=9:c": "octave par defaut o=9",
            "x::c9": "note incomprise : 'c9'",
            "x:z=1:c": "reglage incompris",
            "x::c,x": "note incomprise : 'x'",
            "x::3c": "duree 3 dans '3c'",
            "x::p,p": "aucune note",
        }
        for texte, attendu in cas.items():
            with self.assertRaises(melodie.MelodieError, msg=texte) as cm:
                melodie.parse(texte)
            self.assertIn(attendu, str(cm.exception))

    def test_fichier_illisible_nomme_le_fichier(self):
        with tempfile.TemporaryDirectory() as d:
            mauvais = Path(d) / "casse.rtttl"
            mauvais.write_text("x::c,?", encoding="utf-8")
            with self.assertRaises(melodie.MelodieError) as cm:
                melodie.load(mauvais)
            self.assertTrue(str(cm.exception).startswith("casse.rtttl : "))


class Polyphonie(unittest.TestCase):

    def test_deux_lignes_font_deux_voix(self):
        m = melodie.parse("Melodie:d=4,o=5,b=120:c,d\nBasse:d=2,o=4,b=120:c,g")
        self.assertEqual(m.name, "Melodie")
        self.assertEqual(m.tempo, 120)
        self.assertEqual(m.voices, [
            [(72, 1.0), (74, 1.0)],
            [(60, 2.0), (67, 2.0)],
        ])
        self.assertEqual(m.notes, m.voices[0])
        self.assertEqual(m.pitches(), [72, 74, 60, 67])

    def test_commentaires_et_lignes_vides_sont_ignores(self):
        m = melodie.parse("# source\n\nUne::c\n  # basse\nDeux::g4")
        self.assertEqual(len(m.voices), 2)

    def test_une_seule_ligne_reste_compatible(self):
        m = melodie.parse("Une::c,d")
        self.assertEqual(m.voices, [[(72, 1.0), (74, 1.0)]])
        self.assertEqual(m.notes, [(72, 1.0), (74, 1.0)])

    def test_les_voix_doivent_avoir_le_meme_tempo(self):
        with self.assertRaises(melodie.MelodieError) as cm:
            melodie.parse("Une:b=120:c\nDeux:b=90:g")
        self.assertIn("voix 2 : tempo b=90", str(cm.exception))

    def test_une_erreur_nomme_sa_voix(self):
        with self.assertRaises(melodie.MelodieError) as cm:
            melodie.parse("Une::c\nDeux::?")
        self.assertIn("voix 2 : note incomprise", str(cm.exception))

    def test_un_fichier_sans_sonnerie_est_refuse(self):
        with self.assertRaises(melodie.MelodieError) as cm:
            melodie.parse("# rien ici\n\n")
        self.assertIn("aucune sonnerie", str(cm.exception))

    def test_le_nombre_de_voix_n_est_pas_plafonne(self):
        texte = "\n".join(f"Voix{n}:b=120:c" for n in range(50))
        self.assertEqual(len(melodie.parse(texte).voices), 50)

    def test_la_duree_est_celle_de_la_voix_la_plus_longue(self):
        m = melodie.parse("Courte:d=4,b=60:c\nLongue:d=4,b=60:c,c,c")
        self.assertAlmostEqual(melodie.duration(m), melodie.LEAD + 3 + melodie.TAIL)

    def test_les_coups_du_squelette_suivent_la_voix_principale(self):
        m = melodie.parse("Une:d=4,b=60:c,p,d\nDeux:d=8,b=60:c,c,c,c,c,c")
        self.assertEqual(melodie.onsets(m), [melodie.LEAD, melodie.LEAD + 2])
        self.assertEqual(melodie.onsets(m, voice=1),
                         [melodie.LEAD + n * 0.5 for n in range(6)])


class Catalogue(unittest.TestCase):

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.perso = Path(self._dir.name) / "melodies"

    def tearDown(self):
        self._dir.cleanup()

    def test_les_cinq_melodies_fournies(self):
        self.assertEqual([p.stem for p in melodie.bundled()],
                         ["careless-whisper", "megalovania", "rickroll",
                          "spooky-scary-skeletons", "this-is-halloween"])

    def test_un_nom_trouve_la_fournie(self):
        self.assertEqual(melodie.find("rickroll", self.perso), RICKROLL)
        self.assertEqual(melodie.find("RickRoll", self.perso), RICKROLL)

    def test_un_nom_inconnu_rend_none(self):
        self.assertIsNone(melodie.find("nope", self.perso))

    def test_la_perso_passe_avant_la_fournie(self):
        self.perso.mkdir()
        mien = self.perso / "rickroll.rtttl"
        mien.write_text("x::c", encoding="utf-8")
        self.assertEqual(melodie.find("rickroll", self.perso), mien)
        self.assertEqual(melodie.custom(self.perso), [mien])

    def test_un_chemin_est_pris_tel_quel(self):
        with tempfile.TemporaryDirectory() as d:
            ailleurs = Path(d) / "truc.rtttl"
            ailleurs.write_text("x::c", encoding="utf-8")
            self.assertEqual(melodie.find(str(ailleurs), self.perso), ailleurs)

    def test_un_dossier_perso_absent_ne_gene_pas(self):
        self.assertEqual(melodie.custom(self.perso), [])


class Accordage(unittest.TestCase):

    def test_le_doot_est_un_re5(self):
        self.assertAlmostEqual(melodie.NOTE_MIDI, 74.2, places=1)

    def test_une_octave_double_la_vitesse(self):
        self.assertAlmostEqual(melodie.rate(12), 2 * melodie.rate(0))

    def test_recentrage_par_octaves(self):
        haute = melodie.parse("x:o=7:c,d,e")     # do7 : deux octaves trop haut
        basse = melodie.parse("x:o=4:c,d,e")     # do4 : une octave trop bas
        pile = melodie.parse("x:o=5:c,d,e,f")
        self.assertEqual(melodie.transposition(haute), -24)
        self.assertEqual(melodie.transposition(basse), 12)
        self.assertEqual(melodie.transposition(pile), 0)

    def test_le_milieu_de_l_ambitus_et_non_la_mediane(self):
        """Cent notes de basse sous un theme aigu ne font pas monter le theme."""
        m = melodie.parse("x:o=4:" + ",".join(["d"] * 100) + ",d6,g6")
        self.assertEqual(melodie.transposition(m), 0)

    def test_transpose_s_ajoute_au_recentrage(self):
        m = melodie.parse("x:o=5:d")
        sans = melodie.notes(m)[0][2]
        avec = melodie.notes(m, transpose=3)[0][2]
        self.assertAlmostEqual(avec - sans, 3)

    def test_le_rickroll_reste_en_la_bemol(self):
        # La tonique, sol#4, six demi-tons sous le doot : pas de recentrage.
        m = melodie.load(RICKROLL)
        self.assertEqual(melodie.transposition(m), 0)
        self.assertAlmostEqual(melodie.rate(melodie.notes(m)[0][2]), 415.3 / 594.0, places=3)

    def test_les_fournies_restent_a_moins_d_une_octave_du_doot(self):
        # Le rickroll tient dans une octave et demie de lecture ; les autres
        # descendent plus bas (un riff de basse) ou montent plus haut (un
        # theme), mais jamais a l'octave au-dessus du doot.
        for fichier, bas, haut in ((RICKROLL, 0.6, 1.5), (SPOOKY, 0.45, 1.7), (CARELESS, 0.45, 1.5),
                                   (MEGALOVANIA, 0.35, 1.9), (HALLOWEEN, 0.55, 1.8)):
            vitesses = [melodie.rate(s) for _, _, s in melodie.notes(melodie.load(fichier))]
            self.assertGreater(min(vitesses), bas, fichier.name)
            self.assertLess(max(vitesses), haut, fichier.name)


class Partition(unittest.TestCase):

    def test_le_refrain_fait_huit_mesures(self):
        m = melodie.load(RICKROLL)
        self.assertEqual(sum(temps for _, temps in m.notes), 32)
        self.assertEqual(len(m.pitches()), 54)

    def test_spooky_fait_vingt_mesures(self):
        # Le riff d'intro (4 mesures) puis trois couplets et le pont (16).
        m = melodie.load(SPOOKY)
        self.assertEqual(sum(temps for _, temps in m.notes), 80)

    def test_megalovania_a_deux_voix_de_meme_duree(self):
        m = melodie.load(MEGALOVANIA)
        self.assertEqual(len(m.voices), 2)
        self.assertEqual([sum(temps for _, temps in voix) for voix in m.voices],
                         [64, 64])
        self.assertEqual([sum(midi is not None for midi, _ in voix) for voix in m.voices],
                         [144, 97])

    def test_les_coups_se_suivent_apres_la_tete(self):
        coups = melodie.onsets(melodie.load(RICKROLL))
        self.assertEqual(coups[0], melodie.LEAD)
        self.assertTrue(all(a < b for a, b in zip(coups, coups[1:])))

    def test_les_notes_ne_se_chevauchent_pas(self):
        notes = melodie.notes(melodie.load(SPOOKY))
        for (debut, duree, _), (suivant, _, _) in zip(notes, notes[1:]):
            self.assertLessEqual(debut + duree, suivant + 1e-9)

    def test_la_duree_couvre_tete_melodie_et_queue(self):
        m = melodie.load(RICKROLL)
        fin = max(debut + duree for debut, duree, _ in melodie.notes(m))
        self.assertGreaterEqual(melodie.duration(m), fin + melodie.TAIL - 1e-9)

    def test_le_tempo_etire_la_partition(self):
        m = melodie.parse("x:d=4,b=60:c,c,c,c")
        self.assertAlmostEqual(melodie.duration(m), melodie.LEAD + 4 + melodie.TAIL)


class Tenue(unittest.TestCase):
    """`sustained` : le coup tel quel s'il suffit, sinon boucle puis finale."""

    @classmethod
    def setUpClass(cls):
        cls.source, cls.rate = melodie._read_note()

    def test_un_coup_assez_long_est_rendu_tel_quel(self):
        self.assertEqual(melodie.sustained(self.source, self.rate, len(self.source)), list(self.source))

    def test_la_tenue_atteint_la_longueur_voulue(self):
        voulu = self.rate * 2   # deux secondes, huit fois le coup
        tenu = melodie.sustained(self.source, self.rate, voulu)
        self.assertGreaterEqual(len(tenu), voulu)
        self.assertLess(len(tenu), voulu + len(self.source))

    def test_la_finale_est_celle_du_coup(self):
        """Le « t » du doot termine la note tenue, comme la note courte."""
        tenu = melodie.sustained(self.source, self.rate, self.rate)
        queue = int(self.rate * 0.05)
        self.assertEqual(tenu[-queue:], list(self.source[-queue:]))

    def test_pas_de_saut_aux_raccords(self):
        """Les fondus enchaines evitent le clic : aucun ecart entre deux
        echantillons voisins ne depasse ce qu'on trouve dans le coup lui-meme."""
        tenu = melodie.sustained(self.source, self.rate, self.rate)
        pire_source = max(abs(b - a) for a, b in zip(self.source, self.source[1:]))
        pire_tenu = max(abs(b - a) for a, b in zip(tenu, tenu[1:]))
        self.assertLessEqual(pire_tenu, pire_source)

    def test_une_note_longue_sonne_jusqu_au_bout(self):
        with tempfile.TemporaryDirectory() as d:
            wav = melodie.render(Path(d) / "tenue.wav", melodie.parse("x:d=1,o=5,b=60:d"))
            with wave.open(str(wav), "rb") as handle:
                rate = handle.getframerate()
                samples = array.array("h", handle.readframes(handle.getnframes()))
        # Une ronde a 60 : quatre secondes. Le coup seul se tait au bout de 265 ms.
        debut = melodie.LEAD + 3.0
        tranche = samples[int(debut * rate):int((debut + 0.2) * rate)]
        self.assertGreater(max(abs(v) for v in tranche), 3000)


class RenduPolyphonique(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._dir = tempfile.TemporaryDirectory()
        root = Path(cls._dir.name)
        cls.c = cls.lit(melodie.render(root / "c.wav", melodie.parse("C:d=4,o=5,b=120:c")))
        cls.e = cls.lit(melodie.render(root / "e.wav", melodie.parse("E:d=4,o=5,b=120:e")))
        cls.duo = cls.lit(melodie.render(
            root / "duo.wav", melodie.parse("C:d=4,o=5,b=120:c\nE:d=4,o=5,b=120:e")))
        cls.unisson = cls.lit(melodie.render(
            root / "unisson.wav", melodie.parse("C:d=4,o=5,b=120:c\nC:d=4,o=5,b=120:c")))

    @staticmethod
    def lit(path):
        with wave.open(str(path), "rb") as handle:
            samples = array.array("h", handle.readframes(handle.getnframes()))
            return handle.getframerate(), samples

    @classmethod
    def tearDownClass(cls):
        cls._dir.cleanup()

    def test_le_mix_est_la_somme_des_voix_divisee_par_leur_nombre(self):
        rate, c = self.c
        self.assertEqual(rate, self.e[0])
        self.assertEqual(rate, self.duo[0])
        e, duo = self.e[1], self.duo[1]
        debut = int(melodie.LEAD * rate)
        fin = debut + int(0.2 * rate)
        attendu = [int(a * 0.5) + int(b * 0.5) for a, b in zip(c[debut:fin], e[debut:fin])]
        self.assertEqual(list(duo[debut:fin]), attendu)

    def test_deux_voix_a_l_unisson_gardent_le_niveau_d_une_seule(self):
        _, seule = self.c
        _, deux = self.unisson
        # L'arrondi vers zero peut laisser une unite d'ecart sur les impairs.
        self.assertLessEqual(max(abs(a - b) for a, b in zip(seule, deux)), 1)

    def test_le_mix_reste_mono_16_bits(self):
        rate, samples = self.duo
        self.assertEqual(rate, 48000)
        self.assertTrue(samples)
        self.assertLessEqual(max(samples), 32767)
        self.assertGreaterEqual(min(samples), -32768)


class Rendu(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._dir = tempfile.TemporaryDirectory()
        cls.melodie = melodie.load(RICKROLL)
        cls.wav = melodie.render(Path(cls._dir.name) / "refrain.wav", cls.melodie)
        with wave.open(str(cls.wav), "rb") as handle:
            cls.rate = handle.getframerate()
            cls.channels = handle.getnchannels()
            cls.width = handle.getsampwidth()
            cls.samples = array.array("h", handle.readframes(handle.getnframes()))

    @classmethod
    def tearDownClass(cls):
        cls._dir.cleanup()

    def niveau(self, debut: float, fin: float) -> int:
        tranche = self.samples[int(debut * self.rate):int(fin * self.rate)]
        return max((abs(v) for v in tranche), default=0)

    def test_wav_mono_16_bits(self):
        self.assertEqual((self.channels, self.width), (1, 2))
        self.assertAlmostEqual(len(self.samples) / self.rate,
                               melodie.duration(self.melodie), places=2)

    def test_silence_en_tete(self):
        self.assertEqual(self.niveau(0, melodie.LEAD - 0.01), 0)

    def test_chaque_coup_sonne_ou_il_est_annonce(self):
        for debut, _, _ in melodie.notes(self.melodie):
            # Entre deux doubles-croches il ne reste que 8 % du creneau, soit 10 ms.
            self.assertEqual(self.niveau(debut - 0.005, debut), 0, f"bruit avant {debut:.2f}s")
            self.assertGreater(self.niveau(debut, debut + 0.05), 3000, f"silence a {debut:.2f}s")

    def test_le_silence_revient_a_la_fin(self):
        fin = melodie.duration(self.melodie)
        self.assertEqual(self.niveau(fin - 0.3, fin), 0)
