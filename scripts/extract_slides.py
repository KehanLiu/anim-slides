#!/usr/bin/env python3
"""Extract an outline from an existing deck and suggest illustration archetypes.

Usage:
    extract_slides.py <deck.pptx|deck.html|doc.md> [--stage W H] [-o outline.json]

Reads a PowerPoint file, an HTML slide deck (reveal.js, frontend-slides, any
<section>/.slide/.step markup) or a Markdown document (split on `---` lines,
or on #/## headings when there are none) and writes a JSON outline:

    {"source": "deck.pptx", "stage": [1920, 1080], "slides": [
      {"index": 3, "title": "Release process", "bullets": [...], "notes": "...",
       "text": "...", "has_image": true, "image_count": 1,
       "suggested_archetype": "pipeline", "confidence": 0.6,
       "reason": "cues: arrows, numbered steps"}]}

The archetype is one of pipeline, graph, timeline, states, compare, layers,
chart (see references/archetypes.md) or null when no structural cue is found.
It is only a suggestion from keyword heuristics; review it before building.

The stage defaults to 1920x1080. For .pptx without --stage it is derived from
the deck's slide size, scaled to a width of 1920. python-pptx is used when
installed; otherwise the .pptx is read with zipfile + xml.etree. A one-line
summary per slide goes to stderr; the JSON goes to stdout unless -o is given.
"""
import argparse
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

try:  # optional dependency
    import pptx as _pptx  # type: ignore
except ImportError:  # pragma: no cover - depends on environment
    _pptx = None

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/package/2006/relationships",
}
TITLE_PH = {"title", "ctrTitle"}
NOTES_SKIP_PH = {"sldNum", "sldImg", "dt", "hdr", "ftr"}


def collapse(s):
    return re.sub(r"\s+", " ", s or "").strip()


def make_slide(title="", bullets=(), notes="", text="", image_count=0):
    return {"title": collapse(title), "bullets": [collapse(b) for b in bullets if collapse(b)],
            "notes": collapse(notes), "text": collapse(text),
            "has_image": image_count > 0, "image_count": image_count}


# ---------------------------------------------------------------- pptx ----
def pptx_stage(path):
    with zipfile.ZipFile(path) as z:
        try:
            root = ET.fromstring(z.read("ppt/presentation.xml"))
        except KeyError:
            return None
    sz = root.find("p:sldSz", NS)
    if sz is None:
        return None
    cx, cy = int(sz.get("cx", 0)), int(sz.get("cy", 0))
    return [1920, round(1920 * cy / cx)] if cx and cy else None


def _paragraphs(el):
    for p in el.iter("{%s}p" % NS["a"]):
        yield "".join(t.text or "" for t in p.iter("{%s}t" % NS["a"]))


def _ph_type(sp):
    ph = sp.find("p:nvSpPr/p:nvPr/p:ph", NS)
    return None if ph is None else ph.get("type", "body")


def read_pptx_zip(path):
    slides = []
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        found = [(int(m.group(1)), n) for n in names
                 if (m := re.fullmatch(r"ppt/slides/slide(\d+)\.xml", n))]
        for num, name in sorted(found):
            root = ET.fromstring(z.read(name))
            title, bullets = "", []
            for sp in root.iter("{%s}sp" % NS["p"]):
                paras = [collapse(t) for t in _paragraphs(sp) if collapse(t)]
                if _ph_type(sp) in TITLE_PH and not title:
                    title = " ".join(paras)
                else:
                    bullets.extend(paras)
            text = " ".join(_paragraphs(root))
            pics = len(list(root.iter("{%s}pic" % NS["p"])))
            notes = ""
            rels = "ppt/slides/_rels/slide%d.xml.rels" % num
            if rels in names:
                for rel in ET.fromstring(z.read(rels)).findall("r:Relationship", NS):
                    if rel.get("Type", "").endswith("/notesSlide"):
                        target = os.path.normpath(os.path.join("ppt/slides", rel.get("Target", "")))
                        target = target.replace(os.sep, "/")
                        if target in names:
                            nroot = ET.fromstring(z.read(target))
                            notes = " ".join(
                                t for sp in nroot.iter("{%s}sp" % NS["p"])
                                if _ph_type(sp) not in NOTES_SKIP_PH
                                for t in _paragraphs(sp))
            slides.append(make_slide(title, bullets, notes, text, pics))
    return slides


