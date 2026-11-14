"""Build the rainbow brush stroke used as the colour break in the middle of the home page.

Output: themes/new-palace-painting/assets/images/rainbow-stroke.webp (q92 WebP with alpha; Hugo resizes it)

    python -m pip install numpy pillow scipy
    python tools/build_rainbow_stroke.py

Source: Pexels photo 40276575 by Marie Gaebel, "Vibrant abstract colorful brush strokes texture"
(Pexels licence: free to use, no attribution required). It is a real rainbow painted with a brush;
we keep its colour and swirl marks, cut it into a single stroke shape and relight it so it reads as
wet paint:
  1. the photo's white glints are replaced with nearby saturated colour, then saturation is pushed;
  2. a stroke mask is built: rounded loaded start, ragged edges, bristle streaks, and a dry-brush tail
     where streaks drop out;
  3. the photo is warped along the stroke so the full spectrum runs green -> blue before the tail;
  4. a height map (bristle streaks + the photo's own swirls) is lit from the top left for sheen,
     and paint is darkened slightly where it pools at the rim.
"""

from __future__ import annotations

import io
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "themes/new-palace-painting/assets/images/rainbow-stroke.webp"
SRC = "https://images.pexels.com/photos/40276575/pexels-photo-40276575.jpeg?auto=compress&w=2600"
W, H = 2400, 560
SEED = 11


def smooth_noise(n: int, scale: float, rng) -> np.ndarray:
    a = ndi.gaussian_filter1d(rng.standard_normal(n + 400), scale)[200 : 200 + n]
    return a / (np.abs(a).max() + 1e-9)


def load_photo() -> np.ndarray:
    req = urllib.request.Request(SRC, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        photo = Image.open(io.BytesIO(resp.read())).convert("RGB")
    photo = ImageEnhance.Contrast(ImageEnhance.Color(photo).enhance(1.35)).enhance(1.08)
    p = np.asarray(photo, np.float32) / 255
    # Replace low-saturation glints with surrounding colour so the stroke stays vivid.
    sat = (p.max(-1) - p.min(-1)) / (p.max(-1) + 1e-6)
    w = sat**2
    local = np.stack([ndi.gaussian_filter(p[..., c] * w, 18) for c in range(3)], -1)
    local /= ndi.gaussian_filter(w, 18)[..., None] + 1e-6
    glint = np.clip((0.55 - sat) / 0.35, 0, 1)[..., None]
    p = p * (1 - glint) + local * glint
    gray = p.mean(-1, keepdims=True)
    return np.clip(gray + (p - gray) * 1.25, 0, 1)


def main() -> None:
    rng = np.random.default_rng(SEED)
    u = np.arange(W) / (W - 1)

    # Stroke geometry along its length.
    center = H / 2 + 26 * np.sin(np.pi * u - 0.4) + 10 * smooth_noise(W, 120, rng)
    taper = 0.55 + 0.45 * np.clip((1 - u) / 0.32, 0, 1) ** 0.7
    half = 175 * taper * (1 + 0.05 * smooth_noise(W, 200, rng))
    top_rag = 7 * smooth_noise(W, 18, rng) + 3 * smooth_noise(W, 3, rng)
    bot_rag = 7 * smooth_noise(W, 18, rng) + 3 * smooth_noise(W, 3, rng)

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    v = yy - center[None, :]
    top, bot = -(half + top_rag)[None, :], (half + bot_rag)[None, :]
    edge_dist = np.minimum(v - top, bot - v)
    vn = v / (2 * np.maximum(half[None, :], 1)) + 0.5  # 0..1 across the stroke

    # Rounded, slightly ragged loaded start.
    cap = 18 + 70 * (2 * np.clip(vn, 0, 1) - 1) ** 2 + 6 * smooth_noise(H, 4, rng)[:, None]
    inside = np.clip(edge_dist / 2.5, 0, 1) * np.clip((xx - cap) / 2.5, 0, 1)

    # Bristle streaks across the stroke, gently wavering along it.
    rows = 900
    profile = ndi.gaussian_filter1d(rng.standard_normal(rows), 1.4)
    profile = (profile - profile.min()) / np.ptp(profile)
    streak = profile[np.clip((vn * (rows - 1)).astype(int), 0, rows - 1)]
    streak = np.clip(streak + 0.06 * np.sin(xx / 37 + yy / 90), 0, 1)

    # Dry-brush tail: streaks fall out progressively, with speckle.
    dry = np.clip((u - 0.66) / 0.34, 0, 1)[None, :]
    alpha = inside * np.clip((streak - dry**1.3 * 0.95) / 0.08, 0, 1)
    alpha *= np.where(dry > 0.2, (rng.random((H, W)) > 0.15 * dry).astype(np.float32), 1)
    alpha = np.clip(ndi.gaussian_filter(alpha, 0.6), 0, 1)

    # Colour: warp the painted rainbow along the stroke.
    p = load_photo()
    ph, pw = p.shape[:2]
    px = np.broadcast_to((np.clip(u / 0.86, 0, 1) * (pw - 1))[None, :], (H, W))
    py = (0.22 + 0.56 * np.clip(vn, 0, 1)) * (ph - 1)
    color = np.stack([ndi.map_coordinates(p[..., c], [py, px], order=1) for c in range(3)], -1)

    # Relief and wet sheen.
    lum = color @ np.array([0.3, 0.59, 0.11], np.float32)
    height = ndi.gaussian_filter(0.7 * streak + 0.6 * (lum - ndi.gaussian_filter(lum, 6)), 1.0)
    gy, gx = np.gradient(height)
    k = 5
    nz = 1 / np.sqrt(1 + (gx * k) ** 2 + (gy * k) ** 2)
    nx, ny = -gx * k * nz, -gy * k * nz
    light = np.array([-0.5, -0.6, 0.62]); light /= np.linalg.norm(light)
    half_vec = light + np.array([0, 0, 1]); half_vec /= np.linalg.norm(half_vec)
    diffuse = np.clip(nx * light[0] + ny * light[1] + nz * light[2], 0, 1)
    spec = np.clip(nx * half_vec[0] + ny * half_vec[1] + nz * half_vec[2], 0, 1) ** 60
    rgb = np.clip(color * (0.8 + 0.26 * diffuse)[..., None] + 0.22 * spec[..., None], 0, 1)
    rim = np.clip(1 - edge_dist / 14, 0, 1) * inside
    rgb *= (1 - 0.2 * rim)[..., None]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img = Image.fromarray((np.dstack([rgb, alpha]) * 255).astype(np.uint8), "RGBA")
    img.save(OUT, "WEBP", quality=92, alpha_quality=100, method=6)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KiB)")


if __name__ == "__main__":
    main()
