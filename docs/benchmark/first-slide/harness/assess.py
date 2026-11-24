"""assess.py <result.html> <shots_dir> <out.json>
Loads the file from disk with system Chrome (Playwright), logs every non-file request,
page errors and the Web Animations list, and takes screenshots at 1 s, mid-pass and rest
for desktop 1440x900 and mobile 390x844, plus reduced-motion frames and a loop check."""
import json, sys, hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright

html, shots, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]), Path(sys.argv[3])
shots.mkdir(parents=True, exist_ok=True)
ANIMS = """() => document.getAnimations().map(a => { const t = a.effect && a.effect.getComputedTiming ? a.effect.getComputedTiming() : {};
  return {name: a.animationName || a.id || a.constructor.name, delay: t.delay, duration: t.duration,
          iterations: t.iterations, endTime: t.endTime, target: a.effect && a.effect.target ? (a.effect.target.id || a.effect.target.getAttribute('class') || a.effect.target.tagName) : null}; })"""
report = {"file": str(html), "requests": [], "errors": [], "console": []}


def h(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")

    def page(vp, reduced=False):
        ctx = b.new_context(viewport=vp, reduced_motion="reduce" if reduced else "no-preference")
        pg = ctx.new_page()
        pg.on("request", lambda r: None if r.url.startswith(("file:", "data:", "blob:")) else report["requests"].append(r.url))
        pg.on("pageerror", lambda e: report["errors"].append(str(e)))
        pg.on("console", lambda m: report["console"].append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
        pg.goto(html.as_uri(), wait_until="load")
        return ctx, pg

    # timing probe
    ctx, pg = page({"width": 1440, "height": 900})
    pg.wait_for_timeout(500)
    anims = pg.evaluate(ANIMS)
    finite = [a["endTime"] for a in anims if isinstance(a.get("endTime"), (int, float)) and a["endTime"] not in (None,) and a["endTime"] < 1e9]
    infinite = [a for a in anims if a.get("iterations") in (None, float("inf")) or str(a.get("iterations")) in ("Infinity", "inf")]
    end_ms = max(finite) if finite else 0
    report.update(animations_count=len(anims), infinite_animations=infinite[:20], last_finite_end_ms=end_ms,
                  animations_sample=anims[:60])
    ctx.close()
    end_s = end_ms / 1000 if end_ms else 8.0
    import os
    times = {"t1s": 1.0, "mid": max(1.5, end_s / 2), "rest": end_s + 1.5}
    if os.environ.get("TIMES"): times = dict(zip(("t1s","mid","rest"), map(float, os.environ["TIMES"].split(","))))
    report["times"] = times
    for label, vp in (("desktop", {"width": 1440, "height": 900}), ("mobile", {"width": 390, "height": 844})):
        ctx, pg = page(vp)
        t = 0
        for k, s in sorted(times.items(), key=lambda kv: kv[1]):
            pg.wait_for_timeout(int((s - t) * 1000)); t = s
            pg.screenshot(path=str(shots / f"{label}-{k}.png"))
        # loop check: another frame 6 s after rest
        pg.wait_for_timeout(6000)
        pg.screenshot(path=str(shots / f"{label}-rest-plus6s.png"))
        report[f"{label}_rest_equals_rest_plus6s"] = h(shots / f"{label}-rest.png") == h(shots / f"{label}-rest-plus6s.png")
        report[f"{label}_scroll"] = pg.evaluate("() => ({sw: document.documentElement.scrollWidth, sh: document.documentElement.scrollHeight, iw: innerWidth, ih: innerHeight})")
        if label == "desktop":
            report["visible_text"] = pg.evaluate("() => document.body.innerText")
            report["svg_text"] = pg.evaluate("() => [...document.querySelectorAll('svg text, svg tspan')].map(e => e.textContent.trim()).filter(Boolean)")
            report["buttons"] = pg.evaluate("() => [...document.querySelectorAll('button, [role=button]')].map(e => (e.getAttribute('aria-label') || e.textContent).trim())")
        ctx.close()
    for label, vp in (("desktop", {"width": 1440, "height": 900}), ("mobile", {"width": 390, "height": 844})):
        ctx, pg = page(vp, reduced=True)
        pg.wait_for_timeout(300)
        pg.screenshot(path=str(shots / f"{label}-reduced-0.3s.png"))
        pg.wait_for_timeout(3000)
        pg.screenshot(path=str(shots / f"{label}-reduced-3.3s.png"))
        ctx.close()
    b.close()
out.write_text(json.dumps(report, indent=1, default=str))
print(json.dumps({k: report[k] for k in ("requests", "errors", "console", "animations_count", "last_finite_end_ms", "times",
                                         "desktop_rest_equals_rest_plus6s", "mobile_rest_equals_rest_plus6s",
                                         "desktop_scroll", "mobile_scroll", "buttons")}, indent=1, default=str))
print("infinite:", len(report["infinite_animations"]))
