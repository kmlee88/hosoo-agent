from __future__ import annotations

import base64
import hmac
import json
import os
import sys
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from hosoo_agent.dashboard_data import build_dashboard_payload  # noqa: E402


def _auth_configured() -> bool:
    return bool(os.environ.get("DASHBOARD_USER") and os.environ.get("DASHBOARD_PASSWORD"))


def _expected_auth_header() -> str:
    raw = f"{os.environ['DASHBOARD_USER']}:{os.environ['DASHBOARD_PASSWORD']}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT_DIR / "web"), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self._send_json({"ok": True})
            return

        if not self._is_authorized():
            self._request_auth()
            return

        if parsed.path == "/api/dashboard":
            query = parse_qs(parsed.query)
            target_date = query.get("date", [None])[0]
            self._send_json(build_dashboard_payload(ROOT_DIR, target_date=target_date))
            return

        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def _send_json(self, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _is_authorized(self) -> bool:
        if not _auth_configured():
            return True
        actual = self.headers.get("Authorization", "")
        expected = _expected_auth_header()
        return hmac.compare_digest(actual, expected)

    def _request_auth(self) -> None:
        body = b"Authentication required"
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("WWW-Authenticate", 'Basic realm="Hosoo Dashboard"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "127.0.0.1")
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"Dashboard running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
