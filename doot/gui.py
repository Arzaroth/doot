"""Lanceur graphique des commandes de doot.

La GUI ne reimplemente aucune action : elle compose une ligne de commande et
lance ``python -m doot``. La CLI reste donc l'unique source de verite, y
compris pour la validation, les profils et les futures evolutions.
"""

from __future__ import annotations

import argparse
import os
import queue
import shlex
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


ASSETS_DIR = Path(__file__).with_name("assets")


@dataclass(frozen=True)
class ParameterSpec:
    """Valeur obligatoire propre a une commande."""

    option: str
    label: str
    hint: str
    multiple: bool = False


@dataclass(frozen=True)
class CommandSpec:
    """Une action proposee dans la colonne de gauche."""

    key: str
    title: str
    description: str
    argv: tuple[str, ...] = ()
    parameters: tuple[ParameterSpec, ...] = ()
    image: str = "logo.png"
    detached: bool = False


@dataclass(frozen=True)
class OptionSpec:
    """Un reglage argparse rendu automatiquement dans la GUI."""

    dest: str
    option: str
    help: str
    kind: str
    choices: tuple[str, ...] = ()
    metavar: str = "VALEUR"
    default: object = None


COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "daemon", "Lancer le daemon",
        "Reveille doot en arriere-plan avec les reglages choisis. La GUI peut ensuite etre fermee.",
        image="success/ca_tourne.png", detached=True,
    ),
    CommandSpec(
        "once", "Faire un doot maintenant",
        "Affiche une apparition tout de suite, puis quitte.",
        ("--once",), image="success/premier_doot.png",
    ),
    CommandSpec(
        "play", "Jouer une melodie",
        "Joue une melodie fournie ou un fichier RTTTL personnel.",
        parameters=(ParameterSpec("--play", "Melodie", "nom ou chemin du fichier .rtttl"),),
        image="success/maestro.png",
    ),
    CommandSpec(
        "rickroll", "Rickroll macabre",
        "Joue immediatement la melodie rickroll en doots.",
        ("--rickroll",), image="success/rickroll.png",
    ),
    CommandSpec(
        "melodies", "Voir les melodies",
        "Liste les melodies personnelles et celles fournies avec doot.",
        ("--melodies",), image="success/jukebox_macabre.png",
    ),
    CommandSpec(
        "events", "Voir les rencontres",
        "Liste toutes les rencontres rares disponibles et leur commande d'essai.",
        ("--events",), image="success/collection_evenements.png",
    ),
    CommandSpec(
        "event", "Forcer une rencontre",
        "Declenche une rencontre rare precise, puis quitte.",
        parameters=(ParameterSpec("--event", "Rencontre", "parade, pluie ou vortex"),),
        image="success/choregraphe.png",
    ),
    CommandSpec(
        "achievements", "Voir les succes",
        "Affiche les medailles, le score et la progression locale.",
        ("--achievements",), image="success/cent_doots.png",
    ),
    CommandSpec(
        "status", "Etat de doot",
        "Montre la saison, le daemon actif, l'audio et l'image utilises.",
        ("--status",), image="success/ca_tourne.png",
    ),
    CommandSpec(
        "stop", "Arreter le daemon",
        "Arrete proprement l'instance de doot qui tourne en arriere-plan.",
        ("--stop",), image="success/premier_doot.png",
    ),
    CommandSpec(
        "screens", "Voir les ecrans",
        "Liste les ecrans detectes et leurs index utilisables avec --screen.",
        ("--screens",), image="success/quatre_coins.png",
    ),
    CommandSpec(
        "profiles", "Voir les profils",
        "Liste les profils persistants et indique celui qui est actif.",
        ("--profiles",), image="success/profil_actif.png",
    ),
    CommandSpec(
        "save-profile", "Enregistrer un profil",
        "Sauvegarde les reglages coches dans un nouveau profil.",
        parameters=(ParameterSpec("--save-profile", "Nom du profil", "par exemple : parade"),),
        image="success/profil_actif.png",
    ),
    CommandSpec(
        "activate-profile", "Activer un profil",
        "Rend un profil automatique pour les prochains lancements.",
        parameters=(ParameterSpec("--activate-profile", "Nom du profil", "profil deja enregistre"),),
        image="success/profil_actif.png",
    ),
    CommandSpec(
        "deactivate-profile", "Desactiver le profil",
        "Revient aux reglages historiques sans supprimer les profils.",
        ("--deactivate-profile",), image="success/profil_actif.png",
    ),
    CommandSpec(
        "delete-profile", "Supprimer un profil",
        "Supprime definitivement un profil persistant.",
        parameters=(ParameterSpec("--delete-profile", "Nom du profil", "profil a supprimer"),),
        image="success/profil_actif.png",
    ),
    CommandSpec(
        "sync-init", "Configurer la synchro",
        "Synchronise les succes par un dossier partage ; utilise 'off' pour l'arreter.",
        parameters=(ParameterSpec("--sync-init", "Dossier partage", "chemin du dossier, ou off"),),
        image="success/canon_a_os.png",
    ),
    CommandSpec(
        "export", "Exporter les succes",
        "Ecrit la progression de cette machine dans un fichier ou un dossier.",
        parameters=(ParameterSpec("--export", "Destination", "fichier, dossier, ou - pour la sortie"),),
        image="success/mille_doots.png",
    ),
    CommandSpec(
        "merge", "Fusionner des succes",
        "Importe sans doublon la progression d'autres machines.",
        parameters=(ParameterSpec(
            "--merge", "Sources", "plusieurs chemins peuvent etre separes par un point-virgule", True,
        ),),
        image="success/collection_evenements.png",
    ),
    CommandSpec(
        "paths", "Voir les chemins",
        "Affiche les dossiers de donnees, sons, images, melodies et journal.",
        ("--paths",), image="success/melodie_perso.png",
    ),
    CommandSpec(
        "regen-sound", "Regenerer le jingle",
        "Recree le jingle synthetise, puis affiche l'etat de doot.",
        ("--regen-sound", "--status"), image="success/orchestre.png",
    ),
    CommandSpec(
        "check-update", "Chercher une mise a jour",
        "Verifie si une version plus recente existe, sans rien installer.",
        ("--check-update",), image="success/sept_jours.png",
    ),
    CommandSpec(
        "update", "Mettre doot a jour",
        "Recupere la derniere version et rejoue l'installeur.",
        ("--update",), image="success/sept_jours.png",
    ),
    CommandSpec(
        "art", "Art terminal",
        "Imprime le squelette en ASCII dans la console integree.",
        ("--art",), image="success/premier_doot.png",
    ),
    CommandSpec(
        "help", "Aide complete",
        "Affiche toutes les options de la ligne de commande.",
        ("--help",), image="logo.png",
    ),
    CommandSpec(
        "version", "Version",
        "Affiche la version installee de doot.",
        ("--version",), image="logo.png",
    ),
)


