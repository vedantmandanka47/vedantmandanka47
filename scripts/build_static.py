#!/usr/bin/env python3
"""
Builds the hand-designed SVG assets (everything except the Pac-Man grid):

  assets/hero-{dark,light}.svg     typing intro + C++ -> Blueprints -> Unreal Editor
  assets/stack-{dark,light}.svg    the full-stack toolkit (secondary identity)
  assets/h-*-{dark,light}.svg      section headers
  assets/tide-{dark,light}.svg     slow tide line above the quote

Edit the CONTENT block below, then run:   python scripts/build_static.py

Only the standard library is needed. Logos come from scripts/icons.json
(Simple Icons, CC0). Nothing is loaded from the network at view time.
"""
from __future__ import annotations

import json
import math
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets")
ICONS = json.load(open(os.path.join(HERE, "icons.json"), encoding="utf-8"))

# ----------------------------------------------------------------------------
# CONTENT  (edit freely)
# ----------------------------------------------------------------------------
TITLE = "Hii, I’m Vedant."
NICKNAME = "You can call me shuyona."
ROLE = "Unreal Engine Game Developer"
BAR_LEFT = "VEDANT / PROFILE.md"
BAR_STATUS = "ONLINE"
ALSO = "Also building full-stack applications."
TAGLINE = "Minimalism · Game Development · Creative Engineering"

PIPELINE = [  # name, caption lines, icon slug (or "blueprint")
    ("C++", ["Gameplay Programmer"], "cplusplus"),
    ("Blueprints", ["Scripting & Gameplay Logic"], "blueprint"),
    ("Unreal Editor", ["Environment &", "Project Development"], "unrealengine"),
]

STACK = [  # group, items (icon slug)
    ("Frontend", ["typescript", "javascript", "react", "angular", "html5", "css", "tailwindcss"]),
    ("Backend", ["python", "django", "flask", "fastapi", "openjdk", "springboot"]),
    ("Data & tools", ["postgresql", "mysql", "git"]),
]
ALSO_USED = "React Native · Hibernate · JDBC · JSP · Prisma · PostCSS"

HEADERS = {  # file key -> title
    "projects": "Featured projects",
    "stack": "Full-stack toolkit",
    "creative": "Design & video",
    "grid": "Contribution grid",
    "writer": "Words from the writer",
}

# ----------------------------------------------------------------------------
# Themes
# ----------------------------------------------------------------------------
THEMES = {
    "dark": dict(panel="#0f141b", border="#242c37", text="#e6edf3", muted="#8b949e",
                 dim="#566170", yellow="#ffd60a", pink="#ff9fd0", green="#3fb950",
                 wave="#8b949e"),
    "light": dict(panel="#f6f8fa", border="#d0d7de", text="#1f2328", muted="#59636e",
                  dim="#8c959f", yellow="#c79400", pink="#c2417d", green="#1a7f37",
                  wave="#59636e"),
}
MONO = 'ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono","DejaVu Sans Mono",monospace'
SANS = 'system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'

REDUCED = "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def icon(slug: str, x: float, y: float, size: float, fill: str, opacity: float = 1.0) -> str:
    if slug == "blueprint":
        k = size / 30.0
        return (
            f'<g transform="translate({x} {y}) scale({k:.3f})" fill="none" stroke="{fill}" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" opacity="{opacity}">'
            f'<rect x="2" y="3" width="12" height="9" rx="2"/>'
            f'<rect x="16" y="18" width="12" height="9" rx="2"/>'
            f'<path d="M14 7.5C21 7.5 9 22.5 16 22.5"/>'
            f'<circle cx="14" cy="7.5" r="1.4" fill="{fill}"/><circle cx="16" cy="22.5" r="1.4" fill="{fill}"/></g>')
    k = size / 24.0
    return (f'<path transform="translate({x} {y}) scale({k:.4f})" fill="{fill}" opacity="{opacity}" '
            f'd="{ICONS[slug]["path"]}"/>')


