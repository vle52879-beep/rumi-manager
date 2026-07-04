#!/usr/bin/env python3
"""RUMI Manager v4.4 Vercel — fixed admin account, employee CRUD, roles, scheduling and GPS.

Python standard library only. The Supabase secret key stays in this backend and
is never sent to the browser. Every database object used by this app starts
with rumi_, so it can share the IC3 Smart Class Supabase project safely.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
ENV_FILES = [ROOT / ".env", ROOT / ".env.local"]
SESSION_COOKIE = "rumi_session"
SESSION_TTL = 12 * 60 * 60
PASSWORD_ITERATIONS = 210_000
LOGIN_ATTEMPTS: dict[str, list[float]] = defaultdict(list)

TABLES = {
    "employees": "rumi_employees",
    "users": "rumi_users",
    "locations": "rumi_locations",
    "settings": "rumi_settings",
    "availability": "rumi_availability_requests",
    "leaves": "rumi_leave_requests",
    "shift_changes": "rumi_shift_change_requests",
    "shifts": "rumi_shifts",
    "attendance": "rumi_attendance",
    "inventory": "rumi_inventory",
    "withdrawals": "rumi_withdrawals",
    "purchase_requests": "rumi_purchase_requests",
    "payroll_adjustments": "rumi_payroll_adjustments",
    "payroll_payments": "rumi_payroll_payments",
    "notifications": "rumi_notifications",
    "audit": "rumi_audit_logs",
}


def load_env() -> None:
    for path in ENV_FILES:
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


load_env()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def today_text() -> str:
    return date.today().isoformat()


def current_month() -> str:
    return datetime.now().strftime("%Y-%m")


def month_bounds(month: str) -> tuple[str, str]:
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise APIError("Tháng không hợp lệ")
    start = datetime.strptime(month + "-01", "%Y-%m-%d").date()
    end = date(start.year + (1 if start.month == 12 else 0), 1 if start.month == 12 else start.month + 1, 1)
    return start.isoformat(), end.isoformat()


def num(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def integer(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def parse_date(value: str, label: str = "Ngày") -> str:
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date().isoformat()
    except (TypeError, ValueError) as exc:
        raise APIError(f"{label} không hợp lệ") from exc


def parse_time(value: str, label: str = "Giờ") -> str:
    text = str(value or "")[:5]
    try:
        datetime.strptime(text, "%H:%M")
        return text
    except ValueError as exc:
        raise APIError(f"{label} không hợp lệ") from exc


def time_minutes(value: str) -> int:
    hour, minute = map(int, value[:5].split(":"))
    return hour * 60 + minute


def overlaps(start_a: str, end_a: str, start_b: str, end_b: str) -> bool:
    return time_minutes(start_a) < time_minutes(end_b) and time_minutes(end_a) > time_minutes(start_b)


def calculate_hours(check_in: str, check_out: str | None) -> float:
    if not check_in or not check_out:
        return 0.0
    seconds = (datetime.strptime(check_out[:5], "%H:%M") - datetime.strptime(check_in[:5], "%H:%M")).total_seconds()
    if seconds < 0:
        seconds += 86400
    return round(seconds / 3600, 2)


def normalize_time(value):
    if isinstance(value, str) and re.fullmatch(r"\d{2}:\d{2}:\d{2}(?:\.\d+)?", value):
        return value[:5]
    return value


def normalize_row(row: dict) -> dict:
    result = dict(row)
    for key in ("start_time", "end_time", "check_in", "check_out"):
        if key in result:
            result[key] = normalize_time(result[key])
    for key, value in list(result.items()):
        if isinstance(value, str) and key.endswith("_at") and len(value) > 19:
            result[key] = value
    return result


class APIError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class SupabaseError(APIError):
    pass


class SupabaseREST:
    def __init__(self, base_url: str, service_key: str):
        self.base_url = base_url.rstrip("/")
        self.service_key = service_key

    @property
    def project_host(self) -> str:
        return urlparse(self.base_url).netloc

    def request(self, method: str, resource: str, *, params: dict | None = None, body=None, prefer: str | None = None):
        query = ""
        if params:
            clean = [(k, str(v)) for k, v in params.items() if v is not None and v != ""]
            if clean:
                query = "?" + urlencode(clean, safe="(),.*:-")
        url = f"{self.base_url}/rest/v1/{resource}{query}"
        payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {
            "apikey": self.service_key,
            "Accept": "application/json",
            "User-Agent": "RUMI-Backend/4.4",
        }
        if self.service_key.startswith("eyJ"):
            headers["Authorization"] = f"Bearer {self.service_key}"
        if payload is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
        if prefer:
            headers["Prefer"] = prefer
        req = Request(url, data=payload, method=method, headers=headers)
        try:
            with urlopen(req, timeout=25) as response:
                raw = response.read()
                return json.loads(raw.decode("utf-8")) if raw else None
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(raw)
                message = detail.get("message") or detail.get("details") or raw
                code = detail.get("code", "")
            except json.JSONDecodeError:
                message, code = raw or str(exc), ""
            raise SupabaseError(self._friendly_error(message, code, exc.code), self._status(exc.code, code)) from exc
        except URLError as exc:
            raise SupabaseError("Không thể kết nối Supabase. Kiểm tra Internet, URL dự án và khóa bí mật trong file .env.", 503) from exc

    @staticmethod
    def _status(http_status: int, code: str) -> int:
        if code in {"23505", "23P01"}:
            return 409
        if code in {"23503", "23502", "23514", "P0001"}:
            return 400
        return http_status if 400 <= http_status <= 599 else 500

    @staticmethod
    def _friendly_error(message: str, code: str, http_status: int) -> str:
        text = str(message or "Lỗi cơ sở dữ liệu")
        lowered = text.lower()
        if code == "42P01" or "could not find the table" in lowered or ("relation" in lowered and "does not exist" in lowered):
            return "Chưa nâng cấp cơ sở dữ liệu RUMI v4. Hãy chạy file sql/SUPABASE_RUMI_V4_FULL.sql."
        if "could not find the function" in lowered:
            return "Chưa tạo hàm nghiệp vụ RUMI v4. Hãy chạy lại file SQL v4 trong Supabase."
        if code == "23505":
            if "username" in lowered:
                return "Tên đăng nhập đã tồn tại"
            if "code" in lowered:
                return "Mã nhân viên đã tồn tại"
            if "name" in lowered:
                return "Tên dữ liệu đã tồn tại"
            return "Dữ liệu bị trùng"
        if code == "23503":
            return "Không thể thao tác vì dữ liệu đang được sử dụng"
        if http_status in {401, 403}:
            return "Khóa Supabase không hợp lệ hoặc không đủ quyền. Hãy dùng secret/service_role key ở backend."
        return text

    def select(self, table: str, *, filters: dict | None = None, order: str = "", limit: int | None = None, columns: str = "*") -> list[dict]:
        params = {"select": columns}
        if filters:
            params.update(filters)
        if order:
            params["order"] = order
        if limit is not None:
            params["limit"] = limit
        data = self.request("GET", table, params=params)
        return [normalize_row(x) for x in (data or [])]

    def insert(self, table: str, body: dict) -> dict:
        data = self.request("POST", table, body=body, prefer="return=representation") or []
        return normalize_row(data[0]) if data else {}

    def upsert(self, table: str, body: dict, on_conflict: str) -> dict:
        data = self.request("POST", table, params={"on_conflict": on_conflict}, body=body, prefer="resolution=merge-duplicates,return=representation") or []
        return normalize_row(data[0]) if data else {}

    def update(self, table: str, body: dict, filters: dict) -> list[dict]:
        data = self.request("PATCH", table, params=filters, body=body, prefer="return=representation") or []
        return [normalize_row(x) for x in data]

    def delete(self, table: str, filters: dict) -> list[dict]:
        data = self.request("DELETE", table, params=filters, prefer="return=representation") or []
        return [normalize_row(x) for x in data]

    def rpc(self, function_name: str, body: dict):
        return self.request("POST", f"rpc/{function_name}", body=body)


def get_config() -> tuple[str, str]:
    url = (os.environ.get("RUMI_SUPABASE_URL") or os.environ.get("SUPABASE_URL") or os.environ.get("VITE_SUPABASE_URL") or "").strip()
    key = (os.environ.get("RUMI_SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("RUMI_SUPABASE_SECRET_KEY") or "").strip()
    return url, key


SUPABASE_URL, SUPABASE_KEY = get_config()
SB = SupabaseREST(SUPABASE_URL, SUPABASE_KEY)
SESSION_SECRET = hashlib.sha256((SUPABASE_KEY + "|RUMI_SESSION_V4_3").encode("utf-8")).digest()

ADMIN_USERNAME = (os.environ.get("RUMI_ADMIN_USERNAME") or "admin").strip().lower()
ADMIN_PASSWORD = os.environ.get("RUMI_ADMIN_PASSWORD") or "Rumi@2026"
ADMIN_DISPLAY_NAME = (os.environ.get("RUMI_ADMIN_NAME") or "Chủ cửa hàng RUMI").strip()
ADMIN_RESET_ON_START = str(os.environ.get("RUMI_ADMIN_RESET_ON_START", "0")).strip().lower() in {"1", "true", "yes", "on"}


def password_hash(password: str, salt_b64: str | None = None) -> tuple[str, str]:
    if salt_b64:
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
    else:
        salt = secrets.token_bytes(18)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return base64.urlsafe_b64encode(digest).decode("ascii"), base64.urlsafe_b64encode(salt).decode("ascii")


def verify_password(password: str, expected: str, salt: str) -> bool:
    actual, _ = password_hash(password, salt)
    return hmac.compare_digest(actual, expected)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def make_session(user_id: int) -> str:
    payload = b64url(json.dumps({"uid": user_id, "exp": int(time.time()) + SESSION_TTL, "nonce": secrets.token_hex(8)}, separators=(",", ":")).encode("utf-8"))
    signature = b64url(hmac.new(SESSION_SECRET, payload.encode("ascii"), hashlib.sha256).digest())
    return payload + "." + signature


def parse_session(token: str) -> int | None:
    try:
        payload, signature = token.split(".", 1)
        expected = b64url(hmac.new(SESSION_SECRET, payload.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        data = json.loads(b64url_decode(payload).decode("utf-8"))
        if integer(data.get("exp")) < int(time.time()):
            return None
        return integer(data.get("uid")) or None
    except Exception:
        return None


def public_user(user: dict, employee: dict | None = None) -> dict:
    employee = employee or {}
    return {
        "id": user.get("id"),
        "username": user.get("username"),
        "role": user.get("role"),
        "employee_id": user.get("employee_id"),
        "name": employee.get("name") or (ADMIN_DISPLAY_NAME if user.get("role") == "admin" else user.get("username")),
        "employee_code": employee.get("code"),
        "job_role": employee.get("role"),
    }


def employee_map(rows: list[dict]) -> dict[int, dict]:
    return {integer(row.get("id")): row for row in rows}


def location_map(rows: list[dict]) -> dict[int, dict]:
    return {integer(row.get("id")): row for row in rows}


def add_people(rows: list[dict], employees: list[dict], key: str = "employee_id") -> list[dict]:
    mapping = employee_map(employees)
    output = []
    for row in rows:
        item = dict(row)
        employee = mapping.get(integer(item.get(key)), {})
        item["employee_name"] = employee.get("name")
        item["employee_code"] = employee.get("code")
        item["employee_role"] = employee.get("role")
        output.append(item)
    return output


class RumiHandler(BaseHTTPRequestHandler):
    server_version = "RUMI/4.4"

    def log_message(self, fmt, *args):
        sys.stdout.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def send_json(self, payload, status=200, extra_headers: dict | None = None):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def ok(self, data=None, message="Thành công", *, headers=None):
        self.send_json({"ok": True, "message": message, "data": data}, 200, headers)

    def fail(self, message, status=400):
        self.send_json({"ok": False, "message": message}, status)

    def parse_json(self) -> dict:
        length = integer(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        if length > 1_000_000:
            raise APIError("Dữ liệu gửi lên quá lớn", 413)
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(value, dict):
                raise APIError("Dữ liệu JSON phải là một đối tượng")
            return value
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise APIError("Dữ liệu JSON không hợp lệ") from exc

    def cookie_value(self, name: str) -> str:
        jar = cookies.SimpleCookie()
        try:
            jar.load(self.headers.get("Cookie", ""))
            return jar[name].value if name in jar else ""
        except cookies.CookieError:
            return ""

    def session_header(self, token: str, max_age: int = SESSION_TTL) -> str:
        secure = self.headers.get("X-Forwarded-Proto", "").lower() == "https"
        parts = [f"{SESSION_COOKIE}={token}", "Path=/", "HttpOnly", "SameSite=Lax", f"Max-Age={max_age}"]
        if secure:
            parts.append("Secure")
        return "; ".join(parts)

    def current_user(self, required: bool = True) -> dict | None:
        user_id = parse_session(self.cookie_value(SESSION_COOKIE))
        if not user_id:
            if required:
                raise APIError("Phiên đăng nhập đã hết hạn", 401)
            return None
        users = SB.select(TABLES["users"], filters={"id": f"eq.{user_id}", "active": "eq.true"}, limit=1)
        if not users:
            if required:
                raise APIError("Tài khoản không còn hoạt động", 401)
            return None
        user = users[0]
        employee = None
        if user.get("employee_id"):
            rows = SB.select(TABLES["employees"], filters={"id": f"eq.{user['employee_id']}"}, limit=1)
            employee = rows[0] if rows else None
            if user.get("role") == "employee" and (not employee or employee.get("status") != "Đang làm"):
                raise APIError("Tài khoản nhân viên đã bị khóa", 403)
        user["profile"] = public_user(user, employee)
        user["employee"] = employee
        return user

    @staticmethod
    def require_role(user: dict, role: str):
        if user.get("role") != role:
            raise APIError("Bạn không có quyền thực hiện thao tác này", 403)

    def require_csrf(self):
        if self.headers.get("X-RUMI-Request") != "1":
            raise APIError("Yêu cầu không hợp lệ", 403)

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/"):
                self.handle_api_get(parsed.path, parse_qs(parsed.query))
            else:
                self.serve_static(parsed.path)
        except APIError as exc:
            self.fail(str(exc), exc.status)
        except Exception as exc:
            print("GET error:", repr(exc))
            self.fail("Máy chủ gặp lỗi khi xử lý yêu cầu", 500)

    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            if not parsed.path.startswith("/api/"):
                raise APIError("Không tìm thấy đường dẫn", 404)
            self.handle_api_post(parsed.path, self.parse_json())
        except APIError as exc:
            self.fail(str(exc), exc.status)
        except Exception as exc:
            print("POST error:", repr(exc))
            self.fail("Máy chủ gặp lỗi khi lưu dữ liệu", 500)

    def do_PUT(self):
        try:
            parsed = urlparse(self.path)
            self.handle_api_put(parsed.path, self.parse_json())
        except APIError as exc:
            self.fail(str(exc), exc.status)
        except Exception as exc:
            print("PUT error:", repr(exc))
            self.fail("Máy chủ gặp lỗi khi cập nhật dữ liệu", 500)

    def do_DELETE(self):
        try:
            self.handle_api_delete(urlparse(self.path).path)
        except APIError as exc:
            self.fail(str(exc), exc.status)
        except Exception as exc:
            print("DELETE error:", repr(exc))
            self.fail("Máy chủ gặp lỗi khi xoá dữ liệu", 500)

    def serve_static(self, url_path: str):
        public_url = (os.environ.get("RUMI_PUBLIC_URL") or "").rstrip("/")
        if url_path == "/robots.txt":
            sitemap = f"\nSitemap: {public_url}/sitemap.xml" if public_url else ""
            content = ("User-agent: *\nAllow: /gioi-thieu\nDisallow: /api/\nDisallow: /\n" + sitemap + "\n").encode("utf-8")
            mime = "text/plain"
        elif url_path == "/sitemap.xml":
            loc = f"{public_url}/gioi-thieu" if public_url else "/gioi-thieu"
            xml = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                f'  <url><loc>{loc}</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>\n'
                '</urlset>\n'
            )
            content = xml.encode("utf-8")
            mime = "application/xml"
        else:
            if url_path in ("", "/"):
                file_path = STATIC_DIR / "index.html"
            elif url_path.rstrip("/") == "/gioi-thieu":
                file_path = STATIC_DIR / "landing.html"
            else:
                relative = unquote(url_path.lstrip("/"))
                file_path = (STATIC_DIR / relative).resolve()
                if STATIC_DIR.resolve() not in file_path.parents:
                    raise APIError("Đường dẫn không hợp lệ", 403)
                if not file_path.exists() or not file_path.is_file():
                    file_path = STATIC_DIR / "index.html"
            content = file_path.read_bytes()
            mime = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        self.send_response(200)
        text_mime = mime.startswith("text/") or mime in {"application/javascript", "application/xml"}
        self.send_header("Content-Type", f"{mime}; charset=utf-8" if text_mime else mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.end_headers()
        self.wfile.write(content)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def audit(self, user: dict, action: str, entity_type: str, entity_id="", detail: dict | None = None):
        try:
            SB.insert(TABLES["audit"], {
                "user_id": user.get("id"),
                "action": action,
                "entity_type": entity_type,
                "entity_id": str(entity_id or ""),
                "detail": detail or {},
            })
        except Exception as exc:
            print("Audit warning:", repr(exc))

    def notify_employee(self, employee_id: int, title: str, message: str, type_: str = "info", link: str = ""):
        SB.insert(TABLES["notifications"], {
            "employee_id": employee_id,
            "title": title,
            "message": message,
            "type": type_,
            "link": link,
        })

    def notify_role(self, role: str, title: str, message: str, type_: str = "info", link: str = ""):
        SB.insert(TABLES["notifications"], {
            "audience_role": role,
            "title": title,
            "message": message,
            "type": type_,
            "link": link,
        })

    def enriched_shifts(self, shifts: list[dict]) -> list[dict]:
        employees = SB.select(TABLES["employees"])
        locations = SB.select(TABLES["locations"])
        attendance = SB.select(TABLES["attendance"])
        e_map, l_map = employee_map(employees), location_map(locations)
        a_map = {integer(row.get("shift_id")): row for row in attendance if row.get("shift_id")}
        output = []
        for row in shifts:
            item = dict(row)
            employee = e_map.get(integer(item.get("employee_id")), {})
            location = l_map.get(integer(item.get("location_id")), {})
            att = a_map.get(integer(item.get("id")), {})
            item.update({
                "employee_name": employee.get("name"),
                "employee_code": employee.get("code"),
                "employee_role": employee.get("role"),
                "location_name": location.get("name"),
                "location_address": location.get("address"),
                "location_radius_m": location.get("radius_m"),
                "attendance": att or None,
            })
            output.append(item)
        return output

    def candidate_rows(self, work_date: str, start: str, end: str, exclude_employee_id: int = 0, ignore_shift_id: int = 0) -> list[dict]:
        employees = SB.select(TABLES["employees"], filters={"status": "eq.Đang làm"}, order="name.asc")
        shifts = SB.select(TABLES["shifts"], filters={"shift_date": f"eq.{work_date}"})
        leaves = SB.select(TABLES["leaves"], filters={"status": "eq.Đã duyệt"})
        availability = SB.select(TABLES["availability"], filters={"work_date": f"eq.{work_date}"})
        output = []
        for employee in employees:
            eid = integer(employee.get("id"))
            if eid == exclude_employee_id:
                continue
            approved = [a for a in availability if integer(a.get("employee_id")) == eid and a.get("status") in {"Đã duyệt", "Đã xếp ca"} and time_minutes(a["start_time"]) <= time_minutes(start) and time_minutes(a["end_time"]) >= time_minutes(end)]
            busy = [s for s in shifts if integer(s.get("employee_id")) == eid and integer(s.get("id")) != ignore_shift_id and s.get("status") in {"Đã xếp", "Đã xác nhận"} and overlaps(s["start_time"], s["end_time"], start, end)]
            on_leave = any(integer(l.get("employee_id")) == eid and l.get("start_date") <= work_date <= l.get("end_date") for l in leaves)
            if on_leave:
                state, reason = "on_leave", "Đang nghỉ phép"
            elif busy:
                state, reason = "busy", f"Trùng ca {busy[0]['start_time']}–{busy[0]['end_time']}"
            elif not approved:
                state, reason = "unregistered", "Chưa đăng ký rảnh"
            else:
                state, reason = "available", "Rảnh và đã được duyệt"
            output.append({
                "employee_id": eid,
                "code": employee.get("code"),
                "name": employee.get("name"),
                "role": employee.get("role"),
                "state": state,
                "reason": reason,
                "availability_id": approved[0].get("id") if approved else None,
            })
        output.sort(key=lambda x: ({"available": 0, "unregistered": 1, "busy": 2, "on_leave": 3}.get(x["state"], 9), x["name"] or ""))
        return output

    def build_payroll(self, month: str, employee_id: int | None = None) -> list[dict]:
        start, end = month_bounds(month)
        filters = {"status": "eq.Đang làm"}
        if employee_id:
            filters["id"] = f"eq.{employee_id}"
        employees = SB.select(TABLES["employees"], filters=filters, order="name.asc")
        attendance = SB.select(TABLES["attendance"], filters={"work_date": f"gte.{start}", "and": f"(work_date.lt.{end})"})
        adjustments = SB.select(TABLES["payroll_adjustments"], filters={"month": f"eq.{month}"})
        payments = SB.select(TABLES["payroll_payments"], filters={"month": f"eq.{month}"})
        hours_by_employee: dict[int, float] = defaultdict(float)
        for row in attendance:
            hours_by_employee[integer(row["employee_id"])] += num(row.get("hours"))
        adj_map = {integer(x["employee_id"]): x for x in adjustments}
        pay_map = {integer(x["employee_id"]): x for x in payments}
        output = []
        for employee in employees:
            eid = integer(employee["id"])
            hours = round(hours_by_employee.get(eid, 0), 2)
            adjustment = adj_map.get(eid, {})
            payment = pay_map.get(eid, {})
            bonus = num(adjustment.get("bonus"))
            penalty = num(adjustment.get("penalty"))
            advance = num(adjustment.get("advance_pay"))
            total = round(hours * num(employee.get("hourly_wage")) + bonus - penalty - advance)
            output.append({
                "employee_id": eid,
                "code": employee.get("code"),
                "name": employee.get("name"),
                "role": employee.get("role"),
                "hourly_wage": num(employee.get("hourly_wage")),
                "hours": hours,
                "bonus": bonus,
                "penalty": penalty,
                "advance_pay": advance,
                "note": adjustment.get("note", ""),
                "payment_status": payment.get("status", "Chưa thanh toán"),
                "paid_at": payment.get("paid_at"),
                "total": total,
            })
        return output

    def build_dashboard(self, user: dict) -> dict:
        role = user.get("role")
        today = today_text()
        month = current_month()
        notifications = self.get_notifications(user)
        if role == "admin":
            employees = SB.select(TABLES["employees"], filters={"status": "eq.Đang làm"})
            shifts_today = self.enriched_shifts(SB.select(TABLES["shifts"], filters={"shift_date": f"eq.{today}"}, order="start_time.asc"))
            attendance_today = SB.select(TABLES["attendance"], filters={"work_date": f"eq.{today}"})
            availability = SB.select(TABLES["availability"], filters={"status": "eq.Chờ duyệt"})
            leaves = SB.select(TABLES["leaves"], filters={"status": "eq.Chờ duyệt"})
            changes = SB.select(TABLES["shift_changes"], filters={"status": "eq.Chờ xử lý"})
            inventory = SB.select(TABLES["inventory"])
            purchases = SB.select(TABLES["purchase_requests"], filters={"status": "eq.Chờ mua"})
            payroll = self.build_payroll(month)
            return {
                "role": role,
                "stats": {
                    "employees": len(employees),
                    "shifts_today": len(shifts_today),
                    "working_now": len([x for x in attendance_today if x.get("status") == "Đang làm"]),
                    "pending_schedule": len(availability),
                    "pending_requests": len(leaves) + len(changes),
                    "low_stock": len([x for x in inventory if num(x.get("quantity")) <= num(x.get("min_stock"))]),
                    "pending_purchase": len(purchases),
                    "payroll_total": sum(num(x.get("total")) for x in payroll),
                },
                "today_shifts": shifts_today,
                "notifications": notifications[:6],
            }
        employee_id = integer(user.get("employee_id"))
        shifts = SB.select(TABLES["shifts"], filters={"employee_id": f"eq.{employee_id}", "shift_date": f"gte.{today}"}, order="shift_date.asc,start_time.asc", limit=20)
        shifts = self.enriched_shifts(shifts)
        attendance = SB.select(TABLES["attendance"], filters={"employee_id": f"eq.{employee_id}"})
        month_hours = sum(num(x.get("hours")) for x in attendance if str(x.get("work_date", "")).startswith(month))
        pending_availability = SB.select(TABLES["availability"], filters={"employee_id": f"eq.{employee_id}", "status": "eq.Chờ duyệt"})
        pending_changes = SB.select(TABLES["shift_changes"], filters={"requester_id": f"eq.{employee_id}", "status": "eq.Chờ xử lý"})
        payroll = self.build_payroll(month, employee_id)
        return {
            "role": role,
            "stats": {
                "upcoming_shifts": len(shifts),
                "month_hours": round(month_hours, 2),
                "pending_requests": len(pending_availability) + len(pending_changes),
                "unread_notifications": len([x for x in notifications if not x.get("read_at")]),
                "estimated_salary": payroll[0]["total"] if payroll else 0,
            },
            "today_shifts": [x for x in shifts if x.get("shift_date") == today],
            "upcoming_shifts": shifts[:6],
            "notifications": notifications[:6],
        }

    def get_notifications(self, user: dict) -> list[dict]:
        rows = SB.select(TABLES["notifications"], order="created_at.desc", limit=300)
        eid = integer(user.get("employee_id"))
        role = user.get("role")
        filtered = [x for x in rows if (eid and integer(x.get("employee_id")) == eid) or x.get("audience_role") == role]
        return filtered[:100]

    # ------------------------------------------------------------------
    # GET routes
    # ------------------------------------------------------------------
    def handle_api_get(self, path: str, query: dict):
        if path == "/api/health":
            SB.select(TABLES["employees"], limit=1, columns="id")
            return self.ok({"database": "Supabase/PostgreSQL", "project": SB.project_host, "table_prefix": "rumi_", "version": "5.0", "time": now_iso()})

        if path == "/api/setup/status":
            return self.ok({"needs_setup": False, "admin_configured": True})

        user = self.current_user()

        if path == "/api/auth/me":
            return self.ok(user["profile"])

        if path == "/api/dashboard":
            return self.ok(self.build_dashboard(user))

        if path == "/api/notifications":
            return self.ok(self.get_notifications(user))

        if path == "/api/employees/public":
            rows = SB.select(TABLES["employees"], filters={"status": "eq.Đang làm"}, order="name.asc", columns="id,code,name,role")
            return self.ok(rows)

        if path == "/api/employees":
            self.require_role(user, "admin")
            employees = SB.select(TABLES["employees"], order="status.desc,name.asc")
            users = SB.select(TABLES["users"])
            u_map = {integer(x.get("employee_id")): x for x in users if x.get("employee_id")}
            for employee in employees:
                account = u_map.get(integer(employee.get("id")), {})
                employee["username"] = account.get("username")
                employee["account_active"] = account.get("active", False)
            return self.ok(employees)

        if path == "/api/locations":
            filters = {} if user.get("role") == "admin" else {"active": "eq.true"}
            return self.ok(SB.select(TABLES["locations"], filters=filters, order="active.desc,name.asc"))

        if path == "/api/settings":
            rows = SB.select(TABLES["settings"], filters={"id": "eq.1"}, limit=1)
            return self.ok(rows[0] if rows else {})

        if path == "/api/availability":
            filters = {}
            if user.get("role") == "employee":
                filters["employee_id"] = f"eq.{user['employee_id']}"
            start = query.get("start", [""])[0]
            end = query.get("end", [""])[0]
            if start:
                filters["work_date"] = f"gte.{start}"
            if end:
                filters["and"] = f"(work_date.lte.{end})"
            rows = SB.select(TABLES["availability"], filters=filters, order="work_date.desc,start_time.asc")
            return self.ok(add_people(rows, SB.select(TABLES["employees"])))

        if path == "/api/leaves":
            filters = {}
            if user.get("role") == "employee":
                filters["employee_id"] = f"eq.{user['employee_id']}"
            rows = SB.select(TABLES["leaves"], filters=filters, order="created_at.desc")
            return self.ok(add_people(rows, SB.select(TABLES["employees"])))

        if path == "/api/shift-change-requests":
            filters = {}
            if user.get("role") == "employee":
                filters["requester_id"] = f"eq.{user['employee_id']}"
            rows = SB.select(TABLES["shift_changes"], filters=filters, order="created_at.desc")
            employees = SB.select(TABLES["employees"])
            shifts = {integer(x["id"]): x for x in self.enriched_shifts(SB.select(TABLES["shifts"]))}
            e_map = employee_map(employees)
            output = []
            for row in rows:
                item = dict(row)
                requester = e_map.get(integer(item.get("requester_id")), {})
                replacement = e_map.get(integer(item.get("replacement_employee_id")), {})
                item["employee_name"] = requester.get("name")
                item["replacement_name"] = replacement.get("name")
                item["shift"] = shifts.get(integer(item.get("shift_id")))
                output.append(item)
            return self.ok(output)

        if path == "/api/shifts":
            filters = {}
            if user.get("role") == "employee":
                filters["employee_id"] = f"eq.{user['employee_id']}"
            start = query.get("start", [""])[0]
            end = query.get("end", [""])[0]
            if start:
                filters["shift_date"] = f"gte.{start}"
            if end:
                filters["and"] = f"(shift_date.lte.{end})"
            shifts = SB.select(TABLES["shifts"], filters=filters, order="shift_date.desc,start_time.asc")
            return self.ok(self.enriched_shifts(shifts))

        if path == "/api/scheduling/candidates":
            self.require_role(user, "admin")
            work_date = parse_date(query.get("date", [""])[0])
            start = parse_time(query.get("start", [""])[0], "Giờ bắt đầu")
            end = parse_time(query.get("end", [""])[0], "Giờ kết thúc")
            if time_minutes(end) <= time_minutes(start):
                raise APIError("Giờ kết thúc phải sau giờ bắt đầu")
            exclude = integer(query.get("exclude_employee_id", ["0"])[0])
            ignore_shift = integer(query.get("ignore_shift_id", ["0"])[0])
            return self.ok(self.candidate_rows(work_date, start, end, exclude, ignore_shift))

        if path == "/api/attendance/today":
            self.require_role(user, "employee")
            shifts = SB.select(TABLES["shifts"], filters={"employee_id": f"eq.{user['employee_id']}", "shift_date": f"eq.{today_text()}"}, order="start_time.asc")
            return self.ok(self.enriched_shifts(shifts))

        if path == "/api/attendance":
            month = query.get("month", [current_month()])[0]
            start, end = month_bounds(month)
            filters = {"work_date": f"gte.{start}", "and": f"(work_date.lt.{end})"}
            if user.get("role") == "employee":
                filters["employee_id"] = f"eq.{user['employee_id']}"
            rows = SB.select(TABLES["attendance"], filters=filters, order="work_date.desc,check_in.desc")
            employees = SB.select(TABLES["employees"])
            shifts = {integer(x["id"]): x for x in self.enriched_shifts(SB.select(TABLES["shifts"]))}
            output = add_people(rows, employees)
            for item in output:
                item["shift"] = shifts.get(integer(item.get("shift_id")))
            return self.ok(output)

        if path == "/api/payroll":
            month = query.get("month", [current_month()])[0]
            employee_id = integer(user.get("employee_id")) if user.get("role") == "employee" else None
            return self.ok(self.build_payroll(month, employee_id))

        if path == "/api/inventory":
            rows = SB.select(TABLES["inventory"], order="category.asc,name.asc")
            rows.sort(key=lambda x: (0 if num(x.get("quantity")) <= num(x.get("min_stock")) else 1, str(x.get("category")), str(x.get("name"))))
            return self.ok(rows)

        if path == "/api/withdrawals":
            filters = {}
            if user.get("role") == "employee":
                filters["employee_id"] = f"eq.{user['employee_id']}"
            rows = SB.select(TABLES["withdrawals"], filters=filters, order="taken_at.desc,id.desc", limit=300)
            employees = employee_map(SB.select(TABLES["employees"]))
            inventory = {integer(x["id"]): x for x in SB.select(TABLES["inventory"])}
            for item in rows:
                inv = inventory.get(integer(item.get("inventory_id")), {})
                emp = employees.get(integer(item.get("employee_id")), {})
                item["item_name"] = inv.get("name", "Nguyên liệu")
                item["unit"] = inv.get("unit", "")
                item["employee_name"] = emp.get("name")
            return self.ok(rows)

        if path == "/api/purchase-requests":
            filters = {}
            if user.get("role") == "employee":
                filters["requester_employee_id"] = f"eq.{user['employee_id']}"
            rows = SB.select(TABLES["purchase_requests"], filters=filters, order="id.desc")
            rows.sort(key=lambda x: (0 if x.get("status") == "Chờ mua" else 1, 0 if x.get("priority") == "Gấp" else 1, -integer(x.get("id"))))
            return self.ok(rows)

        if path == "/api/reports":
            self.require_role(user, "admin")
            month = query.get("month", [current_month()])[0]
            payroll = self.build_payroll(month)
            attendance = SB.select(TABLES["attendance"], filters={"work_date": f"gte.{month}-01"})
            employees = SB.select(TABLES["employees"], filters={"status": "eq.Đang làm"})
            return self.ok({
                "month": month,
                "employee_count": len(employees),
                "total_hours": round(sum(num(x.get("hours")) for x in attendance if str(x.get("work_date", "")).startswith(month)), 2),
                "total_payroll": sum(num(x.get("total")) for x in payroll),
                "paid_payroll": sum(num(x.get("total")) for x in payroll if x.get("payment_status") == "Đã thanh toán"),
                "payroll": payroll,
            })

        if path == "/api/audit":
            self.require_role(user, "admin")
            rows = SB.select(TABLES["audit"], order="created_at.desc", limit=200)
            users = {integer(x["id"]): x for x in SB.select(TABLES["users"])}
            for row in rows:
                row["username"] = users.get(integer(row.get("user_id")), {}).get("username", "Hệ thống")
            return self.ok(rows)

        raise APIError("Không tìm thấy API", 404)

    # ------------------------------------------------------------------
    # POST routes
    # ------------------------------------------------------------------
    def handle_api_post(self, path: str, body: dict):
        if path == "/api/setup/admin":
            raise APIError("Không cho phép tự tạo tài khoản admin. Admin đã được cấu hình sẵn trên máy chủ.", 403)

        if path == "/api/auth/login":
            ip = self.client_address[0]
            now = time.time()
            LOGIN_ATTEMPTS[ip] = [x for x in LOGIN_ATTEMPTS[ip] if now - x < 600]
            if len(LOGIN_ATTEMPTS[ip]) >= 8:
                raise APIError("Đăng nhập sai quá nhiều lần. Vui lòng thử lại sau.", 429)
            username = str(body.get("username", "")).strip().lower()
            password = str(body.get("password", ""))
            users = SB.select(TABLES["users"], filters={"username": f"eq.{username}"}, limit=1)
            if not users or not users[0].get("active") or not verify_password(password, users[0].get("password_hash", ""), users[0].get("password_salt", "")):
                LOGIN_ATTEMPTS[ip].append(now)
                raise APIError("Tên đăng nhập hoặc mật khẩu không đúng", 401)
            user = users[0]
            employee = None
            if user.get("employee_id"):
                rows = SB.select(TABLES["employees"], filters={"id": f"eq.{user['employee_id']}"}, limit=1)
                employee = rows[0] if rows else None
                if user.get("role") == "employee" and (not employee or employee.get("status") != "Đang làm"):
                    raise APIError("Tài khoản nhân viên đã bị khóa", 403)
            SB.update(TABLES["users"], {"last_login_at": now_iso()}, {"id": f"eq.{user['id']}"})
            LOGIN_ATTEMPTS[ip].clear()
            token = make_session(integer(user["id"]))
            return self.ok(public_user(user, employee), "Đăng nhập thành công", headers={"Set-Cookie": self.session_header(token)})

        if path == "/api/auth/logout":
            return self.ok(None, "Đã đăng xuất", headers={"Set-Cookie": self.session_header("", 0)})

        user = self.current_user()
        self.require_csrf()

        if path == "/api/auth/change-password":
            old_password = str(body.get("old_password", ""))
            new_password = str(body.get("new_password", ""))
            if len(new_password) < 8:
                raise APIError("Mật khẩu mới phải có ít nhất 8 ký tự")
            if not verify_password(old_password, user.get("password_hash", ""), user.get("password_salt", "")):
                raise APIError("Mật khẩu hiện tại không đúng")
            hashed, salt = password_hash(new_password)
            SB.update(TABLES["users"], {"password_hash": hashed, "password_salt": salt}, {"id": f"eq.{user['id']}"})
            self.audit(user, "change_password", "user", user["id"])
            return self.ok(None, "Đã đổi mật khẩu")

        if path == "/api/notifications/read":
            notification_id = integer(body.get("id"))
            rows = self.get_notifications(user)
            allowed = {integer(x.get("id")) for x in rows}
            if notification_id:
                if notification_id not in allowed:
                    raise APIError("Không tìm thấy thông báo", 404)
                SB.update(TABLES["notifications"], {"read_at": now_iso()}, {"id": f"eq.{notification_id}"})
            else:
                for row in rows:
                    if not row.get("read_at"):
                        SB.update(TABLES["notifications"], {"read_at": now_iso()}, {"id": f"eq.{row['id']}"})
            return self.ok(None, "Đã đánh dấu đã đọc")

        if path == "/api/employees":
            self.require_role(user, "admin")
            code = str(body.get("code", "")).strip().upper()
            name = str(body.get("name", "")).strip()
            username = str(body.get("username", "")).strip().lower()
            password = str(body.get("password", ""))
            if not code or len(name) < 2 or not re.fullmatch(r"[a-z0-9._-]{3,40}", username) or len(password) < 8:
                raise APIError("Vui lòng nhập đủ mã, họ tên, tên đăng nhập và mật khẩu ít nhất 8 ký tự")
            employee = SB.insert(TABLES["employees"], {
                "code": code,
                "name": name,
                "phone": str(body.get("phone", "")).strip(),
                "email": str(body.get("email", "")).strip(),
                "role": str(body.get("job_role", "Nhân viên")).strip(),
                "hourly_wage": num(body.get("hourly_wage"), 25000),
                "status": "Đang làm",
                "joined_at": body.get("joined_at") or today_text(),
            })
            try:
                hashed, salt = password_hash(password)
                SB.insert(TABLES["users"], {
                    "username": username,
                    "password_hash": hashed,
                    "password_salt": salt,
                    "role": "employee",
                    "employee_id": employee["id"],
                    "active": True,
                })
            except Exception:
                SB.delete(TABLES["employees"], {"id": f"eq.{employee['id']}"})
                raise
            self.audit(user, "create", "employee", employee["id"], {"code": code, "name": name})
            return self.ok(employee, "Đã thêm nhân viên và tạo tài khoản")

        reset_match = re.fullmatch(r"/api/employees/(\d+)/reset-password", path)
        if reset_match:
            self.require_role(user, "admin")
            employee_id = integer(reset_match.group(1))
            new_password = str(body.get("password", ""))
            if len(new_password) < 8:
                raise APIError("Mật khẩu mới phải có ít nhất 8 ký tự")
            hashed, salt = password_hash(new_password)
            rows = SB.update(TABLES["users"], {"password_hash": hashed, "password_salt": salt}, {"employee_id": f"eq.{employee_id}"})
            if not rows:
                raise APIError("Nhân viên chưa có tài khoản", 404)
            self.audit(user, "reset_password", "employee", employee_id)
            return self.ok(None, "Đã đặt lại mật khẩu")

        if path == "/api/locations":
            self.require_role(user, "admin")
            name = str(body.get("name", "")).strip()
            lat, lng = num(body.get("latitude"), 999), num(body.get("longitude"), 999)
            radius = integer(body.get("radius_m"), 100)
            if not name or not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                raise APIError("Tên hoặc tọa độ cửa hàng không hợp lệ")
            row = SB.insert(TABLES["locations"], {"name": name, "address": str(body.get("address", "")).strip(), "latitude": lat, "longitude": lng, "radius_m": radius, "active": True})
            self.audit(user, "create", "location", row["id"], {"name": name})
            return self.ok(row, "Đã thêm vị trí cửa hàng")

        if path == "/api/availability":
            self.require_role(user, "employee")
            work_date = parse_date(body.get("work_date"), "Ngày đăng ký")
            start = parse_time(body.get("start_time"), "Giờ bắt đầu")
            end = parse_time(body.get("end_time"), "Giờ kết thúc")
            if work_date < today_text() or time_minutes(end) <= time_minutes(start):
                raise APIError("Ngày hoặc khung giờ đăng ký không hợp lệ")
            row = SB.insert(TABLES["availability"], {"employee_id": user["employee_id"], "work_date": work_date, "start_time": start, "end_time": end, "note": str(body.get("note", "")).strip(), "status": "Chờ duyệt"})
            self.notify_role("admin", "Có lịch rảnh mới", f"{user['profile']['name']} đăng ký rảnh ngày {work_date}, {start}–{end}.", "schedule", "requests")
            self.audit(user, "create", "availability", row["id"])
            return self.ok(row, "Đã gửi lịch rảnh cho quản lý")

        if path == "/api/availability/status":
            self.require_role(user, "admin")
            request_id = integer(body.get("id"))
            status = str(body.get("status", ""))
            if status not in {"Đã duyệt", "Từ chối"}:
                raise APIError("Trạng thái không hợp lệ")
            current = SB.select(TABLES["availability"], filters={"id": f"eq.{request_id}"}, limit=1)
            if not current:
                raise APIError("Không tìm thấy đăng ký lịch", 404)
            rows = SB.update(TABLES["availability"], {"status": status, "admin_note": str(body.get("admin_note", "")).strip(), "reviewed_at": now_iso()}, {"id": f"eq.{request_id}"})
            item = rows[0]
            self.notify_employee(integer(item["employee_id"]), "Lịch rảnh đã được xử lý", f"Đăng ký ngày {item['work_date']} đã được {status.lower()}.", "schedule", "availability")
            self.audit(user, "review", "availability", request_id, {"status": status})
            return self.ok(item, "Đã xử lý đăng ký lịch")

        if path == "/api/leaves":
            self.require_role(user, "employee")
            start_date = parse_date(body.get("start_date"), "Ngày bắt đầu")
            end_date = parse_date(body.get("end_date"), "Ngày kết thúc")
            reason = str(body.get("reason", "")).strip()
            if start_date < today_text() or end_date < start_date or not reason:
                raise APIError("Thời gian nghỉ hoặc lý do chưa hợp lệ")
            row = SB.insert(TABLES["leaves"], {"employee_id": user["employee_id"], "start_date": start_date, "end_date": end_date, "reason": reason, "status": "Chờ duyệt"})
            self.notify_role("admin", "Có đơn xin nghỉ", f"{user['profile']['name']} xin nghỉ từ {start_date} đến {end_date}.", "leave", "requests")
            self.audit(user, "create", "leave", row["id"])
            return self.ok(row, "Đã gửi đơn xin nghỉ")

        if path == "/api/leaves/status":
            self.require_role(user, "admin")
            request_id = integer(body.get("id"))
            status = str(body.get("status", ""))
            if status not in {"Đã duyệt", "Từ chối"}:
                raise APIError("Trạng thái không hợp lệ")
            current = SB.select(TABLES["leaves"], filters={"id": f"eq.{request_id}"}, limit=1)
            if not current:
                raise APIError("Không tìm thấy đơn nghỉ", 404)
            item = SB.update(TABLES["leaves"], {"status": status, "admin_note": str(body.get("admin_note", "")).strip(), "reviewed_at": now_iso()}, {"id": f"eq.{request_id}"})[0]
            self.notify_employee(integer(item["employee_id"]), "Đơn nghỉ đã được xử lý", f"Đơn nghỉ {item['start_date']}–{item['end_date']} đã được {status.lower()}.", "leave", "requests")
            self.audit(user, "review", "leave", request_id, {"status": status})
            return self.ok(item, "Đã xử lý đơn nghỉ")

        if path == "/api/shifts":
            self.require_role(user, "admin")
            employee_id = integer(body.get("employee_id"))
            location_id = integer(body.get("location_id"))
            work_date = parse_date(body.get("shift_date"), "Ngày làm")
            start = parse_time(body.get("start_time"), "Giờ bắt đầu")
            end = parse_time(body.get("end_time"), "Giờ kết thúc")
            force = bool(body.get("force"))
            if not employee_id or not location_id or time_minutes(end) <= time_minutes(start):
                raise APIError("Thông tin ca làm chưa hợp lệ")
            locations = SB.select(TABLES["locations"], filters={"id": f"eq.{location_id}", "active": "eq.true"}, limit=1)
            if not locations:
                raise APIError("Vị trí cửa hàng không tồn tại hoặc đã tắt")
            candidates = self.candidate_rows(work_date, start, end)
            candidate = next((x for x in candidates if integer(x["employee_id"]) == employee_id), None)
            if not candidate:
                raise APIError("Không tìm thấy nhân viên")
            if candidate["state"] in {"busy", "on_leave"}:
                raise APIError(candidate["reason"])
            if candidate["state"] != "available" and not force:
                raise APIError("Nhân viên chưa có lịch rảnh đã duyệt. Chỉ xếp cưỡng chế khi thật sự cần thiết.")
            row = SB.insert(TABLES["shifts"], {
                "employee_id": employee_id,
                "location_id": location_id,
                "shift_date": work_date,
                "start_time": start,
                "end_time": end,
                "note": str(body.get("note", "")).strip(),
                "status": "Đã xếp",
                "created_by": user["id"],
                "availability_request_id": candidate.get("availability_id"),
            })
            if candidate.get("availability_id"):
                SB.update(TABLES["availability"], {"status": "Đã xếp ca"}, {"id": f"eq.{candidate['availability_id']}"})
            self.notify_employee(employee_id, "Bạn có ca làm mới", f"Ngày {work_date}, {start}–{end} tại {locations[0]['name']}.", "schedule", "shifts")
            self.audit(user, "create", "shift", row["id"], {"employee_id": employee_id, "date": work_date, "time": f"{start}-{end}"})
            return self.ok(row, "Đã xếp ca làm")

        if path == "/api/shift-change-requests":
            self.require_role(user, "employee")
            shift_id = integer(body.get("shift_id"))
            shifts = SB.select(TABLES["shifts"], filters={"id": f"eq.{shift_id}", "employee_id": f"eq.{user['employee_id']}"}, limit=1)
            reason = str(body.get("reason", "")).strip()
            if not shifts or not reason:
                raise APIError("Ca làm hoặc lý do chưa hợp lệ")
            shift = shifts[0]
            if shift.get("shift_date") < today_text():
                raise APIError("Không thể yêu cầu thay ca đã qua")
            row = SB.insert(TABLES["shift_changes"], {"shift_id": shift_id, "requester_id": user["employee_id"], "request_type": body.get("request_type", "Tìm người thay"), "reason": reason, "status": "Chờ xử lý"})
            self.notify_role("admin", "Có yêu cầu thay ca", f"{user['profile']['name']} cần xử lý ca {shift['shift_date']} {shift['start_time']}–{shift['end_time']}.", "schedule", "requests")
            self.audit(user, "create", "shift_change", row["id"])
            return self.ok(row, "Đã gửi yêu cầu thay ca")

        if path == "/api/shift-change-requests/status":
            self.require_role(user, "admin")
            request_id = integer(body.get("id"))
            status = str(body.get("status", ""))
            current = SB.select(TABLES["shift_changes"], filters={"id": f"eq.{request_id}"}, limit=1)
            if not current:
                raise APIError("Không tìm thấy yêu cầu", 404)
            request_row = current[0]
            if status == "Đã duyệt":
                replacement_id = integer(body.get("replacement_employee_id"))
                if not replacement_id:
                    raise APIError("Vui lòng chọn nhân viên thay ca")
                result = SB.rpc("rumi_assign_replacement", {"p_request_id": request_id, "p_replacement_employee_id": replacement_id, "p_admin_note": str(body.get("admin_note", "")).strip()})
                shift = SB.select(TABLES["shifts"], filters={"id": f"eq.{result['shift_id']}"}, limit=1)[0]
                self.notify_employee(integer(result["old_employee_id"]), "Yêu cầu thay ca đã được duyệt", f"Ca ngày {shift['shift_date']} đã có người thay.", "schedule", "requests")
                self.notify_employee(integer(result["new_employee_id"]), "Bạn được xếp thay ca", f"Ngày {shift['shift_date']}, {shift['start_time']}–{shift['end_time']}.", "schedule", "shifts")
            elif status == "Từ chối":
                SB.update(TABLES["shift_changes"], {"status": "Từ chối", "admin_note": str(body.get("admin_note", "")).strip(), "reviewed_at": now_iso()}, {"id": f"eq.{request_id}"})
                self.notify_employee(integer(request_row["requester_id"]), "Yêu cầu thay ca bị từ chối", str(body.get("admin_note", "")).strip() or "Quản lý chưa thể sắp xếp người thay.", "warning", "requests")
            else:
                raise APIError("Trạng thái xử lý không hợp lệ")
            self.audit(user, "review", "shift_change", request_id, {"status": status})
            return self.ok(None, "Đã xử lý yêu cầu thay ca")

        if path == "/api/attendance/clock":
            self.require_role(user, "employee")
            shift_id = integer(body.get("shift_id"))
            accuracy = num(body.get("accuracy"), 99999)
            result = SB.rpc("rumi_clock_shift", {
                "p_shift_id": shift_id,
                "p_employee_id": user["employee_id"],
                "p_action": str(body.get("action", "auto")),
                "p_lat": num(body.get("latitude"), 999),
                "p_lng": num(body.get("longitude"), 999),
                "p_accuracy": accuracy,
                "p_now": now_iso(),
            })
            message = "Chấm công vào ca thành công" if result.get("action") == "checkin" else "Chấm công ra ca thành công"
            self.audit(user, result.get("action", "clock"), "attendance", shift_id, {"distance_m": result.get("distance_m")})
            return self.ok(result, message)

        if path == "/api/attendance/manual":
            self.require_role(user, "admin")
            shift_id = integer(body.get("shift_id"))
            shifts = SB.select(TABLES["shifts"], filters={"id": f"eq.{shift_id}"}, limit=1)
            if not shifts:
                raise APIError("Không tìm thấy ca làm")
            shift = shifts[0]
            check_in = parse_time(body.get("check_in"), "Giờ vào")
            check_out = parse_time(body.get("check_out"), "Giờ ra") if body.get("check_out") else None
            hours = calculate_hours(check_in, check_out)
            row = SB.upsert(TABLES["attendance"], {
                "shift_id": shift_id,
                "employee_id": shift["employee_id"],
                "work_date": shift["shift_date"],
                "check_in": check_in,
                "check_out": check_out,
                "hours": hours,
                "status": "Hoàn thành" if check_out else "Đang làm",
                "note": str(body.get("note", "Điều chỉnh bởi quản lý")).strip(),
            }, "shift_id")
            self.audit(user, "manual_update", "attendance", row.get("id"), {"shift_id": shift_id})
            return self.ok(row, "Đã cập nhật chấm công")

        if path == "/api/payroll/adjustment":
            self.require_role(user, "admin")
            employee_id = integer(body.get("employee_id"))
            month = str(body.get("month", ""))
            if not employee_id or not re.fullmatch(r"\d{4}-\d{2}", month):
                raise APIError("Tháng lương không hợp lệ")
            row = SB.upsert(TABLES["payroll_adjustments"], {"employee_id": employee_id, "month": month, "bonus": num(body.get("bonus")), "penalty": num(body.get("penalty")), "advance_pay": num(body.get("advance_pay")), "note": str(body.get("note", "")).strip()}, "employee_id,month")
            self.notify_employee(employee_id, "Bảng lương được cập nhật", f"Các khoản điều chỉnh tháng {month} đã thay đổi.", "payroll", "payroll")
            self.audit(user, "update", "payroll_adjustment", row.get("id"), {"month": month})
            return self.ok(row, "Đã cập nhật thưởng, phạt và tạm ứng")

        if path == "/api/payroll/payment":
            self.require_role(user, "admin")
            employee_id = integer(body.get("employee_id"))
            month = str(body.get("month", ""))
            status = str(body.get("status", "Đã thanh toán"))
            if not employee_id or not re.fullmatch(r"\d{4}-\d{2}", month):
                raise APIError("Thông tin thanh toán không hợp lệ")
            row = SB.upsert(TABLES["payroll_payments"], {"employee_id": employee_id, "month": month, "status": status, "paid_at": now_iso() if status == "Đã thanh toán" else None}, "employee_id,month")
            self.notify_employee(employee_id, "Trạng thái lương", f"Lương tháng {month}: {status}.", "payroll", "payroll")
            self.audit(user, "payment", "payroll", employee_id, {"month": month, "status": status})
            return self.ok(row, "Đã cập nhật trạng thái lương")

        if path == "/api/inventory":
            self.require_role(user, "admin")
            name = str(body.get("name", "")).strip()
            if not name:
                raise APIError("Vui lòng nhập tên nguyên liệu")
            row = SB.insert(TABLES["inventory"], {"name": name, "category": body.get("category", "Nguyên liệu"), "quantity": num(body.get("quantity")), "unit": body.get("unit", "kg"), "min_stock": num(body.get("min_stock")), "cost": num(body.get("cost"))})
            self.audit(user, "create", "inventory", row["id"], {"name": name})
            return self.ok(row, "Đã thêm nguyên liệu")

        if path == "/api/inventory/restock":
            self.require_role(user, "admin")
            inventory_id = integer(body.get("inventory_id"))
            quantity = num(body.get("quantity"))
            if not inventory_id or quantity <= 0:
                raise APIError("Số lượng nhập kho phải lớn hơn 0")
            result = SB.rpc("rumi_restock_inventory", {"p_inventory_id": inventory_id, "p_quantity": quantity})
            self.audit(user, "restock", "inventory", inventory_id, {"quantity": quantity})
            return self.ok(result, "Đã nhập thêm hàng vào kho")

        if path == "/api/inventory/withdraw":
            employee_id = integer(user.get("employee_id")) if user.get("role") == "employee" else integer(body.get("employee_id")) or None
            inventory_id = integer(body.get("inventory_id"))
            quantity = num(body.get("quantity"))
            if not inventory_id or quantity <= 0:
                raise APIError("Số lượng lấy phải lớn hơn 0")
            result = SB.rpc("rumi_withdraw_inventory", {"p_inventory_id": inventory_id, "p_employee_id": employee_id, "p_quantity": quantity, "p_taken_at": body.get("taken_at") or today_text(), "p_note": str(body.get("note", "")).strip()})
            self.audit(user, "withdraw", "inventory", inventory_id, {"quantity": quantity})
            return self.ok(result, "Đã ghi nhận lấy hàng và tự động trừ kho")

        if path == "/api/purchase-requests":
            item_name = str(body.get("item_name", "")).strip()
            quantity = num(body.get("quantity"))
            employee_id = integer(user.get("employee_id")) if user.get("role") == "employee" else integer(body.get("requester_employee_id")) or None
            requester = user["profile"]["name"] if user.get("role") == "employee" else str(body.get("requester_name", user["profile"]["name"])).strip()
            if not item_name or quantity <= 0:
                raise APIError("Vui lòng nhập tên hàng và số lượng")
            row = SB.insert(TABLES["purchase_requests"], {"item_name": item_name, "quantity": quantity, "unit": body.get("unit", "kg"), "reason": str(body.get("reason", "")).strip(), "requester_name": requester, "requester_employee_id": employee_id, "requested_at": body.get("requested_at") or today_text(), "priority": body.get("priority", "Bình thường"), "status": "Chờ mua"})
            self.notify_role("admin", "Có đề xuất mua hàng", f"{requester} đề xuất mua {quantity:g} {body.get('unit','kg')} {item_name}.", "inventory", "purchases")
            self.audit(user, "create", "purchase_request", row["id"])
            return self.ok(row, "Đã gửi đề xuất mua hàng")

        if path == "/api/purchase-requests/status":
            self.require_role(user, "admin")
            request_id = integer(body.get("id"))
            rows = SB.update(TABLES["purchase_requests"], {"status": body.get("status", "Đã mua")}, {"id": f"eq.{request_id}"})
            if not rows:
                raise APIError("Không tìm thấy đề xuất", 404)
            if rows[0].get("requester_employee_id"):
                self.notify_employee(integer(rows[0]["requester_employee_id"]), "Đề xuất mua hàng đã cập nhật", f"{rows[0]['item_name']}: {rows[0]['status']}.", "inventory", "purchases")
            self.audit(user, "status", "purchase_request", request_id, {"status": rows[0]["status"]})
            return self.ok(rows[0], "Đã cập nhật đề xuất mua hàng")

        raise APIError("Không tìm thấy API", 404)

    # ------------------------------------------------------------------
    # PUT routes
    # ------------------------------------------------------------------
    def handle_api_put(self, path: str, body: dict):
        user = self.current_user()
        self.require_csrf()

        match = re.fullmatch(r"/api/employees/(\d+)", path)
        if match:
            self.require_role(user, "admin")
            employee_id = integer(match.group(1))
            code = str(body.get("code", "")).strip().upper()
            name = str(body.get("name", "")).strip()
            username = str(body.get("username", "")).strip().lower()
            if not code or len(name) < 2 or not re.fullmatch(r"[a-z0-9._-]{3,40}", username):
                raise APIError("Mã, họ tên hoặc tên đăng nhập chưa hợp lệ")
            rows = SB.update(TABLES["employees"], {
                "code": code,
                "name": name,
                "phone": str(body.get("phone", "")).strip(),
                "email": str(body.get("email", "")).strip(),
                "role": str(body.get("job_role", "Nhân viên")).strip(),
                "hourly_wage": num(body.get("hourly_wage"), 25000),
                "status": body.get("status", "Đang làm"),
                "joined_at": body.get("joined_at") or today_text(),
            }, {"id": f"eq.{employee_id}"})
            if not rows:
                raise APIError("Không tìm thấy nhân viên", 404)
            active = rows[0].get("status") == "Đang làm"
            account_rows = SB.update(TABLES["users"], {"username": username, "active": active}, {"employee_id": f"eq.{employee_id}"})
            if not account_rows:
                raise APIError("Nhân viên chưa có tài khoản đăng nhập", 409)
            self.audit(user, "update", "employee", employee_id, {"code": code, "name": name, "username": username})
            return self.ok(rows[0], "Đã cập nhật nhân viên và tài khoản")

        match = re.fullmatch(r"/api/locations/(\d+)", path)
        if match:
            self.require_role(user, "admin")
            location_id = integer(match.group(1))
            rows = SB.update(TABLES["locations"], {
                "name": str(body.get("name", "")).strip(),
                "address": str(body.get("address", "")).strip(),
                "latitude": num(body.get("latitude")),
                "longitude": num(body.get("longitude")),
                "radius_m": integer(body.get("radius_m"), 100),
                "active": bool(body.get("active", True)),
            }, {"id": f"eq.{location_id}"})
            if not rows:
                raise APIError("Không tìm thấy vị trí", 404)
            self.audit(user, "update", "location", location_id)
            return self.ok(rows[0], "Đã cập nhật vị trí")

        if path == "/api/settings":
            self.require_role(user, "admin")
            row = SB.upsert(TABLES["settings"], {
                "id": 1,
                "timezone": body.get("timezone", "Asia/Ho_Chi_Minh"),
                "checkin_before_minutes": integer(body.get("checkin_before_minutes"), 15),
                "checkin_after_minutes": integer(body.get("checkin_after_minutes"), 5),
                "checkout_before_minutes": integer(body.get("checkout_before_minutes"), 5),
                "checkout_after_minutes": integer(body.get("checkout_after_minutes"), 5),
                "max_gps_accuracy_m": integer(body.get("max_gps_accuracy_m"), 150),
            }, "id")
            self.audit(user, "update", "settings", 1)
            return self.ok(row, "Đã cập nhật quy định chấm công")

        match = re.fullmatch(r"/api/inventory/(\d+)", path)
        if match:
            self.require_role(user, "admin")
            inventory_id = integer(match.group(1))
            rows = SB.update(TABLES["inventory"], {
                "name": str(body.get("name", "")).strip(),
                "category": body.get("category", "Nguyên liệu"),
                "quantity": num(body.get("quantity")),
                "unit": body.get("unit", "kg"),
                "min_stock": num(body.get("min_stock")),
                "cost": num(body.get("cost")),
            }, {"id": f"eq.{inventory_id}"})
            if not rows:
                raise APIError("Không tìm thấy nguyên liệu", 404)
            self.audit(user, "update", "inventory", inventory_id)
            return self.ok(rows[0], "Đã cập nhật kho")

        raise APIError("Không tìm thấy API", 404)

    # ------------------------------------------------------------------
    # DELETE routes
    # ------------------------------------------------------------------
    def handle_api_delete(self, path: str):
        user = self.current_user()
        self.require_csrf()

        match = re.fullmatch(r"/api/employees/(\d+)", path)
        if match:
            self.require_role(user, "admin")
            employee_id = integer(match.group(1))
            existing = SB.select(TABLES["employees"], filters={"id": f"eq.{employee_id}"}, limit=1)
            if not existing:
                raise APIError("Không tìm thấy nhân viên", 404)
            employee = existing[0]
            rows = SB.delete(TABLES["employees"], {"id": f"eq.{employee_id}"})
            if not rows:
                raise APIError("Không thể xóa nhân viên", 409)
            self.audit(user, "delete", "employee", employee_id, {"code": employee.get("code"), "name": employee.get("name")})
            return self.ok(None, "Đã xóa nhân viên và tài khoản đăng nhập")

        match = re.fullmatch(r"/api/shifts/(\d+)", path)
        if match:
            self.require_role(user, "admin")
            shift_id = integer(match.group(1))
            rows = SB.delete(TABLES["shifts"], {"id": f"eq.{shift_id}"})
            if not rows:
                raise APIError("Không tìm thấy ca làm", 404)
            self.audit(user, "delete", "shift", shift_id)
            return self.ok(None, "Đã xoá ca làm")

        match = re.fullmatch(r"/api/availability/(\d+)", path)
        if match:
            request_id = integer(match.group(1))
            filters = {"id": f"eq.{request_id}"}
            if user.get("role") == "employee":
                filters["employee_id"] = f"eq.{user['employee_id']}"
                existing = SB.select(TABLES["availability"], filters=filters, limit=1)
                if not existing or existing[0].get("status") != "Chờ duyệt":
                    raise APIError("Chỉ có thể hủy đăng ký đang chờ duyệt")
            rows = SB.delete(TABLES["availability"], filters)
            if not rows:
                raise APIError("Không tìm thấy đăng ký", 404)
            self.audit(user, "delete", "availability", request_id)
            return self.ok(None, "Đã hủy đăng ký lịch")

        raise APIError("Không tìm thấy API", 404)


def _legacy_jwt_role(token: str) -> str:
    if not token.startswith("eyJ"):
        return ""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return str(json.loads(base64.urlsafe_b64decode(payload).decode("utf-8")).get("role", ""))
    except Exception:
        return ""


def ensure_configured_admin() -> dict:
    """Create the server-configured admin account when it does not exist.

    There is intentionally no public setup or registration endpoint. Employees
    can only be created, edited or deleted by an authenticated admin.
    """
    if not re.fullmatch(r"[a-z0-9._-]{3,40}", ADMIN_USERNAME):
        raise APIError("RUMI_ADMIN_USERNAME không hợp lệ. Dùng 3-40 ký tự a-z, 0-9, dấu chấm, gạch dưới hoặc gạch ngang.")
    if len(ADMIN_PASSWORD) < 8:
        raise APIError("RUMI_ADMIN_PASSWORD phải có ít nhất 8 ký tự.")
    rows = SB.select(TABLES["users"], filters={"username": f"eq.{ADMIN_USERNAME}"}, limit=1)
    if rows:
        admin = rows[0]
        if admin.get("role") != "admin":
            raise APIError(f"Tên đăng nhập cấu hình '{ADMIN_USERNAME}' đang thuộc tài khoản nhân viên. Hãy đổi RUMI_ADMIN_USERNAME.")
        updates = {}
        if not admin.get("active"):
            updates["active"] = True
        if ADMIN_RESET_ON_START:
            hashed, salt = password_hash(ADMIN_PASSWORD)
            updates.update({"password_hash": hashed, "password_salt": salt})
        if updates:
            admin = SB.update(TABLES["users"], updates, {"id": f"eq.{admin['id']}"})[0]
        return admin
    hashed, salt = password_hash(ADMIN_PASSWORD)
    return SB.insert(TABLES["users"], {
        "username": ADMIN_USERNAME,
        "password_hash": hashed,
        "password_salt": salt,
        "role": "admin",
        "employee_id": None,
        "active": True,
    })


def validate_config() -> None:
    if not SUPABASE_URL or "YOUR_PROJECT" in SUPABASE_URL:
        print("\n[CHƯA CẤU HÌNH URL SUPABASE]\nTạo file .env và điền RUMI_SUPABASE_URL.\n")
        raise SystemExit(2)
    if not SUPABASE_KEY or "YOUR_" in SUPABASE_KEY:
        print("\n[CHƯA CẤU HÌNH KHÓA SUPABASE]\nTạo file .env và điền RUMI_SUPABASE_SERVICE_ROLE_KEY bằng khóa MỚI.\n")
        raise SystemExit(2)
    if SUPABASE_KEY.startswith("sb_publishable_") or _legacy_jwt_role(SUPABASE_KEY) == "anon":
        print("Không dùng publishable/anon key cho backend RUMI. Hãy dùng secret/service_role key.")
        raise SystemExit(2)
    if not (SUPABASE_KEY.startswith("sb_secret_") or _legacy_jwt_role(SUPABASE_KEY) == "service_role"):
        print("Khóa Supabase không đúng loại. Cần secret key (sb_secret_...) hoặc legacy service_role key.")
        raise SystemExit(2)


def main() -> None:
    validate_config()
    cloud_port = os.environ.get("PORT")
    host = os.environ.get("RUMI_HOST") or ("0.0.0.0" if cloud_port else "127.0.0.1")
    port = integer(cloud_port or os.environ.get("RUMI_PORT", "8000"), 8000)
    if cloud_port and ADMIN_PASSWORD == "Rumi@2026":
        raise SystemExit("Triển khai online bắt buộc đặt RUMI_ADMIN_PASSWORD khác mật khẩu mặc định.")
    try:
        SB.select(TABLES["users"], limit=1, columns="id")
        ensure_configured_admin()
    except APIError as exc:
        print(f"\nKhông thể khởi động: {exc}\n")
        raise SystemExit(2) from exc
    server = ThreadingHTTPServer((host, port), RumiHandler)
    print("=" * 68)
    print("RUMI Manager v4.4 Vercel đang chạy")
    print(f"Mở trên máy này: http://localhost:{port}")
    print(f"Tài khoản admin: {ADMIN_USERNAME}")
    if os.environ.get("RUMI_ADMIN_PASSWORD"):
        print("Mật khẩu admin: giá trị RUMI_ADMIN_PASSWORD trong file .env")
    else:
        print("Mật khẩu admin mặc định: Rumi@2026 (hãy đổi sau khi đăng nhập)")
    if host == "0.0.0.0":
        print("Thiết bị khác có thể dùng IP nội bộ của máy Mac; GPS trên điện thoại cần HTTPS.")
    print("Nhấn Control + C để dừng.")
    print("=" * 68)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng RUMI Manager.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
