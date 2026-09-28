"""Level a 360 frame by rotating the sphere, then cut flat views from it.

A tilted camera leans every vertical in a flat view by roughly roll*cos(yaw) + pitch*sin(yaw).
Eight pitch-0 views are cut, the median lean of near-vertical edges is measured in each, the
two terms are fitted, and the sphere is turned back by them; three rounds settle it. Nothing
is cropped and no angle is too large, because the correction happens on the sphere before any
view is cut. Yaw is left alone, so a view's yaw means what it meant in the first pass.

Axes: x right, y up, z forward (yaw 0). Views and tiles are rendered here with cv2.remap
rather than ffmpeg v360, so the rotation found is the rotation applied.
"""
import math
import cv2
import numpy as np

# ---------- geometry ----------

def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], np.float64)

def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], np.float64)

def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], np.float64)

def view_rays(w, h, hfov, yaw, pitch):
    """Unit rays (h, w, 3) in world axes for a rectilinear view."""
    fx = (w / 2) / math.tan(math.radians(hfov) / 2)
    xs = (np.arange(w, dtype=np.float64) + .5 - w / 2) / fx
    ys = -(np.arange(h, dtype=np.float64) + .5 - h / 2) / fx
    X, Y = np.meshgrid(xs, ys)
    d = np.stack([X, Y, np.ones_like(X)], -1)
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    R = rot_y(math.radians(yaw)) @ rot_x(-math.radians(pitch))  # pitch up = look up
    return d @ R.T

def sample(eq, rays, R_level=None, interp=cv2.INTER_CUBIC):
    """Look up rays in the equirect. R_level maps a levelled-world ray to the camera's ray."""
    H, W = eq.shape[:2]
    v = rays if R_level is None else rays @ R_level.T
    lon = np.arctan2(v[..., 0], v[..., 2])
    lat = np.arcsin(np.clip(v[..., 1], -1, 1))
    mx = ((lon + math.pi) / (2 * math.pi) * W - .5).astype(np.float32)
    my = ((math.pi / 2 - lat) / math.pi * H - .5).astype(np.float32)
    return cv2.remap(eq, mx, my, interp, borderMode=cv2.BORDER_WRAP)

def render(eq, R_level, yaw, pitch=0, hfov=100, w=1600, h=1100):
    return sample(eq, view_rays(w, h, hfov, yaw, pitch), R_level)

# ---------- lean ----------

