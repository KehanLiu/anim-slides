#!/usr/bin/env python3
"""Build the README hero: docs/media/hero.gif (before -> after), and optionally a still PNG of the after slide.

Usage (from the repo root):
  python3 .github/scripts/build_hero.py [SOURCE.html] [FRAGMENT.html] [--gif PATH] [--png PATH]
                                [--fps 10] [--hold-before 1.3] [--hold-after 2.0] [--keep DIR]

  SOURCE.html    the "before" slide, a standalone HTML page (default examples/first-slide/source.html).
                 It is rendered as is in headless Chrome, with only a small "before" tag added on top,
                 so the GIF shows exactly the file a visitor can open.
  FRAGMENT.html  the anim-slides fragment for the "after" slide (default pool/parcel-route/parcel-route.html).
                 The after slide is built here: the source's <h1> title and <footer>, the fragment in the
                 body slot on the fragment's dark ground (--anim-bg fallback, or --bg), and an "after" tag.

The GIF (1200x675 by default): the before slide held --hold-before s, a short wipe, then the fragment's
one pass captured at --fps (each frame frozen at second t with a negative animation-delay and a paused
play state, the method of render-phases.sh), then the resting frame held --hold-after s. Identical
consecutive frames are merged. With --png PATH it also writes the after slide's resting frame (gate class
removed, as in print) at twice the GIF size (2400x1350); without it only the GIF is written.

Needs headless Chrome/Chromium/Edge (auto-detected, or set CHROME=/path) and Pillow (pip install pillow).
Pillow is used only by this maintainer script, for GIF encoding and the wipe; the skill itself and
every other script stay stdlib-only.
"""
import argparse, concurrent.futures, html, os, re, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .github/scripts/ -> repo root

try:
    from PIL import Image, ImageChops
except ImportError:  # pragma: no cover
    sys.exit("build_hero.py needs Pillow: pip install pillow")


def find_chrome():
    env = os.environ.get("CHROME")
    if env:
        return env
    for c in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Chromium.app/Contents/MacOS/Chromium",
              "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
              os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")):
        if os.access(c, os.X_OK):
            return c
    for c in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge"):
        p = shutil.which(c)
        if p:
            return p
    sys.exit("error: no Chrome/Chromium/Edge found; set CHROME=/path/to/chrome")


def shoot(chrome, page, png, w, h, scale=1):
    """Screenshot a local HTML file. Headless Chrome makes its own temporary profile per run, so runs
    can go in parallel; an explicit --user-data-dir made headless runs hang on macOS, so none is passed."""
    if os.path.exists(png):
        os.remove(png)
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    f"--force-device-scale-factor={scale}",
                    f"--window-size={w},{h}", f"--screenshot={png}", "file://" + page],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, timeout=120)
    if not os.path.isfile(png):
        sys.exit(f"screenshot failed: {page}")
    im = Image.open(png).convert("RGB")
    im.load()
    return im


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


TAG_CSS = ("position:fixed;top:{top}px;right:{right}px;z-index:2147483647;padding:{py}px {px}px;"
           "border-radius:999px;font:600 {fs}px/1.2 system-ui,-apple-system,'Segoe UI',sans-serif;"
           "letter-spacing:.02em;{colours}")


def tag_html(text, w, dark):
    k = w / 1200
    colours = ("background:#1B2C36;color:#93A7B2;border:1px solid #2A3D49" if dark
               else "background:#e2e2de;color:#55595f;border:1px solid #d3d3ce")
    css = TAG_CSS.format(top=round(24 * k), right=round(24 * k), py=round(5 * k), px=round(14 * k),
                         fs=round(16 * k), colours=colours)
    return f'<div style="{css}">{html.escape(text)}</div>'


def before_page(src_path, out, w, label):
    """The source slide unchanged, plus a <base> for its relative assets and the tag before </body>."""
    doc = open(src_path, encoding="utf-8").read()
    base = '<base href="file://%s/">' % os.path.dirname(os.path.abspath(src_path))
    m = re.search(r"<head\b[^>]*>", doc, re.I)
    doc = doc[:m.end()] + base + doc[m.end():] if m else base + doc
    tag = tag_html(label, w, dark=False)
    ends = list(re.finditer(r"</body\s*>", doc, re.I))
    doc = doc[:ends[-1].start()] + tag + doc[ends[-1].start():] if ends else doc + tag
    open(out, "w", encoding="utf-8").write(doc)


