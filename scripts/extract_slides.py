#!/usr/bin/env python3
"""Extract an outline from an existing deck and suggest illustration archetypes.

Usage:
    extract_slides.py <deck.pptx|deck.html|doc.md> [--stage W H] [-o outline.json]

Reads a PowerPoint file, an HTML slide deck (reveal.js, frontend-slides, any
<section>/.slide/.step markup) or a Markdown document (split on `---` lines,
or on #/## headings when there are none) and writes a JSON outline:

    {"source": "deck.pptx", "stage": [1920, 1080], "aspect": "16:9", "slides": [
      {"index": 3, "title": "Release process", "bullets": [...], "notes": "...",
       "text": "...", "has_image": true, "image_count": 1, "hidden_pictures": 0,
       "layout_pictures": 1,
       "tables": [[["Old", "New"], ["manual", "CI"]]], "connectors": 4,
       "builds": 4, "suggested_archetype": "pipeline", "confidence": 0.6,
       "reason": "cues: arrows, numbered steps", "order_only": true,
       "idea_cues": [], "suggested_verb": "reveal", "verb_cues": []}], "builds": 4}

`tables` (rows of cell strings), `connectors` (connector lines and arrow
shapes), `title_guessed` (no title placeholder; the title is the largest-font
or first short text) and `mermaid` appear only when present.

`image_count` counts the slide's own pictures (`p:pic`) that can be seen;
`hidden_pictures` (pptx, always present) those marked hidden (`cNvPr hidden="1"`,
on the picture or an enclosing group) or placed fully outside the slide.
`layout_pictures` (pptx, always present) counts the visible pictures (`p:pic`,
and `p:sp` filled with `a:blipFill`) of the slide's own layout part, which show
on the slide (a cover photo often lives there); the master's are not counted, a
layout placeholder is not counted, and a slide with `showMasterSp="0"` gets 0.
`has_image` follows `image_count` only. HTML and Markdown sources report 0 for
both new fields.

`builds` (per slide, always present, 0 when none) counts the click builds the
source deck already has; the top-level `builds` is the deck total. The default
control stays `once`; a deck that builds by click only means `step` is worth
mentioning if the presenter wants to click through.
pptx: click-triggered effects in `p:timing` (`p:cTn nodeType="clickEffect"`).
HTML: elements with class `fragment` (reveal.js), `data-fragment-index`,
`build`/`build-item`, `substep` (impress.js substep plugin), and `.step` nested
inside a slide (a deck's own build steps; a top-level impress.js `.step` is the
slide itself). Markdown: remark `--` incremental separators.

The archetype is one of pipeline, graph, timeline, states, compare, layers,
chart (see references/archetypes.md) or null when no structural cue is found.
It is only a suggestion from keyword and shape heuristics; review it before
building. Numbered items, 'then', 'step' and arrows only say the text is laid
out in order, not what shape the idea has.

`idea_cues` (per slide, always present, [] when none) is evidence for the
picture idea: [{"cue": name, "evidence": the matched source words}], with name
one of falling-quantities / rising-quantities (3+ numbers in reading order,
item indices and years skipped, same unit or all bare, strictly monotonic),
returns (cycle, loop, starts again, back to, re-enters, feeds back, iterate ...),
trade-off (versus, trade-off, at the cost of, on the other hand ...), contains
(inside, within, part of, consists of, nested ...), split-merge (splits into,
in parallel, merges, combines, converges ...), handover (hands over, transfer
to, passes to, across the boundary ...), before-after (before ... after, was
... now, from <number> to <number>), share-of-whole (percentages summing to
about 100, 'share of', 'of all' ...). Numbered formatting alone is never a cue.
`order_only` appears only when the suggestion is pipeline: true when no idea
cue fired and the verb is `reveal` (order is all the source says, a row is
right), false otherwise; with idea cues the confidence is capped at 0.3 (except
for a mermaid flowchart) and the reason names the cues.

`suggested_verb` (per slide, always present) is the main motion from
references/motion-verbs.md section 1: grow, count, accumulate, thin, race,
split, merge, sort, stack, nest, transform, wipe, switch, balance, drive, zoom,
open, travel, trace, cycle, or the support move reveal; null only on a slide
with no archetype and no verb cue (keep as text). `verb_cues` (always present,
[] when none) is [{"cue": verb, "evidence": matched source words}] in priority
order, first = the suggested verb; [] beside a verb means the family default
(chart grow, timeline trace, states switch, compare wipe, layers stack,
pipeline/graph reveal). Cues (English, German, Chinese/Japanese): numbers
(falling counts -> thin, rising or 'from 4% to 11%' -> grow, shares summing to
100% or 'of every' -> sort, 'faster than' or versus with numbers -> race, one
headline figure -> count, 'adds up to' -> accumulate); 'became'/'turned into'
-> transform; 'replaced'/'instead of'/before-after -> wipe; threshold, 'becomes
law' -> switch; 'made of'/'consists of'/'breaks down into' -> split;
'combines'/'merges'/'pooled' -> merge; 'inside'/'within'/'part of' -> nest;
'closer look'/'underneath' -> zoom; 'cross-section'/'layers of' -> open; 'builds
on'/'foundation'/'layers' -> stack; 'because'/'drives'/'the more ... the more'
-> drive; trade-off/versus -> balance; 'returns'/'starts again'/'feeds back' -> cycle;
'trend'/'over time' -> trace. `travel` needs a thing that changes place between
named places: 'sent to', 'shipped', 'handed to', 'delivered', 'arrives at',
'route', 'from Leeds to York'; numbering, arrows and connectors are never
travel. A pipeline or graph whose only cues are order (arrows, numbering,
'then', 'step', connectors) keeps confidence <= 0.3 with verb reveal (<= 0.6
for travel); when a stronger verb (a quantity, cycle, trade-off, containment,
before/after, split/merge) fired, the archetype becomes that verb's family
(thin keeps pipeline as a funnel; cycle -> states; balance/race/wipe -> compare;
nest/stack/open/zoom -> layers; split/merge -> graph; grow/sort/accumulate ->
chart). A slide with its own chart (mermaid xychart, a pptx chart part, a
picture beside chart or trend words) keeps its archetype and gets trace (3+
time-axis marks) or grow; another mermaid diagram keeps its archetype and gets
its text verb, else travel (sequence), switch (state) or reveal.

The stage defaults to 1920x1080. For .pptx without --stage it is derived from
the deck's slide size, scaled to a width of 1920 (a 4:3 deck gives 1920x1440).
For HTML without --stage it is read from the deck, first hit wins: CSS custom
properties (--W/--H, --stage-w/--stage-h, --slide-width/--slide-height) on
:root/html/body/.deck; a top-level rule for the slide container (.slide,
section, .deck-stage, .stage, .step) with px width and height; a numeric
viewport meta width (16:9 assumed); reveal.js Reveal.initialize({width,
height}). `stage_source` says which: css-vars, slide-rule, viewport, reveal,
pptx, flag (--stage, always wins) or default.
Cue words include Chinese and Japanese equivalents (matched without word
boundaries, since CJK text has no spaces); 2020年, 3月, 三月 count as dates.
The .pptx is read with zipfile + xml.etree (no dependencies); for a legacy .ppt
convert it first with `soffice --headless --convert-to pptx deck.ppt`. A
one-line summary per slide goes to stderr; the JSON goes to stdout unless -o is
given.
"""
import argparse
import json
import math
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/package/2006/relationships",
}
A, P = "{%s}" % NS["a"], "{%s}" % NS["p"]
TITLE_PH = {"title", "ctrTitle"}
CHROME_PH = {"sldNum", "dt", "ftr", "hdr", "sldImg"}  # slide furniture, never content


def collapse(s):
    return re.sub(r"\s+", " ", s or "").strip()


def make_slide(title="", bullets=(), notes="", text="", image_count=0, tables=None,
               connectors=0, segments=None, branching=False, title_guessed=False, builds=0,
               hidden_pictures=0, layout_pictures=0):
    slide = {"title": collapse(title), "bullets": [collapse(b) for b in bullets if collapse(b)],
             "notes": collapse(notes), "text": collapse(text),
             "has_image": image_count > 0, "image_count": image_count,
             "hidden_pictures": hidden_pictures, "layout_pictures": layout_pictures,
             "builds": builds}
    tables = [t for t in (tables or []) if t]
    if tables:
        slide["tables"] = [[[collapse(c) for c in row] for row in t] for t in tables]
    if connectors:
        slide["connectors"] = connectors
    if title_guessed and slide["title"]:
        slide["title_guessed"] = True
    slide["_segments"] = [collapse(x) for x in (segments or []) if collapse(x)]
    slide["_branching"] = branching
    return slide


# ---------------------------------------------------------------- pptx ----
def pptx_size(z):
    """Slide size in EMU (cx, cy), or None."""
    try:
        root = ET.fromstring(z.read("ppt/presentation.xml"))
    except KeyError:
        return None
    sz = root.find("p:sldSz", NS)
    if sz is None:
        return None
    cx, cy = int(sz.get("cx", 0)), int(sz.get("cy", 0))
    return (cx, cy) if cx and cy else None


def pptx_stage(path):
    with zipfile.ZipFile(path) as z:
        size = pptx_size(z)
    return [1920, round(1920 * size[1] / size[0])] if size else None