def lean(img, max_deg=35):
    """Median lean (degrees, + = top leans right) of near-vertical edges, and how many."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    H = g.shape[0]
    e = cv2.Canny(g, 60, 160)
    lines = cv2.HoughLinesP(e, 1, np.pi / 360, 60, minLineLength=H // 7, maxLineGap=6)
    if lines is None:
        return 0.0, 0
    angs, wts = [], []
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        if y2 < y1:
            x1, y1, x2, y2 = x2, y2, x1, y1
        a = math.degrees(math.atan2(x1 - x2, y2 - y1))  # top relative to bottom
        if abs(a) < max_deg:
            angs.append(a); wts.append(math.hypot(x2 - x1, y2 - y1))
    if len(angs) < 4:
        return 0.0, len(angs)
    o = np.argsort(angs); a = np.array(angs)[o]; w = np.array(wts)[o]
    c = np.cumsum(w)
    return float(a[np.searchsorted(c, c[-1] / 2)]), len(angs)  # length-weighted median

YAWS8 = list(range(-180, 180, 45))

def measure(eq_small, R):
    rows = []
    for y in YAWS8:
        v = sample(eq_small, view_rays(480, 480, 80, y, 0), R, cv2.INTER_LINEAR)
        rows.append((y, *lean(v)))
    return rows

def fit(rows, min_lines=6):
    """lean(yaw) = a*cos(yaw) + b*sin(yaw), weighted by sqrt(lines)."""
    A, z, w = [], [], []
    for y, l, n in rows:
        if n >= min_lines:
            t = math.radians(y); A.append([math.cos(t), math.sin(t)]); z.append(l); w.append(math.sqrt(n))
    if len(A) < 4:
        return None
    A, z, w = np.array(A), np.array(z), np.array(w)
    sol, *_ = np.linalg.lstsq(A * w[:, None], z * w, rcond=None)
    resid = float(np.sqrt(np.average((A @ sol - z) ** 2, weights=w)))
    return float(sol[0]), float(sol[1]), resid, len(z)

# the signs below were found by turning a frame by a known amount (calibrate())
SIGN_A, SIGN_B = 1, 1

def correction(a, b):
    """Rotation that undoes a measured (a, b); a is lean at yaw 0, b at yaw 90."""
    return rot_z(math.radians(SIGN_A * a)) @ rot_x(math.radians(SIGN_B * b))

def estimate(eq, rounds=4, small_w=2048):
    s = small_w / eq.shape[1]
    eq_small = cv2.resize(eq, (small_w, int(eq.shape[0] * s)), interpolation=cv2.INTER_AREA)
    R = np.eye(3); hist = []
    for _ in range(rounds):
        f = fit(measure(eq_small, R))
        if f is None:
            hist.append(None); break
        a, b, resid, n = f
        hist.append((round(a, 2), round(b, 2), round(resid, 2), n))
        if abs(a) < .25 and abs(b) < .25:
            break
        R = R @ correction(a, b)
    return R, hist

# ---------- vertical vanishing point (any tilt) ----------

def _pix_ray(x, y, w, h, hfov):
    fx = (w / 2) / math.tan(math.radians(hfov) / 2)
    d = np.array([(x + .5 - w / 2) / fx, -(y + .5 - h / 2) / fx, 1.0])
    return d / np.linalg.norm(d)

def segments(eq_small, yaws=YAWS8, pitches=(0, 30), w=512, hfov=90):
    """Great-circle normals and lengths of straight edges seen from the sphere's centre."""
    ns, ls = [], []
    for p in pitches:
        for y in yaws:
            Rv = rot_y(math.radians(y)) @ rot_x(-math.radians(p))
            v = sample(eq_small, view_rays(w, w, hfov, y, p), None, cv2.INTER_LINEAR)
            g = cv2.cvtColor(v, cv2.COLOR_BGR2GRAY)
            e = cv2.Canny(g, 60, 160)
            L = cv2.HoughLinesP(e, 1, np.pi / 360, 50, minLineLength=w // 8, maxLineGap=5)
            for x1, y1, x2, y2 in (L.reshape(-1, 4) if L is not None else []):
                a, b = Rv @ _pix_ray(x1, y1, w, w, hfov), Rv @ _pix_ray(x2, y2, w, w, hfov)
                n = np.cross(a, b); k = np.linalg.norm(n)
                if k > 1e-6:
                    ns.append(n / k); ls.append(math.hypot(x2 - x1, y2 - y1))
    return np.array(ns), np.array(ls)

def vertical(eq_small, prior=np.array([0, 1.0, 0]), max_off=70, tol=1.5, iters=3000, seed=0):
    """World up in camera axes: the direction most edges' great circles pass through."""
    ns, ls = segments(eq_small)
    if len(ns) < 8:
        return None, 0, len(ns)
    rng = np.random.default_rng(seed); st = math.sin(math.radians(tol))
    cos_off = math.cos(math.radians(max_off)); best, best_s = None, 0
    p = ls / ls.sum()
    for _ in range(iters):
        i, j = rng.choice(len(ns), 2, replace=False, p=p)
        u = np.cross(ns[i], ns[j]); k = np.linalg.norm(u)
        if k < 1e-3: continue
        u /= k
        if u @ prior < 0: u = -u
        if u @ prior < cos_off: continue
        s = ls[np.abs(ns @ u) < st].sum()
        if s > best_s: best, best_s = u, s
    if best is None:
        return None, 0, len(ns)
    for _ in range(3):  # refine: smallest eigenvector of the inliers' normals
        m = np.abs(ns @ best) < st
        M = (ns[m] * ls[m, None]).T @ ns[m]
        u = np.linalg.eigh(M)[1][:, 0]
        best = u if u @ best > 0 else -u
    frac = float(ls[np.abs(ns @ best) < st].sum() / ls.sum())
    return best, frac, int(m.sum())

def sky_up(eq_small):
    """Mean direction of sky-coloured pixels (camera axes) and the share of the sphere they cover."""
    e = cv2.resize(eq_small, (512, 256), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(e, cv2.COLOR_BGR2HSV).astype(np.float32)
    b, g, r = [e[..., i].astype(np.float32) for i in range(3)]
    Hh, S_, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    blue = (Hh > 90) & (Hh < 130) & (S_ > 40) & (V > 120) & (b > r + 20)
    cloud = (S_ < 35) & (V > 200)
    m = blue | cloud
    lat = (math.pi / 2 - (np.arange(256) + .5) / 256 * math.pi)[:, None]
    lon = ((np.arange(512) + .5) / 512 * 2 * math.pi - math.pi)[None, :]
    wgt = np.cos(lat) * m                     # equal-area weight
    d = np.stack([np.cos(lat) * np.sin(lon), np.sin(lat) * np.ones_like(lon), np.cos(lat) * np.cos(lon)], -1)
    v = (d * wgt[..., None]).sum((0, 1)); area = np.cos(lat).sum() * 512
    share = float(wgt.sum() / area); blue_share = float((np.cos(lat) * blue).sum() / area)
    k = np.linalg.norm(v); conc = float(k / max(wgt.sum(), 1e-9))
    # white walls and blue tiles pass for sky; real sky shows as a good share of blue
    sky_up.last = (round(blue_share, 3), round(conc, 2))
    return (v / k if k > 0 and blue_share > .08 else None), share

def vps(ns, ls, k=4, tol=1.5, iters=2000, seed=0):
    """Up to k vanishing directions, strongest first: (unit vector, support share)."""
    rng = np.random.default_rng(seed); st = math.sin(math.radians(tol))
    alive = np.ones(len(ns), bool); tot = ls.sum(); out = []
    for _ in range(k):
        idx = np.flatnonzero(alive)
        if len(idx) < 8: break
        p = ls[idx] / ls[idx].sum(); best, bs = None, 0
        for _ in range(iters):
            i, j = rng.choice(idx, 2, replace=False, p=p)
            u = np.cross(ns[i], ns[j]); n = np.linalg.norm(u)
            if n < 1e-3: continue
            u /= n; sc = ls[alive & (np.abs(ns @ u) < st)].sum()
            if sc > bs: best, bs = u, sc
        if best is None: break
        for _ in range(3):
            m = alive & (np.abs(ns @ best) < st)
            M = (ns[m] * ls[m, None]).T @ ns[m]
            u = np.linalg.eigh(M)[1][:, 0]; best = u if u @ best > 0 else -u
        m = alive & (np.abs(ns @ best) < st)
        out.append((best, float(ls[m].sum() / tot))); alive &= ~m
    return out

def find_up(eq_small):
    """World up in camera axes, and how it was found."""
    sky, share = sky_up(eq_small)
    outdoor = sky is not None and share > .04
    prior = sky if outdoor else np.array([0, 1.0, 0])
    lim = math.cos(math.radians(40 if outdoor else 30))
    ns, ls = segments(eq_small)
    cands = []
    for u, sup in (vps(ns, ls) if len(ns) >= 8 else []):
        u = u if u @ prior > 0 else -u
        if u @ prior >= lim and sup >= .06:
            cands.append((sup * (u @ prior) ** 4, u, sup))
    if cands:
        _, u, sup = max(cands, key=lambda c: c[0])
        return u, {"how": "edges", "support": round(sup, 2), "sky": round(share, 2),
                   "off_sky": round(math.degrees(math.acos(min(1, u @ sky))), 1) if outdoor else None,
                   "blue_conc": sky_up.last}
    if outdoor:
        return sky, {"how": "sky", "support": 0, "sky": round(share, 2), "off_sky": 0}
    # indoors with no vertical to see (a roof of arches and beams): two strong horizontal directions
    # at right angles, such as a market's aisles and its cross-beams, have the vertical as their cross product
    hz = [(u, sup) for u, sup in (vps(ns, ls) if len(ns) >= 8 else []) if abs(u @ prior) < math.sin(math.radians(25)) and sup >= .08]
    for i in range(len(hz)):
        for j in range(i + 1, len(hz)):
            a, b = hz[i][0], hz[j][0]
            if abs(a @ b) < math.sin(math.radians(8)):
                u = np.cross(a, b); u /= np.linalg.norm(u)
                u = u if u @ prior > 0 else -u
                if u @ prior >= math.cos(math.radians(30)):
                    return u, {"how": "beams", "support": round(hz[i][1] + hz[j][1], 2), "sky": round(share, 2),
                               "off_sky": None}
    return np.array([0, 1.0, 0]), {"how": "none", "support": 0, "sky": round(share, 2), "off_sky": None}

def up_to_R(u):
    """Smallest rotation R with R @ (0,1,0) = u, so yaw keeps its meaning."""
    e = np.array([0, 1.0, 0]); v = np.cross(e, u); s = np.linalg.norm(v); c = float(e @ u)
    if s < 1e-9:
        return np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]]) / s
    a = math.atan2(s, c)
    return np.eye(3) + math.sin(a) * K + (1 - math.cos(a)) * K @ K

def tilt_deg(R):
    """Angle between the camera's up and true up."""
    return math.degrees(math.acos(max(-1, min(1, R[1, 1]))))
