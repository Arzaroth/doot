"""Enumeration des ecrans, pour que le squelette puisse surgir sur n'importe lequel.

tkinter ne sait pas decrire une configuration multi-ecrans : `winfo_screenwidth()`
renvoie l'ecran principal (Windows, macOS) ou tout le bureau virtuel d'un bloc
(X11), ce qui ferait apparaitre le squelette a cheval entre deux dalles. On
interroge donc le systeme :

  - Windows : EnumDisplayMonitors + GetMonitorInfoW (zone de travail, hors barre
    des taches)
  - Linux   : `xrandr --listmonitors`
  - macOS   : CoreGraphics (CGGetActiveDisplayList + CGDisplayBounds)

Chaque methode retombe proprement sur un ecran unique si elle echoue.
"""

from __future__ import annotations

import re
import subprocess
import sys


class Monitor:
    """Un ecran : position et taille en pixels, dans le bureau virtuel."""

    __slots__ = ("x", "y", "width", "height", "primary", "name")

    def __init__(self, x, y, width, height, primary=False, name=""):
        self.x = int(x)
        self.y = int(y)
        self.width = int(width)
        self.height = int(height)
        self.primary = bool(primary)
        self.name = name or "ecran"

    def place(self, width: int, height: int, center: bool, rng) -> tuple[int, int]:
        """Coordonnees ou poser une fenetre width x height sur cet ecran."""
        if center:
            return (
                self.x + (self.width - width) // 2,
                self.y + (self.height - height) // 2,
            )
        return (
            self.x + rng.randint(0, max(0, self.width - width)),
            self.y + rng.randint(0, max(0, self.height - height)),
        )

    def entry(self, width: int, height: int, side: str, rng,
              near=(0.0, 0.03), center=False) -> tuple[int, int, int, int]:
        """Trajet d'une entree par un bord : (depart x, depart y, repos x, repos y).

        Le depart est entierement hors de l'ecran, decale de toute la taille de
        la fenetre, pour que le squelette apparaisse en glissant depuis le bord.
        Il s'arrete contre ce meme bord, a un cheveu pres : s'enfoncer dans
        l'ecran donnerait une traversee, pas une entree.

        `center` ne centre que l'axe perpendiculaire a l'entree — le bord
        d'arrivee, lui, n'est pas negociable.
        """
        libre_x = max(0, self.width - width)
        libre_y = max(0, self.height - height)

        def le_long(libre: int) -> int:
            return libre // 2 if center else rng.randint(0, libre)

        if side in ("left", "right"):
            jeu = min(int(rng.uniform(*near) * self.width), libre_x)
            if side == "left":
                repos_x, depart_x = self.x + jeu, self.x - width
            else:
                repos_x, depart_x = self.x + libre_x - jeu, self.x + self.width
            repos_y = depart_y = self.y + le_long(libre_y)
        else:
            jeu = min(int(rng.uniform(*near) * self.height), libre_y)
            if side == "top":
                repos_y, depart_y = self.y + jeu, self.y - height
            else:
                repos_y, depart_y = self.y + libre_y - jeu, self.y + self.height
            repos_x = depart_x = self.x + le_long(libre_x)

        return depart_x, depart_y, repos_x, repos_y

    def __repr__(self):
        flag = "*" if self.primary else " "
        return f"<Monitor {flag}{self.name} {self.width}x{self.height}+{self.x}+{self.y}>"


# ------------------------------------------------------------- Windows -------

def _windows_monitors() -> list[Monitor]:
    import ctypes
    from ctypes import wintypes

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_ulong),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", ctypes.c_ulong),
            ("szDevice", ctypes.c_wchar * 32),
        ]

    MONITORINFOF_PRIMARY = 0x00000001
    user32 = ctypes.windll.user32
    found: list[Monitor] = []

    callback_type = ctypes.WINFUNCTYPE(
        ctypes.c_int,
        ctypes.c_void_p,               # HMONITOR
        ctypes.c_void_p,               # HDC
        ctypes.POINTER(RECT),          # LPRECT
        ctypes.c_ssize_t,              # LPARAM
    )

    def callback(handle, _hdc, _rect, _param):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(ctypes.c_void_p(handle), ctypes.byref(info)):
            # rcWork exclut la barre des taches : le squelette ne se cache pas dessous
            work = info.rcWork
            found.append(
                Monitor(
                    work.left,
                    work.top,
                    work.right - work.left,
                    work.bottom - work.top,
                    primary=bool(info.dwFlags & MONITORINFOF_PRIMARY),
                    name=info.szDevice,
                )
            )
        return 1

    user32.EnumDisplayMonitors(
        wintypes.HDC(), None, callback_type(callback), ctypes.c_ssize_t(0)
    )
    return found


# --------------------------------------------------------------- Linux -------

_XRANDR_LINE = re.compile(
    r"^\s*(?P<index>\d+):\s+\+(?P<primary>\*?)(?P<name>\S+)\s+"
    r"(?P<width>\d+)/\d+x(?P<height>\d+)/\d+\+(?P<x>-?\d+)\+(?P<y>-?\d+)"
)