def read_pptx_lib(path):
    from pptx.enum.shapes import MSO_SHAPE_TYPE  # type: ignore
    prs = _pptx.Presentation(path)

    def walk(shapes):
        for sh in shapes:
            yield sh
            if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
                yield from walk(sh.shapes)

    slides = []
    for slide in prs.slides:
        title_shape = slide.shapes.title
        title = title_shape.text_frame.text if title_shape is not None else ""
        bullets, text, pics = [], [], 0
        for sh in walk(slide.shapes):
            if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
                pics += 1
            if getattr(sh, "has_text_frame", False) and sh.has_text_frame:
                paras = [p.text for p in sh.text_frame.paragraphs]
                text.extend(paras)
                if title_shape is None or sh.shape_id != title_shape.shape_id:
                    bullets.extend(paras)
            if getattr(sh, "has_table", False) and sh.has_table:
                text.extend(c.text for row in sh.table.rows for c in row.cells)
        notes = ""
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
            notes = slide.notes_slide.notes_text_frame.text
        slides.append(make_slide(title, bullets, notes, " ".join(text), pics))
    stage = [1920, round(1920 * prs.slide_height / prs.slide_width)] if prs.slide_width else None
    return slides, stage


# ---------------------------------------------------------------- html ----
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "source", "track", "wbr", "param"}


class Node:
    def __init__(self, tag, attrs, parent=None):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs), parent, []

    @property
    def classes(self):
        return (self.attrs.get("class") or "").lower().split()

    def iter(self):
        yield self
        for c in self.children:
            if isinstance(c, Node):
                yield from c.iter()


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = self.cur = Node("#root", {})

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.cur)
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:  # ignore stray end tags
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def container_kind(n):
    """'strong' for <section>/.slide/.step, 'weak' for other class*="slide"."""
    cls = n.classes
    if n.tag == "section" or "slide" in cls or "step" in cls:
        return "strong"
    if any("slide" in c for c in cls):
        return "weak"
    return None


def leaf_containers(node):
    """Innermost slide containers; a strong container whose only nested
    containers are weak (e.g. .slide > .slide-content) is itself the slide."""
    out = []
    for child in node.children:
        if not isinstance(child, Node):
            continue
        kind = container_kind(child)
        if kind is None:
            out.extend(leaf_containers(child))
            continue
        nested = [container_kind(d) for d in child.iter() if d is not child]
        if "strong" in nested or (kind == "weak" and "weak" in nested):
            out.extend(leaf_containers(child))
        else:
            out.append(child)
    return out


def node_text(n, skip_notes=True):
    parts = []
    for c in n.children:
        if isinstance(c, str):
            parts.append(c)
        elif c.tag in ("script", "style", "template") or (
                skip_notes and c.tag == "aside" and "notes" in c.classes):
            continue
        else:
            parts.append(" " + node_text(c, skip_notes) + " ")
    return "".join(parts)


def html_slide(n):
    nodes = list(n.iter())
    title = ""
    for wanted in (("h1", "h2"), ("h3",)):
        hit = next((d for d in nodes if d.tag in wanted), None)
        if hit is not None:
            title = node_text(hit)
            break
    notes = " ".join(node_text(d, False) for d in nodes if d.tag == "aside" and "notes" in d.classes)
    in_notes = {id(x) for d in nodes if d.tag == "aside" and "notes" in d.classes for x in d.iter()}
    bullets = [node_text(d) for d in nodes if d.tag == "li" and id(d) not in in_notes]

    def inside(d, tag):
        p = d.parent
        while p is not None and p is not n.parent:
            if p.tag == tag:
                return True
            p = p.parent
        return False
    images = sum(1 for d in nodes if (d.tag == "img" and not inside(d, "picture"))
                 or d.tag == "picture" or (d.tag == "svg" and not inside(d, "svg")))
    return make_slide(title, bullets, notes, node_text(n), images)


def read_html(path):
    tb = TreeBuilder()
    with open(path, encoding="utf-8", errors="replace") as f:
        tb.feed(f.read())
    tb.close()
    leaves = leaf_containers(tb.root)
    if not leaves:
        leaves = [next((d for d in tb.root.iter() if d.tag == "body"), tb.root)]
    return [html_slide(n) for n in leaves]


