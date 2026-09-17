"""Progression locale, robuste et deterministe des succes."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from doot import png, succes


class Enregistrement(unittest.TestCase):
    def setUp(self):
        self.etat = {}
        self.maintenant = datetime(2026, 9, 17, 20, 30)

    def ids(self, nouveaux):
        return {item.identifiant for item in nouveaux}

    def test_premier_doot_debloque_le_premier_succes(self):
        nouveaux = succes.enregistrer(
            self.etat, "doots", self.maintenant, quantite=1,
            formation="random", spin=False, bord=None,
        )
        self.assertIn("premier_doot", self.ids(nouveaux))
        self.assertEqual(self.etat["stats"]["doots"], 1)
        self.assertEqual(succes.score(self.etat), 5)

    def test_un_succes_n_est_annonce_qu_une_fois(self):
        premier = succes.enregistrer(self.etat, "doots", self.maintenant, quantite=1)
        second = succes.enregistrer(self.etat, "doots", self.maintenant, quantite=1)
        self.assertIn("premier_doot", self.ids(premier))
        self.assertNotIn("premier_doot", self.ids(second))

    def test_salve_canon(self):
        nouveaux = succes.enregistrer(
            self.etat, "doots", self.maintenant, quantite=4, formation="canon"
        )
        self.assertIn("trio_infernal", self.ids(nouveaux))
        self.assertIn("canon_a_os", self.ids(nouveaux))
        self.assertEqual(self.etat["stats"]["plus_grande_salve"], 4)

    def test_les_quatre_formations_debloquent_le_choregraphe(self):
        for formation in ("canon", "wave", "rain", "vortex"):
            nouveaux = succes.enregistrer(
                self.etat, "doots", self.maintenant,
                quantite=4, formation=formation,
            )
        self.assertIn("choregraphe", self.ids(nouveaux))

    def test_les_evenements_rares_se_collectionnent(self):
        for rencontre in ("parade", "pluie", "vortex"):
            nouveaux = succes.enregistrer(
                self.etat, "doots", self.maintenant,
                quantite=5, rencontre=rencontre,
            )
        ids = self.ids(nouveaux)
        self.assertIn("collection_evenements", ids)
        self.assertIn("premier_evenement", succes.debloques(self.etat))

    def test_activer_un_profil_a_son_succes(self):
        nouveaux = succes.enregistrer(
            self.etat, "profil", self.maintenant, nom="chaos"
        )
        self.assertIn("profil_actif", self.ids(nouveaux))

    def test_les_quatre_bords_s_accumulent(self):
        for bord in ("left", "right", "top", "bottom"):
            nouveaux = succes.enregistrer(
                self.etat, "doots", self.maintenant, quantite=1, bord=bord
            )
        self.assertIn("quatre_coins", self.ids(nouveaux))

    def test_melodie_fournie_polyphonique_et_rickroll(self):
        nouveaux = succes.enregistrer(
            self.etat,
            "melodie",
            self.maintenant,
            nom="rickroll",
            fournie=True,
            voix=2,
        )
        ids = self.ids(nouveaux)
        self.assertIn("maestro", ids)
        self.assertIn("orchestre", ids)
        self.assertIn("rickroll", ids)
        self.assertNotIn("melodie_perso", ids)

    def test_cinq_melodies_fournies_differentes(self):
        for index in range(5):
            nouveaux = succes.enregistrer(
                self.etat, "melodie", self.maintenant,
                nom=f"morceau-{index}", fournie=True, voix=1,
            )
        self.assertIn("jukebox_macabre", self.ids(nouveaux))

    def test_melodie_perso(self):
        nouveaux = succes.enregistrer(
            self.etat, "melodie", self.maintenant,
            nom="ma-composition", fournie=False, voix=1,
        )
        self.assertIn("melodie_perso", self.ids(nouveaux))

    def test_sept_jours_distincts(self):
        for index in range(7):
            nouveaux = succes.enregistrer(
                self.etat, "doots", self.maintenant + timedelta(days=index), quantite=1
            )
        self.assertIn("sept_jours", self.ids(nouveaux))

    def test_etat_abime_est_repare(self):
        etat = {"stats": [], "succes": "beaucoup"}
        succes.enregistrer(etat, "doots", self.maintenant, quantite=1)
        self.assertIsInstance(etat["stats"], dict)
        self.assertIsInstance(etat["succes"], dict)

    def test_valeurs_invalides_ne_fabriquent_pas_de_score(self):
        etat = {"stats": {"doots": True, "melodies": -10}}
        nouveaux = succes.enregistrer(etat, "doots", self.maintenant, quantite="plein")
        self.assertEqual(nouveaux, [])
        self.assertEqual(succes.score(etat), 0)


class Badges(unittest.TestCase):
    def test_chaque_succes_a_un_png_fourni(self):
        for definition in succes.CATALOGUE:
            with self.subTest(succes=definition.identifiant):
                chemin = succes.badge(definition)
                self.assertIsNotNone(chemin)
                self.assertEqual(png.size(chemin), (256, 256))

    def test_succes_inconnu_n_augmente_ni_le_total_ni_le_score(self):
        etat = {"succes": {"invente": "demain"}}
        self.assertEqual(succes.debloques(etat), {})
        self.assertEqual(succes.score(etat), 0)


if __name__ == "__main__":
    unittest.main()
