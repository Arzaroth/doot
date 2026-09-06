"""Overlay tkinter : le squelette apparait par-dessus tout, puis s'efface.

Multiplateforme :
  - Windows : fond reellement transparent (-transparentcolor) + fenetre
    "click-through" et sans vol de focus (styles etendus Win32).
  - macOS   : fenetre sans bordure, sans icone dans le Dock.
  - Linux   : type de fenetre "splash" quand le WM le supporte ; le fond est
    reellement transparent si un compositeur tourne, sinon fond sombre.
"""

from __future__ import annotations

import sys
from pathlib import Path

from . import art, sound

TRANSPARENT_KEY = "#ff00ff"
FALLBACK_BG = "#0b0b12"
FOREGROUND = "#f4f4f8"

FONT_CANDIDATES = {
    "win32": ("Consolas", "Lucida Console", "Courier New"),
    "darwin": ("Menlo", "Monaco", "Courier New"),
}
LINUX_FONTS = ("DejaVu Sans Mono", "Liberation Mono", "Noto Sans Mono", "monospace")


class TkinterMissing(RuntimeError):
    """tkinter absent : paquet systeme a installer."""


def _import_tk():
    try:
        import tkinter as tk
        import tkinter.font as tkfont
    except Exception as exc:  # pragma: no cover - depend de l'install systeme
        raise TkinterMissing(
            "tkinter est introuvable. Installe-le :\n"
            "  Arch/Manjaro   : sudo pacman -S tk\n"
            "  Debian/Ubuntu  : sudo apt install python3-tk\n"
            "  Fedora         : sudo dnf install python3-tkinter\n"
            "  macOS (brew)   : brew install python-tk\n"
            "  Windows        : reinstalle Python en cochant 'tcl/tk'"
        ) from exc
    return tk, tkfont


def _pick_font(tkfont, size: int):
    families = set(tkfont.families())
    candidates = FONT_CANDIDATES.get(sys.platform, LINUX_FONTS)
    for name in candidates:
        if name in families:
            return (name, size, "bold")
    return ("TkFixedFont", size, "bold")


def _make_click_through(window) -> None:
    """Windows : la fenetre ignore la souris et ne prend jamais le focus."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        WS_EX_NOACTIVATE = 0x08000000
        WS_EX_TOOLWINDOW = 0x00000080

        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
        user32 = ctypes.windll.user32
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(
            hwnd,
            GWL_EXSTYLE,
            style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW,
        )
    except Exception:
        pass


def _setup_transparency(tk_module, window) -> str:
    """Rend le fond transparent si possible ; renvoie la couleur de fond a utiliser."""
    if sys.platform == "win32":
        try:
            window.wm_attributes("-transparentcolor", TRANSPARENT_KEY)
            return TRANSPARENT_KEY
        except Exception:
            return FALLBACK_BG

    if sys.platform == "darwin":
        try:
            window.wm_attributes("-transparent", True)
            window.config(bg="systemTransparent")
            return "systemTransparent"
        except Exception:
            return FALLBACK_BG

    # X11 / Wayland : vraie transparence seulement avec un compositeur.
    try:
        window.wm_attributes("-type", "splash")
    except Exception:
        pass
    return FALLBACK_BG


def show(
    wav_path: Path | None = None,
    duration: float = 2.8,
    font_size: int = 15,
    center: bool = False,
    opacity: float = 1.0,
) -> None:
    """Affiche un doot et rend la main quand il a disparu."""
    tk, tkfont = _import_tk()

    root = tk.Tk()
    root.withdraw()
    root.overrideredirect(True)
    try:
        root.wm_attributes("-topmost", True)
    except Exception:
        pass
    try:
        root.wm_attributes("-alpha", 0.0)  # on apparait en fondu
    except Exception:
        pass

    background = _setup_transparency(tk, root)
    root.configure(bg=background)

    columns, lines = art.size()
    label = tk.Label(
        root,
        text=art.widest_frame(),
        font=_pick_font(tkfont, font_size),
        fg=FOREGROUND,
        bg=background,
        justify="left",
        anchor="nw",
        padx=6,
        pady=6,
        borderwidth=0,
        highlightthickness=0,
    )
    label.pack()

    # Dimensionne sur l'image la plus large, puis repart de la premiere.
    root.update_idletasks()
    width = max(label.winfo_reqwidth(), 1)
    height = max(label.winfo_reqheight(), 1)
    label.configure(text=art.frame(0))

    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    if center:
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
    else:
        import random

        x = random.randint(0, max(0, screen_w - width))
        y = random.randint(0, max(0, screen_h - height))
    root.geometry(f"{width}x{height}+{x}+{y}")

    root.deiconify()
    _make_click_through(root)

    player = sound.play_async(wav_path) if wav_path else None

    total_ms = max(400, int(duration * 1000))
    fade_in_ms = 220
    fade_out_ms = 500
    tick_ms = 40
    state = {"elapsed": 0, "frame": 0}

    def set_alpha(value: float) -> None:
        try:
            root.wm_attributes("-alpha", max(0.0, min(1.0, value)) * opacity)
        except Exception:
            pass

    def tick() -> None:
        state["elapsed"] += tick_ms
        elapsed = state["elapsed"]

        if elapsed < fade_in_ms:
            set_alpha(elapsed / fade_in_ms)
        elif elapsed > total_ms - fade_out_ms:
            set_alpha(max(0, total_ms - elapsed) / fade_out_ms)
        else:
            set_alpha(1.0)

        wanted = min(len(art.DOOT_FRAMES) - 1, elapsed // art.FRAME_MS)
        if wanted != state["frame"]:
            state["frame"] = wanted
            label.configure(text=art.frame(wanted))

        if elapsed >= total_ms:
            root.quit()
            return
        root.after(tick_ms, tick)

    root.after(tick_ms, tick)
    try:
        root.mainloop()
    finally:
        sound.stop(player)
        try:
            root.destroy()
        except Exception:
            pass