def after_page(src_path, frag_path, out, w, label, bg, t):
    """After slide: source title and footer, fragment in the slot. t=None is the resting frame (ungated)."""
    src = open(src_path, encoding="utf-8").read()
    frag = open(frag_path, encoding="utf-8").read()
    m = re.search(r"<h1\b[^>]*>(.*?)</h1\s*>", src, re.I | re.S)
    title = strip_tags(m.group(1)) if m else ""
    m = re.search(r"<footer\b[^>]*>(.*?)</footer\s*>", src, re.I | re.S)
    spans = re.findall(r"<span\b[^>]*>(.*?)</span\s*>", m.group(1), re.I | re.S) if m else []
    footer = "".join(f"<span>{html.escape(strip_tags(s))}</span>" for s in spans) or (
        f"<span>{html.escape(strip_tags(m.group(1)))}</span>" if m else "")
    vb = re.search(r'<svg\b[^>]*\bviewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', frag)
    vw, vh = (float(vb.group(1)), float(vb.group(2))) if vb else (16.0, 9.0)
    pause = "" if t is None else (
        ".visible *{animation-delay:-%ss !important;animation-play-state:paused !important}" % t)
    gate = "" if t is None else " visible"
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<base href="file://{os.path.dirname(os.path.abspath(frag_path))}/">
<style>
html,body{{margin:0;height:100%;background:{bg}}}
body{{display:grid;place-items:center;font-family:system-ui,-apple-system,'Segoe UI',sans-serif}}
.hero-slide{{box-sizing:border-box;width:min(100vw,177.78vh);aspect-ratio:16/9;background:{bg};color:#E6EDF0;
  padding:5.2% 5.4%;position:relative;container-type:inline-size}}
