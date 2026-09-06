"""Overlay tkinter : le squelette apparait par-dessus tout, puis s'efface.

Deux modes :
  - image   : un PNG ou un GIF (anime) depose dans <data_dir>/image/
  - ASCII   : le squelette dessine en caracteres, quand il n'y a pas d'image

Multiplateforme :
  - Windows : fond reellement transparent (-transparentcolor) + fenetre
    "click-through" et sans vol de focus (styles etendus Win32).
  - macOS   : fenetre sans bordure, sans icone dans le Dock.
  - Linux   : type de fenetre "splash" quand le WM le supporte ; le fond est
    reellement transparent si un compositeur tourne, sinon fond sombre.
"""

from __future__ import annotations

import random
import sys
from fractions import Fraction
from pathlib import Path

from . import art, screens, sound

TRANSPARENT_KEY = "#ff00ff"
FALLBACK_BG = "#0b0b12"
FOREGROUND = "#f4f4f8"
GIF_FRAME_MS = 90

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


def _setup_transparency(window) -> str:
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


def _rescale(photo, scale: float):
    """Redimensionne une PhotoImage avec les seuls outils de Tk (zoom/subsample)."""
    if scale == 1.0 or scale <= 0:
        return photo
    ratio = Fraction(scale).limit_denominator(4)
    if ratio.numerator != 1:
        photo = photo.zoom(ratio.numerator)
    if ratio.denominator != 1:
        photo = photo.subsample(ratio.denominator)
    return photo


def _load_frames(tk, path: Path, scale: float) -> list:
    """Charge un PNG (1 image) ou un GIF (toutes ses images)."""
    frames = []
    if path.suffix.lower() == ".gif":
        index = 0
        while True:
            try:
                photo = tk.PhotoImage(file=str(path), format=f"gif -index {index}")
            except Exception:
                break
            frames.append(_rescale(photo, scale))
            index += 1
    if not frames:
        frames = [_rescale(tk.PhotoImage(file=str(path)), scale)]
    return frames


def _auto_scale(width: int, height: int, screen_w: int, screen_h: int) -> float:
    """Reduit l'image si elle mange plus de 40 % de l'ecran."""
    limit_h = screen_h * 0.40
    limit_w = screen_w * 0.40
    if height <= limit_h and width <= limit_w:
        return 1.0
    return min(limit_h / height, limit_w / width)


def show(
    wav_path: Path | None = None,
    duration: float = 2.8,
    font_size: int = 15,
    center: bool = False,
    opacity: float = 1.0,
    image_path: Path | None = None,
    scale: float | None = None,
    screen: str | int | None = None,
) -> None:
    """Affiche un doot et rend la main quand il a disparu.

    `screen` : None/"random" pour un ecran au hasard, "primary" pour l'ecran
    principal, ou l'index d'un ecran precis.
    """
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

    background = _setup_transparency(root)
    root.configure(bg=background)

    # Ecran d'accueil : tkinter ne sait pas decrire un montage multi-ecrans,
    # on demande au systeme (voir screens.py).
    monitor = screens.pick(
        screens.monitors(root.winfo_screenwidth(), root.winfo_screenheight()),
        screen,
    )
    screen_w, screen_h = monitor.width, monitor.height

    frames: list = []
    if image_path is not None:
        try:
            probe = tk.PhotoImage(file=str(image_path)) if image_path.suffix.lower() != ".gif" \
                else tk.PhotoImage(file=str(image_path), format="gif -index 0")
            wanted = scale if scale is not None else _auto_scale(
                probe.width(), probe.height(), screen_w, screen_h
            )
            frames = _load_frames(tk, image_path, wanted)
        except Exception:
            frames = []  # image illisible : on retombe sur l'ASCII

    widget_kwargs = dict(bg=background, borderwidth=0, highlightthickness=0)
    if frames:
        label = tk.Label(root, image=frames[0], **widget_kwargs)
        label.image = frames  # garde une reference, sinon Tk libere les images
    else:
        label = tk.Label(
            root,
            text=art.widest_frame(),
            font=_pick_font(tkfont, font_size),
            fg=FOREGROUND,
            justify="left",
            anchor="nw",
            padx=6,
            pady=6,
            **widget_kwargs,
        )
    label.pack()

    # Dimensionne sur l'etat le plus large, puis repart de la premiere image.
    root.update_idletasks()
    width = max(label.winfo_reqwidth(), 1)
    height = max(label.winfo_reqheight(), 1)
    if not frames:
        label.configure(text=art.frame(0))

    x, y = monitor.place(width, height, center, random)
    root.geometry(f"{width}x{height}+{x}+{y}")

    root.deiconify()
    _make_click_through(root)

    playback = sound.play_async(wav_path) if wav_path else None

    total_ms = max(400, int(duration * 1000))
    fade_in_ms = min(220, total_ms // 4)
    fade_out_ms = min(500, total_ms // 3)
    tick_ms = 40
    state = {"elapsed": 0, "step": 0}

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

        if frames:
            if len(frames) > 1:
                wanted = (elapsed // GIF_FRAME_MS) % len(frames)
                if wanted != state["step"]:
                    state["step"] = wanted
                    label.configure(image=frames[wanted])
        else:
            wanted = min(len(art.DOOT_FRAMES) - 1, elapsed // art.FRAME_MS)
            if wanted != state["step"]:
                state["step"] = wanted
                label.configure(text=art.frame(wanted))

        if elapsed >= total_ms:
            root.quit()
            return
        root.after(tick_ms, tick)

    root.after(tick_ms, tick)
    try:
        root.mainloop()
    finally:
        sound.release(playback)
        try:
            root.destroy()
        except Exception:
            pass
