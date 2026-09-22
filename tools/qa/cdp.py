"""Minimal Chrome DevTools Protocol client (stdlib only) for site QA.
usage: python tools/qa/cdp.py <width> <url> <js-expression-or-file>
"""
import base64, json, os, socket, struct, subprocess, sys, time, urllib.request

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9333


class WS:
    def __init__(self, url):
        host, rest = url[5:].split("/", 1)
        h, p = host.split(":")
        self.s = socket.create_connection((h, int(p)))
        self.s.settimeout(20)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.send((f"GET /{rest} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                     f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.s.recv(4096)
        self.buf = buf.split(b"\r\n\r\n", 1)[1]
        self.id = 0

    def send(self, method, **params):
        self.id += 1
        payload = json.dumps({"id": self.id, "method": method, "params": params}).encode()
        hdr = bytearray([0x81]); n = len(payload)
        if n < 126: hdr.append(0x80 | n)
        elif n < 65536: hdr += bytes([0x80 | 126]) + struct.pack(">H", n)
        else: hdr += bytes([0x80 | 127]) + struct.pack(">Q", n)
        mask = os.urandom(4)
        self.s.send(bytes(hdr) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))
        return self.id

    def _read_exact(self, n):
        while len(self.buf) < n:
            chunk = self.s.recv(65536)
            if not chunk: raise ConnectionError
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self):
        b1, b2 = self._read_exact(2)
        n = b2 & 0x7F
        if n == 126: n = struct.unpack(">H", self._read_exact(2))[0]
        elif n == 127: n = struct.unpack(">Q", self._read_exact(8))[0]
        data = self._read_exact(n)
        return json.loads(data) if (b1 & 0x0F) == 1 else None

    def call(self, method, **params):
        i = self.send(method, **params)
        events = []
        while True:
            m = self.recv()
            if m is None: continue
            if m.get("id") == i:
                return m.get("result", m), events
            events.append(m)


def launch(width, height=900, port=PORT):
    proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run",
                             f"--remote-debugging-port={port}", f"--window-size={width},{height}", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    targets = None
    for _ in range(60):
        try:
            targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json")); break
        except Exception:
            time.sleep(0.25)
    if not targets:
        proc.kill(); raise SystemExit("chrome did not start")
    page = next(t for t in targets if t["type"] == "page")
    return proc, WS(page["webSocketDebuggerUrl"])


def wait_load(ws, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        m = ws.recv()
        if m and m.get("method") == "Page.loadEventFired":
            return True
    return False


def main():
    width, url, js = int(sys.argv[1]), sys.argv[2], sys.argv[3]
    if os.path.exists(js):
        js = open(js, encoding="utf-8").read()
    proc, ws = launch(width)
    try:
        ws.call("Emulation.setDeviceMetricsOverride", width=width, height=900, deviceScaleFactor=1, mobile=width < 800)
        ws.call("Runtime.enable"); ws.call("Log.enable"); ws.call("Page.enable")
        ws.call("Page.navigate", url=url); wait_load(ws); time.sleep(0.8)
        res, events = ws.call("Runtime.evaluate", expression=js, returnByValue=True, awaitPromise=True)
        errs = [e["params"] for e in events if e.get("method") in ("Runtime.exceptionThrown", "Log.entryAdded")]
        print(json.dumps({"value": res.get("result", {}).get("value", res), "errors": errs}, indent=1, ensure_ascii=False))
    finally:
        proc.kill()


if __name__ == "__main__":
    main()
