"""Mise a jour d'une installation existante.

Rien ici ne touche au reseau ni ne lance d'installeur : ce qui est verifie,
c'est la fiche d'installation, le choix de la voie de mise a jour et les
refus. Le telechargement reel est remplace la ou il apparait.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from doot import cli, update


class UpdateTestCase(unittest.TestCase):
    """Isole le dossier de donnees, donc la fiche."""

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        root = Path(self._dir.name)
        self.paths = {
            "data": root,
            "sound": root / "sound",
            "image": root / "image",
            "wav": root / "doot.wav",
            "log": root / "doot.log",
            "pid": root / "doot.pid",
        }
        patch = mock.patch.object(cli, "paths", lambda: self.paths)
        patch.start()
        self.addCleanup(patch.stop)
        self.root = root

    def tearDown(self):
        self._dir.cleanup()


class Fiche(UpdateTestCase):
    """La fiche laissee par l'installeur."""

    def test_absente_rend_un_dictionnaire_vide(self):
        self.assertEqual(update.read_record(), {})

    def test_aller_retour(self):
        donnees = {"source": "/chemin", "commit": "abc123", "min": 300, "max": 900,
                   "autostart": True}
        update.write_record(donnees)
        self.assertEqual(update.read_record(), donnees)

    def test_fiche_illisible_ne_plante_pas(self):
        update.record_path().write_text("{ pas du json", encoding="utf-8")
        self.assertEqual(update.read_record(), {})

    def test_fiche_avec_BOM(self):
        """install.ps1 passe par PowerShell 5.1, qui ecrit l'UTF-8 avec un BOM.

        json.loads refuse ce caractere invisible : lue en utf-8 strict, la
        fiche revenait vide et --check-update annoncait un commit inconnu sur
        une installation pourtant parfaitement enregistree.
        """
        contenu = json.dumps({"commit": "f" * 40, "min": 600})
        update.record_path().write_bytes(b"\xef\xbb\xbf" + contenu.encode("utf-8"))
        self.assertEqual(update.read_record().get("commit"), "f" * 40)
        self.assertEqual(update.local_sha(), "f" * 40)

    def test_commit_lu_dans_la_fiche(self):
        update.write_record({"commit": "0123456789abcdef"})
        self.assertEqual(update.local_sha(), "0123456789abcdef")

    def test_sans_commit_ni_source(self):
        update.write_record({"min": 600})
        self.assertIsNone(update.local_sha())

    def test_ecrite_en_utf8_lisible(self):
        update.write_record({"source": "/home/utilisateur/depot"})
        contenu = json.loads(update.record_path().read_text(encoding="utf-8"))
        self.assertEqual(contenu["source"], "/home/utilisateur/depot")


class Comparaison(UpdateTestCase):
    """`--check-update`, sans reseau."""

    def test_a_jour(self):
        update.write_record({"commit": "a" * 40})
        with mock.patch.object(update, "remote_sha", lambda: "a" * 40):
            self.assertEqual(update.check(verbose=lambda *a: None), 0)

    def test_en_retard(self):
        update.write_record({"commit": "a" * 40})
        with mock.patch.object(update, "remote_sha", lambda: "b" * 40):
            self.assertEqual(update.check(verbose=lambda *a: None), 1)

    def test_reseau_injoignable(self):
        update.write_record({"commit": "a" * 40})
        with mock.patch.object(update, "remote_sha", lambda: None):
            self.assertEqual(update.check(verbose=lambda *a: None), 2)

    def test_commit_inconnu_compare_les_versions(self):
        """Installe depuis une release : pas de commit, mais un numero.

        Sans ce recours, --check-update ne repondait jamais rien d'utile a qui
        avait installe depuis une release, faute de depot git.
        """
        from doot import __version__

        with mock.patch.object(update, "latest_release", lambda: __version__):
            self.assertEqual(update.check(verbose=lambda *a: None), 0)

    def test_version_en_retard(self):
        with mock.patch.object(update, "latest_release", lambda: "99.0.0"):
            self.assertEqual(update.check(verbose=lambda *a: None), 1)

    def test_aucune_release_publiee(self):
        with mock.patch.object(update, "latest_release", lambda: None):
            self.assertEqual(update.check(verbose=lambda *a: None), 2)

    def test_le_commit_prime_sur_la_version(self):
        """Avec un commit connu, on compare les commits, c'est plus precis."""
        update.write_record({"commit": "a" * 40})
        appels = []
        with mock.patch.object(update, "remote_sha", lambda: "a" * 40), \
             mock.patch.object(update, "latest_release",
                               lambda: appels.append(1) or "0.0.1"):
            self.assertEqual(update.check(verbose=lambda *a: None), 0)
        self.assertEqual(appels, [], "la version ne devrait pas etre interrogee")

    def test_etiquette_sans_v(self):
        """tag_name vaut vX.Y.Z, la comparaison porte sur X.Y.Z."""
        donnees = {"tag_name": "v1.2.3"}
        with mock.patch.object(update, "_api", lambda url: donnees):
            self.assertEqual(update.latest_release(), "1.2.3")

    def test_release_injoignable(self):
        with mock.patch.object(update, "_api", lambda url: None):
            self.assertIsNone(update.latest_release())