def _xfrm(el, path):
    """(x, y, cx, cy, chx, chy, chcx, chcy) of el's a:xfrm under path, ints, or None."""
    x = el.find(path, NS)
    if x is None:
        return None
    off, ext = x.find("a:off", NS), x.find("a:ext", NS)
    if off is None or ext is None:
        return None
    vals = [off.get("x"), off.get("y"), ext.get("cx"), ext.get("cy")]
    cho, che = x.find("a:chOff", NS), x.find("a:chExt", NS)
    if cho is not None and che is not None:
        vals += [cho.get("x"), cho.get("y"), che.get("cx"), che.get("cy")]
    try:
        return [int(v) for v in vals]
    except (TypeError, ValueError):
        return None


def _pictures(root, size, blip_shapes=False, skip_placeholders=False):
    """(visible, hidden) picture counts in a slide or layout part. A picture is `p:pic`
    (and, with blip_shapes, a `p:sp` whose spPr is an `a:blipFill`). Hidden: `cNvPr
    hidden="1"` on it or an enclosing group, or its box (mapped through group transforms)
    fully outside the slide. A picture without a position counts as visible."""
    counts = [0, 0]

    def walk(el, tf, hidden):
        for ch in el:
            tag = ch.tag
            if tag == P + "grpSp":
                c = ch.find("p:nvGrpSpPr/p:cNvPr", NS)
                g = _xfrm(ch, "p:grpSpPr/a:xfrm")
                sub = tf
                if g and len(g) == 8:
                    sx = g[2] / g[6] if g[6] else 1.0
                    sy = g[3] / g[7] if g[7] else 1.0
                    sub = (lambda t, g=g, sx=sx, sy=sy:
                           tf((g[0] + (t[0] - g[4]) * sx, g[1] + (t[1] - g[5]) * sy,
                               t[2] * sx, t[3] * sy)))
                walk(ch, sub, hidden or (c is not None and c.get("hidden") in ("1", "true")))
                continue
            if tag == P + "pic":
                nv, sppr = "p:nvPicPr", "p:spPr"
            elif blip_shapes and tag == P + "sp" and ch.find("p:spPr/a:blipFill", NS) is not None:
                nv, sppr = "p:nvSpPr", "p:spPr"
            else:
                walk(ch, tf, hidden)
                continue
            if skip_placeholders and ch.find(nv + "/p:nvPr/p:ph", NS) is not None:
                continue
            c = ch.find(nv + "/p:cNvPr", NS)
            gone = hidden or (c is not None and c.get("hidden") in ("1", "true"))
            box = _xfrm(ch, sppr + "/a:xfrm")
            if not gone and box and size:
                x, y, cx, cy = tf(tuple(box[:4]))
                gone = x + cx <= 0 or y + cy <= 0 or x >= size[0] or y >= size[1]
            counts[1 if gone else 0] += 1
    walk(root, lambda t: t, False)
    return tuple(counts)


def _rel_target(z, names, part, kind):
    """Zip name of the first relationship of `kind` (a Type suffix) from part, or None."""
    folder, base = part.rsplit("/", 1)
    rels = "%s/_rels/%s.rels" % (folder, base)
    if rels not in names:
        return None
    for rel in ET.fromstring(z.read(rels)).findall("r:Relationship", NS):
        if rel.get("Type", "").endswith("/" + kind) and rel.get("TargetMode") != "External":
            t = rel.get("Target", "")
            t = t.lstrip("/") if t.startswith("/") else os.path.normpath(os.path.join(folder, t))
            t = t.replace(os.sep, "/")
            return t if t in names else None
    return None


def pptx_layout_pictures(z, names, slide_name, slide_root, size, cache):
    """Visible pictures on the slide's own layout (not the master); 0 when the slide hides
    master/layout shapes (showMasterSp="0")."""
    if slide_root.get("showMasterSp") in ("0", "false"):
        return 0
    layout = _rel_target(z, names, slide_name, "slideLayout")
    if layout is None:
        return 0
    if layout not in cache:
        cache[layout] = _pictures(ET.fromstring(z.read(layout)), size, blip_shapes=True,
                                  skip_placeholders=True)[0]
    return cache[layout]


def _para_text(p):
    """Text of one <a:p>: runs and fields, <a:br/> as a space, no slide-number/date fields."""
    out = []
    for el in p:
        if el.tag == A + "br":
            out.append(" ")
        elif el.tag == A + "fld":
            kind = el.get("type", "")
            if kind != "slidenum" and not kind.startswith("datetime"):
                out.append(el.findtext("a:t", "", NS))
        elif el.tag in (A + "pPr", A + "endParaRPr"):
            continue
        else:  # a:r, or wrappers such as mc:AlternateContent
            out.append("".join(t.text or "" for t in el.iter(A + "t")))
    return "".join(out)


def _paragraphs(el):
    for p in el.iter(A + "p"):
        yield collapse(_para_text(p))


def _para_size(el):
    sizes = [int(r.get("sz")) for r in el.iter() if r.tag in (A + "rPr", A + "endParaRPr", A + "defRPr")
             and (r.get("sz") or "").isdigit()]
    return max(sizes) if sizes else 0


def _ph_type(sp):
    ph = sp.find("p:nvSpPr/p:nvPr/p:ph", NS)
    return None if ph is None else ph.get("type", "body")


def _is_arrow(sp):
    geom = sp.find("p:spPr/a:prstGeom", NS)
    prst = geom.get("prst", "") if geom is not None else ""
    if "Arrow" in prst or prst in ("chevron", "homePlate"):
        return True
    ln = sp.find("p:spPr/a:ln", NS)
    if ln is None:
        return False
    return any(e is not None and e.get("type", "none") != "none"
               for e in (ln.find("a:headEnd", NS), ln.find("a:tailEnd", NS)))


def _table_rows(tbl):
    rows = []
    for tr in tbl.findall("a:tr", NS):
        cells = []
        for tc in tr.findall("a:tc", NS):
            merged = tc.get("hMerge") == "1" or tc.get("vMerge") == "1"
            cells.append("" if merged else " ".join(t for t in _paragraphs(tc) if t))
        if any(cells):
            rows.append(cells)
    return rows


def pptx_slide(root):
    title, shapes, tables, text = "", [], [], []
    conns = 0
    starts, ends = [], []
    for el in root.iter():
        if el.tag == P + "cxnSp":
            conns += 1
            c = el.find("p:nvCxnSpPr/p:cNvCxnSpPr", NS)
            if c is not None:
                st, en = c.find("a:stCxn", NS), c.find("a:endCxn", NS)
                if st is not None:
                    starts.append(st.get("id"))
                if en is not None:
                    ends.append(en.get("id"))
        elif el.tag == P + "graphicFrame":
            for tbl in el.iter(A + "tbl"):
                rows = _table_rows(tbl)
                if rows:
                    tables.append(rows)
                    text.extend(c for r in rows for c in r if c)
        elif el.tag == P + "sp":
            ph = _ph_type(el)
            if ph in CHROME_PH:
                continue
            if _is_arrow(el):
                conns += 1
            paras = [t for t in _paragraphs(el) if t]
            if not paras:
                continue
            text.extend(paras)
            if ph in TITLE_PH and not title:
                title = " ".join(paras)
                continue
            shapes.append({"paras": paras, "size": _para_size(el)})
    guessed = False
    if not title and shapes:
        title, guessed = _guess_title(shapes), True
    bullets = [t for sh in shapes for t in sh["paras"]]
    branching = len(starts) != len(set(starts)) or len(ends) != len(set(ends))
    return title, bullets, text, tables, conns, branching, guessed, pptx_builds(root)


def pptx_builds(root):
    """Click builds on a slide: each click step of the animation timeline starts with a
    `p:cTn nodeType="clickEffect"` (with-previous and after-previous effects ride on it, and
    effects that start with the slide are not counted)."""
    timing = root.find("p:timing", NS)
    if timing is None:
        return 0
    return sum(1 for c in timing.iter(P + "cTn") if c.get("nodeType") == "clickEffect")


def _guess_title(shapes):
    """No title placeholder (e.g. a LibreOffice-converted .ppt): take the one short text box
    whose font is larger than every other box; else the first short paragraph (a diagram whose
    boxes share one size has no title box). Removes it from the bullets."""
    biggest = max(sh["size"] for sh in shapes)
    top = [sh for sh in shapes if sh["size"] == biggest]
    pick = top[0] if biggest and len(top) == 1 else None
    if pick is not None and len(" ".join(pick["paras"])) <= 100 and len(pick["paras"]) <= 4:
        shapes.remove(pick)
        return " ".join(pick["paras"])
    for sh in shapes:
        for i, t in enumerate(sh["paras"]):
            if len(t) <= 60:
                del sh["paras"][i]
                return t
    return ""


def read_pptx(path):
    slides = []
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        order = _slide_order(z, names)
        size, layouts = pptx_size(z), {}
        for name in order:
            root = ET.fromstring(z.read(name))
            title, bullets, text, tables, conns, branching, guessed, builds = pptx_slide(root)
            pics, hidden = _pictures(root, size)
            on_layout = pptx_layout_pictures(z, names, name, root, size, layouts)
            notes = []
            rels = "%s/_rels/%s.rels" % tuple(name.rsplit("/", 1))
            if rels in names:
                for rel in ET.fromstring(z.read(rels)).findall("r:Relationship", NS):
                    if rel.get("Type", "").endswith("/notesSlide"):
                        target = os.path.normpath(os.path.join("ppt/slides", rel.get("Target", "")))
                        target = target.replace(os.sep, "/")
                        if target in names:
                            nroot = ET.fromstring(z.read(target))
                            notes = [t for sp in nroot.iter(P + "sp")
                                     if _ph_type(sp) not in CHROME_PH
                                     for t in _paragraphs(sp) if t]
            segments = [title] + text + notes
            slides.append(make_slide(title, bullets, " ".join(notes), " ".join(text), pics,
                                     tables, conns, segments, branching, guessed, builds,
                                     hidden, on_layout))
            # a native chart part on the slide: the verb then says how that chart moves
            slides[-1]["_chart"] = any("chart" in (g.get("uri") or "")
                                       for g in root.iter(A + "graphicData"))
    return slides


