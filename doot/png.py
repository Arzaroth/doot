"""Lecture PNG en pur Python (zlib de la stdlib).

L'overlay X11 compose lui-meme ses pixels : il lui faut les octets de l'image,
que tkinter garde pour lui. Sont couverts : PNG non entrelace, profondeurs 1 a
16 bits, niveaux de gris, palette, RGB et RGBA, avec ou sans tRNS.

Le resultat est un `Frame` : du BGRA petit-boutiste a alpha premultiplie, soit
exactement ce qu'attend XPutImage sur un visual ARGB 32 bits.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

SIGNATURE = b"\x89PNG\r\n\x1a\n"
CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
# Profondeurs autorisees par la norme PNG, par type de couleur.
DEPTHS = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}

_CACHE: dict[tuple, "Frame"] = {}
_CACHE_MAX = 4


class PngError(Exception):
    """Image illisible : l'appelant retombe sur tkinter."""


class Frame:
    """Pixels prets pour XPutImage."""

    __slots__ = ("width", "height", "data")

    def __init__(self, width: int, height: int, data: bytes):
        self.width = width
        self.height = height
        self.data = data

    def mirrored(self) -> "Frame":
        """La meme image retournee horizontalement.

        Sert quand le squelette entre par la droite : il doit regarder vers
        l'interieur de l'ecran, donc du cote ou il avance.
        """
        largeur, hauteur = self.width, self.height
        source = self.data
        out = bytearray(len(source))
        for y in range(hauteur):
            debut = y * largeur * 4
            for x in range(largeur):
                lu = debut + x * 4
                ecrit = debut + (largeur - 1 - x) * 4
                out[ecrit:ecrit + 4] = source[lu:lu + 4]
        return Frame(largeur, hauteur, bytes(out))

    def faded(self, factor: float) -> bytes:
        """Le meme rendu a `factor` d'opacite.

        L'alpha etant premultiplie, attenuer les quatre octets d'un pixel du
        meme facteur donne exactement le fondu voulu.
        """
        if factor >= 1.0:
            return self.data
        if factor <= 0.0:
            return bytes(len(self.data))
        table = bytes(int(i * factor + 0.5) for i in range(256))
        return self.data.translate(table)


# ------------------------------------------------------------- decodage ------

def _chunks(blob: bytes):
    if blob[:8] != SIGNATURE:
        raise PngError("signature PNG absente")
    pos = 8
    while pos + 8 <= len(blob):
        length, kind = struct.unpack(">I4s", blob[pos:pos + 8])
        yield kind, blob[pos + 8:pos + 8 + length]
        pos += 12 + length


def _header(blob: bytes) -> tuple:
    for kind, data in _chunks(blob):
        if kind == b"IHDR":
            if len(data) < 13:
                raise PngError("IHDR tronque")
            return struct.unpack(">IIBBBBB", data[:13])
    raise PngError("IHDR manquant")


def _unfilter(raw: bytes, height: int, bpp: int, stride: int) -> bytearray:
    out = bytearray(stride * height)
    prev = bytes(stride)
    pos = 0
    for y in range(height):
        if pos + 1 + stride > len(raw):
            raise PngError("donnees PNG tronquees")
        kind = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride

        if kind == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif kind == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif kind == 3:
            for i in range(bpp):
                line[i] = (line[i] + (prev[i] >> 1)) & 255
            for i in range(bpp, stride):
                line[i] = (line[i] + ((line[i - bpp] + prev[i]) >> 1)) & 255
        elif kind == 4:
            for i in range(bpp):
                line[i] = (line[i] + prev[i]) & 255
            for i in range(bpp, stride):
                a = line[i - bpp]
                b = prev[i]
                c = prev[i - bpp]
                p = a + b - c
                pa = abs(p - a)
                pb = abs(p - b)
                pc = abs(p - c)
                if pa <= pb and pa <= pc:
                    pred = a
                elif pb <= pc:
                    pred = b
                else:
                    pred = c
                line[i] = (line[i] + pred) & 255
        elif kind != 0:
            raise PngError(f"filtre PNG inconnu : {kind}")

        start = y * stride
        out[start:start + stride] = line
        prev = line
    return out


