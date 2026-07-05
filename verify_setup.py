#!/usr/bin/env python3
"""Verify RUMI v6.4.2 Supabase objects without changing business data."""
from server import APIError, SB, SUPABASE_URL, TABLES, now_iso, validate_config


def main():
    validate_config()
    print(f"Supabase: {SUPABASE_URL}")
    print("Kiểm tra bảng RUMI v6.4.2...")
    ok = 0
    for table in TABLES.values():
        try:
            SB.select(table, limit=1, columns="id")
            print(f"  ✓ {table}")
            ok += 1
        except APIError as exc:
            print(f"  ✗ {table}: {exc}")
    print(f"\nKết quả: {ok}/{len(TABLES)} bảng truy cập được.")
    if ok != len(TABLES):
        print("Chạy đầy đủ migration đến sql/SUPABASE_RUMI_V6_4_2_ADMIN_CONTROL.sql.")
        raise SystemExit(1)

    # Read-only function discovery is not available through PostgREST, so call
    # the harmless clear-failure RPC with a unique key.
    try:
        SB.rpc("rumi_auth_clear_failures", {"p_key_hash": "rumi-v55-verify", "p_user_id": None, "p_now": now_iso()})
        print("  ✓ RPC bảo mật v5.5")
    except APIError as exc:
        print(f"  ✗ RPC v5.5: {exc}")
        raise SystemExit(1)
    try:
        SB.rpc("rumi_refresh_weekly_shift_request", {"p_request_id": 0})
        SB.select(TABLES["weekly_requests"], limit=1, columns="id,selected_days,selected_shifts,approved_shifts")
        SB.select(TABLES["withdrawals"], limit=1, columns="id,deleted_at,deleted_by,delete_reason")
        SB.select(TABLES["shift_reassignments"], limit=1, columns="id,shift_id,new_application_id")
        print("  ✓ Ca đôi, xóa lịch sử mềm và đổi nhân viên v6.4.2")
    except APIError as exc:
        print(f"  ✗ Migration v6.4.2: {exc}")
        raise SystemExit(1)
    print("RUMI v6.4.2 đã sẵn sàng.")


if __name__ == "__main__":
    main()