COMMAND_OPTIONS = {
    option
    for command in COMMANDS
    for option in (
        *command.argv,
        *(parameter.option for parameter in command.parameters),
    )
    if option.startswith("--")
}
COMMAND_OPTIONS.update({"--gui", "--help"})


def _long_option(action: argparse.Action) -> str | None:
    """Le nom long canonique d'une action argparse."""

    for option in action.option_strings:
        if option.startswith("--"):
            return option
    return action.option_strings[0] if action.option_strings else None


def option_specs(parser: argparse.ArgumentParser | None = None) -> tuple[OptionSpec, ...]:
    """Extrait tous les reglages non commandes depuis le vrai parser CLI."""

    if parser is None:
        from .cli import build_parser

        parser = build_parser()

    specs = []
    for action in parser._actions:
        option = _long_option(action)
        if not option or set(action.option_strings) & COMMAND_OPTIONS:
            continue
        if isinstance(action, argparse._StoreTrueAction):
            kind = "boolean"
        elif action.choices:
            kind = "choice"
        else:
            kind = "value"
        choices = tuple(str(choice) for choice in (action.choices or ()))
        metavar = action.metavar or action.dest.replace("_", "-").upper()
        specs.append(OptionSpec(
            dest=action.dest,
            option=option,
            help=action.help or "",
            kind=kind,
            choices=choices,
            metavar=str(metavar),
            default=action.default,
        ))
    return tuple(specs)


