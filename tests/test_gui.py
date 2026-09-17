"""Le grimoire graphique compose fidelement des commandes CLI."""

from __future__ import annotations

import unittest
from unittest import mock

from doot import cli, gui


class CatalogueGraphique(unittest.TestCase):
    def test_les_actions_principales_sont_toutes_visibles(self):
        options = gui.COMMAND_OPTIONS
        attendues = {
            "--once", "--play", "--rickroll", "--melodies", "--sync-init",
            "--sync-join", "--sync-endpoint", "--sync-region",
            "--export", "--merge", "--achievements", "--events", "--event",
            "--status", "--stop", "--paths", "--art", "--update",
            "--check-update", "--profiles", "--save-profile",
            "--activate-profile", "--deactivate-profile", "--delete-profile",
            "--screens", "--regen-sound", "--version", "--help", "--gui",
        }
        self.assertEqual(options, attendues)

    def test_tous_les_autres_drapeaux_deviennent_des_reglages(self):
        parser = cli.build_parser()
        reglages = {spec.option for spec in gui.option_specs(parser)}
        visibles = reglages | gui.COMMAND_OPTIONS
        longs = {
            option
            for action in parser._actions
            for option in action.option_strings
            if option.startswith("--") and option not in {"--exporter", "--fusionner", "--succes"}
        }
        self.assertEqual(visibles, longs)
        self.assertIn("--formation", reglages)
        self.assertIn("--ignore-season", reglages)

    def test_chaque_commande_a_son_illustration_embarquee(self):
        absentes = [
            command.image for command in gui.COMMANDS
            if not (gui.ASSETS_DIR / command.image).is_file()
        ]
        self.assertEqual(absentes, [])


class CompositionCommande(unittest.TestCase):
    def setUp(self):
        self.settings = gui.option_specs(cli.build_parser())

    def command(self, key):
        return next(command for command in gui.COMMANDS if command.key == key)

    def test_une_action_et_ses_reglages_forment_argv(self):
        argv = gui.build_command_argv(
            self.command("once"), {},
            {"formation": "wave", "ignore_season": True, "volume": "0.8"},
            self.settings,
        )
        self.assertEqual(
            argv,
            ["--once", "--formation", "wave", "--volume", "0.8", "--ignore-season"],
        )
        parsed = cli.build_parser().parse_args(argv)
        self.assertTrue(parsed.once)
        self.assertEqual(parsed.formation, "wave")

    def test_un_parametre_obligatoire_manquant_est_refuse(self):
        with self.assertRaisesRegex(ValueError, "Melodie"):
            gui.build_command_argv(self.command("play"), {}, {}, self.settings)

    def test_la_fusion_accepte_plusieurs_sources(self):
        argv = gui.build_command_argv(
            self.command("merge"),
            {"--merge": "partage-a ; C:/Mes fichiers/partage-b"}, {}, self.settings,
        )
        self.assertEqual(
            argv,
            ["--merge", "partage-a", "C:/Mes fichiers/partage-b"],
        )

    def test_l_apercu_protege_les_chemins_avec_espaces(self):
        texte = gui.format_command(["--image", "C:/Mes images/doot.png"])
        self.assertIn("C:/Mes images/doot.png", texte)


class EntreeCli(unittest.TestCase):
    def test_gui_delegue_au_lanceur_sans_preparer_le_daemon(self):
        with mock.patch.object(gui, "main", return_value=27) as lancer:
            self.assertEqual(cli.main(["--gui"]), 27)
        lancer.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
