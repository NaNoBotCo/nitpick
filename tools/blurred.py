"""Levelled, face-blurred copies of the demo spheres, so every picture on the site is cut from them.

  python3 tools/blurred.py <nitpick OUT of the first run> <work/eq>

Faces and the top 38% of each person box, as Apple Vision found them on the 24 tiles, are
pixelated on the levelled sphere. Anything a detector missed is caught by eye before publishing.
"""
import json, math, sys
from pathlib import Path
import cv2, numpy as np
sys.path.insert(0, str(Path.home() / ".claude/bin/nitpick"))
import nitpick, sphere

src, dst = Path(sys.argv[1]), Path(sys.argv[2]); dst.mkdir(parents=True, exist_ok=True)
vis = {}
for f in src.glob("vision_*.jsonl"):
    for line in open(f):
        d = json.loads(line); vis[Path(d["path"]).stem] = d

def levelled(eq, R, W=7680, H=3840, strip=240):
    out = np.zeros((H, W, 3), np.uint8)
    lon = np.radians((np.arange(W) + .5) / W * 360 - 180)[None, :]
    for y0 in range(0, H, strip):
        la = np.radians(90 - (np.arange(y0, min(H, y0 + strip)) + .5) / H * 180)[:, None]
        rays = np.stack([np.cos(la) * np.sin(lon), np.sin(la) * np.ones_like(lon), np.cos(la) * np.cos(lon)], -1)
        out[y0:y0 + strip] = sphere.sample(eq, rays, R)
    return out

def pixelate(img, x0, y0, x1, y1):
    H, W = img.shape[:2]
    for a, b in ((x0, x1),) if x0 >= 0 and x1 <= W else (((x0 % W), W), (0, x1 % W)):
        a, b = int(max(0, a)), int(min(W, b)); c, d = int(max(0, y0)), int(min(H, y1))
        if b - a < 2 or d - c < 2: continue
        r = img[c:d, a:b]; k = max(2, min(r.shape[:2]) // 6)
        img[c:d, a:b] = cv2.resize(cv2.resize(r, (max(1, r.shape[1] // k), max(1, r.shape[0] // k))), (r.shape[1], r.shape[0]), interpolation=cv2.INTER_NEAREST)

frames = json.load(open(src / "frames.json"))
for f in frames:
    eq = levelled(nitpick.load(f["path"]), np.array(f["R"]))
    H, W = eq.shape[:2]; n = 0
    for y in nitpick.YAWS:
        for p in nitpick.PITCHES:
            v = vis.get(f"{f['id']}_y{y}_p{p}") or {}
            boxes = [(b["box"], 1.5) for b in v.get("faces", [])]
            boxes += [([b["box"][0], b["box"][1], b["box"][2], b["box"][3] * .38], 1.25) for b in v.get("people", [])]
            for b, grow in boxes:
                yw, pt, w, h = nitpick.box_dir(y, p, b)
                w, h = w * grow, h * grow
                cx, cy = (yw + 180) / 360 * W, (90 - pt) / 180 * H
                hw = w / max(.2, math.cos(math.radians(pt))) / 360 * W / 2; hh = h / 180 * H / 2
                pixelate(eq, cx - hw, cy - hh, cx + hw, cy + hh); n += 1
    cv2.imwrite(str(dst / f"{f['id']}.jpg"), eq, [cv2.IMWRITE_JPEG_QUALITY, 93])
    print(f["id"], "boxes", n, flush=True)