def write(name: str, svg: str):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote assets/{name}  ({len(svg) / 1024:.1f} KB)")


# ----------------------------------------------------------------------------
# Hero
# ----------------------------------------------------------------------------
def hero(theme: str) -> str:
    c = THEMES[theme]
    W, H = 880, 376
    fs = 54
    cw = fs * 0.6                      # monospace cell
    x0 = 40
    base_y = 128
    chars = list(TITLE)

    # typing rhythm: deterministic, slightly uneven, small pauses after "," and spaces
    rnd = random.Random(11)
    t, delays = 0.5, []
    for ch in chars:
        delays.append(t)
        t += 0.062 + rnd.uniform(0, 0.05) + (0.14 if ch == "," else 0.04 if ch == " " else 0)
    t_typed = delays[-1] + 0.1

    css = [
        f"text{{font-family:{MONO}}} .sans{{font-family:{SANS}}}",
        "@keyframes ch{from{opacity:0}to{opacity:1}}",
        "@keyframes rise{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}",
        "@keyframes fade{from{opacity:0}to{opacity:1}}",
        "@keyframes blink{0%,55%{opacity:1}55.1%,100%{opacity:0}}",
        "@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}",
        ".k{animation:ch .01s linear both}",
        f".cur{{animation:blink 1.1s step-end infinite {t_typed + 0.2:.2f}s}}",
        ".live{animation:pulse 2.4s ease-in-out infinite}",
    ]
    # cursor travels with the typing (instant steps)
    steps = [f"0%{{transform:translateX(0)}}"]
    dur = t_typed + 0.05
    for i, d in enumerate(delays):
        steps.append(f"{100 * d / dur:.2f}%{{transform:translateX({(i + 1) * cw:.1f}px)}}")
    steps.append(f"100%{{transform:translateX({len(chars) * cw:.1f}px)}}")   # stay at the end of the line
    css.append(f"@keyframes mv{{{''.join(steps)}}}")
    css.append(f".mv{{animation:mv {dur:.2f}s step-end both}}")

    def appear(cls, delay, dur=0.9, kind="rise"):
        css.append(f".{cls}{{animation:{kind} {dur}s ease-out {delay}s both}}")

    # the nickname arrives once, quietly, after the name has finished typing - and then stays
    appear("nick", t_typed + 0.9, 1.6, "fade")
    appear("role", t_typed + 1.2)
    t_pipe = t_typed + 1.9
    for i in range(3):
        appear(f"p{i}", t_pipe + i * 0.42)
        appear(f"a{i}", t_pipe + i * 0.42 + 0.3, 0.6, "fade")
    appear("foot", t_pipe + 1.6, 1.0, "fade")
    css.append(REDUCED)

    body = []
    body.append(f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="14" fill="{c["panel"]}" stroke="{c["border"]}"/>')
    # unreal watermark (decorative, very faint)
    body.append(icon("unrealengine", 704, 66, 144, c["text"], 0.07))
    # title bar
    body.append(f'<text x="28" y="29" font-size="12" letter-spacing="1.6" fill="{c["muted"]}">{esc(BAR_LEFT)}</text>')
    body.append(f'<circle class="live" cx="{W - 98}" cy="25" r="3.6" fill="{c["green"]}"/>')
    body.append(f'<text x="{W - 28}" y="29" font-size="12" letter-spacing="1.6" text-anchor="end" fill="{c["muted"]}">{esc(BAR_STATUS)}</text>')
    body.append(f'<path d="M0 46.5H{W}" stroke="{c["border"]}"/>')
    # typed title
    for i, (ch, d) in enumerate(zip(chars, delays)):
        if ch == " ":
            continue
        cx = x0 + cw * (i + 0.5)
        body.append(f'<text class="k" style="animation-delay:{d:.2f}s" x="{cx:.1f}" y="{base_y}" font-size="{fs}" '
                    f'font-weight="700" text-anchor="middle" fill="{c["text"]}">{esc(ch)}</text>')
    # cursor
    body.append(f'<g class="mv"><rect class="cur" x="{x0 + 2}" y="{base_y - fs * 0.78:.1f}" width="{cw * 0.5:.1f}" '
                f'height="{fs * 0.92:.1f}" rx="1.5" fill="{c["yellow"]}"/></g>')
    # nickname: tiny, lower-right of the name
    end_x = x0 + cw * len(chars)
    body.append(f'<text class="nick sans" x="{end_x:.1f}" y="{base_y + 26}" font-size="12.5" letter-spacing=".4" '
                f'text-anchor="end" fill="{c["pink"]}">{esc(NICKNAME)}</text>')
    # role
    body.append(f'<text class="role sans" x="{x0}" y="198" font-size="22" font-weight="600" fill="{c["text"]}">{esc(ROLE)}</text>')

    # pipeline: C++ -> Blueprints -> Unreal Editor
    col_x = [40, 325, 610]
    top = 232
    for i, ((name, caps, slug), cx_) in enumerate(zip(PIPELINE, col_x)):
        g = [icon(slug, cx_, top, 30, c["text"], 0.95)]
        g.append(f'<text x="{cx_ + 44}" y="{top + 22}" font-size="20" font-weight="700" fill="{c["text"]}">{esc(name)}</text>')
        for j, line in enumerate(caps):
            g.append(f'<text class="sans" x="{cx_ + 44}" y="{top + 44 + j * 16}" font-size="12.5" fill="{c["muted"]}">{esc(line)}</text>')
        body.append(f'<g class="p{i}">{"".join(g)}</g>')
        if i < 2:
            ax = cx_ + 216
            body.append(
                f'<g class="a{i}"><circle cx="{ax}" cy="{top + 15}" r="1.9" fill="{c["yellow"]}"/>'
                f'<circle cx="{ax + 12}" cy="{top + 15}" r="1.9" fill="{c["yellow"]}" opacity=".75"/>'
                f'<circle cx="{ax + 24}" cy="{top + 15}" r="1.9" fill="{c["yellow"]}" opacity=".5"/>'
                f'<path d="M{ax + 35} {top + 9.5}l6 5.5-6 5.5" fill="none" stroke="{c["yellow"]}" stroke-width="1.8" '
                f'stroke-linecap="round" stroke-linejoin="round"/></g>')

    # footer line
    body.append(f'<path d="M40 318.5H{W - 40}" stroke="{c["border"]}"/>')
    body.append(f'<g class="foot"><text class="sans" x="40" y="348" font-size="14" fill="{c["muted"]}">{esc(ALSO)}</text>'
                f'<text x="{W - 40}" y="348" font-size="11" letter-spacing=".8" text-anchor="end" fill="{c["dim"]}">{esc(TAGLINE)}</text></g>')

    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
            f'aria-labelledby="t d"><title id="t">{esc(TITLE)} {esc(NICKNAME)}</title>'
            f'<desc id="d">{esc(ROLE)}. C++ gameplay programmer, Blueprint scripter, Unreal Editor. {esc(ALSO)}</desc>'
            f'<style>{"".join(css)}</style>{"".join(body)}</svg>')


