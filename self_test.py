#!/usr/bin/env python3
"""Offline checks for security, scheduling, payroll metrics and Excel export."""
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo
from zipfile import ZipFile

from excel_export import build_schedule_week_xlsx
from server import PASSWORD_ITERATIONS, RumiHandler, attendance_metrics, calculate_hours, classify_shift_attendance, make_session, overlaps, parse_session, password_hash, validate_password_policy, verify_password


def main():
    digest, salt = password_hash("MatKhauAnToan123!", iterations=PASSWORD_ITERATIONS)
    assert verify_password("MatKhauAnToan123!", digest, salt, PASSWORD_ITERATIONS)
    validate_password_policy("MatKhauAnToan123!", "nhanvien")
    assert not verify_password("sai", digest, salt, PASSWORD_ITERATIONS)
    token = make_session(42)
    assert parse_session(token) == 42
    assert parse_session(token + "x") is None
    assert overlaps("08:00", "12:00", "11:00", "13:00")
    assert not overlaps("08:00", "12:00", "12:00", "13:00")
    assert calculate_hours("08:00", "12:30") == 4.5
    metrics = attendance_metrics({"start_time":"08:00","end_time":"12:00"}, "08:05", "12:10")
    assert metrics["late_minutes"] == 5
    assert metrics["overtime_minutes"] == 10
    assert metrics["base_payable_minutes"] == 235
    assert metrics["payable_minutes"] == 235
    assert metrics["payable_hours"] == 3.92
    assert metrics["overtime_status"] == "Chờ duyệt"
    approved = attendance_metrics({"start_time":"08:00","end_time":"12:00"}, "07:50", "12:10", approve_overtime=True)
    assert approved["base_payable_minutes"] == 240
    assert approved["payable_minutes"] == 250

    sample_shift = {"shift_date":"2026-07-05","start_time":"08:00","end_time":"16:00"}
    tz = ZoneInfo("Asia/Ho_Chi_Minh")
    assert classify_shift_attendance(sample_shift, None, {}, datetime(2026,7,5,8,3,tzinfo=tz))["status"] == "Đến giờ chấm công"
    assert classify_shift_attendance(sample_shift, None, {}, datetime(2026,7,5,8,18,tzinfo=tz))["status"] == "Đi trễ chưa chấm"
    assert classify_shift_attendance(sample_shift, None, {}, datetime(2026,7,5,9,0,tzinfo=tz))["status"] == "Nguy cơ vắng ca"
    assert classify_shift_attendance(sample_shift, None, {}, datetime(2026,7,5,16,1,tzinfo=tz))["status"] == "Vắng ca"
    assert classify_shift_attendance(sample_shift, {"check_in":"08:02"}, {}, datetime(2026,7,5,16,30,tzinfo=tz))["status"] == "Đến giờ chấm ra"
    assert classify_shift_attendance(sample_shift, {"check_in":"08:02"}, {"checkout_after_minutes":5}, datetime(2026,7,5,16,6,tzinfo=tz))["status"] == "Thiếu giờ ra"

    # Official shifts must remain visible in payroll even before attendance exists.
    future_payroll = RumiHandler.payroll_from_rows(
        None,
        [{"id": 1, "code": "NV001", "name": "Nguyễn An", "role": "Pha chế", "hourly_wage": 25000}],
        [], [], [],
        [{"id": 99, "employee_id": 1, "shift_date": "2099-07-05", "start_time": "08:00", "end_time": "16:00", "status": "Đã xếp"}],
    )[0]
    assert future_payroll["scheduled_shift_count"] == 1
    assert future_payroll["scheduled_hours"] == 8
    assert future_payroll["completed_shift_count"] == 0
    assert future_payroll["payable_hours"] == 0
    assert future_payroll["estimated_salary"] == 200000
    assert future_payroll["payroll_state"] == "Chưa đến ca"
    assert not future_payroll["eligible_for_payment"]

    employee = {
        "id": 1, "status": "Đang làm", "role": "Pha chế", "employment_type": "Full-time",
        "weekly_target_hours": 48, "max_weekly_hours": 48, "max_daily_hours": 8,
        "max_consecutive_days": 6, "weekly_days_off": 1,
    }
    opening = {"work_date":"2026-07-06","start_time":"08:00","end_time":"16:00","required_role":"Pha chế","eligible_employment_type":"Tất cả"}
    rule = RumiHandler.employee_shift_rule(None, employee, opening, [], [], [])
    assert rule["allowed"] and rule["projected_week_hours"] == 8
    six_days = [{"employee_id":1,"shift_date":f"2026-07-{day:02d}","start_time":"08:00","end_time":"16:00","status":"Đã xếp"} for day in range(6,12)]
    blocked = RumiHandler.employee_shift_rule(None, employee, {**opening,"work_date":"2026-07-12"}, six_days, [], [])
    assert not blocked["allowed"] and any("nghỉ" in reason for reason in blocked["reasons"])

    workbook = build_schedule_week_xlsx(
        [{
            "employee_id": 1, "employee_code": "NV001", "employee_name": "Nguyễn An",
            "employee_role": "Pha chế", "shift_date": "2026-07-06", "start_time": "08:00",
            "end_time": "16:00", "location_name": "RUMI", "location_address": "Cửa hàng",
            "status": "Đã xếp", "note": "",
        }],
        [{"id": 1, "code": "NV001", "name": "Nguyễn An", "role": "Pha chế"}],
        "2026-07-06", "2026-07-12", "RUMI", "Admin",
    )
    assert workbook.startswith(b"PK")
    with ZipFile(BytesIO(workbook)) as archive:
        names = set(archive.namelist())
        assert "xl/worksheets/sheet1.xml" in names
        assert "xl/worksheets/sheet2.xml" in names

    print("✓ PBKDF2-HMAC-SHA256 600.000 vòng và chính sách mật khẩu")
    print("✓ Chữ ký phiên đăng nhập")
    print("✓ Kiểm tra trùng ca")
    print("✓ Tính giờ lương theo khung ca; tăng ca phải duyệt")
    print("✓ Ca chính thức vẫn hiện trong bảng lương trước khi chấm công")
    print("✓ Cảnh báo đến giờ, đi trễ, nguy cơ vắng, vắng ca và thiếu giờ ra")
    print("✓ Luật Full-time 6 ngày làm + 1 ngày nghỉ")
    print("✓ Xuất lịch tuần Excel 2 sheet")
    print("Self-test hoàn tất.")


if __name__ == "__main__":
    main()
