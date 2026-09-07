"""Overlay Wayland.

Un compositeur ne peut pas tourner en CI, et la CI tourne aussi sous macOS et
Windows. Ce qui est verifie ici ne depend donc d'aucune session : l'encodage du
protocole, le choix de la sortie, la geometrie logique lue par xdg-output, et le
fait que l'absence de Wayland se solde par un repli et non par une erreur.

Ce qui a besoin d'un serveur en face est joue contre un compositeur en dur sur
un `socketpair`, dont les reponses sont ecrites a l'avance.
"""

from __future__ import annotations

import os
import socket
import struct
import unittest

from doot import wayland


class Encodage(unittest.TestCase):
    """Les chaines Wayland : longueur avec le NUL, bourrage a 4 octets."""

    def test_chaine_courte(self):
        self.assertEqual(wayland._text("wl_shm"),
                         struct.pack("=I", 7) + b"wl_shm\0" + b"\0")

    def test_longueur_deja_multiple_de_quatre(self):
        encode = wayland._text("abc")
        self.assertEqual(encode, struct.pack("=I", 4) + b"abc\0")
        self.assertEqual(len(encode) % 4, 0)

    def test_toujours_aligne(self):
        for nom in ("a", "ab", "abc", "abcd", "abcde", "zwlr_layer_shell_v1"):
            self.assertEqual(len(wayland._text(nom)) % 4, 0, nom)


class ChoixDeLaSortie(unittest.TestCase):
    """`_locate` rend la sortie qui contient le point, et la position dedans."""

    def setUp(self):
        self.sorties = {
            4: {"name": "eDP-1", "x": 0, "y": 0, "width": 2256, "height": 1504, "scale": 2},
            5: {"name": "DP-9", "x": -1356, "y": -1080, "width": 1920, "height": 1080, "scale": 1},
            6: {"name": "DP-10", "x": 564, "y": -1080, "width": 1920, "height": 1080, "scale": 1},
        }

    def test_l_echelle_est_appliquee_a_la_taille(self):
        """eDP-1 fait 2256 pixels mais 1128 unites logiques.

        Une voisine collee a 1128 le prouve : sans division par l'echelle,
        eDP-1 s'etendrait jusqu'a 2256 et avalerait le point.
        """
        voisine = {
            4: self.sorties[4],
            9: {"name": "HDMI-1", "x": 1128, "y": 0,
                "width": 1920, "height": 1080, "scale": 1},
        }
        self.assertEqual(wayland._locate(1100, 700, voisine), (4, 1100, 700))
        self.assertEqual(wayland._locate(1200, 700, voisine), (9, 72, 700))

    def test_position_locale(self):
        oid, x, y = wayland._locate(-800, -700, self.sorties)
        self.assertEqual((oid, x, y), (5, 556, 380))

    def test_coin_superieur_gauche(self):
        self.assertEqual(wayland._locate(564, -1080, self.sorties), (6, 0, 0))

    def test_point_hors_de_toute_sortie_prend_la_plus_proche(self):
        oid, _, _ = wayland._locate(600, -2000, self.sorties)
        self.assertIn(oid, self.sorties)

    def test_sans_sortie(self):
        with self.assertRaises(wayland.WaylandUnavailable):
            wayland._locate(0, 0, {})


class Registre(unittest.TestCase):
    """La poignee de main, jouee contre un compositeur en dur."""

    @staticmethod
    def _evenement(obj, opcode, corps):
        return struct.pack("=II", obj, ((8 + len(corps)) << 16) | opcode) + corps

    def test_lecture_des_globals(self):
        gauche, droite = socket.socketpair()
        self.addCleanup(droite.close)
        self.addCleanup(gauche.close)

        # Reponses pre-ecrites : registre = objet 2, callback de sync = objet 3.
        droite.sendall(
            self._evenement(2, 0, struct.pack("=I", 3) + wayland._text("wl_compositor")
                            + struct.pack("=I", 6))
            + self._evenement(2, 0, struct.pack("=I", 35)
                              + wayland._text("zwlr_layer_shell_v1")
                              + struct.pack("=I", 5))
            + self._evenement(3, 0, struct.pack("=I", 0))
        )

        conn = object.__new__(wayland._Connection)
        conn.sock, conn.buf, conn.next_id = gauche, b"", 2
        conn.globals, conn.handlers = {}, {}
        conn.connect()

        self.assertEqual(conn.globals["wl_compositor"], [(3, 6)])
        self.assertEqual(conn.globals["zwlr_layer_shell_v1"], [(35, 5)])

    def test_une_erreur_du_serveur_devient_WaylandUnavailable(self):
        gauche, droite = socket.socketpair()
        self.addCleanup(droite.close)
        self.addCleanup(gauche.close)
        droite.sendall(self._evenement(
            1, 0, struct.pack("=II", 6, 1) + wayland._text("invalid arguments")))

        conn = object.__new__(wayland._Connection)
        conn.sock, conn.buf, conn.next_id = gauche, b"", 2
        conn.globals, conn.handlers = {}, {}
        with self.assertRaises(wayland.WaylandUnavailable):
            conn.connect()


