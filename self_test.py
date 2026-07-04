#!/usr/bin/env python3
"""Offline checks for security, scheduling, payroll metrics and Excel export."""
from io import BytesIO
from zipfile import ZipFile

from excel_export import build_schedule_week_xlsx
from server import attendance_metrics, calculate_hours, make_session, overlaps, parse_session, password_hash, verify_password


def main():
    digest, salt = password_hash("MatKhauAnToan123")
    assert verify_password("MatKhauAnToan123", digest, salt)
    assert not verify_password("sai", digest, salt)
    token = make_session(42)
    assert parse_session(token) == 42
    assert parse_session(token + "x") is None
    assert overlaps("08:00", "12:00", "11:00", "13:00")
    assert not overlaps("08:00", "12:00", "12:00", "13:00")
    assert calculate_hours("08:00", "12:30") == 4.5
    metrics = attendance_metrics({"start_time":"08:00","end_time":"12:00"}, "08:05", "12:10")
    assert metrics["late_minutes"] == 5
    assert metrics["overtime_minutes"] == 10
    assert metrics["payable_hours"] == 4.08

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

    print("✓ Băm mật khẩu PBKDF2")
    print("✓ Chữ ký phiên đăng nhập")
    print("✓ Kiểm tra trùng ca")
    print("✓ Tính giờ công, đi trễ và tăng ca")
    print("✓ Xuất lịch tuần Excel 2 sheet")
    print("Self-test hoàn tất.")


if __name__ == "__main__":
    main()
