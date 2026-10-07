"""A fake push service for the barbershop's outside suites.

A browser's subscription is an address at its push service; the barbershop posts there, with a signed
header and no body, to say "there is news". A test subscribes with an address here instead of a
browser's, and reads what arrived - the product has no hook for it and needs none.

    python -m utils.fake_push --port 8110

    POST /push/<name>        what the product sends; answered 201, or what the test set with PUT /answer/<name>
    GET  /pushes/<name>      every post to that name, oldest first: its headers and the size of its body
    PUT  /answer/<name>/<n>  the status POST /push/<name> gives from now on (410: the subscription is gone)
    GET  /health
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

_lock = threading.Lock()
_posts: dict[str, list[dict]] = {}
_answers: dict[str, int] = {}


class Handler(BaseHTTPRequestHandler):
    def _answer(self, status: int, body: object | None = None) -> None:
        data = json.dumps(body).encode() if body is not None else b""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        parts = urlparse(self.path).path.strip("/").split("/")
        if len(parts) != 2 or parts[0] != "push":
            return self._answer(404)
        size = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(size) if size else b""
        with _lock:
            _posts.setdefault(parts[1], []).append(
                {
                    "headers": {k.lower(): v for k, v in self.headers.items()},
                    "body_size": len(body),
                    "at": time.time(),
                }
            )
            status = _answers.get(parts[1], 201)
        self._answer(status)

    def do_PUT(self) -> None:
        parts = urlparse(self.path).path.strip("/").split("/")
        if len(parts) != 3 or parts[0] != "answer":
            return self._answer(404)
        with _lock:
            _answers[parts[1]] = int(parts[2])
        self._answer(204)

    def do_GET(self) -> None:
        parts = urlparse(self.path).path.strip("/").split("/")
        if parts == ["health"]:
            return self._answer(200, {"status": "ok"})
        if len(parts) == 2 and parts[0] == "pushes":
            with _lock:
                return self._answer(200, list(_posts.get(parts[1], [])))
        self._answer(404)

    def log_message(self, *_args) -> None:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--port", type=int, default=8110)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