class SansSession(unittest.TestCase):
    """Hors Wayland, on se replie sans bruit."""

    def setUp(self):
        self.env = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(self.env)))

    def test_available_est_faux(self):
        os.environ.pop("WAYLAND_DISPLAY", None)
        self.assertFalse(wayland.available())

    def test_monitors_rend_une_liste_vide(self):
        os.environ.pop("WAYLAND_DISPLAY", None)
        self.assertEqual(wayland.monitors(), [])

    def test_socket_inexistante(self):
        os.environ["WAYLAND_DISPLAY"] = "/nexiste/pas/wayland-99"
        self.assertFalse(wayland.available())


class EchelleFractionnaire(unittest.TestCase):
    """`mode / scale` ne vaut que pour une echelle entiere.

    `wl_output.scale` est un entier : sous echelle fractionnaire le compositeur
    laisse `mode` en pixels et arrondit `scale` au superieur. La geometrie
    logique doit donc venir de `zxdg_output_manager_v1`, pas d'une division.
    """

    def test_la_division_donne_la_mauvaise_dalle(self):
        """Une 2560 a l'echelle 1.5 fait 1707 unites logiques, pas 1280.

        Avec la division, le bord droit tombe a 1280 : un point a 1500, qui est
        bien sur la premiere dalle, est attribue a la voisine.
        """
        naif = {
            4: {"name": "DP-1", "x": 0, "y": 0,
                "width": 2560, "height": 1440, "scale": 2},
            5: {"name": "DP-2", "x": 1707, "y": 0,
                "width": 1920, "height": 1080, "scale": 1},
        }
        self.assertEqual(wayland._locate(1500, 100, naif)[0], 5)

    def test_la_geometrie_logique_rend_la_bonne_dalle(self):
        exact = {
            4: {"name": "DP-1", "x": 0, "y": 0,
                "width": 1707, "height": 960, "scale": 1},
            5: {"name": "DP-2", "x": 1707, "y": 0,
                "width": 1920, "height": 1080, "scale": 1},
        }
        self.assertEqual(wayland._locate(1500, 100, exact), (4, 1500, 100))

    def test_sans_le_gestionnaire_on_garde_le_calcul(self):
        conn = object.__new__(wayland._Connection)
        conn.globals, conn.handlers = {}, {}
        found = {4: {"name": "DP-1", "x": 0, "y": 0,
                     "width": 2560, "height": 1440, "scale": 2}}
        wayland._ask_logical(conn, found)     # ne doit rien emettre ni lever
        self.assertEqual(found[4]["width"], 2560)
        self.assertEqual(found[4]["scale"], 2)