class ChoixDeLaVoie(UpdateTestCase):
    """Depot git s'il est la, archive sinon."""

    def test_sans_source_on_telecharge(self):
        appels = []

        def faux_telechargement(destination):
            appels.append(destination)
            return destination / "doot-main"

        with mock.patch.object(update, "download_source", faux_telechargement):
            source, voie = update.refresh_source({}, self.root, verbose=lambda *a: None)
        self.assertEqual(voie, "archive")
        self.assertEqual(len(appels), 1)

    def test_source_sans_git_on_telecharge(self):
        depot = self.root / "clone_sans_git"
        depot.mkdir()
        with mock.patch.object(update, "download_source",
                               lambda d: d / "doot-main") as _:
            source, voie = update.refresh_source({"source": str(depot)}, self.root,
                                                 verbose=lambda *a: None)
        self.assertEqual(voie, "archive")

    def test_source_git_on_tire(self):
        depot = self.root / "clone"
        (depot / ".git").mkdir(parents=True)
        faux = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(update.shutil, "which", lambda n: "/usr/bin/git"), \
             mock.patch.object(update.subprocess, "run", return_value=faux):
            source, voie = update.refresh_source({"source": str(depot)}, self.root,
                                                 verbose=lambda *a: None)
        self.assertEqual(voie, "git pull")
        self.assertEqual(source, depot)

    def test_git_en_echec_bascule_sur_l_archive(self):
        depot = self.root / "clone"
        (depot / ".git").mkdir(parents=True)
        faux = mock.Mock(returncode=1, stdout="", stderr="divergence")
        with mock.patch.object(update.shutil, "which", lambda n: "/usr/bin/git"), \
             mock.patch.object(update.subprocess, "run", return_value=faux), \
             mock.patch.object(update, "download_source", lambda d: d / "doot-main"):
            source, voie = update.refresh_source({"source": str(depot)}, self.root,
                                                 verbose=lambda *a: None)
        self.assertEqual(voie, "archive")


