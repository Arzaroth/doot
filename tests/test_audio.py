"""Sortie audio native.

La CI n'a ni carte son ni serveur audio, et tourne aussi sous macOS et Windows.
Ce qui est verifie ici ne joue rien : la preparation des echantillons, le choix
de la sortie, et le fait qu'une absence de bibliotheque se solde par un repli et
non par une erreur.
"""

from __future__ import annotations

import array
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from doot import audio, sound


def _ecris(chemin: Path, canaux: int, trames: list) -> Path:
    with wave.open(str(chemin), "wb") as handle:
        handle.setnchannels(canaux)
        handle.setsampwidth(2)
        handle.setframerate(44100)
        plat = [v for t in trames for v in (t if isinstance(t, tuple) else (t,))]
        handle.writeframes(struct.pack("<%dh" % len(plat), *plat))
    return chemin


class PreparationDesEchantillons(unittest.TestCase):
    """Le panoramique doit tomber sur les memes valeurs que `pan_wav`."""

    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.addCleanup(self.dossier.cleanup)
        self.racine = Path(self.dossier.name)

    def test_le_mono_est_duplique_puis_panoramise(self):
        chemin = _ecris(self.racine / "m.wav", 1, [10000] * 8)
        pcm, rate = audio._pcm_stereo(chemin, -1.0)
        ech = array.array("h"); ech.frombytes(pcm)
        gauche, droite = sound.stereo_gains(-1.0)
        self.assertEqual(rate, 44100)
        self.assertEqual(len(ech), 16, "8 trames mono -> 8 trames stereo")
        self.assertEqual(ech[0], int(round(10000 * gauche)))
        self.assertEqual(ech[1], int(round(10000 * droite)))

    def test_chaque_canal_stereo_garde_le_sien(self):
        """`c1=Rg*c0` jetterait le canal droit : c'est le bug corrige cote filtre."""
        chemin = _ecris(self.racine / "s.wav", 2, [(20000, 4000)] * 8)
        pcm, _ = audio._pcm_stereo(chemin, -0.9)
        ech = array.array("h"); ech.frombytes(pcm)
        gauche, droite = sound.stereo_gains(-0.9)
        self.assertEqual(ech[0], int(round(20000 * gauche)))
        self.assertEqual(ech[1], int(round(4000 * droite)),
                         "la droite vient de la droite")

    def test_le_centre_ne_touche_a_rien(self):
        chemin = _ecris(self.racine / "c.wav", 2, [(20000, 4000)] * 4)
        pcm, _ = audio._pcm_stereo(chemin, 0.0)
        ech = array.array("h"); ech.frombytes(pcm)
        self.assertEqual((ech[0], ech[1]), (20000, 4000))

    def test_les_deux_chemins_rendent_les_memes_octets(self):
        """La comparaison croisee, seule capable de voir une divergence.

        Les assertions ci-dessus reprennent la formule du code teste : une
        troncature au lieu d'un arrondi y passerait des deux cotes. Ici c'est la
        sortie native qui est comparee a celle de `pan_wav`, donc a l'autre
        implementation, et l'ecart d'une unite se voit.
        """
        # 7 et -9 sont choisis pour que l'arrondi et la troncature different
        # sur le canal attenue : sans eux les deux implementations tombent sur
        # les memes octets et le test ne prouverait rien.
        for canaux, trames in ((1, [10000, -7777, 7, -9, 32000] * 4),
                               (2, [(20000, 7), (-19999, -9), (5, -5)] * 4)):
            with self.subTest(canaux=canaux):
                source = _ecris(self.racine / ("x%d.wav" % canaux), canaux, trames)
                natif, _ = audio._pcm_stereo(source, -0.9)
                copie = sound.pan_wav(source, self.racine / ("p%d.wav" % canaux), -0.9)
                self.assertIsNotNone(copie)
                with wave.open(str(copie), "rb") as handle:
                    self.assertEqual(natif, handle.readframes(handle.getnframes()))

    def test_un_format_non_gere_rend_none(self):
        chemin = self.racine / "8bits.wav"
        with wave.open(str(chemin), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(1)
            handle.setframerate(44100)
            handle.writeframes(b"\x80" * 16)
        self.assertIsNone(audio._pcm_stereo(chemin, 0.0))

    def test_un_fichier_illisible_rend_none(self):
        chemin = self.racine / "pas-un-wav"
        chemin.write_bytes(b"doot")
        self.assertIsNone(audio._pcm_stereo(chemin, 0.0))


class ChoixDeLaSortie(unittest.TestCase):
    """PulseAudio d'abord, ALSA ensuite, repli sur le lecteur externe sinon."""

    def setUp(self):
        self.addCleanup(setattr, audio, "_SORTIES", audio._SORTIES)

    @staticmethod
    def _sortie(nom, dispo=True, casse=False):
        class Fausse:
            ouvertes = []

            @staticmethod
            def bibliotheque():
                return object() if dispo else None

            def __init__(self, rate):
                if casse:
                    raise OSError("indisponible")
                Fausse.ouvertes.append(rate)
                self.nom = nom

        Fausse.__name__ = nom
        return Fausse

    def test_la_premiere_qui_accepte_gagne(self):
        une, deux = self._sortie("Une"), self._sortie("Deux")
        audio._SORTIES = (une, deux)
        self.assertIsInstance(audio._ouvre(44100), une)

    def test_on_passe_a_la_suivante_si_la_premiere_refuse(self):
        une, deux = self._sortie("Une", casse=True), self._sortie("Deux")
        audio._SORTIES = (une, deux)
        self.assertIsInstance(audio._ouvre(44100), deux)

    def test_une_bibliotheque_absente_est_sautee(self):
        une, deux = self._sortie("Une", dispo=False), self._sortie("Deux")
        audio._SORTIES = (une, deux)
        self.assertIsInstance(audio._ouvre(44100), deux)

    def test_sans_aucune_sortie(self):
        audio._SORTIES = (self._sortie("Une", dispo=False),)
        self.assertIsNone(audio._ouvre(44100))
        self.assertFalse(audio.available())

    def test_play_rend_none_sans_sortie(self):
        audio._SORTIES = (self._sortie("Une", dispo=False),)
        with tempfile.TemporaryDirectory() as d:
            chemin = _ecris(Path(d) / "j.wav", 1, [1000] * 8)
            self.assertIsNone(audio.play(chemin, 0.0))


class EcritureAlsa(unittest.TestCase):
    """La reprise apres underrun doit finir par renoncer.

    `snd_pcm_writei` peut rendre moins de trames que demande, et -EPIPE tant
    que le peripherique sous-alimente. Reprendre est juste ; reprendre sans
    fin brulerait un coeur dans un fil daemon, et l'`atexit` attendrait ses
    cinq secondes par-dessus sans que rien ne sorte.
    """

    # Sans borne cote code teste, la boucle ne rend jamais la main : un test qui
    # pend est pire qu'un test rouge, surtout en CI. La fausse bibliotheque
    # coupe donc d'elle-meme, pour qu'une regression echoue au lieu de tourner.
    GARDE_FOU = 200

    class FausseLib:
        """Un `libasound` qui rend ce qu'on lui dit, tour par tour."""

        def __init__(self, retours, garde):
            self.retours = list(retours)
            self.garde = garde
            self.demandes = []
            self.relances = 0

        def snd_pcm_writei(self, _pcm, _bloc, trames):
            self.demandes.append(trames)
            if len(self.demandes) > self.garde:
                raise AssertionError(
                    f"{self.garde} appels sans que write() rende la main : "
                    "la reprise n'est plus bornee")
            rendu = self.retours.pop(0) if self.retours else 0
            return trames if rendu == "tout" else rendu

        def snd_pcm_prepare(self, _pcm):
            self.relances += 1

    def _sortie(self, retours):
        sortie = object.__new__(audio._SortieAlsa)
        sortie.lib = self.FausseLib(retours, self.GARDE_FOU)
        sortie.pcm = None
        return sortie

    @staticmethod
    def _bloc(trames):
        return bytes(trames * 4)

    def test_une_ecriture_partielle_est_reprise(self):
        sortie = self._sortie([4, 4, 2])
        self.assertTrue(sortie.write(self._bloc(10)))
        self.assertEqual(sortie.lib.demandes, [10, 6, 2], "le reste seulement")

    def test_un_underrun_est_repris(self):
        sortie = self._sortie([-audio.EPIPE, "tout"])
        self.assertTrue(sortie.write(self._bloc(10)))
        self.assertEqual(sortie.lib.relances, 1)

    def test_un_underrun_perpetuel_finit_par_renoncer(self):
        """Le cas qui bouclait : -EPIPE a chaque tour, `pose` immobile."""
        sortie = self._sortie([-audio.EPIPE] * 500)
        self.assertFalse(sortie.write(self._bloc(10)))
        self.assertLessEqual(len(sortie.lib.demandes), audio.REPRISES + 1)

    def test_zero_trame_ecrite_finit_par_renoncer(self):
        """L'autre facon de ne pas avancer, sans erreur pour le dire."""
        sortie = self._sortie([0] * 500)
        self.assertFalse(sortie.write(self._bloc(10)))
        self.assertLessEqual(len(sortie.lib.demandes), audio.REPRISES + 1)
        self.assertEqual(sortie.lib.relances, 0, "rien a relancer sans underrun")

    def test_une_erreur_franche_abandonne_aussitot(self):
        sortie = self._sortie([-5])          # EIO : on ne sait pas en revenir
        self.assertFalse(sortie.write(self._bloc(10)))
        self.assertEqual(len(sortie.lib.demandes), 1)
        self.assertEqual(sortie.lib.relances, 0)

    def test_une_lecture_qui_avance_par_a_coups_va_au_bout(self):
        """Le compteur ne retient que les tours sans progres.

        Un peripherique qui se relance souvent mais avance entre deux doit
        aller jusqu'au bout, meme au-dela de `REPRISES` underruns au total.
        """
        saccade = []
        for _ in range(audio.REPRISES + 4):
            saccade += [-audio.EPIPE, 1]
        sortie = self._sortie(saccade)
        self.assertTrue(sortie.write(self._bloc(audio.REPRISES + 4)))
        self.assertEqual(sortie.lib.relances, audio.REPRISES + 4)


class Arret(unittest.TestCase):

    def test_stop_all_sans_rien_en_cours(self):
        audio.stop_all()          # ne doit pas lever

    def test_une_lecture_neuve_n_est_pas_arretee(self):
        lecture = audio.Lecture()
        self.assertFalse(lecture._arret.is_set())
        lecture.stop()
        self.assertTrue(lecture._arret.is_set())


if __name__ == "__main__":
    unittest.main()
