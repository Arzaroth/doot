"""Toast illustre et micro-fanfare de deblocage."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from doot import melodie, notification, screens, sound


class Animation(unittest.TestCase):
    def test_fondu(self):
        self.assertEqual(notification.opacity_at(0.0, 3.4), 0.0)
        self.assertEqual(notification.opacity_at(1.0, 3.4), 1.0)
        self.assertEqual(notification.opacity_at(3.4, 3.4), 0.0)
        self.assertGreater(notification.opacity_at(3.2, 3.4), 0.0)

    def test_coin_superieur_droit(self):
        monitor = screens.Monitor(-1920, 20, 1920, 1040)
        self.assertEqual(notification.position(monitor, 440, 140), (-464, 44))

    def test_un_grand_toast_reste_dans_l_ecran(self):
        monitor = screens.Monitor(0, 0, 320, 200)
        width, height, x, y = notification.geometry(monitor, 900, 600)
        self.assertEqual((width, height), (320, 200))
        self.assertEqual((x, y), (0, 0))


class Fanfare(unittest.TestCase):
    def test_partition_courte_et_polyphonique(self):
        morceau = melodie.load(notification.VICTORY_RTTTL)
        self.assertEqual(len(morceau.voices), 2)
        self.assertLess(melodie.duration(morceau), 2.0)

    def test_rendu_wav(self):
        with tempfile.TemporaryDirectory() as dossier:
            wav = notification.render_victory(Path(dossier) / "victory.wav")
            self.assertTrue(wav.is_file())
            self.assertGreater(sound.probe_duration(wav), 1.0)


if __name__ == "__main__":
    unittest.main()
