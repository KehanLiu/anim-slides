#!/usr/bin/env python3
"""Bundle a working deck into ONE self-contained HTML file for hand-over. Standard library only.

Usage:
  bundle_deck.py DECK.html -o DECK.bundled.html [--fetch] [--max-asset-mb 8]

Keep the working deck lean (linked files, readable diffs) and bundle only at the end. Inlined:
  - <link rel=stylesheet href=...>  -> <style> with its @import and url() resolved and inlined
  - <script src=...></script>       -> inline <script> (other attributes such as type=module kept)
  - <img src/srcset>, <source src/srcset>, <video src/poster>, <audio src>, <track src>,
    <image href>, <link rel=icon|preload> -> data: URIs with the right MIME type
  - url() in <style> blocks and style="" attributes, fonts in @font-face included
Relative paths resolve against the deck's folder (inside inlined CSS: against that CSS file).
Remote URLs (http(s)://, //host) are left alone and listed unless --fetch is given, which
downloads and inlines them (pinned CDN libraries such as reveal.js or GSAP). Assets over
--max-asset-mb are skipped with a warning. HTML comments (the anim: / anim-style: markers) and
inline script bodies are never touched. Prints a summary; then run check_page.py on the output.
"""
import argparse
import base64
import mimetypes
import os
import re
import sys
import urllib.parse
import urllib.request

MIME = {'.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf', '.otf': 'font/otf',
        '.eot': 'application/vnd.ms-fontobject', '.svg': 'image/svg+xml', '.js': 'text/javascript',
        '.mjs': 'text/javascript', '.css': 'text/css', '.webp': 'image/webp', '.avif': 'image/avif',
        '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif',
        '.ico': 'image/x-icon', '.mp4': 'video/mp4', '.webm': 'video/webm', '.vtt': 'text/vtt',
        '.json': 'application/json', '.mp3': 'audio/mpeg', '.wav': 'audio/wav'}
SKIP = ('data:', '#', 'blob:', 'about:', 'javascript:', 'mailto:')
REMOTE = re.compile(r'^(?:https?:)?//', re.I)


