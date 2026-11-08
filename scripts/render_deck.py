#!/usr/bin/env python3
"""Render a source deck to page PNGs and numbered contact sheets for intake triage.

Usage:
    render_deck.py <deck.pptx|deck.ppt|deck.odp|deck.pdf|deck.html> -o OUTDIR
                   [--per-sheet 12] [--width 320] [--pages 5,12-14] [--out-json FILE]

Writes:
    OUTDIR/pages/p-NN.png   every page at 60 dpi
    OUTDIR/sheet-NN.png     contact sheets: up to --per-sheet thumbnails (4 per row),
                            --width px each, slide number under each, one sheet <= ~1600 px wide
    OUTDIR/full/p-NN.png    only the --pages, at 120 dpi, for a closer look at candidates

Look at the sheets first (one image read per 12 slides); open full/ only for candidates.

Page numbers are the presentation's slide numbers, hidden slides included, so they match
extract_slides.py's "index". Hidden slides (pptx `<p:sld show="0">`, odp
`presentation:visibility="hidden"`) are exported too (LibreOffice ExportHiddenSlides) and
captioned "N hidden"; a LibreOffice that still skips them gets a grey "slide N (hidden)"
placeholder page in their place. One stderr line lists the hidden slide numbers.

Needs: soffice (LibreOffice) for PowerPoint, pdftoppm (poppler) and a Chrome, Chromium or Edge
binary (CHROME=/path overrides detection). HTML decks are printed to PDF with headless Chrome;
that follows the deck's @media print / @page rules (md_to_deck.py decks have them). A deck that
needs its own script to lay out slides, or has no print rules, may print as one long page; then
use render-phases.sh --page deck.html --slide N per candidate instead.
No ImageMagick, no Pillow: the sheets are an HTML grid screenshotted by headless Chrome.
"""
import argparse
import html
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import re
import struct
import time
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

COLS = 4
GAP = 12
CAPTION = 26


def find_chrome():
    env = os.environ.get("CHROME")
    if env:
        return env if (os.access(env, os.X_OK) or shutil.which(env)) else None
    home = os.path.expanduser("~")
    for c in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Chromium.app/Contents/MacOS/Chromium",
              "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
              home + "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        if os.access(c, os.X_OK):
            return c
    for c in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge"):
        if shutil.which(c):
            return shutil.which(c)
    return None


def find_soffice():
    for c in ("soffice", "libreoffice"):
        if shutil.which(c):
            return shutil.which(c)
    for c in ("/Applications/LibreOffice.app/Contents/MacOS/soffice",
              os.path.expanduser("~/Applications/LibreOffice.app/Contents/MacOS/soffice")):
        if os.access(c, os.X_OK):
            return c
    return None


def find_pdftoppm():
    p = shutil.which("pdftoppm")
    if p:
        return p
    for c in ("/opt/homebrew/bin/pdftoppm", "/usr/local/bin/pdftoppm"):
        if os.access(c, os.X_OK):
            return c
    return None


def die(msg, code=1):
    print("error: " + msg, file=sys.stderr)
    sys.exit(code)


def parse_pages(spec):
    out = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            if "-" in part:
                a, b = part.split("-", 1)
                a, b = int(a), int(b)
                if a < 1 or b < a:
                    raise ValueError
                out.update(range(a, b + 1))
            else:
                n = int(part)
                if n < 1:
                    raise ValueError
                out.add(n)
        except ValueError:
            die("--pages: expected numbers and ranges like 5,12-14, got %r" % part, 2)
    return sorted(out)


PPTX_EXT = (".pptx", ".pptm", ".ppsx", ".potx")


def hidden_slides(src):
    """(slide count, sorted hidden slide numbers) in presentation order, or None when the
    format carries no readable flag (.ppt, .key, .pdf, .html) or the file cannot be read."""
    ext = src.suffix.lower()
    try:
        with zipfile.ZipFile(src) as z:
            names = set(z.namelist())
            if ext in PPTX_EXT:
                return _pptx_hidden(z, names)
            if ext == ".odp" and "content.xml" in names:
                xml = z.read("content.xml").decode("utf-8", "replace")
                pages = re.findall(r"<draw:page\b[^>]*>", xml)
                return len(pages), [i + 1 for i, t in enumerate(pages)
                                    if re.search(r'presentation:visibility="hidden"', t)]
    except (zipfile.BadZipFile, OSError, KeyError):
        return None
    return None


