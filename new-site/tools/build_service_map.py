"""Generate the artistic Metro Detroit service-area map used on the home page.

Outputs (theme assets, inlined/linked by partials/service-map.html):
  themes/new-palace-painting/assets/maps/service-map.svg
  themes/new-palace-painting/assets/maps/paint-texture.webp

    python -m pip install pyshp shapely numpy pillow
    python tools/build_service_map.py

Data:
  - US Census Bureau cartographic boundary file, county subdivisions (cities/townships), Michigan 2023.
  - ambientCG "Painted Plaster 004" (CC0): a photographed roller-painted wall, turned into a grey
    detail map that is overlay-blended onto the colours so every fill looks like real wall paint.
Layers:
  1. every municipality in Oakland, Macomb and Wayne counties, outlined; painted a rich cool colour
     (data-o = scroll progress at which it gets painted, spreading outward from Troy);
  2. the paint-roller logo laid over the map and cut along municipal boundaries; each piece is painted a
     rich warm colour (same strength as the surroundings, different hue family) with its own roller
     direction, later in the scroll: roller head first, then arm and handle;
  3. labels for the advertised service areas.
"""

from __future__ import annotations

import io
import math
import random
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import shapefile  # pyshp
from PIL import Image, ImageFilter
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Polygon, box, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "themes/new-palace-painting/assets/maps/service-map.svg"
OUT_TEXTURE = OUT.with_name("paint-texture.webp")
CACHE = Path.home() / ".cache/npp-map"
SRC = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_26_cousub_500k.zip"
TEXTURE_SRC = "https://ambientcg.com/get?file=PaintedPlaster004_1K-JPG.zip"
COUNTIES = {"125": "Oakland", "099": "Macomb", "163": "Wayne"}

WIDTH = 1000  # viewBox width; height follows the data's aspect ratio
PAD = 16
SIMPLIFY = 0.6  # px in output space
TEXTURE_TILE = 300  # texture tile size in viewBox units

# Rich, fresh-paint colours. Surroundings: cool family. Logo: warm family of equal strength,
# so the roller reads by hue contrast rather than by being darker.
AREA_PAINTS = [
    "#2f86a8", "#1f9a8c", "#3b72c6", "#5b5fc4", "#2f9463", "#4aa3cf",
    "#7a5fc6", "#36938a", "#6a83d8", "#2b7396", "#4c8f6e", "#3f9fb0",
]
LOGO_PAINTS = ["#f4a23a", "#ea7440", "#e5564c", "#f6c54a", "#dc4a3c", "#f08f5c", "#ea6b7d", "#de8c2d"]
ROLLER_ANGLES = [0, 90, 35, -35]  # per-piece roller direction (texture rotation)

# (label, municipality names, side of the marker the text sits on)
LABELS = [
    ("Troy", ["Troy"], "right"),
    ("Rochester Hills", ["Rochester Hills"], "right"),
    ("Bloomfield", ["Bloomfield", "Bloomfield Hills"], "left"),
    ("Detroit", ["Detroit"], "right"),
]
COUNTY_LABELS = {"Oakland": "OAKLAND COUNTY", "Macomb": "MACOMB", "Wayne": "WAYNE"}


def load_features():
    shp = CACHE / "cb_2023_26_cousub_500k.shp"
    if not shp.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(SRC) as resp:
            zipfile.ZipFile(io.BytesIO(resp.read())).extractall(CACHE)
    reader = shapefile.Reader(str(shp.with_suffix("")))
    feats = []
    for sr in reader.iterShapeRecords():
        rec = sr.record.as_dict()
        if rec["COUNTYFP"] in COUNTIES and rec["ALAND"] > 0:
            feats.append({"name": rec["NAME"], "county": COUNTIES[rec["COUNTYFP"]], "geom": shape(sr.shape.__geo_interface__).buffer(0)})
    return feats


def project(feats):
    allg = unary_union([f["geom"] for f in feats])
    minx, miny, maxx, maxy = allg.bounds
    lat0 = math.radians((miny + maxy) / 2)
    kx = math.cos(lat0)
    scale = (WIDTH - 2 * PAD) / ((maxx - minx) * kx)
    height = (maxy - miny) * scale + 2 * PAD

    def tf(g):
        g = affinity.translate(g, -minx, -maxy)
        g = affinity.scale(g, kx * scale, -scale, origin=(0, 0))
        return affinity.translate(g, PAD, PAD)

    for f in feats:
        f["geom"] = tf(f["geom"]).simplify(SIMPLIFY, preserve_topology=True)
    return feats, math.ceil(height)


