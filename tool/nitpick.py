#!/usr/bin/env python3
"""nitpick — read 360 (equirect) photographs on this Mac first, so a model looks only where it must.

  nitpick.py prep  OUT SRC...  [--prov cm,cr] [--jobs 4]   levels, tiles, OCR, labels, crops, sweeps
  nitpick.py zoom  OUT FRAME YAW PITCH [--fov 30] [--n 0]  native-scale view, optional neighbour frames
  nitpick.py cost  OUT                                     image-token estimate for the model pass

SRC is equirect JPEGs or GoPro .36p (MPO; frame 0 is the stitched sphere), files or folders.
Everything is written under OUT; sources are only read.

What the model gets (all under OUT):
  digest.txt        one block per moment: time, position, records within 40 m, every sign read
                    (settled = OCR matched a nearby record by name, other lines read at 1.0), every crop id
  sheets/tNNN.jpg   crops of unsettled sign text, rendered from the sphere at >= 26 px per line
  sheets/lNNN.jpg   crops where Apple Vision's scene labels hit a subject of interest
  sweep/wNNN.jpg    the lead frame of each moment as a 360 band, 4 moments a page, yaw ticks
  crops.json        crop id -> frame, yaw, pitch, fov, kind, OCR strings, the other frames it was seen in
Directions are yaw/pitch on the levelled sphere: yaw 0 = the camera's front, + = right, pitch + = up.
"""
import argparse, concurrent.futures as cf, difflib, json, math, os, re, subprocess, sys
from pathlib import Path
import cv2, numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sphere  # noqa: E402

NATIVE = 7680 / 360            # px per degree on a Max 2 sphere
PAGE = 1568                    # long edge a model reads without downscaling
YAWS = list(range(-180, 180, 45))
PITCHES = (-22, 3, 28)
TW, TH, TFOV = 1066, 640, 50   # tile: 50 x 30 degrees at native scale
STILL = {".jpg", ".jpeg", ".36p"}
MOTDANG = Path.home() / "Developer/claude code projects/mot-dang/data/canonical"
CPSRC = Path.home() / "Developer/claude code projects/capture-pipeline/src"

# Apple Vision scene labels worth a look, with the confidence each needs
INTEREST = {
    "graffiti": .25, "painting": .35, "art": .4, "statue": .35, "birdhouse": .25, "decoration": .35,
    "lantern": .3, "chandelier": .3, "umbrella": .45, "textile": .45, "clothing": .5, "doll": .35,
    "toy": .4, "flower_arrangement": .4, "banner": .45, "parking_lot": .4, "motorcycle": .8,
    "scooter": .8, "belltower": .3,
}
LABEL_CAP = 4                  # label crops per moment, sharpest first
SWEEP_ROWS = 5                 # moments per sweep page

MARKS = re.compile(r"[ัิ-ฺ็-๎]")


def skel(s):
    return re.sub(r"[^0-9a-z฀-๿]", "", MARKS.sub("", (s or "").lower()))


def metres(a, b, c, d):
    k = math.cos(math.radians(a))
    return (((a - c) ** 2 + ((b - d) * k) ** 2) ** .5) * 111320


def tokens(w, h):
    s = min(1.0, PAGE / max(w, h))
    return math.ceil(w * s * h * s / 750)


# ---------- reading a frame ----------

def exif(path):
    from PIL import Image, ExifTags
    try:
        raw = Image.open(path)._getexif() or {}
    except Exception:
        return {}
    t = {ExifTags.TAGS.get(k, k): v for k, v in raw.items()}
    out = {"time": str(t.get("DateTimeOriginal") or t.get("DateTime") or "").replace(":", "-", 2)}
    g = {ExifTags.GPSTAGS.get(k, k): v for k, v in (t.get("GPSInfo") or {}).items()}

    def dms(v, ref):
        try:
            d, m, s = [float(x) for x in v]
        except Exception:
            return None
        x = d + m / 60 + s / 3600
        return -x if ref in ("S", "W") else x
    la, lo = dms(g.get("GPSLatitude", []), g.get("GPSLatitudeRef")), dms(g.get("GPSLongitude", []), g.get("GPSLongitudeRef"))
    if la is not None and lo is not None:
        out["lat"], out["lng"] = round(la, 6), round(lo, 6)
    return out