def build_command_argv(
    command: CommandSpec,
    parameter_values: Mapping[str, object],
    setting_values: Mapping[str, object],
    settings: Sequence[OptionSpec] | None = None,
    *,
    strict: bool = True,
) -> list[str]:
    """Compose argv sans shell, donc sans probleme d'echappement ou d'injection."""

    argv = list(command.argv)
    for parameter in command.parameters:
        raw = str(parameter_values.get(parameter.option, "")).strip()
        if not raw:
            if strict:
                raise ValueError(f"Le champ « {parameter.label} » est obligatoire.")
            argv.extend((parameter.option, f"<{parameter.hint}>"))
            continue
        values = [raw]
        if parameter.multiple:
            values = [value.strip() for value in raw.split(";") if value.strip()]
        argv.append(parameter.option)
        argv.extend(values)

    for spec in settings or option_specs():
        value = setting_values.get(spec.dest)
        if spec.kind == "boolean":
            if value:
                argv.append(spec.option)
        elif value is not None and str(value).strip():
            argv.extend((spec.option, str(value).strip()))
    return argv


def format_command(argv: Sequence[str]) -> str:
    """Representation lisible de la commande exacte qui sera lancee."""

    words = ["doot", *argv]
    if os.name == "nt":
        return subprocess.list2cmdline(words)
    return shlex.join(words)