def _slide_order(z, names):
    """Slides in presentation order (sldIdLst), falling back to slideN.xml numbering."""
    found = sorted((int(m.group(1)), n) for n in names
                   if (m := re.fullmatch(r"ppt/slides/slide(\d+)\.xml", n)))
    fallback = [n for _, n in found]
    try:
        pres = ET.fromstring(z.read("ppt/presentation.xml"))
        rels = ET.fromstring(z.read("ppt/_rels/presentation.xml.rels"))
    except KeyError:
        return fallback
    rid = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    target = {r.get("Id"): "ppt/" + r.get("Target", "").lstrip("/").replace("ppt/", "", 1)
              for r in rels.findall("r:Relationship", NS)}
    order = [target.get(s.get(rid)) for s in pres.iterfind("p:sldIdLst/p:sldId", NS)]
    order = [n for n in order if n in names]
    return order or fallback


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
    """'strong' for <section>/.slide, 'step' for .step (impress.js slides, but
    build steps inside a slide), 'weak' for other class*="slide"."""
    cls = n.classes
    if n.tag == "section" or "slide" in cls:
        return "strong"
    if "step" in cls:
        return "step"
    if any("slide" in c for c in cls):
        return "weak"
    return None


def leaf_containers(node):
    """Innermost slide containers; a strong container whose only nested
    containers are weak (e.g. .slide > .slide-content) or steps (a stair of
    .step divs inside one .slide) is itself the slide. A .step is a slide only
    when no <section>/.slide encloses it (impress.js); nested steps are sub-steps."""
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
    tables = []
    for t in (d for d in nodes if d.tag == "table" and not inside(d, "table")):
        rows = [[node_text(c) for c in tr.children if isinstance(c, Node) and c.tag in ("td", "th")]
                for tr in t.iter() if tr.tag == "tr"]
        tables.append([r for r in rows if any(collapse(c) for c in r)])
    return make_slide(title, bullets, notes, node_text(n), images, tables,
                      segments=[title] + bullets + [notes, node_text(n)],
                      builds=html_builds(n))


BUILD_CLASSES = {"fragment", "build", "build-item", "substep"}


def html_builds(n):
    """Click builds inside one slide container: reveal.js `.fragment` and
    `data-fragment-index`, `.build`/`.build-item`, impress.js `.substep`, and `.step`
    elements nested in the slide (a deck's own keyboard builds). Each element counts once."""
    count = 0
    notes = {id(x) for d in n.iter() if d.tag == "aside" and "notes" in d.classes for x in d.iter()}
    for d in n.iter():
        if d is n or id(d) in notes:
            continue
        cls = set(d.classes)
        if cls & BUILD_CLASSES or "data-fragment-index" in d.attrs or "step" in cls:
            count += 1
    return count


def read_html(path):
    tb = TreeBuilder()
    with open(path, encoding="utf-8", errors="replace") as f:
        tb.feed(f.read())
    tb.close()
    leaves = leaf_containers(tb.root)
    if not leaves:
        leaves = [next((d for d in tb.root.iter() if d.tag == "body"), tb.root)]
    return [html_slide(n) for n in leaves]


STAGE_VARS = (("--w", "--h"), ("--stage-w", "--stage-h"), ("--slide-width", "--slide-height"))
STAGE_VAR_SCOPES = {":root", "html", "body", ".deck"}
STAGE_RULE_NAMES = (".slide", "section", ".deck-stage", ".stage", ".step")


def _css_rules(css):
    """(selector list, declarations) for top-level rules; @media/@supports/@keyframes blocks are
    skipped (a print or narrow-screen rule is not the authored stage)."""
    css = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    out, depth, start, skip_from = [], 0, 0, None
    for m in re.finditer(r"[{}]", css):
        if m.group() == "{":
            prelude = css[start:m.start()].rsplit(";", 1)[-1].strip()  # after any @import ...;
            if depth == 0 and prelude.startswith("@"):
                skip_from = 0
            if skip_from is None:
                sel = prelude
            depth += 1
        else:
            depth -= 1
            if skip_from is None and depth == 0:
                out.append(([x.strip().lower() for x in sel.split(",")], css[start:m.start()]))
            if depth == 0:
                skip_from = None
        start = m.end()
    return out


def _decls(body):
    d = {}
    for part in body.split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            d[k.strip().lower()] = v.strip().lower().replace("!important", "").strip()
    return d


def _px(v, unit_required=True):
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(px)?", v or "")
    if not m or (unit_required and not m.group(2)):
        return None
    n = int(round(float(m.group(1))))
    return n if 200 <= n <= 10000 else None


def html_stage(raw):
    """Authored stage size of an HTML deck: ([W, H], source) or (None, "default").
    Order: CSS custom properties on :root/html/body/.deck, an explicit px width+height rule
    for the slide container, a numeric viewport meta width (16:9 assumed), reveal.js
    Reveal.initialize({width, height})."""
    css = " ".join(re.findall(r"<style[^>]*>(.*?)</style>", raw, re.S | re.I))
    rules = _css_rules(css)
    for wk, hk in STAGE_VARS:
        for sels, body in rules:
            if not STAGE_VAR_SCOPES.intersection(sels):
                continue
            d = _decls(body)
            wv, hv = _px(d.get(wk), False), _px(d.get(hk), False)
            if wv and hv:
                return [wv, hv], "css-vars"
    for name in STAGE_RULE_NAMES:
        for sels, body in rules:
            # the selector's last compound must be the container itself (e.g. `.slide`,
            # `section.slide`, `.reveal .slides section`), not a variant like `.slide.title`
            if not any(re.fullmatch(r"(?:.*[\s>])?[a-z]*%s" % re.escape(name), sel) for sel in sels):
                continue
            d = _decls(body)
            wv, hv = _px(d.get("width")), _px(d.get("height"))
            if wv and hv:
                return [wv, hv], "slide-rule"
    for m in re.finditer(r"<meta\b[^>]*>", raw, re.I):
        tag = m.group()
        if re.search(r"name\s*=\s*['\"]?viewport", tag, re.I):
            vw = re.search(r"content\s*=\s*['\"][^'\"]*\bwidth\s*=\s*(\d+)", tag, re.I)
            wv = _px(vw.group(1), False) if vw else None
            if wv:
                return [wv, int(round(wv * 9 / 16))], "viewport"
    for script in re.findall(r"<script[^>]*>(.*?)</script>", raw, re.S | re.I):
        for m in re.finditer(r"Reveal\.(?:initialize|configure)\s*\(\s*\{(.*?)\}\s*\)", script, re.S):
            wv = re.search(r"\bwidth['\"]?\s*:\s*(\d+)(?!\s*%)", m.group(1))
            hv = re.search(r"\bheight['\"]?\s*:\s*(\d+)(?!\s*%)", m.group(1))
            if wv or hv:  # reveal.js defaults to 960x700 for the one left out
                wn = _px(wv.group(1), False) if wv else 960
                hn = _px(hv.group(1), False) if hv else 700
                if wn and hn:
                    return [wn, hn], "reveal"
    return None, "default"


# ------------------------------------------------------------------ md ----
FENCE = re.compile(r"^\s*(`{3,}|~{3,})\s*([\w-]*)")
# remark slide properties: only recognised in the leading lines of a slide
REMARK_PROP = re.compile(r"^\s*(class|name|layout|template|count|exclude|seq|background-image"
                         r"|background-size|background-position|background-color|background-repeat"
                         r"|background)\s*:\s*(.*)$", re.I)
WRAPPER_OPEN = re.compile(r"(?<![\w\])`.\\])\.([A-Za-z][\w-]*)\[")
COMMENT = re.compile(r"<!--(.*?)-->", re.S)
HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
QUOTE = re.compile(r"^\s{0,3}>\s?(.*)$")


def strip_wrappers(s):
    """remark `.class[content]` -> `content`, nested and multi-line, brackets balanced."""
    pos = 0
    while True:
        m = WRAPPER_OPEN.search(s, pos)
        if not m:
            return s
        depth, j = 1, m.end()
        while j < len(s) and depth:
            depth += {"[": 1, "]": -1}.get(s[j], 0)
            j += 1
        if depth:  # unbalanced: keep it, look further
            pos = m.end()
            continue
        s = s[:m.start()] + s[m.end():j - 1] + s[j:]
        pos = m.start()  # rescan: the content may start with another wrapper


def md_inline_text(s):
    """Markdown inline markup -> plain text (images dropped, links to their text)."""
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"</?[A-Za-z][^>]*>", " ", s)
    s = re.sub(r"(\*\*\*|\*\*|___|__|~~)(?=\S)(.+?)(?<=\S)\1", r"\2", s)
    s = re.sub(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])", r"\1", s)
    s = re.sub(r"(?<![\w])_(?=\S)(.+?)(?<=\S)_(?![\w])", r"\1", s)
    s = re.sub(r"\\([\\`*_{}\[\]()#+\-.!>~|])", r"\1", s)
    return collapse(s)


