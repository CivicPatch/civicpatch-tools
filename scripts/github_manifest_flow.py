"""GitHub's App manifest flow from a terminal: a local page posts the manifest to GitHub, and GitHub's redirect
(or the address pasted back, when the browser can't reach this machine) brings the one-time code."""
import html
import json
import queue
import secrets
import sys
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from dev_env import action, heading, note, warn

GITHUB_WEB = "https://github.com"
CALLBACK_HOST = "127.0.0.1"
CALLBACK_PORT = 8765  # first choice; taken ports step to the next one
CALLBACK_PORT_TRIES = 50
CALLBACK_PATH = "/callback"
HTTP_OK = 200


def manifest_form(org: str, manifest: dict, state: str) -> str:
    action = f"{GITHUB_WEB}/organizations/{org}/settings/apps/new?state={state}"
    value = html.escape(json.dumps(manifest), quote=True)
    return (
        f'<form id="f" method="post" action="{action}"><input type="hidden" name="manifest" value="{value}"></form>'
        '<p>Sending you to GitHub to create the app...</p><script>document.getElementById("f").submit()</script>'
    )


def code_from_paste(pasted: str, state: str) -> str | None:
    query = parse_qs(urlparse(pasted.strip()).query)
    return query["code"][0] if query.get("state") == [state] and query.get("code") else None


def callback_handler(forms: dict[str, str], state: str, codes: queue.Queue) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            url = urlparse(self.path)
            query = parse_qs(url.query)
            if url.path == CALLBACK_PATH and query.get("state") == [state]:
                codes.put(query["code"][0])
                self._reply("<p>Done. Back to the terminal.</p>")
                return
            self._reply(forms["page"])

        def _reply(self, body: str) -> None:
            self.send_response(HTTP_OK)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, *_args) -> None:
            return

    return Handler


def bind_callback(handler: type[BaseHTTPRequestHandler]) -> HTTPServer:
    for port in range(CALLBACK_PORT, CALLBACK_PORT + CALLBACK_PORT_TRIES):
        try:
            return HTTPServer((CALLBACK_HOST, port), handler)
        except OSError:
            continue
    raise SystemExit(f"No free port in {CALLBACK_PORT}-{CALLBACK_PORT + CALLBACK_PORT_TRIES - 1}.")


def receive_code(org: str, name: str, manifest_for_port: Callable[[int], dict]) -> str:
    state = secrets.token_urlsafe(16)
    codes: queue.Queue = queue.Queue()
    forms: dict[str, str] = {}
    # The manifest names the callback port, which is only known once bound; the handler reads it per request.
    server = bind_callback(callback_handler(forms, state, codes))
    port = server.server_address[1]
    forms["page"] = manifest_form(org, manifest_for_port(port), state)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def read_paste() -> None:
        for line in sys.stdin:  # ends at end-of-file, so a closed stdin leaves only the browser callback
            if code := code_from_paste(line, state):
                codes.put(code)
                return
            if line.strip():
                warn("No code from this run in that address. Paste the whole address.")

    threading.Thread(target=read_paste, daemon=True).start()
    heading(f"Creating {name}")
    action(1, f"Open http://localhost:{port}/")
    action(2, "Press Create on GitHub")
    note("If the next page won't load, paste its address here.")
    try:
        return codes.get()
    finally:
        # Frees the port on success, Ctrl+C or error alike.
        server.shutdown()
        server.server_close()
