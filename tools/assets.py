"""Pictures for the site, all cut from the levelled, face-blurred spheres in work/eq.

  python3 tools/assets.py

Reads work/np (the nitpick run on work/eq) and writes docs/img/ plus build/data.json.
"""
import glob, json, math, re, shutil, sys
from pathlib import Path
import cv2, numpy as np
sys.path.insert(0, str(Path.home() / ".claude/bin/nitpick"))
import nitpick, sphere

ROOT = Path(__file__).resolve().parent.parent
NP, EQ, RAW0 = ROOT / "work/np", ROOT / "work/eq", ROOT / "work/np0"
IMG = ROOT / "docs/img"; IMG.mkdir(parents=True, exist_ok=True)
(ROOT / "build").mkdir(exist_ok=True)
Q = [cv2.IMWRITE_JPEG_QUALITY, 84]
I = np.eye(3)
HERO, TILE_FRAME = "GSAB2131_149", "GSAB2131_147"

frames = json.load(open(NP / "frames.json"))
byid = {f["id"]: f for f in frames}
eqs = {}


def eq(fid):
    if fid not in eqs:
        eqs.clear(); eqs[fid] = cv2.imread(str(EQ / f"{fid}.jpg"))
    return eqs[fid]


def band(e, R, w, lat=35):
    h = int(w * 2 * lat / 360)
    lon = np.radians((np.arange(w) + .5) / w * 360 - 180)[None, :]
    la = np.radians(lat - (np.arange(h) + .5) / h * 2 * lat)[:, None]
    rays = np.stack([np.cos(la) * np.sin(lon), np.sin(la) * np.ones_like(lon), np.cos(la) * np.cos(lon)], -1)
    return sphere.sample(e, rays, R)


data = {"frames": len(frames)}

# hero: the whole levelled sphere for the drag viewer
cv2.imwrite(str(IMG / "hero.jpg"), cv2.resize(eq(HERO), (4096, 2048), interpolation=cv2.INTER_AREA), Q)

# level: the tilt the camera had, put back, against the levelled band
raw0 = {f["id"]: f for f in json.load(open(RAW0 / "frames.json"))}
R0 = np.array(raw0[HERO]["R"])
data["tilt"] = round(sphere.tilt_deg(R0), 1)
data["tilts"] = sorted(round(sphere.tilt_deg(np.array(f["R"])), 1) for f in raw0.values())
cv2.imwrite(str(IMG / "level-before.jpg"), band(eq(HERO), R0.T, 1600), Q)
cv2.imwrite(str(IMG / "level-after.jpg"), band(eq(HERO), I, 1600), Q)

# shrunk to dust: one sign at the scale a model sees a whole sphere, and at camera scale
crops = json.load(open(NP / "crops.json"))
reads = [json.loads(l) for f in sorted((NP / "reads").glob("*.jsonl")) for l in open(f) if l.strip()]
data["reads"] = reads

# tiles: 24 thumbnails of one frame, three kept full size
e = eq(TILE_FRAME)
for y in nitpick.YAWS:
    for p in nitpick.PITCHES:
        t = sphere.render(e, I, y, p, nitpick.TFOV, nitpick.TW, nitpick.TH)
        cv2.imwrite(str(IMG / f"tile_y{y}_p{p}.jpg"), cv2.resize(t, (320, 192), interpolation=cv2.INTER_AREA), Q)

# the tile with the most reads, boxes drawn
vis = {}
for f in NP.glob("vision_*.jsonl"):
    for line in open(f):
        d = json.loads(line); vis[Path(d["path"]).stem] = d
best = max((k for k in vis if k.startswith(TILE_FRAME)), key=lambda k: len(vis[k].get("text", [])))
yb, pb = [int(x) for x in re.findall(r"_y(-?\d+)_p(-?\d+)", best)[0]]
t = sphere.render(e, I, yb, pb, nitpick.TFOV, nitpick.TW, nitpick.TH)
lines = []
for i, x in enumerate(sorted(vis[best]["text"], key=lambda x: (x["box"][1], x["box"][0])), 1):
    bx, by, bw, bh = x["box"]; p0 = (int(bx * nitpick.TW), int(by * nitpick.TH)); p1 = (int((bx + bw) * nitpick.TW), int((by + bh) * nitpick.TH))
    col = (60, 200, 60) if x["conf"] >= 1 else (40, 180, 255) if x["conf"] >= .5 else (60, 60, 230)
    cv2.rectangle(t, p0, p1, col, 2)
    cv2.rectangle(t, (p0[0], p0[1] - 18), (p0[0] + 26, p0[1]), col, -1)
    cv2.putText(t, str(i), (p0[0] + 3, p0[1] - 4), cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 0, 0), 1)
    lines.append({"n": i, "s": x["s"], "conf": round(x["conf"], 2)})