def _pptx_hidden(z, names):
    """Same order as extract_slides.py: presentation.xml sldIdLst, else slideN.xml numbering."""
    found = sorted((int(m.group(1)), n) for n in names
                   if (m := re.fullmatch(r"ppt/slides/slide(\d+)\.xml", n)))
    order = [n for _, n in found]
    try:
        pres = z.read("ppt/presentation.xml").decode("utf-8", "replace")
        rels = z.read("ppt/_rels/presentation.xml.rels").decode("utf-8", "replace")
        target = {}
        for rel in re.findall(r"<Relationship\b[^>]*>", rels):
            i, t = re.search(r'\bId="([^"]+)"', rel), re.search(r'\bTarget="([^"]+)"', rel)
            if i and t:
                target[i.group(1)] = "ppt/" + t.group(1).lstrip("/").replace("ppt/", "", 1)
        lst = re.search(r"<p:sldIdLst\b.*?</p:sldIdLst>", pres, re.S)
        ids = re.findall(r'<p:sldId\b[^>]*\br:id="([^"]+)"', lst.group(0)) if lst else []
        listed = [target.get(r) for r in ids]
        listed = [n for n in listed if n in names]
        order = listed or order
    except KeyError:
        pass
    hidden = []
    for i, n in enumerate(order, 1):
        head = re.search(r"<p:sld\b[^>]*>", z.read(n).decode("utf-8", "replace"))
        if head and re.search(r'\bshow="(?:0|false)"', head.group(0)):
            hidden.append(i)
    return len(order), hidden


def write_png(path, w, h, rgb=(0x9a, 0x9a, 0x9a)):
    """A solid-colour PNG with the standard library only (fallback placeholder)."""
    row = b"\x00" + bytes(rgb) * w
    raw = zlib.compress(row * h, 9)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                           + chunk(b"IDAT", raw) + chunk(b"IEND", b""))


