# Changelog

Toutes les évolutions notables de doot sont consignées ici.

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), et le
projet applique le [versionnage sémantique](https://semver.org/lang/fr/).

> Les versions antérieures à la 1.0.0 ont été étiquetées après coup : doot a été
> écrit d'une traite, sans numérotation au fil de l'eau. Les étiquettes marquent
> les étapes réelles du dépôt, mais `doot --version` répond `1.0.0` dans ces
> commits-là, la chaîne n'ayant jamais été incrémentée à l'époque.

## [Non publié]

### Ajouté
- Un overlay Wayland natif (`doot/wayland.py`), qui parle `wlr-layer-shell`
  directement sur la socket du compositeur. C'est le seul protocole qui laisse
  un client choisir sa sortie et s'y positionner : ni le cœur de Wayland ni
  xdg-shell ne le permettent, et XWayland divise les coordonnées par le facteur
  d'échelle global avant de poser la fenêtre sur une dalle qui ne suit pas la
  géométrie annoncée. Le multi-écrans devient donc exact, vérifié sur Hyprland ;
  Sway, river et KDE implémentent aussi layer-shell, mais le comportement de
  KWin sur les marges négatives du glissement n'a pas été regardé. GNOME ne
  l'implémente pas du tout : `available()` y renvoie faux et le chemin X11
  reprend la main. Toujours sans dépendance : le descripteur du tampon partagé
  passe par `SCM_RIGHTS`, tout est dans la bibliothèque standard.
- `--screens` et `--status` décrivent les écrans tels que les verra le backend
  qui affichera vraiment, et non un autre espace de coordonnées.

### Corrigé
- L'overlay Wayland lit la géométrie logique des écrans par
  `zxdg_output_manager_v1` au lieu de la déduire de `mode / scale`.
  `wl_output.scale` est un entier : sous échelle fractionnaire les compositeurs
  laissent `mode` en pixels physiques et arrondissent `scale` au supérieur, si
  bien qu'une dalle 2560 à l'échelle 1.5 était annoncée à 1280 unités logiques
  au lieu de 1707. Le squelette se cantonnait alors au quart supérieur gauche,
  et une entrée par la droite démarrait au milieu de la dalle au lieu de son
  bord. Le calcul précédent sert de repli si l'interface manque.
- Le son revient quand le doot est spatialisé. mpv n'atteint le filtre `pan` de
  libavfilter que par `--af=lavfi=[...]` ; écrit `--af=pan=...`, son analyseur
  d'options bute sur les barres verticales, refuse de démarrer et le doot est
  muet. Comme le panoramique s'applique dès que le squelette n'est pas au centre
  du bureau, presque tous les doots l'étaient sur une configuration multi-écrans.
- Un lecteur qui refuse la syntaxe du filtre est rejoué sans panoramique, au
  lieu de laisser un silence. Le module promettait déjà « non panoramisé plutôt
  que muet », mais rien ne tenait la promesse quand le refus venait du lecteur.
- Un son stéréo garde ses deux canaux quand le doot est spatialisé. Le filtre
  tirait les deux sorties du canal d'entrée gauche, ce qui jetait le droit,
  alors que `pan_wav` fait le même travail sur les WAV en gardant chacun le
  sien. Le même fichier changeait donc de rendu au franchissement de
  `SEUIL_PAN` — la marche exacte que `stereo_gains` s'applique à éviter par
  ailleurs. Un `aformat` monte d'abord le mono en stéréo, ce qui laisse une
  seule expression valable pour les deux sources.

## [1.4.2] - 2026-09-07

### Corrigé
- L'énumération des écrans sous Linux ne dépend plus du binaire `xrandr`, qui
  vit dans un paquet à part (`xorg-xrandr`, `x11-xserver-utils`) que rien
  n'installe pour un bureau. Sans lui, la détection échouait en silence et doot
  se rabattait sur un unique écran 1920x1080 à l'origine, sans rapport avec la
  machine. doot interroge maintenant RandR 1.5 sur la socket X, avec la même
  requête que celle envoyée par `xrandr --listmonitors` ; le binaire reste en
  second recours.

## [1.4.1] - 2026-09-07

### Ajouté
- Le `PKGBUILD` joue la suite de tests pendant la construction du paquet Arch,
  avec `python-pillow` en `checkdepends` pour que les tests de conformité PNG
  ne se contentent pas de sauter — sans lui, ils sauteraient en silence et la
  construction resterait verte.
- `optdepends` mentionne `mpv` et `ffmpeg` pour les sons compressés et la
  spatialisation, et `xorg-xrandr` pour la détection des écrans multiples.
- La CI vérifie la syntaxe du `PKGBUILD`, qui n'était couvert par rien.

### Corrigé
- La réécriture du chemin dans l'unité systemd est contrôlée : un `sed` qui ne
  trouvait plus son motif laissait sans un mot une unité pointant dans le vide.
  La construction échoue désormais.
- Le README annonçait « Depuis PyPI » puis expliquait d'abord comment installer
  uv. Les commandes doot passent devant, le prérequis derrière.

### Note
- `sha256sums` reste à `SKIP`, et c'est contraint et non négligent : ce fichier
  vit **dans** l'archive qu'il décrit, donc y inscrire la somme de cette archive
  la modifierait, et modifierait sa somme. Le point fixe est inatteignable. Un
  `PKGBUILD` de l'AUR n'a pas ce problème, vivant à côté des sources. La raison
  est écrite dans le fichier pour que la question ne se rouvre pas.

## [1.4.0] - 2026-09-06

L'outillage passe à uv, et Python 3.8 redevient une promesse tenue plutôt
qu'une case cochée.

### Ajouté
- La CI installe l'interpréteur par uv au lieu de dépendre de ce que l'image du
  runner embarque, ce qui remet `ubuntu / 3.8` dans la matrice — les images
  GitHub ne la fournissent plus ([#6](https://github.com/boubou666/doot/pull/6)).
- Le workflow de release construit par `uv build --no-sources` et vérifie les
  métadonnées par `uvx twine check`, sans rien installer à côté des paquets
  ([#8](https://github.com/boubou666/doot/pull/8)).
- `uv publish --trusted-publishing always` remplace l'action tierce
  ([#9](https://github.com/boubou666/doot/pull/9)). Le mode `always` donne un
  échec net si le jeton OIDC manque, au lieu d'une bascule silencieuse vers une
  recherche d'identifiants. uv invalide en plus le jeton de courte durée après
  l'envoi, y compris quand celui-ci échoue.

### Modifié
- Le README propose `uv` pour installer depuis PyPI, et `uvx` pour lancer doot
  sans l'installer. Il dit aussi où prendre uv, sur les trois systèmes. pipx
  reste indiqué pour qui l'a déjà. La ligne `uvx` porte `--ignore-season`, sans
  quoi une première visite hors saison lit un message et ne voit aucun
  squelette.
- `requires-python` remonte de `>=3.9` à `>=3.8`, avec le classifier
  correspondant. Cette borne avait été descendue faute de pouvoir éprouver 3.8,
  les images GitHub ne la fournissant plus. Depuis que uv télécharge
  l'interpréteur, la CI la couvre à nouveau : l'annoncer n'est plus une promesse
  en l'air. À savoir tout de même : 3.8 est en fin de vie depuis octobre 2024,
  doot y tourne mais l'interpréteur ne reçoit plus de correctifs.

## [1.3.0] - 2026-09-06

doot s'installe désormais en une commande, sur les trois systèmes, sans cloner
quoi que ce soit.

### Ajouté
- Publication sur PyPI : `pipx install spooky-doot`. Le nom `doot` était déjà
  pris par un lanceur de tâches, seul le nom de distribution change — le module
  et la commande restent `doot`.
- Le workflow de release envoie les paquets à PyPI après avoir publié la
  release GitHub, dans un job séparé pour qu'un refus de PyPI n'emporte pas une
  release déjà faite. L'authentification passe par le jeton OIDC de GitHub :
  aucun secret n'est stocké dans le dépôt.
- `twine check` valide les métadonnées avant publication.
- Métadonnées enrichies pour PyPI : classifiers par version de Python et par
  système, liens vers le changelog et le dépôt.

### Modifié
- `requires-python` passe de `>=3.8` à `>=3.9`, ce que la CI éprouve
  réellement. Annoncer 3.8 laissait `pip` installer le paquet sur une version
  que personne ne teste.

## [1.2.1] - 2026-09-06

### Corrigé
- Les PNG en couleur 3 que la norme interdit lèvent désormais `PngError` au
  lieu de se décoder en pixels entièrement transparents
  ([#4](https://github.com/boubou666/doot/pull/4), ferme
  [#3](https://github.com/boubou666/doot/issues/3)). Quatre cas : bloc `PLTE`
  absent, index qu'aucune entrée ne couvre, `tRNS` plus long que la palette, et
  `PLTE` dont la longueur n'est pas un multiple de trois.
- L'enjeu n'est pas cosmétique : `PngError` est ce qui fait basculer
  `window.py` sur le chemin tkinter. Une image refusée proprement s'affiche
  donc quand même par l'autre voie, là où une image acceptée puis rendue vide
  laissait un doot muet et invisible, sans indice sur la cause.
- Le contrôle se fait une fois avant la boucle, et lui retire au passage son
  test par pixel : une image saine n'y perd rien.

## [1.2.0] - 2026-09-06

Le squelette ne se contente plus d'apparaître : il peut entrer par n'importe
lequel des quatre bords de l'écran, en glissant, et pivote pour avoir les pieds
sur celui d'où il vient. Les deux façons d'arriver se côtoient, tirées au sort.

### Ajouté
- Deux façons d'arriver, tirées au sort à chaque apparition : surgir au milieu
  de l'écran comme depuis toujours, ou entrer en glissant depuis un bord. Une
  fois sur deux par défaut, réglable par `--slide-chance`. Demander un bord
  précis avec `--side` impose l'entrée, sinon la demande n'aurait d'effet
  qu'une fois sur deux.
- L'entrée se fait avec une décélération cubique sur 420 ms par défaut. Le
  squelette s'arrête contre le bord, à quelques pixels près, et ne s'enfonce
  pas dans l'écran : ce serait une traversée, pas une entrée.
- Les quatre bords sont possibles, et l'image **pivote** pour poser son bas
  contre celui par lequel elle entre : un quart de tour horaire pour la gauche,
  un antihoraire pour la droite, un demi-tour pour le haut, rien pour le bas.
  Le squelette a donc toujours les pieds sur le bord d'où il vient.
- Le squelette ASCII, lui, ne pivote pas — des glyphes à chasse fixe tournés
  d'un quart de tour ne veulent plus rien dire. Il est retourné quand il entre
  par la droite : les obliques et les parenthèses basculent, et les lettres du
  *doot* changent de côté sans cesser d'être lisibles, les renverser telles
  quelles aurait donné « ! t o o d ».
- `png.write_png()`, un encodeur PNG minimal. tkinter ne sait pas pivoter et
  n'accepte des pixels avec leur transparence que par un fichier : l'image est
  donc décodée, pivotée, puis réécrite à côté.
- Options `--slide-chance`, `--side` (`left`, `right`, `top`, `bottom`),
  `--slide-ms` et `--no-slide`.

### Modifié
- Plus de fondu d'apparition pendant le glissement : le bord de l'écran révèle
  déjà le squelette, et les deux ensemble font bouillie. Le fondu de sortie est
  conservé.

## [1.1.0] - 2026-09-06

Première version où la mise à jour tient debout pour tout le monde, y compris
pour qui a installé depuis une release et n'a aucun dépôt sous la main. Elle
embarque évidemment la spatialisation du son et la mise à jour intégrée,
arrivées respectivement en [0.7.0](#070---2026-09-06) et
[1.0.0](#100---2026-09-06), l'historique étant linéaire.

### Ajouté
- `doot --check-update` se rabat sur le numéro de version, comparé à celui de
  la dernière release, quand l'installation n'a pas de dépôt git derrière elle.
  Il répondait jusqu'ici « commit installé inconnu » indéfiniment, à ceux-là
  mêmes qui ne peuvent pas aller vérifier par leurs propres moyens.
- Le workflow de release vérifie que l'étiquette correspond à la version
  déclarée dans les trois fichiers qui la portent — `doot/__init__.py`,
  `pyproject.toml` et le `PKGBUILD` — et non plus dans le seul premier, les
  deux autres pouvant dériver sans que rien ne le signale.

### Corrigé
- Après une mise à jour par archive, la fiche d'installation gardait comme
  source le dossier temporaire effacé dans la foulée. Elle reçoit désormais le
  commit résolu, et plus de chemin mort : les vérifications suivantes
  redeviennent précises au lieu de rester muettes.

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

[Non publié]: https://github.com/boubou666/doot/compare/v1.4.2...HEAD
[1.4.2]: https://github.com/boubou666/doot/compare/v1.4.1...v1.4.2
[1.4.1]: https://github.com/boubou666/doot/compare/v1.4.0...v1.4.1
[1.4.0]: https://github.com/boubou666/doot/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/boubou666/doot/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/boubou666/doot/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/boubou666/doot/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/boubou666/doot/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/boubou666/doot/compare/v0.7.0...v1.0.0
[0.7.0]: https://github.com/boubou666/doot/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/boubou666/doot/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/boubou666/doot/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/boubou666/doot/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/boubou666/doot/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/boubou666/doot/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/boubou666/doot/releases/tag/v0.1.0
