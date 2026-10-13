"""Front-end integration tests: the real console, in a real headless browser, against a
real server and database.

A server is started on a free port with the current environment, and Edge or Chrome is
driven over the DevTools protocol (no extra packages: `websockets` ships with uvicorn).
Skipped when no browser is installed. Set BROWSER_PATH to point at a specific one.
"""

import asyncio
import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import httpx
import pytest

from app.tests.conftest import MARKER

pytestmark = [pytest.mark.integration, pytest.mark.browser]

ROOT = Path(__file__).resolve().parents[3]
BROWSERS = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/microsoft-edge",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class Page:
    """One browser tab, driven over the DevTools protocol."""

    def __init__(self, socket_, base_url: str) -> None:
        self._socket = socket_
        self._base_url = base_url
        self._pending: dict[int, asyncio.Future] = {}
        self._next_id = 0
        self.errors: list[str] = []

    async def listen(self) -> None:
        async for raw in self._socket:
            message = json.loads(raw)
            if "id" in message:
                self._pending.pop(message["id"]).set_result(message)
            elif message.get("method") == "Runtime.exceptionThrown":
                details = message["params"]["exceptionDetails"]
                self.errors.append(details.get("exception", {}).get("description") or details.get("text", "exception"))
            elif message.get("method") == "Log.entryAdded":
                entry = message["params"]["entry"]
                # Content-Security-Policy violations are reported here.
                if entry["level"] == "error" and entry.get("source") in ("security", "violation"):
                    self.errors.append(entry["text"])

    async def send(self, method: str, **params) -> dict:
        self._next_id += 1
        future = asyncio.get_running_loop().create_future()
        self._pending[self._next_id] = future
        await self._socket.send(json.dumps({"id": self._next_id, "method": method, "params": params}))
        return (await future).get("result", {})

    async def evaluate(self, expression: str):
        result = await self.send("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
        assert "exceptionDetails" not in result, result["exceptionDetails"]
        return result.get("result", {}).get("value")

    async def open(self, route: str) -> None:
        await self.send("Page.navigate", url=f"{self._base_url}/{route}")
        await self.wait_for("document.querySelector('#nav a') !== null")

    async def wait_for(self, condition: str, timeout: float = 10.0):
        """Poll a JavaScript condition until it is truthy; fail with the condition if it never is."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = await self.evaluate(f"(() => {{ try {{ return {condition}; }} catch (error) {{ return false; }} }})()")
            if value:
                return value
            await asyncio.sleep(0.1)
        raise AssertionError(f"Timed out waiting for: {condition}")

    async def click(self, selector: str, text: str | None = None) -> None:
        found = await self.evaluate(
            "(() => { const all = [...document.querySelectorAll(%s)]; const wanted = %s;"
            " const element = wanted ? all.find((e) => e.textContent.trim().includes(wanted)) : all[0];"
            " if (!element) return false; element.click(); return true; })()" % (json.dumps(selector), json.dumps(text)))
        assert found, f"Nothing to click for {selector!r} {text!r}"

    async def type(self, selector: str, value: str) -> None:
        found = await self.evaluate(
            "(() => { const element = document.querySelector(%s); if (!element) return false; element.value = %s;"
            " element.dispatchEvent(new Event('input', { bubbles: true })); return true; })()"
            % (json.dumps(selector), json.dumps(value)))
        assert found, f"No input for {selector!r}"

    async def text(self, selector: str) -> str:
        return await self.evaluate("(document.querySelector(%s) || {}).textContent || ''" % json.dumps(selector))

    async def count(self, selector: str) -> int:
        return await self.evaluate("document.querySelectorAll(%s).length" % json.dumps(selector))

    async def screenshot(self, path: Path) -> None:
        data = await self.send("Page.captureScreenshot", format="png")
        path.write_bytes(base64.b64decode(data["data"]))


@pytest.fixture(scope="module")
def server(clean_database):
    """The application on a free port, using the same environment as the test run."""
    port = free_port()
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base_url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(80):
            try:
                if httpx.get(f"{base_url}/health", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.25)
        else:
            pytest.fail("The application did not start")
        yield base_url
    finally:
        process.terminate()
        process.wait(timeout=20)


@pytest.fixture(scope="module")
def browser():
    executable = os.getenv("BROWSER_PATH") or next((path for path in BROWSERS if Path(path).exists()), None)
    if executable is None:
        pytest.skip("No Edge or Chrome installation found")
    port = free_port()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profile:
        process = subprocess.Popen(
            [executable, "--headless=new", f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
             "--window-size=1440,960", "--hide-scrollbars", "--no-first-run", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(80):
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1)
                    break
                except OSError:
                    time.sleep(0.25)
            else:
                pytest.fail("The browser did not start")
            yield port
        finally:
            process.terminate()
            process.wait(timeout=20)


@pytest.fixture
def console(server, browser):
    """Returns run(scenario): opens a fresh tab, awaits scenario(page), and fails on any page error."""

    def run(scenario, width: int = 1440, height: int = 960, mobile: bool = False):
        import websockets

        async def session():
            request = urllib.request.Request(f"http://127.0.0.1:{browser}/json/new?about:blank", method="PUT")
            target = json.load(urllib.request.urlopen(request, timeout=5))
            async with websockets.connect(target["webSocketDebuggerUrl"], max_size=None) as socket_:
                page = Page(socket_, server)
                listener = asyncio.create_task(page.listen())
                try:
                    for domain in ("Page", "Runtime", "Log"):
                        await page.send(f"{domain}.enable")
                    await page.send("Emulation.setDeviceMetricsOverride", width=width, height=height,
                                    deviceScaleFactor=1, mobile=mobile)
                    await scenario(page)
                    assert page.errors == [], page.errors
                finally:
                    listener.cancel()
                    urllib.request.urlopen(f"http://127.0.0.1:{browser}/json/close/{target['id']}", timeout=5)

        asyncio.run(session())

    return run


@pytest.fixture
def api(server):
    with httpx.Client(base_url=server, timeout=20) as client:
        yield client


@pytest.fixture
def browser_patient(api, patient_fields):
    """A patient that only this test touches, findable by a unique last name."""
    fields = patient_fields(first_name="Zed", city="Testville")
    patient = api.post("/patients", json=fields).json()["data"]
    assert patient["last_name"].startswith(MARKER)
    return patient


ROWS = "table.data tbody tr:not([aria-hidden])"


def test_overview_renders_numbers_chart_and_lists(console):
    async def scenario(page: Page):
        await page.open("#/overview")
        await page.wait_for("document.querySelectorAll('.chart .bar').length === 14")
        assert await page.count(".tile") == 4
        assert await page.wait_for("/^\\d/.test(document.querySelector('.tile-value').textContent)")
        await page.wait_for("document.querySelector('#status-text').textContent.includes('online')")
        await page.click(".segmented button", "30 days")
        await page.wait_for("document.querySelectorAll('.chart .bar').length === 30")
        assert "Overview" in await page.evaluate("document.title")

    console(scenario)


def test_patient_search_filters_on_the_server_and_shows_no_stray_text(console, browser_patient):
    async def scenario(page: Page):
        await page.open("#/patients")
        await page.wait_for(f"document.querySelectorAll('{ROWS}').length > 0")
        await page.type(".search input", browser_patient["last_name"])
        await page.wait_for(f"document.querySelectorAll('{ROWS}').length === 1")
        assert "Zed" in await page.text(f"{ROWS} .person")
        assert browser_patient["last_name"].lower() in (await page.evaluate("location.hash")).lower()
        # Regression: a null child once rendered as the word "null" under the table.
        assert "null" not in await page.text("#main")
        assert "undefined" not in await page.text("#main")
        assert "1-1 of 1" in await page.text(".pagination")

        await page.type(".search input", "no-such-patient-zzzz")
        await page.wait_for("document.querySelector('.state') !== null")
        assert "No patients match" in await page.text(".state")
        assert "null" not in await page.text("#main")

    console(scenario)


def test_record_can_be_edited_with_server_validation_shown_on_the_field(console, api, browser_patient):
    patient_id = browser_patient["patient_id"]

    async def scenario(page: Page):
        await page.open(f"#/patients/{patient_id}")
        await page.wait_for("document.querySelector('.drawer-actions') !== null")
        assert "Zed" in await page.text(".drawer-title")
        assert await page.evaluate("document.querySelector('#app').inert") is True

        await page.click(".drawer-actions button", "Edit details")
        await page.type("#field-phone_number", "123")
        await page.type("#field-city", "Dallas")
        await page.click(".drawer-foot button", "Save changes")
        await page.wait_for("document.querySelector('[data-field=phone_number]').classList.contains('invalid')")
        assert "10-digit" in await page.text("[data-field=phone_number] .error")
        assert "Nothing was saved" in await page.text(".banner")
        assert api.get(f"/patients/{patient_id}").json()["data"]["city"] == "Testville"

        await page.type("#field-phone_number", "(919) 555-0188")
        await page.click(".drawer-foot button", "Save changes")
        await page.wait_for("document.querySelector('.drawer-actions') !== null")
        assert "(919) 555-0188" in await page.text(".drawer-body")
        assert "updated" in await page.text(".toast")

    console(scenario)
    saved = api.get(f"/patients/{patient_id}").json()["data"]
    assert (saved["phone_number"], saved["city"]) == ("9195550188", "Dallas")


def test_record_is_removed_only_after_confirmation(console, api, browser_patient):
    patient_id = browser_patient["patient_id"]

    async def scenario(page: Page):
        await page.open(f"#/patients/{patient_id}")
        await page.wait_for("document.querySelector('.drawer-actions') !== null")
        await page.click(".drawer-actions button", "Remove")
        await page.wait_for("document.querySelector('dialog.confirm[open]') !== null")
        await page.click("dialog.confirm button", "Cancel")
        await page.wait_for("document.querySelector('dialog.confirm') === null")
        assert api.get(f"/patients/{patient_id}").status_code == 200

        await page.click(".drawer-actions button", "Remove")
        await page.wait_for("document.querySelector('dialog.confirm[open]') !== null")
        await page.click("dialog.confirm button", "Remove record")
        await page.wait_for("document.querySelector('.drawer') === null")
        assert await page.evaluate("document.querySelector('#app').inert") is False
        assert patient_id not in await page.evaluate("location.hash")

    console(scenario)
    assert api.get(f"/patients/{patient_id}").status_code == 404


def test_calls_page_lists_calls_and_opens_a_transcript(console, call_tool, end_call, call_id, patient_fields):
    fields = patient_fields(first_name="Zed")
    call_tool("save_patient", {**fields, "read_back_confirmed": True}, call_id)
    end_call(call_id, transcript="AI: Hi, what is your name?\nUser: Zed.\nAI: You're all set, Zed.")

    async def scenario(page: Page):
        await page.open("#/calls")
        await page.wait_for(f"document.querySelectorAll('{ROWS}').length > 0")
        await page.type(".search input", fields["last_name"])
        await page.wait_for(f"document.querySelectorAll('{ROWS}').length === 1")
        assert "Registered" in await page.text(f"{ROWS} .badge")
        assert "null" not in await page.text("#main")
        await page.click(ROWS)
        await page.wait_for("document.querySelectorAll('.drawer .bubble').length === 3")
        assert await page.count(".drawer .bubble.caller") == 1
        await page.evaluate("document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))")
        await page.wait_for("document.querySelector('.drawer') === null")

    console(scenario)


def test_unknown_record_and_unknown_route_are_handled(console):
    async def scenario(page: Page):
        await page.open("#/patients/00000000-0000-4000-8000-000000000000")
        await page.wait_for("document.querySelector('.drawer .state') !== null")
        assert "Record not found" in await page.text(".drawer")
        await page.open("#/nowhere")
        await page.wait_for("location.hash === '#/overview'")

    console(scenario)


def test_theme_switch_and_phone_layout(console):
    async def scenario(page: Page):
        await page.open("#/overview")
        await page.click(".page-actions .btn.square")
        await page.click(".page-actions .btn.square")
        assert await page.evaluate("document.documentElement.dataset.theme") == "dark"
        assert await page.evaluate("getComputedStyle(document.body).backgroundColor") != "rgb(243, 245, 249)"
        for route in ("#/overview", "#/patients", "#/calls"):
            await page.open(route)
            await page.wait_for("document.querySelector('#main').children.length > 0")
            overflow = await page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            assert overflow <= 0, f"{route} scrolls sideways by {overflow}px"

    console(scenario, width=390, height=844, mobile=True)