# ----------------------------------------------------------------------------
# Full-stack toolkit
# ----------------------------------------------------------------------------
def stack(theme: str) -> str:
    c = THEMES[theme]
    W = 880
    col_x = [40, 330, 620]
    row = 27
    top = 34
    rows = max(len(items) for _, items in STACK)
    H = top + rows * row + 14
    body = [f"<style>.sans{{font-family:{SANS}}}text{{font-family:{SANS}}}</style>"]
    for (group, items), x in zip(STACK, col_x):
        body.append(f'<text x="{x}" y="16" font-size="11.5" letter-spacing=".6" fill="{c["dim"]}">{esc(group)}</text>')
        for i, slug in enumerate(items):
            y = top + i * row
            body.append(icon(slug, x, y - 1, 17, c["text"], 0.88))
            body.append(f'<text x="{x + 28}" y="{y + 13}" font-size="14.5" fill="{c["text"]}">{esc(ICONS[slug]["label"])}</text>')
    # secondary skills sit under the short third column
    n3 = len(STACK[2][1])
    y2 = top + n3 * row + 14
    body.append(f'<text x="{col_x[2]}" y="{y2}" font-size="11.5" letter-spacing=".6" fill="{c["dim"]}">Also used</text>')
    parts = ALSO_USED.split(" · ")
    lines, cur = [], ""
    for p in parts:
        nxt = (cur + " · " + p) if cur else p
        if len(nxt) > 30 and cur:
            lines.append(cur)
            cur = p
        else:
            cur = nxt
    lines.append(cur)
    for j, line in enumerate(lines):
        body.append(f'<text x="{col_x[2]}" y="{y2 + 20 + j * 19}" font-size="13" fill="{c["muted"]}">{esc(line)}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
            f'aria-label="Full-stack toolkit: TypeScript, JavaScript, React, Angular, HTML, CSS, Tailwind CSS, Python, '
            f'Django, Flask, FastAPI, Java, Spring Boot, PostgreSQL, MySQL, Git">{"".join(body)}</svg>')