cv2.imwrite(str(IMG / "ocr.jpg"), t, Q)
data["ocr"] = {"tile": best, "yaw": yb, "pitch": pb, "lines": lines,
               "labels": [l for l in vis[best].get("labels", [])[:5]]}
data["tiles_read"] = len(vis)
data["text_boxes"] = sum(len(v.get("text", [])) for v in vis.values())

# dust vs camera scale, on the read with the longest Thai name
thai = [r for r in reads if r.get("frame") and re.search("[฀-๿]", r.get("name", "")) and r.get("yaw") is not None]
pick = max(thai, key=lambda r: (r.get("confidence") == "high", len(r.get("name", ""))))
e = eq(pick["frame"]); fov = max(12, float(pick.get("fov") or 20))
native = nitpick.cut(e, I, pick["yaw"], pick["pitch"], fov, fov * .6, nitpick.NATIVE)
small = nitpick.cut(e, I, pick["yaw"], pick["pitch"], fov, fov * .6, 1568 / 360)
dust = cv2.resize(small, (native.shape[1], native.shape[0]), interpolation=cv2.INTER_NEAREST)
cv2.imwrite(str(IMG / "dust-model.jpg"), dust, Q); cv2.imwrite(str(IMG / "dust-native.jpg"), native, Q)
data["dust"] = {"name": pick["name"], "frame": pick["frame"], "px_small": small.shape[1], "px_native": native.shape[1]}

# sheets, sweep, zooms as the reader saw them
for src, dst in ((NP / "sheets/t001.jpg", "sheet.jpg"), (NP / "sweep/w001.jpg", "sweep.jpg")):
    shutil.copy(src, IMG / dst)
zooms = sorted((NP / "zoom").glob("*.jpg"), key=lambda p: -p.stat().st_size)
data["zooms"] = len(zooms)
for i, z in enumerate(zooms[:2], 1):
    shutil.copy(z, IMG / f"zoom{i}.jpg")
data["zoom_names"] = [z.stem for z in zooms[:2]]
d = open(NP / "digest.txt", encoding="utf-8").read()
data["digest"] = d.split("\n== ")[1].split("\n")[:9] if "\n== " in d else []
data["settled_names"] = [c["lines"][0][0] for k, c in crops.items() if k.startswith("s")]
data["crops"] = {"sign": sum(1 for c in crops if c.startswith("c")), "label": sum(1 for c in crops if c.startswith("l")),
                 "settled": sum(1 for c in crops if c.startswith("s"))}

# finds: one picture per place the reader wrote
fi = []
# rider pictures stay off the site; posters keep their printed faces (cut from the unblurred sphere)
UNBLURRED = {"ร้านเล็กรุ่งโรจน์"}
for i, r in enumerate(sorted((r for r in reads if r.get("frame") in byid and r.get("yaw") is not None and r.get("kind") != "rider"),
                             key=lambda r: (r["frame"], r["yaw"]))):
    fov = min(60, max(10, float(r.get("fov") or 20)))
    if any(u in (r.get("name", "") + r.get("text", "")) for u in UNBLURRED):
        e, R = nitpick.load(raw0[r["frame"]]["path"]), np.array(raw0[r["frame"]]["R"])
    else:
        e, R = eq(r["frame"]), I
    im = nitpick.cut(e, R, r["yaw"], r["pitch"], fov, fov * .66, min(nitpick.NATIVE, 520 / fov))
    cv2.imwrite(str(IMG / f"find{i:02d}.jpg"), im, Q)
    fi.append(r | {"img": f"find{i:02d}.jpg"})
data["finds"] = fi
json.dump(data, open(ROOT / "build/data.json", "w"), ensure_ascii=False, indent=1)
print("assets", len(fi), "finds;", data["tilt"], "deg tilt;", data["zooms"], "zooms")
