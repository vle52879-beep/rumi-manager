#!/usr/bin/env python3
"""Offline checks for core security and scheduling helpers."""
from server import password_hash, verify_password, make_session, parse_session, overlaps, calculate_hours, attendance_metrics


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
    print("✓ Băm mật khẩu PBKDF2")
    print("✓ Chữ ký phiên đăng nhập")
    print("✓ Kiểm tra trùng ca")
    print("✓ Tính giờ công, đi trễ và tăng ca")
    print("Self-test hoàn tất.")


if __name__ == "__main__":
    main()
