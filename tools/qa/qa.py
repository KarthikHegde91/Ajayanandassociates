"""Batch QA over every page in dist/sitemap.xml against a running dev server.
usage: python tools/qa/qa.py <width> [--shots] [--theme dark|light] [--out DIR]
Prints one JSON line per page (overflow, heading order, console errors, dark-mode white leftovers).
"""
import base64, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import launch, wait_load

AUDIT_JS = r"""
(() => {
  const vw = document.documentElement.clientWidth;
  const wide = [];
  document.querySelectorAll('body *').forEach(el => {
    const cs = getComputedStyle(el);
    if (cs.position === 'fixed') return;
    if (el.closest('.table-wrap, .nav')) return;
    const r = el.getBoundingClientRect();
    if (r.right > vw + 1 && r.width > 0) wide.push(el.tagName + '.' + (typeof el.className === 'string' ? el.className.split(' ')[0] : ''));
  });
  const hs = [...document.querySelectorAll('h1,h2,h3,h4')].map(h => +h.tagName[1]);
  let badOrder = false; for (let i = 1; i < hs.length; i++) if (hs[i] > hs[i-1] + 1) badOrder = true;
  const whites = [];
  if (document.documentElement.getAttribute('data-theme') === 'dark') {
    document.querySelectorAll('body *').forEach(el => {
      if (el.closest('.brand, svg, .wa-float, .btn--whatsapp')) return;
      const cs = getComputedStyle(el); const r = el.getBoundingClientRect();
      if (r.width >= 8 && r.height >= 8 && cs.backgroundColor === 'rgb(255, 255, 255)') whites.push(el.tagName + '.' + String(el.className).split(' ')[0]);
    });
  }
  return {vw, scrollWidth: document.documentElement.scrollWidth, docH: document.documentElement.scrollHeight,
          h1: document.querySelectorAll('h1').length, badHeadingOrder: badOrder, title: document.title,
          wide: [...new Set(wide)].slice(0, 8), whites: [...new Set(whites)].slice(0, 8)};
})()
"""


def main():
    width = int(sys.argv[1]); shots = "--shots" in sys.argv
    theme = sys.argv[sys.argv.index("--theme") + 1] if "--theme" in sys.argv else ""
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "shots"
    suffix = f"-{theme}" if theme else ""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sm = open(os.path.join(root, "dist", "sitemap.xml"), encoding="utf-8").read()
    urls = [re.sub(r"^https?://[^/]+", "", u) for u in re.findall(r"<loc>(.*?)</loc>", sm)] + ["/404.html", "/thank-you/"]
    os.makedirs(out, exist_ok=True)
    proc, ws = launch(width)
    try:
        ws.call("Runtime.enable"); ws.call("Log.enable"); ws.call("Page.enable")
        for u in urls:
            ws.call("Emulation.setDeviceMetricsOverride", width=width, height=900, deviceScaleFactor=1, mobile=width < 800)
            ws.call("Page.navigate", url="http://localhost:8000" + u)
            deadline = time.time() + 15; events = []
            while time.time() < deadline:
                m = ws.recv()
                if not m: continue
                events.append(m)
                if m.get("method") == "Page.loadEventFired": break
            ws.call("Runtime.evaluate", expression=f"document.documentElement.setAttribute('data-theme', '{theme or 'light'}')")
            time.sleep(0.6)
            res, ev2 = ws.call("Runtime.evaluate", expression=AUDIT_JS, returnByValue=True)
            events += ev2
            errs = []
            for e in events:
                if e.get("method") == "Runtime.exceptionThrown":
                    errs.append(str(e["params"]["exceptionDetails"].get("exception", {}).get("description", ""))[:200])
                elif e.get("method") == "Log.entryAdded" and e["params"]["entry"]["level"] == "error":
                    errs.append(e["params"]["entry"].get("text", "")[:200])
            v = res.get("result", {}).get("value", {})
            v["url"] = u; v["errors"] = errs
            if shots:
                h = min(int(v.get("docH", 900)), 16000)
                ws.call("Emulation.setDeviceMetricsOverride", width=width, height=h, deviceScaleFactor=1, mobile=width < 800)
                time.sleep(0.5)
                ws.call("Runtime.evaluate", expression="document.querySelectorAll('[data-reveal]').forEach(e=>e.classList.add('is-visible'))")
                time.sleep(0.3)
                r, _ = ws.call("Page.captureScreenshot", format="png", captureBeyondViewport=True)
                name = (u.strip("/").replace("/", "_") or "home").replace(".html", "")
                open(os.path.join(out, f"{name}-{width}{suffix}.png"), "wb").write(base64.b64decode(r["data"]))
            print(json.dumps(v, ensure_ascii=False), flush=True)
    finally:
        proc.kill()


if __name__ == "__main__":
    main()
