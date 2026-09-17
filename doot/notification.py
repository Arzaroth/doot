"""Toast visuel affiche lorsqu'un succes est debloque."""

from __future__ import annotations

import time
from pathlib import Path

from desktop_overlay import window as overlay_window

from . import screens, sound

TRANSPARENT_KEY = "#ff00ff"
PANEL_BG = "#11131f"
PANEL_BORDER = "#d98b2b"
TITLE_COLOR = "#fff4dc"
ACCENT_COLOR = "#ffad42"
TEXT_COLOR = "#d8d8e2"
MARGIN = 24
TOAST_WIDTH = 440
BADGE_SIZE = 88
TICK_MS = 30
DEFAULT_DURATION = 3.4
VICTORY_RTTTL = Path(__file__).resolve().parent / "assets" / "victory-parade.rtttl"


def render_victory(dest: Path) -> Path:
    """Rend la micro-fanfare RTTTL avec le timbre de trompette de doot."""

    from . import melodie

    return melodie.render(dest, melodie.load(VICTORY_RTTTL))


def opacity_at(elapsed: float, duration: float) -> float:
    """Opacite du toast : entree vive, tenue, puis sortie douce."""

    total = max(0.8, float(duration))
    elapsed = max(0.0, float(elapsed))
    fade_in = min(0.18, total / 4)
    fade_out = min(0.45, total / 3)
    if elapsed < fade_in:
        return elapsed / fade_in
    if elapsed > total - fade_out:
        return max(0.0, (total - elapsed) / fade_out)
    return 1.0


def position(monitor, width: int, height: int, margin: int = MARGIN) -> tuple[int, int]:
    """Coin superieur droit du moniteur, toujours garde dans ses bornes."""

    width = min(max(1, width), monitor.width)
    height = min(max(1, height), monitor.height)
    x = monitor.x + max(0, monitor.width - width - margin)
    y = monitor.y + min(max(0, margin), max(0, monitor.height - height))
    return x, y


def geometry(monitor, width: int, height: int,
             margin: int = MARGIN) -> tuple[int, int, int, int]:
    """Dimensions et position du toast, toutes contenues dans le moniteur."""

    width = min(max(1, width), monitor.width)
    height = min(max(1, height), monitor.height)
    x, y = position(monitor, width, height, margin)
    return width, height, x, y


def _font(tkfont, size: int, weight: str = "normal"):
    try:
        font = tkfont.nametofont("TkDefaultFont").copy()
        font.configure(size=size, weight=weight)
        return font
    except Exception:
        return ("TkDefaultFont", size, weight)


def _badge_photo(tk, badge_path: Path | None):
    if badge_path is None or not badge_path.is_file():
        return None
    photo = tk.PhotoImage(file=str(badge_path))
    facteur = max(1, (photo.width() + BADGE_SIZE - 1) // BADGE_SIZE)
    return photo.subsample(facteur) if facteur > 1 else photo


def show(title: str, description: str, points: int, badge_path: Path | None = None,
         wav_path: Path | None = None, duration: float = DEFAULT_DURATION) -> None:
    """Affiche une medaille en haut a droite et joue la fanfare fournie."""

    _afficher(
        f"SUCCES DEBLOQUE  \u00b7  +{points} POINTS", title, description,
        badge_path=badge_path, wav_path=wav_path, duration=duration,
    )


def show_lot(titres: list, points: int, badge_path: Path | None = None,
             wav_path: Path | None = None, duration: float = DEFAULT_DURATION) -> None:
    """Une seule carte pour tout un lot de succes.

    Cinq succes gagnes ensemble faisaient cinq toasts a la suite, et le daemon
    n'avancait plus pendant dix-sept secondes. La carte les annonce ensemble,
    une fanfare pour tous, avec juste de quoi lire une ligne de plus.
    """

    lignes = "\n".join(f"\u00b7 {titre}" for titre in titres)
    _afficher(
        f"{len(titres)} SUCCES DEBLOQUES  \u00b7  +{points} POINTS",
        "Tableau de chasse", lignes,
        badge_path=badge_path, wav_path=wav_path,
        duration=duration + 0.6 * (len(titres) - 1),
    )


def _afficher(entete: str, titre: str, corps: str, badge_path: Path | None = None,
              wav_path: Path | None = None, duration: float = DEFAULT_DURATION) -> None:
    """Le toast lui-meme, quel que soit ce qu'il annonce.

    Volontairement bloquant, comme l'overlay principal : deux toasts ne se
    recouvrent jamais. L'appelant absorbe l'exception si tkinter manque, afin
    qu'un probleme de toast ne puisse jamais annuler le doot qui vient d'etre
    joue.
    """

    tk, tkfont = overlay_window.import_tk()
    root = tk.Tk()
    playback = None
    try:
        background = overlay_window.prepare_window(
            root,
            transparent_key=TRANSPARENT_KEY,
            fallback_background=PANEL_BG,
        )
        root.configure(bg=background)

        panel = tk.Frame(
            root,
            bg=PANEL_BG,
            highlightbackground=PANEL_BORDER,
            highlightcolor=PANEL_BORDER,
            highlightthickness=2,
            borderwidth=0,
        )
        panel.pack(fill="both", expand=True)

        photo = _badge_photo(tk, badge_path)
        if photo is not None:
            badge = tk.Label(panel, image=photo, bg=PANEL_BG, borderwidth=0)
            badge.image = photo
            badge.grid(row=0, column=0, rowspan=3, padx=(16, 12), pady=14)

        colonne = 1 if photo is not None else 0
        gauche = (0, 16) if photo is not None else (18, 18)
        tk.Label(
            panel,
            text=entete,
            bg=PANEL_BG,
            fg=ACCENT_COLOR,
            font=_font(tkfont, 9, "bold"),
            anchor="w",
        ).grid(row=0, column=colonne, sticky="sw", padx=gauche, pady=(14, 2))
        tk.Label(
            panel,
            text=titre,
            bg=PANEL_BG,
            fg=TITLE_COLOR,
            font=_font(tkfont, 15, "bold"),
            anchor="w",
        ).grid(row=1, column=colonne, sticky="w", padx=gauche, pady=0)
        tk.Label(
            panel,
            text=corps,
            bg=PANEL_BG,
            fg=TEXT_COLOR,
            font=_font(tkfont, 10),
            justify="left",
            anchor="nw",
            wraplength=280,
        ).grid(row=2, column=colonne, sticky="nw", padx=gauche, pady=(3, 14))
        panel.grid_columnconfigure(colonne, weight=1)

        root.update_idletasks()
        width = max(TOAST_WIDTH, panel.winfo_reqwidth())
        height = max(118, panel.winfo_reqheight())
        found = screens.monitors(root.winfo_screenwidth(), root.winfo_screenheight())
        monitor = screens.pick(found, "primary")
        width, height, x, y = geometry(monitor, width, height)
        overlay_window.move_window(root, width, height, x, y)

        try:
            root.wm_attributes("-alpha", 0.0)
        except Exception:
            pass
        overlay_window.show_window(root)
        playback = sound.play_async(wav_path, 0.0) if wav_path else None
        depart = time.monotonic()

        def tick() -> None:
            elapsed = time.monotonic() - depart
            try:
                root.wm_attributes("-alpha", opacity_at(elapsed, duration))
            except Exception:
                pass
            if elapsed >= max(0.8, duration):
                root.quit()
                return
            root.after(TICK_MS, tick)

        root.after(TICK_MS, tick)
        root.mainloop()
    finally:
        sound.release(playback)
        try:
            root.destroy()
        except Exception:
            pass