def _tag_fences(lines):
    """Per line: None (prose), ('open', lang), 'code' or 'close'."""
    tags, fence = [], None
    for ln in lines:
        m = FENCE.match(ln)
        if fence is None and m:
            fence = m.group(1)[0] * 3
            tags.append(("open", m.group(2).lower()))
        elif fence and ln.strip().startswith(fence) and not ln.strip().strip(fence[0]):
            fence = None
            tags.append("close")
        else:
            tags.append(None if fence is None else "code")
    return tags


def _clean_runs(pairs, comments):
    """Strip remark wrappers and HTML comments from each run of prose lines, keeping the line
    count (a multi-line wrapper or comment leaves blank lines); comments are collected."""
    out, run = [], []

    def flush():
        if run:
            joined = "\n".join(run)
            comments.extend(COMMENT.findall(joined))
            joined = COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), joined)
            joined = strip_wrappers(joined)
            out.extend((ln, None) for ln in joined.split("\n"))
            run.clear()
    for ln, tag in pairs:
        if tag is None:
            run.append(ln)
        else:
            flush()
            out.append((ln, tag))
    flush()
    return out


def md_chunks(text):
    """Split a Markdown (or remark) deck into slides.

    Returns a list of {"body": [(line, tag)], "notes": [(line, tag)], "props": {}}; tag is None
    for prose, ("open", lang) / "code" / "close" for fenced lines. Slides are `---`-separated
    when the file has such rules, otherwise #/## sections. remark extras: leading `class:`,
    `layout:`, `background-image:` ... property lines go to props, `???` starts the speaker
    notes, a lone `--` (incremental reveal) is dropped, `.class[...]` wrappers are unwrapped,
    and `layout: true` (template) and `exclude: true` slides are skipped like remark does.
    HTML comments are moved to the notes.
    """
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":  # YAML front matter
        end = next((i for i in range(1, len(lines)) if lines[i].strip() in ("---", "...")), None)
        if end is not None:
            lines = lines[end + 1:]
    tags = _tag_fences(lines)
    use_rule = any(ln.strip() == "---" and t is None for ln, t in zip(lines, tags))
    raw, cur, incs, inc = [], [], [], 0
    for ln, t in zip(lines, tags):
        if t is None and use_rule and ln.strip() == "---":
            raw.append(cur)
            incs.append(inc)
            cur, inc = [], 0
            continue
        if t is None and not use_rule and re.match(r"#{1,2}\s", ln) and any(x.strip() for x, _ in cur):
            raw.append(cur)
            incs.append(inc)
            cur, inc = [], 0
        if t is None and ln.strip() == "--":
            inc += 1
            continue
        cur.append((ln, t))
    raw.append(cur)
    incs.append(inc)
    chunks = []
    for pairs, inc in zip(raw, incs):
        props, i = {}, 0
        while i < len(pairs):
            ln, t = pairs[i]
            m = REMARK_PROP.match(ln) if t is None else None
            if m:
                props[m.group(1).lower()] = m.group(2).strip()
            elif t is not None or ln.strip():
                break
            i += 1
        pairs = pairs[i:]
        if props.get("layout", "").lower() == "true" or props.get("exclude", "").lower() == "true":
            continue
        cut = next((k for k, (ln, t) in enumerate(pairs) if t is None and ln.strip() == "???"), None)
        body, notes = (pairs, []) if cut is None else (pairs[:cut], pairs[cut + 1:])
        comments = []
        body = _clean_runs(body, comments)
        notes = _clean_runs(notes, [])
        notes += [(c.strip(), None) for c in comments if c.strip()]
        if not any(ln.strip() for ln, _ in body) and not any(ln.strip() for ln, _ in notes):
            continue
        chunks.append({"body": body, "notes": notes, "props": props, "builds": inc})
    return chunks


def md_blocks(pairs):
    """Block structure of one slide body: a list of
    ("heading", level, text) | ("para", [lines]) | ("quote", [lines]) |
    ("list", [{"indent", "ordered", "lines": [(kind, text)]}]) with kind "t" or "q" |
    ("table", [[cells]]) | ("code", lang, [lines])."""
    blocks, i, n = [], 0, len(pairs)

    def kind(k):
        ln, t = pairs[k]
        if t is not None:
            return "code"
        if not ln.strip():
            return "blank"
        if HEADING.match(ln):
            return "heading"
        if TABLE_ROW.match(ln):
            return "table"
        if LIST_ITEM.match(ln):
            return "item"
        if QUOTE.match(ln):
            return "quote"
        return "text"
    while i < n:
        ln, t = pairs[i]
        k = kind(i)
        if k == "code":
            lang = t[1] if isinstance(t, tuple) else ""
            code, i = [], i + (1 if isinstance(t, tuple) else 0)
            while i < n and pairs[i][1] == "code":
                code.append(pairs[i][0])
                i += 1
            if i < n and pairs[i][1] == "close":
                i += 1
            blocks.append(("code", lang, code))
        elif k == "blank":
            i += 1
        elif k == "heading":
            m = HEADING.match(ln)
            blocks.append(("heading", len(m.group(1)), m.group(2)))
            i += 1
        elif k == "table":
            rows = []
            while i < n and kind(i) == "table":
                row = pairs[i][0]
                if not re.fullmatch(r"[\s|:-]+", row):
                    rows.append([c.strip() for c in row.strip().strip("|").split("|")])
                i += 1
            blocks.append(("table", rows))
        elif k == "quote":
            q = []
            while i < n and kind(i) in ("quote", "text"):
                q.append(QUOTE.match(pairs[i][0]).group(1) if kind(i) == "quote" else pairs[i][0].strip())
                i += 1
            blocks.append(("quote", q))
        elif k == "item":
            items = []
            while i < n:
                kk = kind(i)
                if kk == "item":
                    m = LIST_ITEM.match(pairs[i][0])
                    items.append({"indent": len(m.group(1).expandtabs(4)),
                                  "ordered": m.group(2)[0].isdigit(),
                                  "start": int(re.match(r"\d*", m.group(2)).group(0) or 1),
                                  "lines": [("t", m.group(3))]})
                    i += 1
                elif kk in ("text", "quote"):  # lazy or indented continuation of the item
                    ln2 = pairs[i][0]
                    q = QUOTE.match(ln2.strip()) if kk == "quote" or ln2.strip().startswith(">") else None
                    items[-1]["lines"].append(("q", q.group(1)) if q else ("t", ln2.strip()))
                    i += 1
                elif kk == "blank":
                    j = i
                    while j < n and kind(j) == "blank":
                        j += 1
                    if j < n and (kind(j) == "item" or (kind(j) in ("text", "quote")
                                                        and re.match(r"\s{2,}\S", pairs[j][0]))):
                        i = j
                    else:
                        break
                else:
                    break
            blocks.append(("list", items))
        else:
            para = []
            while i < n and kind(i) == "text":
                para.append(pairs[i][0])
                i += 1
            blocks.append(("para", para))
    return blocks


