"""Capture the viewport of a page at given moments, optionally after scrolling an element into view.
usage: python tools/qa/frames.py <width> <url> <t1,t2,...> [--dark] [--scroll-to CSS_SELECTOR] [--out DIR]
"""
import base64, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import launch, wait_load

args = sys.argv[1:]
width, url, ts = int(args[0]), args[1], [float(x) for x in args[2].split(",")]
dark = "--dark" in args
sel = args[args.index("--scroll-to") + 1] if "--scroll-to" in args else ""
out = args[args.index("--out") + 1] if "--out" in args else "shots"
os.makedirs(out, exist_ok=True)
proc, ws = launch(width)
try:
    ws.call("Emulation.setDeviceMetricsOverride", width=width, height=900, deviceScaleFactor=1, mobile=width < 800)
    ws.call("Page.enable"); ws.call("Runtime.enable")
    ws.call("Page.navigate", url=url); wait_load(ws)
    if dark:
        ws.call("Runtime.evaluate", expression="document.documentElement.setAttribute('data-theme','dark')")
    if sel:
        ws.call("Runtime.evaluate", expression=f"document.querySelector('{sel}').scrollIntoView({{block:'center'}})")
    start = time.time()
    for t in ts:
        while time.time() - start < t:
            time.sleep(0.05)
        r, _ = ws.call("Page.captureScreenshot", format="png")
        name = os.path.join(out, f"frame-{width}-{t:g}{'-dark' if dark else ''}{'-' + sel.strip('.#') if sel else ''}.png")
        open(name, "wb").write(base64.b64decode(r["data"]))
        print("saved", name, flush=True)
finally:
    proc.kill()