class GeometrieLogique(unittest.TestCase):
    """`_ask_logical` contre un compositeur en dur, sur un `socketpair`.

    Les tests d'echelle ci-dessus comparent deux formes de dictionnaire : ils
    montrent la consequence, pas le chemin qui y mene. Ici c'est le protocole
    lui-meme qui est joue — la requete emise, puis les evenements decodes —
    faute de pouvoir mesurer sur un ecran a echelle fractionnaire.
    """

    # Un `_Connection` neuf a `next_id` 10 : le gestionnaire prend 10, les
    # `zxdg_output_v1` 11 et 12 dans l'ordre des sorties, le callback de
    # `roundtrip` 13. Le compositeur en dur repond donc a ces numeros-la.
    MANAGER, PREMIER, SECOND, CALLBACK = 10, 11, 12, 13

    @staticmethod
    def _evenement(obj, opcode, corps):
        return struct.pack("=II", obj, ((8 + len(corps)) << 16) | opcode) + corps

    @staticmethod
    def _emis(sock):
        """Les messages que le client a poses sur la socket, decodes."""
        sock.setblocking(False)
        brut = b""
        try:
            while True:
                bout = sock.recv(8192)
                if not bout:
                    break
                brut += bout
        except BlockingIOError:
            pass
        finally:
            sock.setblocking(True)

        messages = []
        while len(brut) >= 8:
            obj, mot = struct.unpack_from("=II", brut)
            taille, opcode = mot >> 16, mot & 0xFFFF
            if taille < 8 or len(brut) < taille:
                break
            messages.append((obj, opcode, brut[8:taille]))
            brut = brut[taille:]
        return messages

    def _connexion(self):
        gauche, droite = socket.socketpair()
        self.addCleanup(droite.close)
        self.addCleanup(gauche.close)
        gauche.settimeout(2)          # une reponse manquante doit echouer, pas pendre
        conn = object.__new__(wayland._Connection)
        conn.sock, conn.buf, conn.next_id = gauche, b"", 10
        conn.handlers, conn.registry = {}, 2
        conn.globals = {"zxdg_output_manager_v1": [(7, 3)]}
        return conn, droite

    @staticmethod
    def _sorties():
        """Deux dalles a l'echelle 1.5, annoncees en pixels et arrondies a 2."""
        return {
            4: {"name": "DP-1", "x": 0, "y": 0,
                "width": 2560, "height": 1440, "scale": 2},
            5: {"name": "DP-2", "x": 1707, "y": 0,
                "width": 2560, "height": 1440, "scale": 2},
        }

    def test_la_geometrie_logique_remplace_le_calcul(self):
        """2560 a l'echelle 1.5 font 1707 unites, pas les 1280 de la division."""
        conn, droite = self._connexion()
        droite.sendall(
            self._evenement(self.PREMIER, 0, struct.pack("=ii", 0, 0))
            + self._evenement(self.PREMIER, 1, struct.pack("=ii", 1707, 960))
            + self._evenement(self.SECOND, 0, struct.pack("=ii", 1707, 0))
            + self._evenement(self.SECOND, 1, struct.pack("=ii", 1707, 960))
            + self._evenement(self.CALLBACK, 0, struct.pack("=I", 0))
        )

        found = self._sorties()
        wayland._ask_logical(conn, found)

        self.assertEqual(found[4]["width"], 1707)
        self.assertEqual(found[4]["height"], 960)
        self.assertEqual(found[5]["x"], 1707)
        # Deja logique : plus rien a diviser, sinon la dalle retrecirait a
        # nouveau de moitie chez l'appelant.
        self.assertEqual(found[4]["scale"], 1)
        self.assertEqual(found[5]["scale"], 1)
        # Le nom vient de `wl_output`, il ne doit pas etre efface au passage.
        self.assertEqual(found[4]["name"], "DP-1")

    def test_la_bonne_dalle_est_choisie_ensuite(self):
        """La consequence, celle qui se voit : un point a 1500 reste sur DP-1.

        Avec la division, le bord droit tombait a 1280 et le point partait chez
        la voisine.
        """
        conn, droite = self._connexion()
        droite.sendall(
            self._evenement(self.PREMIER, 0, struct.pack("=ii", 0, 0))
            + self._evenement(self.PREMIER, 1, struct.pack("=ii", 1707, 960))
            + self._evenement(self.SECOND, 0, struct.pack("=ii", 1707, 0))
            + self._evenement(self.SECOND, 1, struct.pack("=ii", 1707, 960))
            + self._evenement(self.CALLBACK, 0, struct.pack("=I", 0))
        )

        found = self._sorties()
        self.assertEqual(wayland._locate(1500, 100, found)[0], 5)   # avant
        wayland._ask_logical(conn, found)
        self.assertEqual(wayland._locate(1500, 100, found), (4, 1500, 100))

    def test_une_requete_par_sortie(self):
        """`get_xdg_output` doit apparier chaque objet neuf a sa sortie.

        Les intervertir donnerait deux dalles aux geometries echangees, ce
        qu'aucune assertion sur `found` ne verrait tant qu'elles se ressemblent.
        """
        conn, droite = self._connexion()
        droite.sendall(
            self._evenement(self.PREMIER, 1, struct.pack("=ii", 1707, 960))
            + self._evenement(self.SECOND, 1, struct.pack("=ii", 1707, 960))
            + self._evenement(self.CALLBACK, 0, struct.pack("=I", 0))
        )
        wayland._ask_logical(conn, self._sorties())

        messages = self._emis(droite)
        liaison = [m for m in messages if m[0] == conn.registry]
        self.assertEqual(len(liaison), 1, messages)
        self.assertIn(b"zxdg_output_manager_v1", liaison[0][2])

        demandes = [struct.unpack("=II", corps)
                    for obj, opcode, corps in messages
                    if obj == self.MANAGER and opcode == wayland._XDG_OUTPUT_GET]
        self.assertEqual(demandes, [(self.PREMIER, 4), (self.SECOND, 5)])

    def test_une_sortie_muette_garde_le_calcul(self):
        """Une taille logique absente laisse la sortie telle quelle.

        Le repli est par sortie, pas global : la dalle qui a repondu garde sa
        geometrie exacte, l'autre reste sur `mode / scale` plutot que sur une
        moitie de reponse.
        """
        conn, droite = self._connexion()
        droite.sendall(
            self._evenement(self.PREMIER, 0, struct.pack("=ii", 0, 0))
            + self._evenement(self.PREMIER, 1, struct.pack("=ii", 1707, 960))
            # DP-2 n'annonce que sa position : sans taille, on ne touche a rien.
            + self._evenement(self.SECOND, 0, struct.pack("=ii", 4242, 0))
            + self._evenement(self.CALLBACK, 0, struct.pack("=I", 0))
        )

        found = self._sorties()
        wayland._ask_logical(conn, found)

        self.assertEqual(found[4]["width"], 1707)
        self.assertEqual(found[4]["scale"], 1)
        self.assertEqual(found[5]["width"], 2560)
        self.assertEqual(found[5]["scale"], 2)
        self.assertEqual(found[5]["x"], 1707)


if __name__ == "__main__":
    unittest.main()