class Installeur(UpdateTestCase):
    """La commande construite pour rejouer l'installeur."""

    def commande_pour(self, fiche):
        source = self.root / "src"
        source.mkdir(exist_ok=True)
        script = "install.ps1" if sys.platform == "win32" else "install.sh"
        (source / script).write_text("#", encoding="utf-8")

        vues = []
        faux = mock.Mock(returncode=0, stdout="", stderr="")

        def espion(commande, **kwargs):
            vues.append(commande)
            return faux

        with mock.patch.object(update.subprocess, "run", espion):
            update.run_installer(source, fiche, verbose=lambda *a: None)
        return vues[0]

    def test_les_options_sont_reprises(self):
        commande = self.commande_pour({"min": 42, "max": 99, "autostart": True})
        self.assertIn("42", commande)
        self.assertIn("99", commande)

    def test_sans_autostart(self):
        commande = self.commande_pour({"min": 1, "max": 2, "autostart": False})
        attendu = "-NoAutostart" if sys.platform == "win32" else "--no-autostart"
        self.assertIn(attendu, commande)

    def test_avec_autostart_pas_de_drapeau(self):
        commande = self.commande_pour({"min": 1, "max": 2, "autostart": True})
        for interdit in ("-NoAutostart", "--no-autostart"):
            self.assertNotIn(interdit, commande)

    def test_la_salve_est_reprise(self):
        commande = self.commande_pour({"min": 1, "max": 2, "burst_min": 2,
                                       "burst_max": 5, "burst_delay": 1.5})
        drapeau = "-BurstMax" if sys.platform == "win32" else "--burst-max"
        self.assertIn(drapeau, commande)
        self.assertEqual(commande[commande.index(drapeau) + 1], "5")

    def test_la_formation_est_reprise(self):
        commande = self.commande_pour({"min": 1, "max": 2, "formation": "canon"})
        drapeau = "-Formation" if sys.platform == "win32" else "--formation"
        self.assertIn(drapeau, commande)
        self.assertEqual(commande[commande.index(drapeau) + 1], "canon")

    def test_fiche_d_avant_les_salves_ne_change_rien(self):
        """Le cas de toutes les installations existantes."""
        commande = self.commande_pour({"min": 1, "max": 2, "autostart": True})
        for interdit in ("-BurstMin", "-BurstMax", "-BurstDelay",
                         "--burst-min", "--burst-max", "--burst-delay"):
            self.assertNotIn(interdit, commande)

    def test_salve_a_un_ne_met_aucun_drapeau(self):
        commande = self.commande_pour({"burst_min": 1, "burst_max": 1})
        for interdit in ("-BurstMax", "--burst-max"):
            self.assertNotIn(interdit, commande)

    def test_installeur_manquant(self):
        source = self.root / "vide"
        source.mkdir()
        with self.assertRaises(update.UpdateError):
            update.run_installer(source, {}, verbose=lambda *a: None)

    def test_echec_de_l_installeur_remonte(self):
        source = self.root / "src2"
        source.mkdir()
        script = "install.ps1" if sys.platform == "win32" else "install.sh"
        (source / script).write_text("#", encoding="utf-8")
        faux = mock.Mock(returncode=1, stdout="", stderr="ca a casse")
        with mock.patch.object(update.subprocess, "run", return_value=faux):
            with self.assertRaises(update.UpdateError):
                update.run_installer(source, {}, verbose=lambda *a: None)


class Salve(UpdateTestCase):
    """Ce que la fiche dit des salves, et ce qu'on en fait."""

    def test_fiche_muette_ne_demande_rien(self):
        self.assertIsNone(update.salve_reglee({}))

    def test_une_seule_apparition_ne_demande_rien(self):
        """1 a 1, c'est le defaut : inutile de l'ecrire dans la commande."""
        self.assertIsNone(update.salve_reglee({"burst_min": 1, "burst_max": 1}))

    def test_bornes_reprises(self):
        self.assertEqual(
            update.salve_reglee({"burst_min": 2, "burst_max": 5, "burst_delay": 1.5}),
            ("2", "5", "1.5"),
        )

    def test_les_defauts_completent(self):
        self.assertEqual(update.salve_reglee({"burst_max": 4}), ("1", "4", "0.6"))

    def test_fiche_abimee_ne_fait_pas_echouer(self):
        """Une valeur illisible vaut mieux qu'une mise a jour qui s'arrete."""
        self.assertIsNone(update.salve_reglee({"burst_max": "oups"}))
        self.assertIsNone(update.salve_reglee({"burst_max": None}))
        self.assertIsNone(update.salve_reglee({"burst_max": 5, "burst_delay": "?"}))


class Formation(UpdateTestCase):
    """Ce que la fiche d'installation dit de la choregraphie."""

    def test_fiche_muette_ne_demande_rien(self):
        self.assertIsNone(update.formation_reglee({}))

    def test_canon_est_repris(self):
        self.assertEqual(update.formation_reglee({"formation": "canon"}), "canon")

    def test_random_reste_le_defaut_silencieux(self):
        self.assertIsNone(update.formation_reglee({"formation": "random"}))

    def test_formation_inconnue_est_ignoree(self):
        self.assertIsNone(update.formation_reglee({"formation": "parade"}))


class InstallationSysteme(UpdateTestCase):
    """Une installation par paquet ne doit pas etre ecrasee par --update."""

    def test_refus_si_paquet_systeme(self):
        with mock.patch.object(update, "managed_elsewhere", lambda: "pacman"):
            self.assertEqual(update.update(verbose=lambda *a: None), 3)

    def test_chemin_utilisateur_accepte(self):
        """Le module tourne ici depuis le depot : ce n'est pas un paquet systeme."""
        if sys.platform == "win32":
            self.assertIsNone(update.managed_elsewhere())


if __name__ == "__main__":
    unittest.main()
