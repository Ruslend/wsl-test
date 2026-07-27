from __future__ import annotations

import json
import os
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from database import TicketRepository

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DB_PATH = Path(os.environ.get("OFFICEFLOW_DB", BASE_DIR / "officeflow.db"))
repository = TicketRepository(DB_PATH)
repository.initialize(seed=True)


class OfficeFlowHandler(BaseHTTPRequestHandler):
    server_version = "OfficeFlow/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/tickets":
            params = parse_qs(parsed.query)
            self._json_response(repository.list_tickets(status=params.get("status", [""])[0], search=params.get("search", [""])[0]))
            return
        if parsed.path == "/api/stats":
            self._json_response(repository.stats())
            return
        self._serve_static(parsed.path)

    def do_POST(self) -> None:
        if self.path != "/api/tickets":
            self._json_response({"error": "Маршрут не найден"}, HTTPStatus.NOT_FOUND)
            return
        try:
            self._json_response(repository.create_ticket(self._read_json()), HTTPStatus.CREATED)
        except ValueError as exc:
            self._json_response({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_PATCH(self) -> None:
        match = re.fullmatch(r"/api/tickets/(\d+)", self.path)
        if not match:
            self._json_response({"error": "Маршрут не найден"}, HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self._read_json()
            self._json_response(repository.update_status(int(match.group(1)), str(payload.get("status", ""))))
        except ValueError as exc:
            self._json_response({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except KeyError as exc:
            self._json_response({"error": exc.args[0]}, HTTPStatus.NOT_FOUND)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 100_000:
            raise ValueError("Некорректное тело запроса")
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("Ожидается корректный JSON") from exc

    def _json_response(self, data: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, path: str) -> None:
        routes = {"/": ("index.html", "text/html; charset=utf-8"), "/styles.css": ("styles.css", "text/css; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8")}
        target = routes.get(path)
        if not target:
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return
        body = (STATIC_DIR / target[0]).read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", target[1])
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), OfficeFlowHandler)
    print(f"OfficeFlow запущен: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nСервер остановлен")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