def roller_logo():
    """Paint-roller mark in its own 1024-unit space (same geometry as partials/logo-mark.html)."""

    def rounded(x, y, w, h, r):
        return box(x + r, y + r, x + w - r, y + h - r).buffer(r, quad_segs=6)

    head = rounded(72, 86, 725, 246, 30)
    arm = LineString([(790, 203), (877, 203), (877, 407), (463, 407), (463, 520)]).buffer(26, cap_style="flat", join_style="round")
    collar = rounded(313, 506, 302, 118, 22)
    handle = rounded(358, 600, 210, 355, 24)
    return unary_union([head, arm, collar, handle])


def path_d(geom) -> str:
    polys = geom.geoms if isinstance(geom, MultiPolygon) else [geom] if isinstance(geom, Polygon) else [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)]
    parts = []
    for p in polys:
        for ring in [p.exterior, *p.interiors]:
            pts = list(ring.coords)[:-1]
            if len(pts) < 3:
                continue
            parts.append("M" + "L".join(f"{x:.0f} {y:.0f}" for x, y in pts) + "Z")
    return "".join(parts)


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;")


def build_texture():
    """Grey (128-centred) detail map from a photographed roller-painted wall, for overlay blending."""
    folder = CACHE / "PaintedPlaster004"
    if not folder.exists():
        req = urllib.request.Request(TEXTURE_SRC, headers={"User-Agent": "npp-map-builder"})
        with urllib.request.urlopen(req) as resp:
            zipfile.ZipFile(io.BytesIO(resp.read())).extractall(folder)
    color = Image.open(folder / "PaintedPlaster004_1K-JPG_Color.jpg").convert("L")
    normal = np.asarray(Image.open(folder / "PaintedPlaster004_1K-JPG_NormalGL.jpg").convert("RGB"), np.float32) / 127.5 - 1

    def high_pass(img: Image.Image) -> np.ndarray:
        # Remove the photo's uneven lighting so the tile repeats without blotches; keep roller grain.
        a = np.asarray(img, np.float32)
        a = a - np.asarray(img.filter(ImageFilter.GaussianBlur(28)), np.float32)
        return a / a.std()

    light = np.array([-0.45, 0.55, 0.70])  # top-left light: gives the paint ridges a wet sheen
    shade = (normal * (light / np.linalg.norm(light))).sum(-1)
    shade_img = Image.fromarray(((shade - shade.min()) / np.ptp(shade) * 255).astype(np.uint8))
    tex = 128 + 16 * high_pass(color) + 13 * high_pass(shade_img)
    img = Image.fromarray(np.clip(tex, 0, 255).astype(np.uint8)).resize((512, 512), Image.LANCZOS)
    img.save(OUT_TEXTURE, "WEBP", quality=82)


def distinct_colors(geoms, palette, rnd):
    """Random colours with no two touching shapes sharing one."""
    picks = []
    for i, g in enumerate(geoms):
        near = {picks[j] for j in range(i) if g.distance(geoms[j]) < 1.5}
        options = [c for c in palette if c not in near] or palette
        picks.append(rnd.choice(options))
    return picks


