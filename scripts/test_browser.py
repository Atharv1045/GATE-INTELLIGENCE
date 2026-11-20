import subprocess
import time
import urllib.request
import json
import tempfile
import shutil
import asyncio
import websockets

class ChromeCDP:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = None
        self.msg_id = 0
        self.pending = {}
        self.console_logs = []
        self.page_errors = []

    async def connect(self):
        self.ws = await websockets.connect(self.ws_url, max_size=10*1024*1024)
        asyncio.create_task(self._listen())
        await self.send("Runtime.enable")
        await self.send("Page.enable")
        await self.send("Log.enable")

    async def _listen(self):
        try:
            async for raw in self.ws:
                msg = json.loads(raw)
                if "id" in msg and msg["id"] in self.pending:
                    self.pending[msg["id"]].set_result(msg)
                elif msg.get("method") == "Runtime.consoleAPICalled":
                    args = msg.get("params", {}).get("args", [])
                    txt = " ".join([str(a.get("value", a.get("description", ""))) for a in args])
                    self.console_logs.append(f"[{msg.get('params', {}).get('type')}] {txt}")
                elif msg.get("method") == "Runtime.exceptionThrown":
                    exc = msg.get("params", {}).get("exceptionDetails", {})
                    self.page_errors.append(exc.get("text") or str(exc))
        except Exception:
            pass

    async def send(self, method, params=None):
        self.msg_id += 1
        mid = self.msg_id
        fut = asyncio.get_running_loop().create_future()
        self.pending[mid] = fut
        payload = {"id": mid, "method": method}
        if params:
            payload["params"] = params
        await self.ws.send(json.dumps(payload))
        return await fut

    async def evaluate(self, expression):
        res = await self.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True
        })
        return res.get("result", {}).get("result", {}).get("value")

    async def navigate(self, url):
        await self.send("Page.navigate", {"url": url})
        await asyncio.sleep(2)  # Allow page to load & React to render

    async def close(self):
        if self.ws:
            await self.ws.close()

async def main():
    profile_dir = tempfile.mkdtemp()
    cmd = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "--headless=new",
        "--remote-debugging-port=9222",
        f"--user-data-dir={profile_dir}",
        "--disable-gpu",
        "--no-sandbox",
        "about:blank"
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        # Wait for CDP
        ws_url = None
        for _ in range(20):
            time.sleep(0.5)
            try:
                res = urllib.request.urlopen("http://127.0.0.1:9222/json/list", timeout=1)
                data = json.loads(res.read().decode())
                if data:
                    ws_url = data[0].get("webSocketDebuggerUrl")
                    if ws_url:
                        break
            except Exception:
                pass
        
        if not ws_url:
            print("Failed to get CDP WS URL")
            return

        cdp = ChromeCDP(ws_url)
        await cdp.connect()

        pages_to_test = [
            ("/", "Dashboard"),
            ("/questions", "Question Bank"),
            ("/papers", "Paper Library"),
            ("/analytics", "PYQ Analytics"),
            ("/mock-tests", "Mock Tests"),
            ("/agents", "Agents"),
            ("/settings", "Settings")
        ]

        print("\n=== RUNNING HEADLESS CHROME BROWSER E2E TESTS ===")
        for path, name in pages_to_test:
            url = f"http://127.0.0.1:5173{path}"
            await cdp.navigate(url)
            # Give React a moment to render
            await asyncio.sleep(1.5)
            title = await cdp.evaluate("document.title")
            body_text = await cdp.evaluate("document.body.innerText") or ""
            url_now = await cdp.evaluate("window.location.href")
            has_root = await cdp.evaluate("!!document.getElementById('root')")
            child_count = await cdp.evaluate("document.getElementById('root')?.children.length || 0")
            print(f"[{name}] {url_now}")
            print(f"  Title: '{title}', Root children: {child_count}, Text length: {len(body_text)}")
            print(f"  Snippet: {body_text[:120].replace(chr(10), ' ')}")

        print("\n=== BROWSER CONSOLE LOGS ===")
        for log in cdp.console_logs[-15:]:
            print(" ", log)

        print("\n=== BROWSER PAGE ERRORS ===")
        if cdp.page_errors:
            for err in cdp.page_errors:
                print("  ERROR:", err)
        else:
            print("  Zero unhandled exceptions in browser.")

        await cdp.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
        shutil.rmtree(profile_dir, ignore_errors=True)

if __name__ == "__main__":
    asyncio.run(main())
