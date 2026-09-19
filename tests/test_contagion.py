"""Le Codex, les signaux de flotte et les nouvelles anomalies."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from doot import cli, codex, contagion, evenements, notification, partage, window


class Signaux(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)

    def test_un_signal_frais_est_recu_une_seule_fois(self):
        signal = contagion.creer("portable", self.now, token="abc")
        etat = {"machine": "fixe"}
        self.assertTrue(contagion.recevoir(etat, signal, self.now))
        self.assertFalse(contagion.recevoir(etat, signal, self.now))
        self.assertEqual(contagion.vider(etat, self.now), [signal])
        self.assertEqual(contagion.vider(etat, self.now), [])

    def test_un_signal_perime_ou_local_est_ignore(self):
        vieux = contagion.creer(
            "portable", self.now - timedelta(seconds=contagion.TTL_SECONDS + 1),
            token="vieux",
        )
        self.assertFalse(contagion.valide(vieux, self.now))
        local = contagion.creer("fixe", self.now, token="local")
        self.assertFalse(contagion.recevoir({"machine": "fixe"}, local, self.now))

    def test_le_signal_ne_part_que_dans_le_partage_automatique(self):
        signal = contagion.creer("fixe", token="partage")
        etat = {"machine": "fixe", "contagion_sortante": signal}
        self.assertNotIn("contagion", partage.part_exportable(etat))
        self.assertEqual(
            partage.part_exportable(etat, avec_contagion=True)["contagion"], signal,
        )


class LivreDesRencontres(unittest.TestCase):
    def test_le_codex_cache_ce_qui_n_a_pas_ete_vu(self):
        etat = {"stats": {"evenements_vus": ["duel", "mimic"]}}
        self.assertEqual(codex.vus(etat), {"duel", "mimic"})
        self.assertEqual(codex.progression(etat), (2, len(codex.CATALOGUE)))

    def test_les_trois_nouvelles_rencontres_sont_forceables(self):
        self.assertEqual(evenements.find("duel").formation, "duel")
        self.assertEqual(evenements.find("mimic").mise_en_scene, "mimic")
        self.assertEqual(evenements.find("faux-bug").mise_en_scene, "faux-bug")

    def test_le_duel_alterne_les_deux_bords(self):
        args = cli.build_parser().parse_args(["--formation", "duel"])
        with mock.patch.object(window, "active_monitors", return_value=[object()]):
            plan = cli.formation_plan(args, 6)
        self.assertEqual(
            [etape["side"] for etape in plan],
            ["left", "right", "left", "right", "left", "right"],
        )


class MiseEnScene(unittest.TestCase):
    def test_le_faux_bug_tremble_puis_tombe(self):
        avant = window.glitch_position(500, 4000, 100, 200, 1080, 120)
        fin = window.glitch_position(4000, 4000, 100, 200, 1080, 120)
        self.assertLessEqual(abs(avant[0] - 100), 4)
        self.assertGreater(fin[1], 1080)

    def test_le_mimic_a_plusieurs_mensonges(self):
        self.assertGreaterEqual(len(notification.MIMIC_MESSAGES), 3)

    def test_le_mimic_affiche_son_mensonge_avant_le_doot(self):
        args = cli.build_parser().parse_args(["--quiet"])
        evenement = evenements.find("mimic")
        ordre = []
        with mock.patch.object(
            notification, "show_mimic", side_effect=lambda: ordre.append("mimic"),
        ), mock.patch.object(
            cli, "emit_doots", side_effect=lambda *_args, **_kwargs: ordre.append("doot") or 1,
        ):
            self.assertTrue(cli.emit_evenement(args, evenement))
        self.assertEqual(ordre, ["mimic", "doot"])


if __name__ == "__main__":
    unittest.main()
