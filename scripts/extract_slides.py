#!/usr/bin/env python3
"""Extract an outline from an existing deck and suggest illustration archetypes.

Usage:
    extract_slides.py <deck.pptx|deck.html|doc.md> [--stage W H] [-o outline.json]

Reads a PowerPoint file, an HTML slide deck (reveal.js, frontend-slides, any
<section>/.slide/.step markup) or a Markdown document (split on `---` lines,
or on #/## headings when there are none) and writes a JSON outline:

    {"source": "deck.pptx", "stage": [1920, 1080], "aspect": "16:9", "slides": [
      {"index": 3, "title": "Release process", "bullets": [...], "notes": "...",
       "text": "...", "has_image": true, "image_count": 1,
       "tables": [[["Old", "New"], ["manual", "CI"]]], "connectors": 4,
       "suggested_archetype": "pipeline", "confidence": 0.6,
       "reason": "cues: arrows, numbered steps"}]}

`tables` (rows of cell strings), `connectors` (connector lines and arrow
shapes), `title_guessed` (no title placeholder; the title is the largest-font
or first short text) and `mermaid` appear only when present.

The archetype is one of pipeline, graph, timeline, states, compare, layers,
chart (see references/archetypes.md) or null when no structural cue is found.
It is only a suggestion from keyword and shape heuristics; review it before
building.

The stage defaults to 1920x1080. For .pptx without --stage it is derived from
the deck's slide size, scaled to a width of 1920 (a 4:3 deck gives 1920x1440).
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
               connectors=0, segments=None, branching=False, title_guessed=False):
    slide = {"title": collapse(title), "bullets": [collapse(b) for b in bullets if collapse(b)],
             "notes": collapse(notes), "text": collapse(text),
             "has_image": image_count > 0, "image_count": image_count}
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
    pics = conns = 0
    starts, ends = [], []
    for el in root.iter():
        if el.tag == P + "pic":
            pics += 1
        elif el.tag == P + "cxnSp":
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
    return title, bullets, text, tables, pics, conns, branching, guessed


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
        for name in order:
            root = ET.fromstring(z.read(name))
            title, bullets, text, tables, pics, conns, branching, guessed = pptx_slide(root)
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
                                     tables, conns, segments, branching, guessed))
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
    tables = []
    for t in (d for d in nodes if d.tag == "table" and not inside(d, "table")):
        rows = [[node_text(c) for c in tr.children if isinstance(c, Node) and c.tag in ("td", "th")]
                for tr in t.iter() if tr.tag == "tr"]
        tables.append([r for r in rows if any(collapse(c) for c in r)])
    return make_slide(title, bullets, notes, node_text(n), images, tables,
                      segments=[title] + bullets + [notes, node_text(n)])


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
    tables, cur = [], None
    for ln in raw.splitlines():
        if re.match(r"\s*\|.*\|\s*$", ln):
            if re.fullmatch(r"[\s|:-]+", ln):
                continue
            cur = [] if cur is None else cur
            cur.append([c.strip() for c in ln.strip().strip("|").split("|")])
        elif cur is not None:
            tables.append(cur)
            cur = None
    if cur:
        tables.append(cur)
    slide = make_slide(title, bullets, notes, re.sub(r"^\s*#{1,6}\s+", "", raw, flags=re.M), images,
                       tables, segments=[title] + raw.splitlines() + [notes])
    if mermaid:
        slide["mermaid"] = mermaid
    return slide


# ----------------------------------------------------------- heuristics ----
def w(pattern, flags=0):
    return re.compile(r"(?<![\w-])(?:%s)(?![\w-])" % pattern, flags)


YEAR = re.compile(r"(?<![\d.,$€£])(?:19|20)\d{2}(?![\d%]|,\d|\s?(?:words?|characters?|chars|people|users"
                  r"|scientists|pages?|km|kg|mb|gb|ms|px|euros?|eur|usd|dollars?|€|\$))")
RULES = {  # archetype -> [(cue label, regex)]; regexes run on the lowercased text unless cased
    "pipeline": [("arrows", re.compile(r"->|→|=>|⇒|⟶")), ("'then'", w("then")),
                 ("numbered steps", re.compile(r"(?:^|\s)(?:\d+[.)]|step\s*\d+)\s", re.M)),
                 ("'step'", w(r"steps?|stages?|phases?"))],
    "graph": [("dependency verbs", w(r"depends on|depend on|requires?|calls|uses|imports")),
              ("decision wording", re.compile(r"(?<![\w-])if\b[^.;:?!]{0,80}?\b(?:positive|negative|yes|no"
                                              r"|true|false|fails?|passes?|succeeds?|accepted|rejected)\b")),
              ("'either'", w("either")), ("'OR'", ("cased", w("OR")))],
    "timeline": [("years", YEAR), ("quarters", w("q[1-4]")),
                 ("dates", re.compile(r"\d{4}-\d{2}-\d{2}|(?<![\w])(?:jan|feb|mar|apr|may|jun|jul"
                                      r"|aug|sep|oct|nov|dec)[a-z]*\.? \d{1,2}(?!\d)")),
                 ("months", w(r"january|february|march|april|june|july|august|september|october|november"
                              r"|december|jan|feb|mar|apr|jun|jul|aug|sept?|oct|nov|dec")),
                 ("'roadmap'", w("roadmaps?")), ("'milestone'", w("milestones?")),
                 ("'timeline'", w("timelines?|chronology"))],
    "compare": [("'vs'", w(r"vs\.?|versus")), ("before/after", w("before|after")),
                ("old/new", w("old|new"))],
    "layers": [("'layer'", w("layers?|layered")), ("'tier'", w("tiers?")), ("'stack'", w("stacks?")),
               ("'on top of'", w("on top of"))],
    "states": [("'state'", w("(?<!united )states?")), ("'mode'", w("modes?")), ("'transition'", w("transitions?"))],
}
UNIT_NUM = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?\s?(?:%|ms|s|sec|min|h|hrs?|days?|gb|mb|kb|tb"
                      r"|k|m|bn|x|users|req/s|rps|€|\$|eur|usd|fps)(?![a-z])"
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
SENTENCE = re.compile(r"(?<=[.;!?])\s+(?=[A-Z(\[])")


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


def suggest(slide):
    for body in slide.get("mermaid", []):
        hit = mermaid_archetype(body)
        if hit:
            return hit[0], 0.9, hit[1]
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
        return None, 0.0, "no structural cues"
    conf = min(0.9, 0.3 + 0.15 * (best[0] - 1) + (0.15 if best[1] >= 4 else 0))
    return best[2], round(conf, 2), "cues: " + ", ".join(best[3])


# ----------------------------------------------------------------- main ----
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("source", help="deck.pptx, deck.html or doc.md")
    ap.add_argument("--stage", nargs=2, type=int, metavar=("W", "H"))
    ap.add_argument("-o", "--output", help="write JSON here instead of stdout")
    ap.add_argument("--no-pptx-lib", action="store_true", help=argparse.SUPPRESS)  # no-op, kept
    args = ap.parse_args(argv)

    ext = os.path.splitext(args.source)[1].lower()
    stage = None
    if ext == ".pptx":
        slides, stage = read_pptx(args.source), pptx_stage(args.source)
    elif ext == ".ppt":
        ap.error("legacy .ppt: convert first with  soffice --headless --convert-to pptx %s" % args.source)
    elif ext in (".html", ".htm"):
        slides = read_html(args.source)
    elif ext in (".md", ".markdown"):
        slides = read_md(args.source)
    else:
        ap.error("unsupported input type: %s (want .pptx, .html or .md)" % ext)
    stage = list(args.stage) if args.stage else (stage or [1920, 1080])
    g = math.gcd(*stage) or 1
    aspect = "%d:%d" % (stage[0] // g, stage[1] // g)
    aspect = {"8:5": "16:10"}.get(aspect, aspect)
    print("stage %dx%d (%s)%s" % (*stage, aspect, "" if aspect == "16:9" else
          ": not 16:9, see layouts.md before picking a viewBox"), file=sys.stderr)

    for i, s in enumerate(slides, 1):
        arch, conf, reason = suggest(s)
        s.update(index=i, suggested_archetype=arch, confidence=conf, reason=reason)
        print("%3d  %-36.36s %-9s %.2f" % (i, s["title"] or "(untitled)", arch or "-", conf),
              file=sys.stderr)
    keys = ["index", "title", "title_guessed", "bullets", "notes", "text", "has_image", "image_count",
            "tables", "connectors", "mermaid", "suggested_archetype", "confidence", "reason"]
    slides = [{k: s[k] for k in keys if k in s} for s in slides]
    out = {"source": os.path.basename(args.source), "stage": stage, "aspect": aspect, "slides": slides}
    data = json.dumps(out, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(data + "\n")
    else:
        print(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
