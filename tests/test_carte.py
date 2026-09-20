"""Le rite du dernier soir, la fonte maison et la carte qu'elle imprime."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from doot import carte, cli, codex, evenements, png, police, season, succes, window


def etat_type() -> dict:
    return {
        "machine": "aaaa11112222",
        "stats": {
            "doots": {"aaaa11112222": 412, "bbbb33334444": 238},
            "melodies": {"aaaa11112222": 30},
            "evenements": {"aaaa11112222": 8},
            "plus_grande_salve": 7,
            "evenements_vus": ["parade", "mimic"],
            "jours_actifs": ["2026-09-01", "2026-09-30", "2026-10-31"],
        },
        "succes": {
            "premier_doot": "2026-09-01T21:00:00",
            "dix_doots": "2026-09-02T21:00:00",
        },
    }


class Fonte(unittest.TestCase):
    def test_chaque_signe_fait_cinq_sur_sept(self):
        for signe, dessin in police._DESSINS.items():
            with self.subTest(signe=signe):
                self.assertEqual(len(dessin), police.HAUTEUR)
                for ligne in dessin:
                    self.assertEqual(len(ligne), police.LARGEUR)
                    self.assertEqual(set(ligne) - {"#", "."}, set())

    def test_les_minuscules_montent_en_capitales(self):
        self.assertEqual(police.normaliser("doot"), "DOOT")

    def test_un_accent_garde_sa_lettre(self):
        """"MELODIE" vaut mieux qu'un trou au milieu du mot."""

        self.assertEqual(police.normaliser("mélodie jouée"), "MELODIE JOUEE")

    def test_un_signe_inconnu_devient_une_espace(self):
        self.assertEqual(police.normaliser("a☃b"), "A B")

    def test_la_largeur_annoncee_est_celle_qui_est_ecrite(self):
        toile = png.Toile(400, 40, (0, 0, 0, 255))
        ecrite = police.ecrire(toile, "DOOT 2026", 5, 5, (255, 255, 255, 255), 2)
        self.assertEqual(ecrite, police.largeur("DOOT 2026", 2))
        colonnes = [
            x for x in range(400)
            if any(toile.data[(y * 400 + x) * 4 + 3] and
                   toile.data[(y * 400 + x) * 4] == 255 for y in range(40))
        ]
        self.assertLessEqual(max(colonnes), 5 + ecrite)

    def test_un_texte_vide_ne_prend_pas_de_place(self):
        self.assertEqual(police.largeur(""), 0)

    def test_le_texte_centre_l_est_vraiment(self):
        toile = png.Toile(200, 20, (0, 0, 0, 255))
        police.centrer(toile, "OS", 5, (255, 255, 255, 255), 1)
        allumees = [
            x for x in range(200)
            if any(toile.data[(y * 200 + x) * 4] == 255 for y in range(20))
        ]
        self.assertAlmostEqual((min(allumees) + max(allumees)) / 2, 100, delta=2)


class Toile(unittest.TestCase):
    def test_un_aplat_translucide_voile_le_fond_au_lieu_de_le_percer(self):
        """Deux facons d'empiler dans la meme classe seraient un piege."""

        toile = png.Toile(4, 4, (0, 0, 0, 255))
        toile.rectangle(0, 0, 2, 2, (255, 255, 255, 128))
        self.assertEqual(toile.data[3], 255)
        self.assertEqual(toile.data[0], 128)

    def test_ce_qui_deborde_est_rogne_et_non_refuse(self):
        toile = png.Toile(4, 4)
        toile.rectangle(-10, -10, 100, 100, (10, 20, 30, 255))
        toile.coller(png.Toile(8, 8, (1, 2, 3, 255)).frame(), 2, 2)
        self.assertEqual(toile.frame().width, 4)

    def test_une_toile_sans_dimension_est_refusee(self):
        with self.assertRaises(ValueError):
            png.Toile(0, 10)


class LaDerniereNuit(unittest.TestCase):
    def test_le_soir_du_31_octobre_ferme_la_saison(self):
        self.assertTrue(season.is_last_night(datetime(2026, 10, 31, 20, 0)))
        self.assertTrue(season.is_last_night(datetime(2026, 10, 31, 23, 59)))

    def test_le_matin_du_31_est_encore_un_jour_ordinaire(self):
        self.assertFalse(season.is_last_night(datetime(2026, 10, 31, 10, 0)))

    def test_la_veille_ne_ferme_rien(self):
        self.assertFalse(season.is_last_night(datetime(2026, 10, 30, 22, 0)))

    def test_la_finale_ne_se_tire_pas_au_sort(self):
        """Elle salue une fermeture : un 12 septembre lui oterait tout son sens."""

        tirables = [item.identifiant for item in evenements.tirables()]
        self.assertNotIn("finale", tirables)
        self.assertIsNotNone(evenements.find("finale"))

    def test_la_finale_a_son_entree_au_codex(self):
        self.assertIn("finale", {item.identifiant for item in codex.CATALOGUE})