def _to_bytes_per_sample(lines: bytearray, width: int, height: int, depth: int,
                         channels: int, stride: int, stretch: bool) -> bytearray:
    """Ramene n'importe quelle profondeur a un octet par echantillon.

    `stretch` etire les valeurs sur 0-255, ce qu'il faut pour une intensite et
    jamais pour un index de palette : etirer un index fait lire la mauvaise
    entree de PLTE.
    """
    if depth == 8:
        return lines
    samples = width * channels
    out = bytearray(samples * height)
    if depth == 16:
        # Reduction 16 -> 8 bits standard : on garde l'octet de poids fort.
        for y in range(height):
            row = lines[y * stride:(y + 1) * stride]
            out[y * samples:(y + 1) * samples] = row[0::2]
        return out

    per_byte = 8 // depth
    mask = (1 << depth) - 1
    scale = 255 // mask if stretch else 1
    for y in range(height):
        base = y * stride
        target = y * samples
        for i in range(samples):
            byte = lines[base + i // per_byte]
            shift = 8 - depth * (i % per_byte + 1)
            out[target + i] = ((byte >> shift) & mask) * scale
    return out


def _transparent_key(trns: bytes | None, color: int, depth: int) -> tuple | None:
    """Couleur declaree transparente par tRNS, ramenee a l'echelle 0-255.

    tRNS stocke toujours ses valeurs sur 16 bits, quelle que soit la
    profondeur de l'image : il faut donc les ramener comme les echantillons.
    """
    if not trns or color not in (0, 2):
        return None
    count = len(trns) // 2
    if not count:
        return None
    values = struct.unpack(f">{count}H", trns[:count * 2])
    if depth == 16:
        return tuple(value >> 8 for value in values)
    if depth == 8:
        return tuple(value & 255 for value in values)
    mask = (1 << depth) - 1
    scale = 255 // mask
    return tuple((value & mask) * scale for value in values)


def _premultiplied_bgra(samples: bytearray, width: int, height: int, color: int,
                        palette: bytes, trns: bytes | None, depth: int) -> bytearray:
    """Passe les echantillons en BGRA premultiplie, dans l'ordre memoire de X."""
    count = width * height
    out = bytearray(count * 4)

    if color == 3:
        alphas = bytes(trns or b"")
        for i in range(count):
            index = samples[i]
            a = alphas[index] if index < len(alphas) else 255
            if a == 0:
                continue
            p = index * 3
            if p + 2 >= len(palette):
                continue
            r, g, b = palette[p], palette[p + 1], palette[p + 2]
            d = i * 4
            if a != 255:
                r = (r * a + 127) // 255
                g = (g * a + 127) // 255
                b = (b * a + 127) // 255
            out[d] = b
            out[d + 1] = g
            out[d + 2] = r
            out[d + 3] = a
        return out

    key = _transparent_key(trns, color, depth)
    step = CHANNELS[color]
    for i in range(count):
        s = i * step
        if color in (0, 4):
            r = g = b = samples[s]
            a = samples[s + 1] if color == 4 else 255
            if key is not None and len(key) == 1 and r == key[0]:
                a = 0
        else:
            r, g, b = samples[s], samples[s + 1], samples[s + 2]
            a = samples[s + 3] if color == 6 else 255
            if key is not None and len(key) == 3 and (r, g, b) == key:
                a = 0
        if a == 0:
            continue
        d = i * 4
        if a != 255:
            r = (r * a + 127) // 255
            g = (g * a + 127) // 255
            b = (b * a + 127) // 255
        out[d] = b
        out[d + 1] = g
        out[d + 2] = r
        out[d + 3] = a
    return out


def _resample(src: bytearray, width: int, height: int,
              new_w: int, new_h: int) -> bytearray:
    """Redimensionne du BGRA premultiplie (moyenne a la reduction, plus proche
    voisin a l'agrandissement). Premultiplie, donc pas de frange sur les bords
    transparents."""
    out = bytearray(new_w * new_h * 4)
    if new_w <= width and new_h <= height:
        for dy in range(new_h):
            y0 = dy * height // new_h
            y1 = max(y0 + 1, (dy + 1) * height // new_h)
            row = dy * new_w * 4
            for dx in range(new_w):
                x0 = dx * width // new_w
                x1 = max(x0 + 1, (dx + 1) * width // new_w)
                b = g = r = a = n = 0
                for sy in range(y0, y1):
                    p = (sy * width + x0) * 4
                    for _ in range(x1 - x0):
                        b += src[p]
                        g += src[p + 1]
                        r += src[p + 2]
                        a += src[p + 3]
                        n += 1
                        p += 4
                d = row + dx * 4
                out[d] = b // n
                out[d + 1] = g // n
                out[d + 2] = r // n
                out[d + 3] = a // n
        return out

    for dy in range(new_h):
        sy = dy * height // new_h
        row = dy * new_w * 4
        for dx in range(new_w):
            p = (sy * width + dx * width // new_w) * 4
            d = row + dx * 4
            out[d:d + 4] = src[p:p + 4]
    return out


# ------------------------------------------------------------------ API ------

def size(path: Path) -> tuple[int, int]:
    """Dimensions de l'image, sans decoder les pixels."""
    with open(path, "rb") as handle:
        blob = handle.read(64)
    width, height = _header(blob)[:2]
    if width <= 0 or height <= 0:
        raise PngError("dimensions invalides")
    return width, height


def frame(path: Path, scale: float = 1.0) -> Frame:
    """Charge l'image, mise a l'echelle, prete pour l'overlay.

    Le resultat est garde en cache : le daemon reaffiche la meme image des
    dizaines de fois, autant ne la decoder qu'une seule fois.
    """
    path = Path(path)
    key = (str(path), path.stat().st_mtime_ns, round(float(scale), 4))
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    blob = path.read_bytes()
    width, height, depth, color, compression, filter_method, interlace = _header(blob)
    if interlace:
        raise PngError("PNG entrelace non gere")
    if compression != 0 or filter_method != 0:
        raise PngError("compression ou filtrage PNG non standard")
    if color not in CHANNELS:
        raise PngError(f"type de couleur inconnu : {color}")
    if depth not in DEPTHS[color]:
        raise PngError(f"profondeur {depth} interdite pour le type de couleur {color}")

    palette = b""
    trns = None
    idat = []
    for kind, data in _chunks(blob):
        if kind == b"PLTE":
            palette = data
        elif kind == b"tRNS":
            trns = data
        elif kind == b"IDAT":
            idat.append(data)
        elif kind == b"IEND":
            break
    if not idat:
        raise PngError("aucun IDAT")

    channels = CHANNELS[color]
    bits = channels * depth
    stride = (width * bits + 7) // 8
    try:
        brut = zlib.decompress(b"".join(idat))
    except zlib.error as erreur:
        raise PngError(f"donnees compressees illisibles : {erreur}") from erreur
    lines = _unfilter(brut, height, max(1, bits // 8), stride)
    samples = _to_bytes_per_sample(lines, width, height, depth, channels, stride,
                                   stretch=color != 3)
    pixels = _premultiplied_bgra(samples, width, height, color, palette, trns, depth)

    if scale and scale != 1.0:
        new_w = max(1, int(round(width * scale)))
        new_h = max(1, int(round(height * scale)))
        if (new_w, new_h) != (width, height):
            pixels = _resample(pixels, width, height, new_w, new_h)
            width, height = new_w, new_h

    result = Frame(width, height, bytes(pixels))
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.clear()
    _CACHE[key] = result
    return result
