"""Le refrain en doots : partition, accordage et rendu.

Le rendu est confronte a la partition : chaque note doit commencer ou elle
est annoncee, et la vitesse de lecture doit poser la tonique six demi-tons
sous le coup de trompette, sinon le squelette chante faux.
"""

from __future__ import annotations

import array
import tempfile
import unittest
import wave
from pathlib import Path

from doot import rickroll


class Partition(unittest.TestCase):

    def test_le_refrain_fait_huit_mesures(self):
        self.assertEqual(sum(temps for _, temps in rickroll.CHORUS), 32)

    def test_les_coups_se_suivent_apres_la_tete(self):
        coups = rickroll.onsets()
        self.assertEqual(len(coups), 54)
        self.assertEqual(coups[0], rickroll.LEAD)
        self.assertTrue(all(a < b for a, b in zip(coups, coups[1:])))

    def test_les_notes_ne_se_chevauchent_pas(self):
        notes = rickroll.notes()
        for (debut, duree, _), (suivant, _, _) in zip(notes, notes[1:]):
            self.assertLessEqual(debut + duree, suivant + 1e-9)

    def test_la_duree_couvre_tete_refrain_et_queue(self):
        notes = rickroll.notes()
        fin = max(debut + duree for debut, duree, _ in notes)
        self.assertGreaterEqual(rickroll.duration(), fin + rickroll.TAIL - 1e-9)

    def test_le_tempo_etire_la_partition(self):
        self.assertAlmostEqual(rickroll.duration(60), rickroll.LEAD + 32 + rickroll.TAIL)


class Accordage(unittest.TestCase):

    def test_la_tonique_est_six_demi_tons_sous_le_doot(self):
        # Le la bemol 4 sous le re5 : la sixte tombe sur la vitesse normale.
        self.assertAlmostEqual(rickroll.rate(6), 1.0, delta=0.02)

    def test_une_octave_double_la_vitesse(self):
        self.assertAlmostEqual(rickroll.rate(12), 2 * rickroll.rate(0))

    def test_la_melodie_reste_dans_une_octave_et_demie_de_lecture(self):
        vitesses = [rickroll.rate(demi) for demi, _ in rickroll.CHORUS if demi is not None]
        self.assertGreater(min(vitesses), 0.6)
        self.assertLess(max(vitesses), 1.5)


class Rendu(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._dir = tempfile.TemporaryDirectory()
        cls.wav = rickroll.render(Path(cls._dir.name) / "refrain.wav")
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
        self.assertAlmostEqual(len(self.samples) / self.rate, rickroll.duration(), places=2)

    def test_silence_en_tete(self):
        self.assertEqual(self.niveau(0, rickroll.LEAD - 0.01), 0)

    def test_chaque_coup_sonne_ou_il_est_annonce(self):
        for debut, _, _ in rickroll.notes():
            # Entre deux doubles-croches il ne reste que 8 % du creneau, soit 10 ms.
            self.assertEqual(self.niveau(debut - 0.005, debut), 0, f"bruit avant {debut:.2f}s")
            self.assertGreater(self.niveau(debut, debut + 0.05), 3000, f"silence a {debut:.2f}s")

    def test_le_silence_revient_a_la_fin(self):
        self.assertEqual(self.niveau(rickroll.duration() - 0.3, rickroll.duration()), 0)