class RiteDuSoir(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.addCleanup(self.dossier.cleanup)
        racine = Path(self.dossier.name)
        patch = mock.patch.object(cli, "paths", return_value={
            "data": racine, "state": racine / "state.json", "log": racine / "doot.log",
        })
        patch.start()
        self.addCleanup(patch.stop)
        self.args = cli.parse_args(["--quiet"])

    def rite(self, moment, args=None):
        with mock.patch.object(season, "datetime") as horloge:
            horloge.now.return_value = moment
            return cli.rite_du_soir(args or self.args)

    def test_le_rite_attend_le_dernier_soir(self):
        self.assertIsNone(self.rite(datetime(2026, 10, 31, 10, 0)))
        self.assertIsNotNone(self.rite(datetime(2026, 10, 31, 20, 0)))

    def test_le_rite_n_a_lieu_qu_une_fois_par_saison(self):
        """Un daemon relance dans la soiree ne doit pas le rejouer."""

        cli.write_state({"rite_saison": 2026})
        self.assertIsNone(self.rite(datetime(2026, 10, 31, 22, 0)))

    def test_le_rite_de_l_an_dernier_ne_vaut_pas_pour_celui_ci(self):
        cli.write_state({"rite_saison": 2025})
        self.assertIsNotNone(self.rite(datetime(2026, 10, 31, 22, 0)))

    def test_un_poste_sans_rencontres_n_a_pas_de_rite(self):
        muet = cli.parse_args(["--quiet", "--no-event"])
        self.assertIsNone(self.rite(datetime(2026, 10, 31, 22, 0), muet))

    def test_ignorer_la_saison_ne_prive_pas_du_rite(self):
        """La date est la meme pour qui fait tourner doot toute l'annee."""

        hors = cli.parse_args(["--quiet", "--ignore-season"])
        self.assertIsNotNone(self.rite(datetime(2026, 10, 31, 21, 0), hors))

    def test_clore_la_saison_note_le_rite_et_laisse_la_carte(self):
        cli.write_state(etat_type())
        chemin = cli.clore_la_saison(self.args, 2026)
        self.assertEqual(cli.read_state()["rite_saison"], 2026)
        self.assertTrue(chemin.is_file())
        self.assertEqual(chemin.name, "doot-saison-2026.png")

    def test_une_carte_impossible_ne_rejoue_pas_le_rite(self):
        """La crypte a ferme ; seule l'image manque."""

        cli.write_state(etat_type())
        with mock.patch.object(carte, "ecrire", side_effect=OSError("disque plein")):
            self.assertIsNone(cli.clore_la_saison(self.args, 2026))
        self.assertEqual(cli.read_state()["rite_saison"], 2026)


class RiteInterrompu(unittest.TestCase):
    """La ceremonie peut casser en route sans avoir a etre rejouee."""

    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.addCleanup(self.dossier.cleanup)
        racine = Path(self.dossier.name)
        patch = mock.patch.object(cli, "paths", return_value={
            "data": racine, "state": racine / "state.json", "log": racine / "doot.log",
        })
        patch.start()
        self.addCleanup(patch.stop)
        # Les douze doots de la finale debloquent des succes, et chaque medaille
        # rend sa fanfare avant de s'afficher : trois secondes par test sur un
        # dossier neuf. L'annonce ne fait pas partie de ce qu'on verifie ici,
        # l'enregistrement dans l'etat si - et il a lieu avant elle.
        muet = mock.patch.object(cli, "annoncer_succes", lambda *a, **k: None)
        muet.start()
        self.addCleanup(muet.stop)
        # Ces tests portent sur le marqueur, pas sur l'image. La dessiner pour
        # de vrai decode chaque badge en Python pur et coute onze secondes pour
        # trois cas ; `CarteDeSaison` la verifie deja une fois, ce qui suffit.
        sans_image = mock.patch.object(carte, "ecrire", return_value=Path("carte.png"))
        sans_image.start()
        self.addCleanup(sans_image.stop)
        self.args = cli.parse_args(["--quiet"])

    def finale(self, casse_a=None):
        """Joue la finale, en cassant l'affichage a la n-ieme fenetre."""

        vues = {"n": 0}

        def show(**_):
            vues["n"] += 1
            if casse_a is not None and vues["n"] == casse_a:
                raise RuntimeError("ecran perdu")

        with mock.patch.object(window, "show", side_effect=show), \
             mock.patch.object(cli, "resolve_media", return_value=(None, None, 0.0)):
            try:
                cli.jouer_le_rite(self.args, evenements.find("finale"))
            except RuntimeError:
                pass
        return vues["n"]

    def rejouerait(self):
        with mock.patch.object(season, "datetime") as horloge:
            horloge.now.return_value = datetime(2026, 10, 31, 22, 0)
            return cli.rite_du_soir(self.args) is not None

    def test_une_panne_en_cours_de_ceremonie_la_cloture_quand_meme(self):
        """Sinon la finale repart a chaque declenchement jusqu'a minuit.

        `emit_doots` compte les squelettes deja montres dans son `finally` ; la
        cloture doit suivre le meme chemin, sans quoi l'etat retient les doots
        et oublie que la crypte a ferme.
        """
        self.finale(casse_a=2)
        self.assertEqual(cli.read_state().get("rite_saison"), 2026)
        self.assertFalse(self.rejouerait())

    def test_une_panne_avant_le_premier_doot_laisse_la_saison_ouverte(self):
        """Aucun squelette montre n'est pas une ceremonie : on retentera."""

        self.finale(casse_a=1)
        self.assertNotIn("rite_saison", cli.read_state())
        self.assertTrue(self.rejouerait())

    def test_une_ceremonie_complete_ferme_la_saison(self):
        montres = self.finale()
        self.assertEqual(montres, evenements.find("finale").quantite)
        self.assertEqual(cli.read_state().get("rite_saison"), 2026)
        self.assertFalse(self.rejouerait())


class CarteDeSaison(unittest.TestCase):
    def test_la_carte_est_un_png_relisible(self):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = carte.ecrire(dossier, etat_type(), 2026)
            largeur, hauteur = png.size(chemin)
        self.assertEqual(largeur, carte.LARGEUR)
        self.assertGreater(hauteur, 200)

    def test_un_chemin_complet_est_pris_tel_quel(self):
        with tempfile.TemporaryDirectory() as dossier:
            voulu = Path(dossier) / "ma-saison.png"
            self.assertEqual(carte.ecrire(voulu, etat_type(), 2026), voulu)
            self.assertTrue(voulu.is_file())

    def test_une_saison_vide_se_dessine_quand_meme(self):
        """Personne ne doit voir une trace de pile en demandant sa carte."""

        frame = carte.dessiner({}, 2026)
        self.assertEqual(frame.width, carte.LARGEUR)

    def test_les_totaux_a_zero_ne_font_pas_de_ligne(self):
        pleine = dict(carte._lignes(*self._bilan(etat_type())))
        self.assertEqual(pleine["DOOTS"], "650")  # les parts des deux machines
        self.assertEqual(pleine["SOIRS"], "3 / 61")
        self.assertEqual(carte._lignes(*self._bilan({})), [])

    def test_seuls_les_succes_gagnes_apportent_leur_badge(self):
        self.assertEqual(len(carte._badges(etat_type())), 2)
        self.assertEqual(carte._badges({}), [])

    def test_un_badge_manquant_ne_casse_pas_la_carte(self):
        with mock.patch.object(succes, "badge", return_value=None):
            self.assertEqual(carte._badges(etat_type()), [])
            self.assertEqual(carte.dessiner(etat_type(), 2026).width, carte.LARGEUR)

    def _bilan(self, etat):
        from doot import registre

        return registre.resume(etat), registre.saison(etat, 2026)


class CommandeCarte(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.addCleanup(self.dossier.cleanup)
        racine = Path(self.dossier.name)
        patch = mock.patch.object(cli, "paths", return_value={
            "data": racine, "state": racine / "state.json", "log": racine / "doot.log",
        })
        patch.start()
        self.addCleanup(patch.stop)
        cli.write_state(etat_type())

    def test_sans_chemin_la_carte_va_dans_le_dossier_de_donnees(self):
        with mock.patch("sys.stdout"):
            self.assertEqual(cli.do_carte(cli.parse_args(["--carte"]), ""), 0)
        annee = season.last_season_year()
        self.assertTrue((Path(self.dossier.name) / f"doot-saison-{annee}.png").is_file())

    def test_un_dossier_illisible_se_dit_au_lieu_de_lever(self):
        with mock.patch.object(carte, "ecrire", side_effect=OSError("lecture seule")), \
             mock.patch("sys.stdout"):
            self.assertEqual(cli.do_carte(self.args_carte(), "/nulle/part"), 2)

    def args_carte(self):
        return cli.parse_args(["--carte"])


if __name__ == "__main__":
    unittest.main()
