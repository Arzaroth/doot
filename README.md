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
- **Multi-écrans** : les moniteurs sont énumérés pour de vrai (Win32, xrandr,
  CoreGraphics), le squelette surgit sur l'un d'eux au hasard, jamais à cheval
  entre deux dalles ni sous la barre des tâches.
- **Prêt à l'emploi** : le squelette et son *doot* sont livrés avec ; dépose ton
  propre PNG/GIF ou mp3 pour les remplacer, sans toucher au code.
- **Saisonnier** : la fenêtre du 1er septembre au 31 octobre est appliquée par le
  programme lui-même, pas seulement par le planificateur.

---

## 🛑 Au secours, faites-le taire

Pas de panique, rien n'est installé en profondeur et aucun droit administrateur n'a
été demandé. Trois niveaux, du plus doux au plus définitif :

```bash
doot --stop        # arrête le programme qui tourne, tout de suite
```

```bash
./uninstall.sh     # Linux / macOS : désinstalle tout, y compris le démarrage auto
```

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1   # Windows
```

Ajoute `--purge` (Linux/macOS) ou `-Purge` (Windows) pour effacer aussi le dossier de
données. Tu n'as plus le dépôt sous la main ? Tout se retire à la main :

| Système | Ce qu'il faut supprimer |
| --- | --- |
| **Linux** | `systemctl --user disable --now doot.service` puis `rm -rf ~/.config/systemd/user/doot.service ~/.config/autostart/doot.desktop ~/.local/bin/doot ~/.local/share/doot` |
| **macOS** | `launchctl unload ~/Library/LaunchAgents/com.doot.skeleton.plist` puis `rm -rf ~/Library/LaunchAgents/com.doot.skeleton.plist ~/.local/bin/doot ~/Library/Application\ Support/doot` |
| **Windows** | supprime le raccourci `doot` dans `shell:startup` (Win+R → `shell:startup`), puis les dossiers `%LOCALAPPDATA%\Programs\doot` et `%LOCALAPPDATA%\doot` |

Envie de le garder mais en plus discret ? `doot --min 7200 --max 28800` espace les
apparitions de 2 à 8 heures, et `--no-sound` le rend muet.

---

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
| Arch/Manjaro  | `sudo pacman -S python tk`         | `pipewire-audio`, `libpulse`, `alsa-utils`, `mpv` |
| Debian/Ubuntu | `sudo apt install python3-tk`      | déjà là (`paplay` / `aplay`)                      |
| Fedora        | `sudo dnf install python3-tkinter` | déjà là                                           |
| openSUSE      | `sudo zypper install python3-tk`   | déjà là                                           |
| macOS         | `brew install python-tk`           | `afplay`, intégré                                 |

Pour lire des **mp3** sous Linux il faut un lecteur qui gère le compressé :
`mpv`, `ffmpeg` (ffplay), `sox` ou `vlc`. Les `.wav` passent partout.

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
doot                         # lance le daemon (c'est ce que fait le démarrage auto)
doot --once                  # un doot tout de suite, puis on quitte
doot --once --ignore-season  # idem, même hors saison : pratique pour tester
doot --status                # saison, daemon, son et image utilisés
doot --stop                  # arrête le daemon
doot --paths                 # où sont les fichiers
doot --screens               # liste les écrans détectés
doot --art                   # imprime le squelette dans le terminal
```

| Option | Défaut | Description |
| --- | --- | --- |
| `--min` / `--max` | `600` / `3600` | bornes du délai aléatoire entre deux doot, en secondes |
| `--duration` | durée du son | durée d'affichage, en secondes (au moins 2.8) |
| `--image` | — | un PNG/GIF précis à afficher |
| `--no-image` | — | force l'ASCII art même si une image est disponible |
| `--scale` | auto | échelle de l'image (par défaut ajustée à l'écran) |
| `--volume` | `0.55` | volume du jingle synthétisé, de `0.0` à `1.0` |
| `--opacity` | `1.0` | opacité maximale de l'overlay |
| `--font-size` | `15` | taille du squelette ASCII |
| `--center` | — | toujours au centre, au lieu d'une position aléatoire |
| `--screen` | `random` | écran d'apparition : `random`, `primary`, ou un index (`0`, `1`…) |
| `--no-sound` | — | mode muet |
| `--regen-sound` | — | régénère le jingle |
| `--ignore-season` | — | ignore la fenêtre saisonnière (tests) |
| `--quiet` | — | n'écrit que dans le journal |

