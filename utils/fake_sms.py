"""A fake SMS provider for the barbershop's outside suites.

The barbershop posts every text message to SMS_URL, as it would to a real
provider. Pointed here, the message is kept in memory instead of reaching a
phone, and a test reads the code out of it - the product has no hook for this
and needs none: it only knows it sent an SMS.

    python -m utils.fake_sms --port 8109

    POST /messages      {"to": "0501234567", "text": "..."}   what the product sends
    GET  /messages?to=  every message to that number, oldest first
    GET  /health
"""

from __future__ import annotations

import argparse
import itertools
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

_lock = threading.Lock()
_messages: list[dict] = []
_ids = itertools.count(1)


class Handler(BaseHTTPRequestHandler):
    def _answer(self, status: int, body: object | None = None) -> None:
        data = json.dumps(body, ensure_ascii=False).encode() if body is not None else b""
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/messages":
            return self._answer(404, {"detail": "not found"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            message = {"to": str(body["to"]), "text": str(body["text"])}
        except (ValueError, KeyError, TypeError):
            return self._answer(422, {"detail": "expected {to, text}"})
        with _lock:
            message.update(id=next(_ids), at=time.time())
            _messages.append(message)
        self._answer(202, {"id": message["id"]})

    def do_GET(self) -> None:
        url = urlparse(self.path)
        if url.path == "/health":
            return self._answer(200, {"status": "ok"})
        if url.path != "/messages":
            return self._answer(404, {"detail": "not found"})
        to = parse_qs(url.query).get("to", [None])[0]
        with _lock:
            found = [m for m in _messages if to is None or m["to"] == to]
        self._answer(200, found)

    def log_message(self, *_args) -> None:
        # Quiet: a run sends hundreds of codes, and the suite's own output is
        # where a failure is read.
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--port", type=int, default=8109)
    # 127.0.0.1 unless told otherwise: the codes in it sign people in. Only a
    # product in a container, reaching the host, needs it on every address.
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
