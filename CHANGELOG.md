# Changelog

Toutes les évolutions notables de doot sont consignées ici.

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), et le
projet applique le [versionnage sémantique](https://semver.org/lang/fr/).

> Les versions antérieures à la 1.0.0 ont été étiquetées après coup : doot a été
> écrit d'une traite, sans numérotation au fil de l'eau. Les étiquettes marquent
> les étapes réelles du dépôt, mais `doot --version` répond `1.0.0` dans ces
> commits-là, la chaîne n'ayant jamais été incrémentée à l'époque.

## [Non publié]

## [1.0.0] - 2026-09-06

Première version numérotée pour de bon, et la seule où l'étiquette correspond à
ce que le code annonce.

### Ajouté
- `doot --update` met à jour une installation existante sur les trois systèmes :
  il relit la fiche laissée par l'installeur, rafraîchit la source et rejoue
  l'installeur avec les mêmes options, en arrêtant puis relançant le daemon.
- `doot --check-update` dit si une version plus récente existe, sans rien
  installer.
- Deux voies pour récupérer le code : `git pull --ff-only` si le dépôt cloné est
  toujours là, sinon l'archive de la branche principale téléchargée depuis
  GitHub. La seconde ne demande ni git ni le clone d'origine.
- Fiche `install.json` déposée par les installeurs dans le dossier de données :
  origine du code, commit, options d'installation.
- Refus explicite de se mettre à jour quand doot vient d'un gestionnaire de
  paquets, avec renvoi vers celui-ci.
- Ce changelog, et un workflow qui publie une release à chaque étiquette.

### Corrigé
- La fiche d'installation était illisible sous Windows : PowerShell 5.1 écrit
  l'UTF-8 avec un BOM, que `json.loads` refuse. `--check-update` annonçait un
  commit inconnu sur une installation pourtant enregistrée. Lecture en
  `utf-8-sig`.
- Les installeurs ne pouvaient plus être rejoués pendant que doot tournait : le
  daemon garde le dossier du code ouvert et Windows refuse de remplacer des
  fichiers verrouillés. Ils arrêtent désormais le daemon avant la copie et le
  relancent ensuite. Sous systemd, `enable --now` ne relançait pas une unité
  déjà active, c'est maintenant `restart`.
- `update.py` appelle `cli.paths()` au moment de s'en servir au lieu de
  l'importer une fois pour toutes, sans quoi la fonction n'était plus
  remplaçable et les tests écrivaient dans le vrai dossier de données.

## [0.7.0] - 2026-09-06

### Ajouté
- Spatialisation du son : le doot sort du côté où le squelette apparaît, calculé
  sur l'ensemble du bureau virtuel et non sur un écran isolé.
- Les WAV sont panoramisés dans leurs échantillons, ce qui fonctionne partout ;
  les formats compressés passent par MCI sous Windows et par un filtre `pan`
  pour `mpv` ou `ffplay` sous Linux.
- Option `--no-pan`.

### Corrigé
- Au centre exact, le canal droit sortait une unité en dessous du gauche sous
  Linux : `cos(π/4)` et `sin(π/4)` ne donnent pas le même dernier bit d'une libm
  à l'autre, et la troncature amplifiait l'écart. Gains arrondis, canaux
  strictement symétriques.
- Les échantillons sont arrondis au lieu d'être tronqués, `int()` ajoutant un
  biais à chaque valeur.

### Modifié
- Le canal dominant reste à plein volume, seul l'opposé est atténué. Un
  panoramique à puissance constante aurait rendu le doot 3 dB plus discret
  qu'avant, avec un saut audible au franchissement du seuil.

## [0.6.0] - 2026-09-06

### Ajouté
- Suite de tests qui fabrique les PNG octet par octet à partir de pixels connus,
  au lieu de comparer à Pillow : elle couvre le gris 2 et 4 bits, `tRNS` hors
  palette et sous 8 bits, le 16 bits, les cinq filtres de ligne et les entrées
  refusées ([#2](https://github.com/boubou666/doot/pull/2)).

### Corrigé
- Un IDAT illisible laissait remonter `zlib.error` au lieu de `PngError`,
  faisant mentir le contrat du module.

## [0.5.0] - 2026-09-06

### Ajouté
- Vraie transparence par pixel sous X11 et XWayland : fenêtre ARGB de profondeur
  32 ouverte via libX11 en ctypes, composée avec le bureau
  ([#1](https://github.com/boubou666/doot/pull/1)).
- Décodeur PNG maison en pur stdlib, sortie en BGRA à alpha prémultiplié.
- Click-through sous X11, que seul Windows avait jusque-là.

### Corrigé
- Les index de palette étaient étirés comme des intensités, ce qui faisait lire
  la mauvaise entrée de PLTE sur les PNG palette sous 8 bits.
- Le gestionnaire d'erreurs X était posé une seule fois alors qu'il est global
  au processus : un seul repli vers tkinter et la protection disparaissait. Il
  est désormais installé et restauré autour de chaque overlay.

## [0.4.0] - 2026-09-06

### Ajouté
- CI GitHub Actions sur Linux, Windows et macOS, de Python 3.9 à 3.13.
- Suite de tests couvrant les bornes de la saison, le placement multi-écrans, la
  synthèse du jingle et le refus hors saison.
- Vérification de la syntaxe des quatre installeurs.

## [0.3.0] - 2026-09-06

### Ajouté
- Image et son fournis d'office, pour que ça marche dès la première
  installation.
- Gestion multi-écrans : énumération réelle des moniteurs via Win32, `xrandr` et
  CoreGraphics, avec repli sur un écran unique.
- Options `--screen` et `--screens`.

### Corrigé
- L'installeur Windows ne trouvait jamais Python : le tableau d'arguments était
  passé comme un seul argument faute de splatting, et PowerShell mangeait les
  guillemets de la sonde.

## [0.2.0] - 2026-09-06

### Ajouté
- Mode image : un PNG ou un GIF animé remplace l'ASCII art.
- Sons compressés en plus du WAV : mp3, ogg, opus, flac, m4a.
- Section « Au secours, faites-le taire » en tête du README, avec le retrait
  manuel système par système.

### Modifié
- La durée d'affichage suit la durée du son, pour ne plus couper la note.
- Son et image sont relus à chaque apparition, donc modifiables sans redémarrer
  le daemon.

## [0.1.0] - 2026-09-06

### Ajouté
- Première version : un squelette trompettiste en ASCII surgit au hasard sur
  l'écran, avec un jingle deux notes synthétisé localement.
- Fenêtre saisonnière du 1er septembre au 31 octobre inclus, appliquée par le
  programme lui-même et pas seulement par le planificateur.
- Overlay sans bordure, sans vol de focus, click-through sous Windows.
- Installeurs sans droits administrateur pour Windows, macOS et Linux, avec
  démarrage automatique, et un PKGBUILD pour Arch.

[Non publié]: https://github.com/boubou666/doot/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/boubou666/doot/compare/v0.7.0...v1.0.0
[0.7.0]: https://github.com/boubou666/doot/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/boubou666/doot/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/boubou666/doot/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/boubou666/doot/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/boubou666/doot/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/boubou666/doot/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/boubou666/doot/releases/tag/v0.1.0
