#!/usr/bin/env python3
"""Verify RUMI v5.5 Supabase objects without changing business data."""
from server import APIError, SB, SUPABASE_URL, TABLES, now_iso, validate_config


def main():
    validate_config()
    print(f"Supabase: {SUPABASE_URL}")
    print("Kiểm tra bảng RUMI v5.5...")
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
        print("Chạy SQL v4 → v5.3 → v5.4 → sql/SUPABASE_RUMI_V5_5_SECURITY_ATTENDANCE.sql.")
        raise SystemExit(1)

    # Read-only function discovery is not available through PostgREST, so call
    # the harmless clear-failure RPC with a unique key.
    try:
        SB.rpc("rumi_auth_clear_failures", {"p_key_hash": "rumi-v55-verify", "p_user_id": None, "p_now": now_iso()})
        print("  ✓ RPC bảo mật v5.5")
    except APIError as exc:
        print(f"  ✗ RPC v5.5: {exc}")
        raise SystemExit(1)
    print("RUMI v5.5 đã sẵn sàng.")


if __name__ == "__main__":
    main()
