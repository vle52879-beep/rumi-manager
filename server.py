#!/usr/bin/env python3
"""RUMI Manager v6.4.3 MULTI ADMIN — multiple administrator accounts, employee CRUD, roles, scheduling and GPS.

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
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from datetime import date, datetime, timedelta
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlencode, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from excel_export import build_schedule_week_xlsx

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
ENV_FILES = [ROOT / ".env", ROOT / ".env.local"]
SESSION_COOKIE = "__Host-rumi_session"
LEGACY_SESSION_COOKIE = "rumi_session"
SESSION_TTL = 12 * 60 * 60
SESSION_IDLE_TTL = 2 * 60 * 60
PASSWORD_ITERATIONS = 600_000
PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128
LOGIN_WINDOW_SECONDS = 10 * 60
LOGIN_LOCK_MINUTES = 15


class TTLCache:
    """Tiny process-local cache for warm Vercel Function instances."""

    def __init__(self):
        self._data: dict[object, tuple[float, object]] = {}

    def get(self, key):
        item = self._data.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at <= time.monotonic():
            self._data.pop(key, None)
            return None
        return value

    def set(self, key, value, ttl: float):
        self._data[key] = (time.monotonic() + ttl, value)

    def clear(self):
        self._data.clear()


USER_CACHE = TTLCache()
PAYROLL_CACHE = TTLCache()
ATTENDANCE_ALERT_CACHE = TTLCache()


def parallel_calls(**jobs):
    """Run independent Supabase REST calls concurrently to hide network latency."""
    if not jobs:
        return {}
    with ThreadPoolExecutor(max_workers=min(12, len(jobs))) as pool:
        futures = {name: pool.submit(fn) for name, fn in jobs.items()}
        return {name: future.result() for name, future in futures.items()}


def pg_in(values) -> str:
    unique = []
    seen = set()
    for value in values:
        ivalue = integer(value)
        if ivalue and ivalue not in seen:
            seen.add(ivalue)
            unique.append(ivalue)
    return "in.(" + ",".join(map(str, unique)) + ")"

TABLES = {
    "employees": "rumi_employees",
    "users": "rumi_users",
    "locations": "rumi_locations",
    "settings": "rumi_settings",
    "availability": "rumi_availability_requests",
    "openings": "rumi_shift_openings",
    "applications": "rumi_shift_applications",
    "day_offs": "rumi_weekly_day_off_requests",
    "weekly_requests": "rumi_weekly_shift_requests",
    "weekly_request_items": "rumi_weekly_shift_request_items",
    "leaves": "rumi_leave_requests",
    "shift_changes": "rumi_shift_change_requests",
    "shifts": "rumi_shifts",
    "attendance": "rumi_attendance",
    "inventory": "rumi_inventory",
    "withdrawals": "rumi_withdrawals",
    "purchase_requests": "rumi_purchase_requests",
    "payroll_adjustments": "rumi_payroll_adjustments",
    "payroll_payments": "rumi_payroll_payments",
    "payroll_runs": "rumi_payroll_runs",
    "payroll_items": "rumi_payroll_items",
    "notifications": "rumi_notifications",
    "audit": "rumi_audit_logs",
    "auth_sessions": "rumi_auth_sessions",
    "password_history": "rumi_password_history",
    "login_throttles": "rumi_login_throttles",
    "attendance_events": "rumi_attendance_events",
    "attendance_corrections": "rumi_attendance_correction_requests",
    "attendance_alerts": "rumi_shift_attendance_alerts",
    "shift_reassignments": "rumi_shift_reassignments",
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


LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def local_now() -> datetime:
    """Current store time. Vercel may run in UTC, so never trust server locale."""
    return datetime.now(LOCAL_TZ)


def now_iso() -> str:
    return local_now().isoformat(timespec="seconds")


def today_text() -> str:
    return local_now().date().isoformat()


def current_month() -> str:
    return local_now().strftime("%Y-%m")


def monday_of(value: str | date) -> date:
    day = value if isinstance(value, date) else datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    return day - timedelta(days=day.weekday())


def longest_consecutive_days(values) -> int:
    days = sorted({datetime.strptime(str(v)[:10], "%Y-%m-%d").date() if not isinstance(v, date) else v for v in values if v})
    best = run = 0
    previous = None
    for day in days:
        run = run + 1 if previous and day == previous + timedelta(days=1) else 1
        best = max(best, run)
        previous = day
    return best


def shift_hours(start: str, end: str) -> float:
    return round(max(minutes_delta(start, end), 0) / 60, 2)


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


def number_text(value) -> str:
    number = num(value)
    return str(int(number)) if number.is_integer() else str(round(number, 2))


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


def shift_local_datetimes(shift: dict) -> tuple[datetime, datetime]:
    day = datetime.strptime(str(shift.get("shift_date"))[:10], "%Y-%m-%d").date()
    start_value = datetime.strptime(str(shift.get("start_time"))[:5], "%H:%M").time()
    end_value = datetime.strptime(str(shift.get("end_time"))[:5], "%H:%M").time()
    return datetime.combine(day, start_value, tzinfo=LOCAL_TZ), datetime.combine(day, end_value, tzinfo=LOCAL_TZ)


def classify_shift_attendance(shift: dict, attendance: dict | None, settings: dict | None = None, now: datetime | None = None) -> dict:
    """Return the live attendance state for one official shift.

    The state is calculated from server/store time, never from the employee's
    device clock. It is also used by payroll, dashboard alerts and synthetic
    attendance rows so every screen follows the same rules.
    """
    settings = settings or {}
    now = now or local_now()
    start_dt, end_dt = shift_local_datetimes(shift)
    checkin_before = integer(settings.get("checkin_before_minutes"), 15)
    checkin_after = integer(settings.get("checkin_after_minutes"), 5)
    warning_after = max(integer(settings.get("attendance_warning_minutes"), 15), checkin_after)
    no_show_after = max(integer(settings.get("attendance_no_show_minutes"), 30), warning_after)
    absent_after_end = integer(settings.get("attendance_absent_after_end_minutes"), 0)
    checkout_before = integer(settings.get("checkout_before_minutes"), 5)
    checkout_after = integer(settings.get("checkout_after_minutes"), 180)

    att = attendance or {}
    has_in = bool(att.get("check_in") or att.get("check_in_at"))
    has_out = bool(att.get("check_out") or att.get("check_out_at"))
    minutes_from_start = max(0, int((now - start_dt).total_seconds() // 60)) if now >= start_dt else 0

    if has_in and has_out:
        return {"status": "Hoàn tất", "severity": "success", "minutes_late": integer(att.get("late_minutes")), "requires_action": False}
    if has_in:
        if now < end_dt - timedelta(minutes=checkout_before):
            return {"status": "Đang làm", "severity": "success", "minutes_late": integer(att.get("late_minutes")), "requires_action": False}
        if now <= end_dt + timedelta(minutes=checkout_after):
            return {"status": "Đến giờ chấm ra", "severity": "warning", "minutes_late": integer(att.get("late_minutes")), "requires_action": True}
        return {"status": "Thiếu giờ ra", "severity": "danger", "minutes_late": integer(att.get("late_minutes")), "requires_action": True}

    if now < start_dt - timedelta(minutes=checkin_before):
        return {"status": "Chưa đến ca", "severity": "neutral", "minutes_late": 0, "requires_action": False}
    if now < start_dt:
        return {"status": "Có thể chấm vào", "severity": "info", "minutes_late": 0, "requires_action": False}
    if now <= start_dt + timedelta(minutes=checkin_after):
        return {"status": "Đến giờ chấm công", "severity": "info", "minutes_late": minutes_from_start, "requires_action": True}
    if now < start_dt + timedelta(minutes=no_show_after):
        return {"status": "Đi trễ chưa chấm", "severity": "warning", "minutes_late": minutes_from_start, "requires_action": True}
    if now < end_dt + timedelta(minutes=absent_after_end):
        return {"status": "Nguy cơ vắng ca", "severity": "danger", "minutes_late": minutes_from_start, "requires_action": True}
    return {"status": "Vắng ca", "severity": "danger", "minutes_late": minutes_from_start, "requires_action": True}


def calculate_hours(check_in: str, check_out: str | None) -> float:
    if not check_in or not check_out:
        return 0.0
    seconds = (datetime.strptime(check_out[:5], "%H:%M") - datetime.strptime(check_in[:5], "%H:%M")).total_seconds()
    if seconds < 0:
        seconds += 86400
    return round(seconds / 3600, 2)


def minutes_delta(start: str, end: str) -> int:
    """Minutes from start to end for same-day RUMI shifts."""
    return time_minutes(end) - time_minutes(start)


def attendance_metrics(shift: dict, check_in: str, check_out: str | None, *, approve_overtime: bool = False) -> dict:
    """Calculate salary minutes against the scheduled window.

    Early arrival never increases salary. Minutes after the scheduled end are
    recorded as requested overtime and only become payable after approval.
    """
    scheduled_minutes = max(minutes_delta(shift["start_time"], shift["end_time"]), 0)
    late_minutes = max(minutes_delta(shift["start_time"], check_in), 0) if check_in else 0
    if not check_out:
        return {
            "scheduled_minutes": scheduled_minutes,
            "worked_minutes": 0,
            "base_payable_minutes": 0,
            "payable_minutes": 0,
            "scheduled_hours": round(scheduled_minutes / 60, 2),
            "payable_hours": 0.0,
            "late_minutes": late_minutes,
            "early_leave_minutes": 0,
            "overtime_minutes": 0,
            "overtime_requested_minutes": 0,
            "overtime_approved_minutes": 0,
            "overtime_status": "Không có",
            "status": "Đang làm",
            "calculation_note": f"Vào trễ {late_minutes} phút" if late_minutes else "Vào ca đúng giờ",
        }
    worked_minutes = max(minutes_delta(check_in, check_out), 0)
    early_minutes = max(minutes_delta(check_out, shift["end_time"]), 0)
    overtime_minutes = max(minutes_delta(shift["end_time"], check_out), 0)
    salary_start = max(time_minutes(check_in), time_minutes(shift["start_time"]))
    salary_end = min(time_minutes(check_out), time_minutes(shift["end_time"]))
    base_payable = max(salary_end - salary_start, 0)
    approved_overtime = overtime_minutes if approve_overtime else 0
    payable_minutes = base_payable + approved_overtime
    if overtime_minutes and not approve_overtime:
        status = "Chờ duyệt tăng ca"
    elif late_minutes and early_minutes:
        status = "Đi trễ & về sớm"
    elif late_minutes:
        status = "Đi trễ"
    elif early_minutes:
        status = "Về sớm"
    elif overtime_minutes:
        status = "Có tăng ca"
    else:
        status = "Hoàn thành"
    parts = []
    if late_minutes:
        parts.append(f"Trễ {late_minutes} phút")
    if early_minutes:
        parts.append(f"Về sớm {early_minutes} phút")
    if overtime_minutes:
        parts.append(f"Tăng ca đề nghị {overtime_minutes} phút")
    parts.append(f"Tính lương {payable_minutes} phút")
    return {
        "scheduled_minutes": scheduled_minutes,
        "worked_minutes": worked_minutes,
        "base_payable_minutes": base_payable,
        "payable_minutes": payable_minutes,
        "scheduled_hours": round(scheduled_minutes / 60, 2),
        "payable_hours": round(payable_minutes / 60, 2),
        "late_minutes": late_minutes,
        "early_leave_minutes": early_minutes,
        "overtime_minutes": overtime_minutes,
        "overtime_requested_minutes": overtime_minutes,
        "overtime_approved_minutes": approved_overtime,
        "overtime_status": "Không có" if not overtime_minutes else ("Đã duyệt" if approve_overtime else "Chờ duyệt"),
        "status": status,
        "calculation_note": " · ".join(parts),
    }


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
            "User-Agent": "RUMI-Backend/5.5",
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
        if "deleted_at" in lowered and ("could not find" in lowered or "schema cache" in lowered or code.startswith("PGRST")):
            return "Chưa nâng cấp RUMI v6.4.2. Hãy chạy sql/SUPABASE_RUMI_V6_4_2_ADMIN_CONTROL.sql trong Supabase."
        if code == "42P01" or "could not find the table" in lowered or ("relation" in lowered and "does not exist" in lowered):
            if "shift_reassignments" in lowered:
                return "Chưa nâng cấp RUMI v6.4.2. Hãy chạy sql/SUPABASE_RUMI_V6_4_2_ADMIN_CONTROL.sql trong Supabase."
            if "weekly_shift_requests" in lowered or "weekly_shift_request_items" in lowered or "weekly_request_id" in lowered:
                return "Chưa nâng cấp RUMI v6.4. Hãy chạy sql/SUPABASE_RUMI_V6_4_WEEKLY_REGISTRATION.sql trong Supabase."
            if "shift_attendance_alerts" in lowered or "attendance_warning_minutes" in lowered:
                return "Chưa nâng cấp RUMI v6.2. Hãy chạy sql/SUPABASE_RUMI_V6_2_ATTENDANCE_ALERTS.sql trong Supabase."
            if any(name in lowered for name in ("auth_sessions", "password_history", "login_throttles", "attendance_events", "attendance_correction")):
                return "Chưa nâng cấp RUMI v5.5. Hãy chạy sql/SUPABASE_RUMI_V5_5_SECURITY_ATTENDANCE.sql trong Supabase."
            if "shift_openings" in lowered or "shift_applications" in lowered or "weekly_day_off" in lowered:
                return "Chưa nâng cấp RUMI v5.4. Hãy chạy sql/SUPABASE_RUMI_V5_4_SHIFT_MARKET.sql trong Supabase."
            if any(name in lowered for name in ("scheduled_shift_count", "completed_shift_count", "eligible_for_payment", "payroll_state")):
                return "Chưa nâng cấp logic bảng lương RUMI v6.1. Hãy chạy sql/SUPABASE_RUMI_V6_1_PAYROLL_LOGIC.sql trong Supabase."
            if "payroll_runs" in lowered or "payroll_items" in lowered:
                return "Chưa nâng cấp RUMI v5.3. Hãy chạy sql/SUPABASE_RUMI_V5_3_OPERATIONS.sql trong Supabase."
            return "Chưa tạo đủ bảng RUMI. Hãy chạy SQL v4, v5.3 rồi v5.4 theo đúng thứ tự."
        if "could not find the function" in lowered:
            if "reassign_shift_to_application" in lowered:
                return "Chưa tạo hàm đổi nhân viên RUMI v6.4.2. Hãy chạy SQL v6.4.2 trong Supabase."
            if "submit_weekly_shift_request" in lowered or "refresh_weekly_shift_request" in lowered:
                return "Chưa tạo hàm đăng ký tuần RUMI v6.4. Hãy chạy sql/SUPABASE_RUMI_V6_4_WEEKLY_REGISTRATION.sql trong Supabase."
            if "v55" in lowered or "auth_register_failure" in lowered or "auth_clear_failures" in lowered:
                return "Chưa tạo hàm bảo mật/chấm công RUMI v5.5. Hãy chạy lại SQL v5.5 trong Supabase."
            return "Chưa tạo hàm nghiệp vụ RUMI. Hãy chạy các file SQL nâng cấp theo đúng thứ tự."
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

    def select(self, table: str, *, filters: dict | None = None, order: str = "", limit: int | None = None,
               offset: int | None = None, columns: str = "*") -> list[dict]:
        params = {"select": columns}
        if filters:
            params.update(filters)
        if order:
            params["order"] = order
        if limit is not None:
            params["limit"] = limit
        if offset is not None and offset > 0:
            params["offset"] = offset
        data = self.request("GET", table, params=params)
        return [normalize_row(x) for x in (data or [])]

    def select_all(self, table: str, *, filters: dict | None = None, order: str = "", columns: str = "*",
                   page_size: int = 500) -> list[dict]:
        """Read every matching row in pages instead of silently stopping at a UI limit."""
        rows: list[dict] = []
        offset = 0
        page_size = max(50, min(integer(page_size, 500), 1000))
        while True:
            chunk = self.select(table, filters=filters, order=order, limit=page_size, offset=offset, columns=columns)
            rows.extend(chunk)
            if len(chunk) < page_size:
                break
            offset += len(chunk)
        return rows

    def select_in(self, table: str, column: str, values, *, columns: str = "*", order: str = "") -> list[dict]:
        ids = []
        seen = set()
        for value in values:
            ivalue = integer(value)
            if ivalue and ivalue not in seen:
                seen.add(ivalue)
                ids.append(ivalue)
        if not ids:
            return []
        rows: list[dict] = []
        for offset in range(0, len(ids), 150):
            chunk = ids[offset:offset + 150]
            rows.extend(self.select(table, filters={column: pg_in(chunk)}, columns=columns, order=order))
        return rows

    def insert(self, table: str, body: dict) -> dict:
        data = self.request("POST", table, body=body, prefer="return=representation") or []
        return normalize_row(data[0]) if data else {}

    def insert_many(self, table: str, rows: list[dict]) -> list[dict]:
        if not rows:
            return []
        data = self.request("POST", table, body=rows, prefer="return=representation") or []
        return [normalize_row(x) for x in data]

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


def password_material(password: str) -> bytes:
    """Return password bytes, optionally protected with a backend-only pepper."""
    pepper = (os.environ.get("RUMI_PASSWORD_PEPPER") or "").encode("utf-8")
    raw = password.encode("utf-8")
    return hmac.new(pepper, raw, hashlib.sha256).digest() if pepper else raw


def password_hash(password: str, salt_b64: str | None = None, iterations: int = PASSWORD_ITERATIONS) -> tuple[str, str]:
    if salt_b64:
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
    else:
        salt = secrets.token_bytes(18)
    rounds = max(100_000, min(integer(iterations, PASSWORD_ITERATIONS), 2_000_000))
    digest = hashlib.pbkdf2_hmac("sha256", password_material(password), salt, rounds)
    return base64.urlsafe_b64encode(digest).decode("ascii"), base64.urlsafe_b64encode(salt).decode("ascii")


def verify_password(password: str, expected: str, salt: str, iterations: int = PASSWORD_ITERATIONS) -> bool:
    try:
        actual, _ = password_hash(password, salt, iterations)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def validate_password_policy(password: str, username: str = "", *, admin: bool = False) -> None:
    minimum = 12 if admin else PASSWORD_MIN_LENGTH
    if len(password) < minimum:
        raise APIError(f"Mật khẩu phải có ít nhất {minimum} ký tự")
    if len(password) > PASSWORD_MAX_LENGTH:
        raise APIError(f"Mật khẩu không được vượt quá {PASSWORD_MAX_LENGTH} ký tự")
    categories = sum(bool(re.search(pattern, password)) for pattern in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]"))
    if categories < 3:
        raise APIError("Mật khẩu cần có ít nhất 3 nhóm: chữ thường, chữ hoa, số hoặc ký tự đặc biệt")
    normalized = re.sub(r"[^a-z0-9]", "", password.lower())
    blocked = {
        "password", "password123", "matkhau", "matkhau123", "1234567890", "qwerty123",
        "admin123", "rumi2026", "rumi2026abc", "letmein", "welcome123",
    }
    if normalized in blocked or normalized.startswith("123456"):
        raise APIError("Mật khẩu quá phổ biến, vui lòng chọn mật khẩu khác")
    user_clean = re.sub(r"[^a-z0-9]", "", str(username).lower())
    if user_clean and len(user_clean) >= 3 and user_clean in normalized:
        raise APIError("Mật khẩu không được chứa tên đăng nhập")


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def hash_secret(value: str, purpose: str) -> str:
    key = SESSION_SECRET or hashlib.sha256(b"RUMI-SESSION-FALLBACK").digest()
    return hmac.new(key, f"{purpose}|{value}".encode("utf-8"), hashlib.sha256).hexdigest()


def create_session_token() -> str:
    return b64url(secrets.token_bytes(32))


def session_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    return datetime.now().astimezone()


def iso_after(seconds: int) -> str:
    return (utc_now() + timedelta(seconds=seconds)).isoformat(timespec="seconds")


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def minutes_until(value: str | None) -> int:
    target = parse_iso_datetime(value)
    if not target:
        return 0
    return max(0, int((target - utc_now()).total_seconds() // 60) + 1)


def make_session(user_id: int) -> str:
    """Legacy self-test helper. Production sessions are opaque DB-backed tokens."""
    payload = b64url(json.dumps({"uid": user_id, "exp": int(time.time()) + SESSION_TTL, "nonce": secrets.token_hex(8)}, separators=(",", ":")).encode("utf-8"))
    signature = b64url(hmac.new(SESSION_SECRET, payload.encode("ascii"), hashlib.sha256).digest())
    return payload + "." + signature


def parse_session(token: str) -> int | None:
    """Legacy verifier kept only for migration/self-test compatibility."""
    try:
        payload, signature = token.split(".", 1)
        expected = b64url(hmac.new(SESSION_SECRET, payload.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode("utf-8"))
        if integer(data.get("exp")) < int(time.time()):
            return None
        return integer(data.get("uid")) or None
    except Exception:
        return None


def password_reused(user_id: int, password: str, current_user_row: dict | None = None) -> bool:
    rows = []
    if current_user_row:
        rows.append(current_user_row)
    rows.extend(SB.select(TABLES["password_history"], filters={"user_id": f"eq.{user_id}"}, order="created_at.desc", limit=3,
                          columns="password_hash,password_salt,password_iterations"))
    for row in rows:
        if verify_password(password, row.get("password_hash", ""), row.get("password_salt", ""), integer(row.get("password_iterations"), 210_000)):
            return True
    return False


def public_user(user: dict, employee: dict | None = None) -> dict:
    employee = employee or {}
    return {
        "id": user.get("id"),
        "username": user.get("username"),
        "role": user.get("role"),
        "employee_id": user.get("employee_id"),
        "name": employee.get("name") or (
            ADMIN_DISPLAY_NAME if user.get("role") == "admin" and str(user.get("username") or "").lower() == ADMIN_USERNAME
            else user.get("username")
        ),
        "employee_code": employee.get("code"),
        "job_role": employee.get("role"),
        "employment_type": employee.get("employment_type"),
        "weekly_target_hours": employee.get("weekly_target_hours"),
        "max_weekly_hours": employee.get("max_weekly_hours"),
        "max_daily_hours": employee.get("max_daily_hours"),
        "max_consecutive_days": employee.get("max_consecutive_days"),
        "weekly_days_off": employee.get("weekly_days_off"),
        "must_change_password": bool(user.get("must_change_password")),
        "password_changed_at": user.get("password_changed_at"),
        "last_login_at": user.get("last_login_at"),
        "account_locked_until": user.get("locked_until"),
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
    server_version = "RUMI/6.4.3"

    def log_message(self, fmt, *args):
        sys.stdout.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def add_security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "geolocation=(self), camera=(), microphone=()")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
        if self.is_secure_request():
            self.send_header("Strict-Transport-Security", "max-age=63072000; includeSubDomains")

    def send_json(self, payload, status=200, extra_headers: dict | None = None):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "private, no-store")
        self.add_security_headers()
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def ok(self, data=None, message="Thành công", *, headers=None):
        self.send_json({"ok": True, "message": message, "data": data}, 200, headers)

    def fail(self, message, status=400):
        self.send_json({"ok": False, "message": message}, status)


    def send_binary(self, payload: bytes, content_type: str, filename: str):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Cache-Control", "private, no-store")
        self.add_security_headers()
        self.end_headers()
        self.wfile.write(payload)

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

    def is_secure_request(self) -> bool:
        proto = (self.headers.get("X-Forwarded-Proto") or "").split(",", 1)[0].strip().lower()
        return proto == "https"

    def client_ip(self) -> str:
        forwarded = (self.headers.get("X-Forwarded-For") or "").split(",", 1)[0].strip()
        return forwarded or (self.client_address[0] if self.client_address else "0.0.0.0")

    def ip_hash(self) -> str:
        return hash_secret(self.client_ip(), "ip")

    def user_agent_hash(self) -> str:
        return hash_secret(self.headers.get("User-Agent", ""), "ua")

    def device_label(self) -> str:
        ua = self.headers.get("User-Agent", "")
        browser = "Trình duyệt"
        if "Edg/" in ua:
            browser = "Microsoft Edge"
        elif "Chrome/" in ua and "Chromium" not in ua:
            browser = "Google Chrome"
        elif "Safari/" in ua and "Chrome/" not in ua:
            browser = "Safari"
        elif "Firefox/" in ua:
            browser = "Firefox"
        device = "Điện thoại" if re.search(r"Mobile|Android|iPhone", ua, re.I) else "Máy tính"
        return f"{browser} · {device}"

    def session_token(self) -> str:
        return self.cookie_value(SESSION_COOKIE) or self.cookie_value(LEGACY_SESSION_COOKIE)

    def session_header(self, token: str, max_age: int | None = None) -> str:
        secure = self.is_secure_request()
        name = SESSION_COOKIE if secure else LEGACY_SESSION_COOKIE
        parts = [f"{name}={token}", "Path=/", "HttpOnly", "SameSite=Strict"]
        if secure:
            parts.append("Secure")
        if max_age is not None:
            parts.append(f"Max-Age={max_age}")
        return "; ".join(parts)

    def create_db_session(self, user_id: int) -> tuple[str, dict]:
        token = create_session_token()
        row = SB.insert(TABLES["auth_sessions"], {
            "user_id": user_id,
            "token_hash": session_token_hash(token),
            "user_agent_hash": self.user_agent_hash(),
            "ip_hash": self.ip_hash(),
            "device_label": self.device_label(),
            "last_seen_at": now_iso(),
            "idle_expires_at": iso_after(SESSION_IDLE_TTL),
            "expires_at": iso_after(SESSION_TTL),
        })
        return token, row

    def current_session(self, required: bool = True) -> dict | None:
        token = self.session_token()
        if not token:
            if required:
                raise APIError("Phiên đăng nhập đã hết hạn", 401)
            return None
        token_hash = session_token_hash(token)
        rows = SB.select(TABLES["auth_sessions"], filters={"token_hash": f"eq.{token_hash}"}, limit=1)
        if not rows:
            if required:
                raise APIError("Phiên đăng nhập không hợp lệ", 401)
            return None
        session = rows[0]
        if session.get("revoked_at"):
            if required:
                raise APIError("Phiên đăng nhập đã bị thu hồi", 401)
            return None
        now = utc_now()
        expires = parse_iso_datetime(session.get("expires_at"))
        idle_expires = parse_iso_datetime(session.get("idle_expires_at"))
        if not expires or not idle_expires or expires <= now or idle_expires <= now:
            SB.update(TABLES["auth_sessions"], {"revoked_at": now_iso(), "revoke_reason": "Hết hạn"}, {"id": f"eq.{session['id']}"})
            if required:
                raise APIError("Phiên đăng nhập đã hết hạn", 401)
            return None
        if session.get("user_agent_hash") and not hmac.compare_digest(str(session.get("user_agent_hash")), self.user_agent_hash()):
            SB.update(TABLES["auth_sessions"], {"revoked_at": now_iso(), "revoke_reason": "Thiết bị thay đổi"}, {"id": f"eq.{session['id']}"})
            raise APIError("Phiên đăng nhập không còn hợp lệ trên thiết bị này", 401)
        last_seen = parse_iso_datetime(session.get("last_seen_at"))
        if not last_seen or (now - last_seen).total_seconds() >= 300:
            updates = {"last_seen_at": now_iso(), "idle_expires_at": iso_after(SESSION_IDLE_TTL)}
            if session.get("ip_hash") != self.ip_hash():
                updates["ip_hash"] = self.ip_hash()
            SB.update(TABLES["auth_sessions"], updates, {"id": f"eq.{session['id']}"})
            session.update(updates)
        session["token_hash_current"] = token_hash
        return session

    def revoke_current_session(self, reason: str = "Đăng xuất") -> None:
        token = self.session_token()
        if token:
            SB.update(TABLES["auth_sessions"], {"revoked_at": now_iso(), "revoke_reason": reason}, {"token_hash": f"eq.{session_token_hash(token)}", "revoked_at": "is.null"})

    def current_user(self, required: bool = True) -> dict | None:
        session = self.current_session(required)
        if not session:
            return None
        user_id = integer(session.get("user_id"))
        users = SB.select(TABLES["users"], filters={"id": f"eq.{user_id}", "active": "eq.true"}, limit=1,
                          columns="id,username,password_hash,password_salt,password_iterations,must_change_password,password_changed_at,role,employee_id,active,last_login_at,locked_until,failed_login_count")
        if not users:
            if required:
                raise APIError("Tài khoản không còn hoạt động", 401)
            return None
        user = users[0]
        employee = None
        if user.get("employee_id"):
            rows = SB.select(TABLES["employees"], filters={"id": f"eq.{user['employee_id']}"}, limit=1,
                             columns="id,code,name,phone,email,role,hourly_wage,status,joined_at,employment_type,weekly_target_hours,max_weekly_hours,max_daily_hours,max_consecutive_days,weekly_days_off")
            employee = rows[0] if rows else None
            if user.get("role") == "employee" and (not employee or employee.get("status") != "Đang làm"):
                raise APIError("Tài khoản nhân viên đã bị khóa", 403)
        user["profile"] = public_user(user, employee)
        user["employee"] = employee
        user["session"] = session
        return user

    @staticmethod
    def require_role(user: dict, role: str):
        if user.get("role") != role:
            raise APIError("Bạn không có quyền thực hiện thao tác này", 403)

    def require_password_changed(self, user: dict, path: str) -> None:
        allowed = {
            "/api/auth/me", "/api/bootstrap", "/api/account/security",
            "/api/auth/change-password", "/api/auth/logout", "/api/auth/logout-all",
        }
        if user.get("must_change_password") and path not in allowed:
            raise APIError("Bạn phải đổi mật khẩu trước khi tiếp tục", 428)

    def require_csrf(self):
        if self.headers.get("X-RUMI-Request") != "1":
            raise APIError("Yêu cầu không hợp lệ", 403)
        fetch_site = (self.headers.get("Sec-Fetch-Site") or "").lower()
        if fetch_site and fetch_site not in {"same-origin", "none"}:
            raise APIError("Yêu cầu khác nguồn đã bị chặn", 403)
        origin = self.headers.get("Origin")
        if origin:
            origin_host = urlparse(origin).netloc.lower()
            request_host = (self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or "").split(",", 1)[0].strip().lower()
            if origin_host and request_host and origin_host != request_host:
                raise APIError("Nguồn yêu cầu không hợp lệ", 403)

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
            self.require_csrf()
            self.handle_api_post(parsed.path, self.parse_json())
            if parsed.path not in {"/api/auth/login", "/api/auth/logout"}:
                USER_CACHE.clear()
                PAYROLL_CACHE.clear()
        except APIError as exc:
            self.fail(str(exc), exc.status)
        except Exception as exc:
            print("POST error:", repr(exc))
            self.fail("Máy chủ gặp lỗi khi lưu dữ liệu", 500)

    def do_PUT(self):
        try:
            parsed = urlparse(self.path)
            self.require_csrf()
            self.handle_api_put(parsed.path, self.parse_json())
            USER_CACHE.clear()
            PAYROLL_CACHE.clear()
        except APIError as exc:
            self.fail(str(exc), exc.status)
        except Exception as exc:
            print("PUT error:", repr(exc))
            self.fail("Máy chủ gặp lỗi khi cập nhật dữ liệu", 500)

    def do_DELETE(self):
        try:
            self.require_csrf()
            self.handle_api_delete(urlparse(self.path).path)
            USER_CACHE.clear()
            PAYROLL_CACHE.clear()
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
        self.add_security_headers()
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

    def sync_attendance_alerts(self, user: dict) -> list[dict]:
        """Synchronize live no-check-in / no-check-out alerts for current shifts."""
        role = str(user.get("role") or "")
        employee_id = integer(user.get("employee_id"))
        cache_key = ("attendance-alerts", role, employee_id, local_now().strftime("%Y-%m-%d-%H-%M"))
        cached = ATTENDANCE_ALERT_CACHE.get(cache_key)
        if cached is not None:
            return cached

        today = local_now().date()
        start_day = (today - timedelta(days=1)).isoformat()
        end_day = today.isoformat()
        shift_filters = {
            "shift_date": f"gte.{start_day}",
            "and": f"(shift_date.lte.{end_day})",
            "status": "in.(Đã xếp,Đã xác nhận)",
        }
        if role == "employee":
            shift_filters["employee_id"] = f"eq.{employee_id}"
        base = parallel_calls(
            shifts=lambda: SB.select(TABLES["shifts"], filters=shift_filters, order="shift_date.asc,start_time.asc",
                                     columns="id,employee_id,location_id,shift_date,start_time,end_time,status,note"),
            settings=lambda: SB.select(TABLES["settings"], filters={"id": "eq.1"}, limit=1),
        )
        shifts = base["shifts"]
        if not shifts:
            ATTENDANCE_ALERT_CACHE.set(cache_key, [], 30)
            return []
        shift_ids = [x.get("id") for x in shifts]
        related = parallel_calls(
            attendance=lambda: SB.select_in(TABLES["attendance"], "shift_id", shift_ids),
            alerts=lambda: SB.select_in(TABLES["attendance_alerts"], "shift_id", shift_ids),
            employees=lambda: SB.select_in(TABLES["employees"], "id", [x.get("employee_id") for x in shifts], columns="id,code,name,role"),
            locations=lambda: SB.select_in(TABLES["locations"], "id", [x.get("location_id") for x in shifts], columns="id,name,address"),
        )
        settings = base["settings"][0] if base["settings"] else {}
        attendance_map = {integer(x.get("shift_id")): x for x in related["attendance"]}
        alert_map = {integer(x.get("shift_id")): x for x in related["alerts"]}
        employees = employee_map(related["employees"])
        locations = location_map(related["locations"])
        output = []
        alert_statuses = {"Đến giờ chấm công", "Đi trễ chưa chấm", "Nguy cơ vắng ca", "Vắng ca", "Đến giờ chấm ra", "Thiếu giờ ra"}

        for shift in shifts:
            shift_id = integer(shift.get("id"))
            eid = integer(shift.get("employee_id"))
            current = classify_shift_attendance(shift, attendance_map.get(shift_id), settings)
            existing = alert_map.get(shift_id)
            status = current["status"]
            if status not in alert_statuses:
                if existing and not existing.get("resolved_at"):
                    SB.update(TABLES["attendance_alerts"], {
                        "resolved_at": now_iso(),
                        "resolution_note": f"Tự đóng khi trạng thái chuyển thành {status}",
                        "last_detected_at": now_iso(),
                    }, {"id": f"eq.{existing['id']}"})
                continue

            same_resolved = bool(existing and existing.get("resolved_at") and existing.get("status") == status)
            payload = {
                "shift_id": shift_id,
                "employee_id": eid,
                "status": status,
                "severity": current["severity"],
                "minutes_late": current["minutes_late"],
                "first_detected_at": (existing or {}).get("first_detected_at") or now_iso(),
                "last_detected_at": now_iso(),
                "resolved_at": (existing or {}).get("resolved_at") if same_resolved else None,
                "resolution_note": (existing or {}).get("resolution_note", "") if same_resolved else "",
                "notified_employee_at": (existing or {}).get("notified_employee_at"),
                "notified_admin_at": (existing or {}).get("notified_admin_at"),
            }
            saved = SB.upsert(TABLES["attendance_alerts"], payload, "shift_id")
            employee = employees.get(eid, {})
            location = locations.get(integer(shift.get("location_id")), {})
            time_text = f"{str(shift.get('start_time'))[:5]}-{str(shift.get('end_time'))[:5]}"
            employee_name = employee.get("name") or f"NV #{eid}"
            location_name = location.get("name") or "RUMI"
            status_changed = not existing or existing.get("status") != status

            if not same_resolved and (status_changed or not saved.get("notified_employee_at")):
                employee_messages = {
                    "Đến giờ chấm công": f"Ca {time_text} tại {location_name} đã đến giờ. Hãy chấm công vào.",
                    "Đi trễ chưa chấm": f"Bạn đã trễ {current['minutes_late']} phút cho ca {time_text}. Hãy chấm công ngay hoặc báo quản lý.",
                    "Nguy cơ vắng ca": f"Ca {time_text} chưa có chấm công vào và đang được cảnh báo nguy cơ vắng.",
                    "Vắng ca": f"Ca {time_text} đã kết thúc nhưng không có chấm công vào. Trạng thái tạm ghi nhận: Vắng ca.",
                    "Đến giờ chấm ra": f"Ca {time_text} đã gần/kết thúc. Hãy chấm công ra trước khi rời cửa hàng.",
                    "Thiếu giờ ra": f"Ca {time_text} chưa có chấm công ra. Hãy gửi yêu cầu sửa công nếu bạn đã rời ca.",
                }
                self.notify_employee(eid, status, employee_messages[status], "warning" if current["severity"] != "danger" else "danger", "attendance")
                SB.update(TABLES["attendance_alerts"], {"notified_employee_at": now_iso()}, {"id": f"eq.{saved['id']}"})
                saved["notified_employee_at"] = now_iso()

            admin_needed = status in {"Đi trễ chưa chấm", "Nguy cơ vắng ca", "Vắng ca", "Thiếu giờ ra"}
            if not same_resolved and admin_needed and (status_changed or not saved.get("notified_admin_at")):
                self.notify_role("admin", f"{status}: {employee_name}", f"Ca {time_text} tại {location_name}. Trễ {current['minutes_late']} phút.", "danger" if current["severity"] == "danger" else "warning", "attendance")
                SB.update(TABLES["attendance_alerts"], {"notified_admin_at": now_iso()}, {"id": f"eq.{saved['id']}"})
                saved["notified_admin_at"] = now_iso()

            if same_resolved:
                continue
            saved.update({
                "employee_name": employee_name,
                "employee_code": employee.get("code"),
                "employee_role": employee.get("role"),
                "location_name": location_name,
                "location_address": location.get("address"),
                "shift": dict(shift),
            })
            output.append(saved)

        severity_order = {"danger": 0, "warning": 1, "info": 2}
        output.sort(key=lambda x: (severity_order.get(x.get("severity"), 9), str(x.get("shift", {}).get("start_time") or "")))
        ATTENDANCE_ALERT_CACHE.set(cache_key, output, 30)
        return output

    def enriched_shifts(self, shifts: list[dict], *, employees=None, locations=None, attendance=None) -> list[dict]:
        if not shifts:
            return []
        employee_ids = [row.get("employee_id") for row in shifts]
        location_ids = [row.get("location_id") for row in shifts]
        shift_ids = [row.get("id") for row in shifts]
        jobs = {}
        if employees is None:
            jobs["employees"] = lambda: SB.select_in(
                TABLES["employees"], "id", employee_ids,
                columns="id,code,name,role,status,hourly_wage"
            )
        if locations is None:
            jobs["locations"] = lambda: SB.select_in(
                TABLES["locations"], "id", location_ids,
                columns="id,name,address,latitude,longitude,radius_m,active"
            )
        if attendance is None:
            jobs["attendance"] = lambda: SB.select_in(
                TABLES["attendance"], "shift_id", shift_ids,
                columns="id,shift_id,employee_id,work_date,check_in,check_out,hours,payable_hours,scheduled_hours,late_minutes,early_leave_minutes,overtime_minutes,status,calculation_note,check_in_at,check_out_at,check_in_distance_m,check_out_distance_m,check_in_accuracy_m,check_out_accuracy_m"
            )
        fetched = parallel_calls(**jobs)
        employees = employees if employees is not None else fetched.get("employees", [])
        locations = locations if locations is not None else fetched.get("locations", [])
        attendance = attendance if attendance is not None else fetched.get("attendance", [])
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

    def candidate_rows(self, work_date: str, start: str, end: str, exclude_employee_id: int = 0,
                       ignore_shift_id: int = 0, required_role: str = "") -> list[dict]:
        target = datetime.strptime(work_date, "%Y-%m-%d").date()
        week_start = target - timedelta(days=target.weekday())
        week_end = week_start + timedelta(days=6)
        data = parallel_calls(
            employees=lambda: SB.select(TABLES["employees"], filters={"status": "eq.Đang làm"}, order="name.asc"),
            shifts=lambda: SB.select(TABLES["shifts"], filters={"shift_date": f"gte.{week_start.isoformat()}", "and": f"(shift_date.lte.{week_end.isoformat()})"}),
            leaves=lambda: SB.select(TABLES["leaves"], filters={"status": "eq.Đã duyệt", "start_date": f"lte.{work_date}", "and": f"(end_date.gte.{work_date})"}),
            availability=lambda: SB.select(TABLES["availability"], filters={"work_date": f"eq.{work_date}"}),
        )
        employees, shifts, leaves, availability = data["employees"], data["shifts"], data["leaves"], data["availability"]
        role_need = str(required_role or "").strip().lower()
        output = []
        for employee in employees:
            eid = integer(employee.get("id"))
            if eid == exclude_employee_id:
                continue
            day_shifts = [x for x in shifts if x.get("shift_date") == work_date]
            own_week = [x for x in shifts if integer(x.get("employee_id")) == eid and x.get("status") in {"Đã xếp", "Đã xác nhận"} and integer(x.get("id")) != ignore_shift_id]
            approved = [a for a in availability if integer(a.get("employee_id")) == eid and a.get("status") in {"Đã duyệt", "Đã xếp ca"} and time_minutes(a["start_time"]) <= time_minutes(start) and time_minutes(a["end_time"]) >= time_minutes(end)]
            busy = [x for x in day_shifts if integer(x.get("employee_id")) == eid and integer(x.get("id")) != ignore_shift_id and x.get("status") in {"Đã xếp", "Đã xác nhận"} and overlaps(x["start_time"], x["end_time"], start, end)]
            on_leave = any(integer(x.get("employee_id")) == eid for x in leaves)
            role_match = not role_need or role_need in {"bất kỳ", "bat ky", "all"} or role_need == str(employee.get("role") or "").strip().lower()
            week_hours = round(sum(max(minutes_delta(x["start_time"], x["end_time"]), 0) for x in own_week) / 60, 2)
            week_shifts = len(own_week)
            if on_leave:
                state, reason = "on_leave", "Đang nghỉ phép"
            elif busy:
                state, reason = "busy", f"Trùng ca {busy[0]['start_time']}–{busy[0]['end_time']}"
            elif not role_match:
                state, reason = "role_mismatch", f"Không đúng vị trí cần: {required_role}"
            elif not approved:
                state, reason = "unregistered", "Chưa có lịch rảnh được duyệt"
            else:
                state, reason = "available", "Phù hợp và sẵn sàng"
            score = max(0, round(100 - week_hours * 2 - week_shifts * 3 + (10 if role_match else 0)))
            output.append({
                "employee_id": eid, "code": employee.get("code"), "name": employee.get("name"),
                "role": employee.get("role"), "state": state, "reason": reason,
                "availability_id": approved[0].get("id") if approved else None,
                "week_hours": week_hours, "week_shifts": week_shifts, "score": score,
                "role_match": role_match,
            })
        priority = {"available": 0, "unregistered": 1, "role_mismatch": 2, "busy": 3, "on_leave": 4}
        output.sort(key=lambda x: (priority.get(x["state"], 9), -integer(x.get("score")), num(x.get("week_hours")), x["name"] or ""))
        return output

    def employee_shift_rule(self, employee: dict, opening: dict, shifts: list[dict], leaves: list[dict], day_offs: list[dict], allow_fixed_double: bool = False) -> dict:
        """Return eligibility, workload and a transparent ranking score for one opening."""
        eid = integer(employee.get("id"))
        work_date = str(opening.get("work_date"))
        start = str(opening.get("start_time"))[:5]
        end = str(opening.get("end_time"))[:5]
        target_day = datetime.strptime(work_date, "%Y-%m-%d").date()
        week_start = monday_of(target_day)
        week_end = week_start + timedelta(days=6)
        duration = shift_hours(start, end)
        own = [x for x in shifts if integer(x.get("employee_id")) == eid and x.get("status") in {"Đã xếp", "Đã xác nhận"}]
        week_rows = [x for x in own if week_start.isoformat() <= str(x.get("shift_date")) <= week_end.isoformat()]
        day_rows = [x for x in week_rows if str(x.get("shift_date")) == work_date]
        week_hours = round(sum(shift_hours(x["start_time"], x["end_time"]) for x in week_rows), 2)
        day_hours = round(sum(shift_hours(x["start_time"], x["end_time"]) for x in day_rows), 2)
        week_days = {str(x.get("shift_date")) for x in week_rows}
        future_days = set(week_days)
        future_days.add(work_date)
        consecutive = longest_consecutive_days(future_days)
        employment_type = employee.get("employment_type") or "Part-time"
        required_role = str(opening.get("required_role") or "").strip().lower()
        employee_role = str(employee.get("role") or "").strip().lower()
        eligible_type = opening.get("eligible_employment_type") or "Tất cả"
        max_daily = num(employee.get("max_daily_hours"), 8)
        max_weekly = min(num(employee.get("max_weekly_hours"), 56), 56)
        target_hours = num(employee.get("weekly_target_hours"), 48 if employment_type == "Full-time" else 24)
        max_consecutive = integer(employee.get("max_consecutive_days"), 6)
        weekly_days_off = integer(employee.get("weekly_days_off"), 1 if employment_type == "Full-time" else 0)
        max_work_days = max(1, 7 - weekly_days_off)

        reasons = []
        if employee.get("status") != "Đang làm":
            reasons.append("Tài khoản nhân viên không hoạt động")
        if eligible_type != "Tất cả" and employment_type != eligible_type:
            reasons.append(f"Ca chỉ dành cho {eligible_type}")
        if required_role and required_role not in {"bất kỳ", "bat ky", "all"} and required_role != employee_role:
            reasons.append(f"Cần vị trí {opening.get('required_role')}")
        if any(integer(x.get("employee_id")) == eid and str(x.get("start_date")) <= work_date <= str(x.get("end_date")) and x.get("status") == "Đã duyệt" for x in leaves):
            reasons.append("Đang nghỉ phép")
        if any(integer(x.get("employee_id")) == eid and x.get("status") == "Đã duyệt" and str(x.get("approved_date")) == work_date for x in day_offs):
            reasons.append("Ngày nghỉ tuần đã được duyệt")
        conflict = next((x for x in day_rows if overlaps(x["start_time"], x["end_time"], start, end)), None)
        if conflict:
            reasons.append(f"Trùng ca {str(conflict.get('start_time'))[:5]}–{str(conflict.get('end_time'))[:5]}")
        # Đơn tuần được phép chọn cả hai ca cố định liền nhau trong cùng ngày.
        # Quy tắc này chỉ nới giới hạn ngày lên 14 giờ cho đúng cặp 09–17 + 17–23;
        # giới hạn giờ tuần và mọi kiểm tra nghỉ/trùng ca vẫn giữ nguyên.
        fixed_pair = {(start, end)}
        fixed_pair.update({(str(x.get("start_time"))[:5], str(x.get("end_time"))[:5]) for x in day_rows})
        is_weekly_double = allow_fixed_double and {("09:00", "17:00"), ("17:00", "23:00")}.issubset(fixed_pair)
        effective_daily_limit = max(max_daily, 14) if is_weekly_double else max_daily
        if day_hours + duration > effective_daily_limit + 0.001:
            reasons.append(f"Vượt {number_text(effective_daily_limit)} giờ/ngày")
        if week_hours + duration > max_weekly + 0.001:
            reasons.append(f"Vượt {number_text(max_weekly)} giờ/tuần")
        if employment_type == "Full-time" and len(future_days) > max_work_days:
            reasons.append(f"Phải nghỉ ít nhất {weekly_days_off} ngày/tuần")
        if consecutive > max_consecutive:
            reasons.append(f"Vượt {max_consecutive} ngày làm liên tiếp")

        role_bonus = 20 if not required_role or required_role == employee_role else 0
        target_gap = max(target_hours - week_hours, 0)
        score = round(max(0, 100 + role_bonus + min(target_gap * 2, 40) - week_hours * 1.5 - len(week_days) * 3), 1)
        return {
            "allowed": not reasons,
            "reasons": reasons,
            "reason": "Phù hợp để đăng ký" if not reasons else " · ".join(reasons),
            "score": score,
            "week_hours": week_hours,
            "day_hours": day_hours,
            "week_days": len(week_days),
            "projected_week_hours": round(week_hours + duration, 2),
            "projected_days": len(future_days),
            "consecutive_days": consecutive,
            "employment_type": employment_type,
            "target_hours": target_hours,
        }

    def weekly_request_rows(self, user: dict, requests: list[dict], items: list[dict], openings: list[dict],
                            employees: list[dict], locations: list[dict], applications: list[dict],
                            shifts: list[dict]) -> list[dict]:
        """Group the seven-day registration into one transparent request per employee."""
        e_map = employee_map(employees)
        l_map = location_map(locations)
        opening_map = {integer(x.get("id")): x for x in openings}
        application_map = {integer(x.get("id")): x for x in applications}
        shift_map = {integer(x.get("id")): x for x in shifts}
        grouped: dict[int, list[dict]] = defaultdict(list)
        for raw in items:
            item = dict(raw)
            opening = opening_map.get(integer(item.get("opening_id")), {})
            application = application_map.get(integer(item.get("application_id")), {})
            shift = shift_map.get(integer(item.get("shift_id")), {})
            item.update({
                "opening_status": opening.get("status"),
                "required_count": opening.get("required_count"),
                "opening_note": opening.get("note"),
                "application_status": application.get("status") or item.get("status"),
                "application_id": application.get("id") or item.get("application_id"),
                "shift_id": shift.get("id") or item.get("shift_id"),
            })
            grouped[integer(item.get("request_id"))].append(item)

        output = []
        for raw in requests:
            row = dict(raw)
            employee = e_map.get(integer(row.get("employee_id")), {})
            location = l_map.get(integer(row.get("location_id")), {})
            request_items = sorted(grouped.get(integer(row.get("id")), []), key=lambda x: (str(x.get("work_date")), str(x.get("start_time"))))
            counts = defaultdict(int)
            status_dates: dict[str, set[str]] = defaultdict(set)
            for item in request_items:
                item_status = str(item.get("status") or "Chờ duyệt")
                counts[item_status] += 1
                status_dates[item_status].add(str(item.get("work_date")))
            selected_dates = {str(x.get("work_date")) for x in request_items}
            row.update({
                "employee_name": employee.get("name"),
                "employee_code": employee.get("code"),
                "employee_role": employee.get("role"),
                "employment_type": employee.get("employment_type", "Part-time"),
                "weekly_target_hours": employee.get("weekly_target_hours"),
                "max_weekly_hours": employee.get("max_weekly_hours"),
                "location_name": location.get("name"),
                "location_address": location.get("address"),
                "items": request_items,
                "selected_days": len(selected_dates),
                "selected_shifts": len(request_items),
                "pending_days": len(status_dates["Chờ duyệt"]),
                "approved_days": len(status_dates["Đã duyệt"]),
                "waitlist_days": len(status_dates["Danh sách chờ"]),
                "rejected_days": len(status_dates["Từ chối"]),
                "withdrawn_days": len(status_dates["Đã rút"]),
                "pending_shifts": counts["Chờ duyệt"],
                "approved_shifts": counts["Đã duyệt"],
                "waitlist_shifts": counts["Danh sách chờ"],
                "rejected_shifts": counts["Từ chối"],
                "can_edit": counts["Đã duyệt"] == 0 and row.get("status") not in {"Đã rút"},
            })
            output.append(row)
        output.sort(key=lambda x: (0 if x.get("status") == "Chờ duyệt" else 1, str(x.get("employee_name") or "")))
        return output

    def shift_market_page(self, user: dict, start: str, end: str) -> dict:
        opening_filters = {"work_date": f"gte.{start}", "and": f"(work_date.lte.{end})"}
        request_filters = {"week_start": f"eq.{monday_of(start).isoformat()}"}
        if user.get("role") == "employee":
            request_filters["employee_id"] = f"eq.{integer(user.get('employee_id'))}"
        data = parallel_calls(
            openings=lambda: SB.select(TABLES["openings"], filters=opening_filters, order="work_date.asc,start_time.asc"),
            employees=lambda: SB.select(TABLES["employees"], filters={"status": "eq.Đang làm"}, order="name.asc"),
            locations=lambda: SB.select(TABLES["locations"], filters={"active": "eq.true"}, order="name.asc"),
            shifts=lambda: SB.select(TABLES["shifts"], filters={"shift_date": f"gte.{start}", "and": f"(shift_date.lte.{end})"}, order="shift_date.asc,start_time.asc"),
            leaves=lambda: SB.select(TABLES["leaves"], filters={"status": "eq.Đã duyệt", "start_date": f"lte.{end}", "and": f"(end_date.gte.{start})"}),
            day_offs=lambda: SB.select(TABLES["day_offs"], filters={"week_start": f"gte.{monday_of(start).isoformat()}", "and": f"(week_start.lte.{monday_of(end).isoformat()})"}, order="week_start.asc"),
            weekly_requests=lambda: SB.select(TABLES["weekly_requests"], filters=request_filters, order="submitted_at.asc"),
        )
        openings = data["openings"]
        applications = SB.select_in(TABLES["applications"], "opening_id", [x.get("id") for x in openings], order="applied_at.asc")
        weekly_items = SB.select_in(TABLES["weekly_request_items"], "request_id", [x.get("id") for x in data["weekly_requests"]], order="work_date.asc,start_time.asc")
        e_map = employee_map(data["employees"])
        l_map = location_map(data["locations"])
        apps_by_opening: dict[int, list[dict]] = defaultdict(list)
        for app in applications:
            employee = e_map.get(integer(app.get("employee_id")), {})
            item = dict(app)
            item.update({
                "employee_name": employee.get("name"), "employee_code": employee.get("code"),
                "employee_role": employee.get("role"), "employment_type": employee.get("employment_type", "Part-time"),
            })
            apps_by_opening[integer(app.get("opening_id"))].append(item)
        shifts_by_opening: dict[int, list[dict]] = defaultdict(list)
        for shift in data["shifts"]:
            if shift.get("opening_id"):
                shifts_by_opening[integer(shift.get("opening_id"))].append(shift)
        output = []
        for opening in openings:
            item = dict(opening)
            oid = integer(item.get("id"))
            location = l_map.get(integer(item.get("location_id")), {})
            apps = apps_by_opening.get(oid, [])
            assigned = [x for x in shifts_by_opening.get(oid, []) if x.get("status") in {"Đã xếp", "Đã xác nhận"}]
            item.update({
                "location_name": location.get("name"), "location_address": location.get("address"),
                "approved_count": len([x for x in apps if x.get("status") == "Đã duyệt"]),
                "pending_count": len([x for x in apps if x.get("status") == "Chờ duyệt"]),
                "waitlist_count": len([x for x in apps if x.get("status") == "Danh sách chờ"]),
                "rejected_count": len([x for x in apps if x.get("status") == "Từ chối"]),
                "assigned_count": len(assigned),
                "remaining_slots": max(integer(item.get("required_count"), 1) - len(assigned), 0),
            })
            if user.get("role") == "admin":
                ranked = []
                for app in apps:
                    employee = e_map.get(integer(app.get("employee_id")), {})
                    rule = self.employee_shift_rule(employee, item, data["shifts"], data["leaves"], data["day_offs"], allow_fixed_double=True)
                    enriched = dict(app)
                    enriched.update(rule)
                    ranked.append(enriched)
                ranked.sort(key=lambda x: (0 if x.get("status") == "Chờ duyệt" else 1, -num(x.get("score")), x.get("applied_at") or ""))
                item["applications"] = ranked
            else:
                own = next((x for x in apps if integer(x.get("employee_id")) == integer(user.get("employee_id"))), None)
                employee = user.get("employee") or {}
                item["my_application"] = own
                item["rule"] = self.employee_shift_rule(employee, item, data["shifts"], data["leaves"], data["day_offs"], allow_fixed_double=True)
            output.append(item)
        compliance = self.full_time_compliance(start, end, data=data) if user.get("role") == "admin" else []
        own_day_offs = data["day_offs"] if user.get("role") == "admin" else [x for x in data["day_offs"] if integer(x.get("employee_id")) == integer(user.get("employee_id"))]
        if user.get("role") == "admin":
            own_day_offs = add_people(own_day_offs, data["employees"])
        weekly_requests = self.weekly_request_rows(
            user, data["weekly_requests"], weekly_items, openings,
            data["employees"], data["locations"], applications, data["shifts"]
        )
        return {
            "openings": output, "locations": data["locations"],
            "employees": data["employees"] if user.get("role") == "admin" else [],
            "day_offs": own_day_offs, "compliance": compliance,
            "weekly_requests": weekly_requests,
            "weekly_request": weekly_requests[0] if user.get("role") == "employee" and weekly_requests else None,
            "shifts": self.enriched_shifts(data["shifts"], employees=data["employees"], locations=data["locations"]),
        }

    def full_time_compliance(self, start: str, end: str, data: dict | None = None) -> list[dict]:
        week_start = monday_of(start)
        week_end = week_start + timedelta(days=6)
        if data is None:
            data = parallel_calls(
                employees=lambda: SB.select(TABLES["employees"], filters={"status": "eq.Đang làm", "employment_type": "eq.Full-time"}, order="name.asc"),
                shifts=lambda: SB.select(TABLES["shifts"], filters={"shift_date": f"gte.{week_start.isoformat()}", "and": f"(shift_date.lte.{week_end.isoformat()})"}),
                day_offs=lambda: SB.select(TABLES["day_offs"], filters={"week_start": f"eq.{week_start.isoformat()}"}),
            )
        employees = [x for x in data.get("employees", []) if x.get("employment_type") == "Full-time"]
        shifts = data.get("shifts", [])
        day_offs = data.get("day_offs", [])
        output = []
        for employee in employees:
            eid = integer(employee.get("id"))
            own = [x for x in shifts if integer(x.get("employee_id")) == eid and week_start.isoformat() <= str(x.get("shift_date")) <= week_end.isoformat() and x.get("status") in {"Đã xếp", "Đã xác nhận"}]
            hours = round(sum(shift_hours(x["start_time"], x["end_time"]) for x in own), 2)
            days = sorted({str(x.get("shift_date")) for x in own})
            request = next((x for x in day_offs if integer(x.get("employee_id")) == eid and str(x.get("week_start")) == week_start.isoformat()), None)
            warnings = []
            target = num(employee.get("weekly_target_hours"), 48)
            max_days = 7 - integer(employee.get("weekly_days_off"), 1)
            consecutive = longest_consecutive_days(days)
            if len(days) > max_days:
                warnings.append(f"Vượt {max_days} ngày làm/tuần")
            if consecutive > integer(employee.get("max_consecutive_days"), 6):
                warnings.append(f"Làm {consecutive} ngày liên tiếp")
            if hours < target:
                warnings.append(f"Thiếu {round(target-hours,2)} giờ mục tiêu")
            if not request or request.get("status") != "Đã duyệt":
                warnings.append("Chưa duyệt ngày nghỉ tuần")
            output.append({
                "employee_id": eid, "code": employee.get("code"), "name": employee.get("name"), "role": employee.get("role"),
                "hours": hours, "target_hours": target, "days_worked": len(days), "max_work_days": max_days,
                "consecutive_days": consecutive, "day_off": request, "warnings": warnings,
                "status": "Ổn" if not warnings else ("Cần xử lý" if len(warnings) > 1 else "Cần chú ý"),
            })
        return output

    def approve_shift_application(self, user: dict, application_id: int) -> dict:
        applications = SB.select(TABLES["applications"], filters={"id": f"eq.{application_id}"}, limit=1)
        if not applications:
            raise APIError("Không tìm thấy đơn đăng ký ca", 404)
        application = applications[0]
        openings = SB.select(TABLES["openings"], filters={"id": f"eq.{application['opening_id']}"}, limit=1)
        employees = SB.select(TABLES["employees"], filters={"id": f"eq.{application['employee_id']}"}, limit=1)
        if not openings or not employees:
            raise APIError("Ca hoặc nhân viên không còn tồn tại", 404)
        opening, employee = openings[0], employees[0]
        if opening.get("status") in {"Đã chốt", "Đã hủy"}:
            raise APIError("Ca đã chốt hoặc đã hủy")
        assigned = SB.select(TABLES["shifts"], filters={"opening_id": f"eq.{opening['id']}", "status": "in.(Đã xếp,Đã xác nhận)"})
        if len(assigned) >= integer(opening.get("required_count"), 1):
            raise APIError("Ca đã đủ số nhân viên cần", 409)
        week_start = monday_of(opening["work_date"])
        week_end = week_start + timedelta(days=6)
        data = parallel_calls(
            shifts=lambda: SB.select(TABLES["shifts"], filters={"shift_date": f"gte.{week_start.isoformat()}", "and": f"(shift_date.lte.{week_end.isoformat()})"}),
            leaves=lambda: SB.select(TABLES["leaves"], filters={"status": "eq.Đã duyệt", "start_date": f"lte.{opening['work_date']}", "and": f"(end_date.gte.{opening['work_date']})"}),
            day_offs=lambda: SB.select(TABLES["day_offs"], filters={"week_start": f"eq.{week_start.isoformat()}"}),
        )
        rule = self.employee_shift_rule(employee, opening, data["shifts"], data["leaves"], data["day_offs"], allow_fixed_double=bool(application.get("weekly_request_id")))
        if not rule["allowed"]:
            raise APIError(rule["reason"], 409)
        existing = SB.select(TABLES["shifts"], filters={"application_id": f"eq.{application_id}"}, limit=1)
        if not existing:
            SB.insert(TABLES["shifts"], {
                "employee_id": employee["id"], "location_id": opening["location_id"], "shift_date": opening["work_date"],
                "start_time": opening["start_time"], "end_time": opening["end_time"], "note": opening.get("note", ""),
                "status": "Đã xếp", "created_by": user["id"], "opening_id": opening["id"], "application_id": application_id,
            })
        updated = SB.update(TABLES["applications"], {
            "status": "Đã duyệt", "score_snapshot": rule["score"], "reviewed_at": now_iso(), "reviewed_by": user["id"],
        }, {"id": f"eq.{application_id}"})[0]
        self.notify_employee(integer(employee["id"]), "Đăng ký ca đã được duyệt", f"Ca {opening['work_date']} {str(opening['start_time'])[:5]}–{str(opening['end_time'])[:5]} đã được xếp.", "schedule", "shifts")
        return updated

    def payroll_from_rows(self, employees, attendance, adjustments, payments, shifts=None, settings=None) -> list[dict]:
        """Build monthly payroll with schedule, attendance and payable time separated.

        Official shifts come from rumi_shifts instead of attendance. A future or
        unclocked shift therefore remains visible as scheduled work rather than
        incorrectly appearing as "0 ca · 0 giờ".
        """
        shifts = shifts or []
        settings = settings or {}
        now_local = local_now()
        today_local = now_local.date()

        totals: dict[int, dict] = defaultdict(lambda: {
            "actual_hours": 0.0,
            "payable_hours": 0.0,
            "scheduled_hours": 0.0,
            "late_minutes": 0,
            "early_leave_minutes": 0,
            "overtime_minutes": 0,
            "attendance_count": 0,
            "scheduled_shift_count": 0,
            "completed_shift_count": 0,
            "upcoming_shift_count": 0,
            "active_shift_count": 0,
            "pending_checkin_count": 0,
            "late_unclocked_count": 0,
            "no_show_risk_count": 0,
            "absent_shift_count": 0,
            "missing_attendance_count": 0,
            "incomplete_attendance_count": 0,
        })

        attendance_by_shift = {
            integer(row.get("shift_id")): row
            for row in attendance
            if integer(row.get("shift_id"))
        }

        for shift in shifts:
            eid = integer(shift.get("employee_id"))
            if not eid:
                continue
            bucket = totals[eid]
            scheduled = calculate_hours(
                str(shift.get("start_time") or "00:00"),
                str(shift.get("end_time") or "00:00"),
            )
            bucket["scheduled_hours"] += scheduled
            bucket["scheduled_shift_count"] += 1

            try:
                shift_day = datetime.strptime(str(shift.get("shift_date"))[:10], "%Y-%m-%d").date()
                start_dt = datetime.combine(
                    shift_day,
                    datetime.strptime(str(shift.get("start_time"))[:5], "%H:%M").time(),
                    tzinfo=LOCAL_TZ,
                )
                end_dt = datetime.combine(
                    shift_day,
                    datetime.strptime(str(shift.get("end_time"))[:5], "%H:%M").time(),
                    tzinfo=LOCAL_TZ,
                )
            except Exception:
                shift_day = today_local
                start_dt = now_local
                end_dt = now_local

            att = attendance_by_shift.get(integer(shift.get("id")))
            has_in = bool(att and (att.get("check_in") or att.get("check_in_at")))
            has_out = bool(att and (att.get("check_out") or att.get("check_out_at")))

            live = classify_shift_attendance(shift, att, settings, now_local)
            live_status = live.get("status")
            if live_status in {"Chưa đến ca", "Có thể chấm vào"}:
                bucket["upcoming_shift_count"] += 1
            elif live_status == "Đến giờ chấm công":
                bucket["pending_checkin_count"] += 1
            elif live_status == "Đi trễ chưa chấm":
                bucket["late_unclocked_count"] += 1
            elif live_status == "Nguy cơ vắng ca":
                bucket["no_show_risk_count"] += 1
            elif live_status == "Vắng ca":
                bucket["absent_shift_count"] += 1
                bucket["missing_attendance_count"] += 1
            elif live_status in {"Đang làm", "Đến giờ chấm ra"}:
                bucket["active_shift_count"] += 1
            elif live_status == "Thiếu giờ ra":
                bucket["incomplete_attendance_count"] += 1

        for row in attendance:
            eid = integer(row.get("employee_id"))
            if not eid:
                continue
            bucket = totals[eid]
            worked_minutes = integer(row.get("worked_minutes"))
            if worked_minutes > 0:
                actual = round(worked_minutes / 60, 2)
            elif row.get("check_in") and row.get("check_out"):
                actual = calculate_hours(str(row.get("check_in")), str(row.get("check_out")))
            else:
                actual = num(row.get("hours"))

            payable = num(row.get("payable_hours"), num(row.get("hours")))
            bucket["actual_hours"] += actual
            bucket["payable_hours"] += payable
            if not shifts and num(row.get("scheduled_hours")):
                bucket["scheduled_hours"] += num(row.get("scheduled_hours"))
                bucket["scheduled_shift_count"] += 1
            bucket["late_minutes"] += integer(row.get("late_minutes"))
            bucket["early_leave_minutes"] += integer(row.get("early_leave_minutes"))
            bucket["overtime_minutes"] += integer(
                row.get("overtime_approved_minutes"),
                integer(row.get("overtime_minutes")),
            )
            has_out = bool(row.get("check_out") or row.get("check_out_at"))
            if has_out and row.get("status") != "Đang làm":
                bucket["attendance_count"] += 1
                bucket["completed_shift_count"] += 1

        adj_map = {integer(x.get("employee_id")): x for x in adjustments}
        pay_map = {integer(x.get("employee_id")): x for x in payments}
        output = []

        for employee in employees:
            eid = integer(employee.get("id"))
            t = totals[eid]
            adjustment = adj_map.get(eid, {})
            payment = pay_map.get(eid, {})
            payable_hours = round(t["payable_hours"], 2)
            actual_hours = round(t["actual_hours"], 2)
            scheduled_hours = round(t["scheduled_hours"], 2)
            bonus = num(adjustment.get("bonus"))
            penalty = num(adjustment.get("penalty"))
            advance = num(adjustment.get("advance_pay"))
            base_salary = round(payable_hours * num(employee.get("hourly_wage")))
            estimated_salary = round(scheduled_hours * num(employee.get("hourly_wage")))
            total = round(base_salary + bonus - penalty - advance)

            unresolved = (
                t["missing_attendance_count"]
                + t["incomplete_attendance_count"]
                + t["pending_checkin_count"]
                + t["late_unclocked_count"]
                + t["no_show_risk_count"]
                + t["active_shift_count"]
                + t["upcoming_shift_count"]
            )

            if t["incomplete_attendance_count"]:
                payroll_state = "Thiếu giờ ra"
            elif t["absent_shift_count"]:
                payroll_state = "Vắng ca"
            elif t["no_show_risk_count"]:
                payroll_state = "Nguy cơ vắng ca"
            elif t["late_unclocked_count"]:
                payroll_state = "Đi trễ chưa chấm"
            elif t["pending_checkin_count"]:
                payroll_state = "Đến giờ chấm công"
            elif t["active_shift_count"]:
                payroll_state = "Đang làm"
            elif t["upcoming_shift_count"]:
                payroll_state = "Chưa đến ca"
            elif t["scheduled_shift_count"] == 0 and payable_hours == 0:
                payroll_state = "Không có lịch"
            elif payable_hours > 0:
                payroll_state = "Đủ dữ liệu"
            else:
                payroll_state = "Chưa có công"

            eligible_for_payment = bool(total > 0 and unresolved == 0)

            output.append({
                "employee_id": eid,
                "code": employee.get("code"),
                "name": employee.get("name"),
                "role": employee.get("role"),
                "hourly_wage": num(employee.get("hourly_wage")),
                "hours": payable_hours,
                "actual_hours": actual_hours,
                "payable_hours": payable_hours,
                "scheduled_hours": scheduled_hours,
                "late_minutes": t["late_minutes"],
                "early_leave_minutes": t["early_leave_minutes"],
                "overtime_minutes": t["overtime_minutes"],
                "attendance_count": t["attendance_count"],
                "scheduled_shift_count": t["scheduled_shift_count"],
                "completed_shift_count": t["completed_shift_count"],
                "upcoming_shift_count": t["upcoming_shift_count"],
                "active_shift_count": t["active_shift_count"],
                "pending_checkin_count": t["pending_checkin_count"],
                "late_unclocked_count": t["late_unclocked_count"],
                "no_show_risk_count": t["no_show_risk_count"],
                "absent_shift_count": t["absent_shift_count"],
                "missing_attendance_count": t["missing_attendance_count"],
                "incomplete_attendance_count": t["incomplete_attendance_count"],
                "payroll_state": payroll_state,
                "eligible_for_payment": eligible_for_payment,
                "base_salary": base_salary,
                "estimated_salary": estimated_salary,
                "bonus": bonus,
                "penalty": penalty,
                "advance_pay": advance,
                "note": adjustment.get("note", ""),
                "payment_status": payment.get("status", "Chưa thanh toán"),
                "paid_at": payment.get("paid_at"),
                "total": total,
            })
        return output

    def build_payroll(self, month: str, employee_id: int | None = None) -> list[dict]:
        cache_key = ("live-v2", month, employee_id or 0)
        cached = PAYROLL_CACHE.get(cache_key)
        if cached is not None:
            return cached
        start, end = month_bounds(month)
        employee_filters = {}
        attendance_filters = {"work_date": f"gte.{start}", "and": f"(work_date.lt.{end})"}
        shift_filters = {
            "shift_date": f"gte.{start}",
            "and": f"(shift_date.lt.{end})",
            "status": "in.(Đã xếp,Đã xác nhận)",
        }
        adjustment_filters = {"month": f"eq.{month}"}
        payment_filters = {"month": f"eq.{month}"}
        if employee_id:
            employee_filters["id"] = f"eq.{employee_id}"
            attendance_filters["employee_id"] = f"eq.{employee_id}"
            shift_filters["employee_id"] = f"eq.{employee_id}"
            adjustment_filters["employee_id"] = f"eq.{employee_id}"
            payment_filters["employee_id"] = f"eq.{employee_id}"

        data = parallel_calls(
            employees=lambda: SB.select(
                TABLES["employees"],
                filters=employee_filters,
                order="name.asc",
                columns="id,code,name,role,hourly_wage,status",
            ),
            shifts=lambda: SB.select(
                TABLES["shifts"],
                filters=shift_filters,
                order="shift_date.asc,start_time.asc",
                columns="id,employee_id,shift_date,start_time,end_time,status",
            ),
            attendance=lambda: SB.select(
                TABLES["attendance"],
                filters=attendance_filters,
                columns=(
                    "shift_id,employee_id,hours,payable_hours,scheduled_hours,"
                    "scheduled_minutes,worked_minutes,late_minutes,early_leave_minutes,"
                    "overtime_minutes,overtime_approved_minutes,work_date,check_in,check_out,"
                    "check_in_at,check_out_at,status,review_status"
                ),
            ),
            adjustments=lambda: SB.select(
                TABLES["payroll_adjustments"],
                filters=adjustment_filters,
                columns="employee_id,bonus,penalty,advance_pay,note,month",
            ),
            payments=lambda: SB.select(
                TABLES["payroll_payments"],
                filters=payment_filters,
                columns="employee_id,status,paid_at,month",
            ),
            settings=lambda: SB.select(TABLES["settings"], filters={"id": "eq.1"}, limit=1),
        )
        relevant_ids = {
            integer(x.get("employee_id"))
            for group in (
                data["shifts"],
                data["attendance"],
                data["adjustments"],
                data["payments"],
            )
            for x in group
        }
        employees = [
            x
            for x in data["employees"]
            if x.get("status") == "Đang làm" or integer(x.get("id")) in relevant_ids
        ]
        rows = self.payroll_from_rows(
            employees,
            data["attendance"],
            data["adjustments"],
            data["payments"],
            data["shifts"],
            data["settings"][0] if data["settings"] else {},
        )
        PAYROLL_CACHE.set(cache_key, rows, 20)
        return rows

    def payroll_run(self, month: str) -> dict | None:
        rows = SB.select(TABLES["payroll_runs"], filters={"month": f"eq.{month}"}, limit=1)
        return rows[0] if rows else None

    def payroll_page(self, user: dict, month: str) -> dict:
        employee_id = integer(user.get("employee_id")) if user.get("role") == "employee" else None
        run = self.payroll_run(month)
        if run and run.get("status") == "Đã chốt":
            filters = {"run_id": f"eq.{run['id']}"}
            if employee_id:
                filters["employee_id"] = f"eq.{employee_id}"
            locked_data = parallel_calls(
                items=lambda: SB.select(TABLES["payroll_items"], filters=filters, order="employee_name.asc"),
                payments=lambda: SB.select(TABLES["payroll_payments"], filters={"month": f"eq.{month}"} | ({"employee_id": f"eq.{employee_id}"} if employee_id else {})),
            )
            items, payments = locked_data["items"], locked_data["payments"]
            pmap = {integer(x.get("employee_id")): x for x in payments}
            rows = []
            for item in items:
                payment = pmap.get(integer(item.get("employee_id")), {})
                row = dict(item)
                row["code"] = row.pop("employee_code", "")
                row["name"] = row.pop("employee_name", "")
                row["role"] = row.pop("employee_role", "")
                row["hours"] = num(row.get("payable_hours"))
                row["estimated_salary"] = round(num(row.get("scheduled_hours")) * num(row.get("hourly_wage")))
                row["scheduled_shift_count"] = integer(row.get("scheduled_shift_count"))
                row["completed_shift_count"] = integer(row.get("completed_shift_count"), integer(row.get("attendance_count")))
                row["upcoming_shift_count"] = integer(row.get("upcoming_shift_count"))
                row["active_shift_count"] = integer(row.get("active_shift_count"))
                row["pending_checkin_count"] = integer(row.get("pending_checkin_count"))
                row["late_unclocked_count"] = integer(row.get("late_unclocked_count"))
                row["no_show_risk_count"] = integer(row.get("no_show_risk_count"))
                row["absent_shift_count"] = integer(row.get("absent_shift_count"))
                row["missing_attendance_count"] = integer(row.get("missing_attendance_count"))
                row["incomplete_attendance_count"] = integer(row.get("incomplete_attendance_count"))
                row["payroll_state"] = row.get("payroll_state") or ("Đủ dữ liệu" if num(row.get("payable_hours")) > 0 else "Chưa có công")
                row["eligible_for_payment"] = bool(row.get("eligible_for_payment"))
                row["payment_status"] = payment.get("status", "Chưa thanh toán")
                row["paid_at"] = payment.get("paid_at")
                rows.append(row)
        else:
            rows = self.build_payroll(month, employee_id)
        meta = run or {"month": month, "status": "Chưa tạo", "generated_at": None, "locked_at": None}
        return {"month": month, "run": meta, "items": rows}

    def save_payroll_draft(self, user: dict, month: str, note: str = "") -> dict:
        existing = self.payroll_run(month)
        if existing and existing.get("status") == "Đã chốt":
            raise APIError("Bảng lương tháng này đã chốt. Hãy mở khóa trước khi tính lại.", 409)
        rows = self.build_payroll(month)
        run = SB.upsert(TABLES["payroll_runs"], {
            "month": month, "status": "Nháp", "generated_at": now_iso(), "locked_at": None,
            "generated_by": user.get("id"), "note": note,
            "total_hours": round(sum(num(x.get("payable_hours")) for x in rows), 2),
            "total_amount": round(sum(num(x.get("total")) for x in rows)),
            "employee_count": len(rows),
        }, "month")
        SB.delete(TABLES["payroll_items"], {"run_id": f"eq.{run['id']}"})
        payload = [{
            "run_id": run["id"], "employee_id": x["employee_id"], "employee_code": x.get("code", ""),
            "employee_name": x.get("name", ""), "employee_role": x.get("role", ""),
            "attendance_count": x.get("attendance_count", 0),
            "scheduled_shift_count": x.get("scheduled_shift_count", 0),
            "completed_shift_count": x.get("completed_shift_count", 0),
            "upcoming_shift_count": x.get("upcoming_shift_count", 0),
            "active_shift_count": x.get("active_shift_count", 0),
            "pending_checkin_count": x.get("pending_checkin_count", 0),
            "late_unclocked_count": x.get("late_unclocked_count", 0),
            "no_show_risk_count": x.get("no_show_risk_count", 0),
            "absent_shift_count": x.get("absent_shift_count", 0),
            "missing_attendance_count": x.get("missing_attendance_count", 0),
            "incomplete_attendance_count": x.get("incomplete_attendance_count", 0),
            "payroll_state": x.get("payroll_state", "Chưa có dữ liệu"),
            "eligible_for_payment": bool(x.get("eligible_for_payment")),
            "hourly_wage": x.get("hourly_wage", 0), "scheduled_hours": x.get("scheduled_hours", 0),
            "actual_hours": x.get("actual_hours", 0), "payable_hours": x.get("payable_hours", 0),
            "late_minutes": x.get("late_minutes", 0), "early_leave_minutes": x.get("early_leave_minutes", 0),
            "overtime_minutes": x.get("overtime_minutes", 0), "base_salary": x.get("base_salary", 0),
            "bonus": x.get("bonus", 0), "penalty": x.get("penalty", 0), "advance_pay": x.get("advance_pay", 0),
            "total": x.get("total", 0), "note": x.get("note", ""),
        } for x in rows]
        SB.insert_many(TABLES["payroll_items"], payload)
        PAYROLL_CACHE.clear()
        return self.payroll_page(user, month)

    def build_dashboard(self, user: dict) -> dict:
        role = user.get("role")
        today = today_text()
        month = current_month()
        month_start, month_end = month_bounds(month)
        attendance_alerts = self.sync_attendance_alerts(user)
        if role == "admin":
            data = parallel_calls(
                employees=lambda: SB.select(TABLES["employees"], filters={"status": "eq.Đang làm"},
                                            columns="id,code,name,role,hourly_wage,status"),
                shifts=lambda: SB.select(TABLES["shifts"], filters={"shift_date": f"eq.{today}"}, order="start_time.asc",
                                         columns="id,employee_id,location_id,shift_date,start_time,end_time,status,note"),
                locations=lambda: SB.select(TABLES["locations"], columns="id,name,address,radius_m,active"),
                attendance=lambda: SB.select(TABLES["attendance"],
                                             filters={"work_date": f"gte.{month_start}", "and": f"(work_date.lt.{month_end})"},
                                             columns="id,shift_id,employee_id,work_date,hours,status,check_in,check_out,check_in_distance_m,check_in_accuracy_m"),
                availability=lambda: SB.select(TABLES["availability"], filters={"status": "eq.Chờ duyệt"}, columns="id"),
                leaves=lambda: SB.select(TABLES["leaves"], filters={"status": "eq.Chờ duyệt"}, columns="id"),
                changes=lambda: SB.select(TABLES["shift_changes"], filters={"status": "eq.Chờ xử lý"}, columns="id"),
                inventory=lambda: SB.select(TABLES["inventory"], columns="id,quantity,min_stock"),
                purchases=lambda: SB.select(TABLES["purchase_requests"], filters={"status": "eq.Chờ mua"}, columns="id"),
                adjustments=lambda: SB.select(TABLES["payroll_adjustments"], filters={"month": f"eq.{month}"},
                                              columns="employee_id,bonus,penalty,advance_pay,note,month"),
                payments=lambda: SB.select(TABLES["payroll_payments"], filters={"month": f"eq.{month}"},
                                           columns="employee_id,status,paid_at,month"),
                notifications=lambda: self.get_notifications(user, limit=20),
            )
            attendance_today = [x for x in data["attendance"] if x.get("work_date") == today]
            shifts_today = self.enriched_shifts(
                data["shifts"], employees=data["employees"], locations=data["locations"], attendance=attendance_today
            )
            payroll = self.payroll_from_rows(data["employees"], data["attendance"], data["adjustments"], data["payments"])
            notifications = data["notifications"]
            return {
                "role": role,
                "stats": {
                    "employees": len(data["employees"]),
                    "shifts_today": len(shifts_today),
                    "working_now": len([x for x in attendance_today if x.get("status") == "Đang làm"]),
                    "pending_schedule": len(data["availability"]),
                    "pending_requests": len(data["leaves"]) + len(data["changes"]),
                    "low_stock": len([x for x in data["inventory"] if num(x.get("quantity")) <= num(x.get("min_stock"))]),
                    "pending_purchase": len(data["purchases"]),
                    "payroll_total": sum(num(x.get("total")) for x in payroll),
                    "attendance_alerts": len(attendance_alerts),
                    "attendance_danger": len([x for x in attendance_alerts if x.get("severity") == "danger"]),
                },
                "attendance_alerts": attendance_alerts[:10],
                "today_shifts": shifts_today,
                "notifications": notifications[:6],
                "unread_count": len([x for x in notifications if not x.get("read_at")]),
            }
        employee_id = integer(user.get("employee_id"))
        employee = user.get("employee") or {}
        data = parallel_calls(
            shifts=lambda: SB.select(TABLES["shifts"],
                                     filters={"employee_id": f"eq.{employee_id}", "shift_date": f"gte.{today}"},
                                     order="shift_date.asc,start_time.asc", limit=20,
                                     columns="id,employee_id,location_id,shift_date,start_time,end_time,status,note"),
            locations=lambda: SB.select(TABLES["locations"], filters={"active": "eq.true"},
                                        columns="id,name,address,radius_m,active"),
            attendance=lambda: SB.select(TABLES["attendance"],
                                         filters={"employee_id": f"eq.{employee_id}", "work_date": f"gte.{month_start}", "and": f"(work_date.lt.{month_end})"},
                                         columns="id,shift_id,employee_id,work_date,hours,status,check_in,check_out,check_in_distance_m,check_in_accuracy_m"),
            availability=lambda: SB.select(TABLES["availability"], filters={"employee_id": f"eq.{employee_id}", "status": "eq.Chờ duyệt"}, columns="id"),
            leaves=lambda: SB.select(TABLES["leaves"], filters={"employee_id": f"eq.{employee_id}", "status": "eq.Chờ duyệt"}, columns="id"),
            changes=lambda: SB.select(TABLES["shift_changes"], filters={"requester_id": f"eq.{employee_id}", "status": "eq.Chờ xử lý"}, columns="id"),
            adjustments=lambda: SB.select(TABLES["payroll_adjustments"], filters={"employee_id": f"eq.{employee_id}", "month": f"eq.{month}"},
                                          columns="employee_id,bonus,penalty,advance_pay,note,month"),
            payments=lambda: SB.select(TABLES["payroll_payments"], filters={"employee_id": f"eq.{employee_id}", "month": f"eq.{month}"},
                                       columns="employee_id,status,paid_at,month"),
            notifications=lambda: self.get_notifications(user, limit=20),
        )
        shifts = self.enriched_shifts(data["shifts"], employees=[employee], locations=data["locations"], attendance=data["attendance"])
        payroll = self.payroll_from_rows([employee], data["attendance"], data["adjustments"], data["payments"])
        notifications = data["notifications"]
        return {
            "role": role,
            "stats": {
                "upcoming_shifts": len(shifts),
                "month_hours": round(sum(num(x.get("hours")) for x in data["attendance"]), 2),
                "pending_requests": len(data["availability"]) + len(data["leaves"]) + len(data["changes"]),
                "unread_notifications": len([x for x in notifications if not x.get("read_at")]),
                "estimated_salary": payroll[0]["total"] if payroll else 0,
                "attendance_alerts": len(attendance_alerts),
            },
            "attendance_alerts": attendance_alerts[:6],
            "today_shifts": [x for x in shifts if x.get("shift_date") == today],
            "upcoming_shifts": shifts[:6],
            "notifications": notifications[:6],
            "unread_count": len([x for x in notifications if not x.get("read_at")]),
        }

    def get_notifications(self, user: dict, *, limit: int | None = 100, unread_only: bool = False) -> list[dict]:
        eid = integer(user.get("employee_id"))
        role = str(user.get("role") or "")
        filters = {"audience_role": f"eq.{role}"} if not eid else {"or": f"(employee_id.eq.{eid},audience_role.eq.{role})"}
        if unread_only:
            filters["read_at"] = "is.null"
        columns = "id,employee_id,audience_role,title,message,type,link,read_at,created_at"
        if limit is None:
            return SB.select_all(TABLES["notifications"], filters=filters, order="created_at.desc", columns=columns)
        return SB.select(TABLES["notifications"], filters=filters, order="created_at.desc", limit=limit, columns=columns)

    def build_requests_page(self, user: dict) -> dict:
        employee_mode = user.get("role") == "employee"
        availability_filters = {"employee_id": f"eq.{user['employee_id']}"} if employee_mode else {}
        leave_filters = {"employee_id": f"eq.{user['employee_id']}"} if employee_mode else {}
        change_filters = {"requester_id": f"eq.{user['employee_id']}"} if employee_mode else {}
        data = parallel_calls(
            availability=lambda: SB.select(TABLES["availability"], filters=availability_filters, order="work_date.desc,start_time.asc"),
            leaves=lambda: SB.select(TABLES["leaves"], filters=leave_filters, order="created_at.desc"),
            changes=lambda: SB.select(TABLES["shift_changes"], filters=change_filters, order="created_at.desc"),
            employees=lambda: SB.select(TABLES["employees"], columns="id,code,name,role,status"),
            upcoming=lambda: SB.select(
                TABLES["shifts"],
                filters={"employee_id": f"eq.{user['employee_id']}", "shift_date": f"gte.{today_text()}"},
                order="shift_date.asc,start_time.asc", limit=40,
                columns="id,employee_id,location_id,shift_date,start_time,end_time,status,note"
            ) if employee_mode else [],
        )
        shifts = SB.select_in(
            TABLES["shifts"], "id", [x.get("shift_id") for x in data["changes"]],
            columns="id,employee_id,location_id,shift_date,start_time,end_time,status,note"
        )
        shift_map = {integer(x.get("id")): x for x in shifts}
        e_map = employee_map(data["employees"])
        changes = []
        for row in data["changes"]:
            item = dict(row)
            requester = e_map.get(integer(item.get("requester_id")), {})
            replacement = e_map.get(integer(item.get("replacement_employee_id")), {})
            item["employee_name"] = requester.get("name")
            item["replacement_name"] = replacement.get("name")
            item["shift"] = shift_map.get(integer(item.get("shift_id")))
            changes.append(item)
        upcoming = self.enriched_shifts(data["upcoming"]) if employee_mode else []
        return {
            "availability": add_people(data["availability"], data["employees"]),
            "leaves": add_people(data["leaves"], data["employees"]),
            "changes": changes,
            "upcoming_shifts": upcoming,
        }

    def build_attendance_rows(self, user: dict, month: str) -> list[dict]:
        """Return real attendance plus synthetic rows for official shifts without clocks."""
        start, end = month_bounds(month)
        attendance_filters = {"work_date": f"gte.{start}", "and": f"(work_date.lt.{end})"}
        shift_filters = {"shift_date": f"gte.{start}", "and": f"(shift_date.lt.{end})", "status": "in.(Đã xếp,Đã xác nhận)"}
        if user.get("role") == "employee":
            attendance_filters["employee_id"] = f"eq.{user['employee_id']}"
            shift_filters["employee_id"] = f"eq.{user['employee_id']}"
        data = parallel_calls(
            attendance=lambda: SB.select(TABLES["attendance"], filters=attendance_filters, order="work_date.desc,check_in.desc"),
            shifts=lambda: SB.select(TABLES["shifts"], filters=shift_filters, order="shift_date.desc,start_time.desc",
                                     columns="id,employee_id,location_id,shift_date,start_time,end_time,status,note"),
            settings=lambda: SB.select(TABLES["settings"], filters={"id": "eq.1"}, limit=1),
        )
        rows = data["attendance"]
        shifts = data["shifts"]
        settings = data["settings"][0] if data["settings"] else {}
        employee_ids = list({integer(x.get("employee_id")) for x in rows + shifts if integer(x.get("employee_id"))})
        employees = SB.select_in(TABLES["employees"], "id", employee_ids, columns="id,code,name,role")
        enriched_shifts = self.enriched_shifts(shifts, employees=employees, attendance=rows)
        shift_map = {integer(x.get("id")): x for x in enriched_shifts}
        attendance_by_shift = {integer(x.get("shift_id")): x for x in rows if integer(x.get("shift_id"))}
        output = add_people(rows, employees)
        for item in output:
            item["shift"] = shift_map.get(integer(item.get("shift_id")))
            shift = item.get("shift")
            if shift and item.get("check_in"):
                derived = attendance_metrics(shift, item.get("check_in"), item.get("check_out"))
                for key, value in derived.items():
                    if key not in item or item.get(key) in (None, "", 0, 0.0):
                        item[key] = value
            item["actual_hours"] = num(item.get("worked_minutes")) / 60 if integer(item.get("worked_minutes")) else calculate_hours(str(item.get("check_in") or ""), str(item.get("check_out") or ""))
            item["is_synthetic"] = False

        people = employee_map(employees)
        for shift in enriched_shifts:
            shift_id = integer(shift.get("id"))
            if shift_id in attendance_by_shift:
                continue
            live = classify_shift_attendance(shift, None, settings)
            scheduled = shift_hours(str(shift.get("start_time")), str(shift.get("end_time")))
            employee = people.get(integer(shift.get("employee_id")), {})
            output.append({
                "id": None,
                "shift_id": shift_id,
                "employee_id": shift.get("employee_id"),
                "employee_name": employee.get("name"),
                "employee_code": employee.get("code"),
                "employee_role": employee.get("role"),
                "work_date": shift.get("shift_date"),
                "check_in": None,
                "check_out": None,
                "hours": 0,
                "actual_hours": 0,
                "payable_hours": 0,
                "scheduled_hours": scheduled,
                "late_minutes": live.get("minutes_late", 0),
                "early_leave_minutes": 0,
                "overtime_minutes": 0,
                "status": live.get("status"),
                "calculation_note": f"Có ca chính thức {str(shift.get('start_time'))[:5]}-{str(shift.get('end_time'))[:5]} nhưng chưa có chấm công hợp lệ.",
                "risk_level": "Cao" if live.get("severity") == "danger" else ("Trung bình" if live.get("severity") == "warning" else "Thấp"),
                "review_status": "Chờ duyệt" if live.get("severity") == "danger" else "Không cần duyệt",
                "is_synthetic": True,
                "shift": shift,
            })
        output.sort(key=lambda x: (str(x.get("work_date") or ""), str((x.get("shift") or {}).get("start_time") or x.get("check_in") or "")), reverse=True)
        return output

    def build_inventory_page(self, user: dict) -> dict:
        employee_filters = {"deleted_at": "is.null"}
        if user.get("role") != "admin":
            employee_filters["employee_id"] = f"eq.{user['employee_id']}"
        data = parallel_calls(
            items=lambda: SB.select(TABLES["inventory"], order="category.asc,name.asc"),
            withdrawals=lambda: SB.select_all(TABLES["withdrawals"], filters=employee_filters, order="taken_at.desc,id.desc"),
            employees=lambda: SB.select(TABLES["employees"], filters={"status": "eq.Đang làm"}, order="name.asc", columns="id,code,name,role"),
        )
        data["items"].sort(key=lambda x: (0 if num(x.get("quantity")) <= num(x.get("min_stock")) else 1, str(x.get("category")), str(x.get("name"))))
        inventory = {integer(x.get("id")): x for x in data["items"]}
        employees = employee_map(data["employees"])
        for item in data["withdrawals"]:
            inv = inventory.get(integer(item.get("inventory_id")), {})
            emp = employees.get(integer(item.get("employee_id")), {})
            item["item_name"] = inv.get("name", "Nguyên liệu")
            item["unit"] = inv.get("unit", "")
            item["employee_name"] = emp.get("name")
        return {"items": data["items"], "withdrawals": data["withdrawals"], "employees": data["employees"]}

    # ------------------------------------------------------------------
    # GET routes
    # ------------------------------------------------------------------
    def handle_api_get(self, path: str, query: dict):
        if path == "/api/health":
            parallel_calls(
                employees=lambda: SB.select(TABLES["employees"], limit=1, columns="id"),
                payroll_runs=lambda: SB.select(TABLES["payroll_runs"], limit=1, columns="id"),
                shift_openings=lambda: SB.select(TABLES["openings"], limit=1, columns="id"),
                auth_sessions=lambda: SB.select(TABLES["auth_sessions"], limit=1, columns="id"),
                attendance_events=lambda: SB.select(TABLES["attendance_events"], limit=1, columns="id"),
                attendance_alerts=lambda: SB.select(TABLES["attendance_alerts"], limit=1, columns="id"),
                weekly_requests=lambda: SB.select(TABLES["weekly_requests"], limit=1, columns="id"),
                weekly_request_items=lambda: SB.select(TABLES["weekly_request_items"], limit=1, columns="id"),
                shift_reassignments=lambda: SB.select(TABLES["shift_reassignments"], limit=1, columns="id"),
                withdrawal_archive=lambda: SB.select(TABLES["withdrawals"], limit=1, columns="id,deleted_at"),
            )
            return self.ok({"database": "Supabase/PostgreSQL", "project": SB.project_host, "table_prefix": "rumi_", "version": "6.4.4", "multi_admin_accounts": True, "weekly_shift_registration": True, "weekly_double_shift": True, "next_week_registration": True, "notification_bulk_delete": True, "inventory_history_archive": True, "registered_shift_reassignment": True, "max_weekly_hours_cap": 56, "fixed_weekly_shifts": ["09:00-17:00", "17:00-23:00"], "attendance_alerts": True, "payroll_pdf": True, "payroll_logic_v2": True, "operations_ready": True, "schedule_excel": True, "shift_market": True, "security_sessions": True, "smart_attendance": True, "time": now_iso()})

        if path == "/api/setup/status":
            return self.ok({"needs_setup": False, "admin_configured": True})

        if path == "/api/notifications/unread-count":
            user = self.current_user(required=False)
            if not user:
                return self.ok({"count": 0})
            self.require_password_changed(user, path)
            return self.ok({"count": len(self.get_notifications(user, limit=None, unread_only=True))})

        user = self.current_user()
        self.require_password_changed(user, path)

        if path == "/api/auth/me":
            return self.ok(user["profile"])

        if path == "/api/account/security":
            sessions = SB.select(TABLES["auth_sessions"], filters={"user_id": f"eq.{user['id']}"}, order="created_at.desc", limit=30,
                                 columns="id,device_label,created_at,last_seen_at,idle_expires_at,expires_at,revoked_at,revoke_reason,ip_hash")
            current_id = integer((user.get("session") or {}).get("id"))
            clean_sessions = []
            for row in sessions:
                item = {k: row.get(k) for k in ("id","device_label","created_at","last_seen_at","idle_expires_at","expires_at","revoked_at","revoke_reason")}
                item["current"] = integer(row.get("id")) == current_id
                item["active"] = not bool(row.get("revoked_at")) and (parse_iso_datetime(row.get("expires_at")) or utc_now()) > utc_now()
                clean_sessions.append(item)
            events = SB.select(TABLES["audit"], filters={"user_id": f"eq.{user['id']}", "entity_type": "eq.security"}, order="created_at.desc", limit=20,
                               columns="id,action,entity_id,detail,created_at")
            admin_accounts = []
            if user.get("role") == "admin":
                rows = SB.select(
                    TABLES["users"], filters={"role": "eq.admin"}, order="created_at.asc",
                    columns="id,username,active,must_change_password,password_changed_at,last_login_at,created_at,locked_until,failed_login_count",
                )
                admin_accounts = [{
                    "id": row.get("id"),
                    "username": row.get("username"),
                    "active": bool(row.get("active")),
                    "must_change_password": bool(row.get("must_change_password")),
                    "password_changed_at": row.get("password_changed_at"),
                    "last_login_at": row.get("last_login_at"),
                    "created_at": row.get("created_at"),
                    "locked_until": row.get("locked_until"),
                    "failed_login_count": integer(row.get("failed_login_count")),
                    "current": integer(row.get("id")) == integer(user.get("id")),
                    "primary": str(row.get("username") or "").lower() == ADMIN_USERNAME,
                } for row in rows]
            return self.ok({
                "profile": user["profile"],
                "sessions": clean_sessions,
                "events": events,
                "admin_accounts": admin_accounts,
                "policy": {
                    "minimum_length": 12 if user.get("role") == "admin" else PASSWORD_MIN_LENGTH,
                    "password_history": 5,
                    "idle_timeout_minutes": SESSION_IDLE_TTL // 60,
                    "absolute_timeout_hours": SESSION_TTL // 3600,
                    "max_failed_attempts": 5,
                    "lock_minutes": LOGIN_LOCK_MINUTES,
                    "hash_iterations": PASSWORD_ITERATIONS,
                },
            })

        if path == "/api/bootstrap":
            dashboard = None if user.get("must_change_password") else self.build_dashboard(user)
            return self.ok({"user": user["profile"], "dashboard": dashboard, "unread_count": (dashboard or {}).get("unread_count", 0)})

        if path == "/api/dashboard":
            return self.ok(self.build_dashboard(user))

        if path == "/api/notifications":
            return self.ok(self.get_notifications(user, limit=None))


        if path == "/api/attendance/alerts":
            return self.ok(self.sync_attendance_alerts(user))

        if path == "/api/page/shift-market":
            start = parse_date(query.get("start", [monday_of(today_text()).isoformat()])[0], "Ngày đầu tuần")
            end = parse_date(query.get("end", [(monday_of(start) + timedelta(days=6)).isoformat()])[0], "Ngày cuối tuần")
            if datetime.strptime(end, "%Y-%m-%d").date() < datetime.strptime(start, "%Y-%m-%d").date():
                raise APIError("Khoảng ngày không hợp lệ")
            return self.ok(self.shift_market_page(user, start, end))

        if path == "/api/page/schedule":
            self.require_role(user, "admin")
            start = query.get("start", [today_text()])[0]
            end = query.get("end", [start])[0]
            filters = {"shift_date": f"gte.{start}", "and": f"(shift_date.lte.{end})"}
            data = parallel_calls(
                shifts=lambda: SB.select(TABLES["shifts"], filters=filters, order="shift_date.asc,start_time.asc",
                                         columns="id,employee_id,location_id,shift_date,start_time,end_time,status,note"),
                locations=lambda: SB.select(TABLES["locations"], order="active.desc,name.asc"),
                employees=lambda: SB.select(TABLES["employees"], filters={"status": "eq.Đang làm"}, columns="id,role"),
            )
            roles = sorted({str(x.get("role") or "").strip() for x in data["employees"] if str(x.get("role") or "").strip()})
            return self.ok({"shifts": self.enriched_shifts(data["shifts"], locations=data["locations"]), "locations": data["locations"], "roles": roles})

        if path == "/api/page/requests":
            return self.ok(self.build_requests_page(user))

        if path == "/api/page/attendance":
            month = query.get("month", [current_month()])[0]
            if user.get("role") == "admin":
                history = self.build_attendance_rows(user, month)
                corrections = SB.select(TABLES["attendance_corrections"], order="created_at.desc", limit=200)
                employees = SB.select_in(TABLES["employees"], "id", [x.get("employee_id") for x in corrections], columns="id,code,name,role")
                correction_rows = add_people(corrections, employees)
                pending_overtime = [x for x in history if x.get("overtime_status") == "Chờ duyệt"]
                pending_risk = [x for x in history if x.get("review_status") == "Chờ duyệt" or (not x.get("review_status") and x.get("risk_level") == "Cao")]
                settings_rows = SB.select(TABLES["settings"], filters={"id": "eq.1"}, limit=1)
                return self.ok({"history": history, "alerts": self.sync_attendance_alerts(user), "corrections": correction_rows, "pending_overtime": pending_overtime, "pending_risk": pending_risk, "settings": settings_rows[0] if settings_rows else {}})
            start, end = month_bounds(month)
            data = parallel_calls(
                today_shifts=lambda: SB.select(TABLES["shifts"],
                                               filters={"employee_id": f"eq.{user['employee_id']}", "shift_date": f"eq.{today_text()}"},
                                               order="start_time.asc",
                                               columns="id,employee_id,location_id,shift_date,start_time,end_time,status,note"),
                correction_shifts=lambda: SB.select(TABLES["shifts"],
                                               filters={"employee_id": f"eq.{user['employee_id']}", "shift_date": f"gte.{start}", "and": f"(shift_date.lt.{end})"},
                                               order="shift_date.desc,start_time.desc",
                                               columns="id,employee_id,location_id,shift_date,start_time,end_time,status,note"),
                attendance=lambda: SB.select(TABLES["attendance"],
                                             filters={"employee_id": f"eq.{user['employee_id']}", "work_date": f"gte.{start}", "and": f"(work_date.lt.{end})"},
                                             order="work_date.desc,check_in.desc"),
                settings=lambda: SB.select(TABLES["settings"], filters={"id": "eq.1"}, limit=1),
                locations=lambda: SB.select(TABLES["locations"], filters={"active": "eq.true"}),
            )
            shift_ids = [x.get("shift_id") for x in data["attendance"]]
            history_shifts = SB.select_in(TABLES["shifts"], "id", shift_ids,
                                          columns="id,employee_id,location_id,shift_date,start_time,end_time,status,note")
            all_shifts = {integer(x.get("id")): x for x in history_shifts + data["today_shifts"] + data["correction_shifts"]}
            enriched = self.enriched_shifts(list(all_shifts.values()), employees=[user.get("employee") or {}],
                                            locations=data["locations"], attendance=data["attendance"])
            shift_map = {integer(x.get("id")): x for x in enriched}
            history = add_people(data["attendance"], [user.get("employee") or {}])
            attendance_by_shift = {integer(x.get("shift_id")): x for x in data["attendance"] if integer(x.get("shift_id"))}
            for item in history:
                item["shift"] = shift_map.get(integer(item.get("shift_id")))
                item["is_synthetic"] = False
            settings = data["settings"][0] if data["settings"] else {}
            for raw_shift in data["correction_shifts"]:
                shift_id = integer(raw_shift.get("id"))
                if shift_id in attendance_by_shift:
                    continue
                shift = shift_map.get(shift_id, raw_shift)
                live = classify_shift_attendance(shift, None, settings)
                history.append({
                    "id": None, "shift_id": shift_id, "employee_id": user["employee_id"],
                    "employee_name": user["profile"].get("name"), "employee_code": user["profile"].get("employee_code"),
                    "work_date": shift.get("shift_date"), "check_in": None, "check_out": None,
                    "hours": 0, "actual_hours": 0, "payable_hours": 0,
                    "scheduled_hours": shift_hours(str(shift.get("start_time")), str(shift.get("end_time"))),
                    "late_minutes": live.get("minutes_late", 0), "early_leave_minutes": 0, "overtime_minutes": 0,
                    "status": live.get("status"), "is_synthetic": True, "shift": shift,
                })
            history.sort(key=lambda x: (str(x.get("work_date") or ""), str((x.get("shift") or {}).get("start_time") or x.get("check_in") or "")), reverse=True)
            today_enriched = [shift_map.get(integer(x.get("id")), x) for x in data["today_shifts"]]
            for shift in today_enriched:
                shift["live_attendance_state"] = classify_shift_attendance(shift, shift.get("attendance"), settings)
            corrections = SB.select(TABLES["attendance_corrections"], filters={"employee_id": f"eq.{user['employee_id']}"}, order="created_at.desc", limit=100)
            return self.ok({
                "today_shifts": today_enriched,
                "correction_shifts": [shift_map.get(integer(x.get("id")), x) for x in data["correction_shifts"]],
                "history": history,
                "alerts": self.sync_attendance_alerts(user),
                "corrections": corrections,
                "settings": data["settings"][0] if data["settings"] else {},
            })

        if path == "/api/page/inventory":
            return self.ok(self.build_inventory_page(user))

        if path == "/api/page/locations":
            self.require_role(user, "admin")
            data = parallel_calls(
                locations=lambda: SB.select(TABLES["locations"], order="active.desc,name.asc"),
                settings=lambda: SB.select(TABLES["settings"], filters={"id": "eq.1"}, limit=1),
            )
            return self.ok({"locations": data["locations"], "settings": data["settings"][0] if data["settings"] else {}})

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
                employee["must_change_password"] = bool(account.get("must_change_password"))
                employee["locked_until"] = account.get("locked_until")
                employee["last_login_at"] = account.get("last_login_at")
                employee["failed_login_count"] = integer(account.get("failed_login_count"))
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
            employees = SB.select_in(TABLES["employees"], "id", [x.get("employee_id") for x in rows], columns="id,code,name,role")
            return self.ok(add_people(rows, employees))

        if path == "/api/leaves":
            filters = {}
            if user.get("role") == "employee":
                filters["employee_id"] = f"eq.{user['employee_id']}"
            rows = SB.select(TABLES["leaves"], filters=filters, order="created_at.desc")
            employees = SB.select_in(TABLES["employees"], "id", [x.get("employee_id") for x in rows], columns="id,code,name,role")
            return self.ok(add_people(rows, employees))

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

        if path == "/api/export/schedule-week.xlsx":
            start_value = parse_date(query.get("start", [""])[0], "Ngày bắt đầu")
            end_value = parse_date(query.get("end", [""])[0], "Ngày kết thúc")
            start_day = datetime.strptime(start_value, "%Y-%m-%d").date()
            end_day = datetime.strptime(end_value, "%Y-%m-%d").date()
            if end_day < start_day or (end_day - start_day).days > 6:
                raise APIError("File Excel chỉ xuất tối đa 7 ngày")
            filters = {"shift_date": f"gte.{start_value}", "and": f"(shift_date.lte.{end_value})"}
            location_id = integer(query.get("location_id", ["0"])[0])
            if user.get("role") == "employee":
                filters["employee_id"] = f"eq.{user['employee_id']}"
            elif location_id:
                filters["location_id"] = f"eq.{location_id}"
            shifts = self.enriched_shifts(SB.select(TABLES["shifts"], filters=filters, order="shift_date.asc,start_time.asc"))
            if user.get("role") == "admin":
                employees = SB.select(TABLES["employees"], filters={"status": "eq.Đang làm"}, order="name.asc", columns="id,code,name,role,status")
            else:
                employees = [user.get("employee") or {}]
            location_label = "Tất cả cửa hàng"
            if location_id and user.get("role") == "admin":
                location_rows = SB.select(TABLES["locations"], filters={"id": f"eq.{location_id}"}, limit=1, columns="id,name")
                location_label = location_rows[0].get("name", "Cửa hàng") if location_rows else "Cửa hàng"
            elif user.get("role") == "employee":
                location_label = "Lịch cá nhân"
            workbook = build_schedule_week_xlsx(
                shifts, employees, start_value, end_value, location_label,
                user["profile"].get("name") or user.get("username") or "RUMI",
            )
            filename = f"RUMI_lich_lam_tuan_{start_value}.xlsx"
            self.audit(user, "export", "schedule_week", start_value, {"end": end_value, "location_id": location_id, "shift_count": len(shifts)})
            return self.send_binary(workbook, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename)

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
            required_role = query.get("role", [""])[0]
            return self.ok(self.candidate_rows(work_date, start, end, exclude, ignore_shift, required_role))

        if path == "/api/shifts/reassign-candidates":
            self.require_role(user, "admin")
            shift_id = integer(query.get("shift_id", ["0"])[0])
            shifts = SB.select(TABLES["shifts"], filters={"id": f"eq.{shift_id}"}, limit=1)
            if not shifts:
                raise APIError("Không tìm thấy ca làm", 404)
            shift = shifts[0]
            if not shift.get("opening_id"):
                raise APIError("Ca này không được tạo từ lịch đăng ký nên không có ứng viên đăng ký thay", 409)
            if SB.select(TABLES["attendance"], filters={"shift_id": f"eq.{shift_id}"}, limit=1, columns="id"):
                raise APIError("Ca đã có chấm công nên không thể đổi nhân viên", 409)
            applications = SB.select(TABLES["applications"], filters={
                "opening_id": f"eq.{integer(shift.get('opening_id'))}",
                "status": "in.(Chờ duyệt,Danh sách chờ,Từ chối)",
            }, order="applied_at.asc")
            applications = [x for x in applications if integer(x.get("employee_id")) != integer(shift.get("employee_id"))]
            employees = SB.select_in(TABLES["employees"], "id", [x.get("employee_id") for x in applications])
            openings = SB.select(TABLES["openings"], filters={"id": f"eq.{integer(shift.get('opening_id'))}"}, limit=1)
            if not openings:
                raise APIError("Không tìm thấy lịch đăng ký gốc", 404)
            opening = openings[0]
            week_start = monday_of(str(shift.get("shift_date")))
            week_end = week_start + timedelta(days=6)
            data = parallel_calls(
                shifts=lambda: SB.select(TABLES["shifts"], filters={"shift_date": f"gte.{week_start.isoformat()}", "and": f"(shift_date.lte.{week_end.isoformat()})"}),
                leaves=lambda: SB.select(TABLES["leaves"], filters={"status": "eq.Đã duyệt", "start_date": f"lte.{shift['shift_date']}", "and": f"(end_date.gte.{shift['shift_date']})"}),
                day_offs=lambda: SB.select(TABLES["day_offs"], filters={"week_start": f"eq.{week_start.isoformat()}"}),
            )
            e_map = employee_map(employees)
            rows = []
            for application in applications:
                employee = e_map.get(integer(application.get("employee_id")), {})
                if not employee:
                    continue
                rule = self.employee_shift_rule(employee, opening, data["shifts"], data["leaves"], data["day_offs"], allow_fixed_double=bool(application.get("weekly_request_id")))
                rows.append({
                    **application,
                    "employee_name": employee.get("name"), "employee_code": employee.get("code"),
                    "employee_role": employee.get("role"), "employment_type": employee.get("employment_type"),
                    **rule,
                })
            rows.sort(key=lambda x: (0 if x.get("allowed") else 1, -num(x.get("score")), x.get("applied_at") or ""))
            return self.ok({"shift": self.enriched_shifts([shift])[0], "candidates": rows})

        if path == "/api/attendance/today":
            self.require_role(user, "employee")
            shifts = SB.select(TABLES["shifts"], filters={"employee_id": f"eq.{user['employee_id']}", "shift_date": f"eq.{today_text()}"}, order="start_time.asc")
            return self.ok(self.enriched_shifts(shifts))

        if path == "/api/attendance":
            month = query.get("month", [current_month()])[0]
            return self.ok(self.build_attendance_rows(user, month))

        if path == "/api/payroll":
            month = query.get("month", [current_month()])[0]
            return self.ok(self.payroll_page(user, month)["items"])

        if path == "/api/page/payroll":
            month = query.get("month", [current_month()])[0]
            return self.ok(self.payroll_page(user, month))

        if path == "/api/inventory":
            rows = SB.select(TABLES["inventory"], order="category.asc,name.asc")
            rows.sort(key=lambda x: (0 if num(x.get("quantity")) <= num(x.get("min_stock")) else 1, str(x.get("category")), str(x.get("name"))))
            return self.ok(rows)

        if path == "/api/withdrawals":
            return self.ok(self.build_inventory_page(user)["withdrawals"])

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
            start, end = month_bounds(month)
            data = parallel_calls(
                payroll=lambda: self.build_payroll(month),
                attendance=lambda: SB.select(TABLES["attendance"], filters={"work_date": f"gte.{start}", "and": f"(work_date.lt.{end})"}, columns="hours"),
                employees=lambda: SB.select(TABLES["employees"], filters={"status": "eq.Đang làm"}, columns="id"),
            )
            payroll = data["payroll"]
            return self.ok({
                "month": month,
                "employee_count": len(data["employees"]),
                "total_hours": round(sum(num(x.get("hours")) for x in data["attendance"]), 2),
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
            username = str(body.get("username", "")).strip().lower()
            password = str(body.get("password", ""))
            throttle_key = hash_secret(f"{username}|{self.client_ip()}", "login-throttle")
            throttle_rows = SB.select(TABLES["login_throttles"], filters={"key_hash": f"eq.{throttle_key}"}, limit=1)
            if throttle_rows:
                locked_until = parse_iso_datetime(throttle_rows[0].get("locked_until"))
                if locked_until and locked_until > utc_now():
                    raise APIError(f"Đăng nhập tạm khóa. Thử lại sau khoảng {minutes_until(throttle_rows[0].get('locked_until'))} phút.", 429)

            users = SB.select(TABLES["users"], filters={"username": f"eq.{username}"}, limit=1,
                              columns="id,username,password_hash,password_salt,password_iterations,must_change_password,password_changed_at,role,employee_id,active,last_login_at,locked_until,failed_login_count")
            user = users[0] if users else None
            user_locked = parse_iso_datetime(user.get("locked_until")) if user else None
            valid = bool(user and user.get("active") and (not user_locked or user_locked <= utc_now()) and
                         verify_password(password, user.get("password_hash", ""), user.get("password_salt", ""), integer(user.get("password_iterations"), 210_000)))
            if not valid:
                result = SB.rpc("rumi_auth_register_failure", {
                    "p_key_hash": throttle_key,
                    "p_user_id": integer(user.get("id")) if user else None,
                    "p_now": now_iso(),
                })
                if result and result.get("locked"):
                    raise APIError(f"Đăng nhập sai nhiều lần. Tài khoản tạm khóa {result.get('retry_after_minutes', 15)} phút.", 429)
                raise APIError("Tên đăng nhập hoặc mật khẩu không đúng", 401)

            employee = None
            if user.get("employee_id"):
                rows = SB.select(TABLES["employees"], filters={"id": f"eq.{user['employee_id']}"}, limit=1)
                employee = rows[0] if rows else None
                if user.get("role") == "employee" and (not employee or employee.get("status") != "Đang làm"):
                    raise APIError("Tài khoản nhân viên đã bị khóa", 403)

            updates = {
                "last_login_at": now_iso(),
                "last_login_ip_hash": self.ip_hash(),
                "last_login_user_agent_hash": self.user_agent_hash(),
                "failed_login_count": 0,
                "locked_until": None,
                "last_failed_login_at": None,
            }
            old_iterations = integer(user.get("password_iterations"), 210_000)
            if old_iterations < PASSWORD_ITERATIONS:
                upgraded_hash, upgraded_salt = password_hash(password, iterations=PASSWORD_ITERATIONS)
                updates.update({"password_hash": upgraded_hash, "password_salt": upgraded_salt, "password_iterations": PASSWORD_ITERATIONS})
                user.update(updates)
            SB.update(TABLES["users"], updates, {"id": f"eq.{user['id']}"})
            SB.rpc("rumi_auth_clear_failures", {"p_key_hash": throttle_key, "p_user_id": user["id"], "p_now": now_iso()})
            token, session = self.create_db_session(integer(user["id"]))
            user.update(updates)
            profile = public_user(user, employee)
            user["profile"] = profile
            user["employee"] = employee
            user["session"] = session
            dashboard = None if user.get("must_change_password") else self.build_dashboard(user)
            self.audit(user, "login", "security", user["id"], {"device": self.device_label()})
            return self.ok({"user": profile, "dashboard": dashboard, "unread_count": (dashboard or {}).get("unread_count", 0)},
                           "Đăng nhập thành công", headers={"Set-Cookie": self.session_header(token)})

        if path == "/api/auth/logout":
            current = self.current_user(required=False)
            self.revoke_current_session("Đăng xuất")
            if current:
                self.audit(current, "logout", "security", current.get("id"))
            return self.ok(None, "Đã đăng xuất", headers={"Set-Cookie": self.session_header("", 0)})

        user = self.current_user()
        self.require_password_changed(user, path)

        if path == "/api/admin/accounts":
            self.require_role(user, "admin")
            username = str(body.get("username", "")).strip().lower()
            password = str(body.get("password", ""))
            confirm_password = str(body.get("confirm_password", password))
            if not re.fullmatch(r"[a-z0-9._-]{3,40}", username):
                raise APIError("Tên đăng nhập admin phải có 3-40 ký tự a-z, 0-9, dấu chấm, gạch dưới hoặc gạch ngang")
            if password != confirm_password:
                raise APIError("Xác nhận mật khẩu admin không khớp")
            validate_password_policy(password, username, admin=True)
            existing = SB.select(TABLES["users"], filters={"username": f"eq.{username}"}, limit=1, columns="id,role")
            if existing:
                raise APIError("Tên đăng nhập này đã tồn tại", 409)
            hashed, salt = password_hash(password, iterations=PASSWORD_ITERATIONS)
            account = SB.insert(TABLES["users"], {
                "username": username,
                "password_hash": hashed,
                "password_salt": salt,
                "password_iterations": PASSWORD_ITERATIONS,
                "must_change_password": True,
                "password_changed_at": None,
                "role": "admin",
                "employee_id": None,
                "active": True,
                "failed_login_count": 0,
                "locked_until": None,
            })
            self.audit(user, "create_admin", "security", account.get("id"), {"username": username})
            return self.ok({
                "id": account.get("id"), "username": username, "active": True,
                "must_change_password": True,
            }, "Đã tạo tài khoản admin mới; tài khoản phải đổi mật khẩu ở lần đăng nhập đầu tiên")

        if path == "/api/auth/change-password":
            old_password = str(body.get("old_password", ""))
            new_password = str(body.get("new_password", ""))
            confirm_password = str(body.get("confirm_password", new_password))
            if new_password != confirm_password:
                raise APIError("Xác nhận mật khẩu mới không khớp")
            if not verify_password(old_password, user.get("password_hash", ""), user.get("password_salt", ""), integer(user.get("password_iterations"), 210_000)):
                raise APIError("Mật khẩu hiện tại không đúng")
            validate_password_policy(new_password, user.get("username", ""), admin=user.get("role") == "admin")
            if password_reused(integer(user["id"]), new_password, user):
                raise APIError("Không được dùng lại một trong các mật khẩu gần đây")
            SB.insert(TABLES["password_history"], {
                "user_id": user["id"],
                "password_hash": user.get("password_hash", ""),
                "password_salt": user.get("password_salt", ""),
                "password_iterations": integer(user.get("password_iterations"), 210_000),
            })
            old_history = SB.select(TABLES["password_history"], filters={"user_id": f"eq.{user['id']}"}, order="created_at.desc", columns="id", limit=20)
            for stale in old_history[5:]:
                SB.delete(TABLES["password_history"], {"id": f"eq.{stale['id']}"})
            hashed, salt = password_hash(new_password, iterations=PASSWORD_ITERATIONS)
            SB.update(TABLES["users"], {
                "password_hash": hashed,
                "password_salt": salt,
                "password_iterations": PASSWORD_ITERATIONS,
                "must_change_password": False,
                "password_changed_at": now_iso(),
                "failed_login_count": 0,
                "locked_until": None,
            }, {"id": f"eq.{user['id']}"})
            current_session_id = integer((user.get("session") or {}).get("id"))
            SB.update(TABLES["auth_sessions"], {"revoked_at": now_iso(), "revoke_reason": "Đổi mật khẩu"},
                      {"user_id": f"eq.{user['id']}", "revoked_at": "is.null"})
            token, _session = self.create_db_session(integer(user["id"]))
            self.audit(user, "change_password", "security", user["id"], {"revoked_session_id": current_session_id})
            return self.ok({"must_change_password": False}, "Đã đổi mật khẩu và đăng xuất các phiên khác",
                           headers={"Set-Cookie": self.session_header(token)})

        if path == "/api/auth/logout-all":
            SB.update(TABLES["auth_sessions"], {"revoked_at": now_iso(), "revoke_reason": "Đăng xuất tất cả thiết bị"},
                      {"user_id": f"eq.{user['id']}", "revoked_at": "is.null"})
            self.audit(user, "logout_all", "security", user["id"])
            return self.ok(None, "Đã đăng xuất tất cả thiết bị", headers={"Set-Cookie": self.session_header("", 0)})

        if path == "/api/auth/session/revoke":
            session_id = integer(body.get("session_id"))
            rows = SB.update(TABLES["auth_sessions"], {"revoked_at": now_iso(), "revoke_reason": "Người dùng thu hồi"},
                             {"id": f"eq.{session_id}", "user_id": f"eq.{user['id']}", "revoked_at": "is.null"})
            if not rows:
                raise APIError("Không tìm thấy phiên đăng nhập", 404)
            is_current = session_id == integer((user.get("session") or {}).get("id"))
            self.audit(user, "revoke_session", "security", session_id)
            headers = {"Set-Cookie": self.session_header("", 0)} if is_current else None
            return self.ok({"current": is_current}, "Đã thu hồi phiên đăng nhập", headers=headers)

        if path == "/api/notifications/read":
            notification_id = integer(body.get("id"))
            rows = self.get_notifications(user, limit=None)
            allowed = {integer(x.get("id")) for x in rows}
            if notification_id:
                if notification_id not in allowed:
                    raise APIError("Không tìm thấy thông báo", 404)
                SB.update(TABLES["notifications"], {"read_at": now_iso()}, {"id": f"eq.{notification_id}"})
            else:
                unread_ids = [integer(row.get("id")) for row in rows if not row.get("read_at")]
                for offset in range(0, len(unread_ids), 150):
                    SB.update(TABLES["notifications"], {"read_at": now_iso()}, {"id": pg_in(unread_ids[offset:offset + 150])})
            return self.ok(None, "Đã đánh dấu đã đọc")

        if path == "/api/notifications/delete":
            self.require_role(user, "admin")
            ids = sorted({integer(x) for x in (body.get("ids") or []) if integer(x)})
            if not ids:
                raise APIError("Hãy chọn ít nhất một thông báo")
            allowed = {integer(x.get("id")) for x in self.get_notifications(user, limit=None)}
            selected = [x for x in ids if x in allowed]
            if len(selected) != len(ids):
                raise APIError("Có thông báo không thuộc quyền quản trị", 403)
            deleted = 0
            for offset in range(0, len(selected), 150):
                rows = SB.delete(TABLES["notifications"], {"id": pg_in(selected[offset:offset + 150])})
                deleted += len(rows)
            self.audit(user, "bulk_delete", "notification", "bulk", {"count": deleted, "ids": selected[:100]})
            return self.ok({"deleted_count": deleted}, f"Đã xóa {deleted} thông báo")

        if path == "/api/withdrawals/archive":
            self.require_role(user, "admin")
            ids = sorted({integer(x) for x in (body.get("ids") or []) if integer(x)})
            reason = str(body.get("reason") or "Admin xóa khỏi lịch sử hiển thị").strip()[:500]
            if not ids:
                raise APIError("Hãy chọn ít nhất một lịch sử lấy hàng")
            existing = SB.select_in(TABLES["withdrawals"], "id", ids, columns="id,deleted_at")
            active_ids = [integer(x.get("id")) for x in existing if not x.get("deleted_at")]
            if len(active_ids) != len(ids):
                raise APIError("Có lịch sử không tồn tại hoặc đã bị xóa", 409)
            archived = 0
            for offset in range(0, len(active_ids), 150):
                rows = SB.update(TABLES["withdrawals"], {
                    "deleted_at": now_iso(), "deleted_by": user["id"], "delete_reason": reason,
                }, {"id": pg_in(active_ids[offset:offset + 150]), "deleted_at": "is.null"})
                archived += len(rows)
            self.audit(user, "archive", "inventory_withdrawal", "bulk", {"count": archived, "reason": reason, "ids": active_ids[:100]})
            return self.ok({"deleted_count": archived}, f"Đã xóa {archived} mục khỏi lịch sử; tồn kho không thay đổi")

        if path == "/api/shifts/reassign":
            self.require_role(user, "admin")
            shift_id = integer(body.get("shift_id"))
            application_id = integer(body.get("application_id"))
            if not shift_id or not application_id:
                raise APIError("Ca làm hoặc ứng viên chưa hợp lệ")
            # Kiểm tra bằng cùng API nghiệp vụ trước khi gọi transaction SQL.
            shifts = SB.select(TABLES["shifts"], filters={"id": f"eq.{shift_id}"}, limit=1)
            applications = SB.select(TABLES["applications"], filters={"id": f"eq.{application_id}"}, limit=1)
            if not shifts or not applications:
                raise APIError("Không tìm thấy ca hoặc đơn đăng ký", 404)
            shift, application = shifts[0], applications[0]
            if integer(application.get("opening_id")) != integer(shift.get("opening_id")):
                raise APIError("Nhân viên chưa đăng ký đúng lịch này", 409)
            if application.get("status") not in {"Chờ duyệt", "Danh sách chờ", "Từ chối"}:
                raise APIError("Chỉ có thể đổi sang nhân viên đã đăng ký và chưa rút đơn", 409)
            result = SB.rpc("rumi_reassign_shift_to_application", {
                "p_shift_id": shift_id, "p_application_id": application_id,
                "p_admin_user_id": user["id"], "p_note": str(body.get("note") or "").strip()[:500],
            })
            old_id = integer((result or {}).get("old_employee_id"))
            new_id = integer((result or {}).get("new_employee_id"))
            if old_id:
                self.notify_employee(old_id, "Lịch làm đã được đổi", f"Ca {shift['shift_date']} {str(shift['start_time'])[:5]}–{str(shift['end_time'])[:5]} đã chuyển cho nhân viên khác.", "schedule", "shifts")
            if new_id:
                self.notify_employee(new_id, "Bạn được xếp vào ca đã đăng ký", f"Ca {shift['shift_date']} {str(shift['start_time'])[:5]}–{str(shift['end_time'])[:5]} đã được quản lý duyệt thay.", "schedule", "shifts")
            self.audit(user, "reassign", "shift", shift_id, {"application_id": application_id, "old_employee_id": old_id, "new_employee_id": new_id})
            updated = SB.select(TABLES["shifts"], filters={"id": f"eq.{shift_id}"}, limit=1)
            return self.ok(self.enriched_shifts(updated)[0] if updated else result, "Đã đổi nhân viên cho ca làm")

        if path == "/api/employees":
            self.require_role(user, "admin")
            code = str(body.get("code", "")).strip().upper()
            name = str(body.get("name", "")).strip()
            username = str(body.get("username", "")).strip().lower()
            password = str(body.get("password", ""))
            if not code or len(name) < 2 or not re.fullmatch(r"[a-z0-9._-]{3,40}", username):
                raise APIError("Vui lòng nhập đủ mã, họ tên và tên đăng nhập hợp lệ")
            validate_password_policy(password, username)
            employment_type = body.get("employment_type", "Part-time")
            weekly_target = num(body.get("weekly_target_hours"), 48 if employment_type == "Full-time" else 24)
            requested_weekly_max = num(body.get("max_weekly_hours"), 56)
            if requested_weekly_max > 56:
                raise APIError("Mỗi nhân viên chỉ được cấu hình tối đa 56 giờ/tuần")
            if weekly_target > requested_weekly_max:
                raise APIError("Giờ mục tiêu không được lớn hơn giới hạn giờ tuần")
            employee = SB.insert(TABLES["employees"], {
                "code": code,
                "name": name,
                "phone": str(body.get("phone", "")).strip(),
                "email": str(body.get("email", "")).strip(),
                "role": str(body.get("job_role", "Nhân viên")).strip(),
                "hourly_wage": num(body.get("hourly_wage"), 25000),
                "employment_type": employment_type,
                "weekly_target_hours": weekly_target,
                "max_weekly_hours": requested_weekly_max,
                "max_daily_hours": num(body.get("max_daily_hours"), 8),
                "max_consecutive_days": integer(body.get("max_consecutive_days"), 6),
                "weekly_days_off": integer(body.get("weekly_days_off"), 1 if body.get("employment_type") == "Full-time" else 0),
                "status": "Đang làm",
                "joined_at": body.get("joined_at") or today_text(),
            })
            try:
                hashed, salt = password_hash(password, iterations=PASSWORD_ITERATIONS)
                SB.insert(TABLES["users"], {
                    "username": username,
                    "password_hash": hashed,
                    "password_salt": salt,
                    "password_iterations": PASSWORD_ITERATIONS,
                    "must_change_password": True,
                    "password_changed_at": None,
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
            accounts = SB.select(TABLES["users"], filters={"employee_id": f"eq.{employee_id}"}, limit=1, columns="id,username")
            if not accounts:
                raise APIError("Nhân viên chưa có tài khoản", 404)
            account = accounts[0]
            validate_password_policy(new_password, account.get("username", ""))
            hashed, salt = password_hash(new_password, iterations=PASSWORD_ITERATIONS)
            SB.update(TABLES["users"], {
                "password_hash": hashed,
                "password_salt": salt,
                "password_iterations": PASSWORD_ITERATIONS,
                "must_change_password": True,
                "password_changed_at": now_iso(),
                "failed_login_count": 0,
                "locked_until": None,
            }, {"id": f"eq.{account['id']}"})
            SB.update(TABLES["auth_sessions"], {"revoked_at": now_iso(), "revoke_reason": "Admin đặt lại mật khẩu"},
                      {"user_id": f"eq.{account['id']}", "revoked_at": "is.null"})
            self.audit(user, "reset_password", "employee", employee_id)
            return self.ok(None, "Đã đặt lại mật khẩu; nhân viên phải đổi ở lần đăng nhập tiếp theo")

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

        if path == "/api/shift-market/weekly-openings":
            self.require_role(user, "admin")
            week_start_text = parse_date(body.get("week_start"), "Tuần")
            week_start = datetime.strptime(week_start_text, "%Y-%m-%d").date()
            if week_start.weekday() != 0:
                raise APIError("Ngày đầu tuần phải là Thứ Hai")
            if week_start < monday_of(today_text()):
                raise APIError("Không thể đăng lịch cho tuần đã qua")
            location_id = integer(body.get("location_id"))
            morning_count = max(0, min(integer(body.get("morning_count"), 1), 50))
            evening_count = max(0, min(integer(body.get("evening_count"), 1), 50))
            if morning_count == 0 and evening_count == 0:
                raise APIError("Phải mở ít nhất một ca trong tuần")
            status = str(body.get("status") or "Mở đăng ký")
            eligible = str(body.get("eligible_employment_type") or "Tất cả")
            if status not in {"Nháp", "Mở đăng ký"} or eligible not in {"Tất cả", "Full-time", "Part-time"}:
                raise APIError("Trạng thái hoặc loại nhân viên không hợp lệ")
            locations = SB.select(TABLES["locations"], filters={"id": f"eq.{location_id}", "active": "eq.true"}, limit=1)
            if not locations:
                raise APIError("Cửa hàng không tồn tại hoặc đã tắt")
            raw_days = body.get("days")
            days = sorted({integer(x, -1) for x in raw_days}) if isinstance(raw_days, list) else list(range(7))
            if not days or any(x < 0 or x > 6 for x in days):
                raise APIError("Ngày mở ca không hợp lệ")
            deadline = str(body.get("application_deadline") or "").strip() or None
            if deadline:
                try:
                    parsed_deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
                    if parsed_deadline.tzinfo is None:
                        parsed_deadline = parsed_deadline.replace(tzinfo=LOCAL_TZ)
                    deadline = parsed_deadline.isoformat(timespec="seconds")
                except ValueError as exc:
                    raise APIError("Hạn đăng ký không hợp lệ") from exc
            end_date = week_start + timedelta(days=6)
            existing = SB.select(TABLES["openings"], filters={
                "location_id": f"eq.{location_id}",
                "work_date": f"gte.{week_start.isoformat()}",
                "and": f"(work_date.lte.{end_date.isoformat()})",
            })
            existing_map = {
                (str(x.get("work_date")), str(x.get("start_time"))[:5], str(x.get("end_time"))[:5]): x
                for x in existing if x.get("status") != "Đã hủy"
            }
            specs = [("09:00", "17:00", morning_count, "Ca ngày"), ("17:00", "23:00", evening_count, "Ca tối")]
            created, updated, skipped = [], [], []
            for offset in days:
                work_date = (week_start + timedelta(days=offset)).isoformat()
                for start_time, end_time, required_count, label in specs:
                    if required_count <= 0:
                        continue
                    key = (work_date, start_time, end_time)
                    payload = {
                        "location_id": location_id, "work_date": work_date,
                        "start_time": start_time, "end_time": end_time,
                        "required_role": str(body.get("required_role") or "").strip(),
                        "required_count": required_count,
                        "eligible_employment_type": eligible,
                        "application_deadline": deadline,
                        "note": str(body.get("note") or f"{label} theo lịch tuần").strip(),
                        "status": status, "created_by": user["id"],
                        "published_at": now_iso() if status == "Mở đăng ký" else None,
                    }
                    current = existing_map.get(key)
                    if current and current.get("status") == "Đã chốt":
                        skipped.append(current)
                        continue
                    if current:
                        rows = SB.update(TABLES["openings"], payload, {"id": f"eq.{current['id']}"})
                        if rows:
                            updated.append(rows[0])
                    else:
                        created.append(SB.insert(TABLES["openings"], payload))
            if status == "Mở đăng ký":
                self.notify_role(
                    "employee", "RUMI đã mở đăng ký lịch cả tuần",
                    f"Tuần {week_start.isoformat()} tại {locations[0]['name']} có 2 ca: 09:00–17:00 và 17:00–23:00.",
                    "schedule", "availability"
                )
            self.audit(user, "publish_week", "shift_opening_week", week_start.isoformat(), {
                "location_id": location_id, "created": len(created), "updated": len(updated), "skipped": len(skipped)
            })
            return self.ok({
                "week_start": week_start.isoformat(), "created": created, "updated": updated,
                "skipped": skipped, "opening_count": len(created) + len(updated) + len(skipped),
            }, "Đã đăng lịch tuần gồm ca 09:00–17:00 và 17:00–23:00")

        if path == "/api/shift-market/weekly-requests":
            self.require_role(user, "employee")
            week_start_text = parse_date(body.get("week_start"), "Tuần")
            week_start = datetime.strptime(week_start_text, "%Y-%m-%d").date()
            if week_start.weekday() != 0:
                raise APIError("Ngày đầu tuần phải là Thứ Hai")
            if week_start < monday_of(today_text()):
                raise APIError("Không thể đăng ký tuần đã qua")
            opening_ids = [integer(x) for x in (body.get("opening_ids") or []) if integer(x)]
            if not opening_ids:
                raise APIError("Hãy chọn ít nhất một ca trong tuần")
            openings = SB.select_in(TABLES["openings"], "id", opening_ids)
            if len(openings) != len(set(opening_ids)):
                raise APIError("Có ca đăng ký không còn tồn tại")
            openings.sort(key=lambda x: (str(x.get("work_date")), str(x.get("start_time"))))
            locations = {integer(x.get("location_id")) for x in openings}
            if len(locations) != 1:
                raise APIError("Một đơn tuần chỉ được đăng ký tại một cửa hàng")
            location_id = next(iter(locations))
            employee = user.get("employee") or {}
            employment_type = employee.get("employment_type") or "Part-time"
            selected_dates = {str(x.get("work_date")) for x in openings}
            selected_by_date = defaultdict(list)
            for opening in openings:
                selected_by_date[str(opening.get("work_date"))].append(opening)
            if any(len(rows) > 2 for rows in selected_by_date.values()):
                raise APIError("Mỗi ngày chỉ được đăng ký tối đa 2 ca")
            if employment_type == "Full-time" and len(selected_dates) != 6:
                raise APIError("Full-time phải đăng ký đúng 6 ngày làm và nghỉ 1 ngày; mỗi ngày có thể chọn 1 hoặc 2 ca")
            if employment_type != "Full-time" and len(openings) < 1:
                raise APIError("Hãy chọn ít nhất một ca trong tuần")
            week_end = week_start + timedelta(days=6)
            for opening in openings:
                work_date = datetime.strptime(str(opening.get("work_date")), "%Y-%m-%d").date()
                times = (str(opening.get("start_time"))[:5], str(opening.get("end_time"))[:5])
                if not week_start <= work_date <= week_end:
                    raise APIError("Có ca không thuộc tuần đã chọn")
                if times not in {("09:00", "17:00"), ("17:00", "23:00")}:
                    raise APIError("Đơn tuần chỉ hỗ trợ ca 09:00–17:00 và 17:00–23:00")
                if opening.get("status") != "Mở đăng ký":
                    raise APIError(f"Ca ngày {opening.get('work_date')} không còn nhận đăng ký")
                deadline = parse_iso_datetime(opening.get("application_deadline"))
                if deadline and deadline < utc_now():
                    raise APIError(f"Ca ngày {opening.get('work_date')} đã hết hạn đăng ký")
            data = parallel_calls(
                shifts=lambda: SB.select(TABLES["shifts"], filters={
                    "shift_date": f"gte.{week_start.isoformat()}",
                    "and": f"(shift_date.lte.{week_end.isoformat()})",
                }),
                leaves=lambda: SB.select(TABLES["leaves"], filters={
                    "status": "eq.Đã duyệt", "start_date": f"lte.{week_end.isoformat()}",
                    "and": f"(end_date.gte.{week_start.isoformat()})",
                }),
                day_offs=lambda: SB.select(TABLES["day_offs"], filters={"week_start": f"eq.{week_start.isoformat()}"}),
            )
            day_offs = [x for x in data["day_offs"] if integer(x.get("employee_id")) != integer(user.get("employee_id"))]
            simulated = list(data["shifts"])
            for opening in openings:
                rule = self.employee_shift_rule(employee, opening, simulated, data["leaves"], day_offs, allow_fixed_double=True)
                if not rule["allowed"]:
                    raise APIError(f"{opening['work_date']} {str(opening['start_time'])[:5]}: {rule['reason']}", 409)
                simulated.append({
                    "employee_id": user["employee_id"], "shift_date": opening["work_date"],
                    "start_time": opening["start_time"], "end_time": opening["end_time"], "status": "Đã xếp",
                })
            result = SB.rpc("rumi_submit_weekly_shift_request", {
                "p_employee_id": user["employee_id"],
                "p_week_start": week_start.isoformat(),
                "p_location_id": location_id,
                "p_employee_note": str(body.get("employee_note") or "").strip(),
                "p_opening_ids": opening_ids,
            })
            self.notify_role(
                "admin", "Có đơn đăng ký ca cả tuần",
                f"{employee.get('name')} đã gửi lịch tuần {week_start.isoformat()} gồm {len(selected_dates)} ngày / {len(opening_ids)} ca.",
                "schedule", "requests"
            )
            self.audit(user, "submit_weekly", "weekly_shift_request", (result or {}).get("request_id"), {
                "week_start": week_start.isoformat(), "opening_ids": opening_ids, "selected_days": len(selected_dates), "selected_shifts": len(opening_ids)
            })
            return self.ok(result or {}, "Đã gửi đơn đăng ký cả tuần để admin duyệt")

        if path == "/api/shift-market/weekly-requests/withdraw":
            self.require_role(user, "employee")
            request_id = integer(body.get("id"))
            rows = SB.select(TABLES["weekly_requests"], filters={
                "id": f"eq.{request_id}", "employee_id": f"eq.{user['employee_id']}"
            }, limit=1)
            if not rows:
                raise APIError("Không tìm thấy đơn tuần", 404)
            approved = SB.select(TABLES["weekly_request_items"], filters={
                "request_id": f"eq.{request_id}", "status": "eq.Đã duyệt"
            }, limit=1)
            if approved:
                raise APIError("Đơn đã được duyệt một phần. Hãy gửi yêu cầu thay ca thay vì rút đơn")
            SB.update(TABLES["applications"], {
                "status": "Đã rút", "admin_note": "Nhân viên rút đơn cả tuần",
                "reviewed_at": None, "reviewed_by": None,
            }, {"weekly_request_id": f"eq.{request_id}"})
            SB.update(TABLES["weekly_request_items"], {"status": "Đã rút", "updated_at": now_iso()}, {"request_id": f"eq.{request_id}"})
            row = SB.update(TABLES["weekly_requests"], {
                "status": "Đã rút", "updated_at": now_iso(), "reviewed_at": None, "reviewed_by": None,
            }, {"id": f"eq.{request_id}"})[0]
            self.audit(user, "withdraw_weekly", "weekly_shift_request", request_id, {})
            return self.ok(row, "Đã rút đơn đăng ký cả tuần")

        if path == "/api/shift-market/weekly-requests/review":
            self.require_role(user, "admin")
            request_id = integer(body.get("id"))
            action = str(body.get("action") or "")
            if action not in {"approve_all", "reject_all"}:
                raise APIError("Thao tác duyệt đơn tuần không hợp lệ")
            requests = SB.select(TABLES["weekly_requests"], filters={"id": f"eq.{request_id}"}, limit=1)
            if not requests:
                raise APIError("Không tìm thấy đơn đăng ký tuần", 404)
            items = SB.select(TABLES["weekly_request_items"], filters={"request_id": f"eq.{request_id}"}, order="work_date.asc,start_time.asc")
            if action == "reject_all" and any(x.get("status") == "Đã duyệt" for x in items):
                raise APIError("Đơn đã có ca được duyệt. Hãy xử lý từng ngày hoặc dùng yêu cầu thay ca")
            approved_count = 0
            waitlist_count = 0
            rejected_count = 0
            errors = []
            for item in items:
                application_id = integer(item.get("application_id"))
                if not application_id or item.get("status") in {"Đã rút"}:
                    continue
                if action == "reject_all":
                    SB.update(TABLES["applications"], {
                        "status": "Từ chối", "admin_note": str(body.get("admin_note") or "Từ chối đơn đăng ký cả tuần").strip(),
                        "reviewed_at": now_iso(), "reviewed_by": user["id"],
                    }, {"id": f"eq.{application_id}"})
                    rejected_count += 1
                    continue
                if item.get("status") == "Đã duyệt":
                    approved_count += 1
                    continue
                try:
                    self.approve_shift_application(user, application_id)
                    approved_count += 1
                except APIError as exc:
                    fallback_status = "Danh sách chờ" if exc.status in {400, 409} else "Từ chối"
                    SB.update(TABLES["applications"], {
                        "status": fallback_status, "admin_note": str(exc),
                        "reviewed_at": now_iso(), "reviewed_by": user["id"],
                    }, {"id": f"eq.{application_id}"})
                    if fallback_status == "Danh sách chờ":
                        waitlist_count += 1
                    else:
                        rejected_count += 1
                    errors.append({"work_date": item.get("work_date"), "reason": str(exc), "status": fallback_status})
            SB.update(TABLES["weekly_requests"], {
                "admin_note": str(body.get("admin_note") or "").strip(),
                "reviewed_at": now_iso(), "reviewed_by": user["id"], "updated_at": now_iso(),
            }, {"id": f"eq.{request_id}"})
            SB.rpc("rumi_refresh_weekly_shift_request", {"p_request_id": request_id})
            refreshed = SB.select(TABLES["weekly_requests"], filters={"id": f"eq.{request_id}"}, limit=1)
            employee_id = integer(requests[0].get("employee_id"))
            message = "Đơn đăng ký cả tuần đã được duyệt" if action == "approve_all" else "Đơn đăng ký cả tuần đã bị từ chối"
            self.notify_employee(employee_id, "Kết quả đăng ký lịch tuần", message, "schedule", "availability")
            self.audit(user, "review_weekly", "weekly_shift_request", request_id, {
                "action": action, "approved": approved_count, "waitlist": waitlist_count,
                "rejected": rejected_count, "errors": errors,
            })
            return self.ok({
                "request": refreshed[0] if refreshed else requests[0],
                "approved_count": approved_count, "waitlist_count": waitlist_count,
                "rejected_count": rejected_count, "errors": errors,
            }, "Đã xử lý đơn đăng ký cả tuần")

        if path == "/api/shift-market/openings":
            self.require_role(user, "admin")
            work_date = parse_date(body.get("work_date"), "Ngày làm")
            start = parse_time(body.get("start_time"), "Giờ bắt đầu")
            end = parse_time(body.get("end_time"), "Giờ kết thúc")
            location_id = integer(body.get("location_id"))
            required_count = max(1, min(integer(body.get("required_count"), 1), 50))
            status = body.get("status", "Mở đăng ký")
            eligible = body.get("eligible_employment_type", "Tất cả")
            if work_date < today_text() or time_minutes(end) <= time_minutes(start):
                raise APIError("Ngày hoặc giờ ca làm không hợp lệ")
            if status not in {"Nháp", "Mở đăng ký"} or eligible not in {"Tất cả", "Full-time", "Part-time"}:
                raise APIError("Trạng thái hoặc loại nhân viên không hợp lệ")
            locations = SB.select(TABLES["locations"], filters={"id": f"eq.{location_id}", "active": "eq.true"}, limit=1)
            if not locations:
                raise APIError("Cửa hàng không tồn tại hoặc đã tắt")
            deadline = str(body.get("application_deadline") or "").strip() or None
            if deadline:
                try:
                    parsed_deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
                    if parsed_deadline.tzinfo is None:
                        parsed_deadline = parsed_deadline.replace(tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
                    deadline = parsed_deadline.isoformat(timespec="seconds")
                except ValueError as exc:
                    raise APIError("Hạn đăng ký không hợp lệ") from exc
            row = SB.insert(TABLES["openings"], {
                "location_id": location_id, "work_date": work_date, "start_time": start, "end_time": end,
                "required_role": str(body.get("required_role", "")).strip(), "required_count": required_count,
                "eligible_employment_type": eligible, "application_deadline": deadline,
                "note": str(body.get("note", "")).strip(), "status": status, "created_by": user["id"],
                "published_at": now_iso() if status == "Mở đăng ký" else None,
            })
            if status == "Mở đăng ký":
                self.notify_role("employee", "RUMI vừa mở ca đăng ký", f"{work_date} {start}–{end} tại {locations[0]['name']} · cần {required_count} người.", "schedule", "availability")
            self.audit(user, "create", "shift_opening", row.get("id"), {"date": work_date, "required_count": required_count})
            return self.ok(row, "Đã đăng ca làm cho nhân viên đăng ký")

        if path == "/api/shift-market/openings/status":
            self.require_role(user, "admin")
            opening_id = integer(body.get("id"))
            status = str(body.get("status", ""))
            if status not in {"Nháp", "Mở đăng ký", "Đã đóng", "Đã hủy"}:
                raise APIError("Trạng thái ca không hợp lệ")
            current = SB.select(TABLES["openings"], filters={"id": f"eq.{opening_id}"}, limit=1)
            if not current:
                raise APIError("Không tìm thấy ca đăng ký", 404)
            opening = current[0]
            updates = {"status": status}
            if status == "Mở đăng ký": updates["published_at"] = now_iso()
            if status == "Đã đóng": updates["closed_at"] = now_iso()
            if status == "Đã hủy":
                assigned = SB.select(TABLES["shifts"], filters={"opening_id": f"eq.{opening_id}"})
                attended = SB.select_in(TABLES["attendance"], "shift_id", [x.get("id") for x in assigned], columns="id")
                if attended:
                    raise APIError("Không thể hủy vì đã có chấm công")
                if assigned:
                    SB.delete(TABLES["shifts"], {"opening_id": f"eq.{opening_id}"})
                apps = SB.select(TABLES["applications"], filters={"opening_id": f"eq.{opening_id}"})
                for app in apps:
                    if app.get("status") != "Đã rút":
                        SB.update(TABLES["applications"], {"status": "Từ chối", "admin_note": "Ca đã hủy", "reviewed_at": now_iso(), "reviewed_by": user["id"]}, {"id": f"eq.{app['id']}"})
                        self.notify_employee(integer(app.get("employee_id")), "Ca đăng ký đã hủy", f"Ca {opening['work_date']} {str(opening['start_time'])[:5]}–{str(opening['end_time'])[:5]} đã được quản lý hủy.", "schedule", "availability")
            row = SB.update(TABLES["openings"], updates, {"id": f"eq.{opening_id}"})[0]
            self.audit(user, "status", "shift_opening", opening_id, {"status": status})
            return self.ok(row, "Đã cập nhật trạng thái ca")

        if path == "/api/shift-market/apply":
            self.require_role(user, "employee")
            opening_id = integer(body.get("opening_id"))
            openings = SB.select(TABLES["openings"], filters={"id": f"eq.{opening_id}"}, limit=1)
            if not openings:
                raise APIError("Không tìm thấy ca đăng ký", 404)
            opening = openings[0]
            if opening.get("status") != "Mở đăng ký":
                raise APIError("Ca này không còn nhận đăng ký")
            deadline = opening.get("application_deadline")
            if deadline and datetime.fromisoformat(str(deadline).replace("Z", "+00:00")) < datetime.now().astimezone():
                raise APIError("Đã hết hạn đăng ký ca")
            employee = user.get("employee") or {}
            week_start = monday_of(opening["work_date"])
            week_end = week_start + timedelta(days=6)
            data = parallel_calls(
                shifts=lambda: SB.select(TABLES["shifts"], filters={"shift_date": f"gte.{week_start.isoformat()}", "and": f"(shift_date.lte.{week_end.isoformat()})"}),
                leaves=lambda: SB.select(TABLES["leaves"], filters={"status": "eq.Đã duyệt", "start_date": f"lte.{opening['work_date']}", "and": f"(end_date.gte.{opening['work_date']})"}),
                day_offs=lambda: SB.select(TABLES["day_offs"], filters={"week_start": f"eq.{week_start.isoformat()}"}),
            )
            rule = self.employee_shift_rule(employee, opening, data["shifts"], data["leaves"], data["day_offs"])
            if not rule["allowed"]:
                raise APIError(rule["reason"], 409)
            existing = SB.select(TABLES["applications"], filters={"opening_id": f"eq.{opening_id}", "employee_id": f"eq.{user['employee_id']}"}, limit=1)
            if existing and existing[0].get("status") == "Đã duyệt":
                raise APIError("Bạn đã được duyệt vào ca này")
            row = SB.upsert(TABLES["applications"], {
                "opening_id": opening_id, "employee_id": user["employee_id"], "status": "Chờ duyệt",
                "employee_note": str(body.get("employee_note", "")).strip(), "admin_note": "",
                "score_snapshot": rule["score"], "applied_at": now_iso(), "reviewed_at": None, "reviewed_by": None,
            }, "opening_id,employee_id")
            self.notify_role("admin", "Có nhân viên đăng ký ca", f"{employee.get('name')} đăng ký ca {opening['work_date']} {str(opening['start_time'])[:5]}–{str(opening['end_time'])[:5]}.", "schedule", "requests")
            self.audit(user, "apply", "shift_opening", opening_id, {"application_id": row.get("id")})
            return self.ok(row, "Đã gửi đơn đăng ký ca")

        if path == "/api/shift-market/applications/withdraw":
            self.require_role(user, "employee")
            application_id = integer(body.get("id"))
            rows = SB.select(TABLES["applications"], filters={"id": f"eq.{application_id}", "employee_id": f"eq.{user['employee_id']}"}, limit=1)
            if not rows:
                raise APIError("Không tìm thấy đơn đăng ký", 404)
            if rows[0].get("status") == "Đã duyệt":
                raise APIError("Đơn đã duyệt. Hãy gửi yêu cầu thay ca thay vì tự rút.")
            row = SB.update(TABLES["applications"], {"status": "Đã rút"}, {"id": f"eq.{application_id}"})[0]
            return self.ok(row, "Đã rút đơn đăng ký")

        if path == "/api/shift-market/applications/status":
            self.require_role(user, "admin")
            application_id = integer(body.get("id"))
            status = str(body.get("status", ""))
            if status not in {"Đã duyệt", "Danh sách chờ", "Từ chối"}:
                raise APIError("Trạng thái đơn không hợp lệ")
            if status == "Đã duyệt":
                row = self.approve_shift_application(user, application_id)
            else:
                applications = SB.select(TABLES["applications"], filters={"id": f"eq.{application_id}"}, limit=1)
                if not applications:
                    raise APIError("Không tìm thấy đơn đăng ký", 404)
                application = applications[0]
                linked = SB.select(TABLES["shifts"], filters={"application_id": f"eq.{application_id}"})
                if linked:
                    attendance = SB.select_in(TABLES["attendance"], "shift_id", [x.get("id") for x in linked], columns="id")
                    if attendance:
                        raise APIError("Không thể đổi kết quả vì ca đã có chấm công")
                    SB.delete(TABLES["shifts"], {"application_id": f"eq.{application_id}"})
                row = SB.update(TABLES["applications"], {
                    "status": status, "admin_note": str(body.get("admin_note", "")).strip(),
                    "reviewed_at": now_iso(), "reviewed_by": user["id"],
                }, {"id": f"eq.{application_id}"})[0]
                self.notify_employee(integer(application["employee_id"]), "Kết quả đăng ký ca", f"Đơn đăng ký ca đã chuyển sang: {status}.", "schedule", "availability")
            self.audit(user, "review", "shift_application", application_id, {"status": status})
            return self.ok(row, "Đã xử lý đơn đăng ký ca")

        if path == "/api/shift-market/openings/finalize":
            self.require_role(user, "admin")
            opening_id = integer(body.get("id"))
            force = bool(body.get("force"))
            waitlist_count = max(0, min(integer(body.get("waitlist_count"), 0), 20))
            openings = SB.select(TABLES["openings"], filters={"id": f"eq.{opening_id}"}, limit=1)
            if not openings:
                raise APIError("Không tìm thấy ca", 404)
            opening = openings[0]
            shifts = SB.select(TABLES["shifts"], filters={"opening_id": f"eq.{opening_id}", "status": "in.(Đã xếp,Đã xác nhận)"})
            required = integer(opening.get("required_count"), 1)
            if len(shifts) < required and not force:
                raise APIError(f"Ca còn thiếu {required-len(shifts)} người. Chọn chốt thiếu người nếu vẫn muốn chốt.", 409)
            SB.update(TABLES["shifts"], {"status": "Đã xác nhận"}, {"opening_id": f"eq.{opening_id}"})
            pending = SB.select(TABLES["applications"], filters={"opening_id": f"eq.{opening_id}", "status": "in.(Chờ duyệt,Danh sách chờ)"}, order="score_snapshot.desc,applied_at.asc")
            for index, app in enumerate(pending):
                new_status = "Danh sách chờ" if index < waitlist_count else "Từ chối"
                SB.update(TABLES["applications"], {"status": new_status, "admin_note": "Ca đã chốt", "reviewed_at": now_iso(), "reviewed_by": user["id"]}, {"id": f"eq.{app['id']}"})
                self.notify_employee(integer(app["employee_id"]), "Ca đã chốt", f"Đơn của bạn được chuyển sang {new_status.lower()}.", "schedule", "availability")
            row = SB.update(TABLES["openings"], {"status": "Đã chốt", "closed_at": now_iso(), "finalized_at": now_iso()}, {"id": f"eq.{opening_id}"})[0]
            self.audit(user, "finalize", "shift_opening", opening_id, {"assigned": len(shifts), "required": required, "waitlist": waitlist_count})
            return self.ok(row, "Đã chốt ca và xử lý các đơn còn lại")

        if path == "/api/shift-market/day-offs":
            self.require_role(user, "employee")
            employee = user.get("employee") or {}
            if employee.get("employment_type") != "Full-time":
                raise APIError("Chỉ nhân viên Full-time đăng ký ngày nghỉ tuần")
            week_start = parse_date(body.get("week_start"), "Tuần")
            monday = monday_of(week_start)
            if week_start != monday.isoformat():
                raise APIError("Ngày đầu tuần phải là Thứ Hai")
            preferred = parse_date(body.get("preferred_date"), "Ngày nghỉ ưu tiên")
            alternate = str(body.get("alternate_date") or "").strip()
            if not monday <= datetime.strptime(preferred, "%Y-%m-%d").date() <= monday + timedelta(days=6):
                raise APIError("Ngày nghỉ phải nằm trong tuần đã chọn")
            if alternate:
                alternate = parse_date(alternate, "Ngày nghỉ dự phòng")
                if not monday <= datetime.strptime(alternate, "%Y-%m-%d").date() <= monday + timedelta(days=6):
                    raise APIError("Ngày dự phòng phải nằm trong tuần đã chọn")
            row = SB.upsert(TABLES["day_offs"], {
                "employee_id": user["employee_id"], "week_start": week_start, "preferred_date": preferred,
                "alternate_date": alternate or None, "approved_date": None, "reason": str(body.get("reason", "")).strip(),
                "status": "Chờ duyệt", "admin_note": "", "reviewed_at": None, "reviewed_by": None,
            }, "employee_id,week_start")
            self.notify_role("admin", "Có đăng ký ngày nghỉ tuần", f"{employee.get('name')} muốn nghỉ ngày {preferred}.", "schedule", "requests")
            return self.ok(row, "Đã gửi ngày nghỉ ưu tiên")

        if path == "/api/shift-market/day-offs/status":
            self.require_role(user, "admin")
            request_id = integer(body.get("id"))
            status = str(body.get("status", ""))
            if status not in {"Đã duyệt", "Từ chối"}:
                raise APIError("Trạng thái không hợp lệ")
            rows = SB.select(TABLES["day_offs"], filters={"id": f"eq.{request_id}"}, limit=1)
            if not rows:
                raise APIError("Không tìm thấy đăng ký ngày nghỉ", 404)
            request_row = rows[0]
            approved_date = str(body.get("approved_date") or request_row.get("preferred_date") or "")
            if status == "Đã duyệt":
                approved_date = parse_date(approved_date, "Ngày nghỉ được duyệt")
                monday = datetime.strptime(str(request_row["week_start"]), "%Y-%m-%d").date()
                if not monday <= datetime.strptime(approved_date, "%Y-%m-%d").date() <= monday + timedelta(days=6):
                    raise APIError("Ngày nghỉ được duyệt phải nằm trong tuần")
                conflicts = SB.select(TABLES["shifts"], filters={"employee_id": f"eq.{request_row['employee_id']}", "shift_date": f"eq.{approved_date}", "status": "in.(Đã xếp,Đã xác nhận)"})
                if conflicts:
                    raise APIError("Nhân viên đang có ca trong ngày này. Hãy đổi/xóa ca trước khi duyệt nghỉ.", 409)
            updated = SB.update(TABLES["day_offs"], {
                "status": status, "approved_date": approved_date if status == "Đã duyệt" else None,
                "admin_note": str(body.get("admin_note", "")).strip(), "reviewed_at": now_iso(), "reviewed_by": user["id"],
            }, {"id": f"eq.{request_id}"})[0]
            self.notify_employee(integer(request_row["employee_id"]), "Ngày nghỉ tuần đã được xử lý", f"Yêu cầu tuần {request_row['week_start']}: {status}.", "schedule", "availability")
            return self.ok(updated, "Đã xử lý ngày nghỉ tuần")

        if path == "/api/shift-market/auto-fulltime":
            self.require_role(user, "admin")
            week_start = monday_of(parse_date(body.get("week_start"), "Tuần"))
            week_end = week_start + timedelta(days=6)
            data = parallel_calls(
                openings=lambda: SB.select(TABLES["openings"], filters={"work_date": f"gte.{week_start.isoformat()}", "and": f"(work_date.lte.{week_end.isoformat()})", "status": "in.(Mở đăng ký,Đã đóng)"}, order="work_date.asc,start_time.asc"),
                employees=lambda: SB.select(TABLES["employees"], filters={"status": "eq.Đang làm", "employment_type": "eq.Full-time"}, order="name.asc"),
                shifts=lambda: SB.select(TABLES["shifts"], filters={"shift_date": f"gte.{week_start.isoformat()}", "and": f"(shift_date.lte.{week_end.isoformat()})"}),
                leaves=lambda: SB.select(TABLES["leaves"], filters={"status": "eq.Đã duyệt", "start_date": f"lte.{week_end.isoformat()}", "and": f"(end_date.gte.{week_start.isoformat()})"}),
                day_offs=lambda: SB.select(TABLES["day_offs"], filters={"week_start": f"eq.{week_start.isoformat()}"}),
            )
            applications = SB.select_in(TABLES["applications"], "opening_id", [x.get("id") for x in data["openings"]])
            app_map = {(integer(x.get("opening_id")), integer(x.get("employee_id"))): x for x in applications}
            created = []
            for opening in data["openings"]:
                if opening.get("eligible_employment_type") == "Part-time":
                    continue
                assigned = [x for x in data["shifts"] if integer(x.get("opening_id")) == integer(opening.get("id")) and x.get("status") in {"Đã xếp", "Đã xác nhận"}]
                slots = max(integer(opening.get("required_count"), 1) - len(assigned), 0)
                if not slots:
                    continue
                assigned_ids = {integer(x.get("employee_id")) for x in assigned}
                candidates = []
                for employee in data["employees"]:
                    if integer(employee.get("id")) in assigned_ids:
                        continue
                    rule = self.employee_shift_rule(employee, opening, data["shifts"], data["leaves"], data["day_offs"])
                    if rule["allowed"]:
                        candidates.append((rule["score"], -rule["week_hours"], employee, rule))
                candidates.sort(key=lambda x: (-x[0], -x[1], str(x[2].get("name"))))
                for _, __, employee, rule in candidates[:slots]:
                    existing_app = app_map.get((integer(opening["id"]), integer(employee["id"])))
                    if existing_app:
                        app = SB.update(TABLES["applications"], {"status": "Đã duyệt", "admin_note": "Xếp tự động Full-time", "score_snapshot": rule["score"], "reviewed_at": now_iso(), "reviewed_by": user["id"]}, {"id": f"eq.{existing_app['id']}"})[0]
                    else:
                        app = SB.insert(TABLES["applications"], {"opening_id": opening["id"], "employee_id": employee["id"], "status": "Đã duyệt", "employee_note": "", "admin_note": "Xếp tự động Full-time", "score_snapshot": rule["score"], "reviewed_at": now_iso(), "reviewed_by": user["id"]})
                    shift = SB.insert(TABLES["shifts"], {
                        "employee_id": employee["id"], "location_id": opening["location_id"], "shift_date": opening["work_date"],
                        "start_time": opening["start_time"], "end_time": opening["end_time"], "note": opening.get("note", ""),
                        "status": "Đã xếp", "created_by": user["id"], "opening_id": opening["id"], "application_id": app["id"],
                    })
                    data["shifts"].append(shift)
                    created.append(shift)
                    self.notify_employee(integer(employee["id"]), "Bạn được xếp ca Full-time", f"{opening['work_date']} {str(opening['start_time'])[:5]}–{str(opening['end_time'])[:5]}.", "schedule", "shifts")
            compliance = self.full_time_compliance(week_start.isoformat(), week_end.isoformat())
            self.audit(user, "auto_fulltime", "schedule_week", week_start.isoformat(), {"created": len(created)})
            return self.ok({"created_count": len(created), "compliance": compliance}, f"Đã xếp tự động {len(created)} ca Full-time")

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

        if path == "/api/scheduling/auto-assign":
            self.require_role(user, "admin")
            employee_count = max(1, min(integer(body.get("employee_count"), 1), 20))
            location_id = integer(body.get("location_id"))
            work_date = parse_date(body.get("shift_date"), "Ngày làm")
            start = parse_time(body.get("start_time"), "Giờ bắt đầu")
            end = parse_time(body.get("end_time"), "Giờ kết thúc")
            required_role = str(body.get("required_role", "")).strip()
            if not location_id or time_minutes(end) <= time_minutes(start):
                raise APIError("Thông tin ca làm chưa hợp lệ")
            locations = SB.select(TABLES["locations"], filters={"id": f"eq.{location_id}", "active": "eq.true"}, limit=1)
            if not locations:
                raise APIError("Vị trí cửa hàng không tồn tại hoặc đã tắt")
            candidates = [x for x in self.candidate_rows(work_date, start, end, required_role=required_role) if x.get("state") == "available"]
            selected = candidates[:employee_count]
            if not selected:
                raise APIError("Không có nhân viên phù hợp. Hãy duyệt lịch rảnh hoặc đổi khung giờ.", 409)
            rows = [{
                "employee_id": x["employee_id"], "location_id": location_id, "shift_date": work_date,
                "start_time": start, "end_time": end, "note": str(body.get("note", "")).strip(),
                "status": "Đã xếp", "created_by": user["id"], "availability_request_id": x.get("availability_id"),
            } for x in selected]
            created = SB.insert_many(TABLES["shifts"], rows)
            availability_ids = [x.get("availability_id") for x in selected if x.get("availability_id")]
            if availability_ids:
                SB.update(TABLES["availability"], {"status": "Đã xếp ca"}, {"id": pg_in(availability_ids)})
            SB.insert_many(TABLES["notifications"], [{
                "employee_id": x["employee_id"], "title": "Bạn có ca làm mới",
                "message": f"Ngày {work_date}, {start}–{end} tại {locations[0]['name']}.",
                "type": "schedule", "link": "shifts",
            } for x in selected])
            self.audit(user, "auto_assign", "shift", "bulk", {"date": work_date, "time": f"{start}-{end}", "count": len(created), "requested": employee_count})
            message = f"Đã xếp tự động {len(created)}/{employee_count} nhân viên phù hợp"
            return self.ok(self.enriched_shifts(created), message)

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
            action = str(body.get("action", "auto")).strip().lower()
            latitude = num(body.get("latitude"), 999)
            longitude = num(body.get("longitude"), 999)
            accuracy = num(body.get("accuracy"), 99999)
            client_time = str(body.get("position_timestamp") or body.get("client_time") or "").strip()
            device_raw = str(body.get("device_id") or "").strip()[:200]
            device_hash = hash_secret(device_raw, "attendance-device") if device_raw else ""
            rpc_body = {
                "p_shift_id": shift_id,
                "p_employee_id": user["employee_id"],
                "p_action": action,
                "p_lat": latitude,
                "p_lng": longitude,
                "p_accuracy": accuracy,
                "p_device_hash": device_hash,
                "p_client_time": client_time or None,
                "p_ip_hash": self.ip_hash(),
                "p_now": now_iso(),
            }
            try:
                result = SB.rpc("rumi_clock_shift_v62", rpc_body)
            except APIError as exc:
                try:
                    SB.insert(TABLES["attendance_events"], {
                        "shift_id": shift_id or None,
                        "employee_id": user.get("employee_id"),
                        "action": action or "auto",
                        "success": False,
                        "reason": str(exc)[:500],
                        "latitude": latitude if -90 <= latitude <= 90 else None,
                        "longitude": longitude if -180 <= longitude <= 180 else None,
                        "accuracy_m": accuracy if accuracy < 99999 else None,
                        "device_id_hash": device_hash,
                        "ip_hash": self.ip_hash(),
                        "client_position_at": client_time or None,
                    })
                except Exception:
                    pass
                self.audit(user, "clock_rejected", "attendance", shift_id, {"action": action, "reason": str(exc)[:200]})
                raise
            message = "Chấm công vào ca thành công" if result.get("action") == "checkin" else "Chấm công ra ca thành công"
            if result.get("risk_level") == "Cao" or result.get("review_status") == "Chờ duyệt":
                self.notify_role("admin", "Chấm công cần kiểm tra", f"{user['profile']['name']} có lượt chấm công rủi ro cao tại ca #{shift_id}.", "warning", "attendance")
            self.audit(user, result.get("action", "clock"), "attendance", shift_id, {
                "distance_m": result.get("distance_m"), "accuracy_m": result.get("accuracy_m"),
                "risk_level": result.get("risk_level"),
            })
            ATTENDANCE_ALERT_CACHE.clear()
            PAYROLL_CACHE.clear()
            return self.ok(result, message)

        if path == "/api/attendance/corrections":
            self.require_role(user, "employee")
            shift_id = integer(body.get("shift_id"))
            reason = str(body.get("reason", "")).strip()
            requested_in = parse_time(body.get("requested_check_in"), "Giờ vào đề nghị") if body.get("requested_check_in") else None
            requested_out = parse_time(body.get("requested_check_out"), "Giờ ra đề nghị") if body.get("requested_check_out") else None
            if not shift_id or len(reason) < 5:
                raise APIError("Vui lòng chọn ca và nhập lý do ít nhất 5 ký tự")
            shifts = SB.select(TABLES["shifts"], filters={"id": f"eq.{shift_id}", "employee_id": f"eq.{user['employee_id']}"}, limit=1)
            if not shifts:
                raise APIError("Không tìm thấy ca làm của bạn", 404)
            shift_day = datetime.strptime(str(shifts[0]["shift_date"])[:10], "%Y-%m-%d").date()
            if shift_day > date.today():
                raise APIError("Không thể yêu cầu sửa chấm công cho ca chưa diễn ra")
            if shift_day < date.today() - timedelta(days=62):
                raise APIError("Chỉ tiếp nhận yêu cầu sửa chấm công trong 62 ngày gần nhất")
            attendance = SB.select(TABLES["attendance"], filters={"shift_id": f"eq.{shift_id}"}, limit=1)
            row = SB.insert(TABLES["attendance_corrections"], {
                "attendance_id": attendance[0].get("id") if attendance else None,
                "shift_id": shift_id,
                "employee_id": user["employee_id"],
                "requested_check_in": requested_in,
                "requested_check_out": requested_out,
                "reason": reason,
                "status": "Chờ duyệt",
            })
            self.notify_role("admin", "Có yêu cầu sửa chấm công", f"{user['profile']['name']} gửi yêu cầu sửa ca ngày {shifts[0]['shift_date']}.", "attendance", "attendance")
            self.audit(user, "request_correction", "attendance", shift_id, {"request_id": row.get("id")})
            return self.ok(row, "Đã gửi yêu cầu sửa chấm công")

        if path == "/api/attendance/corrections/review":
            self.require_role(user, "admin")
            request_id = integer(body.get("id"))
            status = str(body.get("status", "")).strip()
            admin_note = str(body.get("admin_note", "")).strip()
            requests = SB.select(TABLES["attendance_corrections"], filters={"id": f"eq.{request_id}"}, limit=1)
            if not requests:
                raise APIError("Không tìm thấy yêu cầu sửa chấm công", 404)
            request_row = requests[0]
            if request_row.get("status") != "Chờ duyệt":
                raise APIError("Yêu cầu này đã được xử lý")
            if status not in {"Đã duyệt", "Từ chối"}:
                raise APIError("Trạng thái xử lý không hợp lệ")
            if status == "Đã duyệt":
                shifts = SB.select(TABLES["shifts"], filters={"id": f"eq.{request_row['shift_id']}"}, limit=1)
                if not shifts:
                    raise APIError("Ca làm không còn tồn tại", 404)
                shift = shifts[0]
                current = SB.select(TABLES["attendance"], filters={"shift_id": f"eq.{request_row['shift_id']}"}, limit=1)
                existing = current[0] if current else {}
                check_in = normalize_time(request_row.get("requested_check_in")) or normalize_time(existing.get("check_in"))
                check_out = normalize_time(request_row.get("requested_check_out")) or normalize_time(existing.get("check_out"))
                if not check_in:
                    raise APIError("Yêu cầu chưa có giờ vào hợp lệ")
                metrics = attendance_metrics(shift, check_in, check_out)
                SB.upsert(TABLES["attendance"], {
                    "shift_id": shift["id"], "employee_id": shift["employee_id"], "work_date": shift["shift_date"],
                    "check_in": check_in, "check_out": check_out,
                    "hours": metrics["payable_hours"], "scheduled_hours": metrics["scheduled_hours"],
                    "scheduled_minutes": metrics["scheduled_minutes"], "worked_minutes": metrics["worked_minutes"],
                    "base_payable_minutes": metrics["base_payable_minutes"], "payable_minutes": metrics["payable_minutes"],
                    "payable_hours": metrics["payable_hours"], "late_minutes": metrics["late_minutes"],
                    "early_leave_minutes": metrics["early_leave_minutes"], "overtime_minutes": metrics["overtime_minutes"],
                    "overtime_requested_minutes": metrics["overtime_requested_minutes"],
                    "overtime_approved_minutes": metrics["overtime_approved_minutes"],
                    "overtime_status": metrics["overtime_status"], "status": metrics["status"],
                    "calculation_note": metrics["calculation_note"], "review_status": "Đã duyệt",
                    "reviewed_by": user["id"], "reviewed_at": now_iso(),
                    "note": admin_note or "Điều chỉnh theo yêu cầu nhân viên",
                }, "shift_id")
            SB.update(TABLES["attendance_corrections"], {
                "status": status, "admin_note": admin_note, "reviewed_by": user["id"], "reviewed_at": now_iso(),
            }, {"id": f"eq.{request_id}"})
            self.notify_employee(integer(request_row["employee_id"]), "Yêu cầu sửa chấm công đã xử lý", f"Trạng thái: {status}. {admin_note}".strip(), "attendance", "attendance")
            self.audit(user, "review_correction", "attendance", request_row.get("shift_id"), {"request_id": request_id, "status": status})
            return self.ok(None, "Đã xử lý yêu cầu sửa chấm công")

        if path == "/api/attendance/overtime/review":
            self.require_role(user, "admin")
            attendance_id = integer(body.get("attendance_id"))
            approved_minutes = max(0, integer(body.get("approved_minutes"), 0))
            result = SB.rpc("rumi_review_overtime_v55", {
                "p_attendance_id": attendance_id,
                "p_approved_minutes": approved_minutes,
                "p_admin_user_id": user["id"],
                "p_note": str(body.get("note", "")).strip(),
            })
            rows = SB.select(TABLES["attendance"], filters={"id": f"eq.{attendance_id}"}, limit=1, columns="employee_id,work_date")
            if rows:
                self.notify_employee(integer(rows[0].get("employee_id")), "Tăng ca đã được xử lý", f"Ngày {rows[0].get('work_date')}: duyệt {result.get('approved_minutes', 0)} phút.", "attendance", "attendance")
            self.audit(user, "review_overtime", "attendance", attendance_id, result)
            return self.ok(result, "Đã cập nhật thời gian tăng ca")

        if path == "/api/attendance/risk/review":
            self.require_role(user, "admin")
            attendance_id = integer(body.get("attendance_id"))
            shift_id = integer(body.get("shift_id"))
            status = str(body.get("status", "")).strip()
            note = str(body.get("note", "")).strip()
            if status not in {"Đã duyệt", "Từ chối"}:
                raise APIError("Trạng thái duyệt rủi ro không hợp lệ")
            updates = {
                "review_status": status,
                "reviewed_by": user["id"],
                "reviewed_at": now_iso(),
                "note": note,
            }
            if status == "Từ chối":
                updates.update({"payable_minutes": 0, "payable_hours": 0, "hours": 0, "status": "Từ chối chấm công"})
            filters = {"id": f"eq.{attendance_id}"} if attendance_id else ({"shift_id": f"eq.{shift_id}"} if shift_id else {})
            rows = SB.update(TABLES["attendance"], updates, filters) if filters else []
            if not rows and shift_id:
                shifts = SB.select(TABLES["shifts"], filters={"id": f"eq.{shift_id}"}, limit=1, columns="id,employee_id,location_id,shift_date,start_time,end_time,status,note")
                if not shifts:
                    raise APIError("Không tìm thấy ca làm", 404)
                shift = shifts[0]
                synthetic_status = "Đã kiểm tra - không có chấm công" if status == "Đã duyệt" else "Từ chối chấm công"
                rows = [SB.upsert(TABLES["attendance"], {
                    "shift_id": shift["id"], "employee_id": shift["employee_id"], "work_date": shift["shift_date"],
                    "check_in": None, "check_out": None, "hours": 0,
                    "scheduled_hours": shift_hours(str(shift.get("start_time")), str(shift.get("end_time"))),
                    "worked_minutes": 0, "base_payable_minutes": 0, "payable_minutes": 0, "payable_hours": 0,
                    "late_minutes": 0, "early_leave_minutes": 0, "overtime_minutes": 0,
                    "overtime_requested_minutes": 0, "overtime_approved_minutes": 0, "overtime_status": "Không có",
                    "status": synthetic_status, "risk_level": "Cao", "review_status": status,
                    "reviewed_by": user["id"], "reviewed_at": now_iso(),
                    "calculation_note": "Admin đã xử lý lượt ca không có chấm công hợp lệ.",
                    "note": note or ("Admin xác nhận đã kiểm tra" if status == "Đã duyệt" else "Admin loại công vì không có chấm công hợp lệ"),
                }, "shift_id")]
                try:
                    SB.update(TABLES["attendance_alerts"], {
                        "status": "Đã xử lý" if status == "Đã duyệt" else "Vắng ca",
                        "resolved_at": now_iso(),
                        "resolution_note": note or synthetic_status,
                        "last_detected_at": now_iso(),
                    }, {"shift_id": f"eq.{shift_id}"})
                    ATTENDANCE_ALERT_CACHE.clear()
                except Exception as exc:
                    print("Attendance alert resolve warning:", repr(exc))
            if not rows:
                raise APIError("Không tìm thấy lượt chấm công", 404)
            self.notify_employee(integer(rows[0].get("employee_id")), "Lượt chấm công đã được kiểm tra", f"Kết quả: {status}. {note}".strip(), "attendance", "attendance")
            self.audit(user, "review_risk", "attendance", rows[0].get("id") or attendance_id or shift_id, {"status": status, "shift_id": shift_id})
            ATTENDANCE_ALERT_CACHE.clear()
            return self.ok(rows[0], "Đã xử lý lượt chấm công rủi ro")

        if path == "/api/attendance/alerts/remind":
            self.require_role(user, "admin")
            alert_id = integer(body.get("id"))
            alerts = SB.select(TABLES["attendance_alerts"], filters={"id": f"eq.{alert_id}"}, limit=1)
            if not alerts:
                raise APIError("Không tìm thấy cảnh báo chấm công", 404)
            alert = alerts[0]
            shifts = SB.select(TABLES["shifts"], filters={"id": f"eq.{alert['shift_id']}"}, limit=1)
            if not shifts:
                raise APIError("Ca làm không còn tồn tại", 404)
            shift = shifts[0]
            message = f"Nhắc chấm công ca {str(shift.get('start_time'))[:5]}-{str(shift.get('end_time'))[:5]} ngày {shift.get('shift_date')}. Trạng thái hiện tại: {alert.get('status')}."
            self.notify_employee(integer(alert.get("employee_id")), "Quản lý nhắc chấm công", message, "warning", "attendance")
            SB.update(TABLES["attendance_alerts"], {"notified_employee_at": now_iso(), "last_detected_at": now_iso()}, {"id": f"eq.{alert_id}"})
            self.audit(user, "remind", "attendance_alert", alert_id, {"status": alert.get("status")})
            ATTENDANCE_ALERT_CACHE.clear()
            return self.ok(None, "Đã gửi nhắc nhở cho nhân viên")

        if path == "/api/attendance/alerts/resolve":
            self.require_role(user, "admin")
            alert_id = integer(body.get("id"))
            action = str(body.get("action") or "dismiss")
            note = str(body.get("note") or "").strip()
            alerts = SB.select(TABLES["attendance_alerts"], filters={"id": f"eq.{alert_id}"}, limit=1)
            if not alerts:
                raise APIError("Không tìm thấy cảnh báo chấm công", 404)
            alert = alerts[0]
            if action == "absent" and alert.get("status") != "Vắng ca":
                raise APIError("Chỉ xác nhận vắng sau khi ca đã kết thúc", 409)
            final_status = "Vắng ca" if action == "absent" else "Đã xử lý"
            resolution = note or ("Admin xác nhận nhân viên vắng ca" if action == "absent" else "Admin đã kiểm tra cảnh báo")
            SB.update(TABLES["attendance_alerts"], {
                "status": final_status,
                "resolved_at": now_iso(),
                "resolution_note": resolution,
                "last_detected_at": now_iso(),
            }, {"id": f"eq.{alert_id}"})
            self.notify_employee(integer(alert.get("employee_id")), "Cảnh báo chấm công đã được xử lý", resolution, "attendance", "attendance")
            self.audit(user, "resolve", "attendance_alert", alert_id, {"action": action, "note": resolution})
            ATTENDANCE_ALERT_CACHE.clear()
            return self.ok(None, "Đã xử lý cảnh báo chấm công")

        if path == "/api/attendance/manual":
            self.require_role(user, "admin")
            shift_id = integer(body.get("shift_id"))
            shifts = SB.select(TABLES["shifts"], filters={"id": f"eq.{shift_id}"}, limit=1)
            if not shifts:
                raise APIError("Không tìm thấy ca làm")
            shift = shifts[0]
            check_in = parse_time(body.get("check_in"), "Giờ vào")
            check_out = parse_time(body.get("check_out"), "Giờ ra") if body.get("check_out") else None
            approve_overtime = str(body.get("approve_overtime", "false")).lower() in {"1","true","yes","on"}
            metrics = attendance_metrics(shift, check_in, check_out, approve_overtime=approve_overtime)
            row = SB.upsert(TABLES["attendance"], {
                "shift_id": shift_id, "employee_id": shift["employee_id"], "work_date": shift["shift_date"],
                "check_in": check_in, "check_out": check_out, "hours": metrics["payable_hours"],
                "scheduled_minutes": metrics["scheduled_minutes"], "worked_minutes": metrics["worked_minutes"],
                "base_payable_minutes": metrics["base_payable_minutes"], "payable_minutes": metrics["payable_minutes"],
                "scheduled_hours": metrics["scheduled_hours"], "payable_hours": metrics["payable_hours"],
                "late_minutes": metrics["late_minutes"], "early_leave_minutes": metrics["early_leave_minutes"],
                "overtime_minutes": metrics["overtime_minutes"], "overtime_requested_minutes": metrics["overtime_requested_minutes"],
                "overtime_approved_minutes": metrics["overtime_approved_minutes"], "overtime_status": metrics["overtime_status"],
                "status": metrics["status"], "calculation_note": metrics["calculation_note"],
                "review_status": "Đã duyệt", "reviewed_by": user["id"], "reviewed_at": now_iso(),
                "note": str(body.get("note", "Điều chỉnh bởi quản lý")).strip(),
            }, "shift_id")
            self.audit(user, "manual_update", "attendance", row.get("id"), {"shift_id": shift_id})
            return self.ok(row, "Đã cập nhật chấm công")

        if path == "/api/payroll/generate":
            self.require_role(user, "admin")
            month = str(body.get("month", ""))
            month_bounds(month)
            data = self.save_payroll_draft(user, month, str(body.get("note", "")).strip())
            self.audit(user, "generate", "payroll", month, {"employee_count": len(data.get("items", []))})
            return self.ok(data, "Đã tạo lại bảng lương tháng")

        if path == "/api/payroll/lock":
            self.require_role(user, "admin")
            month = str(body.get("month", ""))
            month_bounds(month)
            data = self.save_payroll_draft(user, month, str(body.get("note", "")).strip())
            unresolved = [
                x for x in data.get("items", [])
                if integer(x.get("missing_attendance_count"))
                or integer(x.get("incomplete_attendance_count"))
                or integer(x.get("pending_checkin_count"))
                or integer(x.get("late_unclocked_count"))
                or integer(x.get("no_show_risk_count"))
                or integer(x.get("active_shift_count"))
                or integer(x.get("upcoming_shift_count"))
            ]
            if unresolved:
                details = ", ".join(
                    f"{x.get('name')}: {x.get('payroll_state')}"
                    for x in unresolved[:4]
                )
                extra = f" và {len(unresolved)-4} nhân viên khác" if len(unresolved) > 4 else ""
                raise APIError(
                    f"Chưa thể chốt bảng lương vì còn ca chưa hoàn tất ({details}{extra}). "
                    "Hãy chấm công/xử lý công hoặc chờ ca diễn ra.",
                    409,
                )
            if not any(num(x.get("total")) > 0 for x in data.get("items", [])):
                raise APIError("Chưa thể chốt vì tháng này chưa phát sinh khoản lương phải trả.", 409)
            run_id = data["run"]["id"]
            SB.update(TABLES["payroll_runs"], {"status": "Đã chốt", "locked_at": now_iso()}, {"id": f"eq.{run_id}"})
            self.audit(user, "lock", "payroll", month)
            return self.ok(self.payroll_page(user, month), "Đã chốt bảng lương tháng")

        if path == "/api/payroll/unlock":
            self.require_role(user, "admin")
            month = str(body.get("month", ""))
            month_bounds(month)
            run = self.payroll_run(month)
            if not run:
                raise APIError("Tháng này chưa có bảng lương", 404)
            SB.update(TABLES["payroll_runs"], {"status": "Nháp", "locked_at": None}, {"id": f"eq.{run['id']}"})
            self.audit(user, "unlock", "payroll", month)
            return self.ok(self.payroll_page(user, month), "Đã mở khóa bảng lương")

        if path == "/api/payroll/adjustment":
            self.require_role(user, "admin")
            employee_id = integer(body.get("employee_id"))
            month = str(body.get("month", ""))
            run = self.payroll_run(month) if re.fullmatch(r"\d{4}-\d{2}", month) else None
            if run and run.get("status") == "Đã chốt":
                raise APIError("Bảng lương đã chốt, không thể sửa thưởng/phạt.", 409)
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
            if status == "Đã thanh toán":
                run = self.payroll_run(month)
                if not run or run.get("status") != "Đã chốt":
                    raise APIError("Chỉ được xác nhận đã trả sau khi bảng lương tháng đã chốt.", 409)
                items = SB.select(
                    TABLES["payroll_items"],
                    filters={"run_id": f"eq.{run['id']}", "employee_id": f"eq.{employee_id}"},
                    limit=1,
                )
                if not items:
                    raise APIError("Không tìm thấy phiếu lương đã chốt của nhân viên.", 404)
                item = items[0]
                if num(item.get("total")) <= 0:
                    raise APIError("Phiếu lương bằng 0 nên không thể đánh dấu đã thanh toán.", 409)
                if not bool(item.get("eligible_for_payment")):
                    raise APIError(
                        f"Phiếu lương chưa đủ điều kiện thanh toán: {item.get('payroll_state') or 'còn dữ liệu công chưa hoàn tất'}.",
                        409,
                    )
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
        self.require_password_changed(user, path)

        match = re.fullmatch(r"/api/employees/(\d+)", path)
        if match:
            self.require_role(user, "admin")
            employee_id = integer(match.group(1))
            code = str(body.get("code", "")).strip().upper()
            name = str(body.get("name", "")).strip()
            username = str(body.get("username", "")).strip().lower()
            if not code or len(name) < 2 or not re.fullmatch(r"[a-z0-9._-]{3,40}", username):
                raise APIError("Mã, họ tên hoặc tên đăng nhập chưa hợp lệ")
            employment_type = body.get("employment_type", "Part-time")
            weekly_target = num(body.get("weekly_target_hours"), 48 if employment_type == "Full-time" else 24)
            requested_weekly_max = num(body.get("max_weekly_hours"), 56)
            if requested_weekly_max > 56:
                raise APIError("Mỗi nhân viên chỉ được cấu hình tối đa 56 giờ/tuần")
            if weekly_target > requested_weekly_max:
                raise APIError("Giờ mục tiêu không được lớn hơn giới hạn giờ tuần")
            rows = SB.update(TABLES["employees"], {
                "code": code,
                "name": name,
                "phone": str(body.get("phone", "")).strip(),
                "email": str(body.get("email", "")).strip(),
                "role": str(body.get("job_role", "Nhân viên")).strip(),
                "hourly_wage": num(body.get("hourly_wage"), 25000),
                "employment_type": employment_type,
                "weekly_target_hours": weekly_target,
                "max_weekly_hours": requested_weekly_max,
                "max_daily_hours": num(body.get("max_daily_hours"), 8),
                "max_consecutive_days": integer(body.get("max_consecutive_days"), 6),
                "weekly_days_off": integer(body.get("weekly_days_off"), 1 if body.get("employment_type") == "Full-time" else 0),
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
                "checkout_after_minutes": integer(body.get("checkout_after_minutes"), 180),
                "max_gps_accuracy_m": integer(body.get("max_gps_accuracy_m"), 80),
                "late_grace_minutes": integer(body.get("late_grace_minutes"), 5),
                "early_leave_grace_minutes": integer(body.get("early_leave_grace_minutes"), 5),
                "max_overtime_minutes": integer(body.get("max_overtime_minutes"), 180),
                "overtime_requires_approval": str(body.get("overtime_requires_approval", "true")).lower() in {"1","true","yes","on"},
                "location_freshness_seconds": integer(body.get("location_freshness_seconds"), 120),
                "min_clock_gap_minutes": integer(body.get("min_clock_gap_minutes"), 1),
                "attendance_warning_minutes": integer(body.get("attendance_warning_minutes"), 15),
                "attendance_no_show_minutes": integer(body.get("attendance_no_show_minutes"), 30),
                "attendance_absent_after_end_minutes": integer(body.get("attendance_absent_after_end_minutes"), 0),
                "attendance_alert_refresh_seconds": integer(body.get("attendance_alert_refresh_seconds"), 60),
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
        self.require_password_changed(user, path)

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
    rows = SB.select(TABLES["users"], filters={"username": f"eq.{ADMIN_USERNAME}"}, limit=1)
    if rows:
        admin = rows[0]
        if admin.get("role") != "admin":
            raise APIError(f"Tên đăng nhập cấu hình '{ADMIN_USERNAME}' đang thuộc tài khoản nhân viên. Hãy đổi RUMI_ADMIN_USERNAME.")
        updates = {}
        if not admin.get("active"):
            updates["active"] = True
        if ADMIN_RESET_ON_START:
            validate_password_policy(ADMIN_PASSWORD, ADMIN_USERNAME, admin=True)
            hashed, salt = password_hash(ADMIN_PASSWORD, iterations=PASSWORD_ITERATIONS)
            updates.update({
                "password_hash": hashed, "password_salt": salt,
                "password_iterations": PASSWORD_ITERATIONS,
                "must_change_password": False,
                "password_changed_at": now_iso(),
                "failed_login_count": 0,
                "locked_until": None,
            })
            SB.update(TABLES["auth_sessions"], {"revoked_at": now_iso(), "revoke_reason": "Admin đặt lại mật khẩu"},
                      {"user_id": f"eq.{admin['id']}", "revoked_at": "is.null"})
        if updates:
            admin = SB.update(TABLES["users"], updates, {"id": f"eq.{admin['id']}"})[0]
        return admin
    validate_password_policy(ADMIN_PASSWORD, ADMIN_USERNAME, admin=True)
    hashed, salt = password_hash(ADMIN_PASSWORD, iterations=PASSWORD_ITERATIONS)
    return SB.insert(TABLES["users"], {
        "username": ADMIN_USERNAME,
        "password_hash": hashed,
        "password_salt": salt,
        "password_iterations": PASSWORD_ITERATIONS,
        "must_change_password": False,
        "password_changed_at": now_iso(),
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
    print("RUMI Manager v5.5 SECURITY & SMART ATTENDANCE đang chạy")
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