def main():
    rnd = random.Random(7)
    feats, height = project(load_features())

    land = unary_union([f["geom"] for f in feats])
    lx0, ly0, lx1, ly1 = land.bounds

    # Lay the roller across the map: head over Oakland/Macomb, handle reaching down toward Detroit.
    logo = roller_logo()
    lminx, lminy, lmaxx, lmaxy = logo.bounds
    s = (lx1 - lx0) * 0.72 / (lmaxx - lminx)
    ox = lx0 + (lx1 - lx0) * 0.1 - lminx * s
    oy = ly0 + (ly1 - ly0) * 0.1 - lminy * s
    logo_t = affinity.translate(affinity.scale(logo, s, s, origin=(0, 0)), ox, oy)

    def logo_order(pt):
        # Inverse-map to logo space: sweep the head left->right, then arm and handle top->bottom.
        x, y = (pt.x - ox) / s, (pt.y - oy) / s
        if y <= 340:
            return max(0.0, (x - 72) / (797 - 72)) * 0.55
        return 0.55 + min(1.0, (y - 340) / (955 - 340)) * 0.45

    troy = next(f["geom"] for f in feats if f["name"] == "Troy").centroid
    maxd = max(f["geom"].centroid.distance(troy) for f in feats)

    out = [
        f'<svg class="service-map" viewBox="0 0 {WIDTH} {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="svc-map-title">',
        '<title id="svc-map-title">Map of Metro Detroit service area: Oakland, Macomb and Wayne counties</title>',
        "<defs>",
        *[
            f'<pattern id="tx-{k}" width="{TEXTURE_TILE}" height="{TEXTURE_TILE}" patternUnits="userSpaceOnUse" patternTransform="rotate({a})">'
            f'<image href="__PAINT_TEXTURE__" width="{TEXTURE_TILE}" height="{TEXTURE_TILE}"/></pattern>'
            for k, a in enumerate(ROLLER_ANGLES)
        ],
        '<clipPath id="land-clip"><use href="#land"/></clipPath>',
        '<filter id="paint-edge" x="-5%" y="-5%" width="110%" height="115%"><feTurbulence type="fractalNoise" baseFrequency=".035" numOctaves="2" seed="4" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="5" result="d"/><feDropShadow in="d" dx="0" dy="4" stdDeviation="4" flood-color="#1d1a27" flood-opacity=".3"/></filter>',
        "</defs>",
        # Opaque unpainted land: gives the overlay-blended texture a light backdrop so bare land stays clean.
        f'<path id="land" class="map-base" d="{path_d(land)}"/>',
        '<g class="map-land">',
    ]

    ordered = sorted(feats, key=lambda f: f["geom"].centroid.distance(troy))
    paints = distinct_colors([f["geom"] for f in ordered], AREA_PAINTS, rnd)
    for f, paint in zip(ordered, paints):
        o = f["geom"].centroid.distance(troy) / maxd * 0.55
        out.append(
            f'<path class="map-muni" d="{path_d(f["geom"])}" style="--paint:{paint}" data-o="{o:.3f}"><title>{esc(f["name"])}, {f["county"]} County</title></path>'
        )
    out.append("</g>")
    # One wall-paint texture pass over all land; overlay-blended, it only shows where colour has been laid.
    out.append(f'<rect class="map-texture" x="0" y="0" width="{WIDTH}" height="{height}" fill="url(#tx-0)" clip-path="url(#land-clip)"/>')
    # County outlines for structure.
    out.append('<g class="map-counties">')
    for c in COUNTIES.values():
        out.append(f'<path d="{path_d(unary_union([f["geom"] for f in feats if f["county"] == c]).buffer(0.4).buffer(-0.4))}"/>')
    out.append("</g>")

    # Logo mosaic: logo cut by municipal boundaries.
    pieces = []
    for f in feats:
        piece = f["geom"].buffer(0).intersection(logo_t)
        if piece.is_empty or piece.area < 4:
            continue
        pieces.append((logo_order(piece.representative_point()), piece))
    pieces.sort(key=lambda p: p[0])
    piece_paints = distinct_colors([p for _, p in pieces], LOGO_PAINTS, rnd)
    out.append('<g class="map-logo" filter="url(#paint-edge)">')
    for n, ((order, piece), paint) in enumerate(zip(pieces, piece_paints)):
        tx = rnd.randrange(len(ROLLER_ANGLES))
        out.append(
            f'<g class="map-piece" data-o="{0.42 + order * 0.53:.3f}" fill="{paint}"><path id="lp{n}" d="{path_d(piece)}"/><use class="map-texture" href="#lp{n}" fill="url(#tx-{tx})"/></g>'
        )
    out.append("</g>")

    # Labels.
    out.append('<g class="map-labels">')
    for c, text in COUNTY_LABELS.items():
        cx0, cy0, cx1, cy1 = unary_union([f["geom"] for f in feats if f["county"] == c]).bounds
        y = cy1 - 40 if c == "Wayne" else cy0 + 22  # Wayne's middle sits under the roller handle
        out.append(f'<text class="map-county" x="{(cx0 + cx1) / 2:.0f}" y="{y:.0f}">{text}</text>')
    for text, names, side in LABELS:
        geom = unary_union([f["geom"] for f in feats if f["name"] in names and f["county"] in ("Oakland", "Wayne")])
        p = geom.representative_point()
        tx = '<text x="-13" y="7" text-anchor="end">' if side == "left" else '<text x="13" y="7">'
        out.append(f'<g class="map-marker" transform="translate({p.x:.0f} {p.y:.0f})"><circle r="7"/>{tx}{text}</text></g>')
    lake_x = land.bounds[2] - 60
    out.append(f'<text class="map-water" x="{lake_x:.0f}" y="{height * 0.42:.0f}">Lake St. Clair</text>')
    out.append("</g></svg>")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out), encoding="utf-8")
    build_texture()
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.1f} KiB, {len(feats)} municipalities, {len(pieces)} logo pieces)")
    print(f"wrote {OUT_TEXTURE} ({OUT_TEXTURE.stat().st_size / 1024:.1f} KiB)")


if __name__ == "__main__":
    main()
