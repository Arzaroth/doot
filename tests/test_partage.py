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
        refus = {lecture.nom: lecture.refus for lecture in lectures}
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


class Coffre(unittest.TestCase):
    """La cle, l'enveloppe, et le nom des objets."""

    def test_la_cle_fait_l_aller_retour(self):
        from doot import coffre
        cle = coffre.creer()
        self.assertEqual(coffre.depuis_texte(coffre.en_texte(cle)), cle)
        self.assertTrue(coffre.en_texte(cle).startswith(coffre.PREFIXE))

    def test_une_cle_de_travers_est_refusee(self):
        from doot import coffre
        for texte in ("", "bonjour", "dootsync1", "dootsync1aaaa"):
            with self.subTest(cle=texte):
                with self.assertRaises(coffre.CoffreError):
                    coffre.depuis_texte(texte)

    def test_le_nom_d_objet_est_stable_et_opaque(self):
        from doot import coffre
        cle = coffre.creer()
        self.assertEqual(coffre.nom_objet(cle, "abc"), coffre.nom_objet(cle, "abc"))
        self.assertNotIn("abc", coffre.nom_objet(cle, "abc"))
        self.assertNotEqual(coffre.nom_objet(cle, "abc"),
                            coffre.nom_objet(coffre.creer(), "abc"))

    def test_les_copies_de_conflit_ne_sont_pas_des_objets(self):
        from doot import coffre
        cle = coffre.creer()
        vrai = coffre.nom_objet(cle, "abc")
        self.assertTrue(coffre.est_un_objet(vrai))
        for faux in (vrai[:-9] + ".sync-conflict-20260918.dootsync",
                     vrai + ".tmp", "notes.txt", "zz" + vrai[2:]):
            with self.subTest(nom=faux):
                self.assertFalse(coffre.est_un_objet(faux))

    def test_l_enveloppe_se_rouvre(self):
        from doot import coffre
        cle = coffre.creer()
        clair = b'{"machine": "abc"}' * 40
        scelle = coffre.fermer(cle, clair)
        self.assertEqual(coffre.ouvrir(cle, scelle), clair)
        self.assertLess(len(scelle), len(clair), "le gzip doit servir")

    def test_une_autre_cle_est_reconnue_avant_de_dechiffrer(self):
        from doot import coffre
        scelle = coffre.fermer(coffre.creer(), b"x")
        with self.assertRaisesRegex(coffre.CoffreError, "autre cle"):
            coffre.ouvrir(coffre.creer(), scelle)

    def test_un_octet_retourne_est_refuse(self):
        from doot import coffre
        cle = coffre.creer()
        scelle = bytearray(coffre.fermer(cle, b"charge"))
        scelle[-1] ^= 1
        with self.assertRaisesRegex(coffre.CoffreError, "abimee|falsifiee"):
            coffre.ouvrir(cle, bytes(scelle))

    def test_ce_qui_n_est_pas_une_enveloppe_est_refuse(self):
        from doot import coffre
        with self.assertRaises(coffre.CoffreError):
            coffre.ouvrir(coffre.creer(), b"pas une enveloppe du tout")


class TransportDossier(unittest.TestCase):
    def setUp(self):
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        self.racine = Path(dossier.name)

    def test_les_quatre_gestes(self):
        from doot import coffre, transport
        depot = transport.Dossier(self.racine)
        nom = coffre.nom_objet(coffre.creer(), "abc")
        self.assertEqual(depot.lister(), [])
        depot.deposer(nom, b"charge")
        self.assertEqual([o.nom for o in depot.lister()], [nom])
        self.assertEqual(depot.reprendre(depot.lister()[0]), b"charge")
        depot.effacer(nom)
        self.assertEqual(depot.lister(), [])

    def test_seuls_les_objets_sont_listes(self):
        from doot import coffre, transport
        depot = transport.Dossier(self.racine)
        nom = coffre.nom_objet(coffre.creer(), "abc")
        depot.deposer(nom, b"x")
        (depot.racine / "notes.txt").write_bytes(b"x")
        (depot.racine / f"{nom[:-9]}.sync-conflict-20260918.dootsync").write_bytes(b"x")
        self.assertEqual([o.nom for o in depot.lister()], [nom])

    def test_l_ecriture_ne_laisse_pas_de_tampon(self):
        from doot import coffre, transport
        depot = transport.Dossier(self.racine)
        depot.deposer(coffre.nom_objet(coffre.creer(), "abc"), b"x")
        self.assertEqual([p.name for p in depot.racine.iterdir() if p.name.startswith(".")], [])


class SignatureS3(unittest.TestCase):
    """Les trois etages de la signature version 4."""

    def signeur(self):
        from doot import transport
        return transport.S3("https://s3.us-east-1.amazonaws.com", "us-east-1", "doots",
                            cle_acces="AKIAIOSFODNN7EXAMPLE",
                            secret="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")

    def test_les_en_tetes_signes_sont_ceux_attendus(self):
        entetes, _ = self.signeur()._signer("GET", "/doots", {}, b"")
        self.assertEqual(sorted(n for n in entetes if n != "Authorization"),
                         ["host", "x-amz-content-sha256", "x-amz-date"])

    def test_la_charge_entre_dans_la_signature(self):
        signeur = self.signeur()
        vide, _ = signeur._signer("PUT", "/doots/x", {}, b"")
        plein, _ = signeur._signer("PUT", "/doots/x", {}, b"charge")
        self.assertNotEqual(vide["x-amz-content-sha256"], plein["x-amz-content-sha256"])

    def test_la_requete_entre_dans_la_signature(self):
        signeur = self.signeur()
        sans, _ = signeur._signer("GET", "/doots", {}, b"")
        avec, query = signeur._signer("GET", "/doots", {"list-type": "2"}, b"")
        self.assertEqual(query, "list-type=2")
        self.assertNotEqual(sans["Authorization"], avec["Authorization"])

    def test_la_portee_porte_region_et_service(self):
        entetes, _ = self.signeur()._signer("GET", "/doots", {}, b"")
        portee = entetes["Authorization"].split("Credential=")[1].split(",")[0]
        self.assertIn("/us-east-1/s3/aws4_request", portee)