# ----------------------------------------------------------------------------
# Section header: tiny Pac-Man, the title, then a trail of pellets
# ----------------------------------------------------------------------------
def header(theme: str, title: str) -> str:
    c = THEMES[theme]
    W, H = 880, 44
    tx = 34
    est = tx + len(title) * 9.3 + 16
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{esc(title)}">'
        f'<path fill="{c["yellow"]}" d="M14 23.5L20.1 20A7 7 0 1 0 20.1 27Z" transform="translate(-6 -1.5)"/>'
        f'<text x="{tx}" y="28" font-family=\'{MONO}\' font-size="15.5" font-weight="700" letter-spacing=".3" fill="{c["text"]}">{esc(title)}</text>'
        f'<path d="M{est:.0f} 22H{W - 8}" stroke="{c["dim"]}" stroke-width="3" stroke-linecap="round" stroke-dasharray="0 11" opacity=".75"/>'
        f"</svg>")


# ----------------------------------------------------------------------------
# Tide: two slow waves, drifting, rising and falling
# ----------------------------------------------------------------------------
def tide(theme: str) -> str:
    c = THEMES[theme]
    W, H, lam = 880, 56, 110

    def wave(amp, phase, y):
        pts = []
        for xx in range(-lam, W + lam * 2 + 1, 5):
            pts.append(f"{xx},{y + amp * math.sin(2 * math.pi * (xx + phase) / lam):.2f}")
        return "M" + " L".join(pts)

    css = (
        f"@keyframes d1{{to{{transform:translateX({-lam}px)}}}}@keyframes d2{{to{{transform:translateX({lam}px)}}}}"
        "@keyframes ride{0%,100%{transform:translateY(7px)}50%{transform:translateY(-5px)}}"
        ".w1{animation:d1 9s linear infinite}.w2{animation:d2 14s linear infinite}"
        ".tide{animation:ride 13s ease-in-out infinite}" + REDUCED)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="A slow tide line">'
        f'<style>{css}</style><g class="tide" fill="none" stroke-linecap="round">'
        f'<path class="w1" d="{wave(5.5, 0, 26)}" stroke="{c["wave"]}" stroke-width="1.4" opacity=".55"/>'
        f'<path class="w2" d="{wave(4, 40, 34)}" stroke="{c["yellow"]}" stroke-width="1.2" opacity=".45"/>'
        f"</g></svg>")


def main():
    for theme in ("dark", "light"):
        write(f"hero-{theme}.svg", hero(theme))
        write(f"stack-{theme}.svg", stack(theme))
        write(f"tide-{theme}.svg", tide(theme))
        for key, title in HEADERS.items():
            write(f"h-{key}-{theme}.svg", header(theme, title))


if __name__ == "__main__":
    main()