def read_md(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return [md_slide(c) for c in md_chunks(f.read())]


def md_slide(chunk):
    blocks = md_blocks(chunk["body"])
    title, bullets, text, tables, mermaid = "", [], [], [], []
    for b in blocks:
        if b[0] == "heading":
            t = md_inline_text(b[2])
            if not title and t:
                title = t
            else:
                bullets.append(t)
        elif b[0] == "para" or b[0] == "quote":
            bullets.append(md_inline_text(" ".join(b[1])))
        elif b[0] == "list":
            bullets.extend(md_inline_text(" ".join(x for _, x in it["lines"])) for it in b[1])
        elif b[0] == "table":
            tables.append([[md_inline_text(c) for c in r] for r in b[1]])
            text.extend(md_inline_text(c) for r in b[1] for c in r)
        elif b[0] == "code":
            if b[1] == "mermaid":
                mermaid.append("\n".join(b[2]))
            else:
                text.extend(b[2])
    bullets = [x for x in bullets if x]
    notes_blocks = md_blocks(chunk["notes"])
    notes = []
    for b in notes_blocks:
        if b[0] == "heading":
            notes.append(b[2])
        elif b[0] in ("para", "quote"):
            notes.append(" ".join(b[1]))
        elif b[0] == "list":
            notes.extend(" ".join(x for _, x in it["lines"]) for it in b[1])
        elif b[0] == "table":
            notes.extend(" ".join(r) for r in b[1])
        elif b[0] == "code":
            notes.extend(b[2])
    notes = md_inline_text(" ".join(notes))
    raw_body = [ln for ln, t in chunk["body"] if t is None]
    images = sum(len(re.findall(r"!\[[^\]]*\]\([^)]*\)", ln)) + len(re.findall(r"<img\b", ln, re.I))
                 for ln in raw_body)
    visible = " ".join([title] + bullets + text)
    slide = make_slide(title, bullets, notes, visible, images, tables,
                       segments=[title] + raw_body + text + [notes], builds=chunk.get("builds", 0))
    if mermaid:
        slide["mermaid"] = mermaid
    return slide


# ----------------------------------------------------------- heuristics ----
# a word character that is not CJK: Chinese/Japanese text has no spaces, so a cue word next to a
# CJK character still stands on its own (Hangul keeps word status; Korean separates words)
WORD = r"[^\W぀-ヿ㐀-䶿一-鿿豈-﫿]"


def w(pattern, flags=0, cjk=None):
    """Whole-word cue; `cjk` adds Chinese/Japanese alternatives matched without word boundaries."""
    rx = r"(?<!%s|-)(?:%s)(?!%s|-)" % (WORD, pattern, WORD)
    if cjk:
        rx += "|(?:%s)" % cjk
    return re.compile(rx, flags)


def c(pattern):
    """CJK-only cue (no word boundaries)."""
    return re.compile(pattern)


CN_NUM = "十[一二]|[一二三四五六七八九十]|1[0-2]|0?[1-9]"
CJK_MONTH = r"(?<![\d一二三四五六七八九十])(?:%s)月" % CN_NUM
CJK_CHAR = r"[぀-ヿ㐀-䶿一-鿿]"
YEAR = re.compile(r"(?<![\d.,$€£])(?:19|20)\d{2}(?![\d%]|,\d|\s?(?:words?|characters?|chars|people|users"
                  r"|scientists|pages?|km|kg|mb|gb|ms|px|euros?|eur|usd|dollars?|€|\$|人|字|页|頁|名|位"
                  r"|公里|千米|公斤|千克|元|円|美元|欧元))")
RULES = {  # archetype -> [(cue label, regex)]; regexes run on the lowercased text unless cased
    "pipeline": [("arrows", re.compile(r"->|→|=>|⇒|⟶")),
                 ("'then'", w("then", cjk="然后|接着|随后|最后|次に")),
                 ("numbered steps", re.compile(r"(?:^|\s)(?:\d+[.)]|step\s*\d+)\s"
                                               r"|(?:^|\s)\d+[.)、．](?=" + CJK_CHAR + ")"
                                               r"|第[一二三四五六七八九十\d]+步", re.M)),
                 ("'step'", w(r"steps?|stages?|phases?", cjk="流程|步骤|過程|过程|工序|手順|工程"))],
    "graph": [("dependency verbs", w(r"depends on|depend on|requires?|calls|uses|imports",
                                     cjk="依赖|依存|调用|呼び出|连接|接続")),
              ("structure words", c("关系|架构|组件|構成|コンポーネント")),
              ("decision wording", re.compile(r"(?<![\w-])if\b[^.;:?!]{0,80}?\b(?:positive|negative|yes|no"
                                              r"|true|false|fails?|passes?|succeeds?|accepted|rejected)\b")),
              ("'either'", w("either")), ("'OR'", ("cased", w("OR")))],
    "timeline": [("years", YEAR), ("quarters", w("q[1-4]")),
                 ("dates", re.compile(r"\d{4}-\d{2}-\d{2}|(?<![\w])(?:jan|feb|mar|apr|may|jun|jul"
                                      r"|aug|sep|oct|nov|dec)[a-z]*\.? \d{1,2}(?!\d)"
                                      r"|(?:19|20)\d{2}年\d{1,2}月|(?<!\d)\d{1,2}月\d{1,2}[日号]")),
                 ("months", w(r"january|february|march|april|june|july|august|september|october|november"
                              r"|december|jan|feb|mar|apr|jun|jul|aug|sept?|oct|nov|dec", cjk=CJK_MONTH)),
                 ("'roadmap'", w("roadmaps?", cjk="路线图|ロードマップ")),
                 ("'milestone'", w("milestones?", cjk="里程碑|マイルストーン")),
                 ("'timeline'", w("timelines?|chronology", cjk="时间线|时间轴|時間軸|年表|历程|日程")),
                 ("'phase'", c("阶段|段階"))],
    "compare": [("'vs'", w(r"vs\.?|versus", cjk=r"对比|比较|比較|优缺点|(?<=\s)対(?=\s)|(?<=\d)対(?=\d)")),
                ("before/after", w("before|after", cjk="之前|之后|以前|以后|前後")),
                ("old/new", w("old|new"))],
    "layers": [("'layer'", w("layers?|layered", cjk="分层|层(?!面)|層|レイヤー")),
               ("'tier'", w("tiers?")), ("'stack'", w("stacks?", cjk="架构")),
               ("'on top of'", w("on top of"))],
    "states": [("'state'", w("(?<!united )states?", cjk="状态|状態")), ("'mode'", w("modes?")),
               ("'transition'", w("transitions?", cjk="切换|转换|遷移")), ("'phase'", c("阶段"))],
    # chart has no English keyword (numbers with units drive it below); CJK trend words do count
    "chart": [("trend words", c("数据|增长|下降|百分比|趋势|占比|推移|割合"))],
}
UNIT_NUM = re.compile(r"(?<![.])(?<!" + WORD + r")\d+(?:[.,]\d+)?\s?(?:%|ms|s|sec|min|h|hrs?|days?|gb|mb|kb|tb"
                      r"|k|m|bn|x|users|req/s|rps|€|\$|eur|usd|fps|万|亿|億|元|円|倍|吨|噸|公斤|千克|千米|公里)(?![a-z])"
                      r"|[$€£]\s?\d+(?:[.,]\d+)?")
# a citation segment is dropped before cue counting (its years are not a timeline)
CITATION = re.compile(r"\bdoi\b|\bet al\b|\[online\]|\bvol\.\s?\d|\bpp\.\s?\d|\bisbn\b|^\s*(?:source|sources"
                      r"|reference|references|credit|image|photo)s?\s*:|\d+\s*[–-]\s*\d+\s*\((?:19|20)\d{2}\)"
                      r"|^\s*\(\d+\)\s*[A-Z]{2,}", re.I | re.M)
AUTHOR_YEAR = re.compile(r"\b[A-Z][A-Za-z'’-]+,\s+[A-Z][\w.'’ -]{0,30},?\s*\(?(?:19|20)\d{2}[a-z]?\)?[.,;)]"
                         r"|\b[A-Z][a-z]+(?: et al\.?| and [A-Z][a-z]+)?,? \((?:19|20)\d{2}[a-z]?\)"
                         r"|\([A-Z][^()]{1,60},\s*(?:19|20)\d{2}[a-z]?\)")
CITE_SPAN = re.compile(r"\S*(?:https?://|www\.)\S*|\b(?:accessed|retrieved|viewed)\b:?(?:\s+on)?\s*"
                       r"(?:[\w,]+\s+){0,3}(?:19|20)\d{2}", re.I)
SENTENCE = re.compile(r"(?<=[.;!?])\s+(?=[A-Z(\[])|(?<=[。！？；])")


def decite(segments):
    """Drop citation-like sentences and URL/'Accessed <date>' spans."""
    out = []
    for seg in segments:
        for sent in SENTENCE.split(seg):
            if CITATION.search(sent):
                continue
            out.append(CITE_SPAN.sub(" ", AUTHOR_YEAR.sub(" ", sent)))
    return " ".join(out)


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


def _archetype(slide):
    """(archetype, confidence, reason, cue labels) from keyword and shape cues."""
    for body in slide.get("mermaid", []):
        hit = mermaid_archetype(body)
        if hit:
            return hit[0], 0.9, hit[1], []
    segments = slide.get("_segments") or []
    if not segments:  # text already contains title and bullets; adding them again would double-count
        segments = [slide["text"], slide["notes"]]
        if slide["title"] not in slide["text"]:
            segments.insert(0, slide["title"])
    cased = decite(segments)
    blob = cased.lower()
    found = {}  # archetype -> [(label, count, weight)]
    for arch, rules in RULES.items():
        for label, rx in rules:
            hits = rx[1].findall(cased) if isinstance(rx, tuple) else rx.findall(blob)
            if hits:
                found.setdefault(arch, []).append((label, len(hits), 1, hits))
    # month names count only as a sequence of 3+; a lone 'years' cue needs 3+ distinct years in
    # ascending order, else it is just a date mention
    tl = [c for c in found.get("timeline", []) if c[0] != "months" or len(set(c[3])) >= 3]
    if [c[0] for c in tl] == ["years"]:
        seen = list(dict.fromkeys(tl[0][3]))
        if len(seen) < 3 or seen != sorted(seen):
            tl = []
    if tl:
        found["timeline"] = tl
    else:
        found.pop("timeline", None)
    # a lone 'either' or 'OR' is just wording, not a decision
    if [c[0] for c in found.get("graph", [])] in (["'either'"], ["'OR'"]):
        del found["graph"]
    # shape cues: 4+ connectors weigh as two keyword cues
    conns = slide.get("connectors", 0)
    if conns >= 2:
        arch = "graph" if slide.get("_branching") and conns >= 3 else "pipeline"
        label = "%d connectors/arrows%s" % (conns, " (branching)" if arch == "graph" else "")
        found.setdefault(arch, []).append((label, conns, 2 if conns >= 4 else 1, None))
    for t in slide.get("tables", []):
        ncols = max(len(r) for r in t)
        if ncols == 2 and len(t) >= 2:
            found.setdefault("compare", []).append(("2-column table", len(t), 2, None))
    best = (0, 0, None, [])
    for arch, cues in found.items():
        score = (sum(c[2] for c in cues), sum(c[1] for c in cues))
        if score > best[:2]:
            best = (*score, arch, [c[0] for c in cues])
    units = len(UNIT_NUM.findall(blob))
    if units >= 3 and best[0] <= 2:
        best = (2, units, "chart", ["%d numbers with units" % units])
    if best[2] is None:
        return None, 0.0, "no structural cues", []
    conf = min(0.9, 0.3 + 0.15 * (best[0] - 1) + (0.15 if best[1] >= 4 else 0))
    return best[2], round(conf, 2), "cues: " + ", ".join(best[3]), best[3]


# ------------------------------------------------------------ idea cues ----
# Evidence for the picture idea: what the slide says beyond the order of its items. Precision over
# recall; a cue names the source words it matched so the agent can check them. Numbered formatting
# alone is never a cue.
IDEA_RULES = [  # (cue, regex on the cased text, re.I)
    ("returns", w(r"cycles?|cyclical|cyclic|loops?|looping|repeats|repeated|repeating|repeat until"
                  r"|repeat from|(?:starts?|begins?|round|all over|over) again|again and again|back to|returns? to|re-?enters?|re-?entering|re-?entry"
                  r"|feeds? back|fed back|feedback loop|iterate[sd]?|iterating|iterations?|iterative"
                  r"|recycled?|recycling|starts? over|over and over", re.I,
                  cjk="循环|周而复始|反复|重复|再次|回到|サイクル|循環|繰り返")),
    ("trade-off", w(r"versus|vs\.?|trade-?offs?|at the cost of|at the expense of|on the other hand"
                    r"|tension between|(?:but|while) (?:it )?(?:raises|lowers|increases|reduces|costs"
                    r"|slows|adds|loses|cuts)", re.I, cjk="权衡|取舍|代价|トレードオフ|一方で")),
    ("contains", w(r"inside|within(?! (?:\d|a few|the next|hours?|days?|weeks?|minutes?|seconds?"
                   r"|months?|years?|budget|reach|range|limits?|scope))|(?<!as )part of|consists? of"
                   r"|made up of|composed of|nested|layers? of|contains", re.I,
                   cjk="包含|组成|内部|の中に|で構成")),
    ("split-merge", w(r"splits?(?: up)? into|split in two|branch(?:es|ed)? (?:into|off|out)|branching"
                      r"|in parallel|run parallel|merges?|merging|merged|combines?|converge[sd]?"
                      r"|converging|fork(?:s|ed)? into|diverge[sd]?|diverging", re.I,
                      cjk="分为|分成|分支|并行|合并|汇合|分岐|並列|合流")),
    ("handover", w(r"hand(?:s|ed)? (?:it )?over|hand-?offs?|handovers?|hand-over|transfer(?:s|red)? to"
                   r"|pass(?:es|ed)? (?:it )?(?:on )?to|across the (?:boundary|border|membrane|wall)"
                   r"|cross(?:es|ed)? (?:the )?(?:boundary|border|membrane)", re.I,
                   cjk="交接|移交|转交|传给|引き継|受け渡")),
    ("share-of-whole", w(r"(?<!first )(?<!most )(?<!best )(?<!worst )(?<!least )of all(?! the time)"
                         r"|share of|market share|proportion of|fraction of|percent of|out of every",
                         re.I, cjk="占比|份额|比例|割合|シェア")),
]
BEFORE_AFTER = [w(r"before\b.{1,120}?\bafter", re.I | re.S, cjk="之前.{0,40}?之后|以前.{0,40}?(?:现在|現在)"),
                w(r"(?:was|were|used to)\b.{1,60}?\b(?:now|today)", re.I | re.S)]
FROM_TO = re.compile(r"\bfrom\s+([$€£]?\d[\d,.]*\s?%?)\S*\s+to\s+([$€£]?\d[\d,.]*\s?%?)", re.I)
QTY_UNITS = (r"%|ms|sec|s|min|hrs?|h|days?|weeks?|months?|years?|gb|mb|kb|tb|bn|k|m|kg|mg|g|km|cm|mm"
             r"|ml|l|°c|°f|ppm|t|x|万|亿|億|元|円|人|名|个|個")
QTY = re.compile(r"(?<![\w.,\-–/])([$€£])?\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(?![\d,]\d)"
                 r"(?!\s?[–-]\s?\d)\s?(" + QTY_UNITS + r")?(?![a-z\d])", re.I)


def quantities(text, nxt=1):
    """Numbers in reading order as (item, value, unit, source). An item index (1, 2, 3 ... in
    sequence, counted on from `nxt`) is not a quantity but starts the next item; years and ranges
    are skipped. Returns the list and the next expected index."""
    out = []
    for m in QTY.finditer(text):
        cur, digits, frac, unit = m.groups()
        if re.search(r"\d\s?[–-]\s?$", text[:m.start()]):
            continue  # the end of a range
        bare = not (cur or unit or frac or "," in digits)
        val = float(digits.replace(",", "") + ("." + frac if frac else ""))
        if bare and val == nxt:  # an item index: 1, 2, 3 ...
            nxt += 1
            continue
        if bare and len(digits) == 4 and 1000 <= val <= 2099:
            continue  # a year
        out.append((nxt - 1, val, (cur or unit or "").lower(), m.group(0).strip()))
    return out, nxt


def idea_cues(slide):
    """[{"cue": name, "evidence": matched source words}] for the picture-idea step."""
    segments = slide.get("_segments") or [slide["title"], slide["text"], slide["notes"]]
    cased = decite(segments)
    cues = []

    def add(cue, words):
        words = list(dict.fromkeys(collapse(x) for x in words if collapse(x)))
        if words:
            cues.append({"cue": cue, "evidence": " / ".join(words[:4])})

    # quantities in item order (bullets when there are 3+, else items split at their indices):
    # per unit, the first number of each item
    if len(slide["bullets"]) >= 3:
        qs, nxt = [], 1
        for i, b in enumerate(slide["bullets"]):
            found, nxt = quantities(decite([b]), nxt)
            qs += [(i,) + q[1:] for q in found]
    else:
        qs = quantities(decite([slide["text"]]))[0]
        if all(q[0] == 0 for q in qs):  # no item indices: every number is its own item
            qs = [(i,) + q[1:] for i, q in enumerate(qs)]
    groups = {}
    for item, v, unit, src in qs:
        g = groups.setdefault(unit, {})
        g.setdefault(item, (v, src))
    for unit, per_item in groups.items():
        vals = [per_item[k] for k in sorted(per_item)]
        if len(vals) < 3:
            continue
        nums = [v for v, _ in vals]
        pairs = list(zip(nums, nums[1:]))
        if all(a > b for a, b in pairs):
            add("falling-quantities", [s for _, s in vals])
        elif all(a < b for a, b in pairs):
            add("rising-quantities", [s for _, s in vals])
    rx_hits = {cue: [m.group(0) for m in rx.finditer(cased)] for cue, rx in IDEA_RULES}
    for cue in ("returns", "trade-off", "contains", "split-merge", "handover"):
        add(cue, rx_hits[cue])
    ba = [m.group(0) for rx in BEFORE_AFTER for m in rx.finditer(cased)]
    ba += [m.group(0) for m in FROM_TO.finditer(cased)
           if not all(re.fullmatch(r"(?:19|20)\d{2}", g.strip()) for g in m.groups())]
    add("before-after", [b if len(b) <= 40 else b[:18] + " … " + b[-18:] for b in ba])
    pct = [(v, s) for _, v, unit, s in qs if unit == "%"]
    total = sum(v for v, _ in pct)
    share = rx_hits["share-of-whole"]
    if (len(pct) >= 3 and 95 <= total <= 105) or (len(pct) == 2 and 98 <= total <= 102):
        share = [" + ".join(s for _, s in pct) + " ≈ 100%"] + share
    add("share-of-whole", share)
    return cues


# ---------------------------------------------------------- motion verbs ----
# The main motion a fragment could make, read from the grammar of the slide's claim
# (references/motion-verbs.md section 1). Like idea_cues: precision over recall, and each verb names
# the source words it matched. Order (numbering, arrows, connectors, 'then', 'step') is never a verb
# cue; a slide that states only order gets `reveal`. English, German and Chinese/Japanese cue words.
VERBS = ("grow", "count", "accumulate", "thin", "race", "split", "merge", "sort", "stack", "nest",
         "transform", "wipe", "switch", "balance", "drive", "zoom", "open", "travel", "trace", "cycle",
         "reveal")
VERB_RULES = {  # verb -> regex on the cased text (re.I); idea cues and quantities are added in verb_cues
    "cycle": w(r"kreislauf|zyklus|zyklisch|wiederholt sich|beginnt (?:von vorne?|erneut|wieder)|von vorne"
               r"|kehrt (?:\w+ )?zurück|zurück zu[mr]?|rückkopplung|schleife", re.I),
    "thin": w(r"fewer|drop(?:s|ped)? out|drop-?outs?|attrition|funnel|narrows?|narrowing|shrinks?|shrank"
              r"|weeds? out|filtered out|whittled|left over|remain(?:s|ing)?|surviv(?:e|es|ed|ing|ors?)"
              r"|decays?|decayed|erod(?:es|ed|ing)|erosion|depreciat\w*|weniger|übrig|schwund|abbrecher"
              r"|schrumpf\w*|abnahme|zerfall\w*|trichter", re.I, cjk="漏斗|流失|衰减|递减|残る|減って"),
    "sort": w(r"of every \d+|out of every|ranked|rankings?|jede[rs]? (?:zweite|dritte|vierte|fünfte)"
              r"|von (?:je )?100|rangliste", re.I, cjk="排名|ランキング"),
    "sort-share": w(r"majority|minority|mehrheit|minderheit", re.I, cjk="多数|少数|過半数"),  # needs a %
    "race": w(r"faster than|slower than|cheaper than|costlier than|longer than|shorter than|twice as"
              r"|\d+(?:\.\d+)?\s?(?:x|times) (?:faster|slower|more|less|cheaper|longer|shorter)"
              r"|outpaces?|overtakes?|schneller als|langsamer als|billiger als|doppelt so", re.I,
              cjk=r"比.{1,8}?(?:快|慢|高|低|多|少)|倍速"),
    "balance": w(r"pros and cons|for and against|supply and demand|outweighs?|equilibrium|in balance"
                 r"|weigh(?:s|ed)? against|abwägung|zielkonflikt|auf kosten|einerseits|andererseits"
                 r"|im gegensatz zu|vor- und nachteile|pro und contra|gegenüber", re.I,
                 cjk="平衡|天秤|利弊|均衡"),
    "switch": w(r"threshold|tipping point|cross(?:es|ed)? the (?:line|threshold|limit)|once (?:it|the \w+)"
                r" (?:reaches|exceeds|passes|hits)|when (?:it|the \w+) (?:reaches|exceeds|hits)"
                r"|turns? (?:red|green|amber|yellow)|status chang\w+|switch(?:es|ed)? (?:to|from|on|off)"
                r"|becomes? (?:valid|binding|law|legal|active|eligible|ripe|void)|schwellenwert|schwelle"
                r"|kipppunkt|umschalt\w*|wechselt (?:zu|auf|in)|tritt in kraft", re.I,
                cjk="阈值|临界|閾値|切り替|生效"),
    "transform": w(r"became|becomes|become|turn(?:s|ed)? into|transform(?:s|ed)? into|chang(?:es|ed) into"
                   r"|evolv(?:es|ed) into|develop(?:s|ed) into|matur(?:es|ed) into|redefined|renamed"
                   r"|metamorphos[ie]s|wurde zu[mr]?|wird zu[mr]?|verwandel(?:t|te|n)|umgewandelt"
                   r"|entwickelt sich zu", re.I, cjk="变成|变为|转变为|演变为|に変わ|になった|へと変"),
    "wipe": w(r"replac(?:es|ed|ing)|instead of|then and now|no longer|ersetzt|anstelle|stattdessen"
              r"|früher\b.{1,60}?\bheute", re.I | re.S, cjk="取代|替换|代替|置き換|代わりに"),
    "split": w(r"made (?:up )?of|consists? of|composed of|breaks? down into|broken down into|break-?down"
               r"|splits?(?: up)? into|split in two|divided into|divides into|of which|besteht aus"
               r"|bestehen aus|setzt sich (?:\w+ )?zusammen aus|aufgeteilt|teilt sich|zerfällt in"
               r"|davon entfallen", re.I, cjk="分为|分成|由.{0,12}?组成|构成|で構成|に分かれ|内訳"),
    "merge": w(r"joins (?:forces|with|together)|joined (?:with|by|forces)|join forces|combines|combining"
               r"|combined (?:with|into)|combine (?:with|into)|merges?|merged"
               r"|merging|pooled|pools? (?:their|its|the)|together they|converge[sd]?|converging"
               r"|consolidat\w*|unite[sd]|fuse[sd]|flow together|zusammengeführt|zusammenlegen"
               r"|zusammengelegt|vereint|vereinigt|fusion\w*|bündel\w*|fließen zusammen", re.I,
               cjk="合并|汇合|汇聚|合流|统合|統合|結合|集約"),
    "nest": w(r"inside|within(?! (?:\d|a few|the next|hours?|days?|weeks?|minutes?|seconds?|months?|years?"
              r"|budget|reach|range|limits?))|(?<!as )part of|nested|contains|subsets?|jurisdiction"
              r"|falls under|belongs to|innerhalb|enthält|enthalten|teil (?:von|des|der)|gehört zu"
              r"|umfasst|verschachtelt", re.I, cjk="包含|内部|の中に|に含まれ|属于"),
    "zoom": w(r"zoom(?:s|ed|ing)? in|close-?up|up close|closer look|look closer|under the microscope"
              r"|magnified|down to the level of|underneath|beneath|below the surface|im detail"
              r"|nahaufnahme|vergrößert|unter dem mikroskop", re.I, cjk="放大|特写|显微|拡大|顕微"),
    "open": w(r"anatomy|cut-?away|cross-?sections?|exploded view|how the parts fit|inner workings"
              r"|what is inside|under the hood|layers? of|querschnitt|schnittbild|innenleben"
              r"|explosionszeichnung", re.I, cjk="剖面|解剖|断面|内部構造"),
    "stack": w(r"on top of|builds? on|built on|rests? on|foundations?|prerequisites?|pyramid|strata|stratum"
               r"|bottom-?up|maturity|each level|tiers?|layers?|layered|baut auf|aufbauend|grundlage"
               r"|fundament|pyramide|stufen|schichten|ebenen", re.I,
               cjk="基础|层次|分层|層|基盤|ピラミッド"),
    "accumulate": w(r"adds? up(?: to)?|accumulat\w*|piles? up|builds? up|saved up|in total|a total of"
                    r"|cumulative|sums? (?:up )?to|summier\w*|insgesamt|angespart|anhäuf\w*"
                    r"|sammelt sich|kumuliert", re.I,
                    cjk="累计|累积|积累|积少成多|合計|累積|貯ま"),
    "grow": w(r"ris(?:es|ing)|rose|grows?|grew|growth|increas(?:es|ed|ing)|doubled?|tripled?|climb(?:s|ed)?"
              r"|soar(?:s|ed)?|fell|falls|falling|declin(?:es|ed|ing)|drops|dropped|cut (?:by|to)"
              r"|(?:up|down) (?:by|from|to) [$€£]?\d|more than|less than|steigt|stieg|gestiegen|wächst"
              r"|wuchs|gewachsen|zunahme|verdoppelt|sinkt|sank|gesunken|fällt|gefallen|rückgang"
              r"|mehr als|weniger als", re.I, cjk="增长|下降|上升|增加|减少|翻倍|増加|減少|上昇|低下"),
    # a named thing changes place between named places; 'hand X to' and plain arrows are not enough
    "travel": w(r"sent (?:back |on )?to|sends? (?:it |them |the \w+ )?to|shipped|ships? (?:to|from)"
                r"|handed (?:over )?to|hands? (?:it |them )?over to|delivered|delivers? (?:to|it|the)"
                r"|deliver(?:y|ies) to|arriv(?:es|ed|ing)? (?:at|in)|travel(?:s|led|ed)? (?:to|from"
                r"|through|along)|carried (?:to|from)|carries (?:it |them )?to|transported|routed"
                r"|routes?|itinerary|journey|migrat(?:es|ed|ing|ion)|dispatched|forwarded to"
                r"|referred to(?! as)|transferred to|(?:is|are) taken to|flows? (?:from|to|into)"
                r"|geschickt|gesendet|versandt|verschickt|geliefert|ausgeliefert|übergeben an|übergibt"
                r"|kommt (?:\w+ )?an|angekommen|gelangt|transportiert|wandert|weitergeleitet"
                r"|überwiesen|zugestellt", re.I,
                cjk="发送|发往|送到|送往|运往|运送|送达|交给|传给|移交|转交|到达|抵达|届け|送ら|運ば|到着|配送|輸送"),
    "drive": w(r"because|drives?|driven by|causes?|caused by|leads? to|led to|results? in|triggers?"
               r"|the more\b.{1,60}?\bthe (?:more|less|fewer|higher|lower)|levers?|valves?|gears?"
               r"|pump(?:s|ed)?|pulleys?|pistons?|weil|dadurch|führ(?:t|en) zu|verursach\w*|treibt"
               r"|angetrieben|auslöser|je (?:mehr|höher|größer)\b.{1,60}?\bdesto", re.I | re.S,
               cjk="因为|导致|驱动|引起|促使|越.{1,20}?越|ため|により|引き起こ"),
    "trace": w(r"trends?|trajector(?:y|ies)|curves?|over time|over the (?:past|last|next) \d+"
               r"|since (?:19|20)\d{2}|orbits?|coastline|verlauf|kurve|im zeitverlauf"
               r"|seit (?:19|20)\d{2}", re.I, cjk="趋势|轨迹|曲线|推移|軌跡|曲線"),
}
# proper-noun places: "from Rotterdam to Lyon", "von Hamburg nach Wien"
ROUTE = re.compile(r"\bfrom (?:the )?[A-ZÄÖÜ][\w-]+(?: [A-ZÄÖÜ][\w-]+)? (?:to|into) (?:the )?[A-ZÄÖÜ][\w-]+"
                   r"|\bvon (?:der |dem )?[A-ZÄÖÜ][\w-]+ (?:nach|zu[mr]?) [A-ZÄÖÜ][\w-]+")
FIGURE_WORDS = w(r"charts?|graphs?|plots?|figures?|diagrams?|histograms?|bars?|axis|axes|abbildung|diagramm"
                 r"|grafik", re.I, cjk="图表|统计图|グラフ|図表")
TIME_AXIS = w(r"q[1-4]|(?:19|20)\d{2}|january|february|march|april|june|july|august|september|october"
              r"|november|december|monthly|yearly|annual|per year|per month|jahr|monat", re.I,
              cjk=r"\d{4}年|" + CJK_MONTH)
# main-verb priority when several fire: shape claims before mechanisms, quantities before routes,
# `count` (one headline number) last
VERB_ORDER = ("cycle", "thin", "sort", "race", "balance", "switch", "transform", "wipe", "split", "merge",
              "nest", "zoom", "open", "stack", "accumulate", "grow", "travel", "drive", "trace", "count")
# verbs that outweigh row cues (connectors, numbering) and the family their form is built with
STRONG_VERBS = {"cycle": "states", "thin": "pipeline", "sort": "chart", "race": "compare",
                "balance": "compare", "switch": "states", "transform": "states", "wipe": "compare",
                "split": "graph", "merge": "graph", "nest": "layers", "zoom": "layers", "open": "layers",
                "stack": "layers", "accumulate": "chart", "grow": "chart", "count": "chart"}
FAMILY_VERB = {"chart": "grow", "timeline": "trace", "states": "switch", "compare": "wipe",
               "layers": "stack", "graph": "reveal", "pipeline": "reveal"}
ORDER_CUES = ("arrows", "'then'", "numbered steps", "'step'")


def verb_cues(slide, ideas=None):
    """[{"cue": verb, "evidence": matched source words}] in main-verb priority order; [] = order only."""
    segments = slide.get("_segments") or [slide["title"], slide["text"], slide["notes"]]
    cased = decite(segments)
    ideas = {c["cue"]: c["evidence"] for c in (ideas if ideas is not None else idea_cues(slide))}
    nq = len(quantities(cased)[0])
    found = {}

    def add(verb, words):
        words = [collapse(x) for x in words if collapse(x)]
        if words:
            found.setdefault(verb, []).extend(words)

    hits = {v: [m.group(0) for m in rx.finditer(cased)] for v, rx in VERB_RULES.items()}
    add("cycle", ([ideas["returns"]] if "returns" in ideas else []) + hits["cycle"])
    whole = "≈ 100%" in ideas.get("share-of-whole", "")  # falling shares of one whole are a sort
    add("thin", [ideas["falling-quantities"]] if "falling-quantities" in ideas and not whole else [])
    if nq >= 2 or "falling-quantities" in ideas:  # 'fewer', 'remain' need stated counts
        add("thin", hits["thin"])
    add("sort", ([ideas["share-of-whole"]] if "share-of-whole" in ideas else []) + hits["sort"])
    if any(q[2] == "%" for q in quantities(cased)[0]):
        add("sort", hits["sort-share"])
    if nq >= 1:
        add("race", hits["race"])
    if "trade-off" in ideas and nq >= 2:  # two quantities under one clock: the gap is the point
        add("race", [ideas["trade-off"]])
    else:
        add("balance", [ideas["trade-off"]] if "trade-off" in ideas else [])
    add("balance", hits["balance"])
    for v in ("switch", "transform", "wipe"):
        add(v, hits[v])
    if "before-after" in ideas:
        add("grow" if FROM_TO.search(cased) and not any(rx.search(cased) for rx in BEFORE_AFTER)
            else "wipe",
            [ideas["before-after"]])
    for v in ("split", "merge", "nest", "zoom", "open", "stack"):
        add(v, hits[v])
    if nq >= 1:
        add("accumulate", hits["accumulate"])
        add("grow", hits["grow"])
    add("grow", [ideas["rising-quantities"]] if "rising-quantities" in ideas else [])
    add("travel", hits["travel"] + [m.group(0) for m in ROUTE.finditer(cased)]
        + ([ideas["handover"]] if "handover" in ideas else []))
    add("drive", hits["drive"])
    add("trace", hits["trace"])
    if not found:
        heads = [q[3] for q in quantities(cased)[0] if q[2] or q[1] >= 1000]
        if 1 <= nq <= 2 and heads:
            add("count", heads[:1])
    out = []
    for v in VERB_ORDER:
        if v in found:
            words = list(dict.fromkeys(found[v]))
            out.append({"cue": v, "evidence": " / ".join(words[:4])})
    return out


def figure_kind(slide, arch):
    """'chart' when the source already shows a chart (mermaid xychart, a pptx chart part, a picture
    the text calls a chart), 'figure' for another mermaid diagram, else None."""
    if any((mermaid_archetype(b) or ("", ""))[0] == "chart" for b in slide.get("mermaid", [])):
        return "chart"
    if slide.get("mermaid"):
        return "figure"
    if slide.get("_chart"):
        return "chart"
    text = slide["title"] + " " + slide["text"]
    if slide.get("image_count") and (FIGURE_WORDS.search(text) or VERB_RULES["grow"].search(text)
                                     or VERB_RULES["trace"].search(text)):
        return "chart"  # a picture beside 'chart', 'rose', 'fell', 'trend' is most likely a chart
    return None


def suggest(slide):
    """Archetype, confidence, reason, idea cues and motion verb for one slide, as outline fields."""
    arch, conf, reason, labels = _archetype(slide)
    ideas = idea_cues(slide)
    vcues = verb_cues(slide, ideas)
    verb = vcues[0]["cue"] if vcues else None
    out = {"idea_cues": ideas}
    fig = figure_kind(slide, arch)
    order_cues = bool(labels) and all(l in ORDER_CUES or "connectors/arrows" in l for l in labels)
    if fig == "chart" or (arch == "chart" and fig is None and verb not in STRONG_VERBS):
        # a chart keeps its form: the verb says how it moves (a series draws on, or bars grow)
        text = slide["title"] + " " + slide["text"]
        if fig == "chart" or verb not in ("grow", "count", "accumulate", "thin", "race", "sort"):
            verb = "trace" if verb == "trace" or len(TIME_AXIS.findall(text)) >= 3 else "grow"
    elif fig == "figure":
        if verb is None:  # a diagram keeps its form; its kind names the move
            kinds = [b.split()[0] for b in slide["mermaid"] if b.split()]
            verb = ("travel" if "sequenceDiagram" in kinds else
                    "switch" if any(k.startswith("stateDiagram") for k in kinds) else "reveal")
    elif arch in ("pipeline", "graph") and order_cues:
        # numbering, arrows and connectors only say the text is laid out in order
        if verb in STRONG_VERBS:
            new = STRONG_VERBS[verb]
            conf = round(min(0.6, 0.45 + 0.15 * (len(vcues) >= 2)), 2)
            reason = "verb cue: %s (%s); the row cues (%s) are layout only" % (
                verb, vcues[0]["evidence"], ", ".join(labels))
            arch = new
        else:
            conf = min(conf, 0.6 if verb == "travel" else 0.3)
            if verb is None:
                verb = "reveal"
                reason += "; order only: no claim beyond order, verb reveal"
    elif arch is not None and verb is None:
        verb = FAMILY_VERB.get(arch, "reveal")
    if arch == "pipeline":  # a row: is order all the source says?
        out["order_only"] = not ideas and verb == "reveal"
        if ideas and not reason.startswith("mermaid"):
            conf = min(conf, 0.3)
            reason += "; idea cues: %s (the row may only be the layout)" % ", ".join(
                dict.fromkeys(c["cue"] for c in ideas))
    out.update(suggested_archetype=arch, confidence=conf, reason=reason,
               suggested_verb=verb, verb_cues=vcues)
    return out


# ----------------------------------------------------------------- main ----
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("source", help="deck.pptx, deck.html or doc.md")
    ap.add_argument("--stage", nargs=2, type=int, metavar=("W", "H"))
    ap.add_argument("-o", "--output", help="write JSON here instead of stdout")
    ap.add_argument("--no-pptx-lib", action="store_true", help=argparse.SUPPRESS)  # no-op, kept
    args = ap.parse_args(argv)

    ext = os.path.splitext(args.source)[1].lower()
    stage, stage_source = None, "default"
    if ext == ".pptx":
        slides, stage = read_pptx(args.source), pptx_stage(args.source)
        stage_source = "pptx" if stage else "default"
    elif ext == ".ppt":
        ap.error("legacy .ppt: convert first with  soffice --headless --convert-to pptx %s" % args.source)
    elif ext in (".html", ".htm"):
        slides = read_html(args.source)
        with open(args.source, encoding="utf-8", errors="replace") as f:
            stage, stage_source = html_stage(f.read())
    elif ext in (".md", ".markdown"):
        slides = read_md(args.source)
    else:
        ap.error("unsupported input type: %s (want .pptx, .html or .md)" % ext)
    if args.stage:
        stage, stage_source = list(args.stage), "flag"
    stage = stage or [1920, 1080]
    g = math.gcd(*stage) or 1
    aspect = "%d:%d" % (stage[0] // g, stage[1] // g)
    aspect = {"8:5": "16:10"}.get(aspect, aspect)
    print("stage %dx%d (%s, from %s)%s" % (*stage, aspect, stage_source, "" if aspect == "16:9" else
          ": not 16:9, see layouts.md before picking a viewBox"), file=sys.stderr)

    for i, s in enumerate(slides, 1):
        s.update(index=i, **suggest(s))
        print("%3d  %-36.36s %-9s %.2f  %s" % (i, s["title"] or "(untitled)", s["suggested_archetype"]
              or "-", s["confidence"], s["suggested_verb"] or "-"), file=sys.stderr)
    keys = ["index", "title", "title_guessed", "bullets", "notes", "text", "has_image", "image_count",
            "hidden_pictures", "layout_pictures", "tables", "connectors", "mermaid", "builds", "suggested_archetype", "confidence", "reason", "order_only",
            "idea_cues", "suggested_verb", "verb_cues"]
    slides = [{k: s[k] for k in keys if k in s} for s in slides]
    builds = sum(s.get("builds", 0) for s in slides)
    if builds:
        print("builds: %d click build%s in the source; step control is available if the presenter "
              "wants to click through (default stays once)" % (builds, "" if builds == 1 else "s"),
              file=sys.stderr)
    out = {"source": os.path.basename(args.source), "stage": stage, "aspect": aspect,
           "stage_source": stage_source, "slides": slides, "builds": builds}
    data = json.dumps(out, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(data + "\n")
    else:
        print(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
