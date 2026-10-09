"""Make the Beyond Canvas logo files from the video's first and last frames.

The logo is Splat beside the hand lettering, and both are cut straight out of
docs/design/video-cards/closing.png (Splat) and opening.png (lettering), so the logo is the same
crayon drawing the videos show rather than a copy of it. The frames are 1920x1080, which caps the
cut-out Splat at about 300 px wide: enough for a page header and every browser and phone icon,
not for print. The files go into studio/page/assets/brand/, beside the page that shows them.
Run it with any Python that has Pillow and numpy:

    python3 docs/design/logo/make_logo.py
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[3]
FRAMES = ROOT / "docs/design/video-cards"
OUT = ROOT / "studio/page/assets/brand"
PAPER_RGB = (251, 246, 238)
INK = (59, 48, 43)


def crop(name, box):
    return np.asarray(Image.open(FRAMES / name).convert("RGB").crop(box), float)


def trim(rgba, pad=6):
    ys, xs = np.nonzero(rgba[..., 3] > 8)
    return rgba[max(ys.min() - pad, 0):ys.max() + pad + 1, max(xs.min() - pad, 0):xs.max() + pad + 1]


def to_image(rgba):
    return Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), "RGBA")


def lettering(px, ink=INK):
    """Dark crayon letters on paper become ink of one colour, with the paper made see-through."""
    lum = px @ [0.299, 0.587, 0.114]
    out = np.zeros(px.shape[:2] + (4,))
    out[..., :3] = ink
    out[..., 3] = np.clip((228 - lum) / (228 - 80), 0, 1) * 255
    return trim(out)


def shapes(mask, grow):
    """Each separate shape in mask, as (label image, [(label, size, touches the crop's edge)])."""
    arr = np.array(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(grow)))
    labels, found = np.zeros(arr.shape, int), []
    for n in range(1, 250):
        hits = np.argwhere(arr == 255)
        if not len(hits):
            break
        before = arr.copy()
        img = Image.fromarray(before).copy()  # fromarray's image is read-only, and a fill on it does nothing
        ImageDraw.floodfill(img, (int(hits[0][1]), int(hits[0][0])), 0)
        arr = np.array(img)
        region = (before == 255) & (arr == 0)
        labels[region] = n
        edge = region[0].any() or region[-1].any() or region[:, 0].any() or region[:, -1].any()
        found.append((n, int(region.sum()), bool(edge)))
    return labels, found


def lift(px, strength, grow=3, main_only=False):
    """Keep every coloured shape clear of the crop's edge, eyes and smile filled in, paper see-through."""
    labels, found = shapes(strength > 0.5, grow)
    inside = [(size, n) for n, size, edge in found if not edge and size >= 300]
    keep = [max(inside)[1]] if main_only else [n for _, n in inside]
    filled = Image.fromarray(np.where(np.isin(labels, keep), 255, 0).astype(np.uint8)).copy()
    ImageDraw.floodfill(filled, (0, 0), 128)
    solid = np.asarray(filled) != 128
    solid = np.asarray(Image.fromarray((solid * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(grow))) > 0
    near = np.asarray(Image.fromarray((solid * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(7))) > 0
    alpha = np.clip(np.where(solid, 1.0, np.where(near, strength, 0.0)), 0, 1)
    edge = np.median(px[solid], axis=0)  # the soft rim takes the shape's own colour, not the shadow beside it
    out = np.zeros(px.shape[:2] + (4,))
    out[..., :3] = np.where(solid[..., None], px, edge)
    out[..., 3] = alpha * 255
    return trim(out)


def splats():
    """Splat from the last frame: once with its three excitement marks, once alone."""
    px = crop("closing.png", (900, 580, 1280, 870))
    coral = np.clip(((px[..., 0] - (px[..., 1] + px[..., 2]) / 2) - 25) / 55, 0, 1)
    coral[:64, 290:322] = 0  # a brown stick of the book's edge, above Splat
    return to_image(lift(px, coral)), to_image(lift(px, coral, main_only=True))


def fit(img, height):
    return img.resize((round(img.width * height / img.height), height), Image.Resampling.LANCZOS)


def lockup(mark, words, mark_height, gap):
    mark = fit(mark, mark_height)
    canvas = Image.new("RGBA", (mark.width + gap + words.width, max(mark.height, words.height)), (0, 0, 0, 0))
    canvas.alpha_composite(mark, (0, (canvas.height - mark.height) // 2))
    canvas.alpha_composite(words, (mark.width + gap, (canvas.height - words.height) // 2))
    return canvas


def icon(mark, size, fill=0.9, ground=None):
    canvas = Image.new("RGBA", (size, size), ground + (255,) if ground else (0, 0, 0, 0))
    scale = fill * size / max(mark.size)
    small = mark.resize((round(mark.width * scale), round(mark.height * scale)), Image.Resampling.LANCZOS)
    canvas.alpha_composite(small, ((size - small.width) // 2, (size - small.height) // 2))
    return canvas


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    marked, plain = splats()
    opening = crop("opening.png", (120, 360, 860, 660))
    words = to_image(lettering(opening))
    line = to_image(lettering(crop("closing.png", (80, 540, 880, 630))))
    marked.save(OUT / "splat.png")
    plain.save(OUT / "splat-plain.png")
    fit(plain, 88).save(OUT / "splat-header.png")  # the page header's 44 px mark, sharp on a 2x screen
    full = lockup(plain, words, 260, 36)
    full.save(OUT / "lockup.png")
    # The home screen's 56 px logo, sharp on a 2x screen. 256 colours look the same and weigh 12 KB, not 56,
    # which a classroom on a slow link notices.
    header = fit(full, 112).quantize(colors=256, method=Image.Quantize.FASTOCTREE)
    header.save(OUT / "lockup-header.png", optimize=True)
    # The same in paper-coloured letters, for a dark page such as GitHub's dark theme.
    lockup(plain, to_image(lettering(opening, ink=PAPER_RGB)), 260, 36).save(OUT / "lockup-on-dark.png")
    lockup(plain, line, 96, 18).save(OUT / "lockup-line.png")
    for size in (192, 512):
        icon(plain, size).save(OUT / f"icon-{size}.png")
    # The home-screen icon goes into the page as well (build.sh): "Add to Home Screen" fetches it on its own, and the
    # class door refuses that fetch, which carries no password. 256 colours keep it to 4 KB.
    touch = icon(plain, 180, fill=0.78, ground=PAPER_RGB).quantize(colors=256, method=Image.Quantize.FASTOCTREE)
    touch.save(OUT / "apple-touch-icon.png", optimize=True)
    icon(plain, 256, fill=0.98).save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    # The class page's tab icon, written into the page itself by studio/page/build.sh: Chrome on an iPhone or iPad
    # fetches a tab icon apart from the page, refuses the class's own certificate there, and so never showed it.
    tab = icon(plain, 48, fill=0.98).quantize(colors=256, method=Image.Quantize.FASTOCTREE)
    tab.save(OUT / "tab-icon.png", optimize=True)


if __name__ == "__main__":
    main()
