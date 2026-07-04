#!/usr/bin/env python3
"""Verify the RUMI v4 tables in Supabase without changing data."""
from server import SB, TABLES, SUPABASE_KEY, SUPABASE_URL, validate_config, APIError


def main():
    validate_config()
    print(f"Supabase: {SUPABASE_URL}")
    print("Kiểm tra các bảng RUMI v4...")
    ok = 0
    for label, table in TABLES.items():
        try:
            SB.select(table, limit=1, columns="id")
            print(f"  ✓ {table}")
            ok += 1
        except APIError as exc:
            print(f"  ✗ {table}: {exc}")
    print(f"\nKết quả: {ok}/{len(TABLES)} bảng truy cập được.")
    if ok != len(TABLES):
        print("Hãy chạy lại sql/SUPABASE_RUMI_V4_FULL.sql trong Supabase SQL Editor.")
        raise SystemExit(1)
    print("Cấu hình cơ sở dữ liệu RUMI v4 đã sẵn sàng.")


if __name__ == "__main__":
    main()