def placeholder(chrome, path, w, h, n):
    """Grey page labelled 'slide N (hidden)' at w x h px, for a slide the PDF export skipped."""
    hp = Path(path).with_suffix(".html")
    hp.write_text("<!doctype html><meta charset=utf-8><style>html,body{margin:0;height:100%%;"
                  "background:#9a9a9a;color:#fff;display:flex;align-items:center;justify-content:center;"
                  "font:bold %dpx system-ui,sans-serif}</style><div>slide %d (hidden)</div>"
                  % (max(12, h // 9), n), encoding="utf-8")
    try:
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=1", "--window-size=%d,%d" % (w, h),
                        "--screenshot=" + str(path), hp.resolve().as_uri()],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    except (OSError, subprocess.SubprocessError):
        pass
    hp.unlink()
    if not Path(path).exists():
        write_png(path, w, h)
    return Path(path)


def to_pdf(src, tmp, chrome):
    ext = src.suffix.lower()
    if ext == ".pdf":
        return src
    if ext in (".pptx", ".ppt", ".pptm", ".ppsx", ".pps", ".odp", ".key"):
        soffice = find_soffice()
        if not soffice:
            die("no soffice (LibreOffice) found; install it, or export the deck to PDF and pass the PDF")
        profile = Path(tmp) / ("lo-%d" % os.getpid())  # own profile: parallel runs do not collide
        pdf = Path(tmp) / (src.stem + ".pdf")
        # export hidden slides too, so page N is slide N (JSON filter options: LibreOffice 7.4+;
        # an older one fails or ignores them, then the plain export runs and main() fills gaps)
        for fmt in ('pdf:impress_pdf_Export:{"ExportHiddenSlides":{"type":"boolean","value":"true"}}', "pdf"):
            cmd = [soffice, "--headless", "-env:UserInstallation=" + profile.as_uri(),
                   "--convert-to", fmt, "--outdir", str(tmp), str(src)]
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
            if pdf.exists():
                break
        if not pdf.exists():
            die("soffice did not produce a PDF:\n" + r.stderr.decode(errors="replace")[-800:])
        return pdf
    if ext in (".html", ".htm"):
        if not chrome:
            die("no Chrome/Chromium/Edge found to print the HTML deck; set CHROME=/path/to/chrome")
        pdf = Path(tmp) / (src.stem + ".pdf")
        cmd = [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
               "--print-to-pdf=" + str(pdf), src.resolve().as_uri()]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
        if not pdf.exists():
            die("Chrome could not print %s to PDF; render candidates with "
                "render-phases.sh --page deck.html --slide N 1920 1080 rest instead" % src)
        return pdf
    die("unsupported input %s (use .pptx, .ppt, .odp, .pdf or .html)" % src.name, 2)


def rasterize(pdftoppm, pdf, dest, dpi, first=None, last=None, number=None, width=None):
    """Render pages to dest/p-NN.png; returns {page number: path}. number maps a PDF page
    to the slide number used in the file name (default: the same)."""
    dest.mkdir(parents=True, exist_ok=True)
    tmpdir = Path(tempfile.mkdtemp(dir=dest))
    cmd = [pdftoppm, "-png", "-r", str(dpi)]
    if first:
        cmd += ["-f", str(first), "-l", str(last or first)]
    cmd += [str(pdf), str(tmpdir / "x")]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900)
    if r.returncode != 0:
        shutil.rmtree(tmpdir, ignore_errors=True)
        die("pdftoppm failed: " + r.stderr.decode(errors="replace")[-500:])
    out = {}
    for f in tmpdir.glob("x-*.png"):
        out[int(f.stem.split("-")[-1])] = f
    number = number or {}
    width = width or max(2, len(str(max(out) if out else 1)))
    final = {}
    for p, f in sorted(out.items()):
        n = number.get(p, p)
        target = dest / ("p-%0*d.png" % (width, n))
        f.replace(target)
        final[n] = target
    shutil.rmtree(tmpdir, ignore_errors=True)
    return final


def png_size(path):
    with open(path, "rb") as fh:
        head = fh.read(24)
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def build_sheets(chrome, pages, outdir, per_sheet, tw, hidden=()):
    first = pages[min(pages)]
    w, h = png_size(first)
    th = max(1, round(h * tw / w))
    nums = sorted(pages)
    jobs = []
    for i in range(math.ceil(len(nums) / per_sheet)):
        chunk = nums[i * per_sheet:(i + 1) * per_sheet]
        cols = min(COLS, len(chunk))
        rows = math.ceil(len(chunk) / cols)
        cw = cols * (tw + GAP) + GAP
        ch = rows * (th + CAPTION + GAP) + GAP
        cells = "".join(
            '<figure><img src="%s"><figcaption>%d%s</figcaption></figure>'
            % (html.escape(pages[n].resolve().as_uri()), n,
               ' <span style="color:#aaa;font-weight:normal">hidden</span>' if n in hidden else "")
            for n in chunk)
        doc = ("<!doctype html><meta charset=utf-8><style>html,body{margin:0;background:#1d1d1d;"
               "font:bold 20px system-ui,sans-serif;color:#fff}"
               ".g{display:grid;grid-template-columns:repeat(%d,%dpx);gap:%dpx;padding:%dpx}"
               "figure{margin:0}img{width:%dpx;height:%dpx;display:block;object-fit:contain;"
               "background:#fff;outline:1px solid #555}"
               "figcaption{height:%dpx;line-height:%dpx;text-align:center}</style>"
               "<div class=g>%s</div>") % (cols, tw, GAP, GAP, tw, th, CAPTION, CAPTION, cells)
        hp = outdir / (".sheet-%02d.html" % (i + 1))
        hp.write_text(doc, encoding="utf-8")
        png = outdir / ("sheet-%02d.png" % (i + 1))
        if png.exists():
            png.unlink()
        jobs.append((hp, png, cw, ch, chunk))

    def shoot(job):
        hp, png, cw, ch, _ = job
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=1", "--allow-file-access-from-files",
                        "--window-size=%d,%d" % (cw, ch), "--screenshot=" + str(png), hp.resolve().as_uri()],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
        hp.unlink()

    with ThreadPoolExecutor(max_workers=min(4, len(jobs))) as ex:  # one headless Chrome per sheet
        list(ex.map(shoot, jobs))
    sheets = []
    for i, (_, png, _, _, chunk) in enumerate(jobs):
        if not png.exists():
            die("Chrome screenshot failed for sheet %d" % (i + 1))
        sheets.append({"sheet": str(png), "pages": [chunk[0], chunk[-1]]})
    return sheets


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("source", help="deck.pptx, deck.ppt, deck.odp, deck.pdf or deck.html")
    ap.add_argument("-o", "--outdir", required=True, help="output folder (created)")
    ap.add_argument("--per-sheet", type=int, default=12, help="thumbnails per contact sheet (default 12)")
    ap.add_argument("--width", type=int, default=320, help="thumbnail width in px (default 320, max 380)")
    ap.add_argument("--pages", help="also render these pages at 120 dpi into full/, e.g. 5,12-14")
    ap.add_argument("--out-json", help="write {pages, sheets, full} as JSON here")
    a = ap.parse_args()

    src = Path(a.source)
    if not src.is_file():
        die("missing %s" % src, 2)
    if a.per_sheet < 1:
        die("--per-sheet must be >= 1", 2)
    tw = max(120, min(a.width, (1600 - GAP) // COLS - GAP))  # keep a sheet <= ~1600 px wide
    if tw != a.width:
        print("note: --width clamped to %d px (sheet stays <= 1600 px wide)" % tw)
    want = parse_pages(a.pages) if a.pages else []
    chrome = find_chrome()
    pdftoppm = find_pdftoppm()
    if not pdftoppm:
        die("no pdftoppm found; install poppler (brew install poppler / apt install poppler-utils)")
    if not chrome:
        die("no Chrome/Chromium/Edge found for the contact sheets; set CHROME=/path/to/chrome")

    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix="render-deck.") as tmp:
        pdf = to_pdf(src, tmp, chrome)
        t1 = time.time()
        pages_dir = out / "pages"
        if pages_dir.exists():
            for f in pages_dir.glob("p-*.png"):
                f.unlink()
        info = hidden_slides(src)
        total, hidden = info if info else (0, [])
        width = max(2, len(str(total))) if total else None
        pages = rasterize(pdftoppm, pdf, pages_dir, 60, width=width)
        if not pages:
            die("the PDF has no pages")
        width = width or max(2, len(str(max(pages))))
        gaps = bool(hidden) and len(pages) == total - len(hidden)  # export skipped the hidden slides
        number = {}
        if gaps:  # PDF page -> slide number, stepping over the hidden ones
            number = dict(enumerate([n for n in range(1, total + 1) if n not in hidden], 1))
            moved = {}
            for p in sorted(pages, reverse=True):  # slide number >= page number: no overwrite
                target = pages_dir / ("p-%0*d.png" % (width, number[p]))
                pages[p].replace(target)
                moved[number[p]] = target
            pages = moved
            w, h = png_size(next(iter(pages.values())))
            for n in hidden:
                pages[n] = placeholder(chrome, pages_dir / ("p-%0*d.png" % (width, n)), w, h, n)
            pages = dict(sorted(pages.items()))
        if hidden:
            how = ("LibreOffice skipped them; grey placeholder pages inserted" if gaps else
                   "rendered, captioned 'hidden'" if len(pages) == total else
                   "WARNING: PDF has %d pages for %d slides, numbers may drift" % (len(pages), total))
            print("hidden slides: %s (%s)" % (",".join(map(str, hidden)), how), file=sys.stderr)
        elif info and len(pages) != total:
            print("warning: PDF has %d pages for %d slides; numbers may not match extract_slides.py"
                  % (len(pages), total), file=sys.stderr)
        t2 = time.time()
        sheets = build_sheets(chrome, pages, out, a.per_sheet, tw, set(hidden))
        for f in out.glob("sheet-*.png"):  # stale sheets from an earlier, longer deck
            if f.name not in {Path(s["sheet"]).name for s in sheets}:
                f.unlink()
        t3 = time.time()
        full = {}
        bad = [n for n in want if n not in pages]
        if bad:
            print("warning: --pages outside 1-%d ignored: %s" % (max(pages), ",".join(map(str, bad))))
        back = {v: k for k, v in number.items()}  # slide number -> PDF page
        for n in [n for n in want if n in pages]:
            if gaps and n in hidden:
                w, h = png_size(pages[n])
                (out / "full").mkdir(parents=True, exist_ok=True)
                full[n] = placeholder(chrome, (out / "full").joinpath("p-%0*d.png" % (width, n)), 2 * w, 2 * h, n)
                continue
            p = back.get(n, n)
            full.update(rasterize(pdftoppm, pdf, out / "full", 120, p, p, number=number, width=width))
        t4 = time.time()

    print("%s: %d slides (to PDF %.1fs, pages %.1fs, sheets %.1fs, full %.1fs)"
          % (src.name, len(pages), t1 - t0, t2 - t1, t3 - t2, t4 - t3))
    print("pages:  %s/p-*.png" % pages_dir)
    for s in sheets:
        print("sheet:  %s  (slides %d-%d)" % (s["sheet"], s["pages"][0], s["pages"][1]))
    for n, p in sorted(full.items()):
        print("full:   %s" % p)
    print("look at the sheets first; open full/ only for candidates (--pages N,M-K).")
    if a.out_json:
        Path(a.out_json).write_text(json.dumps({
            "pages": len(pages),
            "hidden": hidden,
            "sheets": sheets,
            "full": {str(n): str(p) for n, p in sorted(full.items())},
        }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