# ------------------------------------------------------------------ md ----
FENCE = re.compile(r"^\s*(`{3,}|~{3,})\s*([\w-]*)")


def read_md(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    if lines and lines[0].strip() == "---":  # YAML front matter
        end = next((i for i in range(1, len(lines)) if lines[i].strip() in ("---", "...")), None)
        if end is not None:
            lines = lines[end + 1:]
    # tag each line with whether it is inside a fence
    fenced, fence = [], None
    for ln in lines:
        m = FENCE.match(ln)
        if fence is None and m:
            fence = m.group(1)[0] * 3
            fenced.append(True)
        elif fence and ln.strip().startswith(fence):
            fence = None
            fenced.append(True)
        else:
            fenced.append(fence is not None)
    chunks, cur = [], []
    use_rule = any(ln.strip() == "---" and not fz for ln, fz in zip(lines, fenced))
    for ln, fz in zip(lines, fenced):
        if not fz and use_rule and ln.strip() == "---":
            chunks.append(cur)
            cur = []
            continue
        if not fz and not use_rule and re.match(r"#{1,2}\s", ln) and cur:
            chunks.append(cur)
            cur = []
        cur.append((ln, fz))
    chunks.append(cur)
    return [s for s in (md_slide(c) for c in chunks) if s]


def md_slide(chunk):
    if not any(ln.strip() for ln, _ in chunk):
        return None
    title, bullets, text, mermaid, block, lang = "", [], [], [], None, ""
    for ln, fz in chunk:
        m = FENCE.match(ln)
        if fz and m and block is None:
            block, lang = [], m.group(2).lower()
            continue
        if fz and block is not None and FENCE.match(ln) and not m.group(2):
            if lang == "mermaid":
                mermaid.append("\n".join(block))
            else:
                text.extend(block)
            block = None
            continue
        if block is not None:
            block.append(ln)
            continue
        h = re.match(r"\s*#{1,6}\s+(.*?)\s*#*\s*$", ln)
        if h and not title:
            title = h.group(1)
        b = re.match(r"\s*(?:[-*+]|\d+\.)\s+(.*)", ln)
        if b:
            bullets.append(b.group(1))
        text.append(ln)
    if block is not None:  # unterminated fence
        (mermaid if lang == "mermaid" else text).append("\n".join(block))
    raw = "\n".join(text)
    notes = " ".join(re.findall(r"<!--(.*?)-->", raw, re.S))
    raw = re.sub(r"<!--.*?-->", " ", raw, flags=re.S)
    images = len(re.findall(r"!\[[^\]]*\]\([^)]*\)", raw)) + len(re.findall(r"<img\b", raw, re.I))
    slide = make_slide(title, bullets, notes, re.sub(r"^\s*#{1,6}\s+", "", raw, flags=re.M), images)
    if mermaid:
        slide["mermaid"] = mermaid
    return slide


# ----------------------------------------------------------- heuristics ----
def w(pattern):
    return re.compile(r"(?<![\w-])(?:%s)(?![\w-])" % pattern)


RULES = {  # archetype -> [(cue label, regex)]
    "pipeline": [("arrows", re.compile(r"->|→|=>|⇒|⟶")), ("'then'", w("then")),
                 ("numbered steps", re.compile(r"(?:^|\s)(?:\d+[.)]|step\s*\d+)\s", re.M)),
                 ("'step'", w(r"steps?|stages?|phases?"))],
    "graph": [("dependency verbs", w(r"depends on|depend on|requires?|calls|uses|imports"))],
    "timeline": [("years", re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")), ("quarters", w(r"q[1-4]")),
                 ("dates", re.compile(r"\d{4}-\d{2}-\d{2}|(?<![\w])(?:jan|feb|mar|apr|may|jun|jul"
                                      r"|aug|sep|oct|nov|dec)[a-z]*\.? \d{1,2}(?!\d)")),
                 ("'roadmap'", w("roadmaps?")), ("'milestone'", w("milestones?"))],
    "compare": [("'vs'", w(r"vs\.?|versus")), ("before/after", w("before|after")),
                ("old/new", w("old|new"))],
    "layers": [("'layer'", w("layers?|layered")), ("'tier'", w("tiers?")), ("'stack'", w("stacks?")),
               ("'on top of'", w("on top of"))],
    "states": [("'state'", w("states?")), ("'mode'", w("modes?")), ("'transition'", w("transitions?"))],
}
UNIT_NUM = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?\s?(?:%|ms|s|sec|min|h|hrs?|days?|gb|mb|kb|tb"
                      r"|k|m|bn|x|users|req/s|rps|€|\$|eur|usd|fps)(?![a-z])"
                      r"|[$€£]\s?\d+(?:[.,]\d+)?")


def mermaid_archetype(body):
    lines = [ln.strip() for ln in body.strip().splitlines() if ln.strip() and not ln.strip().startswith("%%")]
    if not lines:
        return None
    kind = lines[0].split()[0]
    if kind in ("flowchart", "graph"):
        sources = []
        for ln in lines[1:]:
            parts = re.split(r"\s*(?:-->|---|-\.->|==>|--[^->]+-->)\s*", ln)
            sources += [re.match(r"[\w-]*", p).group(0) for p in parts[:-1]]
        branching = len(sources) != len(set(sources)) or "{" in body
        return ("graph", "mermaid flowchart with branching") if branching else \
               ("pipeline", "mermaid flowchart without branching")
    table = {"sequenceDiagram": "graph", "stateDiagram": "states", "stateDiagram-v2": "states",
             "timeline": "timeline", "gantt": "timeline", "xychart-beta": "chart", "xychart": "chart"}
    return (table[kind], "mermaid %s" % kind) if kind in table else None


def suggest(slide):
    for body in slide.get("mermaid", []):
        hit = mermaid_archetype(body)
        if hit:
            return hit[0], 0.9, hit[1]
    # text already contains title and bullets; adding them again would double-count cues
    parts = [slide["text"], slide["notes"]]
    if slide["title"] not in slide["text"]:
        parts.insert(0, slide["title"])
    blob = " ".join(parts).lower()
    best = (0, 0, None, [])
    for arch, rules in RULES.items():
        cues = [(label, len(rx.findall(blob))) for label, rx in rules]
        cues = [(lab, n) for lab, n in cues if n]
        if cues:
            score = (len(cues), sum(n for _, n in cues))
            if score > best[:2]:
                best = (*score, arch, [lab for lab, _ in cues])
    units = len(UNIT_NUM.findall(blob))
    if units >= 3 and (2, units) > best[:2]:
        best = (2, units, "chart", ["%d numbers with units" % units])
    if best[2] is None:
        return None, 0.0, "no structural cues"
    conf = min(0.9, 0.3 + 0.15 * (best[0] - 1) + (0.15 if best[1] >= 4 else 0))
    return best[2], round(conf, 2), "cues: " + ", ".join(best[3])


# ----------------------------------------------------------------- main ----
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("source", help="deck.pptx, deck.html or doc.md")
    ap.add_argument("--stage", nargs=2, type=int, metavar=("W", "H"))
    ap.add_argument("-o", "--output", help="write JSON here instead of stdout")
    ap.add_argument("--no-pptx-lib", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    ext = os.path.splitext(args.source)[1].lower()
    stage = None
    if ext == ".pptx":
        if _pptx is not None and not args.no_pptx_lib:
            slides, stage = read_pptx_lib(args.source)
        else:
            slides, stage = read_pptx_zip(args.source), pptx_stage(args.source)
    elif ext in (".html", ".htm"):
        slides = read_html(args.source)
    elif ext in (".md", ".markdown"):
        slides = read_md(args.source)
    else:
        ap.error("unsupported input type: %s (want .pptx, .html or .md)" % ext)
    stage = list(args.stage) if args.stage else (stage or [1920, 1080])

    for i, s in enumerate(slides, 1):
        arch, conf, reason = suggest(s)
        s.update(index=i, suggested_archetype=arch, confidence=conf, reason=reason)
        print("%3d  %-36.36s %-9s %.2f" % (i, s["title"] or "(untitled)", arch or "-", conf),
              file=sys.stderr)
    keys = ["index", "title", "bullets", "notes", "text", "has_image", "image_count", "mermaid",
            "suggested_archetype", "confidence", "reason"]
    slides = [{k: s[k] for k in keys if k in s} for s in slides]
    out = {"source": os.path.basename(args.source), "stage": stage, "slides": slides}
    data = json.dumps(out, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(data + "\n")
    else:
        print(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
