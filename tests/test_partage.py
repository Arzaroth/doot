"""L'identite de replique, et ce qu'elle protege.

Elle ne vit pas dans `state.json` : ce fichier se copie et se restaure, et deux
installations qui partageraient une part verraient leurs progressions
fusionnees par maximum au lieu d'etre additionnees.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from doot import partage, succes


class Identite(unittest.TestCase):
    def setUp(self):
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        self.racine = Path(dossier.name)
        partage._connues.clear()
        self.addCleanup(partage._connues.clear)

    def test_stable_d_un_appel_a_l_autre(self):
        premiere = partage.identite(self.racine)
        partage._connues.clear()
        self.assertEqual(partage.identite(self.racine), premiere)

    def test_deux_installations_ont_deux_identites(self):
        autre = self.racine / "ailleurs"
        self.assertNotEqual(partage.identite(self.racine), partage.identite(autre))

    def test_elle_ne_vient_jamais_de_l_etat(self):
        """`state.json` peut dire n'importe quoi, l'identite vient du poste."""
        (self.racine / "state.json").write_text(
            json.dumps({"machine": "copiee-d-ailleurs"}), encoding="utf-8")
        self.assertNotEqual(partage.identite(self.racine), "copiee-d-ailleurs")

    def test_une_empreinte_qui_change_bat_une_identite_neuve(self):
        """Le dossier de donnees restaure ailleurs : on ne peut pas rester le meme.

        Se re-cler pour rien ne coute qu'une part de plus, et les parts
        s'additionnent ; ne pas se re-cler quand il le fallait coute des doots.
        """
        premiere = partage.identite(self.racine)
        partage._connues.clear()
        with mock.patch.object(partage.platform, "node", lambda: "un-autre-poste"):
            self.assertNotEqual(partage.identite(self.racine), premiere)

    def test_l_identite_survit_a_un_dossier_en_lecture_seule(self):
        """Faute de pouvoir l'ecrire, elle ne doit pas changer a chaque appel."""
        with mock.patch.object(Path, "write_text",
                               mock.Mock(side_effect=OSError("lecture seule"))):
            premiere = partage.identite(self.racine)
            self.assertEqual(partage.identite(self.racine), premiere)


class EtatClone(unittest.TestCase):
    """Le scenario que l'identite dans l'etat cassait en silence."""

    def poste(self, identifiant, souche=None, doots=0):
        etat = json.loads(json.dumps(souche)) if souche else {}
        etat["machine"] = identifiant
        for _ in range(doots):
            succes.enregistrer(etat, "doots", datetime(2026, 9, 18), quantite=1)
        return etat

    def test_ecritures_divergentes_apres_copie_s_additionnent(self):
        souche = self.poste("souche", doots=10)

        # le meme fichier, copie sur deux postes, chacun avec sa propre identite
        a = self.poste("portable", souche, doots=5)
        b = self.poste("fixe", souche, doots=7)
        self.assertEqual(succes.total(a, "doots"), 15)
        self.assertEqual(succes.total(b, "doots"), 17)

        succes.fusionner(a, b)
        self.assertEqual(succes.total(a, "doots"), 22,
                         "les increments divergents doivent s'additionner")

    def test_les_parts_historiques_restent_a_qui_les_a_gagnees(self):
        souche = self.poste("souche", doots=10)
        a = self.poste("portable", souche, doots=5)
        self.assertEqual(a["stats"]["doots"], {"souche": 10, "portable": 5})


class Lectures(unittest.TestCase):
    """Le sort de chaque fichier est rendu, pas imprime."""

    def setUp(self):
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        self.racine = Path(dossier.name)

    def depose(self, nom, contenu):
        chemin = self.racine / nom
        chemin.write_text(contenu if isinstance(contenu, str) else json.dumps(contenu),
                          encoding="utf-8")
        return chemin

    def test_chaque_refus_dit_pourquoi(self):
        etat = {"machine": "ici"}
        fichiers = [
            self.depose("casse.json", "pas du json"),
            self.depose("liste.json", [1, 2]),
            self.depose("moi.json", {"machine": "ici"}),
            self.depose("anonyme.json", {"stats": {}}),
            self.depose("fixe.json", {"machine": "fixe", "stats": {}}),
        ]
        lectures = partage.lire_parts(etat, fichiers)
        refus = {lecture.chemin.name: lecture.refus for lecture in lectures}
        self.assertIn("illisible", refus["casse.json"])
        self.assertIn("pas un etat doot", refus["liste.json"])
        self.assertIn("cette machine", refus["moi.json"])
        self.assertIn("de quelle machine", refus["anonyme.json"])
        self.assertEqual(refus["fixe.json"], "")

    def test_une_lecture_porte_ce_qu_elle_a_debloque(self):
        etat = {"machine": "ici"}
        for _ in range(60):
            succes.enregistrer(etat, "doots", datetime(2026, 9, 18), quantite=1)
        pair = {"machine": "fixe"}
        for _ in range(60):
            succes.enregistrer(pair, "doots", datetime(2026, 9, 18), quantite=1)

        lectures = partage.lire_parts(etat, [self.depose("fixe.json", pair)])
        debloques = {item.identifiant for lecture in lectures
                     for item in lecture.debloques}
        self.assertIn("cent_doots", debloques)


if __name__ == "__main__":
    unittest.main()