.hero-slide h1{{margin:0;font-size:3.4cqw;font-weight:700;color:#E6EDF0;letter-spacing:-.01em}}
.hero-slide h1::after{{content:"";display:block;width:10cqw;height:.35cqw;background:#34D1BF;margin-top:.9cqw}}
.hero-slot{{position:absolute;left:1.5%;right:1.5%;top:22%;bottom:13%;container-type:size;display:grid;place-items:center}}
.hero-fig{{width:min(100cqw,calc(100cqh * {vw} / {vh}));aspect-ratio:{vw}/{vh}}}
.hero-slide footer{{position:absolute;left:5.4%;right:5.4%;bottom:4.5%;display:flex;justify-content:space-between;
  font-size:1.05cqw;color:#93A7B2}}
{pause}
</style></head><body>
<section class="hero-slide{gate}">
<h1>{html.escape(title)}</h1>
<div class="hero-slot"><div class="hero-fig">
{frag}
</div></div>
<footer>{footer}</footer>
</section>
{tag_html(label, w, dark=True)}
</body></html>"""
    open(out, "w", encoding="utf-8").write(doc)


def to_gif_frame(im):
    return im.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("source", nargs="?", default=os.path.join(ROOT, "examples/first-slide/source.html"))
    ap.add_argument("fragment", nargs="?", default=os.path.join(ROOT, "pool/parcel-route/parcel-route.html"))
    ap.add_argument("--gif", default=os.path.join(ROOT, "docs/media/hero.gif"))
    ap.add_argument("--png", help="also write the after slide's resting frame at 2x to this PNG (default: GIF only)")
    ap.add_argument("--width", type=int, default=1200)
    ap.add_argument("--height", type=int, default=675)
    ap.add_argument("--fps", type=float, default=10.0)
    ap.add_argument("--hold-before", type=float, default=1.3)
    ap.add_argument("--hold-after", type=float, default=2.0)
    ap.add_argument("--wipe-frames", type=int, default=4)
    ap.add_argument("--bg", default="#0F1E27", help="after-slide ground (default: the --anim-bg fallback)")
    ap.add_argument("--before-label", default="before")
    ap.add_argument("--after-label", default="after")
    ap.add_argument("--jobs", type=int, default=4, help="parallel Chrome screenshots")
    ap.add_argument("--keep", help="keep the preview pages and frames in this directory")
    a = ap.parse_args()

    src, frag = os.path.abspath(a.source), os.path.abspath(a.fragment)
    for p in (src, frag):
        if not os.path.isfile(p):
            sys.exit(f"missing {p}")
    fm = re.search(r'data-anim-cycle="([\d.]+)"', open(frag, encoding="utf-8").read())
    if not fm:
        sys.exit("fragment has no data-anim-cycle")
    cycle = float(fm.group(1))
    chrome = find_chrome()
    W, H = a.width, a.height
    work = os.path.abspath(a.keep) if a.keep else tempfile.mkdtemp(prefix="build-hero-")
    os.makedirs(work, exist_ok=True)
    try:
        jobs = []  # (key, page, png, w, h, scale)
        before_page(src, os.path.join(work, "before.html"), W, a.before_label)
        jobs.append(("before", "before.html", "before.png", 1))
        n = int(round(cycle * a.fps))
        times = [round(i / a.fps, 3) for i in range(n + 1)]
        for t in times:
            after_page(src, frag, os.path.join(work, f"after-{t:.3f}.html"), W, a.after_label, a.bg, t)
            jobs.append((t, f"after-{t:.3f}.html", f"after-{t:.3f}.png", 1))
        after_page(src, frag, os.path.join(work, "after-rest.html"), W, a.after_label, a.bg, None)
        jobs.append(("rest", "after-rest.html", "after-rest.png", 1))
        if a.png:
            jobs.append(("rest2x", "after-rest.html", "after-rest@2x.png", 2))

        def run(j):
            key, page, png, scale = j
            return key, shoot(chrome, os.path.join(work, page), os.path.join(work, png), W, H, scale)

        with concurrent.futures.ThreadPoolExecutor(max(1, a.jobs)) as ex:
            shots = dict(ex.map(run, jobs))
        print(f"rendered {len(jobs)} screenshots in {work}")

        before, rest = shots["before"], shots["rest"]
        last = shots[times[-1]]
        if ImageChops.difference(last, rest).getbbox():
            print(f"WARN: the frame at {times[-1]} s differs from the resting frame "
                  f"(box {ImageChops.difference(last, rest).getbbox()}); the hold shows the resting frame")

        step = round(1000 / a.fps)
        seq = [(before, round(a.hold_before * 1000))]
        first = shots[times[0]]
        for k in range(1, a.wipe_frames + 1):  # left-to-right wipe from before to the after slide
            x = round(W * k / (a.wipe_frames + 1))
            f = before.copy()
            f.paste(first.crop((0, 0, x, H)), (0, 0))
            seq.append((f, 60))
        seq += [(shots[t], step) for t in times[:-1]]
        seq.append((rest, round(a.hold_after * 1000)))

        merged = []  # identical consecutive frames become one longer frame
        for im, d in seq:
            if merged and not ImageChops.difference(merged[-1][0], im).getbbox():
                merged[-1][1] += d
            else:
                merged.append([im, d])
        frames = [to_gif_frame(im) for im, _ in merged]
        durs = [d for _, d in merged]
        os.makedirs(os.path.dirname(os.path.abspath(a.gif)), exist_ok=True)
        frames[0].save(a.gif, save_all=True, append_images=frames[1:], duration=durs, loop=0,
                       optimize=True, disposal=1)
        print(f"wrote {a.gif}: {W}x{H}, {len(frames)} frames, {sum(durs) / 1000:.2f} s, "
              f"{os.path.getsize(a.gif) / 1e6:.2f} MB")
        if a.png:
            os.makedirs(os.path.dirname(os.path.abspath(a.png)), exist_ok=True)
            shots["rest2x"].save(a.png, optimize=True)
            print(f"wrote {a.png}: {shots['rest2x'].size[0]}x{shots['rest2x'].size[1]}")
    finally:
        if not a.keep:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