def load(path):
    eq = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if eq is None or abs(eq.shape[1] / eq.shape[0] - 2) > .05:
        return None
    return eq


def dhash(eq):
    g = cv2.resize(cv2.cvtColor(eq, cv2.COLOR_BGR2GRAY), (33, 16), interpolation=cv2.INTER_AREA)
    return int("".join("1" if b else "0" for b in (g[:, 1:] > g[:, :-1]).flatten()), 2)


def sharpness(eq):
    band = eq[eq.shape[0] // 3: 2 * eq.shape[0] // 3]
    g = cv2.resize(cv2.cvtColor(band, cv2.COLOR_BGR2GRAY), (1920, 320), interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(g, cv2.CV_64F).var())


def direction(ray):
    return math.degrees(math.atan2(ray[0], ray[2])), math.degrees(math.asin(max(-1, min(1, ray[1]))))


_RAYS = {}


def tile_rays(yaw, pitch):
    if (yaw, pitch) not in _RAYS:
        _RAYS[(yaw, pitch)] = sphere.view_rays(TW, TH, TFOV, yaw, pitch)
    return _RAYS[(yaw, pitch)]


def box_dir(yaw, pitch, b):
    """Normalised tile box -> (yaw, pitch) of its centre, angular width and height."""
    r = tile_rays(yaw, pitch)
    x0, y0 = int(b[0] * (TW - 1)), int(b[1] * (TH - 1))
    x1, y1 = int(min(1, b[0] + b[2]) * (TW - 1)), int(min(1, b[1] + b[3]) * (TH - 1))
    c = direction(r[(y0 + y1) // 2, (x0 + x1) // 2])
    w = math.degrees(math.acos(max(-1, min(1, float(r[(y0 + y1) // 2, x0] @ r[(y0 + y1) // 2, x1])))))
    h = math.degrees(math.acos(max(-1, min(1, float(r[y0, (x0 + x1) // 2] @ r[y1, (x0 + x1) // 2])))))
    return c[0], c[1], w, h


def cut(eq, R, yaw, pitch, fov_w, fov_h, ppd):
    w = max(64, min(PAGE, int(fov_w * ppd)))
    h = max(48, min(1000, int(fov_h * ppd)))
    return sphere.render(eq, R, yaw, pitch, hfov=w / ppd, w=w, h=h)


# ---------- prep ----------

def sources(args):
    out = []
    for s in args:
        p = Path(s)
        out += sorted(q for q in p.rglob("*") if q.suffix.lower() in STILL) if p.is_dir() else [p]
    return out


def pass_frame(path, out):
    fid = path.stem
    rec = {"id": fid, "path": str(path), **exif(path)}
    eq = load(path)
    if eq is None:
        return rec | {"skip": "not a 2:1 equirect"}
    rec["sharp"], rec["hash"] = round(sharpness(eq), 1), dhash(eq)
    small = cv2.resize(eq, (2048, 1024), interpolation=cv2.INTER_AREA)
    up, how = sphere.find_up(small)
    R = sphere.up_to_R(up)
    rec["R"], rec["level"] = R.tolist(), how.get("how")
    for y in YAWS:
        for p in PITCHES:
            t = out / "tiles" / f"{fid}_y{y}_p{p}.jpg"
            if not t.exists():
                cv2.imwrite(str(t), sphere.render(eq, R, y, p, TFOV, TW, TH), [cv2.IMWRITE_JPEG_QUALITY, 92])
    band = sphere.sample(eq, band_rays(), R)
    cv2.imwrite(str(out / "band" / f"{fid}.jpg"), band, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return rec


_BAND = None


def band_rays(w=PAGE, lat=30):
    """Rays for a 360 x (2*lat) band, yaw -180 at the left."""
    global _BAND
    if _BAND is None:
        h = int(w * 2 * lat / 360)
        lon = np.radians((np.arange(w) + .5) / w * 360 - 180)[None, :]
        la = np.radians(lat - (np.arange(h) + .5) / h * 2 * lat)[:, None]
        _BAND = np.stack([np.cos(la) * np.sin(lon), np.sin(la) * np.ones_like(lon), np.cos(la) * np.cos(lon)], -1)
    return _BAND


def ocr(out, jobs):
    """vision3 over every tile not yet read; resumable."""
    done = set()
    for f in out.glob("vision_*.jsonl"):
        for line in open(f):
            try:
                done.add(json.loads(line)["path"])
            except (ValueError, KeyError):
                pass
    todo = sorted(str(t) for t in (out / "tiles").glob("*.jpg") if str(t) not in done)
    print(f"ocr: {len(todo)} tiles to read, {len(done)} already read", flush=True)
    if todo:
        procs = []
        for i in range(jobs):
            part = "\n".join(todo[i::jobs]) + "\n"
            p = subprocess.Popen([str(HERE / "vision3")], stdin=subprocess.PIPE,
                                 stdout=open(out / f"vision_{i}.jsonl", "a"), stderr=subprocess.DEVNULL, text=True)
            p.stdin.write(part); p.stdin.close(); procs.append(p)
        for p in procs:
            p.wait()
    seen = {}
    for f in out.glob("vision_*.jsonl"):
        for line in open(f):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            seen[Path(d["path"]).stem] = d
    return seen


def records(prov, frames):
    pts = [(f["lat"], f["lng"]) for f in frames if "lat" in f]
    if not pts or not prov:
        return []
    sys.path.insert(0, str(CPSRC))
    from cp.places import stream_records
    la0, la1 = min(a for a, _ in pts) - .002, max(a for a, _ in pts) + .002
    lo0, lo1 = min(b for _, b in pts) - .002, max(b for _, b in pts) + .002
    keep = []
    for pv in prov:
        src = MOTDANG / f"{pv}.json"
        if not src.exists():
            continue
        for r in stream_records(src):
            la, lo = r.get("lat"), r.get("lng")
            if la is None or lo is None or not (la0 <= la <= la1 and lo0 <= lo <= lo1):
                continue
            names = [r.get("name"), r.get("nameTh"), r.get("nameEn"), *((r.get("attrs") or {}).get("altNames") or [])]
            keep.append({"id": r["id"], "name": r.get("nameTh") or r.get("name") or r.get("nameEn"),
                         "lat": la, "lng": lo, "sk": {skel(n) for n in names if n and len(skel(n)) >= 3}})
    return keep


def name_hit(sk, rec):
    for n in rec["sk"]:
        if len(n) >= 4 and (n in sk or (len(sk) >= 4 and sk in n and len(sk) >= .6 * len(n))):
            return n
        if difflib.SequenceMatcher(None, sk, n).ratio() >= .8:
            return n
    return None


def clusters(v):
    """Merge a tile's text boxes into signs: boxes whose grown rectangles touch."""
    items = [t for t in v.get("text", []) if len(skel(t["s"])) >= 2]
    groups = []
    for t in items:
        x, y, w, h = t["box"]
        g = [x - h, y - h * .8, x + w + h, y + h * 1.8]
        hit = [G for G in groups if not (g[2] < G["r"][0] or G["r"][2] < g[0] or g[3] < G["r"][1] or G["r"][3] < g[1])]
        new = {"r": g, "t": [t]}
        for G in hit:
            new["t"] += G["t"]
            new["r"] = [min(new["r"][0], G["r"][0]), min(new["r"][1], G["r"][1]), max(new["r"][2], G["r"][2]), max(new["r"][3], G["r"][3])]
            groups.remove(G)
        groups.append(new)
    out = []
    for G in groups:
        ts = sorted(G["t"], key=lambda t: (t["box"][1], t["box"][0]))
        x0 = min(t["box"][0] for t in ts); y0 = min(t["box"][1] for t in ts)
        x1 = max(t["box"][0] + t["box"][2] for t in ts); y1 = max(t["box"][1] + t["box"][3] for t in ts)
        out.append({"lines": [(t["s"], round(t["conf"], 2)) for t in ts], "box": [x0, y0, x1 - x0, y1 - y0],
                    "hmin": min(t["box"][3] for t in ts)})
    return out


def merge_overlaps(signs):
    """Same frame, angular boxes touching -> one sign (tiles overlap by 5 degrees)."""
    out = []
    for s in sorted(signs, key=lambda s: (s["frame"], s["yaw"])):
        for o in out:
            if o["frame"] == s["frame"] and abs(((o["yaw"] - s["yaw"] + 180) % 360) - 180) <= (o["w"] + s["w"]) / 2 \
                    and abs(o["pitch"] - s["pitch"]) <= (o["h"] + s["h"]) / 2:
                keep = o if o["conf"] * len(o["sk"]) >= s["conf"] * len(s["sk"]) else s
                if keep is s:
                    o.update(s)
                break
        else:
            out.append(dict(s))
    return out


def pack(items, prefix, out):
    """Shelf-pack (id, image) into PAGE-wide pages. Returns [(page path, [ids])]."""
    pages, cur, x, y, row_h = [], [], 0, 0, 0
    canvas = np.full((PAGE, PAGE, 3), 255, np.uint8)

    def flush():
        nonlocal canvas, cur, x, y, row_h
        if cur:
            p = out / f"{prefix}{len(pages) + 1:03d}.jpg"
            cv2.imwrite(str(p), canvas[:y + row_h], [cv2.IMWRITE_JPEG_QUALITY, 90])
            pages.append((p, cur))
        canvas = np.full((PAGE, PAGE, 3), 255, np.uint8); cur, x, y, row_h = [], 0, 0, 0
    for cid, im in items:
        if im.shape[1] > PAGE:
            s = PAGE / im.shape[1]; im = cv2.resize(im, (PAGE, int(im.shape[0] * s)), interpolation=cv2.INTER_AREA)
        h, w = im.shape[0] + 20, im.shape[1]
        if x + w > PAGE:
            x, y, row_h = 0, y + row_h + 4, 0
        if y + h > PAGE:
            flush()
        canvas[y:y + 20, x:x + w] = 0
        cv2.putText(canvas, cid, (x + 4, y + 15), cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1)
        canvas[y + 20:y + h, x:x + w] = im
        cur.append(cid); x += w + 4; row_h = max(row_h, h)
    flush()
    return pages


def prep(a):
    out = Path(a.out)
    for d in ("tiles", "band", "sheets", "sweep", "zoom"):
        (out / d).mkdir(parents=True, exist_ok=True)
    state_p = out / "frames.json"
    state = {f["id"]: f for f in json.load(open(state_p))} if state_p.exists() else {}
    srcs = [p for p in sources(a.src) if p.stem not in state]
    print(f"frames: {len(srcs)} new, {len(state)} already levelled", flush=True)
    with cf.ProcessPoolExecutor(a.jobs) as ex:
        for i, rec in enumerate(ex.map(pass_frame, srcs, [out] * len(srcs)), 1):
            state[rec["id"]] = rec
            if i % 20 == 0:
                print(f"  levelled {i}/{len(srcs)}", flush=True)
                json.dump(list(state.values()), open(state_p, "w"))
    frames = sorted((f for f in state.values() if "R" in f), key=lambda f: (f.get("time") or "", f["id"]))
    json.dump(frames, open(state_p, "w"))

    # moments: runs of near-identical frames; the sharpest leads
    mom, prev = 0, None
    for f in frames:
        if prev is not None:
            same = bin(f["hash"] ^ prev["hash"]).count("1") <= 12
            if "lat" in f and "lat" in prev:
                same = same and metres(f["lat"], f["lng"], prev["lat"], prev["lng"]) <= 10
            mom += 0 if same else 1
        f["moment"] = mom; prev = f
    moments = {}
    for f in frames:
        moments.setdefault(f["moment"], []).append(f)
    for fs in moments.values():
        lead = max(fs, key=lambda f: f["sharp"])
        for f in fs:
            f["lead"] = f is lead

    vis = ocr(out, a.jobs)
    recs = records([p for p in a.prov.split(",") if p], frames)
    order = {f["id"]: i for i, f in enumerate(frames)}

    # signs: one group per text across nearby frames, best read wins
    signs = []
    for f in frames:
        near = [r for r in recs if "lat" in f and metres(f["lat"], f["lng"], r["lat"], r["lng"]) <= 60]
        f["near"] = sorted(near, key=lambda r: metres(f["lat"], f["lng"], r["lat"], r["lng"]))
        for y in YAWS:
            for p in PITCHES:
                v = vis.get(f"{f['id']}_y{y}_p{p}")
                if not v:
                    continue
                for c in clusters(v):
                    yw, pt, w, h = box_dir(y, p, c["box"])
                    text = " / ".join(s for s, _ in c["lines"])
                    sk = skel(text)
                    conf = min(k for _, k in c["lines"])
                    match = next((r for r in f["near"] if name_hit(sk, r)), None)
                    if match:  # settled: every line is either sure (1.0) or part of the name that matched
                        n_sk = name_hit(sk, match)
                        c["sure"] = all(k >= 1 or (k >= .5 and len(skel(t)) >= 2 and (skel(t) in n_sk or
                                        difflib.SequenceMatcher(None, skel(t), n_sk).ratio() >= .8)) for t, k in c["lines"])
                    signs.append({"frame": f["id"], "yaw": round(yw, 1), "pitch": round(pt, 1), "w": w, "h": h,
                                  "hdeg": c["hmin"] * 30 / 1.0, "lines": c["lines"], "sk": sk, "conf": conf,
                                  "sharp": f["sharp"], "match": match and match["id"], "sure": bool(match and c.get("sure"))})
    signs = merge_overlaps(signs)
    groups = []
    for s in sorted(signs, key=lambda s: -s["conf"] * math.log1p(s["sharp"])):
        f = state[s["frame"]]
        for g in groups:
            h = state[g[0]["frame"]]
            close = (metres(f["lat"], f["lng"], h["lat"], h["lng"]) <= 150 if "lat" in f and "lat" in h
                     else abs(order[s["frame"]] - order[g[0]["frame"]]) <= 10)
            u, v = s["sk"], g[0]["sk"]
            if close and (u == v or (min(len(u), len(v)) >= 4 and (u in v or v in u))
                          or difflib.SequenceMatcher(None, u, v).ratio() >= .85):
                g.append(s); break
        else:
            groups.append([s])

    crops, text_items, label_items = {}, [], []
    todo = {}  # frame id -> [(crop id, kind, yaw, pitch, fw, fh, ppd)]
    n = 0
    for g in groups:
        best = g[0]
        settled = best["sure"]
        others = sorted({s["frame"] for s in g} - {best["frame"]}, key=order.get)
        entry = {"kind": "sign", "settled": settled, "match": best["match"], "frame": best["frame"],
                 "yaw": best["yaw"], "pitch": best["pitch"], "lines": best["lines"], "also_in": others}
        if settled:
            n += 1; crops[f"s{n:04d}"] = entry
            continue
        alt = [x for x in g[1:] if x["frame"] != best["frame"]][:1] if best["conf"] <= .3 else []
        for s in [best] + alt:
            n += 1; cid = f"c{n:04d}"
            fw, fh = min(40, s["w"] * 1.2 + 2), min(30, s["h"] * 1.2 + 2)
            ppd = max(NATIVE * .5, min(NATIVE * 1.5, 26 / max(.3, s["hdeg"])))
            ppd = min(ppd, math.sqrt(250_000 / (fw * fh)))   # a crop stays under ~330 tokens
            crops[cid] = entry | {"frame": s["frame"], "yaw": s["yaw"], "pitch": s["pitch"], "fov": round(fw, 1),
                                  "lines": s["lines"]}
            todo.setdefault(s["frame"], []).append((cid, "t", s["yaw"], s["pitch"], fw, fh, ppd))

    # scene labels: per moment, one crop per label and direction, sharpest frame
    for m, fs in moments.items():
        hits = []
        for f in fs:
            for y in YAWS:
                for p in PITCHES:
                    v = vis.get(f"{f['id']}_y{y}_p{p}") or {}
                    has_text = bool(v.get("text"))
                    for lab, conf in v.get("labels", []):
                        if conf >= INTEREST.get(lab, 2) and not (lab == "storefront" and has_text):
                            hits.append((lab, y, p, conf, f))
        chosen = []
        for lab, y, p, conf, f in sorted(hits, key=lambda h: -h[3] * math.log1p(h[4]["sharp"])):
            if any(c[0] == lab and abs(((c[1] - y + 180) % 360) - 180) <= 45 for c in chosen):
                continue
            chosen.append((lab, y, p, conf, f))
        for lab, y, p, conf, f in chosen[:LABEL_CAP]:
            n += 1; cid = f"l{n:04d}"
            crops[cid] = {"kind": lab, "conf": round(conf, 2), "frame": f["id"], "yaw": y, "pitch": p, "fov": TFOV}
            todo.setdefault(f["id"], []).append((cid, "l", y, p, TFOV, 30, NATIVE * .45))

    # render crops, one sphere load per frame
    rendered = {}
    for fid, jobs in todo.items():
        f = state[fid]; eq = load(f["path"]); R = np.array(f["R"])
        for cid, kind, y, p, fw, fh, ppd in jobs:
            rendered[cid] = (kind, cut(eq, R, y, p, fw, fh, ppd))
    for cid in sorted(rendered, key=lambda c: (order[crops[c]["frame"]], crops[c]["yaw"])):
        (text_items if rendered[cid][0] == "t" else label_items).append((cid, rendered[cid][1]))
    for old in (out / "sheets").glob("*.jpg"):
        old.unlink()
    pages = pack(text_items, "t", out / "sheets") + pack(label_items, "l", out / "sheets")
    for p, ids in pages:
        for cid in ids:
            crops[cid]["sheet"] = p.name

    # sweeps: lead frame of each moment, four to a page
    for old in (out / "sweep").glob("*.jpg"):
        old.unlink()
    leads = [f for f in frames if f["lead"]]
    sweeps = []
    for i in range(0, len(leads), SWEEP_ROWS):
        rows = []
        for f in leads[i:i + SWEEP_ROWS]:
            b = cv2.imread(str(out / "band" / f"{f['id']}.jpg"))
            bar = np.zeros((20, b.shape[1], 3), np.uint8)
            cv2.putText(bar, f"m{f['moment']:03d} {f['id']} {(f.get('time') or '')[11:19]}", (4, 15),
                        cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1)
            for yv in range(-135, 181, 45):
                x = int((yv + 180) / 360 * b.shape[1])
                cv2.line(b, (x, 0), (x, 8), (0, 255, 255), 2)
                if yv >= -90:  # the frame name sits over -135
                    cv2.putText(bar, str(yv), (min(x, b.shape[1] - 40) - 10, 15), cv2.FONT_HERSHEY_SIMPLEX, .45, (0, 255, 255), 1)
            rows += [bar, b]
            f["sweep"] = f"w{i // SWEEP_ROWS + 1:03d}.jpg"
        p = out / "sweep" / f"w{i // SWEEP_ROWS + 1:03d}.jpg"
        cv2.imwrite(str(p), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85]); sweeps.append(p)

    # digest
    by_frame = {}
    for cid, c in crops.items():
        by_frame.setdefault(c["frame"], []).append((cid, c))
    L = []
    for m, fs in moments.items():
        lead = next(f for f in fs if f["lead"])
        pos = f"{lead['lat']},{lead['lng']}" if "lat" in lead else "no fix"
        L.append(f"\n== m{m:03d} {fs[0]['id']}..{fs[-1]['id']} ({len(fs)}) lead {lead['id']} "
                 f"{(lead.get('time') or '')[11:19]} {pos} sweep {lead.get('sweep')}")
        near = {r["id"]: r for f in fs for r in f.get("near", [])[:8]}
        if near:
            L.append("  near: " + " | ".join(f"{r['id']} {r['name']}" for r in list(near.values())[:8]))
        for f in fs:
            for cid, c in sorted(by_frame.get(f["id"], []), key=lambda t: t[1]["yaw"]):
                where = f"{f['id']} y{c['yaw']:.0f} p{c['pitch']:.0f}"
                if c["kind"] == "sign":
                    txt = " / ".join(f"{s}({k:.2f})" for s, k in c["lines"])
                    tag = f"= {c['match']}" if c["settled"] else f"{c.get('sheet', '')}" + (f" ~{c['match']}" if c["match"] else "")
                    L.append(f"  {cid} {where} {tag} :: {txt}" + (f"  [also {len(c['also_in'])} fr]" if c["also_in"] else ""))
                else:
                    L.append(f"  {cid} {where} {c['kind']} {c['conf']} {c.get('sheet', '')}")
    blocks = [b for b in "\n".join(L).split("\n== ") if b.strip()]
    (out / "batches").mkdir(exist_ok=True)
    for old in (out / "batches").glob("*.txt"):
        old.unlink()
    k, pages, text = 0, set(), []

    def flush():
        nonlocal k, pages, text
        if text:
            k += 1
            (out / "batches" / f"b{k:02d}.txt").write_text(
                "pages: " + " ".join(sorted(pages)) + "\n" + "\n".join("== " + t for t in text) + "\n", encoding="utf-8")
        pages, text = set(), []
    for b in blocks:
        mine = set(re.findall(r"\b([tl]\d{3}\.jpg)", b)) | set(re.findall(r"sweep (w\d{3}\.jpg)", b))
        if text and len(pages | mine) > a.pages:
            flush()
        pages |= mine; text.append(b)
    flush()
    print(f"batches: {k} of <= {a.pages} pages in {out / 'batches'}")
    (out / "digest.txt").write_text(f"nitpick digest — {len(frames)} frames, {len(moments)} moments, "
                                    f"{len(crops)} crops/signs\n" + "\n".join(L) + "\n", encoding="utf-8")
    json.dump(crops, open(out / "crops.json", "w"), ensure_ascii=False, indent=0)
    for f in frames:
        f["near"] = [{"id": r["id"], "name": r["name"]} for r in f.get("near", [])]
    json.dump(frames, open(state_p, "w"), ensure_ascii=False)
    cost(argparse.Namespace(out=a.out))


def cost(a):
    out = Path(a.out)
    rows = {}
    for d, pat in (("sheets", "t*.jpg"), ("sheets", "l*.jpg"), ("sweep", "w*.jpg")):
        for p in (out / d).glob(pat):
            h, w = cv2.imread(str(p)).shape[:2]
            k = f"{d}/{pat[0]}"
            n, t = rows.get(k, (0, 0)); rows[k] = (n + 1, t + tokens(w, h))
    dg = (out / "digest.txt").stat().st_size // 3 if (out / "digest.txt").exists() else 0
    total = dg + sum(t for _, t in rows.values())
    print(f"digest ~{dg} tokens · " + " · ".join(f"{k} {n} pages ~{t}" for k, (n, t) in sorted(rows.items()))
          + f" · total ~{total} input tokens before zooms")


def zoom(a):
    out = Path(a.out)
    frames = json.load(open(out / "frames.json"))
    ids = [f["id"] for f in frames]
    i = ids.index(a.frame)
    ims = []
    for f in frames[max(0, i - a.n): i + a.n + 1]:
        eq = load(f["path"])
        im = cut(eq, np.array(f["R"]), a.yaw, a.pitch, a.fov, a.fov * .66, NATIVE)
        cv2.rectangle(im, (0, 0), (260, 20), (0, 0, 0), -1)
        cv2.putText(im, f"{f['id']} y{a.yaw:g} p{a.pitch:g}", (4, 15), cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1)
        ims.append(im)
    im = np.hstack(ims) if len(ims) > 1 else ims[0]
    if im.shape[1] > PAGE:
        im = np.vstack(ims)
    p = out / "zoom" / f"{a.frame}_y{a.yaw:g}_p{a.pitch:g}_f{a.fov:g}_n{a.n}.jpg"
    cv2.imwrite(str(p), im, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(p, f"~{tokens(im.shape[1], im.shape[0])} tokens")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("prep"); p.add_argument("out"); p.add_argument("src", nargs="+")
    p.add_argument("--prov", default="cm,cr"); p.add_argument("--jobs", type=int, default=4)
    p.add_argument("--pages", type=int, default=12, help="image pages per reading batch")
    z = sp.add_parser("zoom"); z.add_argument("out"); z.add_argument("frame")
    z.add_argument("yaw", type=float); z.add_argument("pitch", type=float)
    z.add_argument("--fov", type=float, default=30); z.add_argument("--n", type=int, default=0)
    c = sp.add_parser("cost"); c.add_argument("out")
    a = ap.parse_args()
    {"prep": prep, "zoom": zoom, "cost": cost}[a.cmd](a)


if __name__ == "__main__":
    main()
