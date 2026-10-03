"""One real local HTTP server for the tests that stand in for a remote API.

``HTTPServer.shutdown`` waits out ``serve_forever``'s poll interval, 0.5s by
default, so a fixture that used the default paid half a second of teardown per
test. The interval is the only thing this module exists to set.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer

_POLL_SECONDS = 0.01


@contextmanager
def serving(handler: type[BaseHTTPRequestHandler]) -> Iterator[str]:
    """Serve ``handler`` on a free loopback port; yield its base URL."""
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": _POLL_SECONDS},
        daemon=True,
    )
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