class BoneScrollbar:
    """Scrollbar verticale dessinee comme un os, compatible avec ``yview``."""

    def __init__(self, master, tk_module, command, *, background: str,
                 bone: str, outline: str, track: str) -> None:
        self.tk = tk_module
        self.command = command
        self.first = 0.0
        self.last = 1.0
        self.thumb_top = 5.0
        self.thumb_bottom = 45.0
        self.drag_offset: float | None = None
        self.background = background
        self.bone = bone
        self.outline = outline
        self.track = track
        self.canvas = tk_module.Canvas(
            master, width=24, bg=background, bd=0, highlightthickness=0,
            cursor="hand2",
        )
        self.canvas.bind("<Configure>", lambda _event: self._draw())
        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)

    def pack(self, *args, **kwargs):
        return self.canvas.pack(*args, **kwargs)

    def grid(self, *args, **kwargs):
        return self.canvas.grid(*args, **kwargs)

    def set(self, first, last) -> None:
        self.first = max(0.0, min(1.0, float(first)))
        self.last = max(self.first, min(1.0, float(last)))
        self._draw()

    def _metrics(self) -> tuple[float, float, float]:
        height = max(1.0, float(self.canvas.winfo_height()))
        padding = 7.0
        track_length = max(1.0, height - padding * 2)
        visible = max(0.0, min(1.0, self.last - self.first))
        thumb_length = min(track_length, max(42.0, track_length * visible))
        travel = max(0.0, track_length - thumb_length)
        if visible >= 1.0 or travel == 0.0:
            top = padding
        else:
            top = padding + travel * (self.first / max(0.0001, 1.0 - visible))
        return top, top + thumb_length, travel

    def _draw(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        middle = width / 2
        canvas.create_line(
            middle, 5, middle, height - 5, fill=self.track, width=2,
        )
        top, bottom, _travel = self._metrics()
        self.thumb_top, self.thumb_bottom = top, bottom

        # Diaphyse : la tige centrale legerement doree de l'os.
        canvas.create_rectangle(
            middle - 3, top + 7, middle + 3, bottom - 7,
            fill=self.bone, outline=self.outline, width=1,
        )
        # Epiphyses : deux lobes a chaque extremite donnent la silhouette d'os.
        for y1, y2 in ((top, top + 11), (bottom - 11, bottom)):
            canvas.create_oval(
                middle - 8, y1, middle, y2,
                fill=self.bone, outline=self.outline, width=1,
            )
            canvas.create_oval(
                middle, y1, middle + 8, y2,
                fill=self.bone, outline=self.outline, width=1,
            )
        canvas.create_oval(
            middle - 4, top + 4, middle + 4, top + 12,
            fill=self.bone, outline=self.outline, width=1,
        )
        canvas.create_oval(
            middle - 4, bottom - 12, middle + 4, bottom - 4,
            fill=self.bone, outline=self.outline, width=1,
        )

    def _press(self, event) -> None:
        if self.thumb_top <= event.y <= self.thumb_bottom:
            self.drag_offset = event.y - self.thumb_top
        else:
            direction = -1 if event.y < self.thumb_top else 1
            self.command("scroll", direction, "pages")

    def _drag(self, event) -> None:
        if self.drag_offset is None:
            return
        top, bottom, travel = self._metrics()
        if travel <= 0:
            return
        padding = 7.0
        fraction = (event.y - self.drag_offset - padding) / travel
        self.command("moveto", max(0.0, min(1.0, fraction)))

    def _release(self, _event) -> None:
        self.drag_offset = None


class DootApp:
    """Fenetre Tkinter : galerie de commandes, reglages et sortie integree."""

    BG = "#0e0b14"
    PANEL = "#171120"
    PANEL_2 = "#20172b"
    CARD = "#261b32"
    CARD_ACTIVE = "#3b2547"
    GOLD = "#d7a84a"
    GOLD_LIGHT = "#f3d486"
    BONE = "#f2e7cf"
    MUTED = "#aa9cb4"
    PURPLE = "#9b6bd1"
    EMBER = "#e76f36"

    def __init__(self, root) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.ttk = ttk
        self.root = root
        self.settings = option_specs()
        self.setting_vars: dict[str, object] = {}
        self.parameter_vars: dict[str, object] = {}
        self.command_buttons: dict[str, object] = {}
        self.images: dict[str, object] = {}
        self.events: queue.Queue = queue.Queue()
        self.processes: list[subprocess.Popen] = []

        root.title("doot — grimoire de commandes")
        root.geometry("1180x860")
        root.minsize(940, 700)
        root.configure(bg=self.BG)
        self._style()
        icon = self._load_image("logo.png", 64)
        if icon is not None:
            root.iconphoto(True, icon)

        self.selected_key = tk.StringVar(value=COMMANDS[0].key)
        self.command_title = tk.StringVar()
        self.command_description = tk.StringVar()
        self.preview = tk.StringVar()

        self._build_header()
        self._build_body()
        self._select_command(COMMANDS[0].key)
        self.root.after(80, self._drain_events)

    def _style(self) -> None:
        style = self.ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", background=self.BG, foreground=self.BONE,
                        font=("Segoe UI", 10))
        style.configure("TFrame", background=self.BG)
        style.configure("Panel.TFrame", background=self.PANEL)
        style.configure("Card.TFrame", background=self.PANEL_2)
        style.configure("TLabel", background=self.BG, foreground=self.BONE)
        style.configure("Muted.TLabel", foreground=self.MUTED)
        style.configure("Gold.TLabel", foreground=self.GOLD_LIGHT)
        style.configure("Title.TLabel", foreground=self.GOLD_LIGHT,
                        font=("Georgia", 24, "bold"))
        style.configure("CommandTitle.TLabel", foreground=self.GOLD_LIGHT,
                        background=self.PANEL, font=("Georgia", 18, "bold"))
        style.configure("Panel.TLabel", background=self.PANEL)
        style.configure("PanelMuted.TLabel", background=self.PANEL, foreground=self.MUTED)
        style.configure("Option.TLabel", background=self.PANEL_2,
                        foreground=self.GOLD_LIGHT, font=("Consolas", 9, "bold"))
        style.configure("OptionHelp.TLabel", background=self.PANEL_2,
                        foreground=self.MUTED, font=("Segoe UI", 9))
        style.configure("TEntry", fieldbackground="#120e19", foreground=self.BONE,
                        insertcolor=self.BONE, bordercolor="#4a365a", padding=7)
        style.configure("TCombobox", fieldbackground="#120e19", foreground=self.BONE,
                        arrowcolor=self.GOLD, bordercolor="#4a365a", padding=6)
        style.map("TCombobox", fieldbackground=[("readonly", "#120e19")],
                  foreground=[("readonly", self.BONE)])
        style.configure("TCheckbutton", background=self.PANEL_2, foreground=self.BONE,
                        indicatorcolor="#120e19", indicatormargin=5)
        style.map("TCheckbutton", background=[("active", self.PANEL_2)],
                  indicatorcolor=[("selected", self.EMBER)])
        style.configure("Run.TButton", background=self.EMBER, foreground="#fff8e8",
                        borderwidth=0, padding=(18, 11), font=("Segoe UI", 11, "bold"))
        style.map("Run.TButton", background=[("active", "#f28b51"), ("pressed", "#bd4f25")])
        style.configure("Clear.TButton", background="#382745", foreground=self.BONE,
                        borderwidth=0, padding=(12, 8))
        style.map("Clear.TButton", background=[("active", "#4c3560")])
        style.configure("TLabelframe", background=self.PANEL, bordercolor="#4c365a")
        style.configure("TLabelframe.Label", background=self.PANEL,
                        foreground=self.GOLD_LIGHT, font=("Georgia", 11, "bold"))
        style.configure("Vertical.TScrollbar", background="#33223e", troughcolor=self.BG,
                        arrowcolor=self.GOLD, bordercolor=self.BG)
        style.configure("TNotebook", background=self.PANEL, borderwidth=0)
        style.configure("TNotebook.Tab", background="#24192f", foreground=self.MUTED,
                        borderwidth=0, padding=(16, 8))
        style.map("TNotebook.Tab", background=[("selected", self.CARD_ACTIVE)],
                  foreground=[("selected", self.GOLD_LIGHT)])

    def _load_image(self, relative: str, target: int = 58):
        key = f"{relative}:{target}"
        if key in self.images:
            return self.images[key]
        try:
            source = self.tk.PhotoImage(file=str(ASSETS_DIR / relative))
            factor = max(1, (max(source.width(), source.height()) + target - 1) // target)
            image = source.subsample(factor)
        except Exception:
            image = None
        self.images[key] = image
        return image

    def _build_header(self) -> None:
        header = self.tk.Frame(self.root, bg=self.BG, height=224)
        header.pack(fill="x", padx=24, pady=(18, 8))
        header.pack_propagate(False)

        copy = self.tk.Frame(header, bg=self.BG)
        copy.pack(side="left", fill="both", expand=True, padx=(14, 10), pady=24)
        self.tk.Label(
            copy, text="LE GRIMOIRE DE DOOT", bg=self.BG, fg=self.GOLD,
            font=("Segoe UI", 10, "bold"), anchor="w",
        ).pack(fill="x")
        self.tk.Label(
            copy, text="Invoque chaque commande\nsans quitter la crypte.",
            bg=self.BG, fg=self.BONE, font=("Georgia", 27, "bold"),
            justify="left", anchor="w",
        ).pack(fill="x", pady=(6, 8))
        self.tk.Label(
            copy,
            text="Choisis une action, ajuste ses runes, puis sonne la trompette.",
            bg=self.BG, fg=self.MUTED, font=("Segoe UI", 11), anchor="w",
        ).pack(fill="x")

        hero = self._load_image("gui-command-center.png", 210)
        self.tk.Label(header, image=hero, bg=self.BG, bd=0).pack(
            side="right", padx=(8, 24), pady=2,
        )

        self.tk.Frame(self.root, bg=self.GOLD, height=1).pack(fill="x", padx=38)

    def _build_body(self) -> None:
        body = self.tk.PanedWindow(
            self.root, orient="horizontal", bg=self.BG, bd=0,
            sashwidth=7, sashrelief="flat",
        )
        body.pack(fill="both", expand=True, padx=24, pady=(12, 20))

        gallery = self.tk.Frame(body, bg=self.PANEL, width=365)
        details = self.tk.Frame(body, bg=self.PANEL)
        body.add(gallery, minsize=300, width=365)
        body.add(details, minsize=500)
        self._build_gallery(gallery)
        self._build_details(details)

    def _build_gallery(self, parent) -> None:
        self.tk.Label(
            parent, text="COMMANDES", bg=self.PANEL, fg=self.GOLD_LIGHT,
            font=("Georgia", 14, "bold"), anchor="w",
        ).pack(fill="x", padx=18, pady=(17, 10))

        canvas = self.tk.Canvas(parent, bg=self.PANEL, highlightthickness=0, bd=0)
        scrollbar = self._bone_scrollbar(parent, canvas.yview, self.PANEL)
        holder = self.tk.Frame(canvas, bg=self.PANEL)
        window = canvas.create_window((0, 0), window=holder, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y", padx=(0, 3), pady=(0, 12))
        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 12))
        holder.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        self._wheel_scroll(canvas, holder)

        for command in COMMANDS:
            image = self._load_image(command.image)
            button = self.tk.Button(
                holder, text=command.title, image=image, compound="left",
                command=lambda key=command.key: self._select_command(key),
                bg=self.CARD, fg=self.BONE, activebackground=self.CARD_ACTIVE,
                activeforeground=self.GOLD_LIGHT, bd=0, relief="flat",
                anchor="w", justify="left", padx=10, pady=8,
                font=("Segoe UI", 10, "bold"), cursor="hand2",
            )
            button.pack(fill="x", padx=5, pady=3)
            self.command_buttons[command.key] = button

    def _build_details(self, parent) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        intro = self.tk.Frame(parent, bg=self.PANEL)
        intro.grid(row=0, column=0, sticky="ew", padx=22, pady=(17, 10))
        self.ttk.Label(intro, textvariable=self.command_title,
                       style="CommandTitle.TLabel").pack(anchor="w")
        self.ttk.Label(
            intro, textvariable=self.command_description, style="PanelMuted.TLabel",
            wraplength=680, justify="left",
        ).pack(fill="x", anchor="w", pady=(5, 0))

        self.parameter_box = self.ttk.LabelFrame(parent, text="  Parametres de la commande  ")
        self.parameter_box.grid(row=1, column=0, sticky="ew", padx=22, pady=(4, 9))

        notebook = self.ttk.Notebook(parent)
        notebook.grid(row=2, column=0, sticky="nsew", padx=22, pady=(0, 10))
        options_tab = self.tk.Frame(notebook, bg=self.PANEL_2)
        output_tab = self.tk.Frame(notebook, bg="#0b0910")
        notebook.add(options_tab, text="  Reglages  ")
        notebook.add(output_tab, text="  Sortie  ")
        self.notebook = notebook
        self.output_tab = output_tab
        self._build_settings(options_tab)
        self._build_output(output_tab)

        launch = self.tk.Frame(parent, bg=self.PANEL)
        launch.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 17))
        preview_label = self.tk.Label(
            launch, textvariable=self.preview, bg="#0b0910", fg=self.PURPLE,
            font=("Consolas", 9), anchor="w", justify="left", padx=12, pady=9,
        )
        preview_label.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.ttk.Button(
            launch, text="SONNER LA TROMPETTE  ›", style="Run.TButton",
            command=self._run_selected,
        ).pack(side="right")

    def _build_settings(self, parent) -> None:
        canvas = self.tk.Canvas(parent, bg=self.PANEL_2, highlightthickness=0, bd=0)
        scrollbar = self._bone_scrollbar(parent, canvas.yview, self.PANEL_2)
        holder = self.tk.Frame(canvas, bg=self.PANEL_2)
        window = canvas.create_window((0, 0), window=holder, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y", padx=(0, 3), pady=4)
        canvas.pack(side="left", fill="both", expand=True)
        holder.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        self._wheel_scroll(canvas, holder)

        heading = self.tk.Frame(holder, bg=self.PANEL_2)
        heading.pack(fill="x", padx=16, pady=(13, 7))
        self.tk.Label(
            heading, text="Toutes les options de doot", bg=self.PANEL_2,
            fg=self.GOLD_LIGHT, font=("Georgia", 13, "bold"), anchor="w",
        ).pack(side="left")
        self.ttk.Button(
            heading, text="Effacer les reglages", style="Clear.TButton",
            command=self._clear_settings,
        ).pack(side="right")

        for index, spec in enumerate(self.settings):
            row = self.tk.Frame(holder, bg=self.PANEL_2)
            row.pack(fill="x", padx=16, pady=5)
            labels = self.tk.Frame(row, bg=self.PANEL_2)
            labels.pack(side="left", fill="x", expand=True, padx=(0, 12))
            self.ttk.Label(labels, text=spec.option, style="Option.TLabel").pack(anchor="w")
            help_text = spec.help
            if spec.kind != "boolean" and spec.default not in (None, ""):
                help_text += f"  ·  defaut : {spec.default}"
            self.ttk.Label(
                labels, text=help_text, style="OptionHelp.TLabel",
                wraplength=420, justify="left",
            ).pack(fill="x", anchor="w", pady=(1, 0))

            if spec.kind == "boolean":
                variable = self.tk.BooleanVar(value=False)
                widget = self.ttk.Checkbutton(row, text="Activer", variable=variable)
            elif spec.kind == "choice":
                variable = self.tk.StringVar(value="")
                widget = self.ttk.Combobox(
                    row, textvariable=variable, values=("", *spec.choices),
                    state="readonly", width=19,
                )
            else:
                variable = self.tk.StringVar(value="")
                widget = self.ttk.Entry(row, textvariable=variable, width=22)
            widget.pack(side="right", padx=(4, 2))
            variable.trace_add("write", lambda *_args: self._update_preview())
            self.setting_vars[spec.dest] = variable

            self.tk.Frame(holder, bg="#30233c", height=1).pack(
                fill="x", padx=16, pady=(2 if index < len(self.settings) - 1 else 12, 0),
            )

    def _build_output(self, parent) -> None:
        toolbar = self.tk.Frame(parent, bg="#0b0910")
        toolbar.pack(fill="x", padx=10, pady=(8, 0))
        self.tk.Label(
            toolbar, text="JOURNAL D'INVOCATION", bg="#0b0910", fg=self.GOLD,
            font=("Consolas", 9, "bold"),
        ).pack(side="left")
        self.ttk.Button(
            toolbar, text="Effacer", style="Clear.TButton", command=self._clear_output,
        ).pack(side="right")
        output_body = self.tk.Frame(parent, bg="#0b0910")
        output_body.pack(fill="both", expand=True)
        self.output = self.tk.Text(
            output_body, bg="#0b0910", fg=self.BONE, insertbackground=self.BONE,
            selectbackground="#523a67", relief="flat", bd=0,
            font=("Consolas", 10), wrap="word", padx=14, pady=12,
        )
        output_scrollbar = self._bone_scrollbar(
            output_body, self.output.yview, "#0b0910",
        )
        self.output.configure(yscrollcommand=output_scrollbar.set)
        output_scrollbar.pack(side="right", fill="y", padx=(0, 3), pady=4)
        self.output.pack(side="left", fill="both", expand=True)
        self.output.configure(state="disabled")
        self.output.tag_configure("command", foreground=self.PURPLE)
        self.output.tag_configure("success", foreground=self.GOLD_LIGHT)
        self.output.tag_configure("error", foreground="#ff7b72")

    def _bone_scrollbar(self, parent, command, background: str) -> BoneScrollbar:
        return BoneScrollbar(
            parent, self.tk, command, background=background,
            bone=self.BONE, outline=self.GOLD, track="#4b3459",
        )

    def _wheel_scroll(self, canvas, widget) -> None:
        def bind(_event):
            canvas.bind_all(
                "<MouseWheel>",
                lambda event: canvas.yview_scroll(int(-event.delta / 120), "units"),
            )
            canvas.bind_all("<Button-4>", lambda _e: canvas.yview_scroll(-1, "units"))
            canvas.bind_all("<Button-5>", lambda _e: canvas.yview_scroll(1, "units"))

        def unbind(_event):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        widget.bind("<Enter>", bind)
        widget.bind("<Leave>", unbind)

    def _selected_command(self) -> CommandSpec:
        key = self.selected_key.get()
        return next(command for command in COMMANDS if command.key == key)

    def _select_command(self, key: str) -> None:
        self.selected_key.set(key)
        command = self._selected_command()
        for command_key, button in self.command_buttons.items():
            selected = command_key == key
            button.configure(
                bg=self.CARD_ACTIVE if selected else self.CARD,
                fg=self.GOLD_LIGHT if selected else self.BONE,
            )
        self.command_title.set(command.title)
        self.command_description.set(command.description)
        for child in self.parameter_box.winfo_children():
            child.destroy()
        self.parameter_vars.clear()

        if not command.parameters:
            self.ttk.Label(
                self.parameter_box, text="Aucun parametre obligatoire.",
                style="PanelMuted.TLabel",
            ).pack(anchor="w", padx=12, pady=10)
        for parameter in command.parameters:
            row = self.tk.Frame(self.parameter_box, bg=self.PANEL)
            row.pack(fill="x", padx=12, pady=9)
            self.tk.Label(
                row, text=parameter.label, bg=self.PANEL, fg=self.GOLD_LIGHT,
                font=("Segoe UI", 9, "bold"), width=18, anchor="w",
            ).pack(side="left")
            variable = self.tk.StringVar(value="")
            variable.trace_add("write", lambda *_args: self._update_preview())
            self.ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
            self.tk.Label(
                row, text=parameter.hint, bg=self.PANEL, fg=self.MUTED,
                font=("Segoe UI", 8), anchor="w",
            ).pack(side="left", padx=(10, 0))
            self.parameter_vars[parameter.option] = variable
        self._update_preview()

    def _values(self, variables: Mapping[str, object]) -> dict[str, object]:
        return {name: variable.get() for name, variable in variables.items()}

    def _current_argv(self, *, strict: bool) -> list[str]:
        return build_command_argv(
            self._selected_command(), self._values(self.parameter_vars),
            self._values(self.setting_vars), self.settings, strict=strict,
        )

    def _update_preview(self) -> None:
        if not hasattr(self, "preview"):
            return
        self.preview.set(format_command(self._current_argv(strict=False)))

    def _clear_settings(self) -> None:
        for variable in self.setting_vars.values():
            variable.set(False if isinstance(variable, self.tk.BooleanVar) else "")

    def _append_output(self, text: str, tag: str | None = None) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", text, tag or ())
        self.output.see("end")
        self.output.configure(state="disabled")

    def _clear_output(self) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

    def _run_selected(self) -> None:
        try:
            argv = self._current_argv(strict=True)
        except ValueError as exc:
            self.notebook.select(self.output_tab)
            self._append_output(f"\n{exc}\n", "error")
            return

        command = self._selected_command()
        shown = format_command(argv)
        self.notebook.select(self.output_tab)
        self._append_output(f"\n❯ {shown}\n", "command")
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        popen_args = [sys.executable, "-m", "doot", *argv]
        try:
            if command.detached:
                kwargs = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
                          "stderr": subprocess.DEVNULL, "env": env}
                if os.name == "nt":
                    kwargs["creationflags"] = (
                        getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                        | getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    )
                else:
                    kwargs["start_new_session"] = True
                process = subprocess.Popen(popen_args, **kwargs)
                self.processes.append(process)
                self._append_output(
                    f"Daemon lance en arriere-plan (pid {process.pid}).\n", "success",
                )
                return

            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            process = subprocess.Popen(
                popen_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
                bufsize=1, env=env, creationflags=flags,
            )
            self.processes.append(process)
        except OSError as exc:
            self._append_output(f"Impossible de lancer doot : {exc}\n", "error")
            return

        threading.Thread(target=self._read_process, args=(process,), daemon=True).start()

    def _read_process(self, process: subprocess.Popen) -> None:
        assert process.stdout is not None
        for line in process.stdout:
            self.events.put(("line", line))
        self.events.put(("done", process.wait()))

    def _drain_events(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "line":
                    self._append_output(value)
                else:
                    tag = "success" if value == 0 else "error"
                    self._append_output(f"[termine avec le code {value}]\n", tag)
        except queue.Empty:
            pass
        self.processes[:] = [process for process in self.processes if process.poll() is None]
        self.root.after(80, self._drain_events)


def main() -> int:
    """Ouvre le lanceur ; renvoie 4 quand Tkinter ou l'affichage manque."""

    try:
        import tkinter as tk
    except ImportError:
        print("doot : la GUI demande tkinter (le paquet python3-tk sous Linux).", file=sys.stderr)
        return 4
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"doot : impossible d'ouvrir la GUI : {exc}", file=sys.stderr)
        return 4
    DootApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
