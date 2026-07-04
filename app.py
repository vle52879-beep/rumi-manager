"""Vercel WSGI entrypoint for RUMI Manager.

The existing application logic remains in server.py. This adapter lets Vercel
run it as a Flask/Werkzeug function while public/ is served by Vercel's CDN.
"""
from __future__ import annotations

import html
import os
import threading
from io import BytesIO

from flask import Flask, Response, request

import server as core

app = Flask(__name__, static_folder=None)

_ready = False
_ready_lock = threading.Lock()


def _validate_runtime_config() -> None:
    if not core.SUPABASE_URL or "YOUR_PROJECT" in core.SUPABASE_URL:
        raise RuntimeError("Thiếu RUMI_SUPABASE_URL trong Vercel Environment Variables")
    if not core.SUPABASE_KEY or "YOUR_" in core.SUPABASE_KEY:
        raise RuntimeError("Thiếu RUMI_SUPABASE_SERVICE_ROLE_KEY trong Vercel Environment Variables")
    if core.SUPABASE_KEY.startswith("sb_publishable_") or core._legacy_jwt_role(core.SUPABASE_KEY) == "anon":
        raise RuntimeError("RUMI cần Supabase secret/service_role key, không dùng publishable/anon key")
    if core.ADMIN_PASSWORD == "Rumi@2026":
        raise RuntimeError("Triển khai online phải đặt RUMI_ADMIN_PASSWORD khác mật khẩu mặc định")


def _ensure_ready() -> None:
    global _ready
    if _ready:
        return
    with _ready_lock:
        if _ready:
            return
        _validate_runtime_config()
        core.SB.select(core.TABLES["users"], limit=1, columns="id")
        core.ensure_configured_admin()
        _ready = True


class InProcessRumiHandler(core.RumiHandler):
    """Runs the existing BaseHTTPRequestHandler without opening a TCP socket."""

    def __init__(self, method: str, path: str, headers, body: bytes, client_ip: str):
        self.command = method
        self.path = path
        self.headers = headers
        self.rfile = BytesIO(body)
        self.wfile = BytesIO()
        self.client_address = (client_ip or "0.0.0.0", 0)
        self.request_version = "HTTP/1.1"
        self._status = 200
        self._response_headers: list[tuple[str, str]] = []

    def send_response(self, code: int, message=None):
        self._status = int(code)

    def send_response_only(self, code: int, message=None):
        self._status = int(code)

    def send_header(self, keyword: str, value: str):
        self._response_headers.append((str(keyword), str(value)))

    def end_headers(self):
        return None

    def log_message(self, fmt, *args):
        return None


def _client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    return (forwarded.split(",", 1)[0].strip() if forwarded else request.remote_addr) or "0.0.0.0"


def _dispatch_core() -> Response:
    method = request.method.upper()
    body = request.get_data(cache=False) or b""
    handler = InProcessRumiHandler(method, request.full_path.rstrip("?") or request.path, request.headers, body, _client_ip())

    if method == "GET" or method == "HEAD":
        handler.do_GET()
    elif method == "POST":
        handler.do_POST()
    elif method == "PUT":
        handler.do_PUT()
    elif method == "DELETE":
        handler.do_DELETE()
    elif method == "OPTIONS":
        return Response(status=204, headers={"Allow": "GET, HEAD, POST, PUT, DELETE, OPTIONS"})
    else:
        return Response("Phương thức không được hỗ trợ", status=405, content_type="text/plain; charset=utf-8")

    payload = b"" if method == "HEAD" else handler.wfile.getvalue()
    excluded = {"content-length", "connection", "transfer-encoding", "server", "date"}
    headers = [(k, v) for k, v in handler._response_headers if k.lower() not in excluded]
    return Response(payload, status=handler._status, headers=headers)


def _public_origin() -> str:
    configured = (os.environ.get("RUMI_PUBLIC_URL") or "").strip().rstrip("/")
    return configured or request.url_root.rstrip("/")


@app.route("/robots.txt", methods=["GET", "HEAD"])
def robots():
    origin = _public_origin()
    text = f"User-agent: *\nAllow: /gioi-thieu\nDisallow: /api/\nDisallow: /\nSitemap: {origin}/sitemap.xml\n"
    return Response(text if request.method != "HEAD" else "", content_type="text/plain; charset=utf-8")


@app.route("/sitemap.xml", methods=["GET", "HEAD"])
def sitemap():
    origin = html.escape(_public_origin(), quote=True)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'  <url><loc>{origin}/gioi-thieu</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>\n'
        '</urlset>\n'
    )
    return Response(xml if request.method != "HEAD" else "", content_type="application/xml; charset=utf-8")


@app.route("/api", defaults={"path": ""}, methods=["GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS"])
@app.route("/api/<path:path>", methods=["GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS"])
def api(path: str):
    try:
        _ensure_ready()
    except Exception as exc:
        message = str(exc) or "Không thể khởi động RUMI trên Vercel"
        return Response(
            core.json.dumps({"ok": False, "message": message}, ensure_ascii=False),
            status=503,
            content_type="application/json; charset=utf-8",
            headers={"Cache-Control": "no-store"},
        )
    return _dispatch_core()


# Fallback for local Flask/vercel dev. In production, files in public/ are served
# directly by Vercel before this route is invoked.
@app.route("/", defaults={"path": ""}, methods=["GET", "HEAD"])
@app.route("/<path:path>", methods=["GET", "HEAD"])
def frontend(path: str):
    return _dispatch_core()
