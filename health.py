import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


def start_health_server(state: dict, port: int) -> None:
    """Serve GET /health as JSON from a shared state dict, in a background thread."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps(state).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = b"{}"
                self.send_response(404)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass  # keep stdout clean for the JSON logs

    server = HTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()