class Bundler:
    def __init__(self, base, fetch, max_bytes):
        self.base, self.fetch, self.max = base, fetch, max_bytes
        self.cache = {}
        self.inlined = {}      # kind -> count
        self.remaining = []    # (url, reason)
        self.bytes_in = 0

    # -------------------------------------------------------------- loading
    def resolve(self, url, ctx):
        """Absolute location of url seen in context ctx (a folder path or a remote URL)."""
        if REMOTE.match(url):
            return 'https:' + url if url.startswith('//') else url
        if url.lower().startswith('file:'):
            return urllib.parse.unquote(urllib.parse.urlparse(url).path)
        if REMOTE.match(ctx):
            return urllib.parse.urljoin(ctx, url)
        return os.path.normpath(os.path.join(ctx, urllib.parse.unquote(re.split(r'[?#]', url)[0])))

    def load(self, loc):
        """bytes or None (and a note in self.remaining)."""
        if loc in self.cache:
            return self.cache[loc]
        data = None
        if REMOTE.match(loc):
            if not self.fetch:
                self.remaining.append((loc, 'remote (pass --fetch to inline)'))
            else:
                try:
                    req = urllib.request.Request(loc, headers={'User-Agent': 'anim-slides-bundle/1'})
                    with urllib.request.urlopen(req, timeout=30) as r:
                        data = r.read(self.max + 1)
                except Exception as e:  # noqa: BLE001 - report and keep the URL
                    self.remaining.append((loc, f'fetch failed: {e}'))
        elif os.path.isfile(loc):
            if os.path.getsize(loc) > self.max:
                data = b'x' * (self.max + 1)
            else:
                data = open(loc, 'rb').read()
        else:
            self.remaining.append((loc, 'local file not found'))
        if data is not None and len(data) > self.max:
            self.remaining.append((loc, f'over --max-asset-mb ({self.max / 2**20:g} MB), skipped'))
            data = None
        if data is not None:
            self.bytes_in += len(data)
        self.cache[loc] = data
        return data

    @staticmethod
    def ctx_of(loc):
        return loc if REMOTE.match(loc) else os.path.dirname(loc)

    @staticmethod
    def mime(loc):
        path = urllib.parse.urlparse(loc).path if REMOTE.match(loc) else loc
        ext = os.path.splitext(path)[1].lower()
        return MIME.get(ext) or mimetypes.guess_type(path)[0] or 'application/octet-stream'

    def data_uri(self, url, ctx, kind):
        if not url or url.startswith(SKIP):
            return None
        frag = ''
        if '#' in url and not url.startswith('#'):
            url, frag = url.split('#', 1)
            frag = '#' + frag
        loc = self.resolve(url, ctx)
        data = self.load(loc)
        if data is None:
            return None
        mt = self.mime(loc)
        if mt == 'text/css':
            data = self.css(data.decode('utf-8', 'replace'), self.ctx_of(loc)).encode('utf-8')
        self.inlined[kind] = self.inlined.get(kind, 0) + 1
        return f'data:{mt};base64,{base64.b64encode(data).decode("ascii")}' + frag

    # -------------------------------------------------------------- css
    def css(self, text, ctx, depth=0):
        def imp(m):
            url = m.group(1) or m.group(2) or m.group(3)
            media = (m.group(4) or '').strip()
            if depth > 8 or url.startswith(SKIP):
                return m.group(0)
            loc = self.resolve(url, ctx)
            data = self.load(loc)
            if data is None:
                return m.group(0)
            self.inlined['css @import'] = self.inlined.get('css @import', 0) + 1
            inner = self.css(data.decode('utf-8', 'replace'), self.ctx_of(loc), depth + 1)
            return f'@media {media} {{\n{inner}\n}}' if media else inner
        text = re.sub(r'''@import\s+(?:url\(\s*["']?([^"')]+)["']?\s*\)|"([^"]+)"|'([^']+)')([^;]*);''', imp, text, flags=re.I)

        def url(m):
            u = m.group(2).strip()
            kind = 'font' if re.search(r'\.(woff2?|ttf|otf|eot)(\?|#|$)', u, re.I) else 'css url()'
            d = self.data_uri(u, ctx, kind)
            return f'url("{d}")' if d else m.group(0)
        return re.sub(r'''url\(\s*(["']?)([^"')]+)\1\s*\)''', url, text, flags=re.I)

    # -------------------------------------------------------------- html
    def html(self, src):
        # protect comments and inline script/style bodies from the tag rewrites
        keep = []

        def stash(s):
            keep.append(s)
            return f'\x00{len(keep) - 1}\x00'
        src = re.sub(r'<!--.*?-->', lambda m: stash(m.group(0)), src, flags=re.S)

        def script(m):
            attrs, body = m.group(1), m.group(2)
            sm = re.search(r'''\ssrc\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))''', attrs, re.I)
            if not sm:
                return stash(m.group(0))
            url = sm.group(1) or sm.group(2) or sm.group(3)
            loc = self.resolve(url, self.base) if not url.startswith(SKIP) else None
            data = self.load(loc) if loc else None
            if data is None:
                return stash(m.group(0))
            self.inlined['script'] = self.inlined.get('script', 0) + 1
            rest = (attrs[:sm.start()] + attrs[sm.end():])
            rest = re.sub(r'''\s(integrity|crossorigin|defer|async)(\s*=\s*("[^"]*"|'[^']*'|[^\s>]+))?''', '', rest, flags=re.I)
            code = data.decode('utf-8', 'replace').replace('</script', '<\\/script')
            return stash(f'<script{rest}>{code}</script>')
        src = re.sub(r'<script\b([^>]*)>(.*?)</script\s*>', script, src, flags=re.S | re.I)

        def style(m):
            return stash(f'<style{m.group(1)}>{self.css(m.group(2), self.base)}</style>')
        src = re.sub(r'<style\b([^>]*)>(.*?)</style\s*>', style, src, flags=re.S | re.I)

        def link(m):
            attrs = m.group(1)
            rel = re.search(r'''\brel\s*=\s*["']?([^"'>]+)''', attrs, re.I)
            rel = rel.group(1).lower() if rel else ''
            hm = re.search(r'''\shref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))''', attrs, re.I)
            if not hm:
                return m.group(0)
            url = hm.group(1) or hm.group(2) or hm.group(3)
            if url.startswith(SKIP):
                return m.group(0)
            if 'stylesheet' in rel:
                loc = self.resolve(url, self.base)
                data = self.load(loc)
                if data is None:
                    return m.group(0)
                self.inlined['stylesheet'] = self.inlined.get('stylesheet', 0) + 1
                media = re.search(r'''\smedia\s*=\s*["']([^"']+)["']''', attrs, re.I)
                ma = f' media="{media.group(1)}"' if media else ''
                css = self.css(data.decode('utf-8', 'replace'), self.ctx_of(loc))
                return stash(f'<style{ma}>\n{css}\n</style>')
            if re.search(r'icon|preload', rel) and 'modulepreload' not in rel:
                d = self.data_uri(url, self.base, 'link ' + rel)
                if d:
                    return m.group(0)[:hm.start() + 5] + f' href="{d}"' + m.group(0)[hm.end() + 5:]
            elif REMOTE.match(url) and re.search(r'modulepreload|manifest', rel):
                self.remaining.append((url, f'<link rel={rel}> not inlined'))
            return m.group(0)
        src = re.sub(r'<link\b([^>]*)>', link, src, flags=re.I)

        attr_re = re.compile(r'''(\s)((?:xlink:)?href|src|srcset|poster)(\s*=\s*)(?:"([^"]*)"|'([^']*)'|([^\s>]+))''', re.I)

        def tag(m):
            name = m.group(1).lower()
            want = {'img': ('src', 'srcset'), 'source': ('src', 'srcset'), 'video': ('src', 'poster'),
                    'audio': ('src',), 'track': ('src',), 'image': ('href', 'xlink:href'),
                    'input': ('src',), 'embed': ('src',)}.get(name, ())

            def one(a):
                an = a.group(2).lower()
                if an not in want:
                    return a.group(0)
                val = a.group(4) if a.group(4) is not None else (a.group(5) if a.group(5) is not None else a.group(6))
                if an == 'srcset':
                    parts = []
                    for part in val.split(','):
                        bits = part.strip().split(None, 1)
                        if not bits:
                            continue
                        d = self.data_uri(bits[0], self.base, name)
                        parts.append(' '.join([d or bits[0]] + bits[1:]))
                    return f'{a.group(1)}{a.group(2)}{a.group(3)}"{", ".join(parts)}"'
                d = self.data_uri(val, self.base, name)
                return f'{a.group(1)}{a.group(2)}{a.group(3)}"{d}"' if d else a.group(0)
            return '<' + m.group(1) + attr_re.sub(one, m.group(2)) + '>'
        src = re.sub(r'<(img|source|video|audio|track|image|input|embed)\b([^>]*)>', tag, src, flags=re.I)

        def style_attr(m):
            return m.group(1) + m.group(2) + self.css(m.group(3), self.base) + m.group(2)
        src = re.sub(r'''(\sstyle\s*=\s*)(["'])(.*?)\2''', style_attr, src, flags=re.S | re.I)

        for m in re.finditer(r'<(use|iframe|object)\b[^>]*\s(?:xlink:href|href|src|data)\s*=\s*["\']?((?:https?:)?//[^"\'\s>]+)',
                             src, re.I):
            self.remaining.append((m.group(2), f'<{m.group(1)}> cannot be inlined'))
        while '\x00' in src:
            src = re.sub(r'\x00(\d+)\x00', lambda m: keep[int(m.group(1))], src)
        return src


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('deck')
    ap.add_argument('-o', '--output', required=True)
    ap.add_argument('--fetch', action='store_true', help='download and inline remote (CDN) assets')
    ap.add_argument('--max-asset-mb', type=float, default=8)
    a = ap.parse_args()
    if os.path.abspath(a.output) == os.path.abspath(a.deck):
        sys.exit('bundle_deck: -o must differ from the deck (keep the working deck lean)')
    src = open(a.deck, encoding='utf-8').read()
    b = Bundler(os.path.dirname(os.path.abspath(a.deck)), a.fetch, int(a.max_asset_mb * 2**20))
    out = b.html(src)
    markers = len(re.findall(r'<!--\s*anim(?:-style)?:[\w-]+:(?:start|end)\s*-->', src))
    kept = len(re.findall(r'<!--\s*anim(?:-style)?:[\w-]+:(?:start|end)\s*-->', out))
    if kept != markers:
        sys.exit(f'bundle_deck: anim markers changed ({markers} -> {kept}); nothing written')
    open(a.output, 'w', encoding='utf-8').write(out)
    n_in, n_out = len(src.encode()), len(out.encode())
    inl = ', '.join(f'{v} {k}' for k, v in sorted(b.inlined.items())) or 'nothing'
    print(f'bundled {a.deck} -> {a.output}: {n_in:,} -> {n_out:,} bytes; inlined {inl}; '
          f'{kept} anim markers kept')
    seen = set()
    for u, why in b.remaining:
        if (u, why) in seen:
            continue
        seen.add((u, why))
        print(f'WARN external left: {u}: {why}', file=sys.stderr)
    print(f'{len(seen)} external reference(s) left' + ('' if seen else ': the file is self-contained')
          + f'. Next: python3 {os.path.join(os.path.dirname(os.path.abspath(__file__)), "check_page.py")} {a.output}')


if __name__ == '__main__':
    main()
