# doot

Un squelette trompettiste surgit au hasard sur ton écran, joue son petit air, puis disparaît.

**Uniquement du 1er septembre au 31 octobre inclus.** Le reste de l'année, le programme
tourne mais reste sagement endormi : le squelette range sa trompette.

```
                                        d    o    o    t   !
            .-"""""""-.
          .'           '.
         /   .-.   .-.   \
        |   ( o ) ( o )   |                  .-----.
        |       ___       |             ,--''       '.
        |      /   \      |            /             \
        |     |=====|     |   ,-------'               |
         \    |||||||========(                        |
          '.  |||||  .'       '------.                |
            '-._____.-'               \              /
             /|     |\                 '--.        ,'
            / |     | \                     '-----'
```

- **Multiplateforme** : Windows 10/11, macOS, Linux (Arch, Debian/Ubuntu, Fedora, openSUSE…)
- **Zéro dépendance** : uniquement la bibliothèque standard de Python 3.8+
- **Discret** : overlay sans bordure, qui ne vole jamais le focus et — sous Windows —
  laisse passer les clics de souris. Il ne bloque rien, il fait juste *doot*.
- **Saisonnier** : la fenêtre du 1er septembre au 31 octobre est appliquée par le
  programme lui-même, pas seulement par le planificateur.

## Installation

### Linux (dont Arch) et macOS

```bash
git clone https://github.com/boubou666/doot.git
cd doot
./install.sh
```

Le script copie le code dans `~/.local/share/doot/app`, crée la commande
`~/.local/bin/doot`, puis configure le démarrage automatique :
`systemd --user` si disponible, sinon une entrée XDG autostart, et un
LaunchAgent sur macOS.

Options : `./install.sh --no-autostart`, `--min 300`, `--max 1800`.

**Prérequis système** (`install.sh` te le dira si quelque chose manque) :

| Distribution  | Affichage (tkinter)                | Son (au choix)                                   |
| ------------- | ---------------------------------- | ------------------------------------------------ |
| Arch/Manjaro  | `sudo pacman -S python tk`         | `pipewire-audio`, `libpulse` ou `alsa-utils`      |
| Debian/Ubuntu | `sudo apt install python3-tk`      | déjà là (`paplay` / `aplay`)                      |
| Fedora        | `sudo dnf install python3-tkinter` | déjà là                                           |
| openSUSE      | `sudo zypper install python3-tk`   | déjà là                                           |
| macOS         | `brew install python-tk`           | `afplay`, intégré                                 |

### Arch Linux, via un paquet

```bash
cd packaging
makepkg -si
systemctl --user enable --now doot.service
```

### Windows

```powershell
git clone https://github.com/boubou666/doot.git
cd doot
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Python 3.8+ est requis (`winget install -e --id Python.Python.3.12`, en cochant
« tcl/tk »). Le script installe dans `%LOCALAPPDATA%\Programs\doot`, ajoute la
commande `doot` au PATH utilisateur et place un raccourci dans le dossier
Démarrage. Aucun droit administrateur, aucun composant système modifié.

### Sans installer (test rapide)

```bash
python3 -m doot --once --ignore-season
```

## Utilisation

```bash
doot                       # lance le daemon (c'est ce que fait le démarrage auto)
doot --once                # un doot tout de suite, puis on quitte
doot --once --ignore-season  # idem, même hors saison : pratique pour tester
doot --status              # saison, daemon, audio, tkinter
doot --stop                # arrête le daemon
doot --art                 # imprime le squelette dans le terminal
```

| Option | Défaut | Description |
| --- | --- | --- |
| `--min` / `--max` | `600` / `3600` | bornes du délai aléatoire entre deux doot, en secondes |
| `--duration` | `2.8` | durée d'affichage, en secondes |
| `--volume` | `0.55` | volume du jingle synthétisé, de `0.0` à `1.0` |
| `--opacity` | `1.0` | opacité maximale de l'overlay |
| `--font-size` | `15` | taille du squelette |
| `--center` | — | toujours au centre, au lieu d'une position aléatoire |
| `--no-sound` | — | mode muet |
| `--regen-sound` | — | régénère le jingle |
| `--ignore-season` | — | ignore la fenêtre saisonnière (tests) |
| `--quiet` | — | n'écrit que dans le journal |

## Le son

Aucun fichier audio n'est distribué avec le projet. Le petit motif deux notes est
**synthétisé localement** au premier lancement (harmoniques, vibrato, enveloppe
ADSR, soft clipping) et mis en cache dans le dossier de données.

Tu veux un autre son ? Dépose un ou plusieurs `.wav` dans le dossier `sound/` de
tes données (`doot --paths` te donne le chemin) : ils sont tirés au hasard et
remplacent le jingle. À toi de n'y mettre que des fichiers que tu as le droit
d'utiliser.

## Où sont les fichiers

`doot --paths` affiche tout. Par défaut :

| Système | Dossier de données |
| --- | --- |
| Linux   | `~/.local/share/doot` |
| macOS   | `~/Library/Application Support/doot` |
| Windows | `%LOCALAPPDATA%\doot` |

Il contient `doot.wav` (le jingle en cache), `doot.log` (le journal),
`doot.pid` et `sound/` (tes sons perso).

## Désinstallation

```bash
./uninstall.sh            # Linux / macOS   (--purge pour effacer les données)
```

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1   # Windows (-Purge)
```

## Dépannage

**Rien ne s'affiche** → `doot --status`. Si tkinter manque, installe le paquet
du tableau ci-dessus. Sous Wayland, l'overlay passe par XWayland ; si ton
compositeur le refuse, lance la session en X11 ou utilise `--center`.

**Pas de son** → `doot --status` indique le lecteur détecté. Sous Linux il faut
au moins un de `pw-play`, `paplay`, `aplay`, `ffplay`, `play`, `mpv`, `cvlc`.
Sans aucun, doot s'affiche en silence plutôt que de planter.

**Le fond n'est pas transparent** (Linux) → il faut un compositeur actif
(`picom`, KWin, Mutter…). Sinon le squelette s'affiche sur un fond sombre.

**Ça ne se déclenche jamais** → on est peut-être hors saison. `doot --status`
te dit la date de réouverture. Pour vérifier que tout marche :
`doot --once --ignore-season`.

**Le daemon ne redémarre pas à la session** →
`systemctl --user status doot` (Linux), `launchctl list | grep doot` (macOS),
ou vérifie le raccourci dans `shell:startup` (Windows).

## Comment ça marche

| Fichier | Rôle |
| --- | --- |
| `doot/season.py` | la fenêtre 1er septembre → 31 octobre |
| `doot/art.py` | l'ASCII art et les images de l'animation |
| `doot/sound.py` | synthèse du jingle et lecture selon l'OS |
| `doot/window.py` | l'overlay tkinter, la transparence, le fondu |
| `doot/cli.py` | la CLI, la boucle aléatoire, l'instance unique |

Le daemon tire un délai au hasard entre `--min` et `--max`, dort, vérifie que la
saison est toujours ouverte, affiche le squelette, recommence. Hors saison, il
se contente de revérifier la date toutes les heures.

## Licence

MIT. L'ASCII art et le jingle synthétisé sont originaux et fournis sous la même
licence.
