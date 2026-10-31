#!/usr/bin/env python3
"""
Pac-Man contribution grid generator.

Turns a GitHub contribution calendar into an animated SVG:

  1. the grid expands, column by column
  2. Pac-Man enters from the top-left and eats the grid row by row
  3. four ghosts emerge from four different edges (top, left, right, bottom)
     and chase him along his own trail, slowly gaining ground
  4. when the last cell is gone, Pinky catches him, the others close in,
     and the screen settles on GAME OVER

Only the standard library is used, so it runs anywhere (including a bare
GitHub Actions runner). Output is plain SVG + CSS keyframes, which GitHub
renders inside <img>/<picture> tags (no JavaScript involved).

Usage
-----
  python scripts/generate_pacman.py --user YOUR_USERNAME          # real data, needs GITHUB_TOKEN
  python scripts/generate_pacman.py --sample                      # offline sample data
  python scripts/generate_pacman.py --user YOUR_USERNAME --out assets
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import urllib.request

# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #
CELL = 12            # contribution square size (px)
PITCH = 16           # distance between square centres (px)
ROWS = 7             # days per week
VB_W = 880           # viewBox width
GRID_TOP = 44        # space above the grid (HUD)
GRID_BOTTOM = 44     # space below the grid (lives)

# --------------------------------------------------------------------------- #
# Timeline (seconds)
# --------------------------------------------------------------------------- #
V = 18.0             # Pac-Man speed, cells / second
VG = 30.0            # speed of a ghost while it dashes in from the edge
T_COL0 = 0.25        # first column starts appearing
T_COL_STEP = 0.048   # delay between columns
T_COL_DUR = 0.30
T_PAC0 = 3.0         # Pac-Man starts running in (3 cells left of the grid)
PRE_RUN = 3          # cells of run-up before the first square
DEATH_DUR = 1.0
HOLD_GAMEOVER = 5.0
FADE_OUT = 0.7

# --------------------------------------------------------------------------- #
# Themes
# --------------------------------------------------------------------------- #
THEMES = {
    "dark": dict(
        l=["#161b22", "#5c4f12", "#8f7a0d", "#d4b200", "#ffd60a"],
        stroke="rgba(255,255,255,.045)",
        text="#8b949e", score="#ffd60a",
        pac="#ffd60a", pac_stroke="none",
        ghosts=dict(blinky="#ff4d4d", pinky="#ff9fd0", inky="#35e0ff", clyde="#ffa94d"),
        over="#ff4d4d", veil="rgba(13,17,23,.80)",
    ),
    "light": dict(
        l=["#ebedf0", "#f7e199", "#f2c94c", "#e0a800", "#b88700"],
        stroke="rgba(27,31,36,.06)",
        text="#656d76", score="#9a6f00",
        pac="#f7c600", pac_stroke="#b88700",
        ghosts=dict(blinky="#e03131", pinky="#f06fa6", inky="#15aabf", clyde="#f08c00"),
        over="#d9251d", veil="rgba(255,255,255,.82)",
    ),
}

FONT = 'ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono","DejaVu Sans Mono",monospace'

# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
          "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}

QUERY = """
query($login:String!){
  user(login:$login){
    contributionsCollection{
      contributionCalendar{
        totalContributions
        weeks{ contributionDays{ contributionCount contributionLevel weekday } }
      }
    }
  }
}"""


def fetch_calendar(user: str, token: str):
    """Return (weeks, total). weeks = list of 7-long lists of (count, level) or None."""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": user}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "pacman-grid"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload or not payload.get("data", {}).get("user"):
        raise RuntimeError(f"GitHub API error: {payload.get('errors') or 'user not found'}")
    cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = []
    for w in cal["weeks"]:
        col = [None] * ROWS
        for d in w["contributionDays"]:
            col[d["weekday"]] = (d["contributionCount"], LEVELS[d["contributionLevel"]])
        weeks.append(col)
    return weeks, cal["totalContributions"]


def sample_calendar(cols: int = 53):
    """Deterministic, believable-looking sample year (used offline / before first run)."""
    rnd = random.Random(1031)
    weeks, total = [], 0
    raw = []
    for c in range(cols):
        season = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(c / 7.5))
        burst = 1.0 if rnd.random() > 0.12 else 0.0
        col = []
        for r in range(ROWS):
            weekday_bias = 0.45 if r in (0, 6) else 1.0
            p = 0.78 * season * burst * weekday_bias
            n = 0 if rnd.random() > p else int(rnd.expovariate(1 / 3.2)) + 1
            col.append(n)
        raw.append(col)
    top = max(max(c) for c in raw)
    for col in raw:
        out = []
        for n in col:
            lvl = 0 if n == 0 else min(4, math.ceil(4 * n / top))
            out.append((n, lvl))
            total += n
        weeks.append(out)
    return weeks, total


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
class Fmt:
    def __init__(self, duration: float):
        self.D = duration

    def pct(self, t: float) -> str:
        v = max(0.0, min(100.0, 100.0 * t / self.D))
        s = f"{v:.3f}".rstrip("0").rstrip(".")
        return (s or "0") + "%"

    def kf(self, name: str, frames, always_ends: bool = True) -> str:
        """frames: list of (time, css-declaration). Equal declarations merge into one rule."""
        frames = sorted(frames, key=lambda f: f[0])
        if always_ends:
            if frames[0][0] > 0:
                frames.insert(0, (0.0, frames[0][1]))
            if frames[-1][0] < self.D:
                frames.append((self.D, frames[-1][1]))
        out, seen = [], {}
        for t, decl in frames:
            p = self.pct(t)
            if p in seen:          # same instant twice -> last one wins
                out[seen[p]] = (p, decl)
            else:
                seen[p] = len(out)
                out.append((p, decl))
        grouped, i = [], 0
        while i < len(out):
            ps, decl = [out[i][0]], out[i][1]
            while i + 1 < len(out) and out[i + 1][1] == decl:
                i += 1
                ps.append(out[i][0])
            grouped.append(f"{','.join(ps)}{{{decl}}}")
            i += 1
        return f"@keyframes {name}{{{''.join(grouped)}}}"


def tx(x: float, y: float) -> str:
    return f"transform:translate({x:.2f}px,{y:.2f}px)"


# --------------------------------------------------------------------------- #
# The scene
# --------------------------------------------------------------------------- #
def build_svg(weeks, total: int, theme: str, user_label: str = "") -> str:
    th = THEMES[theme]
    cols = len(weeks)
    n_cells = cols * ROWS

    grid_w = (cols - 1) * PITCH + CELL
    OX = (VB_W - grid_w) / 2 + CELL / 2
    OY = GRID_TOP + CELL / 2
    VB_H = GRID_TOP + (ROWS - 1) * PITCH + CELL + GRID_BOTTOM

    def px(x):  # cell units -> pixels
        return OX + x * PITCH

    def py(y):
        return OY + y * PITCH

    # ---- Pac-Man's route: row by row, boustrophedon ---------------------- #
    def cell_xy(idx):
        r, i = divmod(idx, cols)
        return (i if r % 2 == 0 else cols - 1 - i, r)

    def t_idx(idx):
        return T_PAC0 + (PRE_RUN + idx) / V

    pac_wp = [(T_PAC0, -PRE_RUN, 0)]
    for r in range(ROWS):
        f, l = r * cols, r * cols + cols - 1
        pac_wp.append((t_idx(f), *cell_xy(f)))
        pac_wp.append((t_idx(l), *cell_xy(l)))
    tE = pac_wp[-1][0]                        # last square eaten
    xmax = cell_xy(n_cells - 1)[0]
    last_row = ROWS - 1

    def pac_xy(t):
        if t <= pac_wp[0][0]:
            return (pac_wp[0][1] - V * (pac_wp[0][0] - t), pac_wp[0][2])
        if t >= pac_wp[-1][0]:
            return (pac_wp[-1][1], pac_wp[-1][2])
        for (t0, x0, y0), (t1, x1, y1) in zip(pac_wp, pac_wp[1:]):
            if t0 <= t <= t1:
                k = 0 if t1 == t0 else (t - t0) / (t1 - t0)
                return (x0 + (x1 - x0) * k, y0 + (y1 - y0) * k)
        return (pac_wp[-1][1], pac_wp[-1][2])

    # ---- Ghosts ---------------------------------------------------------- #
    # kg   : index on Pac-Man's trail where the ghost locks on after dashing in
    # lag0 : cells behind Pac-Man when it locks on;  lag1 : cells behind at the end
    # final: where it ends up around Pac-Man (cell units)
    far = xmax
    ghost_defs = [
        dict(name="blinky", spawn="top",    kg=70,  lag0=20, lag1=8,
             hook=(far - 2.4, 4.8), final=(far, 4.8)),
        dict(name="clyde",  spawn="left",   kg=120, lag0=32, lag1=18,
             hook=None, final=(far - 2.4, last_row)),
        dict(name="inky",   spawn="right",  kg=169, lag0=26, lag1=13,
             hook=(far - 3.8, 4.8), final=(far - 1.3, 4.8)),
        dict(name="pinky",  spawn="bottom", kg=250, lag0=6,  lag1=4,
             hook=None, final=(far - 1.1, last_row)),
    ]
    # scale hooks / kg for grids that aren't 53 columns wide
    for g in ghost_defs:
        g["kg"] = min(g["kg"], n_cells - 60)

    def t_on_last_row(x):                    # time Pac-Man is at column x on the last row
        return tE - (xmax - x) / V

    ghosts = []
    for g in ghost_defs:
        kg, lag0, lag1 = g["kg"], g["lag0"], g["lag1"]
        jx, jy = cell_xy(kg)
        tj = t_idx(kg) + lag0 / V
        spawn = {"top": (jx, -4.0), "bottom": (jx, ROWS + 3.5),
                 "left": (-3.5, jy), "right": (cols + 2.5, jy)}[g["spawn"]]
        dist = abs(spawn[0] - jx) + abs(spawn[1] - jy)
        ts = tj - dist / VG

        # s(t) = t - lag(t)/V is the moment of Pac-Man's trail the ghost stands on
        span = tE - tj
        m = (lag1 - lag0) / (V * span)
        a = 1 - m
        b = -lag0 / V + m * tj

        def ghost_time(s_c, lag1=lag1, a=a, b=b):
            if s_c >= tE - lag1 / V:
                return s_c + lag1 / V
            return (s_c - b) / a

        hx = g["hook"][0] if g["hook"] else g["final"][0]
        t_hook = t_on_last_row(hx) + lag1 / V

        wps = [(0.0, *spawn), (ts, *spawn), (tj, jx, jy)]
        for (tc, cx, cy) in pac_wp[1:]:
            if tc <= t_idx(kg) + 1e-9:
                continue
            t_c = ghost_time(tc)
            if t_c < t_hook - 1e-6:
                wps.append((t_c, cx, cy))
        wps.append((t_hook, hx, last_row))
        if g["hook"]:
            hy = g["hook"][1]
            t_up = t_hook + abs(last_row - hy) / V
            wps.append((t_up, hx, hy))
            wps.append((t_up + abs(g["final"][0] - hx) / V, g["final"][0], hy))
        ghosts.append(dict(g, wps=wps, t_end=wps[-1][0], tj=tj, ts=ts))

    pinky = next(g for g in ghosts if g["name"] == "pinky")
    t_caught = pinky["t_end"]                 # Pinky touches Pac-Man
    t_last_ghost = max(g["t_end"] for g in ghosts)
    t_over = max(t_caught + DEATH_DUR, t_last_ghost) + 0.45
    t_fade = t_over + HOLD_GAMEOVER
    D = math.ceil((t_fade + FADE_OUT) * 10) / 10
    f = Fmt(D)

    # ---- CSS ------------------------------------------------------------- #
    css = []
    c = th
    root = ";".join(f"--l{i}:{col}" for i, col in enumerate(c["l"]))
    css.append(f":root{{{root}}}")
    css.append(f"text{{font-family:{FONT}}}")
    css.append(
        f".c,.col,.sprite,.rot,.dth,.sc,.go,.stage,.life,.pu"
        f"{{animation-duration:{D}s;animation-iteration-count:infinite;animation-timing-function:linear}}"
    )
    css.append(f".c{{shape-rendering:geometricPrecision;stroke:{c['stroke']};stroke-width:1px;fill:var(--l0)}}")
    for i in range(1, 5):
        css.append(f".c{i}{{fill:var(--l{i})}}")
    css.append(".rot,.pu{animation-timing-function:step-end}")
    css.append(".dth{animation-timing-function:ease-in}")
    css.append(".sc,.go,.life{opacity:0}.sc0,.life{opacity:1}")
    css.append(f".hud{{font-size:11px;letter-spacing:1.5px;fill:{c['text']}}}")
    css.append(f".num{{font-size:11px;letter-spacing:1.5px;fill:{c['score']}}}")

    # grid expansion (per column)
    for ci in range(cols):
        t0 = T_COL0 + ci * T_COL_STEP
        css.append(f.kf(f"a{ci}", [
            (0, "opacity:0;transform:translateY(7px)"),
            (t0, "opacity:0;transform:translateY(7px)"),
            (t0 + T_COL_DUR, "opacity:1;transform:translateY(0)"),
        ]))

    # cells being eaten
    cells_svg, cum, eat_events = [], 0, []
    for ci, col in enumerate(weeks):
        col_cells = []
        for ri in range(ROWS):
            d = col[ri] if ri < len(col) else None
            if d is None:
                continue
            count, lvl = d
            x, y = ci * PITCH + (OX - CELL / 2), ri * PITCH + (OY - CELL / 2)
            attrs = f'class="c c{lvl}" x="{x:.1f}" y="{y:.1f}" width="{CELL}" height="{CELL}" rx="2.5"'
            if lvl > 0:
                k = ri * cols + (ci if ri % 2 == 0 else cols - 1 - ci)   # index along the route
                # Pac-Man's route is row-major; ci is the column of this cell
                te = t_idx(k) - 0.35 / V
                eat_events.append((te, count))
                nm = f"e{ci}_{ri}"
                css.append(f.kf(nm, [(0, f"fill:var(--l{lvl})"), (te, f"fill:var(--l{lvl})"),
                                     (te + 0.04, "fill:var(--l0)")]))
                attrs += f' style="animation-name:{nm}"'
            col_cells.append(f"<rect {attrs}/>")
        cells_svg.append(f'<g class="col" style="animation-name:a{ci}">{"".join(col_cells)}</g>')

    # score counter (stepped)
    eat_events.sort()
    N_STEPS = 24
    step_times = [t_idx(0)] + [t_idx(int(n_cells * (i + 1) / N_STEPS) - 1) for i in range(N_STEPS)]
    step_vals = [sum(n for te, n in eat_events if te <= st + 1e-9) for st in step_times]
    step_vals[-1] = sum(n for _, n in eat_events)
    score_svg = []
    for i, (t0, val) in enumerate(zip(step_times, step_vals)):
        t1 = step_times[i + 1] if i + 1 < len(step_times) else None
        frames = [(0, "opacity:%d" % (1 if i == 0 else 0))]
        if i == 0:
            frames += [(t1, "opacity:1"), (t1 + 0.01, "opacity:0")]
        else:
            frames += [(t0, "opacity:0"), (t0 + 0.01, "opacity:1")]
            if t1 is not None:
                frames += [(t1, "opacity:1"), (t1 + 0.01, "opacity:0")]
        css.append(f.kf(f"s{i}", frames))
        score_svg.append(
            f'<text class="num sc sc{i}" x="68" y="26" style="animation-name:s{i}">{val:06d}</text>')

    # Pac-Man: translate, facing, death
    css.append(f.kf("pm", [(t, tx(px(x), py(y))) for t, x, y in pac_wp] +
                    [(0, tx(px(-PRE_RUN), py(0)))]))
    face = [(0, "transform:rotate(0deg)")]
    for r in range(ROWS):
        fidx, lidx = r * cols, r * cols + cols - 1
        d_row = 0 if r % 2 == 0 else 180
        face.append((t_idx(fidx), f"transform:rotate({d_row}deg)"))
        if r < ROWS - 1:
            face.append((t_idx(lidx), "transform:rotate(90deg)"))
    css.append(f.kf("pr", face))
    css.append(f.kf("pd", [
        (0, "transform:scale(1) rotate(0deg)"),
        (t_caught, "transform:scale(1) rotate(0deg)"),
        (t_caught + DEATH_DUR, "transform:scale(0) rotate(720deg)"),
    ]))
    css.append(f.kf("life", [(0, "opacity:1"), (t_caught + 0.25, "opacity:1"), (t_caught + 0.3, "opacity:0")]))
    css.append("@keyframes ct{0%,100%{transform:rotate(0deg)}50%{transform:rotate(-38deg)}}")
    css.append("@keyframes cb{0%,100%{transform:rotate(0deg)}50%{transform:rotate(38deg)}}")
    css.append(".jt{animation:ct .22s ease-in-out infinite}.jb{animation:cb .22s ease-in-out infinite}")
    css.append("@keyframes wa{0%{opacity:1}50%{opacity:0}}@keyframes wb{0%{opacity:0}50%{opacity:1}}")
    css.append(".ga{animation:wa .3s step-end infinite}.gb{animation:wb .3s step-end infinite}")

    # Ghosts
    ghost_svg = []
    for g in ghosts:
        nm = g["name"]
        css.append(f.kf(f"g_{nm}", [(t, tx(px(x), py(y))) for t, x, y in g["wps"]]))
        eyes, prev = [(0, "transform:translate(0px,0px)")], None
        for (t0, x0, y0), (t1, x1, y1) in zip(g["wps"], g["wps"][1:]):
            dx, dy = x1 - x0, y1 - y0
            if abs(dx) + abs(dy) < 1e-6:
                continue
            ex = 0 if abs(dx) < abs(dy) * 0.2 else math.copysign(1.4, dx)
            ey = 0 if abs(dy) < abs(dx) * 0.2 else math.copysign(1.4, dy)
            cur = f"transform:translate({ex:.1f}px,{ey:.1f}px)"
            if cur != prev:
                eyes.append((t0, cur))
                prev = cur
        fx, fy = g["final"]
        ex = 0 if abs(xmax - fx) < 0.05 else 1.4
        ey = 0 if abs(last_row - fy) < 0.05 else 1.4
        eyes.append((g["t_end"], f"transform:translate({ex:.1f}px,{ey:.1f}px)"))
        css.append(f.kf(f"ge_{nm}", eyes))
        col = th["ghosts"][nm]
        sx, sy = g["wps"][0][1], g["wps"][0][2]
        ghost_svg.append(
            f'<g class="sprite" style="animation-name:g_{nm}" transform="translate({px(sx):.1f} {py(sy):.1f})">'
            f'<path class="ga" fill="{col}" d="M-9 9V0a9 9 0 0 1 18 0v9l-3-3-3 3-3-3-3 3-3-3-3 3z"/>'
            f'<path class="gb" fill="{col}" d="M-9 6V0a9 9 0 0 1 18 0v6l-3 3-3-3-3 3-3-3-3 3-3-3z"/>'
            f'<ellipse cx="-3.6" cy="-1.6" rx="3" ry="3.5" fill="#fff"/>'
            f'<ellipse cx="3.6" cy="-1.6" rx="3" ry="3.5" fill="#fff"/>'
            f'<g class="pu" style="animation-name:ge_{nm}">'
            f'<circle cx="-3.6" cy="-1.6" r="1.6" fill="#2540ff"/><circle cx="3.6" cy="-1.6" r="1.6" fill="#2540ff"/>'
            f"</g></g>")

    # Game over
    css.append(f.kf("goveil", [(0, "opacity:0"), (t_over - 0.45, "opacity:0"), (t_over, "opacity:1"),
                               (t_fade, "opacity:1"), (D, "opacity:0")]))
    css.append(f.kf("gotxt", [(0, "opacity:0"), (t_over + 0.25, "opacity:0"), (t_over + 0.26, "opacity:1")]))
    css.append("@keyframes blink{0%,62%{opacity:1}62.1%,100%{opacity:.18}}")
    css.append(".blink{animation:blink 1.2s step-end infinite}")
    css.append(f.kf("stage", [(0, "opacity:0"), (0.15, "opacity:1"), (t_fade, "opacity:1"), (D, "opacity:0")]))
    css.append("@media (prefers-reduced-motion:reduce){*{animation:none!important}}")

    pac_start_x, pac_start_y = px(0), py(0)
    r = 9
    jaw_t = f"M-{r} .7V0A{r} {r} 0 0 1 {r} 0V.7Z"
    jaw_b = f"M-{r} -.7V0A{r} {r} 0 0 0 {r} 0V-.7Z"
    pac_stroke = f' stroke="{th["pac_stroke"]}" stroke-width=".8"' if th["pac_stroke"] != "none" else ""

    score_label = (f'<text class="hud" x="18" y="26">SCORE</text>{"".join(score_svg)}')
    life = (f'<g class="life" style="animation-name:life" transform="translate({OX:.1f} {VB_H - 20})">'
            f'<path fill="{th["pac"]}"{pac_stroke} d="M0 0L6.06 -3.5A7 7 0 1 0 6.06 3.5Z"/></g>')

    pac_svg = (
        f'<g class="sprite" style="animation-name:pm" transform="translate({pac_start_x:.1f} {pac_start_y:.1f})">'
        f'<g class="rot" style="animation-name:pr"><g class="dth" style="animation-name:pd">'
        f'<path class="jt" fill="{th["pac"]}"{pac_stroke} d="{jaw_t}"/>'
        f'<path class="jb" fill="{th["pac"]}"{pac_stroke} d="{jaw_b}"/>'
        f"</g></g></g>")

    cx, cy = VB_W / 2, GRID_TOP + ((ROWS - 1) * PITCH + CELL) / 2
    veil_svg = (
        f'<g class="go" style="animation-name:goveil">'
        f'<rect x="0" y="{GRID_TOP - 6}" width="{VB_W}" height="{(ROWS - 1) * PITCH + CELL + 12}" fill="{th["veil"]}"/></g>')
    over_svg = (
        f'<g class="go" style="animation-name:gotxt"><g class="blink">'
        f'<text x="{cx}" y="{cy + 7.5:.1f}" text-anchor="middle" font-size="22" font-weight="700" '
        f'letter-spacing="7" fill="{th["over"]}">GAME OVER</text></g></g>')

    title = "Pac-Man contribution grid"
    desc = (f"A GitHub contribution graph where Pac-Man eats every square while four ghosts chase him. "
            f"Pinky catches him at the end and the screen reads GAME OVER. {total} contributions in the last year.")

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VB_W} {VB_H}" width="{VB_W}" height="{VB_H}" '
        f'role="img" aria-labelledby="t d">'
        f'<title id="t">{title}</title><desc id="d">{desc}</desc>'
        f'<style>{"".join(css)}</style>'
        f'<g class="stage" style="animation-name:stage">'
        f'{score_label}{"".join(cells_svg)}{veil_svg}{life}{pac_svg}{"".join(ghost_svg)}{over_svg}'
        f"</g></svg>"
    )
    meta = dict(duration=D, t_eaten=tE, t_caught=t_caught, t_over=t_over, ghosts={
        g["name"]: dict(appears=round(g["ts"], 2), locks_on=round(g["tj"], 2), arrives=round(g["t_end"], 2))
        for g in ghosts})
    return svg, meta


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--user", default=os.environ.get("GITHUB_REPOSITORY_OWNER"))
    ap.add_argument("--out", default="assets")
    ap.add_argument("--sample", action="store_true", help="use built-in sample data (no network)")
    ap.add_argument("--meta", action="store_true", help="print the timeline")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if args.sample or not (args.user and token):
        if not args.sample:
            print("! no --user / GITHUB_TOKEN found -> using sample data", file=sys.stderr)
        weeks, total = sample_calendar()
    else:
        weeks, total = fetch_calendar(args.user, token)
        print(f"fetched {len(weeks)} weeks, {total} contributions for {args.user}")

    os.makedirs(args.out, exist_ok=True)
    for theme in ("dark", "light"):
        svg, meta = build_svg(weeks, total, theme)
        path = os.path.join(args.out, f"pacman-{theme}.svg")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(svg)
        print(f"wrote {path}  ({len(svg) / 1024:.0f} KB, loop {meta['duration']}s)")
    if args.meta:
        print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