def _linux_monitors() -> list[Monitor]:
    try:
        out = subprocess.run(
            ["xrandr", "--listmonitors"],
            capture_output=True, text=True, timeout=4,
        )
    except Exception:
        return []
    if out.returncode != 0:
        return []

    found: list[Monitor] = []
    for line in out.stdout.splitlines():
        match = _XRANDR_LINE.match(line)
        if not match:
            continue
        found.append(
            Monitor(
                match.group("x"),
                match.group("y"),
                match.group("width"),
                match.group("height"),
                primary=bool(match.group("primary")),
                name=match.group("name"),
            )
        )
    return found


# --------------------------------------------------------------- macOS -------

def _macos_monitors() -> list[Monitor]:
    import ctypes
    import ctypes.util

    class CGPoint(ctypes.Structure):
        _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

    class CGSize(ctypes.Structure):
        _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]

    class CGRect(ctypes.Structure):
        _fields_ = [("origin", CGPoint), ("size", CGSize)]

    path = ctypes.util.find_library("CoreGraphics")
    if not path:
        return []
    core = ctypes.cdll.LoadLibrary(path)

    max_displays = 16
    displays = (ctypes.c_uint32 * max_displays)()
    count = ctypes.c_uint32(0)
    if core.CGGetActiveDisplayList(max_displays, displays, ctypes.byref(count)) != 0:
        return []

    core.CGDisplayBounds.restype = CGRect
    core.CGDisplayBounds.argtypes = [ctypes.c_uint32]
    core.CGMainDisplayID.restype = ctypes.c_uint32

    main_id = core.CGMainDisplayID()
    found: list[Monitor] = []
    for i in range(count.value):
        display_id = displays[i]
        bounds = core.CGDisplayBounds(display_id)
        found.append(
            Monitor(
                bounds.origin.x,
                bounds.origin.y,
                bounds.size.width,
                bounds.size.height,
                primary=(display_id == main_id),
                name=f"display-{display_id}",
            )
        )
    return found


# ---------------------------------------------------------------- API --------

def monitors(fallback_width: int = 1920, fallback_height: int = 1080) -> list[Monitor]:
    """Tous les ecrans. Jamais vide : au pire un seul, aux dimensions donnees."""
    detect = {
        "win32": _windows_monitors,
        "darwin": _macos_monitors,
    }.get(sys.platform, _linux_monitors)

    try:
        found = detect()
    except Exception:
        found = []

    found = [m for m in found if m.width > 0 and m.height > 0]
    if not found:
        found = [Monitor(0, 0, fallback_width, fallback_height, primary=True, name="ecran")]
    return found


def pick(found: list[Monitor], preference=None, rng=None) -> Monitor:
    """Choisit un ecran.

    preference : None ou "random" -> au hasard ; "primary" -> l'ecran principal ;
    un entier (ou sa forme texte) -> l'ecran de cet index, borne a la liste.
    """
    import random as _random

    rng = rng or _random
    if not found:
        return Monitor(0, 0, 1920, 1080, primary=True)

    if preference in (None, "", "random", "any", "all"):
        return rng.choice(found)

    if preference in ("primary", "main"):
        for monitor in found:
            if monitor.primary:
                return monitor
        return found[0]

    try:
        index = int(preference)
    except (TypeError, ValueError):
        return rng.choice(found)
    return found[max(0, min(index, len(found) - 1))]


def ease_out(t: float) -> float:
    """Glissement vif au depart, qui se pose en douceur (cubique).

    Vit ici, et pas dans window.py, parce que l'overlay X11 s'en sert aussi et
    ne peut pas importer window sans boucler.
    """
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def virtual_bounds(found: list[Monitor]) -> tuple[int, int]:
    """Bornes horizontales du bureau entier, tous ecrans confondus."""
    if not found:
        return 0, 0
    return (
        min(m.x for m in found),
        max(m.x + m.width for m in found),
    )


def pan_for(center_x: float, found: list[Monitor] | None = None) -> float:
    """Panoramique pour une fenetre centree sur `center_x`, de -1 (gauche) a +1.

    Le calcul porte sur tout le bureau virtuel, pas sur un ecran isole : avec
    deux dalles cote a cote, un doot colle au bord droit de celle de droite
    doit sonner franchement a droite, pas au centre comme s'il etait seul.
    """
    found = found if found is not None else monitors()
    left, right = virtual_bounds(found)
    span = right - left
    if span <= 0:
        return 0.0
    ratio = (center_x - left) / span
    return max(-1.0, min(1.0, ratio * 2.0 - 1.0))


def describe(found: list[Monitor]) -> str:
    if len(found) == 1:
        monitor = found[0]
        return f"1 ecran ({monitor.width}x{monitor.height})"
    parts = ", ".join(
        f"{i}:{m.name} {m.width}x{m.height}{'*' if m.primary else ''}"
        for i, m in enumerate(found)
    )
    return f"{len(found)} ecrans [{parts}]"