## Les médias

doot est livré avec le squelette et le son qu'on attend : `doot/assets/doot.png`
et `doot/assets/doot.mp3`, installés d'office. C'est le mème *skull trumpet*
(« doot doot »), qui circule un peu partout depuis 2010 ; il est inclus pour que
ça marche du premier coup. Si tu es l'ayant droit et que ça te dérange, ouvre une
issue et je les retire.

Trois niveaux de repli, dans cet ordre : tes fichiers → les fichiers fournis →
l'ASCII art et le jingle synthétisé maison (harmoniques, vibrato, enveloppe ADSR),
utilisés notamment sur un Linux sans lecteur mp3.

### Mettre les tiens

```bash
doot --paths        # affiche les deux dossiers ci-dessous
```

- **Image** → dossier `image/` : un `.png` ou un `.gif` (les GIF animés sont joués
  en boucle). Prends une image détourée, à fond transparent : sous Windows le fond
  disparaît complètement et le squelette flotte sur le bureau. Plusieurs fichiers ?
  Un est tiré au hasard à chaque apparition.
- **Son** → dossier `sound/` : `.wav`, `.mp3`, `.ogg`, `.flac`, `.m4a`, `.opus`.
  L'affichage s'allonge automatiquement pour couvrir toute la durée du son.

Tes fichiers passent devant ceux fournis, et ils sont relus à chaque apparition :
tu peux les changer pendant que le daemon tourne. Pour revenir au dessin ASCII et
au jingle synthétisé : `doot --no-image --regen-sound` (ou vide les deux dossiers
et supprime `doot/assets/`).

## Où sont les fichiers

`doot --paths` affiche tout. Par défaut :

| Système | Dossier de données |
| --- | --- |
| Linux   | `~/.local/share/doot` |
| macOS   | `~/Library/Application Support/doot` |
| Windows | `%LOCALAPPDATA%\doot` |

Il contient `image/` et `sound/` (tes médias), `doot.wav` (le jingle en cache),
`doot.log` (le journal) et `doot.pid`.

## Dépannage

**Rien ne s'affiche** → `doot --status`. Si tkinter manque, installe le paquet
du tableau ci-dessus. Sous Wayland, l'overlay passe par XWayland ; si ton
compositeur le refuse, lance la session en X11 ou utilise `--center`.

**Pas de son** → `doot --status` indique le lecteur détecté. Sous Linux il faut
au moins un de `mpv`, `ffplay`, `play`, `cvlc` (tous formats) ou `pw-play`,
`paplay`, `aplay` (wav). Sans aucun, doot s'affiche en silence plutôt que de planter.

**Mon image ne s'affiche pas** → tkinter ne lit que le PNG et le GIF. Convertis
ton jpg/webp, par exemple avec `ffmpeg -i image.webp image.png`. Une image
illisible fait simplement revenir l'ASCII art.

**Il n'apparaît que sur un seul écran** → `doot --screens` liste ce que doot
détecte. Sous Linux la détection passe par `xrandr` : sans lui (ou sous Wayland
pur), tout le bureau est vu comme un seul écran. Installe `xorg-xrandr`, ou fixe
la cible avec `doot --screen 0`. Avec des écrans à facteurs d'échelle différents
sous Windows, la position peut se décaler un peu : `--screen primary` évite le
problème.

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
| `doot/image.py` | le choix du PNG/GIF déposé par l'utilisateur |
| `doot/screens.py` | l'énumération des écrans (Win32 / xrandr / CoreGraphics) |
| `doot/sound.py` | synthèse du jingle, durée et lecture selon l'OS |
| `doot/window.py` | l'overlay tkinter, la transparence, le fondu |
| `doot/cli.py` | la CLI, la boucle aléatoire, l'instance unique |

Le daemon tire un délai au hasard entre `--min` et `--max`, dort, vérifie que la
saison est toujours ouverte, affiche le squelette, recommence. Hors saison, il
se contente de revérifier la date toutes les heures.

## Licence

Le **code** est sous licence MIT, ainsi que l'ASCII art et le jingle synthétisé,
qui sont originaux.

Les fichiers de `doot/assets/` sont l'exception : le mème *skull trumpet* n'est
pas de moi et n'est pas couvert par la licence MIT du projet. Il est inclus par
commodité ; retire-le si ton usage l'exige, et les médias que tu ajoutes toi-même
restent soumis à leurs propres droits.
