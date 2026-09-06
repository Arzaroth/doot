"""Synthese du jingle et choix du son.

Tout ce qui est verifie ici tourne sans carte son ni serveur graphique : on ne
joue rien, on verifie ce qui est produit et ce qui est choisi.
"""

from __future__ import annotations

import tempfile
import unittest
import wave
from pathlib import Path

from doot import sound


class SyntheseDuJingle(unittest.TestCase):
    """Le WAV de repli, genere quand aucun autre son n'est disponible."""

    @classmethod
    def setUpClass(cls):
        cls._dir = tempfile.TemporaryDirectory()
        cls.root = Path(cls._dir.name)
        cls.wav = sound.write_wav(cls.root / "jingle.wav", volume=0.55)

    @classmethod
    def tearDownClass(cls):
        cls._dir.cleanup()

    def test_wav_valide(self):
        with wave.open(str(self.wav), "rb") as handle:
            self.assertEqual(handle.getnchannels(), 1)
            self.assertEqual(handle.getsampwidth(), 2)
            self.assertEqual(handle.getframerate(), sound.SAMPLE_RATE)
            self.assertGreater(handle.getnframes(), 0)

    def test_duree_conforme(self):
        with wave.open(str(self.wav), "rb") as handle:
            seconds = handle.getnframes() / handle.getframerate()
        self.assertAlmostEqual(seconds, sound.TOTAL_SECONDS, places=2)

    def test_le_son_n_est_pas_silencieux(self):
        with wave.open(str(self.wav), "rb") as handle:
            frames = handle.readframes(handle.getnframes())
        self.assertTrue(any(frames), "le jingle ne contient que du silence")

    def test_volume_respecte(self):
        """Un volume plus bas doit donner une amplitude plus basse."""
        import struct

        def peak(path):
            with wave.open(str(path), "rb") as handle:
                data = handle.readframes(handle.getnframes())
            values = struct.unpack(f"<{len(data) // 2}h", data)
            return max(abs(v) for v in values)

        fort = sound.write_wav(self.root / "fort.wav", volume=0.9)
        faible = sound.write_wav(self.root / "faible.wav", volume=0.2)
        self.assertGreater(peak(fort), peak(faible))

    def test_pas_de_saturation(self):
        """Le soft clipping doit garder l'echantillon dans les bornes 16 bits."""
        import struct

        with wave.open(str(self.wav), "rb") as handle:
            data = handle.readframes(handle.getnframes())
        values = struct.unpack(f"<{len(data) // 2}h", data)
        self.assertLessEqual(max(abs(v) for v in values), 32767)

    def test_ensure_wav_ne_regenere_pas_sans_raison(self):
        path = self.root / "cache.wav"
        sound.ensure_wav(path, 0.55)
        first = path.stat().st_mtime_ns
        sound.ensure_wav(path, 0.55)
        self.assertEqual(path.stat().st_mtime_ns, first)

    def test_ensure_wav_force_regenere(self):
        path = self.root / "force.wav"
        sound.ensure_wav(path, 0.55)
        path.write_bytes(b"")  # fichier vide : doit etre refait
        sound.ensure_wav(path, 0.55)
        self.assertGreater(path.stat().st_size, 0)


class ChoixDuSon(unittest.TestCase):
    """L'ordre de priorite : perso, puis fourni, puis synthetise."""

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.root = Path(self._dir.name)
        self.customs = self.root / "sound"
        self.customs.mkdir()
        self.cache = self.root / "doot.wav"

    def tearDown(self):
        self._dir.cleanup()

    def test_renvoie_toujours_un_fichier_existant(self):
        chosen = sound.pick_sound(self.cache, self.customs, 0.55)
        self.assertTrue(chosen.is_file(), chosen)

    def test_le_son_perso_est_prioritaire(self):
        mine = self.customs / "a_moi.wav"
        sound.write_wav(mine, 0.5)
        self.assertEqual(sound.pick_sound(self.cache, self.customs, 0.55), mine)

    def test_les_extensions_inconnues_sont_ignorees(self):
        (self.customs / "notes.txt").write_text("pas un son")
        (self.customs / "image.png").write_bytes(b"\x89PNG")
        self.assertEqual(sound.custom_sounds(self.customs), [])

    def test_formats_compresses_reconnus(self):
        for name in ("a.mp3", "b.ogg", "c.flac", "d.m4a", "e.opus"):
            (self.customs / name).write_bytes(b"factice")
        found = {p.name for p in sound.custom_sounds(self.customs)}
        self.assertEqual(len(found), 5)

    def test_dossier_absent(self):
        self.assertEqual(sound.custom_sounds(self.root / "nexiste_pas"), [])

    def test_repli_synthetise_si_rien_d_autre(self):
        """Sans son perso ni son fourni lisible, on doit obtenir le WAV genere."""
        chosen = sound.pick_sound(self.cache, self.customs, 0.55)
        bundled = sound.bundled_sound()
        self.assertIn(chosen, [p for p in (bundled, self.cache) if p is not None])


class Duree(unittest.TestCase):
    """`probe_duration` cale la duree d'affichage sur celle du son."""

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.root = Path(self._dir.name)

    def tearDown(self):
        self._dir.cleanup()

    def test_duree_d_un_wav(self):
        path = sound.write_wav(self.root / "j.wav", 0.55)
        self.assertAlmostEqual(sound.probe_duration(path), sound.TOTAL_SECONDS, places=2)

    def test_fichier_illisible_renvoie_none(self):
        path = self.root / "casse.wav"
        path.write_bytes(b"pas un wav")
        self.assertIsNone(sound.probe_duration(path))

    def test_son_fourni_plausible_ou_inconnu(self):
        """Selon la plateforme on sait lire un mp3 ou non ; jamais d'exception."""
        bundled = sound.bundled_sound()
        if bundled is None:
            self.skipTest("aucun son fourni dans le paquet")
        length = sound.probe_duration(bundled)
        if length is not None:
            self.assertGreater(length, 0.1)
            self.assertLess(length, 60)


if __name__ == "__main__":
    unittest.main()
