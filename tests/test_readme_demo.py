"""The README demo is honest: every visible fact of the hero fragment comes from the demo source slide.

Run from the repo root: python3 -m unittest discover -s tests -v
"""
import os, re, shutil, subprocess, sys, tempfile, unittest
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "examples", "first-slide", "source.html")
FRAGMENT = os.path.join(ROOT, "pool", "parcel-route", "parcel-route.html")
VERIFY = os.path.join(ROOT, "scripts", "verify_facts.py")
README = os.path.join(ROOT, "README.md")


class _Text(HTMLParser):
    """Visible text of a page: everything outside <head>, <style> and <script>, one chunk per line."""
    SKIP = {"head", "style", "script", "title"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.chunks.append(" ".join(data.split()))


def source_text():
    p = _Text()
    with open(SOURCE, encoding="utf-8") as f:
        p.feed(f.read())
    return "\n".join(p.chunks)


def verify(fragment, text):
    return subprocess.run([sys.executable, VERIFY, fragment, "--source-text", text, "--strict"],
                          capture_output=True, text=True, cwd=ROOT, timeout=120)


class ReadmeDemoTest(unittest.TestCase):
    def test_source_text_extracted(self):
        text = source_text()
        self.assertIn("How a package gets delivered", text)
        self.assertIn("about 30 other stops", text)
        self.assertNotIn("font-family", text)

    def test_fragment_traces_to_source(self):
        r = verify(FRAGMENT, source_text())
        self.assertEqual(r.returncode, 0, "verify_facts.py --strict failed:\n" + r.stdout + r.stderr)

    def test_invented_fact_fails(self):
        with open(FRAGMENT, encoding="utf-8") as f:
            frag = f.read()
        self.assertIn("about 30 other stops", frag)
        tmp = tempfile.mkdtemp(prefix="readme-demo-")
        try:
            bad = os.path.join(tmp, "parcel-route.html")
            with open(bad, "w", encoding="utf-8") as f:
                f.write(frag.replace("about 30 other stops", "Van 7 · 32 stops"))
            r = verify(bad, source_text())
            self.assertNotEqual(r.returncode, 0, "an invented 'Van 7 · 32 stops' passed:\n" + r.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_readme_hero_exists(self):
        with open(README, encoding="utf-8") as f:
            readme = f.read()
        # the hero is the first local image (badges before it are remote URLs)
        local = [p for p in re.findall(r"!\[[^\]]*\]\(([^)\s]+)", readme) if not re.match(r"[a-z]+:", p)]
        self.assertTrue(local, "README.md has no local image")
        self.assertTrue(os.path.isfile(os.path.join(ROOT, local[0])), "missing README hero " + local[0])
        self.assertTrue(local[0].endswith("hero.gif"), "README's first local image is not the hero: " + local[0])


if __name__ == "__main__":
    unittest.main()
